from __future__ import annotations

import ast
import inspect
import json
from collections.abc import Callable
from pathlib import Path
from threading import Event, Lock, Thread
from types import SimpleNamespace

import pytest

import namisync.interfaces.web.bridge as bridge_module
import namisync.interfaces.web.pywebview_runtime as pywebview_runtime
from namisync.interfaces.web.bridge import (
    AdmissionGranted,
    BRIDGE_SCHEMA_VERSION,
    BridgeDispatcher,
    BridgeOriginError,
    BridgeProtocolError,
    ExactOrigin,
    NativeDocumentState,
    WebView2Unavailable,
    configure_pywebview2_security,
    prepare_pywebview_host,
    start_edge_chromium,
)
from namisync.interfaces.web.commands import (
    CommandAccess,
    CommandRetry,
    CommandSpec,
    CommandTimeout,
    CommandWork,
    FieldRequirement,
)
from namisync.interfaces.web.document_channel import DocumentChannel
from namisync.interfaces.web.readiness import CommandPhase, ReadinessContext


_REQUEST_ID = "1a" * 16
_OPEN_CONTEXT = ReadinessContext(CommandPhase.OPEN, 0)


def _admit_open(_name: str) -> object:
    return AdmissionGranted(_OPEN_CONTEXT)


def _test_spec(handler) -> CommandSpec:
    return CommandSpec(
        validate_payload=lambda payload: payload,
        handler=handler,
        access=CommandAccess.READ_ONLY,
        command_id=FieldRequirement.FORBIDDEN,
        revision=FieldRequirement.FORBIDDEN,
        timeout=CommandTimeout.INTERACTIVE,
        retry=CommandRetry.NONE,
    )


def _async_test_spec(handler) -> CommandSpec:
    return CommandSpec(
        validate_payload=lambda payload: payload,
        handler=handler,
        access=CommandAccess.MUTATING,
        command_id=FieldRequirement.FORBIDDEN,
        revision=FieldRequirement.FORBIDDEN,
        timeout=CommandTimeout.MUTATION_30_SECONDS,
        retry=CommandRetry.SAME_PAYLOAD_BOUNDED,
        work=CommandWork.ASYNC_SMALL,
    )


def _async_dispatcher(handler) -> BridgeDispatcher:
    return BridgeDispatcher(
        document=_trusted_document(),
        commands={"async_test": _async_test_spec(handler)},
        admit=_admit_open,
    )


def _bind_completion_channel(
    bridge: BridgeDispatcher,
) -> tuple[DocumentChannel, list[str], Event]:
    encoded: list[str] = []
    posted = Event()

    class Core:
        def PostWebMessageAsJson(self, value: str) -> None:
            encoded.append(value)
            posted.set()

    native = SimpleNamespace(
        InvokeRequired=False,
        browser=SimpleNamespace(
            webview=SimpleNamespace(CoreWebView2=Core()),
        ),
    )
    channel = DocumentChannel(native, require_acknowledgment=True)
    bridge._bind_document_channel(channel)
    return channel, encoded, posted


def _dispatcher(document, handlers) -> BridgeDispatcher:
    return BridgeDispatcher(
        document=document,
        commands={name: _test_spec(handler) for name, handler in handlers.items()},
        admit=_admit_open,
    )


class EventHook:
    def __init__(self) -> None:
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def emit(self, args, *, sender=None) -> None:
        for handler in self.handlers:
            handler(sender, args)


class InitializedHook:
    def __init__(self) -> None:
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def emit(self) -> bool:
        return_values = [handler() for handler in self.handlers]
        return any(value is False for value in return_values)


class FakeCoreWebView2:
    def __init__(self, source: str = "http://127.0.0.1:41700/index.html") -> None:
        self.Source = source
        self.NavigationStarting = EventHook()
        self.FrameNavigationStarting = EventHook()
        self.NewWindowRequested = EventHook()
        self.SourceChanged = EventHook()


class BeforeLoadHook:
    def __init__(self, window) -> None:
        self.handlers = []
        self.errors = []
        self._window = window

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def emit(self) -> None:
        self._window._on_ui_thread = True
        try:
            for handler in self.handlers:
                try:
                    handler()
                except Exception as error:
                    self.errors.append(error)
        finally:
            self._window._on_ui_thread = False


class FakeManagedWebView:
    def __init__(self, window, core: FakeCoreWebView2) -> None:
        self._window = window
        self._core = core
        self.core_accesses = 0

    @property
    def CoreWebView2(self) -> FakeCoreWebView2:
        self.core_accesses += 1
        if not self._window._on_ui_thread:
            raise AssertionError("CoreWebView2 accessed outside the UI callback")
        return self._core


class NavigationArgs:
    def __init__(self, uri: str) -> None:
        self.Uri = uri
        self.Cancel = False


class NewWindowArgs:
    def __init__(self, uri: str) -> None:
        self._uri = uri
        self.Handled = False

    def get_Uri(self) -> str:
        return self._uri

    def set_Handled(self, value: bool) -> None:
        self.Handled = value


def _window(core: FakeCoreWebView2):
    window = SimpleNamespace(_on_ui_thread=False)
    managed_webview = FakeManagedWebView(window, core)
    window.native = SimpleNamespace(
        InvokeRequired=False,
        browser=SimpleNamespace(
            webview=managed_webview,
        )
    )
    window.events = SimpleNamespace(before_load=BeforeLoadHook(window))
    window.managed_webview = managed_webview
    return window


def _trusted_document(
    source: str = "https://app.invalid/index.html",
):
    core = FakeCoreWebView2(source)
    window = _window(core)
    document = configure_pywebview2_security(
        window,
        source,
    )
    window.events.before_load.emit()
    return document


def test_pending_document_binds_one_exact_origin_and_keeps_dispatch_closed() -> None:
    document = NativeDocumentState()
    bridge = BridgeDispatcher(
        document=document,
        commands={},
        admit=_admit_open,
    )
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": _REQUEST_ID,
            "command": "ping",
            "payload": {},
        }
    )

    assert bridge.dispatch(command)["error"]["code"] == "bridge_unavailable"

    origin = ExactOrigin.from_url("http://127.0.0.1:41700/index.html")
    document.bind_origin(origin)

    with pytest.raises(RuntimeError, match="already bound"):
        document.bind_origin(origin)
    assert bridge.dispatch(command)["error"]["code"] == "bridge_unavailable"


def test_existing_pending_document_is_bound_then_attached_without_window_rewrite() -> None:
    core = FakeCoreWebView2()
    window = _window(core)
    window._js_api = "host-owned"
    document = NativeDocumentState()
    document.bind_origin(
        ExactOrigin.from_url("http://127.0.0.1:41700/index.html")
    )

    configured = configure_pywebview2_security(
        window,
        "http://127.0.0.1:41700/index.html",
        document=document,
    )

    assert configured is document
    assert window._js_api == "host-owned"
    window.events.before_load.emit()
    assert document.is_attached


def test_existing_document_security_configuration_is_idempotent() -> None:
    core = FakeCoreWebView2()
    window = _window(core)
    document = NativeDocumentState()
    document.bind_origin(
        ExactOrigin.from_url("http://127.0.0.1:41700/index.html")
    )

    first = configure_pywebview2_security(
        window,
        "http://127.0.0.1:41700/index.html",
        document=document,
    )
    second = configure_pywebview2_security(
        window,
        "http://127.0.0.1:41700/index.html",
        document=document,
    )

    assert first is document
    assert second is document
    assert len(window.events.before_load.handlers) == 1
    window.events.before_load.emit()
    assert len(core.NavigationStarting.handlers) == 1


def test_native_installation_waits_for_synchronous_ui_before_load() -> None:
    core = FakeCoreWebView2()
    window = _window(core)

    document = configure_pywebview2_security(
        window,
        "http://127.0.0.1:41700",
    )

    assert window.managed_webview.core_accesses == 0
    assert len(core.NavigationStarting.handlers) == 0

    bridge = _dispatcher(document, {"ping": lambda payload: payload})
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": _REQUEST_ID,
            "command": "ping",
            "payload": {},
        }
    )
    assert bridge.dispatch(command)["error"]["code"] == "bridge_unavailable"

    window.events.before_load.emit()
    window.events.before_load.emit()

    assert window.managed_webview.core_accesses == 1
    assert document.is_attached
    assert document.attachment_error is None
    assert len(core.NavigationStarting.handlers) == 1
    assert len(core.FrameNavigationStarting.handlers) == 1
    assert len(core.NewWindowRequested.handlers) == 1
    assert len(core.SourceChanged.handlers) == 1
    assert bridge.dispatch(command)["result"] == {}


