from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace

import pytest
from xxhash import xxh3_128

from namisync.core.events import (
    ItemOutcome,
    PhaseChanged,
    Progress,
    Terminal,
    TerminalSummary,
)
from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    Outcome,
    Provenance,
    RecordingStatus,
)
from namisync.core.execution import (
    Commitment,
    ExecutionSet,
    ItemRecordingReason,
    PublishedCopyEvidence,
    RecordedCopyIdentity,
    TaskRecordingIssueReason,
    validated_run_id,
)
from namisync.core.integrity import (
    IntegrityOutcome,
    IntegrityReason,
    IntegrityResult,
    IntegrityRunResult,
    PostCopyCandidate,
    PostCopyRecordIdentity,
    PostCopySelection,
    ReadStrategy,
    RecordDisposition,
    VerifierContext,
)
from namisync.core.models import (
    CapabilityProfile,
    EntryKind,
    FileStat,
    MetadataSnapshot,
    Root,
    VolumeEvidence,
    VolumeId,
)
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
    plan_fingerprint,
    selection_digest,
)
from namisync.core.pathing import normalize_relative_path, to_extended_length_path
from namisync.core.preflight import Refusal, RefusalCode, Verdict
from namisync.core.root_authority import RootAuthority
from namisync.core.session import (
    Canceled,
    Disposition,
    OperationResult,
    PauseRequested,
    PhaseResult,
    PhaseStatus,
    RunContext,
    SessionState,
    run_session,
)
from namisync.db.connections import connect_ledger_reader
from namisync.dispatcher import (
    Dispatcher,
    InProcessResourceLockProvider,
)
from namisync.interfaces.service import _workflow_registry
from namisync.modules.verifier import verify_post_copy
from namisync.workflows.models import (
    ExecuteContinuation,
    ExecutionRequest,
    PlanRequest,
    VerifyContinuation,
)
from namisync.workflows.payloads import (
    decode_execution_request,
    encode_execution_request,
)
from namisync.workflows.sync import (
    run_execution,
    settle_canceled_execution,
)
from namisync.workflows.runtime import (
    EXECUTION_KIND,
    PLAN_KIND,
    LocalWorkflowRuntime,
)
from namisync.workflows.views import operation_result_view
from tests.modules._verifier_fixtures import (
    _FakeReader,
    _Recorder as _VerifierRecorder,
    _StreamSpec,
)


NOW = datetime(2026, 7, 25, tzinfo=timezone.utc)


def _stat(size: int, mtime_ns: int = 10) -> FileStat:
    return FileStat(
        EntryKind.FILE,
        size,
        mtime_ns,
        None,
        1,
        MetadataSnapshot(0, None),
    )


def _operation(index: int, size: int = 5) -> PlanOperation:
    intended = _stat(size, 10 + index)
    return PlanOperation(
        op_id=OpId(f"{index:032x}"),
        kind=OperationKind.COPY,
        source_rel_path=f"file-{index}.bin",
        target_rel_path=f"file-{index}.bin",
        source_expected=intended,
        target_expected=None,
        intended=intended,
        content_bytes=size,
        reason=OperationReason.SOURCE_ONLY,
    )


def _plan(*operations: PlanOperation) -> Plan:
    profile = CapabilityProfile("NTFS", 100, True, False, 32767, True, True)
    placeholder = Plan(
        source_root=Root(r"C:\source", "source"),
        target_root=Root(r"D:\target", "target"),
        source_volume_id=None,
        target_volume_id=None,
        source_volume_evidence=None,
        target_volume_evidence=None,
        source_profile=profile,
        target_profile=profile,
        source_complete=True,
        target_complete=True,
        operations=tuple(operations),
        assignment=Assignment("identity", "1", ()),
        preservation=PreservationPolicy(),
        filter_snapshot=FilterSet(),
        deletion_policy=DeletionPolicy.TRASH,
        trash_on_update=True,
        policy_fingerprint="p" * 64,
        required_volumes=frozenset(),
        required_bytes=sum(operation.content_bytes for operation in operations),
        fingerprint=PlanFingerprint("0" * 64),
    )
    return replace(placeholder, fingerprint=plan_fingerprint(placeholder))


def _execution_set(*operations: PlanOperation) -> ExecutionSet:
    plan = _plan(*operations)
    selection = frozenset(operation.op_id for operation in operations)
    return ExecutionSet(
        plan,
        selection,
        validated_run_id("a" * 32),
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
    )


def _evidence(
    operation: PlanOperation,
    *,
    recorded: bool = True,
) -> PublishedCopyEvidence:
    assert operation.intended is not None
    attestation = Attestation(
        ContentEvidence(
            "xxh3_128",
            bytes([int(str(operation.op_id)[-1], 16)]) * 16,
            operation.content_bytes,
            Provenance.COPY_ATTESTED,
            NOW,
        ),
        operation.intended,
    )
    identity = (
        RecordedCopyIdentity(
            row_id=f"row-{operation.op_id}",
            location_id="target-location",
            scope_token="a" * 32,
            rel_path_key=normalize_relative_path(operation.target_rel_path),
        )
        if recorded
        else None
    )
    return PublishedCopyEvidence(attestation, identity)


def _settle(
    xset: ExecutionSet,
    context: RunContext,
    operation: PlanOperation,
    *,
    outcome: Outcome = Outcome.SUCCEEDED,
    evidence: PublishedCopyEvidence | None = None,
) -> ItemOutcome:
    if evidence is not None:
        xset.published_evidence[operation.op_id] = evidence
    xset.status[operation.op_id] = outcome
    item = ItemOutcome(
        str(operation.op_id),
        operation.kind.value,
        operation.target_rel_path,
        outcome,
    )
    context.emit(item)
    return item


def _integrity_outcome(
    candidate: PostCopyCandidate,
    *,
    recording: RecordingStatus = RecordingStatus.OK,
    disposition: RecordDisposition | None = RecordDisposition.APPLIED,
) -> IntegrityOutcome:
    identity = candidate.recorded_identity
    return IntegrityOutcome(
        item_id=candidate.item_id,
        row_id=None if identity is None else identity.row_id,
        location_id=None if identity is None else identity.location_id,
        path=candidate.display_path,
        result=IntegrityResult.VERIFIED,
        reason=(
            IntegrityReason.RECORDING_ERROR
            if identity is None
            else (
                IntegrityReason.RECORDING_STALE
                if disposition is RecordDisposition.STALE
                else None
            )
        ),
        read_strategy=ReadStrategy.WINDOWS_UNBUFFERED,
        recording=recording,
        record_disposition=disposition if identity is not None else None,
    )


class _Recording:
    def __init__(
        self,
        *,
        finish_fails: bool = False,
        enter_fails: bool = False,
        exit_fails: bool = False,
    ) -> None:
        self.recorder = object()
        self.finish_fails = finish_fails
        self.enter_fails = enter_fails
        self.exit_fails = exit_fails
        self.finishes: list[tuple[SessionState, RecordingStatus]] = []

    def __enter__(self):
        if self.enter_fails:
            raise OSError("recording enter failed")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.exit_fails:
            raise OSError("recording exit failed")
        return None

    def finish(
        self,
        status: SessionState,
        recording: RecordingStatus,
    ) -> None:
        self.finishes.append((status, recording))
        if self.finish_fails:
            raise RuntimeError("finish failed")


class _FileSystem:
    def remove_orphaned_temps(self, *args) -> None:
        return None


def _deps(
    *,
    executor,
    verifier,
    recordings: list[_Recording],
    verdict: Verdict | None = None,
):
    world = SimpleNamespace(paths={}, target_parent_paths=frozenset({""}))
    return SimpleNamespace(
        save_execution_details=lambda value: None,
        observer=lambda *args: world,
        observation_fs=object(),
        preflight=lambda execution_set, observed: (
            verdict if verdict is not None else Verdict(True, (), observed)
        ),
        open_recording=lambda execution_set: (
            recordings.append(_Recording()) or recordings[-1]
        ),
        executor=executor,
        executor_policies=object(),
        executor_fs=_FileSystem(),
        verifier=verifier,
        verifier_context=lambda run: VerifierContext(
            run=run,
            clock=SimpleNamespace(now=lambda: NOW),
            hasher_factory=lambda: None,
        ),
    )


def _verify_all(selection, context, recorder) -> IntegrityRunResult:
    del recorder
    outcomes: list[IntegrityOutcome] = []
    for candidate in selection.pending:
        selection.note_bytes_processed(candidate.expected_stat.size)
        outcome = _integrity_outcome(
            candidate,
            recording=(
                RecordingStatus.OK
                if candidate.recorded_identity is not None
                else RecordingStatus.DEGRADED
            ),
        )
        context.run.emit(outcome)
        selection.mark_completed(candidate.item_id, candidate.expected_stat.size)
        outcomes.append(outcome)
    recording = (
        RecordingStatus.DEGRADED
        if any(item.recording is RecordingStatus.DEGRADED for item in outcomes)
        else RecordingStatus.OK
    )
    return IntegrityRunResult(tuple(outcomes), recording)


def _post_copy_verifier_with(reader, verifier_recorder=None):
    actual_recorder = (
        _VerifierRecorder() if verifier_recorder is None else verifier_recorder
    )

    def verifier(selection, context, recorder):
        del recorder
        return verify_post_copy(
            selection,
            replace(
                context,
                hasher_factory=xxh3_128,
                root_authority=None,
            ),
            actual_recorder,
            reader,
        )

    return verifier


def _wait_for_session(
    dispatcher: Dispatcher,
    session_id,
    state: SessionState,
    timeout: float = 2.0,
):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        record = dispatcher.get(session_id)
        if record.state is state and (
            state
            not in {
                SessionState.COMPLETED,
                SessionState.FAILED,
                SessionState.CANCELED,
                SessionState.REFUSED,
            }
            or record.result is not None
        ):
            return record
        sleep(0.005)
    raise AssertionError(
        f"session did not reach {state}: {dispatcher.get(session_id)}"
    )


def test_xv_7_execute_verify_keeps_phase_bytes_separate() -> None:
    operation = _operation(1, 7)
    xset = _execution_set(operation)
    recordings: list[_Recording] = []
    recorder_ids: list[int] = []

    def executor(execution_set, context, recorder, policies, fs):
        del policies, fs
        recorder_ids.append(id(recorder))
        item = _settle(
            execution_set,
            context,
            operation,
            evidence=_evidence(operation),
        )
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=7,
            bytes_total=7,
        )

    def verifier(selection, context, recorder):
        recorder_ids.append(id(recorder))
        return _verify_all(selection, context, recorder)

    events: list[object] = []
    continuations: list[object] = []
    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(events.append, lambda: None),
        _deps(
            executor=executor,
            verifier=verifier,
            recordings=recordings,
        ),
        continuation_sink=continuations.append,
    )

    assert result.status is SessionState.COMPLETED
    assert [item.item_type for item in result.items] == ["operation", "integrity"]
    assert [item.phase for item in result.items] == ["execute", "verify"]
    assert [phase.bytes_done for phase in result.phases] == [7, 7]
    assert [phase.bytes_total for phase in result.phases] == [7, 7]
    assert len(recordings) == 1
    assert recorder_ids[0] == recorder_ids[1] == id(recordings[0].recorder)
    assert recordings[0].finishes == [
        (SessionState.COMPLETED, RecordingStatus.OK)
    ]
    assert isinstance(continuations[-1], VerifyContinuation)


def test_post_copy_verifier_binds_volume_without_optional_device_hint() -> None:
    operation = _operation(71, 7)
    volume_id = VolumeId("A1B2C3D4", "NTFS")
    base_plan = _plan(operation)
    bound_plan = replace(
        base_plan,
        target_volume_id=volume_id,
        target_volume_evidence=VolumeEvidence("Target", None),
        fingerprint=PlanFingerprint("0" * 64),
    )
    bound_plan = replace(
        bound_plan,
        fingerprint=plan_fingerprint(bound_plan),
    )
    selection = frozenset({operation.op_id})
    xset = ExecutionSet(
        bound_plan,
        selection,
        validated_run_id("b" * 32),
        commitment=Commitment(
            bound_plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
    )
    recordings: list[_Recording] = []
    contexts: list[VerifierContext] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(
            execution_set,
            context,
            operation,
            evidence=_evidence(operation),
        )
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=7,
            bytes_total=7,
        )

    def verifier(selection, context, recorder):
        contexts.append(context)
        return _verify_all(selection, context, recorder)

    deps = _deps(
        executor=executor,
        verifier=verifier,
        recordings=recordings,
    )
    deps.verifier_context = lambda run: VerifierContext(
        run=run,
        clock=SimpleNamespace(now=lambda: NOW),
        hasher_factory=lambda: None,
    )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda _body: None, lambda: None),
        deps,
    )

    assert result.status is SessionState.COMPLETED
    assert contexts[0].root_authority == RootAuthority(
        bound_plan.target_root.path,
        None,
        volume_id,
    )


