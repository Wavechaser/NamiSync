"""Top-to-bottom M0 reviewed sync workflows."""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from namisync.core.events import ItemOutcome, PhaseChanged
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.execution import (
    ExecutionSet,
    ExecutorFileSystem,
    PublishedCopyEvidence,
    Recorder,
    validated_run_id,
)
from namisync.core.integrity import (
    IntegrityOutcome,
    IntegrityRecorder,
    IntegrityRunResult,
    PostCopyCandidate,
    PostCopyRecordIdentity,
    PostCopySelection,
    VerifierContext,
)
from namisync.core.models import IgnoreSet, Root, ScanResult
from namisync.core.pathing import (
    from_extended_length_path,
    lexical_absolute_path,
    logical_error_text,
    to_extended_length_path,
)
from namisync.core.planning import (
    MappingSnapshot,
    OperationKind,
    Plan,
    PlanOperation,
    Scope,
    SyncOptions,
    plan_fingerprint,
    selection_digest,
)
from namisync.core.preflight import ObservedWorld, Verdict
from namisync.core.root_authority import (
    RootAuthority,
    RootAuthorityError,
    RootAuthorityIssue,
    admit_root_chain,
    current_volume_anchor,
)
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
)
from namisync.modules.executor import ExecutorPolicies
from namisync.modules.preflight import ObservationFileSystem

from .models import (
    ExecuteContinuation,
    ExecutionContinuation,
    ExecutionDetails,
    PlanArtifact,
    PlanRequest,
    RefusalView,
    VerifyContinuation,
)
from .selection import ExecutionSelection, derive_execution_selection


class CompoundRecorder(Recorder, IntegrityRecorder, Protocol):
    """One run-bound writer exposed through both narrow recorder protocols."""


class RunRecording(Protocol):
    recorder: CompoundRecorder

    def finish(
        self, status: SessionState, recording: RecordingStatus
    ) -> None: ...


Scanner = Callable[[Root, IgnoreSet, RunContext], ScanResult]
Planner = Callable[[ScanResult, ScanResult, MappingSnapshot, SyncOptions, Scope], Plan]
Observer = Callable[[ExecutionSet, ObservationFileSystem], ObservedWorld]
Preflight = Callable[[ExecutionSet, ObservedWorld], Verdict]
Executor = Callable[
    [
        ExecutionSet,
        RunContext,
        Recorder,
        ExecutorPolicies,
        ExecutorFileSystem,
    ],
    OperationResult,
]
PostCopyVerifier = Callable[
    [PostCopySelection, VerifierContext, IntegrityRecorder],
    IntegrityRunResult,
]


@dataclass(frozen=True, slots=True)
class SyncDependencies:
    scanner: Scanner
    planner: Planner
    correspondence: Callable[[ScanResult, ScanResult], MappingSnapshot]
    observation_fs: ObservationFileSystem
    observer: Observer
    preflight: Preflight
    executor: Executor
    executor_policies: ExecutorPolicies
    executor_fs: ExecutorFileSystem
    verifier: PostCopyVerifier
    verifier_context: Callable[[RunContext], VerifierContext]
    open_recording: Callable[[ExecutionSet], AbstractContextManager[RunRecording]]
    save_plan: Callable[[PlanArtifact], None]
    save_execution_details: Callable[[ExecutionDetails], None]
    finish_existing_recording: (
        Callable[[ExecutionSet, SessionState, RecordingStatus], None] | None
    ) = None
    ignores: IgnoreSet = IgnoreSet()


