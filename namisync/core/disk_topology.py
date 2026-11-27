"""Stateless native reads of which physical disks back one local volume.

Every call observes Windows afresh and keeps nothing: disk numbers and volume
names are scheduling evidence for the current attempt, never persisted. All
handles are opened with zero access (no data can be read or written) and only
``FILE_ANY_ACCESS`` control codes are issued.

Platform convention: the non-Windows fallback exists only to keep portable
development and tests usable. ``disk_facts`` returns no facts there, and
``volume_name`` raises ``OSError`` because no volume GUID name exists.
"""

from __future__ import annotations

import ctypes
import os
import re
import struct
from ctypes import wintypes
from dataclasses import dataclass

from .root_authority import current_volume_anchor


BUS_TYPE_UNKNOWN = 0
BUS_TYPE_USB = 7

_IS_WINDOWS = os.name == "nt"

_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_OPEN_EXISTING = 3
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
_IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS = 0x00560000
_STORAGE_DEVICE_PROPERTY = 0
_STORAGE_DEVICE_SEEK_PENALTY_PROPERTY = 7
_PROPERTY_STANDARD_QUERY = 0

_EXTENTS_BUFFER_BYTES = 4096
_DEVICE_DESCRIPTOR_BUFFER_BYTES = 1024
_SEEK_PENALTY_BUFFER_BYTES = 64
_VOLUME_NAME_BUFFER_CHARS = 64

# VOLUME_DISK_EXTENTS: DWORD count, 4 bytes padding, then 24-byte DISK_EXTENTs
# whose first DWORD is the disk number.
_EXTENTS_HEADER_BYTES = 8
_EXTENT_BYTES = 24
# STORAGE_DEVICE_DESCRIPTOR.BusType follows Version, Size, four one-byte
# fields and four offset DWORDs.
_BUS_TYPE_OFFSET = 28
# DEVICE_SEEK_PENALTY_DESCRIPTOR.IncursSeekPenalty follows Version and Size.
_SEEK_PENALTY_OFFSET = 8

_DOS_DEVICE_BUFFER_CHARS = 1024
# The object-namespace target of every local volume's drive letter;
# redirector, Mup and subst (``\??\``) targets differ.
_LOCAL_VOLUME_DEVICE = "\\Device\\HarddiskVolume"

_VOLUME_NAME = re.compile(
    r"\\\\\?\\Volume\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}\\?"
)


@dataclass(frozen=True, slots=True)
class DiskFact:
    """What Windows reported about one physical disk; ``None`` means unknown."""

    disk_number: int
    bus_type: int | None
    incurs_seek_penalty: bool | None


def counts_as_spinning(fact: DiskFact) -> bool:
    """Return whether scheduling must treat the disk as a spinning disk.

    Only a disk whose bus type is known (not ``BusTypeUnknown``) and not USB,
    and which explicitly reports no seek penalty, counts as non-spinning.
    Unknown, unreadable and USB disks are spinning: a wrong guess costs only
    speed, never safety.
    """

    return not (
        fact.bus_type not in (None, BUS_TYPE_UNKNOWN, BUS_TYPE_USB)
        and fact.incurs_seek_penalty is False
    )


def volume_name(anchor: str) -> str:
    """Return the ``\\\\?\\Volume{GUID}\\`` name of an admitted root's volume.

    ``anchor`` is an admitted local root or its volume anchor. Before any call
    that can perform I/O, the root's own drive letter is resolved in the
    object namespace, which never touches a device or the network; only a
    local volume device proceeds. UNC, volume GUID and other device paths,
    mapped network and ``subst`` letters, and unassigned letters raise
    ``OSError`` without a further native call. Also raises ``OSError`` when
    Windows cannot name the volume or off Windows, and ``ValueError``
    (``PathValidationError``) when ``anchor`` is not a valid local root.
    """

    if not _IS_WINDOWS:
        raise OSError("native volume names exist only on Windows")
    dos_name = _dos_device_name(anchor)
    if dos_name is None:
        raise OSError("root is not on a drive letter")
    if not _query_dos_device(dos_name).startswith(_LOCAL_VOLUME_DEVICE):
        raise OSError("root is not on a local volume device", dos_name)
    mount_point = current_volume_anchor(anchor)
    if not mount_point.endswith("\\"):
        mount_point += "\\"
    return _volume_name_for_mount_point(mount_point)


def disk_facts(volume_name: str) -> tuple[DiskFact, ...]:
    """Read the physical disks behind one volume, ordered by disk number.

    Raises ``OSError`` when the volume's extents cannot be read completely
    (including a reply too large for the fixed buffer, or one naming no
    extent), and ``ValueError`` when ``volume_name`` is not a volume GUID
    name. A disk whose handle or property queries fail is still reported,
    with the unreadable fields unknown. Returns no facts off Windows.
    """

    if not _IS_WINDOWS:
        return ()
    if _VOLUME_NAME.fullmatch(volume_name) is None:
        raise ValueError("volume name is not a volume GUID name")

    volume = _open_zero_access(volume_name.rstrip("\\"))
    try:
        extents = _ioctl(
            volume,
            _IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
            None,
            _EXTENTS_BUFFER_BYTES,
        )
    finally:
        _close_handle(volume)
    return tuple(_read_disk(number) for number in _parse_extent_disks(extents))


def _dos_device_name(anchor: str) -> str | None:
    """Return the root's own ``X:`` drive name, read lexically.

    Root paths are drive-letter paths (``pathing`` rejects the volume GUID
    namespace), so anything else is not a local volume root here.
    """

    path = anchor.replace("/", "\\")
    if path.startswith("\\\\?\\"):
        path = path[4:]
    elif path.startswith("\\\\"):
        return None
    if len(path) >= 2 and path[1] == ":" and path[0].isascii() and path[0].isalpha():
        return path[0].upper() + ":"
    return None


