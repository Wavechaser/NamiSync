"""Exact manual verification of current evidence from one retained execution."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.events import PhaseChanged
from namisync.core.exception_graph import retired_failure_detail
from namisync.core.execution import TaskRecordingIssue, TaskRecordingIssueReason
from namisync.core.integrity import (
    INTEGRITY_CANDIDATE_ROW_LIMIT, IntegrityCandidateLimitError,
    IntegrityCandidateLimitExceeded, IntegrityOutcome, PostCopyCandidate,
    PostCopyRecordIdentity, PostCopySelection, PostCopySelectionAuthority,
    bind_verifier_context, snapshot_integrity_outcome,
    snapshot_post_copy_selection_authority, validate_integrity_run_result,
)
from namisync.core.pathing import normalize_relative_path
from namisync.core.root_authority import RootAuthority
from namisync.core.scalars import MAX_REQUEST_ID_UTF8_BYTES, require_utf8_text
from namisync.core.session import (
    Canceled, Disposition, OperationResult, PauseRequested, RunContext, SessionState,
)
from namisync.db.repositories import ExecutionEvidenceKey, InventorySnapshot, LedgerRepository
from namisync.modules.verifier import verify_post_copy

from .execution_review import RetainedExecutionReview, _coherent_state, _is_matching_receipt
from .inventory import (
    IntegrityDependencies, LocationBinding, VolumeResolutionRequired, VolumeResolutionState,
    _integrity_recorder, _integrity_recording_truth, resolve_binding,
)
from .models import ExecutionEvidenceState, ExecutionEvidenceSubject, RetainedExecutionBinding
from .sync import _validate_post_copy_verifier_completion


@dataclass(frozen=True, slots=True)
class ManualVerificationRequest:
    request_id: str
    execution: RetainedExecutionBinding

    def __post_init__(self) -> None:
        if type(self.request_id) is not str or not self.request_id:
            raise ValueError("manual verification request identity is required")
        require_utf8_text(self.request_id, "manual verification request id", maximum_bytes=MAX_REQUEST_ID_UTF8_BYTES)
        if type(self.execution) is not RetainedExecutionBinding:
            raise TypeError("manual verification requires an exact execution binding")


@dataclass(frozen=True, slots=True)
class ManualVerificationReadiness:
    reason: str
    applicable_count: int
    ready_count: int = 0
    already_verified_count: int = 0


@dataclass(frozen=True, slots=True)
class ManualVerificationHandoff:
    readiness: ManualVerificationReadiness
    location_id: int | None = None
    rows: tuple[tuple[str, InventorySnapshot], ...] = ()


class ManualVerificationUnavailable(ValueError):
    def __init__(self, readiness: ManualVerificationReadiness) -> None:
        self.readiness = readiness
        super().__init__(f"Exact post-copy verification is unavailable: {readiness.reason}")


def classify_manual_verification(
    repository: LedgerRepository, review: RetainedExecutionReview,
) -> ManualVerificationHandoff:
    """Include absent selected outcomes in the complete handoff decision."""
    applicable = review.applicable_operations
    count = len(applicable)
    if count > INTEGRITY_CANDIDATE_ROW_LIMIT:
        raise IntegrityCandidateLimitError(IntegrityCandidateLimitExceeded.rows())

    def unavailable(reason: str) -> ManualVerificationHandoff:
        return ManualVerificationHandoff(ManualVerificationReadiness(reason, count))

    if not applicable:
        return unavailable("empty")
    if any(issue.reason is TaskRecordingIssueReason.POST_SETTLEMENT_STATE_DIVERGED
           for issue in review.result.recording_issues):
        return unavailable("settlement-diverged")
    if (review.result.canceled or review.result.disposition is Disposition.UNRUN
            or review.result.status in {SessionState.REFUSED, SessionState.INTERRUPTED, SessionState.CANCELED}):
        return unavailable("execution-ineligible")
    for operation in applicable:
        item = review.operation_items.get(str(operation.op_id))
        if item is None or item.outcome is not Outcome.SUCCEEDED:
            return unavailable("incomplete")
    snapshot = repository.read_manual_verification_evidence(
        review.binding.run_id,
        tuple(ExecutionEvidenceKey(str(operation.op_id), normalize_relative_path(operation.target_rel_path))
              for operation in applicable),
    )
    receipts = {item.operation_token: item for item in snapshot.receipts}
    inventory = {row.rel_path_key: row for row in snapshot.inventory}
    ready = []
    verified = 0
    for operation in applicable:
        item_id = str(operation.op_id)
        key = normalize_relative_path(operation.target_rel_path)
        if not _is_matching_receipt(receipts.get(item_id), operation.kind, key):
            return unavailable("unrecorded")
        row = inventory.get(key)
        state, _content = _coherent_state(snapshot, review.binding.run_id,
            ExecutionEvidenceSubject(review.operation_items[item_id], review.target_owner_unique[item_id]), row)
        if state is ExecutionEvidenceState.RECORDED_COPY:
            assert row is not None
            ready.append((item_id, row))
        elif state is ExecutionEvidenceState.ALREADY_VERIFIED:
            verified += 1
        else:
            return unavailable("superseded")
    assert snapshot.run is not None
    return ManualVerificationHandoff(
        ManualVerificationReadiness("ready" if ready else "already-verified", count, len(ready), verified),
        snapshot.run.target_location_id, tuple(ready),
    )


@dataclass(frozen=True, slots=True)
class ManualVerificationCheckpoint:
    request: ManualVerificationRequest
    binding: LocationBinding
    selection: PostCopySelectionAuthority
    recording: RecordingStatus = RecordingStatus.OK
    recording_issues: tuple[TaskRecordingIssue, ...] = ()
    omitted_detail_count: int = 0


def freeze_manual_verification(
    request: ManualVerificationRequest, binding: LocationBinding,
    handoff: ManualVerificationHandoff, root: str,
) -> ManualVerificationCheckpoint:
    if handoff.readiness.reason != "ready" or handoff.location_id != binding.location_id:
        raise ManualVerificationUnavailable(handoff.readiness)
    candidates = []
    for item_id, row in handoff.rows:
        assert row.observed is not None and row.attestation is not None
        candidates.append(PostCopyCandidate(item_id, Path(root), row.rel_path,
            row.observed, row.attestation, PostCopyRecordIdentity(
                row.row_id, str(row.location_id), row.scope_token, row.rel_path_key)))
    return ManualVerificationCheckpoint(request, binding,
        snapshot_post_copy_selection_authority(PostCopySelection(tuple(candidates))))


class ManualVerificationInvocation:
    def __init__(self, request: ManualVerificationCheckpoint, deps: IntegrityDependencies,
                 runner=verify_post_copy) -> None:
        self.request = request
        self.deps = deps
        self.runner = runner
        authority = request.selection
        self.selection = PostCopySelection(authority.candidates,
            dict(authority.completed_bytes), authority.processed_bytes)
        self.recording = request.recording
        self.issues = request.recording_issues
        self.omitted = request.omitted_detail_count

    def snapshot(self) -> ManualVerificationCheckpoint:
        return replace(self.request, selection=snapshot_post_copy_selection_authority(self.selection),
            recording=self.recording, recording_issues=self.issues, omitted_detail_count=self.omitted)

    def run(self, ctx: RunContext) -> OperationResult:
        outcomes = []
        authority = snapshot_post_copy_selection_authority(self.selection)
        pending = {item.item_id: item for item in authority.candidates
                   if item.item_id not in authority.completed_bytes}
        observation = [None]
        status, error, canceled = SessionState.COMPLETED, None, False

        def emit(body: object) -> None:
            if not isinstance(body, IntegrityOutcome):
                ctx.emit(body)
                return
            candidate = pending.get(body.item_id)
            if candidate is None:
                raise ValueError("manual verifier emitted a duplicate or unknown outcome")
            identity = candidate.recorded_identity
            assert identity is not None
            if (body.path, body.phase, body.row_id, body.location_id) != (
                    candidate.display_path, "verify", identity.row_id, identity.location_id):
                raise ValueError("manual verifier changed outcome identity")
            outcome = snapshot_integrity_outcome(body, item_id=candidate.item_id,
                row_id=identity.row_id, location_id=identity.location_id,
                path=candidate.display_path, phase="verify")
            ctx.emit(replace(outcome))
            outcomes.append(outcome)
            pending.pop(body.item_id)
            if outcome.recording is RecordingStatus.DEGRADED:
                self.recording = RecordingStatus.DEGRADED

        try:
            resolution = resolve_binding(self.request.binding, self.deps.resolver)
            if resolution.state is not VolumeResolutionState.RESOLVED:
                raise VolumeResolutionRequired(resolution)
            root = resolution.root_path
            assert root is not None and resolution.selected_mount is not None
            if any(candidate.root != Path(root) for candidate in self.selection.candidates):
                raise ValueError("manual verification target mount changed")
            owned_run = RunContext(emit, ctx.checkpoint)
            context = bind_verifier_context(self.deps.verifier_context(owned_run), owned_run,
                root_authority=RootAuthority(root, resolution.selected_mount,
                    expected_volume_id=resolution.binding.volume_id))
            with _integrity_recorder(self.deps, root, recorder_observation=observation) as recorder:
                ctx.emit(PhaseChanged("verify"))
                try:
                    result = self.runner(self.selection, context, recorder)
                except BaseException:
                    _validate_post_copy_verifier_completion(self.selection, authority, pending, complete=False)
                    raise
                validate_integrity_run_result(result, outcomes)
                _validate_post_copy_verifier_completion(self.selection, authority, pending, complete=True)
        except PauseRequested:
            self.recording, self.issues, self.omitted = _integrity_recording_truth(
                self.request, self.recording, observation[0])
            raise
        except Canceled:
            status, canceled = SessionState.CANCELED, True
        except Exception as failure:
            status, error = SessionState.FAILED, retired_failure_detail(failure)
        self.recording, self.issues, self.omitted = _integrity_recording_truth(
            self.request, self.recording, observation[0])
        return OperationResult(status, disposition=Disposition.RAN,
            recording=self.recording, items=tuple(outcomes), canceled=canceled, error=error,
            bytes_done=self.selection.processed_bytes, bytes_total=self.selection.physical_bytes_total(),
            recording_issues=self.issues, omitted_detail_count=self.omitted)


def settle_canceled_manual_verification(
    checkpoint: ManualVerificationCheckpoint, disposition: Disposition,
) -> OperationResult:
    if disposition is not Disposition.RAN:
        raise ValueError("started manual verification cancellation must retain RAN disposition")
    selection = PostCopySelection(checkpoint.selection.candidates,
        dict(checkpoint.selection.completed_bytes), checkpoint.selection.processed_bytes)
    return OperationResult(SessionState.CANCELED, disposition=disposition, canceled=True,
        recording=checkpoint.recording, bytes_done=selection.processed_bytes,
        bytes_total=selection.physical_bytes_total(), recording_issues=checkpoint.recording_issues,
        omitted_detail_count=checkpoint.omitted_detail_count)