def run_plan(
    request: PlanRequest,
    ctx: RunContext,
    deps: SyncDependencies,
) -> OperationResult:
    """Scan, plan, observe, and preflight without persisting preview state."""

    run_id = validated_run_id(request.request_id)
    source_root, target_root = _validated_roots(
        request.source_path, request.target_path
    )

    ctx.emit(PhaseChanged("scan-source"))
    source_scan = deps.scanner(source_root, deps.ignores, ctx)
    ctx.emit(PhaseChanged("scan-target"))
    target_scan = deps.scanner(target_root, deps.ignores, ctx)

    ctx.emit(PhaseChanged("plan"))
    correspondence = deps.correspondence(source_scan, target_scan)
    plan = deps.planner(
        source_scan,
        target_scan,
        correspondence,
        request.options,
        Scope.everything(),
    )
    decision = derive_execution_selection(plan)
    preview = ExecutionSet(plan, decision.selection, run_id)

    ctx.emit(PhaseChanged("review-preflight"))
    world = deps.observer(preview, deps.observation_fs)
    verdict = deps.preflight(preview, world)
    deps.save_plan(
        PlanArtifact(request, source_scan, target_scan, plan, verdict)
    )
    return OperationResult(status=SessionState.COMPLETED)


def run_execution(
    continuation: ExecutionContinuation | ExecutionSet,
    ctx: RunContext,
    deps: SyncDependencies,
    *,
    continuation_sink: Callable[[ExecutionContinuation], None] | None = None,
    resumed: bool = False,
) -> OperationResult:
    """Execute and optionally verify under one logical sync-run recording."""

    current: ExecutionContinuation = (
        ExecuteContinuation(continuation)
        if isinstance(continuation, ExecutionSet)
        else continuation
    )
    if not isinstance(current, (ExecuteContinuation, VerifyContinuation)):
        raise TypeError("execution workflow requires a typed continuation")
    if not isinstance(resumed, bool):
        raise TypeError("resumed must be a bool")
    sink = continuation_sink or (lambda value: None)
    xset = current.execution_set
    try:
        try:
            decision = derive_execution_selection(
                xset.plan,
                user_deselected=xset.user_deselected,
            )
        except (TypeError, ValueError) as error:
            commitment_error = (
                "reviewed selection provenance is invalid: "
                f"{type(error).__name__}: {logical_error_text(error)}"
            )
            exclusion_items = ()
        else:
            commitment_error = (
                "carried selection does not match the authoritative derived selection"
                if decision.selection != xset.selection
                else _commitment_error(xset)
            )
            exclusion_items = _exclusion_items(xset.plan, decision)
    except Exception as error:
        if isinstance(current, VerifyContinuation):
            return _settle_verify_incomplete(
                current,
                deps,
                FailureDetail(
                    type(error).__name__, logical_error_text(error)
                ),
            )
        if resumed:
            return _settle_execute_resume_failure(
                current,
                ctx,
                deps,
                FailureDetail(
                    type(error).__name__, logical_error_text(error)
                ),
                (),
            )
        raise
    if commitment_error is not None:
        try:
            deps.save_execution_details(
                ExecutionDetails(
                    str(xset.run_id),
                    commitment_error=commitment_error,
                )
            )
        except Exception as error:
            if isinstance(current, VerifyContinuation):
                return _settle_verify_incomplete(
                    current,
                    deps,
                    FailureDetail(
                        type(error).__name__, logical_error_text(error)
                    ),
                )
            if resumed:
                return _settle_execute_resume_failure(
                    current,
                    ctx,
                    deps,
                    FailureDetail(
                        type(error).__name__, logical_error_text(error)
                    ),
                    exclusion_items,
                )
            raise
        if isinstance(current, VerifyContinuation):
            return _settle_verify_incomplete(
                current,
                deps,
                FailureDetail(
                    "VerificationContinuationInvalid",
                    commitment_error,
                ),
            )
        if resumed:
            return _settle_execute_resume_failure(
                current,
                ctx,
                deps,
                FailureDetail(
                    "ExecutionResumeCommitmentInvalid",
                    commitment_error,
                ),
                exclusion_items,
            )
        return OperationResult(
            status=SessionState.REFUSED,
            disposition=Disposition.UNRUN,
        )

    try:
        ctx.emit(PhaseChanged("execution-preflight"))
        world = deps.observer(xset, deps.observation_fs)
        verdict = deps.preflight(xset, world)
        refusals = refusal_views(verdict)
        deps.save_execution_details(ExecutionDetails(str(xset.run_id), refusals))
    except Exception as error:
        if isinstance(current, VerifyContinuation):
            return _settle_verify_incomplete(
                current,
                deps,
                FailureDetail(
                    type(error).__name__, logical_error_text(error)
                ),
            )
        if resumed:
            return _settle_execute_resume_failure(
                current,
                ctx,
                deps,
                FailureDetail(
                    type(error).__name__, logical_error_text(error)
                ),
                exclusion_items,
            )
        raise
    if not verdict.ok:
        if isinstance(current, VerifyContinuation):
            detail = "; ".join(
                f"{refusal.code}: {refusal.detail}" for refusal in refusals
            ) or "verification preflight refused"
            return _settle_verify_incomplete(
                current,
                deps,
                FailureDetail("VerificationPreflightRefused", detail),
            )
        if resumed:
            detail = "; ".join(
                f"{refusal.code}: {refusal.detail}" for refusal in refusals
            ) or "execution resume preflight refused"
            return _settle_execute_resume_failure(
                current,
                ctx,
                deps,
                FailureDetail("ExecutionResumePreflightRefused", detail),
                exclusion_items,
            )
        _emit_items(ctx, exclusion_items)
        return OperationResult(
            status=SessionState.REFUSED,
            disposition=Disposition.UNRUN,
            items=exclusion_items,
        )

    execution_items: tuple[ItemOutcome, ...] = ()
    emitted_execution_items: list[ItemOutcome] = []

    def observe_execution(body: object) -> None:
        if isinstance(body, ItemOutcome):
            emitted_execution_items.append(body)
        ctx.emit(body)

    with deps.open_recording(xset) as recording:
        finished = False
        finished_recording = xset.recording

        def finish_once(
            filesystem_status: SessionState,
            recording_status: RecordingStatus,
        ) -> RecordingStatus:
            nonlocal finished, finished_recording
            if finished:
                return finished_recording
            finished = True
            finished_recording = _finish_recording(
                recording,
                filesystem_status,
                recording_status,
            )
            return finished_recording

        if isinstance(current, ExecuteContinuation):
            verify_after_execute = current.verify_after_execute
            try:
                deps.executor_fs.remove_orphaned_temps(
                    Path(xset.plan.target_root.path),
                    verdict.observed.target_parent_paths,
                    xset.run_id,
                )
                result = deps.executor(
                    xset,
                    RunContext(observe_execution, ctx.checkpoint),
                    recording.recorder,
                    deps.executor_policies,
                    deps.executor_fs,
                )
                _emit_items(ctx, exclusion_items)
                result = replace(
                    result,
                    items=_merge_operation_results(
                        xset.plan, result.items, exclusion_items
                    ),
                )
                execution_items = result.items
                execution_recording = _combined_recording(
                    xset.recording,
                    result.recording,
                )
                xset.recording = execution_recording
                result = replace(result, recording=execution_recording)
                if not verify_after_execute:
                    recording_status = finish_once(
                        result.status,
                        execution_recording,
                    )
                    return replace(result, recording=recording_status)

                execute_phase = _execute_result_phase(xset, result)
                current = _verify_continuation(
                    xset,
                    result.status,
                    execute_phase,
                )
                if (
                    not current.candidates.candidates
                    and not current.missing_evidence_ids
                ):
                    recording_status = finish_once(
                        result.status,
                        execution_recording,
                    )
                    return replace(
                        result,
                        recording=recording_status,
                        phases=(execute_phase,),
                    )
                sink(current)
            except PauseRequested:
                raise
            except Canceled:
                _emit_items(ctx, exclusion_items)
                execution_items = _merge_operation_results(
                    xset.plan,
                    tuple(emitted_execution_items),
                    exclusion_items,
                )
                recording_status = finish_once(
                    SessionState.CANCELED,
                    xset.recording,
                )
                phase = _execute_continuation_phase(
                    xset,
                    PhaseStatus.CANCELED,
                    "execution canceled",
                )
                return OperationResult(
                    status=SessionState.CANCELED,
                    recording=recording_status,
                    disposition=Disposition.RAN,
                    canceled=True,
                    items=execution_items,
                    phases=(phase,) if verify_after_execute else (),
                    bytes_done=phase.bytes_done,
                    bytes_total=phase.bytes_total or phase.bytes_done,
                )
            except Exception as error:
                recording_status = finish_once(
                    SessionState.FAILED,
                    xset.recording,
                )
                if not verify_after_execute:
                    raise
                _emit_items(ctx, exclusion_items)
                execution_items = _merge_operation_results(
                    xset.plan,
                    tuple(emitted_execution_items),
                    exclusion_items,
                )
                phase = _execute_continuation_phase(
                    xset,
                    PhaseStatus.FAILED,
                    (
                        f"{type(error).__name__}: "
                        f"{logical_error_text(error)}"
                    ),
                )
                return OperationResult(
                    status=SessionState.FAILED,
                    recording=recording_status,
                    disposition=Disposition.RAN,
                    items=execution_items,
                    phases=(phase,),
                    bytes_done=phase.bytes_done,
                    bytes_total=phase.bytes_total or phase.bytes_done,
                    error=FailureDetail(
                        type(error).__name__, logical_error_text(error)
                    ),
                )

        observed_recording = [current.recording]
        verification_items: list[IntegrityOutcome] = []

        def observe_verification(body: object) -> None:
            ctx.emit(body)
            if not isinstance(body, IntegrityOutcome):
                return
            verification_items.append(body)
            if (
                body.recording is RecordingStatus.DEGRADED
                and observed_recording[0] is RecordingStatus.OK
            ):
                observed_recording[0] = RecordingStatus.DEGRADED
                sink(replace(current, recording=RecordingStatus.DEGRADED))

        try:
            ctx.emit(PhaseChanged("verify"))
            verification_context = deps.verifier_context(
                RunContext(observe_verification, ctx.checkpoint)
            )
            target_evidence = xset.plan.target_volume_evidence
            verification_context = replace(
                verification_context,
                root_authority=RootAuthority(
                    logical_root=xset.plan.target_root.path,
                    reviewed_anchor=(
                        target_evidence.device_id
                        if target_evidence is not None
                        else None
                    ),
                    expected_volume_id=xset.plan.target_volume_id,
                ),
            )
            verification = deps.verifier(
                current.candidates,
                verification_context,
                recording.recorder,
            )
            if not isinstance(verification, IntegrityRunResult):
                raise TypeError(
                    "post-copy verifier must return IntegrityRunResult"
                )
            current_recording = _combined_recording(
                current.recording,
                observed_recording[0],
                verification.recording,
            )
            if current_recording is not current.recording:
                current = replace(current, recording=current_recording)
                sink(current)
            verify_phase = _verify_phase(
                current,
                incomplete=bool(current.missing_evidence_ids),
                error=_missing_evidence_error(current.missing_evidence_ids),
            )
            error = (
                None
                if verify_phase.error is None
                else FailureDetail(
                    "PublishedEvidenceInvariantError",
                    verify_phase.error,
                )
            )
            recording_status = finish_once(
                current.filesystem_status,
                current_recording,
            )
            return OperationResult(
                status=current.filesystem_status,
                recording=recording_status,
                disposition=Disposition.RAN,
                items=(*execution_items, *verification_items),
                phases=(current.execute_phase, verify_phase),
                bytes_done=current.execute_phase.bytes_done,
                bytes_total=(
                    current.execute_phase.bytes_total
                    if current.execute_phase.bytes_total is not None
                    else current.execute_phase.bytes_done
                ),
                error=error,
            )
        except PauseRequested:
            raise
        except Canceled:
            current_recording = _combined_recording(
                current.recording,
                observed_recording[0],
            )
            current = replace(current, recording=current_recording)
            verify_phase = _verify_phase(
                current,
                canceled=True,
                error="verification canceled",
            )
            recording_status = finish_once(
                current.filesystem_status,
                current_recording,
            )
            return OperationResult(
                status=current.filesystem_status,
                recording=recording_status,
                disposition=Disposition.RAN,
                canceled=True,
                items=(*execution_items, *verification_items),
                phases=(current.execute_phase, verify_phase),
                bytes_done=current.execute_phase.bytes_done,
                bytes_total=(
                    current.execute_phase.bytes_total
                    if current.execute_phase.bytes_total is not None
                    else current.execute_phase.bytes_done
                ),
            )
        except Exception as error:
            current_recording = _combined_recording(
                current.recording,
                observed_recording[0],
            )
            current = replace(current, recording=current_recording)
            verify_phase = _verify_phase(
                current,
                incomplete=True,
                error=(
                    f"{type(error).__name__}: "
                    f"{logical_error_text(error)}"
                ),
            )
            recording_status = finish_once(
                current.filesystem_status,
                current_recording,
            )
            return OperationResult(
                status=current.filesystem_status,
                recording=recording_status,
                disposition=Disposition.RAN,
                items=(*execution_items, *verification_items),
                phases=(current.execute_phase, verify_phase),
                bytes_done=current.execute_phase.bytes_done,
                bytes_total=(
                    current.execute_phase.bytes_total
                    if current.execute_phase.bytes_total is not None
                    else current.execute_phase.bytes_done
                ),
                error=FailureDetail(
                    type(error).__name__, logical_error_text(error)
                ),
            )


