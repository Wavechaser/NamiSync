from __future__ import annotations

import gc
import os
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace
from weakref import ref

import pytest
from xxhash import xxh3_128

import namisync.dispatcher.event_bus as dispatcher_event_bus
import namisync.modules.executor.runtime as executor_runtime
import namisync.workflows.sync as sync_workflow
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
from namisync.core.preflight import ObservedWorld, Refusal, RefusalCode, Verdict
from namisync.core.root_authority import RootAuthority
from namisync.core.session import (
    Canceled,
    Disposition,
    FailureDetail,
    OperationResult,
    PauseRequested,
    PhaseResult,
    PhaseStatus,
    RunContext,
    SessionState,
    StoredSessionRecord,
    run_session,
)
from namisync.db.connections import connect_ledger_reader
from namisync.dispatcher import (
    Dispatcher,
    InMemorySessionStore,
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


class _PrivateWorkflowFrameValue:
    pass


def _raise_with_private_workflow_frame(
    error: BaseException,
    references: list[ref[_PrivateWorkflowFrameValue]],
) -> None:
    private = _PrivateWorkflowFrameValue()
    references.append(ref(private))
    raise error


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
        policy_fingerprint="a" * 64,
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
    scope_token: str = "a" * 32,
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
            row_id=str(int(str(operation.op_id), 16)),
            location_id="9",
            scope_token=scope_token,
            rel_path_key=normalize_relative_path(operation.target_rel_path),
        )
        if recorded
        else None
    )
    return PublishedCopyEvidence(attestation, identity)


def _verify_continuation_fixture(
    operation: PlanOperation,
) -> VerifyContinuation:
    xset = _execution_set(operation)
    evidence = _evidence(operation)
    xset.status[operation.op_id] = Outcome.SUCCEEDED
    xset.published_evidence[operation.op_id] = evidence
    identity = evidence.recorded_identity
    assert identity is not None
    return VerifyContinuation(
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
            operation.content_bytes,
            operation.content_bytes,
        ),
    )


def _settle(
    xset: ExecutionSet,
    context: RunContext,
    operation: PlanOperation,
    *,
    outcome: Outcome = Outcome.SUCCEEDED,
    evidence: PublishedCopyEvidence | None = None,
    recording_reason: ItemRecordingReason | None = None,
) -> ItemOutcome:
    item = ItemOutcome(
        str(operation.op_id),
        operation.kind.value,
        operation.target_rel_path,
        outcome,
        recording=(
            RecordingStatus.DEGRADED
            if recording_reason is not None
            else RecordingStatus.OK
        ),
        recording_reason=recording_reason,
    )
    context.emit(item)
    if evidence is not None:
        xset.published_evidence[operation.op_id] = evidence
    xset.status[operation.op_id] = outcome
    if recording_reason is not None:
        xset.note_item_recording_failure(operation.op_id, recording_reason)
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


def _observed_world() -> ObservedWorld:
    return ObservedWorld(
        {},
        {},
        frozenset(),
        {},
        None,
        0,
        None,
        NOW,
    )


def _deps(
    *,
    executor,
    verifier,
    recordings: list[_Recording],
    verdict: Verdict | None = None,
):
    world = _observed_world()
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


@pytest.mark.parametrize(
    ("message", "expected_error", "expected_omissions"),
    [
        ("x" * 1021, f"T: {'x' * 1021}", 0),
        ("x" * 1022, None, 1),
        ("é" * 510 + "a", f"T: {'é' * 510}a", 0),
        ("é" * 510 + "aa", None, 1),
    ],
)
def test_verify_continuation_bounds_the_complete_execute_error(
    message: str,
    expected_error: str | None,
    expected_omissions: int,
) -> None:
    operation = _operation(79, 7)
    xset = _execution_set(operation)
    captured: list[VerifyContinuation] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(
            execution_set,
            context,
            operation,
            evidence=_evidence(operation),
        )
        return OperationResult(
            SessionState.FAILED,
            items=(item,),
            bytes_done=7,
            bytes_total=7,
            error=FailureDetail("T", message),
        )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda _body: None, lambda: None),
        _deps(executor=executor, verifier=_verify_all, recordings=[]),
        continuation_sink=captured.append,
    )

    assert captured[0].execute_phase.error == expected_error
    assert result.phases[0].error == expected_error
    assert result.status is SessionState.FAILED
    assert result.phases[0].items_done == result.phases[0].items_total == 1
    assert result.phases[0].bytes_done == result.phases[0].bytes_total == 7
    assert result.omitted_detail_count == xset.omitted_detail_count
    assert result.omitted_detail_count == expected_omissions


def test_execute_diagnostic_omissions_survive_verify_pause_resume_once() -> None:
    operation = _operation(80, 9)
    xset = _execution_set(operation)
    xset.omitted_detail_count = 2
    captured: list[VerifyContinuation] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(
            execution_set,
            context,
            operation,
            evidence=_evidence(operation),
        )
        return OperationResult(
            SessionState.FAILED,
            items=(item,),
            bytes_done=9,
            bytes_total=9,
            error=FailureDetail("T", "x" * 1025),
            omitted_detail_count=2,
        )

    def pause_verifier(*args):
        raise PauseRequested()

    with pytest.raises(PauseRequested):
        run_execution(
            ExecuteContinuation(xset, verify_after_execute=True),
            RunContext(lambda _body: None, lambda: None),
            _deps(executor=executor, verifier=pause_verifier, recordings=[]),
            continuation_sink=captured.append,
        )

    paused = captured[-1]
    assert paused.execute_phase.error is None
    assert paused.execution_set.omitted_detail_count == 3
    restored = decode_execution_request(
        encode_execution_request(ExecutionRequest(paused, NOW))
    ).continuation
    assert isinstance(restored, VerifyContinuation)
    assert restored.execution_set.omitted_detail_count == 3

    result = run_execution(
        restored,
        RunContext(lambda _body: None, lambda: None),
        _deps(
            executor=lambda *args: pytest.fail("execution phase repeated"),
            verifier=_verify_all,
            recordings=[],
        ),
        resumed=True,
    )

    assert result.status is SessionState.FAILED
    assert result.phases[0].error is None
    assert result.omitted_detail_count == 3


def test_verify_continuation_refuses_executor_omission_count_mismatch() -> None:
    operation = _operation(81, 5)
    xset = _execution_set(operation)
    captured: list[VerifyContinuation] = []

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
            bytes_done=5,
            bytes_total=5,
            omitted_detail_count=1,
        )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda _body: None, lambda: None),
        _deps(
            executor=executor,
            verifier=lambda *args: pytest.fail("verification unexpectedly started"),
            recordings=[],
        ),
        continuation_sink=captured.append,
    )

    assert not captured
    assert result.status is SessionState.FAILED
    assert result.error is not None
    assert result.error.type_name == "ValueError"
    assert "omitted detail count" in result.error.message
    assert result.omitted_detail_count == xset.omitted_detail_count == 0


def test_normalized_executor_result_is_released_before_continuation_sink(
) -> None:
    class TrackableResult(OperationResult):
        pass

    operation = _operation(82, 6)
    xset = _execution_set(operation)
    producer_refs = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(
            execution_set,
            context,
            operation,
            evidence=_evidence(operation),
        )
        result = TrackableResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=6,
            bytes_total=6,
        )
        producer_refs.append(ref(result))
        return result

    def inspect_continuation(value):
        assert isinstance(value, VerifyContinuation)
        gc.collect()
        assert producer_refs[-1]() is None

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda _body: None, lambda: None),
        _deps(executor=executor, verifier=_verify_all, recordings=[]),
        continuation_sink=inspect_continuation,
    )

    assert result.status is SessionState.COMPLETED


def test_executor_outcome_is_detached_and_bound_to_reviewed_plan_facts() -> None:
    class HiddenOutcome(ItemOutcome):
        pass

    operation = _operation(85, 6)
    xset = _execution_set(operation)
    producer_refs: list[ref[_PrivateWorkflowFrameValue]] = []
    events: list[object] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        hidden = _PrivateWorkflowFrameValue()
        producer_refs.append(ref(hidden))
        item = HiddenOutcome(
            item_id=str(operation.op_id),
            kind=OperationKind.DELETE,
            path="producer-forged.txt",
            outcome=Outcome.SUCCEEDED,
        )
        object.__setattr__(item, "hidden_graph", hidden)
        context.emit(item)
        object.__setattr__(item, "path", "producer-mutated.txt")
        execution_set.status[operation.op_id] = Outcome.SUCCEEDED
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=operation.content_bytes,
            bytes_total=operation.content_bytes,
        )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(events.append, lambda: None),
        _deps(executor=executor, verifier=_verify_all, recordings=[]),
    )

    operation_events = [body for body in events if isinstance(body, ItemOutcome)]
    assert len(operation_events) == 1
    assert result.items == tuple(operation_events)
    assert type(result.items[0]) is ItemOutcome
    assert result.items[0].item_id == str(operation.op_id)
    assert result.items[0].kind is operation.kind
    assert result.items[0].path == operation.target_rel_path
    gc.collect()
    assert producer_refs and all(reference() is None for reference in producer_refs)


def test_executor_duplicate_refuses_before_reading_hostile_detail() -> None:
    class HostileDuplicate(ItemOutcome):
        def __getattribute__(self, name: str):
            if name == "detail" and object.__getattribute__(
                self, "__dict__"
            ).get("hostile", False):
                raise AssertionError("duplicate detail was read")
            return super().__getattribute__(name)

    operation = _operation(88, 3)
    xset = _execution_set(operation)

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        first = ItemOutcome(
            str(operation.op_id),
            operation.kind,
            operation.target_rel_path,
            Outcome.SUCCEEDED,
        )
        context.emit(first)
        execution_set.status[operation.op_id] = Outcome.SUCCEEDED
        duplicate = HostileDuplicate(
            str(operation.op_id),
            operation.kind,
            operation.target_rel_path,
            Outcome.SUCCEEDED,
        )
        duplicate.hostile = True
        context.emit(duplicate)
        raise AssertionError("duplicate outcome was accepted")

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(lambda _body: None, lambda: None),
        _deps(executor=executor, verifier=_verify_all, recordings=[]),
    )

    assert result.status is SessionState.FAILED
    assert len(result.items) == 1
    assert result.error == FailureDetail(
        "ValueError",
        "executor emitted a duplicate operation outcome",
    )


