"""Executor native filesystem acceptance and regression tests."""

from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import stat as stat_module
import subprocess
import sys
import textwrap
from types import SimpleNamespace

import pytest
from xxhash import xxh3_128

import _executor_fixtures as executor_fixtures
import namisync.modules.executor.native as executor_module
import namisync.modules.executor.pipeline as executor_pipeline
import namisync.modules.executor.runtime as executor_runtime
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.events import ItemOutcome
from namisync.core.execution import (
    CopyDigest,
    RecordedCopyIdentity,
    validated_run_id,
)
from namisync.core.models import (
    FileStat,
    IgnoreSet,
    Root,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import to_extended_length_path
from namisync.core.planning import (
    OpId,
    OperationKind,
    PreservationPolicy,
)
from namisync.core.root_authority import FILE_ATTRIBUTE_OFFLINE
from namisync.core.session import Canceled, RunContext, SessionState
from namisync.modules.executor import (
    NativeCopyBackend,
    NativeFileSystem,
    UnsafeExecutionPath,
    execute,
)
from namisync.modules.executor.pipeline import (
    _PREALLOCATION_THRESHOLD,
)
from namisync.modules.scanner import scan

from _executor_fixtures import (
    RUN_ID,
    FakeRecorder,
    _create_directory_reparse,
    _item_outcome,
    _operation,
    _plan,
    _policies,
    _recorder_names,
    _require_directory_reparse,
    _roots,
    _run,
    _xset,
)


def _create_probe_for_cache_test(link: Path, target: Path) -> None:
    if os.name == "nt":
        link.mkdir()
    else:
        link.symlink_to(target, target_is_directory=True)


def test_directory_reparse_capability_success_is_cached_per_volume_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target"
    first = tmp_path / "first"
    second = tmp_path / "second"
    target.mkdir()
    first.mkdir()
    second.mkdir()
    calls: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        executor_fixtures,
        "_DIRECTORY_REPARSE_CAPABLE_VOLUMES",
        set(),
    )
    monkeypatch.setattr(
        executor_fixtures,
        "_directory_reparse_volume_pair",
        lambda _link_parent, _target: (1, 2),
    )

    def create(link: Path, redirected: Path) -> None:
        calls.append((link, redirected))
        _create_probe_for_cache_test(link, redirected)

    monkeypatch.setattr(executor_fixtures, "_create_directory_reparse", create)

    executor_fixtures._require_directory_reparse(first, target)
    executor_fixtures._require_directory_reparse(second, target)

    assert calls == [(first / "directory-reparse-probe", target)]


def test_directory_reparse_capability_distinguishes_volume_pairs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target"
    first = tmp_path / "first"
    second = tmp_path / "second"
    target.mkdir()
    first.mkdir()
    second.mkdir()
    calls: list[Path] = []
    monkeypatch.setattr(
        executor_fixtures,
        "_DIRECTORY_REPARSE_CAPABLE_VOLUMES",
        set(),
    )
    monkeypatch.setattr(
        executor_fixtures,
        "_directory_reparse_volume_pair",
        lambda link_parent, _target: (hash(link_parent.name), 2),
    )

    def create(link: Path, redirected: Path) -> None:
        calls.append(link)
        _create_probe_for_cache_test(link, redirected)

    monkeypatch.setattr(executor_fixtures, "_create_directory_reparse", create)

    executor_fixtures._require_directory_reparse(first, target)
    executor_fixtures._require_directory_reparse(second, target)

    assert calls == [
        first / "directory-reparse-probe",
        second / "directory-reparse-probe",
    ]


def test_directory_reparse_capability_failure_is_not_cached(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target"
    first = tmp_path / "first"
    second = tmp_path / "second"
    target.mkdir()
    first.mkdir()
    second.mkdir()
    calls: list[Path] = []
    monkeypatch.setattr(
        executor_fixtures,
        "_DIRECTORY_REPARSE_CAPABLE_VOLUMES",
        set(),
    )
    monkeypatch.setattr(
        executor_fixtures,
        "_directory_reparse_volume_pair",
        lambda _link_parent, _target: (1, 2),
    )

    def fail(link: Path, _redirected: Path) -> None:
        calls.append(link)
        raise OSError("unavailable")

    monkeypatch.setattr(executor_fixtures, "_create_directory_reparse", fail)

    with pytest.raises(pytest.skip.Exception, match="unavailable"):
        executor_fixtures._require_directory_reparse(first, target)
    with pytest.raises(pytest.skip.Exception, match="unavailable"):
        executor_fixtures._require_directory_reparse(second, target)

    assert calls == [
        first / "directory-reparse-probe",
        second / "directory-reparse-probe",
    ]


def test_native_filesystem_rejects_lexical_root_before_resolving_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = tmp_path / "configured-root"
    fs = NativeFileSystem()
    observed: list[Path] = []
    reject_reparse = fs._reject_reparse

    def fail_if_followed(_path: Path, *, strict: bool) -> Path:
        raise AssertionError("configured root was followed before rejection")

    def reject_root(path: Path) -> os.stat_result:
        observed.append(path)
        if path == configured:
            raise UnsafeExecutionPath("reparse points are not executable")
        return reject_reparse(path)

    monkeypatch.setattr(executor_module, "_resolved_logical_path", fail_if_followed)
    monkeypatch.setattr(fs, "_reject_reparse", reject_root)

    with pytest.raises(UnsafeExecutionPath, match="reparse points"):
        fs.resolve(configured, "file.bin", must_exist=False)

    assert observed[-1] == configured


def test_native_filesystem_revalidates_an_empty_chain_mount_anchor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = tmp_path / "mounted-root"
    configured.mkdir()
    fs = NativeFileSystem()
    monkeypatch.setattr(
        fs,
        "_observe_root_anchor",
        lambda _path: str(tmp_path),
    )
    monkeypatch.setattr(
        fs,
        "_observe_root_component",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("mismatched reviewed anchor must stop chain admission")
        ),
    )

    with pytest.raises(UnsafeExecutionPath, match="volume anchor changed"):
        fs.revalidate_root(configured, trusted_anchor=configured)


def test_native_filesystem_refuses_same_serial_with_different_filesystem(
    tmp_path: Path,
) -> None:
    fs = NativeFileSystem()
    actual = fs._volume_id(tmp_path)
    expected = VolumeId(
        actual.serial,
        "DIFFERENT" if actual.fs_type != "DIFFERENT" else "OTHER",
    )

    with pytest.raises(UnsafeExecutionPath, match="volume changed"):
        fs.revalidate_root(tmp_path, expected_volume=expected)


def test_native_filesystem_preserves_root_probe_order_and_volume_elision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fs = NativeFileSystem()
    reviewed_anchor = Path(fs._observe_root_anchor(str(tmp_path)))
    reviewed_volume = fs._observe_root_volume(str(tmp_path)).volume_id
    events: list[str] = []
    observe_anchor = fs._observe_root_anchor
    observe_component = fs._observe_root_component
    observe_volume = fs._observe_root_volume

    def anchor(path: str) -> str:
        events.append("anchor")
        return observe_anchor(path)

    def component(path: str) -> os.stat_result:
        events.append("component")
        return observe_component(path)

    def volume(path: str):
        events.append("volume")
        return observe_volume(path)

    monkeypatch.setattr(fs, "_observe_root_anchor", anchor)
    monkeypatch.setattr(fs, "_observe_root_component", component)
    monkeypatch.setattr(fs, "_observe_root_volume", volume)

    fs.revalidate_root(tmp_path, trusted_anchor=reviewed_anchor)

    assert events[0] == "anchor"
    assert events.count("anchor") == 1
    assert events.count("component") >= 1
    assert "volume" not in events

    events.clear()
    fs.revalidate_root(
        tmp_path,
        trusted_anchor=reviewed_anchor,
        expected_volume=reviewed_volume,
    )

    assert events[0] == "anchor"
    assert events.count("volume") == 1
    volume_index = events.index("volume")
    assert "component" in events[1:volume_index]
    if os.name == "nt":
        assert events[-1] == "volume"
        assert events.count("anchor") == 1


