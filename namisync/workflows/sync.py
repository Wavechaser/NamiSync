"""Top-to-bottom M0 reviewed sync workflows."""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from namisync.core.events import ItemOutcome, PhaseChanged
from namisync.core.evidence import RecordingStatus
from namisync.core.execution import (
    ExecutionSet,
    ExecutorFileSystem,
    Recorder,
    validated_run_id,
)
from namisync.core.models import IgnoreSet, Root, ScanResult
from namisync.core.planning import (
    MappingSnapshot,
    Plan,
    Scope,
    SyncOptions,
    plan_fingerprint,
    selection_digest,
)
from namisync.core.preflight import ObservedWorld, Verdict
from namisync.core.session import (
    Canceled,
    Disposition,
    OperationResult,
    PauseRequested,
    RunContext,
    SessionState,
)
from namisync.modules.executor import ExecutorPolicies
from namisync.modules.preflight import ObservationFileSystem

from .models import ExecutionDetails, PlanArtifact, PlanRequest, RefusalView
from .selection import ExecutionSelection, derive_execution_selection


class RunRecording(Protocol):
    recorder: Recorder

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
    open_recording: Callable[[ExecutionSet], AbstractContextManager[RunRecording]]
    save_plan: Callable[[PlanArtifact], None]
    save_execution_details: Callable[[ExecutionDetails], None]
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
    xset: ExecutionSet,
    ctx: RunContext,
    deps: SyncDependencies,
) -> OperationResult:
    """Validate commitment, freshly preflight, then execute and record."""

    commitment_error = _commitment_error(xset)
    if commitment_error is not None:
        deps.save_execution_details(
            ExecutionDetails(str(xset.run_id), commitment_error=commitment_error)
        )
        return OperationResult(
            status=SessionState.REFUSED,
            disposition=Disposition.UNRUN,
        )

    exclusion_items = _exclusion_items(
        xset.plan,
        derive_execution_selection(xset.plan),
        xset.selection,
    )
    ctx.emit(PhaseChanged("execution-preflight"))
    world = deps.observer(xset, deps.observation_fs)
    verdict = deps.preflight(xset, world)
    refusals = refusal_views(verdict)
    deps.save_execution_details(ExecutionDetails(str(xset.run_id), refusals))
    if not verdict.ok:
        _emit_items(ctx, exclusion_items)
        return OperationResult(
            status=SessionState.REFUSED,
            disposition=Disposition.UNRUN,
            items=exclusion_items,
        )

    with deps.open_recording(xset) as recording:
        try:
            deps.executor_fs.remove_orphaned_temps(
                Path(xset.plan.target_root.path),
                verdict.observed.target_parent_paths,
                xset.run_id,
            )
            result = deps.executor(
                xset,
                ctx,
                recording.recorder,
                deps.executor_policies,
                deps.executor_fs,
            )
        except PauseRequested:
            raise
        except Canceled:
            _emit_items(ctx, exclusion_items)
            _finish_best_effort(
                recording,
                SessionState.CANCELED,
                RecordingStatus.OK,
            )
            raise
        except BaseException:
            _emit_items(ctx, exclusion_items)
            _finish_best_effort(
                recording,
                SessionState.FAILED,
                RecordingStatus.OK,
            )
            raise

        _emit_items(ctx, exclusion_items)
        result = replace(
            result,
            items=_merge_operation_results(
                xset.plan, result.items, exclusion_items
            ),
        )
        try:
            recording.finish(result.status, result.recording)
        except Exception:
            result = replace(result, recording=RecordingStatus.DEGRADED)
        return result


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
    selection: frozenset,
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
        if exclusion.op_id not in selection
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
    return None


def _validated_roots(source_path: str, target_path: str) -> tuple[Root, Root]:
    source = Path(source_path).resolve(strict=True)
    target = Path(target_path).resolve(strict=True)
    if not source.is_dir():
        raise NotADirectoryError(f"source is not a directory: {source}")
    if not target.is_dir():
        raise NotADirectoryError(f"target is not a directory: {target}")
    source_key = os.path.normcase(str(source))
    target_key = os.path.normcase(str(target))
    try:
        common = os.path.normcase(os.path.commonpath((source_key, target_key)))
    except ValueError:
        common = ""
    if common in {source_key, target_key}:
        raise ValueError("source and target must be distinct, non-nested directories")
    return Root(str(source), "source"), Root(str(target), "target")


def _finish_best_effort(
    recording: RunRecording,
    status: SessionState,
    recording_status: RecordingStatus,
) -> None:
    try:
        recording.finish(status, recording_status)
    except Exception:
        pass