def test_executor_must_emit_each_newly_settled_operation() -> None:
    operation = _operation(86, 4)
    xset = _execution_set(operation)

    def executor(execution_set, context, recorder, policies, fs):
        del context, recorder, policies, fs
        execution_set.status[operation.op_id] = Outcome.SUCCEEDED
        return OperationResult(
            SessionState.COMPLETED,
            items=(
                ItemOutcome(
                    item_id=str(operation.op_id),
                    kind=operation.kind,
                    path=operation.target_rel_path,
                    outcome=Outcome.SUCCEEDED,
                ),
            ),
            bytes_done=operation.content_bytes,
            bytes_total=operation.content_bytes,
        )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(lambda _body: None, lambda: None),
        _deps(executor=executor, verifier=_verify_all, recordings=[]),
    )

    assert result.status is SessionState.FAILED
    assert result.items == ()
    assert result.error == FailureDetail(
        "ValueError",
        "executor omitted an outcome for a pending operation",
    )


def test_executor_normal_return_must_emit_every_initially_pending_operation() -> None:
    first = _operation(92, 4)
    second = _operation(93, 5)
    xset = _execution_set(first, second)

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(execution_set, context, first)
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=first.content_bytes,
            bytes_total=first.content_bytes + second.content_bytes,
        )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(lambda _body: None, lambda: None),
        _deps(executor=executor, verifier=_verify_all, recordings=[]),
    )

    assert result.status is SessionState.FAILED
    assert [item.item_id for item in result.items] == [str(first.op_id)]
    assert result.error == FailureDetail(
        "ValueError",
        "executor omitted an outcome for a pending operation",
    )


def test_execute_resume_does_not_require_or_reemit_initial_settlements() -> None:
    operation = _operation(96, 4)
    xset = _execution_set(operation)
    xset.status[operation.op_id] = Outcome.SUCCEEDED
    events: list[object] = []

    def executor(execution_set, context, recorder, policies, fs):
        del context, recorder, policies, fs
        assert execution_set.remaining() == ()
        return OperationResult(
            SessionState.COMPLETED,
            bytes_done=operation.content_bytes,
            bytes_total=operation.content_bytes,
        )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(events.append, lambda: None),
        _deps(executor=executor, verifier=_verify_all, recordings=[]),
        resumed=True,
    )

    assert not any(isinstance(event, ItemOutcome) for event in events)
    assert [(item.item_id, item.outcome) for item in result.items] == [
        (str(operation.op_id), Outcome.SUCCEEDED)
    ]


def test_execute_rejects_a_settlement_ahead_of_its_outward_outcome() -> None:
    first = _operation(97, 4)
    second = _operation(98, 5)
    xset = _execution_set(first, second)
    recordings: list[_Recording] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        _settle(execution_set, context, first)
        execution_set.status[second.op_id] = Outcome.SUCCEEDED
        context.emit(
            ItemOutcome(
                str(second.op_id),
                second.kind,
                second.target_rel_path,
                Outcome.SUCCEEDED,
            )
        )
        pytest.fail("rejected operation outcome unexpectedly returned")

    def pause_on_second(body: object) -> None:
        if isinstance(body, ItemOutcome) and body.item_id == str(second.op_id):
            raise PauseRequested()

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(pause_on_second, lambda: None),
        _deps(
            executor=executor,
            verifier=_verify_all,
            recordings=recordings,
        ),
    )

    assert result.status is SessionState.FAILED
    assert [item.item_id for item in result.items] == [str(first.op_id)]
    assert result.error is not None
    assert "settlement" in result.error.message
    assert recordings[0].finishes == [
        (SessionState.FAILED, RecordingStatus.OK)
    ]


def test_execute_resume_reports_only_the_unaccepted_exclusion_suffix() -> None:
    selected = _operation(113, 4)
    excluded = (_operation(114, 2), _operation(115, 3))
    initial = _execution_set(selected, *excluded)
    selection = frozenset({selected.op_id})
    xset = replace(
        initial,
        selection=selection,
        user_deselected=frozenset(item.op_id for item in excluded),
        commitment=Commitment(
            initial.plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
    )
    captured: list[ExecuteContinuation] = []
    first_events: list[ItemOutcome] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(execution_set, context, selected)
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=selected.content_bytes,
            bytes_total=selected.content_bytes,
        )

    def pause_on_second_exclusion(body: object) -> None:
        if isinstance(body, ItemOutcome):
            if body.item_id == str(excluded[1].op_id):
                raise PauseRequested()
            first_events.append(body)

    first_recordings: list[_Recording] = []
    with pytest.raises(PauseRequested):
        run_execution(
            ExecuteContinuation(xset),
            RunContext(pause_on_second_exclusion, lambda: None),
            _deps(
                executor=executor,
                verifier=_verify_all,
                recordings=first_recordings,
            ),
            continuation_sink=captured.append,
        )

    assert [item.item_id for item in first_events] == [
        str(selected.op_id),
        str(excluded[0].op_id),
    ]
    assert captured[-1].reported_exclusion_count == 1
    restored = decode_execution_request(
        encode_execution_request(ExecutionRequest(captured[-1], NOW))
    ).continuation
    assert isinstance(restored, ExecuteContinuation)

    resumed_events: list[ItemOutcome] = []
    resumed_executor_calls = 0

    def resumed_executor(execution_set, context, recorder, policies, fs):
        nonlocal resumed_executor_calls
        del context, recorder, policies, fs
        resumed_executor_calls += 1
        assert not execution_set.remaining()
        return OperationResult(
            SessionState.COMPLETED,
            bytes_done=selected.content_bytes,
            bytes_total=selected.content_bytes,
        )

    result = run_execution(
        restored,
        RunContext(
            lambda body: resumed_events.append(body)
            if isinstance(body, ItemOutcome)
            else None,
            lambda: None,
        ),
        _deps(
            executor=resumed_executor,
            verifier=_verify_all,
            recordings=[],
        ),
        resumed=True,
    )

    assert resumed_executor_calls == 1
    assert [item.item_id for item in resumed_events] == [
        str(excluded[1].op_id)
    ]
    assert [item.item_id for item in result.items] == [
        str(selected.op_id),
        str(excluded[0].op_id),
        str(excluded[1].op_id),
    ]


