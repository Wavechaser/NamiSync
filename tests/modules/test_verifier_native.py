"""Windows verifier reader, handle, and cache-honesty tests."""

from __future__ import annotations

import os
import ctypes
import stat as stat_module
import subprocess
import sys
import struct
from pathlib import Path, PureWindowsPath

import pytest
from xxhash import xxh3_128

import namisync.modules.verifier.native as verifier_native
import namisync.modules.verifier.engine as verifier_engine
import namisync.core.root_authority as root_authority_module
from namisync.core.integrity import (
    IntegrityReason,
    IntegrityResult,
    IntegritySelection,
    MAX_VERIFIER_CHUNK_SIZE,
    ReadStrategy,
    UnsupportedVerification,
    VerifierContext,
)
from namisync.core.models import FileStat
from namisync.core.pathing import from_extended_length_path
from namisync.core.root_authority import (
    RootAuthority,
)
from namisync.core.session import RunContext
from namisync.modules.verifier import WindowsUnbufferedReader, verify

from _verifier_fixtures import (
    _Clock,
    _Recorder,
    _attestation,
    _item,
    _native_context,
    _stat,
)


def test_windows_stream_refuses_alignment_above_public_chunk_ceiling() -> None:
    class _Api:
        def stat(self, handle: int) -> FileStat:
            assert handle == 73
            return _stat(size=1, mtime_ns=1, identity=None)

        def allocate(self, size: int) -> int:
            raise AssertionError(f"unexpected native allocation: {size}")

    stream = verifier_native._WindowsStream(
        _Api(),
        73,
        MAX_VERIFIER_CHUNK_SIZE + 1,
    )

    with pytest.raises(UnsupportedVerification, match="allocation limit"):
        next(stream.iter_chunks(1))


@pytest.mark.skipif(os.name != "nt", reason="Windows handle geometry")
@pytest.mark.parametrize("geometry", ["positive", "unavailable", "zero"])
def test_windows_handle_geometry_uses_open_handle_or_fresh_pathname_fallback(
    monkeypatch: pytest.MonkeyPatch,
    geometry: str,
) -> None:
    query_calls: list[tuple[int, int, int]] = []
    pathname_calls: list[Path] = []
    path = Path(r"F:\reviewed-root\payload.bin")

    class _Kernel32:
        def GetFileInformationByHandleEx(
            self, handle: int, information_class: int, target, size: int
        ) -> int:
            query_calls.append((handle, information_class, size))
            if geometry == "unavailable":
                ctypes.set_last_error(87)
                return 0
            storage = ctypes.cast(
                target, ctypes.POINTER(verifier_native._FileStorageInfo)
            ).contents
            storage.LogicalBytesPerSector = 512 if geometry == "positive" else 0
            return 1

    api = verifier_native._WindowsApi.__new__(verifier_native._WindowsApi)
    api._kernel32 = _Kernel32()
    monkeypatch.setattr(
        api, "sector_size", lambda candidate: pathname_calls.append(candidate) or 4096
    )

    assert api.sector_size_from_handle(73, path) == (
        512 if geometry == "positive" else 4096
    )
    assert query_calls == [(73, 16, 28)]
    assert pathname_calls == ([] if geometry == "positive" else [path])


@pytest.mark.skipif(os.name != "nt", reason="Windows reader error precedence")
@pytest.mark.parametrize("open_failure", [FileNotFoundError, PermissionError])
@pytest.mark.parametrize("geometry_refuses", [False, True])
def test_windows_reader_preserves_open_and_geometry_failure_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    open_failure: type[OSError],
    geometry_refuses: bool,
) -> None:
    path = tmp_path / "payload.bin"
    path.write_bytes(b"payload")
    calls: list[str] = []
    original_error = open_failure(2 if open_failure is FileNotFoundError else 5, "open failed")
    alignment_error = UnsupportedVerification("old pathname alignment refusal")

    class _Api:
        def open_file(self, candidate: Path) -> int:
            assert candidate == path
            calls.append("open")
            raise original_error

        def sector_size(self, candidate: Path) -> int:
            assert candidate == path
            calls.append("pathname")
            if geometry_refuses:
                raise alignment_error
            return 512

        def sector_size_from_handle(self, *_args) -> int:
            raise AssertionError("failed open has no handle geometry")

        def close(self, _handle: int) -> None:
            raise AssertionError("failed open has no handle to close")

    monkeypatch.setattr(verifier_native, "_WindowsApi", _Api)
    reader = WindowsUnbufferedReader()
    expected_error = alignment_error if geometry_refuses else original_error
    with pytest.raises(type(expected_error)) as refused:
        with reader.open(tmp_path, path.name):
            raise AssertionError("failed open yielded a stream")
    assert refused.value is expected_error
    assert calls == ["open", "pathname"]

    recorder = _Recorder()
    result = verify(
        IntegritySelection((_item(tmp_path, path=path.name, baseline_evidence=None),)),
        _native_context([], tmp_path), recorder, reader,
    )
    outcome = result.outcomes[0]
    assert (outcome.result, outcome.reason) == (
        (IntegrityResult.UNSUPPORTED, IntegrityReason.UNSUPPORTED_READ)
        if geometry_refuses else
        (IntegrityResult.MISSING, IntegrityReason.NOT_FOUND)
        if open_failure is FileNotFoundError else
        (IntegrityResult.ERROR, IntegrityReason.READ_ERROR)
    )
    assert outcome.detail is not None and str(expected_error) in outcome.detail
    assert recorder.commands == []