def settle_canceled_execution(
    continuation: ExecutionContinuation,
    disposition: Disposition,
    deps: SyncDependencies,
) -> OperationResult:
    """Finish a previously started paused execution without doing domain work."""

    if disposition is not Disposition.RAN:
        raise ValueError("started execution cancellation must retain RAN disposition")
    if not isinstance(continuation, (ExecuteContinuation, VerifyContinuation)):
        raise TypeError("canceled settlement requires a typed continuation")

    xset = continuation.execution_set
    if isinstance(continuation, ExecuteContinuation):
        phase = _execute_continuation_phase(
            xset,
            PhaseStatus.CANCELED,
            "execution canceled while paused or pending resume",
        )
        phases = (phase,) if continuation.verify_after_execute else ()
        filesystem_status = SessionState.CANCELED
        recording_status = xset.recording
    else:
        phase = _verify_phase(
            continuation,
            canceled=True,
            error="verification canceled while paused or pending resume",
        )
        phases = (continuation.execute_phase, phase)
        filesystem_status = continuation.filesystem_status
        recording_status = _combined_recording(
            xset.recording,
            continuation.recording,
        )

    with deps.open_recording(xset) as recording:
        recording_status = _finish_recording(
            recording,
            filesystem_status,
            recording_status,
        )
    execute_phase = (
        phase
        if isinstance(continuation, ExecuteContinuation)
        else continuation.execute_phase
    )
    return OperationResult(
        status=filesystem_status,
        recording=recording_status,
        disposition=disposition,
        canceled=True,
        phases=phases,
        bytes_done=execute_phase.bytes_done,
        bytes_total=(
            execute_phase.bytes_total
            if execute_phase.bytes_total is not None
            else execute_phase.bytes_done
        ),
    )


