"""Desktop host composition and native lifetime primitives."""

from __future__ import annotations

import ctypes
import importlib
import importlib.resources
import logging
from ctypes import wintypes
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Callable, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from .paths import AppPaths


_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9
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
        self._user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
        self._user32.FindWindowW.restype = wintypes.HWND
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
            self._handle = None
        self._native.close_handle(handle)


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


class _DesktopCloseController:
    """Veto synchronous user closes while one orderly worker owns teardown."""

    def __init__(
        self,
        window: object,
        service: object,
        hooks: _DesktopCloseHooks,
        *,
        window_title: str,
        render_status: Callable[[object, _ClosePhase], None] | None = None,
        retry_prompt: Callable[[], bool] | None = None,
    ) -> None:
        self._window = window
        self._service = service
        self._hooks = hooks
        self._window_title = window_title
        self._render_status = (
            _render_close_status if render_status is None else render_status
        )
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
            self._hooks.reject_dispatch()
            self._hooks.wake_waiters()
            self._start_status(_ClosePhase.CLOSING)
            self._hooks.wait_for_handlers()
            self._hooks.unsubscribe_observations()
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
                self._render_status(self._window, phase)
            except Exception as error:
                _log_cleanup_failure("shutdown.status_render_failed", error)


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
    service = None
    close_controller: _DesktopCloseController | None = None
    logging_configured = False
    failure: Exception | None = None
    try:
        admission = acquire_desktop_instance(identity, native=instance_native)
        if not admission.is_primary:
            if admission.activation_error is not None:
                startup_error(admission.activation_error)
            return _EXIT_SUCCESS
        lease = admission.lease
        if lease is None:
            raise RuntimeError("primary desktop admission did not retain its mutex")

        _configure_logging(paths)
        logging_configured = True
        webview_module = _load_webview()
        _log_startup_dependencies()
        _prepare_webview_host(webview_module)

        service = _create_service(paths)
        contract = service.validate_database_contracts()
        if contract.state == "fresh":
            contract = service.initialize_database_contracts()
        if contract.state != "ready":
            direction = contract.reset_direction or (
                "Close NamiSync and correct the local database pair, then retry."
            )
            reason = contract.reason or contract.state
            raise DesktopStartupError(
                f"NamiSync database pair refused ({reason}). {direction}"
            )

        document = _pending_document()
        dispatcher = _closed_dispatcher(document)
        window = webview_module.create_window(
            identity.window_title,
            _desktop_index_path(index_path),
            js_api=dispatcher,
        )
        if window is None:
            raise DesktopStartupError("NamiSync could not create its desktop window")

        state = _StartupState()
        close_controller = _DesktopCloseController(
            window,
            service,
            _desktop_close_hooks(dispatcher),
            window_title=identity.window_title,
        )

        def initialize_security() -> None:
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

        def loaded_watchdog() -> None:
            attachment_error = document.attachment_error
            if document.is_attached and attachment_error is None:
                close_controller._mark_loaded()
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
            state.refuse(error)
            if close_controller._mark_startup_refused():
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
            service_shutdown_complete=(
                close_controller.service_shutdown_complete
                if close_controller is not None
                else False
            ),
            logging_configured=logging_configured,
            log_path=paths.log_file if logging_configured else None,
            lease=lease,
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


def _closed_dispatcher(document: object):
    from .bridge import BridgeDispatcher

    return BridgeDispatcher(document=document, commands={})


def _desktop_close_hooks(dispatcher: object) -> _DesktopCloseHooks:
    return _DesktopCloseHooks(
        reject_dispatch=dispatcher._reject_new,
        wake_waiters=_noop_close_hook,
        wait_for_handlers=dispatcher._wait_for_handlers,
        unsubscribe_observations=_noop_close_hook,
    )


def _noop_close_hook() -> None:
    return None


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
    status = window.dom.get_element("#host-status")
    if status is None:
        raise RuntimeError("desktop close status element is unavailable")
    status.text = message


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
    service_shutdown_complete: bool,
    logging_configured: bool,
    log_path: Path | None,
    lease: DesktopInstanceLease | None,
) -> Exception | None:
    failure: Exception | None = None
    if service is not None and not service_shutdown_complete:
        try:
            shutdown = service.close()
            if not shutdown.complete:
                logging.getLogger("namisync").error(
                    "startup.cleanup_incomplete unfinished_count=%d "
                    "custody_released=%s",
                    len(shutdown.unfinished),
                    shutdown.custody_released,
                )
                failure = DesktopStartupError(
                    "NamiSync desktop cleanup did not complete"
                )
        except Exception as error:
            _log_cleanup_failure("startup.service_cleanup_failed", error)
            failure = error
    if logging_configured:
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
    if lease is not None:
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


def _startup_failure_message(error: Exception) -> str:
    message = str(error).strip()
    return message or "NamiSync could not start the desktop host"