@pytest.mark.skipif(os.name != "nt", reason="Windows opened handle lifetime")
@pytest.mark.parametrize("failure_at", ["geometry", "final", "stat", "read", "yield"])
def test_windows_reader_closes_open_handle_on_all_later_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_at: str,
) -> None:
    path = tmp_path / "payload.bin"
    path.write_bytes(b"x")
    closed: list[int] = []
    released: list[int] = []
    failure = OSError(5, "owned failure")

    class _Api:
        def open_file(self, candidate: Path) -> int:
            assert candidate == path
            return 73

        def sector_size_from_handle(self, handle: int, candidate: Path) -> int:
            assert handle == 73 and candidate == path
            if failure_at == "geometry":
                raise failure
            return 512

        def require_expected_final_path(self, *_args) -> None:
            if failure_at == "final":
                raise failure

        def stat(self, handle: int) -> FileStat:
            assert handle == 73
            if failure_at == "stat":
                raise failure
            return _stat(size=1, identity=None)

        def allocate(self, _size: int) -> int:
            return 79

        def read(self, *_args) -> int:
            raise failure

        def release(self, address: int) -> None:
            released.append(address)

        def close(self, handle: int) -> None:
            closed.append(handle)

    monkeypatch.setattr(verifier_native, "_WindowsApi", _Api)
    with pytest.raises(OSError) as refused:
        with WindowsUnbufferedReader().open(tmp_path, path.name) as stream:
            if failure_at == "yield":
                raise failure
            next(stream.iter_chunks(1))
    assert refused.value is failure
    assert closed == [73]
    assert released == ([79] if failure_at == "read" else [])


@pytest.mark.skipif(os.name != "nt", reason="Windows cache-honest integration")
def test_windows_reader_uses_read_only_share_and_cache_honest_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "payload.bin"
    path.write_bytes(b"flag contract")
    expected = _stat(
        size=path.stat().st_size,
        mtime_ns=path.stat().st_mtime_ns,
        identity=None,
    )
    calls: list[tuple[object, ...]] = []
    closed: list[int] = []
    native_api = verifier_native._WindowsApi

    class _Kernel32:
        def CreateFileW(self, *args: object) -> int:
            calls.append(args)
            return 73

    class _CapturingApi(native_api):
        def __init__(self) -> None:
            self._kernel32 = _Kernel32()

        def sector_size_from_handle(self, handle: int, candidate: Path) -> int:
            assert handle == 73
            assert candidate == path
            return 4096

        def require_expected_final_path(
            self, root: Path, relative_path: str, file_handle: int
        ) -> None:
            assert root == tmp_path.resolve()
            assert relative_path == path.name
            assert file_handle == 73

        def stat(self, handle: int) -> FileStat:
            assert handle == 73
            return expected

        def close(self, handle: int) -> None:
            closed.append(handle)

    monkeypatch.setattr(verifier_native, "_WindowsApi", _CapturingApi)

    with WindowsUnbufferedReader().open(tmp_path, path.name) as stream:
        assert stream.strategy is ReadStrategy.WINDOWS_UNBUFFERED

    assert len(calls) == 1
    (
        opened_path,
        desired_access,
        share_mode,
        security_attributes,
        creation_disposition,
        flags,
        template,
    ) = calls[0]
    assert opened_path == verifier_native._extended_path(path)
    assert desired_access == verifier_native._GENERIC_READ
    assert share_mode == verifier_native._FILE_SHARE_READ
    assert share_mode & verifier_native._FILE_SHARE_WRITE == 0
    assert share_mode & verifier_native._FILE_SHARE_DELETE == 0
    assert security_attributes is None
    assert creation_disposition == verifier_native._OPEN_EXISTING
    assert flags == (
        verifier_native._FILE_FLAG_NO_BUFFERING
        | verifier_native._FILE_FLAG_SEQUENTIAL_SCAN
        | verifier_native._FILE_FLAG_OPEN_REPARSE_POINT
    )
    assert template is None
    assert closed == [73]


