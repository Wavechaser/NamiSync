"""Pywebview/WebView2 host security and structured bridge boundary."""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import Condition, Lock
from typing import TYPE_CHECKING, Protocol
from urllib.parse import SplitResult, urlsplit

from .pywebview_runtime import (
    WebView2RefusalReason,
    probe_webview2_runtime,
    require_supported_pythonnet_runtime,
)

if TYPE_CHECKING:
    from .commands import CommandSpec


BRIDGE_SCHEMA_VERSION = 1
_MAX_COMMAND_BYTES = 64 * 1024
_OPAQUE_ID = re.compile(r"[0-9a-f]{32}")
_ERROR_MESSAGES = {
    "invalid_request": "The desktop request is invalid.",
    "unsupported_version": (
        "Restart NamiSync to load a compatible desktop page."
    ),
    "unknown_command": "This desktop action is not available.",
    "invalid_payload": "The desktop action contains invalid data.",
    "request_too_large": "The desktop request is too large.",
    "slot_unavailable": (
        "That folder selection is no longer available. Choose both folders again."
    ),
    "picker_unavailable": "The folder picker could not open. Try again.",
    "command_conflict": (
        "This action no longer matches its first attempt. Start the action again."
    ),
    "planning_refused": (
        "NamiSync could not start a plan for those folders. Review both folders "
        "and try again."
    ),
    "bridge_unavailable": (
        "NamiSync is closing or this desktop page is no longer trusted."
    ),
    "internal_error": "NamiSync could not complete the desktop action.",
}
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
_RUNTIME_DETECTION_MESSAGE = (
    "NamiSync could not verify its Microsoft .NET Framework and Edge WebView2 "
    "Runtime prerequisites; restart NamiSync. If this continues, repair or "
    "reinstall those components."
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

    def start(
        self,
        func=None,
        *,
        gui: str,
        debug: bool,
        http_server: bool = True,
        private_mode: bool = True,
        storage_path: str | Path | None = None,
    ) -> None: ...


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

    def __init__(self, origin: ExactOrigin | None = None) -> None:
        if origin is not None and not isinstance(origin, ExactOrigin):
            raise TypeError("native document origin must be an ExactOrigin")
        self._origin = origin
        self._lock = Lock()
        self._current_url = ""
        self._attached = False
        self._attachment_error: str | None = None
        self._security_configuration_claimed = False

    @property
    def is_attached(self) -> bool:
        with self._lock:
            return self._attached

    @property
    def attachment_error(self) -> str | None:
        with self._lock:
            return self._attachment_error

    def bind_origin(self, origin: ExactOrigin) -> None:
        """Bind the one packaged origin that can authorize this document."""

        if not isinstance(origin, ExactOrigin):
            raise TypeError("native document origin must be an ExactOrigin")
        with self._lock:
            if self._origin is not None:
                raise RuntimeError("native document origin is already bound")
            self._origin = origin

    def require_trusted(self) -> None:
        with self._lock:
            origin = self._origin
            attached = self._attached
            attachment_error = self._attachment_error
            current_url = self._current_url
        if attachment_error is not None:
            raise BridgeOriginError(
                "bridge unavailable because WebView2 security attachment failed: "
                f"{attachment_error}"
            )
        if origin is None:
            raise BridgeOriginError(
                "bridge unavailable because packaged document origin is pending"
            )
        if not attached:
            raise BridgeOriginError(
                "bridge unavailable because WebView2 security guards are not attached"
            )
        origin.require(current_url)

    def _require_bound_origin(self, expected: ExactOrigin) -> ExactOrigin:
        with self._lock:
            origin = self._origin
        if origin is None:
            raise RuntimeError(
                "bind the packaged document origin before configuring WebView2 security"
            )
        if origin != expected:
            raise ValueError(
                "trusted URL does not match the bound packaged document origin"
            )
        return origin

    def _claim_security_configuration(self) -> bool:
        with self._lock:
            if self._security_configuration_claimed:
                return False
            self._security_configuration_claimed = True
            return True

    def _release_security_configuration(self) -> None:
        with self._lock:
            self._security_configuration_claimed = False

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
    window: object,
    trusted_url: str,
    *,
    document: NativeDocumentState | None = None,
    on_browser_version: Callable[[str], None] | None = None,
) -> NativeDocumentState:
    """Attach native guards synchronously before pywebview exposes its API."""

    origin = ExactOrigin.from_url(trusted_url)
    if document is None:
        document = NativeDocumentState(origin)
    elif not isinstance(document, NativeDocumentState):
        raise TypeError("document must be a NativeDocumentState")
    else:
        origin = document._require_bound_origin(origin)
    if not document._claim_security_configuration():
        return document
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
            if on_browser_version is not None:
                on_browser_version(str(core.Environment.BrowserVersionString))
            guard.attach(core)
        except Exception as error:
            document._record_attachment_failure(
                _safe_attachment_failure(error)
            )
            raise

    try:
        window.events.before_load += attach_before_load
    except AttributeError as error:
        document._release_security_configuration()
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

    require_supported_pythonnet_runtime()
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
    runtime_probe = probe_webview2_runtime(webview_module.settings)
    if not runtime_probe.available:
        if (
            runtime_probe.refusal_reason
            is WebView2RefusalReason.DOTNET_FRAMEWORK
        ):
            message = _DOTNET_INSTALL_MESSAGE
        elif runtime_probe.refusal_reason is WebView2RefusalReason.WEBVIEW2_RUNTIME:
            message = _WEBVIEW2_INSTALL_MESSAGE
        else:
            message = _RUNTIME_DETECTION_MESSAGE
        raise WebView2Unavailable(message)


