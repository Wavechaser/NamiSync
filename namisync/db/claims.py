"""Cross-process maintenance claims held beside each database main file."""

from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import io
import msvcrt
import os
from pathlib import Path
from typing import Iterator

from namisync.core.pathing import to_extended_length_path

from .connections import validate_database_path
from .schema import DatabaseAdmissionError


CLAIM_SUFFIX = ".claim"
_LOCKFILE_FAIL_IMMEDIATELY = 0x1
_LOCKFILE_EXCLUSIVE_LOCK = 0x2
_ERROR_LOCK_VIOLATION = 33


class DatabaseClaimRefused(DatabaseAdmissionError):
    """A database claim was refused without waiting."""

    def __init__(self, message: str, path: Path) -> None:
        super().__init__(message)
        self.path = path


class DatabaseMaintenanceActive(DatabaseClaimRefused):
    """A writer was refused because maintenance holds the database exclusively."""


class DatabaseInUse(DatabaseClaimRefused):
    """Maintenance was refused because another claim on the database is held."""


class _Overlapped(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


_kernel32: ctypes.WinDLL | None = None


def _bindings() -> ctypes.WinDLL:
    global _kernel32
    if _kernel32 is None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.LockFileEx.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
            wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_Overlapped),
        ]
        kernel32.LockFileEx.restype = wintypes.BOOL
        kernel32.UnlockFileEx.argtypes = [
            wintypes.HANDLE, wintypes.DWORD,
            wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_Overlapped),
        ]
        kernel32.UnlockFileEx.restype = wintypes.BOOL
        _kernel32 = kernel32
    return _kernel32


def claim_path(main: str | Path) -> Path:
    """Return the lock file beside the resolved database main file.

    Resolution is the one database callers already apply, so every spelling of
    a main path that resolves alike shares one claim.
    """

    return Path(f"{validate_database_path(main)}{CLAIM_SUFFIX}")


class DatabaseClaim:
    """One held claim; releasing it unlocks and closes its own handle."""

    def __init__(self, path: Path, exclusive: bool, file: io.FileIO) -> None:
        self.path = path
        self.exclusive = exclusive
        self._file: io.FileIO | None = file

    @property
    def held(self) -> bool:
        return self._file is not None

    def release(self) -> None:
        file, self._file = self._file, None
        if file is None:
            return
        try:
            if not _bindings().UnlockFileEx(
                msvcrt.get_osfhandle(file.fileno()), 0, 1, 0, ctypes.byref(_Overlapped()),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            # Closing the handle drops the lock even if the explicit unlock failed.
            file.close()

    def __enter__(self) -> DatabaseClaim:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()


def acquire_database_claim(main: str | Path, *, exclusive: bool) -> DatabaseClaim:
    """Take a shared or exclusive claim without waiting, or refuse with a typed error."""

    main_path = validate_database_path(main)
    path = claim_path(main_path)
    # Python's own open is visible to audit hooks and, under PEP 446, already
    # non-inheritable (O_NOINHERIT only states it); the lock lives on this handle.
    descriptor = os.open(
        to_extended_length_path(str(path)),
        os.O_RDWR | os.O_CREAT | os.O_BINARY | os.O_NOINHERIT,
        0o666,
    )
    try:
        file = os.fdopen(descriptor, "r+b", buffering=0)
    except BaseException:
        os.close(descriptor)
        raise
    try:
        flags = _LOCKFILE_FAIL_IMMEDIATELY | (_LOCKFILE_EXCLUSIVE_LOCK if exclusive else 0)
        if not _bindings().LockFileEx(
            msvcrt.get_osfhandle(file.fileno()), flags, 0, 1, 0, ctypes.byref(_Overlapped()),
        ):
            error = ctypes.get_last_error()
            if error != _ERROR_LOCK_VIOLATION:
                raise ctypes.WinError(error)
            if exclusive:
                raise DatabaseInUse(
                    f"Database {main_path} is in use by NamiSync work in this or "
                    "another process. Wait for running tasks to finish, close other "
                    "NamiSync windows and commands, then retry.",
                    main_path,
                )
            raise DatabaseMaintenanceActive(
                f"Database maintenance is in progress on {main_path}. New work is "
                "refused, not queued; wait for maintenance to finish, then start "
                "this again.",
                main_path,
            )
    except BaseException:
        file.close()
        raise
    return DatabaseClaim(path, exclusive, file)


@dataclass(frozen=True, slots=True)
class MaintenanceClaims:
    """Both exclusive claims of a pair, held for one maintenance session."""

    ledger: DatabaseClaim
    history: DatabaseClaim


@contextmanager
def hold_maintenance_claims(
    ledger: str | Path, history: str | Path,
) -> Iterator[MaintenanceClaims]:
    """Hold both databases of a pair exclusively, ledger first, or refuse."""

    ledger_claim = acquire_database_claim(ledger, exclusive=True)
    try:
        history_claim = acquire_database_claim(history, exclusive=True)
    except BaseException:
        ledger_claim.release()
        raise
    try:
        yield MaintenanceClaims(ledger_claim, history_claim)
    finally:
        try:
            history_claim.release()
        finally:
            ledger_claim.release()
