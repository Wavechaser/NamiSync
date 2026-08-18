"""Drive ``modules.executor.execute`` over real roots without the ledger.

Inputs come from the real scanner and planner rather than hand-built
operations. Correspondence is deliberately empty, so this measures a
first-run/no-history plan and does not produce MOVE or MOVE_UPDATE operations.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from pathlib import PureWindowsPath
from time import perf_counter
from typing import Sequence
from uuid import uuid4

from xxhash import xxh3_128

from namisync.core.events import ItemOutcome
from namisync.core.execution import ExecutionSet, RunId, validated_run_id
from namisync.core.models import IgnoreSet, Root, ScanResult
from namisync.core.planning import (
    MappingSnapshot,
    OpId,
    OperationKind,
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

from .corpus import WorkspaceClaim
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
        return self.result.bytes_done

    @property
    def outcomes(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in self.result.items:
            if not isinstance(event, ItemOutcome):  # pragma: no cover - contract guard
                continue
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


@dataclass(frozen=True, slots=True)
class PreparedExecution:
    """Immutable scan/plan evidence reusable by fresh execution samples."""

    plan: Plan
    selection: frozenset[OpId]
    source_scan: ScanResult
    target_scan: ScanResult
    ignores: IgnoreSet
    scan_seconds: float
    plan_seconds: float


def prepare_execution(
    source: Path,
    target: Path,
    *,
    options: SyncOptions | None = None,
    ignores: IgnoreSet | None = None,
    tape: Tape | None = None,
) -> PreparedExecution:
    """Scan both roots and derive a safe first-run/no-history selection."""

    source = Path(source).resolve()
    target = Path(target).resolve()
    _require_disjoint_roots(source, target)
    tape = tape or Tape()
    context = tape.context()
    ignore_set = ignores or IgnoreSet()
    sync_options = options or SyncOptions()

    started = perf_counter()
    source_scan = scan_root(Root(str(source), "source"), ignore_set, context)
    target_scan = scan_root(Root(str(target), "target"), ignore_set, context)
    scan_seconds = perf_counter() - started
    _require_complete_scan("source", source_scan)
    _require_complete_scan("target", target_scan)

    started = perf_counter()
    correspondence = MappingSnapshot.empty(source_scan.volume_id, target_scan.volume_id)
    plan = build_plan(
        source_scan, target_scan, correspondence, sync_options, Scope.everything()
    )
    selection = derive_execution_selection(plan)
    if selection.exclusions:
        reasons = ", ".join(
            sorted({exclusion.reason for exclusion in selection.exclusions})
        )
        raise ExecutorRigError(
            "the reviewed plan contains safety exclusions and is not a complete "
            f"benchmark sample: {reasons}"
        )
    plan_seconds = perf_counter() - started
    return PreparedExecution(
        plan,
        selection.selection,
        source_scan,
        target_scan,
        ignore_set,
        scan_seconds,
        plan_seconds,
    )


def require_reusable_copy_plan(prepared: PreparedExecution) -> None:
    """Refuse plan reuse unless it describes one empty-target copy workload."""

    target_directories = tuple(
        record for record in prepared.target_scan.directories if record.rel_path
    )
    if prepared.target_scan.files or target_directories:
        raise ExecutorRigError(
            "reusable execution requires an empty-target copy workload"
        )
    operations = tuple(
        operation
        for operation in prepared.plan.operations
        if operation.op_id in prepared.selection
    )
    if any(
        operation.kind not in {OperationKind.COPY, OperationKind.MKDIR}
        or operation.target_expected is not None
        or operation.prior_target_rel_path is not None
        or operation.prior_target_expected is not None
        for operation in operations
    ):
        raise ExecutorRigError(
            "reusable execution requires an empty-target copy workload"
        )


def execute_prepared(
    prepared: PreparedExecution,
    workspace: WorkspaceClaim,
    *,
    policies: ExecutorPolicies | None = None,
    filesystem: object | None = None,
    collect_metrics: bool = True,
    preflight_gate: bool = True,
    run_id: RunId | None = None,
) -> ExecutorRun:
    """Execute one fresh sample from immutable prepared plan evidence."""

    target = workspace.validate()
    prepared_target = Path(prepared.plan.target_root.path).resolve()
    if target != prepared_target:
        raise ExecutorRigError(
            "prepared plan target does not match the live workspace claim: "
            f"{prepared_target}, {target}"
        )
    execution_set = ExecutionSet(
        prepared.plan,
        prepared.selection,
        run_id or validated_run_id(uuid4().hex),
    )
    tape = Tape()

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
    backend = TappedCopyBackend(inner_backend) if collect_metrics else inner_backend
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
        copy_samples=(
            tuple(backend.samples) if isinstance(backend, TappedCopyBackend) else ()
        ),
        scan_seconds=prepared.scan_seconds,
        plan_seconds=prepared.plan_seconds,
        preflight_seconds=preflight_seconds,
        execute_seconds=execute_seconds,
    )


def run_executor(
    source: Path,
    workspace: WorkspaceClaim,
    *,
    options: SyncOptions | None = None,
    ignores: IgnoreSet | None = None,
    policies: ExecutorPolicies | None = None,
    filesystem: object | None = None,
    collect_metrics: bool = True,
    preflight_gate: bool = True,
) -> ExecutorRun:
    """Execute one plan against real roots and return the measured run.

    A supplied ``policies`` keeps its own pacing and failure policy. Diagnostics
    wrap its copy backend only when ``collect_metrics`` is true.
    """

    source = Path(source).resolve()
    target = workspace.validate()
    prepared = prepare_execution(source, target, options=options, ignores=ignores)
    return execute_prepared(
        prepared,
        workspace,
        policies=policies,
        filesystem=filesystem,
        collect_metrics=collect_metrics,
        preflight_gate=preflight_gate,
    )


def require_stable_copy_evidence(
    reference: ExecutorRun,
    sample: ExecutorRun,
) -> None:
    """Require every byte-producing operation to retain identical content."""

    def evidence(run: ExecutorRun) -> dict[OpId, tuple[str, bytes, int]]:
        return {
            op_id: (
                published.attestation.content.algorithm,
                published.attestation.content.digest,
                published.attestation.content.size,
            )
            for op_id, published in run.execution_set.published_evidence.items()
        }

    if evidence(reference) != evidence(sample):
        raise ExecutorRigError(
            "source corpus copy evidence changed between repeated executions"
        )


def require_source_unchanged(prepared: PreparedExecution) -> float:
    """Rescan once after repeated samples and reject corpus membership drift."""

    tape = Tape()
    started = perf_counter()
    current = scan_root(
        prepared.source_scan.root,
        prepared.ignores,
        tape.context(),
    )
    scan_seconds = perf_counter() - started
    _require_complete_scan("source", current)
    if current != prepared.source_scan:
        raise ExecutorRigError("source corpus changed during the repeated benchmark")
    return scan_seconds


def expected_output_paths(
    run: ExecutorRun,
) -> tuple[frozenset[str], frozenset[str]]:
    """Derive the complete successful target tree from scan and plan semantics."""

    files = {_output_path(record.rel_path) for record in run.target_scan.files}
    directories = {
        _output_path(record.rel_path)
        for record in run.target_scan.directories
        if record.rel_path
    }
    for operation in run.plan.operations:
        if operation.op_id not in run.execution_set.selection:
            continue
        target = _output_path(operation.target_rel_path)
        kind = operation.kind
        if kind is OperationKind.MKDIR:
            _add_directory(target, directories)
        elif kind is OperationKind.COPY:
            files.add(target)
            _add_parents(target, directories)
        elif kind is OperationKind.UPDATE:
            if run.plan.trash_on_update:
                trash = _trash_path(run.execution_set.run_id, target)
                _move_output_tree(files, directories, target, trash)
                _add_parents(trash, directories)
            else:
                _remove_output_tree(files, directories, target)
            files.add(target)
            _add_parents(target, directories)
        elif kind is OperationKind.MOVE:
            if operation.prior_target_rel_path is None:
                raise ExecutorRigError("MOVE output lacks its prior target path")
            _move_output_tree(
                files,
                directories,
                _output_path(operation.prior_target_rel_path),
                target,
            )
            _add_parents(target, directories)
        elif kind is OperationKind.MOVE_UPDATE:
            if operation.prior_target_rel_path is None:
                raise ExecutorRigError("MOVE_UPDATE output lacks its prior target path")
            prior = _output_path(operation.prior_target_rel_path)
            # MOVE_UPDATE always preserves the replaced prior path in this run's
            # trash tree; unlike UPDATE, runtime does not consult trash_on_update.
            trash = _trash_path(run.execution_set.run_id, prior)
            _move_output_tree(files, directories, prior, trash)
            _add_parents(trash, directories)
            files.add(target)
            _add_parents(target, directories)
        elif kind is OperationKind.RECASE:
            if operation.prior_target_rel_path is None:
                raise ExecutorRigError("RECASE output lacks its prior target path")
            _move_output_tree(
                files,
                directories,
                _output_path(operation.prior_target_rel_path),
                target,
            )
        elif kind is OperationKind.TRASH:
            trash = _trash_path(run.execution_set.run_id, target)
            _move_output_tree(files, directories, target, trash)
            _add_parents(trash, directories)
        elif kind is OperationKind.DELETE:
            _remove_output_tree(files, directories, target)
        elif kind is not OperationKind.NOOP:
            raise ExecutorRigError(f"cannot derive outputs for {kind.value}")
    return frozenset(files), frozenset(directories)


def _output_path(relative: str) -> str:
    return "/".join(PureWindowsPath(relative).parts)


def _trash_path(run_id: RunId, relative: str) -> str:
    return "/".join((".synctrash", str(run_id), *PureWindowsPath(relative).parts))


def _add_directory(path: str, directories: set[str]) -> None:
    directories.add(path)
    _add_parents(path, directories)


def _add_parents(path: str, directories: set[str]) -> None:
    parts = PureWindowsPath(path).parts
    for end in range(1, len(parts)):
        directories.add("/".join(parts[:end]))


def _remove_output_tree(
    files: set[str],
    directories: set[str],
    root: str,
) -> None:
    root_parts = tuple(part.casefold() for part in PureWindowsPath(root).parts)
    for paths in (files, directories):
        paths.difference_update(
            path
            for path in paths
            if tuple(part.casefold() for part in PureWindowsPath(path).parts)[
                : len(root_parts)
            ]
            == root_parts
        )


def _move_output_tree(
    files: set[str],
    directories: set[str],
    source: str,
    destination: str,
) -> None:
    source_parts = PureWindowsPath(source).parts
    source_folded = tuple(part.casefold() for part in source_parts)
    destination_parts = PureWindowsPath(destination).parts
    for paths in (files, directories):
        moved: dict[str, str] = {}
        for path in paths:
            parts = PureWindowsPath(path).parts
            if tuple(part.casefold() for part in parts[: len(source_parts)]) == source_folded:
                moved[path] = "/".join((*destination_parts, *parts[len(source_parts) :]))
        paths.difference_update(moved)
        paths.update(moved.values())


def _require_disjoint_roots(source: Path, target: Path) -> None:
    if (
        source == target
        or source.is_relative_to(target)
        or target.is_relative_to(source)
    ):
        raise ExecutorRigError("source and target workspaces must not overlap")


def _require_complete_scan(label: str, result: ScanResult) -> None:
    if result.complete and not result.unsupported:
        return
    warning_codes = sorted({warning.code.value for warning in result.warnings})
    detail = ", ".join(warning_codes) if warning_codes else "unsupported entries"
    raise ExecutorRigError(
        f"{label} scan is not a complete regular-file benchmark corpus: {detail}"
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
