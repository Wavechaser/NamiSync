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
from threading import Event, Lock, Thread
from typing import Callable, Protocol, TYPE_CHECKING

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


class _InstanceNative(Protocol):
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

    def __init__(self, handle: object, native: _InstanceNative) -> None:
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
    native: _InstanceNative | None = None,
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


class DesktopStartupError(RuntimeError):
    """The primary desktop host could not safely open its product window."""


class _StartupState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._failure: Exception | None = None
        self._destroyed = False

    @property
    def failure(self) -> Exception | None:
        with self._lock:
            return self._failure

    def refuse(self, error: Exception) -> None:
        with self._lock:
            if self._failure is None:
                self._failure = error

    def destroy_once(self, window: object) -> None:
        with self._lock:
            if self._destroyed:
                return
            self._destroyed = True
        try:
            window.destroy()
        except Exception as error:
            _log_cleanup_failure("startup.window_destroy_failed", error)


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
    unsubscribe_observations: Callable[[], None]


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
        ("observation_cleanup", hooks.unsubscribe_observations),
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

    def _mark_loaded(self) -> None:
        self._bind_status_target()
        start_attempt = False
        with self._lock:
            if self._phase is _ClosePhase.STARTING:
                if self._startup_close_requested:
                    self._phase = _ClosePhase.CLOSING
                    self._attempt_done.clear()
                    start_attempt = True
                else:
                    self._phase = _ClosePhase.OPEN
        if start_attempt:
            self._start_attempt()

    def _mark_startup_refused(self) -> bool:
        with self._lock:
            if self._phase is _ClosePhase.PROGRAMMATIC_CLOSE:
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
    instance_native: _InstanceNative | None = None,
    index_path: str | Path | None = None,
) -> int:
    """Run the secured headed composition and retain every native owner."""

    lease: DesktopInstanceLease | None = None
    path_lease: AppPathLease | None = None
    service = None
    registry = None
    dispatcher = None
    close_controller: _DesktopCloseController | None = None
    appearance_controller = None
    logging_configured = False
    failure: Exception | None = None

    def close_appearance() -> None:
        nonlocal appearance_controller
        controller = appearance_controller
        if controller is None:
            return
        appearance_controller = None
        try:
            controller.close()
        except Exception as error:
            _log_presentation_failure("appearance.cleanup_failed", error)

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

        document = _pending_document()
        slots = _folder_slots()
        picker = _NativeFolderPicker(webview_module)
        commands = _production_commands(
            picker=picker,
            slots=slots,
            registry=registry,
        )
        dispatcher = _bridge_dispatcher(document, commands)
        window = webview_module.create_window(
            identity.window_title,
            _desktop_index_path(index_path),
            js_api=None,
            background_color=_opaque_window_background(),
            transparent=False,
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

        def initialize_security() -> None:
            nonlocal appearance_controller
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
            try:
                appearance_controller = _configure_window_appearance(window)
            except Exception as error:
                _log_presentation_failure(
                    "appearance.configuration_failed",
                    error,
                )
                state.refuse(error)
                raise

        def loaded_watchdog() -> None:
            attachment_error = document.attachment_error
            appearance_failure = (
                getattr(appearance_controller, "startup_failure", None)
                if appearance_controller is not None
                else None
            )
            if (
                document.is_attached
                and attachment_error is None
                and appearance_failure is None
            ):
                close_controller._mark_loaded()
                return
            if appearance_failure is not None:
                error = appearance_failure
            elif attachment_error is None:
                error = DesktopStartupError(
                    "WebView2 security guards did not attach before page load"
                )
            else:
                error = DesktopStartupError(
                    "WebView2 security guards could not attach: "
                    f"{attachment_error}"
                )
            state.refuse(error)
            if close_controller._mark_startup_refused():
                close_appearance()
                state.destroy_once(window)

        window.events.closing += close_controller._on_closing
        window.events.loaded += loaded_watchdog
        _start_webview(
            webview_module,
            on_initialized=initialize_security,
            storage_path=str(paths.webview2),
        )
        if state.failure is not None:
            raise state.failure
    except Exception as error:
        failure = error
    finally:
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


def _production_commands(
    *,
    picker: object,
    slots: object,
    registry: object,
):
    from .commands import production_command_specs

    return production_command_specs(
        picker=picker,
        slots=slots,
        registry=registry,
    )


def _bridge_dispatcher(document: object, commands: object):
    from .bridge import BridgeDispatcher

    return BridgeDispatcher(document=document, commands=commands)


def _expose_bridge_api(window: object, dispatcher: object) -> None:
    """Expose only the exact RPC function through pywebview's function table."""

    def dispatch(command_json: str) -> object:
        return dispatcher.dispatch(command_json)

    window.expose(dispatch)


def _desktop_close_hooks(
    dispatcher: object,
    registry: object,
) -> _DesktopCloseHooks:
    return _DesktopCloseHooks(
        reject_dispatch=dispatcher.begin_close,
        wake_waiters=registry.begin_close,
        wait_for_handlers=dispatcher.wait_for_handlers,
        unsubscribe_observations=registry.unsubscribe_all,
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


def _opaque_window_background() -> str:
    from .appearance import opaque_window_background

    return opaque_window_background()


def _configure_window_appearance(window: object):
    from .appearance import configure_window_appearance

    return configure_window_appearance(window)


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
                    "observation_cleanup": (
                        "startup.observation_cleanup_failed"
                    ),
                }
                cause = error.__cause__
                if not isinstance(cause, Exception):
                    cause = error
                _log_cleanup_failure(events[error.step], cause)
                if failure is None:
                    failure = cause
                quiesced = False
        elif registry is not None:
            for event, callback in (
                ("startup.registry_wake_failed", registry.begin_close),
                (
                    "startup.observation_cleanup_failed",
                    registry.unsubscribe_all,
                ),
            ):
                try:
                    callback()
                except Exception as error:
                    _log_cleanup_failure(event, error)
                    if failure is None:
                        failure = error
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
