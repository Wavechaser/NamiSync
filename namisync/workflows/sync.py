"""Top-to-bottom M0 reviewed sync workflows."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from namisync.core.exception_graph import retire_exception_graph
from namisync.core.events import ItemOutcome, PhaseChanged, snapshot_item_outcome
from namisync.core.evidence import Outcome, RecordingStatus, snapshot_attestation
from namisync.core.execution import (
    ExecutionOperationFact,
    ExecutionSet,
    ExecutionSetAuthority,
    ExecutorFileSystem,
    ItemRecordingReason,
    PublishedCopyEvidence,
    Recorder,
    TaskRecordingIssue,
    TaskRecordingIssueReason,
    revalidate_execution_set_authority,
    snapshot_execution_set_authority,
    validated_run_id,
)
from namisync.core.integrity import (
    IntegrityOutcome,
    IntegrityRecorder,
    IntegrityRunResult,
    PostCopyCandidate,
    PostCopyCandidateFact,
    PostCopyRecordIdentity,
    PostCopySelection,
    PostCopySelectionAuthority,
    VerifierContext,
    bind_verifier_context,
    revalidate_post_copy_selection_authority,
    snapshot_integrity_outcome,
    snapshot_post_copy_selection_authority,
    validate_integrity_run_result,
)
from namisync.core.models import (
    IgnoreSet,
    Root,
    ScanResult,
    ScanScope,
    snapshot_ignore_set,
)
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
from namisync.core.preflight import (
    ObservedWorld,
    Verdict,
)
from namisync.core.review import (
    PlanReviewAdmission,
    ReviewFactLimitExceeded,
    ReviewFactLimitError,
    admit_retained_plan_scan,
    consume_plan_review_fact_limit,
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
    bounded_utf8_text,
    require_safe_int,
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
    snapshot_operation_result,
)
from namisync.modules.executor import ExecutorPolicies
from namisync.modules.planner import (
    admit_retained_plan_candidate,
    snapshot_mapping_snapshot,
    snapshot_plan_candidate,
    snapshot_plan_options,
)
from namisync.modules.preflight import (
    ObservationFileSystem,
    admit_retained_plan_observed_world,
    admit_retained_plan_verdict,
    snapshot_plan_observed_world,
    snapshot_plan_verdict,
)

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
)


class CompoundRecorder(Recorder, IntegrityRecorder, Protocol):
    """One run-bound writer exposed through both narrow recorder protocols."""


class RunRecording(Protocol):
    recorder: CompoundRecorder

    def finish(
        self, status: SessionState, recording: RecordingStatus
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class _ClosedRecordingFailure:
    detail: FailureDetail
    issue_detail: str | None


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
            self._boundary.enter_failure = _close_recording_failure(error)
            raise

    def __exit__(self, exc_type, exc, traceback) -> bool:
        try:
            revalidate = self._boundary.snapshot_exit_revalidator()
        except Exception as error:
            if self._boundary.integrity_failure is None:
                self._boundary.integrity_failure = _retired_failure_detail(error)
            revalidate = lambda: None
        try:
            suppressed = self._context.__exit__(exc_type, exc, traceback)
        except Exception as error:
            self._boundary.exit_failure = _close_recording_failure(error)
            suppressed = False
        try:
            revalidate()
        except Exception as error:
            if self._boundary.integrity_failure is None:
                self._boundary.integrity_failure = _retired_failure_detail(error)
        is_suppressed = bool(suppressed)
        if is_suppressed and isinstance(exc, BaseException):
            retire_exception_graph(exc)
        return is_suppressed


class _RecordingBoundary:
    def __init__(
        self,
        factory: Callable[
            [ExecutionSet], AbstractContextManager[RunRecording]
        ],
        snapshot_exit_revalidator: (
            Callable[[], Callable[[], None]] | None
        ) = None,
    ) -> None:
        self._factory = factory
        self.snapshot_exit_revalidator = (
            snapshot_exit_revalidator or (lambda: lambda: None)
        )
        self.enter_failure: _ClosedRecordingFailure | None = None
        self.exit_failure: _ClosedRecordingFailure | None = None
        self.integrity_failure: FailureDetail | None = None

    def open(
        self, execution_set: ExecutionSet
    ) -> AbstractContextManager[RunRecording]:
        try:
            context = self._factory(execution_set)
        except (PauseRequested, Canceled):
            raise
        except Exception as error:
            self.enter_failure = _close_recording_failure(error)
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


def _review_limit_refusal(
    fact: ReviewFactLimitExceeded,
) -> OperationResult:
    return OperationResult(
        status=SessionState.REFUSED,
        disposition=Disposition.UNRUN,
        review_fact_limit=fact,
    )


def _snapshot_scanner_result(
    value: ScanResult,
    expected_root: Root,
    admission: PlanReviewAdmission,
) -> ScanResult:
    snapshot = snapshot_plan_scan_result(value, admission)
    if snapshot.root != expected_root:
        raise ValueError("plan scanner returned a different root authority")
    if snapshot.scope != ScanScope.full():
        raise ValueError("plan scanner must return the requested full scope")
    return snapshot


def _disposable_plan_preview(
    plan: Plan,
    source: ScanResult,
    target: ScanResult,
    options: SyncOptions,
    selection: frozenset[str],
    run_id: str,
    review_admission: PlanReviewAdmission,
) -> ExecutionSet:
    """Detach the mutable execution shell and its plan for one collaborator."""

    return ExecutionSet(
        snapshot_plan_candidate(
            plan,
            source,
            target,
            options,
            review_admission=review_admission,
        ),
        selection,
        run_id,
    )


def _run_plan(
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
    retained_admission = PlanReviewAdmission()
    review_limit_fact: ReviewFactLimitExceeded | None = None
    invalid_review_limit = False
    unadmitted_review_limit = False
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
        source_ignores = snapshot_ignore_set(deps.ignores)
        raw_source_scan = deps.scanner(
            Root(source_root.path, source_root.root_id),
            source_ignores,
            ctx,
            review_admission=retained_admission.fresh(),
        )
        source_scan = _snapshot_scanner_result(
            raw_source_scan,
            source_root,
            retained_admission.fresh(),
        )
        del raw_source_scan, source_ignores
        admit_retained_plan_scan(source_scan, retained_admission)

        ctx.emit(PhaseChanged("scan-target"))
        target_ignores = snapshot_ignore_set(deps.ignores)
        raw_target_scan = deps.scanner(
            Root(target_root.path, target_root.root_id),
            target_ignores,
            ctx,
            review_admission=retained_admission.fresh(),
        )
        target_scan = _snapshot_scanner_result(
            raw_target_scan,
            target_root,
            retained_admission.fresh(),
        )
        del raw_target_scan, target_ignores, source_root, target_root
        admit_retained_plan_scan(target_scan, retained_admission)

        ctx.emit(PhaseChanged("plan"))
        correspondence_source = snapshot_plan_scan_result(
            source_scan,
            retained_admission.fresh(),
        )
        correspondence_target = snapshot_plan_scan_result(
            target_scan,
            retained_admission.fresh(),
        )
        raw_correspondence = deps.correspondence(
            correspondence_source,
            correspondence_target,
        )
        correspondence = snapshot_mapping_snapshot(
            raw_correspondence,
            review_admission=retained_admission.fresh(),
        )
        del raw_correspondence, correspondence_source, correspondence_target

        planner_source = snapshot_plan_scan_result(
            source_scan,
            retained_admission.fresh(),
        )
        planner_target = snapshot_plan_scan_result(
            target_scan,
            retained_admission.fresh(),
        )
        raw_plan = deps.planner(
            planner_source,
            planner_target,
            correspondence,
            live_options,
            Scope.everything(),
            review_admission=retained_admission.fresh(),
        )
        plan = snapshot_plan_candidate(
            raw_plan,
            source_scan,
            target_scan,
            retained_options,
            review_admission=retained_admission.fresh(),
        )
        del (
            raw_plan,
            planner_source,
            planner_target,
            correspondence,
            live_options,
        )
        admit_retained_plan_candidate(plan, retained_admission)

        decision = derive_execution_selection(plan)
        selection = decision.selection
        del decision
        authoritative_xset = ExecutionSet(plan, selection, run_id)

        ctx.emit(PhaseChanged("review-preflight"))
        observer_preview = _disposable_plan_preview(
            plan,
            source_scan,
            target_scan,
            retained_options,
            selection,
            run_id,
            retained_admission.fresh(),
        )
        raw_world = deps.observer(
            observer_preview,
            deps.observation_fs,
            review_admission=retained_admission.fresh(),
        )
        world = snapshot_plan_observed_world(
            raw_world,
            authoritative_xset,
            retained_admission.fresh(),
        )
        del raw_world, observer_preview
        admit_retained_plan_observed_world(world, retained_admission)

        preflight_preview = _disposable_plan_preview(
            plan,
            source_scan,
            target_scan,
            retained_options,
            selection,
            run_id,
            retained_admission.fresh(),
        )
        preflight_world = snapshot_plan_observed_world(
            world,
            authoritative_xset,
            retained_admission.fresh(),
        )
        raw_verdict = deps.preflight(
            preflight_preview,
            preflight_world,
            review_admission=retained_admission.fresh(),
        )
        verdict = snapshot_plan_verdict(
            raw_verdict,
            preflight_world,
            world,
            authoritative_xset,
            retained_admission.fresh(),
        )
        del (
            raw_verdict,
            preflight_preview,
            preflight_world,
            authoritative_xset,
            selection,
            world,
            retained_options,
            run_id,
        )
        admit_retained_plan_verdict(verdict, retained_admission)
        artifact = PlanArtifact(
            retained_request,
            source_scan,
            target_scan,
            plan,
            verdict,
        )
    except ReviewFactLimitError as error:
        if type(error) is not ReviewFactLimitError:
            invalid_review_limit = True
        else:
            try:
                review_limit_fact = consume_plan_review_fact_limit(
                    error,
                    retained_admission,
                )
                unadmitted_review_limit = review_limit_fact is None
            except (AttributeError, TypeError, ValueError) as fact_error:
                retire_exception_graph(fact_error)
                invalid_review_limit = True
        retire_exception_graph(error)

    if invalid_review_limit:
        raise RuntimeError("plan review limit failure is invalid")
    if unadmitted_review_limit:
        raise RuntimeError("unadmitted collaborator raised a review fact limit")
    if review_limit_fact is not None:
        return _review_limit_refusal(review_limit_fact)

    del (
        retained_request,
        source_scan,
        target_scan,
        plan,
        verdict,
        retained_admission,
    )
    deps.save_plan(artifact)
    return OperationResult(status=SessionState.COMPLETED)


def run_plan(
    request: PlanRequest,
    ctx: RunContext,
    deps: SyncDependencies,
) -> OperationResult:
    """Run planning after retiring rejected phase traceback links."""

    try:
        return _run_plan(request, ctx, deps)
    except BaseException as error:
        retire_exception_graph(error)
        del request, ctx, deps
        raise


def _recording_integrity_failure_result(
    result: OperationResult,
    failure: FailureDetail,
    authority: ExecutionSetAuthority,
    *,
    verification: bool,
    filesystem_status: SessionState,
) -> OperationResult:
    """Project terminal truth captured before a hostile recording mutation."""

    phase_name = VerifyContinuation.phase if verification else ExecuteContinuation.phase
    phase_status = PhaseStatus.INCOMPLETE if verification else PhaseStatus.FAILED
    phase_error = f"{failure.type_name}: {failure.message}"
    phases = tuple(
        replace(
            phase,
            status=phase_status,
            error=phase_error,
        )
        if phase.phase == phase_name
        else phase
        for phase in result.phases
    )
    return replace(
        result,
        status=filesystem_status,
        canceled=False,
        phases=phases,
        error=failure,
        recording_issues=authority.recording_issues,
        omitted_detail_count=authority.omitted_detail_count,
    )


def _run_execution_with_recording(
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
    pre_exit_execution_authority: list[ExecutionSetAuthority | None] = [None]
    downstream_sink = continuation_sink or (lambda value: None)

    def capture(value: ExecutionContinuation) -> None:
        current[0] = value
        downstream_sink(value)

    def snapshot_recording_exit_revalidator() -> Callable[[], None]:
        active = current[0]
        execution_authority = snapshot_execution_set_authority(
            active.execution_set
        )
        pre_exit_execution_authority[0] = execution_authority
        candidate_authority = (
            snapshot_post_copy_selection_authority(active.candidates)
            if isinstance(active, VerifyContinuation)
            else None
        )

        def revalidate() -> None:
            revalidate_execution_set_authority(
                active.execution_set,
                execution_authority,
                allow_progress=False,
            )
            if candidate_authority is not None:
                revalidate_post_copy_selection_authority(
                    active.candidates,
                    candidate_authority,
                    allow_progress=False,
                )

        return revalidate

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
    boundary = _RecordingBoundary(
        recording_factory,
        snapshot_recording_exit_revalidator,
    )

    def capture_recording_integrity_failure(
        failure: FailureDetail,
        authority: ExecutionSetAuthority,
    ) -> None:
        if boundary.integrity_failure is None:
            boundary.integrity_failure = failure
        pre_exit_execution_authority[0] = authority

    def preserve_exit_failure(error: BaseException) -> None:
        if boundary.exit_failure is None:
            return
        retire_exception_graph(error)

        active = current[0]
        try:
            _note_closed_recording_issue(
                active.execution_set,
                TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
                boundary.exit_failure,
            )
            if isinstance(active, VerifyContinuation):
                if active.recording is RecordingStatus.OK:
                    active = replace(active, recording=RecordingStatus.DEGRADED)
            capture(active)
        except Exception as continuation_error:
            failure = _recording_failure_detail(continuation_error)
            _try_add_exception_note(
                error,
                "recording degradation continuation capture also failed: "
                f"{failure.type_name}: {failure.message}",
            )
        failure = boundary.exit_failure.detail
        _try_add_exception_note(
            error,
            "recording context exit also failed: "
            f"{failure.type_name}: {failure.message}",
        )

    try:
        result = _run_execution(
            continuation,
            ctx,
            deps,
            continuation_sink=capture,
            resumed=resumed,
            open_recording=boundary.open,
            recording_integrity_sink=capture_recording_integrity_failure,
        )
    except PauseRequested as error:
        preserve_exit_failure(error)
        if boundary.integrity_failure is not None:
            failure = boundary.integrity_failure
            retire_exception_graph(error)
            raise RuntimeError(
                f"recording boundary changed continuation truth: "
                f"{failure.type_name}: {failure.message}"
            ) from None
        raise
    except Canceled as error:
        if boundary.integrity_failure is not None:
            failure = boundary.integrity_failure
            retire_exception_graph(error)
            raise RuntimeError(
                f"recording boundary changed continuation truth: "
                f"{failure.type_name}: {failure.message}"
            ) from None
        retire_exception_graph(error)
        result = _recording_entry_canceled_result(
            current[0],
            ctx,
            deps,
            continuation_sink=capture,
        )
        return _result_with_execution_recording(
            result,
            current[0].execution_set,
        )
    except BaseException as error:
        preserve_exit_failure(error)
        if boundary.integrity_failure is not None:
            failure = boundary.integrity_failure
            _try_add_exception_note(
                error,
                "recording boundary also changed continuation truth: "
                f"{failure.type_name}: {failure.message}",
            )
        if boundary.enter_failure is None:
            raise
        retire_exception_graph(error)
        current = (
            ExecuteContinuation(continuation)
            if isinstance(continuation, ExecutionSet)
            else continuation
        )
        result = _recording_open_failure_result(
            current,
            ctx,
            deps,
            boundary.enter_failure,
            continuation_sink=capture,
        )
        return _result_with_execution_recording(
            result,
            current.execution_set,
        )
    if boundary.integrity_failure is not None:
        authority = pre_exit_execution_authority[0]
        if authority is None:
            failure = boundary.integrity_failure
            raise RuntimeError(
                f"recording boundary lost continuation truth: "
                f"{failure.type_name}: {failure.message}"
            )
        active = current[0]
        return _recording_integrity_failure_result(
            result,
            boundary.integrity_failure,
            authority,
            verification=isinstance(active, VerifyContinuation),
            filesystem_status=(
                active.filesystem_status
                if isinstance(active, VerifyContinuation)
                else SessionState.FAILED
            ),
        )
    if boundary.exit_failure is None:
        return _result_with_execution_recording(
            result,
            current[0].execution_set,
        )
    execution_set = (
        continuation
        if isinstance(continuation, ExecutionSet)
        else continuation.execution_set
    )
    _note_closed_recording_issue(
        execution_set,
        TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
        boundary.exit_failure,
    )
    result = replace(
        result,
        recording=RecordingStatus.DEGRADED,
        error=(
            result.error
            if result.error is not None
            else boundary.exit_failure.detail
        ),
    )
    return _result_with_execution_recording(result, execution_set)


def run_execution(
    continuation: ExecutionContinuation | ExecutionSet,
    ctx: RunContext,
    deps: SyncDependencies,
    *,
    continuation_sink: Callable[[ExecutionContinuation], None] | None = None,
    resumed: bool = False,
) -> OperationResult:
    """Execute while preserving identity after retiring phase traceback links."""

    try:
        return _run_execution_with_recording(
            continuation,
            ctx,
            deps,
            continuation_sink=continuation_sink,
            resumed=resumed,
        )
    except BaseException as error:
        retire_exception_graph(error)
        del continuation, ctx, deps, continuation_sink
        raise


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
    recording_integrity_sink: (
        Callable[[FailureDetail, ExecutionSetAuthority], None] | None
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
    retained_verification_authority: PostCopySelectionAuthority | None = None
    retained_execution_authority: ExecutionSetAuthority | None = None
    verification_handoff_error: BaseException | None = None
    if isinstance(current, VerifyContinuation):
        retained_verification_authority = (
            snapshot_post_copy_selection_authority(current.candidates)
        )
    sink = continuation_sink or (lambda value: None)
    xset = current.execution_set
    try:
        try:
            decision = derive_execution_selection(
                xset.plan,
                user_deselected=xset.user_deselected,
            )
        except (TypeError, ValueError) as error:
            failure = _retired_failure_detail(error)
            commitment_error = (
                "reviewed selection provenance is invalid: "
                f"{failure.type_name}: {failure.message}"
            )
            exclusion_items = ()
        else:
            commitment_error = (
                "carried selection does not match the authoritative derived selection"
                if decision.selection != xset.selection
                else _commitment_error(xset)
            )
            exclusion_items = _exclusion_items(xset.plan, decision)
            if isinstance(current, ExecuteContinuation):
                if current.reported_exclusion_count > len(exclusion_items):
                    commitment_error = (
                        "reported exclusion count exceeds the derived exclusions"
                    )
                elif not resumed and current.reported_exclusion_count:
                    commitment_error = (
                        "fresh execution cannot carry reported exclusions"
                    )
    except Exception as error:
        failure = _retired_failure_detail(error)
        if isinstance(current, VerifyContinuation):
            return _settle_verify_incomplete(
                current,
                deps,
                failure,
            )
        if resumed:
            return _settle_execute_resume_failure(
                current,
                ctx,
                deps,
                failure,
                (),
                continuation_sink=sink,
            )
        return _settle_fresh_execute_boundary(
            current,
            ctx,
            (),
            continuation_sink=sink,
            error=failure,
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
        except Canceled as error:
            retire_exception_graph(error)
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
                continuation_sink=sink,
                status=SessionState.CANCELED,
            )
        except Exception as error:
            failure = _retired_failure_detail(error)
            if isinstance(current, VerifyContinuation):
                return _settle_verify_incomplete(
                    current,
                    deps,
                    failure,
                )
            if resumed:
                return _settle_execute_resume_failure(
                    current,
                    ctx,
                    deps,
                    failure,
                    exclusion_items,
                    continuation_sink=sink,
                )
            return _settle_fresh_execute_boundary(
                current,
                ctx,
                exclusion_items,
                continuation_sink=sink,
                error=failure,
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
                continuation_sink=sink,
            )
        return OperationResult(
            status=SessionState.REFUSED,
            disposition=Disposition.UNRUN,
        )

    try:
        execution_authority = snapshot_execution_set_authority(xset)
        retained_execution_authority = execution_authority

        def revalidate_preflight_authority() -> None:
            revalidate_execution_set_authority(
                xset,
                execution_authority,
                allow_progress=False,
            )
            if retained_verification_authority is not None:
                revalidate_post_copy_selection_authority(
                    current.candidates,
                    retained_verification_authority,
                    allow_progress=False,
                )

        ctx.emit(PhaseChanged("execution-preflight"))
        revalidate_preflight_authority()
        review_admission = PlanReviewAdmission()
        raw_world = deps.observer(xset, deps.observation_fs)
        revalidate_preflight_authority()
        world = snapshot_plan_observed_world(
            raw_world,
            xset,
            review_admission.fresh(),
        )
        del raw_world
        preflight_world = snapshot_plan_observed_world(
            world,
            xset,
            review_admission.fresh(),
        )
        raw_verdict = deps.preflight(xset, preflight_world)
        revalidate_preflight_authority()
        verdict = snapshot_plan_verdict(
            raw_verdict,
            preflight_world,
            world,
            xset,
            review_admission.fresh(),
        )
        del raw_verdict, preflight_world
        refusals = refusal_views(verdict)
        deps.save_execution_details(ExecutionDetails(str(xset.run_id), refusals))
        revalidate_preflight_authority()
    except PauseRequested:
        raise
    except Canceled as error:
        retire_exception_graph(error)
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
            continuation_sink=sink,
            status=SessionState.CANCELED,
        )
    except Exception as error:
        failure = _retired_failure_detail(error)
        if isinstance(current, VerifyContinuation):
            return _settle_verify_incomplete(
                current,
                deps,
                failure,
            )
        if resumed:
            return _settle_execute_resume_failure(
                current,
                ctx,
                deps,
                failure,
                exclusion_items,
                continuation_sink=sink,
            )
        return _settle_fresh_execute_boundary(
            current,
            ctx,
            exclusion_items,
            continuation_sink=sink,
            error=failure,
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
                continuation_sink=sink,
            )
        emitted_exclusions: list[ItemOutcome] = []
        try:
            current, _emitted = _emit_execution_exclusion_suffix(
                current,
                ctx,
                exclusion_items,
                sink,
                accept=emitted_exclusions.append,
                revalidate=revalidate_preflight_authority,
                allow_control=False,
            )
        except Exception as error:
            return OperationResult(
                status=SessionState.REFUSED,
                disposition=Disposition.UNRUN,
                items=tuple(emitted_exclusions),
                error=_retired_failure_detail(error),
            )
        return OperationResult(
            status=SessionState.REFUSED,
            disposition=Disposition.UNRUN,
            items=tuple(emitted_exclusions),
        )

    target_parent_paths = verdict.observed.target_parent_paths
    del decision, refusals, review_admission, verdict, world

    recording_factory = open_recording or deps.open_recording
    with recording_factory(xset) as recording:
        revalidate_preflight_authority()
        finished = False
        finished_recording = xset.recording

        def finish_once(
            filesystem_status: SessionState,
            recording_status: RecordingStatus,
            *,
            guard_candidates: bool = True,
        ) -> RecordingStatus:
            nonlocal finished, finished_recording
            if finished:
                return finished_recording
            finished = True
            finish_authority = snapshot_execution_set_authority(xset)
            candidate_authority = (
                snapshot_post_copy_selection_authority(current.candidates)
                if guard_candidates
                and isinstance(current, VerifyContinuation)
                else None
            )
            try:
                finished_recording = _finish_recording(
                    recording,
                    xset,
                    filesystem_status,
                    recording_status,
                )
                if candidate_authority is not None:
                    revalidate_post_copy_selection_authority(
                        current.candidates,
                        candidate_authority,
                        allow_progress=False,
                    )
            except Exception as error:
                if recording_integrity_sink is None:
                    raise
                recording_integrity_sink(
                    _retired_failure_detail(error),
                    finish_authority,
                )
            return finished_recording

        if isinstance(current, ExecuteContinuation):
            revalidate_preflight_authority()
            execute_continuation = current
            initially_settled = {
                item_id: (
                    settlement.outcome,
                    settlement.recording_reason,
                )
                for item_id, settlement in execution_authority.settlements.items()
            }
            pending_operation_by_id = {
                item_id: operation
                for item_id, operation in execution_authority.operations.items()
                if item_id not in initially_settled
            }
            operation_items_by_id: dict[str, ItemOutcome] = {}
            operation_items_by_id.update(
                (item.item_id, item)
                for item in exclusion_items[
                    : current.reported_exclusion_count
                ]
            )
            operation_id_by_text = {
                str(op_id): op_id for op_id in xset.selection
            }
            confirmed_settlement_count = len(xset.status)
            confirmed_recording_reason_count = len(xset.recording_reasons)
            confirmed_evidence_count = len(xset.published_evidence)
            pending_execution_item: ItemOutcome | None = None
            last_full_reconciliation_error: BaseException | None = None

            def take_operation_results() -> tuple[ItemOutcome, ...]:
                owned = tuple(
                    _iter_ordered_operation_results(
                        xset.plan,
                        execution_authority.operations,
                        operation_items_by_id,
                        initially_settled,
                    )
                )
                operation_items_by_id.clear()
                return owned

            def observe_execution(body: object) -> None:
                nonlocal pending_execution_item
                if not isinstance(body, ItemOutcome):
                    reconcile_execution_edge()
                    ctx.emit(body)
                    reconcile_execution_edge()
                    return
                reconcile_execution_edge()
                snapshot = _canonical_operation_outcome(
                    body,
                    pending_operation_by_id,
                    operation_items_by_id,
                )
                ctx.emit(
                    snapshot_item_outcome(
                        snapshot,
                        item_id=snapshot.item_id,
                        kind=snapshot.kind,
                        path=snapshot.path,
                    )
                )
                operation_items_by_id[snapshot.item_id] = snapshot
                pending_execution_item = snapshot

            def reconcile_execution_edge() -> None:
                nonlocal confirmed_settlement_count
                nonlocal confirmed_recording_reason_count
                nonlocal confirmed_evidence_count
                nonlocal pending_execution_item
                item = pending_execution_item
                if item is None:
                    if (
                        len(xset.status) != confirmed_settlement_count
                        or len(xset.recording_reasons)
                        != confirmed_recording_reason_count
                        or len(xset.published_evidence)
                        != confirmed_evidence_count
                    ):
                        raise ValueError(
                            "executor settlement must match its accepted "
                            "operation outcomes"
                        )
                    return

                op_id = operation_id_by_text[item.item_id]
                recording_reason = xset.recording_reasons.get(op_id)
                has_evidence = op_id in xset.published_evidence
                if (
                    len(xset.status) != confirmed_settlement_count + 1
                    or len(xset.recording_reasons)
                    != confirmed_recording_reason_count
                    + int(recording_reason is not None)
                    or len(xset.published_evidence)
                    != confirmed_evidence_count + int(has_evidence)
                ):
                    raise ValueError(
                        "executor settlement must match its accepted "
                        "operation outcomes"
                    )
                expected_recording = (
                    RecordingStatus.DEGRADED
                    if recording_reason is not None
                    else RecordingStatus.OK
                )
                if (
                    xset.status.get(op_id) is not item.outcome
                    or item.recording is not expected_recording
                    or item.recording_reason is not recording_reason
                ):
                    raise ValueError(
                        "executor outcome disagrees with execution-set settlement"
                    )
                confirmed_settlement_count += 1
                confirmed_recording_reason_count += int(
                    recording_reason is not None
                )
                confirmed_evidence_count += int(has_evidence)
                pending_execution_item = None

            def reconcile_execution(*, complete: bool) -> None:
                nonlocal last_full_reconciliation_error
                try:
                    _reconcile_executor_outcomes(
                        xset,
                        execution_authority,
                        pending_operation_by_id,
                        operation_items_by_id,
                        complete=complete,
                    )
                except BaseException as error:
                    last_full_reconciliation_error = error
                    raise
                else:
                    last_full_reconciliation_error = None

            def checkpoint_execution() -> None:
                reconcile_execution_edge()
                ctx.checkpoint()
                reconcile_execution_edge()

            verify_after_execute = current.verify_after_execute
            exclusion_failure: FailureDetail | None = None
            exclusion_execution_authority: ExecutionSetAuthority | None = None

            def emit_exclusions(
                *,
                allow_control: bool,
            ) -> FailureDetail | None:
                nonlocal current, execute_continuation, exclusion_failure
                nonlocal exclusion_execution_authority, exclusion_items
                if exclusion_failure is not None:
                    return exclusion_failure
                if exclusion_execution_authority is None:
                    exclusion_execution_authority = (
                        snapshot_execution_set_authority(xset)
                    )

                def accept(item: ItemOutcome) -> None:
                    operation_items_by_id[item.item_id] = item

                def advance(value: ExecuteContinuation) -> None:
                    nonlocal current, execute_continuation
                    execute_continuation = value
                    if isinstance(current, ExecuteContinuation):
                        current = value

                def revalidate_exclusion_authority() -> None:
                    assert exclusion_execution_authority is not None
                    revalidate_execution_set_authority(
                        xset,
                        exclusion_execution_authority,
                        allow_progress=False,
                    )

                try:
                    execute_continuation, _emitted = (
                        _emit_execution_exclusion_suffix(
                            execute_continuation,
                            ctx,
                            exclusion_items,
                            sink,
                            accept=accept,
                            advance=advance,
                            revalidate=revalidate_exclusion_authority,
                            allow_control=allow_control,
                        )
                    )
                    if isinstance(current, ExecuteContinuation):
                        current = execute_continuation
                except (PauseRequested, Canceled):
                    raise
                except Exception as error:
                    # Retain closed first-failure truth without replaying
                    # accepted siblings or re-offering this failure.
                    exclusion_failure = _recording_failure_detail(error)
                    return exclusion_failure
                return None

            def failed_execution_result(
                failure: FailureDetail,
            ) -> OperationResult:
                emission_failure = emit_exclusions(allow_control=False)
                if emission_failure is not None:
                    failure = emission_failure
                phase = _execute_continuation_phase(
                    xset,
                    PhaseStatus.FAILED,
                    f"{failure.type_name}: {failure.message}",
                )
                terminal = OperationResult(
                    status=SessionState.FAILED,
                    recording=xset.recording,
                    disposition=Disposition.RAN,
                    items=take_operation_results(),
                    phases=(phase,) if verify_after_execute else (),
                    bytes_done=phase.bytes_done,
                    bytes_total=phase.bytes_total or phase.bytes_done,
                    error=failure,
                )
                recording_status = finish_once(
                    SessionState.FAILED,
                    terminal.recording,
                )
                return replace(terminal, recording=recording_status)

            try:
                deps.executor_fs.remove_orphaned_temps(
                    Path(xset.plan.target_root.path),
                    target_parent_paths,
                    xset.run_id,
                )
                returned_result = deps.executor(
                    xset,
                    RunContext(observe_execution, checkpoint_execution),
                    recording.recorder,
                    deps.executor_policies,
                    deps.executor_fs,
                )
                try:
                    result = snapshot_operation_result(
                        returned_result,
                        emitted_items=(),
                    )
                finally:
                    del returned_result
                reconcile_execution(complete=True)
                _validate_executor_result(xset, result)
                failure = emit_exclusions(
                    allow_control=result.status is SessionState.COMPLETED,
                )
                if failure is not None:
                    return failed_execution_result(failure)
                execution_recording = xset.recording
                result = replace(result, recording=execution_recording)
                if not verify_after_execute:
                    terminal = replace(
                        result,
                        items=take_operation_results(),
                    )
                    recording_status = finish_once(
                        result.status,
                        execution_recording,
                    )
                    return replace(
                        terminal,
                        recording=recording_status,
                    )

                result = _normalize_execute_result_diagnostics(xset, result)
                execute_phase = _execute_result_phase(xset, result)
                current = _verify_continuation(
                    xset,
                    result.status,
                    execute_phase,
                )
                retained_execution_authority = (
                    snapshot_execution_set_authority(xset)
                )
                revalidate_execution_set_authority(
                    xset,
                    retained_execution_authority,
                    allow_progress=False,
                )
                if (
                    not current.candidates.candidates
                    and not current.missing_evidence_ids
                ):
                    terminal = replace(
                        result,
                        items=take_operation_results(),
                        phases=(execute_phase,),
                    )
                    recording_status = finish_once(
                        result.status,
                        execution_recording,
                    )
                    return replace(
                        terminal,
                        recording=recording_status,
                    )
                del result
                retained_verification_authority = (
                    snapshot_post_copy_selection_authority(
                        current.candidates
                    )
                )
                sink(current)
                revalidate_execution_set_authority(
                    xset,
                    retained_execution_authority,
                    allow_progress=False,
                )
                try:
                    revalidate_post_copy_selection_authority(
                        current.candidates,
                        retained_verification_authority,
                        allow_progress=False,
                    )
                except Exception as error:
                    verification_handoff_error = error
                result_items = list(
                    _iter_ordered_operation_results(
                        xset.plan,
                        execution_authority.operations,
                        operation_items_by_id,
                        initially_settled,
                    )
                )
            except PauseRequested as error:
                if error is not last_full_reconciliation_error:
                    try:
                        reconcile_execution(complete=False)
                    except Exception:
                        retire_exception_graph(error)
                        raise
                raise
            except Canceled as error:
                if error is not last_full_reconciliation_error:
                    try:
                        reconcile_execution(complete=False)
                    except Exception as reconciliation_error:
                        retire_exception_graph(error)
                        return failed_execution_result(
                            _recording_failure_detail(reconciliation_error)
                        )
                retire_exception_graph(error)
                failure = emit_exclusions(allow_control=False)
                if failure is not None:
                    return failed_execution_result(failure)
                phase = _execute_continuation_phase(
                    xset,
                    PhaseStatus.CANCELED,
                    "execution canceled",
                )
                terminal = OperationResult(
                    status=SessionState.CANCELED,
                    recording=xset.recording,
                    disposition=Disposition.RAN,
                    canceled=True,
                    items=take_operation_results(),
                    phases=(phase,) if verify_after_execute else (),
                    bytes_done=phase.bytes_done,
                    bytes_total=phase.bytes_total or phase.bytes_done,
                )
                recording_status = finish_once(
                    SessionState.CANCELED,
                    terminal.recording,
                )
                return replace(terminal, recording=recording_status)
            except Exception as error:
                if error is not last_full_reconciliation_error:
                    try:
                        reconcile_execution(complete=False)
                    except Exception as reconciliation_error:
                        retire_exception_graph(error)
                        error = reconciliation_error
                return failed_execution_result(
                    _recording_failure_detail(error)
                )
            del (
                failed_execution_result,
                emit_exclusions,
                exclusion_items,
                observe_execution,
                operation_items_by_id,
                initially_settled,
                execution_authority,
                operation_id_by_text,
                pending_operation_by_id,
                reconcile_execution_edge,
                reconcile_execution,
                take_operation_results,
            )
        else:
            result_items: list[ItemOutcome | IntegrityOutcome] = []

        def take_result_items() -> tuple[ItemOutcome | IntegrityOutcome, ...]:
            owned = tuple(result_items)
            result_items.clear()
            return owned

        verification_item_start = len(result_items)
        observed_recording = current.recording
        if retained_verification_authority is None:
            raise RuntimeError("verification continuation snapshot is missing")
        if retained_execution_authority is None:
            raise RuntimeError("verification execution snapshot is missing")
        initial_verification_authority = retained_verification_authority
        initial_completed_verification = dict(
            initial_verification_authority.completed_bytes
        )
        observed_verification_ids = set(initial_completed_verification)
        observed_verification_count = len(observed_verification_ids)
        verification_candidates = {
            candidate.item_id: candidate
            for candidate in initial_verification_authority.candidates
            if candidate.item_id not in observed_verification_ids
        }
        last_verification_reconciliation_error: BaseException | None = None

        def reconcile_verification(*, complete: bool) -> None:
            nonlocal last_verification_reconciliation_error
            try:
                _validate_post_copy_verifier_completion(
                    current.candidates,
                    initial_verification_authority,
                    verification_candidates,
                    complete=complete,
                )
            except BaseException as error:
                last_verification_reconciliation_error = error
                raise
            else:
                last_verification_reconciliation_error = None

        def revalidate_verification_authority() -> None:
            revalidate_execution_set_authority(
                xset,
                retained_execution_authority,
                allow_progress=False,
            )
            revalidate_post_copy_selection_authority(
                current.candidates,
                initial_verification_authority,
                allow_progress=True,
            )

        def checkpoint_verification() -> None:
            ctx.checkpoint()
            revalidate_verification_authority()

        def observe_verification(body: object) -> None:
            nonlocal observed_recording, observed_verification_count
            if not isinstance(body, IntegrityOutcome):
                revalidate_verification_authority()
                ctx.emit(body)
                revalidate_verification_authority()
                return
            snapshot = _canonical_integrity_outcome(
                body,
                verification_candidates,
                observed_verification_ids,
            )
            reconcile_verification(complete=False)
            # A degraded recording snapshot can fail.  Publish it before the
            # reliable item so a raised sink error cannot leave the reporter
            # unable to tell whether downstream accepted that item.
            if (
                snapshot.recording is RecordingStatus.DEGRADED
                and observed_recording is RecordingStatus.OK
            ):
                observed_recording = RecordingStatus.DEGRADED
                sink(replace(current, recording=RecordingStatus.DEGRADED))
                revalidate_verification_authority()
            ctx.emit(
                snapshot_integrity_outcome(
                    snapshot,
                    item_id=snapshot.item_id,
                    row_id=snapshot.row_id,
                    location_id=snapshot.location_id,
                    path=snapshot.path,
                    phase=snapshot.phase,
                )
            )
            result_items.append(snapshot)
            verification_candidates.pop(snapshot.item_id)
            observed_verification_ids.add(snapshot.item_id)
            observed_verification_count += 1
            revalidate_verification_authority()

        def failed_verification_result(
            error: BaseException,
        ) -> OperationResult:
            nonlocal current
            verification_candidates.clear()
            observed_verification_ids.clear()
            failure = _retired_failure_detail(error)
            current_recording = _combined_recording(
                current.recording,
                observed_recording,
            )
            if current_recording is not current.recording:
                current = replace(current, recording=current_recording)
            verify_phase = _verify_phase(
                current,
                items_done_floor=observed_verification_count,
                incomplete=True,
                error=f"{failure.type_name}: {failure.message}",
            )
            terminal = OperationResult(
                status=current.filesystem_status,
                recording=current_recording,
                disposition=Disposition.RAN,
                items=take_result_items(),
                phases=(current.execute_phase, verify_phase),
                bytes_done=current.execute_phase.bytes_done,
                bytes_total=(
                    current.execute_phase.bytes_total
                    if current.execute_phase.bytes_total is not None
                    else current.execute_phase.bytes_done
                ),
                error=failure,
            )
            recording_status = finish_once(
                current.filesystem_status,
                current_recording,
                guard_candidates=False,
            )
            return replace(terminal, recording=recording_status)

        if verification_handoff_error is not None:
            return failed_verification_result(verification_handoff_error)

        try:
            progress_items_total, progress_bytes_total = (
                _verify_progress_totals(current)
            )
            ctx.emit(PhaseChanged("verify"))
            revalidate_verification_authority()
            owned_run = RunContext(
                observe_verification,
                checkpoint_verification,
            )
            raw_verification_context = deps.verifier_context(owned_run)
            revalidate_verification_authority()
            target_evidence = xset.plan.target_volume_evidence
            verification_context = bind_verifier_context(
                raw_verification_context,
                owned_run,
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
            del raw_verification_context
            revalidate_verification_authority()
            reconcile_verification(complete=False)
            returned_verification = deps.verifier(
                current.candidates,
                verification_context,
                recording.recorder,
            )
            try:
                verification_recording = validate_integrity_run_result(
                    returned_verification,
                    result_items,
                    start=verification_item_start,
                )
                reconcile_verification(complete=True)
            finally:
                del returned_verification
            verification_candidates.clear()
            observed_verification_ids.clear()
            current_recording = _combined_recording(
                current.recording,
                observed_recording,
                verification_recording,
            )
            if current_recording is not current.recording:
                current = replace(current, recording=current_recording)
                sink(current)
                revalidate_verification_authority()
            verify_phase = _verify_phase(
                current,
                items_done_floor=observed_verification_count,
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
            terminal = OperationResult(
                status=current.filesystem_status,
                recording=current_recording,
                disposition=Disposition.RAN,
                items=take_result_items(),
                phases=(current.execute_phase, verify_phase),
                bytes_done=current.execute_phase.bytes_done,
                bytes_total=(
                    current.execute_phase.bytes_total
                    if current.execute_phase.bytes_total is not None
                    else current.execute_phase.bytes_done
                ),
                error=error,
            )
            recording_status = finish_once(
                current.filesystem_status,
                current_recording,
            )
            return replace(terminal, recording=recording_status)
        except PauseRequested as error:
            if error is not last_verification_reconciliation_error:
                try:
                    reconcile_verification(complete=False)
                except Exception as reconciliation_error:
                    retire_exception_graph(error)
                    return failed_verification_result(reconciliation_error)
            verification_candidates.clear()
            observed_verification_ids.clear()
            raise
        except Canceled as error:
            if error is not last_verification_reconciliation_error:
                try:
                    reconcile_verification(complete=False)
                except Exception as reconciliation_error:
                    retire_exception_graph(error)
                    return failed_verification_result(reconciliation_error)
            verification_candidates.clear()
            observed_verification_ids.clear()
            retire_exception_graph(error)
            current_recording = _combined_recording(
                current.recording,
                observed_recording,
            )
            current = replace(current, recording=current_recording)
            verify_phase = _verify_phase(
                current,
                items_done_floor=observed_verification_count,
                canceled=True,
                error="verification canceled",
            )
            terminal = OperationResult(
                status=current.filesystem_status,
                recording=current_recording,
                disposition=Disposition.RAN,
                canceled=True,
                items=take_result_items(),
                phases=(current.execute_phase, verify_phase),
                bytes_done=current.execute_phase.bytes_done,
                bytes_total=(
                    current.execute_phase.bytes_total
                    if current.execute_phase.bytes_total is not None
                    else current.execute_phase.bytes_done
                ),
            )
            recording_status = finish_once(
                current.filesystem_status,
                current_recording,
            )
            return replace(terminal, recording=recording_status)
        except Exception as error:
            if error is not last_verification_reconciliation_error:
                try:
                    reconcile_verification(complete=False)
                except Exception as reconciliation_error:
                    retire_exception_graph(error)
                    error = reconciliation_error
            return failed_verification_result(error)


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

    candidate_authority = (
        snapshot_post_copy_selection_authority(continuation.candidates)
        if isinstance(continuation, VerifyContinuation)
        else None
    )
    terminal_authority = snapshot_execution_set_authority(xset)
    boundary = _RecordingBoundary(
        deps.open_recording,
        lambda: _strict_execution_revalidator(xset),
    )
    recording_failure: _ClosedRecordingFailure | None = None
    integrity_failure: FailureDetail | None = None
    try:
        with boundary.open(xset) as recording:
            finish_authority = snapshot_execution_set_authority(xset)
            try:
                recording_status = _finish_recording(
                    recording,
                    xset,
                    filesystem_status,
                    recording_status,
                )
                if candidate_authority is not None:
                    revalidate_post_copy_selection_authority(
                        continuation.candidates,
                        candidate_authority,
                        allow_progress=False,
                    )
            except Exception as error:
                integrity_failure = _retired_failure_detail(error)
                terminal_authority = finish_authority
            else:
                terminal_authority = snapshot_execution_set_authority(xset)
    except Exception as error:
        recording_failure = (
            boundary.enter_failure or _close_recording_failure(error)
        )
        retire_exception_graph(error)
        _note_closed_recording_issue(
            xset,
            TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
            recording_failure,
        )
        recording_status = xset.recording
        terminal_authority = snapshot_execution_set_authority(xset)
        try:
            recording_status = _finish_recording_without_open(
                deps,
                xset,
                filesystem_status,
                recording_status,
            )
            if candidate_authority is not None:
                revalidate_post_copy_selection_authority(
                    continuation.candidates,
                    candidate_authority,
                    allow_progress=False,
                )
        except Exception as finish_error:
            integrity_failure = _retired_failure_detail(finish_error)
        else:
            terminal_authority = snapshot_execution_set_authority(xset)
    if integrity_failure is None and boundary.integrity_failure is not None:
        integrity_failure = boundary.integrity_failure
    if integrity_failure is None and candidate_authority is not None:
        try:
            revalidate_post_copy_selection_authority(
                continuation.candidates,
                candidate_authority,
                allow_progress=False,
            )
        except Exception as error:
            integrity_failure = _retired_failure_detail(error)
    if boundary.exit_failure is not None:
        recording_failure = boundary.exit_failure
        if integrity_failure is None:
            _note_closed_recording_issue(
                xset,
                TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
                boundary.exit_failure,
            )
            recording_status = xset.recording
            terminal_authority = snapshot_execution_set_authority(xset)
    execute_phase = (
        phase
        if isinstance(continuation, ExecuteContinuation)
        else continuation.execute_phase
    )
    terminal = OperationResult(
        status=filesystem_status,
        recording=recording_status,
        recording_issues=terminal_authority.recording_issues,
        omitted_detail_count=terminal_authority.omitted_detail_count,
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
            if recording_failure is None
            else recording_failure.detail
        ),
    )
    if integrity_failure is not None:
        return _recording_integrity_failure_result(
            terminal,
            integrity_failure,
            terminal_authority,
            verification=isinstance(continuation, VerifyContinuation),
            filesystem_status=(
                filesystem_status
                if isinstance(continuation, VerifyContinuation)
                else SessionState.FAILED
            ),
        )
    return terminal


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
        ctx.emit(
            snapshot_item_outcome(
                item,
                item_id=item.item_id,
                kind=item.kind,
                path=item.path,
            )
        )


def _strict_execution_revalidator(
    xset: ExecutionSet,
) -> Callable[[], None]:
    authority = snapshot_execution_set_authority(xset)

    def revalidate() -> None:
        revalidate_execution_set_authority(
            xset,
            authority,
            allow_progress=False,
        )

    return revalidate


def _emit_execution_exclusion_suffix(
    continuation: ExecuteContinuation,
    ctx: RunContext,
    items: tuple[ItemOutcome, ...],
    continuation_sink: Callable[[ExecutionContinuation], None],
    *,
    accept: Callable[[ItemOutcome], None] | None = None,
    advance: Callable[[ExecuteContinuation], None] | None = None,
    revalidate: Callable[[], None] | None = None,
    allow_control: bool = True,
) -> tuple[ExecuteContinuation, tuple[ItemOutcome, ...]]:
    """Publish the unreported deterministic suffix and advance its witness."""

    cursor = continuation.reported_exclusion_count
    if cursor > len(items):
        raise ValueError("reported exclusion count exceeds the derived exclusions")
    emitted: list[ItemOutcome] = []
    current = continuation
    while cursor < len(items):
        item = items[cursor]
        try:
            ctx.emit(
                snapshot_item_outcome(
                    item,
                    item_id=item.item_id,
                    kind=item.kind,
                    path=item.path,
                )
            )
            if accept is not None:
                accept(item)
            emitted.append(item)
            cursor += 1
            current = replace(current, reported_exclusion_count=cursor)
            if advance is not None:
                advance(current)
            continuation_sink(current)
            if revalidate is not None:
                revalidate()
        except (PauseRequested, Canceled) as error:
            if allow_control:
                raise
            retire_exception_graph(error)
            raise RuntimeError(
                "control cannot interrupt terminal exclusion settlement"
            ) from None
    return current, tuple(emitted)


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


def _canonical_operation_outcome(
    value: ItemOutcome,
    pending_by_id: dict[str, ExecutionOperationFact],
    accepted_by_id: dict[str, ItemOutcome],
) -> ItemOutcome:
    """Bind an executor outcome to reviewed operation identity and path facts."""

    item_id = value.item_id
    if type(item_id) is not str:
        raise TypeError("executor outcome item id must be text")
    if item_id in accepted_by_id:
        raise ValueError("executor emitted a duplicate operation outcome")
    operation = pending_by_id.get(item_id)
    if operation is None:
        raise ValueError("executor emitted an outcome outside its selection")
    return snapshot_item_outcome(
        value,
        item_id=item_id,
        kind=operation.kind,
        path=operation.target_rel_path,
    )


def _reconcile_executor_outcomes(
    xset: ExecutionSet,
    authority: ExecutionSetAuthority,
    pending_by_id: dict[str, ExecutionOperationFact],
    accepted_by_id: dict[str, ItemOutcome],
    *,
    complete: bool,
) -> None:
    """Require accepted operation events to match durable continuation truth."""

    revalidate_execution_set_authority(
        xset,
        authority,
        allow_progress=True,
    )

    accepted_ids = {
        item_id for item_id in accepted_by_id if item_id in pending_by_id
    }
    if complete and len(accepted_ids) != len(pending_by_id):
        raise ValueError("executor omitted an outcome for a pending operation")
    initially_settled_ids = set(authority.settlements)
    newly_settled_ids = {
        str(op_id)
        for op_id in xset.status
        if str(op_id) not in initially_settled_ids
    }
    if accepted_ids != newly_settled_ids:
        raise ValueError(
            "executor settlement must match its accepted operation outcomes"
        )
    op_id_by_text = {str(op_id): op_id for op_id in xset.selection}
    for item_id in accepted_ids:
        item = accepted_by_id[item_id]
        op_id = op_id_by_text[item_id]
        settled_outcome = xset.status.get(op_id)
        recording_reason = xset.recording_reasons.get(op_id)
        expected_recording = (
            RecordingStatus.DEGRADED
            if recording_reason is not None
            else RecordingStatus.OK
        )
        if (
            item.outcome is not settled_outcome
            or item.recording is not expected_recording
            or item.recording_reason is not recording_reason
        ):
            raise ValueError(
                "executor outcome disagrees with execution-set settlement"
            )


def _validate_executor_result(
    xset: ExecutionSet,
    result: OperationResult,
) -> None:
    """Bind the executor aggregate to workflow-owned settlement axes."""

    if result.status not in {SessionState.COMPLETED, SessionState.FAILED}:
        raise ValueError("executor returned an invalid terminal status")
    if result.disposition is not Disposition.RAN or result.canceled:
        raise ValueError("executor returned an invalid execution disposition")
    if result.phases:
        raise ValueError("executor returned workflow-owned phases")
    if (
        result.audit is not RecordingStatus.OK
        or result.review_fact_limit is not None
    ):
        raise ValueError("executor returned workflow-owned result fields")
    if result.omitted_detail_count != xset.omitted_detail_count:
        raise ValueError(
            "executor result omitted detail count disagrees with execution set"
        )
    if (
        result.recording is not xset.recording
        or result.recording_issues != xset.recording_issues
    ):
        raise ValueError(
            "executor result recording must match execution-set recording"
        )

    phase = _execute_continuation_phase(xset, PhaseStatus.COMPLETED, None)
    if result.bytes_done != phase.bytes_done or result.bytes_total != phase.bytes_total:
        raise ValueError("executor byte totals disagree with execution settlement")
    if any(
        outcome in {Outcome.FAILED, Outcome.CANCELED, Outcome.DEFERRED}
        for outcome in xset.status.values()
    ) and result.status is not SessionState.FAILED:
        raise ValueError("executor status disagrees with operation settlements")


def _canonical_integrity_outcome(
    value: IntegrityOutcome,
    candidate_by_id: dict[str, PostCopyCandidateFact],
    completed_ids: set[str],
) -> IntegrityOutcome:
    """Bind a verifier outcome to its admitted post-copy candidate facts."""

    item_id = value.item_id
    if type(item_id) is not str:
        raise TypeError("integrity outcome item id must be text")
    if item_id in completed_ids:
        raise ValueError("verifier emitted a duplicate integrity outcome")
    candidate = candidate_by_id.get(item_id)
    if candidate is None:
        raise ValueError("verifier emitted an outcome outside its candidates")
    identity = candidate.recorded_identity
    return snapshot_integrity_outcome(
        value,
        item_id=candidate.item_id,
        row_id=None if identity is None else identity[0],
        location_id=None if identity is None else identity[1],
        path=candidate.display_path,
        phase="verify",
    )


def _validate_post_copy_verifier_completion(
    selection: PostCopySelection,
    authority: PostCopySelectionAuthority,
    pending_by_id: dict[str, PostCopyCandidateFact],
    *,
    complete: bool,
) -> None:
    """Revalidate verifier-owned completion against accepted outcome identities."""

    revalidate_post_copy_selection_authority(
        selection,
        authority,
        allow_progress=True,
    )
    completed = dict(selection.completed_bytes)
    initial_completed = dict(authority.completed_bytes)
    initial_candidate_ids = {
        candidate.item_id for candidate in authority.candidates
    }
    pending_ids = set(pending_by_id)
    emitted_ids = initial_candidate_ids - set(initial_completed) - pending_ids
    if set(completed) != set(initial_completed) | emitted_ids:
        raise ValueError(
            "post-copy verifier completion must match its emitted outcomes"
        )
    if complete and pending_ids:
        raise ValueError("post-copy verifier returned with pending candidates")


def _iter_ordered_operation_results(
    plan: Plan,
    operation_facts: Mapping[str, ExecutionOperationFact],
    items_by_id: dict[str, ItemOutcome],
    initially_settled: dict[
        str,
        tuple[Outcome, ItemRecordingReason | None],
    ] | None = None,
) -> Iterator[ItemOutcome]:
    for plan_operation in plan.operations:
        item_id = str(plan_operation.op_id)
        item = items_by_id.get(item_id)
        if item is not None:
            yield item
            continue
        if initially_settled is None:
            continue
        settlement = initially_settled.get(item_id)
        if settlement is None:
            continue
        operation = operation_facts[item_id]
        outcome, recording_reason = settlement
        yield ItemOutcome(
            item_id=item_id,
            kind=operation.kind,
            path=operation.target_rel_path,
            outcome=outcome,
            detail={"continued": True},
            recording=(
                RecordingStatus.DEGRADED
                if recording_reason is not None
                else RecordingStatus.OK
            ),
            recording_reason=recording_reason,
        )


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
    attestation = snapshot_attestation(evidence.attestation)
    return PostCopyCandidate(
        item_id=str(operation.op_id),
        root=target_root,
        display_path=operation.target_rel_path,
        expected_stat=attestation.subject,
        copy_attestation=attestation,
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
        retire_exception_graph(error)
        raise ValueError("execution returned invalid compound filesystem truth") from None
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
    continuation_sink: Callable[[ExecutionContinuation], None] | None = None,
    status: SessionState = SessionState.FAILED,
    error: FailureDetail | None = None,
) -> OperationResult:
    """Project pre-executor truth without consulting a lossy snapshot."""

    if status not in {SessionState.FAILED, SessionState.CANCELED}:
        raise ValueError("fresh execute boundary must fail or cancel")
    if status is SessionState.FAILED and error is None:
        raise ValueError("fresh execute failure requires an error")
    emitted_items: list[ItemOutcome] = []
    try:
        _continuation, _emitted = _emit_execution_exclusion_suffix(
            continuation,
            ctx,
            exclusion_items,
            continuation_sink or (lambda value: None),
            accept=emitted_items.append,
            revalidate=_strict_execution_revalidator(
                continuation.execution_set
            ),
            allow_control=False,
        )
    except (PauseRequested, Canceled):
        raise
    except Exception as emit_error:
        emit_failure = _retired_failure_detail(emit_error)
        if error is None:
            error = emit_failure
        else:
            error = FailureDetail(
                error.type_name,
                f"{error.message}; outcome emission also failed: "
                f"{emit_failure.type_name}: {emit_failure.message}",
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
        items=tuple(emitted_items),
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
    failure: _ClosedRecordingFailure,
    *,
    continuation_sink: Callable[[ExecutionContinuation], None] | None = None,
) -> OperationResult:
    """Project an unavailable run recording from authoritative continuation."""

    xset = continuation.execution_set
    _note_closed_recording_issue(
        xset,
        TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
        failure,
    )
    detail = failure.detail
    execution_authority = snapshot_execution_set_authority(xset)
    if isinstance(continuation, VerifyContinuation):
        candidate_authority = snapshot_post_copy_selection_authority(
            continuation.candidates
        )
        phase = _verify_phase(
            continuation,
            incomplete=True,
            error=f"{detail.type_name}: {detail.message}",
        )
        terminal = OperationResult(
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
            error=detail,
        )
        try:
            _finish_recording_without_open(
                deps,
                xset,
                continuation.filesystem_status,
                xset.recording,
            )
            revalidate_post_copy_selection_authority(
                continuation.candidates,
                candidate_authority,
                allow_progress=False,
            )
        except Exception as error:
            return _recording_integrity_failure_result(
                terminal,
                _retired_failure_detail(error),
                execution_authority,
                verification=True,
                filesystem_status=continuation.filesystem_status,
            )
        return terminal

    phase = _execute_continuation_phase(
        xset,
        PhaseStatus.FAILED,
        f"{detail.type_name}: {detail.message}",
    )
    emitted_exclusions: list[ItemOutcome] = []
    try:
        decision = derive_execution_selection(
            xset.plan,
            user_deselected=xset.user_deselected,
        )
        exclusion_items = _exclusion_items(xset.plan, decision)
        _continuation, _emitted = _emit_execution_exclusion_suffix(
            continuation,
            ctx,
            exclusion_items,
            continuation_sink or (lambda value: None),
            accept=emitted_exclusions.append,
            revalidate=_strict_execution_revalidator(xset),
            allow_control=False,
        )
    except (PauseRequested, Canceled):
        raise
    except Exception as emit_error:
        emit_failure = _recording_failure_detail(emit_error)
        error_context = f"{emit_failure.type_name}: {emit_failure.message}"
        phase_error = (
            f"{detail.type_name}: {detail.message}; "
            f"outcome emission also failed: {error_context}"
        )
        phase = replace(phase, error=phase_error)
    terminal = OperationResult(
        status=SessionState.FAILED,
        recording=RecordingStatus.DEGRADED,
        disposition=Disposition.RAN,
        items=tuple(emitted_exclusions),
        phases=(phase,) if continuation.verify_after_execute else (),
        bytes_done=phase.bytes_done,
        bytes_total=(
            phase.bytes_total
            if phase.bytes_total is not None
            else phase.bytes_done
        ),
        error=detail,
    )
    try:
        _finish_recording_without_open(
            deps,
            xset,
            SessionState.FAILED,
            RecordingStatus.DEGRADED,
        )
    except Exception as error:
        return _recording_integrity_failure_result(
            terminal,
            _retired_failure_detail(error),
            execution_authority,
            verification=False,
            filesystem_status=SessionState.FAILED,
        )
    return terminal


def _recording_entry_canceled_result(
    continuation: ExecutionContinuation,
    ctx: RunContext,
    deps: SyncDependencies,
    *,
    continuation_sink: Callable[[ExecutionContinuation], None] | None = None,
) -> OperationResult:
    """Settle entry-time cancellation without reopening the recording owner."""

    xset = continuation.execution_set
    emitted_items: list[ItemOutcome] = []
    emission_error: FailureDetail | None = None
    candidate_authority: PostCopySelectionAuthority | None = None
    if isinstance(continuation, ExecuteContinuation):
        try:
            decision = derive_execution_selection(
                xset.plan,
                user_deselected=xset.user_deselected,
            )
            continuation, _emitted = _emit_execution_exclusion_suffix(
                continuation,
                ctx,
                _exclusion_items(xset.plan, decision),
                continuation_sink or (lambda value: None),
                accept=emitted_items.append,
                revalidate=_strict_execution_revalidator(xset),
                allow_control=False,
            )
        except (PauseRequested, Canceled):
            raise
        except Exception as error:
            emission_error = _retired_failure_detail(error)
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
        candidate_authority = snapshot_post_copy_selection_authority(
            continuation.candidates
        )
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
    terminal = OperationResult(
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
    execution_authority = snapshot_execution_set_authority(xset)
    try:
        recording_status = _finish_recording_without_open(
            deps,
            xset,
            filesystem_status,
            recording_status,
        )
        if candidate_authority is not None:
            revalidate_post_copy_selection_authority(
                continuation.candidates,
                candidate_authority,
                allow_progress=False,
            )
    except Exception as error:
        return _recording_integrity_failure_result(
            terminal,
            _retired_failure_detail(error),
            execution_authority,
            verification=isinstance(continuation, VerifyContinuation),
            filesystem_status=(
                filesystem_status
                if isinstance(continuation, VerifyContinuation)
                else SessionState.FAILED
            ),
        )
    return replace(terminal, recording=recording_status)


def _settle_execute_resume_failure(
    continuation: ExecuteContinuation,
    ctx: RunContext,
    deps: SyncDependencies,
    error: FailureDetail,
    exclusion_items: tuple[ItemOutcome, ...],
    *,
    continuation_sink: Callable[[ExecutionContinuation], None] | None = None,
) -> OperationResult:
    """Finish an already-started execute continuation without more domain work."""

    emitted_items: list[ItemOutcome] = []
    try:
        continuation, _emitted = _emit_execution_exclusion_suffix(
            continuation,
            ctx,
            exclusion_items,
            continuation_sink or (lambda value: None),
            accept=emitted_items.append,
            revalidate=_strict_execution_revalidator(
                continuation.execution_set
            ),
            allow_control=False,
        )
    except (PauseRequested, Canceled):
        raise
    except Exception as emit_error:
        try:
            error = FailureDetail(type(emit_error).__name__, str(emit_error))
        finally:
            retire_exception_graph(emit_error)
    phase = _execute_continuation_phase(
        continuation.execution_set,
        PhaseStatus.FAILED,
        f"{error.type_name}: {error.message}",
    )
    terminal = OperationResult(
        status=SessionState.FAILED,
        recording=continuation.execution_set.recording,
        disposition=Disposition.RAN,
        items=tuple(emitted_items),
        phases=(phase,) if continuation.verify_after_execute else (),
        bytes_done=phase.bytes_done,
        bytes_total=(
            phase.bytes_total
            if phase.bytes_total is not None
            else phase.bytes_done
        ),
        error=error,
    )
    execution_authority = snapshot_execution_set_authority(
        continuation.execution_set
    )
    try:
        recording_status = _finish_existing_recording(
            deps,
            continuation.execution_set,
            SessionState.FAILED,
            terminal.recording,
        )
    except Exception as finish_error:
        return _recording_integrity_failure_result(
            terminal,
            _retired_failure_detail(finish_error),
            execution_authority,
            verification=False,
            filesystem_status=SessionState.FAILED,
        )
    return replace(terminal, recording=recording_status)


def _settle_verify_incomplete(
    continuation: VerifyContinuation,
    deps: SyncDependencies,
    error: FailureDetail,
) -> OperationResult:
    candidate_authority = snapshot_post_copy_selection_authority(
        continuation.candidates
    )
    phase = _verify_phase(
        continuation,
        incomplete=True,
        error=f"{error.type_name}: {error.message}",
    )
    recording_status = _combined_recording(
        continuation.execution_set.recording,
        continuation.recording,
    )
    terminal = OperationResult(
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
    execution_authority = snapshot_execution_set_authority(
        continuation.execution_set
    )
    try:
        recording_status = _finish_existing_recording(
            deps,
            continuation.execution_set,
            continuation.filesystem_status,
            recording_status,
        )
        revalidate_post_copy_selection_authority(
            continuation.candidates,
            candidate_authority,
            allow_progress=False,
        )
    except Exception as finish_error:
        return _recording_integrity_failure_result(
            terminal,
            _retired_failure_detail(finish_error),
            execution_authority,
            verification=True,
            filesystem_status=continuation.filesystem_status,
        )
    return replace(terminal, recording=recording_status)


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
        authority = snapshot_execution_set_authority(xset)
        try:
            finisher(xset, status, recording_status)
        except Exception as error:
            try:
                revalidate_execution_set_authority(
                    xset,
                    authority,
                    allow_progress=False,
                )
            except Exception:
                retire_exception_graph(error)
                raise
            _note_task_recording_issue(
                xset,
                TaskRecordingIssueReason.FINISH_FAILED,
                error,
            )
        else:
            revalidate_execution_set_authority(
                xset,
                authority,
                allow_progress=False,
            )
        return _combined_recording(recording_status, xset.recording)
    boundary = _RecordingBoundary(
        deps.open_recording,
        lambda: _strict_execution_revalidator(xset),
    )
    try:
        with boundary.open(xset) as recording:
            recording_status = _finish_recording(
                recording,
                xset,
                status,
                recording_status,
            )
    except Exception as error:
        if boundary.integrity_failure is not None:
            failure = boundary.integrity_failure
            retire_exception_graph(error)
            raise RuntimeError(
                f"recording boundary changed continuation truth: "
                f"{failure.type_name}: {failure.message}"
            ) from None
        failure = boundary.enter_failure or _close_recording_failure(error)
        _note_closed_recording_issue(
            xset,
            TaskRecordingIssueReason.RECORDING_OPEN_FAILED,
            failure,
        )
    if boundary.integrity_failure is not None:
        failure = boundary.integrity_failure
        raise RuntimeError(
            f"recording boundary changed continuation truth: "
            f"{failure.type_name}: {failure.message}"
        )
    if boundary.exit_failure is not None:
        _note_closed_recording_issue(
            xset,
            TaskRecordingIssueReason.RECORDING_CLOSE_FAILED,
            boundary.exit_failure,
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
    authority = snapshot_execution_set_authority(xset)
    try:
        finisher(xset, status, recording_status)
    except Exception as error:
        try:
            revalidate_execution_set_authority(
                xset,
                authority,
                allow_progress=False,
            )
        except Exception:
            retire_exception_graph(error)
            raise
        _note_task_recording_issue(
            xset,
            TaskRecordingIssueReason.FINISH_FAILED,
            error,
        )
    else:
        revalidate_execution_set_authority(
            xset,
            authority,
            allow_progress=False,
        )
    return _combined_recording(recording_status, xset.recording)


def _finish_recording(
    recording: RunRecording,
    xset: ExecutionSet,
    status: SessionState,
    recording_status: RecordingStatus,
) -> RecordingStatus:
    authority = snapshot_execution_set_authority(xset)
    try:
        recording.finish(status, recording_status)
    except Exception as error:
        try:
            revalidate_execution_set_authority(
                xset,
                authority,
                allow_progress=False,
            )
        except Exception:
            retire_exception_graph(error)
            raise
        _note_task_recording_issue(
            xset,
            TaskRecordingIssueReason.FINISH_FAILED,
            error,
        )
    else:
        revalidate_execution_set_authority(
            xset,
            authority,
            allow_progress=False,
        )
    return _combined_recording(recording_status, xset.recording)


def _retired_failure_detail(error: BaseException) -> FailureDetail:
    try:
        return FailureDetail(type(error).__name__, logical_error_text(error))
    finally:
        retire_exception_graph(error)


def _try_add_exception_note(error: BaseException, note: str) -> None:
    """Add secondary diagnostics without replacing the escaping primary."""

    try:
        BaseException.add_note(error, note)
    except BaseException as note_error:
        retire_exception_graph(note_error)


def _note_task_recording_issue(
    xset: ExecutionSet,
    reason: TaskRecordingIssueReason,
    error: BaseException,
) -> None:
    _note_closed_recording_issue(
        xset,
        reason,
        _close_recording_failure(error),
    )


def _note_closed_recording_issue(
    xset: ExecutionSet,
    reason: TaskRecordingIssueReason,
    failure: _ClosedRecordingFailure,
) -> None:
    issue = TaskRecordingIssue(reason)
    xset.note_task_recording_issue(
        issue.reason,
        failure.issue_detail,
    )


def _recording_error_message(error: BaseException) -> str | None:
    try:
        return logical_error_text(error)
    except BaseException as diagnostic_error:
        retire_exception_graph(diagnostic_error)
        return None


def _close_recording_failure(error: BaseException) -> _ClosedRecordingFailure:
    try:
        type_name = type(error).__name__
        message = _recording_error_message(error)
        return _ClosedRecordingFailure(
            FailureDetail(
                type_name,
                "recording diagnostic unavailable" if message is None else message,
            ),
            None if message is None else f"{type_name}: {message}",
        )
    finally:
        retire_exception_graph(error)


def _recording_failure_detail(error: BaseException) -> FailureDetail:
    return _close_recording_failure(error).detail


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
        cause = BaseException.__cause__.__get__(error, BaseException)
        try:
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
                detail = logical_error_text(
                    cause if isinstance(cause, OSError) else error
                )
        finally:
            if isinstance(cause, BaseException):
                retire_exception_graph(cause)
            retire_exception_graph(error)
        raise ValueError(detail) from None
    return Path(logical)


def _physical_logical_root(path: Path) -> Path:
    try:
        resolved = Path(to_extended_length_path(str(path))).resolve(
            strict=True
        )
    except OSError as error:
        try:
            detail = logical_error_text(error)
        finally:
            retire_exception_graph(error)
        raise ValueError(detail) from None
    return Path(from_extended_length_path(str(resolved)))


def _validate_sync_paths(
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
    except ValueError as error:
        retire_exception_graph(error)
        common = ""
    if common in {source_key, target_key}:
        raise ValueError("source and target must be distinct, non-nested directories")
    return source, target


def validate_sync_paths(
    source_path: str,
    target_path: str,
) -> tuple[Path, Path]:
    """Resolve an interface path pair without retaining failed path frames."""

    try:
        return _validate_sync_paths(source_path, target_path)
    except BaseException as error:
        retire_exception_graph(error)
        del source_path, target_path
        raise


def _validated_roots(source_path: str, target_path: str) -> tuple[Root, Root]:
    source, target = validate_sync_paths(source_path, target_path)
    return Root(str(source), "source"), Root(str(target), "target")
