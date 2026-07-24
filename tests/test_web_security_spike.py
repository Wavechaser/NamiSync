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
    ExactOrigin,
    WebView2Unavailable,
    install_pywebview2_guards,
    start_edge_chromium,
)


class EventHook:
    def __init__(self) -> None:
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def emit(self, args) -> None:
        for handler in self.handlers:
            handler(None, args)


class FakeCoreWebView2:
    def __init__(self) -> None:
        self.NavigationStarting = EventHook()
        self.NewWindowRequested = EventHook()


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
    return SimpleNamespace(
        native=SimpleNamespace(
            browser=SimpleNamespace(
                webview=SimpleNamespace(CoreWebView2=core)
            )
        )
    )


def test_native_webview2_hooks_cancel_untrusted_navigation_and_all_popups() -> None:
    core = FakeCoreWebView2()
    install_pywebview2_guards(
        _window(core),
        "http://127.0.0.1:41700",
    )
    trusted = NavigationArgs("http://127.0.0.1:41700/index.html")
    external = NavigationArgs("https://example.com/")
    core.NavigationStarting.emit(trusted)
    core.NavigationStarting.emit(external)
    popup = NewWindowArgs("https://example.com/")
    core.NewWindowRequested.emit(popup)

    assert not trusted.Cancel
    assert external.Cancel
    assert popup.Handled


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
    current = ["http://127.0.0.1:41700/index.html"]
    hostile = '</script><img src=x onerror="alert(1)">'
    bridge = BridgeDispatcher(
        origin=ExactOrigin.parse("http://127.0.0.1:41700"),
        current_url=lambda: current[0],
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

    current[0] = "https://example.com/"
    with pytest.raises(BridgeOriginError):
        bridge.dispatch(command)


def test_dispatch_is_the_only_public_bridge_method_and_allowlist_is_exact() -> None:
    bridge = BridgeDispatcher(
        origin=ExactOrigin.parse("https://app.invalid"),
        current_url=lambda: "https://app.invalid/index.html",
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
        origin=ExactOrigin.parse("https://app.invalid"),
        current_url=lambda: "https://app.invalid/",
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