def test_xv_1_missing_published_evidence_is_named_verification_incomplete() -> None:
    operation = _operation(2, 9)
    xset = _execution_set(operation)
    recordings: list[_Recording] = []
    events: list[object] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(execution_set, context, operation)
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=9,
            bytes_total=9,
        )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(events.append, lambda: None),
        _deps(
            executor=executor,
            verifier=verify_post_copy,
            recordings=recordings,
        ),
    )

    assert result.status is SessionState.COMPLETED
    assert result.phases[1].status is PhaseStatus.INCOMPLETE
    assert result.phases[1].items_done == 0
    assert result.phases[1].items_total == 1
    assert result.error is not None
    assert result.error.type_name == "PublishedEvidenceInvariantError"
    assert str(operation.op_id) in result.error.message
    verify_progress = [
        event
        for event in events
        if isinstance(event, Progress) and event.phase == "verify"
    ]
    assert verify_progress
    assert {
        (event.items_total, event.bytes_total) for event in verify_progress
    } == {(1, 9)}
    assert verify_progress[-1].items_done == result.phases[1].items_done
    assert verify_progress[-1].bytes_done == result.phases[1].bytes_done
    assert recordings[0].finishes == [
        (SessionState.COMPLETED, RecordingStatus.OK)
    ]


def test_verify_progress_admits_candidates_and_missing_evidence_together() -> None:
    candidate_operation = _operation(75, 5)
    missing_operation = _operation(76, 6)
    xset = _execution_set(candidate_operation, missing_operation)
    recordings: list[_Recording] = []
    events: list[object] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        candidate = _settle(
            execution_set,
            context,
            candidate_operation,
            evidence=_evidence(candidate_operation),
        )
        missing = _settle(execution_set, context, missing_operation)
        return OperationResult(
            SessionState.COMPLETED,
            items=(candidate, missing),
            bytes_done=11,
            bytes_total=11,
        )

    reader = _FakeReader(
        {
            candidate_operation.target_rel_path: _StreamSpec(
                candidate_operation.intended,
                (b"x" * (candidate_operation.content_bytes + 2),),
            )
        }
    )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(events.append, lambda: None),
        _deps(
            executor=executor,
            verifier=_post_copy_verifier_with(reader),
            recordings=recordings,
        ),
    )

    verify_progress = [
        event
        for event in events
        if isinstance(event, Progress) and event.phase == "verify"
    ]
    assert verify_progress
    assert verify_progress[-1].bytes_done == result.phases[1].bytes_done == 7
    assert all(event.items_total == 2 for event in verify_progress)
    assert [event.bytes_total for event in verify_progress] == sorted(
        event.bytes_total for event in verify_progress
    )
    assert verify_progress[0].bytes_total == 11
    assert verify_progress[-1].bytes_total == result.phases[1].bytes_total == 13
    assert verify_progress[-1].items_done == result.phases[1].items_done == 1


def test_verify_progress_retains_missing_evidence_budget_across_pause_resume() -> None:
    candidate_operation = _operation(77, 5)
    missing_operation = _operation(78, 6)
    xset = _execution_set(candidate_operation, missing_operation)
    captured: list[VerifyContinuation] = []
    first_events: list[object] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        candidate = _settle(
            execution_set,
            context,
            candidate_operation,
            evidence=_evidence(candidate_operation),
        )
        missing = _settle(execution_set, context, missing_operation)
        return OperationResult(
            SessionState.COMPLETED,
            items=(candidate, missing),
            bytes_done=11,
            bytes_total=11,
        )

    class PausingStream:
        strategy = ReadStrategy.WINDOWS_UNBUFFERED

        def stat(self):
            return candidate_operation.intended

        def iter_chunks(self, chunk_size):
            assert chunk_size > 0
            yield b"x" * 2
            raise PauseRequested()

    class PausingReader:
        @contextmanager
        def open(self, root, relative_path):
            del root
            assert relative_path == candidate_operation.target_rel_path
            yield PausingStream()

    with pytest.raises(PauseRequested):
        run_execution(
            ExecuteContinuation(xset, verify_after_execute=True),
            RunContext(first_events.append, lambda: None),
            _deps(
                executor=executor,
                verifier=_post_copy_verifier_with(PausingReader()),
                recordings=[],
            ),
            continuation_sink=captured.append,
        )

    paused = captured[-1]
    assert paused.candidates.processed_bytes == 2
    first_progress = [
        event
        for event in first_events
        if isinstance(event, Progress) and event.phase == "verify"
    ]
    assert first_progress
    assert all(event.items_total == 2 for event in first_progress)
    assert all(event.bytes_total >= 11 for event in first_progress)
    assert first_progress[-1].bytes_done == 2
    assert first_progress[-1].bytes_total == 13

    restored = decode_execution_request(
        encode_execution_request(ExecutionRequest(paused, NOW))
    ).continuation
    assert isinstance(restored, VerifyContinuation)
    resumed_events: list[object] = []
    reader = _FakeReader(
        {
            candidate_operation.target_rel_path: _StreamSpec(
                candidate_operation.intended,
                (b"y" * candidate_operation.content_bytes,),
            )
        }
    )

    result = run_execution(
        restored,
        RunContext(resumed_events.append, lambda: None),
        _deps(
            executor=lambda *args: pytest.fail("execution phase repeated"),
            verifier=_post_copy_verifier_with(reader),
            recordings=[],
        ),
        resumed=True,
    )

    resumed_progress = [
        event
        for event in resumed_events
        if isinstance(event, Progress) and event.phase == "verify"
    ]
    assert resumed_progress
    assert {
        (event.items_total, event.bytes_total) for event in resumed_progress
    } == {(2, 13)}
    assert resumed_progress[0].bytes_done == 2
    assert resumed_progress[-1].bytes_done == result.phases[1].bytes_done == 7
    assert resumed_progress[-1].items_done == result.phases[1].items_done == 1
    assert result.phases[1].items_total == 2
    assert result.phases[1].bytes_total == 13


def test_partial_execution_still_verifies_every_successful_publish() -> None:
    first = _operation(3, 5)
    later = _operation(4, 6)
    xset = _execution_set(first, later)
    recordings: list[_Recording] = []
    verified: list[str] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        succeeded = _settle(
            execution_set,
            context,
            first,
            evidence=_evidence(first),
        )
        failed = _settle(
            execution_set,
            context,
            later,
            outcome=Outcome.FAILED,
        )
        return OperationResult(
            SessionState.FAILED,
            items=(succeeded, failed),
            bytes_done=5,
            bytes_total=11,
        )

    def verifier(selection, context, recorder):
        verified.extend(candidate.item_id for candidate in selection.pending)
        return _verify_all(selection, context, recorder)

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda body: None, lambda: None),
        _deps(
            executor=executor,
            verifier=verifier,
            recordings=recordings,
        ),
    )

    assert result.status is SessionState.FAILED
    assert verified == [str(first.op_id)]
    assert xset.status[first.op_id] is Outcome.SUCCEEDED
    assert [phase.status for phase in result.phases] == [
        PhaseStatus.FAILED,
        PhaseStatus.COMPLETED,
    ]


def test_rowless_matching_readback_keeps_filesystem_success_and_degrades_recording() -> None:
    operation = _operation(5, 4)
    xset = _execution_set(operation)
    recordings: list[_Recording] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        evidence = _evidence(operation, recorded=False)
        item = _settle(
            execution_set,
            context,
            operation,
            evidence=evidence,
        )
        execution_set.note_item_recording_failure(
            operation.op_id,
            ItemRecordingReason.RECORD_WRITE_FAILED,
        )
        return OperationResult(
            SessionState.COMPLETED,
            recording=RecordingStatus.DEGRADED,
            items=(item,),
            bytes_done=4,
            bytes_total=4,
        )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda body: None, lambda: None),
        _deps(
            executor=executor,
            verifier=_verify_all,
            recordings=recordings,
        ),
    )

    integrity = next(
        item for item in result.items if isinstance(item, IntegrityOutcome)
    )
    assert result.status is SessionState.COMPLETED
    assert integrity.result is IntegrityResult.VERIFIED
    assert integrity.row_id is None
    assert integrity.location_id is None
    assert result.recording is RecordingStatus.DEGRADED
    assert recordings[0].finishes == [
        (SessionState.COMPLETED, RecordingStatus.DEGRADED)
    ]


def test_executor_result_degradation_is_frozen_before_verify_handoff() -> None:
    operation = _operation(51, 4)
    xset = _execution_set(operation)
    recordings: list[_Recording] = []
    captured: list[VerifyContinuation] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(
            execution_set,
            context,
            operation,
            evidence=_evidence(operation, recorded=False),
        )
        execution_set.note_item_recording_failure(
            operation.op_id,
            ItemRecordingReason.RECORD_WRITE_FAILED,
        )
        return OperationResult(
            SessionState.COMPLETED,
            recording=RecordingStatus.DEGRADED,
            items=(item,),
            bytes_done=4,
            bytes_total=4,
        )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda body: None, lambda: None),
        _deps(
            executor=executor,
            verifier=_verify_all,
            recordings=recordings,
        ),
        continuation_sink=captured.append,
    )

    assert xset.recording is RecordingStatus.DEGRADED
    assert captured[0].execution_set.recording is RecordingStatus.DEGRADED
    assert captured[0].recording is RecordingStatus.DEGRADED
    assert result.recording is RecordingStatus.DEGRADED
    assert recordings[0].finishes == [
        (SessionState.COMPLETED, RecordingStatus.DEGRADED)
    ]


def test_verify_exception_is_phase_visible_without_rewriting_filesystem() -> None:
    operation = _operation(6, 8)
    xset = _execution_set(operation)
    recordings: list[_Recording] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(
            execution_set,
            context,
            operation,
            evidence=_evidence(operation),
        )
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=8,
            bytes_total=8,
        )

    def explode(selection, context, recorder):
        del selection, context, recorder
        raise RuntimeError("readback exploded")

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda body: None, lambda: None),
        _deps(
            executor=executor,
            verifier=explode,
            recordings=recordings,
        ),
    )

    assert result.status is SessionState.COMPLETED
    assert result.phases[1].status is PhaseStatus.INCOMPLETE
    assert result.phases[1].items_done == 0
    assert result.phases[1].error == "RuntimeError: readback exploded"
    assert result.error is not None
    assert result.error.type_name == "RuntimeError"
    assert recordings[0].finishes == [
        (SessionState.COMPLETED, RecordingStatus.OK)
    ]


def test_verify_phase_counts_reliable_outcome_before_continuation_failure() -> None:
    operation = _operation(67, 8)
    xset = _execution_set(operation)
    recordings: list[_Recording] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(
            execution_set,
            context,
            operation,
            evidence=_evidence(operation),
        )
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=8,
            bytes_total=8,
        )

    def emit_then_fail_completion(selection, context, recorder):
        del recorder
        candidate = selection.pending[0]
        context.run.emit(_integrity_outcome(candidate))
        raise RuntimeError("completion bookkeeping failed")

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda body: None, lambda: None),
        _deps(
            executor=executor,
            verifier=emit_then_fail_completion,
            recordings=recordings,
        ),
    )

    assert result.status is SessionState.COMPLETED
    assert result.phases[1].status is PhaseStatus.INCOMPLETE
    assert result.phases[1].items_done == 1
    assert result.phases[1].items_total == 1
    assert result.error is not None
    assert result.error.type_name == "RuntimeError"