def test_native_installation_refuses_an_off_ui_before_load_callback() -> None:
    core = FakeCoreWebView2()
    window = _window(core)
    window.native.InvokeRequired = True
    document = configure_pywebview2_security(
        window,
        "http://127.0.0.1:41700",
    )

    window.events.before_load.emit()

    assert not document.is_attached
    assert document.attachment_error is not None
    assert "UI thread" in document.attachment_error
    assert len(window.events.before_load.errors) == 1
    assert window.managed_webview.core_accesses == 0
    assert len(core.NavigationStarting.handlers) == 0

    bridge = _dispatcher(document, {"ping": lambda payload: payload})
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": _REQUEST_ID,
            "command": "ping",
            "payload": {},
        }
    )
    assert bridge.dispatch(command)["error"]["code"] == "bridge_unavailable"


def test_native_installation_failure_is_sticky_after_a_partial_subscription() -> None:
    core = FakeCoreWebView2()
    del core.FrameNavigationStarting
    window = _window(core)
    document = configure_pywebview2_security(
        window,
        "http://127.0.0.1:41700/index.html",
    )

    window.events.before_load.emit()
    window.events.before_load.emit()

    assert not document.is_attached
    assert document.attachment_error is not None
    assert "navigation events" in document.attachment_error
    assert len(window.events.before_load.errors) == 1
    assert window.managed_webview.core_accesses == 1
    assert len(core.NavigationStarting.handlers) == 1


def test_native_installation_records_uninitialized_webview2() -> None:
    core = FakeCoreWebView2()
    window = _window(core)
    window.managed_webview._core = None
    document = configure_pywebview2_security(
        window,
        "http://127.0.0.1:41700/index.html",
    )

    window.events.before_load.emit()

    assert not document.is_attached
    assert document.attachment_error == "WebView2 is not initialized"
    assert len(window.events.before_load.errors) == 1


def test_native_installation_records_an_unavailable_document_source() -> None:
    core = FakeCoreWebView2(source="")
    window = _window(core)
    document = configure_pywebview2_security(
        window,
        "http://127.0.0.1:41700/index.html",
    )

    window.events.before_load.emit()

    assert not document.is_attached
    assert document.attachment_error == "WebView2 document source is unavailable"
    assert len(window.events.before_load.errors) == 1


def test_before_load_reports_native_browser_version_on_the_ui_thread() -> None:
    core = FakeCoreWebView2()
    core.Environment = SimpleNamespace(BrowserVersionString="150.0.4078.105")
    window = _window(core)
    reported: list[str] = []

    def report(browser_version: str) -> None:
        assert window._on_ui_thread
        assert len(core.NavigationStarting.handlers) == 0
        assert len(core.FrameNavigationStarting.handlers) == 0
        assert len(core.NewWindowRequested.handlers) == 0
        assert len(core.SourceChanged.handlers) == 0
        reported.append(browser_version)

    configure_pywebview2_security(
        window,
        "http://127.0.0.1:41700/index.html",
        on_browser_version=report,
    )

    window.events.before_load.emit()
    window.events.before_load.emit()

    assert reported == ["150.0.4078.105"]


def test_native_webview2_hooks_cancel_untrusted_navigation_frames_and_popups() -> None:
    core = FakeCoreWebView2()
    window = _window(core)
    document = configure_pywebview2_security(
        window,
        "http://127.0.0.1:41700",
    )
    window.events.before_load.emit()
    trusted = NavigationArgs("http://127.0.0.1:41700/index.html")
    external = NavigationArgs("https://example.com/")
    core.NavigationStarting.emit(trusted, sender=core)
    core.NavigationStarting.emit(external, sender=core)
    trusted_frame = NavigationArgs("http://127.0.0.1:41700/frame.html")
    external_frame = NavigationArgs("https://example.com/frame.html")
    core.FrameNavigationStarting.emit(trusted_frame, sender=core)
    core.FrameNavigationStarting.emit(external_frame, sender=core)
    popup = NewWindowArgs("https://example.com/")
    core.NewWindowRequested.emit(popup, sender=core)

    assert not trusted.Cancel
    assert external.Cancel
    assert trusted_frame.Cancel
    assert external_frame.Cancel
    assert popup.Handled

    bridge = _dispatcher(document, {"ping": lambda payload: payload})
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": _REQUEST_ID,
            "command": "ping",
            "payload": {},
        }
    )
    assert bridge.dispatch(command)["result"] == {}

    core.Source = "https://example.com/"
    core.SourceChanged.emit(SimpleNamespace(), sender=core)
    assert bridge.dispatch(command)["error"]["code"] == "bridge_unavailable"


def test_pywebview_popup_chain_keeps_packaged_document_and_bridge() -> None:
    core = FakeCoreWebView2()
    window = _window(core)
    system_browser_launches: list[str] = []
    attempted_navigations: list[NavigationArgs] = []
    settings = {"OPEN_EXTERNAL_LINKS_IN_BROWSER": False}

    def pywebview_new_window_handler(sender: object, args: NewWindowArgs) -> None:
        del sender
        args.set_Handled(True)
        uri = args.get_Uri()
        if settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"]:
            system_browser_launches.append(uri)
            return
        navigation = NavigationArgs(uri)
        attempted_navigations.append(navigation)
        core.NavigationStarting.emit(navigation, sender=core)
        if not navigation.Cancel:
            core.Source = uri
            core.SourceChanged.emit(SimpleNamespace(), sender=core)

    core.NewWindowRequested += pywebview_new_window_handler
    document = configure_pywebview2_security(
        window,
        "http://127.0.0.1:41700/index.html",
    )
    window.events.before_load.emit()
    bridge = _dispatcher(document, {"ping": lambda payload: payload})
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": _REQUEST_ID,
            "command": "ping",
            "payload": {"still": "trusted"},
        }
    )

    popup = NewWindowArgs("https://example.invalid/")
    core.NewWindowRequested.emit(popup, sender=core)

    assert popup.Handled
    assert system_browser_launches == []
    assert len(attempted_navigations) == 1
    assert attempted_navigations[0].Cancel
    assert core.Source == "http://127.0.0.1:41700/index.html"
    assert bridge.dispatch(command)["result"] == {"still": "trusted"}


def test_prepare_pywebview_host_refuses_a_conflicting_pythonnet_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHONNET_RUNTIME", "coreclr")
    webview = SimpleNamespace(settings={})

    with pytest.raises(RuntimeError, match="PYTHONNET_RUNTIME"):
        prepare_pywebview_host(webview)

    assert webview.settings == {}


def test_prepare_pywebview_host_uses_only_read_only_runtime_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, str, int, int]] = []

    class RegistryKey:
        def __init__(self, path: str) -> None:
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            del args

    def open_key(hive: object, path: str, reserved: int, access: int):
        calls.append((hive, path, reserved, access))
        if hive == pywebview_runtime.winreg.HKEY_CURRENT_USER:
            raise FileNotFoundError(path)
        return RegistryKey(path)

    def query_value(key: RegistryKey, name: str) -> tuple[object, int]:
        if key.path == pywebview_runtime.DOTNET_RELEASE_REGISTRY_PATH:
            assert name == "Release"
            return pywebview_runtime.MINIMUM_DOTNET_RELEASE, 1
        assert name == "pv"
        return "150.0.4078.105", 1

    def reject_write(*args, **kwargs) -> None:
        del args, kwargs
        pytest.fail("runtime detection attempted a registry write")

    monkeypatch.setattr(pywebview_runtime, "machine", lambda: "AMD64")
    monkeypatch.setattr(pywebview_runtime.winreg, "OpenKey", open_key)
    monkeypatch.setattr(pywebview_runtime.winreg, "QueryValueEx", query_value)
    monkeypatch.setattr(pywebview_runtime.winreg, "CreateKeyEx", reject_write)
    monkeypatch.setattr(pywebview_runtime.winreg, "SetValueEx", reject_write)
    webview = SimpleNamespace(
        settings={
            "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,
            "ALLOW_FILE_URLS": True,
            "ALLOW_DOWNLOADS": True,
            "REMOTE_DEBUGGING_PORT": 9222,
            "WEBVIEW2_RUNTIME_PATH": None,
        }
    )

    prepare_pywebview_host(webview)

    assert webview.settings == {
        "OPEN_EXTERNAL_LINKS_IN_BROWSER": False,
        "ALLOW_FILE_URLS": False,
        "ALLOW_DOWNLOADS": False,
        "REMOTE_DEBUGGING_PORT": None,
        "WEBVIEW2_RUNTIME_PATH": None,
    }
    assert calls == [
        (
            pywebview_runtime.winreg.HKEY_LOCAL_MACHINE,
            pywebview_runtime.DOTNET_RELEASE_REGISTRY_PATH,
            0,
            pywebview_runtime.winreg.KEY_READ,
        ),
        (
            pywebview_runtime.winreg.HKEY_CURRENT_USER,
            "SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\"
            "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
            0,
            pywebview_runtime.winreg.KEY_READ,
        ),
        (
            pywebview_runtime.winreg.HKEY_LOCAL_MACHINE,
            "SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\"
            "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
            0,
            pywebview_runtime.winreg.KEY_READ,
        ),
    ]


