"""Desktop host composition and native lifetime primitives."""

from __future__ import annotations

import ctypes
import importlib
import importlib.resources
import logging
import os
import sys
from ctypes import wintypes
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Event, Lock, Thread, Timer
from typing import Callable, Protocol, TYPE_CHECKING

from namisync.dispatcher import retire_exception_graph

from .readiness import DesktopReadinessGate, DesktopStartupError

if TYPE_CHECKING:
    from .paths import AppPathLease, AppPaths


_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_MAX_LONG_PATH_CHARS = 32_768
_EXIT_SUCCESS = 0
_EXIT_STARTUP = 1
_ID_RETRY = 4
_MB_RETRYCANCEL = 0x00000005
_MB_ICONWARNING = 0x00000030
_MB_SETFOREGROUND = 0x00010000
_WM_CLOSE = 0x0010
_CLOSE_INCOMPLETE_CAPTION = "NamiSync - Close Incomplete"
_CLOSE_INCOMPLETE_MESSAGE = (
    "NamiSync could not finish closing safely.\n\n"
    "Choose Retry to try the orderly close again. Cancel keeps NamiSync open."
)


class _NativeFolderPicker:
    """Late-bind the created window while using only pywebview's public API."""

    def __init__(self, webview_module: object) -> None:
        self._webview_module = webview_module
        self._window: object | None = None
        self._dialog_lock = Lock()

    def bind(self, window: object) -> None:
        if window is None:
            raise ValueError("folder picker window must be present")
        if self._window is not None:
            raise RuntimeError("folder picker window is already bound")
        self._window = window

    def __call__(self) -> list[str] | tuple[str, ...] | None:
        window = self._window
        if window is None:
            raise RuntimeError("folder picker window is not bound")
        if not self._dialog_lock.acquire(blocking=False):
            raise RuntimeError("folder picker is already active")
        webview_module = self._webview_module
        try:
            return window.create_file_dialog(
                webview_module.FileDialog.FOLDER,
                allow_multiple=False,
            )
        finally:
            self._dialog_lock.release()


@dataclass(frozen=True, slots=True)
class DesktopInstanceIdentity:
    """One injected mutex/title pair shared by holder and activator."""

    mutex_name: str
    window_title: str

    def __post_init__(self) -> None:
        if not self.mutex_name or not self.window_title:
            raise ValueError("desktop instance identity values must be non-empty")


def production_instance_identity() -> DesktopInstanceIdentity:
    """Return the fixed, version- and data-root-independent product identity."""

    return DesktopInstanceIdentity(
        mutex_name=r"Local\NamiSync.Desktop",
        window_title="NamiSync",
    )


class InstanceNative(Protocol):
    def create_mutex(self, name: str) -> tuple[object, bool]: ...

    def close_handle(self, handle: object) -> None: ...

    def find_window(self, title: str) -> object | None: ...

    def window_belongs_to_current_executable(self, window: object) -> bool: ...

    def restore_window(self, window: object) -> None: ...

    def foreground_window(self, window: object) -> bool: ...