def test_terminal_exclusion_control_becomes_failure_without_replay() -> None:
    selected, excluded = _operation(116, 4), _operation(117, 2)
    initial = _execution_set(selected, excluded)
    selection = frozenset({selected.op_id})
    xset = replace(
        initial,
        selection=selection,
        user_deselected=frozenset({excluded.op_id}),
        commitment=Commitment(
            initial.plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
    )
    executor_calls = 0
    captured: list[ExecuteContinuation] = []

    def executor(execution_set, context, recorder, policies, fs):
        nonlocal executor_calls
        del recorder, policies, fs
        executor_calls += 1
        _settle(execution_set, context, selected)
        raise RuntimeError("executor stopped")

    def pause_on_exclusion(body: object) -> None:
        if isinstance(body, ItemOutcome) and body.item_id == str(excluded.op_id):
            raise PauseRequested()

    result = run_execution(
        ExecuteContinuation(xset),
        RunContext(pause_on_exclusion, lambda: None),
        _deps(executor=executor, verifier=_verify_all, recordings=[]),
        continuation_sink=captured.append,
    )

    assert executor_calls == 1
    assert not captured
    assert result.status is SessionState.FAILED
    assert [item.item_id for item in result.items] == [str(selected.op_id)]
    assert result.error == FailureDetail(
        "RuntimeError",
        "control cannot interrupt terminal exclusion settlement",
    )


@pytest.mark.parametrize("control", (PauseRequested, Canceled))
def test_fresh_preflight_refusal_contains_terminal_exclusion_control(
    control: type[BaseException],
) -> None:
    selected = _operation(126, 4)
    excluded = (_operation(127, 2), _operation(128, 3))
    initial = _execution_set(selected, *excluded)
    selection = frozenset({selected.op_id})
    xset = replace(
        initial,
        selection=selection,
        user_deselected=frozenset(item.op_id for item in excluded),
        commitment=Commitment(
            initial.plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
    )
    events: list[ItemOutcome] = []
    recordings: list[_Recording] = []
    executor_calls = 0

    def executor(*args: object) -> None:
        nonlocal executor_calls
        del args
        executor_calls += 1

    def interrupt_second(body: object) -> None:
        if not isinstance(body, ItemOutcome):
            return
        if body.item_id == str(excluded[1].op_id):
            raise control()
        events.append(body)

    world = _observed_world()
    result = run_execution(
        ExecuteContinuation(xset),
        RunContext(interrupt_second, lambda: None),
        _deps(
            executor=executor,
            verifier=_verify_all,
            recordings=recordings,
            verdict=Verdict(
                False,
                (Refusal(RefusalCode.ROOT_UNAVAILABLE, detail="refused"),),
                world,
            ),
        ),
    )

    assert result.status is SessionState.REFUSED
    assert result.disposition is Disposition.UNRUN
    assert result.phases == ()
    assert [item.item_id for item in events] == [str(excluded[0].op_id)]
    assert [item.item_id for item in result.items] == [str(excluded[0].op_id)]
    assert result.error == FailureDetail(
        "RuntimeError",
        "control cannot interrupt terminal exclusion settlement",
    )
    assert executor_calls == 0
    assert recordings == []


def test_exclusion_cursor_capture_failure_stops_later_siblings() -> None:
    selected = _operation(118, 4)
    excluded = (_operation(119, 2), _operation(120, 3))
    initial = _execution_set(selected, *excluded)
    selection = frozenset({selected.op_id})
    xset = replace(
        initial,
        selection=selection,
        user_deselected=frozenset(item.op_id for item in excluded),
        commitment=Commitment(
            initial.plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
    )
    events: list[ItemOutcome] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(execution_set, context, selected)
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=selected.content_bytes,
            bytes_total=selected.content_bytes,
        )

    def emit(body: object) -> None:
        if isinstance(body, ItemOutcome):
            events.append(body)

    def reject_capture(value: object) -> None:
        assert isinstance(value, ExecuteContinuation)
        assert value.reported_exclusion_count == 1
        raise OSError("cursor custody unavailable")

    result = run_execution(
        ExecuteContinuation(xset),
        RunContext(emit, lambda: None),
        _deps(executor=executor, verifier=_verify_all, recordings=[]),
        continuation_sink=reject_capture,
    )

    assert result.status is SessionState.FAILED
    assert [item.item_id for item in events] == [
        str(selected.op_id),
        str(excluded[0].op_id),
    ]
    assert [item.item_id for item in result.items] == [
        str(selected.op_id),
        str(excluded[0].op_id),
    ]
    assert result.error == FailureDetail(
        "OSError",
        "cursor custody unavailable",
    )


def test_exclusion_cursor_cancellation_never_replays_an_accepted_item() -> None:
    selected = _operation(129, 4)
    excluded = (_operation(130, 2), _operation(131, 3))
    initial = _execution_set(selected, *excluded)
    selection = frozenset({selected.op_id})
    xset = replace(
        initial,
        selection=selection,
        user_deselected=frozenset(item.op_id for item in excluded),
        commitment=Commitment(
            initial.plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
    )
    events: list[ItemOutcome] = []
    captured_counts: list[int] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(execution_set, context, selected)
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=selected.content_bytes,
            bytes_total=selected.content_bytes,
        )

    def capture(value: object) -> None:
        assert isinstance(value, ExecuteContinuation)
        captured_counts.append(value.reported_exclusion_count)
        if value.reported_exclusion_count == 1:
            raise Canceled()

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(
            lambda body: events.append(body)
            if isinstance(body, ItemOutcome)
            else None,
            lambda: None,
        ),
        _deps(executor=executor, verifier=_verify_all, recordings=[]),
        continuation_sink=capture,
    )

    expected_ids = [
        str(selected.op_id),
        str(excluded[0].op_id),
        str(excluded[1].op_id),
    ]
    assert result.status is SessionState.CANCELED
    assert result.canceled
    assert captured_counts == [1, 2]
    assert [item.item_id for item in events] == expected_ids
    assert [item.item_id for item in result.items] == expected_ids


@pytest.mark.parametrize(
    ("reported_count", "resumed", "expected_status"),
    (
        (1, False, SessionState.REFUSED),
        (2, True, SessionState.FAILED),
    ),
)
def test_invalid_exclusion_cursor_stops_before_domain_collaborators(
    reported_count: int,
    resumed: bool,
    expected_status: SessionState,
) -> None:
    selected, excluded = _operation(124, 4), _operation(125, 2)
    initial = _execution_set(selected, excluded)
    selection = frozenset({selected.op_id})
    xset = replace(
        initial,
        selection=selection,
        user_deselected=frozenset({excluded.op_id}),
        commitment=Commitment(
            initial.plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
    )
    calls = {"observer": 0, "preflight": 0, "executor": 0}
    dependencies = _deps(
        executor=lambda *args: calls.__setitem__(
            "executor", calls["executor"] + 1
        ),
        verifier=_verify_all,
        recordings=[],
    )
    dependencies.observer = lambda *args: calls.__setitem__(
        "observer", calls["observer"] + 1
    )
    dependencies.preflight = lambda *args: calls.__setitem__(
        "preflight", calls["preflight"] + 1
    )

    result = run_execution(
        ExecuteContinuation(
            xset,
            reported_exclusion_count=reported_count,
        ),
        RunContext(lambda _body: None, lambda: None),
        dependencies,
        resumed=resumed,
    )

    assert result.status is expected_status
    assert result.disposition is (
        Disposition.RAN if resumed else Disposition.UNRUN
    )
    assert calls == {"observer": 0, "preflight": 0, "executor": 0}


def test_execute_retains_an_accepted_item_when_later_reconciliation_fails() -> None:
    operation = _operation(121, 4)
    xset = _execution_set(operation)

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(execution_set, context, operation)
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=operation.content_bytes,
            bytes_total=operation.content_bytes,
        )

    def mutate_after_accept(body: object) -> None:
        if isinstance(body, ItemOutcome):
            xset.recording_reasons[operation.op_id] = (
                ItemRecordingReason.RECORD_WRITE_FAILED
            )

    result = run_execution(
        ExecuteContinuation(xset),
        RunContext(mutate_after_accept, lambda: None),
        _deps(executor=executor, verifier=_verify_all, recordings=[]),
    )

    assert result.status is SessionState.FAILED
    assert [item.item_id for item in result.items] == [str(operation.op_id)]
    assert result.error == FailureDetail(
        "ValueError",
        "executor outcome disagrees with execution-set settlement",
    )


def test_verify_retains_an_accepted_item_when_revalidation_fails() -> None:
    operation = _operation(122, 5)
    continuation = _verify_continuation_fixture(operation)

    def mutate_after_accept(body: object) -> None:
        if isinstance(body, IntegrityOutcome):
            object.__setattr__(
                continuation.candidates.candidates[0],
                "display_path",
                "mutated.txt",
            )

    result = run_execution(
        continuation,
        RunContext(mutate_after_accept, lambda: None),
        _deps(
            executor=lambda *args: pytest.fail("execution phase repeated"),
            verifier=_verify_all,
            recordings=[],
        ),
        resumed=True,
    )

    assert result.status is SessionState.COMPLETED
    assert result.phases[-1].status is PhaseStatus.INCOMPLETE
    assert [item.item_id for item in result.items] == [str(operation.op_id)]
    assert result.items[0].path == operation.target_rel_path
    assert result.error == FailureDetail(
        "ValueError",
        "post-copy recorded identity does not match its display path",
    )


@pytest.mark.parametrize("owner", ("execute", "verify"))
@pytest.mark.parametrize("seam", ("finish", "exit"))
def test_recording_boundary_mutation_cannot_overwrite_reliable_truth(
    owner: str,
    seam: str,
) -> None:
    operation = _operation(123, 5)
    if owner == "execute":
        continuation: ExecuteContinuation | VerifyContinuation = (
            ExecuteContinuation(_execution_set(operation))
        )
    else:
        continuation = _verify_continuation_fixture(operation)

    def mutate() -> None:
        if owner == "execute":
            continuation.execution_set.status.clear()
            continuation.execution_set.bytes_done_high_water = 0
        else:
            assert isinstance(continuation, VerifyContinuation)
            continuation.candidates._completed_bytes.clear()
            continuation.candidates._processed_bytes = 0

    class MutatingRecording(_Recording):
        def finish(
            self,
            status: SessionState,
            recording: RecordingStatus,
        ) -> None:
            super().finish(status, recording)
            if seam == "finish":
                mutate()

        def __exit__(self, exc_type, exc, traceback) -> None:
            if seam == "exit":
                mutate()
            return super().__exit__(exc_type, exc, traceback)

    recording = MutatingRecording()

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(execution_set, context, operation)
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=operation.content_bytes,
            bytes_total=operation.content_bytes,
        )

    dependencies = _deps(
        executor=(
            executor
            if owner == "execute"
            else lambda *args: pytest.fail("execution phase repeated")
        ),
        verifier=_verify_all,
        recordings=[],
    )
    dependencies.open_recording = lambda _execution_set: recording

    result = run_execution(
        continuation,
        RunContext(lambda _body: None, lambda: None),
        dependencies,
        resumed=owner == "verify",
    )

    assert [item.item_id for item in result.items] == [str(operation.op_id)]
    assert result.items[0].path == operation.target_rel_path
    assert result.error is not None
    assert result.error.type_name == "ValueError"
    if owner == "execute":
        assert result.status is SessionState.FAILED
        assert result.bytes_done == operation.content_bytes
        assert result.bytes_total == operation.content_bytes
        assert result.error.message == "executor changed an existing settlement"
    else:
        assert result.status is SessionState.COMPLETED
        assert result.phases[-1].status is PhaseStatus.INCOMPLETE
        assert result.phases[-1].items_done == 1
        assert result.phases[-1].bytes_done == operation.content_bytes
        assert result.phases[-1].bytes_total == operation.content_bytes
        assert result.error.message == (
            "post-copy prior completion changed during collaboration"
        )


@pytest.mark.parametrize("owner", ("execute", "verify"))
@pytest.mark.parametrize("route", ("paused-cancel", "fallback-finish"))
def test_recording_finish_mutation_preserves_canceled_and_fallback_truth(
    owner: str,
    route: str,
) -> None:
    operation = _operation(132, 5)
    if owner == "execute":
        xset = _execution_set(operation)
        xset.status[operation.op_id] = Outcome.SUCCEEDED
        xset.note_bytes_done(operation.content_bytes)
        continuation: ExecuteContinuation | VerifyContinuation = ExecuteContinuation(
            xset,
            verify_after_execute=True,
        )
    else:
        continuation = _verify_continuation_fixture(operation)
        continuation.candidates.note_bytes_processed(operation.content_bytes)
        continuation.candidates.mark_completed(
            str(operation.op_id),
            operation.content_bytes,
        )
        xset = continuation.execution_set

    def mutate() -> None:
        if owner == "execute":
            xset.status.clear()
            xset.bytes_done_high_water = 0
        else:
            assert isinstance(continuation, VerifyContinuation)
            continuation.candidates._completed_bytes.clear()
            continuation.candidates._processed_bytes = 0

    if route == "paused-cancel":
        class MutatingRecording(_Recording):
            def finish(self, status, recording):
                super().finish(status, recording)
                mutate()

        result = settle_canceled_execution(
            continuation,
            Disposition.RAN,
            SimpleNamespace(
                open_recording=lambda execution_set: MutatingRecording()
            ),
        )
    else:
        dependencies = _deps(
            executor=lambda *args: pytest.fail("execution unexpectedly started"),
            verifier=lambda *args: pytest.fail("verification unexpectedly started"),
            recordings=[],
        )
        dependencies.observer = lambda *args: (_ for _ in ()).throw(
            OSError("preflight unavailable")
        )
        dependencies.finish_existing_recording = (
            lambda execution_set, status, recording: mutate()
        )
        result = run_execution(
            continuation,
            RunContext(lambda _body: None, lambda: None),
            dependencies,
            resumed=True,
        )

    assert not result.canceled
    assert result.error is not None
    assert result.error.type_name == "ValueError"
    if owner == "execute":
        assert result.status is SessionState.FAILED
        assert result.phases[-1].status is PhaseStatus.FAILED
        assert result.phases[-1].items_done == 1
        assert result.phases[-1].bytes_done == operation.content_bytes
        assert result.bytes_done == operation.content_bytes
        assert result.error.message == "executor changed an existing settlement"
    else:
        assert result.status is SessionState.COMPLETED
        assert result.phases[-1].status is PhaseStatus.INCOMPLETE
        assert result.phases[-1].items_done == 1
        assert result.phases[-1].bytes_done == operation.content_bytes
        assert result.error.message == (
            "post-copy prior completion changed during collaboration"
        )