def refusal_views(verdict: Verdict) -> tuple[RefusalView, ...]:
    views: list[RefusalView] = []
    for refusal in verdict.refusals:
        path = None
        if refusal.subject is not None:
            path = verdict.observed.paths.get(refusal.subject)
        views.append(RefusalView(refusal.code.value, path, refusal.detail))
    return tuple(views)


def _emit_items(ctx: RunContext, items: tuple[ItemOutcome, ...]) -> None:
    for item in items:
        ctx.emit(item)


def _exclusion_items(
    plan: Plan,
    decision: ExecutionSelection,
) -> tuple[ItemOutcome, ...]:
    operations = {operation.op_id: operation for operation in plan.operations}
    return tuple(
        ItemOutcome(
            item_id=str(exclusion.op_id),
            kind=operations[exclusion.op_id].kind.value,
            path=operations[exclusion.op_id].target_rel_path,
            outcome=exclusion.outcome,
            reason=exclusion.reason,
            detail=exclusion.detail,
        )
        for exclusion in decision.exclusions
    )


def _merge_operation_results(
    plan: Plan,
    executed: tuple[ItemOutcome, ...],
    excluded: tuple[ItemOutcome, ...],
) -> tuple[ItemOutcome, ...]:
    by_id = {
        str(item.item_id): item for item in (*executed, *excluded)
    }
    ordered = [
        by_id.pop(str(operation.op_id))
        for operation in plan.operations
        if str(operation.op_id) in by_id
    ]
    ordered.extend(by_id.values())
    return tuple(ordered)


