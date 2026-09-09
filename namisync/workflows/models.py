"""Typed workflow requests and interface-facing read models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar, Mapping, TypeAlias

from namisync.core.execution import (
    ExecutionSet,
    ExecutionSetAuthority,
    snapshot_execution_set_authority,
    validate_execution_set,
)
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.integrity import (
    PostCopySelection,
    PostCopySelectionAuthority,
    snapshot_post_copy_selection_authority,
)
from namisync.core.models import ScanResult
from namisync.core.planning import OperationKind, Plan, SyncOptions
from namisync.core.preflight import Verdict
from namisync.core.scalars import bounded_utf8_text, require_safe_int
from namisync.core.session import PhaseResult, PhaseStatus, SessionState
from namisync.workflows.views import (
    PhaseResultView,
    RecordingIssueView,
    ReviewFactLimitView,
    ResultItemView,
    SemanticSettingsView,
)


@dataclass(frozen=True, slots=True)
class PlanRequest:
    request_id: str
    source_path: str
    target_path: str
    options: SyncOptions = SyncOptions()


@dataclass(frozen=True, slots=True)
class ExecuteContinuation:
    """Execution-phase continuation retained by the workflow checkpoint."""

    phase: ClassVar[str] = "execute"

    execution_set: ExecutionSet
    verify_after_execute: bool = False
    reported_exclusion_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.execution_set, ExecutionSet):
            raise TypeError("execute continuation requires an ExecutionSet")
        if not isinstance(self.verify_after_execute, bool):
            raise TypeError("verify_after_execute must be a bool")
        require_safe_int(
            self.reported_exclusion_count,
            "reported exclusion count",
        )


@dataclass(frozen=True, slots=True)
class VerifyContinuation:
    """Verification-phase continuation with frozen handoff and phase truth."""

    phase: ClassVar[str] = "verify"

    execution_set: ExecutionSet
    candidates: PostCopySelection
    filesystem_status: SessionState
    recording: RecordingStatus
    execute_phase: PhaseResult
    missing_evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.execution_set, ExecutionSet):
            raise TypeError("verify continuation requires an ExecutionSet")
        if not isinstance(self.candidates, PostCopySelection):
            raise TypeError("verify continuation requires a PostCopySelection")
        if not isinstance(self.filesystem_status, SessionState):
            raise TypeError("verify filesystem status has the wrong type")
        if not isinstance(self.recording, RecordingStatus):
            raise TypeError("verify recording status has the wrong type")
        source_phase = self.execute_phase
        if not isinstance(source_phase, PhaseResult):
            raise TypeError("verify continuation requires an execute PhaseResult")
        phase_name = source_phase.phase
        if type(phase_name) is not str:
            raise TypeError("verify continuation execute phase name must be text")
        execute_phase = PhaseResult(
            phase=phase_name,
            status=source_phase.status,
            items_done=source_phase.items_done,
            items_total=source_phase.items_total,
            bytes_done=source_phase.bytes_done,
            bytes_total=source_phase.bytes_total,
            error=source_phase.error,
        )
        if execute_phase.phase != ExecuteContinuation.phase:
            raise ValueError("verify continuation phase result must describe execute")
        execute_error = execute_phase.error
        bounded_error = bounded_utf8_text(
            execute_error,
            "verify continuation execute phase error",
        )
        if execute_error is not None and bounded_error is None:
            raise ValueError(
                "verify continuation execute phase error exceeds its bound"
            )
        if self.filesystem_status is SessionState.CANCELED:
            raise ValueError(
                "canceled execution is terminal and cannot continue to verify"
            )
        try:
            expected_phase_status = PhaseStatus(self.filesystem_status.value)
        except ValueError as error:
            raise ValueError(
                "verify continuation requires settled execute filesystem truth"
            ) from error
        if execute_phase.status is not expected_phase_status:
            raise ValueError(
                "verify filesystem status disagrees with its execute phase"
            )
        if (
            self.execution_set.recording is RecordingStatus.DEGRADED
            and self.recording is RecordingStatus.OK
        ):
            raise ValueError(
                "compound recording cannot recover degraded execution recording"
            )
        if not isinstance(self.missing_evidence_ids, tuple):
            raise TypeError("missing evidence ids must be a tuple")
        if any(
            not isinstance(item_id, str) or not item_id
            for item_id in self.missing_evidence_ids
        ):
            raise ValueError("missing evidence ids must be non-empty strings")
        if len(self.missing_evidence_ids) != len(set(self.missing_evidence_ids)):
            raise ValueError("missing evidence ids must be unique")

        byte_kinds = {
            OperationKind.COPY,
            OperationKind.UPDATE,
            OperationKind.MOVE_UPDATE,
        }
        successful_ids = tuple(
            str(operation.op_id)
            for operation in self.execution_set.plan.operations
            if operation.op_id in self.execution_set.selection
            and operation.kind in byte_kinds
            and self.execution_set.status.get(operation.op_id) is Outcome.SUCCEEDED
        )
        candidate_ids = tuple(
            candidate.item_id for candidate in self.candidates.candidates
        )
        candidate_set = set(candidate_ids)
        missing_set = set(self.missing_evidence_ids)
        if candidate_set & missing_set:
            raise ValueError("candidate and missing evidence ids must be disjoint")
        if candidate_set | missing_set != set(successful_ids):
            raise ValueError(
                "candidate and missing evidence ids must equal successful publishes"
            )
        if candidate_ids != tuple(
            item_id for item_id in successful_ids if item_id in candidate_set
        ):
            raise ValueError("post-copy candidates must retain plan order")
        if self.missing_evidence_ids != tuple(
            item_id for item_id in successful_ids if item_id in missing_set
        ):
            raise ValueError("missing evidence ids must retain plan order")

        evidence_by_id = {
            str(op_id): evidence
            for op_id, evidence in self.execution_set.published_evidence.items()
        }
        if set(evidence_by_id) != candidate_set:
            raise ValueError(
                "post-copy candidates must exactly match published evidence"
            )
        operations = {
            str(operation.op_id): operation
            for operation in self.execution_set.plan.operations
        }
        target_root = Path(self.execution_set.plan.target_root.path)
        for candidate in self.candidates.candidates:
            operation = operations[candidate.item_id]
            evidence = evidence_by_id[candidate.item_id]
            if candidate.root != target_root:
                raise ValueError("post-copy candidate root differs from the plan")
            if candidate.display_path != operation.target_rel_path:
                raise ValueError("post-copy candidate path differs from the plan")
            if (
                candidate.expected_stat != evidence.attestation.subject
                or candidate.copy_attestation != evidence.attestation
            ):
                raise ValueError(
                    "post-copy candidate differs from its published evidence"
                )
            published_identity = evidence.recorded_identity
            candidate_identity = candidate.recorded_identity
            if (published_identity is None) != (candidate_identity is None):
                raise ValueError(
                    "post-copy candidate recording identity is contradictory"
                )
            if published_identity is not None and candidate_identity is not None:
                if (
                    published_identity.row_id,
                    published_identity.location_id,
                    published_identity.scope_token,
                    published_identity.rel_path_key,
                ) != (
                    candidate_identity.row_id,
                    candidate_identity.location_id,
                    candidate_identity.scope_token,
                    candidate_identity.rel_path_key,
                ):
                    raise ValueError(
                        "post-copy candidate recording identity changed at handoff"
                    )
        object.__setattr__(self, "execute_phase", execute_phase)


def _exact_verify_continuation(
    value: VerifyContinuation,
) -> VerifyContinuation:
    if not isinstance(value, VerifyContinuation):
        raise TypeError("verify continuation has the wrong type")
    return VerifyContinuation(
        execution_set=value.execution_set,
        candidates=value.candidates,
        filesystem_status=value.filesystem_status,
        recording=value.recording,
        execute_phase=value.execute_phase,
        missing_evidence_ids=value.missing_evidence_ids,
    )


ExecutionContinuation: TypeAlias = ExecuteContinuation | VerifyContinuation


@dataclass(frozen=True, slots=True, init=False)
class ExecutionRequest:
    """Initial or resumed execution request with a stable facade projection."""

    continuation: ExecutionContinuation
    started_at: datetime | None = None

    def __init__(
        self,
        continuation: ExecutionContinuation | ExecutionSet | None = None,
        started_at: datetime | None = None,
        *,
        execution_set: ExecutionSet | None = None,
    ) -> None:
        if continuation is not None and execution_set is not None:
            raise TypeError(
                "execution request accepts either continuation or execution_set"
            )
        if execution_set is not None:
            continuation = execution_set
        value = (
            ExecuteContinuation(continuation)
            if isinstance(continuation, ExecutionSet)
            else continuation
        )
        if not isinstance(value, (ExecuteContinuation, VerifyContinuation)):
            raise TypeError("execution request requires a typed continuation")
        if started_at is not None:
            if not isinstance(started_at, datetime):
                raise TypeError("execution start must be a datetime")
            if started_at.tzinfo is None or started_at.utcoffset() is None:
                raise ValueError("execution start must be timezone-aware")
            if started_at.utcoffset() != timezone.utc.utcoffset(started_at):
                raise ValueError("execution start must be UTC")
        object.__setattr__(self, "continuation", value)
        object.__setattr__(self, "started_at", started_at)

    @property
    def execution_set(self) -> ExecutionSet:
        return self.continuation.execution_set


@dataclass(frozen=True, slots=True)
class _ExecuteDelta:
    verify_after_execute: bool
    reported_exclusion_count: int


@dataclass(frozen=True, slots=True)
class _VerifyDelta:
    candidates: PostCopySelectionAuthority
    filesystem_status: SessionState
    recording: RecordingStatus
    execute_phase: PhaseResult
    missing_evidence_ids: tuple[str, ...]


_ExecutionDelta: TypeAlias = _ExecuteDelta | _VerifyDelta


@dataclass(frozen=True, slots=True, init=False)
class ExecutionCheckpoint:
    """Detached semantic state retained while an execution is not running."""

    _execution: ExecutionSetAuthority
    _started_at: datetime | None
    _delta: _ExecutionDelta

    def __init__(self, request: ExecutionRequest) -> None:
        if type(request) is not ExecutionRequest:
            raise TypeError(
                "execution checkpoint requires an exact ExecutionRequest"
            )
        continuation = request.continuation
        validate_execution_set(continuation.execution_set)
        if isinstance(continuation, VerifyContinuation):
            continuation = _exact_verify_continuation(continuation)
        execution = snapshot_execution_set_authority(
            continuation.execution_set
        )
        if isinstance(continuation, ExecuteContinuation):
            delta: _ExecutionDelta = _ExecuteDelta(
                continuation.verify_after_execute,
                continuation.reported_exclusion_count,
            )
        else:
            delta = _VerifyDelta(
                snapshot_post_copy_selection_authority(continuation.candidates),
                continuation.filesystem_status,
                continuation.recording,
                continuation.execute_phase,
                continuation.missing_evidence_ids,
            )
        object.__setattr__(self, "_execution", execution)
        object.__setattr__(self, "_started_at", request.started_at)
        object.__setattr__(self, "_delta", delta)

    def materialize(self) -> ExecutionRequest:
        """Create fresh mutable continuation state for one invocation."""

        retained = self._execution
        execution_set = ExecutionSet(
            plan=retained.plan,
            selection=retained.selection,
            run_id=retained.run_id,
            commitment=retained.commitment,
            user_deselected=retained.user_deselected,
            status=dict(retained.status),
            recording_reasons=dict(retained.recording_reasons),
            published_evidence=dict(retained.published_evidence),
            recording_issues=retained.recording_issues,
            omitted_detail_count=retained.omitted_detail_count,
            bytes_done_high_water=retained.bytes_done_high_water,
        )
        delta = self._delta
        if isinstance(delta, _ExecuteDelta):
            continuation: ExecutionContinuation = ExecuteContinuation(
                execution_set,
                verify_after_execute=delta.verify_after_execute,
                reported_exclusion_count=delta.reported_exclusion_count,
            )
        else:
            candidates = delta.candidates
            continuation = VerifyContinuation(
                execution_set=execution_set,
                candidates=PostCopySelection(
                    candidates.candidates,
                    dict(candidates.completed_bytes),
                    candidates.processed_bytes,
                ),
                filesystem_status=delta.filesystem_status,
                recording=delta.recording,
                execute_phase=delta.execute_phase,
                missing_evidence_ids=delta.missing_evidence_ids,
            )
        return ExecutionRequest(continuation, self._started_at)


@dataclass(frozen=True, slots=True)
class WorkflowPreparation:
    checkpoint: object
    resources: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class RefusalView:
    code: str
    path: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class PlanOperationView:
    operation_id: str
    kind: str
    source_path: str | None
    target_path: str
    prior_target_path: str | None
    reason: str
    blocked_reason: str | None
    selection_outcome: str | None
    selection_reason: str | None
    content_bytes: str


@dataclass(frozen=True, slots=True)
class PlanReview:
    request_id: str
    source_path: str
    target_path: str
    source_volume: str
    target_volume: str
    deletion_policy: str
    trash_on_update: bool
    semantic_settings: SemanticSettingsView
    fingerprint: str
    selection_digest_hex: str
    required_bytes: str
    free_bytes: str | None
    reclaimable_temp_bytes: str
    warnings: tuple[str, ...]
    refusals: tuple[RefusalView, ...]
    operations: tuple[PlanOperationView, ...]

    @property
    def can_commit(self) -> bool:
        return not self.refusals


@dataclass(frozen=True, slots=True)
class ExecutionDetails:
    run_id: str
    refusals: tuple[RefusalView, ...] = ()
    commitment_error: str | None = None


@dataclass(frozen=True, slots=True)
class HistoryRunSummaryView:
    run_token: str
    session_id: str
    activity_kind: str
    subject_kind: str | None
    subject_id: str | None
    source_context: str | None
    target_context: str | None
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    completion_status: str
    current_state: str
    current_phase: str | None
    last_committed_seq: int
    item_count: int
    duplicate_item_count: int
    rejected_event_count: int
    last_committed_at: datetime | None
    filesystem_status: str | None
    recording_status: str | None
    audit_status: str | None
    disposition: str | None
    canceled: bool | None
    integrity_status: str
    headline: str
    bytes_done: str | None
    bytes_total: str | None
    recording_degraded_items: int | None
    recording_issues: tuple[RecordingIssueView, ...]
    omitted_detail_count: int | None
    review_refusal: ReviewFactLimitView | None
    succeeded_count: int
    skipped_count: int
    failed_count: int
    canceled_count: int
    deferred_count: int
    blocked_count: int
    phases: tuple[PhaseResultView, ...]
    error: str | None


@dataclass(frozen=True, slots=True)
class HistoryItemView:
    item_order: int
    event_seq: int
    item: ResultItemView


@dataclass(frozen=True, slots=True)
class HistoryItemPageView:
    run_token: str
    through_order: int
    next_after_order: int
    has_more: bool
    items: tuple[HistoryItemView, ...]


@dataclass(frozen=True, slots=True)
class HistoryEventView:
    session_id: str
    sequence: int
    at: str
    schema_version: int
    body_type: str
    disposition: str
    body: Mapping[str, object] | None
    payload_hash: str
    receipt_hash: str
    duplicate_of_seq: int | None
    rejection_reason: str | None


@dataclass(frozen=True, slots=True)
class HistoryEventPageView:
    run_token: str
    through_seq: int
    next_after_seq: int
    has_more: bool
    events: tuple[HistoryEventView, ...]


@dataclass(frozen=True, slots=True)
class PlanArtifact:
    request: PlanRequest
    source_scan: ScanResult
    target_scan: ScanResult
    plan: Plan
    verdict: Verdict