def start_edge_chromium(
    webview_module: _WebviewModule,
    setup: Callable[[], None] | None = None,
    *,
    on_initialized: Callable[[], None] | None = None,
    storage_path: str | Path | None = None,
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
    if storage_path is None:
        webview_module.start(setup, gui="edgechromium", debug=False)
    else:
        webview_module.start(
            setup,
            gui="edgechromium",
            debug=False,
            http_server=True,
            private_mode=True,
            storage_path=storage_path,
        )
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
        commands: Mapping[str, CommandSpec],
    ) -> None:
        from .commands import CommandSpec

        snapshot = dict(commands)
        if any(
            not isinstance(name, str) or not name or name.startswith("_")
            for name in snapshot
        ):
            raise ValueError("bridge commands require explicit public command names")
        if any(type(spec) is not CommandSpec for spec in snapshot.values()):
            raise TypeError("every bridge command must be an exact CommandSpec")
        self._document = document
        self._commands = snapshot
        self._admission = Condition(Lock())
        self._accepting = True
        self._admitted = 0

    def dispatch(self, command_json: str) -> dict[str, object]:
        """Return one exact response envelope; never export a Python failure."""

        if not self._admit():
            return self._failure(None, None, "bridge_unavailable")
        try:
            try:
                self._document.require_trusted()
            except BaseException:
                return self._failure(None, None, "bridge_unavailable")

            if type(command_json) is not str:
                return self._failure(None, None, "invalid_request")
            try:
                command_size = len(command_json.encode("utf-8"))
            except UnicodeEncodeError:
                return self._failure(None, None, "invalid_request")
            if command_size > _MAX_COMMAND_BYTES:
                return self._failure(None, None, "request_too_large")
            try:
                raw = json.loads(
                    command_json,
                    object_pairs_hook=_unique_object,
                    parse_constant=lambda value: _reject_json_constant(value),
                )
            except Exception:
                return self._failure(None, None, "invalid_request")

            request_id = _recover_request_id(raw)
            if (
                type(raw) is not dict
                or set(raw)
                != {"schema_version", "request_id", "command", "payload"}
                or request_id is None
            ):
                return self._failure(request_id, None, "invalid_request")
            if (
                type(raw["schema_version"]) is not int
                or raw["schema_version"] != BRIDGE_SCHEMA_VERSION
            ):
                return self._failure(request_id, None, "unsupported_version")

            name = raw["command"]
            try:
                _require_json_value(name)
            except BridgeProtocolError:
                return self._failure(request_id, None, "invalid_request")
            if type(name) is not str or not name:
                return self._failure(request_id, None, "invalid_request")
            spec = self._commands.get(name)
            if spec is None:
                return self._failure(request_id, None, "unknown_command")

            payload = raw["payload"]
            if type(payload) is not dict:
                return self._failure(request_id, name, "invalid_payload")
            try:
                _require_json_value(payload)
            except BridgeProtocolError:
                return self._failure(request_id, name, "invalid_payload")

            from .commands import (
                CommandConflictError,
                CommandPayloadError,
                PickerUnavailableError,
                PlanningRefusedError,
            )
            from .slots import SlotUnavailableError

            try:
                result = spec.invoke(payload)
            except CommandPayloadError:
                return self._failure(request_id, name, "invalid_payload")
            except SlotUnavailableError:
                return self._failure(request_id, name, "slot_unavailable")
            except PickerUnavailableError:
                return self._failure(request_id, name, "picker_unavailable")
            except CommandConflictError:
                return self._failure(request_id, name, "command_conflict")
            except PlanningRefusedError:
                return self._failure(request_id, name, "planning_refused")
            except BaseException:
                return self._failure(request_id, name, "internal_error")
            try:
                result = to_primitive_view(result)
            except BaseException:
                return self._failure(request_id, name, "internal_error")
            return {
                "schema_version": BRIDGE_SCHEMA_VERSION,
                "request_id": request_id,
                "ok": True,
                "result": result,
            }
        except BaseException:
            return self._failure(None, None, "internal_error")
        finally:
            self._release()

    def _failure(
        self,
        request_id: str | None,
        command: str | None,
        code: str,
    ) -> dict[str, object]:
        try:
            logging.getLogger("namisync").info(
                "bridge.refused request_id=%s command=%s code=%s",
                request_id if request_id is not None else "-",
                command if command is not None else "-",
                code,
            )
        except BaseException:
            pass
        return {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": request_id,
            "ok": False,
            "error": {
                "code": code,
                "message": _ERROR_MESSAGES[code],
            },
        }

    def _admit(self) -> bool:
        with self._admission:
            if not self._accepting:
                return False
            self._admitted += 1
            return True

    def _release(self) -> None:
        with self._admission:
            self._admitted -= 1
            if self._admitted == 0:
                self._admission.notify_all()

    def _reject_new(self) -> None:
        with self._admission:
            self._accepting = False

    def _wait_for_handlers(self) -> None:
        with self._admission:
            while self._admitted:
                self._admission.wait()