def test_native_filesystem_refuses_anchor_change_during_volume_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fs = NativeFileSystem()
    reviewed_anchor = Path(fs._observe_root_anchor(str(tmp_path)))
    reviewed_volume = fs._observe_root_volume(str(tmp_path))
    changed = replace(
        reviewed_volume,
        evidence=VolumeEvidence(device_id=str(tmp_path / "changed-anchor")),
    )
    monkeypatch.setattr(fs, "_observe_root_volume", lambda _path: changed)

    with pytest.raises(
        UnsafeExecutionPath,
        match="volume anchor changed before filesystem access",
    ):
        fs.revalidate_root(
            tmp_path,
            trusted_anchor=reviewed_anchor,
            expected_volume=reviewed_volume.volume_id,
        )


def test_native_filesystem_maps_invalid_reviewed_anchor_to_unsafe_path(
    tmp_path: Path,
) -> None:
    configured = tmp_path / "configured"
    unrelated = tmp_path / "unrelated"
    configured.mkdir()
    unrelated.mkdir()

    with pytest.raises(
        UnsafeExecutionPath,
        match="volume anchor changed before filesystem access",
    ):
        NativeFileSystem().revalidate_root(
            configured,
            trusted_anchor=unrelated,
        )


@pytest.mark.parametrize(
    ("mode", "attributes", "reparse_tag"),
    (
        pytest.param(
            stat_module.S_IFDIR,
            FILE_ATTRIBUTE_OFFLINE,
            0,
            id="offline-only",
        ),
        pytest.param(
            stat_module.S_IFDIR,
            0,
            0xA000000C,
            id="tag-only",
        ),
        pytest.param(
            stat_module.S_IFREG,
            0,
            0,
            id="regular-first-directory-second",
        ),
    ),
)
def test_native_filesystem_keeps_legacy_root_component_classification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: int,
    attributes: int,
    reparse_tag: int,
) -> None:
    fs = NativeFileSystem()
    reviewed_anchor = Path(fs._observe_root_anchor(str(tmp_path)))
    observed = SimpleNamespace(
        st_mode=mode,
        st_file_attributes=attributes,
        st_reparse_tag=reparse_tag,
    )
    monkeypatch.setattr(fs, "_reject_reparse", lambda _path: observed)

    fs.revalidate_root(tmp_path, trusted_anchor=reviewed_anchor)


def test_native_directory_flush_succeeds_on_target_ntfs(tmp_path: Path) -> None:
    _, target = _roots(tmp_path)

    assert NativeFileSystem().flush_directory(target)


@pytest.mark.skipif(os.name != "nt", reason="requires FileAllocationInfo")
def test_native_preallocation_keeps_logical_eof_and_exclusive_temp(
    tmp_path: Path,
) -> None:
    path = tmp_path / "allocated.tmp"
    fs = NativeFileSystem()

    with fs.create_temp(path, allocation_size=8 * 1024 * 1024) as stream:
        assert path.stat().st_size == 0
        stream.write(b"x")

    assert path.read_bytes() == b"x"
    with pytest.raises(FileExistsError):
        fs.create_temp(path, allocation_size=None)


@pytest.mark.skipif(os.name != "nt", reason="requires FileAllocationInfo")
@pytest.mark.parametrize(
    ("winerror", "falls_back"),
    [
        (1, True),
        (50, True),
        (87, False),
        (120, True),
        (5, False),
        (112, False),
        (1816, False),
        (9999, False),
    ],
)
def test_preallocation_falls_back_only_for_explicitly_unsupported_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    winerror: int,
    falls_back: bool,
) -> None:
    bindings = executor_module._WINDOWS
    assert bindings is not None
    monkeypatch.setattr(bindings, "set_file_information", lambda *_args: 0)
    monkeypatch.setattr(executor_module.ctypes, "get_last_error", lambda: winerror)
    path = tmp_path / f"allocation-{winerror}.tmp"
    fs = NativeFileSystem()

    if falls_back:
        with fs.create_temp(path, allocation_size=1024) as stream:
            stream.write(b"payload")
        assert path.read_bytes() == b"payload"
    else:
        with pytest.raises(OSError) as caught:
            fs.create_temp(path, allocation_size=1024)
        assert getattr(caught.value, "winerror", None) == winerror