def test_executor_cannot_return_refused_unrun_after_execution_started() -> None:
    operation = _operation(99, 4)
    xset = _execution_set(operation)

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(execution_set, context, operation)
        return OperationResult(
            SessionState.REFUSED,
            disposition=Disposition.UNRUN,
            items=(item,),
            bytes_done=operation.content_bytes,
            bytes_total=operation.content_bytes,
        )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(lambda _body: None, lambda: None),
        _deps(executor=executor, verifier=_verify_all, recordings=[]),
    )

    assert result.status is SessionState.FAILED
    assert result.disposition is Disposition.RAN
    assert result.error == FailureDetail(
        "ValueError",
        "executor returned an invalid terminal status",
    )


def test_executor_cannot_change_fixed_execution_authority() -> None:
    operation = _operation(105, 4)
    xset = _execution_set(operation)

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(execution_set, context, operation)
        execution_set.run_id = validated_run_id("b" * 32)
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=operation.content_bytes,
            bytes_total=operation.content_bytes,
        )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(lambda _body: None, lambda: None),
        _deps(executor=executor, verifier=_verify_all, recordings=[]),
    )

    assert result.status is SessionState.FAILED
    assert result.error == FailureDetail(
        "ValueError",
        "executor changed the execution run identity",
    )


@pytest.mark.parametrize("corruption", ["outcome", "recording"])
def test_executor_emission_must_match_retained_settlement(corruption: str) -> None:
    operation = _operation(94, 4)
    xset = _execution_set(operation)

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        emitted = ItemOutcome(
            str(operation.op_id),
            operation.kind,
            operation.target_rel_path,
            Outcome.SUCCEEDED,
        )
        context.emit(emitted)
        execution_set.status[operation.op_id] = (
            Outcome.FAILED if corruption == "outcome" else Outcome.SUCCEEDED
        )
        if corruption == "recording":
            execution_set.note_item_recording_failure(
                operation.op_id,
                ItemRecordingReason.RECORD_WRITE_FAILED,
            )
        return OperationResult(
            SessionState.FAILED if corruption == "outcome" else SessionState.COMPLETED,
            recording=execution_set.recording,
            items=(emitted,),
            bytes_done=operation.content_bytes,
            bytes_total=operation.content_bytes,
        )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(lambda _body: None, lambda: None),
        _deps(executor=executor, verifier=_verify_all, recordings=[]),
    )

    assert result.status is SessionState.FAILED
    assert len(result.items) == 1
    assert result.error == FailureDetail(
        "ValueError",
        "executor outcome disagrees with execution-set settlement",
    )


def test_executor_aggregate_recording_must_match_execution_settlement() -> None:
    operation = _operation(91, 4)
    xset = _execution_set(operation)
    recordings: list[_Recording] = []

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(execution_set, context, operation)
        return OperationResult(
            SessionState.COMPLETED,
            recording=RecordingStatus.DEGRADED,
            items=(item,),
            bytes_done=operation.content_bytes,
            bytes_total=operation.content_bytes,
        )

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda _body: None, lambda: None),
        _deps(
            executor=executor,
            verifier=lambda *args: pytest.fail("verification unexpectedly started"),
            recordings=recordings,
        ),
    )

    assert result.status is SessionState.FAILED
    assert len(result.items) == 1
    assert result.recording is RecordingStatus.OK
    assert result.error == FailureDetail(
        "ValueError",
        "executor result recording must match execution-set recording",
    )
    assert recordings[0].finishes == [
        (SessionState.FAILED, RecordingStatus.OK)
    ]


def test_verifier_rejects_aggregate_outcome_missing_from_reliable_emission() -> None:
    class HiddenIntegrityOutcome(IntegrityOutcome):
        pass

    class HiddenRunResult(IntegrityRunResult):
        pass

    class InspectRecording(_Recording):
        def finish(
            self,
            status: SessionState,
            recording: RecordingStatus,
        ) -> None:
            gc.collect()
            assert aggregate_refs[-1]() is None
            super().finish(status, recording)

    operation = _operation(87, 5)
    continuation = _verify_continuation_fixture(operation)
    producer_refs: list[ref[_PrivateWorkflowFrameValue]] = []
    aggregate_refs: list[ref[HiddenRunResult]] = []
    events: list[object] = []

    def verifier(selection, context, recorder):
        del recorder
        candidate = selection.pending[0]
        hidden = _PrivateWorkflowFrameValue()
        producer_refs.append(ref(hidden))
        item = HiddenIntegrityOutcome(
            item_id=candidate.item_id,
            row_id="forged-row",
            location_id="forged-location",
            path="producer-forged.txt",
            result=IntegrityResult.VERIFIED,
            read_strategy=ReadStrategy.WINDOWS_UNBUFFERED,
            record_disposition=RecordDisposition.APPLIED,
        )
        object.__setattr__(item, "hidden_graph", hidden)
        selection.note_bytes_processed(candidate.expected_stat.size)
        context.run.emit(item)
        object.__setattr__(item, "path", "producer-mutated.txt")
        selection.mark_completed(candidate.item_id, candidate.expected_stat.size)
        unreported = IntegrityOutcome(
            item_id="unreported",
            row_id=None,
            location_id=None,
            path="unreported.txt",
            result=IntegrityResult.ERROR,
            recording=RecordingStatus.DEGRADED,
        )
        aggregate = HiddenRunResult(
            (unreported,),
            RecordingStatus.DEGRADED,
        )
        aggregate_refs.append(ref(aggregate))
        return aggregate

    recordings: list[_Recording] = []
    dependencies = _deps(
        executor=lambda *args: pytest.fail("execution phase repeated"),
        verifier=verifier,
        recordings=recordings,
    )
    dependencies.open_recording = lambda _execution_set: (
        recordings.append(InspectRecording()) or recordings[-1]
    )
    result = run_execution(
        continuation,
        RunContext(events.append, lambda: None),
        dependencies,
        resumed=True,
    )

    integrity_events = [
        body for body in events if isinstance(body, IntegrityOutcome)
    ]
    assert len(integrity_events) == 1
    assert result.items == tuple(integrity_events)
    item = result.items[0]
    assert type(item) is IntegrityOutcome
    assert item.item_id == continuation.candidates.candidates[0].item_id
    assert item.path == operation.target_rel_path
    identity = continuation.candidates.candidates[0].recorded_identity
    assert identity is not None
    assert (item.row_id, item.location_id) == (
        identity.row_id,
        identity.location_id,
    )
    assert item.phase == "verify"
    assert result.phases[-1].status is PhaseStatus.INCOMPLETE
    assert result.error == FailureDetail(
        "ValueError",
        "integrity runner outcomes must match emitted outcomes",
    )
    assert result.recording is RecordingStatus.OK
    gc.collect()
    assert producer_refs and all(reference() is None for reference in producer_refs)
    assert aggregate_refs and all(reference() is None for reference in aggregate_refs)


def test_verifier_aggregate_cannot_erase_emitted_recording_degradation() -> None:
    operation = _operation(90, 5)
    continuation = _verify_continuation_fixture(operation)

    def verifier(selection, context, recorder):
        del recorder
        candidate = selection.pending[0]
        outcome = _integrity_outcome(
            candidate,
            recording=RecordingStatus.DEGRADED,
            disposition=RecordDisposition.STALE,
        )
        selection.note_bytes_processed(candidate.expected_stat.size)
        context.run.emit(outcome)
        selection.mark_completed(candidate.item_id, candidate.expected_stat.size)
        aggregate = IntegrityRunResult(
            (outcome,),
            RecordingStatus.DEGRADED,
        )
        object.__setattr__(aggregate, "recording", RecordingStatus.OK)
        return aggregate

    recordings: list[_Recording] = []
    result = run_execution(
        continuation,
        RunContext(lambda _body: None, lambda: None),
        _deps(
            executor=lambda *args: pytest.fail("execution phase repeated"),
            verifier=verifier,
            recordings=recordings,
        ),
        resumed=True,
    )

    assert len(result.items) == 1
    assert result.items[0].recording is RecordingStatus.DEGRADED
    assert result.recording is RecordingStatus.DEGRADED
    assert result.phases[-1].status is PhaseStatus.INCOMPLETE
    assert result.error == FailureDetail(
        "ValueError",
        "integrity runner recording must derive from emitted outcomes",
    )
    assert recordings[0].finishes == [
        (SessionState.COMPLETED, RecordingStatus.DEGRADED)
    ]