def test_prepare_pywebview_host_reports_malformed_dotnet_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queries = 0

    class RegistryKey:
        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            del args

    def open_key(hive: object, path: str, reserved: int, access: int):
        del hive, reserved, access
        assert path == pywebview_runtime.DOTNET_RELEASE_REGISTRY_PATH
        return RegistryKey()

    def query_value(key: RegistryKey, name: str) -> tuple[str, int]:
        nonlocal queries
        del key
        assert name == "Release"
        queries += 1
        return str(pywebview_runtime.MINIMUM_DOTNET_RELEASE), 1

    monkeypatch.setattr(pywebview_runtime.winreg, "OpenKey", open_key)
    monkeypatch.setattr(pywebview_runtime.winreg, "QueryValueEx", query_value)
    webview = SimpleNamespace(
        settings={
            "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,
            "ALLOW_FILE_URLS": True,
            "ALLOW_DOWNLOADS": True,
            "REMOTE_DEBUGGING_PORT": 9222,
            "WEBVIEW2_RUNTIME_PATH": None,
        }
    )

    with pytest.raises(WebView2Unavailable, match="could not verify"):
        prepare_pywebview_host(webview)

    assert queries == 1


def test_prepare_pywebview_host_fixed_runtime_reads_only_dotnet_prerequisite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []

    class RegistryKey:
        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            del args

    def open_key(hive: object, path: str, reserved: int, access: int):
        del hive, reserved, access
        opened.append(path)
        assert path == pywebview_runtime.DOTNET_RELEASE_REGISTRY_PATH
        return RegistryKey()

    monkeypatch.setattr(pywebview_runtime.winreg, "OpenKey", open_key)
    monkeypatch.setattr(
        pywebview_runtime.winreg,
        "QueryValueEx",
        lambda key, name: (pywebview_runtime.MINIMUM_DOTNET_RELEASE, 1),
    )
    webview = SimpleNamespace(
        settings={
            "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,
            "ALLOW_FILE_URLS": True,
            "ALLOW_DOWNLOADS": True,
            "REMOTE_DEBUGGING_PORT": 9222,
            "WEBVIEW2_RUNTIME_PATH": r"runtime\WebView2",
        }
    )

    prepare_pywebview_host(webview)

    assert webview.settings["WEBVIEW2_RUNTIME_PATH"] == r"runtime\WebView2"
    assert opened == [pywebview_runtime.DOTNET_RELEASE_REGISTRY_PATH]


def test_start_forces_edge_chromium_and_reports_missing_runtime() -> None:
    calls = []
    host_initialized = []
    initial_settings = {
        "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,
        "ALLOW_FILE_URLS": True,
        "ALLOW_DOWNLOADS": True,
        "REMOTE_DEBUGGING_PORT": 9222,
        "WEBVIEW2_RUNTIME_PATH": r"runtime\WebView2",
    }
    required_settings = {
        "OPEN_EXTERNAL_LINKS_IN_BROWSER": False,
        "ALLOW_FILE_URLS": False,
        "ALLOW_DOWNLOADS": False,
        "REMOTE_DEBUGGING_PORT": None,
        "WEBVIEW2_RUNTIME_PATH": r"runtime\WebView2",
    }

    class Webview:
        settings = dict(initial_settings)
        renderer = "edgechromium"
        windows = [
            SimpleNamespace(
                events=SimpleNamespace(initialized=InitializedHook()),
            )
        ]

        @staticmethod
        def start(func=None, *, gui: str, debug: bool) -> None:
            assert Webview.settings == required_settings
            assert not Webview.windows[0].events.initialized.emit()
            calls.append((func, gui, debug))

    setup = lambda: None
    start_edge_chromium(
        Webview,
        setup,
        on_initialized=lambda: host_initialized.append("edgechromium"),
    )
    assert calls == [(setup, "edgechromium", False)]
    assert host_initialized == ["edgechromium"]

    class BrokenWebview:
        settings = dict(initial_settings)
        renderer = "mshtml"
        windows = [
            SimpleNamespace(
                events=SimpleNamespace(initialized=InitializedHook()),
            )
        ]

        @staticmethod
        def start(func=None, *, gui: str, debug: bool) -> None:
            del func, gui, debug
            assert BrokenWebview.windows[0].events.initialized.emit()

    refused_host_initialization = []
    with pytest.raises(WebView2Unavailable, match="install"):
        start_edge_chromium(
            BrokenWebview,
            on_initialized=lambda: refused_host_initialization.append("called"),
        )
    assert refused_host_initialization == []

    class WebViewException(Exception):
        pass

    unrelated_error = WebViewException("GUI is not initialized")

    class MisconfiguredWebview:
        settings = dict(initial_settings)
        renderer = "edgechromium"
        windows = [
            SimpleNamespace(
                events=SimpleNamespace(initialized=InitializedHook()),
            )
        ]

        @staticmethod
        def start(func=None, *, gui: str, debug: bool) -> None:
            del func, gui, debug
            raise unrelated_error

    with pytest.raises(WebViewException, match="GUI is not initialized") as raised:
        start_edge_chromium(MisconfiguredWebview)
    assert raised.value is unrelated_error

    host_error = RuntimeError("origin setup failed")

    class HostInitializationFailure:
        settings = dict(initial_settings)
        renderer = "edgechromium"
        windows = [
            SimpleNamespace(
                events=SimpleNamespace(initialized=InitializedHook()),
            )
        ]

        @staticmethod
        def start(func=None, *, gui: str, debug: bool) -> None:
            del func, gui, debug
            assert HostInitializationFailure.windows[0].events.initialized.emit()

    def fail_host_initialization() -> None:
        raise host_error

    with pytest.raises(RuntimeError, match="origin setup failed") as raised:
        start_edge_chromium(
            HostInitializationFailure,
            on_initialized=fail_host_initialization,
        )
    assert raised.value is host_error


def test_start_forwards_private_http_server_storage_options(tmp_path: Path) -> None:
    calls: list[tuple[object, ...]] = []
    storage = tmp_path / "webview2"

    class Webview:
        settings = {
            "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,
            "ALLOW_FILE_URLS": True,
            "ALLOW_DOWNLOADS": True,
            "REMOTE_DEBUGGING_PORT": 9222,
            "WEBVIEW2_RUNTIME_PATH": r"runtime\WebView2",
        }
        renderer = "edgechromium"
        windows = [
            SimpleNamespace(events=SimpleNamespace(initialized=InitializedHook()))
        ]

        @staticmethod
        def start(
            func=None,
            *,
            gui: str,
            debug: bool,
            http_server: bool,
            private_mode: bool,
            storage_path: Path,
        ) -> None:
            calls.append(
                (
                    func,
                    gui,
                    debug,
                    http_server,
                    private_mode,
                    storage_path,
                )
            )
            assert not Webview.windows[0].events.initialized.emit()

    setup = lambda: None
    start_edge_chromium(Webview, setup, storage_path=storage)

    assert calls == [(setup, "edgechromium", False, True, True, storage)]


def test_start_refuses_missing_security_settings_before_native_startup() -> None:
    started = False

    class IncompleteWebview:
        settings = {
            "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,
            "ALLOW_FILE_URLS": True,
            "ALLOW_DOWNLOADS": True,
        }
        renderer = "edgechromium"
        windows = [
            SimpleNamespace(
                events=SimpleNamespace(initialized=InitializedHook()),
            )
        ]

        @staticmethod
        def start(func=None, *, gui: str, debug: bool) -> None:
            nonlocal started
            del func, gui, debug
            started = True

    with pytest.raises(RuntimeError, match="REMOTE_DEBUGGING_PORT"):
        start_edge_chromium(IncompleteWebview)
    assert not started


def _stub_runtime_registry(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dotnet_present: bool,
) -> list[str]:
    """Fail every WebView2 client probe, choosing whether .NET itself is found."""

    opened_paths: list[str] = []

    class Key:
        def __init__(self, path: str) -> None:
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            del args

    def open_key(hive, path, *args, **kwargs):
        del hive, args, kwargs
        opened_paths.append(path)
        if path == pywebview_runtime.DOTNET_RELEASE_REGISTRY_PATH and dotnet_present:
            return Key(path)
        raise FileNotFoundError(path)

    def query_value(key, name):
        del name
        return pywebview_runtime.MINIMUM_DOTNET_RELEASE, 1

    monkeypatch.setattr(pywebview_runtime.winreg, "OpenKey", open_key)
    monkeypatch.setattr(pywebview_runtime.winreg, "QueryValueEx", query_value)
    return opened_paths


def test_start_refuses_missing_dotnet_with_its_own_prerequisite_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened_paths = _stub_runtime_registry(monkeypatch, dotnet_present=False)

    class NoDotnetWebview:
        settings = {
            "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,
            "ALLOW_FILE_URLS": True,
            "ALLOW_DOWNLOADS": True,
            "REMOTE_DEBUGGING_PORT": 9222,
            "WEBVIEW2_RUNTIME_PATH": None,
        }
        renderer = None
        windows = [
            SimpleNamespace(events=SimpleNamespace(initialized=InitializedHook()))
        ]

        @staticmethod
        def start(func=None, *, gui: str, debug: bool) -> None:
            raise AssertionError("pywebview must not start without .NET")

    with pytest.raises(WebView2Unavailable, match=r"\.NET Framework 4\.6\.2"):
        start_edge_chromium(NoDotnetWebview)
    assert (
        opened_paths.count(pywebview_runtime.DOTNET_RELEASE_REGISTRY_PATH) == 1
    )