def test_degraded_outcome_snapshot_failure_keeps_progress_and_phase_aligned() -> None:
    candidate_operation = _operation(79, 5)
    missing_operation = _operation(80, 6)
    xset = _execution_set(candidate_operation, missing_operation)
    events: list[object] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        candidate = _settle(
            execution_set,
            context,
            candidate_operation,
            evidence=_evidence(candidate_operation),
        )
        missing = _settle(execution_set, context, missing_operation)
        return OperationResult(
            SessionState.COMPLETED,
            items=(candidate, missing),
            bytes_done=11,
            bytes_total=11,
        )

    def reject_degraded_snapshot(value) -> None:
        if (
            isinstance(value, VerifyContinuation)
            and value.recording is RecordingStatus.DEGRADED
        ):
            raise RuntimeError("degraded continuation snapshot failed")

    reader = _FakeReader(
        {
            candidate_operation.target_rel_path: _StreamSpec(
                candidate_operation.intended,
                (b"x" * candidate_operation.content_bytes,),
            )
        }
    )
    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(events.append, lambda: None),
        _deps(
            executor=executor,
            verifier=_post_copy_verifier_with(
                reader,
                _VerifierRecorder(RecordDisposition.STALE),
            ),
            recordings=[],
        ),
        continuation_sink=reject_degraded_snapshot,
    )

    assert not any(isinstance(event, IntegrityOutcome) for event in events)
    verify_progress = [
        event
        for event in events
        if isinstance(event, Progress) and event.phase == "verify"
    ]
    final_progress = verify_progress[-1]
    verify_phase = result.phases[1]
    assert (
        final_progress.items_done,
        final_progress.items_total,
        final_progress.bytes_done,
        final_progress.bytes_total,
    ) == (
        verify_phase.items_done,
        verify_phase.items_total,
        verify_phase.bytes_done,
        verify_phase.bytes_total,
    ) == (0, 2, 5, 16)
    assert final_progress.current_path is None
    assert final_progress.item_id is None
    assert verify_phase.status is PhaseStatus.INCOMPLETE
    assert result.error is not None
    assert result.error.type_name == "RuntimeError"


@pytest.mark.parametrize(
    ("fault", "message"),
    [
        ("context", "verifier context failed"),
        ("result", "post-copy verifier must return IntegrityRunResult"),
    ],
)
def test_verify_setup_and_result_errors_finish_once_with_visible_phase(
    fault: str,
    message: str,
) -> None:
    operation = _operation(61, 8)
    xset = _execution_set(operation)
    recordings: list[_Recording] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(
            execution_set,
            context,
            operation,
            evidence=_evidence(operation),
        )
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=8,
            bytes_total=8,
        )

    deps = _deps(
        executor=executor,
        verifier=(
            (lambda *args: object())
            if fault == "result"
            else lambda *args: pytest.fail("verifier unexpectedly started")
        ),
        recordings=recordings,
    )
    if fault == "context":
        deps.verifier_context = lambda run: (_ for _ in ()).throw(
            RuntimeError(message)
        )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda body: None, lambda: None),
        deps,
    )

    assert result.status is SessionState.COMPLETED
    assert result.phases[0].status is PhaseStatus.COMPLETED
    assert result.phases[1].status is PhaseStatus.INCOMPLETE
    assert result.phases[1].items_done == 0
    assert message in (result.phases[1].error or "")
    assert result.error is not None
    assert recordings[0].finishes == [
        (SessionState.COMPLETED, RecordingStatus.OK)
    ]


def test_continuation_sink_failure_finishes_once_as_execute_failure() -> None:
    operation = _operation(62, 9)
    xset = _execution_set(operation)
    recordings: list[_Recording] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(
            execution_set,
            context,
            operation,
            evidence=_evidence(operation),
        )
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=9,
            bytes_total=9,
        )

    def reject_continuation(value) -> None:
        del value
        raise RuntimeError("continuation publication failed")

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda body: None, lambda: None),
        _deps(
            executor=executor,
            verifier=lambda *args: pytest.fail("verification unexpectedly started"),
            recordings=recordings,
        ),
        continuation_sink=reject_continuation,
    )

    assert result.status is SessionState.FAILED
    assert len(result.phases) == 1
    assert result.phases[0].phase == "execute"
    assert result.phases[0].status is PhaseStatus.FAILED
    assert result.error is not None
    assert result.error.type_name == "RuntimeError"
    assert recordings[0].finishes == [
        (SessionState.FAILED, RecordingStatus.OK)
    ]


def test_noncompound_execute_exception_uses_execution_continuation_bytes() -> None:
    first = _operation(63, 5)
    second = _operation(64, 7)
    xset = _execution_set(first, second)
    recordings: list[_Recording] = []
    events: list[object] = []

    def fail_after_unemitted_work(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        context.emit(
            Progress(
                "execute",
                items_done=0,
                items_total=2,
                bytes_done=2,
                bytes_total=12,
                current_path=first.target_rel_path,
                item_id=str(first.op_id),
                item_type="operation",
                item_attempt_id="c" * 32,
                item_bytes_done=2,
                item_bytes_total=first.content_bytes,
            )
        )
        execution_set.note_bytes_done(6)
        raise RuntimeError("executor escaped after authoritative work")

    outcome = run_session(
        lambda context: run_execution(
            ExecuteContinuation(xset, verify_after_execute=False),
            context,
            _deps(
                executor=fail_after_unemitted_work,
                verifier=lambda *args: pytest.fail(
                    "verification unexpectedly started"
                ),
                recordings=recordings,
            ),
        ),
        emit=events.append,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
    )

    assert outcome.result is not None
    result = outcome.result
    assert result.status is SessionState.FAILED
    assert result.phases == ()
    assert result.bytes_done == 6
    assert result.bytes_total == 12
    assert result.error is not None
    assert result.error.type_name == "RuntimeError"
    assert result.error.message == "executor escaped after authoritative work"
    assert [event.bytes_done for event in events if isinstance(event, Progress)] == [2]
    assert isinstance(events[-1], Terminal)
    assert events[-1].result == TerminalSummary.from_result(result)
    assert recordings[0].finishes == [
        (SessionState.FAILED, RecordingStatus.OK)
    ]


@pytest.mark.parametrize("boundary", ["enter", "exit"])
def test_recording_boundary_failure_preserves_execution_truth(boundary: str) -> None:
    operation = _operation(65, 9)
    xset = _execution_set(operation)
    xset.note_bytes_done(4)
    recording = _Recording(
        enter_fails=boundary == "enter",
        exit_fails=boundary == "exit",
    )
    executor_calls = 0
    finished_without_open: list[tuple[SessionState, RecordingStatus]] = []

    def executor(execution_set, context, recorder, policies, fs):
        nonlocal executor_calls
        del context, recorder, policies, fs
        executor_calls += 1
        execution_set.note_bytes_done(9)
        return OperationResult(
            SessionState.COMPLETED,
            bytes_done=9,
            bytes_total=9,
        )

    deps = _deps(
        executor=executor,
        verifier=lambda *args: pytest.fail("verification unexpectedly started"),
        recordings=[],
    )
    deps.open_recording = lambda execution_set: recording
    deps.finish_existing_recording = (
        lambda execution_set, status, recording_status: finished_without_open.append(
            (status, recording_status)
        )
    )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(lambda body: None, lambda: None),
        deps,
        resumed=True,
    )

    assert executor_calls == (0 if boundary == "enter" else 1)
    assert result.status is (
        SessionState.FAILED if boundary == "enter" else SessionState.COMPLETED
    )
    assert result.phases == ()
    assert result.bytes_done == (4 if boundary == "enter" else 9)
    assert result.bytes_total == 9
    assert result.recording is RecordingStatus.DEGRADED
    assert result.error is not None
    assert result.error.type_name == "OSError"
    assert result.error.message == f"recording {boundary} failed"
    assert xset.recording is RecordingStatus.DEGRADED
    assert tuple(issue.reason for issue in xset.recording_issues) == (
        (
            TaskRecordingIssueReason.RECORDING_OPEN_FAILED
            if boundary == "enter"
            else TaskRecordingIssueReason.RECORDING_CLOSE_FAILED
        ),
    )
    assert finished_without_open == (
        [(SessionState.FAILED, RecordingStatus.DEGRADED)]
        if boundary == "enter"
        else []
    )


@pytest.mark.parametrize("boundary", ["factory", "enter"])
def test_recording_entry_pause_remains_cooperative_control(boundary: str) -> None:
    operation = _operation(70, 9)
    xset = _execution_set(operation)
    xset.note_bytes_done(5)
    events: list[object] = []
    open_calls = 0
    executor_calls = 0
    finished_without_open: list[tuple[SessionState, RecordingStatus]] = []

    class PauseOnEnter:
        def __enter__(self):
            raise PauseRequested()

        def __exit__(self, exc_type, exc, traceback) -> None:
            pytest.fail("recording exit unexpectedly reached")

    def open_recording(execution_set):
        nonlocal open_calls
        assert execution_set is xset
        open_calls += 1
        if boundary == "factory":
            raise PauseRequested()
        return PauseOnEnter()

    def executor(execution_set, context, recorder, policies, fs):
        nonlocal executor_calls
        del execution_set, context, recorder, policies, fs
        executor_calls += 1
        pytest.fail("executor unexpectedly started")

    deps = _deps(
        executor=executor,
        verifier=lambda *args: pytest.fail("verification unexpectedly started"),
        recordings=[],
    )
    deps.open_recording = open_recording
    deps.finish_existing_recording = (
        lambda execution_set, status, recording_status: finished_without_open.append(
            (status, recording_status)
        )
    )

    with pytest.raises(PauseRequested):
        run_execution(
            ExecuteContinuation(xset, verify_after_execute=False),
            RunContext(events.append, lambda: None),
            deps,
            resumed=True,
        )

    assert open_calls == 1
    assert executor_calls == 0
    assert finished_without_open == []
    assert xset.bytes_done_high_water == 5
    assert not any(isinstance(event, Terminal) for event in events)


@pytest.mark.parametrize("boundary", ["factory", "enter"])
def test_recording_entry_cancel_uses_continuation_authority_without_reopen(
    boundary: str,
) -> None:
    operation = _operation(71, 9)
    xset = _execution_set(operation)
    xset.note_bytes_done(5)
    events: list[object] = []
    settled: list[tuple[SessionState, OperationResult | None]] = []
    published: list[OperationResult] = []
    open_calls = 0
    executor_calls = 0
    finished_without_open: list[tuple[SessionState, RecordingStatus]] = []

    class CancelOnEnter:
        def __enter__(self):
            raise Canceled()

        def __exit__(self, exc_type, exc, traceback) -> None:
            pytest.fail("recording exit unexpectedly reached")

    def open_recording(execution_set):
        nonlocal open_calls
        assert execution_set is xset
        open_calls += 1
        if boundary == "factory":
            raise Canceled()
        return CancelOnEnter()

    def executor(execution_set, context, recorder, policies, fs):
        nonlocal executor_calls
        del execution_set, context, recorder, policies, fs
        executor_calls += 1
        pytest.fail("executor unexpectedly started")

    deps = _deps(
        executor=executor,
        verifier=lambda *args: pytest.fail("verification unexpectedly started"),
        recordings=[],
    )
    deps.open_recording = open_recording
    deps.finish_existing_recording = (
        lambda execution_set, status, recording_status: finished_without_open.append(
            (status, recording_status)
        )
    )

    def work(context: RunContext) -> OperationResult:
        context.emit(PhaseChanged("execute"))
        context.emit(
            Progress(
                "execute",
                items_done=0,
                items_total=1,
                bytes_done=1,
                bytes_total=9,
                current_path=operation.target_rel_path,
                item_id=str(operation.op_id),
                item_type="operation",
                item_attempt_id="d" * 32,
                item_bytes_done=1,
                item_bytes_total=9,
            )
        )
        return run_execution(
            ExecuteContinuation(xset, verify_after_execute=False),
            context,
            deps,
            resumed=True,
        )

    outcome = run_session(
        work,
        emit=events.append,
        checkpoint=lambda: None,
        settle=lambda state, result: settled.append((state, result)),
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=published.append,
    )

    assert not outcome.paused
    assert outcome.result is not None
    assert outcome.result.status is SessionState.CANCELED
    assert outcome.result.canceled
    assert outcome.result.disposition is Disposition.RAN
    assert outcome.result.error is None
    assert outcome.result.bytes_done == 5
    assert outcome.result.bytes_total == 9
    assert open_calls == 1
    assert executor_calls == 0
    assert finished_without_open == [
        (SessionState.CANCELED, RecordingStatus.OK)
    ]
    assert settled == [(SessionState.CANCELED, outcome.result)]
    assert published == [outcome.result]
    assert isinstance(events[-1], Terminal)
    assert events[-1].result == TerminalSummary.from_result(outcome.result)
    assert [event.bytes_done for event in events if isinstance(event, Progress)] == [1]