@pytest.mark.parametrize("corruption", ["missing-completion", "silent-completion"])
def test_verifier_success_requires_exact_emitted_completion(
    corruption: str,
) -> None:
    operation = _operation(95, 5)
    continuation = _verify_continuation_fixture(operation)

    def verifier(selection, context, recorder):
        del recorder
        candidate = selection.pending[0]
        if corruption == "silent-completion":
            selection.note_bytes_processed(candidate.expected_stat.size)
            selection.mark_completed(candidate.item_id, candidate.expected_stat.size)
            return IntegrityRunResult((), RecordingStatus.OK)
        outcome = _integrity_outcome(candidate)
        context.run.emit(outcome)
        return IntegrityRunResult((outcome,), RecordingStatus.OK)

    result = run_execution(
        continuation,
        RunContext(lambda _body: None, lambda: None),
        _deps(
            executor=lambda *args: pytest.fail("execution phase repeated"),
            verifier=verifier,
            recordings=[],
        ),
        resumed=True,
    )

    assert result.status is SessionState.COMPLETED
    assert result.phases[-1].status is PhaseStatus.INCOMPLETE
    assert result.error == FailureDetail(
        "ValueError",
        "post-copy verifier completion must match its emitted outcomes",
    )


def test_verifier_pause_cannot_silently_complete_an_unemitted_candidate() -> None:
    operation = _operation(103, 5)
    continuation = _verify_continuation_fixture(operation)

    def verifier(selection, context, recorder):
        del context, recorder
        candidate = selection.pending[0]
        selection.note_bytes_processed(candidate.expected_stat.size)
        selection.mark_completed(candidate.item_id, candidate.expected_stat.size)
        raise PauseRequested()

    result = run_execution(
        continuation,
        RunContext(lambda _body: None, lambda: None),
        _deps(
            executor=lambda *args: pytest.fail("execution phase repeated"),
            verifier=verifier,
            recordings=[],
        ),
        resumed=True,
    )

    assert result.status is SessionState.COMPLETED
    assert result.phases[-1].status is PhaseStatus.INCOMPLETE
    assert result.error == FailureDetail(
        "ValueError",
        "post-copy verifier completion must match its emitted outcomes",
    )


def test_verify_handoff_rejects_candidate_mutation_before_verifier_entry() -> None:
    operation = _operation(104, 5)
    xset = _execution_set(operation)
    verifier_calls = 0

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
            bytes_done=operation.content_bytes,
            bytes_total=operation.content_bytes,
        )

    def mutate_handoff(value):
        if not isinstance(value, VerifyContinuation):
            return
        candidate = value.candidates.candidates[0]
        object.__setattr__(
            candidate.expected_stat,
            "mtime_ns",
            candidate.expected_stat.mtime_ns + 1,
        )

    def verifier(*args):
        nonlocal verifier_calls
        verifier_calls += 1
        pytest.fail("mutated verification candidate was admitted")

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda _body: None, lambda: None),
        _deps(executor=executor, verifier=verifier, recordings=[]),
        continuation_sink=mutate_handoff,
    )

    assert verifier_calls == 0
    assert result.status is SessionState.COMPLETED
    assert result.phases[-1].status is PhaseStatus.INCOMPLETE
    assert result.error == FailureDetail(
        "ValueError",
        "post-copy candidate changed during collaboration",
    )


def test_verifier_duplicate_refuses_before_reading_hostile_detail() -> None:
    class HostileDuplicate(IntegrityOutcome):
        def __getattribute__(self, name: str):
            if name == "detail" and object.__getattribute__(
                self, "__dict__"
            ).get("hostile", False):
                raise AssertionError("duplicate detail was read")
            return super().__getattribute__(name)

    operation = _operation(89, 3)
    continuation = _verify_continuation_fixture(operation)

    def verifier(selection, context, recorder):
        del recorder
        candidate = selection.pending[0]
        first = _integrity_outcome(candidate)
        selection.note_bytes_processed(candidate.expected_stat.size)
        context.run.emit(first)
        selection.mark_completed(candidate.item_id, candidate.expected_stat.size)
        identity = candidate.recorded_identity
        assert identity is not None
        duplicate = HostileDuplicate(
            candidate.item_id,
            identity.row_id,
            identity.location_id,
            candidate.display_path,
            IntegrityResult.VERIFIED,
        )
        duplicate.hostile = True
        context.run.emit(duplicate)
        raise AssertionError("duplicate outcome was accepted")

    result = run_execution(
        continuation,
        RunContext(lambda _body: None, lambda: None),
        _deps(
            executor=lambda *args: pytest.fail("execution phase repeated"),
            verifier=verifier,
            recordings=[],
        ),
        resumed=True,
    )

    assert result.status is SessionState.COMPLETED
    assert len(result.items) == 1
    assert result.error == FailureDetail(
        "ValueError",
        "verifier emitted a duplicate integrity outcome",
    )
    assert result.phases[-1].status is PhaseStatus.INCOMPLETE


@pytest.mark.parametrize("corruption", ["mutated", "forged"])
def test_run_execution_revalidates_direct_verify_continuations(
    corruption: str,
) -> None:
    continuation = _verify_continuation_fixture(_operation(83, 4))
    phase = continuation.execute_phase
    if corruption == "mutated":
        object.__setattr__(phase, "items_done", -1)
    else:
        forged = object.__new__(PhaseResult)
        for name, value in (
            ("phase", phase.phase),
            ("status", phase.status),
            ("items_done", -1),
            ("items_total", phase.items_total),
            ("bytes_done", phase.bytes_done),
            ("bytes_total", phase.bytes_total),
            ("error", phase.error),
        ):
            object.__setattr__(forged, name, value)
        object.__setattr__(continuation, "execute_phase", forged)

    with pytest.raises(ValueError, match="phase items_done"):
        run_execution(
            continuation,
            RunContext(lambda _body: None, lambda: None),
            _deps(
                executor=lambda *args: pytest.fail("execution phase repeated"),
                verifier=_verify_all,
                recordings=[],
            ),
            resumed=True,
        )


def test_canceled_settlement_revalidates_direct_verify_continuation() -> None:
    continuation = _verify_continuation_fixture(_operation(84, 5))
    object.__setattr__(continuation.execute_phase, "error", "x" * 1025)
    recordings: list[_Recording] = []

    with pytest.raises(ValueError, match="execute phase error"):
        settle_canceled_execution(
            continuation,
            Disposition.RAN,
            SimpleNamespace(
                open_recording=lambda execution_set: (
                    recordings.append(_Recording()) or recordings[-1]
                )
            ),
        )

    assert not recordings


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
            evidence=_evidence(operation, scope_token="b" * 32),
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
            recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
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
            recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
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
    assert result.error == FailureDetail("RuntimeError", "readback exploded")
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
    assert result.error == FailureDetail(
        "ValueError",
        "post-copy verifier completion must match its emitted outcomes",
    )


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
        ("result", "integrity runner must return IntegrityRunResult"),
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
    failure = RuntimeError("continuation publication failed")
    references: list[ref[_PrivateWorkflowFrameValue]] = []

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
            error=FailureDetail("T", "x" * 1022),
        )

    def reject_continuation(value) -> None:
        del value
        _raise_with_private_workflow_frame(failure, references)

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
    assert result.omitted_detail_count == xset.omitted_detail_count == 1
    assert recordings[0].finishes == [
        (SessionState.FAILED, RecordingStatus.OK)
    ]
    gc.collect()
    assert references and all(reference() is None for reference in references)


@pytest.mark.parametrize(
    "owner",
    ("execution-details", "observer", "preflight", "executor", "verifier"),
)
def test_execution_retires_consumed_callback_failure_frames(owner: str) -> None:
    operation = _operation(83, 9)
    xset = _execution_set(operation)
    if owner == "execution-details":
        xset = replace(xset, commitment=None)
    failure = RuntimeError(f"{owner} failed")
    references: list[ref[_PrivateWorkflowFrameValue]] = []
    recordings: list[_Recording] = []

    def fail(*args: object, **kwargs: object) -> None:
        del args, kwargs
        _raise_with_private_workflow_frame(failure, references)

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        if owner == "executor":
            fail()
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

    deps = _deps(
        executor=executor,
        verifier=fail if owner == "verifier" else _verify_all,
        recordings=recordings,
    )
    if owner == "execution-details":
        deps.save_execution_details = fail
    elif owner == "observer":
        deps.observer = fail
    elif owner == "preflight":
        deps.preflight = fail

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=owner == "verifier"),
        RunContext(lambda body: None, lambda: None),
        deps,
    )

    assert result.status is (
        SessionState.COMPLETED if owner == "verifier" else SessionState.FAILED
    )
    assert result.error == FailureDetail("RuntimeError", f"{owner} failed")
    gc.collect()
    assert references and all(reference() is None for reference in references)


def test_execution_retires_consumed_cancellation_frames() -> None:
    operation = _operation(84, 9)
    xset = _execution_set(operation)
    cancellation = Canceled("executor canceled")
    references: list[ref[_PrivateWorkflowFrameValue]] = []

    def cancel_executor(*args: object) -> None:
        del args
        _raise_with_private_workflow_frame(cancellation, references)

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(lambda body: None, lambda: None),
        _deps(
            executor=cancel_executor,
            verifier=lambda *args: pytest.fail("verification unexpectedly started"),
            recordings=[],
        ),
    )

    assert result.status is SessionState.CANCELED
    assert result.canceled
    assert result.disposition is Disposition.RAN
    gc.collect()
    assert references and all(reference() is None for reference in references)


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


