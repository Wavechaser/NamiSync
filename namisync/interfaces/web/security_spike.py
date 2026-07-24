"""Stage 1 proof of the pywebview/WebView2 bridge security boundary."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import SplitResult, urlsplit


BRIDGE_SCHEMA_VERSION = 1
_MAX_COMMAND_BYTES = 64 * 1024


class BridgeProtocolError(ValueError):
    """A bridge command is malformed, unsupported, or not JSON-safe."""


class BridgeOriginError(PermissionError):
    """The current top-level document is not the packaged asset origin."""


class WebView2Unavailable(RuntimeError):
    """The required Edge Chromium renderer could not be started."""


class _WebviewModule(Protocol):
    def start(self, func=None, *, gui: str) -> None: ...


@dataclass(frozen=True, slots=True)
class ExactOrigin:
    """A conventional scheme/host/effective-port origin comparison."""

    scheme: str
    host: str
    port: int

    @classmethod
    def parse(cls, value: str) -> ExactOrigin:
        parsed = urlsplit(value)
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("packaged asset origin must not include a path or query")
        return cls._from_split(parsed)

    @classmethod
    def _from_split(cls, parsed: SplitResult) -> ExactOrigin:
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("packaged asset origin must be an HTTP(S) origin")
        default_port = 443 if parsed.scheme.lower() == "https" else 80
        try:
            port = parsed.port or default_port
        except ValueError as error:
            raise ValueError("packaged asset origin has an invalid port") from error
        return cls(parsed.scheme.lower(), parsed.hostname.lower(), port)

    def allows(self, value: str) -> bool:
        try:
            return ExactOrigin._from_split(urlsplit(value)) == self
        except (TypeError, ValueError):
            return False

    def require(self, value: str) -> None:
        if not self.allows(value):
            raise BridgeOriginError("bridge dispatch rejected outside packaged origin")


class NativeNavigationGuard:
    """Installs native WebView2 guards behind pywebview's Windows backend."""

    def __init__(self, origin: ExactOrigin) -> None:
        self._origin = origin

    def attach(self, core_webview2: object) -> None:
        try:
            core_webview2.NavigationStarting += self._on_navigation_starting
            core_webview2.NewWindowRequested += self._on_new_window_requested
        except AttributeError as error:
            raise RuntimeError(
                "pywebview Edge Chromium backend does not expose required "
                "WebView2 navigation events"
            ) from error

    def _on_navigation_starting(self, sender: object, args: object) -> None:
        del sender
        if not self._origin.allows(_event_uri(args)):
            _set_event_flag(args, "Cancel", True)

    def _on_new_window_requested(self, sender: object, args: object) -> None:
        del sender
        _set_event_flag(args, "Handled", True)


def install_pywebview2_guards(
    window: object, trusted_origin: str
) -> NativeNavigationGuard:
    """Reach the forced Edge backend once and attach native WebView2 handlers."""

    try:
        core = window.native.browser.webview.CoreWebView2
    except AttributeError as error:
        raise RuntimeError(
            "forced Edge Chromium backend is unavailable; install Microsoft "
            "Edge WebView2 Runtime"
        ) from error
    if core is None:
        raise RuntimeError("WebView2 is not initialized")
    guard = NativeNavigationGuard(ExactOrigin.parse(trusted_origin))
    guard.attach(core)
    return guard


def start_edge_chromium(
    webview_module: _WebviewModule,
    setup: Callable[[], None] | None = None,
) -> None:
    """Force pywebview's Edge Chromium renderer; never accept MSHTML fallback."""

    try:
        webview_module.start(setup, gui="edgechromium")
    except Exception as error:
        if type(error).__name__ != "WebViewException":
            raise
        raise WebView2Unavailable(
            "NamiSync requires Microsoft Edge WebView2 Runtime; install it "
            "and restart NamiSync."
        ) from error


class BridgeDispatcher:
    """The one JS-exposed object: versioned allowlisted structured RPC."""

    def __init__(
        self,
        *,
        origin: ExactOrigin,
        current_url: Callable[[], str],
        handlers: Mapping[str, Callable[[Mapping[str, object]], object]],
    ) -> None:
        if not handlers or any(
            not isinstance(name, str) or not name or name.startswith("_")
            for name in handlers
        ):
            raise ValueError("bridge handlers require explicit public command names")
        if any(not callable(handler) for handler in handlers.values()):
            raise TypeError("every bridge command handler must be callable")
        self._origin = origin
        self._current_url = current_url
        self._handlers = dict(handlers)

    def dispatch(self, command_json: str) -> dict[str, object]:
        """Validate one command and return ordinary structured data."""

        self._origin.require(self._current_url())
        if not isinstance(command_json, str):
            raise BridgeProtocolError("bridge command must be a JSON string")
        if len(command_json.encode("utf-8")) > _MAX_COMMAND_BYTES:
            raise BridgeProtocolError("bridge command exceeds the size limit")
        try:
            raw = json.loads(
                command_json,
                parse_constant=lambda value: _reject_json_constant(value),
            )
        except (json.JSONDecodeError, ValueError) as error:
            raise BridgeProtocolError("bridge command is not valid JSON") from error
        command = _validate_command(raw)
        name = command["command"]
        handler = self._handlers.get(name)
        if handler is None:
            raise BridgeProtocolError(f"bridge command is not allowed: {name}")
        result = handler(command["payload"])
        try:
            _require_json_value(result)
        except BridgeProtocolError as error:
            raise BridgeProtocolError(
                f"bridge handler returned non-JSON data: {name}"
            ) from error
        return {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": command["request_id"],
            "result": result,
        }


def _validate_command(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "request_id",
        "command",
        "payload",
    }:
        raise BridgeProtocolError("bridge command has missing or unknown fields")
    if value["schema_version"] != BRIDGE_SCHEMA_VERSION:
        raise BridgeProtocolError(
            f"unsupported bridge schema version: {value['schema_version']}"
        )
    request_id = value["request_id"]
    command = value["command"]
    payload = value["payload"]
    if not isinstance(request_id, str) or not request_id:
        raise BridgeProtocolError("bridge request_id must be a non-empty string")
    if not isinstance(command, str) or not command:
        raise BridgeProtocolError("bridge command name must be a non-empty string")
    if not isinstance(payload, dict) or not all(
        isinstance(key, str) for key in payload
    ):
        raise BridgeProtocolError("bridge payload must be a string-keyed object")
    return {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": request_id,
        "command": command,
        "payload": payload,
    }


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON number: {value}")


def _require_json_value(value: object) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if math.isfinite(value):
            return
        raise BridgeProtocolError("structured bridge data contains a non-finite number")
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise BridgeProtocolError(
                "structured bridge data contains a non-string object key"
            )
        for item in value.values():
            _require_json_value(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _require_json_value(item)
        return
    raise BridgeProtocolError("structured bridge data is not JSON-compatible")


def _event_uri(args: object) -> str:
    value = getattr(args, "Uri", None)
    if value is None:
        getter = getattr(args, "get_Uri", None)
        if callable(getter):
            value = getter()
    return "" if value is None else str(value)


def _set_event_flag(args: object, name: str, value: bool) -> None:
    setter = getattr(args, f"set_{name}", None)
    if callable(setter):
        setter(value)
        return
    try:
        setattr(args, name, value)
    except (AttributeError, TypeError) as error:
        raise RuntimeError(f"WebView2 event does not expose {name}") from error