@pytest.mark.skipif(os.name != "nt", reason="requires FileAllocationInfo")
@pytest.mark.parametrize("winerror", [5, 87, 112, 1816, 9999])
def test_substantive_preallocation_failure_cleans_temp_before_copying(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    winerror: int,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    source_path.write_bytes(b"")
    with source_path.open("r+b") as stream:
        stream.truncate(_PREALLOCATION_THRESHOLD)
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    backend = CountingCopyBackend()
    bindings = executor_module._WINDOWS
    assert bindings is not None
    monkeypatch.setattr(bindings, "set_file_information", lambda *_args: 0)
    monkeypatch.setattr(
        executor_module.ctypes, "get_last_error", lambda: winerror
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(
            copy_backend=backend,
            max_chunk_size=4 * 1024 * 1024,
        ),
    )

    assert result.status is SessionState.FAILED
    item = _item_outcome(_)
    assert item.reason == "io-error"
    assert backend.calls == 0
    assert recorder.calls == []
    assert not (target / "file.bin").exists()
    assert not list(target.glob("*.synctmp-*"))


@pytest.mark.skipif(os.name != "nt", reason="requires FileAllocationInfo")
@pytest.mark.parametrize("winerror", [1, 50, 120])
def test_unsupported_preallocation_falls_back_through_real_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    winerror: int,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    with source_path.open("wb") as stream:
        stream.truncate(_PREALLOCATION_THRESHOLD)
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    backend = CountingCopyBackend()
    bindings = executor_module._WINDOWS
    assert bindings is not None
    set_file_information = bindings.set_file_information

    def fail_allocation_only(
        handle,
        information_class,
        information,
        information_size,
    ):
        if information_class == executor_module._FILE_ALLOCATION_INFO_CLASS:
            return 0
        return set_file_information(
            handle,
            information_class,
            information,
            information_size,
        )

    monkeypatch.setattr(bindings, "set_file_information", fail_allocation_only)
    monkeypatch.setattr(
        executor_module.ctypes, "get_last_error", lambda: winerror
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(
            copy_backend=backend,
            max_chunk_size=4 * 1024 * 1024,
        ),
    )

    assert result.status is SessionState.COMPLETED
    assert backend.calls == 1
    assert (target / "file.bin").stat().st_size == _PREALLOCATION_THRESHOLD
    assert _recorder_names(recorder) == ["copied"]
    assert not list(target.glob("*.synctmp-*"))


@pytest.mark.skipif(os.name != "nt", reason="requires O_SEQUENTIAL")
def test_cached_source_open_uses_the_sequential_hint_and_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "source.bin"
    path.write_bytes(b"payload")
    observed_flags: list[int] = []
    real_open = executor_module.os.open

    def recording_open(path_value, flags, *args):
        observed_flags.append(flags)
        return real_open(path_value, flags, *args)

    monkeypatch.setattr(executor_module.os, "open", recording_open)
    with NativeFileSystem().open_source(path) as stream:
        descriptor = stream.fileno()
        assert stream.read() == b"payload"

    assert observed_flags[0] & os.O_SEQUENTIAL
    with pytest.raises(OSError):
        os.fstat(descriptor)


class FinalizationOrderFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.last_access_values: list[int] = []
        self.acl_applied = False
        self.writer_flushes = 0

    def flush_file(self, stream) -> None:
        self.writer_flushes += 1
        super().flush_file(stream)

    def _open_metadata_handle(self, path: Path) -> int:
        if self.acl_applied:
            raise PermissionError("restrictive ACL would deny a later reopen")
        self.calls.append("open")
        return super()._open_metadata_handle(path)

    def copy_security(self, source: Path, target: Path) -> None:
        self.calls.append("acl")
        self.acl_applied = True

    def _set_basic_info(self, handle, basic) -> None:
        self.calls.append("basic")
        self.last_access_values.append(basic.LastAccessTime)
        super()._set_basic_info(handle, basic)

    def _flush_handle(self, handle) -> None:
        self.calls.append("flush")
        super()._flush_handle(handle)

    def _close_handle(self, handle) -> None:
        self.calls.append("close")
        super()._close_handle(handle)


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_temp_finalization_holds_one_handle_before_acl_and_flushes_once(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    temp = tmp_path / "temp.bin"
    source.write_bytes(b"payload")
    temp.write_bytes(b"payload")
    fs = FinalizationOrderFileSystem()
    intended = fs.stat_path(source)
    assert intended is not None
    initial_temp = temp.stat(follow_symlinks=False)
    requested_access_ns = max(
        0, initial_temp.st_mtime_ns - 2_000_000_000
    )
    os.utime(
        temp,
        ns=(requested_access_ns, initial_temp.st_mtime_ns),
    )
    preserved_access_ns = temp.stat(follow_symlinks=False).st_atime_ns

    finalized = fs.finalize_temp(
        temp,
        intended,
        preserve_created=True,
        acl_source=source,
    )

    assert finalized.size == len(b"payload")
    assert fs.calls == ["open", "acl", "basic", "flush", "close"]
    assert fs.last_access_values == [0]
    assert temp.stat(follow_symlinks=False).st_atime_ns == preserved_access_ns


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_apply_metadata_changes_mtime_without_managing_atime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "metadata.bin"
    path.write_bytes(b"payload")
    fs = NativeFileSystem()
    observed = fs.stat_path(path)
    assert observed is not None
    requested_access_ns = max(0, observed.mtime_ns - 3_000_000_000)
    requested_mtime_ns = max(0, observed.mtime_ns - 1_000_000_000)
    os.utime(path, ns=(requested_access_ns, observed.mtime_ns))
    preserved_access_ns = path.stat(follow_symlinks=False).st_atime_ns
    bindings = executor_module._WINDOWS
    assert bindings is not None
    native_set_file_time = bindings.set_file_time
    access_arguments: list[object] = []

    def recording_set_file_time(
        handle,
        created,
        accessed,
        modified,
    ):
        access_arguments.append(accessed)
        return native_set_file_time(handle, created, accessed, modified)

    monkeypatch.setattr(
        bindings,
        "set_file_time",
        recording_set_file_time,
    )

    fs.apply_metadata(
        path,
        replace(observed, mtime_ns=requested_mtime_ns),
        preserve_created=False,
        apply_readonly=False,
    )

    after = path.stat(follow_symlinks=False)
    assert access_arguments == [None]
    assert after.st_atime_ns == preserved_access_ns
    assert after.st_mtime_ns == requested_mtime_ns


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_full_copy_has_no_writer_flush_and_finalizes_before_restrictive_acl(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"payload")
    fs = FinalizationOrderFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, _, recorder = _run(
        _xset(
            _plan(
                source,
                target,
                (operation,),
                preservation=PreservationPolicy(preserve_acl=True),
            )
        ),
        fs=fs,
    )

    assert result.status is SessionState.COMPLETED
    assert (target / "file.bin").read_bytes() == b"payload"
    assert fs.writer_flushes == 0
    assert fs.calls == ["open", "acl", "basic", "flush", "close"]
    assert _recorder_names(recorder) == ["copied"]


class PublishedMetadataSpyFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.stat_calls = 0
        self.open_calls = 0
        self.flush_calls = 0

    def _stat_path(self, path: Path) -> FileStat | None:
        self.stat_calls += 1
        return super()._stat_path(path)

    def _open_metadata_handle(self, path: Path) -> int:
        self.open_calls += 1
        return super()._open_metadata_handle(path)

    def _flush_handle(self, handle) -> None:
        self.flush_calls += 1
        super()._flush_handle(handle)

    def reset_counts(self) -> None:
        self.stat_calls = 0
        self.open_calls = 0
        self.flush_calls = 0


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_atime_change_does_not_trigger_publish_repair_or_target_flush(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    temp = tmp_path / "temp.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"payload")
    temp.write_bytes(b"payload")
    fs = PublishedMetadataSpyFileSystem()
    intended = fs.stat_path(source)
    assert intended is not None
    finalized = fs.finalize_temp(
        temp, intended, preserve_created=True, acl_source=None
    )
    fs.publish_new(temp, target)
    changed_access_ns = max(0, finalized.mtime_ns - 1_000_000_000)
    os.utime(target, ns=(changed_access_ns, finalized.mtime_ns))
    before_access_ns = target.stat(follow_symlinks=False).st_atime_ns
    assert before_access_ns != finalized.mtime_ns
    fs.reset_counts()

    published = fs.ensure_published_metadata(
        target,
        finalized,
        intended,
        preserve_created=True,
        apply_readonly=True,
    )

    assert published.size == len(b"payload")
    assert fs.stat_calls == 1
    assert fs.open_calls == 0
    assert fs.flush_calls == 0
    assert target.stat(follow_symlinks=False).st_atime_ns == before_access_ns


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_deferred_readonly_repairs_once_and_returns_the_final_handle_stat(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    temp = tmp_path / "temp.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"payload")
    temp.write_bytes(b"payload")
    fs = PublishedMetadataSpyFileSystem()
    intended = fs.stat_path(source)
    assert intended is not None
    intended = replace(
        intended,
        metadata=replace(
            intended.metadata,
            attributes=intended.metadata.attributes | 0x1,
        ),
    )
    finalized = fs.finalize_temp(
        temp, intended, preserve_created=True, acl_source=None
    )
    assert not finalized.metadata.attributes & 0x1
    fs.publish_new(temp, target)
    fs.reset_counts()

    try:
        published = fs.ensure_published_metadata(
            target,
            finalized,
            intended,
            preserve_created=True,
            apply_readonly=True,
        )

        assert published.metadata.attributes & 0x1
        assert fs.stat_calls == 1
        assert fs.open_calls == 1
        assert fs.flush_calls == 1
    finally:
        fs.clear_readonly(target)


class PublishedRepairResultFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.returned_stat: FileStat | None = None
        self.repairs = 0

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        self.repairs += 1
        self.returned_stat = super().ensure_published_metadata(
            path, *args, **kwargs
        )
        return self.returned_stat


class NoRepairReuseFileSystem(NativeFileSystem):
    def __init__(self, published_path: Path) -> None:
        self.published_path = published_path
        self.comparison_stat: FileStat | None = None
        self.returned_stat: FileStat | None = None
        self.target_comparisons = 0
        self.target_metadata_opens = 0

    def _stat_path(self, path: Path) -> FileStat | None:
        result = super()._stat_path(path)
        if path == self.published_path and result is not None:
            self.target_comparisons += 1
            self.comparison_stat = result
        return result

    def _open_metadata_handle(self, path: Path) -> int:
        if path == self.published_path:
            self.target_metadata_opens += 1
        return super()._open_metadata_handle(path)

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        result = super().ensure_published_metadata(path, *args, **kwargs)
        if path == self.published_path:
            assert result is self.comparison_stat
            self.returned_stat = result
        return result


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_clean_copy_reuses_exact_postpublish_comparison_stat_for_attestation(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    published_path = target / "file.bin"
    (source / "file.bin").write_bytes(b"clean-publish")
    fs = NoRepairReuseFileSystem(published_path)
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
    )

    _, _, attestation = recorder.calls[0]
    assert result.status is SessionState.COMPLETED
    assert fs.target_comparisons == 1
    assert fs.target_metadata_opens == 0
    assert fs.comparison_stat is fs.returned_stat
    assert attestation.subject is fs.returned_stat


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_copy_attests_to_exact_postpublish_repair_stat(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"post-repair")
    fs = PublishedRepairResultFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    intended = replace(
        source_stat,
        metadata=replace(
            source_stat.metadata,
            attributes=source_stat.metadata.attributes | 0x1,
        ),
    )
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=intended,
    )

    try:
        result, _, recorder = _run(
            _xset(_plan(source, target, (operation,))),
            fs=fs,
        )

        _, _, attestation = recorder.calls[0]
        assert result.status is SessionState.COMPLETED
        assert fs.repairs == 1
        assert fs.returned_stat is not None
        assert fs.returned_stat.metadata.attributes & 0x1
        assert attestation.subject is fs.returned_stat
    finally:
        published = target / "file.bin"
        if published.exists():
            fs.clear_readonly(published)


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_attribute_repair_preserves_atime_and_source_attributes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    temp = tmp_path / "temp.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"payload")
    temp.write_bytes(b"payload")
    fs = PublishedMetadataSpyFileSystem()
    intended = fs.stat_path(source)
    assert intended is not None
    intended = replace(
        intended,
        metadata=replace(
            intended.metadata,
            attributes=(
                intended.metadata.attributes
                | 0x1  # readonly
                | 0x2  # hidden
                | 0x4  # system
                | 0x2000  # not-content-indexed
            ),
            created_ns=None,
        ),
    )
    temp_created = fs.stat_path(temp)
    assert temp_created is not None
    finalized = fs.finalize_temp(
        temp, intended, preserve_created=True, acl_source=None
    )
    assert finalized.metadata.created_ns == temp_created.metadata.created_ns
    assert finalized.metadata.attributes & 0x2000
    assert not finalized.metadata.attributes & 0x1
    fs.publish_new(temp, target)
    before_repair = fs.stat_path(target)
    assert before_repair is not None
    wrong_access = max(0, finalized.mtime_ns - 1_000_000_000)
    os.utime(target, ns=(wrong_access, finalized.mtime_ns))
    before_access_ns = target.stat(follow_symlinks=False).st_atime_ns
    fs.reset_counts()

    try:
        published = fs.ensure_published_metadata(
            target,
            finalized,
            intended,
            preserve_created=True,
            apply_readonly=True,
        )
        target_info = target.stat(follow_symlinks=False)

        assert target_info.st_atime_ns == before_access_ns
        assert published.metadata.created_ns == before_repair.metadata.created_ns
        assert published.metadata.attributes & 0x1
        assert published.metadata.attributes & 0x2
        assert published.metadata.attributes & 0x4
        assert published.metadata.attributes & 0x2000
        assert fs.stat_calls == 1
        assert fs.open_calls == 1
        assert fs.flush_calls == 1
    finally:
        fs.clear_readonly(target)


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_name_tunneled_creation_and_readonly_repair_only_changed_fields(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    temp = tmp_path / "temp.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"payload")
    temp.write_bytes(b"payload")
    fs = PublishedMetadataSpyFileSystem()
    intended = fs.stat_path(source)
    assert intended is not None and intended.metadata.created_ns is not None
    intended = replace(
        intended,
        metadata=replace(
            intended.metadata,
            attributes=intended.metadata.attributes | 0x1,
        ),
    )
    finalized = fs.finalize_temp(
        temp, intended, preserve_created=True, acl_source=None
    )
    assert finalized.metadata.created_ns is not None
    assert not finalized.metadata.attributes & 0x1
    fs.publish_new(temp, target)
    fs._set_creation_time(
        target, max(0, finalized.metadata.created_ns - 1_000_000_000)
    )
    before = target.stat(follow_symlinks=False)
    before_attributes = fs._get_attributes(target)
    fs.reset_counts()

    try:
        published = fs.ensure_published_metadata(
            target,
            finalized,
            intended,
            preserve_created=True,
            apply_readonly=True,
        )
        after = target.stat(follow_symlinks=False)

        assert published.metadata.created_ns == finalized.metadata.created_ns
        assert published.metadata.attributes & 0x1
        assert after.st_mtime_ns == before.st_mtime_ns
        assert after.st_atime_ns == before.st_atime_ns
        assert (
            fs._get_attributes(target)
            == before_attributes | 0x1
        )
        assert fs.stat_calls == 1
        assert fs.open_calls == 1
        assert fs.flush_calls == 1
    finally:
        fs.clear_readonly(target)


@pytest.mark.skipif(os.name != "nt", reason="requires native metadata handles")
def test_normalized_timestamp_rounding_does_not_trigger_publish_repair(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    temp = tmp_path / "temp.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"payload")
    temp.write_bytes(b"payload")
    fs = PublishedMetadataSpyFileSystem()
    intended = fs.stat_path(source)
    assert intended is not None
    intended = replace(intended, mtime_ns=intended.mtime_ns + 37)
    finalized = fs.finalize_temp(
        temp, intended, preserve_created=True, acl_source=None
    )
    assert finalized.mtime_ns != intended.mtime_ns
    fs.publish_new(temp, target)
    fs.reset_counts()

    published = fs.ensure_published_metadata(
        target,
        finalized,
        intended,
        preserve_created=True,
        apply_readonly=True,
    )

    assert published.mtime_ns == finalized.mtime_ns
    assert fs.stat_calls == 1
    assert fs.open_calls == 0
    assert fs.flush_calls == 0


@pytest.mark.skipif(os.name != "nt", reason="requires Windows filename casing")
def test_native_atomic_replace_uses_requested_destination_casing(tmp_path: Path) -> None:
    _, target = _roots(tmp_path)
    existing = target / "keep.txt"
    replacement = target / "replacement.tmp"
    existing.write_bytes(b"old")
    replacement.write_bytes(b"new")

    NativeFileSystem().replace(replacement, target / "KEEP.txt")

    assert [path.name for path in target.iterdir()] == ["KEEP.txt"]
    assert (target / "KEEP.txt").read_bytes() == b"new"


class UnavailableDirectoryFlushFileSystem(NativeFileSystem):
    def flush_directory(self, path: Path) -> bool:
        return False


def test_unavailable_directory_flush_remains_an_honest_warning(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"content")
    fs = UnavailableDirectoryFlushFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )

    result, events, _ = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    item = _item_outcome(events)
    assert result.status is SessionState.COMPLETED
    assert item.detail["durability_warnings"] == (
        f"parent directory flush unsupported: {target}",
    )


@pytest.mark.skipif(os.name != "nt", reason="requires native durability handles")
def test_published_copy_metadata_survives_process_exit_after_record(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    payload = b"durable-before-record"
    source_path = source / "file.bin"
    source_path.write_bytes(payload)
    parent_fs = NativeFileSystem()
    source_stat = parent_fs.stat_path(source_path)
    assert source_stat is not None
    intended_mask = 0x1 | 0x2 | 0x2000
    parent_fs.apply_metadata(
        source_path,
        replace(
            source_stat,
            metadata=replace(
                source_stat.metadata,
                attributes=source_stat.metadata.attributes | intended_mask,
            ),
        ),
        preserve_created=True,
        apply_readonly=True,
    )
    source_stat = parent_fs.stat_path(source_path)
    assert source_stat is not None
    marker = tmp_path / "recorded.marker"
    child = textwrap.dedent(
        """
        import os
        from pathlib import Path
        import runpy
        import sys

        sys.path.insert(0, str(Path(sys.argv[1]).parent))
        ns = runpy.run_path(sys.argv[1])
        source = Path(sys.argv[2])
        target = Path(sys.argv[3])
        marker = Path(sys.argv[4])
        windows = ns["executor_module"]._WINDOWS
        if windows is None:
            os._exit(90)
        native_flush = windows.flush_file_buffers
        handle_events = []

        def observe_native_flush(handle):
            handle_events.append(("native-flush", None, handle))
            return native_flush(handle)

        windows.flush_file_buffers = observe_native_flush

        class FlushObservedFileSystem(ns["NativeFileSystem"]):
            def __init__(self):
                self.directory_flushed = False

            def _open_metadata_handle(self, path):
                handle = super()._open_metadata_handle(path)
                handle_events.append(("open", path, handle))
                return handle

            def _set_basic_info(self, handle, basic):
                handle_events.append(("basic", None, handle))
                return super()._set_basic_info(handle, basic)

            def _close_handle(self, handle):
                handle_events.append(("close", None, handle))
                return super()._close_handle(handle)

            def flush_directory(self, path):
                result = super().flush_directory(path)
                self.directory_flushed = True
                return result

        fs = FlushObservedFileSystem()
        source_stat = fs.stat(source, "file.bin")
        if source_stat is None:
            os._exit(90)
        operation = ns["_operation"](
            1,
            ns["OperationKind"].COPY,
            source_rel_path="file.bin",
            target_rel_path="file.bin",
            source_expected=source_stat,
            target_expected=None,
            intended=source_stat,
        )

        class ExitAtRecord(ns["FakeRecorder"]):
            def record_copied(self, op, attestation):
                if not fs.directory_flushed:
                    os._exit(24)
                temp_open_indexes = [
                    index
                    for index, (kind, path, _handle) in enumerate(handle_events)
                    if kind == "open" and ".synctmp-" in path.name
                ]
                if len(temp_open_indexes) != 1:
                    os._exit(25)
                open_index = temp_open_indexes[0]
                temp_handle = handle_events[open_index][2]
                close_index = next(
                    (
                        index
                        for index in range(open_index + 1, len(handle_events))
                        if handle_events[index]
                        == ("close", None, temp_handle)
                    ),
                    None,
                )
                if close_index is None:
                    os._exit(25)
                lifecycle = [
                    (kind, handle)
                    for kind, _path, handle in handle_events[
                        open_index : close_index + 1
                    ]
                ]
                if lifecycle != [
                    ("open", temp_handle),
                    ("basic", temp_handle),
                    ("native-flush", temp_handle),
                    ("close", temp_handle),
                ]:
                    os._exit(25)
                with marker.open("wb", buffering=0) as stream:
                    stream.write(attestation.content.digest.hex().encode("ascii"))
                    os.fsync(stream.fileno())
                return super().record_copied(op, attestation)

        def emit(event):
            if isinstance(event, ns["ItemOutcome"]) and event.outcome is ns["Outcome"].SUCCEEDED:
                if not fs.directory_flushed or not marker.exists():
                    os._exit(24)
                os._exit(23)

        ns["execute"](
            ns["_xset"](ns["_plan"](source, target, (operation,))),
            ns["RunContext"](emit, lambda: None),
            ExitAtRecord(),
            ns["_policies"](),
            fs,
        )
        os._exit(99)
        """
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            child,
            str(Path(__file__).resolve()),
            str(source),
            str(target),
            str(marker),
        ],
        check=False,
        timeout=30,
    )

    published = target / "file.bin"
    try:
        published_stat = parent_fs.stat_path(published)
        assert completed.returncode == 23
        assert marker.read_text(encoding="ascii") == xxh3_128(payload).hexdigest()
        assert published.read_bytes() == payload
        assert published_stat is not None
        assert published_stat.mtime_ns == source_stat.mtime_ns
        assert (
            published_stat.metadata.created_ns
            == source_stat.metadata.created_ns
        )
        assert (
            published_stat.metadata.attributes & intended_mask
            == source_stat.metadata.attributes & intended_mask
        )
        assert not list(target.glob("*.synctmp-*"))
    finally:
        parent_fs.clear_readonly(source_path)
        if published.exists():
            parent_fs.clear_readonly(published)


def test_executor_live_stat_matches_native_scanner_evidence(tmp_path: Path) -> None:
    source, _ = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"evidence")
    scanned = scan(
        Root(str(source), "source"),
        IgnoreSet(),
        RunContext(lambda _: None, lambda: None),
    )

    assert scanned.complete
    assert len(scanned.files) == 1
    actual = NativeFileSystem().stat(source, "file.bin")
    assert actual is not None
    assert replace(actual, file_identity=scanned.files[0].stat.file_identity) == scanned.files[0].stat


def test_exact_temp_recovery_preserves_user_lookalike(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    exact = fs.owned_temp(target / "file.bin", RUN_ID, operation.op_id)
    with fs.create_temp(
        exact, allocation_size=_PREALLOCATION_THRESHOLD
    ) as orphan:
        orphan.write(b"orphan")
    lookalike = target / "notes.synctmp-user.txt"
    lookalike.write_bytes(b"user")

    result, _, _ = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert not exact.exists()
    assert lookalike.read_bytes() == b"user"


def test_orphan_temp_sweep_is_exact_scoped_and_preserves_current_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target"
    touched = target / "touched"
    untouched = target / "untouched"
    trash = target / ".synctrash"
    off_volume = target / "off-volume"
    for directory in (touched, untouched, trash, off_volume):
        directory.mkdir(parents=True)
    fs = NativeFileSystem()
    old_run = validated_run_id("2" * 32)
    old_op = OpId("3" * 32)
    old_preallocated_op = OpId("5" * 32)
    current_op = OpId("4" * 32)
    old_temp = fs.owned_temp(touched / "old.bin", old_run, old_op)
    old_preallocated = fs.owned_temp(
        touched / "preallocated.bin", old_run, old_preallocated_op
    )
    current_temp = fs.owned_temp(touched / "current.bin", RUN_ID, current_op)
    untouched_temp = fs.owned_temp(untouched / "later.bin", old_run, old_op)
    trash_temp = fs.owned_temp(trash / "backup.bin", old_run, old_op)
    off_volume_temp = fs.owned_temp(off_volume / "mounted.bin", old_run, old_op)
    lookalike = touched / "notes.synctmp-user.txt"
    exact_directory = fs.owned_temp(touched / "directory", old_run, old_op)
    old_temp.write_bytes(b"old")
    with fs.create_temp(
        old_preallocated, allocation_size=_PREALLOCATION_THRESHOLD
    ) as stream:
        stream.write(b"preallocated")
    current_temp.write_bytes(b"current")
    untouched_temp.write_bytes(b"untouched")
    trash_temp.write_bytes(b"trash")
    off_volume_temp.write_bytes(b"mounted")
    lookalike.write_bytes(b"user")
    exact_directory.mkdir()
    native_volume = fs._volume_serial
    monkeypatch.setattr(
        fs,
        "_volume_serial",
        lambda path: "off-volume" if path.name == "off-volume" else native_volume(path),
    )

    fs.remove_orphaned_temps(
        target,
        frozenset({"touched", ".synctrash", "off-volume"}),
        RUN_ID,
    )

    assert not old_temp.exists()
    assert not old_preallocated.exists()
    assert current_temp.read_bytes() == b"current"
    assert untouched_temp.read_bytes() == b"untouched"
    assert trash_temp.read_bytes() == b"trash"
    assert off_volume_temp.read_bytes() == b"mounted"
    assert lookalike.read_bytes() == b"user"
    assert exact_directory.is_dir()


class CountingCopyBackend:
    def __init__(self) -> None:
        self.native = NativeCopyBackend(hasher_factory=xxh3_128)
        self.calls = 0

    def copy(self, *args, **kwargs) -> CopyDigest:
        self.calls += 1
        return self.native.copy(*args, **kwargs)


class ReadRecordingStream:
    def __init__(self, stream, requests: list[int]) -> None:
        self.stream = stream
        self.requests = requests

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def read(self, size: int) -> bytes:
        self.requests.append(size)
        return self.stream.read(size)

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


class BackupShapeFileSystem(NativeFileSystem):
    def __init__(self, source_path: Path, old_target: Path) -> None:
        self.source_path = source_path
        self.old_target = old_target
        self.read_requests: dict[Path, list[int]] = {
            source_path: [],
            old_target: [],
        }
        self.temp_requests: list[tuple[Path, int | None]] = []
        self.finalized_paths: list[Path] = []
        self.finalization_flushes: list[tuple[Path, int]] = []
        self.security_pairs: list[tuple[Path, Path]] = []
        self.writer_flushes = 0
        self.handle_flushes = 0

    def open_source(self, path: Path):
        stream = super().open_source(path)
        return ReadRecordingStream(stream, self.read_requests[path])

    def create_temp(self, path: Path, *, allocation_size: int | None):
        self.temp_requests.append((path, allocation_size))
        return super().create_temp(path, allocation_size=allocation_size)

    def finalize_temp(self, path: Path, *args, **kwargs) -> FileStat:
        before = self.handle_flushes
        self.finalized_paths.append(path)
        result = super().finalize_temp(path, *args, **kwargs)
        self.finalization_flushes.append(
            (path, self.handle_flushes - before)
        )
        return result

    def flush_file(self, stream) -> None:
        self.writer_flushes += 1
        super().flush_file(stream)

    def _flush_handle(self, handle) -> None:
        self.handle_flushes += 1
        super()._flush_handle(handle)

    def copy_security(self, source: Path, target: Path) -> None:
        self.security_pairs.append((source, target))


def test_copied_backup_stays_serial_hashless_fixed_chunk_and_unallocated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    old_target = target / "file.bin"
    source_path.write_bytes(b"n" * (9 * 1024 * 1024))
    old_target.write_bytes(b"o" * (9 * 1024 * 1024))
    fs = BackupShapeFileSystem(source_path, old_target)
    source_stat = fs.stat(source, "file.bin")
    old_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=old_stat,
        intended=source_stat,
    )
    backend = CountingCopyBackend()
    worker_names: list[str | None] = []
    real_thread = executor_pipeline.Thread

    def recording_thread(*args, **kwargs):
        worker_names.append(kwargs.get("name"))
        return real_thread(*args, **kwargs)

    monkeypatch.setattr(executor_pipeline, "Thread", recording_thread)

    result, _, _ = _run(
        _xset(
            _plan(
                source,
                target,
                (operation,),
                hardlinks=False,
                preservation=PreservationPolicy(preserve_acl=True),
            )
        ),
        fs=fs,
        policies=_policies(
            copy_backend=backend,
            max_chunk_size=4 * 1024 * 1024,
        ),
    )

    trash_root = target / ".synctrash"
    backup_temps = [
        (path, allocation)
        for path, allocation in fs.temp_requests
        if trash_root in path.parents
    ]
    assert result.status is SessionState.COMPLETED
    assert backend.calls == 1
    assert set(fs.read_requests[old_target]) == {4 * 1024 * 1024}
    assert set(fs.read_requests[source_path]) == {1024 * 1024}
    assert len(backup_temps) == 1 and backup_temps[0][1] is None
    assert backup_temps[0][0] in fs.finalized_paths
    assert fs.writer_flushes == 0
    assert dict(fs.finalization_flushes)[backup_temps[0][0]] == 1
    assert worker_names == [
        "namisync-copy-hasher",
        "namisync-copy-writer",
    ]
    assert fs.security_pairs == [
        (
            source_path,
            next(
                path
                for path, _ in fs.temp_requests
                if trash_root not in path.parents
            ),
        )
    ]


class MutatingBackupStream:
    def __init__(self, stream, path: Path, mutation: str) -> None:
        self.stream = stream
        self.path = path
        self.mutation = mutation
        self.mutated = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def read(self, size: int) -> bytes:
        chunk = self.stream.read(size)
        if chunk and not self.mutated:
            before = self.path.stat(follow_symlinks=False)
            if self.mutation == "grow":
                with self.path.open("ab", buffering=0) as writer:
                    writer.write(b"-external-growth")
            elif self.mutation == "shrink":
                with self.path.open("r+b", buffering=0) as writer:
                    writer.truncate(0)
            else:
                with self.path.open("r+b", buffering=0) as writer:
                    writer.write(b"X" * before.st_size)
                os.utime(
                    self.path,
                    ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000),
                )
            self.mutated = True
        return chunk

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


class MutatingCopiedBackupFileSystem(NativeFileSystem):
    def __init__(self, live: Path, mutation: str) -> None:
        self.live = live
        self.mutation = mutation
        self.backup_publish_calls = 0
        self.replace_calls = 0

    def open_source(self, path: Path):
        stream = super().open_source(path)
        if path != self.live:
            return stream
        return MutatingBackupStream(stream, path, self.mutation)

    def publish_new(self, temp: Path, target: Path) -> None:
        if ".synctrash" in target.parts:
            self.backup_publish_calls += 1
        super().publish_new(temp, target)

    def replace(self, temp: Path, target: Path) -> None:
        self.replace_calls += 1
        super().replace(temp, target)


class CopiedBackupPublicationSpyFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.backup_publish_calls = 0
        self.replace_calls = 0

    def publish_new(self, temp: Path, target: Path) -> None:
        if ".synctrash" in target.parts:
            self.backup_publish_calls += 1
        super().publish_new(temp, target)

    def replace(self, temp: Path, target: Path) -> None:
        self.replace_calls += 1
        super().replace(temp, target)


def test_copied_backup_does_not_adopt_target_drift_after_reviewed_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    live = target / "file.bin"
    source_path.write_bytes(b"new-version")
    live.write_bytes(b"old-version")
    fs = CopiedBackupPublicationSpyFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    real_require_stat_path = executor_runtime._require_stat_path
    mutated = False

    def mutate_after_reviewed_guard(filesystem, path: Path) -> FileStat:
        nonlocal mutated
        if not mutated and ".synctmp-" in path.name:
            live.write_bytes(b"external-version-is-different")
            mutated = True
        return real_require_stat_path(filesystem, path)

    monkeypatch.setattr(
        executor_runtime,
        "_require_stat_path",
        mutate_after_reviewed_guard,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)),
        fs=fs,
    )

    item = _item_outcome(events)
    backup = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert mutated
    assert result.status is SessionState.FAILED
    assert item.reason == "target-drift"
    assert item.detail["message"] == (
        "live update target drifted before its backup was copied"
    )
    assert live.read_bytes() == b"external-version-is-different"
    assert fs.backup_publish_calls == 0
    assert fs.replace_calls == 0
    assert not backup.exists()
    assert not list(target.rglob("*.synctmp-*"))
    assert recorder.calls == []


