"""Pywebview/WebView2 host security and structured bridge boundary."""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Callable, Iterable, Mapping, MutableMapping
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from pathlib import Path
from threading import Condition, Lock, Thread, current_thread, local
from time import monotonic
from typing import TYPE_CHECKING, Protocol
from urllib.parse import SplitResult, urlsplit
from uuid import uuid4

from namisync.dispatcher import retire_exception_graph
from namisync.interfaces.ui_state import MAX_JAVASCRIPT_SAFE_INTEGER
from namisync.workflows.views import (
    OperationResultView, SessionRecordView, validate_operation_result_view,
    validate_session_record_view,
)

from namisync.interfaces.task_port import (
    TaskDrainView, TaskEventUpdateView, TaskRecordUpdateView,
    TaskUnavailableError, validate_task_drain_view, validate_task_update_view,
)

from .pywebview_runtime import (
    WebView2RefusalReason,
    probe_webview2_runtime,
    require_supported_pythonnet_runtime,
)

if TYPE_CHECKING:
    from .commands import CommandSpec


_VIEW_VALIDATORS = {
    SessionRecordView: validate_session_record_view,
    OperationResultView: validate_operation_result_view,
    TaskDrainView: validate_task_drain_view,
    TaskEventUpdateView: validate_task_update_view,
    TaskRecordUpdateView: validate_task_update_view,
}
# SessionEventView is intentionally absent: the bridge does not recertify a
# trusted producer's event-body semantics.


