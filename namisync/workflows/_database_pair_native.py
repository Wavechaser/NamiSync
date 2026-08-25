"""Handle-bound Windows ownership for database-pair reservations."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Protocol

from namisync.core.file_identity import file_identity_from_windows_handle
from namisync.core.pathing import to_extended_length_path


_DELETE = 0x00010000
_FILE_READ_ATTRIBUTES = 0x00000080
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_SHARE_DELETE = 0x00000004
_CREATE_NEW = 1
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_STANDARD_INFO_CLASS = 1
_FILE_DISPOSITION_INFO_EX_CLASS = 21
_FILE_DISPOSITION_FLAG_DELETE = 0x00000001
_FILE_DISPOSITION_FLAG_POSIX_SEMANTICS = 0x00000002
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


ArtifactIdentity = tuple[int, int]


class ArtifactNative(Protocol):
    """Minimal native surface needed by an owned-artifact lease."""

    def reserve(self, path: Path) -> tuple[int, ArtifactIdentity]: ...

    def path_identity(self, path: Path) -> ArtifactIdentity: ...

    def delete(self, handle: int) -> None: ...

    def close(self, handle: int) -> None: ...


@dataclass(slots=True)
class OwnedArtifactLease:
    """A reservation whose cleanup authority stays bound to its open handle."""

    path: Path
    identity: ArtifactIdentity
    _handle: int | None
    _native: ArtifactNative
    _failures: tuple[OSError, ...] = ()
    _retracted: bool = False

    @classmethod
    def reserve(
        cls,
        path: Path,
        native: ArtifactNative,
    ) -> OwnedArtifactLease:
        handle, identity = native.reserve(path)
        return cls(path, identity, handle, native)

    def matches_path(self) -> bool:
        """Return whether the reserved object is still published at its path."""

        try:
            return self._native.path_identity(self.path) == self.identity
        except OSError:
            return False

    def release(self) -> tuple[OSError, ...]:
        """Close this lease without deleting its reserved object."""

        handle = self._handle
        if handle is None:
            return self._failures
        try:
            self._native.close(handle)
        except OSError as error:
            self._failures = (error,)
        else:
            self._handle = None
            self._failures = ()
        return self._failures

    def retract(self) -> tuple[bool, tuple[OSError, ...]]:
        """Delete the reserved object itself, never the current pathname target."""

        handle = self._handle
        if handle is None:
            return self._retracted, self._failures
        failures: list[OSError] = []
        if not self._retracted:
            try:
                self._native.delete(handle)
                self._retracted = True
            except OSError as error:
                failures.append(error)
                try:
                    self._native.close(handle)
                except OSError as close_error:
                    failures.append(close_error)
                else:
                    self._handle = None
            except BaseException as error:
                try:
                    self._native.close(handle)
                except BaseException:
                    error.add_note(
                        "database reservation-handle release was incomplete"
                    )
                else:
                    self._handle = None
                raise
        if self._retracted:
            try:
                self._native.close(handle)
            except OSError as error:
                failures.append(error)
            else:
                self._handle = None
        self._failures = tuple(failures)
        return self._retracted, self._failures


class WindowsArtifactNative:
    """Win32 implementation for exact-object reservation and deletion."""

    def __init__(self) -> None:
        self._kernel32: ctypes.WinDLL | None = None

    def reserve(self, path: Path) -> tuple[int, ArtifactIdentity]:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._open(
            path,
            # sqlite3's Windows VFS does not grant FILE_SHARE_DELETE to every
            # reader.  Keep this long-lived lease read-only, then acquire the
            # short-lived DELETE handle only after SQLite closes its handles.
            desired_access=_FILE_READ_ATTRIBUTES,
            creation_disposition=_CREATE_NEW,
        )
        try:
            return handle, self._identity(handle)
        except BaseException as error:
            try:
                self.close(handle)
            except BaseException:
                error.add_note("database reservation-handle release was incomplete")
            raise

    def path_identity(self, path: Path) -> ArtifactIdentity:
        handle = self._open(
            path,
            desired_access=_FILE_READ_ATTRIBUTES,
            creation_disposition=_OPEN_EXISTING,
        )
        try:
            identity = self._identity(handle)
        except BaseException as error:
            try:
                self.close(handle)
            except BaseException:
                error.add_note("database identity-handle release was incomplete")
            raise
        else:
            self.close(handle)
            return identity

    def delete(self, handle: int) -> None:
        delete_handle = self._bindings().ReOpenFile(
            handle,
            _DELETE | _FILE_READ_ATTRIBUTES,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            0,
        )
        if delete_handle == _INVALID_HANDLE_VALUE:
            error = ctypes.get_last_error()
            if error == 5 and self._delete_pending(handle):
                return
            _raise_last_error(error=error)
        try:
            disposition = _FileDispositionInfoEx(
                _FILE_DISPOSITION_FLAG_DELETE
                | _FILE_DISPOSITION_FLAG_POSIX_SEMANTICS
            )
            kernel32 = self._bindings()
            if not kernel32.SetFileInformationByHandle(
                delete_handle,
                _FILE_DISPOSITION_INFO_EX_CLASS,
                ctypes.byref(disposition),
                ctypes.sizeof(disposition),
            ):
                _raise_last_error()
        except BaseException as error:
            try:
                self.close(delete_handle)
            except BaseException:
                error.add_note("database delete-handle release was incomplete")
            raise
        else:
            self.close(delete_handle)

    def _delete_pending(self, handle: int) -> bool:
        information = _FileStandardInformation()
        if not self._bindings().GetFileInformationByHandleEx(
            handle,
            _FILE_STANDARD_INFO_CLASS,
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            _raise_last_error()
        return bool(information.DeletePending)

    def close(self, handle: int) -> None:
        if not self._bindings().CloseHandle(handle):
            _raise_last_error()

    def _open(
        self,
        path: Path,
        *,
        desired_access: int,
        creation_disposition: int,
    ) -> int:
        handle = self._bindings().CreateFileW(
            to_extended_length_path(str(path)),
            desired_access,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            None,
            creation_disposition,
            _FILE_ATTRIBUTE_NORMAL | _FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        if handle == _INVALID_HANDLE_VALUE:
            _raise_last_error(path)
        return handle

    def _identity(self, handle: int) -> ArtifactIdentity:
        bindings = self._bindings()
        identity = file_identity_from_windows_handle(
            handle,
            bindings.GetFileInformationByHandleEx,
        )
        return int(identity.volume_serial, 16), identity.file_index

    def _bindings(self) -> ctypes.WinDLL:
        if os.name != "nt":
            raise OSError("database publication requires Windows handle semantics")
        if self._kernel32 is None:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateFileW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.LPVOID,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HANDLE,
            ]
            kernel32.CreateFileW.restype = wintypes.HANDLE
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            kernel32.GetFileInformationByHandleEx.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                wintypes.LPVOID,
                wintypes.DWORD,
            ]
            kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL
            kernel32.ReOpenFile.argtypes = [
                wintypes.HANDLE,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
            ]
            kernel32.ReOpenFile.restype = wintypes.HANDLE
            kernel32.SetFileInformationByHandle.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                wintypes.LPVOID,
                wintypes.DWORD,
            ]
            kernel32.SetFileInformationByHandle.restype = wintypes.BOOL
            self._kernel32 = kernel32
        return self._kernel32


class _FileStandardInformation(ctypes.Structure):
    _fields_ = [
        ("AllocationSize", ctypes.c_longlong),
        ("EndOfFile", ctypes.c_longlong),
        ("NumberOfLinks", wintypes.DWORD),
        ("DeletePending", wintypes.BOOLEAN),
        ("Directory", wintypes.BOOLEAN),
    ]


class _FileDispositionInfoEx(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD)]


def _raise_last_error(
    path: Path | None = None,
    *,
    error: int | None = None,
) -> None:
    if error is None:
        error = ctypes.get_last_error()
    raise OSError(
        error,
        os.strerror(error),
        None if path is None else str(path),
    )