_BYTE_PRODUCING_KINDS = frozenset(
    {
        OperationKind.COPY,
        OperationKind.UPDATE,
        OperationKind.MOVE_UPDATE,
    }
)


def _verify_continuation(
    xset: ExecutionSet,
    filesystem_status: SessionState,
    execute_phase: PhaseResult,
) -> VerifyContinuation:
    candidates: list[PostCopyCandidate] = []
    missing_evidence_ids: list[str] = []
    target_root = Path(xset.plan.target_root.path)
    recording = xset.recording
    for operation in xset.plan.operations:
        if (
            operation.op_id not in xset.selection
            or operation.kind not in _BYTE_PRODUCING_KINDS
            or xset.status.get(operation.op_id) is not Outcome.SUCCEEDED
        ):
            continue
        evidence = xset.published_evidence.get(operation.op_id)
        if evidence is None:
            missing_evidence_ids.append(str(operation.op_id))
            continue
        candidates.append(_post_copy_candidate(operation, evidence, target_root))
        if evidence.recorded_identity is None:
            recording = RecordingStatus.DEGRADED
    return VerifyContinuation(
        execution_set=xset,
        candidates=PostCopySelection(tuple(candidates)),
        filesystem_status=filesystem_status,
        recording=recording,
        execute_phase=execute_phase,
        missing_evidence_ids=tuple(missing_evidence_ids),
    )


