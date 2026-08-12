"""Desktop host composition and native lifetime primitives."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from threading import Lock
from typing import Protocol


_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9


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