def to_primitive_view(value: object) -> object:
    """Recursively encode only approved public views as JSON-native data."""

    from .commands import PUBLIC_VIEW_DATACLASSES, PUBLIC_VIEW_ENUMS

    return _to_primitive_view(
        value,
        set(),
        PUBLIC_VIEW_DATACLASSES,
        PUBLIC_VIEW_ENUMS,
    )


def _to_primitive_view(
    value: object,
    active: set[int],
    approved_dataclasses: frozenset[type[object]],
    approved_enums: frozenset[type[object]],
) -> object:
    if value is None or type(value) in {bool, int, str}:
        if type(value) is str:
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as error:
                raise BridgeProtocolError(
                    "structured bridge data contains invalid Unicode"
                ) from error
        return value
    if type(value) is float:
        if math.isfinite(value):
            return value
        raise BridgeProtocolError(
            "structured bridge data contains a non-finite number"
        )
    if type(value) is datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise BridgeProtocolError(
                "structured bridge data contains a naive datetime"
            )
        return value.isoformat()
    if isinstance(value, Enum):
        if type(value) not in approved_enums:
            raise BridgeProtocolError(
                "structured bridge data contains an unapproved enum"
            )
        if value.value is value:
            raise BridgeProtocolError("structured bridge data is recursive")
        return _to_primitive_view(
            value.value,
            active,
            approved_dataclasses,
            approved_enums,
        )

    identity = id(value)
    if identity in active:
        raise BridgeProtocolError("structured bridge data is recursive")
    if is_dataclass(value) and not isinstance(value, type):
        if type(value) not in approved_dataclasses:
            raise BridgeProtocolError(
                "structured bridge data contains an unapproved dataclass"
            )
        active.add(identity)
        try:
            return {
                field.name: _to_primitive_view(
                    getattr(value, field.name),
                    active,
                    approved_dataclasses,
                    approved_enums,
                )
                for field in fields(value)
            }
        finally:
            active.remove(identity)
    if isinstance(value, Mapping):
        active.add(identity)
        try:
            encoded: dict[str, object] = {}
            for key, item in value.items():
                if type(key) is not str:
                    raise BridgeProtocolError(
                        "structured bridge data contains a non-string object key"
                    )
                try:
                    key.encode("utf-8")
                except UnicodeEncodeError as error:
                    raise BridgeProtocolError(
                        "structured bridge data contains invalid Unicode"
                    ) from error
                encoded[key] = _to_primitive_view(
                    item,
                    active,
                    approved_dataclasses,
                    approved_enums,
                )
            return encoded
        finally:
            active.remove(identity)
    if isinstance(value, (list, tuple)):
        active.add(identity)
        try:
            return [
                _to_primitive_view(
                    item,
                    active,
                    approved_dataclasses,
                    approved_enums,
                )
                for item in value
            ]
        finally:
            active.remove(identity)
    raise BridgeProtocolError("structured bridge data is not JSON-compatible")


def _recover_request_id(value: object) -> str | None:
    if type(value) is not dict:
        return None
    request_id = value.get("request_id")
    if type(request_id) is not str or _OPAQUE_ID.fullmatch(request_id) is None:
        return None
    return request_id


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
        for key, item in value.items():
            if not isinstance(key, str):
                raise BridgeProtocolError(
                    "structured bridge data contains a non-string object key"
                )
            try:
                key.encode("utf-8")
            except UnicodeEncodeError as error:
                raise BridgeProtocolError(
                    "structured bridge data contains invalid Unicode"
                ) from error
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
