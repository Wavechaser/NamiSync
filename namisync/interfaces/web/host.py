"""Desktop host composition and native lifetime primitives."""

from __future__ import annotations

import ctypes
import importlib
import importlib.resources
import logging
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Callable, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from .paths import AppPaths


_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9
_EXIT_SUCCESS = 0
_EXIT_STARTUP = 1


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


def run_desktop(
    paths: AppPaths,
    identity: DesktopInstanceIdentity,
    *,
    startup_error: Callable[[str], None],
    instance_native: _InstanceNative | None = None,
) -> int:
    """Run the secured headed composition and retain every native owner."""

    lease: DesktopInstanceLease | None = None
    service = None
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
            _packaged_index_path(),
            js_api=dispatcher,
        )
        if window is None:
            raise DesktopStartupError("NamiSync could not create its desktop window")

        state = _StartupState()

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
            state.destroy_once(window)

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
        cleanup_failure = _finalize_primary(
            service,
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

    return BridgeDispatcher(document=document, handlers={})


def _packaged_index_path() -> str:
    package = importlib.resources.files("namisync.interfaces.web")
    return str(package / "assets" / "index.html")


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


def _finalize_primary(
    service: object | None,
    *,
    logging_configured: bool,
    log_path: Path | None,
    lease: DesktopInstanceLease | None,
) -> Exception | None:
    failure: Exception | None = None
    if service is not None:
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
