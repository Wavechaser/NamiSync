"""Installed-wheel child composition for the Slice 2 real transport gates."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import sys
import threading
from collections.abc import Mapping
from contextlib import ExitStack
from dataclasses import dataclass, field
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import MappingProxyType
from typing import Any
from unittest.mock import patch


_OPAQUE_ID = re.compile(r"[0-9a-f]{32}")
_SLOT_ID = re.compile(r"slot-[0-9a-f]{32}")
_TASK_ID = re.compile(r"task-[0-9a-f]{32}")


class _Recorder:
    def __init__(self, output: Path, mode: str) -> None:
        self._output = output
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {
            "schema_version": 1,
            "mode": mode,
            "startup_errors": [],
        }

    def set(self, name: str, value: Any) -> None:
        with self._lock:
            self._data[name] = value

    def append(self, name: str, value: Any) -> None:
        with self._lock:
            self._data.setdefault(name, []).append(value)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def startup_error(self, message: str) -> None:
        self.append("startup_errors", message)

    def write(self) -> None:
        with self._lock:
            encoded = json.dumps(self._data, indent=2, sort_keys=True)
            temporary = self._output.with_suffix(self._output.suffix + ".tmp")
            temporary.write_text(encoded, encoding="utf-8")
            temporary.replace(self._output)


@dataclass(frozen=True, slots=True)
class _Report:
    phase: str
    value: Mapping[str, object]


@dataclass(slots=True)
class _DrainProbe:
    entered: threading.Event = field(default_factory=threading.Event)
    exited: threading.Event = field(default_factory=threading.Event)


class _QuietRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        del format, args


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("transport", "off-origin"), required=True)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--scenario", required=True, type=Path)
    return parser.parse_args()


def _read_scenario(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError("transport gate scenario must be an object")
    return value


def _runtime_identity() -> dict[str, object]:
    import namisync

    return {
        "executable": sys.executable,
        "namisync_file": str(Path(namisync.__file__).resolve()),
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("namisync", "pywebview", "pythonnet")
        },
    }


def _test_spec(
    scenario: Mapping[str, object],
    recorder: _Recorder,
    *,
    off_origin_url: str | None,
    drain_probe: _DrainProbe | None,
):
    from namisync.interfaces.web.commands import (
        CommandAccess,
        CommandPayloadError,
        CommandRetry,
        CommandSpec,
        CommandTimeout,
        FieldRequirement,
    )

    def validate(payload: object) -> _Report:
        if type(payload) is not dict or type(payload.get("phase")) is not str:
            raise CommandPayloadError("test report payload is invalid")
        phase = payload["phase"]
        if phase == "hostile" and set(payload) == {"phase"}:
            return _Report(phase, MappingProxyType(dict(payload)))
        if phase == "complete" and set(payload) == {
            "phase",
            "observed",
            "source_id",
            "target_id",
            "source_keys",
            "target_keys",
            "source_display",
            "target_display",
            "plan",
            "dom",
        }:
            observed = payload["observed"]
            source_id = payload["source_id"]
            target_id = payload["target_id"]
            source_keys = payload["source_keys"]
            target_keys = payload["target_keys"]
            source_display = payload["source_display"]
            target_display = payload["target_display"]
            plan = payload["plan"]
            dom = payload["dom"]
            if (
                type(observed) is str
                and type(source_id) is str
                and _SLOT_ID.fullmatch(source_id) is not None
                and type(target_id) is str
                and _SLOT_ID.fullmatch(target_id) is not None
                and source_keys == ["display", "id"]
                and target_keys == ["display", "id"]
                and type(source_display) is str
                and type(target_display) is str
                and type(plan) is dict
                and set(plan) == {"task_id", "request_id", "session_id"}
                and type(plan["task_id"]) is str
                and _TASK_ID.fullmatch(plan["task_id"]) is not None
                and type(plan["request_id"]) is str
                and _OPAQUE_ID.fullmatch(plan["request_id"]) is not None
                and type(plan["session_id"]) is str
                and _OPAQUE_ID.fullmatch(plan["session_id"]) is not None
                and type(dom) is dict
                and set(dom)
                == {
                    "element_children",
                    "script_count_before",
                    "script_count_after",
                    "image_count",
                    "hostile_marker_defined",
                }
                and all(
                    type(dom[name]) is int
                    for name in (
                        "element_children",
                        "script_count_before",
                        "script_count_after",
                        "image_count",
                    )
                )
                and type(dom["hostile_marker_defined"]) is bool
            ):
                return _Report(phase, MappingProxyType(dict(payload)))
        if phase == "off_origin_target" and set(payload) == {"phase"}:
            return _Report(phase, MappingProxyType(dict(payload)))
        if phase == "off_origin_attempt" and set(payload) == {"phase"}:
            return _Report(phase, MappingProxyType(dict(payload)))
        if (
            phase == "drain_probe"
            and set(payload) == {"phase", "drain_settled"}
            and type(payload["drain_settled"]) is bool
            and drain_probe is not None
        ):
            return _Report(phase, MappingProxyType(dict(payload)))
        raise CommandPayloadError("test report payload is invalid")

    def report(value: object) -> object:
        if type(value) is not _Report:
            raise TypeError("test report received unvalidated data")
        if value.phase == "hostile":
            corpus = scenario.get("corpus")
            if type(corpus) is not str:
                raise ValueError("transport gate corpus is invalid")
            return {"corpus": corpus}
        if value.phase == "complete":
            recorder.set("report", dict(value.value))
            recorder.write()
            return {"accepted": True}
        if value.phase == "off_origin_target":
            if off_origin_url is None:
                raise RuntimeError("off-origin server is unavailable")
            return {"url": off_origin_url}
        if value.phase == "drain_probe":
            assert drain_probe is not None
            evidence = {
                "drain_entered": drain_probe.entered.is_set(),
                "drain_exited": drain_probe.exited.is_set(),
                "drain_settled": value.value["drain_settled"],
            }
            recorder.set("drain_probe_report", evidence)
            recorder.write()
            return evidence
        recorder.append("off_origin_handler_calls", dict(value.value))
        recorder.write()
        return {"accepted": True}

    return CommandSpec(
        validate_payload=validate,
        handler=report,
        access=CommandAccess.READ_ONLY,
        command_id=FieldRequirement.FORBIDDEN,
        revision=FieldRequirement.FORBIDDEN,
        timeout=CommandTimeout.INTERACTIVE,
        retry=CommandRetry.NONE,
    )


def _serve_second_origin(root: Path) -> tuple[ThreadingHTTPServer, str]:
    handler = partial(_QuietRequestHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(
        target=server.serve_forever,
        name="namisync-test-second-origin",
        daemon=True,
    )
    thread.start()
    port = int(server.server_address[1])
    return server, f"http://127.0.0.1:{port}/off_origin.html"


def _run(arguments: argparse.Namespace, recorder: _Recorder) -> int:
    from namisync.interfaces.service import NamiSyncService
    from namisync.interfaces.web import bridge, host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    scenario = _read_scenario(arguments.scenario)
    recorder.set("runtime", _runtime_identity())
    recorder.set("off_origin_handler_calls", [])
    original_dispatcher = host._bridge_dispatcher
    original_expose_bridge = host._expose_bridge_api
    original_task_registry = host._task_registry
    original_dispatch = bridge.BridgeDispatcher.dispatch
    original_start_plan = NamiSyncService.start_plan
    original_unsubscribe = NamiSyncService.unsubscribe
    original_log_renderer = host._log_startup_renderer
    original_pending_document = host._pending_document
    original_attach = bridge._NativeNavigationGuard.attach
    original_source_changed = bridge._NativeNavigationGuard._on_source_changed
    original_record_document = bridge.NativeDocumentState._record
    document_holder: dict[str, object] = {}
    drain_probe = _DrainProbe() if arguments.mode == "transport" else None
    second_origin: ThreadingHTTPServer | None = None
    off_origin_url: str | None = None
    if arguments.mode == "off-origin":
        second_origin, off_origin_url = _serve_second_origin(arguments.index.parent)

    def dispatcher(document: object, commands: object) -> object:
        production = dict(commands)
        recorder.set("production_command_names", sorted(production))
        combined = MappingProxyType(
            {
                **production,
                "test_report": _test_spec(
                    scenario,
                    recorder,
                    off_origin_url=off_origin_url,
                    drain_probe=drain_probe,
                ),
            }
        )
        value = original_dispatcher(document, combined)
        recorder.set(
            "dispatcher_type",
            f"{type(value).__module__}.{type(value).__qualname__}",
        )
        recorder.set("combined_command_names", sorted(combined))
        recorder.set("combined_mapping_type", type(combined).__name__)
        return value

    def observed_dispatch(dispatcher: object, command_json: str) -> object:
        response = original_dispatch(dispatcher, command_json)
        if type(command_json) is str:
            recorder.append("raw_dispatch_bodies", command_json)
            if '"phase":"off_origin_attempt"' in command_json:
                recorder.set("off_origin_response", response)
                recorder.write()
        return response

    def expose_bridge(window: object, dispatcher: object) -> None:
        original_expose_bridge(window, dispatcher)
        recorder.set("pywebview_js_api_is_none", window._js_api is None)
        recorder.set("pywebview_function_names", sorted(window._functions))

    def record_document(document: object, current_url: str) -> None:
        recorder.append("document_records", current_url)
        original_record_document(document, current_url)

    def task_registry(service: object) -> object:
        registry = original_task_registry(service)
        if drain_probe is None:
            return registry
        original_drain = registry.drain

        def observed_drain(
            task_id: str,
            session_id: str,
            drain_id: str,
            *,
            replay_from: int | None,
        ) -> object:
            drain_probe.entered.set()
            recorder.set("drain_entered", True)
            recorder.write()
            try:
                result = original_drain(
                    task_id,
                    session_id,
                    drain_id,
                    replay_from=replay_from,
                )
            except BaseException as error:
                recorder.set(
                    "drain_exit",
                    {"type": type(error).__name__, "message": str(error)},
                )
                raise
            else:
                recorder.set(
                    "drain_exit",
                    {"type": "return", "update_count": len(result.updates)},
                )
                return result
            finally:
                drain_probe.exited.set()
                recorder.set("drain_exited", True)
                recorder.write()

        registry.drain = observed_drain  # type: ignore[method-assign]
        return registry

    def start_plan(
        service: object,
        source: str,
        target: str,
        *,
        deletion_policy: str | None = None,
        command_id: str | None = None,
        observation_sink=None,
    ) -> object:
        recorder.append(
            "service_start_plan_calls",
            {
                "source": source,
                "target": target,
                "deletion_policy": deletion_policy,
                "command_id": command_id,
            },
        )
        if deletion_policy == "additive":
            from namisync.interfaces.service import PlanSession

            recorder.set("controlled_plan_session", "b" * 32)
            return PlanSession("a" * 32, "b" * 32)
        return original_start_plan(
            service,
            source,
            target,
            deletion_policy=deletion_policy,
            command_id=command_id,
            observation_sink=observation_sink,
        )

    def unsubscribe(service: object, session_id: str) -> None:
        if session_id == "b" * 32:
            recorder.append(
                "controlled_service_cleanup",
                ["unsubscribe", session_id],
            )
            return
        original_unsubscribe(service, session_id)

    def log_renderer(browser_version: str) -> None:
        recorder.set("native_browser_version", browser_version)
        original_log_renderer(browser_version)

    def pending_document() -> object:
        document = original_pending_document()
        document_holder["value"] = document
        return document

    def attach(guard: object, core: object) -> None:
        original_attach(guard, core)
        if arguments.mode == "off-origin":
            core.NavigationStarting -= guard._on_navigation_starting
            recorder.set("navigation_starting_removed", True)

    def source_changed(guard: object, sender: object, event_args: object) -> None:
        original_source_changed(guard, sender, event_args)
        recorder.append("committed_sources", str(sender.Source))

    with ExitStack() as stack:
        stack.enter_context(patch.object(host, "_bridge_dispatcher", dispatcher))
        stack.enter_context(
            patch.object(host, "_expose_bridge_api", expose_bridge)
        )
        stack.enter_context(
            patch.object(bridge.BridgeDispatcher, "dispatch", observed_dispatch)
        )
        stack.enter_context(
            patch.object(bridge.NativeDocumentState, "_record", record_document)
        )
        stack.enter_context(patch.object(host, "_task_registry", task_registry))
        stack.enter_context(patch.object(host, "_pending_document", pending_document))
        stack.enter_context(patch.object(host, "_log_startup_renderer", log_renderer))
        if arguments.mode == "transport":
            stack.enter_context(
                patch.object(NamiSyncService, "start_plan", start_plan)
            )
            stack.enter_context(
                patch.object(NamiSyncService, "unsubscribe", unsubscribe)
            )
        elif arguments.mode == "off-origin":
            stack.enter_context(
                patch.object(bridge._NativeNavigationGuard, "attach", attach)
            )
            stack.enter_context(
                patch.object(
                    bridge._NativeNavigationGuard,
                    "_on_source_changed",
                    source_changed,
                )
            )
        exit_code = host.run_desktop(
            AppPaths.from_root(arguments.data_dir),
            DesktopInstanceIdentity(arguments.mutex, arguments.title),
            startup_error=recorder.startup_error,
            index_path=arguments.index,
        )

    if second_origin is not None:
        second_origin.shutdown()
        second_origin.server_close()
    document = document_holder.get("value")
    if document is not None:
        lock = document._lock
        with lock:
            recorder.set("final_document_url", str(document._current_url))
    recorder.set("exit_code", exit_code)
    recorder.write()
    return exit_code


def main() -> int:
    arguments = _parse_arguments()
    recorder = _Recorder(arguments.output, arguments.mode)
    try:
        return _run(arguments, recorder)
    except BaseException as error:
        recorder.set(
            "child_failure",
            {"type": type(error).__name__, "message": str(error)},
        )
        recorder.write()
        raise


if __name__ == "__main__":
    raise SystemExit(main())