def test_start_refuses_missing_runtime_before_pywebview_initialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = InitializedHook()
    started = False

    opened_paths = _stub_runtime_registry(monkeypatch, dotnet_present=True)

    class MissingRuntimeWebview:
        settings = {
            "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,
            "ALLOW_FILE_URLS": True,
            "ALLOW_DOWNLOADS": True,
            "REMOTE_DEBUGGING_PORT": 9222,
            "WEBVIEW2_RUNTIME_PATH": None,
        }
        renderer = None
        windows = [SimpleNamespace(events=SimpleNamespace(initialized=initialized))]

        @staticmethod
        def start(func=None, *, gui: str, debug: bool) -> None:
            nonlocal started
            del func, gui, debug
            started = True

    with pytest.raises(WebView2Unavailable, match="Edge WebView2 Runtime") as raised:
        start_edge_chromium(MissingRuntimeWebview)
    assert ".NET Framework" not in str(raised.value)

    assert not started
    assert initialized.handlers == []
    assert (
        opened_paths.count(pywebview_runtime.DOTNET_RELEASE_REGISTRY_PATH) == 1
    )


@pytest.mark.parametrize(
    ("asset_url", "allowed_url"),
    [
        (
            "http://127.0.0.1:41700",
            "http://127.0.0.1:41700/index.html",
        ),
        (
            "http://127.0.0.1:41700/index.html?view=plan#current",
            "http://127.0.0.1:41700/assets/app.js",
        ),
        (
            "https://APP.INVALID/root/index.html",
            "https://app.invalid/other?query=yes",
        ),
        (
            "http://[::1]:41700/root?next=https://example.invalid/a/b",
            "http://[::1]:41700/other",
        ),
    ],
)
def test_exact_origin_derives_from_full_asset_urls(
    asset_url: str,
    allowed_url: str,
) -> None:
    origin = ExactOrigin.from_url(asset_url)

    assert origin.allows(allowed_url)
    assert not origin.allows("https://example.invalid/")


def test_exact_origin_parse_remains_strict_for_origin_contracts() -> None:
    assert ExactOrigin.parse("https://app.invalid/") == ExactOrigin(
        scheme="https",
        host="app.invalid",
        port=443,
    )
    with pytest.raises(ValueError, match="must not include a path"):
        ExactOrigin.parse("https://app.invalid/index.html")
    assert ExactOrigin.from_url("http://app.invalid:0/index.html").port == 0
    loopback = ExactOrigin.from_url("http://127.0.0.1:41700/index.html")
    assert not loopback.allows("http://127.0.0.1:41701/index.html")
    assert not loopback.allows("https://127.0.0.1:41700/index.html")


@pytest.mark.parametrize(
    "asset_url",
    [
        "relative/index.html",
        "file:///C:/app/index.html",
        "https://user@app.invalid/index.html",
        "http://app.invalid:not-a-port/index.html",
    ],
)
def test_exact_origin_rejects_non_http_authorities(asset_url: str) -> None:
    with pytest.raises(ValueError, match="packaged asset origin"):
        ExactOrigin.from_url(asset_url)


def test_dispatch_rechecks_origin_and_returns_hostile_text_as_data() -> None:
    core = FakeCoreWebView2()
    window = _window(core)
    document = configure_pywebview2_security(
        window,
        "http://127.0.0.1:41700",
    )
    window.events.before_load.emit()
    hostile = '</script><img src=x onerror="alert(1)">'
    bridge = _dispatcher(
        document,
        {"next_events": lambda payload: [{"path": payload["path"]}]},
    )
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": _REQUEST_ID,
            "command": "next_events",
            "payload": {"path": hostile},
        }
    )

    assert bridge.dispatch(command) == {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "ok": True,
        "result": [{"path": hostile}],
    }

    core.Source = "https://example.com/"
    core.SourceChanged.emit(SimpleNamespace(), sender=core)
    assert bridge.dispatch(command)["error"]["code"] == "bridge_unavailable"


def test_bridge_public_surface_is_dispatch_and_typed_lifecycle_only() -> None:
    bridge = _dispatcher(
        _trusted_document(),
        {"ping": lambda payload: payload},
    )
    public_methods = {
        name
        for name, member in inspect.getmembers(bridge, predicate=callable)
        if not name.startswith("_")
    }
    assert public_methods == {"begin_close", "dispatch", "wait_for_handlers"}

    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": _REQUEST_ID,
            "command": "unknown",
            "payload": {},
        }
    )
    assert bridge.dispatch(command)["error"]["code"] == "unknown_command"


def test_empty_handler_surface_is_valid_but_invalid_entries_are_rejected() -> None:
    document = _trusted_document()
    bridge = BridgeDispatcher(
        document=document,
        commands={},
        admit=_admit_open,
    )
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": _REQUEST_ID,
            "command": "ping",
            "payload": {},
        }
    )

    assert bridge.dispatch(command)["error"]["code"] == "unknown_command"
    for invalid_name in ("", "_private", "not-valid", "x" * 65, 7):
        with pytest.raises(ValueError, match="lowercase snake names"):
            BridgeDispatcher(
                document=document,
                commands={invalid_name: _test_spec(lambda payload: payload)},
                admit=_admit_open,
            )
    with pytest.raises(TypeError, match="exact CommandSpec"):
        BridgeDispatcher(
            document=document,
            commands={"ping": lambda payload: payload},
            admit=_admit_open,
        )


def test_pinned_pywebview_raw_receiver_cannot_traverse_bridge_state() -> None:
    from webview.util import js_bridge_call

    from namisync.interfaces.web import host

    document = _trusted_document()
    bridge = _dispatcher(document, {"ping": lambda payload: payload})
    callbacks: list[str] = []
    returned = Event()

    class RawWindow:
        def __init__(self) -> None:
            self._js_api = None
            self._functions: dict[str, object] = {}
            self._callbacks: dict[str, object] = {}

        def expose(self, *functions: object) -> None:
            self._functions.update(
                {
                    function.__name__: function
                    for function in functions
                }
            )

        def evaluate_js(self, source: str) -> None:
            callbacks.append(source)
            returned.set()

    window = RawWindow()
    host._expose_bridge_api(window, bridge)

    js_bridge_call(
        window,
        "_document._record",
        ["https://attacker.invalid/"],
        "raw-document",
    )
    js_bridge_call(window, "_commands.clear", [], "raw-commands")
    js_bridge_call(
        window,
        "dispatch.__self__._document._record",
        ["https://attacker.invalid/"],
        "raw-bound-method",
    )

    document.require_trusted()
    assert tuple(bridge._commands) == ("ping",)
    assert callbacks == []

    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": _REQUEST_ID,
            "command": "ping",
            "payload": {"value": 1},
        }
    )
    js_bridge_call(window, "dispatch", [command], "intended-dispatch")

    assert returned.wait(1.0)
    assert len(callbacks) == 1
    assert '"ok": true' in callbacks[0]
    assert '"result": {"value": 1}' in callbacks[0]


def test_bridge_close_gate_rejects_new_and_waits_for_admitted_handler() -> None:
    entered = Event()
    release = Event()
    finished = Event()

    def slow_handler(payload):
        entered.set()
        assert release.wait(1.0)
        return payload

    bridge = _dispatcher(_trusted_document(), {"slow": slow_handler})
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": _REQUEST_ID,
            "command": "slow",
            "payload": {"value": 1},
        }
    )
    dispatch_thread = Thread(target=lambda: bridge.dispatch(command))
    dispatch_thread.start()
    assert entered.wait(1.0)

    bridge.begin_close()
    waiter = Thread(target=lambda: (bridge.wait_for_handlers(), finished.set()))
    waiter.start()

    assert not finished.wait(0.05)
    assert bridge.dispatch(command)["error"]["code"] == "bridge_unavailable"
    release.set()
    dispatch_thread.join(1.0)
    waiter.join(1.0)

    assert not dispatch_thread.is_alive()
    assert not waiter.is_alive()
    assert finished.is_set()