@pytest.mark.parametrize(
    ("mutation", "expected_live"),
    [
        ("grow", b"old-version-external-growth"),
        ("shrink", b""),
        ("rewrite", b"X" * len(b"old-version")),
    ],
)
def test_copied_backup_rejects_live_drift_before_backup_or_update_publish(
    tmp_path: Path,
    mutation: str,
    expected_live: bytes,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    live = target / "file.bin"
    source_path.write_bytes(b"new-version")
    live.write_bytes(b"old-version")
    fs = MutatingCopiedBackupFileSystem(live, mutation)
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)),
        fs=fs,
    )

    item = _item_outcome(events)
    backup = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert result.status is SessionState.FAILED
    assert item.reason == "target-drift"
    assert item.detail["message"] == (
        "live update target drifted while its backup was copied"
    )
    assert live.read_bytes() == expected_live
    assert fs.backup_publish_calls == 0
    assert fs.replace_calls == 0
    assert not backup.exists()
    assert not list(target.rglob("*.synctmp-*"))
    assert recorder.calls == []


class FailingBackupWriter:
    def __init__(self, stream) -> None:
        self.stream = stream

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def write(self, _data) -> int:
        raise OSError("injected backup write failure")

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


class BackupFailureFileSystem(NativeFileSystem):
    def __init__(self, failure: str) -> None:
        self.failure = failure

    def create_temp(self, path: Path, *, allocation_size: int | None):
        stream = super().create_temp(path, allocation_size=allocation_size)
        if self.failure == "write":
            return FailingBackupWriter(stream)
        return stream

    def finalize_temp(self, path: Path, *args, **kwargs) -> FileStat:
        if self.failure == "finalize":
            raise OSError("injected backup finalization failure")
        return super().finalize_temp(path, *args, **kwargs)