def test_recording_entry_cancel_attributes_fallback_finish_failure() -> None:
    operation = _operation(72, 9)
    xset = _execution_set(operation)

    def cancel_open(execution_set):
        assert execution_set is xset
        raise Canceled()

    def fail_finish(execution_set, status, recording_status):
        assert execution_set is xset
        assert status is SessionState.CANCELED
        assert recording_status is RecordingStatus.OK
        raise OSError("fallback finish failed")

    deps = _deps(
        executor=lambda *args: pytest.fail("executor unexpectedly started"),
        verifier=lambda *args: pytest.fail("verification unexpectedly started"),
        recordings=[],
    )
    deps.open_recording = cancel_open
    deps.finish_existing_recording = fail_finish

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(lambda body: None, lambda: None),
        deps,
        resumed=True,
    )

    assert result.status is SessionState.CANCELED
    assert result.recording is RecordingStatus.DEGRADED
    assert tuple(issue.reason for issue in xset.recording_issues) == (
        TaskRecordingIssueReason.FINISH_FAILED,
    )


def test_pause_recording_exit_failure_persists_degraded_continuation() -> None:
    operation = _operation(69, 9)
    xset = _execution_set(operation)
    captured: list[ExecuteContinuation] = []
    recording = _Recording(exit_fails=True)

    def pause_executor(execution_set, context, recorder, policies, fs):
        del execution_set, context, recorder, policies, fs
        raise PauseRequested()

    deps = _deps(
        executor=pause_executor,
        verifier=lambda *args: pytest.fail("verification unexpectedly started"),
        recordings=[],
    )
    deps.open_recording = lambda execution_set: recording

    with pytest.raises(PauseRequested) as raised:
        run_execution(
            ExecuteContinuation(xset, verify_after_execute=False),
            RunContext(lambda body: None, lambda: None),
            deps,
            continuation_sink=lambda value: captured.append(value),
        )

    assert any(
        "recording context exit also failed" in note
        for note in raised.value.__notes__
    )
    assert xset.recording is RecordingStatus.DEGRADED
    assert tuple(issue.reason for issue in xset.recording_issues) == (
        TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
    )
    assert captured
    assert isinstance(captured[-1], ExecuteContinuation)
    assert captured[-1].execution_set.recording is RecordingStatus.DEGRADED

    restored = decode_execution_request(
        encode_execution_request(ExecutionRequest(captured[-1], NOW))
    ).continuation
    assert isinstance(restored, ExecuteContinuation)
    assert tuple(
        issue.reason for issue in restored.execution_set.recording_issues
    ) == (TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,)
    canceled_recordings: list[_Recording] = []
    canceled = settle_canceled_execution(
        restored,
        Disposition.RAN,
        _deps(
            executor=lambda *args: pytest.fail("execution reopened"),
            verifier=lambda *args: pytest.fail("verification reopened"),
            recordings=canceled_recordings,
        ),
    )

    assert canceled.status is SessionState.CANCELED
    assert canceled.recording is RecordingStatus.DEGRADED
    assert canceled_recordings[0].finishes == [
        (SessionState.CANCELED, RecordingStatus.DEGRADED)
    ]


def test_verify_recording_open_failure_does_not_rewrite_execution_axis() -> None:
    operation = _operation(68, 6)
    xset = _execution_set(operation)
    evidence = _evidence(operation)
    xset.status[operation.op_id] = Outcome.SUCCEEDED
    xset.published_evidence[operation.op_id] = evidence
    identity = evidence.recorded_identity
    assert identity is not None
    continuation = VerifyContinuation(
        execution_set=xset,
        candidates=PostCopySelection(
            (
                PostCopyCandidate(
                    item_id=str(operation.op_id),
                    root=Path(xset.plan.target_root.path),
                    display_path=operation.target_rel_path,
                    expected_stat=evidence.attestation.subject,
                    copy_attestation=evidence.attestation,
                    recorded_identity=PostCopyRecordIdentity(
                        identity.row_id,
                        identity.location_id,
                        identity.scope_token,
                        identity.rel_path_key,
                    ),
                ),
            )
        ),
        filesystem_status=SessionState.COMPLETED,
        recording=RecordingStatus.OK,
        execute_phase=PhaseResult(
            "execute",
            PhaseStatus.COMPLETED,
            1,
            1,
            6,
            6,
        ),
    )
    deps = _deps(
        executor=lambda *args: pytest.fail("execution unexpectedly repeated"),
        verifier=lambda *args: pytest.fail("verification unexpectedly started"),
        recordings=[],
    )
    deps.open_recording = lambda execution_set: _Recording(enter_fails=True)

    result = run_execution(
        continuation,
        RunContext(lambda body: None, lambda: None),
        deps,
        resumed=True,
    )

    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.DEGRADED
    assert result.bytes_done == 6
    assert result.bytes_total == 6
    assert result.phases[0] == continuation.execute_phase
    assert result.phases[1].status is PhaseStatus.INCOMPLETE
    assert result.error is not None
    assert result.error.type_name == "OSError"
    assert xset.recording is RecordingStatus.DEGRADED
    assert tuple(issue.reason for issue in xset.recording_issues) == (
        TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
    )


def test_verify_base_exception_escapes_and_does_not_finish() -> None:
    operation = _operation(7, 3)
    xset = _execution_set(operation)
    recordings: list[_Recording] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(
            execution_set,
            context,
            operation,
            evidence=_evidence(operation),
        )
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=3,
            bytes_total=3,
        )

    def interrupt(selection, context, recorder):
        del selection, context, recorder
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run_execution(
            ExecuteContinuation(xset, verify_after_execute=True),
            RunContext(lambda body: None, lambda: None),
            _deps(
                executor=executor,
                verifier=interrupt,
                recordings=recordings,
            ),
        )

    assert len(recordings) == 1
    assert recordings[0].finishes == []


def test_xv_4_verify_pause_resumes_remaining_without_duplicates() -> None:
    first = _operation(8, 5)
    second = _operation(9, 5)
    xset = _execution_set(first, second)
    first_recordings: list[_Recording] = []
    captured: list[VerifyContinuation] = []
    events: list[object] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        items = tuple(
            _settle(
                execution_set,
                context,
                operation,
                evidence=_evidence(operation),
            )
            for operation in (first, second)
        )
        return OperationResult(
            SessionState.COMPLETED,
            items=items,
            bytes_done=10,
            bytes_total=10,
        )

    def pause_after_one(selection, context, recorder):
        del recorder
        candidate = selection.pending[0]
        selection.note_bytes_processed(candidate.expected_stat.size)
        outcome = _integrity_outcome(
            candidate,
            recording=RecordingStatus.DEGRADED,
            disposition=RecordDisposition.STALE,
        )
        context.run.emit(outcome)
        selection.mark_completed(candidate.item_id, candidate.expected_stat.size)
        raise PauseRequested()

    with pytest.raises(PauseRequested):
        run_execution(
            ExecuteContinuation(xset, verify_after_execute=True),
            RunContext(events.append, lambda: None),
            _deps(
                executor=executor,
                verifier=pause_after_one,
                recordings=first_recordings,
            ),
            continuation_sink=lambda value: captured.append(value),
        )

    assert first_recordings[0].finishes == []
    assert captured[-1].recording is RecordingStatus.DEGRADED
    assert captured[-1].candidates.completed_count == 1

    resumed_request = decode_execution_request(
        encode_execution_request(ExecutionRequest(captured[-1], NOW))
    )
    assert isinstance(resumed_request.continuation, VerifyContinuation)
    resumed_recordings: list[_Recording] = []
    resumed_ids: list[str] = []
    resumed_contexts: list[VerifierContext] = []

    def verify_remaining(selection, context, recorder):
        resumed_ids.extend(candidate.item_id for candidate in selection.pending)
        resumed_contexts.append(context)
        return _verify_all(selection, context, recorder)

    resumed = run_execution(
        resumed_request.continuation,
        RunContext(events.append, lambda: None),
        _deps(
            executor=lambda *args: pytest.fail("execution phase repeated"),
            verifier=verify_remaining,
            recordings=resumed_recordings,
        ),
    )

    outcomes = [item for item in events if isinstance(item, IntegrityOutcome)]
    assert resumed_ids == [str(second.op_id)]
    decoded_plan = resumed_request.continuation.execution_set.plan
    target_evidence = decoded_plan.target_volume_evidence
    assert resumed_contexts[0].root_authority == RootAuthority(
        decoded_plan.target_root.path,
        None if target_evidence is None else target_evidence.device_id,
        decoded_plan.target_volume_id,
    )
    assert [item.item_id for item in outcomes] == [
        str(first.op_id),
        str(second.op_id),
    ]
    assert resumed.recording is RecordingStatus.DEGRADED
    assert resumed.phases[1].bytes_done == 10
    assert resumed.phases[1].bytes_total == 10
    assert resumed_recordings[0].finishes == [
        (SessionState.COMPLETED, RecordingStatus.DEGRADED)
    ]


def test_verify_phase_total_counts_completed_physical_read_overrun() -> None:
    first = _operation(71, 2)
    second = _operation(72, 5)
    xset = _execution_set(first, second)
    recordings: list[_Recording] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        items = tuple(
            _settle(
                execution_set,
                context,
                operation,
                evidence=_evidence(operation),
            )
            for operation in (first, second)
        )
        return OperationResult(
            SessionState.COMPLETED,
            items=items,
            bytes_done=7,
            bytes_total=7,
        )

    def verify_with_physical_reads(selection, context, recorder):
        del recorder
        outcomes: list[IntegrityOutcome] = []
        for candidate, bytes_read in zip(
            selection.pending,
            (4, 0),
            strict=True,
        ):
            selection.note_bytes_processed(bytes_read)
            outcome = _integrity_outcome(candidate)
            context.run.emit(outcome)
            selection.mark_completed(candidate.item_id, bytes_read)
            outcomes.append(outcome)
        return IntegrityRunResult(tuple(outcomes), RecordingStatus.OK)

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda body: None, lambda: None),
        _deps(
            executor=executor,
            verifier=verify_with_physical_reads,
            recordings=recordings,
        ),
    )

    assert result.phases[1].bytes_done == 4
    assert result.phases[1].bytes_total == 9


def test_verify_phase_total_retains_abandoned_attempt_work_across_resume() -> None:
    first = _operation(73, 2)
    second = _operation(74, 5)
    xset = _execution_set(first, second)
    captured: list[VerifyContinuation] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        items = tuple(
            _settle(
                execution_set,
                context,
                operation,
                evidence=_evidence(operation),
            )
            for operation in (first, second)
        )
        return OperationResult(
            SessionState.COMPLETED,
            items=items,
            bytes_done=7,
            bytes_total=7,
        )

    def pause_after_abandoned_read(selection, context, recorder):
        del context, recorder
        selection.note_bytes_processed(1)
        raise PauseRequested()

    with pytest.raises(PauseRequested):
        run_execution(
            ExecuteContinuation(xset, verify_after_execute=True),
            RunContext(lambda body: None, lambda: None),
            _deps(
                executor=executor,
                verifier=pause_after_abandoned_read,
                recordings=[],
            ),
            continuation_sink=captured.append,
        )

    restored = decode_execution_request(
        encode_execution_request(ExecutionRequest(captured[-1], NOW))
    ).continuation
    assert isinstance(restored, VerifyContinuation)
    assert restored.candidates.processed_bytes == 1

    def verify_with_physical_reads(selection, context, recorder):
        del recorder
        outcomes: list[IntegrityOutcome] = []
        for candidate, bytes_read in zip(
            selection.pending,
            (4, 0),
            strict=True,
        ):
            selection.note_bytes_processed(bytes_read)
            outcome = _integrity_outcome(candidate)
            context.run.emit(outcome)
            selection.mark_completed(candidate.item_id, bytes_read)
            outcomes.append(outcome)
        return IntegrityRunResult(tuple(outcomes), RecordingStatus.OK)

    resumed = run_execution(
        restored,
        RunContext(lambda body: None, lambda: None),
        _deps(
            executor=lambda *args: pytest.fail("execution phase repeated"),
            verifier=verify_with_physical_reads,
            recordings=[],
        ),
        resumed=True,
    )

    assert resumed.phases[1].bytes_done == 5
    assert resumed.phases[1].bytes_total == 10