@pytest.mark.skipif(os.name != "nt", reason="Windows cache-honest integration")
def test_windows_reader_refuses_a_final_root_reparse_before_api_setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "configured-root"
    root.mkdir()
    (root / "payload.bin").write_bytes(b"payload")
    original_lstat = verifier_native.os.lstat

    def root_reparse_lstat(path):
        if Path(from_extended_length_path(str(path))) == root:
            class _RootReparse:
                st_mode = stat_module.S_IFDIR | 0o755
                st_file_attributes = verifier_native._FILE_ATTRIBUTE_REPARSE_POINT
                st_reparse_tag = 1

            return _RootReparse()
        return original_lstat(path)

    class _UnexpectedApi:
        def __init__(self) -> None:
            raise AssertionError("Windows API setup must follow root rejection")

    monkeypatch.setattr(verifier_native.os, "lstat", root_reparse_lstat)
    monkeypatch.setattr(verifier_native, "_WindowsApi", _UnexpectedApi)

    with pytest.raises(UnsupportedVerification, match="reparse location root"):
        with WindowsUnbufferedReader().open(root, "payload.bin"):
            raise AssertionError("unsafe root yielded a stream")


@pytest.mark.skipif(os.name != "nt", reason="Windows cache-honest integration")
def test_windows_reader_verifies_externally_flushed_file_without_cached_fallback(
    tmp_path: Path,
) -> None:
    chunk_size = 4 * 1024 * 1024
    pattern = b"NamiSync cache-honest verifier\n"
    payload = (
        pattern * ((chunk_size // len(pattern)) + 1)
    )[:chunk_size] + b"tail"
    path = tmp_path / "payload.bin"
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os, sys\n"
                "size = int(sys.argv[2])\n"
                "pattern = b'NamiSync cache-honest verifier\\n'\n"
                "payload = (pattern * ((size // len(pattern)) + 1))[:size]"
                " + b'tail'\n"
                "with open(sys.argv[1], 'wb') as handle:\n"
                "    handle.write(payload)\n"
                "    handle.flush()\n"
                "    os.fsync(handle.fileno())\n"
            ),
            str(path),
            str(chunk_size),
        ],
        check=True,
    )
    assert len(payload) == chunk_size + len(b"tail")
    os_stat = path.stat()
    expected = _stat(
        size=len(payload),
        mtime_ns=os_stat.st_mtime_ns,
        identity=None,
    )
    events: list[object] = []
    context = VerifierContext(
        run=RunContext(emit=events.append, checkpoint=lambda: None),
        clock=_Clock(),
        hasher_factory=xxh3_128,
        root_authority=_native_context([], tmp_path).root_authority,
    )
    assert context.chunk_size == chunk_size
    reader = WindowsUnbufferedReader()
    item = _item(
        tmp_path,
        path="payload.bin",
        expected_stat=expected,
        baseline_evidence=_attestation(payload, expected),
    )

    result = verify(
        IntegritySelection((item,)),
        context,
        _Recorder(),
        reader,
    )

    outcome = result.outcomes[0]
    assert outcome.result is IntegrityResult.VERIFIED
    assert outcome.reason is None
    assert outcome.read_strategy is ReadStrategy.WINDOWS_UNBUFFERED


