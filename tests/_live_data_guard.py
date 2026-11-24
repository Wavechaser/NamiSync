"""Suite guard (M2-A1): no test may change the live production data root.

The root comes from the Windows known folder, never from ``LOCALAPPDATA``,
which tests monkeypatch. One audit hook, installed for the whole pytest
session, refuses any operation that could create or change an entry beneath
``<LocalAppData>\\NamiSync``. Reads, stats and listings stay legal, and
``NamiSync-Development`` never matches. Audit hooks cannot be removed, and
native calls made through ``ctypes`` are not audited.
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote

import pytest


class LiveDataGuardError(BaseException):
    """A test reached the live data root.

    A ``BaseException`` so product ``except Exception`` handlers cannot turn a
    refused operation into a quiet fallback.
    """


_WRITE_FLAGS = 0
for _name in (
    "O_WRONLY",
    "O_RDWR",
    "O_APPEND",
    "O_CREAT",
    "O_TRUNC",
    "O_EXCL",
    "O_TEMPORARY",  # deletes on close
):
    _WRITE_FLAGS |= getattr(os, _name, 0)
# _winapi.CreateFile desired access: GENERIC_ALL/WRITE, MAXIMUM_ALLOWED, DELETE,
# WRITE_DAC/OWNER, FILE_WRITE_DATA/APPEND_DATA/EA/DELETE_CHILD/ATTRIBUTES;
# dispositions that create or truncate; FILE_FLAG_DELETE_ON_CLOSE.
_WINAPI_WRITE_ACCESS = (
    0x10000000 | 0x40000000 | 0x02000000 | 0x00010000 | 0x00040000 | 0x00080000
    | 0x0002 | 0x0004 | 0x0010 | 0x0040 | 0x0100
)
_WINAPI_CREATING_DISPOSITIONS = frozenset((1, 2, 4, 5))
_FILE_FLAG_DELETE_ON_CLOSE = 0x04000000

# Audit event -> indexes of the arguments naming entries the operation creates,
# changes or removes. ``open`` and ``sqlite3.connect`` have their own readers.
_MUTATING_EVENTS: dict[str, tuple[int, ...]] = {
    "os.mkdir": (0,),
    "os.rmdir": (0,),
    "os.remove": (0,),
    "os.rename": (0, 1),
    "os.chmod": (0,),
    "os.chown": (0,),
    "os.lchown": (0,),
    "os.utime": (0,),
    "os.truncate": (0,),
    "os.symlink": (1,),
    "os.link": (0, 1),
    "shutil.rmtree": (0,),
    "shutil.copyfile": (1,),
    "shutil.copymode": (1,),
    "shutil.copystat": (1,),
    "shutil.copytree": (1,),
    "shutil.move": (0, 1),
    "shutil.make_archive": (0,),
    "shutil.unpack_archive": (1,),
    "tempfile.mkdtemp": (0,),
    "tempfile.mkstemp": (0,),
    "_winapi.CreateJunction": (1,),
}
_WATCHED = frozenset(
    (*_MUTATING_EVENTS, "open", "sqlite3.connect", "_winapi.CreateFile")
)

_installed_root: Path | None = None
# Every refusal, so a product handler that swallows the exception still fails the
# owning test (see ``fail_on_unacknowledged_refusals``).
_refusals: list[tuple[str, str, int]] = []


def known_live_root() -> Path:
    """Return ``<LocalAppData>\\NamiSync`` from the Windows known folder."""

    class _Guid(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    # FOLDERID_LocalAppData {F1B32785-6FBA-4FCF-9D55-7B8E7F157091}
    folder_id = _Guid(
        0xF1B32785,
        0x6FBA,
        0x4FCF,
        (ctypes.c_ubyte * 8)(0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91),
    )
    shell32 = ctypes.WinDLL("shell32")
    ole32 = ctypes.WinDLL("ole32")
    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(_Guid),
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    pointer = ctypes.c_void_p()
    status = shell32.SHGetKnownFolderPath(
        ctypes.byref(folder_id), 0, None, ctypes.byref(pointer)
    )
    try:
        if status != 0 or not pointer.value:
            raise RuntimeError(
                f"M2-A1 live-data guard cannot resolve LocalAppData (HRESULT {status})"
            )
        local_app_data = ctypes.wstring_at(pointer.value)
    finally:
        ole32.CoTaskMemFree(pointer)
    return Path(local_app_data) / "NamiSync"


def path_components(value: object) -> tuple[str, ...] | None:
    """Return normalized absolute components, or ``None`` for a non-path."""

    if isinstance(value, (str, bytes, os.PathLike)):
        text = os.fsdecode(value)
    else:
        return None
    for prefix in ("\\\\?\\", "\\\\.\\", "//?/", "//./"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    if not text:
        return None
    absolute = os.path.normcase(os.path.abspath(text))
    return tuple(part for part in absolute.split("\\") if part)


def _under(components: tuple[str, ...] | None, root: tuple[str, ...]) -> bool:
    return components is not None and components[: len(root)] == root


def _sqlite_target(database: object) -> object:
    """Return the file named by a ``sqlite3.connect`` argument, if any."""

    if not isinstance(database, (str, bytes, os.PathLike)):
        return None
    text = os.fsdecode(database)
    if text[:5].lower() == "file:":
        text = text[5:].partition("?")[0].partition("#")[0]
        if text.startswith("//"):
            authority, slash, rest = text[2:].partition("/")
            if authority.lower() in ("", "localhost"):
                text = slash + rest
            else:  # file://host/share/x names a UNC path
                text = "//" + authority + slash + rest
        text = unquote(text)
        if text[:1] == "/" and text[2:3] == ":":
            text = text[1:]
    if text in ("", ":memory:"):
        return None
    return text


def _opens_for_write(args: tuple) -> bool:
    mode = args[1] if len(args) > 1 else None
    flags = args[2] if len(args) > 2 else None
    if isinstance(mode, str) and any(letter in mode for letter in "wax+"):
        return True
    return isinstance(flags, int) and bool(flags & _WRITE_FLAGS)


def _refused_target(event: str, args: tuple, root: tuple[str, ...]) -> object:
    """Return the first argument that makes ``event`` touch the root."""

    if event == "_winapi.CreateFile":
        access = args[1] if len(args) > 1 else None
        disposition = args[3] if len(args) > 3 else None
        flags = args[4] if len(args) > 4 else None
        if (
            (isinstance(access, int) and access & _WINAPI_WRITE_ACCESS)
            or disposition in _WINAPI_CREATING_DISPOSITIONS
            or (isinstance(flags, int) and flags & _FILE_FLAG_DELETE_ON_CLOSE)
        ):
            return args[0] if _under(path_components(args[0]), root) else None
        return None
    if event == "open":
        if args and _opens_for_write(args) and _under(path_components(args[0]), root):
            return args[0]
        return None
    if event == "sqlite3.connect":
        target = _sqlite_target(args[0]) if args else None
        if target is not None and _under(path_components(target), root):
            return args[0]
        return None
    for index in _MUTATING_EVENTS[event]:
        if index < len(args) and _under(path_components(args[index]), root):
            return args[index]
    return None


def _check(
    event: str, args: tuple, root: tuple[str, ...], live_root: Path
) -> None:
    try:
        offender = _refused_target(event, args, root)
    except Exception:  # odd argument types must never break unrelated work
        return
    if offender is not None:
        path = os.fsdecode(offender)
        _refusals.append((event, path, threading.get_ident()))
        raise LiveDataGuardError(
            f"M2-A1 live-data guard refused {event} on {path}: it is under "
            f"the live production data root {live_root}. Source-tree runs use "
            "%LOCALAPPDATA%\\NamiSync-Development; tests must use a tmp_path root."
        )


def check_event(event: str, args: tuple, live_root: Path) -> None:
    """Raise ``LiveDataGuardError`` if ``event`` would change ``live_root``."""

    if event not in _WATCHED:
        return
    root = path_components(live_root)
    if root is not None:
        _check(event, args, root, live_root)


def install(live_root: Path | None = None) -> Path:
    """Install the session audit hook once and return the guarded root."""

    global _installed_root
    if _installed_root is not None:
        return _installed_root
    root = known_live_root() if live_root is None else live_root
    root_components = path_components(root)
    if root_components is None:
        raise RuntimeError("M2-A1 live-data guard needs an absolute live root")

    def hook(event: str, args: tuple) -> None:
        if event in _WATCHED:
            _check(event, args, root_components, root)

    sys.addaudithook(hook)
    _installed_root = root
    return root


def installed_root() -> Path | None:
    """Return the guarded root, or ``None`` before installation."""

    return _installed_root


@contextmanager
def expected_refusals(*expected: tuple[str, object]):
    """Acknowledge exactly the named ``(event, path)`` refusals as intended.

    Only matching entries recorded on the calling thread inside the block are
    acknowledged; any other refusal stays recorded and fails the test. When the
    block completes normally, every expected refusal must have been recorded.
    Only ``tests/test_live_data_guard.py`` may use this.
    """

    if not expected:
        raise ValueError("expected_refusals needs at least one (event, path)")
    start = len(_refusals)
    thread = threading.get_ident()
    pending = [(event, path_components(path)) for event, path in expected]

    def acknowledge() -> list[tuple[str, object]]:
        kept = []
        for entry in _refusals[start:]:
            event, path, owner = entry
            key = (event, path_components(path))
            if owner == thread and key in pending:
                pending.remove(key)
            else:
                kept.append(entry)
        _refusals[start:] = kept
        return pending

    try:
        yield
    except BaseException:
        acknowledge()
        raise
    missing = acknowledge()
    if missing:
        raise AssertionError(f"expected live-data refusals did not occur: {missing}")


def take_refusals() -> list[tuple[str, str]]:
    """Drain and return every recorded ``(event, path)`` refusal."""

    refused = [(event, path) for event, path, _owner in _refusals]
    del _refusals[:]
    return refused


def fail_on_unacknowledged_refusals(*, setup: bool = False) -> None:
    """Fail the running test if a refusal was raised and not acknowledged.

    Called from the autouse fixture, so a refusal swallowed by a product
    ``except BaseException`` handler or finalizer still fails the test. At setup
    it reports refusals recorded outside any test.
    """

    refused = take_refusals()
    if not refused:
        return
    listing = "; ".join(f"{event} {path}" for event, path in refused)
    if setup:
        message = f"M2-A1 live-data guard: refusal recorded outside this test: {listing}"
    else:
        message = (
            "M2-A1 live-data guard refused operations during this test, even if "
            f"the code swallowed the exception: {listing}"
        )
    pytest.fail(message, pytrace=False)