class BackupCleanupDiagnosticFileSystem(BackupFailureFileSystem):
    def __init__(self) -> None:
        super().__init__("write")

    def remove_owned_temp(self, path: Path) -> None:
        native = to_extended_length_path(str(path))
        raise PermissionError(13, "cleanup denied", native)


class BackupFinalizationSpyFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.finalize_calls = 0

    def finalize_temp(self, path: Path, *args, **kwargs) -> FileStat:
        self.finalize_calls += 1
        return super().finalize_temp(path, *args, **kwargs)


class BackupTempCreationSpyFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.source_opened = False
        self.create_calls = 0

    def open_source(self, path: Path):
        stream = super().open_source(path)
        self.source_opened = True
        return stream

    def create_temp(self, path: Path, *, allocation_size: int | None):
        self.create_calls += 1
        return super().create_temp(path, allocation_size=allocation_size)


class UpdateSourceGuardTrashSwapFileSystem(NativeFileSystem):
    def __init__(
        self,
        source_root: Path,
        target_root: Path,
        redirected_root: Path,
    ) -> None:
        self.source_root = source_root
        self.target_root = target_root
        self.redirected_root = redirected_root
        self.detached_root = target_root / f".detached-trash-{RUN_ID}"
        self.backup_created = False
        self.swapped = False
        self.replace_calls = 0

    def hardlink(self, source: Path, target: Path) -> None:
        super().hardlink(source, target)
        if ".synctrash" in target.parts:
            self.backup_created = True

    def copy_backup(
        self,
        source,
        temp,
        target,
        source_expected,
        checkpoint,
        validate_destination,
    ) -> None:
        super().copy_backup(
            source,
            temp,
            target,
            source_expected,
            checkpoint,
            validate_destination,
        )
        self.backup_created = True

    def stat(self, root: Path, relative_path: str) -> FileStat | None:
        actual = super().stat(root, relative_path)
        if root == self.source_root and self.backup_created and not self.swapped:
            run_root = self.target_root / ".synctrash" / str(RUN_ID)
            run_root.rename(self.detached_root)
            _create_directory_reparse(run_root, self.redirected_root)
            self.swapped = True
        return actual

    def replace(self, temp: Path, target: Path) -> None:
        self.replace_calls += 1
        super().replace(temp, target)


