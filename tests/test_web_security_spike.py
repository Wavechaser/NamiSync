from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest

from namisync.interfaces.web.security_spike import (
    BRIDGE_SCHEMA_VERSION,
    BridgeDispatcher,
    BridgeOriginError,
    BridgeProtocolError,
    WebView2Unavailable,
    configure_pywebview2_security,
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


class FakeCoreWebView2:
    def __init__(self, source: str = "http://127.0.0.1:41700/index.html") -> None:
        self.Source = source
        self.NavigationStarting = EventHook()
        self.NewWindowRequested = EventHook()
        self.SourceChanged = EventHook()


class BeforeLoadHook:
    def __init__(self, window) -> None:
        self.handlers = []
        self._window = window

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def emit(self) -> None:
        self._window._on_ui_thread = True
        try:
            for handler in self.handlers:
                handler()
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
        source.rsplit("/", 1)[0],
    )
    window.events.before_load.emit()
    return document


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
    with pytest.raises(BridgeOriginError):
        bridge.dispatch(command)

    window.events.before_load.emit()
    window.events.before_load.emit()

    assert window.managed_webview.core_accesses == 1
    assert len(core.NavigationStarting.handlers) == 1
    assert len(core.NewWindowRequested.handlers) == 1
    assert len(core.SourceChanged.handlers) == 1
    assert bridge.dispatch(command)["result"] == {}


def test_native_installation_refuses_an_off_ui_before_load_callback() -> None:
    core = FakeCoreWebView2()
    window = _window(core)
    window.native.InvokeRequired = True
    configure_pywebview2_security(
        window,
        "http://127.0.0.1:41700",
    )

    with pytest.raises(RuntimeError, match="UI thread"):
        window.events.before_load.emit()

    assert window.managed_webview.core_accesses == 0
    assert len(core.NavigationStarting.handlers) == 0


def test_native_webview2_hooks_cancel_untrusted_navigation_and_all_popups() -> None:
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
    popup = NewWindowArgs("https://example.com/")
    core.NewWindowRequested.emit(popup, sender=core)

    assert not trusted.Cancel
    assert external.Cancel
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


def test_start_forces_edge_chromium_and_reports_missing_runtime() -> None:
    calls = []

    class Webview:
        @staticmethod
        def start(func=None, *, gui: str) -> None:
            calls.append((func, gui))

    setup = lambda: None
    start_edge_chromium(Webview, setup)
    assert calls == [(setup, "edgechromium")]

    class WebViewException(Exception):
        pass

    class BrokenWebview:
        @staticmethod
        def start(func=None, *, gui: str) -> None:
            del func, gui
            raise WebViewException("runtime missing")

    with pytest.raises(WebView2Unavailable, match="install"):
        start_edge_chromium(BrokenWebview)


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


def test_bridge_source_has_no_host_to_javascript_application_data_channel() -> None:
    source = inspect.getsource(
        __import__(
            "namisync.interfaces.web.security_spike",
            fromlist=["security_spike"],
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
