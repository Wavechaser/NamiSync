"""Installed-wheel child processes for the real WebView2 host gates."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import sys
import threading
import time
import webbrowser
from collections.abc import Callable, Mapping
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal
from unittest.mock import patch

from _headed_evidence import (
    EvidencePaths,
    EvidenceProtocolError,
    EvidencePublisher,
)
from _startup_test_support import headed_command_extension


_SETTINGS = (
    "OPEN_EXTERNAL_LINKS_IN_BROWSER",
    "ALLOW_FILE_URLS",
    "ALLOW_DOWNLOADS",
    "REMOTE_DEBUGGING_PORT",
)
_POISONED_SETTINGS = {
    "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,
    "ALLOW_FILE_URLS": True,
    "ALLOW_DOWNLOADS": True,
    "REMOTE_DEBUGGING_PORT": 9222,
}
_OFF_ORIGIN_COMMITTED = "https://example.invalid/committed"
_MANAGED_URL_POISON = "https://example.invalid/managed-url-poison"
_PACKAGED_POPUP_SCRIPT = r"""
(() => {
  if (window.__namiPackagedPopupGate) {
    return;
  }
  const state = {
    stage: 0,
    readyCount: 0,
    initialUrl: window.location.href,
    documentToken: "packaged-" + Math.random().toString(16).slice(2),
  };
  window.__namiPackagedPopupGate = state;
  const onReady = async () => {
    state.readyCount += 1;
    if (state.stage === 0) {
      state.stage = 1;
      window.open("https://example.invalid/packaged-popup");
      return;
    }
    if (state.stage !== 1) {
      return;
    }
    state.stage = 2;
    const bridge = await import("./bridge.js");
    await bridge.whenBridgeReady();
    const result = await bridge.dispatchInteractive(
      "packaged_probe",
      Object.freeze({
        initial_url: state.initialUrl,
        final_url: window.location.href,
        document_token: state.documentToken,
        ready_count: state.readyCount,
      }),
      (value) => value !== null
        && typeof value === "object"
        && !Array.isArray(value)
        && Object.keys(value).length === 1
        && value.token === "packaged-popup-ok",
    );
    document.getElementById("host-status").textContent =
      result.token === "packaged-popup-ok"
        ? "Packaged popup gate passed"
        : "Packaged popup gate failed";
  };
  window.addEventListener("pywebviewready", onReady);
  if (window.pywebview?.api?.dispatch) {
    void onReady();
  }
})();
"""


class _Recorder:
    def __init__(self, evidence_root: Path, mode: str) -> None:
        self.publisher = EvidencePublisher(EvidencePaths(evidence_root))
        self.lock = threading.Lock()
        self.initial: Literal["ready", "failure"] | None = None
        self.final_published = False
        self.data: dict[str, Any] = {
            "schema_version": 1,
            "mode": mode,
            "events": [],
            "startup_errors": [],
        }

    def event(self, name: str, **details: Any) -> None:
        record = {
            "name": name,
            "at": time.monotonic(),
            "thread": threading.get_ident(),
            **details,
        }
        with self.lock:
            self.data["events"].append(record)

    def set(self, name: str, value: Any) -> None:
        with self.lock:
            self.data[name] = value

    def append(self, name: str, value: Any) -> None:
        with self.lock:
            self.data.setdefault(name, []).append(value)

    def get(self, name: str, default: Any = None) -> Any:
        with self.lock:
            return self.data.get(name, default)

    def startup_error(self, message: str) -> None:
        self.append("startup_errors", message)

    def publish_ready(self) -> None:
        with self.lock:
            if self.initial is not None or self.final_published:
                raise EvidenceProtocolError(
                    "native gate ready evidence was already settled"
                )
            payload = deepcopy(self.data)
            self.publisher.publish_ready(payload)
            self.initial = "ready"

    def publish_final(self, payload: dict[str, object] | None = None) -> None:
        with self.lock:
            if self.final_published:
                raise EvidenceProtocolError(
                    "native gate final evidence was already published"
                )
            if payload is None:
                payload = deepcopy(self.data)
            self.publisher.publish_final(payload)
            self.final_published = True

    def publish_failure(self, error: BaseException) -> None:
        with self.lock:
            if self.initial == "failure" or self.final_published:
                return
            self.data["child_failure"] = {
                "type": type(error).__name__,
                "message": str(error),
            }
            payload = deepcopy(self.data)
            if self.initial == "ready":
                self.publisher.publish_final(payload)
                self.final_published = True
            else:
                self.publisher.publish_failure(payload)
                self.initial = "failure"


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=(
            "live",
            "packaged-popup",
            "attachment-failure",
            "runtime-refusal",
        ),
        required=True,
    )
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    return parser.parse_args()


def _runtime_identity() -> dict[str, Any]:
    import namisync

    return {
        "python": sys.version,
        "python_info": list(sys.version_info[:3]),
        "executable": sys.executable,
        "namisync_file": str(Path(namisync.__file__).resolve()),
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("namisync", "pywebview", "pythonnet")
        },
        "entry_points": sorted(
            (
                {
                    "group": entry.group,
                    "name": entry.name,
                    "value": entry.value,
                }
                for entry in importlib.metadata.entry_points()
                if entry.name in {"nami-sync", "nami-sync-gui"}
            ),
            key=lambda entry: (entry["group"], entry["name"]),
        ),
    }


def _settings_snapshot(module: object) -> dict[str, object]:
    settings = getattr(module, "settings")
    return {name: settings[name] for name in _SETTINGS}


def _document_url(document: object) -> str:
    lock = getattr(document, "_lock")
    with lock:
        return str(getattr(document, "_current_url"))


def _event_uri(arguments: object) -> str:
    getter = getattr(arguments, "get_Uri", None)
    if callable(getter):
        return str(getter())
    return str(getattr(arguments, "Uri", ""))


def _event_flag(arguments: object, name: str) -> bool:
    getter = getattr(arguments, f"get_{name}", None)
    if callable(getter):
        return bool(getter())
    return bool(getattr(arguments, name, False))


def _transport_evidence() -> dict[str, object]:
    import webview
    import webview.util
    import webview.window

    package = Path(webview.__file__).resolve().parent
    util_source = inspect.getsource(webview.util.js_bridge_call)
    api_source = (package / "js" / "api.js").read_text(encoding="utf-8")
    backend_source = (package / "platforms" / "edgechromium.py").read_text(
        encoding="utf-8"
    )
    return {
        "webview_file": str(Path(webview.__file__).resolve()),
        "util_file": str(Path(inspect.getfile(webview.util.js_bridge_call)).resolve()),
        "window_file": str(Path(inspect.getfile(webview.window.Window)).resolve()),
        "js_bridge_call_sha256": hashlib.sha256(
            util_source.encode("utf-8")
        ).hexdigest(),
        "api_js_sha256": hashlib.sha256(api_source.encode("utf-8")).hexdigest(),
        "uses_js_bridge_call": "js_bridge_call(" in backend_source,
        "edge_backend_sha256": hashlib.sha256(
            backend_source.encode("utf-8")
        ).hexdigest(),
        "uses_window_evaluate_js": "window.evaluate_js(" in util_source,
        "uses_return_callback_table": (
            "_returnValuesCallbacks" in util_source
            and "_returnValuesCallbacks" in api_source
        ),
        "uses_structured_json_result": (
            "json.dumps(result)" in util_source
            and "JSON.parse(value)" in api_source
        ),
    }


def _install_module_observers(
    host: object,
    recorder: _Recorder,
    runtime: dict[str, Any],
) -> Callable[[], object]:
    original_load = host._load_webview

    def load_webview() -> object:
        recorder.event("load_webview.begin")
        module = original_load()
        for name, value in _POISONED_SETTINGS.items():
            module.settings[name] = value
        recorder.set("settings_before_prepare", _settings_snapshot(module))
        recorder.set("transport", _transport_evidence())
        recorder.event("load_webview.end")
        runtime["webview"] = module

        original_create = module.create_window
        original_start = module.start
        popup_wrapped = False

        def create_window(*args: object, **kwargs: object) -> object:
            nonlocal popup_wrapped
            if not popup_wrapped:
                from webview.platforms.edgechromium import EdgeChrome

                original_popup = EdgeChrome.on_new_window_request

                def observe_pywebview_popup(
                    backend: object,
                    sender: object,
                    arguments: object,
                ) -> object:
                    uri = _event_uri(arguments)
                    recorder.event(
                        "pywebview_popup.begin",
                        uri=uri,
                        handled=_event_flag(arguments, "Handled"),
                    )
                    try:
                        return original_popup(backend, sender, arguments)
                    finally:
                        recorder.event(
                            "pywebview_popup.end",
                            uri=uri,
                            handled=_event_flag(arguments, "Handled"),
                        )

                EdgeChrome.on_new_window_request = observe_pywebview_popup
                popup_wrapped = True
            recorder.event(
                "create_window.begin",
                index=str(args[1]) if len(args) > 1 else str(kwargs.get("url")),
                width=kwargs.get("width"),
                height=kwargs.get("height"),
                min_size=list(kwargs["min_size"]),
                settings=_settings_snapshot(module),
            )
            window = original_create(*args, **kwargs)
            runtime["original_get_current_url"] = window.get_current_url
            original_evaluate = window.evaluate_js
            delayed_evaluate = threading.Event()
            runtime["delayed_evaluate"] = delayed_evaluate

            def observe_evaluate_js(
                script: str,
                callback: Callable[..., Any] | None = None,
            ) -> object:
                is_delayed_return = (
                    recorder.get("delayed_handler_completed", False)
                    and "_returnValuesCallbacks" in script
                    and not delayed_evaluate.is_set()
                )
                if is_delayed_return:
                    recorder.event("delayed_return.evaluate.begin")
                try:
                    return original_evaluate(script, callback)
                except BaseException as error:
                    if is_delayed_return:
                        recorder.set(
                            "delayed_return_evaluate_error",
                            type(error).__name__,
                        )
                    raise
                finally:
                    if is_delayed_return:
                        recorder.event("delayed_return.evaluate.end")
                        delayed_evaluate.set()

            window.evaluate_js = observe_evaluate_js
            runtime["window"] = window
            recorder.event("create_window.end")
            return window

        def start(*args: object, **kwargs: object) -> object:
            recorder.event(
                "webview.start",
                gui=kwargs.get("gui"),
                debug=kwargs.get("debug"),
                http_server=kwargs.get("http_server"),
                private_mode=kwargs.get("private_mode"),
                storage_path=str(kwargs.get("storage_path")),
                settings=_settings_snapshot(module),
            )
            return original_start(*args, **kwargs)

        module.create_window = create_window
        module.start = start
        return module

    return load_webview


def _install_native_observer(
    host: object,
    recorder: _Recorder,
    runtime: dict[str, Any],
) -> Callable[..., None]:
    original = host._configure_window_security

    def configure(
        window: object,
        trusted_url: str,
        document: object,
        renderer_callback: Callable[[str], None],
    ) -> None:
        recorder.event("configure_security.begin", trusted_url=trusted_url)
        recorder.set("trusted_url", trusted_url)

        def before_production_guard() -> None:
            recorder.event("before_load.enter")

        window.events.before_load += before_production_guard
        original(window, trusted_url, document, renderer_callback)
        observed = False

        def observe_before_load() -> None:
            nonlocal observed
            if observed:
                return
            observed = True
            native = window.native
            core = native.browser.webview.CoreWebView2
            browser_version = str(core.Environment.BrowserVersionString)
            recorder.event(
                "before_load.after",
                invoke_required=bool(native.InvokeRequired),
                core_type=str(type(core)),
                browser_version=browser_version,
                source=str(core.Source),
            )
            recorder.set("browser_version", browser_version)
            recorder.set("native_core_type", str(type(core)))

            def subscription_probe(sender: object, arguments: object) -> None:
                del sender, arguments

            core.SourceChanged += subscription_probe
            core.SourceChanged -= subscription_probe
            recorder.set(
                "pythonnet_event_subscription",
                {"add": True, "remove": True},
            )

            def navigation(sender: object, arguments: object) -> None:
                del sender
                uri = _event_uri(arguments)
                cancel = _event_flag(arguments, "Cancel")
                recorder.append(
                    "top_level_navigation",
                    {
                        "uri": uri,
                        "cancel": cancel,
                        "at": time.monotonic(),
                        "thread": threading.get_ident(),
                    },
                )
                if uri.startswith("https://example.invalid/") and not cancel:
                    raise RuntimeError(
                        "production top-level guard did not cancel the native event"
                    )

            def frame_navigation(sender: object, arguments: object) -> None:
                del sender
                uri = _event_uri(arguments)
                cancel = _event_flag(arguments, "Cancel")
                recorder.append(
                    "frame_navigation",
                    {
                        "uri": uri,
                        "cancel": cancel,
                        "at": time.monotonic(),
                        "thread": threading.get_ident(),
                    },
                )
                if uri.startswith("https://example.invalid/") and not cancel:
                    raise RuntimeError(
                        "production frame guard did not cancel the native event"
                    )

            def new_window(sender: object, arguments: object) -> None:
                del sender
                uri = _event_uri(arguments)
                handled = _event_flag(arguments, "Handled")
                recorder.append(
                    "new_window",
                    {
                        "uri": uri,
                        "handled": handled,
                        "at": time.monotonic(),
                        "thread": threading.get_ident(),
                    },
                )
                if uri.startswith("https://example.invalid/") and not handled:
                    raise RuntimeError(
                        "production popup guard did not handle the native event"
                    )

            def source_changed(sender: object, arguments: object) -> None:
                del arguments
                recorder.append(
                    "native_source_changes",
                    {
                        "source": str(sender.Source),
                        "at": time.monotonic(),
                        "thread": threading.get_ident(),
                    },
                )

            core.NavigationStarting += navigation
            core.FrameNavigationStarting += frame_navigation
            core.NewWindowRequested += new_window
            core.SourceChanged += source_changed
            runtime["native_handlers"] = (
                subscription_probe,
                navigation,
                frame_navigation,
                new_window,
                source_changed,
            )

        window.events.before_load += observe_before_load

        def observe_bridge_ready() -> None:
            count = int(runtime.get("bridge_ready_count", 0)) + 1
            runtime["bridge_ready_count"] = count
            recorder.event("pywebviewready", count=count)
            if count >= 2:
                ready = runtime.setdefault("reinjection_ready", threading.Event())
                ready.set()

        window.events._pywebviewready += observe_bridge_ready
        recorder.event("configure_security.end")

    return configure


def _run_live(arguments: argparse.Namespace, recorder: _Recorder) -> int:
    from namisync.interfaces.web import bridge, host
    from namisync.interfaces.web.commands import (
        CommandAccess,
        CommandRetry,
        CommandSpec,
        CommandTimeout,
        FieldRequirement,
    )
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    runtime: dict[str, Any] = {}

    def test_spec(handler: Callable[[object], object]) -> CommandSpec:
        return CommandSpec(
            validate_payload=lambda payload: payload,
            handler=handler,
            access=CommandAccess.READ_ONLY,
            command_id=FieldRequirement.FORBIDDEN,
            revision=FieldRequirement.FORBIDDEN,
            timeout=CommandTimeout.INTERACTIVE,
            retry=CommandRetry.NONE,
        )
    recorder.set("runtime", _runtime_identity())
    recorder.set("input_index", str(arguments.index.resolve()))
    recorder.set("input_data_root", str(arguments.data_dir.resolve()))

    original_prepare = bridge.prepare_pywebview_host
    original_guard_attach = bridge._NativeNavigationGuard.attach
    original_nami_navigation = (
        bridge._NativeNavigationGuard._on_navigation_starting
    )
    original_nami_frame = bridge._NativeNavigationGuard._on_frame_navigation_starting
    original_nami_popup = bridge._NativeNavigationGuard._on_new_window_requested
    original_nami_source = bridge._NativeNavigationGuard._on_source_changed

    def prepare(module: object) -> None:
        recorder.event("prepare.begin")
        original_prepare(module)
        recorder.append("prepare_settings", _settings_snapshot(module))
        recorder.event("prepare.end")

    def attach(guard: object, core: object) -> None:
        recorder.event(
            "guard_attach.begin",
            core_type=str(type(core)),
        )
        original_guard_attach(guard, core)
        recorder.event("guard_attach.end")

    def observe_nami_popup(
        guard: object,
        sender: object,
        event_arguments: object,
    ) -> None:
        uri = _event_uri(event_arguments)
        recorder.event(
            "nami_popup.begin",
            uri=uri,
            handled=_event_flag(event_arguments, "Handled"),
        )
        try:
            original_nami_popup(guard, sender, event_arguments)
        finally:
            recorder.event(
                "nami_popup.end",
                uri=uri,
                handled=_event_flag(event_arguments, "Handled"),
            )

    def observe_nami_navigation(
        guard: object,
        sender: object,
        event_arguments: object,
    ) -> None:
        uri = _event_uri(event_arguments)
        recorder.event(
            "nami_navigation.begin",
            uri=uri,
            cancel=_event_flag(event_arguments, "Cancel"),
        )
        try:
            original_nami_navigation(guard, sender, event_arguments)
        finally:
            recorder.event(
                "nami_navigation.end",
                uri=uri,
                cancel=_event_flag(event_arguments, "Cancel"),
            )

    def observe_nami_frame(
        guard: object,
        sender: object,
        event_arguments: object,
    ) -> None:
        uri = _event_uri(event_arguments)
        recorder.event(
            "nami_frame.begin",
            uri=uri,
            cancel=_event_flag(event_arguments, "Cancel"),
        )
        try:
            original_nami_frame(guard, sender, event_arguments)
        finally:
            recorder.event(
                "nami_frame.end",
                uri=uri,
                cancel=_event_flag(event_arguments, "Cancel"),
            )

    def observe_nami_source(
        guard: object,
        sender: object,
        event_arguments: object,
    ) -> None:
        source = str(getattr(sender, "Source", ""))
        recorder.event("nami_source.begin", source=source)
        try:
            original_nami_source(guard, sender, event_arguments)
        finally:
            document = document_holder.get("value")
            recorder.event(
                "nami_source.end",
                source=source,
                document_url=(
                    None if document is None else _document_url(document)
                ),
            )

    dispatcher_holder: dict[str, object] = {}
    document_holder: dict[str, object] = {}
    delayed_handler_started = threading.Event()

    def extension(document: object, _registry: object) -> dict[str, object]:
        document_holder["value"] = document

        def native_probe(payload: Mapping[str, object]) -> object:
            phase = str(payload.get("phase"))
            recorder.event("dispatch", phase=phase)
            if phase == "inner_must_not_run":
                recorder.set("off_origin_inner_handler_called", True)
                return {"unexpected": True}
            if phase == "delayed_return":
                delayed_handler_started.set()
                reinjection_ready = runtime.setdefault(
                    "reinjection_ready",
                    threading.Event(),
                )
                if not reinjection_ready.wait(10.0):
                    raise RuntimeError("native reinjection was not observed")
                original_get_current_url = runtime["original_get_current_url"]
                measured_managed_url = original_get_current_url()
                recorder.set(
                    "off_thread_current_url_after_cancel",
                    {
                        "thread": threading.get_ident(),
                        "value": (
                            ""
                            if measured_managed_url is None
                            else str(measured_managed_url)
                        ),
                    },
                )

                def poisoned_get_current_url() -> str:
                    return _MANAGED_URL_POISON

                window = runtime["window"]
                window.get_current_url = poisoned_get_current_url
                recorder.set("delayed_handler_completed", True)
                recorder.event("delayed_handler.complete")
            elif phase == "wait_delayed_started":
                if not delayed_handler_started.wait(10.0):
                    raise RuntimeError("delayed bridge handler did not start")
            elif phase == "wait_delayed_transport":
                delayed_evaluate = runtime.get("delayed_evaluate")
                if not isinstance(delayed_evaluate, threading.Event):
                    raise RuntimeError("delayed return transport was not instrumented")
                if not delayed_evaluate.wait(10.0):
                    raise RuntimeError("delayed return transport was not attempted")
                recorder.event("delayed_transport.ack")

            window = runtime["window"]
            managed_url = window.get_current_url()
            document_url = _document_url(document)
            result: dict[str, object] = {
                "phase": phase,
                "token": f"returned-{phase}",
                "handler_thread": threading.get_ident(),
                "managed_url": "" if managed_url is None else str(managed_url),
                "native_cached_url": document_url,
                "document_attached": bool(document.is_attached),
                "page_document_token": payload.get("document_token"),
                "page_ready_count": payload.get("ready_count"),
                "page_url": payload.get("page_url"),
                "popup_return": payload.get("popup_return"),
            }
            if phase == "wait_delayed_transport":
                result["delayed_evaluate_observed"] = True
                result["delayed_evaluate_error"] = recorder.get(
                    "delayed_return_evaluate_error"
                )

            if phase == "off_origin_refusal":
                previous = document_url
                document._record(_OFF_ORIGIN_COMMITTED)
                nested_called_before = bool(
                    recorder.get("off_origin_inner_handler_called", False)
                )
                try:
                    refusal = dispatcher_holder["value"].dispatch(
                        json.dumps(
                            {
                                "schema_version": 1,
                                "request_id": "7b" * 16,
                                "command": "native_probe",
                                "payload": {"phase": "inner_must_not_run"},
                            }
                        )
                    )
                    result["injected_committed_source_refusal"] = {
                        "response": refusal,
                        "inner_handler_called": bool(
                            recorder.get(
                                "off_origin_inner_handler_called",
                                False,
                            )
                        )
                        and not nested_called_before,
                    }
                finally:
                    document._record(previous)

            if phase == "complete":
                recorder.set("page", dict(payload))
                module = runtime.get("webview")
                recorder.set(
                    "renderer",
                    None if module is None else module.renderer,
                )
                recorder.set(
                    "system_browser_calls",
                    recorder.get("system_browser_calls", []),
                )
                recorder.publish_ready()
            return result

        return {"native_probe": test_spec(native_probe)}

    def observe_composition(production: object, combined: object) -> None:
        recorder.set("production_command_names", sorted(production))
        recorder.set("combined_command_names", sorted(combined))
        recorder.set("combined_mapping_type", type(combined).__name__)

    def observe_dispatcher(dispatcher: object) -> None:
        dispatcher_holder["value"] = dispatcher

    def browser_open(*values: object, **keywords: object) -> bool:
        recorder.append(
            "system_browser_calls",
            {"args": [str(value) for value in values], "kwargs": keywords},
        )
        return False

    with ExitStack() as stack:
        stack.enter_context(patch.object(bridge, "prepare_pywebview_host", prepare))
        stack.enter_context(
            patch.object(bridge._NativeNavigationGuard, "attach", attach)
        )
        stack.enter_context(
            patch.object(
                bridge._NativeNavigationGuard,
                "_on_navigation_starting",
                observe_nami_navigation,
            )
        )
        stack.enter_context(
            patch.object(
                bridge._NativeNavigationGuard,
                "_on_frame_navigation_starting",
                observe_nami_frame,
            )
        )
        stack.enter_context(
            patch.object(
                bridge._NativeNavigationGuard,
                "_on_new_window_requested",
                observe_nami_popup,
            )
        )
        stack.enter_context(
            patch.object(
                bridge._NativeNavigationGuard,
                "_on_source_changed",
                observe_nami_source,
            )
        )
        stack.enter_context(
            patch.object(
                host,
                "_load_webview",
                _install_module_observers(host, recorder, runtime),
            )
        )
        stack.enter_context(
            patch.object(
                host,
                "_configure_window_security",
                _install_native_observer(host, recorder, runtime),
            )
        )
        stack.enter_context(
            headed_command_extension(
                host,
                extension,
                observe_composition=observe_composition,
                observe_dispatcher=observe_dispatcher,
            )
        )
        stack.enter_context(patch.object(webbrowser, "open", browser_open))
        exit_code = host.run_desktop(
            AppPaths.from_root(arguments.data_dir),
            DesktopInstanceIdentity(arguments.mutex, arguments.title),
            startup_error=recorder.startup_error,
            index_path=arguments.index,
        )

    recorder.publish_final({"host_returned": True, "exit_code": exit_code})
    return exit_code


def _run_attachment_failure(
    arguments: argparse.Namespace,
    recorder: _Recorder,
) -> int:
    from namisync.interfaces.web import bridge, host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    runtime: dict[str, object] = {}
    recorder.set("runtime", _runtime_identity())
    document_holder: dict[str, object] = {}
    original_pending = host._pending_document
    original_load = host._load_webview
    original_configure = host._configure_window_security
    original_native_close = host._post_native_window_close

    def pending_document() -> object:
        document = original_pending()
        document_holder["value"] = document
        return document

    def load_webview() -> object:
        module = original_load()
        recorder.set("transport", _transport_evidence())
        original_create = module.create_window

        def create_window(*args: object, **kwargs: object) -> object:
            window = original_create(*args, **kwargs)

            def observe_destroy(*values: object, **keywords: object) -> object:
                del values, keywords
                recorder.event("attachment.window.destroy")
                raise RuntimeError("native gate injected public destroy failure")

            window.destroy = observe_destroy
            runtime["window"] = window
            return window

        module.create_window = create_window
        return module

    def native_close(window: object) -> None:
        recorder.event("attachment.window.native_close")
        original_native_close(window)

    def fail_attachment(guard: object, core: object) -> None:
        del guard, core
        recorder.event("attachment.guard.fail")
        raise bridge._AttachmentError("native gate injected attachment failure")

    def configure(
        window: object,
        trusted_url: str,
        document: object,
        renderer_callback: Callable[[str], None],
    ) -> None:
        def before_failure() -> None:
            recorder.event("attachment.before_load.enter")

        window.events.before_load += before_failure
        original_configure(
            window,
            trusted_url,
            document,
            renderer_callback,
        )

        def after_swallowed_failure() -> None:
            recorder.event("attachment.before_load.after")

        window.events.before_load += after_swallowed_failure
        recorder.event("attachment.configure.end")

    with ExitStack() as stack:
        stack.enter_context(patch.object(host, "_pending_document", pending_document))
        stack.enter_context(patch.object(host, "_load_webview", load_webview))
        stack.enter_context(
            patch.object(host, "_configure_window_security", configure)
        )
        stack.enter_context(
            patch.object(host, "_post_native_window_close", native_close)
        )
        stack.enter_context(
            patch.object(
                bridge._NativeNavigationGuard,
                "attach",
                fail_attachment,
            )
        )
        exit_code = host.run_desktop(
            AppPaths.from_root(arguments.data_dir),
            DesktopInstanceIdentity(arguments.mutex, arguments.title),
            startup_error=recorder.startup_error,
            index_path=arguments.index,
        )

    document = document_holder.get("value")
    window = runtime.get("window")
    recorder.set("exit_code", exit_code)
    recorder.set(
        "attachment_error",
        None if document is None else document.attachment_error,
    )
    recorder.set(
        "window_closed",
        bool(window is not None and window.events.closed.is_set()),
    )
    recorder.publish_final()
    return exit_code


def _run_packaged_popup(
    arguments: argparse.Namespace,
    recorder: _Recorder,
) -> int:
    """Invoke the real popup chain from the wheel's packaged index page."""

    from namisync.interfaces.web import bridge, host
    from namisync.interfaces.web.commands import (
        CommandAccess,
        CommandRetry,
        CommandSpec,
        CommandTimeout,
        FieldRequirement,
    )
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    runtime: dict[str, Any] = {}
    recorder.set("runtime", _runtime_identity())
    original_nami_popup = bridge._NativeNavigationGuard._on_new_window_requested
    observed_configure = _install_native_observer(host, recorder, runtime)
    probe_injected = False

    def observe_nami_popup(
        guard: object,
        sender: object,
        event_arguments: object,
    ) -> None:
        uri = _event_uri(event_arguments)
        recorder.event(
            "nami_popup.begin",
            uri=uri,
            handled=_event_flag(event_arguments, "Handled"),
        )
        try:
            original_nami_popup(guard, sender, event_arguments)
        finally:
            recorder.event(
                "nami_popup.end",
                uri=uri,
                handled=_event_flag(event_arguments, "Handled"),
            )

    def configure(
        window: object,
        trusted_url: str,
        document: object,
        renderer_callback: Callable[[str], None],
    ) -> None:
        nonlocal probe_injected
        observed_configure(
            window,
            trusted_url,
            document,
            renderer_callback,
        )

        def execute_packaged_probe() -> None:
            nonlocal probe_injected
            if probe_injected:
                return
            probe_injected = True
            native = window.native
            if native.InvokeRequired:
                raise RuntimeError("packaged popup probe left the WinForms UI thread")
            core = native.browser.webview.CoreWebView2
            recorder.event(
                "packaged_probe.execute",
                source=str(core.Source),
            )
            core.ExecuteScriptAsync(_PACKAGED_POPUP_SCRIPT)

        window.events.before_load += execute_packaged_probe

    def extension(_document: object, _registry: object) -> dict[str, object]:
        def packaged_probe(payload: Mapping[str, object]) -> object:
            recorder.event("dispatch", phase="packaged_popup")
            recorder.set("packaged_page", dict(payload))
            module = runtime.get("webview")
            recorder.set(
                "renderer",
                None if module is None else module.renderer,
            )
            recorder.set(
                "system_browser_calls",
                recorder.get("system_browser_calls", []),
            )
            recorder.publish_ready()
            return {"token": "packaged-popup-ok"}

        spec = CommandSpec(
            validate_payload=lambda payload: payload,
            handler=packaged_probe,
            access=CommandAccess.READ_ONLY,
            command_id=FieldRequirement.FORBIDDEN,
            revision=FieldRequirement.FORBIDDEN,
            timeout=CommandTimeout.INTERACTIVE,
            retry=CommandRetry.NONE,
        )
        return {"packaged_probe": spec}

    def observe_composition(production: object, combined: object) -> None:
        recorder.set("production_command_names", sorted(production))
        recorder.set("combined_command_names", sorted(combined))
        recorder.set("combined_mapping_type", type(combined).__name__)

    def browser_open(*values: object, **keywords: object) -> bool:
        recorder.append(
            "system_browser_calls",
            {"args": [str(value) for value in values], "kwargs": keywords},
        )
        return False

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                host,
                "_load_webview",
                _install_module_observers(host, recorder, runtime),
            )
        )
        stack.enter_context(
            patch.object(host, "_configure_window_security", configure)
        )
        stack.enter_context(
            headed_command_extension(
                host,
                extension,
                observe_composition=observe_composition,
            )
        )
        stack.enter_context(
            patch.object(
                bridge._NativeNavigationGuard,
                "_on_new_window_requested",
                observe_nami_popup,
            )
        )
        stack.enter_context(patch.object(webbrowser, "open", browser_open))
        exit_code = host.run_desktop(
            AppPaths.from_root(arguments.data_dir),
            DesktopInstanceIdentity(arguments.mutex, arguments.title),
            startup_error=recorder.startup_error,
        )

    recorder.publish_final({"host_returned": True, "exit_code": exit_code})
    return exit_code


