"""Local artifact paths owned by the headed NamiSync application."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Mapping, Protocol

_LOCAL_DRIVE = re.compile(r"(?:\\\\\?\\)?[A-Za-z]:", re.ASCII)
_LOCAL_DRIVE_TYPES = frozenset({2, 3, 5, 6})
_GENERIC_READ = 0x80000000
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class AppPathError(ValueError):
    """The GUI application root is unavailable or is not a local path."""


class _PathLeaseNative(Protocol):
    def open(self, path: Path, *, directory: bool) -> object: ...

    def close(self, handle: object) -> None: ...


class AppPathLease:
    """Hold app directories and databases against pathname replacement."""

    def __init__(
        self,
        paths: AppPaths,
        native: _PathLeaseNative,
        handles: dict[Path, object],
    ) -> None:
        self._paths = paths
        self._native = native
        self._handles = handles
        self._lock = Lock()

    def bind_databases(self) -> None:
        """Pin both published database files before the runtime admits work."""

        opened: dict[Path, object] = {}
        try:
            for path in (self._paths.ledger, self._paths.history):
                with self._lock:
                    if path in self._handles:
                        continue
                opened[path] = self._native.open(path, directory=False)
        except BaseException:
            for handle in reversed(tuple(opened.values())):
                try:
                    self._native.close(handle)
                except OSError:
                    pass
            raise
        with self._lock:
            self._handles.update(opened)

    def close(self) -> None:
        """Release every guard, retaining failed handles for a safe retry."""

        failures: list[OSError] = []
        with self._lock:
            entries = tuple(reversed(tuple(self._handles.items())))
            for path, handle in entries:
                try:
                    self._native.close(handle)
                except OSError as error:
                    failures.append(error)
                else:
                    self._handles.pop(path, None)
        if failures:
            raise failures[0]


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Every local artifact used by one GUI composition."""

    root: Path
    ledger: Path
    history: Path
    settings: Path
    ui_state: Path
    logs: Path
    log_file: Path
    webview2: Path

    @classmethod
    def production(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> AppPaths:
        values = os.environ if environment is None else environment
        local_app_data = values.get("LOCALAPPDATA")
        if not local_app_data:
            raise AppPathError("LOCALAPPDATA is unavailable")
        return cls.from_root(Path(local_app_data) / "NamiSync")

    @classmethod
    def from_root(cls, root: str | Path) -> AppPaths:
        resolved = _resolve_local_path(root)
        logs = resolved / "logs"
        return cls(
            root=resolved,
            ledger=resolved / "ledger.db",
            history=resolved / "history.db",
            settings=resolved / "settings.json",
            ui_state=resolved / "ui-state.json",
            logs=logs,
            log_file=logs / "namisync.log",
            webview2=resolved / "webview2",
        )

    def ensure_directories(self) -> None:
        """Create the root and directory artifacts; safe to call repeatedly."""

        self.root.mkdir(parents=True, exist_ok=True)
        self._require_physical_containment()
        self.logs.mkdir(exist_ok=True)
        self.webview2.mkdir(exist_ok=True)
        self._require_physical_containment()

    def acquire_lease(
        self,
        *,
        native: _PathLeaseNative | None = None,
    ) -> AppPathLease:
        """Pin the application directory chain for the headed process lifetime."""

        self.ensure_directories()
        adapter = WindowsPathLeaseNative() if native is None else native
        handles: dict[Path, object] = {}
        try:
            for path in (self.root, self.logs, self.webview2):
                handles[path] = adapter.open(path, directory=True)
        except BaseException:
            for handle in reversed(tuple(handles.values())):
                try:
                    adapter.close(handle)
                except OSError:
                    pass
            raise
        return AppPathLease(self, adapter, handles)

    def _require_physical_containment(self) -> None:
        root = self.root.resolve(strict=True)
        for artifact in (
            self.ledger,
            self.history,
            self.settings,
            self.ui_state,
            self.logs,
            self.log_file,
            self.webview2,
        ):
            if not (
                artifact.exists()
                or artifact.is_symlink()
                or artifact.is_junction()
            ):
                continue
            resolved = artifact.resolve(strict=False)
            if not resolved.is_relative_to(root):
                raise AppPathError(
                    "GUI artifact path resolves outside the application data root"
                )


def resolve_local_index_path(value: str | Path) -> Path:
    """Resolve one construction-injected headed-test page on a local drive."""

    resolved = _resolve_local_path(value)
    if not resolved.is_file():
        raise AppPathError("desktop index path must resolve to a local file")
    return resolved


def _resolve_local_path(value: str | Path) -> Path:
    path = Path(value)
    _require_absolute_local(path)
    try:
        resolved = path.resolve(strict=False)
    except OSError as error:
        raise AppPathError("application data root could not be resolved") from error
    _require_absolute_local(resolved)
    return resolved


def _require_absolute_local(path: Path) -> None:
    if (
        not path.is_absolute()
        or _LOCAL_DRIVE.fullmatch(path.drive) is None
        or _drive_type(path) not in _LOCAL_DRIVE_TYPES
    ):
        raise AppPathError("application data root must be an absolute local path")


def _drive_type(path: Path) -> int:
    root = f"{path.drive}\\"
    return int(ctypes.windll.kernel32.GetDriveTypeW(root))


class WindowsPathLeaseNative:
    """Open exact local artifacts while denying delete/rename sharing."""

    def __init__(self) -> None:
        self._kernel32: ctypes.WinDLL | None = None

    def open(self, path: Path, *, directory: bool) -> object:
        flags = _FILE_FLAG_OPEN_REPARSE_POINT
        if directory:
            flags |= _FILE_FLAG_BACKUP_SEMANTICS
        handle = self._bindings().CreateFileW(
            _extended_length_path(path),
            _GENERIC_READ,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE,
            None,
            _OPEN_EXISTING,
            flags,
            None,
        )
        if handle == _INVALID_HANDLE_VALUE:
            _raise_last_error(path)
        information = _ByHandleFileInformation()
        try:
            if not self._bindings().GetFileInformationByHandle(
                handle,
                ctypes.byref(information),
            ):
                _raise_last_error(path)
            if information.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                raise AppPathError("GUI artifact path must not be a reparse point")
            observed_directory = bool(
                information.dwFileAttributes & _FILE_ATTRIBUTE_DIRECTORY
            )
            if observed_directory is not directory:
                raise AppPathError("GUI artifact path has the wrong filesystem type")
        except BaseException:
            self.close(handle)
            raise
        return handle

    def close(self, handle: object) -> None:
        if not self._bindings().CloseHandle(handle):
            _raise_last_error()

    def _bindings(self) -> ctypes.WinDLL:
        if os.name != "nt":
            raise OSError("GUI path leases require Windows handle semantics")
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
            kernel32.GetFileInformationByHandle.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(_ByHandleFileInformation),
            ]
            kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
            self._kernel32 = kernel32
        return self._kernel32


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


def _raise_last_error(path: Path | None = None) -> None:
    error = ctypes.get_last_error()
    raise OSError(
        error,
        os.strerror(error),
        None if path is None else str(path),
    )


def _extended_length_path(path: Path) -> str:
    """Return the already-validated local path in Win32 long-path form."""

    value = str(path)
    if value.startswith("\\\\?\\"):
        return value
    return "\\\\?\\" + value