@pytest.mark.parametrize("hostile_sink", [False, True])
@pytest.mark.parametrize("execution_exit", ["failed", "completed", "canceled"])
@pytest.mark.parametrize("accepted_exclusions", [0, 1])
@pytest.mark.parametrize("verify_after_execute", [False, True])
def test_compound_exclusion_close_failure_retains_terminal_truth(
    execution_exit: str, accepted_exclusions: int, verify_after_execute: bool,
    hostile_sink: bool,
) -> None:
    first, second = _operation(63, 5), _operation(64, 7)
    excluded = (_operation(65, 2), _operation(66, 3))
    initial = _execution_set(first, second, *excluded)
    selection = frozenset({first.op_id, second.op_id})
    xset = replace(
        initial,
        selection=selection,
        commitment=Commitment(initial.plan.fingerprint, selection_digest(selection), NOW),
        user_deselected=frozenset(operation.op_id for operation in excluded),
    )
    recording = _Recording(exit_fails=True)
    events: list[object] = []
    published: list[OperationResult] = []
    rejected = excluded[accepted_exclusions]
    primary = (
        _UnrenderableRecordingError() if hostile_sink
        else RuntimeError("first exclusion sink failure")
    )
    references: list[ref[_PrivateWorkflowFrameValue]] = []
    rejected_calls = 0

    def executor(execution_set, context, *args):
        first_item = _settle(execution_set, context, first, evidence=_evidence(first))
        execution_set.note_bytes_done(6 if execution_exit != "completed" else 12)
        if execution_exit == "failed":
            raise OSError("execution failed before exclusions")
        if execution_exit == "canceled":
            raise Canceled()
        second_item = _settle(execution_set, context, second, evidence=_evidence(second))
        return OperationResult(
            SessionState.COMPLETED,
            items=(first_item, second_item),
            bytes_done=12,
            bytes_total=12,
        )

    def emit(body):
        nonlocal rejected_calls
        if isinstance(body, ItemOutcome) and body.item_id == str(rejected.op_id):
            rejected_calls += 1
            if rejected_calls == 1:
                _raise_with_private_workflow_frame(primary, references)
            raise RuntimeError("later exclusion sink failure")
        events.append(body)

    deps = _deps(
        executor=executor,
        verifier=lambda *args: pytest.fail("verification unexpectedly started"),
        recordings=[],
    )
    deps.open_recording = lambda execution_set: recording
    outcome = run_session(
        lambda context: run_execution(
            ExecuteContinuation(xset, verify_after_execute=verify_after_execute),
            context,
            deps,
        ),
        emit=emit,
        checkpoint=lambda: None,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=published.append,
    )

    result = outcome.result
    assert result is not None
    assert result.status is SessionState.FAILED
    assert not result.canceled
    assert result.recording is xset.recording is RecordingStatus.DEGRADED
    assert result.recording_issues == xset.recording_issues
    assert tuple(issue.reason for issue in result.recording_issues) == (
        TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
    )
    assert result.error is not None
    assert result.error.type_name == type(primary).__name__
    assert result.error.message == (
        "recording diagnostic unavailable" if hostile_sink
        else "first exclusion sink failure"
    )
    assert rejected_calls == 1
    assert result.bytes_done == (12 if execution_exit == "completed" else 6)
    assert result.bytes_total == 12
    assert len(result.phases) == int(verify_after_execute)
    if verify_after_execute:
        assert result.phases[0].status is PhaseStatus.FAILED
        assert result.phases[0].bytes_done == result.bytes_done
    expected_ids = [str(first.op_id)]
    if execution_exit == "completed":
        expected_ids.append(str(second.op_id))
    expected_ids.extend(str(op.op_id) for op in excluded[:accepted_exclusions])
    assert [item.item_id for item in result.items] == expected_ids
    assert [
        event.item_id for event in events if isinstance(event, ItemOutcome)
    ] == expected_ids
    terminals = [event for event in events if isinstance(event, Terminal)]
    assert len(terminals) == 1
    assert terminals[0].result == TerminalSummary.from_result(result)
    assert published == [result]
    assert recording.finishes == [(SessionState.FAILED, RecordingStatus.OK)]
    gc.collect()
    assert references and all(reference() is None for reference in references)


@pytest.mark.parametrize("verify_after_execute", [False, True])
def test_dispatcher_compound_exclusion_close_failure_survives_payload_scrub(
    tmp_path: Path, monkeypatch, verify_after_execute: bool
) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    for name in ("a.bin", "b.bin", "c.bin"):
        (source / name).write_bytes(b"reviewed")
    runtime = LocalWorkflowRuntime(tmp_path / "ledger.db", tmp_path / "history.db")
    store = InMemorySessionStore()
    finishes: list[tuple[SessionState, RecordingStatus]] = []
    observed_xsets: list[ExecutionSet] = []
    emitted: list[object] = []
    original_emit = dispatcher_event_bus.EventHub.emit
    original_open = runtime._deps.open_recording

    def fail_executor(execution_set, *args):
        execution_set.note_bytes_done(3)
        observed_xsets.append(execution_set)
        raise OSError("execution failed before exclusions")

    @contextmanager
    def close_failed_recording(execution_set):
        try:
            with original_open(execution_set) as recording:
                def finish(status, recording_status):
                    finishes.append((status, recording_status))
                    recording.finish(status, recording_status)

                yield SimpleNamespace(recorder=recording.recorder, finish=finish)
        finally:
            raise OSError("recording close failed")

    def reject_exclusion(hub, body, **kwargs):
        if isinstance(body, ItemOutcome) and body.path == "c.bin":
            raise RuntimeError("exclusion sink failure")
        envelope = original_emit(hub, body, **kwargs)
        emitted.append(body)
        return envelope

    runtime._deps = replace(
        runtime._deps, executor=fail_executor, open_recording=close_failed_recording
    )
    monkeypatch.setattr(dispatcher_event_bus.EventHub, "emit", reject_exclusion)
    dispatcher = Dispatcher(
        _workflow_registry(runtime),
        store=store,
        lock_provider=InProcessResourceLockProvider(),
        clock=runtime.clock,
        audit_observer_factory=runtime.audit_observer,
    )
    try:
        request = PlanRequest(
            request_id="5" * 32, source_path=str(source), target_path=str(target)
        )
        runtime.open_plan(runtime.prepare_plan(request).payload).run(
            RunContext(lambda body: None, lambda: None)
        )
        plan = runtime.get_plan(request.request_id).plan
        execution = runtime.commit_plan(
            request.request_id,
            run_id="6" * 32,
            committed_at=NOW,
            verify_after_execute=verify_after_execute,
            user_deselected=frozenset(
                str(operation.op_id) for operation in plan.operations
                if operation.target_rel_path in {"b.bin", "c.bin"}
            ),
        )
        session_id = dispatcher.submit(EXECUTION_KIND, execution)
        record = _wait_for_session(dispatcher, session_id, SessionState.FAILED)
        stored = next(row for row in store.snapshot() if row.session_id == session_id)
    finally:
        shutdown = dispatcher.shutdown()
        runtime.close()

    assert shutdown.complete
    assert type(stored) is StoredSessionRecord
    assert not hasattr(stored, "payload")
    assert stored.session_id == record.session_id
    assert stored.kind == record.kind
    assert stored.state is record.state
    assert stored.resources == record.resources
    assert stored.supports_pause is record.supports_pause
    assert stored.admission_order == record.admission_order
    assert stored.created_at == record.created_at
    assert stored.started_at == record.started_at
    assert stored.ended_at == record.ended_at
    assert stored.result is record.result
    assert record.payload is None
    result = record.result
    assert result is not None
    assert result.recording is RecordingStatus.DEGRADED
    assert result.recording_issues == observed_xsets[0].recording_issues
    assert tuple(issue.reason for issue in result.recording_issues) == (
        TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
    )
    assert result.error is not None
    assert result.error.message == "exclusion sink failure"
    assert result.bytes_done == 3
    assert result.bytes_total == len(b"reviewed")
    assert [item.path for item in result.items] == ["b.bin"]
    assert [event.path for event in emitted if isinstance(event, ItemOutcome)] == ["b.bin"]
    terminals = [event for event in emitted if isinstance(event, Terminal)]
    assert len(terminals) == 1
    assert terminals[0].result == TerminalSummary.from_result(result)
    assert finishes == [(SessionState.FAILED, RecordingStatus.OK)]


def test_recording_open_failure_preserves_already_failed_resume_projection() -> None:
    xset = _execution_set(_operation(65))
    open_calls = 0

    def fail_preflight(*args):
        raise OSError("preflight failure")

    def fail_open(*args):
        nonlocal open_calls
        open_calls += 1
        raise RuntimeError("recording open failure")

    deps = _deps(executor=lambda *args: None, verifier=lambda *args: None, recordings=[])
    deps.observer = fail_preflight
    deps.open_recording = fail_open
    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(lambda body: None, lambda: None),
        deps,
        resumed=True,
    )

    assert open_calls == 1
    assert result.status is SessionState.FAILED
    assert result.error is not None
    assert result.error.message == "preflight failure"
    assert result.recording is RecordingStatus.DEGRADED
    assert tuple(issue.reason for issue in result.recording_issues) == (
        TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
    )


def test_verify_present_close_failure_retains_execution_task_issue() -> None:
    operation = _operation(65)
    xset = _execution_set(operation)
    recording = _Recording(exit_fails=True)

    def executor(execution_set, context, *args):
        item = _settle(execution_set, context, operation, evidence=_evidence(operation))
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=operation.content_bytes,
            bytes_total=operation.content_bytes,
        )

    deps = _deps(executor=executor, verifier=_verify_all, recordings=[])
    deps.open_recording = lambda execution_set: recording
    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(lambda body: None, lambda: None),
        deps,
    )

    assert result.status is SessionState.COMPLETED
    assert len(result.phases) == 2
    assert result.recording is xset.recording is RecordingStatus.DEGRADED
    assert result.recording_issues == xset.recording_issues
    assert tuple(issue.reason for issue in result.recording_issues) == (
        TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
    )


def test_canceled_open_failure_passes_degraded_axis_to_fallback_finisher() -> None:
    xset = _execution_set(_operation(65))
    finished: list[tuple[SessionState, RecordingStatus]] = []

    def fail_open(*args):
        raise OSError("recording open failure")

    result = settle_canceled_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        Disposition.RAN,
        SimpleNamespace(
            open_recording=fail_open,
            finish_existing_recording=lambda execution_set, status, recording: (
                finished.append((status, recording))
            ),
        ),
    )

    assert result.status is SessionState.CANCELED
    assert result.recording is RecordingStatus.DEGRADED
    assert finished == [(SessionState.CANCELED, RecordingStatus.DEGRADED)]
    assert tuple(issue.reason for issue in result.recording_issues) == (
        TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
    )


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
        del recorder, policies, fs
        executor_calls += 1
        item = _settle(execution_set, context, operation)
        execution_set.note_bytes_done(9)
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
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