def _run_runtime_refusal(
    arguments: argparse.Namespace,
    recorder: _Recorder,
) -> int:
    from namisync.interfaces.web import bridge, host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths
    from namisync.interfaces.web.pywebview_runtime import (
        WebView2RefusalReason,
        WebView2RuntimeProbe,
    )
    import namisync.interfaces.web.pywebview_runtime as runtime_probe_module

    recorder.set("runtime", _runtime_identity())
    create_called = False
    original_load = host._load_webview

    def load_webview() -> object:
        module = original_load()
        for name, value in _POISONED_SETTINGS.items():
            module.settings[name] = value
        recorder.set("settings_before_prepare", _settings_snapshot(module))
        recorder.set("transport", _transport_evidence())
        original_create = module.create_window

        def create_window(*args: object, **kwargs: object) -> object:
            nonlocal create_called
            create_called = True
            return original_create(*args, **kwargs)

        module.create_window = create_window
        return module

    unavailable = WebView2RuntimeProbe(
        available=False,
        refusal_reason=WebView2RefusalReason.WEBVIEW2_RUNTIME,
    )
    original_probe = bridge.probe_webview2_runtime

    def observed_probe(settings: Mapping[str, object]) -> WebView2RuntimeProbe:
        recorder.set(
            "settings_at_runtime_probe",
            {name: settings[name] for name in _SETTINGS},
        )
        opens: list[dict[str, object]] = []
        original_open = runtime_probe_module.winreg.OpenKey

        def observe_open(
            hive: object,
            path: str,
            reserved: int = 0,
            access: int = runtime_probe_module.winreg.KEY_READ,
        ) -> object:
            hive_name = (
                "HKCU"
                if hive == runtime_probe_module.winreg.HKEY_CURRENT_USER
                else "HKLM"
                if hive == runtime_probe_module.winreg.HKEY_LOCAL_MACHINE
                else "other"
            )
            opens.append(
                {
                    "hive": hive_name,
                    "path": path,
                    "reserved": reserved,
                    "access": access,
                }
            )
            return original_open(hive, path, reserved, access)

        with patch.object(runtime_probe_module.winreg, "OpenKey", observe_open):
            real_probe = original_probe(settings)
        recorder.set(
            "real_runtime_probe",
            {
                "available": real_probe.available,
                "refusal_reason": (
                    None
                    if real_probe.refusal_reason is None
                    else str(real_probe.refusal_reason)
                ),
            },
        )
        recorder.set("registry_key_read", runtime_probe_module.winreg.KEY_READ)
        recorder.set("registry_opens", opens)
        return unavailable

    with ExitStack() as stack:
        stack.enter_context(patch.object(host, "_load_webview", load_webview))
        stack.enter_context(
            patch.object(bridge, "probe_webview2_runtime", observed_probe)
        )
        exit_code = host.run_desktop(
            AppPaths.from_root(arguments.data_dir),
            DesktopInstanceIdentity(arguments.mutex, arguments.title),
            startup_error=recorder.startup_error,
            index_path=arguments.index,
        )

    recorder.set("exit_code", exit_code)
    recorder.set("create_window_called", create_called)
    recorder.set(
        "platform_modules",
        sorted(
            name
            for name in sys.modules
            if name in {
                "webview.platforms.mshtml",
                "webview.platforms.winforms",
                "webview.platforms.edgechromium",
            }
        ),
    )
    recorder.publish_final()
    return exit_code


def main() -> int:
    arguments = _parse_arguments()
    recorder = _Recorder(arguments.evidence_dir, arguments.mode)
    try:
        if arguments.mode == "live":
            return _run_live(arguments, recorder)
        if arguments.mode == "packaged-popup":
            return _run_packaged_popup(arguments, recorder)
        if arguments.mode == "attachment-failure":
            return _run_attachment_failure(arguments, recorder)
        return _run_runtime_refusal(arguments, recorder)
    except BaseException as error:
        recorder.publish_failure(error)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