def _read_disk(disk_number: int) -> DiskFact:
    try:
        disk = _open_zero_access(f"\\\\.\\PhysicalDrive{disk_number}")
    except OSError:
        return DiskFact(disk_number, None, None)
    try:
        return DiskFact(
            disk_number,
            _query_bus_type(disk),
            _query_seek_penalty(disk),
        )
    finally:
        _close_handle(disk)


def _query_bus_type(disk: int) -> int | None:
    try:
        reply = _ioctl(
            disk,
            _IOCTL_STORAGE_QUERY_PROPERTY,
            _property_query(_STORAGE_DEVICE_PROPERTY),
            _DEVICE_DESCRIPTOR_BUFFER_BYTES,
        )
    except OSError:
        return None
    if len(reply) < _BUS_TYPE_OFFSET + 4:
        return None
    return struct.unpack_from("<I", reply, _BUS_TYPE_OFFSET)[0]


def _query_seek_penalty(disk: int) -> bool | None:
    try:
        reply = _ioctl(
            disk,
            _IOCTL_STORAGE_QUERY_PROPERTY,
            _property_query(_STORAGE_DEVICE_SEEK_PENALTY_PROPERTY),
            _SEEK_PENALTY_BUFFER_BYTES,
        )
    except OSError:
        return None
    if len(reply) <= _SEEK_PENALTY_OFFSET:
        return None
    return bool(reply[_SEEK_PENALTY_OFFSET])


def _property_query(property_id: int) -> bytes:
    # STORAGE_PROPERTY_QUERY: PropertyId, QueryType, one padded parameter byte.
    return struct.pack("<II4s", property_id, _PROPERTY_STANDARD_QUERY, b"\0" * 4)


def _parse_extent_disks(reply: bytes) -> tuple[int, ...]:
    if len(reply) < _EXTENTS_HEADER_BYTES:
        raise OSError("volume disk extents reply is truncated")
    (count,) = struct.unpack_from("<I", reply)
    if count == 0:
        raise OSError("volume disk extents reply names no extent")
    if _EXTENTS_HEADER_BYTES + count * _EXTENT_BYTES > len(reply):
        raise OSError("volume disk extents reply is truncated")
    return tuple(
        sorted(
            {
                struct.unpack_from(
                    "<I", reply, _EXTENTS_HEADER_BYTES + index * _EXTENT_BYTES
                )[0]
                for index in range(count)
            }
        )
    )


class _Bindings:
    """Process-lifetime kernel32 bindings; no native state is cached."""

    def __init__(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.create_file = kernel32.CreateFileW
        self.create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        self.create_file.restype = wintypes.HANDLE
        self.close_handle = kernel32.CloseHandle
        self.close_handle.argtypes = [wintypes.HANDLE]
        self.close_handle.restype = wintypes.BOOL
        self.device_io_control = kernel32.DeviceIoControl
        self.device_io_control.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        self.device_io_control.restype = wintypes.BOOL
        self.get_volume_name = kernel32.GetVolumeNameForVolumeMountPointW
        self.get_volume_name.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
        ]
        self.get_volume_name.restype = wintypes.BOOL
        self.query_dos_device = kernel32.QueryDosDeviceW
        self.query_dos_device.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
        ]
        self.query_dos_device.restype = wintypes.DWORD


_WINDOWS = _Bindings() if os.name == "nt" else None


# The native seam: tests replace these three, the volume-name lookup and the
# object-namespace lookup.


def _query_dos_device(dos_name: str) -> str:
    """Return the first object-namespace target of one DOS device name."""

    assert _WINDOWS is not None
    target = ctypes.create_unicode_buffer(_DOS_DEVICE_BUFFER_CHARS)
    if not _WINDOWS.query_dos_device(dos_name, target, len(target)):
        raise OSError(ctypes.get_last_error(), "QueryDosDeviceW failed", dos_name)
    return target.value


def _volume_name_for_mount_point(mount_point: str) -> str:
    assert _WINDOWS is not None
    name = ctypes.create_unicode_buffer(_VOLUME_NAME_BUFFER_CHARS)
    if not _WINDOWS.get_volume_name(mount_point, name, len(name)):
        raise OSError(
            ctypes.get_last_error(),
            "GetVolumeNameForVolumeMountPointW failed",
            mount_point,
        )
    return name.value


def _open_zero_access(path: str) -> int:
    assert _WINDOWS is not None
    handle = _WINDOWS.create_file(
        path,
        0,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE,
        None,
        _OPEN_EXISTING,
        0,
        None,
    )
    if handle is None or handle == _INVALID_HANDLE_VALUE:
        raise OSError(ctypes.get_last_error(), "CreateFileW failed", path)
    return handle


def _close_handle(handle: int) -> None:
    assert _WINDOWS is not None
    _WINDOWS.close_handle(handle)


def _ioctl(
    handle: int, code: int, request: bytes | None, reply_bytes: int
) -> bytes:
    """Issue one control code; any failure, including more data, is OSError."""

    assert _WINDOWS is not None
    reply = ctypes.create_string_buffer(reply_bytes)
    returned = wintypes.DWORD()
    query = ctypes.create_string_buffer(request, len(request)) if request else None
    if not _WINDOWS.device_io_control(
        handle,
        code,
        query,
        len(request) if request else 0,
        reply,
        reply_bytes,
        ctypes.byref(returned),
        None,
    ):
        raise OSError(ctypes.get_last_error(), "DeviceIoControl failed")
    return reply.raw[: returned.value]