def test_xv_5_execute_pause_preserves_exact_evidence_then_verifies_all() -> None:
    first = _operation(13, 5)
    second = _operation(14, 5)
    xset = _execution_set(first, second)
    continuation = ExecuteContinuation(xset, verify_after_execute=True)
    first_recordings: list[_Recording] = []
    events: list[object] = []
    expected_evidence = _evidence(first)

    def pause_after_publish(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        _settle(
            execution_set,
            context,
            first,
            evidence=expected_evidence,
        )
        execution_set.note_bytes_done(7)
        context.emit(
            Progress(
                "execute",
                items_done=1,
                items_total=2,
                bytes_done=7,
                bytes_total=10,
                current_path=second.target_rel_path,
                item_id=str(second.op_id),
                item_type="operation",
                item_attempt_id="a" * 32,
                item_bytes_done=2,
                item_bytes_total=second.content_bytes,
            )
        )
        raise PauseRequested()

    with pytest.raises(PauseRequested):
        run_execution(
            continuation,
            RunContext(events.append, lambda: None),
            _deps(
                executor=pause_after_publish,
                verifier=lambda *args: pytest.fail("verify started after pause"),
                recordings=first_recordings,
            ),
        )

    assert first_recordings[0].finishes == []
    assert continuation.execution_set.bytes_done_high_water == 7
    resumed_request = decode_execution_request(
        encode_execution_request(ExecutionRequest(continuation, NOW))
    )
    assert isinstance(resumed_request.continuation, ExecuteContinuation)
    resumed_xset = resumed_request.execution_set
    assert resumed_xset.status == {first.op_id: Outcome.SUCCEEDED}
    assert resumed_xset.published_evidence[first.op_id] == expected_evidence
    assert resumed_xset.bytes_done_high_water == 7

    resumed_recordings: list[_Recording] = []
    verified: list[str] = []

    def finish_execution(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        assert execution_set.published_evidence[first.op_id] == expected_evidence
        second_item = _settle(
            execution_set,
            context,
            second,
            evidence=_evidence(second),
        )
        return OperationResult(
            SessionState.COMPLETED,
            items=(second_item,),
            bytes_done=10,
            bytes_total=10,
        )

    def verify_both(selection, context, recorder):
        verified.extend(candidate.item_id for candidate in selection.pending)
        return _verify_all(selection, context, recorder)

    result = run_execution(
        resumed_request.continuation,
        RunContext(events.append, lambda: None),
        _deps(
            executor=finish_execution,
            verifier=verify_both,
            recordings=resumed_recordings,
        ),
    )

    assert verified == [str(first.op_id), str(second.op_id)]
    assert result.status is SessionState.COMPLETED
    assert [
        item.item_id for item in events if isinstance(item, ItemOutcome)
    ] == [str(first.op_id), str(second.op_id)]
    assert resumed_recordings[0].finishes == [
        (SessionState.COMPLETED, RecordingStatus.OK)
    ]


def test_resumed_verify_preflight_refusal_finishes_as_incomplete() -> None:
    operation = _operation(10, 6)
    xset = _execution_set(operation)
    captured: list[VerifyContinuation] = []
    first_recordings: list[_Recording] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(
            execution_set,
            context,
            operation,
            evidence=_evidence(operation),
        )
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=6,
            bytes_total=6,
        )

    def pause_before_item(selection, context, recorder):
        del selection, context, recorder
        raise PauseRequested()

    with pytest.raises(PauseRequested):
        run_execution(
            ExecuteContinuation(xset, verify_after_execute=True),
            RunContext(lambda body: None, lambda: None),
            _deps(
                executor=executor,
                verifier=pause_before_item,
                recordings=first_recordings,
            ),
            continuation_sink=lambda value: captured.append(value),
        )

    resumed_recordings: list[_Recording] = []
    refused = Verdict(
        False,
        (
            Refusal(
                RefusalCode.ROOT_CHANGED,
                detail="target root changed before resume",
            ),
        ),
        SimpleNamespace(paths={}, target_parent_paths=frozenset({""})),
    )
    result = run_execution(
        captured[-1],
        RunContext(lambda body: None, lambda: None),
        _deps(
            executor=lambda *args: pytest.fail("execution phase repeated"),
            verifier=lambda *args: pytest.fail("verification should not start"),
            recordings=resumed_recordings,
            verdict=refused,
        ),
    )

    assert result.status is SessionState.COMPLETED
    assert not result.canceled
    assert result.phases[1].status is PhaseStatus.INCOMPLETE
    assert result.phases[1].items_done == 0
    assert result.error is not None
    assert result.error.type_name == "VerificationPreflightRefused"
    assert resumed_recordings[0].finishes == [
        (SessionState.COMPLETED, RecordingStatus.OK)
    ]


@pytest.mark.parametrize("verify_after_execute", [False, True])
@pytest.mark.parametrize("preflight_fault", ["refused", "exception"])
def test_resumed_execute_preflight_failure_finishes_as_ran_failure(
    preflight_fault: str,
    verify_after_execute: bool,
) -> None:
    first = _operation(101, 5)
    second = _operation(102, 7)
    xset = _execution_set(first, second)
    xset.status[first.op_id] = Outcome.SUCCEEDED
    xset.published_evidence[first.op_id] = _evidence(first)
    xset.note_bytes_done(9)
    recordings: list[_Recording] = []
    deps = _deps(
        executor=lambda *args: pytest.fail("execution unexpectedly resumed"),
        verifier=lambda *args: pytest.fail("verification unexpectedly started"),
        recordings=recordings,
        verdict=Verdict(
            False,
            (
                Refusal(
                    RefusalCode.ROOT_CHANGED,
                    detail="target changed during pause",
                ),
            ),
            SimpleNamespace(paths={}, target_parent_paths=frozenset({""})),
        ),
    )
    if preflight_fault == "exception":
        deps.preflight = lambda *args: (_ for _ in ()).throw(
            RuntimeError("resume preflight failed")
        )

    result = run_execution(
        ExecuteContinuation(
            xset,
            verify_after_execute=verify_after_execute,
        ),
        RunContext(lambda body: None, lambda: None),
        deps,
        resumed=True,
    )

    assert result.status is SessionState.FAILED
    assert result.disposition is Disposition.RAN
    assert not result.canceled
    assert len(result.phases) == int(verify_after_execute)
    if verify_after_execute:
        assert result.phases[0].status is PhaseStatus.FAILED
        assert result.phases[0].items_done == 1
        assert result.phases[0].items_total == 2
        assert result.phases[0].bytes_done == 9
        assert result.phases[0].bytes_total == 12
    assert result.bytes_done == 9
    assert result.bytes_total == 12
    assert result.error is not None
    assert result.error.type_name == (
        "ExecutionResumePreflightRefused"
        if preflight_fault == "refused"
        else "RuntimeError"
    )
    assert recordings[0].finishes == [
        (SessionState.FAILED, RecordingStatus.OK)
    ]


def test_paused_verify_cancel_preserves_execute_truth_and_finish_failure_axis() -> None:
    operation = _operation(11, 5)
    xset = _execution_set(operation)
    evidence = _evidence(operation)
    xset.status[operation.op_id] = Outcome.SUCCEEDED
    xset.published_evidence[operation.op_id] = evidence
    identity = evidence.recorded_identity
    assert identity is not None
    continuation = VerifyContinuation(
        execution_set=xset,
        candidates=PostCopySelection(
            (
                PostCopyCandidate(
                    item_id=str(operation.op_id),
                    root=Path(xset.plan.target_root.path),
                    display_path=operation.target_rel_path,
                    expected_stat=evidence.attestation.subject,
                    copy_attestation=evidence.attestation,
                    recorded_identity=PostCopyRecordIdentity(
                        identity.row_id,
                        identity.location_id,
                        identity.scope_token,
                        identity.rel_path_key,
                    ),
                ),
            )
        ),
        filesystem_status=SessionState.COMPLETED,
        recording=RecordingStatus.OK,
        execute_phase=PhaseResult(
            "execute",
            PhaseStatus.COMPLETED,
            1,
            1,
            5,
            5,
        ),
    )
    recording = _Recording(finish_fails=True)

    deps = SimpleNamespace(
        open_recording=lambda execution_set: recording,
    )
    result = settle_canceled_execution(
        continuation,
        Disposition.RAN,
        deps,
    )

    assert result.status is SessionState.COMPLETED
    assert result.canceled
    assert result.recording is RecordingStatus.DEGRADED
    assert result.phases[0] == continuation.execute_phase
    assert result.phases[1].status is PhaseStatus.CANCELED
    assert recording.finishes == [
        (SessionState.COMPLETED, RecordingStatus.OK)
    ]
    assert tuple(issue.reason for issue in xset.recording_issues) == (
        TaskRecordingIssueReason.FINISH_FAILED,
    )


def test_paused_execute_cancel_finishes_without_starting_verify() -> None:
    operation = _operation(12, 5)
    xset = _execution_set(operation)
    xset.note_bytes_done(3)
    recording = _Recording()
    result = settle_canceled_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        Disposition.RAN,
        SimpleNamespace(open_recording=lambda execution_set: recording),
    )

    assert result.status is SessionState.CANCELED
    assert result.canceled
    assert len(result.phases) == 1
    assert result.phases[0].phase == "execute"
    assert result.phases[0].status is PhaseStatus.CANCELED
    assert result.phases[0].items_done == 0
    assert result.phases[0].bytes_done == 3
    assert result.phases[0].bytes_total == 5
    assert result.bytes_done == 3
    assert result.bytes_total == 5
    assert recording.finishes == [
        (SessionState.CANCELED, RecordingStatus.OK)
    ]


@pytest.mark.parametrize("boundary", ["enter", "exit"])
def test_paused_execute_cancel_preserves_continuation_on_recording_fault(
    boundary: str,
) -> None:
    operation = _operation(66, 8)
    xset = _execution_set(operation)
    xset.note_bytes_done(5)
    recording = _Recording(
        enter_fails=boundary == "enter",
        exit_fails=boundary == "exit",
    )

    result = settle_canceled_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        Disposition.RAN,
        SimpleNamespace(open_recording=lambda execution_set: recording),
    )

    assert result.status is SessionState.CANCELED
    assert result.canceled
    assert result.phases == ()
    assert result.bytes_done == 5
    assert result.bytes_total == 8
    assert result.recording is RecordingStatus.DEGRADED
    assert result.error is not None
    assert result.error.type_name == "OSError"
    assert result.error.message == f"recording {boundary} failed"
    assert xset.recording is RecordingStatus.DEGRADED
    assert tuple(issue.reason for issue in xset.recording_issues) == (
        (
            TaskRecordingIssueReason.RECORDING_OPEN_FAILED
            if boundary == "enter"
            else TaskRecordingIssueReason.RECORDING_CLOSE_FAILED
        ),
    )


def test_running_execute_cancel_never_starts_verify() -> None:
    operation = _operation(15, 5)
    xset = _execution_set(operation)
    recordings: list[_Recording] = []
    verifier_called = False

    def cancel_executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        execution_set.note_bytes_done(3)
        context.emit(
            Progress(
                "execute",
                items_done=0,
                items_total=1,
                bytes_done=3,
                bytes_total=5,
                current_path=operation.target_rel_path,
                item_id=str(operation.op_id),
                item_type="operation",
                item_attempt_id="b" * 32,
                item_bytes_done=3,
                item_bytes_total=operation.content_bytes,
            )
        )
        _settle(
            execution_set,
            context,
            operation,
            outcome=Outcome.CANCELED,
        )
        raise Canceled()

    def verifier(*args):
        nonlocal verifier_called
        verifier_called = True
        raise AssertionError("verification started after execution cancellation")

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda body: None, lambda: None),
        _deps(
            executor=cancel_executor,
            verifier=verifier,
            recordings=recordings,
        ),
    )

    assert not verifier_called
    assert result.status is SessionState.CANCELED
    assert result.canceled
    assert xset.bytes_done_high_water == 3
    assert [phase.status for phase in result.phases] == [
        PhaseStatus.CANCELED
    ]
    assert result.phases[0].bytes_done == 3
    assert result.phases[0].bytes_total == 5
    assert recordings[0].finishes == [
        (SessionState.CANCELED, RecordingStatus.OK)
    ]


