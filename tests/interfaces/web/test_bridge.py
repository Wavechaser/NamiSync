from __future__ import annotations

import inspect
import json
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import pytest

import namisync.interfaces.web.pywebview_runtime as pywebview_runtime
from namisync.interfaces.web.bridge import (
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
    bridge = BridgeDispatcher(document=document, handlers={})
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": "pending-document",
            "command": "ping",
            "payload": {},
        }
    )

    with pytest.raises(BridgeOriginError, match="origin is pending"):
        bridge.dispatch(command)

    origin = ExactOrigin.from_url("http://127.0.0.1:41700/index.html")
    document.bind_origin(origin)

    with pytest.raises(RuntimeError, match="already bound"):
        document.bind_origin(origin)
    with pytest.raises(BridgeOriginError, match="not attached"):
        bridge.dispatch(command)


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

    bridge = BridgeDispatcher(
        document=document,
        handlers={"ping": lambda payload: payload},
    )
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": "before-native-attach",
            "command": "ping",
            "payload": {},
        }
    )
    with pytest.raises(BridgeOriginError, match="not attached"):
        bridge.dispatch(command)

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

    bridge = BridgeDispatcher(
        document=document,
        handlers={"ping": lambda payload: payload},
    )
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": "failed-native-attach",
            "command": "ping",
            "payload": {},
        }
    )
    with pytest.raises(BridgeOriginError, match="attachment failed.*UI thread"):
        bridge.dispatch(command)


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

    bridge = BridgeDispatcher(
        document=document,
        handlers={"ping": lambda payload: payload},
    )
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": "after-cancelled-navigation",
            "command": "ping",
            "payload": {},
        }
    )
    assert bridge.dispatch(command)["result"] == {}

    core.Source = "https://example.com/"
    core.SourceChanged.emit(SimpleNamespace(), sender=core)
    with pytest.raises(BridgeOriginError):
        bridge.dispatch(command)


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
    bridge = BridgeDispatcher(
        document=document,
        handlers={"ping": lambda payload: payload},
    )
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": "after-window-open",
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


@pytest.mark.parametrize(
    ("version", "supported"),
    [
        ("85.0.9999.999", False),
        ("86.0.621.999", True),
        ("86.0.622", True),
        ("150.0.4078.105", True),
        ("not-a-version", False),
        (None, False),
    ],
)
def test_webview2_runtime_version_helper(version: object, supported: bool) -> None:
    assert pywebview_runtime.is_supported_webview2_version(version) is supported


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
    bridge = BridgeDispatcher(
        document=document,
        handlers={"next_events": lambda payload: [{"path": payload["path"]}]},
    )
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": "request-1",
            "command": "next_events",
            "payload": {"path": hostile},
        }
    )

    assert bridge.dispatch(command) == {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": "request-1",
        "result": [{"path": hostile}],
    }

    core.Source = "https://example.com/"
    core.SourceChanged.emit(SimpleNamespace(), sender=core)
    with pytest.raises(BridgeOriginError):
        bridge.dispatch(command)


def test_dispatch_is_the_only_public_bridge_method_and_allowlist_is_exact() -> None:
    bridge = BridgeDispatcher(
        document=_trusted_document(),
        handlers={"ping": lambda payload: payload},
    )
    public_methods = {
        name
        for name, member in inspect.getmembers(bridge, predicate=callable)
        if not name.startswith("_")
    }
    assert public_methods == {"dispatch"}

    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": "request-2",
            "command": "unknown",
            "payload": {},
        }
    )
    with pytest.raises(BridgeProtocolError, match="not allowed"):
        bridge.dispatch(command)


def test_empty_handler_surface_is_valid_but_invalid_entries_are_rejected() -> None:
    document = _trusted_document()
    bridge = BridgeDispatcher(document=document, handlers={})
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": "closed-slice-one-surface",
            "command": "ping",
            "payload": {},
        }
    )

    with pytest.raises(BridgeProtocolError, match="not allowed"):
        bridge.dispatch(command)
    for invalid_name in ("", "_private", 7):
        with pytest.raises(ValueError, match="public command names"):
            BridgeDispatcher(
                document=document,
                handlers={invalid_name: lambda payload: payload},
            )
    with pytest.raises(TypeError, match="must be callable"):
        BridgeDispatcher(document=document, handlers={"ping": object()})


def test_bridge_close_gate_rejects_new_and_waits_for_admitted_handler() -> None:
    entered = Event()
    release = Event()
    finished = Event()

    def slow_handler(payload):
        entered.set()
        assert release.wait(1.0)
        return payload

    bridge = BridgeDispatcher(
        document=_trusted_document(),
        handlers={"slow": slow_handler},
    )
    command = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": "admitted-before-close",
            "command": "slow",
            "payload": {"value": 1},
        }
    )
    dispatch_thread = Thread(target=lambda: bridge.dispatch(command))
    dispatch_thread.start()
    assert entered.wait(1.0)

    bridge._reject_new()
    waiter = Thread(target=lambda: (bridge._wait_for_handlers(), finished.set()))
    waiter.start()

    assert not finished.wait(0.05)
    with pytest.raises(BridgeProtocolError, match="bridge is closing"):
        bridge.dispatch(command)
    release.set()
    dispatch_thread.join(1.0)
    waiter.join(1.0)

    assert not dispatch_thread.is_alive()
    assert not waiter.is_alive()
    assert finished.is_set()


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
    bridge = BridgeDispatcher(
        document=_trusted_document(),
        handlers={
            "echo": lambda payload: payload,
            "bad_result": lambda payload: {"nested": {1: payload}},
        },
    )
    invalid_number = (
        '{"schema_version":1,"request_id":"request-3",'
        '"command":"echo","payload":{"value":NaN}}'
    )
    with pytest.raises(BridgeProtocolError, match="not valid JSON"):
        bridge.dispatch(invalid_number)

    duplicate_command = (
        '{"schema_version":1,"request_id":"request-duplicate",'
        '"command":"echo","command":"echo","payload":{}}'
    )
    with pytest.raises(BridgeProtocolError, match="not valid JSON"):
        bridge.dispatch(duplicate_command)

    for invalid_version in (True, 1.0, "1"):
        with pytest.raises(BridgeProtocolError, match="schema version"):
            bridge.dispatch(
                json.dumps(
                    {
                        "schema_version": invalid_version,
                        "request_id": "request-version",
                        "command": "echo",
                        "payload": {},
                    }
                )
            )

    with pytest.raises(BridgeProtocolError, match="Unicode"):
        bridge.dispatch("\ud800")

    bad_result = json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": "request-4",
            "command": "bad_result",
            "payload": {},
        }
    )
    with pytest.raises(BridgeProtocolError, match="returned non-JSON"):
        bridge.dispatch(bad_result)


@pytest.mark.parametrize(
    "command_json",
    [
        (
            '{"schema_version":1,"request_id":"overflow",'
            '"command":"echo","payload":{"value":1e999}}'
        ),
        (
            '{"schema_version":1,"request_id":"surrogate",'
            '"command":"echo","payload":{"value":"\\ud800"}}'
        ),
    ],
)
def test_bridge_rejects_non_json_payload_values_before_handler(
    command_json: str,
) -> None:
    handled: list[object] = []
    bridge = BridgeDispatcher(
        document=_trusted_document(),
        handlers={"echo": handled.append},
    )

    with pytest.raises(BridgeProtocolError):
        bridge.dispatch(command_json)

    assert handled == []
