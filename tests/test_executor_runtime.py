"""Executor runtime acceptance and regression tests."""

from __future__ import annotations

import ast
from dataclasses import replace
import inspect
import os
from pathlib import Path
import re
from threading import Event, Lock
import time
from typing import Callable

import pytest
from xxhash import xxh3_128

import namisync.modules.executor as executor_facade
import namisync.modules.executor.native as executor_module
import namisync.modules.executor.pipeline as executor_pipeline
import namisync.modules.executor.runtime as executor_runtime
from namisync.core.evidence import Outcome, Provenance, RecordingStatus
from namisync.core.events import ItemOutcome, Progress, Terminal
from namisync.core.execution import (
    CopyDigest,
    ExecutionReason,
    ItemRecordingReason,
    validated_run_id,
)
from namisync.core.models import (
    EntryKind,
    FileIdentity,
    FileStat,
    IgnoreSet,
    Root,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.planning import (
    OpId,
    OperationKind,
    OperationReason,
    Plan,
    PlanOperation,
)
from namisync.core.session import (
    Canceled,
    PauseRequested,
    RunContext,
    SessionState,
    run_session,
)
from namisync.modules.executor import (
    BoundedFailurePolicy,
    ExecutorPolicies,
    NativeCopyBackend,
    NativeFileSystem,
    UnsafeExecutionPath,
    execute,
)
from namisync.modules.executor.pipeline import (
    _PREALLOCATION_THRESHOLD,
    _allocation_size,
    _copy_chunk_size,
)
from namisync.modules.scanner import scan

from _executor_fixtures import (
    RUN_ID,
    FakeRecorder,
    FixedClock,
    _create_directory_reparse,
    _item_outcome,
    _operation,
    _plan,
    _policies,
    _profile,
    _recorder_names,
    _nonbyte_mutation_operation,
    _reviewed_byte_operation,
    _require_directory_reparse,
    _roots,
    _run,
    _sharing_violation,
    _xset,
)


def test_executor_derives_root_authority_from_reviewed_plan_facts(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    source_volume = VolumeId("SOURCE", "NTFS")
    target_volume = VolumeId("TARGET", "NTFS")
    plan = replace(
        _plan(source, target, ()),
        source_volume_id=source_volume,
        target_volume_id=target_volume,
        source_volume_evidence=VolumeEvidence(device_id=str(tmp_path)),
        target_volume_evidence=VolumeEvidence(device_id=str(tmp_path)),
    )
    xset = _xset(plan)

    source_authority = executor_runtime._source_root_authority(xset)
    target_authority = executor_runtime._target_root_authority(xset)

    assert source_authority.logical_root == plan.source_root.path
    assert source_authority.reviewed_anchor == str(tmp_path)
    assert source_authority.expected_volume_id == source_volume
    assert target_authority.logical_root == plan.target_root.path
    assert target_authority.reviewed_anchor == str(tmp_path)
    assert target_authority.expected_volume_id == target_volume


def test_executor_maps_invalid_plan_anchor_to_unsafe_path(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    source_file = source / "file.bin"
    source_file.write_bytes(b"reviewed")
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
    plan = replace(
        _plan(source, target, (operation,)),
        target_volume_id=fs._volume_id(target),
        target_volume_evidence=VolumeEvidence(device_id=str(source)),
    )

    result, events, recorder = _run(_xset(plan), fs=fs)

    item = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert item.outcome is Outcome.FAILED
    assert item.reason == "unsafe-path"
    assert not (target / "file.bin").exists()
    assert recorder.calls == []


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
    item = _item_outcome(events)
    assert "durability_warnings" not in item.detail


def test_executor_rejects_a_nonpositive_maximum_chunk() -> None:
    with pytest.raises(ValueError, match="maximum copy chunk size"):
        _policies(max_chunk_size=0)


def test_executor_policies_requires_an_explicit_copy_backend() -> None:
    with pytest.raises(TypeError):
        ExecutorPolicies()  # type: ignore[call-arg]


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
        assert op_id not in xset.status
        assert op_id not in xset.published_evidence
        if op_id in byte_ids:
            assert body.outcome is Outcome.SUCCEEDED

    result = execute(
        xset,
        RunContext(emit, lambda: None),
        FakeRecorder(),
        _policies(),
        fs,
    )

    assert result.status is SessionState.COMPLETED
    assert {OpId(item.item_id) for item in emitted} == set(xset.selection)
    assert set(xset.status) == set(xset.selection)
    assert set(xset.published_evidence) == byte_ids
    assert all(
        evidence.copy_recorded
        and evidence.attestation.content.provenance
        is Provenance.COPY_ATTESTED
        for evidence in xset.published_evidence.values()
    )


def test_one_shot_reliable_outcome_failure_replays_committed_copy_settlement(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    content = b"payload"
    (source / "copy.bin").write_bytes(content)
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "copy.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="copy.bin",
        target_rel_path="copy.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    recorder = FakeRecorder()
    accepted: list[ItemOutcome] = []
    outcome_attempts = 0
    original = OSError("reliable outcome sink failed")

    def emit(body: object) -> None:
        nonlocal outcome_attempts
        if isinstance(body, ItemOutcome):
            outcome_attempts += 1
            if outcome_attempts == 1:
                raise original
            accepted.append(body)

    with pytest.raises(OSError) as raised:
        execute(
            xset,
            RunContext(emit, lambda: None),
            recorder,
            _policies(),
            fs,
        )

    assert raised.value is original
    assert outcome_attempts == 2
    assert len(accepted) == 1
    assert accepted[0].outcome is Outcome.SUCCEEDED
    assert accepted[0].recording is RecordingStatus.OK
    assert accepted[0].recording_reason is None
    assert xset.status == {operation.op_id: Outcome.SUCCEEDED}
    published = xset.published_evidence[operation.op_id]
    assert published.recorded_identity == recorder._copy_identity(operation.op_id)
    assert xset.recording_reasons == {}
    assert xset.recording_issues == ()
    assert _recorder_names(recorder) == ["copied"]
    assert (target / "copy.bin").read_bytes() == content


def test_run_session_excludes_executor_outcomes_rejected_by_sink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    content = b"payload"
    (source / "copy.bin").write_bytes(content)
    fs = NativeFileSystem()
    source_stat = fs.stat(source, "copy.bin")
    assert source_stat is not None
    operation = _operation(
        1,
        OperationKind.COPY,
        source_rel_path="copy.bin",
        target_rel_path="copy.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )
    xset = _xset(_plan(source, target, (operation,)))
    recorder = FakeRecorder()
    accepted: list[object] = []
    retained: list[
        tuple[executor_runtime._EffectJournal, executor_runtime._Settled]
    ] = []
    original_retain = executor_runtime._EffectJournal.retain_pending_settlement

    def tracked_retain(
        journal: executor_runtime._EffectJournal,
        op_id: OpId,
        settled: executor_runtime._Settled,
    ) -> executor_runtime._Settled:
        value = original_retain(journal, op_id, settled)
        retained.append((journal, value))
        return value

    monkeypatch.setattr(
        executor_runtime._EffectJournal,
        "retain_pending_settlement",
        tracked_retain,
    )
    outcome_attempts = 0
    original = OSError("reliable outcome sink failed")
    secondary = OSError("reliable outcome sink still failed")

    def emit(body: object) -> None:
        nonlocal outcome_attempts
        if isinstance(body, ItemOutcome):
            outcome_attempts += 1
            raise original if outcome_attempts == 1 else secondary
        accepted.append(body)

    session_outcome = run_session(
        lambda ctx: execute(
            xset,
            ctx,
            recorder,
            _policies(),
            fs,
        ),
        emit=emit,
        checkpoint=lambda: None,
        settle=lambda _state, _result: None,
        finalize_audit=lambda _result: RecordingStatus.OK,
        publish_result=lambda _result: None,
    )

    assert outcome_attempts == 2
    assert xset.status == {}
    assert xset.published_evidence == {}
    assert xset.recording_reasons == {}
    assert len(retained) == 2
    journal, pending = retained[0]
    retry_journal, retry_pending = retained[1]
    assert retry_journal is journal
    assert retry_pending is pending
    assert journal.has_active_entry(operation.op_id)
    assert journal.pending_settlement(operation.op_id) is pending
    assert pending.outcome is Outcome.SUCCEEDED
    assert pending.recording_reason is None
    assert pending.published_evidence is not None
    assert (
        pending.published_evidence.recorded_identity
        == recorder._copy_identity(operation.op_id)
    )
    assert _recorder_names(recorder) == ["copied"]
    assert (target / "copy.bin").read_bytes() == content
    assert session_outcome.result is not None
    assert session_outcome.result.status is SessionState.FAILED
    assert session_outcome.result.items == ()
    assert session_outcome.result.error is not None
    assert session_outcome.result.error.type_name == "OSError"
    assert session_outcome.result.error.message == str(original)
    assert (
        session_outcome.result.bytes_done,
        session_outcome.result.bytes_total,
    ) == (len(content), len(content))
    terminal = next(body for body in accepted if isinstance(body, Terminal))
    assert terminal.result.status is SessionState.FAILED
    assert terminal.result.recording_degraded_items == 0
    final_progress = next(
        body for body in reversed(accepted) if isinstance(body, Progress)
    )
    assert (
        final_progress.items_done,
        final_progress.items_total,
        final_progress.bytes_done,
        final_progress.bytes_total,
    ) == (0, 1, len(content), len(content))


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
    item = _item_outcome(events)
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

    xset = _xset(_plan(source, target, (operation,)))
    result, events, recorder = _run(
        xset,
        fs=fs,
        policies=_policies(copy_backend=MutatingBackend(path)),
    )

    assert result.status is SessionState.FAILED
    assert not (target / "file.bin").exists()
    assert not list(target.glob("*.synctmp-*"))
    assert recorder.calls == []
    assert xset.recording_reasons == {}
    assert xset.recording_issues == ()
    outcome = _item_outcome(events)
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
    item = _item_outcome(events)
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
    item = _item_outcome(events)
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
    item = _item_outcome(events)
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

    item = _item_outcome(events)
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

    item = _item_outcome(events)
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
    item = _item_outcome(events)
    assert item.reason == "published-size-mismatch"
    if kind is OperationKind.MOVE_UPDATE:
        assert (target / "old.bin").read_bytes() == b"old"


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
    assert _recorder_names(recorder) == ["copied"]


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
    assert _recorder_names(recorder) == ["copied", "mkdir"]


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
    item = _item_outcome(events)
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
    reason, detail = executor_runtime._failure_reason_and_message(
        PermissionError(13, "denied", native)
    )

    assert reason is ExecutionReason.IO_ERROR
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
    assert _recorder_names(recorder) == ["trashed", "deleted"]


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
    assert _recorder_names(recorder) == ["moved", "deleted"]


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

    item = _item_outcome(events)
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

    item = _item_outcome(events)
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

    item = _item_outcome(events)
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

    item = _item_outcome(events)
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
        return _sharing_violation("sharing report after publish")

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

    item = _item_outcome(events)
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
        raise _sharing_violation("sharing report after committed trash rename")

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

    item = _item_outcome(events)
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

    item = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert item.outcome is Outcome.FAILED
    assert item.reason == "sharing-violation"
    assert item.detail["mutation_state"] == "unverified"
    assert item.detail["durable_state"] == "trash-state-unverified"
    assert "reparse points" in item.detail["mutation_state_error"]
    assert item.recording is RecordingStatus.DEGRADED
    assert item.recording_reason is ItemRecordingReason.UNRECORDED_MUTATION
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
    item = _item_outcome(events)
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
    assert _recorder_names(recorder) == ["recased"]
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
    item = _item_outcome(events)
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
    item = _item_outcome(events)
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
    assert _recorder_names(recorder) == ["move_updated"]
    assert recorder.flushes == 2
    assert set(xset.published_evidence) == {operation.op_id}
    assert xset.published_evidence[operation.op_id].copy_recorded


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
    assert _recorder_names(recorder) == ["noop", "trashed", "deleted"]


class FailFirstFlushRecorder(FakeRecorder):
    def flush(self) -> None:
        self.flushes += 1
        if self.flushes == 1:
            raise RuntimeError("injected first flush failure")


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

    xset = _xset(_plan(source, target, (operation,)))
    result, _, _ = _run(
        xset,
        fs=fs,
        recorder=FailFirstFlushRecorder(),
    )

    assert result.status is SessionState.FAILED
    assert result.recording is RecordingStatus.DEGRADED
    assert xset.recording_reasons == {
        operation.op_id: ItemRecordingReason.RECORDING_PREREQUISITE_FAILED
    }
    assert xset.recording_issues == ()
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

    item = _item_outcome(events)
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

    item = _item_outcome(events)
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

    item = _item_outcome(events)
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


class RootBindingCallSpyFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.revalidate_calls: list[Path] = []
        self.resolve_calls: list[tuple[Path, str, bool]] = []

    def revalidate_root(
        self,
        root: Path,
        *args,
        **kwargs,
    ) -> None:
        del args, kwargs
        self.revalidate_calls.append(root)

    def resolve(
        self,
        root: Path,
        relative_path: str,
        *,
        must_exist: bool,
    ) -> Path:
        self.resolve_calls.append((root, relative_path, must_exist))
        return root / relative_path


def test_target_root_guard_refuses_mismatched_runtime_root_before_touch(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    xset = _xset(_plan(source, target, ()))
    fs = RootBindingCallSpyFileSystem()

    with pytest.raises(
        UnsafeExecutionPath,
        match="target root does not match reviewed authority",
    ):
        executor_runtime._resolve_target_path(
            fs,
            xset,
            source,
            source / "file.bin",
            must_exist=False,
        )

    assert fs.revalidate_calls == []
    assert fs.resolve_calls == []


def test_source_root_guard_refuses_mismatched_runtime_root_before_touch(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    xset = _xset(_plan(source, target, ()))
    fs = RootBindingCallSpyFileSystem()

    with pytest.raises(
        UnsafeExecutionPath,
        match="source root does not match reviewed authority",
    ):
        executor_runtime._revalidate_source_root(fs, xset, target)

    assert fs.revalidate_calls == []
    assert fs.resolve_calls == []


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

    item = _item_outcome(events)
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

    item = _item_outcome(events)
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

    item = _item_outcome(events)
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

    item = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert item.reason == "target-drift"
    assert (target / "file.bin").read_bytes() == b"external-swap"
    assert (target / ".synctrash" / str(RUN_ID) / "file.bin").read_bytes() == b"planned-old"
    assert recorder.calls == []


def _active_operation_progress(
    events: list[object], operation: PlanOperation
) -> list[Progress]:
    return [
        event
        for event in events
        if isinstance(event, Progress) and event.item_id == str(operation.op_id)
    ]


def _assert_operation_progress_clears_after_outcome(
    events: list[object],
    operation: PlanOperation,
    *,
    clear_current_path: bool = False,
) -> None:
    outcome_index = next(
        index
        for index, event in enumerate(events)
        if isinstance(event, ItemOutcome)
        and event.item_id == str(operation.op_id)
    )
    following = [
        event
        for event in events[outcome_index + 1 :]
        if isinstance(event, Progress)
    ]
    assert following
    assert all(
        (
            event.item_id,
            event.item_type,
            event.item_attempt_id,
            event.item_bytes_done,
            event.item_bytes_total,
        )
        == (None, None, None, None, None)
        for event in following
    )
    assert following[0].current_path == (
        None if clear_current_path else operation.target_rel_path
    )


def test_progress_start_refuses_to_replace_an_active_operation(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    first = _reviewed_progress_copy(source, target, fs, b"first")
    second = replace(
        first,
        op_id=OpId("2" * 32),
        source_rel_path="second.bin",
        target_rel_path="second.bin",
    )
    timeline: list[object] = []
    tracker = executor_runtime._ProgressTracker(
        _xset(_plan(source, target, (first, second))),
        RunContext(timeline.append, lambda: None),
        _policies(progress_interval_seconds=0),
    )

    tracker.start(first)

    with pytest.raises(
        RuntimeError,
        match="cannot replace the active progress operation",
    ):
        tracker.start(second)

    latest = next(
        event for event in reversed(timeline) if isinstance(event, Progress)
    )
    assert (latest.item_id, latest.current_path) == (
        str(first.op_id),
        first.target_rel_path,
    )


def test_deferred_directories_leave_inactive_handoffs_before_settlement(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operations: list[PlanOperation] = []
    for number in range(1, 4):
        name = f"folder-{number}"
        (source / name).mkdir()
        source_stat = fs.stat(source, name)
        assert source_stat is not None
        operations.append(
            _operation(
                number,
                OperationKind.MKDIR,
                source_rel_path=name,
                target_rel_path=name,
                source_expected=source_stat,
                target_expected=None,
                intended=source_stat,
            )
        )

    result, timeline, _ = _run(
        _xset(_plan(source, target, tuple(operations))),
        fs=fs,
        policies=_policies(progress_interval_seconds=0),
    )

    first_outcome = next(
        index
        for index, event in enumerate(timeline)
        if isinstance(event, ItemOutcome)
    )
    before_settlement = [
        event
        for event in timeline[:first_outcome]
        if isinstance(event, Progress)
    ]
    assert result.status is SessionState.COMPLETED
    assert [event.item_id for event in before_settlement] == [
        None,
        str(operations[0].op_id),
        None,
        str(operations[1].op_id),
        None,
        str(operations[2].op_id),
        None,
    ]
    assert [
        (event.items_done, event.current_path)
        for event in before_settlement[2::2]
    ] == [
        (0, operation.target_rel_path) for operation in operations
    ]


def test_deferred_directory_handoff_precedes_child_copy_activation(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "folder").mkdir()
    (source / "folder" / "child.bin").write_bytes(b"child")
    fs = NativeFileSystem()
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
    )
    child = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="folder\\child.bin",
        target_rel_path="folder\\child.bin",
        source_expected=child_stat,
        target_expected=None,
        intended=child_stat,
        dependencies=(mkdir.op_id,),
    )

    result, timeline, _ = _run(
        _xset(_plan(source, target, (mkdir, child))),
        fs=fs,
        policies=_policies(progress_interval_seconds=0),
    )

    progress = [event for event in timeline if isinstance(event, Progress)]
    mkdir_active = next(
        index
        for index, event in enumerate(progress)
        if event.item_id == str(mkdir.op_id)
    )
    child_active = next(
        index
        for index, event in enumerate(progress)
        if event.item_id == str(child.op_id)
    )
    handoff = progress[mkdir_active + 1 : child_active]
    assert result.status is SessionState.COMPLETED
    assert len(handoff) == 1
    assert (
        handoff[0].items_done,
        handoff[0].items_total,
        handoff[0].current_path,
        handoff[0].item_id,
        handoff[0].item_type,
        handoff[0].item_attempt_id,
        handoff[0].item_bytes_done,
        handoff[0].item_bytes_total,
    ) == (0, 2, mkdir.target_rel_path, None, None, None, None, None)
    assert not any(
        isinstance(event, ItemOutcome)
        for event in timeline[: timeline.index(progress[child_active])]
    )


class ScriptedProgressCopyBackend:
    def __init__(
        self,
        attempts: tuple[tuple[int, ...], ...],
        *,
        failing_attempts: frozenset[int],
    ) -> None:
        self._attempts = attempts
        self._failing_attempts = failing_attempts
        self.calls = 0

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
        checkpoint()
        self.calls += 1
        attempt = self.calls
        chunks = self._attempts[attempt - 1]
        payload = source.read()
        offset = 0
        for size in chunks:
            chunk = payload[offset : offset + size]
            assert len(chunk) == size
            assert target.write(chunk) == size
            on_chunk(size)
            offset += size
        if attempt in self._failing_attempts:
            raise _sharing_violation(f"injected stream failure {attempt}")
        assert offset == len(payload)
        return CopyDigest(xxh3_128(payload).digest(), len(payload))


class OverreportingProgressCopyBackend:
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
        checkpoint()
        payload = source.read()
        assert target.write(payload) == len(payload)
        on_chunk(len(payload))
        on_chunk(len(payload))
        return CopyDigest(xxh3_128(payload).digest(), len(payload))


class FrozenTeardownProgressClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class PartialProgressCopyBackend:
    def __init__(
        self,
        clock: FrozenTeardownProgressClock,
        *,
        failure: Exception | None = None,
    ) -> None:
        self._clock = clock
        self._failure = failure
        self.cancel_requested = False

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
        checkpoint()
        chunk = source.read(16)
        assert len(chunk) == 16
        assert target.write(chunk) == 16
        self._clock.value = 0.2
        on_chunk(16)
        if self._failure is not None:
            raise self._failure
        self.cancel_requested = True
        checkpoint()
        raise AssertionError("cancellation checkpoint returned")


class PauseThenCompleteProgressCopyBackend:
    def __init__(self, clock: FrozenTeardownProgressClock) -> None:
        self._clock = clock
        self.calls = 0
        self.pause_requested = False

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
        checkpoint()
        self.calls += 1
        payload = source.read()
        if self.calls == 1:
            offset = 0
            for size in (8, 16):
                chunk = payload[offset : offset + size]
                assert len(chunk) == size
                assert target.write(chunk) == size
                offset += size
                self._clock.value = 0.2
                on_chunk(size)
            self.pause_requested = True
            checkpoint()
            raise AssertionError("pause checkpoint returned")

        for offset in range(0, len(payload), 8):
            chunk = payload[offset : offset + 8]
            assert target.write(chunk) == len(chunk)
            on_chunk(len(chunk))
        return CopyDigest(xxh3_128(payload).digest(), len(payload))


class FirstThrottleWindowPauseCopyBackend:
    def __init__(self) -> None:
        self.pause_requested = False

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
        checkpoint()
        chunk = source.read(48)
        assert len(chunk) == 48
        assert target.write(chunk) == 48
        on_chunk(48)
        self.pause_requested = True
        checkpoint()
        raise AssertionError("pause checkpoint returned")


class EscapingFailurePolicy:
    def on_item_failed(
        self,
        operation: PlanOperation,
        error: Exception,
        attempt: int,
    ) -> None:
        del operation, error, attempt
        raise RuntimeError("injected failure-policy escape")


class ProgressCleanupFailureFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.temp_created = False
        self.cleanup_attempts = 0

    def create_temp(self, path: Path, *, allocation_size: int | None):
        stream = super().create_temp(path, allocation_size=allocation_size)
        self.temp_created = True
        return stream

    def remove_owned_temp(self, path: Path) -> None:
        if self.temp_created and path.exists():
            self.cleanup_attempts += 1
            raise PermissionError("injected retry cleanup failure")
        super().remove_owned_temp(path)


class PublishedMetadataProgressRetryFileSystem(NativeFileSystem):
    def __init__(self) -> None:
        self.published_target: Path | None = None
        self.published_metadata_attempts = 0
        self.source_opens = 0

    def open_source(self, path: Path):
        self.source_opens += 1
        return super().open_source(path)

    def ensure_published_metadata(self, path: Path, *args, **kwargs) -> FileStat:
        if path == self.published_target:
            self.published_metadata_attempts += 1
            if self.published_metadata_attempts == 1:
                raise _sharing_violation("injected post-publication retry")
        return super().ensure_published_metadata(path, *args, **kwargs)


def _reviewed_progress_copy(
    source: Path,
    target: Path,
    fs: NativeFileSystem,
    payload: bytes,
) -> PlanOperation:
    (source / "file.bin").write_bytes(payload)
    source_stat = fs.stat(source, "file.bin")
    assert source_stat is not None
    return _operation(
        1,
        OperationKind.COPY,
        source_rel_path="file.bin",
        target_rel_path="file.bin",
        source_expected=source_stat,
        target_expected=None,
        intended=source_stat,
    )


def _assert_partial_progress_cleared_before_terminal(
    timeline: list[object],
    operation: PlanOperation,
    *,
    payload_size: int,
    expected_outcome: Outcome,
) -> None:
    outcome_index = next(
        index
        for index, event in enumerate(timeline)
        if isinstance(event, ItemOutcome)
        and event.item_id == str(operation.op_id)
    )
    terminal_index = next(
        index
        for index, event in enumerate(timeline)
        if isinstance(event, Terminal)
    )
    latest_progress_index = max(
        index
        for index, event in enumerate(timeline)
        if isinstance(event, Progress)
    )
    active_before_outcome = [
        event
        for event in timeline[:outcome_index]
        if isinstance(event, Progress)
        and event.item_id == str(operation.op_id)
    ]
    latest_progress = timeline[latest_progress_index]

    assert _item_outcome(timeline).outcome is expected_outcome
    assert (
        active_before_outcome[-1].item_bytes_done,
        active_before_outcome[-1].item_bytes_total,
    ) == (16, payload_size)
    assert outcome_index < latest_progress_index < terminal_index
    assert isinstance(latest_progress, Progress)
    assert (
        latest_progress.item_id,
        latest_progress.item_type,
        latest_progress.item_bytes_done,
        latest_progress.item_bytes_total,
    ) == (None, None, None, None)
    assert (
        latest_progress.items_done,
        latest_progress.items_total,
        latest_progress.bytes_done,
        latest_progress.bytes_total,
        latest_progress.current_path,
    ) == (1, 1, 16, payload_size, None)
    _assert_operation_progress_clears_after_outcome(
        timeline,
        operation,
        clear_current_path=True,
    )


def test_partial_copy_cancellation_clears_progress_before_terminal(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    payload = b"x" * 64
    fs = NativeFileSystem()
    operation = _reviewed_progress_copy(source, target, fs, payload)
    clock = FrozenTeardownProgressClock()
    backend = PartialProgressCopyBackend(clock)
    timeline: list[object] = []

    def checkpoint() -> None:
        if backend.cancel_requested:
            raise Canceled()

    session_outcome = run_session(
        lambda ctx: execute(
            _xset(_plan(source, target, (operation,))),
            ctx,
            FakeRecorder(),
            _policies(
                copy_backend=backend,
                monotonic=clock,
                progress_interval_seconds=0.1,
            ),
            fs,
        ),
        emit=timeline.append,
        checkpoint=checkpoint,
        settle=lambda _state, _result: None,
        finalize_audit=lambda _result: RecordingStatus.OK,
        publish_result=lambda _result: None,
    )

    assert session_outcome.result is not None
    assert session_outcome.result.status is SessionState.CANCELED
    _assert_partial_progress_cleared_before_terminal(
        timeline,
        operation,
        payload_size=len(payload),
        expected_outcome=Outcome.CANCELED,
    )


def test_cancellation_before_first_item_does_not_publish_an_unseen_path(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operation = _reviewed_progress_copy(source, target, fs, b"payload")
    xset = _xset(_plan(source, target, (operation,)))
    timeline: list[object] = []

    def cancel_before_first_item() -> None:
        raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(timeline.append, cancel_before_first_item),
            FakeRecorder(),
            _policies(
                monotonic=lambda: 0.0,
                progress_interval_seconds=0.1,
            ),
            fs,
        )

    progress = [event for event in timeline if isinstance(event, Progress)]
    outcome_index = timeline.index(_item_outcome(timeline))
    final_progress_index = next(
        index
        for index, event in reversed(tuple(enumerate(timeline)))
        if event is progress[-1]
    )
    assert xset.status == {operation.op_id: Outcome.CANCELED}
    assert outcome_index < final_progress_index
    assert (
        progress[-1].items_done,
        progress[-1].items_total,
        progress[-1].bytes_done,
        progress[-1].bytes_total,
        progress[-1].current_path,
    ) == (1, 1, 0, len(b"payload"), None)
    assert (
        progress[-1].item_id,
        progress[-1].item_type,
        progress[-1].item_bytes_done,
        progress[-1].item_bytes_total,
    ) == (None, None, None, None)


def test_fast_multi_item_cancellation_reports_all_reliable_settlements(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operations: list[PlanOperation] = []
    for number in range(1, 31):
        name = f"file-{number:02}.bin"
        (source / name).write_bytes(bytes((number,)) * 8)
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
    timeline: list[object] = []

    def checkpoint() -> None:
        if xset.status.get(operations[0].op_id) is Outcome.SUCCEEDED:
            raise Canceled()

    with pytest.raises(Canceled):
        execute(
            xset,
            RunContext(timeline.append, checkpoint),
            FakeRecorder(),
            _policies(
                monotonic=lambda: 0.0,
                progress_interval_seconds=0.1,
            ),
            fs,
        )

    outcomes = [event for event in timeline if isinstance(event, ItemOutcome)]
    progress = [event for event in timeline if isinstance(event, Progress)]
    assert len(outcomes) == 30
    assert [event.outcome for event in outcomes].count(Outcome.SUCCEEDED) == 1
    assert [event.outcome for event in outcomes].count(Outcome.CANCELED) == 29
    assert (
        progress[-1].items_done,
        progress[-1].items_total,
        progress[-1].bytes_done,
        progress[-1].bytes_total,
        progress[-1].current_path,
        progress[-1].item_id,
        progress[-1].item_type,
        progress[-1].item_bytes_done,
        progress[-1].item_bytes_total,
    ) == (30, 30, 8, 240, None, None, None, None, None)
    assert timeline.index(outcomes[-1]) < len(timeline) - 1
    assert xset.bytes_done_high_water == 8


def test_all_ordinary_failures_count_as_completed_items(tmp_path: Path) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operations: list[PlanOperation] = []
    for number in range(1, 7):
        name = f"missing-{number}.bin"
        source_path = source / name
        source_path.write_bytes(b"planned")
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
        source_path.unlink()

    result, events, _ = _run(
        _xset(_plan(source, target, tuple(operations))),
        fs=fs,
        policies=_policies(
            monotonic=lambda: 0.0,
            progress_interval_seconds=0.1,
        ),
    )

    outcomes = [event for event in events if isinstance(event, ItemOutcome)]
    final_progress = next(
        event for event in reversed(events) if isinstance(event, Progress)
    )
    assert result.status is SessionState.FAILED
    assert len(outcomes) == 6
    assert all(event.outcome is Outcome.FAILED for event in outcomes)
    assert (
        final_progress.items_done,
        final_progress.items_total,
        final_progress.bytes_done,
        final_progress.bytes_total,
    ) == (6, 6, 0, 42)
    assert (
        final_progress.item_id,
        final_progress.item_type,
        final_progress.item_bytes_done,
        final_progress.item_bytes_total,
    ) == (None, None, None, None)


def test_escaping_failure_policy_clears_progress_before_failed_terminal(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    payload = b"x" * 64
    fs = NativeFileSystem()
    operation = _reviewed_progress_copy(source, target, fs, payload)
    clock = FrozenTeardownProgressClock()
    backend = PartialProgressCopyBackend(
        clock,
        failure=OSError("injected stream failure"),
    )
    timeline: list[object] = []

    session_outcome = run_session(
        lambda ctx: execute(
            _xset(_plan(source, target, (operation,))),
            ctx,
            FakeRecorder(),
            _policies(
                copy_backend=backend,
                failure=EscapingFailurePolicy(),
                monotonic=clock,
                progress_interval_seconds=0.1,
            ),
            fs,
        ),
        emit=timeline.append,
        checkpoint=lambda: None,
        settle=lambda _state, _result: None,
        finalize_audit=lambda _result: RecordingStatus.OK,
        publish_result=lambda _result: None,
    )

    assert session_outcome.result is not None
    assert session_outcome.result.status is SessionState.FAILED
    assert session_outcome.result.error is not None
    assert session_outcome.result.error.type_name == "RuntimeError"
    _assert_partial_progress_cleared_before_terminal(
        timeline,
        operation,
        payload_size=len(payload),
        expected_outcome=Outcome.FAILED,
    )


def test_terminal_progress_sink_failure_remains_secondary_to_policy_escape(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operation = _reviewed_progress_copy(source, target, fs, b"x" * 64)
    clock = FrozenTeardownProgressClock()
    backend = PartialProgressCopyBackend(
        clock,
        failure=OSError("injected stream failure"),
    )
    timeline: list[object] = []
    outcome_seen = False
    sink_failures = 0

    def emit(body: object) -> None:
        nonlocal outcome_seen, sink_failures
        timeline.append(body)
        if isinstance(body, ItemOutcome):
            outcome_seen = True
        elif (
            outcome_seen
            and isinstance(body, Progress)
            and body.item_id is None
        ):
            sink_failures += 1
            raise OSError("injected terminal progress sink failure")

    with pytest.raises(
        RuntimeError,
        match="injected failure-policy escape",
    ) as raised:
        execute(
            _xset(_plan(source, target, (operation,))),
            RunContext(emit, lambda: None),
            FakeRecorder(),
            _policies(
                copy_backend=backend,
                failure=EscapingFailurePolicy(),
                monotonic=clock,
                progress_interval_seconds=0.1,
            ),
            fs,
        )

    notes = getattr(raised.value, "__notes__", ())
    assert sink_failures == 1
    assert _item_outcome(timeline).outcome is Outcome.FAILED
    assert any(
        "executor terminal progress emission also failed" in note
        and "injected terminal progress sink failure" in note
        for note in notes
    )


def test_partial_copy_pause_forces_latest_snapshot_and_resume_stays_monotonic(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    payload = b"x" * 64
    fs = NativeFileSystem()
    operation = _reviewed_progress_copy(source, target, fs, payload)
    xset = _xset(_plan(source, target, (operation,)))
    clock = FrozenTeardownProgressClock()
    backend = PauseThenCompleteProgressCopyBackend(clock)
    timeline: list[object] = []

    def pause_checkpoint() -> None:
        if backend.pause_requested:
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(timeline.append, pause_checkpoint),
            FakeRecorder(),
            _policies(
                copy_backend=backend,
                monotonic=clock,
                progress_interval_seconds=0.1,
            ),
            fs,
        )

    paused_progress = [
        event for event in timeline if isinstance(event, Progress)
    ]
    assert not any(isinstance(event, ItemOutcome) for event in timeline)
    paused_attempt_id = paused_progress[-1].item_attempt_id
    assert paused_attempt_id is not None
    assert {
        event.item_attempt_id
        for event in paused_progress
        if event.item_attempt_id is not None
    } == {paused_attempt_id}
    assert (
        paused_progress[-1].item_id,
        paused_progress[-1].item_type,
        paused_progress[-1].item_bytes_done,
        paused_progress[-1].item_bytes_total,
    ) == (str(operation.op_id), "operation", 24, len(payload))
    assert (
        paused_progress[-1].items_done,
        paused_progress[-1].items_total,
        paused_progress[-1].bytes_done,
        paused_progress[-1].bytes_total,
        paused_progress[-1].current_path,
    ) == (0, 1, 24, len(payload), operation.target_rel_path)
    assert xset.bytes_done_high_water == 24

    resume_start = len(timeline)
    backend.pause_requested = False
    result = execute(
        xset,
        RunContext(timeline.append, lambda: None),
        FakeRecorder(),
        _policies(
            copy_backend=backend,
            monotonic=clock,
            progress_interval_seconds=0,
        ),
        fs,
    )

    resumed_determinate = [
        event
        for event in timeline[resume_start:]
        if isinstance(event, Progress)
        and event.item_id == str(operation.op_id)
        and event.item_bytes_done is not None
    ]
    progress = [event for event in timeline if isinstance(event, Progress)]
    assert result.status is SessionState.COMPLETED
    assert backend.calls == 2
    assert resumed_determinate[0].item_attempt_id != paused_attempt_id
    assert (
        resumed_determinate[0].item_bytes_done,
        resumed_determinate[0].item_bytes_total,
        resumed_determinate[0].bytes_done,
    ) == (0, len(payload), 24)
    assert [event.bytes_done for event in progress] == sorted(
        event.bytes_done for event in progress
    )
    assert xset.bytes_done_high_water == len(payload)
    assert (target / "file.bin").read_bytes() == payload
    _assert_operation_progress_clears_after_outcome(timeline, operation)


def test_pause_inside_first_throttle_window_forces_coherent_live_snapshot(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    payload = b"x" * 64
    fs = NativeFileSystem()
    operation = _reviewed_progress_copy(source, target, fs, payload)
    xset = _xset(_plan(source, target, (operation,)))
    clock = FrozenTeardownProgressClock()
    backend = FirstThrottleWindowPauseCopyBackend()
    timeline: list[object] = []

    def checkpoint() -> None:
        if backend.pause_requested:
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(timeline.append, checkpoint),
            FakeRecorder(),
            _policies(
                copy_backend=backend,
                monotonic=clock,
                progress_interval_seconds=0.1,
            ),
            fs,
        )

    progress = [event for event in timeline if isinstance(event, Progress)]
    assert len(progress) == 2
    assert (
        progress[-1].items_done,
        progress[-1].items_total,
        progress[-1].bytes_done,
        progress[-1].bytes_total,
        progress[-1].current_path,
        progress[-1].item_id,
        progress[-1].item_type,
        progress[-1].item_bytes_done,
        progress[-1].item_bytes_total,
    ) == (
        0,
        1,
        48,
        len(payload),
        operation.target_rel_path,
        str(operation.op_id),
        "operation",
        48,
        len(payload),
    )
    assert xset.status == {}
    assert xset.bytes_done_high_water == 48


def test_pause_directory_finalization_retains_active_child_progress(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    (source / "folder").mkdir()
    payload = b"x" * 64
    (source / "folder" / "child.bin").write_bytes(payload)
    fs = NativeFileSystem()
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
    )
    child = _operation(
        2,
        OperationKind.COPY,
        source_rel_path="folder\\child.bin",
        target_rel_path="folder\\child.bin",
        source_expected=child_stat,
        target_expected=None,
        intended=child_stat,
        dependencies=(mkdir.op_id,),
    )
    xset = _xset(_plan(source, target, (mkdir, child)))
    clock = FrozenTeardownProgressClock()
    backend = PauseThenCompleteProgressCopyBackend(clock)
    timeline: list[object] = []

    def checkpoint() -> None:
        if backend.pause_requested:
            raise PauseRequested()

    with pytest.raises(PauseRequested):
        execute(
            xset,
            RunContext(timeline.append, checkpoint),
            FakeRecorder(),
            _policies(
                copy_backend=backend,
                monotonic=clock,
                progress_interval_seconds=0.1,
            ),
            fs,
        )

    outcomes = [event for event in timeline if isinstance(event, ItemOutcome)]
    final_progress = next(
        event
        for event in reversed(timeline)
        if isinstance(event, Progress)
    )
    assert xset.status == {mkdir.op_id: Outcome.SUCCEEDED}
    assert [(outcome.item_id, outcome.outcome) for outcome in outcomes] == [
        (str(mkdir.op_id), Outcome.SUCCEEDED)
    ]
    assert (
        final_progress.item_id,
        final_progress.item_type,
        final_progress.item_bytes_done,
        final_progress.item_bytes_total,
    ) == (str(child.op_id), "operation", 24, len(payload))
    assert (
        final_progress.items_done,
        final_progress.items_total,
        final_progress.bytes_done,
        final_progress.bytes_total,
        final_progress.current_path,
    ) == (1, 2, 24, len(payload), child.target_rel_path)
    assert xset.bytes_done_high_water == 24
    assert timeline.index(outcomes[0]) < len(timeline) - 1


@pytest.mark.parametrize(
    "kind",
    (OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE),
)
def test_byte_operation_progress_has_stable_identity_and_stream_lifecycle(
    tmp_path: Path, kind: OperationKind,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operation, _ = _reviewed_byte_operation(kind, source, target, fs)

    result, events, _ = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(max_chunk_size=4),
    )

    active = _active_operation_progress(events, operation)
    assert result.status is SessionState.COMPLETED
    assert active
    assert all(event.phase == "execute" for event in active)
    assert all(event.item_type == "operation" for event in active)
    assert (active[0].item_bytes_done, active[0].item_bytes_total) == (
        None,
        None,
    )
    streamed = [
        event for event in active if event.item_bytes_done is not None
    ]
    assert len({event.item_attempt_id for event in streamed}) == 1
    assert streamed[0].item_attempt_id is not None
    assert (
        streamed[0].item_bytes_done,
        streamed[0].item_bytes_total,
    ) == (0, operation.content_bytes)
    assert (
        streamed[-1].item_bytes_done,
        streamed[-1].item_bytes_total,
    ) == (operation.content_bytes, operation.content_bytes)
    assert [event.item_bytes_done for event in streamed] == sorted(
        event.item_bytes_done for event in streamed
    )
    _assert_operation_progress_clears_after_outcome(events, operation)


def test_zero_byte_operation_mints_one_bounded_attempt(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    operation = _reviewed_progress_copy(source, target, fs, b"")

    result, events, _ = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(progress_interval_seconds=0),
    )

    active = _active_operation_progress(events, operation)
    determinate = [
        event for event in active if event.item_bytes_done is not None
    ]
    assert result.status is SessionState.COMPLETED
    assert [
        (event.item_bytes_done, event.item_bytes_total)
        for event in determinate
    ] == [(0, 0)]
    assert determinate[0].item_attempt_id is not None
    assert {
        event.item_attempt_id
        for event in active
        if event.item_attempt_id is not None
    } == {determinate[0].item_attempt_id}
    _assert_operation_progress_clears_after_outcome(events, operation)


def test_overreported_stream_suppresses_item_fraction_without_aggregate_regression(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    payload = b"eleven-byte"
    assert len(payload) == 11
    fs = NativeFileSystem()
    operation = _reviewed_progress_copy(source, target, fs, payload)

    result, events, _ = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(
            copy_backend=OverreportingProgressCopyBackend(),
            progress_interval_seconds=0,
        ),
    )

    active = _active_operation_progress(events, operation)
    assert result.status is SessionState.COMPLETED
    assert [
        (event.item_bytes_done, event.item_bytes_total) for event in active
    ] == [
        (None, None),
        (0, len(payload)),
        (len(payload), len(payload)),
        (None, None),
    ]
    assert all(event.item_type == "operation" for event in active)
    assert active[0].item_attempt_id is None
    assert active[-1].item_attempt_id == active[1].item_attempt_id
    assert active[-1].item_attempt_id is not None
    assert [event.bytes_done for event in active] == [
        0,
        0,
        len(payload),
        len(payload),
    ]
    assert all(event.bytes_done <= event.bytes_total for event in active)
    assert (target / "file.bin").read_bytes() == payload
    _assert_operation_progress_clears_after_outcome(events, operation)


def test_nonbyte_operation_progress_has_indeterminate_stable_identity(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    fs = NativeFileSystem()
    (source / "same.bin").write_bytes(b"same")
    (target / "same.bin").write_bytes(b"same")
    source_stat = fs.stat(source, "same.bin")
    target_stat = fs.stat(target, "same.bin")
    assert source_stat is not None and target_stat is not None
    operation = _operation(
        1,
        OperationKind.NOOP,
        source_rel_path="same.bin",
        target_rel_path="same.bin",
        source_expected=source_stat,
        target_expected=target_stat,
        intended=target_stat,
        reason=OperationReason.METADATA_MATCH,
    )

    result, events, _ = _run(
        _xset(_plan(source, target, (operation,))), fs=fs
    )

    active = _active_operation_progress(events, operation)
    assert result.status is SessionState.COMPLETED
    assert active
    assert all(event.item_type == "operation" for event in active)
    assert all(event.item_attempt_id is None for event in active)
    assert all(
        (event.item_bytes_done, event.item_bytes_total) == (None, None)
        for event in active
    )
    _assert_operation_progress_clears_after_outcome(events, operation)


def test_true_pipeline_retry_forces_reset_without_aggregate_regression(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    payload = b"abcdefghijkl"
    fs = NativeFileSystem()
    operation = _reviewed_progress_copy(source, target, fs, payload)
    backend = ScriptedProgressCopyBackend(
        ((8,), (4, 4, 4)),
        failing_attempts=frozenset({1}),
    )
    timeline: list[object] = []

    result = execute(
        _xset(_plan(source, target, (operation,))),
        RunContext(timeline.append, lambda: None),
        FakeRecorder(),
        _policies(
            copy_backend=backend,
            monotonic=lambda: 0.0,
            progress_interval_seconds=10.0,
            sleep=lambda _delay: timeline.append("retry-sleep"),
        ),
        fs,
    )

    active = _active_operation_progress(timeline, operation)
    retry_index = timeline.index("retry-sleep")
    reset_index = timeline.index(active[0])
    progress = [event for event in timeline if isinstance(event, Progress)]
    assert result.status is SessionState.COMPLETED
    assert backend.calls == 2
    assert len(active) == 1
    assert reset_index > retry_index
    assert (
        active[0].item_bytes_done,
        active[0].item_bytes_total,
        active[0].bytes_done,
    ) == (0, len(payload), 8)
    assert [event.bytes_done for event in progress] == [0, 8, 12]
    streamed_attempts = {
        event.item_attempt_id
        for event in active
        if event.item_attempt_id is not None
    }
    assert len(streamed_attempts) == 1
    assert (target / "file.bin").read_bytes() == payload
    _assert_operation_progress_clears_after_outcome(timeline, operation)


def test_terminal_retried_stream_retains_aggregate_high_water(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    payload = b"abcdefghijkl"
    fs = NativeFileSystem()
    operation = _reviewed_progress_copy(source, target, fs, payload)
    backend = ScriptedProgressCopyBackend(
        ((8,), (4,)),
        failing_attempts=frozenset({1, 2}),
    )

    result, events, recorder = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(
            copy_backend=backend,
            failure=BoundedFailurePolicy(retries=1, initial_delay=0),
        ),
    )

    active = _active_operation_progress(events, operation)
    assert result.status is SessionState.FAILED
    assert backend.calls == 2
    assert [event.item_bytes_done for event in active] == [None, 0, 8, 0, 4]
    reset_attempts = [
        event.item_attempt_id
        for event in active
        if event.item_bytes_done == 0
    ]
    assert len(reset_attempts) == 2
    assert reset_attempts[0] != reset_attempts[1]
    assert [event.bytes_done for event in active] == [0, 0, 8, 8, 8]
    assert result.bytes_done == 8
    assert result.bytes_total == len(payload)
    assert recorder.calls == []
    assert not (target / "file.bin").exists()
    assert not list(target.glob("*.synctmp-*"))
    _assert_operation_progress_clears_after_outcome(events, operation)


def test_failed_retry_cleanup_does_not_reset_item_progress(
    tmp_path: Path,
) -> None:
    source, target = _roots(tmp_path)
    payload = b"abcdefghijkl"
    fs = ProgressCleanupFailureFileSystem()
    operation = _reviewed_progress_copy(source, target, fs, payload)
    backend = ScriptedProgressCopyBackend(
        ((8,),),
        failing_attempts=frozenset({1}),
    )

    result, events, _ = _run(
        _xset(_plan(source, target, (operation,))),
        fs=fs,
        policies=_policies(
            copy_backend=backend,
            failure=BoundedFailurePolicy(retries=1, initial_delay=0),
        ),
    )

    active = _active_operation_progress(events, operation)
    outcome = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert outcome.reason == "cleanup-failed"
    assert backend.calls == 1
    assert fs.cleanup_attempts == 1
    assert [event.item_bytes_done for event in active] == [None, 0, 8]
    assert [event.bytes_done for event in active] == [0, 0, 8]
    assert result.bytes_done == 8
    _assert_operation_progress_clears_after_outcome(events, operation)


@pytest.mark.parametrize(
    "kind",
    (OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE),
)
def test_retained_byte_continuation_does_not_reset_item_progress(
    tmp_path: Path,
    kind: OperationKind,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _roots(tmp_path)
    fs = PublishedMetadataProgressRetryFileSystem()
    operation, published_target = _reviewed_byte_operation(
        kind, source, target, fs
    )
    fs.published_target = published_target
    timeline: list[object] = []
    file_bytes_at_settlement: list[int | None] = []
    attempt_ids_at_settlement: list[str | None] = []
    original_settled = executor_runtime._ProgressTracker.settled

    def observe_settlement(
        tracker: executor_runtime._ProgressTracker,
        settled_operation: PlanOperation,
        outcome: Outcome,
    ) -> None:
        file_bytes_at_settlement.append(tracker._file_bytes)
        attempt_ids_at_settlement.append(tracker._item_attempt_id)
        original_settled(tracker, settled_operation, outcome)

    monkeypatch.setattr(
        executor_runtime._ProgressTracker,
        "settled",
        observe_settlement,
    )

    result = execute(
        _xset(_plan(source, target, (operation,))),
        RunContext(timeline.append, lambda: None),
        FakeRecorder(),
        _policies(sleep=lambda _delay: timeline.append("retry-sleep")),
        fs,
    )

    active = _active_operation_progress(timeline, operation)
    retry_index = timeline.index("retry-sleep")
    full_index = next(
        index
        for index, event in enumerate(timeline)
        if isinstance(event, Progress)
        and event.item_id == str(operation.op_id)
        and event.item_bytes_done == operation.content_bytes
    )
    assert result.status is SessionState.COMPLETED
    assert fs.source_opens == 1
    assert fs.published_metadata_attempts == 2
    assert file_bytes_at_settlement == [operation.content_bytes]
    assert attempt_ids_at_settlement[0] is not None
    assert full_index < retry_index
    assert sum(event.item_bytes_done == 0 for event in active) == 1
    assert {
        event.item_attempt_id
        for event in active
        if event.item_attempt_id is not None
    } == set(attempt_ids_at_settlement)
    assert not any(
        isinstance(event, Progress)
        and event.item_id == str(operation.op_id)
        and event.item_bytes_done == 0
        for event in timeline[retry_index + 1 :]
    )
    _assert_operation_progress_clears_after_outcome(timeline, operation)


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
    item = _item_outcome(events)
    assert result.status is SessionState.FAILED
    assert item.reason == "source-missing"
    assert progress[-1].bytes_done == 0
    assert progress[-1].bytes_total == len(b"planned")
    assert recorder.calls == []
    assert not list(target.glob("*.synctmp-*"))


def test_executor_imports_core_but_no_sibling_module() -> None:
    package = Path(__file__).parents[1] / "namisync" / "modules" / "executor"
    sources = {
        path.name: path.read_text(encoding="utf-8")
        for path in package.glob("*.py")
    }
    assert set(sources) == {
        "__init__.py",
        "native.py",
        "pipeline.py",
        "runtime.py",
    }

    forbidden_components = (
        "namisync.modules.planner",
        "namisync.modules.preflight",
        "namisync.modules.scanner",
        "namisync.modules.verifier",
    )
    assert all(
        component not in text
        for text in sources.values()
        for component in forbidden_components
    )

    def relative_imports(name: str) -> set[str]:
        tree = ast.parse(sources[name])
        return {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level
        }

    def project_imports(name: str) -> set[str]:
        tree = ast.parse(sources[name])
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and not node.level and node.module:
                if node.module.startswith("namisync."):
                    imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(
                    alias.name
                    for alias in node.names
                    if alias.name.startswith("namisync.")
                )
        return imported

    assert relative_imports("__init__.py") == {"native", "pipeline", "runtime"}
    assert relative_imports("runtime.py") == {"native", "pipeline"}
    assert relative_imports("native.py") == set()
    assert relative_imports("pipeline.py") == set()
    for name in ("native.py", "pipeline.py", "runtime.py"):
        assert project_imports(name)
        assert all(
            module.startswith("namisync.core.")
            for module in project_imports(name)
        )

    assert "WinDLL" not in inspect.getsource(NativeFileSystem)


def test_executor_public_facade_preserves_exact_exports_and_signatures() -> None:
    assert executor_facade.__all__ == [
        "BoundedFailurePolicy",
        "CopyPipelineMetrics",
        "ExecutorPolicies",
        "NativeCopyBackend",
        "NativeFileSystem",
        "OperationFailure",
        "SystemClock",
        "UnsafeExecutionPath",
        "execute",
    ]
    assert executor_facade.NativeFileSystem is executor_module.NativeFileSystem
    assert (
        executor_facade.UnsafeExecutionPath
        is executor_module.UnsafeExecutionPath
    )
    assert executor_facade.NativeCopyBackend is executor_pipeline.NativeCopyBackend
    assert (
        executor_facade.CopyPipelineMetrics
        is executor_pipeline.CopyPipelineMetrics
    )
    assert (
        executor_facade.BoundedFailurePolicy
        is executor_runtime.BoundedFailurePolicy
    )
    assert executor_facade.ExecutorPolicies is executor_runtime.ExecutorPolicies
    assert executor_facade.OperationFailure is executor_runtime.OperationFailure
    assert executor_facade.SystemClock is executor_runtime.SystemClock
    assert executor_facade.execute is executor_runtime.execute
    assert issubclass(executor_facade.UnsafeExecutionPath, OSError)

    signatures = {
        name: str(inspect.signature(getattr(executor_facade, name)))
        for name in (
            "execute",
            "BoundedFailurePolicy",
            "ExecutorPolicies",
            "OperationFailure",
            "SystemClock",
            "NativeFileSystem",
            "NativeCopyBackend",
            "CopyPipelineMetrics",
        )
    }
    assert signatures == {
        "execute": (
            "(xset: 'ExecutionSet', ctx: 'RunContext', recorder: 'Recorder', "
            "policies: 'ExecutorPolicies', fs: 'ExecutorFileSystem') -> "
            "'OperationResult'"
        ),
        "BoundedFailurePolicy": (
            "(*, retries: 'int' = 3, initial_delay: 'float' = 0.05) -> "
            "'None'"
        ),
        "ExecutorPolicies": (
            "(copy_backend: 'CopyBackend', failure: 'FailurePolicy' = "
            "<factory>, clock: 'Clock' = <factory>, max_chunk_size: 'int' = "
            "4194304, max_retries: 'int' = 3, progress_interval_seconds: "
            "'float' = 0.1, monotonic: 'Callable[[], float]' = <built-in "
            "function monotonic>, sleep: 'Callable[[float], None]' = "
            "<built-in function sleep>) -> None"
        ),
        "OperationFailure": (
            "(reason: 'ExecutionReason', detail: 'str', *, cause: "
            "'Exception | None' = None) -> 'None'"
        ),
        "SystemClock": "()",
        "NativeFileSystem": "()",
        "NativeCopyBackend": (
            "(*, hasher_factory: 'HasherFactory', collect_metrics: 'bool' = "
            "False) -> 'None'"
        ),
        "CopyPipelineMetrics": (
            "(reader_blocked_seconds: 'float' = 0.0, writer_starved_seconds: "
            "'float' = 0.0, payload_high_water: 'int' = 0, reserved_bytes: "
            "'int' = 0) -> None"
        ),
    }


def test_run_id_rejects_user_controlled_temp_name_material() -> None:
    with pytest.raises(ValueError):
        validated_run_id("../not-an-owned-id")