@pytest.mark.parametrize("verify_after_execute", [False, True])
def test_running_execute_cancel_preserves_degraded_recording_status(
    verify_after_execute: bool,
) -> None:
    operation = _operation(16, 5)
    excluded = _operation(17, 7)
    initial = _execution_set(operation, excluded)
    selection = frozenset({operation.op_id})
    xset = replace(
        initial,
        selection=selection,
        commitment=Commitment(
            initial.plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
        user_deselected=frozenset({excluded.op_id}),
    )
    recordings: list[_Recording] = []
    events: list[object] = []

    def cancel_executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        _settle(execution_set, context, operation)
        execution_set.note_item_recording_failure(
            operation.op_id,
            ItemRecordingReason.RECORD_WRITE_FAILED,
        )
        raise Canceled()

    result = run_execution(
        ExecuteContinuation(
            xset,
            verify_after_execute=verify_after_execute,
        ),
        RunContext(events.append, lambda: None),
        _deps(
            executor=cancel_executor,
            verifier=lambda *args: pytest.fail(
                "verification started after execution cancellation"
            ),
            recordings=recordings,
        ),
    )

    assert result.status is SessionState.CANCELED
    assert result.canceled
    assert result.recording is RecordingStatus.DEGRADED
    result_items = [item for item in result.items if isinstance(item, ItemOutcome)]
    emitted_items = [item for item in events if isinstance(item, ItemOutcome)]
    assert [item.item_id for item in result_items] == [
        str(operation.op_id),
        str(excluded.op_id),
    ]
    assert emitted_items == result_items
    assert result_items[0].outcome is Outcome.SUCCEEDED
    assert result_items[1].outcome is Outcome.SKIPPED
    assert result_items[1].reason == "user-deselected"
    assert recordings[0].finishes == [
        (SessionState.CANCELED, RecordingStatus.DEGRADED)
    ]


@pytest.mark.parametrize("verify_after_execute", [False, True])
def test_execute_failure_returns_emitted_item_truth(
    verify_after_execute: bool,
) -> None:
    operation = _operation(18, 5)
    xset = _execution_set(operation)
    recordings: list[_Recording] = []
    events: list[object] = []

    def fail_executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        _settle(execution_set, context, operation)
        raise RuntimeError("execution failed after settlement")

    result = run_execution(
        ExecuteContinuation(
            xset,
            verify_after_execute=verify_after_execute,
        ),
        RunContext(events.append, lambda: None),
        _deps(
            executor=fail_executor,
            verifier=lambda *args: pytest.fail(
                "verification started after execution failure"
            ),
            recordings=recordings,
        ),
    )

    result_items = [item for item in result.items if isinstance(item, ItemOutcome)]
    emitted_items = [item for item in events if isinstance(item, ItemOutcome)]
    assert result.status is SessionState.FAILED
    assert emitted_items == result_items
    assert [item.item_id for item in result_items] == [str(operation.op_id)]
    assert result_items[0].outcome is Outcome.SUCCEEDED
    assert len(result.phases) == int(verify_after_execute)


def test_real_runtime_copy_readback_uses_one_finished_run(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    content = b"one real execute-to-verify handoff"
    (source / "file.bin").write_bytes(content)
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    original_verifier_context = runtime._deps.verifier_context
    runtime._deps = replace(
        runtime._deps,
        executor_policies=replace(
            runtime._deps.executor_policies,
            progress_interval_seconds=0,
        ),
        verifier_context=lambda context: replace(
            original_verifier_context(context),
            progress_interval_seconds=0,
        ),
    )
    events: list[object] = []
    context = RunContext(events.append, lambda: None)
    try:
        plan_request = PlanRequest(
            request_id="c" * 32,
            source_path=str(source),
            target_path=str(target),
        )
        plan_result = runtime.open_plan(
            runtime.prepare_plan(plan_request).payload
        ).run(context)
        assert plan_result.status is SessionState.COMPLETED
        execution = runtime.commit_plan(
            plan_request.request_id,
            run_id="d" * 32,
            committed_at=NOW,
            verify_after_execute=True,
        )
        result = runtime.open_execution(
            runtime.prepare_execution(execution).payload
        ).run(context)
    finally:
        runtime.close()

    assert result.status is SessionState.COMPLETED
    assert [phase.phase for phase in result.phases] == ["execute", "verify"]
    assert [phase.bytes_done for phase in result.phases] == [
        len(content),
        len(content),
    ]
    assert [item.item_type for item in result.items] == [
        "operation",
        "integrity",
    ]
    operation = result.items[0]
    assert isinstance(operation, ItemOutcome)
    execute_phase = next(
        index
        for index, event in enumerate(events)
        if isinstance(event, PhaseChanged) and event.phase == "execute"
    )
    verify_phase = next(
        index
        for index, event in enumerate(events)
        if isinstance(event, PhaseChanged) and event.phase == "verify"
    )
    execute_progress = [
        event
        for event in events[execute_phase + 1 : verify_phase]
        if isinstance(event, Progress)
        and event.item_id == operation.item_id
    ]
    verify_progress = [
        event
        for event in events[verify_phase + 1 :]
        if isinstance(event, Progress)
        and event.item_id == operation.item_id
    ]
    assert execute_progress and verify_progress
    assert all(
        event.phase == "execute" and event.item_type == "operation"
        for event in execute_progress
    )
    assert all(
        event.phase == "verify" and event.item_type == "operation"
        for event in verify_progress
    )
    integrity = result.items[1]
    assert isinstance(integrity, IntegrityOutcome)
    assert integrity.item_type == "integrity"
    assert integrity.phase == "verify"
    assert integrity.item_id == operation.item_id
    assert integrity.result is IntegrityResult.VERIFIED
    integrity_index = events.index(integrity)
    verify_active_index = next(
        index
        for index, event in enumerate(events)
        if isinstance(event, Progress)
        and event.phase == "verify"
        and event.item_id == integrity.item_id
    )
    verify_clear_index = next(
        index
        for index, event in enumerate(
            events[integrity_index + 1 :],
            integrity_index + 1,
        )
        if isinstance(event, Progress)
        and event.phase == "verify"
        and event.item_id is None
    )
    assert verify_phase < verify_active_index < integrity_index < verify_clear_index
    assert (target / "file.bin").read_bytes() == content

    connection = connect_ledger_reader(tmp_path / "ledger.db")
    try:
        rows = connection.execute(
            """SELECT run_token, ended_at, filesystem_status, recording_status
                 FROM runs"""
        ).fetchall()
    finally:
        connection.close()
    assert len(rows) == 1
    assert rows[0]["run_token"] == "d" * 32
    assert rows[0]["ended_at"] is not None
    assert rows[0]["filesystem_status"] == SessionState.COMPLETED.value
    assert rows[0]["recording_status"] == RecordingStatus.OK.value


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length paths")
def test_long_path_plan_preflight_execute_verify_and_rerun_converge(
    tmp_path: Path,
) -> None:
    source = (
        tmp_path
        / "source-root"
        / ("s" * 90)
        / ("t" * 90)
    )
    target = (
        tmp_path
        / "target-root"
        / ("u" * 90)
        / ("v" * 90)
    )
    assert len(str(source)) > 260
    assert len(str(target)) > 260
    os.makedirs(to_extended_length_path(str(source)))
    os.makedirs(to_extended_length_path(str(target)))
    source_payloads = {
        "copied.bin": b"long-path plan to verified publication",
        "updated.bin": b"new long-path update content",
    }
    for relative_path, payload in source_payloads.items():
        with open(
            to_extended_length_path(str(source / relative_path)), "wb"
        ) as stream:
            stream.write(payload)
    target_payloads = {
        "updated.bin": b"displaced update content",
        "removed.bin": b"target-only trash content",
    }
    for relative_path, payload in target_payloads.items():
        with open(
            to_extended_length_path(str(target / relative_path)), "wb"
        ) as stream:
            stream.write(payload)

    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    context = RunContext(lambda body: None, lambda: None)

    def cycle(request_id: str, run_id: str):
        request = PlanRequest(request_id, str(source), str(target))
        planned = runtime.open_plan(
            runtime.prepare_plan(request).payload
        ).run(context)
        assert planned.status is SessionState.COMPLETED
        artifact = runtime.get_plan(request_id)
        assert artifact is not None
        execution = runtime.commit_plan(
            request_id,
            run_id=run_id,
            committed_at=NOW,
            verify_after_execute=True,
        )
        result = runtime.open_execution(
            runtime.prepare_execution(execution).payload
        ).run(context)
        return artifact, runtime.get_plan_review(request_id), result

    try:
        artifact, review, result = cycle("1" * 32, "2" * 32)
        rerun_artifact, rerun_review, rerun = cycle("3" * 32, "4" * 32)
    finally:
        runtime.close()

    assert not artifact.plan.source_root.path.startswith("\\\\?\\")
    assert not artifact.plan.target_root.path.startswith("\\\\?\\")
    assert artifact.plan.trash_on_update
    assert sorted(operation.kind for operation in review.operations) == [
        "copy",
        "trash",
        "update",
    ]
    assert result.status is SessionState.COMPLETED
    integrity = [
        item for item in result.items if isinstance(item, IntegrityOutcome)
    ]
    assert len(integrity) == 2
    assert all(item.result is IntegrityResult.VERIFIED for item in integrity)
    for relative_path, payload in source_payloads.items():
        destination = target / relative_path
        assert len(str(destination)) > 260
        with open(
            to_extended_length_path(str(destination)), "rb"
        ) as stream:
            assert stream.read() == payload
    assert not os.path.exists(
        to_extended_length_path(str(target / "removed.bin"))
    )
    for relative_path, payload in target_payloads.items():
        displaced = target / ".synctrash" / ("2" * 32) / relative_path
        with open(
            to_extended_length_path(str(displaced)), "rb"
        ) as stream:
            assert stream.read() == payload

    assert not rerun_artifact.plan.source_root.path.startswith("\\\\?\\")
    assert not rerun_artifact.plan.target_root.path.startswith("\\\\?\\")
    assert {
        operation.kind for operation in rerun_review.operations
    } == {"noop"}
    assert len(rerun_review.operations) == 2
    assert rerun.status is SessionState.COMPLETED


def test_xv_8_retained_compound_history_projects_phases_after_reopen(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    ledger_path = tmp_path / "ledger.db"
    history_path = tmp_path / "history.db"
    source.mkdir()
    target.mkdir()
    content = b"retained compound history"
    (source / "file.bin").write_bytes(content)
    runtime = LocalWorkflowRuntime(ledger_path, history_path)
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
    )
    run_id = "8" * 32
    try:
        request = PlanRequest(
            request_id="7" * 32,
            source_path=str(source),
            target_path=str(target),
        )
        plan_session = dispatcher.submit(PLAN_KIND, request)
        plan_record = _wait_for_session(
            dispatcher,
            plan_session,
            SessionState.COMPLETED,
        )
        assert plan_record.result is not None
        execution = runtime.commit_plan(
            request.request_id,
            run_id=run_id,
            committed_at=NOW,
            verify_after_execute=True,
        )
        execution_session = dispatcher.submit(EXECUTION_KIND, execution)
        execution_record = _wait_for_session(
            dispatcher,
            execution_session,
            SessionState.COMPLETED,
        )
        assert execution_record.result is not None
        live = operation_result_view(execution_record.result)
    finally:
        shutdown = dispatcher.shutdown()
        runtime.close()
    assert shutdown.complete

    reopened = LocalWorkflowRuntime(ledger_path, history_path)
    try:
        retained = reopened.get_history_summary(run_id)
        retained_items = reopened.get_history_items(run_id)
        listed = reopened.list_history()
    finally:
        reopened.close()

    assert retained.canceled is False
    assert retained.integrity_status == live.integrity
    assert retained.headline == live.headline
    assert [
        (
            item.item.item_type,
            item.item.phase,
            item.item.result,
        )
        for item in retained_items.items
    ] == [
        ("operation", "execute", "succeeded"),
        ("integrity", "verify", "verified"),
    ]
    assert [
        (
            phase.phase,
            phase.status,
            phase.items_done,
            phase.items_total,
            phase.bytes_done,
            phase.bytes_total,
            phase.error,
        )
        for phase in retained.phases
    ] == [
        ("execute", "completed", 1, 1, str(len(content)), str(len(content)), None),
        ("verify", "completed", 1, 1, str(len(content)), str(len(content)), None),
    ]
    assert [item.run_token for item in listed] == [run_id]
    assert listed[0].phases == retained.phases
    assert listed[0].item_count == retained.item_count == 2


def test_terminal_history_retains_rolled_back_attempted_byte_high_water(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    ledger_path = tmp_path / "ledger.db"
    history_path = tmp_path / "history.db"
    source.mkdir()
    target.mkdir()
    content = b"rolled back work"
    (source / "file.bin").write_bytes(content)

    class FailBeforePublication:
        def copy(
            self,
            source_stream,
            target_stream,
            *,
            chunk_size: int,
            checkpoint,
            on_chunk,
        ):
            del chunk_size
            checkpoint()
            attempted = source_stream.read(8)
            assert len(attempted) == 8
            assert target_stream.write(attempted) == 8
            on_chunk(8)
            raise OSError("injected failure before publication")

    runtime = LocalWorkflowRuntime(ledger_path, history_path)
    runtime._deps = replace(
        runtime._deps,
        executor_policies=replace(
            runtime._deps.executor_policies,
            copy_backend=FailBeforePublication(),
            progress_interval_seconds=0,
        ),
    )
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
    )
    run_id = "c" * 32
    try:
        request = PlanRequest(
            request_id="b" * 32,
            source_path=str(source),
            target_path=str(target),
        )
        runtime.open_plan(runtime.prepare_plan(request).payload).run(
            RunContext(lambda body: None, lambda: None)
        )
        execution = runtime.commit_plan(
            request.request_id,
            run_id=run_id,
            committed_at=NOW,
            verify_after_execute=False,
        )
        session_id = dispatcher.submit(EXECUTION_KIND, execution)
        record = _wait_for_session(
            dispatcher,
            session_id,
            SessionState.FAILED,
        )
    finally:
        shutdown = dispatcher.shutdown()
        runtime.close()
    assert shutdown.complete

    assert record.result is not None
    assert record.result.status is SessionState.FAILED
    assert record.result.disposition is Disposition.RAN
    assert record.result.phases == ()
    assert (record.result.bytes_done, record.result.bytes_total) == (
        8,
        len(content),
    )
    assert [
        item.outcome
        for item in record.result.items
        if isinstance(item, ItemOutcome)
    ] == [Outcome.FAILED]
    assert not (target / "file.bin").exists()
    assert not tuple(target.glob("*.synctmp-*"))

    reopened = LocalWorkflowRuntime(ledger_path, history_path)
    try:
        retained = reopened.get_history_summary(run_id)
    finally:
        reopened.close()

    assert retained.completion_status == "finalized"
    assert retained.filesystem_status == SessionState.FAILED.value
    assert retained.phases == ()
    assert (retained.bytes_done, retained.bytes_total) == ("8", str(len(content)))


@pytest.mark.parametrize(
    ("drift_kind", "expected"),
    [
        ("stable-bytes", IntegrityResult.MISMATCHED),
        ("stat", IntegrityResult.MODIFIED),
    ],
)
def test_xv_6_readback_keeps_copy_success_for_mismatch_and_stat_drift(
    tmp_path: Path,
    drift_kind: str,
    expected: IntegrityResult,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "file.bin").write_bytes(b"abcdef")
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )

    def drift_then_verify(selection, context, recorder):
        candidate = selection.pending[0]
        path = candidate.root / candidate.display_path
        if drift_kind == "stable-bytes":
            path.write_bytes(b"ABCDEF")
            os.utime(
                path,
                ns=(
                    candidate.expected_stat.mtime_ns,
                    candidate.expected_stat.mtime_ns,
                ),
            )
        else:
            changed = candidate.expected_stat.mtime_ns + 10_000_000_000
            os.utime(path, ns=(changed, changed))
        return verify_post_copy(selection, context, recorder)

    runtime._deps = replace(runtime._deps, verifier=drift_then_verify)
    context = RunContext(lambda body: None, lambda: None)
    try:
        request = PlanRequest(
            request_id="3" * 32,
            source_path=str(source),
            target_path=str(target),
        )
        runtime.open_plan(runtime.prepare_plan(request).payload).run(context)
        execution = runtime.commit_plan(
            request.request_id,
            run_id="4" * 32,
            committed_at=NOW,
            verify_after_execute=True,
        )
        result = runtime.open_execution(
            runtime.prepare_execution(execution).payload
        ).run(context)
    finally:
        runtime.close()

    operation = next(
        item for item in result.items if isinstance(item, ItemOutcome)
    )
    integrity = next(
        item for item in result.items if isinstance(item, IntegrityOutcome)
    )
    assert result.status is SessionState.COMPLETED
    assert operation.outcome is Outcome.SUCCEEDED
    assert integrity.result is expected
    assert (
        integrity.reason is IntegrityReason.HASH_MISMATCH
        if expected is IntegrityResult.MISMATCHED
        else integrity.reason is IntegrityReason.STAT_CHANGED
    )


def test_xv_6_stale_conditional_recording_degrades_only_recording(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "file.bin").write_bytes(b"verified but stale")
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )

    class StaleRecorder:
        def record_integrity(self, command):
            del command
            return RecordDisposition.STALE

    def stale_then_verify(selection, context, recorder):
        del recorder
        return verify_post_copy(selection, context, StaleRecorder())

    runtime._deps = replace(runtime._deps, verifier=stale_then_verify)
    context = RunContext(lambda body: None, lambda: None)
    try:
        request = PlanRequest(
            request_id="5" * 32,
            source_path=str(source),
            target_path=str(target),
        )
        runtime.open_plan(runtime.prepare_plan(request).payload).run(context)
        execution = runtime.commit_plan(
            request.request_id,
            run_id="6" * 32,
            committed_at=NOW,
            verify_after_execute=True,
        )
        result = runtime.open_execution(
            runtime.prepare_execution(execution).payload
        ).run(context)
    finally:
        runtime.close()

    operation = next(
        item for item in result.items if isinstance(item, ItemOutcome)
    )
    integrity = next(
        item for item in result.items if isinstance(item, IntegrityOutcome)
    )
    assert result.status is SessionState.COMPLETED
    assert operation.outcome is Outcome.SUCCEEDED
    assert integrity.result is IntegrityResult.VERIFIED
    assert integrity.reason is IntegrityReason.RECORDING_STALE
    assert integrity.record_disposition is RecordDisposition.STALE
    assert integrity.recording is RecordingStatus.DEGRADED
    assert result.recording is RecordingStatus.DEGRADED


