"""Drive ``modules.executor.execute`` over real roots without the ledger.

Inputs come from the real scanner and planner rather than hand-built
operations, so the measured operation mix, dependencies, and blocked flags are
the ones the product would actually produce.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter
from typing import Sequence
from uuid import uuid4

from xxhash import xxh3_128

from namisync.core.evidence import Outcome
from namisync.core.events import ItemOutcome, Progress
from namisync.core.execution import ExecutionSet, RunId, validated_run_id
from namisync.core.models import IgnoreSet, Root, ScanResult
from namisync.core.planning import (
    MappingSnapshot,
    Plan,
    Scope,
    SyncOptions,
)
from namisync.core.session import OperationResult
from namisync.modules.executor import (
    ExecutorPolicies,
    NativeCopyBackend,
    NativeFileSystem,
    execute,
)
from namisync.modules.planner import plan as build_plan
from namisync.modules.preflight import LocalObservationFileSystem, observe, preflight
from namisync.modules.scanner import scan as scan_root
from namisync.workflows.selection import derive_execution_selection

from .seams import CopySample, LedgerlessRecorder, RigClock, Tape, TappedCopyBackend


class ExecutorRigError(RuntimeError):
    """The rig refused to execute the plan it built."""


@dataclass(frozen=True, slots=True)
class ExecutorRun:
    """One measured execution plus everything needed to interpret it."""

    result: OperationResult
    execution_set: ExecutionSet
    plan: Plan
    source_scan: ScanResult
    target_scan: ScanResult
    tape: Tape
    recorder: LedgerlessRecorder
    copy_samples: tuple[CopySample, ...]
    scan_seconds: float
    plan_seconds: float
    preflight_seconds: float
    execute_seconds: float

    @property
    def bytes_done(self) -> int:
        progress = self.tape.of_type(Progress)
        return progress[-1][1].bytes_done if progress else 0

    @property
    def outcomes(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for _, event in self.tape.of_type(ItemOutcome):
            counts[event.outcome.value] = counts.get(event.outcome.value, 0) + 1
        return counts

    @property
    def operation_kinds(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for operation in self.plan.operations:
            if operation.op_id in self.execution_set.selection:
                counts[operation.kind.value] = counts.get(operation.kind.value, 0) + 1
        return counts

    @property
    def throughput_mib_s(self) -> float:
        if self.execute_seconds <= 0:
            return 0.0
        return self.bytes_done / (1024**2) / self.execute_seconds

    @property
    def succeeded(self) -> bool:
        return all(
            outcome is Outcome.SUCCEEDED
            for outcome in self.execution_set.status.values()
        )


@dataclass(frozen=True, slots=True)
class PreparedExecution:
    """Everything the scan/plan phase produced for one pending execution."""

    execution_set: ExecutionSet
    plan: Plan
    source_scan: ScanResult
    target_scan: ScanResult
    scan_seconds: float
    plan_seconds: float


def build_execution_set(
    source: Path,
    target: Path,
    *,
    options: SyncOptions | None = None,
    ignores: IgnoreSet | None = None,
    tape: Tape | None = None,
    run_id: RunId | None = None,
) -> PreparedExecution:
    """Scan both roots and derive the same safe subset the workflow would."""

    tape = tape or Tape()
    context = tape.context()
    ignore_set = ignores or IgnoreSet()
    sync_options = options or SyncOptions()

    started = perf_counter()
    source_scan = scan_root(Root(str(Path(source).resolve()), "source"), ignore_set, context)
    target_scan = scan_root(Root(str(Path(target).resolve()), "target"), ignore_set, context)
    scan_seconds = perf_counter() - started

    started = perf_counter()
    correspondence = MappingSnapshot.empty(source_scan.volume_id, target_scan.volume_id)
    plan = build_plan(
        source_scan, target_scan, correspondence, sync_options, Scope.everything()
    )
    selection = derive_execution_selection(plan)
    execution_set = ExecutionSet(
        plan, selection.selection, run_id or validated_run_id(uuid4().hex)
    )
    plan_seconds = perf_counter() - started
    return PreparedExecution(
        execution_set, plan, source_scan, target_scan, scan_seconds, plan_seconds
    )


def run_executor(
    source: Path,
    target: Path,
    *,
    options: SyncOptions | None = None,
    ignores: IgnoreSet | None = None,
    policies: ExecutorPolicies | None = None,
    filesystem: object | None = None,
    collect_metrics: bool = True,
    preflight_gate: bool = True,
) -> ExecutorRun:
    """Execute one plan against real roots and return the measured run.

    A supplied ``policies`` keeps its own pacing and failure policy, but its
    copy backend is wrapped so per-operation diagnostics are still sampled.
    """

    tape = Tape()
    prepared = build_execution_set(
        source, target, options=options, ignores=ignores, tape=tape
    )
    execution_set = prepared.execution_set

    preflight_seconds = 0.0
    if preflight_gate:
        started = perf_counter()
        world = observe(execution_set, LocalObservationFileSystem())
        verdict = preflight(execution_set, world)
        preflight_seconds = perf_counter() - started
        if not verdict.ok:
            reasons = ", ".join(refusal.code.value for refusal in verdict.refusals)
            raise ExecutorRigError(f"preflight refused the rig plan: {reasons}")

    inner_backend = (
        NativeCopyBackend(hasher_factory=xxh3_128, collect_metrics=collect_metrics)
        if policies is None
        else policies.copy_backend
    )
    backend = TappedCopyBackend(inner_backend)
    run_policies = (
        ExecutorPolicies(copy_backend=backend, clock=RigClock())
        if policies is None
        else replace(policies, copy_backend=backend)
    )
    recorder = LedgerlessRecorder(prepared.plan, execution_set.run_id)

    started = perf_counter()
    result = execute(
        execution_set,
        tape.context(),
        recorder,
        run_policies,
        filesystem or NativeFileSystem(),
    )
    execute_seconds = perf_counter() - started

    return ExecutorRun(
        result=result,
        execution_set=execution_set,
        plan=prepared.plan,
        source_scan=prepared.source_scan,
        target_scan=prepared.target_scan,
        tape=tape,
        recorder=recorder,
        copy_samples=tuple(backend.samples),
        scan_seconds=prepared.scan_seconds,
        plan_seconds=prepared.plan_seconds,
        preflight_seconds=preflight_seconds,
        execute_seconds=execute_seconds,
    )


def copy_metrics_summary(samples: Sequence[CopySample]) -> dict[str, object]:
    """Aggregate the executor's opt-in pipeline diagnostics."""

    if not samples:
        return {"copies": 0}
    collected = [sample for sample in samples if sample.metrics is not None]
    summary: dict[str, object] = {
        "copies": len(samples),
        "bytes": sum(sample.size for sample in samples),
        "seconds": sum(sample.seconds for sample in samples),
        "chunk_sizes": sorted({sample.chunk_size for sample in samples}),
    }
    if collected:
        summary["reader_blocked_seconds"] = sum(
            sample.metrics.reader_blocked_seconds for sample in collected
        )
        summary["writer_starved_seconds"] = sum(
            sample.metrics.writer_starved_seconds for sample in collected
        )
        summary["payload_high_water"] = max(
            sample.metrics.payload_high_water for sample in collected
        )
        summary["reserved_bytes"] = sum(
            sample.metrics.reserved_bytes for sample in collected
        )
    return summary
