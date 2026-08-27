"""Top-to-bottom M0 reviewed sync workflows."""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from types import MappingProxyType
from typing import Protocol

from namisync.core.events import ItemOutcome, PhaseChanged
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.execution import (
    ExecutionSet,
    ExecutorFileSystem,
    PublishedCopyEvidence,
    Recorder,
    TaskRecordingIssue,
    TaskRecordingIssueReason,
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
from namisync.core.models import (
    FileIdentity,
    FileStat,
    IgnoreSet,
    MetadataSnapshot,
    Root,
    ScanResult,
    ScanScope,
    VolumeEvidence,
    VolumeId,
)
from namisync.core.pathing import (
    from_extended_length_path,
    lexical_absolute_path,
    logical_error_text,
    normalize_relative_path,
    to_extended_length_path,
    validate_relative_path,
)
from namisync.core.planning import (
    MappingSnapshot,
    OpId,
    OperationKind,
    Plan,
    PlanOperation,
    Scope,
    SyncOptions,
    plan_fingerprint,
    selection_digest,
)
from namisync.core.preflight import (
    ObservedWorld,
    Refusal,
    RefusalCode,
    RootObservation,
    StatObservation,
    Subject,
    TrashObservation,
    Verdict,
)
from namisync.core.review import (
    PlanReviewAdmission,
    ReviewFactLimitError,
    admit_plan_scan_copy,
    admit_retained_plan_scan,
    snapshot_plan_scan_result,
)
from namisync.core.root_authority import (
    RootAuthority,
    RootAuthorityError,
    RootAuthorityIssue,
    admit_root_chain,
    current_volume_anchor,
)
from namisync.core.scalars import (
    MAX_DIAGNOSTIC_UTF8_BYTES,
    bounded_utf8_text,
    require_safe_int,
    require_signed_64,
    require_utf16_path,
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
    normalize_result_diagnostics,
)
from namisync.modules.executor import ExecutorPolicies
from namisync.modules.planner import (
    admit_plan_mapping_copy,
    admit_retained_plan_candidate,
    snapshot_mapping_snapshot,
    snapshot_plan_candidate,
    snapshot_plan_options,
)
from namisync.modules.preflight import ObservationFileSystem

from .models import (
    ExecuteContinuation,
    ExecutionContinuation,
    ExecutionDetails,
    PlanArtifact,
    PlanRequest,
    RefusalView,
    VerifyContinuation,
    _exact_verify_continuation,
)
from .selection import (
    ExecutionSelection,
    derive_execution_selection,
    derive_plan_review_selection,
)


class CompoundRecorder(Recorder, IntegrityRecorder, Protocol):
    """One run-bound writer exposed through both narrow recorder protocols."""


class RunRecording(Protocol):
    recorder: CompoundRecorder

    def finish(
        self, status: SessionState, recording: RecordingStatus
    ) -> None: ...


class _ContainedRecordingContext:
    def __init__(
        self,
        context: AbstractContextManager[RunRecording],
        boundary: "_RecordingBoundary",
    ) -> None:
        self._context = context
        self._boundary = boundary

    def __enter__(self) -> RunRecording:
        try:
            return self._context.__enter__()
        except (PauseRequested, Canceled):
            raise
        except Exception as error:
            self._boundary.enter_error = error
            raise

    def __exit__(self, exc_type, exc, traceback) -> bool | None:
        try:
            return self._context.__exit__(exc_type, exc, traceback)
        except Exception as error:
            self._boundary.exit_error = error
            return False


class _RecordingBoundary:
    def __init__(
        self,
        factory: Callable[
            [ExecutionSet], AbstractContextManager[RunRecording]
        ],
    ) -> None:
        self._factory = factory
        self.enter_error: Exception | None = None
        self.exit_error: Exception | None = None

    def open(
        self, execution_set: ExecutionSet
    ) -> AbstractContextManager[RunRecording]:
        try:
            context = self._factory(execution_set)
        except (PauseRequested, Canceled):
            raise
        except Exception as error:
            self.enter_error = error
            raise
        return _ContainedRecordingContext(context, self)


class Scanner(Protocol):
    def __call__(
        self,
        root: Root,
        ignores: IgnoreSet,
        ctx: RunContext,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> ScanResult: ...


class Planner(Protocol):
    def __call__(
        self,
        source: ScanResult,
        target: ScanResult,
        correspondence: MappingSnapshot,
        options: SyncOptions,
        scope: Scope,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Plan: ...


class Correspondence(Protocol):
    def __call__(
        self,
        source: ScanResult,
        target: ScanResult,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> MappingSnapshot: ...


class Observer(Protocol):
    def __call__(
        self,
        execution_set: ExecutionSet,
        fs: ObservationFileSystem,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> ObservedWorld: ...


class Preflight(Protocol):
    def __call__(
        self,
        execution_set: ExecutionSet,
        world: ObservedWorld,
        *,
        review_admission: PlanReviewAdmission | None = None,
    ) -> Verdict: ...


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
    correspondence: Correspondence
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


def _review_limit_refusal(error: ReviewFactLimitError) -> OperationResult:
    return OperationResult(
        status=SessionState.REFUSED,
        disposition=Disposition.UNRUN,
        review_fact_limit=error.fact,
    )


def _snapshot_plan_scan_copy(
    value: ScanResult,
    admission: PlanReviewAdmission,
    *,
    logical_source: bool = False,
) -> ScanResult:
    admit_plan_scan_copy(value, admission)
    return snapshot_plan_scan_result(
        value,
        admission,
        logical_source=logical_source,
    )


def _snapshot_scanner_result(
    value: ScanResult,
    expected_root: Root,
    admission: PlanReviewAdmission,
    *,
    logical_source: bool = False,
) -> ScanResult:
    snapshot = _snapshot_plan_scan_copy(
        value,
        admission,
        logical_source=logical_source,
    )
    if snapshot.root != expected_root:
        raise ValueError("plan scanner returned a different root authority")
    if snapshot.scope != ScanScope.full():
        raise ValueError("plan scanner must return the requested full scope")
    return snapshot


def _snapshot_ignore_set(
    value: object,
    admission: PlanReviewAdmission,
) -> IgnoreSet:
    if type(value) is not IgnoreSet:
        raise TypeError("plan scanner ignores must be an exact IgnoreSet")
    if type(value.exact_names) is not frozenset:
        raise TypeError("plan scanner exact ignore names must be a frozenset")
    if (
        type(value.exclude_owned_temps) is not bool
        or type(value.exclude_sync_trash) is not bool
    ):
        raise TypeError("plan scanner ignore flags must be bools")
    admission.require_source_rows(len(value.exact_names))
    admission.admit_domain_shape(reference_slots=len(value.exact_names))
    for name in value.exact_names:
        if type(name) is not str:
            raise TypeError("plan scanner exact ignore names must be text")
        canonical = validate_relative_path(name)
        if (
            canonical != name
            or PureWindowsPath(canonical).name != canonical
            or normalize_relative_path(canonical) != canonical
        ):
            raise ValueError("plan scanner exact ignore name is not canonical")
    return IgnoreSet(
        frozenset(name for name in value.exact_names),
        value.exclude_owned_temps,
        value.exclude_sync_trash,
    )


def _admit_plan_selection_shape(
    value: object,
    admission: PlanReviewAdmission,
) -> frozenset[OpId]:
    if type(value) is not frozenset:
        raise TypeError("plan selection must be an exact frozenset")
    admission.require_source_rows(len(value))
    admission.admit_domain_shape(reference_slots=len(value))
    for op_id in value:
        if type(op_id) is not str:
            raise TypeError("plan selection ids must be text")
    return value


def _snapshot_plan_selection(
    value: object,
    admission: PlanReviewAdmission,
) -> frozenset[OpId]:
    value = _admit_plan_selection_shape(value, admission)
    return frozenset(op_id for op_id in value)


def _disposable_plan_preview(
    plan: Plan,
    source: ScanResult,
    target: ScanResult,
    options: SyncOptions,
    selection: frozenset[OpId],
    run_id: str,
    admission: PlanReviewAdmission,
) -> ExecutionSet:
    copied_selection = _snapshot_plan_selection(selection, admission)
    return ExecutionSet(
        snapshot_plan_candidate(
            plan,
            source,
            target,
            options,
            review_admission=admission,
            retain_rows=False,
        ),
        copied_selection,
        run_id,
    )


def _plan_observation_scope(
    plan: Plan,
    selection: frozenset[OpId],
    admission: PlanReviewAdmission,
) -> tuple[dict[Subject, str], frozenset[str]]:
    if type(admission) is not PlanReviewAdmission:
        raise TypeError("plan review admission has the wrong type")
    paths: dict[Subject, str] = {}
    parents: set[str] = set()

    def retain_path(subject: Subject, path: str, *, replace: bool = True) -> None:
        if subject not in paths:
            admission.require_source_rows(len(paths) + 1)
            admission.admit_domain_shape(reference_slots=2)
        elif not replace:
            return
        paths[subject] = path

    def retain_parent(path: str) -> None:
        if path in parents:
            return
        admission.require_source_rows(len(parents) + 1)
        admission.admit_domain_shape(reference_slots=1)
        parents.add(path)

    for operation in plan.operations:
        if operation.op_id not in selection:
            continue
        if operation.source_rel_path is not None:
            retain_path(
                Subject(
                    plan.source_root.root_id,
                    normalize_relative_path(operation.source_rel_path),
                ),
                operation.source_rel_path,
            )
        target_paths = (
            operation.target_rel_path,
            operation.prior_target_rel_path,
        )
        for target_path in target_paths:
            if target_path is None:
                continue
            retain_path(
                Subject(
                    plan.target_root.root_id,
                    normalize_relative_path(target_path),
                ),
                target_path,
            )
            parent = str(PureWindowsPath(target_path).parent)
            parent = "" if parent == "." else parent
            retain_parent(parent)
            if parent:
                retain_path(
                    Subject(
                        plan.target_root.root_id,
                        normalize_relative_path(parent),
                    ),
                    parent,
                    replace=False,
                )
    admission.admit_domain_shape(reference_slots=len(parents))
    return paths, frozenset(parents)


_MAPPING_PROXY_TYPE = type(MappingProxyType({}))


def _snapshot_subject(value: object, plan: Plan) -> Subject:
    if type(value) is not Subject:
        raise TypeError("observed-world subjects must be exact Subject values")
    if type(value.root_id) is not str or type(value.rel_path_key) is not str:
        raise TypeError("observed-world subject fields must be text")
    if value.root_id not in {
        plan.source_root.root_id,
        plan.target_root.root_id,
    }:
        raise ValueError("observed subject names an unknown root")
    validate_relative_path(value.rel_path_key, allow_root=True)
    if value.rel_path_key != normalize_relative_path(
        value.rel_path_key,
        allow_root=True,
    ):
        raise ValueError("observed subject path key is not canonical")
    return Subject(value.root_id, value.rel_path_key)


def _snapshot_diagnostic(value: object, field_name: str) -> str | None:
    snapshot = bounded_utf8_text(
        value,
        field_name,
        maximum_bytes=MAX_DIAGNOSTIC_UTF8_BYTES,
    )
    if value is not None and snapshot is None:
        raise ValueError(f"{field_name} exceeds its diagnostic bound")
    return snapshot


def _snapshot_file_identity(
    value: object,
) -> FileIdentity | None:
    if value is None:
        return None
    if type(value) is not FileIdentity:
        raise TypeError("observed file identity has the wrong type")
    return FileIdentity(value.volume_serial, value.file_index)


def _snapshot_metadata(value: object) -> MetadataSnapshot:
    if type(value) is not MetadataSnapshot:
        raise TypeError("observed file metadata has the wrong type")
    return MetadataSnapshot(value.attributes, value.created_ns)


def _snapshot_file_stat(value: object) -> FileStat | None:
    if value is None:
        return None
    if type(value) is not FileStat:
        raise TypeError("observed file stat has the wrong type")
    return FileStat(
        value.kind,
        value.size,
        value.mtime_ns,
        _snapshot_file_identity(value.file_identity),
        value.nlink,
        _snapshot_metadata(value.metadata),
    )


def _snapshot_stat_observation(value: object) -> StatObservation:
    if type(value) is not StatObservation:
        raise TypeError("observed stats must contain StatObservation values")
    if type(value.contained) is not bool or type(value.representable) is not bool:
        raise TypeError("observed stat flags must be bools")
    return StatObservation(
        _snapshot_file_stat(value.stat),
        _snapshot_diagnostic(value.error, "stat observation error"),
        value.contained,
        value.representable,
    )


def _snapshot_volume_id(value: object) -> VolumeId | None:
    if value is None:
        return None
    if type(value) is not VolumeId:
        raise TypeError("observed volume identity has the wrong type")
    return VolumeId(value.serial, value.fs_type)


def _snapshot_volume_evidence(value: object) -> VolumeEvidence | None:
    if value is None:
        return None
    if type(value) is not VolumeEvidence:
        raise TypeError("observed volume evidence has the wrong type")
    return VolumeEvidence(value.label, value.device_id, value.clone_ambiguous)


def _snapshot_native_path(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return require_utf16_path(value, field_name)


def _snapshot_root_observation(value: object) -> RootObservation:
    if type(value) is not RootObservation:
        raise TypeError("observed roots must contain RootObservation values")
    if (
        value.authority_issue is not None
        and type(value.authority_issue) is not RootAuthorityIssue
    ):
        raise TypeError("observed root authority issue has the wrong type")
    return RootObservation(
        _snapshot_native_path(value.resolved_path, "observed root path"),
        _snapshot_volume_id(value.volume_id),
        _snapshot_volume_evidence(value.volume_evidence),
        _snapshot_diagnostic(value.error, "root observation error"),
        value.authority_issue,
    )


def _snapshot_trash_observation(value: object) -> TrashObservation | None:
    if value is None:
        return None
    if type(value) is not TrashObservation:
        raise TypeError("observed trash has the wrong type")
    if any(
        type(flag) is not bool
        for flag in (
            value.available,
            value.contained,
            value.same_volume,
            value.writable,
            value.reparse_safe,
        )
    ):
        raise TypeError("observed trash flags must be bools")
    return TrashObservation(
        _snapshot_native_path(value.resolved_path, "observed trash path"),
        value.available,
        value.contained,
        value.same_volume,
        value.writable,
        value.reparse_safe,
        _snapshot_diagnostic(value.error, "trash observation error"),
    )


def _snapshot_observed_at(value: object) -> datetime:
    if type(value) is not datetime or value.tzinfo is not timezone.utc:
        raise TypeError("observation timestamp must be an exact UTC datetime")
    return datetime(
        value.year,
        value.month,
        value.day,
        value.hour,
        value.minute,
        value.second,
        value.microsecond,
        tzinfo=timezone.utc,
        fold=value.fold,
    )


def _admit_plan_observed_world_shape(
    value: object,
    admission: PlanReviewAdmission,
) -> ObservedWorld:
    if type(value) is not ObservedWorld:
        raise TypeError("plan observer must return an exact ObservedWorld")
    if type(admission) is not PlanReviewAdmission:
        raise TypeError("plan review admission has the wrong type")
    populations = (value.stats, value.paths, value.roots)
    if any(
        type(population) not in {dict, _MAPPING_PROXY_TYPE}
        for population in populations
    ):
        raise TypeError("observed-world mappings must be exact snapshots")
    for population in populations:
        admission.require_source_rows(len(population))
    if type(value.target_parent_paths) is not frozenset:
        raise TypeError("observed target parent paths must be a frozenset")
    admission.require_source_rows(len(value.target_parent_paths))
    if len(value.roots) > 2:
        raise ValueError("observed world has more than two endpoint roots")
    admission.admit_domain_shape(
        reference_slots=(
            2 * len(value.stats)
            + 2 * len(value.paths)
            + len(value.target_parent_paths)
            + 2 * len(value.roots)
        )
    )
    return value


def _snapshot_plan_observed_world(
    value: object,
    plan: Plan,
    allowed_paths: dict[Subject, str],
    allowed_parents: frozenset[str],
    admission: PlanReviewAdmission,
    *,
    allow_owned_mappings: bool = False,
) -> ObservedWorld:
    if type(allow_owned_mappings) is not bool:
        raise TypeError("allow_owned_mappings must be a bool")
    allowed_mapping_types = (
        {dict, _MAPPING_PROXY_TYPE}
        if allow_owned_mappings
        else {dict}
    )
    if type(value) is ObservedWorld and any(
        type(population) not in allowed_mapping_types
        for population in (value.stats, value.paths, value.roots)
    ):
        raise TypeError(
            "raw observed-world mappings must be exact dictionaries"
        )
    value = _admit_plan_observed_world_shape(value, admission)
    stats: dict[Subject, StatObservation] = {}
    for raw_subject, raw_observation in value.stats.items():
        subject = _snapshot_subject(raw_subject, plan)
        if subject not in allowed_paths:
            raise ValueError("observer returned a subject outside the plan")
        stats[subject] = _snapshot_stat_observation(raw_observation)

    paths: dict[Subject, str] = {}
    for raw_subject, raw_path in value.paths.items():
        subject = _snapshot_subject(raw_subject, plan)
        path = validate_relative_path(raw_path, allow_root=True)
        if subject not in allowed_paths or allowed_paths[subject] != path:
            raise ValueError("observer returned a path outside the plan")
        paths[subject] = path
    if stats.keys() != paths.keys():
        raise ValueError("observed stats and paths must name the same subjects")

    def snapshot_parent(parent: object) -> str:
        path = validate_relative_path(parent, allow_root=True)
        if path not in allowed_parents:
            raise ValueError("observer returned an unknown target parent")
        return path

    target_parent_paths = frozenset(
        snapshot_parent(parent) for parent in value.target_parent_paths
    )

    endpoint_ids = {
        plan.source_root.root_id,
        plan.target_root.root_id,
    }
    roots: dict[str, RootObservation] = {}
    for root_id, observation in value.roots.items():
        if type(root_id) is not str or root_id not in endpoint_ids:
            raise ValueError("observed root names an unknown endpoint")
        roots[root_id] = _snapshot_root_observation(observation)

    free_space = (
        None
        if value.free_space is None
        else require_signed_64(value.free_space, "observed free space")
    )
    reclaimable_temp_bytes = require_signed_64(
        value.reclaimable_temp_bytes,
        "observed reclaimable temporary bytes",
    )
    return ObservedWorld(
        MappingProxyType(stats),
        MappingProxyType(paths),
        target_parent_paths,
        MappingProxyType(roots),
        free_space,
        reclaimable_temp_bytes,
        _snapshot_trash_observation(value.trash),
        _snapshot_observed_at(value.observed_at),
    )


def _snapshot_plan_verdict(
    value: object,
    callback_world: ObservedWorld,
    callback_stats_owner: object,
    callback_paths_owner: object,
    callback_roots_owner: object,
    authoritative_world: ObservedWorld,
    plan: Plan,
    allowed_paths: dict[Subject, str],
    allowed_parents: frozenset[str],
    allowed_ids: frozenset[OpId],
    admission: PlanReviewAdmission,
) -> Verdict:
    if type(value) is not Verdict or type(value.refusals) is not tuple:
        raise TypeError("preflight must return an exact Verdict snapshot")
    if value.observed is not callback_world:
        raise ValueError("preflight verdict must retain its exact input world")
    if (
        callback_world.stats is not callback_stats_owner
        or callback_world.paths is not callback_paths_owner
        or callback_world.roots is not callback_roots_owner
    ):
        raise TypeError("preflight mutated an owned observed-world mapping")
    validated_callback_world = _snapshot_plan_observed_world(
        callback_world,
        plan,
        allowed_paths,
        allowed_parents,
        admission,
        allow_owned_mappings=True,
    )
    if validated_callback_world != authoritative_world:
        raise ValueError("preflight mutated its admitted observed world")
    if type(value.ok) is not bool or value.ok == bool(value.refusals):
        raise ValueError("preflight verdict truth does not match its refusals")
    admission.require_informational_source_rows(len(value.refusals))

    unique: dict[tuple[object, ...], Refusal] = {}
    for raw_refusal in value.refusals:
        if (
            type(raw_refusal) is not Refusal
            or type(raw_refusal.code) is not RefusalCode
            or type(raw_refusal.detail) is not str
        ):
            raise TypeError("preflight refusals must contain exact typed values")
        if raw_refusal.op_id is not None and (
            type(raw_refusal.op_id) is not str
            or raw_refusal.op_id not in allowed_ids
        ):
            raise ValueError("preflight refusal names an unselected operation")
        subject = (
            None
            if raw_refusal.subject is None
            else _snapshot_subject(raw_refusal.subject, plan)
        )
        if subject is not None and subject not in allowed_paths:
            raise ValueError("preflight refusal names an unobserved subject")
        refusal = Refusal(
            raw_refusal.code,
            raw_refusal.op_id,
            subject,
            _snapshot_diagnostic(
                raw_refusal.detail,
                "preflight refusal detail",
            )
            or "",
        )
        key_owner = admission.fork()
        key_owner.admit_informational_shape(
            # Precharge the speculative four-slot key before it exists.
            # Duplicate candidates never acquire dictionary insertion slots.
            reference_slots=4,
            rows=0,
        )
        key = (
            refusal.code,
            refusal.op_id,
            refusal.subject,
            refusal.detail,
        )
        if key not in unique:
            admission.admit_informational_shape(
                # Four key-tuple slots plus the dictionary key/value owners.
                reference_slots=6,
                rows=0,
            )
        unique[key] = refusal
    admission.admit_informational_shape(
        # ``tuple(sorted(values))`` retains both construction containers.
        reference_slots=2 * len(unique),
        rows=0,
    )
    ordered = tuple(
        sorted(
            unique.values(),
            key=lambda refusal: (
                refusal.code.value,
                str(refusal.op_id or ""),
                refusal.subject or Subject("", ""),
                refusal.detail,
            ),
        )
    )
    return Verdict(not ordered, ordered, authoritative_world)


def _admit_retained_plan_verdict(
    value: Verdict,
    admission: PlanReviewAdmission,
) -> None:
    if type(value) is not Verdict or type(value.refusals) is not tuple:
        raise TypeError("plan verdict must be an exact Verdict snapshot")
    admission.require_informational_source_rows(len(value.refusals))
    admission.admit_informational_shape(
        reference_slots=len(value.refusals),
        rows=len(value.refusals),
    )


def run_plan(
    request: PlanRequest,
    ctx: RunContext,
    deps: SyncDependencies,
) -> OperationResult:
    """Scan, plan, observe, and preflight without persisting preview state."""

    if type(request) is not PlanRequest:
        raise TypeError("plan workflow requires an exact PlanRequest")
    request_id = request.request_id
    source_path = request.source_path
    target_path = request.target_path
    request_options = request.options
    if any(
        type(value) is not str
        for value in (
            request_id,
            source_path,
            target_path,
        )
    ):
        raise TypeError("plan request text fields must be exact strings")
    run_id = validated_run_id(request_id)
    source_root, target_root = _validated_roots(
        source_path,
        target_path,
    )
    admission = PlanReviewAdmission()
    try:
        live_options, retained_options = snapshot_plan_options(request_options)
        retained_request = PlanRequest(
            request_id,
            source_path,
            target_path,
            retained_options,
        )
        del request, request_id, source_path, target_path, request_options

        ctx.emit(PhaseChanged("scan-source"))
        source_stage = admission.fork()
        source_ignores = _snapshot_ignore_set(deps.ignores, source_stage)
        raw_source_scan = deps.scanner(
            Root(source_root.path, source_root.root_id),
            source_ignores,
            ctx,
            review_admission=source_stage,
        )
        source_capture = source_stage.fork()
        source_scan = _snapshot_scanner_result(
            raw_source_scan,
            source_root,
            source_capture,
            logical_source=True,
        )
        del (
            raw_source_scan,
            source_ignores,
            source_stage,
            source_capture,
        )
        admit_retained_plan_scan(source_scan, admission)

        ctx.emit(PhaseChanged("scan-target"))
        target_stage = admission.fork()
        target_ignores = _snapshot_ignore_set(deps.ignores, target_stage)
        raw_target_scan = deps.scanner(
            Root(target_root.path, target_root.root_id),
            target_ignores,
            ctx,
            review_admission=target_stage,
        )
        target_capture = target_stage.fork()
        target_scan = _snapshot_scanner_result(
            raw_target_scan,
            target_root,
            target_capture,
        )
        del (
            raw_target_scan,
            target_ignores,
            target_stage,
            target_capture,
            source_root,
            target_root,
        )
        admit_retained_plan_scan(target_scan, admission)

        ctx.emit(PhaseChanged("plan"))
        correspondence_stage = admission.fork()
        correspondence_source = _snapshot_plan_scan_copy(
            source_scan,
            correspondence_stage,
            logical_source=True,
        )
        correspondence_target = _snapshot_plan_scan_copy(
            target_scan,
            correspondence_stage,
        )
        raw_correspondence = deps.correspondence(
            correspondence_source,
            correspondence_target,
            review_admission=correspondence_stage,
        )
        correspondence_capture = correspondence_stage.fork()
        correspondence = snapshot_mapping_snapshot(
            raw_correspondence,
            review_admission=correspondence_capture,
        )
        del (
            raw_correspondence,
            correspondence_source,
            correspondence_target,
            correspondence_stage,
            correspondence_capture,
        )

        planner_stage = admission.fork()
        admit_plan_mapping_copy(correspondence, planner_stage)
        planner_source = _snapshot_plan_scan_copy(
            source_scan,
            planner_stage,
            logical_source=True,
        )
        planner_target = _snapshot_plan_scan_copy(
            target_scan,
            planner_stage,
        )
        planner_correspondence = snapshot_mapping_snapshot(
            correspondence,
            review_admission=planner_stage,
        )
        del correspondence
        raw_plan = deps.planner(
            planner_source,
            planner_target,
            planner_correspondence,
            live_options,
            Scope.everything(),
            review_admission=planner_stage,
        )
        plan_capture = planner_stage.fork()
        plan = snapshot_plan_candidate(
            raw_plan,
            source_scan,
            target_scan,
            retained_options,
            review_admission=plan_capture,
            retain_rows=False,
        )
        del (
            raw_plan,
            planner_source,
            planner_target,
            planner_correspondence,
            planner_stage,
            plan_capture,
            live_options,
        )
        admit_retained_plan_candidate(plan, admission)

        selection_stage = admission.fork()
        raw_selection = derive_plan_review_selection(
            plan,
            review_admission=selection_stage,
        )
        selection_capture = selection_stage.fork()
        selection = _snapshot_plan_selection(
            raw_selection,
            selection_capture,
        )
        del raw_selection, selection_stage, selection_capture
        review_stage = admission.fork()
        _admit_plan_selection_shape(selection, review_stage)
        allowed_paths, allowed_parents = _plan_observation_scope(
            plan,
            selection,
            review_stage,
        )

        ctx.emit(PhaseChanged("review-preflight"))
        observer_stage = review_stage.fork()
        observer_preview = _disposable_plan_preview(
            plan,
            source_scan,
            target_scan,
            retained_options,
            selection,
            run_id,
            observer_stage,
        )
        raw_world = deps.observer(
            observer_preview,
            deps.observation_fs,
            review_admission=observer_stage,
        )
        world_capture = observer_stage.fork()
        world = _snapshot_plan_observed_world(
            raw_world,
            plan,
            allowed_paths,
            allowed_parents,
            world_capture,
        )
        del raw_world, observer_preview, observer_stage, world_capture
        _admit_plan_observed_world_shape(world, admission)
        _admit_plan_observed_world_shape(world, review_stage)

        preflight_stage = review_stage.fork()
        preflight_preview = _disposable_plan_preview(
            plan,
            source_scan,
            target_scan,
            retained_options,
            selection,
            run_id,
            preflight_stage,
        )
        preflight_world = _snapshot_plan_observed_world(
            world,
            plan,
            allowed_paths,
            allowed_parents,
            preflight_stage,
            allow_owned_mappings=True,
        )
        preflight_stats_owner = preflight_world.stats
        preflight_paths_owner = preflight_world.paths
        preflight_roots_owner = preflight_world.roots
        raw_verdict = deps.preflight(
            preflight_preview,
            preflight_world,
            review_admission=preflight_stage,
        )
        verdict_capture = preflight_stage.fork()
        verdict = _snapshot_plan_verdict(
            raw_verdict,
            preflight_world,
            preflight_stats_owner,
            preflight_paths_owner,
            preflight_roots_owner,
            world,
            plan,
            allowed_paths,
            allowed_parents,
            selection,
            verdict_capture,
        )
        del (
            raw_verdict,
            preflight_preview,
            preflight_world,
            preflight_stats_owner,
            preflight_paths_owner,
            preflight_roots_owner,
            preflight_stage,
            verdict_capture,
            review_stage,
            selection,
            allowed_paths,
            allowed_parents,
        )
        _admit_retained_plan_verdict(verdict, admission)
        del world, retained_options, run_id
        artifact = PlanArtifact(
            retained_request,
            source_scan,
            target_scan,
            plan,
            verdict,
        )
    except ReviewFactLimitError as error:
        return _review_limit_refusal(error)

    del (
        retained_request,
        source_scan,
        target_scan,
        plan,
        verdict,
        admission,
    )
    deps.save_plan(artifact)
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

    if isinstance(continuation, VerifyContinuation):
        continuation = _exact_verify_continuation(continuation)
    current: list[ExecutionContinuation] = [
        ExecuteContinuation(continuation)
        if isinstance(continuation, ExecutionSet)
        else continuation
    ]
    downstream_sink = continuation_sink or (lambda value: None)

    def capture(value: ExecutionContinuation) -> None:
        current[0] = value
        downstream_sink(value)

    recording_factory = getattr(deps, "open_recording", None)
    if recording_factory is None:
        result = _run_execution(
            continuation,
            ctx,
            deps,
            continuation_sink=capture,
            resumed=resumed,
        )
        return _result_with_execution_recording(
            result,
            current[0].execution_set,
        )
    boundary = _RecordingBoundary(recording_factory)

    def preserve_exit_failure(error: BaseException) -> None:
        if boundary.exit_error is None:
            return
        active = current[0]
        try:
            _note_task_recording_issue(
                active.execution_set,
                TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
                boundary.exit_error,
            )
            if isinstance(active, VerifyContinuation):
                if active.recording is RecordingStatus.OK:
                    active = replace(active, recording=RecordingStatus.DEGRADED)
            capture(active)
        except Exception as continuation_error:
            failure = _recording_failure_detail(continuation_error)
            error.add_note(
                "recording degradation continuation capture also failed: "
                f"{failure.type_name}: {failure.message}"
            )
        failure = _recording_failure_detail(boundary.exit_error)
        error.add_note(
            "recording context exit also failed: "
            f"{failure.type_name}: {failure.message}"
        )

    try:
        result = _run_execution(
            continuation,
            ctx,
            deps,
            continuation_sink=capture,
            resumed=resumed,
            open_recording=boundary.open,
        )
    except PauseRequested as error:
        preserve_exit_failure(error)
        raise
    except Canceled:
        result = _recording_entry_canceled_result(
            current[0], ctx, deps
        )
        return _result_with_execution_recording(
            result,
            current[0].execution_set,
        )
    except BaseException as error:
        preserve_exit_failure(error)
        if boundary.enter_error is None or error is not boundary.enter_error:
            raise
        current = (
            ExecuteContinuation(continuation)
            if isinstance(continuation, ExecutionSet)
            else continuation
        )
        result = _recording_open_failure_result(current, ctx, deps, error)
        return _result_with_execution_recording(
            result,
            current.execution_set,
        )
    if boundary.exit_error is None:
        return _result_with_execution_recording(
            result,
            current[0].execution_set,
        )
    execution_set = (
        continuation
        if isinstance(continuation, ExecutionSet)
        else continuation.execution_set
    )
    _note_task_recording_issue(
        execution_set,
        TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
        boundary.exit_error,
    )
    result = replace(
        result,
        recording=RecordingStatus.DEGRADED,
        error=(
            result.error
            if result.error is not None
            else _recording_failure_detail(boundary.exit_error)
        ),
    )
    return _result_with_execution_recording(result, execution_set)


def _run_execution(
    continuation: ExecutionContinuation | ExecutionSet,
    ctx: RunContext,
    deps: SyncDependencies,
    *,
    continuation_sink: Callable[[ExecutionContinuation], None] | None = None,
    resumed: bool = False,
    open_recording: (
        Callable[[ExecutionSet], AbstractContextManager[RunRecording]] | None
    ) = None,
) -> OperationResult:

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
        return _settle_fresh_execute_boundary(
            current,
            ctx,
            (),
            error=FailureDetail(type(error).__name__, logical_error_text(error)),
        )
    if commitment_error is not None:
        try:
            deps.save_execution_details(
                ExecutionDetails(
                    str(xset.run_id),
                    commitment_error=commitment_error,
                )
            )
        except PauseRequested:
            raise
        except Canceled:
            if isinstance(current, VerifyContinuation) or resumed:
                return settle_canceled_execution(
                    current,
                    Disposition.RAN,
                    deps,
                )
            return _settle_fresh_execute_boundary(
                current,
                ctx,
                exclusion_items,
                status=SessionState.CANCELED,
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
            return _settle_fresh_execute_boundary(
                current,
                ctx,
                exclusion_items,
                error=FailureDetail(
                    type(error).__name__, logical_error_text(error)
                ),
            )
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
    except PauseRequested:
        raise
    except Canceled:
        if isinstance(current, VerifyContinuation) or resumed:
            return settle_canceled_execution(
                current,
                Disposition.RAN,
                deps,
            )
        return _settle_fresh_execute_boundary(
            current,
            ctx,
            exclusion_items,
            status=SessionState.CANCELED,
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
        return _settle_fresh_execute_boundary(
            current,
            ctx,
            exclusion_items,
            error=FailureDetail(type(error).__name__, logical_error_text(error)),
        )
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
        ctx.emit(body)
        if isinstance(body, ItemOutcome):
            emitted_execution_items.append(body)

    recording_factory = open_recording or deps.open_recording
    with recording_factory(xset) as recording:
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
                xset,
                filesystem_status,
                recording_status,
            )
            return finished_recording

        if isinstance(current, ExecuteContinuation):
            verify_after_execute = current.verify_after_execute
            accepted_exclusions: list[ItemOutcome] = []
            exclusion_error: Exception | None = None

            def emit_exclusions() -> None:
                nonlocal exclusion_error
                if exclusion_error is not None:
                    raise exclusion_error
                for item in exclusion_items[len(accepted_exclusions):]:
                    try:
                        ctx.emit(item)
                    except (PauseRequested, Canceled):
                        raise
                    except Exception as error:
                        # Failed projection retains the first sink error without
                        # replaying accepted siblings or re-offering this failure.
                        exclusion_error = error
                        raise
                    accepted_exclusions.append(item)

            def failed_execution_result(error: Exception) -> OperationResult:
                recording_status = finish_once(
                    SessionState.FAILED,
                    xset.recording,
                )
                try:
                    emit_exclusions()
                except (PauseRequested, Canceled):
                    raise
                except Exception as emission_error:
                    error = emission_error
                execution_items = _merge_operation_results(
                    xset.plan,
                    tuple(emitted_execution_items),
                    tuple(accepted_exclusions),
                )
                failure = _recording_failure_detail(error)
                phase = _execute_continuation_phase(
                    xset,
                    PhaseStatus.FAILED,
                    f"{failure.type_name}: {failure.message}",
                )
                return OperationResult(
                    status=SessionState.FAILED,
                    recording=recording_status,
                    disposition=Disposition.RAN,
                    items=execution_items,
                    phases=(phase,) if verify_after_execute else (),
                    bytes_done=phase.bytes_done,
                    bytes_total=phase.bytes_total or phase.bytes_done,
                    error=failure,
                )

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
                emit_exclusions()
                result = replace(
                    result,
                    items=_merge_operation_results(
                        xset.plan, result.items, tuple(accepted_exclusions)
                    ),
                )
                execution_items = result.items
                execution_recording = _combined_recording(
                    xset.recording,
                    result.recording,
                )
                result = replace(result, recording=execution_recording)
                if not verify_after_execute:
                    recording_status = finish_once(
                        result.status,
                        execution_recording,
                    )
                    return replace(result, recording=recording_status)

                result = _normalize_execute_result_diagnostics(xset, result)
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
                del result
                sink(current)
            except PauseRequested:
                raise
            except Canceled:
                try:
                    emit_exclusions()
                except (PauseRequested, Canceled):
                    raise
                except Exception as error:
                    return failed_execution_result(error)
                execution_items = _merge_operation_results(
                    xset.plan,
                    tuple(emitted_execution_items),
                    tuple(accepted_exclusions),
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
                return failed_execution_result(error)

        observed_recording = [current.recording]
        verification_items: list[IntegrityOutcome] = []
        observed_verification_ids = set(current.candidates.completed_bytes)
        verification_candidate_ids = {
            candidate.item_id for candidate in current.candidates.candidates
        }

        def observe_verification(body: object) -> None:
            if not isinstance(body, IntegrityOutcome):
                ctx.emit(body)
                return
            # A degraded recording snapshot can fail.  Publish it before the
            # reliable item so a raised sink error cannot leave the reporter
            # unable to tell whether downstream accepted that item.
            if (
                body.recording is RecordingStatus.DEGRADED
                and observed_recording[0] is RecordingStatus.OK
            ):
                observed_recording[0] = RecordingStatus.DEGRADED
                sink(replace(current, recording=RecordingStatus.DEGRADED))
            ctx.emit(body)
            verification_items.append(body)
            if body.item_id in verification_candidate_ids:
                observed_verification_ids.add(body.item_id)

        try:
            progress_items_total, progress_bytes_total = (
                _verify_progress_totals(current)
            )
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
                post_copy_items_total=progress_items_total,
                post_copy_bytes_total=progress_bytes_total,
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
                items_done_floor=len(observed_verification_ids),
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
                items_done_floor=len(observed_verification_ids),
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
                items_done_floor=len(observed_verification_ids),
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
    if isinstance(continuation, VerifyContinuation):
        continuation = _exact_verify_continuation(continuation)

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

    boundary = _RecordingBoundary(deps.open_recording)
    recording_error: Exception | None = None
    try:
        with boundary.open(xset) as recording:
            recording_status = _finish_recording(
                recording,
                xset,
                filesystem_status,
                recording_status,
            )
    except Exception as error:
        recording_error = error
        _note_task_recording_issue(
            xset,
            TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
            boundary.enter_error or error,
        )
        recording_status = xset.recording
        recording_status = _finish_recording_without_open(
            deps,
            xset,
            filesystem_status,
            recording_status,
        )
    if boundary.exit_error is not None:
        recording_error = boundary.exit_error
        _note_task_recording_issue(
            xset,
            TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
            boundary.exit_error,
        )
        recording_status = xset.recording
    execute_phase = (
        phase
        if isinstance(continuation, ExecuteContinuation)
        else continuation.execute_phase
    )
    return OperationResult(
        status=filesystem_status,
        recording=recording_status,
        recording_issues=xset.recording_issues,
        omitted_detail_count=xset.omitted_detail_count,
        disposition=disposition,
        canceled=True,
        phases=phases,
        bytes_done=execute_phase.bytes_done,
        bytes_total=(
            execute_phase.bytes_total
            if execute_phase.bytes_total is not None
            else execute_phase.bytes_done
        ),
        error=(
            None
            if recording_error is None
            else _recording_failure_detail(recording_error)
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
    error_text = (
        None
        if result.error is None
        else f"{result.error.type_name}: {result.error.message}"
    )
    bounded_error = bounded_utf8_text(
        error_text,
        "verify continuation execute phase error",
    )
    if error_text is not None and bounded_error is None:
        _note_omitted_diagnostics(xset, 1)
    return PhaseResult(
        phase=ExecuteContinuation.phase,
        status=status,
        items_done=len(xset.status),
        items_total=len(xset.selection),
        bytes_done=result.bytes_done,
        bytes_total=result.bytes_total,
        error=bounded_error,
    )


def _normalize_execute_result_diagnostics(
    xset: ExecutionSet,
    result: OperationResult,
) -> OperationResult:
    if result.omitted_detail_count != xset.omitted_detail_count:
        raise ValueError(
            "executor result omitted detail count disagrees with execution set"
        )
    normalized = normalize_result_diagnostics(result)
    _note_omitted_diagnostics(
        xset,
        normalized.omitted_detail_count - result.omitted_detail_count,
    )
    return normalized


def _note_omitted_diagnostics(xset: ExecutionSet, count: int) -> None:
    if not count:
        return
    xset.omitted_detail_count = require_safe_int(
        xset.omitted_detail_count + count,
        "execution omitted_detail_count",
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
    committed_bytes = sum(
        operation.content_bytes
        for operation in xset.plan.operations
        if xset.status.get(operation.op_id) is Outcome.SUCCEEDED
        and operation.kind in _BYTE_PRODUCING_KINDS
    )
    bytes_done = max(committed_bytes, xset.bytes_done_high_water)
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
    items_done_floor: int = 0,
    incomplete: bool = False,
    canceled: bool = False,
    error: str | None = None,
) -> PhaseResult:
    if incomplete and canceled:
        raise ValueError("verify phase cannot be incomplete and canceled")
    candidates = continuation.candidates
    items_total, bytes_total = _verify_progress_totals(continuation)
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
        items_done=max(candidates.completed_count, items_done_floor),
        items_total=items_total,
        bytes_done=candidates.processed_bytes,
        bytes_total=bytes_total,
        error=error,
    )


def _verify_progress_totals(
    continuation: VerifyContinuation,
) -> tuple[int, int]:
    candidates = continuation.candidates
    bytes_total = candidates.physical_bytes_total(
        _missing_evidence_bytes(continuation)
    )
    return (
        (
            len(candidates.candidates)
            + len(continuation.missing_evidence_ids)
        ),
        bytes_total,
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


def _settle_fresh_execute_boundary(
    continuation: ExecuteContinuation,
    ctx: RunContext,
    exclusion_items: tuple[ItemOutcome, ...],
    *,
    status: SessionState = SessionState.FAILED,
    error: FailureDetail | None = None,
) -> OperationResult:
    """Project pre-executor truth without consulting a lossy snapshot."""

    if status not in {SessionState.FAILED, SessionState.CANCELED}:
        raise ValueError("fresh execute boundary must fail or cancel")
    if status is SessionState.FAILED and error is None:
        raise ValueError("fresh execute failure requires an error")
    emitted_items = exclusion_items
    try:
        _emit_items(ctx, exclusion_items)
    except Exception as emit_error:
        emitted_items = ()
        if error is None:
            error = FailureDetail(
                type(emit_error).__name__,
                logical_error_text(emit_error),
            )
        else:
            error = FailureDetail(
                error.type_name,
                f"{error.message}; outcome emission also failed: "
                f"{type(emit_error).__name__}: {logical_error_text(emit_error)}",
            )
    phase = _execute_continuation_phase(
        continuation.execution_set,
        (
            PhaseStatus.CANCELED
            if status is SessionState.CANCELED
            else PhaseStatus.FAILED
        ),
        None if error is None else f"{error.type_name}: {error.message}",
    )
    return OperationResult(
        status=status,
        recording=continuation.execution_set.recording,
        disposition=Disposition.UNRUN,
        canceled=status is SessionState.CANCELED,
        items=emitted_items,
        bytes_done=phase.bytes_done,
        bytes_total=(
            phase.bytes_total
            if phase.bytes_total is not None
            else phase.bytes_done
        ),
        error=error,
    )


def _recording_open_failure_result(
    continuation: ExecutionContinuation,
    ctx: RunContext,
    deps: SyncDependencies,
    error: BaseException,
) -> OperationResult:
    """Project an unavailable run recording from authoritative continuation."""

    xset = continuation.execution_set
    _note_task_recording_issue(
        xset,
        TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
        error,
    )
    failure = _recording_failure_detail(error)
    if isinstance(continuation, VerifyContinuation):
        _finish_recording_without_open(
            deps,
            xset,
            continuation.filesystem_status,
            xset.recording,
        )
        phase = _verify_phase(
            continuation,
            incomplete=True,
            error=f"{failure.type_name}: {failure.message}",
        )
        return OperationResult(
            status=continuation.filesystem_status,
            recording=RecordingStatus.DEGRADED,
            disposition=Disposition.RAN,
            phases=(continuation.execute_phase, phase),
            bytes_done=continuation.execute_phase.bytes_done,
            bytes_total=(
                continuation.execute_phase.bytes_total
                if continuation.execute_phase.bytes_total is not None
                else continuation.execute_phase.bytes_done
            ),
            error=failure,
        )

    _finish_recording_without_open(
        deps,
        xset,
        SessionState.FAILED,
        RecordingStatus.DEGRADED,
    )
    try:
        decision = derive_execution_selection(
            xset.plan,
            user_deselected=xset.user_deselected,
        )
        exclusion_items = _exclusion_items(xset.plan, decision)
        _emit_items(ctx, exclusion_items)
    except Exception as emit_error:
        emit_failure = _recording_failure_detail(emit_error)
        error_context = f"{emit_failure.type_name}: {emit_failure.message}"
        phase_error = (
            f"{failure.type_name}: {failure.message}; "
            f"outcome emission also failed: {error_context}"
        )
        exclusion_items = ()
    else:
        phase_error = f"{failure.type_name}: {failure.message}"
    phase = _execute_continuation_phase(
        xset,
        PhaseStatus.FAILED,
        phase_error,
    )
    return OperationResult(
        status=SessionState.FAILED,
        recording=RecordingStatus.DEGRADED,
        disposition=Disposition.RAN,
        items=exclusion_items,
        phases=(phase,) if continuation.verify_after_execute else (),
        bytes_done=phase.bytes_done,
        bytes_total=(
            phase.bytes_total
            if phase.bytes_total is not None
            else phase.bytes_done
        ),
        error=failure,
    )


def _recording_entry_canceled_result(
    continuation: ExecutionContinuation,
    ctx: RunContext,
    deps: SyncDependencies,
) -> OperationResult:
    """Settle entry-time cancellation without reopening the recording owner."""

    xset = continuation.execution_set
    emitted_items: list[ItemOutcome] = []
    emission_error: FailureDetail | None = None
    if isinstance(continuation, ExecuteContinuation):
        try:
            decision = derive_execution_selection(
                xset.plan,
                user_deselected=xset.user_deselected,
            )
            for item in _exclusion_items(xset.plan, decision):
                ctx.emit(item)
                emitted_items.append(item)
        except Exception as error:
            emission_error = FailureDetail(
                type(error).__name__,
                logical_error_text(error),
            )
        phase = _execute_continuation_phase(
            xset,
            PhaseStatus.CANCELED,
            "execution canceled while entering run recording",
        )
        phases = (phase,) if continuation.verify_after_execute else ()
        filesystem_status = SessionState.CANCELED
        recording_status = xset.recording
        execute_phase = phase
    else:
        phase = _verify_phase(
            continuation,
            canceled=True,
            error="verification canceled while entering run recording",
        )
        phases = (continuation.execute_phase, phase)
        filesystem_status = continuation.filesystem_status
        recording_status = _combined_recording(
            xset.recording,
            continuation.recording,
        )
        execute_phase = continuation.execute_phase
    recording_status = _finish_recording_without_open(
        deps,
        xset,
        filesystem_status,
        recording_status,
    )
    return OperationResult(
        status=filesystem_status,
        recording=recording_status,
        disposition=Disposition.RAN,
        canceled=True,
        items=tuple(emitted_items),
        phases=phases,
        bytes_done=execute_phase.bytes_done,
        bytes_total=(
            execute_phase.bytes_total
            if execute_phase.bytes_total is not None
            else execute_phase.bytes_done
        ),
        error=emission_error,
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
        phases=(phase,) if continuation.verify_after_execute else (),
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
        except Exception as error:
            _note_task_recording_issue(
                xset,
                TaskRecordingIssueReason.FINISH_FAILED,
                error,
            )
        return _combined_recording(recording_status, xset.recording)
    boundary = _RecordingBoundary(deps.open_recording)
    try:
        with boundary.open(xset) as recording:
            recording_status = _finish_recording(
                recording,
                xset,
                status,
                recording_status,
            )
    except Exception as error:
        _note_task_recording_issue(
            xset,
            TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
            boundary.enter_error or error,
        )
    if boundary.exit_error is not None:
        _note_task_recording_issue(
            xset,
            TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
            boundary.exit_error,
        )
    return _combined_recording(recording_status, xset.recording)


def _finish_recording_without_open(
    deps: SyncDependencies,
    xset: ExecutionSet,
    status: SessionState,
    recording_status: RecordingStatus,
) -> RecordingStatus:
    finisher = getattr(deps, "finish_existing_recording", None)
    if finisher is None:
        return _combined_recording(recording_status, xset.recording)
    try:
        finisher(xset, status, recording_status)
    except Exception as error:
        _note_task_recording_issue(
            xset,
            TaskRecordingIssueReason.FINISH_FAILED,
            error,
        )
    return _combined_recording(recording_status, xset.recording)


def _finish_recording(
    recording: RunRecording,
    xset: ExecutionSet,
    status: SessionState,
    recording_status: RecordingStatus,
) -> RecordingStatus:
    try:
        recording.finish(status, recording_status)
    except Exception as error:
        _note_task_recording_issue(
            xset,
            TaskRecordingIssueReason.FINISH_FAILED,
            error,
        )
    return _combined_recording(recording_status, xset.recording)


def _note_task_recording_issue(
    xset: ExecutionSet,
    reason: TaskRecordingIssueReason,
    error: BaseException,
) -> None:
    issue = TaskRecordingIssue(reason)
    message = _recording_error_message(error)
    xset.note_task_recording_issue(
        issue.reason,
        None if message is None else f"{type(error).__name__}: {message}",
    )


def _recording_error_message(error: BaseException) -> str | None:
    try:
        return logical_error_text(error)
    except Exception:
        return None


def _recording_failure_detail(error: BaseException) -> FailureDetail:
    message = _recording_error_message(error)
    return FailureDetail(
        type(error).__name__,
        "recording diagnostic unavailable" if message is None else message,
    )


def _result_with_execution_recording(
    result: OperationResult,
    xset: ExecutionSet,
) -> OperationResult:
    """Attach the centrally reduced item/task recording witnesses."""

    return replace(
        result,
        recording=_combined_recording(result.recording, xset.recording),
        recording_issues=xset.recording_issues,
        omitted_detail_count=xset.omitted_detail_count,
    )


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