@pytest.mark.skipif(os.name != "nt", reason="Windows cache-honest integration")
@pytest.mark.parametrize("rejection", ["reparse", "alignment", "containment"])
def test_windows_reader_safety_rejections_classify_unsupported_never_verified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rejection: str,
) -> None:
    payload = b"guarded subject"
    path = tmp_path / "payload.bin"
    path.write_bytes(payload)
    expected = _stat(
        size=len(payload),
        mtime_ns=path.stat().st_mtime_ns,
        identity=None,
    )
    closed: list[int] = []
    native_api = verifier_native._WindowsApi

    if rejection == "reparse":
        original_reject = verifier_native._reject_reparse_components
        original_lstat = verifier_native.os.lstat

        def report_reparse(
            authority: RootAuthority,
            relative_path: str,
            *,
            root_hold=None,
        ) -> None:
            candidate = Path(authority.logical_root).joinpath(
                *PureWindowsPath(relative_path).parts
            )

            def reparse_lstat(current: Path):
                observed = original_lstat(current)
                if Path(from_extended_length_path(str(current))) != candidate:
                    return observed

                class _ReportedReparse:
                    st_mode = observed.st_mode
                    st_file_attributes = (
                        verifier_native._FILE_ATTRIBUTE_REPARSE_POINT
                    )

                return _ReportedReparse()

            with monkeypatch.context() as patch:
                patch.setattr(verifier_native.os, "lstat", reparse_lstat)
                original_reject(authority, relative_path, root_hold=root_hold)

        monkeypatch.setattr(
            verifier_native, "_reject_reparse_components", report_reparse
        )
        expected_detail = "verification refuses reparse component"

        class _RejectingApi:
            def __init__(self) -> None:
                raise AssertionError("reparse rejection must precede Windows API setup")

    elif rejection == "alignment":
        expected_detail = "volume reported an invalid sector size"

        class _Kernel32:
            def GetFileInformationByHandleEx(self, *_args: object) -> int:
                ctypes.set_last_error(87)
                return 0

            def GetVolumePathNameW(
                self, _path: str, volume_buffer, _size: int
            ) -> int:
                volume_buffer.value = tmp_path.anchor
                return 1

            def GetDiskFreeSpaceW(self, *_args: object) -> int:
                return 1

        class _RejectingApi(native_api):
            def __init__(self) -> None:
                self._kernel32 = _Kernel32()

            def open_file(self, candidate: Path) -> int:
                assert candidate == path
                return 73

            def close(self, handle: int) -> None:
                closed.append(handle)

    else:
        expected_detail = (
            "the opened handle does not resolve to the selected root-relative path"
        )

        class _RejectingApi(native_api):
            def __init__(self) -> None:
                pass

            def sector_size_from_handle(self, handle: int, candidate: Path) -> int:
                assert handle == 73
                assert candidate == path
                return 4096

            def open_file(self, candidate: Path) -> int:
                assert candidate == path
                return 73

            def open_directory(self, root: Path) -> int:
                assert root == tmp_path.resolve()
                return 74

            def final_path(self, handle: int) -> str:
                return (
                    r"\\?\C:\selected-root"
                    if handle == 74
                    else r"\\?\C:\escaped-root\payload.bin"
                )

            def close(self, handle: int) -> None:
                closed.append(handle)

    monkeypatch.setattr(verifier_native, "_WindowsApi", _RejectingApi)
    recorder = _Recorder()
    item = _item(
        tmp_path,
        path=path.name,
        expected_stat=expected,
        baseline_evidence=_attestation(payload, expected),
    )

    result = verify(
        IntegritySelection((item,)),
        _native_context([], tmp_path),
        recorder,
        WindowsUnbufferedReader(),
    )

    outcome = result.outcomes[0]
    assert outcome.result is IntegrityResult.UNSUPPORTED
    assert outcome.result is not IntegrityResult.VERIFIED
    assert outcome.reason is IntegrityReason.UNSUPPORTED_READ
    assert outcome.detail is not None and expected_detail in outcome.detail
    assert recorder.commands == []
    assert closed == (
        [74, 73] if rejection == "containment"
        else [73] if rejection == "alignment" else []
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows cache-honest integration")
def test_windows_reader_holds_selected_path_against_write_and_replacement(
    tmp_path: Path,
) -> None:
    path = tmp_path / "payload.bin"
    replacement = tmp_path / "replacement.bin"
    path.write_bytes(b"selected subject")
    replacement.write_bytes(b"replacement subject")

    reader = WindowsUnbufferedReader()
    try:
        with reader.open(tmp_path, path.name) as stream:
            with pytest.raises(PermissionError):
                path.write_bytes(b"overwritten")
            with pytest.raises(PermissionError):
                os.replace(replacement, path)
            assert stream.stat().size == len(b"selected subject")
    except UnsupportedVerification as exc:
        pytest.skip(f"unbuffered strategy unavailable: {exc}")

    assert path.read_bytes() == b"selected subject"
    assert replacement.read_bytes() == b"replacement subject"


def _reuse_verifier_root(reader, authority, context, invocation, owner):
    if owner == "engine":
        verifier_engine._admit_verification_root(
            Path(authority.logical_root), context, reader=reader, root_invocation=invocation
        )
    else:
        with reader.open_with_authority("payload.bin", authority):
            pass


@pytest.mark.skipif(os.name != "nt", reason="native Windows held attributes")
@pytest.mark.parametrize("owner", ("engine", "native"))
@pytest.mark.parametrize("state", ("placeholder", "query-failure"))
def test_verifier_held_admission_refuses_current_attributes_before_later_probes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    owner: str,
    state: str,
) -> None:
    context = _native_context([], tmp_path)
    authority = context.root_authority
    reader = WindowsUnbufferedReader()
    queries = []
    with reader.root_scope(authority, invocation_owner=reader) as invocation:
        verifier_engine._admit_verification_root(
            tmp_path, context, reader=reader, root_invocation=invocation
        )
        assert invocation.admitted is not None and invocation.hold.confirm()
        assert root_authority_module._WINDOWS is not None

        def query(handle, kind, output, size):
            queries.append(kind)
            assert kind == 0
            if state == "query-failure":
                ctypes.set_last_error(5)
                return False
            info = ctypes.cast(output, ctypes.POINTER(root_authority_module._FileBasicInfo)).contents
            info.FileAttributes = 0x10 | 0x400 | 0x1000
            return True

        def later_probe(*args, **kwargs):
            raise AssertionError("unsafe held root reached fallback or later probe")

        monkeypatch.setattr(root_authority_module._WINDOWS, "get_file_information_ex", query)
        monkeypatch.setattr(verifier_engine, "admit_root", later_probe)
        monkeypatch.setattr(verifier_native, "_verification_lstat", later_probe)
        monkeypatch.setattr(verifier_native, "_WindowsApi", later_probe)
        expected = PermissionError if owner == "native" and state == "query-failure" else UnsupportedVerification
        with pytest.raises(expected):
            _reuse_verifier_root(reader, authority, context, invocation, owner)
        assert queries == [0]