class _UnrenderableRecordingError(RuntimeError):
    def __init__(self, diagnostic: str = "str") -> None:
        super().__init__("recorder failed")
        self.diagnostic = diagnostic

    def __str__(self) -> str:
        if self.diagnostic == "str":
            raise ValueError("recording message unavailable")
        return super().__str__()

    @property
    def filename(self) -> str:
        raise ValueError("recording filename unavailable")


class _FatalRecordingDiagnosticError(RuntimeError):
    def __init__(
        self,
        diagnostic: str,
        failure: BaseException,
        references: list[ref[_PrivateWorkflowFrameValue]],
    ) -> None:
        super().__init__("recorder failed")
        self.diagnostic = diagnostic
        self.failure = failure
        self.references = references

    def __str__(self) -> str:
        if self.diagnostic == "str":
            _raise_with_private_workflow_frame(
                self.failure,
                self.references,
            )
        return super().__str__()

    @property
    def filename(self) -> str:
        if self.diagnostic == "filename":
            _raise_with_private_workflow_frame(
                self.failure,
                self.references,
            )
        return "recording.db"


class _HostileNotePause(PauseRequested):
    def add_note(self, note: str) -> None:
        del note
        raise AssertionError("dynamic add_note was invoked")


class _CorruptNotesPause(PauseRequested):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.__notes__ = "caller-owned corrupt notes"


@pytest.mark.parametrize("diagnostic", ["str", "logical"])
@pytest.mark.parametrize("boundary", ["factory", "enter", "finish", "exit"])
def test_recording_diagnostic_failure_preserves_workflow_truth(
    boundary: str, diagnostic: str
) -> None:
    xset = _execution_set(_operation(65, 9))
    xset.note_bytes_done(4)
    primary = _UnrenderableRecordingError(diagnostic)
    references: list[ref[_PrivateWorkflowFrameValue]] = []

    class Recording(_Recording):
        def __enter__(self):
            if boundary == "enter":
                _raise_with_private_workflow_frame(primary, references)
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            if boundary == "exit":
                _raise_with_private_workflow_frame(primary, references)

        def finish(self, status, recording_status) -> None:
            super().finish(status, recording_status)
            if boundary == "finish":
                _raise_with_private_workflow_frame(primary, references)

    recording = Recording()

    def open_recording(execution_set):
        if boundary == "factory":
            _raise_with_private_workflow_frame(primary, references)
        return recording

    def executor(execution_set, context, recorder, policies, fs):
        del recorder, policies, fs
        item = _settle(execution_set, context, xset.plan.operations[0])
        execution_set.note_bytes_done(9)
        return OperationResult(
            SessionState.COMPLETED,
            items=(item,),
            bytes_done=9,
            bytes_total=9,
        )

    deps = _deps(
        executor=executor,
        verifier=lambda *args: pytest.fail("verification unexpectedly started"),
        recordings=[],
    )
    deps.open_recording = open_recording
    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(lambda body: None, lambda: None),
        deps,
        resumed=True,
    )

    open_failed = boundary in {"factory", "enter"}
    reason = (
        TaskRecordingIssueReason.RECORDING_OPEN_FAILED if open_failed else
        TaskRecordingIssueReason.FINISH_FAILED if boundary == "finish" else
        TaskRecordingIssueReason.RECORDING_CLOSE_FAILED
    )
    assert result.status is (
        SessionState.FAILED if open_failed else SessionState.COMPLETED
    )
    assert result.bytes_done == (4 if open_failed else 9)
    assert result.bytes_total == 9
    assert result.recording is xset.recording is RecordingStatus.DEGRADED
    assert tuple((issue.reason, issue.detail) for issue in result.recording_issues) == (
        (reason, None),
    )
    assert result.recording_issues == xset.recording_issues
    assert result.omitted_detail_count == xset.omitted_detail_count == 0
    if boundary == "finish":
        assert result.error is None
    else:
        assert result.error is not None
        assert result.error.type_name == type(primary).__name__
        assert result.error.message == "recording diagnostic unavailable"
    gc.collect()
    assert references and all(reference() is None for reference in references)


@pytest.mark.parametrize("diagnostic", ["str", "filename"])
def test_recording_process_fatal_diagnostic_cannot_mask_primary(
    diagnostic: str,
) -> None:
    xset = _execution_set(_operation(65, 9))
    xset.note_bytes_done(4)
    primary_references: list[ref[_PrivateWorkflowFrameValue]] = []
    diagnostic_references: list[ref[_PrivateWorkflowFrameValue]] = []
    diagnostic_failure = KeyboardInterrupt("diagnostic interrupted")
    primary = _FatalRecordingDiagnosticError(
        diagnostic,
        diagnostic_failure,
        diagnostic_references,
    )

    def fail_open(*args: object) -> None:
        del args
        _raise_with_private_workflow_frame(primary, primary_references)

    deps = _deps(
        executor=lambda *args: pytest.fail("execution unexpectedly started"),
        verifier=lambda *args: pytest.fail("verification unexpectedly started"),
        recordings=[],
    )
    deps.open_recording = fail_open

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(lambda body: None, lambda: None),
        deps,
        resumed=True,
    )

    assert result.status is SessionState.FAILED
    assert result.error == FailureDetail(
        "_FatalRecordingDiagnosticError",
        "recording diagnostic unavailable",
    )
    assert result.recording is RecordingStatus.DEGRADED
    assert tuple((issue.reason, issue.detail) for issue in result.recording_issues) == (
        (TaskRecordingIssueReason.RECORDING_OPEN_FAILED, None),
    )
    gc.collect()
    assert primary_references and all(
        reference() is None for reference in primary_references
    )
    assert diagnostic_references and all(
        reference() is None for reference in diagnostic_references
    )


def test_recording_exit_truth_tests_once_and_retires_suppressed_failure() -> None:
    xset = _execution_set(_operation(66, 8))
    primary = KeyboardInterrupt("suppressed finish failure")
    references: list[ref[_PrivateWorkflowFrameValue]] = []
    truth_tests = 0

    class Truthy:
        def __bool__(self) -> bool:
            nonlocal truth_tests
            truth_tests += 1
            return True

    class Recording(_Recording):
        def finish(self, status, recording_status) -> None:
            del status, recording_status
            _raise_with_private_workflow_frame(primary, references)

        def __exit__(self, exc_type, exc, traceback) -> object:
            assert exc is primary
            return Truthy()

    result = settle_canceled_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        Disposition.RAN,
        SimpleNamespace(open_recording=lambda execution_set: Recording()),
    )

    assert result.status is SessionState.CANCELED
    assert result.error is None
    assert truth_tests == 1
    gc.collect()
    assert references and all(reference() is None for reference in references)


def test_recording_exit_truthiness_failure_preserves_python_behavior() -> None:
    xset = _execution_set(_operation(67, 8))
    primary = PauseRequested("execution paused")
    truth_failure = LookupError("recording exit truthiness failed")
    references: list[ref[_PrivateWorkflowFrameValue]] = []
    truth_tests = 0

    class HostileTruth:
        def __bool__(self) -> bool:
            nonlocal truth_tests
            truth_tests += 1
            _raise_with_private_workflow_frame(truth_failure, references)

    class Recording(_Recording):
        def __exit__(self, exc_type, exc, traceback) -> object:
            assert exc is primary
            return HostileTruth()

    def pause_executor(*args: object) -> None:
        del args
        raise primary

    deps = _deps(
        executor=pause_executor,
        verifier=lambda *args: pytest.fail("verification unexpectedly started"),
        recordings=[],
    )
    deps.open_recording = lambda execution_set: Recording()

    with pytest.raises(LookupError) as raised:
        run_execution(
            ExecuteContinuation(xset, verify_after_execute=False),
            RunContext(lambda body: None, lambda: None),
            deps,
        )

    assert raised.value is truth_failure
    assert truth_tests == 1
    assert truth_failure.__context__ is None
    gc.collect()
    assert references and all(reference() is None for reference in references)


def test_recording_close_diagnostic_failure_preserves_primary_filesystem_error() -> None:
    primary = OSError("primary filesystem error")

    class Recording(_Recording):
        def __exit__(self, exc_type, exc, traceback) -> None:
            raise _UnrenderableRecordingError()

    def executor(*args):
        raise primary

    deps = _deps(executor=executor, verifier=lambda *args: None, recordings=[])
    deps.open_recording = lambda execution_set: Recording()
    result = run_execution(
        ExecuteContinuation(_execution_set(_operation(65)), verify_after_execute=False),
        RunContext(lambda body: None, lambda: None),
        deps,
    )

    assert result.status is SessionState.FAILED
    assert result.error is not None
    assert result.error.type_name == "OSError"
    assert result.error.message == "primary filesystem error"
    assert result.recording is RecordingStatus.DEGRADED
    assert tuple((issue.reason, issue.detail) for issue in result.recording_issues) == (
        (TaskRecordingIssueReason.RECORDING_CLOSE_FAILED, None),
    )


@pytest.mark.parametrize(
    "primary_type",
    [PauseRequested, _HostileNotePause, _CorruptNotesPause, KeyboardInterrupt],
)
def test_recording_diagnostic_failure_cannot_mask_escaping_primary(
    primary_type: type[BaseException],
) -> None:
    xset = _execution_set(_operation(65))
    primary = primary_type("primary execution failure")
    references: list[ref[_PrivateWorkflowFrameValue]] = []

    class Recording(_Recording):
        def __exit__(self, exc_type, exc, traceback) -> None:
            raise _UnrenderableRecordingError()

    def executor(*args):
        _raise_with_private_workflow_frame(primary, references)

    def capture(value):
        if value.execution_set.recording is RecordingStatus.DEGRADED:
            raise _UnrenderableRecordingError()

    deps = _deps(executor=executor, verifier=lambda *args: None, recordings=[])
    deps.open_recording = lambda execution_set: Recording()
    with pytest.raises(primary_type) as raised:
        run_execution(
            ExecuteContinuation(xset, verify_after_execute=False),
            RunContext(lambda body: None, lambda: None),
            deps,
            continuation_sink=capture,
        )

    assert raised.value is primary
    assert xset.recording is RecordingStatus.DEGRADED
    assert tuple((issue.reason, issue.detail) for issue in xset.recording_issues) == (
        (TaskRecordingIssueReason.RECORDING_CLOSE_FAILED, None),
    )
    if isinstance(primary, _CorruptNotesPause):
        assert primary.__notes__ == "caller-owned corrupt notes"
    else:
        assert primary.__notes__ == [
            "recording degradation continuation capture also failed: "
            "_UnrenderableRecordingError: recording diagnostic unavailable",
            "recording context exit also failed: "
            "_UnrenderableRecordingError: recording diagnostic unavailable",
        ]
    gc.collect()
    assert references and all(reference() is None for reference in references)