def _post_copy_candidate(
    operation: PlanOperation,
    evidence: PublishedCopyEvidence,
    target_root: Path,
) -> PostCopyCandidate:
    identity = evidence.recorded_identity
    return PostCopyCandidate(
        item_id=str(operation.op_id),
        root=target_root,
        display_path=operation.target_rel_path,
        expected_stat=evidence.attestation.subject,
        copy_attestation=evidence.attestation,
        recorded_identity=(
            None
            if identity is None
            else PostCopyRecordIdentity(
                row_id=identity.row_id,
                location_id=identity.location_id,
                scope_token=identity.scope_token,
                rel_path_key=identity.rel_path_key,
            )
        ),
    )


def _execute_result_phase(
    xset: ExecutionSet,
    result: OperationResult,
) -> PhaseResult:
    try:
        status = PhaseStatus(result.status.value)
    except ValueError as error:
        raise ValueError("execution returned invalid compound filesystem truth") from error
    return PhaseResult(
        phase=ExecuteContinuation.phase,
        status=status,
        items_done=len(xset.status),
        items_total=len(xset.selection),
        bytes_done=result.bytes_done,
        bytes_total=result.bytes_total,
        error=(
            None
            if result.error is None
            else f"{result.error.type_name}: {result.error.message}"
        ),
    )