@pytest.mark.parametrize("blocked_stage", ["serialization", "evaluation"])
@pytest.mark.parametrize("failure_stage", [None, "serialization", "evaluation"])
def test_br_g_32_native_return_retains_handler_capacity_until_worker_exit(
    monkeypatch: pytest.MonkeyPatch,
    blocked_stage: str,
    failure_stage: str | None,
) -> None:
    import webview.util

    from namisync.interfaces.web import host

    bridge = _dispatcher(_trusted_document(), {"echo": lambda payload: payload})
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "echo",
        "payload": {"value": "native return"},
    })
    entered = Event()
    release = Event()
    guard = Lock()
    blocked = 0
    workers: list[Thread] = []
    failures: list[type[Exception]] = []
    return_scripts: list[str] = []
    close_errors: list[type[Exception]] = []
    close_done = Event()
    closer: Thread | None = None

    def hold_return() -> None:
        nonlocal blocked
        with guard:
            blocked += 1
            if blocked == 64:
                entered.set()
        assert release.wait(5.0)

    def dumps(value: object) -> str:
        if isinstance(value, dict) and "transport_version" in value:
            if blocked_stage == "serialization":
                hold_return()
            if failure_stage == "serialization":
                raise ValueError("native serialization failed")
        return json.dumps(value)

    def evaluate(script: str) -> None:
        return_scripts.append(script)
        if blocked_stage == "evaluation":
            hold_return()
        if failure_stage == "evaluation":
            raise RuntimeError("native evaluation failed")

    def worker(*, target) -> Thread:
        def run() -> None:
            try:
                target()
            except Exception as error:
                failures.append(type(error))

        result = Thread(target=run)
        workers.append(result)
        return result

    def wait_for_close() -> None:
        try:
            bridge.wait_for_handlers(timeout=1.0)
        except Exception as error:
            close_errors.append(type(error))
        finally:
            close_done.set()

    window = SimpleNamespace(
        _js_api=None,
        _functions={},
        _callbacks={},
        expose=lambda *functions: window._functions.update(
            {function.__name__: function for function in functions}
        ),
        evaluate_js=evaluate,
    )
    host._expose_bridge_api(window, bridge)
    monkeypatch.setattr(webview.util, "Thread", worker)
    monkeypatch.setattr(webview.util, "json", SimpleNamespace(dumps=dumps))

    try:
        for index in range(64):
            webview.util.js_bridge_call(window, "dispatch", [command], str(index))
        assert entered.wait(3.0)
        assert bridge.dispatch(command)["error"]["code"] == "bridge_busy"
        bridge.begin_close()
        with pytest.raises(TimeoutError, match="did not quiesce"):
            bridge.wait_for_handlers(timeout=0.02)
        assert bridge._admitted == 64
        closer = Thread(target=wait_for_close)
        closer.start()
        assert not close_done.wait(0.02)
    finally:
        release.set()
        for thread in workers:
            thread.join(2.0)
        if closer is not None:
            closer.join(2.0)

    assert all(not thread.is_alive() for thread in workers)
    assert failures == ([RuntimeError] * 64 if failure_stage == "evaluation" else [])
    assert len(return_scripts) == 64
    assert all(
        ("isError: true" in script) is (failure_stage == "serialization")
        for script in return_scripts
    )
    if failure_stage == "serialization":
        assert all("native serialization failed" in script for script in return_scripts)
    assert close_done.is_set()
    assert close_errors == []
    assert bridge._admitted == 0


@pytest.mark.parametrize(
    ("retirement", "expected_evaluations", "expected_failures"),
    [
        ("before_evaluation", 0, []),
        ("during_evaluation", 1, []),
        ("current", 1, ["JavascriptException"]),
    ],
)
def test_pinned_pywebview_native_return_is_generation_contained(
    monkeypatch: pytest.MonkeyPatch,
    retirement: str,
    expected_evaluations: int,
    expected_failures: list[str],
) -> None:
    import webview.util
    from webview.errors import JavascriptException

    from namisync.interfaces.web import host

    entered = Event()
    release = Event()
    effects: list[object] = []
    evaluations: list[str] = []
    failures: list[str] = []
    workers: list[Thread] = []

    def handler(payload: object) -> object:
        effects.append(payload)
        entered.set()
        assert release.wait(1.0)
        return payload

    bridge = _dispatcher(_trusted_document(), {"echo": handler})
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "echo",
        "payload": {"value": "native return"},
    })

    def evaluate(script: str) -> None:
        evaluations.append(script)
        if retirement == "during_evaluation":
            bridge._retire_document_responses()
        if retirement in {"during_evaluation", "current"}:
            raise JavascriptException({"name": "TypeError"})

    def worker(*, target: Callable[[], None]) -> Thread:
        def capture() -> None:
            try:
                target()
            except BaseException as error:
                failures.append(type(error).__name__)

        thread = Thread(target=capture)
        workers.append(thread)
        return thread

    window = SimpleNamespace(
        _js_api=None,
        _functions={},
        _callbacks={},
        expose=lambda *functions: window._functions.update(
            {function.__name__: function for function in functions}
        ),
        evaluate_js=evaluate,
    )
    host._expose_bridge_api(window, bridge)
    monkeypatch.setattr(webview.util, "Thread", worker)

    webview.util.js_bridge_call(window, "dispatch", [command], "return-id")
    assert entered.wait(1.0)
    if retirement == "before_evaluation":
        bridge._retire_document_responses()
    release.set()
    for thread in workers:
        thread.join(1.0)
        assert not thread.is_alive()
    if retirement == "current":
        bridge._retire_document_responses()
    bridge.wait_for_handlers(1.0)

    assert effects == [{"value": "native return"}]
    assert len(evaluations) == expected_evaluations
    assert failures == expected_failures
    assert bridge._admitted == 0


def test_br_g_32_native_return_requires_worker_exit_and_exact_browser_receipt() -> None:
    bridge = _dispatcher(_trusted_document(), {"echo": lambda payload: payload})
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "echo",
        "payload": {},
    })
    responses = []

    def run() -> None:
        responses.append(bridge._dispatch_native(command))
        responses.append(bridge._dispatch_native(command))

    owner = Thread(target=run)
    owner.start()
    owner.join(1.0)

    assert not owner.is_alive()
    assert responses[0]["response"]["ok"] is True
    response_token = responses[0]["response_token"]
    assert isinstance(response_token, str)
    assert responses[1]["response_token"] is None
    assert responses[1]["response"]["error"]["code"] == "bridge_busy"
    with pytest.raises(TimeoutError, match="did not quiesce"):
        bridge.wait_for_handlers(0.01)
    assert bridge._dispatch_native(f"ack:{response_token}") is True
    assert bridge._dispatch_native(f"ack:{response_token}") is False
    bridge.wait_for_handlers(1.0)
    assert bridge.dispatch(command)["ok"] is True


def test_native_acknowledgment_return_carries_a_one_shot_generation() -> None:
    bridge = _dispatcher(_trusted_document(), {"echo": lambda payload: payload})
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "echo",
        "payload": {},
    })
    responses: list[dict[str, object]] = []
    producer = Thread(
        target=lambda: responses.append(bridge._dispatch_native(command))
    )
    producer.start()
    producer.join(1.0)
    assert not producer.is_alive()
    token = responses[0]["response_token"]
    assert isinstance(token, str)

    acknowledgments: list[object] = []
    generations: list[int | None] = []
    current: list[bool] = []
    acknowledged = Event()
    inspect_return = Event()

    def acknowledge() -> None:
        acknowledgments.append(bridge._dispatch_native(f"ack:{token}"))
        acknowledged.set()
        assert inspect_return.wait(1.0)
        generation = bridge._claim_native_return_generation()
        generations.append(generation)
        assert generation is not None
        current.append(bridge._is_document_generation_current(generation))
        generations.append(bridge._claim_native_return_generation())

    consumer = Thread(target=acknowledge)
    consumer.start()
    assert acknowledged.wait(1.0)
    bridge._retire_document_responses()
    inspect_return.set()
    consumer.join(1.0)

    assert not consumer.is_alive()
    assert acknowledgments == [True]
    assert generations == [0, None]
    assert current == [False]
    bridge.wait_for_handlers(1.0)


def test_br_g_32_exact_native_receipt_remains_available_after_trust_loss() -> None:
    document = _trusted_document()
    calls: list[object] = []
    bridge = _dispatcher(document, {"echo": lambda payload: calls.append(payload)})
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "echo",
        "payload": {},
    })
    responses: list[dict[str, object]] = []
    document._record("https://off-origin.invalid/")

    owner = Thread(target=lambda: responses.append(bridge._dispatch_native(command)))
    owner.start()
    owner.join(1.0)

    assert not owner.is_alive()
    assert calls == []
    assert len(responses) == 1
    response = responses[0]
    assert response["response"] == {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": None,
        "ok": False,
        "error": {
            "code": "bridge_unavailable",
            "message": (
                "NamiSync is closing or this desktop page is no longer trusted."
            ),
        },
    }
    response_token = response["response_token"]
    assert isinstance(response_token, str)
    assert bridge._dispatch_native(f"ack:{response_token}") is True
    assert bridge._dispatch_native(f"ack:{response_token}") is False
    bridge.wait_for_handlers(1.0)