@pytest.mark.skipif(os.name != "nt", reason="native NTFS in-place root conversion")
@pytest.mark.parametrize("owner", ("engine", "native"))
def test_verifier_held_admission_refuses_inplace_attribute_only_conversion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    owner: str,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    sibling = tmp_path / "owned-sibling"
    sibling.mkdir()
    marker = sibling / "untouched.bin"
    marker.write_bytes(b"owned sibling unchanged")
    context = _native_context([], root)
    authority = context.root_authority
    if authority.expected_volume_id.fs_type != "NTFS":
        pytest.skip("native junction conversion witness requires NTFS")
    reader = WindowsUnbufferedReader()
    ioctl = ctypes.WinDLL("kernel32", use_last_error=True).DeviceIoControl
    ioctl.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                      ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32),
                      ctypes.c_void_p]
    ioctl.restype = ctypes.c_int
    substitute = ("\\??\\" + str(sibling)).encode("utf-16-le")
    printed = str(sibling).encode("utf-16-le")
    paths = substitute + b"\0\0" + printed + b"\0\0"
    data = struct.pack("<LHHHHHH", 0xA0000003, 8 + len(paths), 0,
                       0, len(substitute), len(substitute) + 2, len(printed)) + paths
    with reader.root_scope(authority, invocation_owner=reader) as invocation:
        verifier_engine._admit_verification_root(
            root, context, reader=reader, root_invocation=invocation
        )
        assert invocation.admitted is not None and invocation.hold.confirm()
        assert root_authority_module._WINDOWS is not None
        handle = root_authority_module._WINDOWS.create_file(
            verifier_native._extended_path(root), 0x100, 7, None, 3, 0x02200000, None
        )
        assert handle != root_authority_module._INVALID_HANDLE_VALUE
        converted = False
        try:
            buffer = ctypes.create_string_buffer(data)
            returned = ctypes.c_uint32()
            converted = bool(ioctl(handle, 0x900A4, buffer, len(data), None, 0,
                                   ctypes.byref(returned), None))
            assert converted, ctypes.get_last_error()
            assert root.lstat().st_file_attributes & 0x400

            def later_probe(*args, **kwargs):
                raise AssertionError("converted held root reached fallback or later probe")

            monkeypatch.setattr(verifier_engine, "admit_root", later_probe)
            monkeypatch.setattr(verifier_native, "_verification_lstat", later_probe)
            monkeypatch.setattr(verifier_native, "_WindowsApi", later_probe)
            with pytest.raises(UnsupportedVerification, match="reparse"):
                _reuse_verifier_root(reader, authority, context, invocation, owner)
            assert marker.read_bytes() == b"owned sibling unchanged"
        finally:
            try:
                if converted:
                    delete = ctypes.create_string_buffer(struct.pack("<LHH", 0xA0000003, 0, 0))
                    returned = ctypes.c_uint32()
                    assert ioctl(handle, 0x900AC, delete, 8, None, 0,
                                 ctypes.byref(returned), None), ctypes.get_last_error()
            finally:
                root_authority_module._WINDOWS.close_handle(handle)
        assert not root.lstat().st_file_attributes & 0x400
    root.rename(tmp_path / "released-root")
