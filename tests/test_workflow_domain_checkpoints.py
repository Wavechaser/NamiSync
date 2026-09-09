"""Typed execution-domain and semantic-checkpoint ownership contracts."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

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
    TaskRecordingIssue,
    TaskRecordingIssueReason,
    validate_execution_set,
    validated_run_id,
)
from namisync.core.integrity import (
    PostCopyCandidate,
    PostCopyRecordIdentity,
    PostCopySelection,
)
from namisync.core.models import (
    CapabilityProfile,
    EntryKind,
    FileStat,
    MetadataSnapshot,
    Root,
)
from namisync.core.pathing import normalize_relative_path
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
from namisync.core.scalars import MAX_SAFE_INTEGER
from namisync.core.session import PhaseResult, PhaseStatus, SessionState
from namisync.workflows.models import (
    ExecuteContinuation,
    ExecutionCheckpoint,
    ExecutionRequest,
    VerifyContinuation,
)


NOW = datetime(2026, 7, 19, 12, 30, tzinfo=timezone.utc)
RUN_ID = validated_run_id("a" * 32)


def _stat(
    size: int,
    *,
    kind: EntryKind = EntryKind.FILE,
    mtime_ns: int = 10,
) -> FileStat:
    return FileStat(
        kind,
        size,
        mtime_ns,
        None,
        1,
        MetadataSnapshot(0, None),
    )


def _operation(
    index: int,
    *,
    kind: OperationKind = OperationKind.COPY,
    size: int = 0,
) -> PlanOperation:
    path = "folder" if kind is OperationKind.MKDIR else f"file-{index}.bin"
    intended = _stat(
        size,
        kind=(
            EntryKind.DIRECTORY
            if kind is OperationKind.MKDIR
            else EntryKind.FILE
        ),
        mtime_ns=10 + index,
    )
    return PlanOperation(
        op_id=OpId(f"{index:032x}"),
        kind=kind,
        source_rel_path=path,
        target_rel_path=path,
        source_expected=intended,
        target_expected=None,
        intended=intended,
        content_bytes=size,
        reason=(
            OperationReason.REQUIRED_DIRECTORY
            if kind is OperationKind.MKDIR
            else OperationReason.SOURCE_ONLY
        ),
    )


def _plan() -> Plan:
    operations = (
        _operation(1, kind=OperationKind.MKDIR),
        _operation(2, size=5),
        _operation(3, size=7),
    )
    profile = CapabilityProfile(
        "NTFS",
        100,
        True,
        False,
        32_767,
        True,
        True,
    )
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
        operations=operations,
        assignment=Assignment("identity", "1", ()),
        preservation=PreservationPolicy(),
        filter_snapshot=FilterSet(),
        deletion_policy=DeletionPolicy.TRASH,
        trash_on_update=True,
        policy_fingerprint="a" * 64,
        required_volumes=frozenset(),
        required_bytes=12,
        fingerprint=PlanFingerprint("0" * 64),
    )
    return replace(placeholder, fingerprint=plan_fingerprint(placeholder))


def _evidence(
    operation: PlanOperation,
    *,
    recorded: bool = True,
    location_id: str = "9",
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
            location_id=location_id,
            scope_token=str(RUN_ID),
            rel_path_key=normalize_relative_path(operation.target_rel_path),
        )
        if recorded
        else None
    )
    return PublishedCopyEvidence(attestation, identity)


def _execution_set() -> ExecutionSet:
    plan = _plan()
    directory, first, second = plan.operations
    selection = frozenset(operation.op_id for operation in plan.operations)
    return ExecutionSet(
        plan=plan,
        selection=selection,
        run_id=RUN_ID,
        status={
            directory.op_id: Outcome.FAILED,
            first.op_id: Outcome.SUCCEEDED,
            second.op_id: Outcome.SUCCEEDED,
        },
        commitment=Commitment(
            plan.fingerprint,
            selection_digest(selection),
            NOW,
        ),
        published_evidence={first.op_id: _evidence(first)},
        recording_reasons={
            directory.op_id: ItemRecordingReason.UNRECORDED_MUTATION
        },
        recording_issues=(
            TaskRecordingIssue(
                TaskRecordingIssueReason.FINAL_FLUSH_FAILED,
                "flush failed",
            ),
        ),
        omitted_detail_count=2,
        bytes_done_high_water=12,
    )


def _candidate(
    operation: PlanOperation,
    evidence: PublishedCopyEvidence,
) -> PostCopyCandidate:
    identity = evidence.recorded_identity
    assert identity is not None
    return PostCopyCandidate(
        item_id=str(operation.op_id),
        root=Path(r"D:\target"),
        display_path=operation.target_rel_path,
        expected_stat=evidence.attestation.subject,
        copy_attestation=evidence.attestation,
        recorded_identity=PostCopyRecordIdentity(
            identity.row_id,
            identity.location_id,
            identity.scope_token,
            identity.rel_path_key,
        ),
    )


def _request(phase: str) -> ExecutionRequest:
    execution_set = _execution_set()
    if phase == "execute":
        continuation = ExecuteContinuation(
            execution_set,
            verify_after_execute=True,
            reported_exclusion_count=2,
        )
    else:
        _directory, first, second = execution_set.plan.operations
        evidence = execution_set.published_evidence[first.op_id]
        continuation = VerifyContinuation(
            execution_set=execution_set,
            candidates=PostCopySelection(
                (_candidate(first, evidence),),
                {str(first.op_id): first.content_bytes},
                first.content_bytes,
            ),
            filesystem_status=SessionState.FAILED,
            recording=RecordingStatus.DEGRADED,
            execute_phase=PhaseResult(
                "execute",
                PhaseStatus.FAILED,
                3,
                3,
                12,
                12,
                "one operation failed",
            ),
            missing_evidence_ids=(str(second.op_id),),
        )
    return ExecutionRequest(continuation, NOW)


def test_execution_request_preserves_execution_set_keyword() -> None:
    execution_set = _execution_set()

    request = ExecutionRequest(execution_set=execution_set, started_at=NOW)

    assert type(request.continuation) is ExecuteContinuation
    assert request.execution_set is execution_set
    assert request.started_at == NOW


@pytest.mark.parametrize(
    "started_at",
    (
        datetime(2026, 7, 19, 12, 30),
        datetime(
            2026,
            7,
            19,
            12,
            30,
            tzinfo=timezone(timedelta(hours=1)),
        ),
    ),
)
def test_execution_request_requires_utc_start(
    started_at: datetime,
) -> None:
    with pytest.raises(ValueError, match="timezone-aware|UTC"):
        ExecutionRequest(_execution_set(), started_at)


@pytest.mark.parametrize(
    ("value", "error"),
    (
        (True, TypeError),
        (-1, ValueError),
        (MAX_SAFE_INTEGER + 1, ValueError),
    ),
)
def test_execute_continuation_rejects_invalid_reported_exclusion_count(
    value: object,
    error: type[Exception],
) -> None:
    continuation = _request("execute").continuation
    assert type(continuation) is ExecuteContinuation

    with pytest.raises(error, match="reported exclusion count"):
        replace(continuation, reported_exclusion_count=value)


class _TextSubtype(str):
    pass


class _BytesSubtype(bytes):
    pass


class _DatetimeSubtype(datetime):
    pass


@pytest.mark.parametrize(
    ("field_name", "replacement", "message"),
    (
        ("algorithm", _TextSubtype("xxh3_128"), "algorithm"),
        ("digest", _BytesSubtype(b"\x02" * 16), "digest"),
        (
            "observed_at",
            _DatetimeSubtype(2026, 7, 19, 12, 30, tzinfo=timezone.utc),
            "time",
        ),
    ),
)
def test_execution_validation_requires_exact_evidence_shape(
    field_name: str,
    replacement: object,
    message: str,
) -> None:
    execution_set = _execution_set()
    first = execution_set.plan.operations[1]
    evidence = execution_set.published_evidence[first.op_id]
    content = replace(
        evidence.attestation.content,
        **{field_name: replacement},
    )
    execution_set.published_evidence[first.op_id] = replace(
        evidence,
        attestation=replace(evidence.attestation, content=content),
    )

    with pytest.raises(TypeError, match=message):
        validate_execution_set(execution_set)


@pytest.mark.parametrize(
    ("contradiction", "message"),
    (
        ("status", "successful operation status"),
        ("content-size", "reviewed content bytes"),
        ("scope", "scope token does not match"),
        ("path", "relative path key does not match"),
        ("location", "share one target location"),
        ("recording", "cannot carry a recorded identity"),
        ("identityless", "requires that operation's record-write-failed"),
        ("non-byte", "non-byte-producing"),
    ),
)
def test_execution_validation_rejects_mutable_overlay_contradictions(
    contradiction: str,
    message: str,
) -> None:
    execution_set = _execution_set()
    directory, first, second = execution_set.plan.operations
    evidence = execution_set.published_evidence[first.op_id]
    identity = evidence.recorded_identity
    assert identity is not None

    if contradiction == "status":
        execution_set.status[first.op_id] = Outcome.FAILED
    elif contradiction == "content-size":
        changed_size = first.content_bytes + 1
        execution_set.published_evidence[first.op_id] = PublishedCopyEvidence(
            Attestation(
                replace(evidence.attestation.content, size=changed_size),
                replace(evidence.attestation.subject, size=changed_size),
            ),
            identity,
        )
    elif contradiction == "scope":
        execution_set.published_evidence[first.op_id] = replace(
            evidence,
            recorded_identity=replace(identity, scope_token="b" * 32),
        )
    elif contradiction == "path":
        execution_set.published_evidence[first.op_id] = replace(
            evidence,
            recorded_identity=replace(identity, rel_path_key="OTHER.BIN"),
        )
    elif contradiction == "location":
        execution_set.published_evidence[second.op_id] = _evidence(
            second,
            location_id="10",
        )
    elif contradiction == "recording":
        execution_set.recording_reasons[first.op_id] = (
            ItemRecordingReason.RECORD_WRITE_FAILED
        )
    elif contradiction == "identityless":
        execution_set.published_evidence[first.op_id] = replace(
            evidence,
            recorded_identity=None,
        )
    else:
        execution_set.published_evidence[directory.op_id] = (
            execution_set.published_evidence.pop(first.op_id)
        )

    with pytest.raises(ValueError, match=message):
        validate_execution_set(execution_set)


def test_execution_validation_accepts_attributed_identityless_evidence() -> None:
    execution_set = _execution_set()
    first = execution_set.plan.operations[1]
    execution_set.published_evidence[first.op_id] = _evidence(
        first,
        recorded=False,
    )
    execution_set.recording_reasons[first.op_id] = (
        ItemRecordingReason.RECORD_WRITE_FAILED
    )

    validate_execution_set(execution_set)

    assert execution_set.recording is RecordingStatus.DEGRADED
    assert execution_set.published_evidence[first.op_id].recorded_identity is None


def test_execution_byte_high_water_is_bounded_and_monotonic() -> None:
    execution_set = replace(_execution_set(), bytes_done_high_water=4)

    execution_set.note_bytes_done(6)
    execution_set.note_bytes_done(6)

    assert execution_set.bytes_done_high_water == 6
    with pytest.raises(ValueError, match="cannot regress"):
        execution_set.note_bytes_done(5)
    with pytest.raises(ValueError, match="exceeds selected content"):
        execution_set.note_bytes_done(13)
    with pytest.raises(TypeError, match="non-Boolean integer"):
        execution_set.note_bytes_done(True)
    assert execution_set.bytes_done_high_water == 6


@pytest.mark.parametrize(
    ("high_water", "error", "message"),
    (
        (True, TypeError, "non-Boolean integer"),
        (-1, ValueError, "nonnegative signed-64 domain"),
        (13, ValueError, "exceeds selected content"),
    ),
)
def test_execution_set_rejects_invalid_initial_high_water(
    high_water: object,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=message):
        replace(_execution_set(), bytes_done_high_water=high_water)


def test_task_recording_issues_keep_order_and_omit_overlimit_detail() -> None:
    execution_set = _execution_set()
    overlimit = "é" * 513

    execution_set.note_task_recording_issue(
        TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
        "open failed",
    )
    execution_set.note_task_recording_issue(
        TaskRecordingIssueReason.FINAL_FLUSH_FAILED,
        "duplicate must not replace the first observation",
    )
    execution_set.note_task_recording_issue(
        TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
        overlimit,
    )

    assert execution_set.recording_issues == (
        TaskRecordingIssue(
            TaskRecordingIssueReason.FINAL_FLUSH_FAILED,
            "flush failed",
        ),
        TaskRecordingIssue(
            TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
            "open failed",
        ),
        TaskRecordingIssue(
            TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
            None,
        ),
    )
    assert execution_set.omitted_detail_count == 3
    with pytest.raises(ValueError, match="detail exceeds"):
        TaskRecordingIssue(
            TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
            overlimit,
        )


@pytest.mark.parametrize(
    ("contradiction", "message"),
    (
        ("recording", "cannot recover degraded"),
        ("filesystem", "disagrees"),
        ("canceled", "terminal"),
        ("missing", "equal successful publishes"),
        ("overlap", "disjoint"),
        ("root", "root differs"),
        ("path", "path differs"),
        ("evidence", "differs from its published evidence"),
        ("identity", "recording identity is contradictory"),
    ),
)
def test_verify_continuation_rejects_truth_candidate_and_evidence_drift(
    contradiction: str,
    message: str,
) -> None:
    continuation = _request("verify").continuation
    assert type(continuation) is VerifyContinuation
    candidate = continuation.candidates.candidates[0]

    if contradiction == "recording":
        changes = {"recording": RecordingStatus.OK}
    elif contradiction == "filesystem":
        changes = {"filesystem_status": SessionState.COMPLETED}
    elif contradiction == "canceled":
        changes = {
            "filesystem_status": SessionState.CANCELED,
            "execute_phase": replace(
                continuation.execute_phase,
                status=PhaseStatus.CANCELED,
            ),
        }
    elif contradiction == "missing":
        changes = {"missing_evidence_ids": ()}
    elif contradiction == "overlap":
        changes = {
            "missing_evidence_ids": (
                candidate.item_id,
                *continuation.missing_evidence_ids,
            )
        }
    else:
        if contradiction == "root":
            changed_candidate = replace(candidate, root=Path(r"E:\redirected"))
        elif contradiction == "path":
            identity = candidate.recorded_identity
            assert identity is not None
            changed_candidate = replace(
                candidate,
                display_path="other.bin",
                recorded_identity=replace(
                    identity,
                    rel_path_key=normalize_relative_path("other.bin"),
                ),
            )
        elif contradiction == "evidence":
            changed_candidate = replace(
                candidate,
                copy_attestation=replace(
                    candidate.copy_attestation,
                    content=replace(
                        candidate.copy_attestation.content,
                        digest=b"\xff" * 16,
                    ),
                ),
            )
        else:
            changed_candidate = replace(candidate, recorded_identity=None)
        changes = {
            "candidates": PostCopySelection(
                (changed_candidate,),
                dict(continuation.candidates.completed_bytes),
                continuation.candidates.processed_bytes,
            )
        }

    with pytest.raises(ValueError, match=message):
        replace(continuation, **changes)


def test_verify_continuation_rejects_candidates_out_of_plan_order() -> None:
    continuation = _request("verify").continuation
    assert type(continuation) is VerifyContinuation
    _directory, first, second = continuation.execution_set.plan.operations
    second_evidence = _evidence(second)
    continuation.execution_set.published_evidence[second.op_id] = second_evidence
    first_candidate = continuation.candidates.candidates[0]
    second_candidate = _candidate(second, second_evidence)

    with pytest.raises(ValueError, match="retain plan order"):
        replace(
            continuation,
            candidates=PostCopySelection(
                (second_candidate, first_candidate),
                {
                    second_candidate.item_id: second.content_bytes,
                    first_candidate.item_id: first.content_bytes,
                },
                first.content_bytes + second.content_bytes,
            ),
            missing_evidence_ids=(),
        )


def test_verify_continuation_detaches_and_revalidates_execute_phase() -> None:
    class HiddenPhase(PhaseResult):
        pass

    continuation = _request("verify").continuation
    assert type(continuation) is VerifyContinuation
    phase = continuation.execute_phase
    source = HiddenPhase(
        phase.phase,
        phase.status,
        phase.items_done,
        phase.items_total,
        phase.bytes_done,
        phase.bytes_total,
        phase.error,
    )
    object.__setattr__(source, "hidden_graph", ["hidden"])

    admitted = replace(continuation, execute_phase=source)
    object.__setattr__(source, "items_done", -1)
    object.__setattr__(source, "error", "x" * 1025)

    assert type(admitted.execute_phase) is PhaseResult
    assert admitted.execute_phase == phase
    assert admitted.execute_phase is not source
    assert not hasattr(admitted.execute_phase, "hidden_graph")
    with pytest.raises(ValueError, match="execute phase error"):
        replace(
            continuation,
            execute_phase=replace(phase, error="x" * 1025),
        )

    object.__setattr__(admitted.execute_phase, "items_done", -1)
    with pytest.raises(ValueError, match="items_done"):
        ExecutionCheckpoint(ExecutionRequest(admitted, NOW))


@pytest.mark.parametrize("text", ("\ud800", "\udcff", "\ud83d\ude00"))
def test_root_contract_rejects_surrogate_code_units(text: str) -> None:
    root = _plan().source_root

    with pytest.raises(ValueError, match="valid Unicode"):
        replace(root, root_id="source_" + text)


@pytest.mark.parametrize("phase", ("execute", "verify"))
def test_execution_checkpoint_detaches_and_reopens_independent_state(
    phase: str,
) -> None:
    request = _request(phase)
    source = request.execution_set
    source_continuation = request.continuation
    checkpoint = ExecutionCheckpoint(request)
    expected = checkpoint.materialize()

    source.status.clear()
    source.recording_reasons.clear()
    source.published_evidence.clear()
    source.recording_issues = ()
    source.omitted_detail_count = 0
    source.bytes_done_high_water = 0
    if type(source_continuation) is VerifyContinuation:
        source_continuation.candidates._completed_bytes.clear()
        source_continuation.candidates._processed_bytes = 0

    first = checkpoint.materialize()
    second = checkpoint.materialize()

    assert first == expected
    assert second == expected
    assert first.execution_set is not second.execution_set
    assert first.execution_set.status is not second.execution_set.status
    assert first.execution_set.status is not source.status
    assert first.execution_set.recording_reasons is not source.recording_reasons
    assert first.execution_set.published_evidence is not source.published_evidence
    assert first.execution_set.status == {
        first.execution_set.plan.operations[0].op_id: Outcome.FAILED,
        first.execution_set.plan.operations[1].op_id: Outcome.SUCCEEDED,
        first.execution_set.plan.operations[2].op_id: Outcome.SUCCEEDED,
    }
    assert len(first.execution_set.published_evidence) == 1
    assert first.execution_set.recording is RecordingStatus.DEGRADED
    assert first.execution_set.recording_issues == (
        TaskRecordingIssue(
            TaskRecordingIssueReason.FINAL_FLUSH_FAILED,
            "flush failed",
        ),
    )
    assert first.execution_set.omitted_detail_count == 2
    assert first.execution_set.bytes_done_high_water == 12
    assert first.started_at == NOW
    assert first.continuation.phase == phase

    if type(first.continuation) is ExecuteContinuation:
        assert first.continuation.verify_after_execute
        assert first.continuation.reported_exclusion_count == 2
    else:
        assert type(second.continuation) is VerifyContinuation
        assert first.continuation.candidates is not second.continuation.candidates
        assert (
            first.continuation.candidates._completed_bytes
            is not second.continuation.candidates._completed_bytes
        )
        assert first.continuation.candidates.completed_bytes == {
            str(first.execution_set.plan.operations[1].op_id): 5
        }
        assert first.continuation.candidates.processed_bytes == 5
        assert first.continuation.filesystem_status is SessionState.FAILED
        assert first.continuation.recording is RecordingStatus.DEGRADED
        assert first.continuation.execute_phase == PhaseResult(
            "execute",
            PhaseStatus.FAILED,
            3,
            3,
            12,
            12,
            "one operation failed",
        )
        assert first.continuation.missing_evidence_ids == (
            str(first.execution_set.plan.operations[2].op_id),
        )

    first.execution_set.status.clear()
    first.execution_set.recording_reasons.clear()
    first.execution_set.published_evidence.clear()
    first.execution_set.recording_issues = ()
    first.execution_set.omitted_detail_count = 0
    first.execution_set.bytes_done_high_water = 0
    if type(first.continuation) is VerifyContinuation:
        first.continuation.candidates._completed_bytes.clear()
        first.continuation.candidates._processed_bytes = 0

    assert second == expected
    assert checkpoint.materialize() == expected