def test_br_g_32_duplicate_native_token_cannot_receipt_an_earlier_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = _dispatcher(_trusted_document(), {"echo": lambda payload: payload})
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "echo",
        "payload": {},
    })
    monkeypatch.setattr(
        bridge_module,
        "uuid4",
        lambda: SimpleNamespace(hex="a" * 32),
    )
    responses = []

    for _ in range(2):
        owner = Thread(
            target=lambda: responses.append(bridge._dispatch_native(command))
        )
        owner.start()
        owner.join(1.0)
        assert not owner.is_alive()

    assert responses[0]["response_token"] == "a" * 32
    assert responses[0]["response"]["ok"] is True
    assert responses[1]["response_token"] is None
    assert responses[1]["response"]["error"]["code"] == "bridge_busy"
    assert bridge._dispatch_native("ack:" + ("a" * 32)) is True
    bridge.wait_for_handlers(1.0)


def test_br_g_32_cleanup_receipt_bypasses_saturation_but_not_worker_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge_module, "_MAX_ADMITTED_HANDLERS", 1)
    bridge = _dispatcher(_trusted_document(), {"echo": lambda payload: payload})
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "echo",
        "payload": {},
    })
    returned = Event()
    release_owner = Event()
    responses: list[dict[str, object]] = []

    def run() -> None:
        responses.append(bridge._dispatch_native(command))
        returned.set()
        assert release_owner.wait(1.0)

    owner = Thread(target=run)
    owner.start()
    assert returned.wait(1.0)
    token = responses[0]["response_token"]
    assert isinstance(token, str)
    assert bridge.dispatch(command)["error"]["code"] == "bridge_busy"

    assert bridge._dispatch_native("ack:" + ("0" * 32)) is False
    assert bridge._dispatch_native(f"ack:{token}") is True
    assert bridge.dispatch(command)["error"]["code"] == "bridge_busy"

    release_owner.set()
    owner.join(1.0)
    assert not owner.is_alive()
    bridge.wait_for_handlers(1.0)
    assert bridge.dispatch(command)["ok"] is True


def test_br_g_32_document_retirement_releases_unacknowledged_dead_workers() -> None:
    bridge = _dispatcher(_trusted_document(), {"echo": lambda payload: payload})
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "echo",
        "payload": {},
    })
    responses: list[dict[str, object]] = []
    owner = Thread(target=lambda: responses.append(bridge._dispatch_native(command)))
    owner.start()
    owner.join(1.0)
    assert not owner.is_alive()
    with pytest.raises(TimeoutError, match="did not quiesce"):
        bridge.wait_for_handlers(0.01)

    bridge._retire_document_responses()

    bridge.wait_for_handlers(1.0)
    assert bridge._dispatch_native(
        f"ack:{responses[0]['response_token']}"
    ) is False
    assert bridge.dispatch(command)["ok"] is True


def test_br_g_32_document_retirement_refuses_a_preempted_native_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = _dispatcher(_trusted_document(), {"echo": lambda payload: payload})
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "echo",
        "payload": {},
    })
    entered_token_generation = Event()
    resume_token_generation = Event()
    responses: list[dict[str, object]] = []
    generations: list[int | None] = []

    class DelayedToken:
        @property
        def hex(self) -> str:
            entered_token_generation.set()
            assert resume_token_generation.wait(1.0)
            return "a" * 32

    monkeypatch.setattr(bridge_module, "uuid4", lambda: DelayedToken())
    def dispatch() -> None:
        responses.append(bridge._dispatch_native(command))
        generations.append(bridge._claim_native_return_generation())
        generations.append(bridge._claim_native_return_generation())

    owner = Thread(target=dispatch)
    owner.start()
    assert entered_token_generation.wait(1.0)

    bridge._retire_document_responses()
    resume_token_generation.set()
    owner.join(1.0)

    assert not owner.is_alive()
    assert responses[0]["response_token"] is None
    assert responses[0]["response"]["error"]["code"] == "bridge_unavailable"
    assert generations == [0, None]
    assert bridge._is_document_generation_current(generations[0]) is False
    bridge.wait_for_handlers(1.0)
    assert bridge.dispatch(command)["ok"] is True


def test_br_g_32_direct_dispatch_does_not_reserve_native_worker_lifetime() -> None:
    bridge = _dispatcher(_trusted_document(), {"echo": lambda payload: payload})
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "echo",
        "payload": {},
    })

    for _ in range(65):
        assert bridge.dispatch(command)["ok"] is True
    assert bridge._admitted == 0
    native = bridge._dispatch_native(command)
    assert native["response_token"] is None
    assert native["response"]["error"]["code"] == "internal_error"
    assert bridge._admitted == 0


def test_async_small_preserves_direct_dispatch_and_delivers_exact_completion() -> None:
    calls: list[object] = []
    bridge = _async_dispatcher(
        lambda payload: calls.append(payload) or {"value": "complete"}
    )
    _channel, encoded, posted = _bind_completion_channel(bridge)
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "async_test",
        "payload": {"value": "input"},
    })

    direct = bridge.dispatch(command)
    assert direct["ok"] is True
    assert direct["result"] == {"value": "complete"}
    assert encoded == []

    native: list[dict[str, object]] = []
    owner = Thread(target=lambda: native.append(bridge._dispatch_native(command)))
    owner.start()
    owner.join(1.0)
    assert not owner.is_alive()
    assert posted.wait(1.0)
    admission = native[0]
    assert set(admission) == {"transport_version", "response_token", "completion"}
    response_token = admission["response_token"]
    assert isinstance(response_token, str)
    completion = admission["completion"]
    assert completion == {
        "phase": "completion",
        "generation": 0,
        "request_id": _REQUEST_ID,
        "completion_token": completion["completion_token"],
    }
    assert isinstance(completion["completion_token"], str)
    message = json.loads(encoded[0])
    assert message == {
        "kind": "namisync.command-completion.v1",
        "phase": "completion",
        "generation": 0,
        "request_id": _REQUEST_ID,
        "completion_token": completion["completion_token"],
        "response": {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": _REQUEST_ID,
            "ok": True,
            "result": {"value": "complete"},
        },
    }
    assert bridge._dispatch_native(f"ack:{response_token}") is True
    bridge._document._record("https://off-origin.invalid/")
    completion_ack = (
        f"ack:completion:0:{_REQUEST_ID}:{completion['completion_token']}"
    )
    assert bridge._dispatch_native(completion_ack) is True
    assert bridge._dispatch_native(completion_ack) is False
    bridge.wait_for_handlers(1.0)
    bridge._retire_document_responses()
    _channel.replace_document()
    assert bridge._dispatch_native(completion_ack) is False
    assert len(encoded) == 1
    assert calls == [{"value": "input"}, {"value": "input"}]


def test_async_small_reuses_shared_capacity_only_after_both_workers_and_receipts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge_module, "_MAX_ADMITTED_HANDLERS", 1)
    entered = Event()
    release_command = Event()
    release_native = Event()
    calls: list[object] = []

    def handler(payload: object) -> object:
        calls.append(payload)
        entered.set()
        assert release_command.wait(1.0)
        return {"value": "complete"}

    bridge = _async_dispatcher(handler)
    _channel, encoded, posted = _bind_completion_channel(bridge)
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "async_test",
        "payload": {},
    })
    native: list[dict[str, object]] = []
    native_returned = Event()

    def dispatch() -> None:
        native.append(bridge._dispatch_native(command))
        native_returned.set()
        assert release_native.wait(1.0)

    owner = Thread(target=dispatch)
    owner.start()
    assert entered.wait(1.0)
    assert native_returned.wait(1.0)
    response_token = native[0]["response_token"]
    completion = native[0]["completion"]
    assert isinstance(response_token, str)
    assert bridge.dispatch(command)["error"]["code"] == "bridge_busy"
    assert bridge._dispatch_native(f"ack:{response_token}") is True
    assert bridge.dispatch(command)["error"]["code"] == "bridge_busy"

    release_command.set()
    assert posted.wait(1.0)
    completion_ack = (
        f"ack:completion:0:{_REQUEST_ID}:{completion['completion_token']}"
    )
    assert bridge._dispatch_native(completion_ack) is True
    assert bridge.dispatch(command)["error"]["code"] == "bridge_busy"
    assert len(encoded) == 1

    release_native.set()
    owner.join(1.0)
    assert not owner.is_alive()
    assert bridge.dispatch(command)["ok"] is True
    bridge.wait_for_handlers(1.0)
    assert calls == [{}, {}]