@pytest.mark.parametrize("boundary", ["enter", "finish", "exit"])
def test_recording_diagnostic_failure_preserves_canceled_settlement(boundary: str) -> None:
    xset = _execution_set(_operation(66, 8))
    xset.note_bytes_done(5)
    primary = _UnrenderableRecordingError()

    class Recording(_Recording):
        def __enter__(self):
            if boundary == "enter":
                raise primary
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            if boundary == "exit":
                raise primary

        def finish(self, status, recording_status) -> None:
            if boundary == "finish":
                raise primary

    result = settle_canceled_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        Disposition.RAN,
        SimpleNamespace(open_recording=lambda execution_set: Recording()),
    )

    reason = {
        "enter": TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
        "finish": TaskRecordingIssueReason.FINISH_FAILED,
        "exit": TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
    }[boundary]
    assert result.status is SessionState.CANCELED
    assert result.canceled
    assert result.bytes_done == 5
    assert result.bytes_total == 8
    assert result.recording is RecordingStatus.DEGRADED
    assert tuple((issue.reason, issue.detail) for issue in result.recording_issues) == (
        (reason, None),
    )
    if boundary == "finish":
        assert result.error is None
    else:
        assert result.error is not None
        assert result.error.type_name == type(primary).__name__
        assert result.error.message == "recording diagnostic unavailable"


@pytest.mark.parametrize("fallback", ["entry-cancel", "preflight", "preflight-reopen"])
def test_recording_diagnostic_failure_contains_fallback_finish(fallback: str) -> None:
    xset = _execution_set(_operation(66, 8))

    def fail_finish(*args):
        raise _UnrenderableRecordingError()

    def cancel_open(*args):
        raise Canceled()

    def fail_preflight(*args):
        raise OSError("preflight unavailable")

    class Recording(_Recording):
        def finish(self, status, recording_status) -> None:
            fail_finish()

    deps = _deps(
        executor=lambda *args: pytest.fail("execution unexpectedly started"),
        verifier=lambda *args: pytest.fail("verification unexpectedly started"),
        recordings=[],
    )
    if fallback == "entry-cancel":
        deps.open_recording = cancel_open
        deps.finish_existing_recording = fail_finish
    else:
        deps.observer = fail_preflight
        if fallback == "preflight":
            deps.finish_existing_recording = fail_finish
        else:
            deps.open_recording = lambda execution_set: Recording()

    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=False),
        RunContext(lambda body: None, lambda: None),
        deps,
        resumed=True,
    )

    assert result.status is (
        SessionState.CANCELED if fallback == "entry-cancel" else SessionState.FAILED
    )
    assert result.recording is RecordingStatus.DEGRADED
    assert tuple((issue.reason, issue.detail) for issue in result.recording_issues) == (
        (TaskRecordingIssueReason.FINISH_FAILED, None),
    )
    if fallback != "entry-cancel":
        assert result.error is not None
        assert result.error.type_name == "OSError"
        assert result.error.message == "preflight unavailable"


def test_recording_open_primary_survives_secondary_emission_diagnostic_failure() -> None:
    selected, excluded = _operation(65), _operation(66)
    initial = _execution_set(selected, excluded)
    selection = frozenset({selected.op_id})
    xset = replace(
        initial,
        selection=selection,
        user_deselected=frozenset({excluded.op_id}),
        commitment=Commitment(initial.plan.fingerprint, selection_digest(selection), NOW),
    )

    def fail_open(*args):
        raise OSError("recording unavailable")

    def fail_exclusion(body):
        if isinstance(body, ItemOutcome):
            raise _UnrenderableRecordingError()

    deps = _deps(
        executor=lambda *args: pytest.fail("execution unexpectedly started"),
        verifier=lambda *args: pytest.fail("verification unexpectedly started"),
        recordings=[],
    )
    deps.open_recording = fail_open
    result = run_execution(
        ExecuteContinuation(xset, verify_after_execute=True),
        RunContext(fail_exclusion, lambda: None),
        deps,
    )

    assert result.status is SessionState.FAILED
    assert result.error is not None
    assert result.error.type_name == "OSError"
    assert result.error.message == "recording unavailable"
    assert result.recording is RecordingStatus.DEGRADED
    assert tuple(issue.reason for issue in result.recording_issues) == (
        TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
    )
    assert result.phases[0].error == (
        "OSError: recording unavailable; outcome emission also failed: "
        "_UnrenderableRecordingError: recording diagnostic unavailable"
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
        _observed_world(),
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
            _observed_world(),
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
        _settle(
            execution_set,
            context,
            operation,
            recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
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


@pytest.mark.parametrize("reject_persistently", [False, True])
def test_committed_copy_receipt_survives_reliable_sink_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reject_persistently: bool,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    content = b"payload"
    (source / "file.bin").write_bytes(content)
    runtime = LocalWorkflowRuntime(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
    )
    original_executor = runtime._deps.executor
    execution_sets: list[ExecutionSet] = []

    def observed_executor(execution_set, context, recorder, policies, fs):
        execution_sets.append(execution_set)
        return original_executor(execution_set, context, recorder, policies, fs)

    runtime._deps = replace(
        runtime._deps,
        executor=observed_executor,
        executor_policies=replace(
            runtime._deps.executor_policies,
            progress_interval_seconds=0,
        ),
    )
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
    attempted_items: list[ItemOutcome] = []
    accepted: list[object] = []
    published_results: list[OperationResult] = []
    original = OSError("reliable outcome sink failed")
    secondary = OSError("reliable outcome sink still failed")

    def emit(body: object) -> None:
        if isinstance(body, ItemOutcome):
            attempted_items.append(body)
            if len(attempted_items) == 1:
                raise original
            if reject_persistently:
                raise secondary
        accepted.append(body)

    try:
        plan_request = PlanRequest(
            request_id="c" * 32,
            source_path=str(source),
            target_path=str(target),
        )
        plan_result = runtime.open_plan(
            runtime.prepare_plan(plan_request).payload
        ).run(RunContext(lambda _body: None, lambda: None))
        assert plan_result.status is SessionState.COMPLETED
        execution = runtime.commit_plan(
            plan_request.request_id,
            run_id="d" * 32,
            committed_at=NOW,
            verify_after_execute=False,
        )
        invocation = runtime.open_execution(
            runtime.prepare_execution(execution).payload
        )
        session = run_session(
            invocation.run,
            emit=emit,
            checkpoint=lambda: None,
            settle=lambda _state, _result: None,
            finalize_audit=lambda _result: RecordingStatus.OK,
            publish_result=published_results.append,
        )
    finally:
        runtime.close()

    assert len(execution_sets) == 1
    xset = execution_sets[0]
    operation = xset.plan.operations[0]
    assert len(attempted_items) == 2
    assert all(item.outcome is Outcome.SUCCEEDED for item in attempted_items)
    assert all(item.recording is RecordingStatus.OK for item in attempted_items)
    assert len(retained) == 2
    journal, pending = retained[0]
    retry_journal, retry_pending = retained[1]
    assert retry_journal is journal
    assert retry_pending is pending
    assert pending.outcome is Outcome.SUCCEEDED
    assert pending.recording_reason is None
    assert pending.published_evidence is not None
    receipt = pending.published_evidence.recorded_identity
    assert receipt is not None

    assert session.result is not None
    result = session.result
    assert published_results == [result]
    assert result.status is SessionState.FAILED
    assert result.error is not None
    assert result.error.type_name == "OSError"
    assert result.error.message == str(original)
    assert (result.bytes_done, result.bytes_total) == (len(content), len(content))
    accepted_items = tuple(
        body for body in accepted if isinstance(body, ItemOutcome)
    )
    assert result.items == accepted_items
    assert len(accepted_items) == (0 if reject_persistently else 1)
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
    ) == (
        0 if reject_persistently else 1,
        1,
        len(content),
        len(content),
    )

    if reject_persistently:
        assert xset.status == {}
        assert xset.published_evidence == {}
        assert journal.has_active_entry(operation.op_id)
        assert journal.pending_settlement(operation.op_id) is pending
    else:
        assert xset.status == {operation.op_id: Outcome.SUCCEEDED}
        assert xset.published_evidence[operation.op_id].recorded_identity == receipt
        assert not journal.has_active_entry(operation.op_id)
    assert xset.recording_reasons == {}
    assert (target / "file.bin").read_bytes() == content

    connection = connect_ledger_reader(tmp_path / "ledger.db")
    try:
        operations = connection.execute(
            """SELECT operations.op_token, operations.kind, operations.outcome
                 FROM operations
                 JOIN runs ON runs.id = operations.run_id
                WHERE runs.run_token = ?""",
            ("d" * 32,),
        ).fetchall()
        row = connection.execute(
            """SELECT id, location_id, scope_token, rel_path_key
                 FROM inventory WHERE id = ?""",
            (receipt.row_id,),
        ).fetchone()
    finally:
        connection.close()

    assert [
        (value["op_token"], value["kind"], value["outcome"])
        for value in operations
    ] == [(str(operation.op_id), OperationKind.COPY.value, Outcome.SUCCEEDED.value)]
    assert row is not None
    assert str(row["id"]) == receipt.row_id
    assert str(row["location_id"]) == receipt.location_id
    assert row["scope_token"] == receipt.scope_token
    assert row["rel_path_key"] == receipt.rel_path_key


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
