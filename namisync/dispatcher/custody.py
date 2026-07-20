"""Deterministic generic resource custody providers."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterable
from threading import Condition, Lock
from time import monotonic
from typing import Protocol

from namisync.core.session import Canceled, ResourceId


class ResourceLease(Protocol):
    def release(self) -> None: ...


class ResourceLockProvider(Protocol):
    def acquire(
        self, resources: Iterable[ResourceId], canceled: Callable[[], bool]
    ) -> ResourceLease: ...


class _CallbackLease:
    def __init__(self, release: Callable[[], None]) -> None:
        self._release = release
        self._released = False
        self._lock = Lock()

    def release(self) -> None:
        with self._lock:
            if self._released:
                return
            self._released = True
        self._release()


_LOCAL_CONDITION = Condition()
_LOCAL_HELD: set[ResourceId] = set()


class InProcessResourceLockProvider:
    """Portable fallback; the scheduler still supplies FIFO admission."""

    def __init__(self, poll_interval: float = 0.05) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self._poll_interval = poll_interval

    def acquire(
        self, resources: Iterable[ResourceId], canceled: Callable[[], bool]
    ) -> ResourceLease:
        ordered = tuple(sorted(set(resources)))
        with _LOCAL_CONDITION:
            while any(resource in _LOCAL_HELD for resource in ordered):
                if canceled():
                    raise Canceled()
                _LOCAL_CONDITION.wait(self._poll_interval)
            if canceled():
                raise Canceled()
            _LOCAL_HELD.update(ordered)

        def release() -> None:
            with _LOCAL_CONDITION:
                _LOCAL_HELD.difference_update(ordered)
                _LOCAL_CONDITION.notify_all()

        return _CallbackLease(release)


class WindowsNamedMutexProvider:
    """Cross-process Windows mutex custody with abandoned-holder recovery."""

    _WAIT_OBJECT_0 = 0x00000000
    _WAIT_ABANDONED = 0x00000080
    _WAIT_TIMEOUT = 0x00000102
    _WAIT_FAILED = 0xFFFFFFFF

    def __init__(self, poll_interval: float = 0.05) -> None:
        if os.name != "nt":
            raise OSError("Windows named mutexes are available only on Windows")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self._poll_ms = max(1, int(poll_interval * 1000))

    @staticmethod
    def mutex_name(resource: ResourceId) -> str:
        material = f"{resource.namespace}\0{resource.key}".encode("utf-8")
        digest = hashlib.sha256(material).hexdigest()
        return rf"Global\NamiSync.Resource.{digest}"

    def acquire(
        self, resources: Iterable[ResourceId], canceled: Callable[[], bool]
    ) -> ResourceLease:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        create_mutex.restype = wintypes.HANDLE
        wait = kernel32.WaitForSingleObject
        wait.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        wait.restype = wintypes.DWORD
        release_mutex = kernel32.ReleaseMutex
        release_mutex.argtypes = (wintypes.HANDLE,)
        release_mutex.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL

        handles: list[int] = []
        try:
            for resource in sorted(set(resources)):
                if canceled():
                    raise Canceled()
                handle = create_mutex(None, False, self.mutex_name(resource))
                if not handle:
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    while True:
                        if canceled():
                            raise Canceled()
                        outcome = wait(handle, self._poll_ms)
                        if outcome in (self._WAIT_OBJECT_0, self._WAIT_ABANDONED):
                            handles.append(handle)
                            handle = None
                            break
                        if outcome == self._WAIT_TIMEOUT:
                            continue
                        if outcome == self._WAIT_FAILED:
                            raise ctypes.WinError(ctypes.get_last_error())
                        raise OSError(f"unexpected mutex wait result: {outcome}")
                finally:
                    if handle:
                        close_handle(handle)
        except BaseException:
            self._release_handles(handles, release_mutex, close_handle)
            raise

        return _CallbackLease(
            lambda: self._release_handles(handles, release_mutex, close_handle)
        )

    @staticmethod
    def _release_handles(handles, release_mutex, close_handle) -> None:
        first_error: OSError | None = None
        for handle in reversed(handles):
            if not release_mutex(handle) and first_error is None:
                import ctypes

                first_error = ctypes.WinError(ctypes.get_last_error())
            close_handle(handle)
        handles.clear()
        if first_error is not None:
            raise first_error


def default_lock_provider() -> ResourceLockProvider:
    if os.name == "nt":
        return WindowsNamedMutexProvider()
    return InProcessResourceLockProvider()