def test_async_small_does_not_reap_after_both_receipts_until_command_worker_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge_module, "_MAX_ADMITTED_HANDLERS", 1)
    bridge = _async_dispatcher(lambda _payload: {"value": "complete"})
    channel, _encoded, posted = _bind_completion_channel(bridge)
    original_post = channel.post
    post_returned = Event()
    release_worker = Event()

    def post_then_hold(*args: object, **kwargs: object) -> None:
        original_post(*args, **kwargs)
        post_returned.set()
        assert release_worker.wait(1.0)

    channel.post = post_then_hold
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "async_test",
        "payload": {},
    })
    native: list[dict[str, object]] = []
    owner = Thread(target=lambda: native.append(bridge._dispatch_native(command)))
    owner.start()
    owner.join(1.0)
    assert not owner.is_alive()
    assert posted.wait(1.0)
    assert post_returned.wait(1.0)
    response_token = native[0]["response_token"]
    completion = native[0]["completion"]
    assert isinstance(response_token, str)
    assert bridge._dispatch_native(f"ack:{response_token}") is True
    assert bridge._dispatch_native(
        f"ack:completion:0:{_REQUEST_ID}:{completion['completion_token']}"
    ) is True
    assert bridge.dispatch(command)["error"]["code"] == "bridge_busy"

    release_worker.set()
    bridge.wait_for_handlers(1.0)
    assert bridge.dispatch(command)["ok"] is True


def test_async_small_shared_capacity_refuses_the_sixty_fifth_before_worker_creation() -> None:
    release = Event()
    lock = Lock()
    entered = 0
    all_entered = Event()

    def handler(_payload: object) -> object:
        nonlocal entered
        with lock:
            entered += 1
            if entered == 64:
                all_entered.set()
        assert release.wait(3.0)
        return {}

    bridge = _async_dispatcher(handler)
    channel, _encoded, _posted = _bind_completion_channel(bridge)
    admissions: list[dict[str, object]] = []

    def command(index: int) -> str:
        return json.dumps({
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": f"{index:032x}",
            "command": "async_test",
            "payload": {"index": index},
        })

    for index in range(64):
        owner = Thread(
            target=lambda index=index: admissions.append(
                bridge._dispatch_native(command(index))
            )
        )
        owner.start()
        owner.join(1.0)
        assert not owner.is_alive()
    assert all_entered.wait(1.0)

    refused: list[dict[str, object]] = []
    owner = Thread(target=lambda: refused.append(bridge._dispatch_native(command(64))))
    owner.start()
    owner.join(1.0)
    assert not owner.is_alive()
    assert len(admissions) == 64
    assert all("completion" in admission for admission in admissions)
    assert refused[0]["response_token"] is None
    assert refused[0]["response"]["error"]["code"] == "bridge_busy"
    with lock:
        assert entered == 64

    bridge._retire_document_responses()
    channel.replace_document()
    release.set()
    bridge.wait_for_handlers(3.0)


def test_async_small_worker_start_refusal_invokes_no_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    bridge = _async_dispatcher(lambda payload: calls.append(payload))
    _bind_completion_channel(bridge)
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "async_test",
        "payload": {},
    })
    enter_dispatch = Event()
    responses: list[dict[str, object]] = []
    original_start = Thread.start

    def dispatch() -> None:
        assert enter_dispatch.wait(1.0)
        responses.append(bridge._dispatch_native(command))

    owner = Thread(target=dispatch)
    owner.start()

    def start(worker: Thread) -> None:
        if worker.name.startswith("namisync-command-"):
            raise RuntimeError("injected command-worker start refusal")
        original_start(worker)

    monkeypatch.setattr(Thread, "start", start)
    enter_dispatch.set()
    owner.join(1.0)

    assert not owner.is_alive()
    assert calls == []
    assert responses[0]["response"]["error"]["code"] == "internal_error"
    token = responses[0]["response_token"]
    assert isinstance(token, str)
    assert bridge._dispatch_native(f"ack:{token}") is True
    bridge.wait_for_handlers(1.0)


def test_async_small_reload_before_command_worker_start_retires_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    bridge = _async_dispatcher(lambda payload: calls.append(payload) or {})
    channel, encoded, _posted = _bind_completion_channel(bridge)
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "async_test",
        "payload": {},
    })
    start_entered = Event()
    resume_start = Event()
    begin_dispatch = Event()
    responses: list[dict[str, object]] = []
    original_start = Thread.start

    def dispatch() -> None:
        assert begin_dispatch.wait(1.0)
        responses.append(bridge._dispatch_native(command))

    owner = Thread(target=dispatch)
    owner.start()

    def delayed_start(worker: Thread) -> None:
        if worker.name.startswith("namisync-command-"):
            start_entered.set()
            assert resume_start.wait(1.0)
        original_start(worker)

    monkeypatch.setattr(Thread, "start", delayed_start)
    begin_dispatch.set()
    assert start_entered.wait(1.0)
    bridge._retire_document_responses()
    channel.replace_document()
    resume_start.set()
    owner.join(1.0)
    assert not owner.is_alive()
    bridge.wait_for_handlers(1.0)

    assert calls == [{}]
    assert encoded == []
    assert set(responses[0]) == {
        "transport_version",
        "response_token",
        "completion",
    }
    assert bridge._dispatch_native(
        f"ack:{responses[0]['response_token']}"
    ) is False


def test_async_small_reload_during_handler_keeps_effect_and_retires_delivery() -> None:
    entered = Event()
    resume = Event()
    calls: list[object] = []

    def handler(payload: object) -> object:
        calls.append(payload)
        entered.set()
        assert resume.wait(1.0)
        return {"value": "finished"}

    bridge = _async_dispatcher(handler)
    channel, encoded, _posted = _bind_completion_channel(bridge)
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "async_test",
        "payload": {},
    })
    responses: list[dict[str, object]] = []
    owner = Thread(target=lambda: responses.append(bridge._dispatch_native(command)))
    owner.start()
    assert entered.wait(1.0)
    owner.join(1.0)
    assert not owner.is_alive()

    bridge._retire_document_responses()
    channel.replace_document()
    resume.set()
    bridge.wait_for_handlers(1.0)

    assert calls == [{}]
    assert encoded == []
    completion = responses[0]["completion"]
    assert bridge._dispatch_native(
        f"ack:completion:0:{_REQUEST_ID}:{completion['completion_token']}"
    ) is False


def test_async_small_reload_after_result_before_post_retires_delivery() -> None:
    bridge = _async_dispatcher(lambda _payload: {"value": "finished"})
    channel, encoded, _posted = _bind_completion_channel(bridge)
    original_post = channel.post
    post_entered = Event()
    resume_post = Event()

    def delayed_post(*args: object, **kwargs: object) -> None:
        post_entered.set()
        assert resume_post.wait(1.0)
        original_post(*args, **kwargs)

    channel.post = delayed_post
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "async_test",
        "payload": {},
    })
    owner = Thread(target=lambda: bridge._dispatch_native(command))
    owner.start()
    assert post_entered.wait(1.0)
    bridge._retire_document_responses()
    channel.replace_document()
    resume_post.set()
    owner.join(1.0)
    assert not owner.is_alive()
    bridge.wait_for_handlers(1.0)
    assert encoded == []


def test_async_small_reload_after_post_retires_unacknowledged_completion() -> None:
    calls: list[object] = []
    bridge = _async_dispatcher(lambda payload: calls.append(payload) or {})
    channel, encoded, posted = _bind_completion_channel(bridge)
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "async_test",
        "payload": {},
    })
    responses: list[dict[str, object]] = []
    owner = Thread(target=lambda: responses.append(bridge._dispatch_native(command)))
    owner.start()
    owner.join(1.0)
    assert not owner.is_alive()
    assert posted.wait(1.0)

    bridge._retire_document_responses()
    channel.replace_document()
    bridge.wait_for_handlers(1.0)

    completion = responses[0]["completion"]
    assert len(encoded) == 1
    assert calls == [{}]
    assert bridge._dispatch_native(
        f"ack:completion:0:{_REQUEST_ID}:{completion['completion_token']}"
    ) is False


