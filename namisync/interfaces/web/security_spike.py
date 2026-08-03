"""Stage 6 proof of the pywebview/WebView2 host security boundary."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from threading import Lock
from typing import Protocol
from urllib.parse import SplitResult, urlsplit

from .pywebview_runtime import has_webview2_runtime, missing_dotnet_framework


BRIDGE_SCHEMA_VERSION = 1
_MAX_COMMAND_BYTES = 64 * 1024
_REQUIRED_WEBVIEW_SETTINGS: tuple[tuple[str, object], ...] = (
    ("OPEN_EXTERNAL_LINKS_IN_BROWSER", False),
    ("ALLOW_FILE_URLS", False),
    ("ALLOW_DOWNLOADS", False),
    ("REMOTE_DEBUGGING_PORT", None),
)
_WEBVIEW2_INSTALL_MESSAGE = (
    "NamiSync requires Microsoft Edge WebView2 Runtime; install it and restart "
    "NamiSync."
)
_DOTNET_INSTALL_MESSAGE = (
    "NamiSync requires Microsoft .NET Framework 4.6.2 or later before Microsoft "
    "Edge WebView2 Runtime can be used; install it and restart NamiSync."
)


class BridgeProtocolError(ValueError):
    """A bridge command is malformed, unsupported, or not JSON-safe."""


class BridgeOriginError(PermissionError):
    """Native document authority is unavailable or outside the packaged origin."""


class WebView2Unavailable(RuntimeError):
    """The required Edge Chromium renderer could not be started."""


class _AttachmentError(RuntimeError):
    """A sanitized native-guard attachment failure."""


class _WebviewModule(Protocol):
    settings: MutableMapping[str, object]
    renderer: str | None
    windows: list[object]

    def start(self, func=None, *, gui: str, debug: bool) -> None: ...


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
            raise ValueError(
                "packaged asset origin must not include a path, query, or fragment"
            )
        return cls._from_split(parsed)

    @classmethod
    def from_url(cls, value: str) -> ExactOrigin:
        """Derive an origin from a complete packaged-asset URL."""

        return cls._from_split(urlsplit(value))

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
            parsed_port = parsed.port
        except ValueError as error:
            raise ValueError("packaged asset origin has an invalid port") from error
        port = parsed_port if parsed_port is not None else default_port
        return cls(parsed.scheme.lower(), parsed.hostname.lower(), port)

    def allows(self, value: str) -> bool:
        try:
            return ExactOrigin._from_split(urlsplit(value)) == self
        except (TypeError, ValueError):
            return False

    def require(self, value: str) -> None:
        if not self.allows(value):
            raise BridgeOriginError("bridge dispatch rejected outside packaged origin")


class NativeDocumentState:
    """Thread-safe native attachment and top-level document state."""

    def __init__(self, origin: ExactOrigin) -> None:
        self._origin = origin
        self._lock = Lock()
        self._current_url = ""
        self._attached = False
        self._attachment_error: str | None = None

    @property
    def is_attached(self) -> bool:
        with self._lock:
            return self._attached

    @property
    def attachment_error(self) -> str | None:
        with self._lock:
            return self._attachment_error

    def require_trusted(self) -> None:
        with self._lock:
            attached = self._attached
            attachment_error = self._attachment_error
            current_url = self._current_url
        if attachment_error is not None:
            raise BridgeOriginError(
                "bridge unavailable because WebView2 security attachment failed: "
                f"{attachment_error}"
            )
        if not attached:
            raise BridgeOriginError(
                "bridge unavailable because WebView2 security guards are not attached"
            )
        self._origin.require(current_url)

    def _mark_attached(self, current_url: str) -> None:
        with self._lock:
            self._current_url = current_url
            self._attached = True

    def _record_attachment_failure(self, message: str) -> None:
        with self._lock:
            self._attachment_error = message

    def _record(self, current_url: str) -> None:
        with self._lock:
            self._current_url = current_url


class _NativeNavigationGuard:
    """Installs native WebView2 guards behind pywebview's Windows backend."""

    def __init__(
        self,
        origin: ExactOrigin,
        document: NativeDocumentState,
    ) -> None:
        self._origin = origin
        self._document = document

    def attach(self, core_webview2: object) -> None:
        try:
            core_webview2.NavigationStarting += self._on_navigation_starting
            core_webview2.FrameNavigationStarting += (
                self._on_frame_navigation_starting
            )
            core_webview2.NewWindowRequested += self._on_new_window_requested
            core_webview2.SourceChanged += self._on_source_changed
        except AttributeError as error:
            raise _AttachmentError(
                "pywebview Edge Chromium backend does not expose required "
                "WebView2 navigation events"
            ) from error
        current_url = _core_source(core_webview2)
        if not current_url:
            raise _AttachmentError("WebView2 document source is unavailable")
        self._document._mark_attached(current_url)

    def _on_navigation_starting(self, sender: object, args: object) -> None:
        del sender
        if not self._origin.allows(_event_uri(args)):
            _set_event_flag(args, "Cancel", True)

    def _on_new_window_requested(self, sender: object, args: object) -> None:
        del sender
        _set_event_flag(args, "Handled", True)

    def _on_frame_navigation_starting(self, sender: object, args: object) -> None:
        del sender
        _set_event_flag(args, "Cancel", True)

    def _on_source_changed(self, sender: object, args: object) -> None:
        del args
        self._document._record(_core_source(sender))


