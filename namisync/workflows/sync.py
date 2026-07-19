"""Top-to-bottom M0 reviewed sync workflows."""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from namisync.core.events import PhaseChanged
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
from namisync.modules.preflight import ObservationFileSystem, SettingsReader

from .models import ExecutionDetails, PlanArtifact, PlanRequest, RefusalView


class RunRecording(Protocol):
    recorder: Recorder

    def finish(
        self, status: SessionState, recording: RecordingStatus
    ) -> None: ...


Scanner = Callable[[Root, IgnoreSet, RunContext], ScanResult]
Planner = Callable[[ScanResult, ScanResult, MappingSnapshot, SyncOptions, Scope], Plan]
Observer = Callable[[ExecutionSet, ObservationFileSystem, SettingsReader], ObservedWorld]
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
    settings: Callable[[Plan], SettingsReader]
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
    selection = frozenset(operation.op_id for operation in plan.operations)
    preview = ExecutionSet(plan, selection, run_id)

    ctx.emit(PhaseChanged("review-preflight"))
    world = deps.observer(preview, deps.observation_fs, deps.settings(plan))
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

    ctx.emit(PhaseChanged("execution-preflight"))
    world = deps.observer(xset, deps.observation_fs, deps.settings(xset.plan))
    verdict = deps.preflight(xset, world)
    refusals = refusal_views(verdict)
    deps.save_execution_details(ExecutionDetails(str(xset.run_id), refusals))
    if not verdict.ok:
        return OperationResult(
            status=SessionState.REFUSED,
            disposition=Disposition.UNRUN,
        )

    with deps.open_recording(xset) as recording:
        try:
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
            _finish_best_effort(
                recording,
                SessionState.CANCELED,
                RecordingStatus.OK,
            )
            raise
        except BaseException:
            _finish_best_effort(
                recording,
                SessionState.FAILED,
                RecordingStatus.OK,
            )
            raise

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