def test_async_small_completion_accepts_exact_byte_ceiling_and_first_excess_is_uncertain() -> None:
    template = {
        "kind": "namisync.command-completion.v1",
        "phase": "completion",
        "generation": 0,
        "request_id": _REQUEST_ID,
        "completion_token": "0" * 32,
        "response": {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": _REQUEST_ID,
            "ok": True,
            "result": {"value": ""},
        },
    }
    base = len(json.dumps(
        template,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ))
    accepted = 65_536 - base
    fixed_error_sizes = {
        code: len(json.dumps(
            {
                **template,
                "response": {
                    "schema_version": BRIDGE_SCHEMA_VERSION,
                    "request_id": _REQUEST_ID,
                    "ok": False,
                    "error": {"code": code, "message": message},
                },
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8"))
        for code, message in bridge_module._ERROR_MESSAGES.items()
    }
    assert max(fixed_error_sizes.items(), key=lambda item: item[1]) == (
        "planning_refused",
        404,
    )

    def deliver(length: int) -> dict[str, object]:
        bridge = _async_dispatcher(lambda _payload: {"value": "x" * length})
        _channel, encoded, posted = _bind_completion_channel(bridge)
        command = json.dumps({
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": _REQUEST_ID,
            "command": "async_test",
            "payload": {},
        })
        native: list[dict[str, object]] = []
        owner = Thread(
            target=lambda: native.append(bridge._dispatch_native(command))
        )
        owner.start()
        owner.join(1.0)
        assert not owner.is_alive()
        assert posted.wait(1.0)
        response_token = native[0]["response_token"]
        completion = native[0]["completion"]
        assert isinstance(response_token, str)
        assert bridge._dispatch_native(f"ack:{response_token}") is True
        assert bridge._dispatch_native(
            f"ack:completion:0:{_REQUEST_ID}:{completion['completion_token']}"
        ) is True
        bridge.wait_for_handlers(1.0)
        return {"encoded": encoded[0], "message": json.loads(encoded[0])}

    at_limit = deliver(accepted)
    assert len(at_limit["encoded"].encode("utf-8")) == 65_536
    assert at_limit["message"]["response"]["ok"] is True

    first_excess = deliver(accepted + 1)
    assert len(first_excess["encoded"].encode("utf-8")) < 65_536
    assert first_excess["message"]["response"]["error"]["code"] == (
        "internal_error"
    )


def test_async_small_post_effect_encoding_failure_uses_fixed_uncertainty_completion() -> None:
    calls: list[object] = []
    bridge = _async_dispatcher(
        lambda payload: calls.append(payload) or {"value": "\ud800"}
    )
    _channel, encoded, posted = _bind_completion_channel(bridge)
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "async_test",
        "payload": {},
    })
    native: list[dict[str, object]] = []
    owner = Thread(target=lambda: native.append(bridge._dispatch_native(command)))
    owner.start()
    owner.join(1.0)
    assert not owner.is_alive()
    assert posted.wait(1.0)

    message = json.loads(encoded[0])
    assert calls == [{}]
    assert message["response"] == {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "ok": False,
        "error": {
            "code": "internal_error",
            "message": "NamiSync could not complete the desktop action.",
        },
    }
    response_token = native[0]["response_token"]
    completion = native[0]["completion"]
    assert isinstance(response_token, str)
    assert bridge._dispatch_native(f"ack:{response_token}") is True
    assert bridge._dispatch_native(
        f"ack:completion:0:{_REQUEST_ID}:{completion['completion_token']}"
    ) is True
    bridge.wait_for_handlers(1.0)


def test_async_small_completion_ack_requires_exact_phase_and_identity() -> None:
    bridge = _async_dispatcher(lambda _payload: {})
    _channel, _encoded, posted = _bind_completion_channel(bridge)
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "async_test",
        "payload": {},
    })
    native: list[dict[str, object]] = []
    owner = Thread(target=lambda: native.append(bridge._dispatch_native(command)))
    owner.start()
    owner.join(1.0)
    assert not owner.is_alive()
    assert posted.wait(1.0)
    completion = native[0]["completion"]
    token = completion["completion_token"]

    malformed = bridge._dispatch_native(
        f"ack:completed:0:{_REQUEST_ID}:{token}"
    )
    assert malformed["response"]["error"]["code"] == "internal_error"
    assert bridge._dispatch_native(
        f"ack:completion:1:{_REQUEST_ID}:{token}"
    ) is False
    assert bridge._dispatch_native(
        f"ack:completion:0:{'2' * 32}:{token}"
    ) is False
    assert bridge._dispatch_native(
        f"ack:completion:0:{_REQUEST_ID}:{'3' * 32}"
    ) is False
    assert bridge._dispatch_native(
        f"ack:completion:9007199254740992:{_REQUEST_ID}:{token}"
    ) is False

    response_token = native[0]["response_token"]
    assert isinstance(response_token, str)
    assert bridge._dispatch_native(f"ack:{response_token}") is True
    assert bridge._dispatch_native(
        f"ack:completion:0:{_REQUEST_ID}:{token}"
    ) is True
    bridge.wait_for_handlers(1.0)


def test_async_small_post_failure_is_delivery_uncertainty_without_repeated_effect() -> None:
    calls: list[object] = []
    bridge = _async_dispatcher(lambda payload: calls.append(payload) or {})
    channel, _encoded, _posted = _bind_completion_channel(bridge)
    core = channel._native_window.browser.webview.CoreWebView2

    def refuse(_value: str) -> None:
        raise RuntimeError("injected document post failure")

    core.PostWebMessageAsJson = refuse
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "async_test",
        "payload": {},
    })
    responses: list[dict[str, object]] = []
    owner = Thread(target=lambda: responses.append(bridge._dispatch_native(command)))
    owner.start()
    owner.join(1.0)
    assert not owner.is_alive()
    response_token = responses[0]["response_token"]
    assert isinstance(response_token, str)
    assert bridge._dispatch_native(f"ack:{response_token}") is True
    bridge.wait_for_handlers(1.0)

    assert calls == [{}]
    completion = responses[0]["completion"]
    assert bridge._dispatch_native(
        f"ack:completion:0:{_REQUEST_ID}:{completion['completion_token']}"
    ) is False


def test_async_small_close_timeout_is_retryable_until_command_worker_exits() -> None:
    entered = Event()
    resume = Event()

    def handler(_payload: object) -> object:
        entered.set()
        assert resume.wait(1.0)
        return {}

    bridge = _async_dispatcher(handler)
    _bind_completion_channel(bridge)
    command = json.dumps({
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": _REQUEST_ID,
        "command": "async_test",
        "payload": {},
    })
    owner = Thread(target=lambda: bridge._dispatch_native(command))
    owner.start()
    assert entered.wait(1.0)
    owner.join(1.0)
    assert not owner.is_alive()

    bridge.begin_close()
    with pytest.raises(TimeoutError, match="did not quiesce"):
        bridge.wait_for_handlers(0.01)
    assert bridge.dispatch(command)["error"]["code"] == "bridge_unavailable"

    resume.set()
    bridge.wait_for_handlers(1.0)
    assert bridge.dispatch(command)["error"]["code"] == "bridge_unavailable"


def test_pinned_pywebview_keeps_serialization_and_return_on_one_worker() -> None:
    from webview.util import js_bridge_call

    function = ast.parse(inspect.getsource(js_bridge_call)).body[0]
    worker = next(
        node for node in function.body
        if isinstance(node, ast.FunctionDef) and node.name == "_call"
    )
    assert len(worker.body) == 2
    dispatch_and_serialization, native_return = worker.body
    assert isinstance(dispatch_and_serialization, ast.Try)
    assert ast.unparse(dispatch_and_serialization.body[0]) == (
        "result = func(*func_params)"
    )
    assert "json.dumps(result)" in ast.unparse(dispatch_and_serialization.body[1])
    assert isinstance(native_return, ast.Expr)
    assert ast.unparse(native_return.value.func) == "window.evaluate_js"
    assert any(
        isinstance(node, ast.Assign)
        and ast.unparse(node) == "thread = Thread(target=_call)"
        for node in ast.walk(function)
    )


def test_namisync_bridge_module_constructs_no_javascript() -> None:
    source = inspect.getsource(
        __import__(
            "namisync.interfaces.web.bridge",
            fromlist=["bridge"],
        )
    )
    assert "evaluate_js" not in source
    assert "run_js" not in source
    assert "Window.state" not in source


def test_bridge_rejects_nonstandard_json_and_non_json_handler_results() -> None:
    bridge = _dispatcher(
        _trusted_document(),
        {
            "echo": lambda payload: payload,
            "bad_result": lambda payload: {"nested": {1: payload}},
        },
    )
    invalid_number = (
        f'{{"schema_version":1,"request_id":"{_REQUEST_ID}",'
        '"command":"echo","payload":{"value":NaN}}'
    )
    assert bridge.dispatch(invalid_number)["error"]["code"] == "invalid_request"

    duplicate_command = (
        f'{{"schema_version":1,"request_id":"{_REQUEST_ID}",'
        '"command":"echo","command":"echo","payload":{}}'
    )
    assert bridge.dispatch(duplicate_command)["error"]["code"] == "invalid_request"

    for invalid_version in (True, 1.0, "1"):
        response = bridge.dispatch(
            json.dumps(
                {
                    "schema_version": invalid_version,
                    "request_id": _REQUEST_ID,
                    "command": "echo",
                    "payload": {},
                }
            )
        )
        assert response["error"]["code"] == "unsupported_version"

    assert bridge.dispatch("\ud800")["error"]["code"] == "invalid_request"

    bad_result = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": _REQUEST_ID,
            "command": "bad_result",
            "payload": {},
        }
    )
    assert bridge.dispatch(bad_result)["error"]["code"] == "internal_error"


@pytest.mark.parametrize(
    "command_json",
    [
        (
            f'{{"schema_version":1,"request_id":"{_REQUEST_ID}",'
            '"command":"echo","payload":{"value":1e999}}'
        ),
        (
            f'{{"schema_version":1,"request_id":"{_REQUEST_ID}",'
            '"command":"echo","payload":{"value":"\\ud800"}}'
        ),
    ],
)
def test_bridge_rejects_non_json_payload_values_before_handler(
    command_json: str,
) -> None:
    handled: list[object] = []
    bridge = _dispatcher(_trusted_document(), {"echo": handled.append})

    assert bridge.dispatch(command_json)["error"]["code"] == "invalid_payload"

    assert handled == []
