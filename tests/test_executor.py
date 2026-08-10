"""M0 executor acceptance and PoC-regression tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import inspect
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Event, Lock
import textwrap
import time
from typing import Callable

import pytest
from xxhash import xxh3_128

import namisync.modules.executor as executor_module
from namisync.core.evidence import Outcome, Provenance, RecordingStatus
from namisync.core.events import ItemOutcome, Progress, Terminal, result_item_to_dict
from namisync.core.execution import (
    CopyDigest,
    ExecutionSet,
    RecordedCopyIdentity,
    Retry,
    RunId,
    Stop,
    validated_run_id,
)
from namisync.core.models import (
    CapabilityProfile,
    EntryKind,
    FileIdentity,
    FileStat,
    IgnoreSet,
    Root,
    VolumeId,
)
from namisync.core.pathing import to_extended_length_path
from namisync.core.planning import (
    Assignment,
    DeletionPolicy,
    FilterSet,
    OpId,
    OperationKind,
    OperationReason,
    Plan,
    PlanFingerprint,
    PlanOperation,
    PreservationPolicy,
)
from namisync.core.session import Canceled, PauseRequested, RunContext, SessionState
from namisync.modules.executor import (
    BoundedFailurePolicy,
    ExecutorPolicies,
    NativeCopyBackend,
    NativeFileSystem,
    SystemClock,
    UnsafeExecutionPath,
    _PREALLOCATION_THRESHOLD,
    _allocation_size,
    _copy_chunk_size,
    execute,
)
from namisync.modules.scanner import scan


RUN_ID = validated_run_id("1" * 32)


class FakeRecorder:
    def __init__(self, *, fail: str | None = None) -> None:
        self.fail = fail
        self.calls: list[tuple[str, object, object | None]] = []
        self.flushes = 0

    def _record(self, name: str, first: object, second: object | None = None) -> None:
        if self.fail == name:
            raise RuntimeError(f"injected {name} failure")
        self.calls.append((name, first, second))

    def flush(self) -> None:
        self.flushes += 1
        if self.fail == "flush":
            raise RuntimeError("injected flush failure")

    @staticmethod
    def _copy_identity(op: OpId) -> RecordedCopyIdentity:
        return RecordedCopyIdentity(
            row_id=f"row-{op}",
            location_id="target-location",
            scope_token=f"scope-{op}",
            rel_path_key=f"PATH-{op}".upper(),
        )

    def record_copied(self, op, attestation) -> RecordedCopyIdentity:
        self._record("copied", op, attestation)
        return self._copy_identity(op)

    def record_updated(self, op, attestation) -> RecordedCopyIdentity:
        self._record("updated", op, attestation)
        return self._copy_identity(op)

    def record_moved(self, op, target) -> None:
        self._record("moved", op, target)

    def record_recased(self, op, target) -> None:
        self._record("recased", op, target)

    def record_move_updated(self, op, attestation) -> RecordedCopyIdentity:
        self._record("move_updated", op, attestation)
        return self._copy_identity(op)

    def record_mkdir(self, op, target) -> None:
        self._record("mkdir", op, target)

    def record_trashed(self, op, trash_relative_path, target) -> None:
        self._record("trashed", op, (trash_relative_path, target))

    def record_deleted(self, op, prior) -> None:
        self._record("deleted", op, prior)

    def record_noop(self, op, source, target) -> None:
        self._record("noop", op, (source, target))


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 7, 18, 12, tzinfo=UTC)


def _profile(*, hardlinks: bool = True) -> CapabilityProfile:
    return CapabilityProfile(
        fs_type="NTFS",
        mtime_granularity_ns=100,
        stable_file_identity=True,
        incurs_seek_penalty=False,
        max_path=32767,
        supports_ads=True,
        supports_hardlinks=hardlinks,
    )


def _operation(
    number: int,
    kind: OperationKind,
    *,
    source_rel_path: str | None,
    target_rel_path: str,
    source_expected: FileStat | None,
    target_expected: FileStat | None,
    intended: FileStat | None,
    prior_target_rel_path: str | None = None,
    prior_target_expected: FileStat | None = None,
    dependencies: tuple[OpId, ...] = (),
    reason: OperationReason = OperationReason.SOURCE_ONLY,
) -> PlanOperation:
    return PlanOperation(
        op_id=OpId(f"{number:032x}"),
        kind=kind,
        source_rel_path=source_rel_path,
        target_rel_path=target_rel_path,
        source_expected=source_expected,
        target_expected=target_expected,
        intended=intended,
        prior_target_rel_path=prior_target_rel_path,
        prior_target_expected=prior_target_expected,
        metadata=None if intended is None else intended.metadata,
        content_bytes=(
            0
            if source_expected is None
            or kind not in {OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE}
            else source_expected.size
        ),
        dependencies=dependencies,
        reason=reason,
    )


def _plan(
    source: Path,
    target: Path,
    operations: tuple[PlanOperation, ...],
    *,
    hardlinks: bool = True,
    preservation: PreservationPolicy = PreservationPolicy(),
    trash_on_update: bool = True,
) -> Plan:
    profile = _profile(hardlinks=hardlinks)
    return Plan(
        source_root=Root(str(source), "source"),
        target_root=Root(str(target), "target"),
        source_volume_id=None,
        target_volume_id=None,
        source_volume_evidence=None,
        target_volume_evidence=None,
        source_profile=profile,
        target_profile=profile,
        source_complete=True,
        target_complete=True,
        operations=operations,
        assignment=Assignment("identity", "1", ()),
        preservation=preservation,
        filter_snapshot=FilterSet(),
        deletion_policy=DeletionPolicy.TRASH,
        trash_on_update=trash_on_update,
        policy_fingerprint="p" * 64,
        required_volumes=frozenset(),
        required_bytes=sum(operation.content_bytes for operation in operations),
        fingerprint=PlanFingerprint("f" * 64),
    )


def _xset(plan: Plan) -> ExecutionSet:
    return ExecutionSet(
        plan=plan,
        selection=frozenset(operation.op_id for operation in plan.operations),
        run_id=RUN_ID,
    )


def _policies(**changes: object) -> ExecutorPolicies:
    values: dict[str, object] = {
        "failure": BoundedFailurePolicy(retries=2, initial_delay=0),
        "copy_backend": NativeCopyBackend(hasher_factory=xxh3_128),
        "clock": FixedClock(),
        "max_chunk_size": 4,
        "progress_interval_seconds": 0,
        "sleep": lambda _: None,
    }
    values.update(changes)
    return ExecutorPolicies(**values)  # type: ignore[arg-type]


def _run(
    xset: ExecutionSet,
    *,
    fs: NativeFileSystem | None = None,
    recorder: FakeRecorder | None = None,
    policies: ExecutorPolicies | None = None,
    checkpoint: Callable[[], None] = lambda: None,
) -> tuple[object, list[object], FakeRecorder]:
    events: list[object] = []
    actual_recorder = recorder or FakeRecorder()
    result = execute(
        xset,
        RunContext(events.append, checkpoint),
        actual_recorder,
        policies or _policies(),
        fs or NativeFileSystem(),
    )
    return result, events, actual_recorder


def _roots(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    return source, target


def test_native_filesystem_rejects_lexical_root_before_resolving_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = tmp_path / "configured-root"
    fs = NativeFileSystem()
    observed: list[Path] = []

    def fail_if_followed(_path: Path, *, strict: bool) -> Path:
        raise AssertionError("configured root was followed before rejection")

    def reject_root(path: Path) -> None:
        observed.append(path)
        if path == configured:
            raise UnsafeExecutionPath("reparse points are not executable")

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
        executor_module,
        "trusted_volume_anchor",
        lambda _path: str(tmp_path),
    )
    monkeypatch.setattr(
        fs,
        "_reject_reparse_chain",
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


def test_copy_is_atomic_hashed_and_attested_to_published_target(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"complete-content")
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

    xset = _xset(_plan(source, target, (operation,)))
    result, events, recorder = _run(xset, fs=fs)

    assert result.status is SessionState.COMPLETED
    assert result.bytes_total == len(b"complete-content")
    assert (target / "file.bin").read_bytes() == b"complete-content"
    assert not list(target.glob("*.synctmp-*"))
    name, _, attestation = recorder.calls[0]
    assert name == "copied"
    assert set(xset.published_evidence) == {operation.op_id}
    published = xset.published_evidence[operation.op_id]
    assert published.attestation is attestation
    assert published.recorded_identity == recorder._copy_identity(operation.op_id)
    assert published.copy_recorded
    assert attestation.content.algorithm == "xxh3_128"
    assert attestation.content.digest == xxh3_128(b"complete-content").digest()
    assert attestation.content.provenance is Provenance.COPY_ATTESTED
    assert attestation.content.observed_at == FixedClock().now()
    assert attestation.subject.file_identity != source_stat.file_identity
    progress = [event for event in events if isinstance(event, Progress)]
    assert [event.bytes_done for event in progress] == sorted(
        event.bytes_done for event in progress
    )
    assert max(event.bytes_done for event in progress) == len(b"complete-content")
    assert not any(isinstance(event, Terminal) for event in events)
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert "durability_warnings" not in item.detail


@pytest.mark.parametrize(
    ("reviewed_size", "expected"),
    [
        (0, 256 * 1024),
        (8 * 1024 * 1024 - 1, 256 * 1024),
        (8 * 1024 * 1024, 1024 * 1024),
        (32 * 1024 * 1024 - 1, 1024 * 1024),
        (32 * 1024 * 1024, 4 * 1024 * 1024),
    ],
)
def test_adaptive_copy_chunk_bands_are_exact(
    reviewed_size: int, expected: int
) -> None:
    assert _copy_chunk_size(reviewed_size, 4 * 1024 * 1024) == expected
    assert _copy_chunk_size(reviewed_size, 128 * 1024) == 128 * 1024


def test_executor_rejects_a_nonpositive_maximum_chunk() -> None:
    with pytest.raises(ValueError, match="maximum copy chunk size"):
        _policies(max_chunk_size=0)


def test_native_copy_backend_requires_a_keyword_only_hasher_factory() -> None:
    with pytest.raises(TypeError):
        NativeCopyBackend()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        NativeCopyBackend(xxh3_128)  # type: ignore[misc]


def test_executor_policies_requires_an_explicit_copy_backend() -> None:
    with pytest.raises(TypeError):
        ExecutorPolicies()  # type: ignore[call-arg]


def test_copy_digest_accepts_only_raw_xxh3_128_width() -> None:
    assert CopyDigest(b"x" * 16, 0).digest == b"x" * 16
    with pytest.raises(ValueError, match="XXH3-128"):
        CopyDigest(b"x" * 32, 0)


def test_recorded_copy_identity_requires_a_canonical_relative_path_key() -> None:
    identity = FakeRecorder._copy_identity(OpId("1" * 32))

    with pytest.raises(ValueError, match="must be canonical"):
        replace(identity, rel_path_key="mixed\\Case.bin")


def test_xv_1_published_evidence_cardinality_and_atomic_emission_for_all_byte_kinds(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    for name, content in (
        ("copy.bin", b"copy"),
        ("update.bin", b"update-new"),
        ("moved.bin", b"move-new"),
        ("noop.bin", b"same"),
    ):
        (source / name).write_bytes(content)
    (target / "update.bin").write_bytes(b"update-old")
    (target / "old-moved.bin").write_bytes(b"move-old")
    (target / "noop.bin").write_bytes(b"same")
    fs = NativeFileSystem()
    source_stats = {
        name: fs.stat(source, name)
        for name in ("copy.bin", "update.bin", "moved.bin", "noop.bin")
    }
    target_update = fs.stat(target, "update.bin")
    target_old_move = fs.stat(target, "old-moved.bin")
    target_noop = fs.stat(target, "noop.bin")
    assert all(value is not None for value in source_stats.values())
    assert target_update is not None
    assert target_old_move is not None
    assert target_noop is not None
    operations = (
        _operation(
            1,
            OperationKind.COPY,
            source_rel_path="copy.bin",
            target_rel_path="copy.bin",
            source_expected=source_stats["copy.bin"],
            target_expected=None,
            intended=source_stats["copy.bin"],
        ),
        _operation(
            2,
            OperationKind.UPDATE,
            source_rel_path="update.bin",
            target_rel_path="update.bin",
            source_expected=source_stats["update.bin"],
            target_expected=target_update,
            intended=source_stats["update.bin"],
        ),
        _operation(
            3,
            OperationKind.MOVE_UPDATE,
            source_rel_path="moved.bin",
            target_rel_path="moved.bin",
            source_expected=source_stats["moved.bin"],
            target_expected=None,
            intended=source_stats["moved.bin"],
            prior_target_rel_path="old-moved.bin",
            prior_target_expected=target_old_move,
        ),
        _operation(
            4,
            OperationKind.NOOP,
            source_rel_path="noop.bin",
            target_rel_path="noop.bin",
            source_expected=source_stats["noop.bin"],
            target_expected=target_noop,
            intended=target_noop,
        ),
    )
    xset = _xset(_plan(source, target, operations))
    byte_ids = {
        operation.op_id
        for operation in operations
        if operation.kind
        in {
            OperationKind.COPY,
            OperationKind.UPDATE,
            OperationKind.MOVE_UPDATE,
        }
    }
    emitted: list[ItemOutcome] = []

    def emit(body: object) -> None:
        if not isinstance(body, ItemOutcome):
            return
        emitted.append(body)
        op_id = OpId(body.item_id)
        assert xset.status[op_id] is body.outcome
        if op_id in byte_ids:
            assert body.outcome is Outcome.SUCCEEDED
            assert op_id in xset.published_evidence
        else:
            assert op_id not in xset.published_evidence

    result = execute(
        xset,
        RunContext(emit, lambda: None),
        FakeRecorder(),
        _policies(),
        fs,
    )

    assert result.status is SessionState.COMPLETED
    assert {OpId(item.item_id) for item in emitted} == set(xset.selection)
    assert set(xset.published_evidence) == byte_ids
    assert all(
        evidence.copy_recorded
        and evidence.attestation.content.provenance
        is Provenance.COPY_ATTESTED
        for evidence in xset.published_evidence.values()
    )


def test_preallocation_policy_uses_the_measured_private_crossover() -> None:
    assert _allocation_size(0) is None
    assert _allocation_size(_PREALLOCATION_THRESHOLD - 1) is None
    assert _allocation_size(_PREALLOCATION_THRESHOLD) == _PREALLOCATION_THRESHOLD


class SizingCopyBackend:
    def __init__(self) -> None:
        self.chunk_sizes: list[int] = []

    def copy(
        self,
        source,
        target,
        *,
        chunk_size: int,
        checkpoint,
        on_chunk,
    ) -> CopyDigest:
        checkpoint()
        size = os.fstat(source.fileno()).st_size
        target.truncate(size)
        self.chunk_sizes.append(chunk_size)
        if size:
            on_chunk(size)
        return CopyDigest(xxh3_128(b"sizing-backend").digest(), size)


class AllocationRecordingFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.allocation_sizes: list[int | None] = []

    def create_temp(self, path: Path, *, allocation_size: int | None):
        self.allocation_sizes.append(allocation_size)
        return super().create_temp(path, allocation_size=None)


@pytest.mark.parametrize(
    "size",
    [
        0,
        8 * 1024 * 1024 - 1,
        8 * 1024 * 1024,
        32 * 1024 * 1024 - 1,
        32 * 1024 * 1024,
    ],
)
def test_prepare_copy_passes_actual_adaptive_chunk_and_allocation_request(
    tmp_path: Path, size: int
) -> None:
    case = tmp_path / f"size-{size}"
    case.mkdir()
    source, target = _roots(case)
    (source / "file.bin").write_bytes(b"")
    with (source / "file.bin").open("r+b") as stream:
        stream.truncate(size)
    fs = AllocationRecordingFileSystem()
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
    backend = SizingCopyBackend()

    result, _, _ = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(
            copy_backend=backend,
            max_chunk_size=4 * 1024 * 1024,
        ),
    )

    assert result.status is SessionState.COMPLETED
    assert backend.chunk_sizes == [
        _copy_chunk_size(size, 4 * 1024 * 1024)
    ]
    assert fs.allocation_sizes == [_allocation_size(size)]


class ConcurrencyProbeBackend:
    def __init__(self) -> None:
        self._lock = Lock()
        self._second_started = Event()
        self._calls = 0
        self._active = 0
        self.max_active = 0

    def copy(
        self,
        source,
        target,
        *,
        chunk_size: int,
        checkpoint,
        on_chunk,
    ) -> CopyDigest:
        del chunk_size
        with self._lock:
            self._calls += 1
            call = self._calls
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        if call == 1:
            self._second_started.wait(0.2)
        else:
            self._second_started.set()
        try:
            checkpoint()
            payload = source.read()
            assert target.write(payload) == len(payload)
            on_chunk(len(payload))
            return CopyDigest(xxh3_128(payload).digest(), len(payload))
        finally:
            with self._lock:
                self._active -= 1


def test_b19_executor_streams_at_most_one_file_at_a_time(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operations: list[PlanOperation] = []
    for number in (1, 2):
        name = f"file-{number}.bin"
        (source / name).write_bytes(f"payload-{number}".encode())
        source_stat = fs.stat(source, name)
        assert source_stat is not None
        operations.append(
            _operation(
                number,
                OperationKind.COPY,
                source_rel_path=name,
                target_rel_path=name,
                source_expected=source_stat,
                target_expected=None,
                intended=source_stat,
            )
        )
    backend = ConcurrencyProbeBackend()

    result, _, _ = _run(
        _xset(_plan(source, target, tuple(operations))),
        fs=fs,
        policies=_policies(copy_backend=backend),
    )

    assert result.status is SessionState.COMPLETED
    assert backend.max_active == 1


class FaultingPipelineStream:
    def __init__(self, stream, stage: str) -> None:
        self.stream = stream
        self.stage = stage
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def read(self, size: int) -> bytes:
        self.calls += 1
        if self.stage == "reader" and self.calls == 2:
            raise OSError("injected integrated reader failure")
        return self.stream.read(size)

    def write(self, data) -> int:
        self.calls += 1
        if self.stage == "writer" and self.calls == 2:
            raise OSError("injected integrated writer failure")
        return self.stream.write(data)

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


class FaultingPipelineFileSystem(NativeFileSystem):
    def __init__(self, stage: str) -> None:
        self.stage = stage
        self.temp_paths: list[Path] = []
        self.allocation_requests: list[int | None] = []
        self.exclusive_conflicts = 0

    def open_source(self, path: Path):
        stream = super().open_source(path)
        if self.stage == "reader":
            return FaultingPipelineStream(stream, self.stage)
        return stream

    def create_temp(self, path: Path, *, allocation_size: int | None):
        stream = super().create_temp(path, allocation_size=allocation_size)
        self.temp_paths.append(path)
        self.allocation_requests.append(allocation_size)
        try:
            super().create_temp(path, allocation_size=None)
        except FileExistsError:
            self.exclusive_conflicts += 1
        else:
            stream.close()
            raise AssertionError("owned temp creation was not exclusive")
        if self.stage == "writer":
            return FaultingPipelineStream(stream, self.stage)
        return stream


class IntegratedFailingHasher:
    def __init__(self) -> None:
        self.inner = xxh3_128()
        self.updates = 0

    def update(self, data: bytes) -> None:
        self.updates += 1
        if self.updates == 2:
            raise RuntimeError("injected integrated hasher failure")
        self.inner.update(data)

    def digest(self) -> bytes:
        return self.inner.digest()


@pytest.mark.parametrize("stage", ["reader", "hasher", "writer", "callback"])
def test_native_pipeline_faults_are_atomic_and_clean_current_owned_temp(
    tmp_path: Path, stage: str
) -> None:
    source, target = _roots(tmp_path)
    payload = b"0123456789abcdef" * (512 * 1024)
    source_path = source / "file.bin"
    source_path.write_bytes(payload)
    fs = FaultingPipelineFileSystem(stage)
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
    xset = _xset(_plan(source, target, (operation,)))
    recorder = FakeRecorder()
    events: list[object] = []
    callback_failed = False

    def emit(event: object) -> None:
        nonlocal callback_failed
        events.append(event)
        if (
            stage == "callback"
            and not callback_failed
            and isinstance(event, Progress)
            and event.bytes_done > 0
        ):
            callback_failed = True
            raise OSError("injected integrated callback failure")

    factory = IntegratedFailingHasher if stage == "hasher" else xxh3_128
    result = execute(
        xset,
        RunContext(emit, lambda: None),
        recorder,
        _policies(
            copy_backend=NativeCopyBackend(hasher_factory=factory),
            max_chunk_size=4 * 1024 * 1024,
        ),
        fs,
    )

    expected_name = (
        f"file.bin.synctmp-{RUN_ID}-{operation.op_id}"
    )
    expected_temp = target / expected_name
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert item.reason == "io-error"
    assert not (target / "file.bin").exists()
    assert not list(target.rglob("*.synctmp-*"))
    assert recorder.calls == []
    assert fs.temp_paths == [expected_temp]
    assert re.fullmatch(
        rf"file[.]bin[.]synctmp-{RUN_ID}-{operation.op_id}",
        fs.temp_paths[0].name,
    )
    assert fs.allocation_requests == [len(payload)]
    assert fs.exclusive_conflicts == 1
    assert xxh3_128(source_path.read_bytes()).digest() == xxh3_128(
        payload
    ).digest()


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
    item = next(event for event in _ if isinstance(event, ItemOutcome))
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
    assert [call[0] for call in recorder.calls] == ["copied"]
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
    assert [call[0] for call in recorder.calls] == ["copied"]


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


class FailingDirectoryFlushFileSystem(NativeFileSystem):
    def flush_directory(self, path: Path) -> bool:
        raise OSError("injected parent-directory flush failure")


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

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.COMPLETED
    assert item.detail["durability_warnings"] == (
        f"parent directory flush unsupported: {target}",
    )


def test_parent_directory_flush_error_records_nothing_after_publish(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"durable-content")
    fs = FailingDirectoryFlushFileSystem()
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

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))), fs=fs
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert item.reason == "io-error"
    assert (target / "file.bin").read_bytes() == b"durable-content"
    assert recorder.calls == []


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


class MutatingBackend(NativeCopyBackend):
    def __init__(self, source: Path) -> None:
        super().__init__(hasher_factory=xxh3_128)
        self.source = source

    def copy(self, *args, **kwargs):
        digest = super().copy(*args, **kwargs)
        self.source.write_bytes(b"drifted-source")
        return digest


def test_source_drift_after_stream_removes_temp_and_records_nothing(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    path = source / "file.bin"
    path.write_bytes(b"original")
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

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(copy_backend=MutatingBackend(path)),
    )

    assert result.status is SessionState.FAILED
    assert not (target / "file.bin").exists()
    assert not list(target.glob("*.synctmp-*"))
    assert recorder.calls == []
    outcome = next(event for event in events if isinstance(event, ItemOutcome))
    assert outcome.reason == "source-drift"


class MidReadMutationStream:
    def __init__(
        self,
        stream,
        path: Path,
        mode: str,
        requests: list[int] | None = None,
    ) -> None:
        self.stream = stream
        self.path = path
        self.mode = mode
        self.requests = requests
        self.reads = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def read(self, size: int) -> bytes:
        if self.requests is not None:
            self.requests.append(size)
        chunk = self.stream.read(size)
        self.reads += 1
        if self.reads == 1:
            if self.mode == "grow":
                with self.path.open("ab", buffering=0) as writer:
                    writer.write(b"EF")
            else:
                with self.path.open("r+b", buffering=0) as writer:
                    writer.truncate(len(chunk))
        return chunk

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


class MidReadMutationFileSystem(NativeFileSystem):
    def __init__(self, source: Path, mode: str) -> None:
        self.source = source
        self.mode = mode
        self.read_requests: list[int] = []

    def open_source(self, path: Path):
        return MidReadMutationStream(
            super().open_source(path),
            path,
            self.mode,
            self.read_requests,
        )


class CapturingCopyBackend:
    def __init__(self) -> None:
        self.native = NativeCopyBackend(hasher_factory=xxh3_128)
        self.result: CopyDigest | None = None

    def copy(self, *args, **kwargs) -> CopyDigest:
        self.result = self.native.copy(*args, **kwargs)
        return self.result


@pytest.mark.parametrize(
    ("mode", "initial", "observed_content"),
    [
        ("grow", b"abcd", b"abcdEF"),
        ("shrink", b"abcdef", b"ab"),
    ],
)
def test_source_growth_and_shrink_are_read_to_real_eof_then_classified_as_drift(
    tmp_path: Path,
    mode: str,
    initial: bytes,
    observed_content: bytes,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    source_path.write_bytes(initial)
    fs = MidReadMutationFileSystem(source_path, mode)
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
    backend = CapturingCopyBackend()

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(copy_backend=backend, max_chunk_size=2),
    )

    assert result.status is SessionState.FAILED
    assert backend.result is not None
    assert backend.result.size == len(observed_content)
    assert backend.result.digest == xxh3_128(observed_content).digest()
    assert recorder.calls == []
    assert not (target / "file.bin").exists()
    assert not list(target.glob("*.synctmp-*"))
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.reason == "source-drift"


def test_256k_ceiling_reads_growth_across_reviewed_8mib_band_to_eof(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    with source_path.open("wb") as stream:
        stream.truncate(_PREALLOCATION_THRESHOLD - 1)
    fs = MidReadMutationFileSystem(source_path, "grow")
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
    backend = CapturingCopyBackend()

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(
            copy_backend=backend,
            max_chunk_size=256 * 1024,
        ),
    )

    assert result.status is SessionState.FAILED
    assert backend.result is not None
    assert backend.result.size == _PREALLOCATION_THRESHOLD + 1
    assert fs.read_requests
    assert set(fs.read_requests) == {256 * 1024}
    assert recorder.calls == []
    assert not (target / "file.bin").exists()
    assert not list(target.glob("*.synctmp-*"))
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.reason == "source-drift"


class AppearanceFileSystem(NativeFileSystem):
    def publish_new(self, temp: Path, target: Path) -> None:
        target.write_bytes(b"external")
        super().publish_new(temp, target)


def test_conditional_publish_does_not_overwrite_target_appearance(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"planned")
    fs = AppearanceFileSystem()
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

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))), fs=fs
    )

    assert result.status is SessionState.FAILED
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.reason == "destination-occupied"
    assert (target / "file.bin").read_bytes() == b"external"
    assert recorder.calls == []


class PublishedSizeFaultFileSystem(NativeFileSystem):
    def __init__(self, published_name: str) -> None:
        self.published_name = published_name

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        result = super().ensure_published_metadata(path, *args, **kwargs)
        if path.name == self.published_name:
            with path.open("ab", buffering=0) as stream:
                stream.write(b"!")
            return replace(result, size=result.size + 1)
        return result


class FlushTempSubstitutionRecorder(FakeRecorder):
    def __init__(self, temp: Path) -> None:
        super().__init__()
        self.temp = temp
        self.substituted = False

    def flush(self) -> None:
        super().flush()
        if self.substituted or not self.temp.exists():
            return
        before = self.temp.stat(follow_symlinks=False)
        replacement = self.temp.with_name(f"{self.temp.name}.replacement")
        replacement.write_bytes(b"EVIL-CONTENT")
        os.utime(
            replacement,
            ns=(before.st_atime_ns, before.st_mtime_ns),
        )
        os.replace(replacement, self.temp)
        after = self.temp.stat(follow_symlinks=False)
        assert after.st_size == before.st_size
        assert after.st_mtime_ns == before.st_mtime_ns
        assert after.st_ino != before.st_ino
        self.substituted = True


def test_update_revalidates_prepared_temp_after_recorder_flush(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    source_name = "file.bin"
    (source / source_name).write_bytes(b"GOOD-CONTENT")
    published = target / source_name
    published.write_bytes(b"OLD!-CONTENT")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, source_name)
    target_stat = fs.stat(target, source_name)
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path=source_name,
        target_rel_path=source_name,
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    temp = target / f"{source_name}.synctmp-{RUN_ID}-{operation.op_id}"
    recorder = FlushTempSubstitutionRecorder(temp)
    xset = _xset(
        _plan(
            source,
            target,
            (operation,),
            trash_on_update=False,
        )
    )

    result, events, _ = _run(xset, fs=fs, recorder=recorder)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert recorder.substituted
    assert result.status is SessionState.FAILED
    assert item.reason == "target-drift"
    assert published.read_bytes() == b"OLD!-CONTENT"
    assert not temp.exists()
    assert result.recording is RecordingStatus.OK
    assert recorder.calls == []
    assert xset.published_evidence == {}


class PostPublishSubstitutionFileSystem(NativeFileSystem):
    def __init__(self, published: Path) -> None:
        self.published = published
        self.substitutions = 0

    def _substitute_published(self, path: Path) -> None:
        if path != self.published:
            return
        before = path.stat(follow_symlinks=False)
        replacement = path.with_name(f"{path.name}.replacement")
        replacement.write_bytes(b"EVIL-CONTENT")
        os.utime(
            replacement,
            ns=(before.st_atime_ns, before.st_mtime_ns),
        )
        os.replace(replacement, path)
        after = path.stat(follow_symlinks=False)
        assert after.st_size == before.st_size
        assert after.st_mtime_ns == before.st_mtime_ns
        assert after.st_ino != before.st_ino
        self.substitutions += 1

    def publish_new(self, temp: Path, target: Path) -> None:
        super().publish_new(temp, target)
        self._substitute_published(target)

    def replace(self, temp: Path, target: Path) -> None:
        super().replace(temp, target)
        self._substitute_published(target)


@pytest.mark.parametrize(
    "kind",
    [OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE],
)
def test_byte_operation_refuses_substituted_postpublish_identity_before_record(
    tmp_path: Path,
    kind: OperationKind,
) -> None:
    source, target = _roots(tmp_path)
    source_name = "new.bin"
    published_name = "new.bin"
    (source / source_name).write_bytes(b"GOOD-CONTENT")
    published = target / published_name
    fs = PostPublishSubstitutionFileSystem(published)
    source_stat = fs.stat(source, source_name)
    assert source_stat is not None
    target_expected = None
    prior_path = None
    prior_expected = None
    if kind is OperationKind.UPDATE:
        published.write_bytes(b"OLD!-CONTENT")
        target_expected = fs.stat(target, published_name)
        assert target_expected is not None
    elif kind is OperationKind.MOVE_UPDATE:
        (target / "old.bin").write_bytes(b"OLD!-CONTENT")
        prior_path = "old.bin"
        prior_expected = fs.stat(target, prior_path)
        assert prior_expected is not None
    operation = _operation(
        1,
        kind,
        source_rel_path=source_name,
        target_rel_path=published_name,
        source_expected=source_stat,
        target_expected=target_expected,
        intended=source_stat,
        prior_target_rel_path=prior_path,
        prior_target_expected=prior_expected,
    )
    xset = _xset(
        _plan(
            source,
            target,
            (operation,),
            trash_on_update=False,
        )
    )

    result, events, recorder = _run(xset, fs=fs)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert fs.substitutions == 1
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.reason == "target-drift"
    assert published.read_bytes() == b"EVIL-CONTENT"
    assert recorder.calls == []
    assert xset.published_evidence == {}
    if kind is OperationKind.MOVE_UPDATE:
        assert (target / "old.bin").read_bytes() == b"OLD!-CONTENT"


@pytest.mark.parametrize(
    "kind",
    [OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE],
)
def test_published_size_guard_fails_all_byte_producing_operations_before_record(
    tmp_path: Path, kind: OperationKind
) -> None:
    source, target = _roots(tmp_path)
    source_name = "new.bin"
    published_name = "new.bin"
    (source / source_name).write_bytes(b"new")
    fs = PublishedSizeFaultFileSystem(published_name)
    source_stat = fs.stat(source, source_name)
    assert source_stat is not None
    target_expected = None
    prior_path = None
    prior_expected = None
    if kind is OperationKind.UPDATE:
        (target / published_name).write_bytes(b"old")
        target_expected = fs.stat(target, published_name)
        assert target_expected is not None
    elif kind is OperationKind.MOVE_UPDATE:
        (target / "old.bin").write_bytes(b"old")
        prior_path = "old.bin"
        prior_expected = fs.stat(target, prior_path)
        assert prior_expected is not None
    operation = _operation(
        1,
        kind,
        source_rel_path=source_name,
        target_rel_path=published_name,
        source_expected=source_stat,
        target_expected=target_expected,
        intended=source_stat,
        prior_target_rel_path=prior_path,
        prior_target_expected=prior_expected,
    )

    xset = _xset(_plan(source, target, (operation,)))
    result, events, recorder = _run(xset, fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / published_name).stat().st_size == source_stat.size + 1
    assert recorder.calls == []
    assert xset.published_evidence == {}
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.reason == "published-size-mismatch"
    if kind is OperationKind.MOVE_UPDATE:
        assert (target / "old.bin").read_bytes() == b"old"


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


@pytest.mark.parametrize("hardlinks", [True, False])
def test_update_preserves_displaced_version_before_replace(
    tmp_path: Path, hardlinks: bool
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = NativeFileSystem()
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

    xset = _xset(_plan(source, target, (operation,), hardlinks=hardlinks))
    result, _, recorder = _run(xset, fs=fs)

    assert result.status is SessionState.COMPLETED
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"old-version"
    assert recorder.calls[0][0] == "updated"
    assert result.bytes_total == len(b"new-version")
    assert set(xset.published_evidence) == {operation.op_id}
    assert xset.published_evidence[operation.op_id].copy_recorded


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
    real_thread = executor_module.Thread

    def recording_thread(*args, **kwargs):
        worker_names.append(kwargs.get("name"))
        return real_thread(*args, **kwargs)

    monkeypatch.setattr(executor_module, "Thread", recording_thread)

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
    real_require_stat_path = executor_module._require_stat_path
    mutated = False

    def mutate_after_reviewed_guard(filesystem, path: Path) -> FileStat:
        nonlocal mutated
        if not mutated and ".synctmp-" in path.name:
            live.write_bytes(b"external-version-is-different")
            mutated = True
        return real_require_stat_path(filesystem, path)

    monkeypatch.setattr(
        executor_module,
        "_require_stat_path",
        mutate_after_reviewed_guard,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)),
        fs=fs,
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
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

    item = next(event for event in events if isinstance(event, ItemOutcome))
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

    item = next(event for event in events if isinstance(event, ItemOutcome))
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

    monkeypatch.setattr(executor_module, "_attestation", fail_attestation)
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


class ReplaceFaultFileSystem(NativeFileSystem):
    def __init__(self, *, after: bool) -> None:
        self.after = after

    def replace(self, temp: Path, target: Path) -> None:
        if self.after:
            super().replace(temp, target)
        raise OSError("injected replace fault")


class UnverifiableReplaceFaultFileSystem(NativeFileSystem):
    def __init__(self, target: Path) -> None:
        self.target = target
        self.published = False

    def replace(self, temp: Path, target: Path) -> None:
        super().replace(temp, target)
        self.published = True
        raise OSError("injected replace fault")

    def stat_path(self, path: Path) -> FileStat | None:
        if self.published and path == self.target:
            raise PermissionError("injected publication state probe failure")
        return super().stat_path(path)


@pytest.mark.parametrize("after", [False, True])
def test_update_fault_never_leaves_live_target_absent(tmp_path: Path, after: bool) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceFaultFileSystem(after=after)
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
        _xset(_plan(source, target, (operation,))), fs=fs
    )

    assert result.status is SessionState.FAILED
    assert (target / "file.bin").read_bytes() == (
        b"new-version" if after else b"old-version"
    )
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"old-version"
    assert recorder.calls == []
    assert result.recording is (
        RecordingStatus.DEGRADED if after else RecordingStatus.OK
    )
    if after:
        item = next(event for event in events if isinstance(event, ItemOutcome))
        assert item.detail["publish_state"] == "published"
        assert item.detail["target_state"] == "published"
        assert item.detail["durable_state"] == "target-published-with-backup"


def test_unverifiable_publish_failure_degrades_recording(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    published_target = target / "file.bin"
    published_target.write_bytes(b"old-version")
    fs = UnverifiableReplaceFaultFileSystem(published_target)
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
        _xset(_plan(source, target, (operation,))), fs=fs
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert published_target.read_bytes() == b"new-version"
    assert recorder.calls == []
    assert item.detail["publish_state"] == "unverified"
    assert item.detail["durable_state"] == "publication-unverified"
    assert item.detail["state_error_type"] == "PermissionError"
    assert item.detail["recording"] == RecordingStatus.DEGRADED.value


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
    assert next(event for event in events if isinstance(event, ItemOutcome)).reason == "acl-copy-failed"


def test_failed_work_does_not_abort_independent_and_defers_dependents(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "missing.bin").write_bytes(b"gone")
    (source / "good.bin").write_bytes(b"good")
    fs = NativeFileSystem()
    missing_stat = fs.stat(source, "missing.bin")
    good_stat = fs.stat(source, "good.bin")
    assert missing_stat is not None and good_stat is not None
    first = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="missing.bin",
        target_rel_path="missing.bin",
        source_expected=missing_stat,
        target_expected=None,
        intended=missing_stat,
    )
    second = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="good.bin",
        target_rel_path="good.bin",
        source_expected=good_stat,
        target_expected=None,
        intended=good_stat,
    )
    dependent = _operation(
        3,
        OperationKind.NOOP,
        source_rel_path="missing.bin",
        target_rel_path="missing.bin",
        source_expected=missing_stat,
        target_expected=missing_stat,
        intended=missing_stat,
        dependencies=(first.op_id,),
    )
    (source / "missing.bin").unlink()

    xset = _xset(_plan(source, target, (first, second, dependent)))
    result, _, recorder = _run(xset, fs=fs)

    assert result.status is SessionState.FAILED
    assert xset.status == {
        first.op_id: Outcome.FAILED,
        second.op_id: Outcome.SUCCEEDED,
        dependent.op_id: Outcome.DEFERRED,
    }
    assert (target / "good.bin").read_bytes() == b"good"
    assert [call[0] for call in recorder.calls] == ["copied"]


def test_directory_metadata_is_applied_after_child_operation(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "folder").mkdir()
    (source / "folder" / "file.bin").write_bytes(b"child")

    class LoggingFileSystem(NativeFileSystem):
        def __init__(self) -> None:
            self.metadata_paths: list[Path] = []

        def finalize_temp(self, path: Path, *args, **kwargs):
            self.metadata_paths.append(path)
            return super().finalize_temp(path, *args, **kwargs)

        def apply_metadata(self, path: Path, *args, **kwargs) -> None:
            self.metadata_paths.append(path)
            super().apply_metadata(path, *args, **kwargs)

    fs = LoggingFileSystem()
    dir_stat = fs.stat(source, "folder")
    file_stat = fs.stat(source, "folder\\file.bin")
    assert dir_stat is not None and file_stat is not None
    mkdir = _operation(
        1,
        OperationKind.MKDIR,
        source_rel_path="folder",
        target_rel_path="folder",
        source_expected=dir_stat,
        target_expected=None,
        intended=dir_stat,
    )
    copy = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="folder\\file.bin",
        target_rel_path="folder\\file.bin",
        source_expected=file_stat,
        target_expected=None,
        intended=file_stat,
        dependencies=(mkdir.op_id,),
    )

    result, _, recorder = _run(_xset(_plan(source, target, (mkdir, copy))), fs=fs)

    assert result.status is SessionState.COMPLETED
    copied_temp = next(
        path for path in fs.metadata_paths if ".synctmp-" in path.name
    )
    assert fs.metadata_paths.index(copied_temp) < fs.metadata_paths.index(target / "folder")
    assert [call[0] for call in recorder.calls] == ["copied", "mkdir"]


def test_mkdir_refuses_vanished_reviewed_source_directory(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    source_directory = source / "folder"
    source_directory.mkdir()
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "folder")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.MKDIR,
        source_rel_path="folder",
        target_rel_path="folder",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        reason=OperationReason.REQUIRED_DIRECTORY,
    )
    source_directory.rmdir()

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
    )

    assert result.status is SessionState.FAILED
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.reason == "source-missing"
    assert not (target / "folder").exists()
    assert recorder.calls == []


def test_explicit_directory_chain_supports_long_destination_path(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    first_name = "a" * 150
    second_name = "b" * 100
    source_first = source / first_name
    source_second = source_first / second_name
    source_second.mkdir(parents=True)
    (source_second / "file.bin").write_bytes(b"long-path")
    first_rel = first_name
    second_rel = f"{first_name}\\{second_name}"
    file_rel = f"{second_rel}\\file.bin"
    assert len(str(target / first_name / second_name / "file.bin")) > 260
    fs = NativeFileSystem()
    first_stat = fs.stat(source, first_rel)
    second_stat = fs.stat(source, second_rel)
    file_stat = fs.stat(source, file_rel)
    assert first_stat is not None and second_stat is not None and file_stat is not None
    first = _operation(
        1,
        OperationKind.MKDIR,
        source_rel_path=first_rel,
        target_rel_path=first_rel,
        source_expected=first_stat,
        target_expected=None,
        intended=first_stat,
    )
    second = _operation(
        2,
        OperationKind.MKDIR,
        source_rel_path=second_rel,
        target_rel_path=second_rel,
        source_expected=second_stat,
        target_expected=None,
        intended=second_stat,
        dependencies=(first.op_id,),
    )
    copy = _operation(
        3,
        OperationKind.COPY,
        source_rel_path=file_rel,
        target_rel_path=file_rel,
        source_expected=file_stat,
        target_expected=None,
        intended=file_stat,
        dependencies=(second.op_id,),
    )

    result, _, _ = _run(_xset(_plan(source, target, (first, second, copy))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert (target / first_name / second_name / "file.bin").read_bytes() == b"long-path"


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length paths")
def test_executor_failure_detail_does_not_expose_native_prefix(
    tmp_path: Path,
) -> None:
    logical = tmp_path / ("a" * 90) / ("b" * 90) / ("c" * 90) / "file.bin"
    assert len(str(logical)) > 260
    native = executor_module._win32_path(logical)
    reason, detail = executor_module._failure_reason_and_message(
        PermissionError(13, "denied", native)
    )

    assert reason is executor_module.ExecutionReason.IO_ERROR
    assert "file.bin" in detail
    assert "\\\\?\\" not in detail


def test_nonempty_directory_delete_refuses_without_recursive_removal(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (target / "folder").mkdir()
    (target / "folder" / "child.txt").write_text("keep", encoding="utf-8")
    fs = NativeFileSystem()
    directory_stat = fs.stat(target, "folder")
    assert directory_stat is not None and directory_stat.kind is EntryKind.DIRECTORY
    operation = _operation(
        1,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="folder",
        source_expected=None,
        target_expected=directory_stat,
        intended=None,
        reason=OperationReason.DIRECTORY_CLEANUP,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / "folder" / "child.txt").read_text(encoding="utf-8") == "keep"
    assert recorder.calls == []


def test_directory_cleanup_succeeds_after_last_child_is_trashed(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    folder = target / "obsolete"
    folder.mkdir()
    child = folder / "child.bin"
    child.write_bytes(b"old")
    fs = NativeFileSystem()
    child_stat = fs.stat(target, r"obsolete\child.bin")
    directory_stat = fs.stat(target, "obsolete")
    assert child_stat is not None and directory_stat is not None
    time.sleep(0.02)
    trash = _operation(
        1,
        OperationKind.TRASH,
        source_rel_path=None,
        target_rel_path=r"obsolete\child.bin",
        source_expected=None,
        target_expected=child_stat,
        intended=None,
    )
    cleanup = _operation(
        2,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="obsolete",
        source_expected=None,
        target_expected=directory_stat,
        intended=None,
        dependencies=(trash.op_id,),
        reason=OperationReason.DIRECTORY_CLEANUP,
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (trash, cleanup))), fs=fs
    )

    assert result.status is SessionState.COMPLETED
    assert not folder.exists()
    assert (
        target / ".synctrash" / str(RUN_ID) / "obsolete" / "child.bin"
    ).read_bytes() == b"old"
    assert [call[0] for call in recorder.calls] == ["trashed", "deleted"]


def test_directory_cleanup_succeeds_after_last_child_is_moved(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    source_new_folder = source / "new"
    source_new_folder.mkdir()
    old_folder = target / "old"
    new_folder = target / "new"
    old_folder.mkdir()
    new_folder.mkdir()
    child = old_folder / "child.bin"
    child.write_bytes(b"content")
    fs = NativeFileSystem()
    child_stat = fs.stat(target, r"old\child.bin")
    directory_stat = fs.stat(target, "old")
    assert child_stat is not None and directory_stat is not None
    source_child = source_new_folder / "child.bin"
    source_child.write_bytes(b"content")
    os.utime(
        source_child,
        ns=(child_stat.mtime_ns, child_stat.mtime_ns),
    )
    source_stat = fs.stat(source, r"new\child.bin")
    assert source_stat is not None
    time.sleep(0.02)
    move = _operation(
        1,
        OperationKind.MOVE,
        source_rel_path=r"new\child.bin",
        target_rel_path=r"new\child.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path=r"old\child.bin",
        prior_target_expected=child_stat,
        reason=OperationReason.IDENTITY_RENAME,
    )
    cleanup = _operation(
        2,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="old",
        source_expected=None,
        target_expected=directory_stat,
        intended=None,
        dependencies=(move.op_id,),
        reason=OperationReason.DIRECTORY_CLEANUP,
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (move, cleanup))), fs=fs
    )

    assert result.status is SessionState.COMPLETED
    assert not old_folder.exists()
    assert (new_folder / "child.bin").read_bytes() == b"content"
    assert [call[0] for call in recorder.calls] == ["moved", "deleted"]


def test_directory_cleanup_rejects_replaced_empty_directory(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    folder = target / "folder"
    folder.mkdir()
    fs = NativeFileSystem()
    expected = fs.stat(target, "folder")
    assert expected is not None and expected.file_identity is not None
    folder.rmdir()
    folder.mkdir()
    replacement = fs.stat(target, "folder")
    assert replacement is not None
    assert replacement.file_identity != expected.file_identity
    cleanup = _operation(
        1,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="folder",
        source_expected=None,
        target_expected=expected,
        intended=None,
        reason=OperationReason.DIRECTORY_CLEANUP,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (cleanup,))), fs=fs
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert item.reason == "target-drift"
    assert folder.is_dir()
    assert recorder.calls == []


def test_directory_cleanup_allows_absent_reviewed_identity(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    folder = target / "folder"
    folder.mkdir()
    fs = NativeFileSystem()
    actual = fs.stat(target, "folder")
    assert actual is not None
    cleanup = _operation(
        1,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="folder",
        source_expected=None,
        target_expected=replace(
            actual,
            file_identity=None,
            mtime_ns=actual.mtime_ns - 1,
            nlink=actual.nlink + 1,
        ),
        intended=None,
        reason=OperationReason.DIRECTORY_CLEANUP,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (cleanup,))), fs=fs
    )

    assert result.status is SessionState.COMPLETED
    assert not folder.exists()
    assert recorder.calls[0][0] == "deleted"


def test_identityless_directory_cleanup_still_rejects_metadata_drift(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    folder = target / "folder"
    folder.mkdir()
    fs = NativeFileSystem()
    actual = fs.stat(target, "folder")
    assert actual is not None
    cleanup = _operation(
        1,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="folder",
        source_expected=None,
        target_expected=replace(
            actual,
            file_identity=None,
            metadata=replace(
                actual.metadata,
                attributes=actual.metadata.attributes ^ 0x2,
            ),
        ),
        intended=None,
        reason=OperationReason.DIRECTORY_CLEANUP,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (cleanup,))), fs=fs
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert item.reason == "target-drift"
    assert folder.is_dir()
    assert recorder.calls == []


def test_directory_cleanup_reason_does_not_relax_file_evidence(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    path = target / "file.bin"
    path.write_bytes(b"old")
    fs = NativeFileSystem()
    expected = fs.stat(target, "file.bin")
    assert expected is not None
    time.sleep(0.02)
    path.write_bytes(b"new")
    cleanup = _operation(
        1,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="file.bin",
        source_expected=None,
        target_expected=expected,
        intended=None,
        reason=OperationReason.DIRECTORY_CLEANUP,
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (cleanup,))), fs=fs
    )

    assert result.status is SessionState.FAILED
    assert path.read_bytes() == b"new"
    assert recorder.calls == []


def test_noop_drift_does_not_refresh_recorder_evidence(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"same")
    (target / "file.bin").write_bytes(b"same")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "file.bin")
    target_stat = fs.stat(target, "file.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.NOOP,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=target_stat,
    )
    (target / "file.bin").write_bytes(b"drift")

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    assert recorder.calls == []


class ReadObservedStream:
    def __init__(self, stream, observed: Event) -> None:
        self.stream = stream
        self.observed = observed
        self.read_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def read(self, size: int) -> bytes:
        self.read_calls += 1
        chunk = self.stream.read(size)
        if chunk:
            self.observed.set()
        return chunk

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


class ReadObservedFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.read_observed = Event()
        self.reader: ReadObservedStream | None = None

    def open_source(self, path: Path):
        self.reader = ReadObservedStream(
            super().open_source(path), self.read_observed
        )
        return self.reader


@pytest.mark.parametrize("control", [Canceled, PauseRequested])
def test_copy_control_unwinds_within_one_chunk_and_cleans_temp(
    tmp_path: Path, control: type[Exception]
) -> None:
    source, target = _roots(tmp_path)
    (source / "large.bin").write_bytes(b"x" * 32)
    fs = ReadObservedFileSystem()
    source_stat = fs.stat(source, "large.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="large.bin",
        target_rel_path="large.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    events: list[object] = []

    def checkpoint() -> None:
        if fs.read_observed.is_set():
            raise control()

    with pytest.raises(control):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(max_chunk_size=4),
            fs,
        )

    assert not (target / "large.bin").exists()
    assert not list(target.glob("*.synctmp-*"))
    assert fs.reader is not None
    assert fs.reader.read_calls == 1
    assert not any(isinstance(event, Terminal) for event in events)
    if control is Canceled:
        assert xset.status[operation.op_id] is Outcome.CANCELED
    else:
        assert operation.op_id not in xset.status


def test_pause_retains_settled_copy_evidence_for_in_memory_resume(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operations = []
    for number, name in enumerate(("first.bin", "second.bin"), start=1):
        (source / name).write_bytes(name.encode("ascii"))
        source_stat = fs.stat(source, name)
        assert source_stat is not None
        operations.append(
            _operation(
                number,
                OperationKind.COPY,
                source_rel_path=name,
                target_rel_path=name,
                source_expected=source_stat,
                target_expected=None,
                intended=source_stat,
            )
        )
    first, second = operations
    xset = _xset(_plan(source, target, tuple(operations)))
    first_settled = Event()
    events: list[object] = []

    def emit(event: object) -> None:
        events.append(event)
        if (
            isinstance(event, ItemOutcome)
            and event.item_id == str(first.op_id)
            and event.outcome is Outcome.SUCCEEDED
        ):
            first_settled.set()

    def checkpoint() -> None:
        if first_settled.is_set():
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(emit, checkpoint),
            FakeRecorder(),
            _policies(),
            fs,
        )

    assert xset.status == {first.op_id: Outcome.SUCCEEDED}
    assert set(xset.published_evidence) == {first.op_id}
    first_evidence = xset.published_evidence[first.op_id]
    assert first_evidence.copy_recorded

    result, _, _ = _run(xset, fs=fs)

    assert result.status is SessionState.COMPLETED
    assert xset.status == {
        first.op_id: Outcome.SUCCEEDED,
        second.op_id: Outcome.SUCCEEDED,
    }
    assert set(xset.published_evidence) == {first.op_id, second.op_id}
    assert xset.published_evidence[first.op_id] is first_evidence
    assert xset.published_evidence[second.op_id].copy_recorded


def test_noncopy_recording_degradation_survives_pause_and_resume(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    (source / "same.bin").write_bytes(b"same")
    (target / "same.bin").write_bytes(b"same")
    (source / "copy.bin").write_bytes(b"copy")
    source_same = fs.stat(source, "same.bin")
    target_same = fs.stat(target, "same.bin")
    copy_stat = fs.stat(source, "copy.bin")
    assert source_same is not None
    assert target_same is not None
    assert copy_stat is not None
    noop = _operation(
        1,
        OperationKind.NOOP,
        source_rel_path="same.bin",
        target_rel_path="same.bin",
        source_expected=source_same,
        target_expected=target_same,
        intended=source_same,
        reason=OperationReason.METADATA_MATCH,
    )
    copied = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="copy.bin",
        target_rel_path="copy.bin",
        source_expected=copy_stat,
        target_expected=None,
        intended=copy_stat,
    )
    xset = _xset(_plan(source, target, (noop, copied)))
    noop_settled = Event()

    def emit(event: object) -> None:
        if isinstance(event, ItemOutcome) and event.item_id == str(noop.op_id):
            noop_settled.set()

    def checkpoint() -> None:
        if noop_settled.is_set():
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(emit, checkpoint),
            FakeRecorder(fail="noop"),
            _policies(),
            fs,
        )

    assert xset.status == {noop.op_id: Outcome.SKIPPED}
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence == {}

    result, _, _ = _run(xset, fs=fs)

    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.DEGRADED
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence[copied.op_id].copy_recorded


def test_pause_flush_degradation_is_retained_for_resume(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"content")
    fs = ReadObservedFileSystem()
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
    xset = _xset(_plan(source, target, (operation,)))

    def checkpoint() -> None:
        if fs.read_observed.is_set():
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(lambda _event: None, checkpoint),
            FakeRecorder(fail="flush"),
            _policies(),
            fs,
        )

    assert xset.status == {}
    assert xset.published_evidence == {}
    assert xset.recording is RecordingStatus.DEGRADED

    result, _, _ = _run(xset, fs=fs)

    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.DEGRADED
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence[operation.op_id].copy_recorded


class InterruptingBackend(NativeCopyBackend):
    def copy(self, _source, target, **_kwargs):
        target.write(b"partial")
        raise KeyboardInterrupt()


def test_unexpected_base_exception_cleans_owned_temp_before_propagating(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"complete")
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
    xset = _xset(_plan(source, target, (operation,)))
    recorder = FakeRecorder()

    with pytest.raises(KeyboardInterrupt):
        execute(
            xset,
            RunContext(lambda _: None, lambda: None),
            recorder,
            _policies(
                copy_backend=InterruptingBackend(hasher_factory=xxh3_128)
            ),
            fs,
        )

    assert not (target / "file.bin").exists()
    assert not list(target.glob("*.synctmp-*"))
    assert operation.op_id not in xset.status
    assert recorder.calls == []
    assert recorder.flushes == 1


class SharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def publish_new(self, temp: Path, target: Path) -> None:
        self.attempts += 1
        if self.attempts == 1:
            error = OSError("sharing violation")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error
        super().publish_new(temp, target)


class SharingViolationWriter:
    def __init__(self, stream) -> None:
        self.stream = stream
        self.writes = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def write(self, data) -> int:
        self.writes += 1
        if self.writes == 2:
            error = OSError("sharing violation during streamed write")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error
        return self.stream.write(data)

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


class MidCopySharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.create_attempts = 0
        self.cleaned: list[Path] = []

    def create_temp(self, path: Path, *, allocation_size: int | None):
        self.create_attempts += 1
        stream = super().create_temp(
            path, allocation_size=allocation_size
        )
        if self.create_attempts == 1:
            return SharingViolationWriter(stream)
        return stream

    def remove_owned_temp(self, path: Path) -> None:
        if path.exists():
            self.cleaned.append(path)
        super().remove_owned_temp(path)


class CleanupDiagnosticFileSystem(NativeFileSystem):
    def __init__(self, *, fail_finalize: bool) -> None:
        self.fail_finalize = fail_finalize
        self.temp_created = False
        self.fail_cleanup = False

    def create_temp(self, path: Path, *, allocation_size: int | None):
        stream = super().create_temp(path, allocation_size=allocation_size)
        self.temp_created = True
        if not self.fail_finalize:
            self.fail_cleanup = True
        return stream

    def finalize_temp(
        self,
        path: Path,
        intended: FileStat,
        *,
        preserve_created: bool,
        acl_source: Path | None,
    ) -> FileStat:
        if self.fail_finalize:
            self.fail_cleanup = True
            raise OSError("injected finalization failure")
        return super().finalize_temp(
            path,
            intended,
            preserve_created=preserve_created,
            acl_source=acl_source,
        )

    def remove_owned_temp(self, path: Path) -> None:
        if self.fail_cleanup:
            native = to_extended_length_path(str(path))
            raise PermissionError(13, "cleanup denied", native)
        super().remove_owned_temp(path)


class PublishCancelCleanupDiagnosticFileSystem(CleanupDiagnosticFileSystem):
    def __init__(self) -> None:
        super().__init__(fail_finalize=False)

    def publish_new(self, temp: Path, target: Path) -> None:
        del temp, target
        raise Canceled()


def test_failed_cleanup_detail_sanitizes_native_temp_filename(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"payload")
    fs = CleanupDiagnosticFileSystem(fail_finalize=True)
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

    outcome = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.items == (outcome,)
    assert outcome.reason == "cleanup-failed"
    assert r"file.bin.synctmp-" in outcome.detail["message"]
    assert "\\\\?\\" not in outcome.detail["message"]
    assert "\\\\?\\" not in str(result_item_to_dict(outcome))


def test_canceled_cleanup_detail_sanitizes_native_temp_filename(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"payload")
    fs = CleanupDiagnosticFileSystem(fail_finalize=False)
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
    events: list[object] = []

    def checkpoint() -> None:
        if fs.temp_created:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            _xset(_plan(source, target, (operation,))),
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(),
            fs,
        )

    outcome = next(event for event in events if isinstance(event, ItemOutcome))
    assert outcome.outcome is Outcome.CANCELED
    assert r"file.bin.synctmp-" in outcome.detail["cleanup_error"]
    assert "\\\\?\\" not in outcome.detail["cleanup_error"]
    assert "\\\\?\\" not in str(result_item_to_dict(outcome))


def test_canceled_durable_settlement_sanitizes_cleanup_filename(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"payload")
    fs = PublishCancelCleanupDiagnosticFileSystem()
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
    events: list[object] = []

    with pytest.raises(Canceled):
        execute(
            _xset(_plan(source, target, (operation,))),
            RunContext(events.append, lambda: None),
            FakeRecorder(),
            _policies(),
            fs,
        )

    outcome = next(event for event in events if isinstance(event, ItemOutcome))
    assert outcome.outcome is Outcome.CANCELED
    assert outcome.detail["publish_state"] == "not-published"
    assert r"file.bin.synctmp-" in outcome.detail["cleanup_error"]
    assert "\\\\?\\" not in outcome.detail["cleanup_error"]
    assert "\\\\?\\" not in str(result_item_to_dict(outcome))


def test_midcopy_sharing_retry_recreates_owned_temp_and_converges(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    payload = b"abcdefghijkl"
    (source / "file.bin").write_bytes(payload)
    fs = MidCopySharingOnceFileSystem()
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
        policies=_policies(max_chunk_size=4),
    )

    expected_temp = target / (
        f"file.bin.synctmp-{RUN_ID}-{operation.op_id}"
    )
    assert result.status is SessionState.COMPLETED
    assert fs.create_attempts == 2
    assert fs.cleaned == [expected_temp]
    assert (target / "file.bin").read_bytes() == payload
    assert not expected_temp.exists()
    assert [call[0] for call in recorder.calls] == ["copied"]


def test_transient_sharing_violation_retries_within_bound(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"retry")
    fs = SharingOnceFileSystem()
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

    result, _, _ = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 2
    assert (target / "file.bin").read_bytes() == b"retry"


class CopyMetadataSharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.metadata_attempts = 0
        self.source_opens = 0

    def open_source(self, path: Path):
        self.source_opens += 1
        return super().open_source(path)

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        self.metadata_attempts += 1
        if self.metadata_attempts == 1:
            error = OSError("sharing violation after copy publish")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error
        return super().ensure_published_metadata(path, *args, **kwargs)


class PublishedRetrySharingOnceFileSystem(NativeFileSystem):
    def __init__(self, published_target: Path, *, before_stat_cache: bool) -> None:
        self.published_target = published_target
        self.before_stat_cache = before_stat_cache
        self.published_metadata_observed = False
        self.metadata_attempts = 0
        self.flush_attempts = 0
        self.source_opens = 0

    def open_source(self, path: Path):
        self.source_opens += 1
        return super().open_source(path)

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        if path == self.published_target:
            self.metadata_attempts += 1
            if self.before_stat_cache and self.metadata_attempts == 1:
                native = path.stat(follow_symlinks=False)
                os.utime(
                    path,
                    ns=(native.st_atime_ns, native.st_mtime_ns + 2_000_000_000),
                )
                error = OSError("sharing violation before published stat")
                error.winerror = 32  # type: ignore[attr-defined]
                raise error
        observed = super().ensure_published_metadata(path, *args, **kwargs)
        if path == self.published_target:
            self.published_metadata_observed = True
        return observed

    def flush_directory(self, path: Path) -> bool:
        if not self.before_stat_cache and self.published_metadata_observed:
            self.flush_attempts += 1
            if self.flush_attempts == 1:
                error = OSError("sharing violation after published stat")
                error.winerror = 32  # type: ignore[attr-defined]
                raise error
        return super().flush_directory(path)


def _published_retry_operation(
    kind: OperationKind,
    source: Path,
    target: Path,
    fs: NativeFileSystem,
) -> tuple[PlanOperation, Path]:
    target_rel_path = (
        "renamed.bin" if kind is OperationKind.MOVE_UPDATE else "file.bin"
    )
    (source / target_rel_path).write_bytes(b"new-version")
    source_stat = fs.stat(source, target_rel_path)
    assert source_stat is not None

    target_expected = None
    prior_target_rel_path = None
    prior_target_expected = None
    if kind is OperationKind.UPDATE:
        (target / target_rel_path).write_bytes(b"old-version")
        target_expected = fs.stat(target, target_rel_path)
        assert target_expected is not None
    elif kind is OperationKind.MOVE_UPDATE:
        prior_target_rel_path = "old.bin"
        (target / prior_target_rel_path).write_bytes(b"old-version")
        prior_target_expected = fs.stat(target, prior_target_rel_path)
        assert prior_target_expected is not None

    return (
        _operation(
            1,
            kind,
            source_rel_path=target_rel_path,
            target_rel_path=target_rel_path,
            source_expected=source_stat,
            target_expected=target_expected,
            intended=source_stat,
            prior_target_rel_path=prior_target_rel_path,
            prior_target_expected=prior_target_expected,
        ),
        target / target_rel_path,
    )


def _replace_published_target(path: Path, fs: NativeFileSystem) -> None:
    published = fs.stat_path(path)
    assert published is not None
    replacement = path.with_name(f".{path.name}.foreign")
    replacement.write_bytes(b"bad-version")
    os.utime(
        replacement,
        ns=(replacement.stat().st_atime_ns, published.mtime_ns),
    )
    replacement_stat = fs.stat_path(replacement)
    assert replacement_stat is not None
    assert replacement_stat.size == published.size
    assert replacement_stat.mtime_ns == published.mtime_ns
    assert replacement_stat.file_identity != published.file_identity
    os.replace(replacement, path)


@pytest.mark.parametrize(
    "kind",
    (OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE),
)
@pytest.mark.parametrize(
    "before_stat_cache",
    (
        pytest.param(True, id="before-stat-cache"),
        pytest.param(False, id="after-stat-cache"),
    ),
)
def test_retry_rejects_replaced_published_target(
    tmp_path: Path,
    kind: OperationKind,
    before_stat_cache: bool,
) -> None:
    source, target = _roots(tmp_path)
    published_target = target / (
        "renamed.bin" if kind is OperationKind.MOVE_UPDATE else "file.bin"
    )
    fs = PublishedRetrySharingOnceFileSystem(
        published_target,
        before_stat_cache=before_stat_cache,
    )
    operation, published_target = _published_retry_operation(
        kind, source, target, fs
    )

    xset = _xset(_plan(source, target, (operation,), hardlinks=False))
    result, events, recorder = _run(
        xset,
        fs=fs,
        policies=_policies(
            sleep=lambda _delay: _replace_published_target(published_target, fs)
        ),
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert item.outcome is Outcome.FAILED
    assert item.reason == "target-drift"
    assert result.recording is RecordingStatus.DEGRADED
    assert item.detail["publish_state"] == "published"
    assert item.detail["target_state"] == "changed-after-publish"
    assert item.detail["durable_state"] == "target-changed-after-publish"
    assert item.detail["recording"] == RecordingStatus.DEGRADED.value
    assert fs.metadata_attempts == 1
    assert fs.flush_attempts == (0 if before_stat_cache else 1)
    assert recorder.calls == []
    assert xset.published_evidence == {}
    assert published_target.read_bytes() == b"bad-version"


@pytest.mark.parametrize(
    "kind",
    (OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE),
)
def test_cancel_after_published_target_changes_reports_changed_durable_state(
    tmp_path: Path,
    kind: OperationKind,
) -> None:
    source, target = _roots(tmp_path)
    published_target = target / (
        "renamed.bin" if kind is OperationKind.MOVE_UPDATE else "file.bin"
    )
    fs = PublishedRetrySharingOnceFileSystem(
        published_target,
        before_stat_cache=True,
    )
    operation, published_target = _published_retry_operation(
        kind, source, target, fs
    )
    xset = _xset(_plan(source, target, (operation,), hardlinks=False))
    cancel_requested = False
    events: list[object] = []

    def sleep_for_retry(_delay: float) -> None:
        nonlocal cancel_requested
        _replace_published_target(published_target, fs)
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep_for_retry),
            fs,
        )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.outcome is Outcome.FAILED
    assert item.reason == "canceled-after-publish"
    assert item.detail["publish_state"] == "published"
    assert item.detail["target_state"] == "changed-after-publish"
    assert item.detail["durable_state"] == "target-changed-after-publish"
    assert item.detail["recording"] == RecordingStatus.DEGRADED.value
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence == {}


def test_metadata_retry_repairs_published_mtime_without_recopy(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    published_target = target / "file.bin"
    fs = PublishedRetrySharingOnceFileSystem(
        published_target,
        before_stat_cache=True,
    )
    operation, _ = _published_retry_operation(
        OperationKind.COPY, source, target, fs
    )

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
    )

    published = fs.stat_path(published_target)
    assert published is not None
    assert operation.source_expected is not None
    assert result.status is SessionState.COMPLETED
    assert published.mtime_ns == operation.source_expected.mtime_ns
    assert fs.metadata_attempts == 2
    assert fs.source_opens == 1
    assert [call[0] for call in recorder.calls] == ["copied"]


class PermanentPublishedMetadataFailureFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.metadata_attempts = 0
        self.published_target: Path | None = None

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        if path != self.published_target:
            return super().ensure_published_metadata(path, *args, **kwargs)
        self.metadata_attempts += 1
        error = OSError("persistent sharing violation after publish")
        error.winerror = 32  # type: ignore[attr-defined]
        raise error


class TerminalPublishAfterCommitFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.published_target: Path | None = None

    def replace(self, temp: Path, target: Path) -> None:
        super().replace(temp, target)
        if target == self.published_target:
            error = OSError("sharing report after committed publish")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error

    def publish_new(self, temp: Path, target: Path) -> None:
        super().publish_new(temp, target)
        if target == self.published_target:
            error = OSError("sharing report after committed publish")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error


@pytest.mark.parametrize(
    ("kind", "durable_state"),
    [
        (OperationKind.COPY, "target-published"),
        (OperationKind.UPDATE, "target-published-with-backup"),
        (OperationKind.MOVE_UPDATE, "new-and-old"),
    ],
)
def test_terminal_post_publish_failure_degrades_recording_and_reports_durable_state(
    tmp_path: Path,
    kind: OperationKind,
    durable_state: str,
) -> None:
    source, target = _roots(tmp_path)
    fs = PermanentPublishedMetadataFailureFileSystem()
    operation, published_target = _published_retry_operation(
        kind,
        source,
        target,
        fs,
    )
    fs.published_target = published_target
    recorder = FakeRecorder()
    xset = _xset(_plan(source, target, (operation,), hardlinks=False))

    result, events, _ = _run(xset, fs=fs, recorder=recorder)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.outcome is Outcome.FAILED
    assert item.reason == "sharing-violation"
    assert item.detail["publish_state"] == "published"
    assert item.detail["target_state"] == "published"
    assert item.detail["durable_state"] == durable_state
    assert item.detail["published_path"] == operation.target_rel_path
    assert item.detail["recording"] == RecordingStatus.DEGRADED.value
    assert item.detail["recording_error"] == (
        "published filesystem mutation failed before ledger settlement"
    )
    assert published_target.read_bytes() == b"new-version"
    assert fs.metadata_attempts == 3
    assert recorder.calls == []
    assert xset.published_evidence == {}

    if kind is OperationKind.UPDATE:
        backup = target / ".synctrash" / str(RUN_ID) / "file.bin"
        assert item.detail["backup_state"] == "retained"
        assert backup.read_bytes() == b"old-version"
    elif kind is OperationKind.MOVE_UPDATE:
        assert item.detail["prior_path"] == "old.bin"
        assert (target / "old.bin").read_bytes() == b"old-version"


@pytest.mark.parametrize(
    ("kind", "durable_state"),
    [
        (OperationKind.COPY, "target-published"),
        (OperationKind.UPDATE, "target-published-with-backup"),
        (OperationKind.MOVE_UPDATE, "new-and-old"),
    ],
)
def test_terminal_publish_that_commits_before_error_degrades_recording(
    tmp_path: Path,
    kind: OperationKind,
    durable_state: str,
) -> None:
    source, target = _roots(tmp_path)
    fs = TerminalPublishAfterCommitFileSystem()
    operation, published_target = _published_retry_operation(
        kind,
        source,
        target,
        fs,
    )
    fs.published_target = published_target
    recorder = FakeRecorder()
    xset = _xset(_plan(source, target, (operation,), hardlinks=False))

    result, events, _ = _run(
        xset,
        fs=fs,
        recorder=recorder,
        policies=_policies(failure=BoundedFailurePolicy(retries=0)),
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.outcome is Outcome.FAILED
    assert item.reason == "sharing-violation"
    assert item.detail["publish_state"] == "published"
    assert item.detail["target_state"] == "published"
    assert item.detail["durable_state"] == durable_state
    assert item.detail["recording"] == RecordingStatus.DEGRADED.value
    assert published_target.read_bytes() == b"new-version"
    assert recorder.calls == []
    assert xset.published_evidence == {}


def test_pause_during_published_copy_retry_settles_without_recopy(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"published-copy")
    fs = CopyMetadataSharingOnceFileSystem()
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
    xset = _xset(_plan(source, target, (operation,)))
    pause_requested = False

    def sleep(_delay: float) -> None:
        nonlocal pause_requested
        pause_requested = True

    def checkpoint() -> None:
        if pause_requested:
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(lambda _: None, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    assert fs.metadata_attempts == 2
    assert fs.source_opens == 1
    assert xset.status == {operation.op_id: Outcome.SUCCEEDED}
    assert set(xset.published_evidence) == {operation.op_id}
    assert (target / "file.bin").read_bytes() == b"published-copy"

    resumed, _, _ = _run(xset, fs=fs)
    assert resumed.status is SessionState.COMPLETED


def test_cancel_during_published_copy_retry_fails_without_false_evidence(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"published-copy")
    fs = CopyMetadataSharingOnceFileSystem()
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
    xset = _xset(_plan(source, target, (operation,)))
    cancel_requested = False
    events: list[object] = []

    def sleep(_delay: float) -> None:
        nonlocal cancel_requested
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.outcome is Outcome.FAILED
    assert item.reason == "canceled-after-publish"
    assert item.detail["durable_state"] == "target-published"
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence == {}
    assert fs.source_opens == 1
    assert (target / "file.bin").read_bytes() == b"published-copy"


def test_cancel_after_failed_copy_publish_does_not_claim_foreign_target(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"prepared-copy")
    fs = SharingOnceFileSystem()
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
    xset = _xset(_plan(source, target, (operation,)))
    cancel_requested = False
    events: list[object] = []

    def sleep(_delay: float) -> None:
        nonlocal cancel_requested
        (target / "file.bin").write_bytes(b"foreign-write")
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.outcome is Outcome.CANCELED
    assert item.reason == "canceled"
    assert item.detail["publish_state"] == "not-published"
    assert item.detail["target_state"] == "unexpectedly-present-before-publish"
    assert xset.recording is RecordingStatus.OK
    assert xset.published_evidence == {}
    assert fs.attempts == 1
    assert (target / "file.bin").read_bytes() == b"foreign-write"
    assert not list(target.glob("*.synctmp-*"))


class VanishingTempSharingFileSystem(NativeFileSystem):
    def publish_new(self, temp: Path, target: Path) -> None:
        del target
        temp.unlink()
        error = OSError("sharing report with missing staged temp")
        error.winerror = 32  # type: ignore[attr-defined]
        raise error


def test_unclassifiable_cancel_does_not_assume_publish_or_degrade_recording(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"prepared-copy")
    fs = VanishingTempSharingFileSystem()
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
    xset = _xset(_plan(source, target, (operation,)))
    cancel_requested = False
    events: list[object] = []

    def sleep(_delay: float) -> None:
        nonlocal cancel_requested
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.outcome is Outcome.FAILED
    assert item.reason == "target-missing"
    assert item.detail["publish_state"] == "unverified"
    assert item.detail["durable_state"] == "unverified"
    assert xset.recording is RecordingStatus.OK
    assert xset.published_evidence == {}


class PublishedMtimeThenFlushSharingFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.flush_attempts = 0

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        super().ensure_published_metadata(path, *args, **kwargs)
        native = path.stat(follow_symlinks=False)
        os.utime(
            path,
            ns=(native.st_atime_ns, native.st_mtime_ns + 2_000_000_000),
        )
        observed = self.stat_path(path)
        assert observed is not None
        return observed

    def flush_directory(self, path: Path) -> bool:
        self.flush_attempts += 1
        if self.flush_attempts == 1:
            error = OSError("sharing violation after repaired metadata")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error
        return super().flush_directory(path)


def test_cancel_uses_cached_published_stat_after_metadata_changes(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"published-copy")
    fs = PublishedMtimeThenFlushSharingFileSystem()
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
    xset = _xset(_plan(source, target, (operation,)))
    cancel_requested = False
    events: list[object] = []

    def sleep(_delay: float) -> None:
        nonlocal cancel_requested
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.outcome is Outcome.FAILED
    assert item.reason == "canceled-after-publish"
    assert item.detail["publish_state"] == "published"
    assert item.detail["target_state"] == "published"
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence == {}


class PrepareSharingFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.failed = False
        self.attempts = 0

    def open_source(self, path: Path):
        self.attempts += 1
        self.failed = True
        error = OSError("sharing violation before durable ownership")
        error.winerror = 32  # type: ignore[attr-defined]
        raise error


def test_pause_without_durable_continuation_unwinds_before_retry_sleep(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"not-staged")
    fs = PrepareSharingFileSystem()
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
    xset = _xset(_plan(source, target, (operation,)))
    slept = False

    def checkpoint() -> None:
        if fs.failed:
            raise PauseRequested()

    def sleep(_delay: float) -> None:
        nonlocal slept
        slept = True

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(lambda _: None, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    assert fs.attempts == 1
    assert not slept
    assert operation.op_id not in xset.status
    assert not (target / "file.bin").exists()
    assert not list(target.glob("*.synctmp-*"))


def test_production_retry_sleep_budget_is_350_milliseconds() -> None:
    policy = BoundedFailurePolicy()
    error = OSError("sharing violation")
    error.winerror = 32  # type: ignore[attr-defined]
    operation = object()

    decisions = [
        policy.on_item_failed(operation, error, attempt)  # type: ignore[arg-type]
        for attempt in range(1, 5)
    ]
    delays = [decision.after for decision in decisions if isinstance(decision, Retry)]

    assert delays == pytest.approx([0.05, 0.1, 0.2])
    assert sum(delays) == pytest.approx(0.35)


class ReplaceSharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def replace(self, temp: Path, target: Path) -> None:
        self.attempts += 1
        if self.attempts == 1:
            error = OSError("sharing violation during replace")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error
        super().replace(temp, target)


@pytest.mark.parametrize("hardlinks", [True, False])
def test_update_retries_replace_without_restarting_after_backup(
    tmp_path: Path, hardlinks: bool
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingOnceFileSystem()
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

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=hardlinks)), fs=fs
    )

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 2
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"old-version"
    assert [call[0] for call in recorder.calls] == ["updated"]


class ReplaceSharingAfterCommitFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def replace(self, temp: Path, target: Path) -> None:
        self.attempts += 1
        super().replace(temp, target)
        error = OSError("sharing report after committed replace")
        error.winerror = 32  # type: ignore[attr-defined]
        raise error


def test_update_retry_recognizes_replace_that_committed_before_error(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingAfterCommitFileSystem()
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

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 1
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"old-version"
    assert [call[0] for call in recorder.calls] == ["updated"]


class BackupSharingAfterCommitFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def copy_backup(
        self,
        source,
        temp,
        target,
        source_expected,
        checkpoint,
        validate_destination,
    ) -> None:
        self.attempts += 1
        super().copy_backup(
            source,
            temp,
            target,
            source_expected,
            checkpoint,
            validate_destination,
        )
        error = OSError("sharing report after committed backup")
        error.winerror = 32  # type: ignore[attr-defined]
        raise error


def test_update_retry_recognizes_committed_copy_backup(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = BackupSharingAfterCommitFileSystem()
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

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)), fs=fs
    )

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 1
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"old-version"
    assert [call[0] for call in recorder.calls] == ["updated"]


class CopyBackupMetadataSharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.backup_metadata_attempts = 0
        self.replace_metadata_attempts: list[int] = []

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        if ".synctrash" in path.parts:
            self.backup_metadata_attempts += 1
            if self.backup_metadata_attempts == 1:
                observed = self.stat_path(path)
                assert observed is not None
                damaged_mtime = observed.mtime_ns + 10_000_000_000
                os.utime(path, ns=(damaged_mtime, damaged_mtime))
                error = OSError("sharing violation before backup metadata repair")
                error.winerror = 32  # type: ignore[attr-defined]
                raise error
        return super().ensure_published_metadata(path, *args, **kwargs)

    def replace(self, temp: Path, target: Path) -> None:
        self.replace_metadata_attempts.append(self.backup_metadata_attempts)
        super().replace(temp, target)


def test_copied_backup_metadata_repair_resumes_before_update_replace(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = CopyBackupMetadataSharingOnceFileSystem()
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

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)),
        fs=fs,
    )

    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    repaired = fs.stat_path(trash)
    assert result.status is SessionState.COMPLETED
    assert fs.backup_metadata_attempts == 2
    assert fs.replace_metadata_attempts == [2]
    assert repaired is not None
    assert repaired.mtime_ns == target_stat.mtime_ns
    assert trash.read_bytes() == b"old-version"
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert [call[0] for call in recorder.calls] == ["updated"]


class CopyBackupMetadataSharingAlwaysFileSystem(
    CopyBackupMetadataSharingOnceFileSystem
):
    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        if ".synctrash" in path.parts:
            self.backup_metadata_attempts += 1
            error = OSError("persistent backup metadata sharing violation")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error
        return NativeFileSystem.ensure_published_metadata(
            self,
            path,
            *args,
            **kwargs,
        )


def test_persistent_copied_backup_metadata_failure_prevents_update_replace(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = CopyBackupMetadataSharingAlwaysFileSystem()
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

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)),
        fs=fs,
    )

    assert result.status is SessionState.FAILED
    assert fs.backup_metadata_attempts == 3
    assert fs.replace_metadata_attempts == []
    assert (target / "file.bin").read_bytes() == b"old-version"
    assert recorder.calls == []


def test_resumed_update_rejects_target_drift_before_backup_metadata_repair(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = CopyBackupMetadataSharingOnceFileSystem()
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
    published_target = target / "file.bin"

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)),
        fs=fs,
        policies=_policies(
            sleep=lambda _delay: _replace_published_target(
                published_target,
                fs,
            )
        ),
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert item.reason == "target-drift"
    assert fs.backup_metadata_attempts == 1
    assert recorder.calls == []
    assert published_target.read_bytes() == b"bad-version"


class CopyBackupStatSharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.backup_created = False
        self.backup_stat_failed = False
        self.backup_copy_attempts = 0

    def copy_backup(
        self,
        source,
        temp,
        target,
        source_expected,
        checkpoint,
        validate_destination,
    ) -> None:
        self.backup_copy_attempts += 1
        super().copy_backup(
            source,
            temp,
            target,
            source_expected,
            checkpoint,
            validate_destination,
        )
        self.backup_created = True

    def stat_path(self, path: Path) -> FileStat | None:
        if (
            self.backup_created
            and not self.backup_stat_failed
            and ".synctrash" in path.parts
        ):
            self.backup_stat_failed = True
            error = OSError("sharing violation observing published backup")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error
        return super().stat_path(path)


def test_update_retry_retains_continuation_when_backup_stat_temporarily_fails(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = CopyBackupStatSharingOnceFileSystem()
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

    result, _, recorder = _run(
        _xset(_plan(source, target, (operation,), hardlinks=False)),
        fs=fs,
    )

    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert result.status is SessionState.COMPLETED
    assert fs.backup_copy_attempts == 1
    assert fs.backup_stat_failed
    assert trash.read_bytes() == b"old-version"
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert [call[0] for call in recorder.calls] == ["updated"]


class ReplaceSharingAlwaysFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def replace(self, temp: Path, target: Path) -> None:
        self.attempts += 1
        error = OSError("persistent replace sharing violation")
        error.winerror = 32  # type: ignore[attr-defined]
        raise error


def test_persistent_update_sharing_exhausts_policy_without_false_drift(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingAlwaysFileSystem()
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
        _xset(_plan(source, target, (operation,))), fs=fs
    )

    outcome = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert fs.attempts == 3
    assert outcome.reason == "sharing-violation"
    assert (target / "file.bin").read_bytes() == b"old-version"
    assert recorder.calls == []


def test_pause_during_update_retry_settles_then_resumes_without_trash_collision(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingOnceFileSystem()
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
    xset = _xset(_plan(source, target, (operation,)))
    pause_requested = False

    def sleep(_delay: float) -> None:
        nonlocal pause_requested
        pause_requested = True

    def checkpoint() -> None:
        if pause_requested:
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(lambda _: None, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert fs.attempts == 2
    assert xset.status == {operation.op_id: Outcome.SUCCEEDED}
    assert set(xset.published_evidence) == {operation.op_id}
    assert (target / "file.bin").read_bytes() == b"new-version"
    assert trash.read_bytes() == b"old-version"

    resumed, _, _ = _run(xset, fs=fs)
    assert resumed.status is SessionState.COMPLETED


@pytest.mark.parametrize(
    ("fs_factory", "expected_outcome", "expected_state"),
    [
        pytest.param(
            ReplaceSharingAlwaysFileSystem,
            Outcome.CANCELED,
            "backup-retained",
            id="before-publish",
        ),
        pytest.param(
            ReplaceSharingAfterCommitFileSystem,
            Outcome.FAILED,
            "target-published-with-backup",
            id="after-publish",
        ),
    ],
)
def test_cancel_during_update_retry_reports_owned_durable_state(
    tmp_path: Path,
    fs_factory: Callable[[], NativeFileSystem],
    expected_outcome: Outcome,
    expected_state: str,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = fs_factory()
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
    xset = _xset(_plan(source, target, (operation,)))
    cancel_requested = False
    events: list[object] = []

    def sleep(_delay: float) -> None:
        nonlocal cancel_requested
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert item.outcome is expected_outcome
    assert item.detail["durable_state"] == expected_state
    assert item.detail["backup_state"] == "retained"
    assert item.detail["backup_path"] == (
        f".synctrash\\{RUN_ID}\\file.bin"
    )
    assert trash.read_bytes() == b"old-version"
    assert not list(target.glob("*.synctmp-*"))
    assert xset.published_evidence == {}
    if expected_outcome is Outcome.CANCELED:
        assert item.reason == "canceled"
        assert xset.recording is RecordingStatus.OK
        assert (target / "file.bin").read_bytes() == b"old-version"
    else:
        assert item.reason == "canceled-after-publish"
        assert xset.recording is RecordingStatus.DEGRADED
        assert item.detail["recording"] == "degraded"
        assert (target / "file.bin").read_bytes() == b"new-version"


def test_cancel_during_update_retry_does_not_claim_replaced_backup(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingAlwaysFileSystem()
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
    xset = _xset(_plan(source, target, (operation,), hardlinks=False))
    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    cancel_requested = False
    events: list[object] = []

    def sleep(_delay: float) -> None:
        nonlocal cancel_requested
        retained = fs.stat_path(trash)
        assert retained is not None
        replacement = trash.with_name("replacement.bin")
        replacement.write_bytes(b"bad-version")
        os.utime(
            replacement,
            ns=(retained.mtime_ns, retained.mtime_ns),
        )
        os.replace(replacement, trash)
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.outcome is Outcome.CANCELED
    assert item.reason == "canceled"
    assert item.detail["backup_state"] == "changed"
    assert item.detail["backup_path"] == (
        f".synctrash\\{RUN_ID}\\file.bin"
    )
    assert item.detail["durable_state"] == "target-not-published"
    assert trash.read_bytes() == b"bad-version"
    assert (target / "file.bin").read_bytes() == b"old-version"


def test_cancel_after_failed_update_replace_does_not_claim_foreign_write(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingOnceFileSystem()
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
    xset = _xset(_plan(source, target, (operation,), hardlinks=False))
    cancel_requested = False
    events: list[object] = []

    def sleep(_delay: float) -> None:
        nonlocal cancel_requested
        (target / "file.bin").write_bytes(b"foreign-write")
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert item.outcome is Outcome.CANCELED
    assert item.reason == "canceled"
    assert item.detail["publish_state"] == "not-published"
    assert item.detail["target_state"] == "changed-before-publish"
    assert item.detail["durable_state"] == "backup-retained"
    assert xset.recording is RecordingStatus.OK
    assert xset.published_evidence == {}
    assert fs.attempts == 1
    assert (target / "file.bin").read_bytes() == b"foreign-write"
    assert trash.read_bytes() == b"old-version"
    assert not list(target.glob("*.synctmp-*"))


def test_cancel_update_settlement_rejects_matching_backup_decoy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "file.bin"
    live = target / "file.bin"
    source_path.write_bytes(b"new-version")
    live.write_bytes(b"old-version")
    redirected = tmp_path / "redirected-trash"
    redirected.mkdir()
    _require_directory_reparse(tmp_path, redirected)
    fs = ReplaceSharingAlwaysFileSystem()
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
    xset = _xset(_plan(source, target, (operation,)))
    trash = target / ".synctrash" / str(RUN_ID) / "file.bin"
    run_root = trash.parent
    detached = target / f".detached-trash-{RUN_ID}"
    real_stat_path = fs.stat_path
    decoy_stat: FileStat | None = None
    decoy_reads = 0
    swapped = False
    cancel_requested = False
    events: list[object] = []

    def matching_decoy_stat(path: Path) -> FileStat | None:
        nonlocal decoy_reads
        if swapped and path == trash:
            decoy_reads += 1
            assert decoy_stat is not None
            return decoy_stat
        return real_stat_path(path)

    monkeypatch.setattr(fs, "stat_path", matching_decoy_stat)

    def swap_before_cancel(_delay: float) -> None:
        nonlocal cancel_requested, decoy_stat, swapped
        decoy_stat = real_stat_path(trash)
        assert decoy_stat is not None
        run_root.rename(detached)
        _create_directory_reparse(run_root, redirected)
        (redirected / "file.bin").write_bytes(b"old-version")
        swapped = True
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=swap_before_cancel),
            fs,
        )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert swapped
    assert decoy_reads == 0
    assert item.outcome is Outcome.CANCELED
    assert item.reason == "canceled"
    assert item.detail["backup_state"] == "unverified"
    assert "reparse points" in item.detail["backup_state_error"]
    assert item.detail["durable_state"] == "target-not-published"
    assert live.read_bytes() == b"old-version"
    assert (detached / "file.bin").read_bytes() == b"old-version"
    assert (redirected / "file.bin").read_bytes() == b"old-version"
    assert xset.recording is RecordingStatus.OK
    assert xset.published_evidence == {}


def test_cancel_preempts_an_already_latched_durable_pause(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    (target / "file.bin").write_bytes(b"old-version")
    fs = ReplaceSharingAlwaysFileSystem()
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
    xset = _xset(_plan(source, target, (operation,)))
    backoff_started = False
    pause_observed = False

    def sleep(_delay: float) -> None:
        nonlocal backoff_started
        backoff_started = True

    def checkpoint() -> None:
        nonlocal pause_observed
        if not backoff_started:
            return
        if not pause_observed:
            pause_observed = True
            raise PauseRequested()
        raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(lambda _: None, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    assert pause_observed
    assert xset.status == {operation.op_id: Outcome.CANCELED}
    assert xset.published_evidence == {}
    assert (target / "file.bin").read_bytes() == b"old-version"


class RetryThenStopPolicy:
    def on_item_failed(self, operation, error, attempt):
        del operation, error
        return Retry(0) if attempt == 1 else Stop()


class ImmediateStopPolicy:
    def on_item_failed(self, operation, error, attempt):
        del operation, error, attempt
        return Stop()


def test_policy_stop_suppresses_latched_pause_and_settles_remaining_work(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "locked.bin").write_bytes(b"new")
    (target / "locked.bin").write_bytes(b"old")
    (source / "later.bin").write_bytes(b"later")
    fs = ReplaceSharingAlwaysFileSystem()
    locked_source = fs.stat(source, "locked.bin")
    locked_target = fs.stat(target, "locked.bin")
    later_source = fs.stat(source, "later.bin")
    assert locked_source is not None and locked_target is not None
    assert later_source is not None
    locked = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="locked.bin",
        target_rel_path="locked.bin",
        source_expected=locked_source,
        target_expected=locked_target,
        intended=locked_source,
    )
    later = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="later.bin",
        target_rel_path="later.bin",
        source_expected=later_source,
        target_expected=None,
        intended=later_source,
    )
    xset = _xset(_plan(source, target, (locked, later)))
    pause_requested = False

    def sleep(_delay: float) -> None:
        nonlocal pause_requested
        pause_requested = True

    def checkpoint() -> None:
        if pause_requested:
            raise PauseRequested()

    result, events, _ = _run(
        xset,
        fs=fs,
        checkpoint=checkpoint,
        policies=_policies(failure=RetryThenStopPolicy(), sleep=sleep),
    )

    items = [event for event in events if isinstance(event, ItemOutcome)]
    assert result.status is SessionState.FAILED
    assert [item.outcome for item in items] == [Outcome.FAILED, Outcome.CANCELED]
    assert items[1].reason == "policy-stop"
    assert not (target / "later.bin").exists()


def test_cancel_interrupts_policy_stop_settlement_sweep(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    operations: list[PlanOperation] = []
    fs = PrepareSharingFileSystem()
    for index, name in enumerate(
        ("locked.bin", "stopped.bin", "cancel-now.bin", "unreached.bin"),
        start=1,
    ):
        (source / name).write_bytes(name.encode())
        source_stat = fs.stat(source, name)
        assert source_stat is not None
        operations.append(
            _operation(
                index,
                OperationKind.COPY,
                source_rel_path=name,
                target_rel_path=name,
                source_expected=source_stat,
                target_expected=None,
                intended=source_stat,
            )
        )
    xset = _xset(_plan(source, target, tuple(operations)))
    checkpoint_calls = 0
    events: list[object] = []

    def checkpoint() -> None:
        nonlocal checkpoint_calls
        checkpoint_calls += 1
        if checkpoint_calls == 3:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(failure=ImmediateStopPolicy()),
            fs,
        )

    items = [event for event in events if isinstance(event, ItemOutcome)]
    assert checkpoint_calls == 3
    assert [item.outcome for item in items] == [
        Outcome.FAILED,
        Outcome.CANCELED,
        Outcome.CANCELED,
        Outcome.CANCELED,
    ]
    assert [item.reason for item in items] == [
        "sharing-violation",
        "policy-stop",
        "canceled",
        "canceled",
    ]


class PersistentSharingFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def publish_new(self, temp: Path, target: Path) -> None:
        if target.name == "locked.bin":
            self.attempts += 1
            error = OSError("persistent sharing violation")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error
        super().publish_new(temp, target)


def test_persistent_sharing_is_bounded_and_independent_work_continues(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "locked.bin").write_bytes(b"locked")
    (source / "free.bin").write_bytes(b"free")
    fs = PersistentSharingFileSystem()
    locked_stat = fs.stat(source, "locked.bin")
    free_stat = fs.stat(source, "free.bin")
    assert locked_stat is not None and free_stat is not None
    locked = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="locked.bin",
        target_rel_path="locked.bin",
        source_expected=locked_stat,
        target_expected=None,
        intended=locked_stat,
    )
    free = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="free.bin",
        target_rel_path="free.bin",
        source_expected=free_stat,
        target_expected=None,
        intended=free_stat,
    )

    result, events, _ = _run(_xset(_plan(source, target, (locked, free))), fs=fs)

    assert result.status is SessionState.FAILED
    assert fs.attempts == 3
    assert not (target / "locked.bin").exists()
    assert (target / "free.bin").read_bytes() == b"free"
    outcome = next(
        event
        for event in events
        if isinstance(event, ItemOutcome) and event.item_id == str(locked.op_id)
    )
    assert outcome.reason == "sharing-violation"


def test_recorder_failure_preserves_filesystem_success_and_degrades_axis(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"copied")
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

    xset = _xset(_plan(source, target, (operation,)))
    result, events, _ = _run(
        xset,
        fs=fs,
        recorder=FakeRecorder(fail="copied"),
    )

    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.DEGRADED
    assert (target / "file.bin").read_bytes() == b"copied"
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.outcome is Outcome.SUCCEEDED
    assert item.detail["recording"] == "degraded"
    assert xset.recording is RecordingStatus.DEGRADED
    assert set(xset.published_evidence) == {operation.op_id}
    published = xset.published_evidence[operation.op_id]
    assert not published.copy_recorded
    assert published.recorded_identity is None


class MissingCopyIdentityRecorder(FakeRecorder):
    def record_copied(self, op, attestation) -> None:
        self._record("copied", op, attestation)


def test_copy_recorder_none_return_is_degraded_not_recorded(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"copied")
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
    xset = _xset(_plan(source, target, (operation,)))

    result, events, _ = _run(
        xset,
        fs=fs,
        recorder=MissingCopyIdentityRecorder(),
    )

    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.DEGRADED
    published = xset.published_evidence[operation.op_id]
    assert not published.copy_recorded
    assert published.recorded_identity is None
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert "did not return a recorded copy identity" in item.detail["recording_error"]


class FailFirstCopyRecorder(FakeRecorder):
    def __init__(self) -> None:
        super().__init__()
        self.copy_attempts = 0

    def record_copied(self, op, attestation) -> RecordedCopyIdentity:
        self.copy_attempts += 1
        if self.copy_attempts == 1:
            raise RuntimeError("injected first copy record failure")
        return super().record_copied(op, attestation)


def test_recording_truth_is_per_copy_while_aggregate_degradation_is_sticky(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operations = []
    for number, name in enumerate(("first.bin", "second.bin"), start=1):
        (source / name).write_bytes(name.encode("ascii"))
        source_stat = fs.stat(source, name)
        assert source_stat is not None
        operations.append(
            _operation(
                number,
                OperationKind.COPY,
                source_rel_path=name,
                target_rel_path=name,
                source_expected=source_stat,
                target_expected=None,
                intended=source_stat,
            )
        )
    xset = _xset(_plan(source, target, tuple(operations)))

    result, _, recorder = _run(
        xset,
        fs=fs,
        recorder=FailFirstCopyRecorder(),
    )

    first, second = operations
    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.DEGRADED
    assert xset.recording is RecordingStatus.DEGRADED
    assert set(xset.published_evidence) == {
        first.op_id,
        second.op_id,
    }
    assert not xset.published_evidence[first.op_id].copy_recorded
    assert xset.published_evidence[second.op_id].copy_recorded
    assert recorder.copy_attempts == 2


def test_trash_collision_preserves_live_item(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (target / "file.bin").write_bytes(b"live")
    collision = target / ".synctrash" / str(RUN_ID) / "file.bin"
    collision.parent.mkdir(parents=True)
    collision.write_bytes(b"existing-trash")
    fs = NativeFileSystem()
    target_stat = fs.stat(target, "file.bin")
    assert target_stat is not None
    operation = _operation(
        1,
        OperationKind.TRASH,
        source_rel_path=None,
        target_rel_path="file.bin",
        source_expected=None,
        target_expected=target_stat,
        intended=None,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / "file.bin").read_bytes() == b"live"
    assert collision.read_bytes() == b"existing-trash"
    assert recorder.calls == []


class UnsafeTrashFileSystem(NativeFileSystem):
    def trash_destination(self, target_root, run_id, relative_path):
        raise UnsafeExecutionPath("injected reparse/off-volume trash")


def test_unsafe_trash_is_refused_before_move(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (target / "file.bin").write_bytes(b"live")
    fs = UnsafeTrashFileSystem()
    target_stat = fs.stat(target, "file.bin")
    assert target_stat is not None
    operation = _operation(
        1,
        OperationKind.TRASH,
        source_rel_path=None,
        target_rel_path="file.bin",
        source_expected=None,
        target_expected=target_stat,
        intended=None,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / "file.bin").read_bytes() == b"live"
    assert recorder.calls == []


def _create_directory_reparse(link: Path, target: Path) -> None:
    if os.name != "nt":
        os.symlink(target, link, target_is_directory=True)
        return
    environment = os.environ.copy()
    environment["NAMISYNC_TEST_LINK"] = str(link)
    environment["NAMISYNC_TEST_TARGET"] = str(target)
    completed = subprocess.run(
        (
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "New-Item -ItemType Junction -Path $env:NAMISYNC_TEST_LINK "
            "-Target $env:NAMISYNC_TEST_TARGET -ErrorAction Stop | Out-Null",
        ),
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if completed.returncode:
        raise OSError(completed.stderr.strip() or "junction creation failed")


def _require_directory_reparse(tmp_path: Path, target: Path) -> None:
    probe = tmp_path / "directory-reparse-probe"
    try:
        _create_directory_reparse(probe, target)
    except OSError as error:
        pytest.skip(f"directory reparse creation unavailable: {error}")
    if os.name == "nt":
        probe.rmdir()
    else:
        probe.unlink()


def _with_reviewed_target_binding(plan: Plan, target: Path) -> Plan:
    target_snapshot = scan(
        Root(str(target), "target"),
        IgnoreSet(),
        RunContext(lambda _event: None, lambda: None),
    )
    assert target_snapshot.volume_id is not None
    assert target_snapshot.volume_evidence is not None
    return replace(
        plan,
        target_volume_id=target_snapshot.volume_id,
        target_volume_evidence=target_snapshot.volume_evidence,
    )


def _with_reviewed_source_binding(plan: Plan, source: Path) -> Plan:
    source_snapshot = scan(
        Root(str(source), "source"),
        IgnoreSet(),
        RunContext(lambda _event: None, lambda: None),
    )
    assert source_snapshot.volume_id is not None
    assert source_snapshot.volume_evidence is not None
    return replace(
        plan,
        source_volume_id=source_snapshot.volume_id,
        source_volume_evidence=source_snapshot.volume_evidence,
    )


class TargetRootReadGuardFileSystem(NativeFileSystem):
    def __init__(self, target_root: Path) -> None:
        self.target_root = target_root
        self.swapped = False
        self.decoy_stats: dict[str, FileStat] = {}
        self.decoy_reads: list[Path] = []
        self.replace_calls = 0

    def stat_path(self, path: Path) -> FileStat | None:
        if self.swapped and (
            path == self.target_root or self.target_root in path.parents
        ):
            self.decoy_reads.append(path)
            relative = str(path.relative_to(self.target_root)).replace(os.sep, "\\")
            return self.decoy_stats.get(relative)
        return super().stat_path(path)

    def replace(self, temp: Path, target: Path) -> None:
        self.replace_calls += 1
        super().replace(temp, target)


class PrepareBoundaryRootSwapFileSystem(TargetRootReadGuardFileSystem):
    def __init__(
        self,
        target_root: Path,
        redirected_root: Path,
        *,
        temp_name: str,
        swap_on_source_enter: bool,
    ) -> None:
        super().__init__(target_root)
        self.redirected_root = redirected_root
        self.temp_name = temp_name
        self.swap_on_source_enter = swap_on_source_enter
        self.detached_root = target_root.with_name(
            f"{target_root.name}-detached-{RUN_ID}"
        )
        self.create_calls = 0
        self.finalize_calls = 0

    def swap_root(self) -> None:
        if self.swapped:
            return
        temp = self.target_root / self.temp_name
        temp_stat = NativeFileSystem.stat_path(self, temp)
        temp_payload = None if temp_stat is None else temp.read_bytes()
        if temp_stat is not None:
            self.decoy_stats[self.temp_name] = temp_stat
        self.target_root.rename(self.detached_root)
        if temp_payload is not None:
            (self.redirected_root / self.temp_name).write_bytes(temp_payload)
        _create_directory_reparse(self.target_root, self.redirected_root)
        self.swapped = True

    def open_source(self, path: Path):
        stream = super().open_source(path)
        if not self.swap_on_source_enter:
            return stream
        owner = self

        class _SwapOnEnter:
            def __enter__(self):
                opened = stream.__enter__()
                owner.swap_root()
                return opened

            def __exit__(self, *args):
                return stream.__exit__(*args)

        return _SwapOnEnter()

    def create_temp(self, path: Path, *, allocation_size: int | None):
        self.create_calls += 1
        return super().create_temp(path, allocation_size=allocation_size)

    def finalize_temp(self, path: Path, *args, **kwargs) -> FileStat:
        self.finalize_calls += 1
        return super().finalize_temp(path, *args, **kwargs)


class RootSwapAfterCopyBackend(NativeCopyBackend):
    def __init__(self, swap_root: Callable[[], None]) -> None:
        super().__init__(hasher_factory=xxh3_128)
        self._swap_root = swap_root

    def copy(self, source, target, **kwargs) -> CopyDigest:
        digest = super().copy(source, target, **kwargs)
        target.flush()
        target.close()
        self._swap_root()
        return digest


@pytest.mark.parametrize(
    "swap_boundary",
    ("source-open", "after-copy"),
)
def test_copy_prepare_revalidates_root_after_blocking_boundaries(
    tmp_path: Path,
    swap_boundary: str,
) -> None:
    source, target = _roots(tmp_path)
    redirected = tmp_path / "redirected-target"
    redirected.mkdir()
    _require_directory_reparse(tmp_path, redirected)
    source_name = "file.bin"
    (source / source_name).write_bytes(b"new-version")
    setup_fs = NativeFileSystem()
    source_stat = setup_fs.stat(source, source_name)
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path=source_name,
        target_rel_path=source_name,
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    temp_name = f"{source_name}.synctmp-{RUN_ID}-{operation.op_id}"
    fs = PrepareBoundaryRootSwapFileSystem(
        target,
        redirected,
        temp_name=temp_name,
        swap_on_source_enter=swap_boundary == "source-open",
    )
    policies = (
        _policies()
        if swap_boundary == "source-open"
        else _policies(copy_backend=RootSwapAfterCopyBackend(fs.swap_root))
    )
    plan = _with_reviewed_target_binding(
        _plan(source, target, (operation,)),
        target,
    )

    result, events, recorder = _run(
        _xset(plan),
        fs=fs,
        policies=policies,
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert fs.swapped
    assert result.status is SessionState.FAILED
    assert item.outcome is Outcome.FAILED
    assert fs.create_calls == (0 if swap_boundary == "source-open" else 1)
    assert fs.finalize_calls == 0
    assert fs.decoy_reads == []
    assert recorder.calls == []
    assert not (fs.detached_root / source_name).exists()
    if swap_boundary == "source-open":
        assert not (fs.detached_root / temp_name).exists()
        assert not list(redirected.iterdir())
    else:
        assert (fs.detached_root / temp_name).read_bytes() == b"new-version"
        assert (redirected / temp_name).read_bytes() == b"new-version"


class TargetRootSwappingRecorder(FakeRecorder):
    def __init__(
        self,
        target_root: Path,
        redirected_root: Path,
        fs: TargetRootReadGuardFileSystem,
        *,
        live_name: str,
        temp_name: str,
    ) -> None:
        super().__init__()
        self.target_root = target_root
        self.redirected_root = redirected_root
        self.fs = fs
        self.live_name = live_name
        self.temp_name = temp_name
        self.detached_root = target_root.with_name(
            f"{target_root.name}-detached-{RUN_ID}"
        )
        self.swapped = False

    def flush(self) -> None:
        super().flush()
        if self.swapped:
            return
        live = self.target_root / self.live_name
        temp = self.target_root / self.temp_name
        live_stat = self.fs.stat_path(live)
        temp_stat = self.fs.stat_path(temp)
        assert live_stat is not None and temp_stat is not None
        self.fs.decoy_stats = {
            self.live_name: live_stat,
            self.temp_name: temp_stat,
        }
        live_payload = live.read_bytes()
        temp_payload = temp.read_bytes()
        self.target_root.rename(self.detached_root)
        (self.redirected_root / self.live_name).write_bytes(live_payload)
        (self.redirected_root / self.temp_name).write_bytes(temp_payload)
        _create_directory_reparse(self.target_root, self.redirected_root)
        self.fs.swapped = True
        self.swapped = True


def test_update_rejects_target_root_swap_after_recorder_barrier(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    redirected = tmp_path / "redirected-target"
    redirected.mkdir()
    _require_directory_reparse(tmp_path, redirected)
    source_name = "file.bin"
    (source / source_name).write_bytes(b"new-version")
    (target / source_name).write_bytes(b"old-version")
    fs = TargetRootReadGuardFileSystem(target)
    source_stat = fs.stat(source, source_name)
    target_stat = fs.stat(target, source_name)
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path=source_name,
        target_rel_path=source_name,
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    temp_name = f"{source_name}.synctmp-{RUN_ID}-{operation.op_id}"
    plan = _with_reviewed_target_binding(
        _plan(
            source,
            target,
            (operation,),
            trash_on_update=False,
        ),
        target,
    )
    recorder = TargetRootSwappingRecorder(
        target,
        redirected,
        fs,
        live_name=source_name,
        temp_name=temp_name,
    )

    result, events, _ = _run(_xset(plan), fs=fs, recorder=recorder)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert recorder.swapped
    assert result.status is SessionState.FAILED
    assert item.outcome is Outcome.FAILED
    assert item.detail["publish_state"] == "unverified"
    assert "reparse" in item.detail["state_error"].lower()
    assert fs.replace_calls == 0
    assert fs.decoy_reads == []
    assert recorder.calls == []
    assert (recorder.detached_root / source_name).read_bytes() == b"old-version"
    assert (recorder.detached_root / temp_name).read_bytes() == b"new-version"
    assert (redirected / source_name).read_bytes() == b"old-version"
    assert (redirected / temp_name).read_bytes() == b"new-version"


class PublishedBackoffRootSwapFileSystem(TargetRootReadGuardFileSystem):
    def __init__(self, target_root: Path, failure_point: str) -> None:
        super().__init__(target_root)
        self.failure_point = failure_point
        self.injected = False

    @staticmethod
    def _sharing_error() -> OSError:
        error = OSError("sharing report after publish")
        error.winerror = 32  # type: ignore[attr-defined]
        return error

    def publish_new(self, temp: Path, target: Path) -> None:
        super().publish_new(temp, target)
        if self.failure_point == "committed-publish" and not self.injected:
            self.injected = True
            raise self._sharing_error()

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        if self.failure_point == "published-metadata" and not self.injected:
            self.injected = True
            raise self._sharing_error()
        return super().ensure_published_metadata(path, *args, **kwargs)


@pytest.mark.parametrize(
    "failure_point",
    ("published-metadata", "committed-publish"),
)
def test_published_retry_rejects_matching_decoy_after_target_root_swap(
    tmp_path: Path,
    failure_point: str,
) -> None:
    source, target = _roots(tmp_path)
    redirected = tmp_path / "redirected-target"
    redirected.mkdir()
    _require_directory_reparse(tmp_path, redirected)
    source_name = "file.bin"
    (source / source_name).write_bytes(b"new-version")
    fs = PublishedBackoffRootSwapFileSystem(target, failure_point)
    source_stat = fs.stat(source, source_name)
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path=source_name,
        target_rel_path=source_name,
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    plan = _with_reviewed_target_binding(
        _plan(source, target, (operation,)),
        target,
    )
    detached = target.with_name(f"{target.name}-detached-{RUN_ID}")

    def swap_during_backoff(_delay: float) -> None:
        if fs.swapped:
            return
        published = target / source_name
        published_stat = NativeFileSystem.stat_path(fs, published)
        assert published_stat is not None
        payload = published.read_bytes()
        fs.decoy_stats[source_name] = published_stat
        target.rename(detached)
        (redirected / source_name).write_bytes(payload)
        _create_directory_reparse(target, redirected)
        fs.swapped = True

    result, events, recorder = _run(
        _xset(plan),
        fs=fs,
        policies=_policies(sleep=swap_during_backoff),
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert fs.injected and fs.swapped
    assert result.status is SessionState.FAILED
    assert item.outcome is Outcome.FAILED
    assert fs.decoy_reads == []
    assert recorder.calls == []
    assert (detached / source_name).read_bytes() == b"new-version"
    assert (redirected / source_name).read_bytes() == b"new-version"
    if failure_point == "published-metadata":
        assert item.detail["publish_state"] == "published"
        assert item.detail["target_state"] == "unverified-after-publish"
        assert "reparse" in item.detail["target_state_error"].lower()
    else:
        assert item.detail["publish_state"] == "unverified"
        assert item.detail["durable_state"] == "publication-unverified"
        assert "reparse" in item.detail["state_error"].lower()


class TrashParentSwappingRecorder(FakeRecorder):
    def __init__(self, target_root: Path, redirected_root: Path) -> None:
        super().__init__()
        self.target_root = target_root
        self.redirected_root = redirected_root
        self.detached_root = target_root / f".detached-trash-{RUN_ID}"
        self.swapped = False

    def flush(self) -> None:
        super().flush()
        if self.swapped:
            return
        run_root = self.target_root / ".synctrash" / str(RUN_ID)
        run_root.rename(self.detached_root)
        _create_directory_reparse(run_root, self.redirected_root)
        self.swapped = True


class TrashCommitThenParentSwapFileSystem(NativeFileSystem):
    def __init__(self, target_root: Path, redirected_root: Path) -> None:
        self.target_root = target_root
        self.redirected_root = redirected_root
        self.detached_root = target_root / f".detached-trash-{RUN_ID}"
        self.destination: Path | None = None
        self.decoy_stat: FileStat | None = None
        self.decoy_reads = 0

    def rename_new(self, source: Path, target: Path) -> None:
        if ".synctrash" not in target.parts:
            super().rename_new(source, target)
            return
        super().rename_new(source, target)
        self.destination = target
        self.decoy_stat = super().stat_path(target)
        assert self.decoy_stat is not None
        run_root = self.target_root / ".synctrash" / str(RUN_ID)
        run_root.rename(self.detached_root)
        _create_directory_reparse(run_root, self.redirected_root)
        (self.redirected_root / target.name).write_bytes(b"old-version")
        error = OSError("sharing report after committed trash rename")
        error.winerror = 32  # type: ignore[attr-defined]
        raise error

    def stat_path(self, path: Path) -> FileStat | None:
        if self.destination is not None and path == self.destination:
            self.decoy_reads += 1
            assert self.decoy_stat is not None
            return self.decoy_stat
        return super().stat_path(path)


@pytest.mark.parametrize(
    ("kind", "hardlinks"),
    (
        pytest.param(OperationKind.TRASH, True, id="trash"),
        pytest.param(OperationKind.UPDATE, True, id="update-hardlink"),
        pytest.param(OperationKind.UPDATE, False, id="update-copy"),
        pytest.param(OperationKind.MOVE_UPDATE, True, id="move-update"),
    ),
)
def test_owned_trash_parent_reparse_swap_during_recorder_flush_is_refused(
    tmp_path: Path,
    kind: OperationKind,
    hardlinks: bool,
) -> None:
    source, target = _roots(tmp_path)
    redirected = tmp_path / "redirected-trash"
    redirected.mkdir()
    _require_directory_reparse(tmp_path, redirected)

    old_name = "old.bin" if kind is OperationKind.MOVE_UPDATE else "file.bin"
    new_name = "new.bin" if kind is OperationKind.MOVE_UPDATE else "file.bin"
    old_path = target / old_name
    old_path.write_bytes(b"old-version")
    fs = NativeFileSystem()
    old_stat = fs.stat(target, old_name)
    assert old_stat is not None

    if kind is OperationKind.TRASH:
        operation = _operation(
            1,
            kind,
            source_rel_path=None,
            target_rel_path=old_name,
            source_expected=None,
            target_expected=old_stat,
            intended=None,
        )
    else:
        source_path = source / new_name
        source_path.write_bytes(b"new-version")
        source_stat = fs.stat(source, new_name)
        assert source_stat is not None
        operation = _operation(
            1,
            kind,
            source_rel_path=new_name,
            target_rel_path=new_name,
            source_expected=source_stat,
            target_expected=(old_stat if kind is OperationKind.UPDATE else None),
            intended=source_stat,
            prior_target_rel_path=(
                old_name if kind is OperationKind.MOVE_UPDATE else None
            ),
            prior_target_expected=(
                old_stat if kind is OperationKind.MOVE_UPDATE else None
            ),
        )

    recorder = TrashParentSwappingRecorder(target, redirected)
    result, events, _ = _run(
        _xset(_plan(source, target, (operation,), hardlinks=hardlinks)),
        fs=fs,
        recorder=recorder,
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert recorder.swapped
    assert recorder.flushes >= 1
    assert recorder.calls == []
    assert result.status is SessionState.FAILED
    assert item.outcome is Outcome.FAILED
    assert item.reason == "unsafe-path"
    swapped_root = target / ".synctrash" / str(RUN_ID)
    assert (
        swapped_root.is_junction()
        if os.name == "nt"
        else swapped_root.is_symlink()
    )
    assert old_path.read_bytes() == b"old-version"
    assert not list(redirected.iterdir())

    detached_backup = recorder.detached_root / old_name
    if kind is OperationKind.UPDATE:
        assert detached_backup.read_bytes() == b"old-version"
        assert not list(target.glob("*.synctmp-*"))
    else:
        assert not detached_backup.exists()
    if kind is OperationKind.MOVE_UPDATE:
        assert (target / new_name).read_bytes() == b"new-version"
        assert result.recording is RecordingStatus.DEGRADED
        assert item.detail["publish_state"] == "published"
    else:
        assert result.recording is RecordingStatus.OK
        assert "publish_state" not in item.detail
        if kind is OperationKind.UPDATE:
            assert (target / new_name).read_bytes() == b"old-version"


def test_failed_trash_settlement_rejects_matching_destination_decoy(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    live = target / "file.bin"
    live.write_bytes(b"old-version")
    redirected = tmp_path / "redirected-trash"
    redirected.mkdir()
    _require_directory_reparse(tmp_path, redirected)
    fs = TrashCommitThenParentSwapFileSystem(target, redirected)
    target_stat = fs.stat(target, "file.bin")
    assert target_stat is not None
    operation = _operation(
        1,
        OperationKind.TRASH,
        source_rel_path=None,
        target_rel_path="file.bin",
        source_expected=None,
        target_expected=target_stat,
        intended=None,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(failure=BoundedFailurePolicy(retries=0)),
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.outcome is Outcome.FAILED
    assert item.reason == "sharing-violation"
    assert item.detail["mutation_state"] == "unverified"
    assert item.detail["durable_state"] == "trash-state-unverified"
    assert "reparse points" in item.detail["mutation_state_error"]
    assert item.detail["recording"] == RecordingStatus.DEGRADED.value
    assert fs.decoy_reads == 0
    assert not live.exists()
    assert (fs.detached_root / "file.bin").read_bytes() == b"old-version"
    assert (redirected / "file.bin").read_bytes() == b"old-version"
    assert recorder.calls == []


def test_move_uses_nonreplacing_target_rename_and_records_result(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (target / "old.bin").write_bytes(b"moved")
    fs = NativeFileSystem()
    old_stat = fs.stat(target, "old.bin")
    assert old_stat is not None
    source_file = source / "new.bin"
    source_file.write_bytes(b"moved")
    os.utime(
        source_file,
        ns=(old_stat.mtime_ns, old_stat.mtime_ns),
    )
    source_stat = fs.stat(source, "new.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE,
        source_rel_path="new.bin",
        target_rel_path="new.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert not (target / "old.bin").exists()
    assert (target / "new.bin").read_bytes() == b"moved"
    assert recorder.calls[0][0] == "moved"
    assert result.bytes_total == 0


def test_move_refuses_vanished_reviewed_source_before_target_rename(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    source_file = source / "new.bin"
    source_file.write_bytes(b"same")
    (target / "old.bin").write_bytes(b"same")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "new.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE,
        source_rel_path="new.bin",
        target_rel_path="new.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
        reason=OperationReason.IDENTITY_RENAME,
    )
    source_file.unlink()

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
    )

    assert result.status is SessionState.FAILED
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.reason == "source-missing"
    assert (target / "old.bin").read_bytes() == b"same"
    assert not (target / "new.bin").exists()
    assert recorder.calls == []


def test_recase_renames_in_place_without_copy_or_trash(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "KEEP.txt").write_bytes(b"same")
    (target / "keep.txt").write_bytes(b"same")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "KEEP.txt")
    target_stat = fs.stat(target, "keep.txt")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.RECASE,
        source_rel_path="KEEP.txt",
        target_rel_path="KEEP.txt",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=target_stat,
        prior_target_rel_path="keep.txt",
        prior_target_expected=target_stat,
        reason=OperationReason.CASE_MISMATCH,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    recased = fs.stat(target, "KEEP.txt")
    assert result.status is SessionState.COMPLETED
    assert recased is not None
    assert recased.file_identity == target_stat.file_identity
    assert (target / "KEEP.txt").read_bytes() == b"same"
    assert [path.name for path in target.iterdir()] == ["KEEP.txt"]
    assert [call[0] for call in recorder.calls] == ["recased"]
    assert result.bytes_total == 0
    assert not (target / ".synctrash").exists()


def test_recase_refuses_source_drift_before_renaming_target(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    source_file = source / "KEEP.txt"
    source_file.write_bytes(b"same")
    (target / "keep.txt").write_bytes(b"same")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "KEEP.txt")
    target_stat = fs.stat(target, "keep.txt")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.RECASE,
        source_rel_path="KEEP.txt",
        target_rel_path="KEEP.txt",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=target_stat,
        prior_target_rel_path="keep.txt",
        prior_target_expected=target_stat,
        reason=OperationReason.CASE_MISMATCH,
    )
    source_file.unlink()

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    assert [path.name for path in target.iterdir()] == ["keep.txt"]
    assert recorder.calls == []


@pytest.mark.parametrize("old_missing", [False, True])
def test_move_occupancy_or_vanished_old_path_fails_without_overwrite(
    tmp_path: Path, old_missing: bool
) -> None:
    source, target = _roots(tmp_path)
    (target / "old.bin").write_bytes(b"old")
    fs = NativeFileSystem()
    old_stat = fs.stat(target, "old.bin")
    assert old_stat is not None
    source_file = source / "new.bin"
    source_file.write_bytes(b"old")
    os.utime(
        source_file,
        ns=(old_stat.mtime_ns, old_stat.mtime_ns),
    )
    source_stat = fs.stat(source, "new.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE,
        source_rel_path="new.bin",
        target_rel_path="new.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )
    if old_missing:
        (target / "old.bin").unlink()
    else:
        (target / "new.bin").write_bytes(b"occupant")

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))), fs=fs
    )

    assert result.status is SessionState.FAILED
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.reason == (
        "target-missing" if old_missing else "destination-occupied"
    )
    if not old_missing:
        assert (target / "old.bin").read_bytes() == b"old"
        assert (target / "new.bin").read_bytes() == b"occupant"
    assert recorder.calls == []


@pytest.mark.parametrize(
    ("kind", "source_name", "old_name", "new_name", "reason"),
    (
        (
            OperationKind.MOVE,
            "new.bin",
            "old.bin",
            "new.bin",
            OperationReason.IDENTITY_RENAME,
        ),
        (
            OperationKind.RECASE,
            "KEEP.txt",
            "keep.txt",
            "KEEP.txt",
            OperationReason.CASE_MISMATCH,
        ),
    ),
    ids=("move", "recase"),
)
def test_pure_rename_refuses_substituted_post_rename_identity(
    tmp_path: Path,
    kind: OperationKind,
    source_name: str,
    old_name: str,
    new_name: str,
    reason: OperationReason,
) -> None:
    source, target = _roots(tmp_path)
    source_file = source / source_name
    old_target = target / old_name
    source_file.write_bytes(b"same")
    old_target.write_bytes(b"same")

    class SubstitutingPostRenameFileSystem(NativeFileSystem):
        def __init__(self) -> None:
            self.renamed = False

        def rename_new(self, old: Path, new: Path) -> None:
            super().rename_new(old, new)
            self.renamed = True

        def stat_path(self, path: Path) -> FileStat | None:
            actual = super().stat_path(path)
            if (
                self.renamed
                and actual is not None
                and path.name == new_name
            ):
                identity = actual.file_identity
                assert identity is not None
                return replace(
                    actual,
                    file_identity=FileIdentity(
                        identity.volume_serial,
                        identity.file_index + 1,
                    ),
                )
            return actual

    fs = SubstitutingPostRenameFileSystem()
    old_stat = fs.stat(target, old_name)
    assert old_stat is not None
    os.utime(
        source_file,
        ns=(old_stat.mtime_ns, old_stat.mtime_ns),
    )
    source_stat = fs.stat(source, source_name)
    assert source_stat is not None
    operation = _operation(
        1,
        kind,
        source_rel_path=source_name,
        target_rel_path=new_name,
        source_expected=source_stat,
        target_expected=(
            old_stat if kind is OperationKind.RECASE else None
        ),
        intended=(
            old_stat if kind is OperationKind.RECASE else source_stat
        ),
        prior_target_rel_path=old_name,
        prior_target_expected=old_stat,
        reason=reason,
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
    )

    assert result.status is SessionState.FAILED
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert item.reason == "target-drift"
    assert recorder.calls == []


def test_composite_move_update_publishes_new_then_trashes_old(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )

    xset = _xset(_plan(source, target, (operation,)))
    result, _, recorder = _run(xset, fs=fs)

    assert result.status is SessionState.COMPLETED
    assert (target / "renamed.bin").read_bytes() == b"changed"
    assert not (target / "old.bin").exists()
    assert (target / ".synctrash" / str(RUN_ID) / "old.bin").read_bytes() == b"old"
    assert [call[0] for call in recorder.calls] == ["move_updated"]
    assert recorder.flushes == 2
    assert set(xset.published_evidence) == {operation.op_id}
    assert xset.published_evidence[operation.op_id].copy_recorded


class MoveUpdateStageFaultStream:
    def __init__(
        self,
        stream,
        stage: str,
        fault: Callable[[str], None],
    ) -> None:
        self.stream = stream
        self.stage = stage
        self.fault = fault
        self.reads = 0
        self.writes = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def read(self, size: int) -> bytes:
        self.reads += 1
        if self.stage == "read" and self.reads == 2:
            self.fault("read")
        return self.stream.read(size)

    def write(self, data) -> int:
        self.writes += 1
        if self.stage == "write" and self.writes == 2:
            self.fault("write")
        return self.stream.write(data)

    def __getattr__(self, name: str):
        return getattr(self.stream, name)


class MoveUpdateStageFaultHasher:
    def __init__(self, fault: Callable[[str], None]) -> None:
        self.inner = xxh3_128()
        self.fault = fault
        self.updates = 0

    def update(self, data: bytes) -> None:
        self.updates += 1
        if self.updates == 2:
            self.fault("hash")
        self.inner.update(data)

    def digest(self) -> bytes:
        return self.inner.digest()


class MoveUpdateStageFaultFileSystem(NativeFileSystem):
    def __init__(
        self,
        stage: str,
        fault: Callable[[str], None],
    ) -> None:
        self.stage = stage
        self.fault = fault
        self.temp_paths: list[Path] = []

    def open_source(self, path: Path):
        stream = super().open_source(path)
        if self.stage == "read":
            return MoveUpdateStageFaultStream(stream, self.stage, self.fault)
        return stream

    def create_temp(self, path: Path, *, allocation_size: int | None):
        stream = super().create_temp(path, allocation_size=allocation_size)
        self.temp_paths.append(path)
        if self.stage == "prepare":
            stream.close()
            self.fault("prepare")
        if self.stage == "write":
            return MoveUpdateStageFaultStream(stream, self.stage, self.fault)
        return stream

    def finalize_temp(self, path: Path, *args, **kwargs) -> FileStat:
        result = super().finalize_temp(path, *args, **kwargs)
        if self.stage == "finalize":
            self.fault("finalize")
        return result

    def publish_new(self, temp: Path, target: Path) -> None:
        super().publish_new(temp, target)
        if self.stage == "publish":
            self.fault("publish")

    def ensure_published_metadata(
        self, path: Path, *args, **kwargs
    ) -> FileStat:
        result = super().ensure_published_metadata(path, *args, **kwargs)
        if self.stage == "post-metadata":
            self.fault("post-metadata")
        return result

    def rename_new(self, source: Path, target: Path) -> None:
        super().rename_new(source, target)
        if self.stage == "trash" and ".synctrash" in target.parts:
            self.fault("trash")

    def flush_directory(self, path: Path) -> bool:
        if self.stage == "directory-flush":
            self.fault("directory-flush")
        return super().flush_directory(path)


class MoveUpdateStageFaultRecorder(FakeRecorder):
    def __init__(
        self,
        stage: str,
        fault: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.stage = stage
        self.fault = fault
        self.move_update_attempts = 0

    def record_move_updated(self, op, attestation) -> RecordedCopyIdentity:
        self.move_update_attempts += 1
        if self.stage == "record":
            self.fault("record")
        return super().record_move_updated(op, attestation)


@pytest.mark.parametrize(
    ("stage", "expected_paths"),
    [
        pytest.param("prepare", "old-only", id="prepare"),
        pytest.param("read", "old-only", id="read"),
        pytest.param("hash", "old-only", id="hash"),
        pytest.param("write", "old-only", id="write"),
        pytest.param("finalize", "old-only", id="finalize"),
        pytest.param("publish", "both-live", id="publish"),
        pytest.param("post-metadata", "both-live", id="post-metadata"),
        pytest.param("attestation", "both-live", id="attestation"),
        pytest.param("trash", "new-and-trash", id="trash"),
        pytest.param("directory-flush", "new-and-trash", id="directory-flush"),
        pytest.param("record", "new-and-trash", id="record"),
    ],
)
def test_a15_move_update_stage_faults_never_lose_both_versions_or_false_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    expected_paths: str,
) -> None:
    source, target = _roots(tmp_path)
    payload = b"changed-content"
    old_payload = b"old-content"
    source_path = source / "new.bin"
    old_path = target / "old.bin"
    new_path = target / "new.bin"
    source_path.write_bytes(payload)
    old_path.write_bytes(old_payload)
    observed_faults: list[str] = []
    failure = RuntimeError(f"injected move-update {stage} failure")

    def fault(point: str) -> None:
        observed_faults.append(point)
        raise failure

    fs = MoveUpdateStageFaultFileSystem(stage, fault)
    source_stat = fs.stat(source, "new.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="new.bin",
        target_rel_path="new.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )
    if stage == "attestation":
        monkeypatch.setattr(
            executor_module,
            "_attestation",
            lambda *_args, **_kwargs: fault("attestation"),
        )
    hasher_factory = (
        (lambda: MoveUpdateStageFaultHasher(fault))
        if stage == "hash"
        else xxh3_128
    )
    recorder = MoveUpdateStageFaultRecorder(stage, fault)

    result, events, _ = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        recorder=recorder,
        policies=_policies(
            copy_backend=NativeCopyBackend(
                hasher_factory=hasher_factory,
            ),
            max_chunk_size=4,
        ),
    )

    trash_path = target / ".synctrash" / str(RUN_ID) / "old.bin"
    expected_temp = target / (
        f"new.bin.synctmp-{RUN_ID}-{operation.op_id}"
    )
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert observed_faults == [stage]
    assert old_path.exists() or new_path.exists()
    assert not expected_temp.exists()
    assert not list(target.rglob("*.synctmp-*"))
    assert recorder.calls == []

    if expected_paths == "old-only":
        assert old_path.read_bytes() == old_payload
        assert not new_path.exists()
        assert not trash_path.exists()
        assert fs.temp_paths == [expected_temp]
    elif expected_paths == "both-live":
        assert old_path.read_bytes() == old_payload
        assert new_path.read_bytes() == payload
        assert not trash_path.exists()
        assert fs.temp_paths == [expected_temp]
    else:
        assert not old_path.exists()
        assert new_path.read_bytes() == payload
        assert trash_path.read_bytes() == old_payload
        assert fs.temp_paths == [expected_temp]

    if stage == "record":
        assert result.status is SessionState.COMPLETED
        assert result.recording is RecordingStatus.DEGRADED
        assert item.outcome is Outcome.SUCCEEDED
        assert item.reason is None
        assert item.detail["recording"] == RecordingStatus.DEGRADED.value
        assert recorder.move_update_attempts == 1
    else:
        assert result.status is SessionState.FAILED
        assert item.outcome is Outcome.FAILED
        assert item.reason == "io-error"
        assert recorder.move_update_attempts == 0
        if stage in {
            "publish",
            "post-metadata",
            "attestation",
            "trash",
            "directory-flush",
        }:
            assert result.recording is RecordingStatus.DEGRADED
            assert item.detail["publish_state"] == "published"
            assert item.detail["recording"] == RecordingStatus.DEGRADED.value
        else:
            assert result.recording is RecordingStatus.OK
            assert "recording" not in item.detail


class MoveUpdateTrashSharingOnceFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def rename_new(self, source: Path, target: Path) -> None:
        if ".synctrash" in target.parts:
            self.attempts += 1
            if self.attempts == 1:
                error = OSError("sharing violation while trashing old path")
                error.winerror = 32  # type: ignore[attr-defined]
                raise error
        super().rename_new(source, target)


def test_move_update_retries_old_to_trash_without_republishing(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = MoveUpdateTrashSharingOnceFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 2
    assert (target / "renamed.bin").read_bytes() == b"changed"
    assert not (target / "old.bin").exists()
    assert (target / ".synctrash" / str(RUN_ID) / "old.bin").read_bytes() == b"old"
    assert [call[0] for call in recorder.calls] == ["move_updated"]
    assert recorder.flushes == 3


class MoveUpdateTrashSharingAfterCommitFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.attempts = 0

    def rename_new(self, source: Path, target: Path) -> None:
        if ".synctrash" in target.parts:
            self.attempts += 1
            super().rename_new(source, target)
            error = OSError("sharing report after committed trash rename")
            error.winerror = 32  # type: ignore[attr-defined]
            raise error
        super().rename_new(source, target)


def test_move_update_retry_recognizes_committed_old_to_trash_rename(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = MoveUpdateTrashSharingAfterCommitFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert fs.attempts == 1
    assert (target / "renamed.bin").read_bytes() == b"changed"
    assert not (target / "old.bin").exists()
    assert (target / ".synctrash" / str(RUN_ID) / "old.bin").read_bytes() == b"old"
    assert [call[0] for call in recorder.calls] == ["move_updated"]
    assert recorder.flushes == 2


def test_move_update_retry_revalidates_committed_trash_parent(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "renamed.bin"
    old_path = target / "old.bin"
    new_path = target / "renamed.bin"
    source_path.write_bytes(b"changed")
    old_path.write_bytes(b"old")
    redirected = tmp_path / "redirected-trash"
    redirected.mkdir()
    _require_directory_reparse(tmp_path, redirected)
    fs = MoveUpdateTrashSharingAfterCommitFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )
    run_root = target / ".synctrash" / str(RUN_ID)
    detached = target / f".detached-trash-{RUN_ID}"
    swapped = False

    def swap_before_retry(_delay: float) -> None:
        nonlocal swapped
        run_root.rename(detached)
        _create_directory_reparse(run_root, redirected)
        swapped = True

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(sleep=swap_before_retry),
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert swapped
    assert fs.attempts == 1
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.reason == "unsafe-path"
    assert item.detail["publish_state"] == "published"
    assert not old_path.exists()
    assert new_path.read_bytes() == b"changed"
    assert (detached / "old.bin").read_bytes() == b"old"
    assert not list(redirected.iterdir())
    assert recorder.calls == []


def test_pause_during_move_update_retry_settles_then_resumes_without_collision(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = MoveUpdateTrashSharingOnceFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    pause_requested = False

    def sleep(_delay: float) -> None:
        nonlocal pause_requested
        pause_requested = True

    def checkpoint() -> None:
        if pause_requested:
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(lambda _: None, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    trash = target / ".synctrash" / str(RUN_ID) / "old.bin"
    assert fs.attempts == 2
    assert xset.status == {operation.op_id: Outcome.SUCCEEDED}
    assert set(xset.published_evidence) == {operation.op_id}
    assert (target / "renamed.bin").read_bytes() == b"changed"
    assert not (target / "old.bin").exists()
    assert trash.read_bytes() == b"old"

    resumed, _, _ = _run(xset, fs=fs)
    assert resumed.status is SessionState.COMPLETED


@pytest.mark.parametrize(
    ("fs_factory", "expected_state"),
    [
        pytest.param(
            MoveUpdateTrashSharingOnceFileSystem,
            "new-and-old",
            id="old-still-live",
        ),
        pytest.param(
            MoveUpdateTrashSharingAfterCommitFileSystem,
            "new-and-trash",
            id="old-already-trashed",
        ),
    ],
)
def test_cancel_during_move_update_retry_reports_partial_publish(
    tmp_path: Path,
    fs_factory: Callable[[], NativeFileSystem],
    expected_state: str,
) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = fs_factory()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    cancel_requested = False
    events: list[object] = []

    def sleep(_delay: float) -> None:
        nonlocal cancel_requested
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=sleep),
            fs,
        )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    trash = target / ".synctrash" / str(RUN_ID) / "old.bin"
    assert item.outcome is Outcome.FAILED
    assert item.reason == "canceled-after-publish"
    assert item.detail["durable_state"] == expected_state
    assert item.detail["trash_path"] == (
        f".synctrash\\{RUN_ID}\\old.bin"
    )
    assert item.detail["recording"] == "degraded"
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence == {}
    assert (target / "renamed.bin").read_bytes() == b"changed"
    if expected_state == "new-and-old":
        assert (target / "old.bin").read_bytes() == b"old"
        assert not trash.exists()
    else:
        assert not (target / "old.bin").exists()
        assert trash.read_bytes() == b"old"


def test_cancel_move_update_settlement_rejects_matching_trash_decoy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    source_path = source / "renamed.bin"
    old_path = target / "old.bin"
    new_path = target / "renamed.bin"
    source_path.write_bytes(b"changed")
    old_path.write_bytes(b"old")
    redirected = tmp_path / "redirected-trash"
    redirected.mkdir()
    _require_directory_reparse(tmp_path, redirected)
    fs = MoveUpdateTrashSharingAfterCommitFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    trash = target / ".synctrash" / str(RUN_ID) / "old.bin"
    run_root = trash.parent
    detached = target / f".detached-trash-{RUN_ID}"
    real_stat_path = fs.stat_path
    decoy_stat: FileStat | None = None
    decoy_reads = 0
    swapped = False
    cancel_requested = False
    events: list[object] = []

    def matching_decoy_stat(path: Path) -> FileStat | None:
        nonlocal decoy_reads
        if swapped and path == trash:
            decoy_reads += 1
            assert decoy_stat is not None
            return decoy_stat
        return real_stat_path(path)

    monkeypatch.setattr(fs, "stat_path", matching_decoy_stat)

    def swap_before_cancel(_delay: float) -> None:
        nonlocal cancel_requested, decoy_stat, swapped
        decoy_stat = real_stat_path(trash)
        assert decoy_stat is not None
        run_root.rename(detached)
        _create_directory_reparse(run_root, redirected)
        (redirected / "old.bin").write_bytes(b"old")
        swapped = True
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            FakeRecorder(),
            _policies(sleep=swap_before_cancel),
            fs,
        )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert swapped
    assert decoy_reads == 0
    assert item.outcome is Outcome.FAILED
    assert item.reason == "canceled-after-publish"
    assert item.detail["durable_state"] == "new-and-old-unverified"
    assert "reparse points" in item.detail["trash_state_error"]
    assert item.detail["recording"] == RecordingStatus.DEGRADED.value
    assert not old_path.exists()
    assert new_path.read_bytes() == b"changed"
    assert (detached / "old.bin").read_bytes() == b"old"
    assert (redirected / "old.bin").read_bytes() == b"old"
    assert xset.recording is RecordingStatus.DEGRADED
    assert xset.published_evidence == {}


class CompositeTrashFaultFileSystem(NativeFileSystem):
    def rename_new(self, source: Path, target: Path) -> None:
        raise OSError("injected old-path trash failure")


def test_composite_fault_after_publish_leaves_both_versions_and_no_record(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "renamed.bin").write_bytes(b"changed")
    (target / "old.bin").write_bytes(b"old")
    fs = CompositeTrashFaultFileSystem()
    source_stat = fs.stat(source, "renamed.bin")
    old_stat = fs.stat(target, "old.bin")
    assert source_stat is not None and old_stat is not None
    operation = _operation(
        1,
        OperationKind.MOVE_UPDATE,
        source_rel_path="renamed.bin",
        target_rel_path="renamed.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
        prior_target_rel_path="old.bin",
        prior_target_expected=old_stat,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (operation,))), fs=fs)

    assert result.status is SessionState.FAILED
    assert (target / "renamed.bin").read_bytes() == b"changed"
    assert (target / "old.bin").read_bytes() == b"old"
    assert recorder.calls == []


def test_successful_trash_delete_and_noop_record_after_filesystem_result(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "same.bin").write_bytes(b"same")
    (target / "same.bin").write_bytes(b"same")
    (target / "trash.bin").write_bytes(b"trash")
    (target / "delete.bin").write_bytes(b"delete")
    fs = NativeFileSystem()
    source_same = fs.stat(source, "same.bin")
    target_same = fs.stat(target, "same.bin")
    trash_stat = fs.stat(target, "trash.bin")
    delete_stat = fs.stat(target, "delete.bin")
    assert all(value is not None for value in (source_same, target_same, trash_stat, delete_stat))
    noop = _operation(
        1,
        OperationKind.NOOP,
        source_rel_path="same.bin",
        target_rel_path="same.bin",
        source_expected=source_same,
        target_expected=target_same,
        intended=target_same,
    )
    trash = _operation(
        2,
        OperationKind.TRASH,
        source_rel_path=None,
        target_rel_path="trash.bin",
        source_expected=None,
        target_expected=trash_stat,
        intended=None,
    )
    delete = _operation(
        3,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="delete.bin",
        source_expected=None,
        target_expected=delete_stat,
        intended=None,
    )

    result, _, recorder = _run(_xset(_plan(source, target, (noop, trash, delete))), fs=fs)

    assert result.status is SessionState.COMPLETED
    assert not (target / "trash.bin").exists()
    assert (target / ".synctrash" / str(RUN_ID) / "trash.bin").read_bytes() == b"trash"
    assert not (target / "delete.bin").exists()
    assert [call[0] for call in recorder.calls] == ["noop", "trashed", "deleted"]


def test_recorder_flush_failure_blocks_destructive_delete(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (target / "file.bin").write_bytes(b"keep")
    fs = NativeFileSystem()
    target_stat = fs.stat(target, "file.bin")
    assert target_stat is not None
    operation = _operation(
        1,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="file.bin",
        source_expected=None,
        target_expected=target_stat,
        intended=None,
    )

    result, _, _ = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        recorder=FakeRecorder(fail="flush"),
    )

    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert (target / "file.bin").read_bytes() == b"keep"


class ReplacingFlushRecorder(FakeRecorder):
    def __init__(self, target: Path, replacement: bytes) -> None:
        super().__init__()
        self.target = target
        self.replacement = replacement

    def flush(self) -> None:
        super().flush()
        if self.flushes != 1:
            return
        reviewed = self.target.stat(follow_symlinks=False)
        foreign = self.target.with_name(f".{self.target.name}.foreign")
        foreign.write_bytes(self.replacement)
        os.utime(
            foreign,
            ns=(reviewed.st_atime_ns, reviewed.st_mtime_ns),
        )
        os.replace(foreign, self.target)


def test_update_final_guard_runs_after_recorder_barrier(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"new-version")
    live = target / "file.bin"
    live.write_bytes(b"reviewed-version")
    fs = NativeFileSystem()
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
    recorder = ReplacingFlushRecorder(live, b"foreign-version")
    xset = _xset(_plan(source, target, (operation,)))

    result, events, _ = _run(xset, fs=fs, recorder=recorder)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    backup = target / ".synctrash" / str(RUN_ID) / "file.bin"
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.OK
    assert item.reason == "target-drift"
    assert live.read_bytes() == b"foreign-version"
    assert backup.read_bytes() == b"reviewed-version"
    assert recorder.calls == []
    assert xset.published_evidence == {}


def test_delete_final_guard_runs_after_recorder_barrier(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    live = target / "file.bin"
    live.write_bytes(b"reviewed-version")
    fs = NativeFileSystem()
    target_stat = fs.stat(target, "file.bin")
    assert target_stat is not None
    operation = _operation(
        1,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="file.bin",
        source_expected=None,
        target_expected=target_stat,
        intended=None,
    )
    recorder = ReplacingFlushRecorder(live, b"foreign-version")

    result, events, _ = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        recorder=recorder,
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.OK
    assert item.reason == "target-drift"
    assert live.read_bytes() == b"foreign-version"
    assert recorder.calls == []


@pytest.mark.parametrize(
    "kind",
    (
        OperationKind.MOVE,
        OperationKind.RECASE,
        OperationKind.MOVE_UPDATE,
        OperationKind.TRASH,
    ),
    ids=("move", "recase", "move-update", "trash"),
)
def test_rename_final_guards_run_after_recorder_barrier(
    tmp_path: Path,
    kind: OperationKind,
) -> None:
    source, target = _roots(tmp_path)
    old_name = "keep.txt" if kind is OperationKind.RECASE else "old.bin"
    new_name = "KEEP.txt" if kind is OperationKind.RECASE else "new.bin"
    source_name = new_name
    reviewed = target / old_name
    reviewed.write_bytes(b"reviewed-version")
    fs = NativeFileSystem()
    old_stat = fs.stat(target, old_name)
    assert old_stat is not None

    if kind is OperationKind.TRASH:
        operation = _operation(
            1,
            kind,
            source_rel_path=None,
            target_rel_path=old_name,
            source_expected=None,
            target_expected=old_stat,
            intended=None,
        )
    else:
        source_file = source / source_name
        source_file.write_bytes(
            b"changed-version!"
            if kind is OperationKind.MOVE_UPDATE
            else b"reviewed-version"
        )
        if kind is not OperationKind.MOVE_UPDATE:
            os.utime(
                source_file,
                ns=(old_stat.mtime_ns, old_stat.mtime_ns),
            )
        source_stat = fs.stat(source, source_name)
        assert source_stat is not None
        operation = _operation(
            1,
            kind,
            source_rel_path=source_name,
            target_rel_path=new_name,
            source_expected=source_stat,
            target_expected=(
                old_stat if kind is OperationKind.RECASE else None
            ),
            intended=(
                old_stat if kind is OperationKind.RECASE else source_stat
            ),
            prior_target_rel_path=old_name,
            prior_target_expected=old_stat,
            reason=(
                OperationReason.CASE_MISMATCH
                if kind is OperationKind.RECASE
                else OperationReason.IDENTITY_RENAME
            ),
        )

    recorder = ReplacingFlushRecorder(reviewed, b"foreign!-version")
    xset = _xset(_plan(source, target, (operation,)))
    result, events, _ = _run(xset, fs=fs, recorder=recorder)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert item.reason == "target-drift"
    assert reviewed.read_bytes() == b"foreign!-version"
    assert recorder.calls == []
    assert recorder.flushes == 2
    if kind is OperationKind.MOVE_UPDATE:
        assert (target / new_name).read_bytes() == b"changed-version!"
        assert result.recording is RecordingStatus.DEGRADED
        assert xset.published_evidence == {}
    elif kind is OperationKind.RECASE:
        assert [path.name for path in target.iterdir()] == [old_name]
        assert result.recording is RecordingStatus.OK
    else:
        assert not (target / new_name).exists()
        assert result.recording is RecordingStatus.OK
    trash = target / ".synctrash" / str(RUN_ID) / old_name
    assert not trash.exists()


class NonByteMutationFaultFileSystem(NativeFileSystem):
    def __init__(
        self,
        primitive: str,
        *,
        commit: bool,
        sharing: bool = False,
    ) -> None:
        self.primitive = primitive
        self.commit = commit
        self.sharing = sharing
        self.faults = 0

    def _fault(self) -> None:
        self.faults += 1
        error = OSError("injected mutation fault")
        if self.sharing:
            error.winerror = 32  # type: ignore[attr-defined]
        raise error

    def rename_new(self, source: Path, target: Path) -> None:
        if self.primitive != "rename":
            return super().rename_new(source, target)
        if self.commit:
            super().rename_new(source, target)
        self._fault()

    def remove_file(self, path: Path) -> None:
        if self.primitive != "remove-file":
            return super().remove_file(path)
        if self.commit:
            super().remove_file(path)
        self._fault()

    def remove_directory(self, path: Path) -> None:
        if self.primitive != "remove-directory":
            return super().remove_directory(path)
        if self.commit:
            super().remove_directory(path)
        self._fault()

    def mkdir_new(self, path: Path) -> None:
        if self.primitive != "mkdir":
            return super().mkdir_new(path)
        if self.commit:
            super().mkdir_new(path)
        self._fault()


def _nonbyte_mutation_operation(
    source: Path,
    target: Path,
    fs: NativeFileSystem,
    kind: OperationKind,
    *,
    directory_delete: bool = False,
) -> PlanOperation:
    if kind is OperationKind.MKDIR:
        (source / "folder").mkdir()
        source_stat = fs.stat(source, "folder")
        assert source_stat is not None
        return _operation(
            1,
            kind,
            source_rel_path="folder",
            target_rel_path="folder",
            source_expected=source_stat,
            target_expected=None,
            intended=source_stat,
            reason=OperationReason.REQUIRED_DIRECTORY,
        )
    if kind is OperationKind.DELETE:
        name = "folder" if directory_delete else "old.bin"
        live = target / name
        live.mkdir() if directory_delete else live.write_bytes(b"reviewed")
        target_stat = fs.stat(target, name)
        assert target_stat is not None
        return _operation(
            1,
            kind,
            source_rel_path=None,
            target_rel_path=name,
            source_expected=None,
            target_expected=target_stat,
            intended=None,
            reason=(
                OperationReason.DIRECTORY_CLEANUP
                if directory_delete
                else OperationReason.TARGET_ONLY
            ),
        )
    if kind is OperationKind.TRASH:
        (target / "old.bin").write_bytes(b"reviewed")
        target_stat = fs.stat(target, "old.bin")
        assert target_stat is not None
        return _operation(
            1,
            kind,
            source_rel_path=None,
            target_rel_path="old.bin",
            source_expected=None,
            target_expected=target_stat,
            intended=None,
            reason=OperationReason.TARGET_ONLY,
        )

    old_name = "keep.txt" if kind is OperationKind.RECASE else "old.bin"
    new_name = "KEEP.txt" if kind is OperationKind.RECASE else "new.bin"
    (target / old_name).write_bytes(b"reviewed")
    old_stat = fs.stat(target, old_name)
    assert old_stat is not None
    source_file = source / new_name
    source_file.write_bytes(b"reviewed")
    os.utime(source_file, ns=(old_stat.mtime_ns, old_stat.mtime_ns))
    source_stat = fs.stat(source, new_name)
    assert source_stat is not None
    return _operation(
        1,
        kind,
        source_rel_path=new_name,
        target_rel_path=new_name,
        source_expected=source_stat,
        target_expected=old_stat if kind is OperationKind.RECASE else None,
        intended=old_stat if kind is OperationKind.RECASE else source_stat,
        prior_target_rel_path=old_name,
        prior_target_expected=old_stat,
        reason=(
            OperationReason.CASE_MISMATCH
            if kind is OperationKind.RECASE
            else OperationReason.IDENTITY_RENAME
        ),
    )


class ReviewedBindingSwapFileSystem(NativeFileSystem):
    def __init__(self, target_root: Path, *, swap_during_resolve: bool) -> None:
        self.target_root = target_root
        self.swap_during_resolve = swap_during_resolve
        self.swapped = False
        self.reviewed_refusals = 0
        self.rename_calls = 0
        self.remove_calls = 0
        self.mkdir_calls = 0

    def revalidate_root(
        self,
        root: Path,
        *,
        trusted_anchor: Path | None = None,
        expected_volume=None,
    ) -> None:
        if (
            self.swapped
            and root == self.target_root
            and trusted_anchor is not None
            and expected_volume is not None
        ):
            self.reviewed_refusals += 1
            raise UnsafeExecutionPath(
                "reviewed target anchor or volume changed"
            )
        super().revalidate_root(
            root,
            trusted_anchor=trusted_anchor,
            expected_volume=expected_volume,
        )

    def resolve(
        self,
        root: Path,
        relative_path: str,
        *,
        must_exist: bool,
    ) -> Path:
        resolved = super().resolve(
            root,
            relative_path,
            must_exist=must_exist,
        )
        if self.swap_during_resolve and root == self.target_root:
            self.swapped = True
        return resolved

    def rename_new(self, source: Path, target: Path) -> None:
        self.rename_calls += 1
        super().rename_new(source, target)

    def remove_file(self, path: Path) -> None:
        self.remove_calls += 1
        super().remove_file(path)

    def remove_directory(self, path: Path) -> None:
        self.remove_calls += 1
        super().remove_directory(path)

    def mkdir_new(self, path: Path) -> None:
        self.mkdir_calls += 1
        super().mkdir_new(path)


class ReviewedBindingSwapRecorder(FakeRecorder):
    def __init__(self, fs: ReviewedBindingSwapFileSystem) -> None:
        super().__init__()
        self.fs = fs

    def flush(self) -> None:
        super().flush()
        self.fs.swapped = True


class ReviewedSourceSwapFileSystem(NativeFileSystem):
    def __init__(
        self,
        source_root: Path,
        *,
        swap_after_source_resolve: bool = False,
    ) -> None:
        self.source_root = source_root
        self.swap_after_source_resolve = swap_after_source_resolve
        self.swapped = False
        self.matching_source_stat: FileStat | None = None
        self.reviewed_refusals = 0
        self.foreign_stat_reads = 0
        self.foreign_source_opens = 0
        self.source_opens = 0
        self.target_mutations = 0

    def revalidate_root(
        self,
        root: Path,
        *,
        trusted_anchor: Path | None = None,
        expected_volume=None,
    ) -> None:
        if (
            self.swapped
            and root == self.source_root
            and trusted_anchor is not None
            and expected_volume is not None
        ):
            self.reviewed_refusals += 1
            raise UnsafeExecutionPath(
                "reviewed source anchor or volume changed"
            )
        super().revalidate_root(
            root,
            trusted_anchor=trusted_anchor,
            expected_volume=expected_volume,
        )

    def stat(self, root: Path, relative_path: str) -> FileStat | None:
        if self.swapped and root == self.source_root:
            self.foreign_stat_reads += 1
            return self.matching_source_stat
        return super().stat(root, relative_path)

    def resolve(
        self,
        root: Path,
        relative_path: str,
        *,
        must_exist: bool,
    ) -> Path:
        resolved = super().resolve(
            root,
            relative_path,
            must_exist=must_exist,
        )
        if self.swap_after_source_resolve and root == self.source_root:
            self.swapped = True
        return resolved

    def open_source(self, path: Path):
        self.source_opens += 1
        if self.swapped:
            self.foreign_source_opens += 1
        return super().open_source(path)

    def publish_new(self, temp: Path, target: Path) -> None:
        self.target_mutations += 1
        super().publish_new(temp, target)

    def replace(self, temp: Path, target: Path) -> None:
        self.target_mutations += 1
        super().replace(temp, target)

    def rename_new(self, source: Path, target: Path) -> None:
        self.target_mutations += 1
        super().rename_new(source, target)


class ReviewedSourceSwapRecorder(FakeRecorder):
    def __init__(self, fs: ReviewedSourceSwapFileSystem) -> None:
        super().__init__()
        self.fs = fs

    def flush(self) -> None:
        super().flush()
        self.fs.swapped = True


def _identity_weak_operation(operation: PlanOperation) -> PlanOperation:
    assert operation.source_expected is not None
    intended = operation.intended
    return replace(
        operation,
        source_expected=replace(
            operation.source_expected,
            file_identity=None,
        ),
        intended=(
            None
            if intended is None
            else replace(intended, file_identity=None)
        ),
    )


def test_copy_refuses_reviewed_source_swap_before_open(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"matching-foreign-bytes")
    fs = ReviewedSourceSwapFileSystem(
        source,
        swap_after_source_resolve=True,
    )
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    operation = _identity_weak_operation(
        _operation(
            1,
            OperationKind.COPY,
            source_rel_path="file.bin",
            target_rel_path="file.bin",
            source_expected=source_stat,
            target_expected=None,
            intended=source_stat,
        )
    )
    fs.matching_source_stat = operation.source_expected
    plan = _with_reviewed_source_binding(
        replace(
            _plan(source, target, (operation,)),
            source_profile=replace(
                _profile(),
                stable_file_identity=False,
            ),
        ),
        source,
    )

    result, events, recorder = _run(_xset(plan), fs=fs)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert fs.swapped and fs.reviewed_refusals >= 1
    assert result.status is SessionState.FAILED
    assert item.outcome is Outcome.FAILED
    assert fs.source_opens == 0
    assert fs.foreign_source_opens == 0
    assert fs.foreign_stat_reads == 0
    assert fs.target_mutations == 0
    assert recorder.calls == []
    assert not (target / "file.bin").exists()


@pytest.mark.parametrize(
    "kind",
    (OperationKind.UPDATE, OperationKind.MOVE),
    ids=("update", "move"),
)
def test_source_swap_during_recorder_barrier_cannot_authorize_mutation(
    tmp_path: Path,
    kind: OperationKind,
) -> None:
    source, target = _roots(tmp_path)
    fs = ReviewedSourceSwapFileSystem(source)
    if kind is OperationKind.UPDATE:
        (source / "file.bin").write_bytes(b"new-version")
        (target / "file.bin").write_bytes(b"old-version")
        source_stat = fs.stat(source, "file.bin")
        target_stat = fs.stat(target, "file.bin")
        assert source_stat is not None and target_stat is not None
        operation = _operation(
            1,
            kind,
            source_rel_path="file.bin",
            target_rel_path="file.bin",
            source_expected=source_stat,
            target_expected=target_stat,
            intended=source_stat,
        )
    else:
        operation = _nonbyte_mutation_operation(source, target, fs, kind)
    operation = _identity_weak_operation(operation)
    fs.matching_source_stat = operation.source_expected
    plan = _with_reviewed_source_binding(
        replace(
            _plan(
                source,
                target,
                (operation,),
                trash_on_update=False,
            ),
            source_profile=replace(
                _profile(),
                stable_file_identity=False,
            ),
        ),
        source,
    )
    recorder = ReviewedSourceSwapRecorder(fs)

    result, events, _ = _run(
        _xset(plan),
        fs=fs,
        recorder=recorder,
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert fs.swapped and fs.reviewed_refusals >= 1
    assert result.status is SessionState.FAILED
    assert item.outcome is Outcome.FAILED
    assert fs.foreign_source_opens == 0
    assert fs.foreign_stat_reads == 0
    assert fs.target_mutations == 0
    assert recorder.calls == []
    if kind is OperationKind.UPDATE:
        assert fs.source_opens == 1
        assert (target / "file.bin").read_bytes() == b"old-version"
    else:
        assert fs.source_opens == 0
        assert (target / "old.bin").read_bytes() == b"reviewed"
        assert not (target / "new.bin").exists()


@pytest.mark.parametrize(
    "kind",
    (
        OperationKind.MOVE,
        OperationKind.RECASE,
        OperationKind.DELETE,
        OperationKind.MKDIR,
    ),
    ids=("move", "recase", "delete", "mkdir"),
)
def test_nonbyte_mutations_refuse_reviewed_target_binding_swap(
    tmp_path: Path,
    kind: OperationKind,
) -> None:
    source, target = _roots(tmp_path)
    fs = ReviewedBindingSwapFileSystem(
        target,
        swap_during_resolve=kind is OperationKind.MKDIR,
    )
    operation = _nonbyte_mutation_operation(source, target, fs, kind)
    plan = _with_reviewed_target_binding(
        _plan(source, target, (operation,)),
        target,
    )
    recorder = ReviewedBindingSwapRecorder(fs)

    result, events, _ = _run(
        _xset(plan),
        fs=fs,
        recorder=recorder,
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert fs.swapped
    assert fs.reviewed_refusals >= 1
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.OK
    assert item.outcome is Outcome.FAILED
    assert "mutation_state" not in item.detail
    assert "durable_state" not in item.detail
    assert fs.rename_calls == 0
    assert fs.remove_calls == 0
    assert fs.mkdir_calls == 0
    assert recorder.calls == []
    if kind is OperationKind.MOVE:
        assert (target / "old.bin").read_bytes() == b"reviewed"
        assert not (target / "new.bin").exists()
    elif kind is OperationKind.RECASE:
        assert [path.name for path in target.iterdir()] == ["keep.txt"]
    elif kind is OperationKind.DELETE:
        assert (target / "old.bin").read_bytes() == b"reviewed"
    else:
        assert not (target / "folder").exists()


@pytest.mark.parametrize(
    ("kind", "primitive", "directory_delete", "mutation_state", "durable_state"),
    (
        (OperationKind.MOVE, "rename", False, "committed", "target-renamed"),
        (OperationKind.RECASE, "rename", False, "unverified", "recase-state-unverified"),
        (OperationKind.TRASH, "rename", False, "committed", "target-trashed"),
        (OperationKind.DELETE, "remove-file", False, "committed", "target-deleted"),
        (OperationKind.DELETE, "remove-directory", True, "committed", "target-deleted"),
        (OperationKind.MKDIR, "mkdir", False, "unverified", "directory-present-after-create-attempt"),
    ),
    ids=("move", "recase", "trash", "delete-file", "delete-directory", "mkdir"),
)
def test_nonbyte_commit_then_raise_degrades_unrecorded_mutation(
    tmp_path: Path,
    kind: OperationKind,
    primitive: str,
    directory_delete: bool,
    mutation_state: str,
    durable_state: str,
) -> None:
    source, target = _roots(tmp_path)
    fs = NonByteMutationFaultFileSystem(primitive, commit=True)
    operation = _nonbyte_mutation_operation(
        source,
        target,
        fs,
        kind,
        directory_delete=directory_delete,
    )
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(xset, fs=fs)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.reason == "io-error"
    assert item.detail["mutation_state"] == mutation_state
    assert item.detail["durable_state"] == durable_state
    assert item.detail["recording"] == RecordingStatus.DEGRADED.value
    assert recorder.calls == []
    assert xset.published_evidence == {}
    if kind is OperationKind.MOVE:
        assert not (target / "old.bin").exists()
        assert (target / "new.bin").read_bytes() == b"reviewed"
    elif kind is OperationKind.RECASE:
        assert [path.name for path in target.iterdir()] == ["KEEP.txt"]
    elif kind is OperationKind.TRASH:
        assert not (target / "old.bin").exists()
        assert (target / ".synctrash" / str(RUN_ID) / "old.bin").exists()
    elif kind is OperationKind.DELETE:
        assert not (target / operation.target_rel_path).exists()
    else:
        assert (target / "folder").is_dir()


@pytest.mark.parametrize(
    ("kind", "primitive"),
    (
        (OperationKind.MOVE, "rename"),
        (OperationKind.DELETE, "remove-file"),
        (OperationKind.MKDIR, "mkdir"),
    ),
    ids=("move", "delete", "mkdir"),
)
def test_nonbyte_precommit_failure_keeps_recording_ok_when_state_is_unchanged(
    tmp_path: Path,
    kind: OperationKind,
    primitive: str,
) -> None:
    source, target = _roots(tmp_path)
    fs = NonByteMutationFaultFileSystem(primitive, commit=False)
    operation = _nonbyte_mutation_operation(source, target, fs, kind)
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(xset, fs=fs)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.OK
    assert "durable_state" not in item.detail
    assert "recording" not in item.detail
    assert recorder.calls == []
    assert xset.published_evidence == {}
    if kind is OperationKind.MOVE:
        assert (target / "old.bin").exists()
        assert not (target / "new.bin").exists()
    elif kind is OperationKind.DELETE:
        assert (target / "old.bin").exists()
    else:
        assert not (target / "folder").exists()


class DestinationAppearedRenameFileSystem(NativeFileSystem):
    def rename_new(self, source: Path, target: Path) -> None:
        target.write_bytes(b"foreign")
        raise FileExistsError(target)


def test_move_failure_with_retained_source_and_occupied_destination_is_ambiguous(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = DestinationAppearedRenameFileSystem()
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MOVE)
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(xset, fs=fs)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.reason == "destination-occupied"
    assert item.detail["source_state"] == "reviewed"
    assert item.detail["destination_state"] == "changed"
    assert item.detail["durable_state"] == "move-state-ambiguous"
    assert recorder.calls == []
    assert (target / "old.bin").read_bytes() == b"reviewed"
    assert (target / "new.bin").read_bytes() == b"foreign"


class PostMoveDurabilityDriftFileSystem(NativeFileSystem):
    def __init__(self, moved: Path) -> None:
        self.moved = moved
        self.faulted = False

    def flush_directory(self, path: Path) -> bool:
        if not self.faulted and self.moved.exists():
            self.moved.unlink()
            self.moved.write_bytes(b"foreign")
            self.faulted = True
            raise PermissionError("injected post-move durability fault")
        return super().flush_directory(path)


def test_committed_move_failure_probes_current_durable_state(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = PostMoveDurabilityDriftFileSystem(target / "new.bin")
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MOVE)
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(xset, fs=fs)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert fs.faulted
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.detail["mutation_state"] == "committed"
    assert item.detail["source_state"] == "absent"
    assert item.detail["destination_state"] == "changed"
    assert item.detail["durable_state"] == "move-state-ambiguous"
    assert recorder.calls == []
    assert not (target / "old.bin").exists()
    assert (target / "new.bin").read_bytes() == b"foreign"


def test_nonbyte_sharing_retry_retains_committed_mutation_state(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NonByteMutationFaultFileSystem("rename", commit=True, sharing=True)
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MOVE)
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(
        xset,
        fs=fs,
        policies=_policies(
            failure=BoundedFailurePolicy(retries=1),
            max_retries=1,
        ),
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert fs.faults == 1
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.detail["mutation_state"] == "committed"
    assert item.detail["durable_state"] == "target-renamed"
    assert recorder.calls == []
    assert xset.published_evidence == {}
    assert not (target / "old.bin").exists()
    assert (target / "new.bin").read_bytes() == b"reviewed"


def test_cancel_during_nonbyte_retry_settles_committed_mutation(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NonByteMutationFaultFileSystem("rename", commit=True, sharing=True)
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MOVE)
    xset = _xset(_plan(source, target, (operation,)))
    recorder = FakeRecorder()
    events: list[object] = []
    checkpoints = 0

    def checkpoint() -> None:
        nonlocal checkpoints
        checkpoints += 1
        if checkpoints == 2:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            recorder,
            _policies(),
            fs,
        )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert fs.faults == 1
    assert item.outcome is Outcome.FAILED
    assert item.reason == "canceled-after-mutation"
    assert item.detail["durable_state"] == "target-renamed"
    assert xset.recording is RecordingStatus.DEGRADED
    assert recorder.calls == []
    assert xset.published_evidence == {}
    assert not (target / "old.bin").exists()
    assert (target / "new.bin").read_bytes() == b"reviewed"


def test_pause_during_nonbyte_retry_settles_committed_mutation_before_pausing(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NonByteMutationFaultFileSystem("rename", commit=True, sharing=True)
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MOVE)
    xset = _xset(_plan(source, target, (operation,)))
    recorder = FakeRecorder()
    events: list[object] = []
    checkpoints = 0

    def checkpoint() -> None:
        nonlocal checkpoints
        checkpoints += 1
        if checkpoints == 2:
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            recorder,
            _policies(),
            fs,
        )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert fs.faults == 1
    assert item.outcome is Outcome.FAILED
    assert item.detail["mutation_state"] == "committed"
    assert item.detail["durable_state"] == "target-renamed"
    assert xset.recording is RecordingStatus.DEGRADED
    assert recorder.calls == []
    assert xset.published_evidence == {}
    assert not (target / "old.bin").exists()
    assert (target / "new.bin").read_bytes() == b"reviewed"


class NonByteMutationProbeFailureFileSystem(NonByteMutationFaultFileSystem):
    def stat_path(self, path: Path) -> FileStat | None:
        if self.faults:
            raise PermissionError("injected mutation-state probe failure")
        return super().stat_path(path)


def test_nonbyte_probe_failure_conservatively_degrades_recording(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NonByteMutationProbeFailureFileSystem("rename", commit=False)
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MOVE)
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(xset, fs=fs)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.detail["mutation_state"] == "unverified"
    assert item.detail["durable_state"] == "move-state-unverified"
    assert "PermissionError" in item.detail["mutation_state_error"]
    assert recorder.calls == []
    assert xset.published_evidence == {}
    assert (target / "old.bin").read_bytes() == b"reviewed"
    assert not (target / "new.bin").exists()


class CreatedDirectoryMetadataFailureFileSystem(NativeFileSystem):
    def __init__(self, target: Path) -> None:
        self.target = target

    def apply_metadata(self, path: Path, *args, **kwargs) -> None:
        if path == self.target:
            raise PermissionError("injected created-directory metadata failure")
        super().apply_metadata(path, *args, **kwargs)


def test_mkdir_deferred_metadata_failure_degrades_created_directory(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = CreatedDirectoryMetadataFailureFileSystem(target / "folder")
    operation = _nonbyte_mutation_operation(source, target, fs, OperationKind.MKDIR)
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(xset, fs=fs)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.detail["mutation_state"] == "committed"
    assert item.detail["durable_state"] == "directory-created"
    assert (target / "folder").is_dir()
    assert recorder.calls == []
    assert xset.published_evidence == {}


class ResumedDirectoryRestoreFileSystem(NativeFileSystem):
    def __init__(self, directory: Path, *, failure: str | None) -> None:
        self.directory = directory
        self.failure = failure
        self.restore_attempts = 0

    def apply_metadata(self, path: Path, *args, **kwargs) -> None:
        if path == self.directory:
            self.restore_attempts += 1
            if self.failure == "before":
                raise PermissionError("injected resumed-directory restore failure")
        super().apply_metadata(path, *args, **kwargs)
        if path == self.directory and self.failure == "after":
            raise PermissionError("injected post-restore failure")


def _resumed_directory_execution(
    source: Path,
    target: Path,
    fs: NativeFileSystem,
) -> tuple[ExecutionSet, PlanOperation, PlanOperation, FileStat]:
    source_directory = source / "folder"
    source_directory.mkdir()
    (source_directory / "child.bin").write_bytes(b"child")
    os.utime(source_directory, ns=(1_000_000_000, 1_000_000_000))
    (target / "folder").mkdir()
    directory_stat = fs.stat(source, "folder")
    child_stat = fs.stat(source, "folder\\child.bin")
    assert directory_stat is not None and child_stat is not None
    mkdir = _operation(
        1,
        OperationKind.MKDIR,
        source_rel_path="folder",
        target_rel_path="folder",
        source_expected=directory_stat,
        target_expected=None,
        intended=directory_stat,
        reason=OperationReason.REQUIRED_DIRECTORY,
    )
    copy = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="folder\\child.bin",
        target_rel_path="folder\\child.bin",
        source_expected=child_stat,
        target_expected=None,
        intended=child_stat,
        dependencies=(mkdir.op_id,),
    )
    xset = _xset(_plan(source, target, (mkdir, copy)))
    xset.status[mkdir.op_id] = Outcome.SUCCEEDED
    return xset, mkdir, copy, directory_stat


def test_resumed_directory_restore_failure_degrades_recording(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    directory = target / "folder"
    fs = ResumedDirectoryRestoreFileSystem(directory, failure="before")
    xset, mkdir, copy, _ = _resumed_directory_execution(source, target, fs)

    result, _, recorder = _run(xset, fs=fs)

    assert fs.restore_attempts == 1
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert xset.status[mkdir.op_id] is Outcome.SUCCEEDED
    assert xset.status[copy.op_id] is Outcome.SUCCEEDED
    assert [call[0] for call in recorder.calls] == ["copied"]


def test_resumed_directory_restore_then_raise_keeps_recording_truth(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    directory = target / "folder"
    fs = ResumedDirectoryRestoreFileSystem(directory, failure="after")
    xset, _, _, _ = _resumed_directory_execution(source, target, fs)

    result, _, recorder = _run(xset, fs=fs)

    assert fs.restore_attempts == 1
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.OK
    assert [call[0] for call in recorder.calls] == ["copied"]


def test_cancel_restores_resumed_directory_metadata_before_unwind(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    directory = target / "folder"
    fs = ResumedDirectoryRestoreFileSystem(directory, failure=None)
    xset, mkdir, copy, intended = _resumed_directory_execution(source, target, fs)
    recorder = FakeRecorder()
    events: list[object] = []

    def checkpoint() -> None:
        raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            recorder,
            _policies(),
            fs,
        )

    restored = fs.stat(target, "folder")
    assert restored is not None
    assert fs.restore_attempts == 1
    assert restored.mtime_ns == intended.mtime_ns
    assert xset.recording is RecordingStatus.OK
    assert xset.status[mkdir.op_id] is Outcome.SUCCEEDED
    assert xset.status[copy.op_id] is Outcome.CANCELED
    assert recorder.calls == []


class ReadonlyReplaceFailureFileSystem(NativeFileSystem):
    def __init__(self, target: Path, *, fail_restore: bool) -> None:
        self.target = target
        self.fail_restore = fail_restore
        self.restore_attempts = 0

    def replace(self, temp: Path, target: Path) -> None:
        raise PermissionError("injected replace failure")

    def apply_metadata(self, path: Path, *args, **kwargs) -> None:
        if path == self.target and kwargs.get("apply_readonly"):
            self.restore_attempts += 1
            if self.fail_restore:
                raise PermissionError("injected readonly restoration failure")
        super().apply_metadata(path, *args, **kwargs)


class CanceledReadonlyProbeFileSystem(NativeFileSystem):
    def __init__(
        self,
        target: Path,
        *,
        fail_restore: bool,
        commit_replace: bool = False,
    ) -> None:
        self.target = target
        self.fail_restore = fail_restore
        self.commit_replace = commit_replace
        self.restore_attempts = 0
        self.probe_failures = 0

    def replace(self, temp: Path, target: Path) -> None:
        if self.commit_replace:
            super().replace(temp, target)
        error = OSError("injected replace sharing failure")
        error.winerror = 32  # type: ignore[attr-defined]
        raise error

    def apply_metadata(self, path: Path, *args, **kwargs) -> None:
        if path == self.target and kwargs.get("apply_readonly"):
            self.restore_attempts += 1
            if self.fail_restore:
                error = OSError("injected readonly restoration sharing failure")
                error.winerror = 32  # type: ignore[attr-defined]
                raise error
        super().apply_metadata(path, *args, **kwargs)

    def stat_path(self, path: Path) -> FileStat | None:
        if path == self.target and self.probe_failures:
            self.probe_failures -= 1
            raise PermissionError("cancel publication-state probe unavailable")
        return super().stat_path(path)


@pytest.mark.parametrize("fail_restore", [False, True], ids=("restored", "restore-failed"))
def test_failed_readonly_update_reports_restoration_truth(
    tmp_path: Path,
    fail_restore: bool,
) -> None:
    source, target = _roots(tmp_path)
    (source / "readonly.bin").write_bytes(b"new-version")
    live = target / "readonly.bin"
    live.write_bytes(b"old-version")
    setup_fs = NativeFileSystem()
    expected = setup_fs.stat(target, "readonly.bin")
    assert expected is not None
    setup_fs.apply_metadata(
        live,
        replace(
            expected,
            metadata=replace(
                expected.metadata,
                attributes=expected.metadata.attributes | 1,
            ),
        ),
        preserve_created=True,
        apply_readonly=True,
    )
    fs = ReadonlyReplaceFailureFileSystem(live, fail_restore=fail_restore)
    source_stat = fs.stat(source, "readonly.bin")
    target_stat = fs.stat(target, "readonly.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="readonly.bin",
        target_rel_path="readonly.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,), trash_on_update=False))

    result, events, recorder = _run(xset, fs=fs)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    restored = fs.stat(target, "readonly.bin")
    assert restored is not None
    assert fs.restore_attempts == 1
    assert result.status is SessionState.FAILED
    assert live.read_bytes() == b"old-version"
    assert recorder.calls == []
    assert xset.published_evidence == {}
    if fail_restore:
        assert result.recording is RecordingStatus.DEGRADED
        assert not restored.metadata.attributes & 1
        assert item.detail["publish_state"] == "not-published"
        assert item.detail["mutation_state"] == "unverified"
        assert item.detail["durable_state"] == "target-metadata-changed-before-publish"
    else:
        assert result.recording is RecordingStatus.OK
        assert restored.metadata.attributes & 1
        assert "durable_state" not in item.detail


@pytest.mark.parametrize(
    ("fail_restore", "commit_replace"),
    ((False, False), (True, False), (False, True)),
    ids=("restored", "restore-failed", "published"),
)
def test_cancel_composes_byte_and_readonly_mutation_state(
    tmp_path: Path,
    fail_restore: bool,
    commit_replace: bool,
) -> None:
    source, target = _roots(tmp_path)
    (source / "readonly.bin").write_bytes(b"new-version")
    live = target / "readonly.bin"
    live.write_bytes(b"old-version")
    setup_fs = NativeFileSystem()
    expected = setup_fs.stat(target, "readonly.bin")
    assert expected is not None
    setup_fs.apply_metadata(
        live,
        replace(
            expected,
            metadata=replace(
                expected.metadata,
                attributes=expected.metadata.attributes | 1,
            ),
        ),
        preserve_created=True,
        apply_readonly=True,
    )
    fs = CanceledReadonlyProbeFileSystem(
        live,
        fail_restore=fail_restore,
        commit_replace=commit_replace,
    )
    source_stat = fs.stat(source, "readonly.bin")
    target_stat = fs.stat(target, "readonly.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.UPDATE,
        source_rel_path="readonly.bin",
        target_rel_path="readonly.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,), trash_on_update=False))
    recorder = FakeRecorder()
    cancel_requested = False
    events: list[object] = []

    def sleep(_delay: float) -> None:
        nonlocal cancel_requested
        if not commit_replace:
            fs.probe_failures = 1
        cancel_requested = True

    def checkpoint() -> None:
        if cancel_requested:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(events.append, checkpoint),
            recorder,
            _policies(sleep=sleep),
            fs,
        )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    observed = setup_fs.stat(target, "readonly.bin")
    assert observed is not None
    assert fs.probe_failures == 0
    assert item.outcome is Outcome.FAILED
    assert recorder.calls == []
    assert xset.published_evidence == {}
    assert not list(target.glob("*.synctmp-*"))
    if commit_replace:
        assert fs.restore_attempts == 0
        assert item.reason == "canceled-after-publish"
        assert item.detail["publish_state"] == "published"
        assert item.detail["durable_state"] == "target-published"
        assert "mutation_state" not in item.detail
        assert "mutation_durable_state" not in item.detail
        assert xset.recording is RecordingStatus.DEGRADED
        assert live.read_bytes() == b"new-version"
        assert not observed.metadata.attributes & 1
    elif fail_restore:
        assert fs.restore_attempts == 1
        assert item.reason == "canceled-after-mutation"
        assert xset.recording is RecordingStatus.DEGRADED
        assert not observed.metadata.attributes & 1
        assert item.detail["mutation_state"] == "unverified"
        assert item.detail["mutation_durable_state"] == (
            "target-metadata-changed-before-publish"
        )
        assert item.detail["recording"] == RecordingStatus.DEGRADED.value
    else:
        assert fs.restore_attempts == 1
        assert item.reason == "io-error"
        assert xset.recording is RecordingStatus.OK
        assert observed.metadata.attributes & 1
        assert "mutation_state" not in item.detail
        assert "mutation_durable_state" not in item.detail
        assert "recording" not in item.detail
    if not commit_replace:
        assert item.detail["publish_state"] == "unverified"
        assert item.detail["durable_state"] == "unverified"
        assert item.detail["state_error_type"] == "PermissionError"
        assert item.detail["state_error"] == (
            "cancel publication-state probe unavailable"
        )
        assert live.read_bytes() == b"old-version"


class FailingReadonlyDeleteFileSystem(NativeFileSystem):
    def __init__(self, target: Path, *, fail_restore: bool) -> None:
        self.target = target
        self.fail_restore = fail_restore
        self.restore_attempts = 0

    def remove_file(self, path: Path) -> None:
        raise PermissionError("injected delete failure")

    def apply_metadata(self, path: Path, *args, **kwargs) -> None:
        if path == self.target and kwargs.get("apply_readonly"):
            self.restore_attempts += 1
            if self.fail_restore:
                raise PermissionError("injected readonly restoration failure")
        super().apply_metadata(path, *args, **kwargs)


@pytest.mark.parametrize("fail_restore", [False, True], ids=("restored", "restore-failed"))
def test_failed_readonly_delete_reports_restoration_truth(
    tmp_path: Path,
    fail_restore: bool,
) -> None:
    source, target = _roots(tmp_path)
    live = target / "readonly.bin"
    live.write_bytes(b"keep")
    setup_fs = NativeFileSystem()
    expected = setup_fs.stat(target, "readonly.bin")
    assert expected is not None
    setup_fs.apply_metadata(
        live,
        replace(
            expected,
            metadata=replace(
                expected.metadata, attributes=expected.metadata.attributes | 1
            ),
        ),
        preserve_created=True,
        apply_readonly=True,
    )
    fs = FailingReadonlyDeleteFileSystem(live, fail_restore=fail_restore)
    expected = fs.stat(target, "readonly.bin")
    assert expected is not None
    operation = _operation(
        1,
        OperationKind.DELETE,
        source_rel_path=None,
        target_rel_path="readonly.bin",
        source_expected=None,
        target_expected=expected,
        intended=None,
    )
    xset = _xset(_plan(source, target, (operation,)))

    result, events, recorder = _run(xset, fs=fs)

    item = next(event for event in events if isinstance(event, ItemOutcome))
    restored = fs.stat(target, "readonly.bin")
    assert result.status is SessionState.FAILED
    assert live.read_bytes() == b"keep"
    assert restored is not None
    assert fs.restore_attempts == 1
    assert recorder.calls == []
    assert xset.published_evidence == {}
    if fail_restore:
        assert result.recording is RecordingStatus.DEGRADED
        assert not restored.metadata.attributes & 1
        assert item.detail["mutation_state"] == "unverified"
        assert item.detail["durable_state"] == "target-changed-after-delete-attempt"
    else:
        assert result.recording is RecordingStatus.OK
        assert restored.metadata.attributes & 1
        assert "durable_state" not in item.detail


class ExternalSwapAfterBackupFileSystem(NativeFileSystem):
    def hardlink(self, source: Path, target: Path) -> None:
        super().hardlink(source, target)
        source.unlink()
        source.write_bytes(b"external-swap")


def test_update_external_swap_after_backup_is_rejected_without_overwrite(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "file.bin").write_bytes(b"planned-new")
    (target / "file.bin").write_bytes(b"planned-old")
    fs = ExternalSwapAfterBackupFileSystem()
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
        _xset(_plan(source, target, (operation,))),
        fs=fs,
    )

    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert item.reason == "target-drift"
    assert (target / "file.bin").read_bytes() == b"external-swap"
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"planned-old"
    assert recorder.calls == []


def test_progress_rate_is_throttled_while_item_outcomes_remain_reliable(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operations: list[PlanOperation] = []
    for number in range(1, 21):
        name = f"file-{number}.bin"
        (source / name).write_bytes(b"same")
        (target / name).write_bytes(b"same")
        source_stat = fs.stat(source, name)
        target_stat = fs.stat(target, name)
        assert source_stat is not None and target_stat is not None
        operations.append(
            _operation(
                number,
                OperationKind.NOOP,
                source_rel_path=name,
                target_rel_path=name,
                source_expected=source_stat,
                target_expected=target_stat,
                intended=target_stat,
            )
        )

    result, events, _ = _run(
        _xset(_plan(source, target, tuple(operations))),
        fs=fs,
        policies=_policies(monotonic=lambda: 0.0, progress_interval_seconds=10.0),
    )

    assert result.status is SessionState.COMPLETED
    assert len([event for event in events if isinstance(event, Progress)]) == 2
    assert len([event for event in events if isinstance(event, ItemOutcome)]) == 20


def test_failed_copy_without_transferred_bytes_keeps_byte_progress_at_zero(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    path = source / "missing.bin"
    path.write_bytes(b"planned")
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "missing.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="missing.bin",
        target_rel_path="missing.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    path.unlink()

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))), fs=fs
    )

    progress = [event for event in events if isinstance(event, Progress)]
    item = next(event for event in events if isinstance(event, ItemOutcome))
    assert result.status is SessionState.FAILED
    assert item.reason == "source-missing"
    assert progress[-1].bytes_done == 0
    assert progress[-1].bytes_total == len(b"planned")
    assert recorder.calls == []
    assert not list(target.glob("*.synctmp-*"))


def test_executor_imports_core_but_no_sibling_module() -> None:
    source = Path(__file__).parents[1] / "namisync" / "modules" / "executor.py"
    text = source.read_text(encoding="utf-8")
    assert "namisync.modules." not in text
    assert "namisync.core" in text
    assert "WinDLL" not in inspect.getsource(NativeFileSystem)


def test_run_id_rejects_user_controlled_temp_name_material() -> None:
    with pytest.raises(ValueError):
        validated_run_id("../not-an-owned-id")
