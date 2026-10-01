"""Canonical Windows ``FILE_ID_128`` identity adaptation."""

from __future__ import annotations

from collections.abc import Callable
import ctypes
from ctypes import wintypes

from .models import FileIdentity
from .scalars import MAX_FILE_INDEX_128, file_index_128_to_text


FILE_ID_INFO_CLASS = 18
_SUPPORTED_IDENTITY_FILESYSTEMS = frozenset({"NTFS", "REFS"})


class _FileId128(ctypes.Structure):
    _fields_ = [("identifier", ctypes.c_ubyte * 16)]


class _FileIdInfo(ctypes.Structure):
    _fields_ = [
        ("volume_serial_number", ctypes.c_ulonglong),
        ("file_id", _FileId128),
    ]


GetFileInformationByHandleEx = Callable[[int, int, object, int], object]


def supports_stable_file_identity(fs_type: str) -> bool:
    """Identify filesystems on which identity-query failures must fail closed."""

    return fs_type.upper() in _SUPPORTED_IDENTITY_FILESYSTEMS


def file_index_128_from_bytes(value: bytes | bytearray | memoryview) -> int:
    """Canonicalize Windows' little-endian 16-byte file identifier."""

    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError("FILE_ID_128 must be a byte buffer")
    raw = bytes(value)
    if len(raw) != 16:
        raise ValueError("FILE_ID_128 must contain exactly 16 bytes")
    return int.from_bytes(raw, byteorder="little", signed=False)


def file_index_128_text(value: int) -> str:
    """Return the canonical persistence/wire spelling of a file index."""

    return file_index_128_to_text(value)


def file_identity_from_stat(
    volume_serial: str,
    fs_type: str,
    st_ino: object,
) -> FileIdentity | None:
    """Adapt CPython's complete Windows ``st_ino`` on witnessed filesystems."""

    if not supports_stable_file_identity(fs_type):
        return None
    if type(st_ino) is not int or not 0 <= st_ino <= MAX_FILE_INDEX_128:
        return None
    return FileIdentity(volume_serial, st_ino)


def file_identity_from_windows_handle(
    handle: int,
    get_file_information_ex: GetFileInformationByHandleEx,
) -> FileIdentity | None:
    """Read ``FileIdInfo``, allowing absence only on other filesystems."""

    info = _FileIdInfo()
    succeeded = get_file_information_ex(
        handle,
        FILE_ID_INFO_CLASS,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not succeeded:
        error = ctypes.WinError(ctypes.get_last_error())
        if not supports_stable_file_identity(_filesystem_from_windows_handle(handle)):
            return None
        raise error
    return file_identity_from_windows_parts(
        info.volume_serial_number,
        bytes(info.file_id.identifier),
    )


def _filesystem_from_windows_handle(handle: int) -> str:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_volume_information = kernel32.GetVolumeInformationByHandleW
    get_volume_information.argtypes = [
        wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR, wintypes.DWORD,
    ]
    get_volume_information.restype = wintypes.BOOL
    filesystem = ctypes.create_unicode_buffer(261)
    if not get_volume_information(
        handle, None, 0, None, None, None, filesystem, len(filesystem),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return filesystem.value


def file_identity_from_windows_parts(
    volume_serial_number: int,
    identifier: bytes,
) -> FileIdentity:
    """Canonicalize an already-observed complete Windows identity."""

    if type(volume_serial_number) is not int or not 0 <= volume_serial_number < 1 << 64:
        raise ValueError("volume serial number is outside the unsigned-64 domain")
    return FileIdentity(
        f"{volume_serial_number & 0xFFFFFFFF:08X}",
        file_index_128_from_bytes(identifier),
    )