class WindowsInstanceNative:
    """Win32 mutex and existing-window activation adapter."""

    def __init__(self) -> None:
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32.CreateMutexW.argtypes = (
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        )
        self._kernel32.CreateMutexW.restype = wintypes.HANDLE
        self._kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32.OpenProcess.argtypes = (
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        )
        self._kernel32.OpenProcess.restype = wintypes.HANDLE
        self._kernel32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        )
        self._kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self._user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
        self._user32.FindWindowW.restype = wintypes.HWND
        self._user32.GetWindowThreadProcessId.argtypes = (
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        )
        self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self._user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
        self._user32.ShowWindow.restype = wintypes.BOOL
        self._user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
        self._user32.SetForegroundWindow.restype = wintypes.BOOL

    def create_mutex(self, name: str) -> tuple[object, bool]:
        ctypes.set_last_error(0)
        handle = self._kernel32.CreateMutexW(None, False, name)
        error = ctypes.get_last_error()
        if not handle:
            raise ctypes.WinError(error)
        return handle, error == _ERROR_ALREADY_EXISTS

    def close_handle(self, handle: object) -> None:
        if not self._kernel32.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def find_window(self, title: str) -> object | None:
        window = self._user32.FindWindowW(None, title)
        return window or None

    def window_belongs_to_current_executable(self, window: object) -> bool:
        process_id = wintypes.DWORD()
        if not self._user32.GetWindowThreadProcessId(
            window,
            ctypes.byref(process_id),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        process = self._kernel32.OpenProcess(
            _PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            process_id.value,
        )
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            image = ctypes.create_unicode_buffer(_MAX_LONG_PATH_CHARS)
            size = wintypes.DWORD(len(image))
            if not self._kernel32.QueryFullProcessImageNameW(
                process,
                0,
                image,
                ctypes.byref(size),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.close_handle(process)
        observed = os.path.normcase(os.path.abspath(image.value))
        expected = {
            os.path.normcase(os.path.abspath(executable))
            for executable in (
                sys.executable,
                getattr(sys, "_base_executable", sys.executable),
            )
            if isinstance(executable, str) and executable
        }
        return observed in expected

    def restore_window(self, window: object) -> None:
        self._user32.ShowWindow(window, _SW_RESTORE)

    def foreground_window(self, window: object) -> bool:
        return bool(self._user32.SetForegroundWindow(window))


class DesktopInstanceLease:
    """The primary instance's lifetime-held native mutex handle."""

    def __init__(self, handle: object, native: InstanceNative) -> None:
        self._handle = handle
        self._native = native
        self._lock = Lock()

    def close(self) -> None:
        with self._lock:
            handle = self._handle
            if handle is None:
                return
            self._native.close_handle(handle)
            self._handle = None


@dataclass(frozen=True, slots=True)
class DesktopInstanceAdmission:
    """Primary lease or typed losing-instance activation result."""

    lease: DesktopInstanceLease | None
    activated: bool
    activation_error: str | None

    @property
    def is_primary(self) -> bool:
        return self.lease is not None


def acquire_desktop_instance(
    identity: DesktopInstanceIdentity,
    *,
    native: InstanceNative | None = None,
) -> DesktopInstanceAdmission:
    """Acquire the fixed mutex or activate the window with the injected title."""

    adapter = WindowsInstanceNative() if native is None else native
    handle, already_exists = adapter.create_mutex(identity.mutex_name)
    if not already_exists:
        return DesktopInstanceAdmission(
            lease=DesktopInstanceLease(handle, adapter),
            activated=False,
            activation_error=None,
        )

    adapter.close_handle(handle)
    try:
        window = adapter.find_window(identity.window_title)
        if window is None:
            return DesktopInstanceAdmission(
                lease=None,
                activated=False,
                activation_error="The existing NamiSync window could not be found.",
            )
        if not adapter.window_belongs_to_current_executable(window):
            return DesktopInstanceAdmission(
                lease=None,
                activated=False,
                activation_error=(
                    "The existing NamiSync window could not be authenticated."
                ),
            )
        adapter.restore_window(window)
        if not adapter.foreground_window(window):
            return DesktopInstanceAdmission(
                lease=None,
                activated=False,
                activation_error=(
                    "The existing NamiSync window could not be brought to the foreground."
                ),
            )
    except OSError:
        return DesktopInstanceAdmission(
            lease=None,
            activated=False,
            activation_error="The existing NamiSync window could not be activated.",
        )
    return DesktopInstanceAdmission(
        lease=None,
        activated=True,
        activation_error=None,
    )


def _schedule_startup_deadline(
    seconds: float,
    callback: Callable[[], None],
) -> Callable[[], None]:
    timer = Timer(seconds, callback)
    timer.daemon = True
    timer.start()
    return timer.cancel


class _StartupState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._failure: Exception | None = None
        self._destroy_attempted = False

    @property
    def failure(self) -> Exception | None:
        with self._lock:
            return self._failure

    def refuse(self, error: Exception) -> None:
        with self._lock:
            if self._failure is None:
                self._failure = error

    def destroy_once(self, window: object) -> bool:
        with self._lock:
            if self._destroy_attempted:
                return False
            self._destroy_attempted = True
        public_error: Exception | None = None
        try:
            window.destroy()
        except Exception as error:
            public_error = error
        else:
            closed = getattr(getattr(window, "events", None), "closed", None)
            is_set = getattr(closed, "is_set", None)
            if callable(is_set):
                try:
                    closed_landed = is_set()
                except Exception as error:
                    public_error = error
                else:
                    if not closed_landed:
                        public_error = RuntimeError(
                            "public window destroy returned before closure"
                        )
        if public_error is not None:
            _log_cleanup_failure("startup.window_destroy_failed", public_error)
            try:
                _post_native_window_close(window)
            except Exception as fallback_error:
                _log_cleanup_failure(
                    "startup.native_window_close_failed",
                    fallback_error,
                )
                return False
        return True


def _post_native_window_close(window: object) -> None:
    """Request the normal Win32 close path after public destruction fails."""

    native_handle = window.native.Handle
    to_int64 = getattr(native_handle, "ToInt64", None)
    handle = int(to_int64() if callable(to_int64) else native_handle)
    if handle <= 0:
        raise RuntimeError("desktop window has no native close handle")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.PostMessageW.argtypes = (
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )
    user32.PostMessageW.restype = wintypes.BOOL
    ctypes.set_last_error(0)
    if not user32.PostMessageW(handle, _WM_CLOSE, 0, 0):
        raise ctypes.WinError(ctypes.get_last_error())


class _ClosePhase(Enum):
    STARTING = "starting"
    OPEN = "open"
    CLOSING = "closing"
    RETRYABLE = "retryable"
    PROGRAMMATIC_CLOSE = "programmatic_close"
    STARTUP_REFUSED = "startup_refused"


@dataclass(frozen=True, slots=True)
class _DesktopCloseHooks:
    reject_dispatch: Callable[[], None]
    wake_waiters: Callable[[], None]
    wait_for_handlers: Callable[[], None]


class _DesktopQuiescenceError(RuntimeError):
    """Name the failed close boundary without exposing its private cause."""

    def __init__(self, step: str) -> None:
        super().__init__(f"desktop quiescence failed during {step}")
        self.step = step


def _quiesce_desktop(
    hooks: _DesktopCloseHooks,
    *,
    after_waiters_wake: Callable[[], None] | None = None,
) -> None:
    """Run the one fail-closed bridge/task quiescence sequence."""

    for step, callback in (
        ("dispatch_rejection", hooks.reject_dispatch),
        ("registry_wake", hooks.wake_waiters),
        ("handler_wait", hooks.wait_for_handlers),
    ):
        try:
            callback()
        except Exception as error:
            raise _DesktopQuiescenceError(step) from error
        if step == "registry_wake" and after_waiters_wake is not None:
            after_waiters_wake()


class _DesktopCloseController:
    """Veto synchronous user closes while one orderly worker owns teardown."""

    def __init__(
        self,
        window: object,
        service: object,
        hooks: _DesktopCloseHooks,
        *,
        window_title: str,
        close_appearance: Callable[[], None] | None = None,
        render_status: Callable[[object, _ClosePhase], None] | None = None,
        retry_prompt: Callable[[], bool] | None = None,
    ) -> None:
        self._window = window
        self._service = service
        self._hooks = hooks
        self._close_appearance = close_appearance or (lambda: None)
        self._window_title = window_title
        self._render_status = (
            _render_close_status if render_status is None else render_status
        )
        self._uses_bound_status = (
            self._render_status is _ORIGINAL_CLOSE_STATUS_RENDERER
        )
        self._status_target: object | None = None
        self._retry_prompt = (
            (lambda: _show_retry_close_prompt(self._window_title))
            if retry_prompt is None
            else retry_prompt
        )
        self._lock = Lock()
        self._presentation_lock = Lock()
        self._phase = _ClosePhase.STARTING
        self._startup_close_requested = False
        self._prompt_active = False
        self._attempt_done = Event()
        self._attempt_done.set()
        self._service_shutdown_complete = False

    @property
    def service_shutdown_complete(self) -> bool:
        with self._lock:
            return self._service_shutdown_complete

    def _wait_for_attempt(self) -> None:
        self._attempt_done.wait()

    def _is_open(self) -> bool:
        with self._lock:
            return self._phase is _ClosePhase.OPEN

    def _begin_readiness_refusal(
        self,
        record_failure: Callable[[], None],
    ) -> bool | None:
        if not callable(record_failure):
            raise TypeError("readiness failure recorder must be callable")
        start_attempt = False
        with self._lock:
            if self._phase is _ClosePhase.STARTING:
                return False
            if self._phase is _ClosePhase.OPEN:
                self._phase = _ClosePhase.CLOSING
                self._attempt_done.clear()
                start_attempt = True
            elif self._phase is _ClosePhase.STARTUP_REFUSED:
                return False
            else:
                return None
        if start_attempt:
            record_failure()
            self._start_attempt()
        return True

    def _on_closing(self) -> bool | None:
        start_attempt = False
        start_prompt = False
        with self._lock:
            if self._phase in {
                _ClosePhase.PROGRAMMATIC_CLOSE,
                _ClosePhase.STARTUP_REFUSED,
            }:
                return None
            if self._phase is _ClosePhase.STARTING:
                self._startup_close_requested = True
            elif self._phase is _ClosePhase.OPEN:
                self._phase = _ClosePhase.CLOSING
                self._attempt_done.clear()
                start_attempt = True
            elif (
                self._phase is _ClosePhase.RETRYABLE
                and not self._prompt_active
            ):
                self._prompt_active = True
                start_prompt = True
        if start_attempt:
            self._start_attempt()
        elif start_prompt:
            self._start_prompt()
        return False

    def _mark_loaded(self) -> bool:
        start_attempt = False
        opened = False
        with self._lock:
            if self._phase is _ClosePhase.STARTING:
                if self._startup_close_requested:
                    self._phase = _ClosePhase.CLOSING
                    self._attempt_done.clear()
                    start_attempt = True
                else:
                    self._phase = _ClosePhase.OPEN
                    opened = True
            elif self._phase is _ClosePhase.OPEN:
                opened = True
        if start_attempt:
            self._start_attempt()
        return opened

    def _mark_startup_refused(self) -> bool:
        with self._lock:
            if self._phase in {
                _ClosePhase.PROGRAMMATIC_CLOSE,
                _ClosePhase.STARTUP_REFUSED,
            }:
                return False
            self._phase = _ClosePhase.STARTUP_REFUSED
            return True

    def _start_attempt(self) -> None:
        try:
            Thread(
                target=self._run_attempt,
                name="namisync-desktop-close",
                daemon=True,
            ).start()
        except Exception as error:
            self._attempt_done.set()
            _log_cleanup_failure("shutdown.worker_start_failed", error)
            self._become_retryable()

    def _run_attempt(self) -> None:
        retryable = False
        try:
            _quiesce_desktop(
                self._hooks,
                after_waiters_wake=lambda: self._start_status(
                    _ClosePhase.CLOSING
                ),
            )
            shutdown = self._service.close()
        except Exception as error:
            _log_cleanup_failure("shutdown.attempt_failed", error)
            retryable = True
        else:
            retryable = self._settle_attempt(shutdown)
        finally:
            self._attempt_done.set()
        if retryable:
            self._become_retryable()

    def _settle_attempt(self, shutdown: object) -> bool:
        if not shutdown.complete:
            logging.getLogger("namisync").error(
                "shutdown.incomplete unfinished_count=%d custody_released=%s",
                len(shutdown.unfinished),
                shutdown.custody_released,
            )
            return True

        should_destroy = False
        with self._lock:
            self._service_shutdown_complete = True
            if self._phase is not _ClosePhase.STARTUP_REFUSED:
                self._phase = _ClosePhase.PROGRAMMATIC_CLOSE
                should_destroy = True
        if not should_destroy:
            return False
        try:
            self._close_appearance()
        except Exception as error:
            _log_presentation_failure("appearance.cleanup_failed", error)
        try:
            self._window.destroy()
        except Exception as error:
            _log_cleanup_failure("shutdown.window_destroy_failed", error)
        return False

    def _become_retryable(self) -> None:
        start_prompt = False
        with self._lock:
            if self._phase is _ClosePhase.STARTUP_REFUSED:
                return
            self._phase = _ClosePhase.RETRYABLE
            if not self._prompt_active:
                self._prompt_active = True
                start_prompt = True
        self._start_status(_ClosePhase.RETRYABLE)
        if start_prompt:
            self._start_prompt()

    def _start_status(self, phase: _ClosePhase) -> None:
        try:
            Thread(
                target=self._show_status,
                args=(phase,),
                name="namisync-close-status",
                daemon=True,
            ).start()
        except Exception as error:
            _log_cleanup_failure("shutdown.status_worker_start_failed", error)

    def _start_prompt(self) -> None:
        try:
            Thread(
                target=self._run_prompt,
                name="namisync-close-retry",
                daemon=True,
            ).start()
        except Exception as error:
            with self._lock:
                self._prompt_active = False
            _log_cleanup_failure("shutdown.retry_prompt_start_failed", error)

    def _run_prompt(self) -> None:
        retry = False
        try:
            retry = bool(self._retry_prompt())
        except Exception as error:
            _log_cleanup_failure("shutdown.retry_prompt_failed", error)

        start_attempt = False
        with self._lock:
            self._prompt_active = False
            if retry and self._phase is _ClosePhase.RETRYABLE:
                self._phase = _ClosePhase.CLOSING
                self._attempt_done.clear()
                start_attempt = True
        if start_attempt:
            self._start_attempt()

    def _show_status(self, phase: _ClosePhase) -> None:
        with self._presentation_lock:
            with self._lock:
                if self._phase is not phase:
                    return
            try:
                if self._uses_bound_status:
                    status = self._status_target
                    if status is None:
                        logging.getLogger("namisync").error(
                            "shutdown.status_target_unavailable"
                        )
                        return
                    _render_close_status_target(status, phase)
                else:
                    self._render_status(self._window, phase)
            except Exception as error:
                _log_presentation_failure("shutdown.status_render_failed", error)

    def _bind_status_target(self) -> None:
        if not self._uses_bound_status:
            return
        try:
            status = self._window.dom.get_element("#host-status")
        except Exception as error:
            _log_presentation_failure("shutdown.status_bind_failed", error)
            status = None
        if status is None:
            logging.getLogger("namisync").error(
                "shutdown.status_target_unavailable"
            )
        with self._presentation_lock:
            self._status_target = status


def run_desktop(
    paths: AppPaths,
    identity: DesktopInstanceIdentity,
    *,
    startup_error: Callable[[str], None],
    instance_native: InstanceNative | None = None,
    index_path: str | Path | None = None,
    startup_deadline_scheduler: Callable[
        [float, Callable[[], None]], Callable[[], None]
    ] = _schedule_startup_deadline,
) -> int:
    """Run the secured headed composition and retain every native owner."""

    lease: DesktopInstanceLease | None = None
    path_lease: AppPathLease | None = None
    service = None
    registry = None
    dispatcher = None
    cosmetics = None
    initial_appearance = None
    close_controller: _DesktopCloseController | None = None
    appearance_controller = None
    document_channel = None
    startup_gate: DesktopReadinessGate | None = None
    logging_configured = False
    failure: Exception | None = None

    def close_appearance() -> None:
        nonlocal appearance_controller, document_channel
        controller = appearance_controller
        appearance_controller = None
        channel = document_channel
        document_channel = None
        if controller is not None:
            try:
                controller.close()
            except Exception as error:
                _log_presentation_failure("appearance.cleanup_failed", error)
        close_channel = getattr(channel, "close", None)
        if callable(close_channel):
            try:
                close_channel()
            except Exception as error:
                _log_presentation_failure("document_channel.cleanup_failed", error)

    try:
        admission = acquire_desktop_instance(identity, native=instance_native)
        if not admission.is_primary:
            if admission.activation_error is not None:
                startup_error(admission.activation_error)
            return _EXIT_SUCCESS
        lease = admission.lease
        if lease is None:
            raise RuntimeError("primary desktop admission did not retain its mutex")

        path_lease = paths.acquire_lease()
        _configure_logging(paths)
        logging_configured = True
        webview_module = _load_webview()
        _log_startup_dependencies()
        _prepare_webview_host(webview_module)

        service = _create_service(paths)
        contract = service.validate_database_contracts()
        if contract.state == "fresh":
            contract = service.initialize_database_contracts()
        if contract.state == "ready":
            path_lease.bind_databases()
            contract = service.validate_database_contracts()
        if contract.state != "ready":
            direction = contract.reset_direction or (
                "Close NamiSync and correct the local database pair, then retry."
            )
            reason = contract.reason or contract.state
            raise DesktopStartupError(
                f"NamiSync database pair refused ({reason}). {direction}"
            )
        registry = _task_registry(service)
        cosmetics = _ui_state_owner(paths.ui_state)
        initial_appearance = _read_initial_appearance(cosmetics)
        startup_gate = DesktopReadinessGate(startup_deadline_scheduler)

        def acknowledge_readiness(generation: int, challenge: str) -> bool:
            channel = document_channel
            if channel is not None:
                from .document_channel import DocumentPostKind

                acknowledge = getattr(channel, "acknowledge", None)
                if callable(acknowledge):
                    acknowledge(
                        DocumentPostKind.REQUIRED,
                        (generation, challenge),
                    )
            return startup_gate.acknowledge_echo(generation, challenge)

        def acknowledge_appearance(revision: int) -> None:
            channel = document_channel
            if channel is None:
                return
            from .document_channel import DocumentPostKind

            acknowledge = getattr(channel, "acknowledge", None)
            if callable(acknowledge):
                acknowledge(DocumentPostKind.REPLACEABLE, revision)

        document = _pending_document()
        slots = _folder_slots()
        picker = _NativeFolderPicker(webview_module)
        commands = _production_commands(
            picker=picker,
            slots=slots,
            registry=registry,
            cosmetics=cosmetics,
            startup_gate=startup_gate,
            readiness_echo=acknowledge_readiness,
            appearance_acknowledged=acknowledge_appearance,
        )
        dispatcher = _bridge_dispatcher(document, commands, startup_gate)
        window = webview_module.create_window(
            identity.window_title,
            _desktop_index_path(index_path),
            js_api=None,
            background_color=_opaque_window_background(initial_appearance),
            transparent=False,
            width=1280,
            height=800,
            min_size=(1024, 640),
        )
        if window is None:
            raise DesktopStartupError("NamiSync could not create its desktop window")
        _expose_bridge_api(window, dispatcher)
        picker.bind(window)

        state = _StartupState()

        close_controller = _DesktopCloseController(
            window,
            service,
            _desktop_close_hooks(dispatcher, registry),
            window_title=identity.window_title,
            close_appearance=close_appearance,
        )

        def refuse_startup(error: Exception) -> None:
            ordinary_close = close_controller._begin_readiness_refusal(
                lambda: state.refuse(error)
            )
            if ordinary_close is None:
                return
            if ordinary_close:
                return
            state.refuse(error)
            if not close_controller._mark_startup_refused():
                return
            for event, reject in (
                ("startup.dispatch_rejection_failed", dispatcher.begin_close),
                ("startup.registry_wake_failed", registry.begin_close),
            ):
                try:
                    reject()
                except Exception as close_error:
                    _log_cleanup_failure(event, close_error)
            close_appearance()
            state.destroy_once(window)

        def initialize_security() -> None:
            nonlocal appearance_controller, document_channel
            try:
                real_url = window.real_url
                _bind_document_origin(document, real_url)
                _configure_window_security(
                    window,
                    real_url,
                    document,
                    _log_startup_renderer,
                )
            except Exception as error:
                state.refuse(error)
                raise
            window.events.before_load += startup_gate.begin_generation
            window.events.before_load += dispatcher._retire_document_responses

            def bind_document_channel() -> None:
                nonlocal document_channel
                channel = None
                try:
                    generation = startup_gate.command_context().generation
                    revoke_publication = getattr(
                        appearance_controller,
                        "_revoke_document_publication",
                        None,
                    )
                    if document_channel is None:
                        channel = _document_channel(window)
                        dispatcher._bind_document_channel(channel)
                        bind_appearance_channel = getattr(
                            appearance_controller,
                            "_bind_document_channel",
                            None,
                        )
                        if callable(bind_appearance_channel):
                            bind_appearance_channel(channel)
                    if callable(revoke_publication):
                        revoke_publication(generation)
                    if channel is not None:
                        document_channel = channel
                        return
                    replace_document = getattr(
                        document_channel,
                        "replace_document",
                        None,
                    )
                    if callable(replace_document):
                        replace_document()
                    return
                except Exception as error:
                    close_channel = getattr(channel, "close", None)
                    if callable(close_channel):
                        try:
                            close_channel()
                        except Exception as close_error:
                            _log_presentation_failure(
                                "document_channel.cleanup_failed",
                                close_error,
                            )
                    _log_presentation_failure(
                        "readiness.document_channel_bind_failed",
                        error,
                    )
                    startup_gate.refuse(
                        DesktopStartupError(
                            "NamiSync could not bind its document channel"
                        )
                    )
                    return

            window.events.before_load += bind_document_channel
            try:
                appearance_controller = _configure_window_appearance(
                    window,
                    cosmetics,
                    initial_appearance,
                )
            except Exception as error:
                _log_presentation_failure(
                    "appearance.configuration_failed",
                    error,
                )

                def request_surface_settlement(
                    callback: Callable[[Exception | None], None],
                ) -> None:
                    callback(None)
            else:
                request_surface_settlement = (
                    appearance_controller.request_initial_surface_settlement
                )

            def request_challenge_post(
                generation: int,
                challenge: str,
                callback: Callable[[Exception | None], None],
            ) -> None:
                channel = document_channel
                if channel is None:
                    raise RuntimeError("desktop document channel is unavailable")
                channel.post(
                    {
                        "kind": "namisync.readiness.v1",
                        "challenge": challenge,
                    },
                    still_current=lambda: startup_gate.recognizes_echo(
                        generation,
                        challenge,
                    ),
                    completion=callback,
                    kind=_required_document_post_kind(),
                    acknowledgment=(generation, challenge),
                )

            def open_desktop(generation: int) -> bool:
                opened = close_controller._mark_loaded()
                if not opened:
                    return False
                controller = appearance_controller
                open_publication = getattr(
                    controller,
                    "_open_document_publication",
                    None,
                )
                if callable(open_publication):
                    try:
                        publication_opened = open_publication(generation)
                    except Exception as error:
                        _log_presentation_failure(
                            "appearance.document_publication_failed",
                            error,
                        )
                    else:
                        if type(publication_opened) is not bool:
                            _log_presentation_failure(
                                "appearance.document_publication_failed",
                                TypeError(
                                    "appearance publication returned invalid data"
                                ),
                            )
                            return False
                        if not publication_opened:
                            return False
                return True

            startup_gate.bind(
                request_surface_settlement=request_surface_settlement,
                request_challenge_post=request_challenge_post,
                open_desktop=open_desktop,
                refuse_desktop=refuse_startup,
            )
            window.events.loaded += loaded_watchdog

        def loaded_watchdog() -> None:
            close_controller._bind_status_target()
            attachment_error = document.attachment_error
            if document.is_attached and attachment_error is None:
                startup_gate.native_loaded()
                return
            if attachment_error is None:
                error = DesktopStartupError(
                    "WebView2 security guards did not attach before page load"
                )
            else:
                error = DesktopStartupError(
                    "WebView2 security guards could not attach: "
                    f"{attachment_error}"
                )
            startup_gate.refuse(error)

        def on_closing() -> bool | None:
            cancel_readiness = close_controller._is_open()
            result = close_controller._on_closing()
            if cancel_readiness:
                startup_gate.cancel()
            return result

        window.events.closing += on_closing
        _start_webview(
            webview_module,
            on_initialized=initialize_security,
            storage_path=str(paths.webview2),
        )
        if state.failure is not None:
            raise state.failure
    except Exception as error:
        failure = error
        if logging_configured:
            try:
                _log_startup_failure(error)
            except BaseException:
                pass
    finally:
        if startup_gate is not None:
            startup_gate.cancel()
        if close_controller is not None:
            close_controller._wait_for_attempt()
        cleanup_failure = _finalize_primary(
            service,
            dispatcher=dispatcher,
            registry=registry,
            service_shutdown_complete=(
                close_controller.service_shutdown_complete
                if close_controller is not None
                else False
            ),
            logging_configured=logging_configured,
            log_path=paths.log_file if logging_configured else None,
            lease=lease,
            path_lease=path_lease,
            close_presentation=close_appearance,
            cosmetics=cosmetics,
        )
        if failure is None:
            failure = cleanup_failure

    if failure is not None:
        startup_error(_startup_failure_message(failure))
        return _EXIT_STARTUP
    return _EXIT_SUCCESS


def _configure_logging(paths: AppPaths) -> None:
    from .logging_config import configure_logging

    configure_logging(paths)


def _load_webview():
    return importlib.import_module("webview")


def _log_startup_dependencies() -> None:
    from .logging_config import log_startup_dependencies

    log_startup_dependencies()


def _log_startup_renderer(browser_version: str) -> None:
    from .logging_config import log_startup_renderer

    log_startup_renderer(browser_version)


def _log_startup_failure(error: Exception) -> None:
    from .logging_config import log_startup_failure

    log_startup_failure(error)


def _prepare_webview_host(webview_module: object) -> None:
    from .bridge import prepare_pywebview_host

    prepare_pywebview_host(webview_module)


def _create_service(paths: AppPaths):
    from namisync.interfaces.service import NamiSyncService

    return NamiSyncService(
        paths.ledger,
        paths.history,
        settings_path=paths.settings,
    )


def _pending_document():
    from .bridge import NativeDocumentState

    return NativeDocumentState()


def _folder_slots():
    from .slots import FolderSlotTable

    return FolderSlotTable()


def _task_registry(service: object):
    from .drain import TaskRegistry

    return TaskRegistry(service)


def _ui_state_owner(path: Path):
    from namisync.interfaces.ui_state import UiStateOwner

    return UiStateOwner(path)


def _read_initial_appearance(cosmetics: object):
    try:
        return cosmetics.read_section("appearance", 1)
    except Exception as error:
        _log_presentation_failure("appearance.cosmetic_initial_read_failed", error)
        return None


def _production_commands(
    *,
    picker: object,
    slots: object,
    registry: object,
    cosmetics: object,
    startup_gate: DesktopReadinessGate,
    readiness_echo: Callable[[int, str], bool] | None = None,
    appearance_acknowledged: Callable[[int], None] | None = None,
):
    from .commands import production_command_specs

    return production_command_specs(
        picker=picker,
        slots=slots,
        registry=registry,
        cosmetics=cosmetics,
        shell_ready=startup_gate.acknowledge_shell,
        readiness_echo=(
            startup_gate.acknowledge_echo
            if readiness_echo is None
            else readiness_echo
        ),
        appearance_acknowledged=appearance_acknowledged,
    )


def _bridge_dispatcher(
    document: object,
    commands: object,
    startup_gate: DesktopReadinessGate,
):
    from .bridge import AdmissionGranted, AdmissionRefused, BridgeDispatcher
    from .commands import CommandSpec
    from .readiness import CommandPhase, ReadinessContext

    command_specs = dict(commands)

    def admit(name: str) -> object:
        spec = command_specs.get(name)
        if type(spec) is not CommandSpec:
            return AdmissionRefused()
        context = startup_gate.command_context()
        if (
            name == "readiness_echo"
            and type(context) is ReadinessContext
            and context.phase is CommandPhase.OPEN
        ):
            context = ReadinessContext(CommandPhase.BOOTSTRAP, context.generation)
        if (
            type(context) is not ReadinessContext
            or context.phase is not spec.phase
        ):
            return AdmissionRefused()
        return AdmissionGranted(context)

    return BridgeDispatcher(
        document=document,
        commands=command_specs,
        admit=admit,
    )


class _PywebviewCallbackRegistry(dict):
    """Keep asynchronous callbacks without unused synchronous sentinel cells."""

    def __setitem__(self, key: str, callback: object) -> None:
        if callback is not None:
            super().__setitem__(key, callback)


def _expose_bridge_api(window: object, dispatcher: object) -> None:
    """Expose only the exact RPC function through pywebview's function table."""

    if type(window._callbacks) is not dict or window._callbacks:
        raise RuntimeError("native callback registry is not empty before exposure")
    window._callbacks = _PywebviewCallbackRegistry()
    _contain_obsolete_native_returns(window, dispatcher)

    def dispatch(command_json: str) -> object:
        return dispatcher._dispatch_native(command_json)

    window.expose(dispatch)


def _contain_obsolete_native_returns(window: object, dispatcher: object) -> None:
    """Keep pywebview from returning into a retired document callback."""

    from webview.errors import JavascriptException

    evaluate = window.evaluate_js
    if not callable(evaluate):
        raise TypeError("native JavaScript evaluator must be callable")

    def evaluate_current_document(*args: object, **kwargs: object) -> object:
        generation = dispatcher._claim_native_return_generation()
        if generation is None:
            return evaluate(*args, **kwargs)
        if not dispatcher._is_document_generation_current(generation):
            return None
        try:
            return evaluate(*args, **kwargs)
        except JavascriptException as error:
            if dispatcher._is_document_generation_current(generation):
                raise
            retire_exception_graph(error)
            return None

    window.evaluate_js = evaluate_current_document


def _document_channel(window: object):
    from .document_channel import DocumentChannel

    return DocumentChannel(window.native, require_acknowledgment=True)


def _required_document_post_kind():
    from .document_channel import DocumentPostKind

    return DocumentPostKind.REQUIRED


def _desktop_close_hooks(
    dispatcher: object,
    registry: object,
) -> _DesktopCloseHooks:
    return _DesktopCloseHooks(
        reject_dispatch=dispatcher.begin_close,
        wake_waiters=registry.begin_close,
        wait_for_handlers=dispatcher.wait_for_handlers,
    )


def _packaged_index_path() -> str:
    package = importlib.resources.files("namisync.interfaces.web")
    return str(package / "assets" / "index.html")


def _desktop_index_path(index_path: str | Path | None) -> str:
    if index_path is None:
        return _packaged_index_path()
    from .paths import resolve_local_index_path

    return str(resolve_local_index_path(index_path))


def _configure_window_security(
    window: object,
    trusted_url: str,
    document: object,
    renderer_callback: Callable[[str], None],
) -> None:
    from .bridge import configure_pywebview2_security

    configure_pywebview2_security(
        window,
        trusted_url,
        document=document,
        on_browser_version=renderer_callback,
    )


def _opaque_window_background(initial_appearance: object | None = None) -> str:
    from .appearance import opaque_window_background

    if initial_appearance is None:
        return opaque_window_background()
    return opaque_window_background(theme_mode=initial_appearance.value.theme)


def _configure_window_appearance(
    window: object,
    cosmetics: object | None = None,
    initial_appearance: object | None = None,
):
    from .appearance import configure_window_appearance

    return configure_window_appearance(
        window,
        cosmetics=cosmetics,
        initial_cosmetic=initial_appearance,
    )


def _bind_document_origin(document: object, trusted_url: str) -> None:
    from .bridge import ExactOrigin

    document.bind_origin(ExactOrigin.from_url(trusted_url))


def _start_webview(
    webview_module: object,
    *,
    on_initialized: Callable[[], None],
    storage_path: str,
) -> None:
    from .bridge import start_edge_chromium

    start_edge_chromium(
        webview_module,
        on_initialized=on_initialized,
        storage_path=storage_path,
    )


def _render_close_status(window: object, phase: _ClosePhase) -> None:
    status = window.dom.get_element("#host-status")
    if status is None:
        raise RuntimeError("desktop close status element is unavailable")
    _render_close_status_target(status, phase)


def _render_close_status_target(status: object, phase: _ClosePhase) -> None:
    messages = {
        _ClosePhase.CLOSING: "Closing safely…",
        _ClosePhase.RETRYABLE: (
            "Close did not finish. Choose Retry in the close dialog to try again."
        ),
    }
    try:
        message = messages[phase]
    except KeyError as error:
        raise ValueError("unsupported desktop close presentation state") from error
    status.text = message


_ORIGINAL_CLOSE_STATUS_RENDERER = _render_close_status


def _show_retry_close_prompt(window_title: str) -> bool:
    user32 = ctypes.windll.user32
    owner = user32.FindWindowW(None, window_title)
    result = user32.MessageBoxW(
        owner or None,
        _CLOSE_INCOMPLETE_MESSAGE,
        _CLOSE_INCOMPLETE_CAPTION,
        _MB_RETRYCANCEL | _MB_ICONWARNING | _MB_SETFOREGROUND,
    )
    return int(result) == _ID_RETRY


def _finalize_primary(
    service: object | None,
    *,
    dispatcher: object | None,
    registry: object | None,
    service_shutdown_complete: bool,
    logging_configured: bool,
    log_path: Path | None,
    lease: DesktopInstanceLease | None,
    path_lease: object | None = None,
    close_presentation: Callable[[], None] | None = None,
    cosmetics: object | None = None,
) -> Exception | None:
    failure: Exception | None = None
    safe_to_release_owners = service is None or service_shutdown_complete
    if service is not None and not service_shutdown_complete:
        quiesced = True
        if dispatcher is not None and registry is not None:
            try:
                _quiesce_desktop(_desktop_close_hooks(dispatcher, registry))
            except _DesktopQuiescenceError as error:
                events = {
                    "dispatch_rejection": "startup.dispatch_rejection_failed",
                    "registry_wake": "startup.registry_wake_failed",
                    "handler_wait": "startup.handler_wait_failed",
                }
                cause = error.__cause__
                if not isinstance(cause, Exception):
                    cause = error
                _log_cleanup_failure(events[error.step], cause)
                if failure is None:
                    failure = cause
                quiesced = False
        elif registry is not None:
            try:
                registry.begin_close()
            except Exception as error:
                _log_cleanup_failure("startup.registry_wake_failed", error)
                if failure is None:
                    failure = error
                quiesced = False
        if quiesced:
            try:
                shutdown = service.close()
                if not shutdown.complete:
                    logging.getLogger("namisync").error(
                        "startup.cleanup_incomplete unfinished_count=%d "
                        "custody_released=%s",
                        len(shutdown.unfinished),
                        shutdown.custody_released,
                    )
                    if failure is None:
                        failure = DesktopStartupError(
                            "NamiSync desktop cleanup did not complete"
                        )
                else:
                    safe_to_release_owners = True
            except Exception as error:
                _log_cleanup_failure("startup.service_cleanup_failed", error)
                if failure is None:
                    failure = error
    if safe_to_release_owners and close_presentation is not None:
        try:
            close_presentation()
        except Exception as error:
            _log_cleanup_failure("startup.presentation_cleanup_failed", error)
            if failure is None:
                failure = error
    if safe_to_release_owners and cosmetics is not None:
        try:
            cosmetics.close()
        except Exception as error:
            _log_cleanup_failure("startup.cosmetic_cleanup_failed", error)
            if failure is None:
                failure = error
    if logging_configured and safe_to_release_owners:
        try:
            _shutdown_logging()
        except Exception as error:
            _log_cleanup_failure(
                "startup.logging_cleanup_failed",
                error,
                log_path=log_path,
            )
            if failure is None:
                failure = error
    if path_lease is not None and safe_to_release_owners:
        try:
            path_lease.close()
        except Exception as error:
            _log_cleanup_failure(
                "startup.path_lease_cleanup_failed",
                error,
                log_path=log_path,
            )
            if failure is None:
                failure = error
    if lease is not None and safe_to_release_owners:
        try:
            lease.close()
        except Exception as error:
            _log_cleanup_failure(
                "startup.mutex_cleanup_failed",
                error,
                log_path=log_path,
            )
            if failure is None:
                failure = error
    return failure


def _shutdown_logging() -> None:
    from .logging_config import shutdown_logging

    shutdown_logging()


def _log_cleanup_failure(
    event: str,
    error: Exception,
    *,
    log_path: Path | None = None,
) -> None:
    if log_path is not None:
        from .logging_config import record_late_cleanup_failure

        record_late_cleanup_failure(log_path, event, error)
        return
    logging.getLogger("namisync").error(
        "%s exception_type=%s",
        event,
        type(error).__name__,
        exc_info=(type(error), error, error.__traceback__),
    )


def _log_presentation_failure(event: str, error: Exception) -> None:
    logging.getLogger("namisync").error(
        "%s exception_type=%s",
        event,
        type(error).__name__,
    )


def _startup_failure_message(error: Exception) -> str:
    message = str(error).strip()
    return message or "NamiSync could not start the desktop host"