def _execute_continuation_phase(
    xset: ExecutionSet,
    status: PhaseStatus,
    error: str | None,
) -> PhaseResult:
    bytes_total = sum(
        operation.content_bytes
        for operation in xset.plan.operations
        if operation.op_id in xset.selection
        and operation.kind in _BYTE_PRODUCING_KINDS
    )
    bytes_done = sum(
        operation.content_bytes
        for operation in xset.plan.operations
        if xset.status.get(operation.op_id) is Outcome.SUCCEEDED
        and operation.kind in _BYTE_PRODUCING_KINDS
    )
    return PhaseResult(
        phase=ExecuteContinuation.phase,
        status=status,
        items_done=len(xset.status),
        items_total=len(xset.selection),
        bytes_done=min(bytes_done, bytes_total),
        bytes_total=bytes_total,
        error=error,
    )


def _verify_phase(
    continuation: VerifyContinuation,
    *,
    incomplete: bool = False,
    canceled: bool = False,
    error: str | None = None,
) -> PhaseResult:
    if incomplete and canceled:
        raise ValueError("verify phase cannot be incomplete and canceled")
    candidates = continuation.candidates
    planned_bytes = sum(
        candidate.expected_stat.size for candidate in candidates.candidates
    ) + _missing_evidence_bytes(continuation)
    completed_bytes = sum(candidates.completed_bytes.values())
    retry_bytes = max(0, candidates.processed_bytes - completed_bytes)
    bytes_total = max(
        candidates.processed_bytes,
        planned_bytes + retry_bytes,
    )
    status = (
        PhaseStatus.CANCELED
        if canceled
        else PhaseStatus.INCOMPLETE
        if incomplete
        else PhaseStatus.COMPLETED
    )
    return PhaseResult(
        phase=VerifyContinuation.phase,
        status=status,
        items_done=candidates.completed_count,
        items_total=(
            len(candidates.candidates)
            + len(continuation.missing_evidence_ids)
        ),
        bytes_done=candidates.processed_bytes,
        bytes_total=bytes_total,
        error=error,
    )


def _missing_evidence_bytes(continuation: VerifyContinuation) -> int:
    missing = set(continuation.missing_evidence_ids)
    return sum(
        operation.content_bytes
        for operation in continuation.execution_set.plan.operations
        if str(operation.op_id) in missing
    )


def _missing_evidence_error(item_ids: tuple[str, ...]) -> str | None:
    if not item_ids:
        return None
    return "missing published evidence for successful operations: " + ", ".join(
        item_ids
    )


def _settle_execute_resume_failure(
    continuation: ExecuteContinuation,
    ctx: RunContext,
    deps: SyncDependencies,
    error: FailureDetail,
    exclusion_items: tuple[ItemOutcome, ...],
) -> OperationResult:
    """Finish an already-started execute continuation without more domain work."""

    try:
        _emit_items(ctx, exclusion_items)
    except Exception as emit_error:
        error = FailureDetail(type(emit_error).__name__, str(emit_error))
    phase = _execute_continuation_phase(
        continuation.execution_set,
        PhaseStatus.FAILED,
        f"{error.type_name}: {error.message}",
    )
    recording_status = _finish_existing_recording(
        deps,
        continuation.execution_set,
        SessionState.FAILED,
        continuation.execution_set.recording,
    )
    return OperationResult(
        status=SessionState.FAILED,
        recording=recording_status,
        disposition=Disposition.RAN,
        items=exclusion_items,
        phases=(phase,),
        bytes_done=phase.bytes_done,
        bytes_total=(
            phase.bytes_total
            if phase.bytes_total is not None
            else phase.bytes_done
        ),
        error=error,
    )


def _settle_verify_incomplete(
    continuation: VerifyContinuation,
    deps: SyncDependencies,
    error: FailureDetail,
) -> OperationResult:
    phase = _verify_phase(
        continuation,
        incomplete=True,
        error=f"{error.type_name}: {error.message}",
    )
    recording_status = _combined_recording(
        continuation.execution_set.recording,
        continuation.recording,
    )
    recording_status = _finish_existing_recording(
        deps,
        continuation.execution_set,
        continuation.filesystem_status,
        recording_status,
    )
    return OperationResult(
        status=continuation.filesystem_status,
        recording=recording_status,
        disposition=Disposition.RAN,
        phases=(continuation.execute_phase, phase),
        bytes_done=continuation.execute_phase.bytes_done,
        bytes_total=(
            continuation.execute_phase.bytes_total
            if continuation.execute_phase.bytes_total is not None
            else continuation.execute_phase.bytes_done
        ),
        error=error,
    )


