"""Windows cache-honest verifier reader and native root adaptation."""

from __future__ import annotations

import ctypes
import ntpath
import os
from ctypes import wintypes
from contextlib import contextmanager
from pathlib import Path, PureWindowsPath
from typing import Iterator

from namisync.core.integrity import (
    ReadStrategy,
    UnsupportedVerification,
)
from namisync.core.models import EntryKind, FileIdentity, FileStat, MetadataSnapshot
from namisync.core.pathing import (
    lexical_absolute_path,
    logical_error_text,
    to_extended_length_path,
    validate_relative_path,
)
from namisync.core.root_authority import (
    RootAuthority,
    RootAuthorityError,
    RootAuthorityIssue,
    admit_root_chain,
    is_placeholder_stat,
    is_reparse_stat,
)


_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_GENERIC_READ = 0x80000000
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_SHARE_DELETE = 0x00000004
_OPEN_EXISTING = 3
_FILE_FLAG_NO_BUFFERING = 0x20000000
_FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_MEM_COMMIT = 0x00001000
_MEM_RESERVE = 0x00002000
_MEM_RELEASE = 0x00008000
_PAGE_READWRITE = 0x04
_ERROR_FILE_NOT_FOUND = 2
_ERROR_PATH_NOT_FOUND = 3
_ERROR_ACCESS_DENIED = 5
_ERROR_INVALID_PARAMETER = 87
_WINDOWS_EPOCH_TICKS = 116_444_736_000_000_000


class WindowsUnbufferedReader:
    """Read one Windows file through ``FILE_FLAG_NO_BUFFERING``.

    There is deliberately no buffered fallback.  A filesystem, subject, or
    alignment condition that cannot honor the declared strategy produces
    ``UnsupportedVerification`` and can never be rendered as verified.
    """

    def __init__(self, root_authority: RootAuthority | None = None) -> None:
        self._root_authority = root_authority

    @contextmanager
    def open(self, root: Path, relative_path: str) -> Iterator[_WindowsStream]:
        with self._open_bound(
            relative_path,
            self._root_authority,
            selected_root=root,
        ) as stream:
            yield stream

    @contextmanager
    def open_with_authority(
        self,
        relative_path: str,
        authority: RootAuthority,
    ) -> Iterator[_WindowsStream]:
        with self._open_bound(relative_path, authority) as stream:
            yield stream

    @contextmanager
    def _open_bound(
        self,
        relative_path: str,
        root_authority: RootAuthority | None,
        *,
        selected_root: Path | None = None,
    ) -> Iterator[_WindowsStream]:
        if os.name != "nt":
            raise UnsupportedVerification(
                "cache-honest verification is implemented only for Windows"
            )

        normalized = validate_relative_path(relative_path)
        if selected_root is None:
            if root_authority is None:  # internal contract; defensive only
                raise TypeError("authority-bound open requires root authority")
            logical_root: str | Path = root_authority.logical_root
        else:
            logical_root = selected_root
        root_path = Path(lexical_absolute_path(logical_root))
        authority = root_authority or RootAuthority(str(root_path))
        if selected_root is not None and not _same_logical_path(
            str(root_path), authority.logical_root
        ):
            raise UnsupportedVerification(
                "verification selection root does not match its reviewed root"
            )
        candidate = root_path.joinpath(*PureWindowsPath(normalized).parts)
        _reject_reparse_components(authority, normalized)

        api = _WindowsApi()
        sector_size = api.sector_size(candidate)
        handle = api.open_file(candidate)
        try:
            api.require_expected_final_path(root_path, normalized, handle)
            stream = _WindowsStream(api, handle, sector_size)
            stream.stat()  # reject directories/reparse points before yielding
            yield stream
        finally:
            api.close(handle)


def _reject_reparse_components(
    authority: RootAuthority,
    normalized_path: str,
) -> None:
    try:
        admit_root_chain(
            authority,
            lstat=_verification_lstat,
        )
    except RootAuthorityError as error:
        _raise_verification_root_admission(error)

    current = Path(authority.logical_root)
    for component in PureWindowsPath(normalized_path).parts:
        current = current / component
        observed = _verification_lstat(str(current))
        if is_placeholder_stat(observed) or is_reparse_stat(observed):
            raise UnsupportedVerification(
                f"verification refuses reparse component: {component}"
            )


def _verification_lstat(path: str) -> os.stat_result:
    return os.lstat(to_extended_length_path(path))