def configure_pywebview2_security(
    window: object, trusted_url: str
) -> NativeDocumentState:
    """Attach native guards synchronously before pywebview exposes its API."""

    origin = ExactOrigin.from_url(trusted_url)
    document = NativeDocumentState(origin)
    guard = _NativeNavigationGuard(origin, document)
    attempted = False

    def attach_before_load() -> None:
        nonlocal attempted
        if attempted:
            return
        attempted = True
        try:
            try:
                native = window.native
                if native.InvokeRequired:
                    raise _AttachmentError(
                        "WebView2 security guards must attach on the WinForms UI "
                        "thread"
                    )
                core = native.browser.webview.CoreWebView2
            except AttributeError as error:
                raise _AttachmentError(
                    "forced Edge Chromium backend is unavailable; install Microsoft "
                    "Edge WebView2 Runtime"
                ) from error
            if core is None:
                raise _AttachmentError("WebView2 is not initialized")
            guard.attach(core)
        except Exception as error:
            document._record_attachment_failure(
                _safe_attachment_failure(error)
            )
            raise

    try:
        window.events.before_load += attach_before_load
    except AttributeError as error:
        raise RuntimeError(
            "pywebview does not expose the synchronous before_load event"
        ) from error
    return document


def _safe_attachment_failure(error: Exception) -> str:
    if isinstance(error, _AttachmentError):
        return str(error)
    return "native WebView2 security guards could not attach"


def harden_pywebview_settings(webview_module: _WebviewModule) -> None:
    """Pin pywebview settings that close renderer escape paths."""

    for name, value in _REQUIRED_WEBVIEW_SETTINGS:
        try:
            if name not in webview_module.settings:
                raise KeyError(name)
            webview_module.settings[name] = value
            if webview_module.settings[name] != value:
                raise ValueError(name)
        except Exception as error:
            raise RuntimeError(
                f"required pywebview security setting is unavailable: {name}"
            ) from error


def prepare_pywebview_host(webview_module: _WebviewModule) -> None:
    """Harden pywebview and refuse a missing WebView2 before window creation."""

    harden_pywebview_settings(webview_module)
    # Presence probe only. The detector reads the value itself; this turns a
    # pywebview that dropped the key into the same actionable settings error as
    # the hardened keys above, instead of an opaque KeyError from the detector.
    try:
        _ = webview_module.settings["WEBVIEW2_RUNTIME_PATH"]
    except Exception as error:
        raise RuntimeError(
            "required pywebview security setting is unavailable: "
            "WEBVIEW2_RUNTIME_PATH"
        ) from error
    if not has_webview2_runtime(webview_module.settings):
        raise WebView2Unavailable(
            _DOTNET_INSTALL_MESSAGE
            if missing_dotnet_framework()
            else _WEBVIEW2_INSTALL_MESSAGE
        )


def start_edge_chromium(
    webview_module: _WebviewModule,
    setup: Callable[[], None] | None = None,
    *,
    on_initialized: Callable[[], None] | None = None,
) -> None:
    """Force pywebview's Edge Chromium renderer; never accept MSHTML fallback."""

    prepare_pywebview_host(webview_module)
    try:
        window = webview_module.windows[0]
        initialized_event = window.events.initialized
    except (AttributeError, IndexError) as error:
        raise RuntimeError(
            "create a pywebview window before starting the desktop host"
        ) from error

    renderer_checked = False
    renderer_error: WebView2Unavailable | None = None
    host_initialization_error: Exception | None = None

    def initialize_host_if_edge_chromium() -> bool | None:
        nonlocal renderer_checked, renderer_error, host_initialization_error
        renderer_checked = True
        if webview_module.renderer != "edgechromium":
            renderer_error = WebView2Unavailable(_WEBVIEW2_INSTALL_MESSAGE)
            return False
        if on_initialized is not None:
            try:
                on_initialized()
            except Exception as error:
                host_initialization_error = error
                return False
        return None

    initialized_event += initialize_host_if_edge_chromium
    webview_module.start(setup, gui="edgechromium", debug=False)
    if renderer_error is not None:
        raise renderer_error
    if host_initialization_error is not None:
        raise host_initialization_error
    if not renderer_checked:
        raise RuntimeError("pywebview renderer initialization was not observed")


class BridgeDispatcher:
    """The one JS-exposed object: versioned allowlisted structured RPC."""

    def __init__(
        self,
        *,
        document: NativeDocumentState,
        handlers: Mapping[str, Callable[[Mapping[str, object]], object]],
    ) -> None:
        if not handlers or any(
            not isinstance(name, str) or not name or name.startswith("_")
            for name in handlers
        ):
            raise ValueError("bridge handlers require explicit public command names")
        if any(not callable(handler) for handler in handlers.values()):
            raise TypeError("every bridge command handler must be callable")
        self._document = document
        self._handlers = dict(handlers)

    def dispatch(self, command_json: str) -> dict[str, object]:
        """Validate one command and return ordinary structured data."""

        self._document.require_trusted()
        if not isinstance(command_json, str):
            raise BridgeProtocolError("bridge command must be a JSON string")
        try:
            command_size = len(command_json.encode("utf-8"))
        except UnicodeEncodeError as error:
            raise BridgeProtocolError(
                "bridge command must contain valid Unicode"
            ) from error
        if command_size > _MAX_COMMAND_BYTES:
            raise BridgeProtocolError("bridge command exceeds the size limit")
        try:
            raw = json.loads(
                command_json,
                object_pairs_hook=_unique_object,
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
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != BRIDGE_SCHEMA_VERSION
    ):
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
    _require_json_value(request_id)
    _require_json_value(command)
    _require_json_value(payload)
    return {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": request_id,
        "command": command,
        "payload": payload,
    }


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON number: {value}")


def _unique_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _require_json_value(value: object) -> None:
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise BridgeProtocolError(
                "structured bridge data contains invalid Unicode"
            ) from error
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


def _core_source(core_webview2: object) -> str:
    value = getattr(core_webview2, "Source", None)
    if value is None:
        getter = getattr(core_webview2, "get_Source", None)
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