def test_xv_2_copy_record_failure_still_builds_rowless_candidate(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "file.bin").write_bytes(b"published without ledger row")
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    original_open = runtime._open_recording

    class FaultingRecorder:
        def __init__(self, recorder) -> None:
            self._recorder = recorder

        def record_copied(self, op_id, attestation):
            del op_id, attestation
            raise RuntimeError("copy ledger transaction failed")

        def __getattr__(self, name: str):
            return getattr(self._recorder, name)

    class FaultingRecording:
        def __init__(self, inner) -> None:
            self._inner = inner
            self.recorder = None

        def __enter__(self):
            opened = self._inner.__enter__()
            self.recorder = FaultingRecorder(opened.recorder)
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return self._inner.__exit__(exc_type, exc, traceback)

        def finish(self, status, recording) -> None:
            self._inner.finish(status, recording)

    runtime._deps = replace(
        runtime._deps,
        open_recording=lambda xset: FaultingRecording(original_open(xset)),
    )
    context = RunContext(lambda body: None, lambda: None)
    try:
        request = PlanRequest(
            request_id="7" * 32,
            source_path=str(source),
            target_path=str(target),
        )
        runtime.open_plan(runtime.prepare_plan(request).payload).run(context)
        execution = runtime.commit_plan(
            request.request_id,
            run_id="8" * 32,
            committed_at=NOW,
            verify_after_execute=True,
        )
        result = runtime.open_execution(
            runtime.prepare_execution(execution).payload
        ).run(context)
    finally:
        runtime.close()

    operation = next(
        item for item in result.items if isinstance(item, ItemOutcome)
    )
    integrity = next(
        item for item in result.items if isinstance(item, IntegrityOutcome)
    )
    assert operation.outcome is Outcome.SUCCEEDED
    assert integrity.result is IntegrityResult.VERIFIED
    assert integrity.row_id is None
    assert integrity.location_id is None
    assert integrity.reason is IntegrityReason.RECORDING_ERROR
    assert result.recording is RecordingStatus.DEGRADED
    assert (target / "file.bin").read_bytes() == b"published without ledger row"


def test_xv_3_verify_pause_reopens_same_unfinished_run(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "file.bin").write_bytes(b"pause and reopen")
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    current_phase: list[str | None] = [None]
    pause_verify = [True]

    def emit(body: object) -> None:
        if isinstance(body, PhaseChanged):
            current_phase[0] = body.phase

    def checkpoint() -> None:
        if current_phase[0] == "verify" and pause_verify[0]:
            pause_verify[0] = False
            raise PauseRequested()

    context = RunContext(emit, checkpoint)
    try:
        request = PlanRequest(
            request_id="e" * 32,
            source_path=str(source),
            target_path=str(target),
        )
        runtime.open_plan(runtime.prepare_plan(request).payload).run(
            RunContext(lambda body: None, lambda: None)
        )
        execution = runtime.commit_plan(
            request.request_id,
            run_id="f" * 32,
            committed_at=NOW,
            verify_after_execute=True,
        )
        invocation = runtime.open_execution(
            runtime.prepare_execution(execution).payload
        )
        with pytest.raises(PauseRequested):
            invocation.run(context)
        snapshot = invocation.snapshot()
        decoded = decode_execution_request(snapshot)
        assert isinstance(decoded.continuation, VerifyContinuation)

        connection = connect_ledger_reader(runtime.ledger_path)
        try:
            paused_rows = connection.execute(
                "SELECT run_token, ended_at FROM runs"
            ).fetchall()
        finally:
            connection.close()
        assert [(row["run_token"], row["ended_at"]) for row in paused_rows] == [
            ("f" * 32, None)
        ]

        result = runtime.open_execution(snapshot).run(context)
    finally:
        runtime.close()

    assert result.status is SessionState.COMPLETED
    assert [item.item_type for item in result.items] == ["integrity"]
    connection = connect_ledger_reader(tmp_path / "ledger.db")
    try:
        rows = connection.execute(
            "SELECT run_token, ended_at, filesystem_status FROM runs"
        ).fetchall()
    finally:
        connection.close()
    assert len(rows) == 1
    assert rows[0]["run_token"] == "f" * 32
    assert rows[0]["ended_at"] is not None
    assert rows[0]["filesystem_status"] == SessionState.COMPLETED.value


