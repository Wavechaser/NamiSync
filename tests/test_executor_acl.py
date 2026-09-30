"""Windows ACL proof for the executor's held finalization handle."""

from __future__ import annotations

import ctypes
from contextlib import nullcontext
from dataclasses import replace
from ctypes import wintypes
import os
from pathlib import Path

import pytest

import namisync.modules.executor.native as executor_module
from namisync.core.planning import OpId
from namisync.modules.executor import NativeFileSystem

from _executor_fixtures import RUN_ID


_DACL_SECURITY_INFORMATION = 0x00000004
_ERROR_ACCESS_DENIED = 5
_FILE_PERSISTENT_ACLS = 0x00000008
_SDDL_REVISION_1 = 1

# Deny FILE_WRITE_ATTRIBUTES to Everyone, then retain read, delete, and
# security-descriptor repair rights. The explicit deny defeats inherited
# grants while DELETE and WRITE_DAC keep rename and cleanup recoverable.
_RESTRICTIVE_DACL = (
    "D:P"
    "(D;;0x00000100;;;WD)"
    "(A;;0x001F0089;;;WD)"
)


def _security_descriptor(path: Path) -> bytes:
    windows = executor_module._WINDOWS
    assert windows is not None
    needed = wintypes.DWORD()
    windows.get_security(
        executor_module._win32_path(path),
        _DACL_SECURITY_INFORMATION,
        None,
        0,
        ctypes.byref(needed),
    )
    if needed.value == 0:
        raise ctypes.WinError(ctypes.get_last_error())
    buffer = ctypes.create_string_buffer(needed.value)
    if not windows.get_security(
        executor_module._win32_path(path),
        _DACL_SECURITY_INFORMATION,
        buffer,
        needed,
        ctypes.byref(needed),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return bytes(buffer.raw[: needed.value])


def _set_security_descriptor(path: Path, descriptor: bytes) -> None:
    windows = executor_module._WINDOWS
    assert windows is not None
    buffer = ctypes.create_string_buffer(descriptor)
    if not windows.set_security(
        executor_module._win32_path(path),
        _DACL_SECURITY_INFORMATION,
        buffer,
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def _set_restrictive_dacl(path: Path, sddl: str = _RESTRICTIVE_DACL) -> None:
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    convert = advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD),
    ]
    convert.restype = wintypes.BOOL
    local_free = kernel32.LocalFree
    local_free.argtypes = [wintypes.HLOCAL]
    local_free.restype = wintypes.HLOCAL

    descriptor = wintypes.LPVOID()
    if not convert(
        sddl,
        _SDDL_REVISION_1,
        ctypes.byref(descriptor),
        None,
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        windows = executor_module._WINDOWS
        assert windows is not None
        if not windows.set_security(
            executor_module._win32_path(path),
            _DACL_SECURITY_INFORMATION,
            descriptor,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        local_free(descriptor)


def _supports_persistent_acls(path: Path) -> bool:
    windows = executor_module._WINDOWS
    assert windows is not None
    volume_path = ctypes.create_unicode_buffer(32768)
    if not windows.get_volume_path(
        executor_module._win32_path(path),
        volume_path,
        len(volume_path),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    flags = wintypes.DWORD()
    if not windows.get_volume_information(
        volume_path.value,
        None,
        0,
        None,
        None,
        ctypes.byref(flags),
        None,
        0,
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return bool(flags.value & _FILE_PERSISTENT_ACLS)


class RestrictiveAclFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None]] = []
        self.reopen_error: OSError | None = None

    def _open_metadata_handle(self, path: Path) -> int:
        handle = super()._open_metadata_handle(path)
        self.calls.append(("open", handle))
        return handle

    def copy_security(self, source: Path, target: Path) -> None:
        super().copy_security(source, target)
        self.calls.append(("acl", None))
        try:
            reopened = NativeFileSystem._open_metadata_handle(self, target)
        except OSError as error:
            self.reopen_error = error
            self.calls.append(("reopen-denied", None))
            if getattr(error, "winerror", None) != _ERROR_ACCESS_DENIED:
                raise AssertionError(
                    "the copied DACL did not cause an access denial"
                ) from error
        else:
            NativeFileSystem._close_handle(reopened)
            raise AssertionError(
                "the copied DACL allowed a fresh metadata reopen"
            )

    def _set_basic_info(
        self,
        handle: int,
        basic: executor_module._FileBasicInfo,
    ) -> None:
        self.calls.append(("basic", handle))
        NativeFileSystem._set_basic_info(handle, basic)

    def _flush_handle(self, handle: int) -> None:
        self.calls.append(("flush", handle))
        NativeFileSystem._flush_handle(handle)

    def _close_handle(self, handle: int) -> None:
        self.calls.append(("close", handle))
        NativeFileSystem._close_handle(handle)


@pytest.mark.skipif(os.name != "nt", reason="requires Windows persistent ACLs")
def test_restrictive_acl_cannot_block_held_finalization_handle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _supports_persistent_acls(tmp_path):
        pytest.skip("temporary volume does not support persistent ACLs")

    fs = RestrictiveAclFileSystem()
    windows = executor_module._WINDOWS
    assert windows is not None
    native_flush = windows.flush_file_buffers
    native_flush_handles: list[int] = []

    def observe_native_flush(handle: int):
        native_flush_handles.append(handle)
        return native_flush(handle)

    monkeypatch.setattr(
        windows,
        "flush_file_buffers",
        observe_native_flush,
    )
    source = tmp_path / "source.bin"
    target = tmp_path / "target.bin"
    temp = fs.owned_temp(
        target,
        RUN_ID,
        OpId("2" * 32),
    )
    source.write_bytes(b"source payload")
    temp.write_bytes(b"source payload")
    original_dacl = _security_descriptor(source)

    try:
        _set_restrictive_dacl(source)
        with fs.open_source(source) as stream:
            assert stream.read() == b"source payload"
        intended = fs.stat_path(source)
        assert intended is not None

        finalized = fs.finalize_temp(
            temp,
            intended,
            preserve_created=True,
            acl_source=source,
        )
        fs.publish_new(temp, target)

        assert target.read_bytes() == b"source payload"
        assert finalized.size == len(b"source payload")
        assert not temp.exists()
        assert fs.reopen_error is not None
        assert [name for name, _ in fs.calls] == [
            "open",
            "acl",
            "reopen-denied",
            "basic",
            "flush",
            "close",
        ]
        held_handle = fs.calls[0][1]
        assert held_handle is not None
        assert fs.calls[3][1] == held_handle
        assert fs.calls[4][1] == held_handle
        assert fs.calls[5][1] == held_handle
        assert native_flush_handles == [held_handle]
        try:
            reopened = NativeFileSystem._open_metadata_handle(fs, target)
        except OSError as error:
            assert getattr(error, "winerror", None) == _ERROR_ACCESS_DENIED
        else:
            NativeFileSystem._close_handle(reopened)
            pytest.fail("the published DACL allowed a fresh metadata reopen")
    finally:
        for path in (source, temp, target):
            if path.exists():
                _set_security_descriptor(path, original_dacl)


@pytest.mark.skipif(os.name != "nt", reason="requires Windows persistent ACLs")
@pytest.mark.parametrize("denial", ("delete", "write-data", "write-attributes", "inherited-write"))
@pytest.mark.parametrize("retained", (False, True), ids=("path-finish", "retained-finish"))
def test_retained_copy_finishes_with_permissions_granted_before_acl_denial(
    tmp_path: Path,
    denial: str,
    retained: bool,
) -> None:
    if not _supports_persistent_acls(tmp_path):
        pytest.skip("temporary volume does not support persistent ACLs")
    source = tmp_path / "source.bin"
    parent = tmp_path / "target"
    parent.mkdir()
    temp = parent / "temp.bin"
    target = parent / "target.bin"
    source.write_bytes(b"payload")
    original_dacl = _security_descriptor(source)
    parent_dacl = _security_descriptor(parent)
    fs = NativeFileSystem()
    try:
        if denial == "delete":
            _set_restrictive_dacl(source, "D:P(D;;SD;;;WD)(A;;FA;;;WD)")
            _set_restrictive_dacl(parent, "D:P(D;;0x40;;;WD)(A;OICI;FA;;;WD)")
        elif denial == "write-data":
            _set_restrictive_dacl(source, "D:P(D;;0x2;;;WD)(A;;FA;;;WD)")
        elif denial == "write-attributes":
            _set_restrictive_dacl(source)
        else:
            _set_restrictive_dacl(parent, "D:P(D;OIIO;0x2;;;WD)(A;OICI;FA;;;WD)")
        intended = fs.stat_path(source)
        assert intended is not None
        if denial in {"write-data", "write-attributes"}:
            intended = replace(
                intended, metadata=replace(intended.metadata, attributes=1)
            )
        scope = (
            executor_module._root_invocation_scope(fs, object(), (), None)
            if retained else nullcontext()
        )
        with scope:
            with fs.create_temp(temp, allocation_size=None) as writer:
                descriptor = writer.fileno()
                writer.write(b"payload")

            def finish() -> None:
                finalized = fs.finalize_temp(
                    temp, intended, preserve_created=True,
                    acl_source=None if denial == "inherited-write" else source,
                )
                fs.publish_new(temp, target)
                published = fs.ensure_published_metadata(
                    target, finalized, intended,
                    preserve_created=True, apply_readonly=True,
                )
                assert published.size == len(b"payload")

            if retained:
                finish()
                assert not temp.exists() and target.read_bytes() == b"payload"
                with pytest.raises(OSError):
                    os.fstat(descriptor)
            else:
                with pytest.raises(PermissionError) as refused:
                    finish()
                assert refused.value.winerror == _ERROR_ACCESS_DENIED
    finally:
        for path in (source, temp, target):
            if path.exists():
                _set_security_descriptor(path, original_dacl)
                fs.clear_readonly(path)
        _set_security_descriptor(parent, parent_dacl)