def _raise_verification_root_admission(error: RootAuthorityError) -> None:
    if error.issue is RootAuthorityIssue.COMPONENT_UNAVAILABLE:
        cause = error.__cause__
        if isinstance(cause, OSError):
            raise cause from error
    if error.issue in {
        RootAuthorityIssue.PLACEHOLDER_COMPONENT,
        RootAuthorityIssue.REPARSE_COMPONENT,
    }:
        raise UnsupportedVerification(
            "verification refuses a reparse location root chain"
        ) from error
    if error.issue is RootAuthorityIssue.NON_DIRECTORY_COMPONENT:
        raise UnsupportedVerification(
            "verification location root chain is not an ordinary directory"
        ) from error
    raise UnsupportedVerification(logical_error_text(error)) from error


def _same_logical_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(
        os.path.normpath(right)
    )


class _FileTime(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", ctypes.c_uint32),
        ("dwHighDateTime", ctypes.c_uint32),
    ]


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", ctypes.c_uint32),
        ("ftCreationTime", _FileTime),
        ("ftLastAccessTime", _FileTime),
        ("ftLastWriteTime", _FileTime),
        ("dwVolumeSerialNumber", ctypes.c_uint32),
        ("nFileSizeHigh", ctypes.c_uint32),
        ("nFileSizeLow", ctypes.c_uint32),
        ("nNumberOfLinks", ctypes.c_uint32),
        ("nFileIndexHigh", ctypes.c_uint32),
        ("nFileIndexLow", ctypes.c_uint32),
    ]