def test_resumed_execute_preflight_refusal_finishes_existing_partial_run(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "a.bin").write_bytes(b"first")
    (source / "b.bin").write_bytes(b"second!")
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    settled: list[ItemOutcome] = []
    pause_once = [True]

    def emit(body: object) -> None:
        if isinstance(body, ItemOutcome) and body.outcome is Outcome.SUCCEEDED:
            settled.append(body)

    def checkpoint() -> None:
        if len(settled) == 1 and pause_once[0]:
            pause_once[0] = False
            raise PauseRequested()

    try:
        request = PlanRequest(
            request_id="3" * 32,
            source_path=str(source),
            target_path=str(target),
        )
        runtime.open_plan(runtime.prepare_plan(request).payload).run(
            RunContext(lambda body: None, lambda: None)
        )
        execution = runtime.commit_plan(
            request.request_id,
            run_id="4" * 32,
            committed_at=NOW,
            verify_after_execute=True,
        )
        invocation = runtime.open_execution(
            runtime.prepare_execution(execution).payload
        )
        with pytest.raises(PauseRequested):
            invocation.run(RunContext(emit, checkpoint))
        snapshot = invocation.snapshot()
        paused = decode_execution_request(snapshot)
        assert isinstance(paused.continuation, ExecuteContinuation)
        assert len(paused.execution_set.status) == 1
        assert len(settled) == 1

        connection = connect_ledger_reader(runtime.ledger_path)
        try:
            open_row = connection.execute(
                """SELECT run_token, started_at, ended_at
                     FROM runs"""
            ).fetchone()
        finally:
            connection.close()
        assert open_row is not None
        assert open_row["run_token"] == "4" * 32
        assert open_row["ended_at"] is None
        original_started_at = open_row["started_at"]

        runtime._deps = replace(
            runtime._deps,
            preflight=lambda execution_set, world: Verdict(
                False,
                (
                    Refusal(
                        RefusalCode.ROOT_CHANGED,
                        detail="target changed during execute pause",
                    ),
                ),
                world,
            ),
        )
        resumed_events: list[object] = []
        result = runtime.open_execution(snapshot).run(
            RunContext(resumed_events.append, lambda: None)
        )
    finally:
        runtime.close()

    assert result.status is SessionState.FAILED
    assert result.disposition is Disposition.RAN
    assert result.phases[0].status is PhaseStatus.FAILED
    assert result.phases[0].items_done == 1
    assert result.phases[0].items_total == 2
    assert result.error is not None
    assert result.error.type_name == "ExecutionResumePreflightRefused"
    assert not any(
        isinstance(body, PhaseChanged) and body.phase == "verify"
        for body in resumed_events
    )
    assert len(tuple(target.glob("*.bin"))) == 1

    connection = connect_ledger_reader(tmp_path / "ledger.db")
    try:
        rows = connection.execute(
            """SELECT run_token, started_at, ended_at, filesystem_status
                 FROM runs"""
        ).fetchall()
    finally:
        connection.close()
    assert len(rows) == 1
    assert rows[0]["run_token"] == "4" * 32
    assert rows[0]["started_at"] == original_started_at
    assert rows[0]["ended_at"] is not None
    assert rows[0]["filesystem_status"] == SessionState.FAILED.value


def test_real_resumed_verify_preflight_refusal_finishes_existing_run(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "file.bin").write_bytes(b"preflight refusal")
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    phase: list[str | None] = [None]
    should_pause = [True]

    def emit(body: object) -> None:
        if isinstance(body, PhaseChanged):
            phase[0] = body.phase

    def checkpoint() -> None:
        if phase[0] == "verify" and should_pause[0]:
            should_pause[0] = False
            raise PauseRequested()

    try:
        request = PlanRequest(
            request_id="9" * 32,
            source_path=str(source),
            target_path=str(target),
        )
        runtime.open_plan(runtime.prepare_plan(request).payload).run(
            RunContext(lambda body: None, lambda: None)
        )
        execution = runtime.commit_plan(
            request.request_id,
            run_id="a" * 32,
            committed_at=NOW,
            verify_after_execute=True,
        )
        invocation = runtime.open_execution(
            runtime.prepare_execution(execution).payload
        )
        with pytest.raises(PauseRequested):
            invocation.run(RunContext(emit, checkpoint))
        snapshot = invocation.snapshot()

        runtime._deps = replace(
            runtime._deps,
            preflight=lambda execution_set, world: Verdict(
                False,
                (
                    Refusal(
                        RefusalCode.ROOT_CHANGED,
                        detail="fault-injected resume refusal",
                    ),
                ),
                world,
            ),
        )
        result = runtime.open_execution(snapshot).run(
            RunContext(lambda body: None, lambda: None)
        )
    finally:
        runtime.close()

    assert result.status is SessionState.COMPLETED
    assert not result.canceled
    assert result.phases[0].status is PhaseStatus.COMPLETED
    assert result.phases[1].status is PhaseStatus.INCOMPLETE
    assert result.phases[1].items_done == 0
    assert result.error is not None
    assert result.error.type_name == "VerificationPreflightRefused"

    connection = connect_ledger_reader(tmp_path / "ledger.db")
    try:
        rows = connection.execute(
            "SELECT run_token, ended_at, filesystem_status FROM runs"
        ).fetchall()
    finally:
        connection.close()
    assert len(rows) == 1
    assert rows[0]["run_token"] == "a" * 32
    assert rows[0]["ended_at"] is not None
    assert rows[0]["filesystem_status"] == SessionState.COMPLETED.value


def test_dispatcher_paused_execute_cancel_finishes_same_run_without_verify(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "a.bin").write_bytes(b"first")
    (source / "b.bin").write_bytes(b"second")
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    entered = Event()
    executor_calls = 0

    def pauseable_executor(execution_set, context, recorder, policies, fs):
        nonlocal executor_calls
        del execution_set, recorder, policies, fs
        executor_calls += 1
        entered.set()
        while True:
            context.checkpoint()
            sleep(0.005)

    runtime._deps = replace(runtime._deps, executor=pauseable_executor)
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
    )
    try:
        request = PlanRequest(
            request_id="5" * 32,
            source_path=str(source),
            target_path=str(target),
        )
        runtime.open_plan(runtime.prepare_plan(request).payload).run(
            RunContext(lambda body: None, lambda: None)
        )
        execution = runtime.commit_plan(
            request.request_id,
            run_id="6" * 32,
            committed_at=NOW,
            verify_after_execute=True,
        )
        session_id = dispatcher.submit(EXECUTION_KIND, execution)
        assert entered.wait(2)
        assert dispatcher.pause(session_id).accepted
        _wait_for_session(dispatcher, session_id, SessionState.PAUSED)
        assert dispatcher.cancel(session_id).accepted
        record = _wait_for_session(
            dispatcher,
            session_id,
            SessionState.CANCELED,
        )
        assert not dispatcher.cancel(session_id).accepted
    finally:
        shutdown = dispatcher.shutdown()
        runtime.close()

    assert shutdown.complete
    assert executor_calls == 1
    assert record.result is not None
    assert record.result.status is SessionState.CANCELED
    assert record.result.canceled
    assert record.result.disposition is Disposition.RAN
    assert len(record.result.phases) == 1
    assert record.result.phases[0].phase == "execute"
    assert record.result.phases[0].status is PhaseStatus.CANCELED
    assert record.result.phases[0].items_done == 0
    assert record.result.phases[0].items_total == 2

    connection = connect_ledger_reader(tmp_path / "ledger.db")
    try:
        rows = connection.execute(
            """SELECT run_token, ended_at, filesystem_status
                 FROM runs"""
        ).fetchall()
    finally:
        connection.close()
    assert len(rows) == 1
    assert rows[0]["run_token"] == "6" * 32
    assert rows[0]["ended_at"] is not None
    assert rows[0]["filesystem_status"] == SessionState.CANCELED.value
    assert tuple(target.iterdir()) == ()


def test_dispatcher_pause_resume_retains_v6_item_attribution_and_attestation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "file.bin").write_bytes(b"transient evidence")
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    entered = Event()
    executor_calls = 0

    def pause_after_attributed_settlement(
        execution_set, context, recorder, policies, fs
    ):
        nonlocal executor_calls
        del recorder, policies, fs
        executor_calls += 1
        operation = execution_set.plan.operations[0]
        if operation.op_id not in execution_set.status:
            item = ItemOutcome(
                str(operation.op_id),
                operation.kind.value,
                operation.target_rel_path,
                Outcome.SUCCEEDED,
                recording=RecordingStatus.DEGRADED,
                recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
            )
            context.emit(item)
            execution_set.published_evidence[operation.op_id] = _evidence(
                operation,
                recorded=False,
            )
            execution_set.status[operation.op_id] = Outcome.SUCCEEDED
            execution_set.note_item_recording_failure(
                operation.op_id,
                ItemRecordingReason.RECORD_WRITE_FAILED,
            )
            entered.set()
            while True:
                context.checkpoint()
                sleep(0.005)
        return OperationResult(
            SessionState.COMPLETED,
            recording=execution_set.recording,
            bytes_done=operation.content_bytes,
            bytes_total=operation.content_bytes,
        )

    runtime._deps = replace(
        runtime._deps,
        executor=pause_after_attributed_settlement,
    )
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
    )
    try:
        request = PlanRequest(
            request_id="9" * 32,
            source_path=str(source),
            target_path=str(target),
        )
        runtime.open_plan(runtime.prepare_plan(request).payload).run(
            RunContext(lambda body: None, lambda: None)
        )
        execution = runtime.commit_plan(
            request.request_id,
            run_id="a" * 32,
            committed_at=NOW,
            verify_after_execute=False,
        )
        session_id = dispatcher.submit(EXECUTION_KIND, execution)
        assert entered.wait(2)
        assert dispatcher.pause(session_id).accepted
        paused = _wait_for_session(
            dispatcher,
            session_id,
            SessionState.PAUSED,
        )
        assert paused.payload is not None
        carried = decode_execution_request(paused.payload).execution_set
        operation = carried.plan.operations[0]
        assert carried.recording_reasons == {
            operation.op_id: ItemRecordingReason.RECORD_WRITE_FAILED
        }
        assert carried.published_evidence[
            operation.op_id
        ].recorded_identity is None

        assert dispatcher.resume(session_id).accepted
        terminal = _wait_for_session(
            dispatcher,
            session_id,
            SessionState.COMPLETED,
        )
    finally:
        shutdown = dispatcher.shutdown()
        runtime.close()

    assert shutdown.complete
    assert executor_calls == 2
    assert terminal.payload is None
    assert terminal.result is not None
    assert terminal.result.recording is RecordingStatus.DEGRADED


def test_dispatcher_paused_verify_cancel_uses_runtime_compound_settlement(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "file.bin").write_bytes(b"dispatcher cancel")
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    entered = Event()
    verifier_calls = 0

    def pauseable_verifier(selection, context, recorder):
        nonlocal verifier_calls
        del selection, recorder
        verifier_calls += 1
        entered.set()
        while True:
            context.run.checkpoint()
            sleep(0.005)

    runtime._deps = replace(runtime._deps, verifier=pauseable_verifier)
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        lock_provider=InProcessResourceLockProvider(),
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
    )
    try:
        request = PlanRequest(
            request_id="1" * 32,
            source_path=str(source),
            target_path=str(target),
        )
        runtime.open_plan(runtime.prepare_plan(request).payload).run(
            RunContext(lambda body: None, lambda: None)
        )
        execution = runtime.commit_plan(
            request.request_id,
            run_id="2" * 32,
            committed_at=NOW,
            verify_after_execute=True,
        )
        session_id = dispatcher.submit(EXECUTION_KIND, execution)
        assert entered.wait(2)
        assert dispatcher.pause(session_id).accepted
        _wait_for_session(dispatcher, session_id, SessionState.PAUSED)
        assert dispatcher.cancel(session_id).accepted
        record = _wait_for_session(
            dispatcher,
            session_id,
            SessionState.CANCELED,
        )
        assert not dispatcher.cancel(session_id).accepted
        assert dispatcher.shutdown().complete
    finally:
        runtime.close()

    assert verifier_calls == 1
    assert record.result is not None
    live = operation_result_view(record.result)
    assert record.result.status is SessionState.COMPLETED
    assert record.result.canceled
    assert [phase.status for phase in record.result.phases] == [
        PhaseStatus.COMPLETED,
        PhaseStatus.CANCELED,
    ]
    assert [item.item_type for item in record.result.items] == ["operation"]

    connection = connect_ledger_reader(tmp_path / "ledger.db")
    try:
        rows = connection.execute(
            "SELECT run_token, ended_at, filesystem_status FROM runs"
        ).fetchall()
    finally:
        connection.close()
    assert len(rows) == 1
    assert rows[0]["run_token"] == "2" * 32
    assert rows[0]["ended_at"] is not None
    assert rows[0]["filesystem_status"] == SessionState.COMPLETED.value

    reopened = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    try:
        history = reopened.get_history_summary("2" * 32)
    finally:
        reopened.close()
    assert history.filesystem_status == SessionState.COMPLETED.value
    assert history.canceled is True
    assert history.integrity_status == live.integrity
    assert history.headline == live.headline
    assert [phase.status for phase in history.phases] == [
        PhaseStatus.COMPLETED.value,
        PhaseStatus.CANCELED.value,
    ]