@pytest.mark.parametrize("failure", ["cancel", "write", "finalize"])
def test_copied_backup_removes_its_temp_on_every_prepublish_failure(
    tmp_path: Path, failure: str
) -> None:
    target = tmp_path / "target"
    trash = target / ".synctrash" / str(RUN_ID)
    trash.mkdir(parents=True)
    live = target / "file.bin"
    live.write_bytes(b"old-version")
    backup = trash / "file.bin"
    fs = BackupFailureFileSystem(failure)
    temp = fs.owned_temp(backup, RUN_ID, OpId("2" * 32))
    live_stat = fs.stat_path(live)
    assert live_stat is not None

    def checkpoint() -> None:
        if failure == "cancel":
            raise Canceled()

    expected_error = Canceled if failure == "cancel" else OSError
    with pytest.raises(expected_error):
        fs.copy_backup(
            live,
            temp,
            backup,
            live_stat,
            checkpoint,
            lambda: None,
        )

    assert live.read_bytes() == b"old-version"
    assert not backup.exists()
    assert not list(target.rglob("*.synctmp-*"))


def test_copied_backup_cleanup_note_sanitizes_native_filename(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    trash = target / ".synctrash" / str(RUN_ID)
    trash.mkdir(parents=True)
    live = target / "file.bin"
    live.write_bytes(b"old-version")
    backup = trash / "file.bin"
    fs = BackupCleanupDiagnosticFileSystem()
    temp = fs.owned_temp(backup, RUN_ID, OpId("2" * 32))
    live_stat = fs.stat_path(live)
    assert live_stat is not None

    with pytest.raises(OSError) as captured:
        fs.copy_backup(
            live,
            temp,
            backup,
            live_stat,
            lambda: None,
            lambda: None,
        )

    notes = captured.value.__notes__
    assert len(notes) == 1
    assert r"file.bin.synctmp-" in notes[0]
    assert "\\\\?\\" not in notes[0]


def test_copied_backup_revalidates_parent_before_temp_finalization(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    trash = target / ".synctrash" / str(RUN_ID)
    trash.mkdir(parents=True)
    live = target / "file.bin"
    live.write_bytes(b"old-version")
    backup = trash / "file.bin"
    fs = BackupFinalizationSpyFileSystem()
    temp = fs.owned_temp(backup, RUN_ID, OpId("2" * 32))
    live_stat = fs.stat_path(live)
    assert live_stat is not None
    validations = 0

    def reject_redirected_parent() -> None:
        nonlocal validations
        validations += 1
        if validations >= 2:
            raise UnsafeExecutionPath("injected redirected trash parent")

    with pytest.raises(UnsafeExecutionPath, match="redirected trash parent"):
        fs.copy_backup(
            live,
            temp,
            backup,
            live_stat,
            lambda: None,
            reject_redirected_parent,
        )

    assert validations == 3
    assert fs.finalize_calls == 0
    assert temp.exists()
    assert not backup.exists()


def test_copied_backup_revalidates_parent_after_source_open_before_temp_create(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    trash = target / ".synctrash" / str(RUN_ID)
    trash.mkdir(parents=True)
    live = target / "file.bin"
    live.write_bytes(b"old-version")
    backup = trash / "file.bin"
    fs = BackupTempCreationSpyFileSystem()
    temp = fs.owned_temp(backup, RUN_ID, OpId("2" * 32))
    live_stat = fs.stat_path(live)
    assert live_stat is not None
    validations = 0

    def reject_redirect_after_source_open() -> None:
        nonlocal validations
        validations += 1
        if fs.source_opened:
            raise UnsafeExecutionPath("injected source-open parent redirect")

    with pytest.raises(UnsafeExecutionPath, match="source-open parent redirect"):
        fs.copy_backup(
            live,
            temp,
            backup,
            live_stat,
            lambda: None,
            reject_redirect_after_source_open,
        )

    assert validations == 2
    assert fs.create_calls == 0
    assert not temp.exists()
    assert not backup.exists()


@pytest.mark.parametrize("hardlinks", [True, False], ids=("hardlink", "copy"))
def test_update_revalidates_trash_parent_after_guards_before_replace(
    tmp_path: Path,
    hardlinks: bool,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    live = target / "file.bin"
    source_path.write_bytes(b"new-version")
    live.write_bytes(b"old-version")
    redirected = tmp_path / "redirected-trash"
    redirected.mkdir()
    _require_directory_reparse(tmp_path, redirected)
    fs = UpdateSourceGuardTrashSwapFileSystem(source, target, redirected)
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=hardlinks)),
        fs=fs,
    )

    item = _item_outcome(events)
    assert fs.swapped
    assert fs.replace_calls == 0
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.OK
    assert item.outcome is Outcome.FAILED
    assert item.reason == "unsafe-path"
    assert "publish_state" not in item.detail
    assert live.read_bytes() == b"old-version"
    assert (fs.detached_root / "file.bin").read_bytes() == b"old-version"
    assert not list(redirected.iterdir())
    assert recorder.calls == []


def test_no_hardlink_update_flushes_readonly_backup_before_readonly(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new")
    live = target / "file.bin"
    live.write_bytes(b"old")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    old = fs.stat(target, "file.bin")
    assert source_stat is not None and old is not None
    fs.apply_metadata(
        live,
        replace(old, metadata=replace(old.metadata, attributes=old.metadata.attributes | 1)),
        preserve_created=True,
        apply_readonly=True,
    )
    old = fs.stat(target, "file.bin")
    assert old is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=old,
        intended=source_stat,
    )

    result, _, _ = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)), fs=fs
    )

    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    trash_stat = fs.stat_path(trash)
    assert result.status is SessionState.COMPLETED
    assert trash.read_bytes() == b"old"
    assert trash_stat is not None and trash_stat.metadata.attributes & 1


class HardlinkRepairFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.flushes = 0
        self.repairs: list[tuple[Path, int, FileStat]] = []

    def _flush_handle(self, handle) -> None:
        self.flushes += 1
        super()._flush_handle(handle)

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        before = self.flushes
        result = super().ensure_published_metadata(path, *args, **kwargs)
        self.repairs.append((path, self.flushes - before, result))
        return result


class RepairAwareRecorder(FakeRecorder):
    def __init__(self, fs: HardlinkRepairFileSystem, trash: Path) -> None:
        super().__init__()
        self.fs = fs
        self.trash = trash

    def record_updated(self, op, attestation) -> RecordedCopyIdentity:
        trash_repairs = [
            (flushes, stat)
            for path, flushes, stat in self.fs.repairs
            if path == self.trash
        ]
        assert trash_repairs
        assert trash_repairs[-1][0] == 1
        assert trash_repairs[-1][1].metadata.attributes & 1
        return super().record_updated(op, attestation)


@pytest.mark.skipif(os.name != "nt", reason="requires NTFS hardlinks and readonly")
def test_hardlink_backup_restores_and_flushes_displaced_readonly_inode_before_record(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new")
    live = target / "file.bin"
    live.write_bytes(b"old")
    fs = HardlinkRepairFileSystem()
    source_stat = fs.stat(source, "file.bin")
    old = fs.stat(target, "file.bin")
    assert source_stat is not None and old is not None
    fs.apply_metadata(
        live,
        replace(
            old,
            metadata=replace(old.metadata, attributes=old.metadata.attributes | 1),
        ),
        preserve_created=True,
        apply_readonly=True,
    )
    old = fs.stat(target, "file.bin")
    assert old is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=old,
        intended=source_stat,
    )
    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    recorder = RepairAwareRecorder(fs, trash)

    result, _, _ = _run(
        _xset(_plan(source, target, (operation,), hardlinks=True)),
        fs=fs,
        recorder=recorder,
    )

    assert result.status is SessionState.COMPLETED
    assert trash.read_bytes() == b"old"
    live_stat = fs.stat_path(live)
    trash_stat = fs.stat_path(trash)
    assert live_stat is not None
    assert not live_stat.metadata.attributes & 0x1
    assert trash_stat is not None
    assert trash_stat.metadata.attributes & 0x1
    fs.clear_readonly(trash)


class HardlinkCompletionOrderFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.order: list[str] = []
        self.backup_metadata_completed = False

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        result = super().ensure_published_metadata(path, *args, **kwargs)
        if ".synctrash" in path.parts:
            self.order.append("backup-metadata")
            self.backup_metadata_completed = True
        else:
            self.order.append("target-metadata")
        return result


def test_update_hardlink_backup_metadata_completes_before_attestation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = HardlinkCompletionOrderFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )

    def fail_attestation(*_args, **_kwargs):
        assert fs.backup_metadata_completed
        fs.order.append("attestation")
        raise RuntimeError("injected attestation failure")

    monkeypatch.setattr(executor_runtime, "_attestation", fail_attestation)
    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=True)),
        fs=fs,
    )

    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert result.status is SessionState.FAILED
    assert fs.order == ["target-metadata", "backup-metadata", "attestation"]
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert trash.read_bytes() == b"old-version"
    assert recorder.calls == []


class AclFailureFileSystem(NativeFileSystem):
    def copy_security(self, source: Path, target: Path) -> None:
        raise PermissionError("ACL copy denied")


def test_acl_failure_happens_before_update_publish(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new")
    (target / "file.bin").write_bytes(b"old")
    fs = AclFailureFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    plan = _plan(
        source,
        target,
        (operation,),
        preservation=PreservationPolicy(preserve_acl=True),
    )

    result, events, recorder = _run(_xset(plan), fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / "file.bin").read_bytes() == b"old"
    assert recorder.calls == []
    assert _item_outcome(events).reason == "acl-copy-failed"