BRIDGE_SCHEMA_VERSION = 1
_MAX_COMMAND_BYTES = 64 * 1024
MAX_BRIDGE_RESPONSE_JSON_BYTES = 8 * 1024 * 1024
_SUCCESS_RESPONSE_FIXED_CANONICAL_BYTES = len(
    json.dumps(
        {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": "0" * 32,
            "ok": True,
            "result": None,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
) - len("null")
# Sized for one ordinary long poll per each of 48 retained tasks plus 16 shared
# calls. Positions are neither partitioned nor reserved; saturation is
# `bridge_busy`.
_MAX_ADMITTED_HANDLERS = 64
_HANDLER_WAIT_TIMEOUT_SECONDS = 35.0
_OPAQUE_ID = re.compile(r"[0-9a-f]{32}")
_NATIVE_RESPONSE_ACK = re.compile(r"ack:([0-9a-f]{32})")
_COMMAND_COMPLETION_ACK = re.compile(
    r"ack:completion:(0|[1-9][0-9]{0,15}):([0-9a-f]{32}):([0-9a-f]{32})"
)
_NATIVE_TRANSPORT_VERSION = 1
_COMMAND_COMPLETION_KIND = "namisync.command-completion.v1"
_COMMAND_COMPLETION_PHASE = "completion"
_MAX_COMMAND_COMPLETION_BYTES = 65_536
_COMMAND_NAME = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")
_ERROR_MESSAGES = {
    "invalid_request": "The desktop request is invalid.",
    "unsupported_version": (
        "Restart NamiSync to load a compatible desktop page."
    ),
    "unknown_command": "This desktop action is not available.",
    "invalid_payload": "The desktop action contains invalid data.",
    "request_too_large": "The desktop request is too large.",
    "response_too_large": "The desktop response is too large.",
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
    "task_unavailable": "That desktop task is no longer available.",
    "drain_busy": (
        "That desktop task already has an event request in progress."
    ),
    "observation_conflict": (
        "That desktop task is already observing different work."
    ),
    "bridge_busy": "NamiSync is busy. Try this action again.",
    "bridge_unavailable": (
        "NamiSync is closing or this desktop page is no longer trusted."
    ),
    "internal_error": "NamiSync could not complete the desktop action.",
}
_MIN_RESPONSE_JSON_BYTES = max(
    len(
        json.dumps(
            {
                "schema_version": BRIDGE_SCHEMA_VERSION,
                "request_id": request_id,
                "ok": False,
                "error": {"code": code, "message": message},
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )
    for request_id in (None, "0" * 32)
    for code, message in _ERROR_MESSAGES.items()
)
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


class BridgeResponseTooLargeError(BridgeProtocolError):
    """The complete canonical-JSON response occurrence graph exceeds its wall."""


@dataclass(slots=True)
class _JsonByteBudget:
    remaining: int

    def consume(self, count: int) -> None:
        if count > self.remaining:
            raise BridgeResponseTooLargeError(
                "structured bridge response exceeds its JSON byte ceiling"
            )
        self.remaining -= count


@dataclass(slots=True)
class _NativeResponseCustody:
    owner: Thread
    browser_released: bool = False
    command_owner: Thread | None = None
    completion_generation: int | None = None
    completion_request_id: str | None = None
    completion_token: str | None = None
    completion_released: bool = True


@dataclass(frozen=True, slots=True)
class _AsyncAdmission:
    generation: int
    request_id: str
    completion_token: str


_TASK_DRAIN_ADMISSION_ISSUER = object()


@dataclass(slots=True)
class _AdmittedTaskDrainResponse:
    result: TaskDrainView | None
    issuer: object


def _peek_task_drain_response(value: object) -> TaskDrainView:
    if (
        type(value) is not _AdmittedTaskDrainResponse
        or value.issuer is not _TASK_DRAIN_ADMISSION_ISSUER
        or type(value.result) is not TaskDrainView
    ):
        raise TypeError("task drain lacks exact bridge response admission")
    return value.result


def _consume_task_drain_response(value: object) -> TaskDrainView:
    result = _peek_task_drain_response(value)
    assert type(value) is _AdmittedTaskDrainResponse
    value.result = None
    value.issuer = None
    return result


class WebView2Unavailable(RuntimeError):
    """The required Edge Chromium renderer could not be started."""


@dataclass(frozen=True, slots=True)
class AdmissionGranted:
    """Opaque composition approval consumed by the transport."""

    context: object


@dataclass(frozen=True, slots=True)
class AdmissionRefused:
    """Composition refused this command for the current document."""


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
    """Own versioned allowlisted RPC state behind one exposed function."""

    def __init__(
        self,
        *,
        document: NativeDocumentState,
        commands: Mapping[str, CommandSpec],
        admit: Callable[[str], object],
    ) -> None:
        from .commands import CommandSpec

        snapshot = dict(commands)
        if any(
            type(name) is not str
            or len(name) > 64
            or _COMMAND_NAME.fullmatch(name) is None
            for name in snapshot
        ):
            raise ValueError(
                "bridge commands require bounded lowercase snake names"
            )
        if any(type(spec) is not CommandSpec for spec in snapshot.values()):
            raise TypeError("every bridge command must be an exact CommandSpec")
        if not callable(admit):
            raise TypeError("bridge command admission must be callable")
        self._document = document
        self._commands = snapshot
        self._admit_command = admit
        self._handler_condition = Condition(Lock())
        self._accepting = True
        self._admitted = 0
        self._native_responses: dict[str, _NativeResponseCustody] = {}
        self._document_generation = 0
        self._native_return_marker = local()
        self._document_channel: object | None = None

    def _bind_document_channel(self, channel: object) -> None:
        """Bind the one current-document completion lane after construction."""

        from .document_channel import DocumentChannel

        if type(channel) is not DocumentChannel:
            raise TypeError("bridge completion lane must be an exact DocumentChannel")
        with self._handler_condition:
            if (
                self._document_channel is not None
                and self._document_channel is not channel
            ):
                raise RuntimeError("bridge completion lane is already bound")
            self._document_channel = channel

    def dispatch(self, command_json: str) -> dict[str, object]:
        """Return one exact response envelope; never export a Python failure."""

        return self._dispatch(command_json, native_custody=None)

    def _dispatch_native(self, command_json: str) -> object:
        """Retain native/browser custody until worker exit and exact receipt."""

        owner = current_thread()
        native_generation = None
        try:
            if type(owner) is Thread:
                with self._handler_condition:
                    native_generation = self._document_generation
            else:
                native_generation = None

            if type(command_json) is str and len(command_json) == 36:
                acknowledgment = _NATIVE_RESPONSE_ACK.fullmatch(command_json)
                if acknowledgment is not None:
                    return self._acknowledge_native_response(
                        acknowledgment.group(1)
                    )
            if type(command_json) is str:
                acknowledgment = _COMMAND_COMPLETION_ACK.fullmatch(command_json)
                if acknowledgment is not None:
                    generation = int(acknowledgment.group(1))
                    if generation > MAX_JAVASCRIPT_SAFE_INTEGER:
                        return False
                    return self._acknowledge_command_completion(
                        generation,
                        acknowledgment.group(2),
                        acknowledgment.group(3),
                    )

            if native_generation is None:
                return self._native_response(
                    None,
                    self._failure(None, None, "internal_error"),
                )
            try:
                response_token = uuid4().hex
                if (
                    type(response_token) is not str
                    or _OPAQUE_ID.fullmatch(response_token) is None
                ):
                    raise RuntimeError("native response token generation failed")
            except BaseException as error:
                retire_exception_graph(error)
                return self._native_response(
                    None,
                    self._failure(None, None, "internal_error"),
                )
            custody = _NativeResponseCustody(owner)
            response = self._dispatch(
                command_json,
                native_custody=custody,
                native_token=response_token,
                native_generation=native_generation,
            )
            with self._handler_condition:
                admitted_token = (
                    response_token
                    if self._native_responses.get(response_token) is custody
                    else None
                )
            if type(response) is _AsyncAdmission:
                return self._native_admission_response(admitted_token, response)
            return self._native_response(admitted_token, response)
        finally:
            if type(owner) is Thread and native_generation is not None:
                self._native_return_marker.generation = native_generation

    def _claim_native_return_generation(self) -> int | None:
        """Consume the calling native worker's one pending return marker."""

        generation = getattr(self._native_return_marker, "generation", None)
        if generation is not None:
            del self._native_return_marker.generation
        return generation

    def _is_document_generation_current(self, generation: int) -> bool:
        """Compare one claimed native return with the current document."""

        with self._handler_condition:
            return generation == self._document_generation

    def _dispatch(
        self,
        command_json: str,
        *,
        native_custody: _NativeResponseCustody | None,
        native_token: str | None = None,
        native_generation: int | None = None,
    ) -> dict[str, object]:
        refusal = self._reserve_handler(
            native_custody,
            native_token,
            native_generation,
        )
        if refusal is not None:
            return self._failure(None, None, refusal)
        try:
            try:
                self._document.require_trusted()
            except BaseException as error:
                retire_exception_graph(error)
                return self._failure(None, None, "bridge_unavailable")

            if type(command_json) is not str:
                return self._failure(None, None, "invalid_request")
            if len(command_json) > _MAX_COMMAND_BYTES:
                return self._failure(None, None, "request_too_large")
            try:
                command_size = len(command_json.encode("utf-8"))
            except UnicodeEncodeError as error:
                retire_exception_graph(error)
                return self._failure(None, None, "invalid_request")
            if command_size > _MAX_COMMAND_BYTES:
                return self._failure(None, None, "request_too_large")
            try:
                raw = json.loads(
                    command_json,
                    object_pairs_hook=_unique_object,
                    parse_constant=lambda value: _reject_json_constant(value),
                )
            except Exception as error:
                retire_exception_graph(error)
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
            except BridgeProtocolError as error:
                retire_exception_graph(error)
                return self._failure(request_id, None, "invalid_request")
            if (
                type(name) is not str
                or len(name) > 64
                or _COMMAND_NAME.fullmatch(name) is None
            ):
                return self._failure(request_id, None, "invalid_request")
            spec = self._commands.get(name)
            if spec is None:
                return self._failure(request_id, None, "unknown_command")

            try:
                admission = self._admit_command(name)
            except BaseException as error:
                retire_exception_graph(error)
                return self._failure(request_id, name, "bridge_unavailable")
            if type(admission) is AdmissionRefused:
                return self._failure(request_id, name, "bridge_unavailable")
            if type(admission) is not AdmissionGranted:
                return self._failure(request_id, name, "bridge_unavailable")

            payload = raw["payload"]
            if type(payload) is not dict:
                return self._failure(request_id, name, "invalid_payload")
            try:
                _require_json_value(payload)
            except BridgeProtocolError as error:
                retire_exception_graph(error)
                return self._failure(request_id, name, "invalid_payload")

            from .commands import (
                CommandAdmissionError,
                CommandConflictError,
                CommandPayloadError,
                CommandWork,
                PickerUnavailableError,
                PlanningRefusedError,
            )

            try:
                prepared = spec.prepare_for_bridge(
                    payload,
                    context=admission.context,
                )
            except CommandAdmissionError as error:
                retire_exception_graph(error)
                return self._failure(request_id, name, "bridge_unavailable")
            except CommandPayloadError as error:
                retire_exception_graph(error)
                return self._failure(request_id, name, "invalid_payload")
            except BaseException as error:
                retire_exception_graph(error)
                return self._failure(request_id, name, "internal_error")
            if (
                native_custody is not None
                and spec.work is CommandWork.ASYNC_SMALL
            ):
                assert native_token is not None
                assert native_generation is not None
                return self._start_async_command(
                    request_id=request_id,
                    name=name,
                    spec=spec,
                    prepared=prepared,
                    custody=native_custody,
                    native_token=native_token,
                    generation=native_generation,
                )
            return self._execute_prepared_command(
                request_id,
                name,
                spec,
                prepared,
            )
        except BaseException as error:
            retire_exception_graph(error)
            return self._failure(None, None, "internal_error")
        finally:
            self._release_handler(native_token)

    def _execute_prepared_command(
        self,
        request_id: str,
        name: str,
        spec: CommandSpec,
        prepared: object,
        *,
        maximum_json_bytes: int = MAX_BRIDGE_RESPONSE_JSON_BYTES,
        oversize_code: str = "response_too_large",
    ) -> dict[str, object]:
        from .commands import (
            CommandAdmissionError,
            CommandConflictError,
            CommandPayloadError,
            PickerUnavailableError,
            PlanningRefusedError,
        )
        from .drain import DrainBusyError, ObservationConflictError
        from .slots import SlotUnavailableError

        try:
            result = spec.invoke_prepared_for_bridge(prepared)
        except CommandAdmissionError as error:
            retire_exception_graph(error)
            return self._failure(request_id, name, "bridge_unavailable")
        except CommandPayloadError as error:
            retire_exception_graph(error)
            return self._failure(request_id, name, "invalid_payload")
        except SlotUnavailableError as error:
            retire_exception_graph(error)
            return self._failure(request_id, name, "slot_unavailable")
        except PickerUnavailableError as error:
            retire_exception_graph(error)
            return self._failure(request_id, name, "picker_unavailable")
        except CommandConflictError as error:
            retire_exception_graph(error)
            return self._failure(request_id, name, "command_conflict")
        except PlanningRefusedError as error:
            retire_exception_graph(error)
            return self._failure(request_id, name, "planning_refused")
        except TaskUnavailableError as error:
            retire_exception_graph(error)
            return self._failure(request_id, name, "task_unavailable")
        except DrainBusyError as error:
            retire_exception_graph(error)
            return self._failure(request_id, name, "drain_busy")
        except ObservationConflictError as error:
            retire_exception_graph(error)
            return self._failure(request_id, name, "observation_conflict")
        except BaseException as error:
            retire_exception_graph(error)
            return self._failure(request_id, name, "internal_error")
        try:
            if type(result) is _AdmittedTaskDrainResponse:
                captured_result = _consume_task_drain_response(result)
            else:
                captured_result = snapshot_bridge_response_result(
                    result,
                    request_id,
                    maximum_json_bytes,
                )
        except BridgeResponseTooLargeError as error:
            retire_exception_graph(error)
            return self._failure(request_id, name, oversize_code)
        except BaseException as error:
            retire_exception_graph(error)
            return self._failure(request_id, name, "internal_error")
        del result
        try:
            result = _project_response_value(captured_result, set())
        except BaseException as error:
            retire_exception_graph(error)
            return self._failure(request_id, name, "internal_error")
        del captured_result
        return {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": request_id,
            "ok": True,
            "result": result,
        }

    def _start_async_command(
        self,
        *,
        request_id: str,
        name: str,
        spec: CommandSpec,
        prepared: object,
        custody: _NativeResponseCustody,
        native_token: str,
        generation: int,
    ) -> _AsyncAdmission | dict[str, object]:
        if not 0 <= generation <= MAX_JAVASCRIPT_SAFE_INTEGER:
            return self._failure(request_id, name, "internal_error")
        try:
            completion_token = uuid4().hex
            if _OPAQUE_ID.fullmatch(completion_token) is None:
                raise RuntimeError("command completion token generation failed")
        except BaseException as error:
            retire_exception_graph(error)
            return self._failure(request_id, name, "internal_error")

        def run() -> None:
            self._run_async_command(
                request_id=request_id,
                name=name,
                spec=spec,
                prepared=prepared,
                custody=custody,
            )

        worker = Thread(
            target=run,
            name=f"namisync-command-{name}",
            daemon=True,
        )
        with self._handler_condition:
            if (
                self._native_responses.get(native_token) is not custody
                or self._document_channel is None
                or generation != self._document_generation
                or any(
                    item.completion_token == completion_token
                    for item in self._native_responses.values()
                )
            ):
                return self._failure(request_id, name, "bridge_unavailable")
            custody.command_owner = worker
            custody.completion_generation = generation
            custody.completion_request_id = request_id
            custody.completion_token = completion_token
            custody.completion_released = False
        try:
            worker.start()
        except BaseException as error:
            retire_exception_graph(error)
            with self._handler_condition:
                custody.command_owner = None
                custody.completion_generation = None
                custody.completion_request_id = None
                custody.completion_token = None
                custody.completion_released = True
                self._handler_condition.notify_all()
            return self._failure(request_id, name, "internal_error")
        return _AsyncAdmission(generation, request_id, completion_token)

    def _run_async_command(
        self,
        *,
        request_id: str,
        name: str,
        spec: CommandSpec,
        prepared: object,
        custody: _NativeResponseCustody,
    ) -> None:
        response = self._execute_prepared_command(
            request_id,
            name,
            spec,
            prepared,
            maximum_json_bytes=_MAX_COMMAND_COMPLETION_BYTES,
            oversize_code="internal_error",
        )
        message = self._command_completion_message(custody, response)
        try:
            encoded = json.dumps(
                message,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            if len(encoded) > _MAX_COMMAND_COMPLETION_BYTES:
                raise BridgeResponseTooLargeError(
                    "command completion exceeds its document-message ceiling"
                )
        except BaseException as error:
            retire_exception_graph(error)
            response = self._failure(request_id, name, "internal_error")
            message = self._command_completion_message(custody, response)
        with self._handler_condition:
            channel = self._document_channel
        if channel is None:
            self._retire_command_completion(custody)
            return
        from .document_channel import DocumentPostKind

        acknowledgment = (
            custody.completion_generation,
            custody.completion_request_id,
            custody.completion_token,
            _COMMAND_COMPLETION_PHASE,
        )
        try:
            channel.post(
                message,
                still_current=lambda: self._command_completion_is_current(custody),
                completion=lambda _error: self._retire_command_completion(custody),
                kind=DocumentPostKind.COMMAND,
                acknowledgment=acknowledgment,
            )
        except BaseException as error:
            retire_exception_graph(error)
            self._retire_command_completion(custody)

    @staticmethod
    def _command_completion_message(
        custody: _NativeResponseCustody,
        response: dict[str, object],
    ) -> dict[str, object]:
        return {
            "kind": _COMMAND_COMPLETION_KIND,
            "phase": _COMMAND_COMPLETION_PHASE,
            "generation": custody.completion_generation,
            "request_id": custody.completion_request_id,
            "completion_token": custody.completion_token,
            "response": response,
        }

    def _command_completion_is_current(
        self,
        custody: _NativeResponseCustody,
    ) -> bool:
        with self._handler_condition:
            return (
                not custody.completion_released
                and custody.completion_generation == self._document_generation
                and any(
                    current is custody
                    for current in self._native_responses.values()
                )
            )

    def _retire_command_completion(
        self,
        custody: _NativeResponseCustody,
    ) -> None:
        with self._handler_condition:
            custody.completion_released = True
            self._reap_native_returns_locked()
            self._handler_condition.notify_all()

    @staticmethod
    def _native_response(
        response_token: str | None,
        response: dict[str, object],
    ) -> dict[str, object]:
        return {
            "transport_version": _NATIVE_TRANSPORT_VERSION,
            "response_token": response_token,
            "response": response,
        }

    @staticmethod
    def _native_admission_response(
        response_token: str | None,
        admission: _AsyncAdmission,
    ) -> dict[str, object]:
        return {
            "transport_version": _NATIVE_TRANSPORT_VERSION,
            "response_token": response_token,
            "completion": {
                "phase": _COMMAND_COMPLETION_PHASE,
                "generation": admission.generation,
                "request_id": admission.request_id,
                "completion_token": admission.completion_token,
            },
        }

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
                _safe_log_command(command),
                code,
            )
        except BaseException as error:
            retire_exception_graph(error)
        return {
            "schema_version": BRIDGE_SCHEMA_VERSION,
            "request_id": request_id,
            "ok": False,
            "error": {
                "code": code,
                "message": _ERROR_MESSAGES[code],
            },
        }

    def _reserve_handler(
        self,
        native_custody: _NativeResponseCustody | None,
        native_token: str | None,
        native_generation: int | None,
    ) -> str | None:
        with self._handler_condition:
            self._reap_native_returns_locked()
            if not self._accepting:
                return "bridge_unavailable"
            direct_call = (
                native_custody is None
                and native_token is None
                and native_generation is None
            )
            native_call = (
                native_custody is not None
                and native_token is not None
                and native_generation is not None
            )
            if not (direct_call or native_call):
                return "bridge_unavailable"
            if (
                native_generation is not None
                and native_generation != self._document_generation
            ):
                return "bridge_unavailable"
            if (
                self._admitted >= _MAX_ADMITTED_HANDLERS
                or (
                    native_custody is not None
                    and any(
                        custody.owner is native_custody.owner
                        for custody in self._native_responses.values()
                    )
                )
                or native_token in self._native_responses
            ):
                return "bridge_busy"
            self._admitted += 1
            if native_custody is not None:
                assert native_token is not None
                self._native_responses[native_token] = native_custody
            return None

    def _release_handler(self, native_token: str | None) -> None:
        with self._handler_condition:
            if native_token is None:
                self._admitted -= 1
            self._handler_condition.notify_all()

    def _reap_native_returns_locked(self) -> None:
        finished = tuple(
            token
            for token, custody in self._native_responses.items()
            if (
                custody.browser_released
                and not custody.owner.is_alive()
                and custody.completion_released
                and (
                    custody.command_owner is None
                    or not custody.command_owner.is_alive()
                )
            )
        )
        for token in finished:
            del self._native_responses[token]
        self._admitted -= len(finished)

    def _acknowledge_native_response(self, response_token: str) -> bool:
        """Release exact response custody without granting document authority."""

        with self._handler_condition:
            custody = self._native_responses.get(response_token)
            if custody is None:
                return False
            custody.browser_released = True
            self._reap_native_returns_locked()
            self._handler_condition.notify_all()
            return True

    def _acknowledge_command_completion(
        self,
        generation: int,
        request_id: str,
        completion_token: str,
    ) -> bool:
        """Retire one exact completion without granting command authority."""

        with self._handler_condition:
            matches = tuple(
                custody
                for custody in self._native_responses.values()
                if (
                    not custody.completion_released
                    and custody.completion_generation == generation
                    and custody.completion_request_id == request_id
                    and custody.completion_token == completion_token
                )
            )
            channel = self._document_channel
        if len(matches) != 1 or channel is None:
            return False
        from .document_channel import DocumentPostKind

        return bool(
            channel.acknowledge(
                DocumentPostKind.COMMAND,
                (
                    generation,
                    request_id,
                    completion_token,
                    _COMMAND_COMPLETION_PHASE,
                ),
            )
        )

    def _retire_document_responses(self) -> None:
        """Retire browser custody invalidated by a document generation change."""

        with self._handler_condition:
            self._document_generation += 1
            for custody in self._native_responses.values():
                custody.browser_released = True
                custody.completion_released = True
            self._reap_native_returns_locked()
            self._handler_condition.notify_all()

    def begin_close(self) -> None:
        """Reject every later dispatch while admitted handlers settle."""

        with self._handler_condition:
            self._accepting = False
            for custody in self._native_responses.values():
                custody.browser_released = True
                custody.completion_released = True
            channel = self._document_channel
            self._reap_native_returns_locked()
            self._handler_condition.notify_all()
        close = getattr(channel, "close", None)
        if callable(close):
            close()

    def wait_for_handlers(
        self,
        timeout: float = _HANDLER_WAIT_TIMEOUT_SECONDS,
    ) -> None:
        """Wait a bounded interval for true handler quiescence."""

        if type(timeout) not in {int, float} or not math.isfinite(timeout):
            raise ValueError("bridge handler wait timeout must be finite")
        if timeout <= 0:
            raise ValueError("bridge handler wait timeout must be positive")
        deadline = monotonic() + timeout
        while True:
            with self._handler_condition:
                self._reap_native_returns_locked()
                if not self._admitted:
                    return
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        "bridge handlers did not quiesce before the deadline"
                    )
                owners = tuple(
                    owner
                    for custody in self._native_responses.values()
                    for owner in (custody.owner, custody.command_owner)
                    if owner is not None and owner.is_alive()
                )
                if not owners:
                    self._handler_condition.wait(remaining)
                    continue
            for owner in owners:
                owner.join(max(0.0, deadline - monotonic()))


def to_primitive_view(value: object) -> object:
    """Recursively encode only approved public views as JSON-native data."""

    from .commands import PUBLIC_VIEW_DATACLASSES

    snapshot = _snapshot_response_value(
        value,
        set(),
        PUBLIC_VIEW_DATACLASSES,
        None,
    )
    _validate_owned_response_tree(snapshot, set())
    return _project_response_value(snapshot, set())


def snapshot_bridge_response_result(
    value: object,
    request_id: str,
    maximum_json_bytes: int = MAX_BRIDGE_RESPONSE_JSON_BYTES,
) -> object:
    """Return one detached, validated response result admitted by exact bytes."""

    if type(request_id) is not str or _OPAQUE_ID.fullmatch(request_id) is None:
        raise BridgeProtocolError("successful response request id is invalid")
    if (
        type(maximum_json_bytes) is not int
        or maximum_json_bytes < _MIN_RESPONSE_JSON_BYTES
        or maximum_json_bytes > MAX_BRIDGE_RESPONSE_JSON_BYTES
    ):
        raise ValueError("bridge response JSON ceiling is outside the product range")
    from .commands import PUBLIC_VIEW_DATACLASSES

    budget = _JsonByteBudget(maximum_json_bytes)
    budget.consume(_SUCCESS_RESPONSE_FIXED_CANONICAL_BYTES)
    snapshot = _snapshot_response_value(
        value,
        set(),
        PUBLIC_VIEW_DATACLASSES,
        budget,
    )
    _validate_owned_response_tree(snapshot, set())
    return snapshot


def snapshot_task_drain_response_prefix(
    task_id: str,
    session_id: str,
    drain_id: str,
    updates: Iterable[TaskUpdateView],
) -> TaskDrainView:
    """Capture each source update once and return its longest admitted prefix."""

    return _consume_task_drain_response(
        _admit_task_drain_response_prefix(
            task_id,
            session_id,
            drain_id,
            updates,
        )
    )


def _admit_task_drain_response_prefix(
    task_id: str,
    session_id: str,
    drain_id: str,
    updates: Iterable[TaskUpdateView],
) -> _AdmittedTaskDrainResponse:
    """Transfer one validated longest-prefix owner without a second copy."""

    from .commands import PUBLIC_VIEW_DATACLASSES

    budget = _JsonByteBudget(MAX_BRIDGE_RESPONSE_JSON_BYTES)
    budget.consume(_SUCCESS_RESPONSE_FIXED_CANONICAL_BYTES)
    empty = _snapshot_response_value(
        TaskDrainView(task_id, session_id, drain_id, ()),
        set(),
        PUBLIC_VIEW_DATACLASSES,
        budget,
    )
    if type(empty) is not TaskDrainView:
        raise RuntimeError("bridge response admission changed task drain type")
    admitted: list[TaskUpdateView] = []
    for update in updates:
        try:
            if admitted:
                budget.consume(1)
            captured = _snapshot_response_value(
                update,
                set(),
                PUBLIC_VIEW_DATACLASSES,
                budget,
            )
        except BridgeResponseTooLargeError:
            if not admitted:
                raise
            break
        if type(captured) not in {TaskEventUpdateView, TaskRecordUpdateView}:
            raise RuntimeError("bridge response admission changed task update type")
        admitted.append(captured)
    result = TaskDrainView(
        empty.task_id,
        empty.session_id,
        empty.drain_id,
        tuple(admitted),
    )
    _validate_owned_response_tree(result, set())
    return _AdmittedTaskDrainResponse(result, _TASK_DRAIN_ADMISSION_ISSUER)


def _snapshot_response_value(
    value: object,
    active: set[int],
    approved_dataclasses: frozenset[type[object]],
    budget: _JsonByteBudget | None,
) -> object:
    """Capture each hostile occurrence once, then validate only owned state."""

    if value is None:
        _consume_json_bytes(budget, 4)
        return value
    if type(value) is bool:
        _consume_json_bytes(budget, 4 if value else 5)
        return value
    if type(value) is int:
        if (
            value < -MAX_JAVASCRIPT_SAFE_INTEGER
            or value > MAX_JAVASCRIPT_SAFE_INTEGER
        ):
            raise BridgeProtocolError(
                "structured bridge data contains an unsafe integer"
            )
        _consume_json_bytes(budget, len(str(value)))
        return value
    if type(value) is str:
        _consume_canonical_json_string(value, budget)
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise BridgeProtocolError(
                "structured bridge data contains a non-finite number"
            )
        _consume_json_bytes(
            budget,
            len(
                json.dumps(
                    value,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                )
            ),
        )
        return value
    if type(value) is datetime:
        if value.tzinfo is None:
            raise BridgeProtocolError(
                "structured bridge data contains a naive datetime"
            )
        projected = value.isoformat()
        parsed = datetime.fromisoformat(projected)
        if parsed.utcoffset() is None:
            raise BridgeProtocolError(
                "structured bridge data contains a naive datetime"
            )
        _consume_canonical_json_string(projected, budget)
        return projected
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
            _consume_json_bytes(budget, 2)
            captured: dict[str, object] = {}
            for index, field in enumerate(fields(value)):
                if index:
                    _consume_json_bytes(budget, 1)
                _consume_canonical_json_string(field.name, budget)
                _consume_json_bytes(budget, 1)
                captured[field.name] = _snapshot_response_value(
                    getattr(value, field.name),
                    active,
                    approved_dataclasses,
                    budget,
                )
        finally:
            active.remove(identity)
        try:
            snapshot = type(value)(**captured)
        except (TypeError, ValueError) as error:
            raise BridgeProtocolError(
                "structured bridge view is invalid"
            ) from error
        return snapshot
    if isinstance(value, Mapping):
        active.add(identity)
        try:
            _consume_json_bytes(budget, 2)
            captured_mapping: dict[str, object] = {}
            for index, (key, item) in enumerate(value.items()):
                if type(key) is not str:
                    raise BridgeProtocolError(
                        "structured bridge data contains a non-string object key"
                    )
                if key in captured_mapping:
                    raise BridgeProtocolError(
                        "structured bridge data contains a duplicate object key"
                    )
                if index:
                    _consume_json_bytes(budget, 1)
                _consume_canonical_json_string(key, budget)
                _consume_json_bytes(budget, 1)
                captured_mapping[key] = _snapshot_response_value(
                    item,
                    active,
                    approved_dataclasses,
                    budget,
                )
            return captured_mapping
        finally:
            active.remove(identity)
    if isinstance(value, (list, tuple)):
        active.add(identity)
        try:
            _consume_json_bytes(budget, 2)
            captured_items = []
            for index, item in enumerate(value):
                if index:
                    _consume_json_bytes(budget, 1)
                captured_items.append(_snapshot_response_value(
                    item,
                    active,
                    approved_dataclasses,
                    budget,
                ))
            if type(value) is tuple:
                return tuple(captured_items)
            return captured_items
        finally:
            active.remove(identity)
    raise BridgeProtocolError("structured bridge data is not JSON-compatible")


def _validate_owned_response_tree(value: object, active: set[int]) -> None:
    """Invoke the retained type-specific validator when one exists."""

    validator = _VIEW_VALIDATORS.get(type(value))
    if validator is not None:
        try:
            validator(value)
        except (TypeError, ValueError) as error:
            raise BridgeProtocolError(
                "structured bridge view is invalid"
            ) from error
        return
    if value is None or type(value) in {bool, int, float, str}:
        return
    identity = id(value)
    if identity in active:
        raise BridgeProtocolError("structured bridge data is recursive")
    if is_dataclass(value) and not isinstance(value, type):
        active.add(identity)
        try:
            for field in fields(value):
                _validate_owned_response_tree(getattr(value, field.name), active)
        finally:
            active.remove(identity)
        return
    if type(value) is dict:
        active.add(identity)
        try:
            for item in value.values():
                _validate_owned_response_tree(item, active)
        finally:
            active.remove(identity)
        return
    if type(value) in {list, tuple}:
        active.add(identity)
        try:
            for item in value:
                _validate_owned_response_tree(item, active)
        finally:
            active.remove(identity)
        return
    raise BridgeProtocolError("owned bridge response contains an invalid value")


def _project_response_value(
    value: object,
    active: set[int],
) -> object:
    """Normalize a detached graph already admitted and revalidated above."""

    if value is None or type(value) in {bool, int, float, str}:
        return value
    identity = id(value)
    if identity in active:
        raise BridgeProtocolError("structured bridge data is recursive")
    if is_dataclass(value) and not isinstance(value, type):
        active.add(identity)
        try:
            projected: dict[str, object] = {}
            for field in fields(value):
                projected[field.name] = _project_response_value(
                    getattr(value, field.name),
                    active,
                )
            return projected
        finally:
            active.remove(identity)
    if type(value) is dict:
        active.add(identity)
        try:
            for key, item in value.items():
                value[key] = _project_response_value(item, active)
            return value
        finally:
            active.remove(identity)
    if type(value) is list:
        active.add(identity)
        try:
            for index, item in enumerate(value):
                value[index] = _project_response_value(item, active)
            return value
        finally:
            active.remove(identity)
    if type(value) is tuple:
        active.add(identity)
        try:
            return [
                _project_response_value(item, active)
                for item in value
            ]
        finally:
            active.remove(identity)
    raise BridgeProtocolError("structured bridge data is not JSON-compatible")


def _consume_json_bytes(budget: _JsonByteBudget | None, count: int) -> None:
    if budget is not None:
        budget.consume(count)


def _consume_canonical_json_string(
    value: str,
    budget: _JsonByteBudget | None,
) -> None:
    """Count strict compact ensure_ascii=False JSON without a text copy."""

    _consume_json_bytes(budget, 2)
    for character in value:
        codepoint = ord(character)
        if 0xD800 <= codepoint <= 0xDFFF:
            raise BridgeProtocolError(
                "structured bridge data contains invalid Unicode"
            )
        if character in {'"', "\\", "\b", "\t", "\n", "\f", "\r"}:
            count = 2
        elif codepoint < 0x20:
            count = 6
        elif codepoint <= 0x7F:
            count = 1
        elif codepoint <= 0x7FF:
            count = 2
        elif codepoint <= 0xFFFF:
            count = 3
        else:
            count = 4
        _consume_json_bytes(budget, count)


def _recover_request_id(value: object) -> str | None:
    if type(value) is not dict:
        return None
    request_id = value.get("request_id")
    if type(request_id) is not str or _OPAQUE_ID.fullmatch(request_id) is None:
        return None
    return request_id


def _safe_log_command(value: object) -> str:
    if (
        type(value) is str
        and len(value) <= 64
        and _COMMAND_NAME.fullmatch(value) is not None
    ):
        return value
    return "-"


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