def _combined_recording(
    *values: RecordingStatus,
) -> RecordingStatus:
    return (
        RecordingStatus.DEGRADED
        if RecordingStatus.DEGRADED in values
        else RecordingStatus.OK
    )


def _finish_existing_recording(
    deps: SyncDependencies,
    xset: ExecutionSet,
    status: SessionState,
    recording_status: RecordingStatus,
) -> RecordingStatus:
    finisher = getattr(deps, "finish_existing_recording", None)
    if finisher is not None:
        try:
            finisher(xset, status, recording_status)
        except Exception:
            return RecordingStatus.DEGRADED
        return recording_status
    with deps.open_recording(xset) as recording:
        return _finish_recording(recording, status, recording_status)


def _finish_recording(
    recording: RunRecording,
    status: SessionState,
    recording_status: RecordingStatus,
) -> RecordingStatus:
    try:
        recording.finish(status, recording_status)
    except Exception:
        return RecordingStatus.DEGRADED
    return recording_status


def _commitment_error(xset: ExecutionSet) -> str | None:
    commitment = xset.commitment
    if commitment is None:
        return "execution set is not committed"
    calculated_fingerprint = plan_fingerprint(xset.plan)
    if calculated_fingerprint != xset.plan.fingerprint:
        return "reviewed plan content does not match its fingerprint"
    if commitment.plan_fingerprint != calculated_fingerprint:
        return "commitment plan fingerprint does not match the reviewed plan"
    if commitment.selection_digest != selection_digest(xset.selection):
        return "commitment selection digest does not match the reviewed selection"
    if not xset.selection:
        return "nothing is selected to synchronize"
    return None


def _ordinary_logical_root(path: str) -> Path:
    logical = lexical_absolute_path(path)
    try:
        admit_root_chain(
            RootAuthority(logical),
            anchor_probe=current_volume_anchor,
        )
    except RootAuthorityError as error:
        if error.issue in {
            RootAuthorityIssue.PLACEHOLDER_COMPONENT,
            RootAuthorityIssue.REPARSE_COMPONENT,
            RootAuthorityIssue.NON_DIRECTORY_COMPONENT,
        }:
            detail = (
                "location root chain contains a nonordinary directory: "
                f"{error.logical_path}"
            )
        else:
            cause = error.__cause__
            detail = logical_error_text(
                cause if isinstance(cause, OSError) else error
            )
        raise ValueError(detail) from error
    return Path(logical)


def _physical_logical_root(path: Path) -> Path:
    try:
        resolved = Path(to_extended_length_path(str(path))).resolve(
            strict=True
        )
    except OSError as error:
        raise ValueError(logical_error_text(error)) from error
    return Path(from_extended_length_path(str(resolved)))


def validate_sync_paths(
    source_path: str,
    target_path: str,
) -> tuple[Path, Path]:
    """Resolve one interface path pair without exposing native path spelling."""

    source = _ordinary_logical_root(source_path)
    target = _ordinary_logical_root(target_path)
    source_key = os.path.normcase(str(_physical_logical_root(source)))
    target_key = os.path.normcase(str(_physical_logical_root(target)))
    try:
        common = os.path.normcase(os.path.commonpath((source_key, target_key)))
    except ValueError:
        common = ""
    if common in {source_key, target_key}:
        raise ValueError("source and target must be distinct, non-nested directories")
    return source, target


def _validated_roots(source_path: str, target_path: str) -> tuple[Root, Root]:
    source, target = validate_sync_paths(source_path, target_path)
    return Root(str(source), "source"), Root(str(target), "target")