class _WindowsApi:
    def __init__(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32 = kernel32
        self._configure_signatures()

    def _configure_signatures(self) -> None:
        k32 = self._kernel32
        k32.CreateFileW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        k32.CreateFileW.restype = ctypes.c_void_p
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        k32.CloseHandle.restype = ctypes.c_int
        k32.GetFileInformationByHandle.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_ByHandleFileInformation),
        ]
        k32.GetFileInformationByHandle.restype = ctypes.c_int
        k32.ReadFile.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_void_p,
        ]
        k32.ReadFile.restype = ctypes.c_int
        k32.VirtualAlloc.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_uint32,
            ctypes.c_uint32,
        ]
        k32.VirtualAlloc.restype = ctypes.c_void_p
        k32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
        k32.VirtualFree.restype = ctypes.c_int
        k32.GetFinalPathNameByHandleW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
        ]
        k32.GetFinalPathNameByHandleW.restype = ctypes.c_uint32
        k32.GetVolumePathNameW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
        ]
        k32.GetVolumePathNameW.restype = ctypes.c_int
        k32.GetDiskFreeSpaceW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
        ]
        k32.GetDiskFreeSpaceW.restype = ctypes.c_int

    def open_file(self, path: Path) -> int:
        handle = self._kernel32.CreateFileW(
            _extended_path(path),
            _GENERIC_READ,
            # Keep the attested path bound to this subject for the whole read.
            # Existing or new writers/deleters must not be able to replace the
            # selected name while this handle still refers to the old file.
            _FILE_SHARE_READ,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_NO_BUFFERING
            | _FILE_FLAG_SEQUENTIAL_SCAN
            | _FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        if handle == ctypes.c_void_p(-1).value:
            self._raise_open_error(path)
        return handle

    def open_directory(self, path: Path) -> int:
        handle = self._kernel32.CreateFileW(
            _extended_path(path),
            0,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if handle == ctypes.c_void_p(-1).value:
            self._raise_open_error(path)
        return handle

    def _raise_open_error(self, path: Path) -> None:
        error = ctypes.get_last_error()
        if error in (_ERROR_FILE_NOT_FOUND, _ERROR_PATH_NOT_FOUND):
            raise FileNotFoundError(error, os.strerror(error), str(path))
        if error == _ERROR_ACCESS_DENIED:
            raise PermissionError(error, os.strerror(error), str(path))
        raise OSError(error, os.strerror(error), str(path))

    def close(self, handle: int) -> None:
        self._kernel32.CloseHandle(handle)

    def stat(self, handle: int) -> FileStat:
        info = _ByHandleFileInformation()
        if not self._kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            error = ctypes.get_last_error()
            raise OSError(error, os.strerror(error))
        if info.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            raise UnsupportedVerification("verification refuses a reparse subject")
        if info.dwFileAttributes & _FILE_ATTRIBUTE_DIRECTORY:
            raise UnsupportedVerification("verification selections must name files")

        size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
        file_index = (info.nFileIndexHigh << 32) | info.nFileIndexLow
        identity = FileIdentity(
            volume_serial=f"{info.dwVolumeSerialNumber:08X}",
            file_index=file_index,
        )
        return FileStat(
            kind=EntryKind.FILE,
            size=size,
            mtime_ns=_filetime_to_unix_ns(info.ftLastWriteTime),
            file_identity=identity,
            nlink=info.nNumberOfLinks,
            metadata=MetadataSnapshot(
                attributes=info.dwFileAttributes,
                created_ns=_filetime_to_unix_ns(info.ftCreationTime),
            ),
        )

    def sector_size(self, path: Path) -> int:
        volume_buffer = ctypes.create_unicode_buffer(32768)
        if not self._kernel32.GetVolumePathNameW(
            _extended_path(path), volume_buffer, len(volume_buffer)
        ):
            error = ctypes.get_last_error()
            raise UnsupportedVerification(
                f"cannot identify the verification volume (Windows error {error})"
            )
        sectors_per_cluster = ctypes.c_uint32()
        bytes_per_sector = ctypes.c_uint32()
        free_clusters = ctypes.c_uint32()
        total_clusters = ctypes.c_uint32()
        if not self._kernel32.GetDiskFreeSpaceW(
            volume_buffer.value,
            ctypes.byref(sectors_per_cluster),
            ctypes.byref(bytes_per_sector),
            ctypes.byref(free_clusters),
            ctypes.byref(total_clusters),
        ):
            error = ctypes.get_last_error()
            raise UnsupportedVerification(
                f"cannot determine unbuffered-read alignment (Windows error {error})"
            )
        if bytes_per_sector.value <= 0:
            raise UnsupportedVerification("volume reported an invalid sector size")
        return bytes_per_sector.value

    def require_expected_final_path(
        self, root: Path, relative_path: str, file_handle: int
    ) -> None:
        root_handle = self.open_directory(root)
        try:
            root_final = self.final_path(root_handle).rstrip("\\/")
        finally:
            self.close(root_handle)
        expected = root_final + "\\" + relative_path
        actual = self.final_path(file_handle)
        if ntpath.normcase(expected) != ntpath.normcase(actual):
            raise UnsupportedVerification(
                "the opened handle does not resolve to the selected root-relative path"
            )

    def final_path(self, handle: int) -> str:
        size = 512
        while True:
            buffer = ctypes.create_unicode_buffer(size)
            length = self._kernel32.GetFinalPathNameByHandleW(handle, buffer, size, 0)
            if length == 0:
                error = ctypes.get_last_error()
                raise OSError(error, os.strerror(error))
            if length < size:
                return buffer.value
            size = length + 1

    def read(self, handle: int, address: int, size: int) -> int:
        bytes_read = ctypes.c_uint32()
        if not self._kernel32.ReadFile(
            handle, address, size, ctypes.byref(bytes_read), None
        ):
            error = ctypes.get_last_error()
            if error == _ERROR_INVALID_PARAMETER:
                raise UnsupportedVerification(
                    "the volume rejected an aligned unbuffered read"
                )
            raise OSError(error, os.strerror(error))
        return bytes_read.value

    def allocate(self, size: int) -> int:
        address = self._kernel32.VirtualAlloc(
            None, size, _MEM_COMMIT | _MEM_RESERVE, _PAGE_READWRITE
        )
        if not address:
            error = ctypes.get_last_error()
            raise OSError(error, os.strerror(error))
        return address

    def release(self, address: int) -> None:
        if not self._kernel32.VirtualFree(address, 0, _MEM_RELEASE):
            error = ctypes.get_last_error()
            raise OSError(error, os.strerror(error))


class _WindowsStream:
    strategy = ReadStrategy.WINDOWS_UNBUFFERED

    def __init__(self, api: _WindowsApi, handle: int, sector_size: int) -> None:
        self._api = api
        self._handle = handle
        self._sector_size = sector_size

    def stat(self) -> FileStat:
        return self._api.stat(self._handle)

    def iter_chunks(self, chunk_size: int) -> Iterator[bytes]:
        subject_size = self.stat().size
        if subject_size == 0:
            return
        aligned_size = _align_up(chunk_size, self._sector_size)
        address = self._api.allocate(aligned_size)
        total = 0
        try:
            while total < subject_size:
                count = self._api.read(self._handle, address, aligned_size)
                if count == 0:
                    break
                total += count
                yield ctypes.string_at(address, count)
        finally:
            self._api.release(address)


def _align_up(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _filetime_to_unix_ns(value: _FileTime) -> int:
    ticks = (value.dwHighDateTime << 32) | value.dwLowDateTime
    return (ticks - _WINDOWS_EPOCH_TICKS) * 100


def _extended_path(path: Path) -> str:
    return to_extended_length_path(str(path))
