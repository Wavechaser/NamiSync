"""Guarded operations engine for reviewed sync plans."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
import os
from pathlib import Path, PureWindowsPath
import time

from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    Outcome,
    Provenance,
    RecordingStatus,
)
from namisync.core.events import ItemOutcome, PhaseChanged, Progress
from namisync.core.execution import (
    Clock,
    Continue,
    CopyBackend,
    CopyDigest,
    ExecutionReason,
    ExecutionSet,
    ExecutorFileSystem,
    FailureDecision,
    FailurePolicy,
    PublishedCopyEvidence,
    Recorder,
    RecordedCopyIdentity,
    Retry,
    Stop,
)
from namisync.core.models import EntryKind, FileStat, MANAGED_FILE_ATTRIBUTE_MASK
from namisync.core.pathing import (
    PathValidationError,
    logical_error_text,
    normalize_relative_path,
)
from namisync.core.planning import (
    OpId,
    OperationKind,
    OperationReason,
    PlanOperation,
)
from namisync.core.root_authority import RootAuthority
from namisync.core.session import (
    Canceled,
    Disposition,
    OperationResult,
    PauseRequested,
    RunContext,
    SessionState,
)

from .native import (
    UnsafeExecutionPath,
    _READONLY,
    _SecurityCopyFailure,
    _UpdateBackupBeforeCopyDrift,
    _UpdateBackupDrift,
)
from .pipeline import _allocation_size, _copy_chunk_size


_SHARING_VIOLATIONS = {32, 33}


class OperationFailure(Exception):
    """A typed, user-actionable operation failure."""

    def __init__(
        self,
        reason: ExecutionReason,
        detail: str,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail
        self.cause = cause


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class BoundedFailurePolicy:
    """Retry Windows sharing violations; continue past every other failure."""

    def __init__(self, *, retries: int = 3, initial_delay: float = 0.05) -> None:
        if retries < 0:
            raise ValueError("retry count cannot be negative")
        if initial_delay < 0:
            raise ValueError("retry delay cannot be negative")
        self._retries = retries
        self._initial_delay = initial_delay

    def on_item_failed(
        self, operation: PlanOperation, error: Exception, attempt: int
    ) -> FailureDecision:
        del operation
        winerror = _find_winerror(error)
        if winerror in _SHARING_VIOLATIONS and attempt <= self._retries:
            return Retry(self._initial_delay * (2 ** (attempt - 1)))
        return Continue()


@dataclass(frozen=True, slots=True)
class ExecutorPolicies:
    """Snapshotted executor policy implementations and bounded pacing."""

    copy_backend: CopyBackend
    failure: FailurePolicy = field(default_factory=BoundedFailurePolicy)
    clock: Clock = field(default_factory=SystemClock)
    max_chunk_size: int = 4 * 1024 * 1024
    max_retries: int = 3
    progress_interval_seconds: float = 0.1
    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        if self.max_chunk_size <= 0:
            raise ValueError("maximum copy chunk size must be positive")
        if self.max_retries < 0:
            raise ValueError("maximum retries cannot be negative")
        if self.progress_interval_seconds < 0:
            raise ValueError("progress interval cannot be negative")
        if not callable(self.monotonic) or not callable(self.sleep):
            raise TypeError("executor timing collaborators must be callable")


def _find_winerror(error: Exception) -> int | None:
    current: BaseException | None = error
    while current is not None:
        winerror = getattr(current, "winerror", None)
        if isinstance(winerror, int):
            return winerror
        current = current.__cause__
    return None


@dataclass(frozen=True, slots=True)
class _Settled:
    outcome: Outcome
    reason: ExecutionReason | None = None
    detail: dict[str, object] = field(default_factory=dict)
    published_evidence: PublishedCopyEvidence | None = None


@dataclass(frozen=True, slots=True)
class _PreparedCopy:
    source: Path
    target: Path
    temp: Path
    digest: CopyDigest
    intended: FileStat
    finalized: FileStat


@dataclass(slots=True)
class _CopyContinuation:
    prepared: _PreparedCopy
    prepared_stat: FileStat
    published: bool = False
    published_stat: FileStat | None = None
    attestation: Attestation | None = None
    detail: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class _UpdateBackup:
    path: Path
    kind: str
    created_stat: FileStat | None = None
    published_stat: FileStat | None = None


@dataclass(slots=True)
class _UpdateContinuation:
    prepared: _PreparedCopy
    prepared_stat: FileStat
    live_stat: FileStat
    backup: _UpdateBackup | None
    detail: dict[str, object]
    published: bool = False
    published_stat: FileStat | None = None
    attestation: Attestation | None = None


@dataclass(slots=True)
class _MoveUpdateContinuation:
    prepared: _PreparedCopy
    prepared_stat: FileStat
    old_relative_path: str
    old_expected: FileStat
    published: bool = False
    published_stat: FileStat | None = None
    trash: Path | None = None
    attestation: Attestation | None = None
    detail: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class _MutationAttempt:
    kind: OperationKind
    primary: Path
    primary_before: FileStat | None
    secondary: Path | None = None
    destination_relative: str | None = None
    trash_source_relative: str | None = None
    committed: bool = False


@dataclass(slots=True)
class _ExecutionState:
    execution_set: ExecutionSet
    outcomes: dict[OpId, ItemOutcome]
    inflight_temp: Path | None = None
    pending_directories: list[PlanOperation] = field(default_factory=list)
    ready_directories: set[OpId] = field(default_factory=set)
    restore_directories: set[OpId] = field(default_factory=set)
    retry_continuations: dict[
        OpId, _CopyContinuation | _UpdateContinuation | _MoveUpdateContinuation
    ] = field(default_factory=dict)
    retry_errors: dict[OpId, Exception] = field(default_factory=dict)
    mutation_attempts: dict[OpId, _MutationAttempt] = field(default_factory=dict)
    pause_latched: bool = False
    filesystem_failed: bool = False

    @property
    def recording(self) -> RecordingStatus:
        return self.execution_set.recording

    @recording.setter
    def recording(self, value: RecordingStatus) -> None:
        self.execution_set.recording = value


class _ProgressTracker:
    def __init__(
        self,
        xset: ExecutionSet,
        ctx: RunContext,
        policies: ExecutorPolicies,
    ) -> None:
        self._ctx = ctx
        self._policies = policies
        self.items_total = len(xset.selection)
        self.items_done = len(xset.status)
        self.bytes_total = sum(
            operation.content_bytes
            for operation in xset.plan.operations
            if operation.op_id in xset.selection
            and operation.kind
            in {OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE}
        )
        settled_ids = set(xset.status)
        self._committed_bytes = sum(
            operation.content_bytes
            for operation in xset.plan.operations
            if operation.op_id in settled_ids
            and xset.status[operation.op_id] is Outcome.SUCCEEDED
            and operation.kind
            in {OperationKind.COPY, OperationKind.UPDATE, OperationKind.MOVE_UPDATE}
        )
        self.bytes_done = min(self._committed_bytes, self.bytes_total)
        self._file_bytes = 0
        self._current: PlanOperation | None = None
        self._last_emitted_at = float("-inf")

    def start(self, operation: PlanOperation) -> None:
        self._current = operation
        self._file_bytes = 0
        self.emit(force=False)

    def copied(self, size: int) -> None:
        self._file_bytes += size
        candidate = min(
            self.bytes_total,
            self._committed_bytes + min(self._file_bytes, self._current.content_bytes),
        )
        self.bytes_done = max(self.bytes_done, candidate)
        self.emit(force=False)

    def settled(self, operation: PlanOperation, outcome: Outcome) -> None:
        self.items_done += 1
        if outcome is Outcome.SUCCEEDED and operation.kind in {
            OperationKind.COPY,
            OperationKind.UPDATE,
            OperationKind.MOVE_UPDATE,
        }:
            self._committed_bytes = min(
                self.bytes_total, self._committed_bytes + operation.content_bytes
            )
            self.bytes_done = max(self.bytes_done, self._committed_bytes)
        self._current = operation
        self.emit(force=False)

    def emit(self, *, force: bool) -> None:
        now = self._policies.monotonic()
        if (
            not force
            and now - self._last_emitted_at
            < self._policies.progress_interval_seconds
        ):
            return
        self._last_emitted_at = now
        self._ctx.emit(
            Progress(
                items_done=self.items_done,
                items_total=self.items_total,
                bytes_done=min(self.bytes_done, self.bytes_total),
                bytes_total=self.bytes_total,
                current_path=(
                    None if self._current is None else self._current.target_rel_path
                ),
            )
        )


def execute(
    xset: ExecutionSet,
    ctx: RunContext,
    recorder: Recorder,
    policies: ExecutorPolicies,
    fs: ExecutorFileSystem,
) -> OperationResult:
    """Apply remaining selected operations without emitting a terminal event.

    Commitment matching and fresh observe/preflight are workflow obligations.
    This function assumes they succeeded and retains the operation-local live
    guards that remain necessary at every point of touch.
    """

    source_root = Path(xset.plan.source_root.path)
    target_root = Path(xset.plan.target_root.path)
    state = _ExecutionState(
        execution_set=xset,
        outcomes={},
        restore_directories={
            operation.op_id
            for operation in xset.plan.operations
            if operation.kind is OperationKind.MKDIR
            and xset.status.get(operation.op_id) is Outcome.SUCCEEDED
        },
    )
    progress = _ProgressTracker(xset, ctx, policies)
    ctx.emit(PhaseChanged("execute"))
    progress.emit(force=True)
    current: PlanOperation | None = None

    try:
        stop_requested = False
        for operation in xset.plan.operations:
            if operation.op_id not in xset.selection or operation.op_id in xset.status:
                continue
            current = operation

            if stop_requested:
                _policy_stop_checkpoint(ctx)
                progress.start(operation)
                _settle(
                    xset,
                    state,
                    progress,
                    ctx,
                    operation,
                    _Settled(Outcome.CANCELED, ExecutionReason.POLICY_STOP),
                )
                continue
            ctx.checkpoint()
            progress.start(operation)
            if operation.blocked:
                _settle(
                    xset,
                    state,
                    progress,
                    ctx,
                    operation,
                    _Settled(
                        Outcome.FAILED,
                        ExecutionReason.BLOCKED,
                        {"blocked_reason": operation.blocked_reason.value},
                    ),
                )
                continue
            if not _dependencies_succeeded(xset, state, operation):
                _settle(
                    xset,
                    state,
                    progress,
                    ctx,
                    operation,
                    _Settled(Outcome.DEFERRED, ExecutionReason.DEPENDENCY_FAILED),
                )
                continue
            if operation.kind is OperationKind.MKDIR:
                try:
                    _start_directory(
                        operation,
                        xset,
                        fs,
                        source_root,
                        target_root,
                        state,
                    )
                except (Canceled, PauseRequested):
                    raise
                except Exception as error:
                    mutation_failure = _failed_after_mutation_settlement(
                        operation,
                        error,
                        fs,
                        state,
                    )
                    state.mutation_attempts.pop(operation.op_id, None)
                    if mutation_failure is None:
                        _settle_failure(xset, state, progress, ctx, operation, error)
                    else:
                        _settle(
                            xset,
                            state,
                            progress,
                            ctx,
                            operation,
                            mutation_failure,
                        )
                continue

            attempt = 0
            while True:
                attempt += 1
                try:
                    settled = _execute_operation(
                        operation,
                        xset,
                        ctx,
                        recorder,
                        policies,
                        fs,
                        source_root,
                        target_root,
                        state,
                        progress,
                    )
                except (Canceled, PauseRequested):
                    raise
                except Exception as error:
                    decision = policies.failure.on_item_failed(operation, error, attempt)
                    if (
                        isinstance(decision, Retry)
                        and attempt <= policies.max_retries
                    ):
                        state.retry_errors[operation.op_id] = error
                        retry_cleanup_error: Exception | None = None
                        if (
                            operation.op_id not in state.retry_continuations
                            and operation.op_id not in state.mutation_attempts
                        ):
                            retry_cleanup_error = _cleanup_inflight(state, fs)
                        if retry_cleanup_error is None:
                            _retry_checkpoint(ctx, state, operation.op_id)
                            policies.sleep(decision.after)
                            _retry_checkpoint(ctx, state, operation.op_id)
                            continue
                        error = OperationFailure(
                            ExecutionReason.CLEANUP_FAILED,
                            "operation failed and its owned temp could not be removed: "
                            f"{logical_error_text(retry_cleanup_error)}",
                            cause=error,
                        )
                    durable_failure = _failed_durable_settlement(
                        operation,
                        error,
                        fs,
                        target_root,
                        state,
                    )
                    cleanup_error = _cleanup_inflight(state, fs)
                    if cleanup_error is not None:
                        if durable_failure is None:
                            error = OperationFailure(
                                ExecutionReason.CLEANUP_FAILED,
                                "operation failed and its owned temp could not be removed: "
                                f"{logical_error_text(cleanup_error)}",
                                cause=error,
                            )
                        else:
                            detail = dict(durable_failure.detail)
                            detail["cleanup_error"] = logical_error_text(
                                cleanup_error
                            )
                            durable_failure = replace(
                                durable_failure,
                                detail=detail,
                            )
                    state.retry_continuations.pop(operation.op_id, None)
                    state.retry_errors.pop(operation.op_id, None)
                    state.mutation_attempts.pop(operation.op_id, None)
                    if durable_failure is None:
                        _settle_failure(
                            xset,
                            state,
                            progress,
                            ctx,
                            operation,
                            error,
                        )
                    else:
                        _settle(
                            xset,
                            state,
                            progress,
                            ctx,
                            operation,
                            durable_failure,
                        )
                    if isinstance(decision, Stop):
                        stop_requested = True
                        state.pause_latched = False
                    elif state.pause_latched:
                        state.pause_latched = False
                        raise PauseRequested()
                    break
                else:
                    state.retry_continuations.pop(operation.op_id, None)
                    state.retry_errors.pop(operation.op_id, None)
                    state.mutation_attempts.pop(operation.op_id, None)
                    _settle(xset, state, progress, ctx, operation, settled)
                    if state.pause_latched:
                        state.pause_latched = False
                        raise PauseRequested()
                    break

        _finalize_directories(
            xset, ctx, recorder, fs, target_root, state, progress
        )
        _restore_completed_directory_metadata(xset, fs, target_root, state)
        try:
            recorder.flush()
        except Exception:
            state.recording = RecordingStatus.DEGRADED
    except Canceled:
        durable_settlement = (
            None
            if current is None or current.op_id in xset.status
            else _canceled_durable_settlement(
                current,
                fs,
                target_root,
                state,
            )
        )
        cleanup_error = _cleanup_inflight(state, fs)
        if durable_settlement is not None and current is not None:
            detail = dict(durable_settlement.detail)
            if cleanup_error is not None:
                detail["cleanup_error"] = logical_error_text(cleanup_error)
                cleanup_error = None
            state.retry_continuations.pop(current.op_id, None)
            state.retry_errors.pop(current.op_id, None)
            state.mutation_attempts.pop(current.op_id, None)
            _settle(
                xset,
                state,
                progress,
                ctx,
                current,
                replace(durable_settlement, detail=detail),
            )
        if current is not None:
            state.mutation_attempts.pop(current.op_id, None)
        _finalize_directories(
            xset, ctx, recorder, fs, target_root, state, progress
        )
        _restore_completed_directory_metadata(xset, fs, target_root, state)
        for operation in xset.plan.operations:
            if operation.op_id in xset.selection and operation.op_id not in xset.status:
                detail = {}
                if cleanup_error is not None and operation is current:
                    detail["cleanup_error"] = logical_error_text(cleanup_error)
                _settle(
                    xset,
                    state,
                    progress,
                    ctx,
                    operation,
                    _Settled(Outcome.CANCELED, ExecutionReason.CANCELED, detail),
                )
        try:
            recorder.flush()
        except Exception:
            state.recording = RecordingStatus.DEGRADED
        raise
    except PauseRequested:
        _cleanup_inflight(state, fs)
        _finalize_directories(
            xset, ctx, recorder, fs, target_root, state, progress
        )
        _restore_completed_directory_metadata(xset, fs, target_root, state)
        try:
            recorder.flush()
        except Exception:
            state.recording = RecordingStatus.DEGRADED
        raise
    except BaseException:
        _cleanup_inflight(state, fs)
        try:
            recorder.flush()
        except Exception:
            state.recording = RecordingStatus.DEGRADED
        raise

    items = tuple(
        state.outcomes.get(operation.op_id)
        or ItemOutcome(
            item_id=str(operation.op_id),
            kind=operation.kind.value,
            path=operation.target_rel_path,
            outcome=xset.status[operation.op_id],
            reason="previously-settled",
            detail={"continued": True},
        )
        for operation in xset.plan.operations
        if operation.op_id in xset.selection
    )
    failed = state.filesystem_failed or any(
        outcome
        in {Outcome.FAILED, Outcome.CANCELED, Outcome.DEFERRED}
        for outcome in xset.status.values()
    )
    progress.emit(force=True)
    return OperationResult(
        status=SessionState.FAILED if failed else SessionState.COMPLETED,
        recording=state.recording,
        audit=RecordingStatus.OK,
        disposition=Disposition.RAN,
        canceled=False,
        items=items,
        bytes_done=min(progress.bytes_done, progress.bytes_total),
        bytes_total=progress.bytes_total,
    )


def _execute_operation(
    operation: PlanOperation,
    xset: ExecutionSet,
    ctx: RunContext,
    recorder: Recorder,
    policies: ExecutorPolicies,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
    progress: _ProgressTracker,
) -> _Settled:
    _revalidate_target_root(fs, xset, target_root)
    if operation.source_rel_path is not None:
        _revalidate_source_root(fs, xset, source_root)
    if operation.kind is OperationKind.COPY:
        return _copy(
            operation,
            xset,
            ctx,
            recorder,
            policies,
            fs,
            source_root,
            target_root,
            state,
            progress,
        )
    if operation.kind is OperationKind.UPDATE:
        return _update(
            operation,
            xset,
            ctx,
            recorder,
            policies,
            fs,
            source_root,
            target_root,
            state,
            progress,
        )
    if operation.kind is OperationKind.MOVE:
        return _move(
            operation,
            xset,
            recorder,
            fs,
            source_root,
            target_root,
            state,
        )
    if operation.kind is OperationKind.RECASE:
        return _recase(
            operation,
            xset,
            recorder,
            fs,
            source_root,
            target_root,
            state,
        )
    if operation.kind is OperationKind.MOVE_UPDATE:
        return _move_update(
            operation,
            xset,
            ctx,
            recorder,
            policies,
            fs,
            source_root,
            target_root,
            state,
            progress,
        )
    if operation.kind is OperationKind.TRASH:
        return _trash(operation, xset, recorder, fs, target_root, state)
    if operation.kind is OperationKind.DELETE:
        return _delete(operation, xset, recorder, fs, target_root, state)
    if operation.kind is OperationKind.NOOP:
        return _noop(operation, recorder, fs, source_root, target_root, state)
    raise OperationFailure(
        ExecutionReason.IO_ERROR, f"unsupported operation kind: {operation.kind}"
    )


def _prepare_copy(
    operation: PlanOperation,
    xset: ExecutionSet,
    ctx: RunContext,
    policies: ExecutorPolicies,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
    progress: _ProgressTracker,
) -> _PreparedCopy:
    if operation.source_rel_path is None or operation.source_expected is None:
        raise OperationFailure(
            ExecutionReason.SOURCE_MISSING, "copy operation has no source evidence"
        )
    _revalidate_source_root(fs, xset, source_root)
    _guard_present(
        fs,
        source_root,
        operation.source_rel_path,
        operation.source_expected,
        missing=ExecutionReason.SOURCE_MISSING,
        drift=ExecutionReason.SOURCE_DRIFT,
    )
    _guard_expected_target(fs, target_root, operation)
    source = fs.resolve(source_root, operation.source_rel_path, must_exist=True)
    target = fs.resolve(target_root, operation.target_rel_path, must_exist=False)
    temp = fs.owned_temp(target, xset.run_id, operation.op_id)
    try:
        _resolve_target_path(
            fs,
            xset,
            target_root,
            temp,
            must_exist=False,
        )
        fs.remove_owned_temp(temp)
    except Exception as error:
        raise OperationFailure(
            ExecutionReason.CLEANUP_FAILED,
            f"cannot recover owned temp: {temp}",
            cause=error,
        ) from error
    state.inflight_temp = temp
    try:
        reviewed_size = operation.source_expected.size
        chunk_size = _copy_chunk_size(reviewed_size, policies.max_chunk_size)
        _revalidate_source_root(fs, xset, source_root)
        with fs.open_source(source) as reader:
            _resolve_target_path(
                fs,
                xset,
                target_root,
                temp,
                must_exist=False,
            )
            with fs.create_temp(
                temp, allocation_size=_allocation_size(reviewed_size)
            ) as writer:
                digest = policies.copy_backend.copy(
                    reader,
                    writer,
                    chunk_size=chunk_size,
                    checkpoint=ctx.checkpoint,
                    on_chunk=progress.copied,
                )
        intended = operation.intended or operation.source_expected
        if digest.size != reviewed_size:
            raise OperationFailure(
                ExecutionReason.SOURCE_DRIFT,
                "source byte count changed during copy",
            )
        try:
            _revalidate_source_root(fs, xset, source_root)
            _resolve_target_path(
                fs,
                xset,
                target_root,
                temp,
                must_exist=True,
            )
            finalized = fs.finalize_temp(
                temp,
                intended,
                preserve_created=xset.plan.preservation.preserve_created,
                acl_source=source if xset.plan.preservation.preserve_acl else None,
            )
        except _SecurityCopyFailure as error:
            raise OperationFailure(
                ExecutionReason.ACL_COPY_FAILED,
                "security descriptor copy failed before publish",
                cause=error.__cause__ if isinstance(error.__cause__, Exception) else error,
            ) from error
        ctx.checkpoint()
        _revalidate_source_root(fs, xset, source_root)
        _guard_present(
            fs,
            source_root,
            operation.source_rel_path,
            operation.source_expected,
            missing=ExecutionReason.SOURCE_MISSING,
            drift=ExecutionReason.SOURCE_DRIFT,
        )
        _guard_expected_target(fs, target_root, operation)
        return _PreparedCopy(source, target, temp, digest, intended, finalized)
    except BaseException:
        raise


def _published_copy_stat(
    prepared: _PreparedCopy,
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
    target_root: Path,
) -> FileStat:
    target = _resolve_target_path(
        fs,
        xset,
        target_root,
        prepared.target,
        must_exist=True,
    )
    observed = fs.ensure_published_metadata(
        target,
        prepared.finalized,
        prepared.intended,
        preserve_created=xset.plan.preservation.preserve_created,
        apply_readonly=True,
    )
    return _profiled_stat(
        observed, xset.plan.target_profile.stable_file_identity
    )


def _guard_resumed_published_target(
    continuation: (
        _CopyContinuation | _UpdateContinuation | _MoveUpdateContinuation
    ),
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
    target_root: Path,
) -> None:
    stable_identity = xset.plan.target_profile.stable_file_identity
    observed = _stat_target_path(
        fs,
        xset,
        target_root,
        continuation.prepared.target,
    )
    if observed is None:
        raise OperationFailure(
            ExecutionReason.TARGET_DRIFT,
            "published target disappeared during retry",
        )
    if continuation.published_stat is None:
        matches = _same_unrepaired_publication(
            observed,
            continuation.prepared_stat,
            stable_identity,
        )
    else:
        expected = _profiled_stat(continuation.published_stat, stable_identity)
        actual = _profiled_stat(observed, stable_identity)
        matches = _same_file_version(actual, expected)
    if not matches:
        raise OperationFailure(
            ExecutionReason.TARGET_DRIFT,
            "published target drifted during retry",
        )


def _same_unrepaired_publication(
    actual: FileStat,
    created: FileStat,
    stable_identity: bool,
) -> bool:
    return (
        actual.kind is created.kind
        and actual.size == created.size
        and (
            not stable_identity
            or created.file_identity is None
            or actual.file_identity == created.file_identity
        )
    )


def _guard_published_prepared_copy(
    continuation: (
        _CopyContinuation | _UpdateContinuation | _MoveUpdateContinuation
    ),
    xset: ExecutionSet,
) -> None:
    assert continuation.published_stat is not None
    if not _same_unrepaired_publication(
        continuation.published_stat,
        continuation.prepared_stat,
        xset.plan.target_profile.stable_file_identity,
    ):
        raise OperationFailure(
            ExecutionReason.TARGET_DRIFT,
            "published target does not match the prepared copy",
        )


def _complete_published_byte_operation(
    continuation: (
        _CopyContinuation | _UpdateContinuation | _MoveUpdateContinuation
    ),
    xset: ExecutionSet,
    policies: ExecutorPolicies,
    fs: ExecutorFileSystem,
    state: _ExecutionState,
    target_root: Path,
    *,
    resumed_published: bool,
    finish_filesystem: Callable[[], tuple[Path, ...]],
    record_published: Callable[[Attestation], RecordedCopyIdentity],
    attest_before_filesystem: bool = False,
) -> _Settled:
    if resumed_published:
        _guard_resumed_published_target(
            continuation,
            xset,
            fs,
            target_root,
        )
    if continuation.published_stat is None:
        continuation.published_stat = _published_copy_stat(
            continuation.prepared,
            xset,
            fs,
            target_root,
        )
    assert continuation.published_stat is not None
    _guard_attestation_size(
        continuation.prepared.digest,
        continuation.published_stat,
    )
    _guard_published_prepared_copy(continuation, xset)
    if attest_before_filesystem and continuation.attestation is None:
        continuation.attestation = _attestation(
            continuation.prepared.digest,
            continuation.published_stat,
            policies.clock,
        )
    durability_paths = finish_filesystem()
    continuation.detail.update(_durability_detail(fs, *durability_paths))
    if continuation.attestation is None:
        continuation.attestation = _attestation(
            continuation.prepared.digest,
            continuation.published_stat,
            policies.clock,
        )
    assert continuation.attestation is not None
    recorded_identity = _record(
        state,
        continuation.detail,
        lambda: record_published(continuation.attestation),
        identity_required=True,
    )
    return _Settled(
        Outcome.SUCCEEDED,
        detail=continuation.detail,
        published_evidence=PublishedCopyEvidence(
            continuation.attestation,
            recorded_identity,
        ),
    )


def _guard_update_backup(
    backup: _UpdateBackup,
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
) -> None:
    stable_identity = xset.plan.target_profile.stable_file_identity
    actual = _require_stat_path(fs, backup.path)
    if backup.published_stat is None:
        if backup.created_stat is None:
            raise RuntimeError("update backup lacks creation evidence")
        matches = _same_unrepaired_publication(
            actual,
            backup.created_stat,
            stable_identity,
        )
    else:
        matches = _same_file_version(
            _profiled_stat(actual, stable_identity),
            backup.published_stat,
        )
    if not matches:
        raise OperationFailure(
            ExecutionReason.TRASH_COLLISION,
            "update backup drifted after publication",
        )


def _observe_update_backup_creation(
    continuation: _UpdateContinuation,
    operation: PlanOperation,
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
    target_root: Path,
) -> None:
    backup = continuation.backup
    if backup is None:
        return
    if backup.created_stat is None:
        _revalidate_target_root(fs, xset, target_root)
        fs.revalidate_trash_destination(
            target_root,
            xset.run_id,
            operation.target_rel_path,
            backup.path,
        )
        backup.created_stat = _require_stat_path(fs, backup.path)


def _expected_update_live(continuation: _UpdateContinuation) -> FileStat:
    backup = continuation.backup
    if backup is None or backup.kind != "hardlink":
        return continuation.live_stat
    return replace(
        continuation.live_stat,
        nlink=continuation.live_stat.nlink + 1,
    )


def _repair_update_backup_metadata(
    backup: _UpdateBackup,
    operation: PlanOperation,
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
    target_root: Path,
    *,
    validate_before_repair: bool,
) -> None:
    fs.revalidate_trash_destination(
        target_root,
        xset.run_id,
        operation.target_rel_path,
        backup.path,
    )
    if validate_before_repair:
        _guard_update_backup(backup, xset, fs)
    if backup.published_stat is not None:
        return
    expected = operation.target_expected
    if expected is None:
        raise RuntimeError("update backup requires displaced target evidence")
    repaired = fs.ensure_published_metadata(
        backup.path,
        expected,
        expected,
        preserve_created=True,
        apply_readonly=True,
    )
    backup.published_stat = _profiled_stat(
        repaired,
        xset.plan.target_profile.stable_file_identity,
    )


def _finish_update_filesystem(
    continuation: _UpdateContinuation,
    operation: PlanOperation,
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
    target_root: Path,
    *,
    validate_before_repair: bool,
) -> tuple[Path, ...]:
    backup = continuation.backup
    if backup is None:
        return (continuation.prepared.target.parent,)
    if backup.kind == "hardlink":
        _repair_update_backup_metadata(
            backup,
            operation,
            xset,
            fs,
            target_root,
            validate_before_repair=validate_before_repair,
        )
    else:
        fs.revalidate_trash_destination(
            target_root,
            xset.run_id,
            operation.target_rel_path,
            backup.path,
        )
        if validate_before_repair:
            _guard_update_backup(backup, xset, fs)
    return (
        continuation.prepared.target.parent,
        backup.path.parent,
    )


def _copy(
    operation: PlanOperation,
    xset: ExecutionSet,
    ctx: RunContext,
    recorder: Recorder,
    policies: ExecutorPolicies,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
    progress: _ProgressTracker,
) -> _Settled:
    existing = state.retry_continuations.get(operation.op_id)
    resumed_published = existing is not None and existing.published
    if existing is None:
        prepared = _prepare_copy(
            operation,
            xset,
            ctx,
            policies,
            fs,
            source_root,
            target_root,
            state,
            progress,
        )
        continuation = _CopyContinuation(
            prepared=prepared,
            prepared_stat=_require_stat_path(fs, prepared.temp),
        )
        state.retry_continuations[operation.op_id] = continuation
    elif isinstance(existing, _CopyContinuation):
        continuation = existing
        prepared = continuation.prepared
    else:
        raise RuntimeError("executor continuation kind does not match copy")

    if not continuation.published:
        temp_stat = _stat_target_path(
            fs,
            xset,
            target_root,
            prepared.temp,
        )
        if temp_stat is None:
            published = _require_target_stat(
                fs,
                xset,
                target_root,
                prepared.target,
            )
            if not _same_file_version(published, continuation.prepared_stat):
                raise OperationFailure(
                    ExecutionReason.TARGET_DRIFT,
                    "copy temp disappeared without the prepared file being published",
                )
            continuation.published = True
            state.inflight_temp = None
        else:
            _revalidate_source_root(fs, xset, source_root)
            _guard_present(
                fs,
                source_root,
                operation.source_rel_path,
                operation.source_expected,
                missing=ExecutionReason.SOURCE_MISSING,
                drift=ExecutionReason.SOURCE_DRIFT,
            )
            _guard_path_stat(
                temp_stat,
                continuation.prepared_stat,
                ExecutionReason.TARGET_DRIFT,
                "prepared copy temp drifted before retry",
            )
            _guard_expected_target(fs, target_root, operation)
            try:
                _revalidate_source_root(fs, xset, source_root)
                _revalidate_target_root(fs, xset, target_root)
                fs.publish_new(prepared.temp, prepared.target)
            except FileExistsError as error:
                raise OperationFailure(
                    ExecutionReason.DESTINATION_OCCUPIED,
                    "destination appeared before conditional publish",
                    cause=error,
                ) from error
            state.inflight_temp = None
            continuation.published = True

    return _complete_published_byte_operation(
        continuation,
        xset,
        policies,
        fs,
        state,
        target_root,
        resumed_published=resumed_published,
        finish_filesystem=lambda: (prepared.target.parent,),
        record_published=lambda attestation: recorder.record_copied(
            operation.op_id,
            attestation,
        ),
    )


def _update(
    operation: PlanOperation,
    xset: ExecutionSet,
    ctx: RunContext,
    recorder: Recorder,
    policies: ExecutorPolicies,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
    progress: _ProgressTracker,
) -> _Settled:
    if operation.target_expected is None:
        raise OperationFailure(
            ExecutionReason.TARGET_MISSING, "update has no displaced target evidence"
        )
    existing = state.retry_continuations.get(operation.op_id)
    resumed_published = existing is not None and existing.published
    if existing is None:
        prepared = _prepare_copy(
            operation,
            xset,
            ctx,
            policies,
            fs,
            source_root,
            target_root,
            state,
            progress,
        )
        live_stat = _guard_present(
            fs,
            target_root,
            operation.target_rel_path,
            operation.target_expected,
            missing=ExecutionReason.TARGET_MISSING,
            drift=ExecutionReason.TARGET_DRIFT,
        )
        prepared_stat = _require_stat_path(fs, prepared.temp)
        detail: dict[str, object] = {}
        backup: _UpdateBackup | None = None
        backup_error: Exception | None = None
        if xset.plan.trash_on_update:
            _revalidate_target_root(fs, xset, target_root)
            backup_path = fs.trash_destination(
                target_root, xset.run_id, operation.target_rel_path
            )
            fs.revalidate_trash_destination(
                target_root,
                xset.run_id,
                operation.target_rel_path,
                backup_path,
            )
            if fs.stat_path(backup_path) is not None:
                raise OperationFailure(
                    ExecutionReason.TRASH_COLLISION,
                    f"update trash exists: {backup_path}",
                )
            backup_kind = (
                "hardlink"
                if xset.plan.target_profile.supports_hardlinks
                else "copy"
            )
            detail["backup"] = backup_kind
            try:
                if backup_kind == "hardlink":
                    fs.revalidate_trash_destination(
                        target_root,
                        xset.run_id,
                        operation.target_rel_path,
                        backup_path,
                    )
                    fs.hardlink(prepared.target, backup_path)
                else:
                    backup_temp = fs.owned_temp(
                        backup_path,
                        xset.run_id,
                        operation.op_id,
                    )

                    def validate_backup_destination() -> None:
                        _revalidate_target_root(fs, xset, target_root)
                        fs.revalidate_trash_destination(
                            target_root,
                            xset.run_id,
                            operation.target_rel_path,
                            backup_path,
                        )

                    try:
                        validate_backup_destination()
                        fs.remove_owned_temp(backup_temp)
                    except Exception as error:
                        raise OperationFailure(
                            ExecutionReason.CLEANUP_FAILED,
                            f"cannot recover exact backup temp: {backup_temp}",
                            cause=error,
                        ) from error
                    try:
                        fs.copy_backup(
                            prepared.target,
                            backup_temp,
                            backup_path,
                            live_stat,
                            ctx.checkpoint,
                            validate_backup_destination,
                        )
                    except _UpdateBackupDrift as error:
                        message = (
                            "live update target drifted before its backup was copied"
                            if isinstance(error, _UpdateBackupBeforeCopyDrift)
                            else "live update target drifted while its backup was copied"
                        )
                        translated = OperationFailure(
                            ExecutionReason.TARGET_DRIFT,
                            message,
                            cause=error,
                        )
                        for note in getattr(error, "__notes__", ()):
                            translated.add_note(note)
                        raise translated from error
            except (Canceled, PauseRequested):
                raise
            except Exception as error:
                fs.revalidate_trash_destination(
                    target_root,
                    xset.run_id,
                    operation.target_rel_path,
                    backup_path,
                )
                if fs.stat_path(backup_path) is None:
                    raise
                backup_error = error
            backup = _UpdateBackup(
                path=backup_path,
                kind=backup_kind,
            )
        continuation = _UpdateContinuation(
            prepared=prepared,
            prepared_stat=prepared_stat,
            live_stat=live_stat,
            backup=backup,
            detail=detail,
        )
        state.retry_continuations[operation.op_id] = continuation
        if backup_error is not None:
            _observe_update_backup_creation(
                continuation,
                operation,
                xset,
                fs,
                target_root,
            )
            raise backup_error
    elif isinstance(existing, _UpdateContinuation):
        continuation = existing
        prepared = continuation.prepared
    else:
        raise RuntimeError("executor continuation kind does not match update")

    if not continuation.published:
        _flush_before_destructive(recorder, state)
        _revalidate_source_root(fs, xset, source_root)
        _revalidate_target_root(fs, xset, target_root)
        if continuation.backup is not None:
            fs.revalidate_trash_destination(
                target_root,
                xset.run_id,
                operation.target_rel_path,
                continuation.backup.path,
            )
    _observe_update_backup_creation(
        continuation,
        operation,
        xset,
        fs,
        target_root,
    )
    if (
        not continuation.published
        and continuation.backup is not None
        and continuation.backup.kind == "copy"
    ):
        live = _require_target_stat(
            fs,
            xset,
            target_root,
            prepared.target,
        )
        _guard_path_stat(
            live,
            _expected_update_live(continuation),
            ExecutionReason.TARGET_DRIFT,
            "live update target drifted before backup metadata repair",
        )
        _repair_update_backup_metadata(
            continuation.backup,
            operation,
            xset,
            fs,
            target_root,
            validate_before_repair=existing is not None,
        )

    if not continuation.published:
        if continuation.backup is not None:
            _guard_update_backup(continuation.backup, xset, fs)
        temp_stat = _stat_target_path(
            fs,
            xset,
            target_root,
            prepared.temp,
        )
        if temp_stat is None:
            published = _require_target_stat(
                fs,
                xset,
                target_root,
                prepared.target,
            )
            if not _same_file_version(published, continuation.prepared_stat):
                raise OperationFailure(
                    ExecutionReason.TARGET_DRIFT,
                    "update temp disappeared without the prepared file being published",
                )
            continuation.published = True
            state.inflight_temp = None
        else:
            _revalidate_source_root(fs, xset, source_root)
            _guard_present(
                fs,
                source_root,
                operation.source_rel_path,
                operation.source_expected,
                missing=ExecutionReason.SOURCE_MISSING,
                drift=ExecutionReason.SOURCE_DRIFT,
            )
            _guard_path_stat(
                temp_stat,
                continuation.prepared_stat,
                ExecutionReason.TARGET_DRIFT,
                "prepared update temp drifted before retry",
            )
            live = _require_target_stat(
                fs,
                xset,
                target_root,
                prepared.target,
            )
            _guard_path_stat(
                live,
                _expected_update_live(continuation),
                ExecutionReason.TARGET_DRIFT,
                "live update target drifted after its backup was created",
            )
            if continuation.backup is not None:
                fs.revalidate_trash_destination(
                    target_root,
                    xset.run_id,
                    operation.target_rel_path,
                    continuation.backup.path,
                )
            readonly_cleared = bool(
                operation.target_expected.metadata.attributes & _READONLY
            )
            _revalidate_source_root(fs, xset, source_root)
            _revalidate_target_root(fs, xset, target_root)
            if readonly_cleared:
                _retain_mutation_attempt(
                    state,
                    operation,
                    primary=prepared.target,
                    primary_before=live,
                )
            try:
                if readonly_cleared:
                    fs.clear_readonly(prepared.target)
                _revalidate_source_root(fs, xset, source_root)
                _revalidate_target_root(fs, xset, target_root)
                fs.replace(prepared.temp, prepared.target)
                state.inflight_temp = None
                continuation.published = True
                state.mutation_attempts.pop(operation.op_id, None)
            finally:
                live = _stat_target_path(
                    fs,
                    xset,
                    target_root,
                    prepared.target,
                )
                if (
                    readonly_cleared
                    and not continuation.published
                    and live is not None
                    and _same_file_version(live, continuation.live_stat)
                ):
                    fs.apply_metadata(
                        prepared.target,
                        operation.target_expected,
                        preserve_created=xset.plan.preservation.preserve_created,
                        apply_readonly=True,
                    )

    return _complete_published_byte_operation(
        continuation,
        xset,
        policies,
        fs,
        state,
        target_root,
        resumed_published=resumed_published,
        finish_filesystem=lambda: _finish_update_filesystem(
            continuation,
            operation,
            xset,
            fs,
            target_root,
            validate_before_repair=resumed_published,
        ),
        record_published=lambda attestation: recorder.record_updated(
            operation.op_id,
            attestation,
        ),
    )


def _move(
    operation: PlanOperation,
    xset: ExecutionSet,
    recorder: Recorder,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
) -> _Settled:
    if operation.source_rel_path is None or operation.source_expected is None:
        raise OperationFailure(
            ExecutionReason.SOURCE_MISSING,
            "move operation lacks source evidence",
        )
    old_rel, old_expected = _prior_target(operation)
    _flush_before_destructive(recorder, state)
    _revalidate_source_root(fs, xset, source_root)
    _revalidate_target_root(fs, xset, target_root)
    _guard_present(
        fs,
        source_root,
        operation.source_rel_path,
        operation.source_expected,
        missing=ExecutionReason.SOURCE_MISSING,
        drift=ExecutionReason.SOURCE_DRIFT,
    )
    old_actual = _guard_present(
        fs,
        target_root,
        old_rel,
        old_expected,
        missing=ExecutionReason.TARGET_MISSING,
        drift=ExecutionReason.TARGET_DRIFT,
    )
    _guard_absent(fs, target_root, operation.target_rel_path)
    old = fs.resolve(target_root, old_rel, must_exist=True)
    new = fs.resolve(target_root, operation.target_rel_path, must_exist=False)
    _revalidate_source_root(fs, xset, source_root)
    _revalidate_target_root(fs, xset, target_root)
    mutation = _retain_mutation_attempt(
        state,
        operation,
        primary=old,
        primary_before=old_actual,
        secondary=new,
    )
    try:
        fs.rename_new(old, new)
    except FileExistsError as error:
        raise OperationFailure(
            ExecutionReason.DESTINATION_OCCUPIED,
            "move destination appeared before conditional rename",
            cause=error,
        ) from error
    mutation.committed = True
    detail = _durability_detail(fs, old.parent, new.parent)
    moved = _profiled_stat(
        _require_target_stat(fs, xset, target_root, new),
        xset.plan.target_profile.stable_file_identity,
    )
    _guard_path_stat(
        moved,
        old_expected,
        ExecutionReason.TARGET_DRIFT,
        "moved target is not the reviewed target version",
    )
    _record(state, detail, lambda: recorder.record_moved(operation.op_id, moved))
    return _Settled(Outcome.SUCCEEDED, detail=detail)


def _recase(
    operation: PlanOperation,
    xset: ExecutionSet,
    recorder: Recorder,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
) -> _Settled:
    old_rel, old_expected = _prior_target(operation)
    if operation.source_rel_path is None or operation.source_expected is None:
        raise OperationFailure(
            ExecutionReason.SOURCE_MISSING,
            "recase operation lacks source evidence",
        )
    if (
        old_rel == operation.target_rel_path
        or normalize_relative_path(old_rel)
        != normalize_relative_path(operation.target_rel_path)
    ):
        raise OperationFailure(
            ExecutionReason.UNSAFE_PATH,
            "recase paths must differ only by Windows filename casing",
        )
    _flush_before_destructive(recorder, state)
    _revalidate_source_root(fs, xset, source_root)
    _revalidate_target_root(fs, xset, target_root)
    _guard_present(
        fs,
        source_root,
        operation.source_rel_path,
        operation.source_expected,
        missing=ExecutionReason.SOURCE_MISSING,
        drift=ExecutionReason.SOURCE_DRIFT,
    )
    old_actual = _guard_present(
        fs,
        target_root,
        old_rel,
        old_expected,
        missing=ExecutionReason.TARGET_MISSING,
        drift=ExecutionReason.TARGET_DRIFT,
    )
    old = fs.resolve(target_root, old_rel, must_exist=True)
    new = fs.resolve(target_root, operation.target_rel_path, must_exist=False)
    _revalidate_source_root(fs, xset, source_root)
    _revalidate_target_root(fs, xset, target_root)
    mutation = _retain_mutation_attempt(
        state,
        operation,
        primary=old,
        primary_before=old_actual,
        secondary=new,
    )
    try:
        fs.rename_new(old, new)
    except FileExistsError as error:
        raise OperationFailure(
            ExecutionReason.DESTINATION_OCCUPIED,
            "recase destination is a distinct occupied entry",
            cause=error,
        ) from error
    mutation.committed = True
    detail = _durability_detail(fs, old.parent, new.parent)
    recased = _profiled_stat(
        _require_target_stat(fs, xset, target_root, new),
        xset.plan.target_profile.stable_file_identity,
    )
    _guard_path_stat(
        recased,
        old_expected,
        ExecutionReason.TARGET_DRIFT,
        "recased target is not the reviewed target version",
    )
    _record(
        state,
        detail,
        lambda: recorder.record_recased(operation.op_id, recased),
    )
    return _Settled(Outcome.SUCCEEDED, detail=detail)


def _finish_move_update_filesystem(
    continuation: _MoveUpdateContinuation,
    xset: ExecutionSet,
    recorder: Recorder,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
) -> tuple[Path, ...]:
    prepared = continuation.prepared
    _revalidate_target_root(fs, xset, target_root)
    if continuation.trash is None:
        continuation.trash = fs.trash_destination(
            target_root,
            xset.run_id,
            continuation.old_relative_path,
        )
    trash = continuation.trash
    old = fs.resolve(
        target_root,
        continuation.old_relative_path,
        must_exist=False,
    )
    old_actual = fs.stat(target_root, continuation.old_relative_path)
    fs.revalidate_trash_destination(
        target_root,
        xset.run_id,
        continuation.old_relative_path,
        trash,
    )
    trash_actual = _stat_target_path(fs, xset, target_root, trash)
    if old_actual is not None:
        _flush_before_destructive(recorder, state)
        _revalidate_target_root(fs, xset, target_root)
        old_actual = fs.stat(target_root, continuation.old_relative_path)
        fs.revalidate_trash_destination(
            target_root,
            xset.run_id,
            continuation.old_relative_path,
            trash,
        )
        trash_actual = _stat_target_path(fs, xset, target_root, trash)
    if old_actual is None:
        if trash_actual is None or not _matches_expected(
            trash_actual,
            continuation.old_expected,
        ):
            raise OperationFailure(
                ExecutionReason.TARGET_MISSING,
                "move-update old path vanished without reaching owned trash",
            )
    else:
        _guard_path_stat(
            old_actual,
            continuation.old_expected,
            ExecutionReason.TARGET_DRIFT,
            "move-update old path drifted before trash",
        )
        if trash_actual is not None:
            raise OperationFailure(
                ExecutionReason.TRASH_COLLISION,
                f"move-update trash exists: {trash}",
            )
        try:
            _revalidate_target_root(fs, xset, target_root)
            fs.rename_new(old, trash)
        except FileExistsError as error:
            raise OperationFailure(
                ExecutionReason.TRASH_COLLISION,
                "move-update trash destination appeared before conditional rename",
                cause=error,
            ) from error
    return prepared.target.parent, old.parent, trash.parent


def _move_update(
    operation: PlanOperation,
    xset: ExecutionSet,
    ctx: RunContext,
    recorder: Recorder,
    policies: ExecutorPolicies,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
    progress: _ProgressTracker,
) -> _Settled:
    existing = state.retry_continuations.get(operation.op_id)
    resumed_published = existing is not None and existing.published
    if existing is None:
        old_rel, old_expected = _prior_target(operation)
        _guard_present(
            fs,
            target_root,
            old_rel,
            old_expected,
            missing=ExecutionReason.TARGET_MISSING,
            drift=ExecutionReason.TARGET_DRIFT,
        )
        prepared = _prepare_copy(
            operation,
            xset,
            ctx,
            policies,
            fs,
            source_root,
            target_root,
            state,
            progress,
        )
        continuation = _MoveUpdateContinuation(
            prepared=prepared,
            prepared_stat=_require_stat_path(fs, prepared.temp),
            old_relative_path=old_rel,
            old_expected=old_expected,
        )
        state.retry_continuations[operation.op_id] = continuation
    elif isinstance(existing, _MoveUpdateContinuation):
        continuation = existing
        prepared = continuation.prepared
    else:
        raise RuntimeError("executor continuation kind does not match move-update")

    if not continuation.published:
        temp_stat = _stat_target_path(
            fs,
            xset,
            target_root,
            prepared.temp,
        )
        if temp_stat is None:
            published_actual = _require_target_stat(
                fs,
                xset,
                target_root,
                prepared.target,
            )
            if not _same_file_version(
                published_actual,
                continuation.prepared_stat,
            ):
                raise OperationFailure(
                    ExecutionReason.TARGET_DRIFT,
                    "move-update temp disappeared without the prepared file being published",
                )
            continuation.published = True
            state.inflight_temp = None
        else:
            _revalidate_source_root(fs, xset, source_root)
            _guard_present(
                fs,
                source_root,
                operation.source_rel_path,
                operation.source_expected,
                missing=ExecutionReason.SOURCE_MISSING,
                drift=ExecutionReason.SOURCE_DRIFT,
            )
            _guard_path_stat(
                temp_stat,
                continuation.prepared_stat,
                ExecutionReason.TARGET_DRIFT,
                "prepared move-update temp drifted before retry",
            )
            _guard_present(
                fs,
                target_root,
                continuation.old_relative_path,
                continuation.old_expected,
                missing=ExecutionReason.TARGET_MISSING,
                drift=ExecutionReason.TARGET_DRIFT,
            )
            _guard_expected_target(fs, target_root, operation)
            try:
                _revalidate_source_root(fs, xset, source_root)
                _revalidate_target_root(fs, xset, target_root)
                fs.publish_new(prepared.temp, prepared.target)
            except FileExistsError as error:
                raise OperationFailure(
                    ExecutionReason.DESTINATION_OCCUPIED,
                    "move-update destination appeared before conditional publish",
                    cause=error,
                ) from error
            state.inflight_temp = None
            continuation.published = True

    return _complete_published_byte_operation(
        continuation,
        xset,
        policies,
        fs,
        state,
        target_root,
        resumed_published=resumed_published,
        finish_filesystem=lambda: _finish_move_update_filesystem(
            continuation,
            xset,
            recorder,
            fs,
            target_root,
            state,
        ),
        record_published=lambda attestation: recorder.record_move_updated(
            operation.op_id,
            attestation,
        ),
        attest_before_filesystem=True,
    )


def _trash(
    operation: PlanOperation,
    xset: ExecutionSet,
    recorder: Recorder,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
) -> _Settled:
    if operation.target_expected is None:
        raise OperationFailure(
            ExecutionReason.TARGET_MISSING, "trash operation has no target evidence"
        )
    _revalidate_target_root(fs, xset, target_root)
    destination = fs.trash_destination(
        target_root, xset.run_id, operation.target_rel_path
    )
    _flush_before_destructive(recorder, state)
    _revalidate_target_root(fs, xset, target_root)
    source_actual = _guard_present(
        fs,
        target_root,
        operation.target_rel_path,
        operation.target_expected,
        missing=ExecutionReason.TARGET_MISSING,
        drift=ExecutionReason.TARGET_DRIFT,
    )
    source = fs.resolve(target_root, operation.target_rel_path, must_exist=True)
    fs.revalidate_trash_destination(
        target_root,
        xset.run_id,
        operation.target_rel_path,
        destination,
    )
    if _stat_target_path(fs, xset, target_root, destination) is not None:
        raise OperationFailure(
            ExecutionReason.TRASH_COLLISION, f"trash destination exists: {destination}"
        )
    _revalidate_target_root(fs, xset, target_root)
    fs.revalidate_trash_destination(
        target_root,
        xset.run_id,
        operation.target_rel_path,
        destination,
    )
    mutation = _retain_mutation_attempt(
        state,
        operation,
        primary=source,
        primary_before=source_actual,
        secondary=destination,
        destination_relative=_target_relative_path(destination, target_root),
        trash_source_relative=operation.target_rel_path,
    )
    try:
        fs.rename_new(source, destination)
    except FileExistsError as error:
        raise OperationFailure(
            ExecutionReason.TRASH_COLLISION,
            "trash destination appeared before conditional rename",
            cause=error,
        ) from error
    mutation.committed = True
    detail = _durability_detail(fs, source.parent, destination.parent)
    moved = _profiled_stat(
        _require_target_stat(fs, xset, target_root, destination),
        xset.plan.target_profile.stable_file_identity,
    )
    trash_relative = str(destination.relative_to(target_root)).replace(os.sep, "\\")
    _record(
        state,
        detail,
        lambda: recorder.record_trashed(operation.op_id, trash_relative, moved),
    )
    return _Settled(Outcome.SUCCEEDED, detail=detail)


def _delete(
    operation: PlanOperation,
    xset: ExecutionSet,
    recorder: Recorder,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
) -> _Settled:
    if operation.target_expected is None:
        raise OperationFailure(
            ExecutionReason.TARGET_MISSING, "delete operation has no target evidence"
        )
    directory_cleanup = (
        operation.target_expected.kind is EntryKind.DIRECTORY
        and operation.reason is OperationReason.DIRECTORY_CLEANUP
    )
    _flush_before_destructive(recorder, state)
    _revalidate_target_root(fs, xset, target_root)
    target_actual = _guard_present(
        fs,
        target_root,
        operation.target_rel_path,
        operation.target_expected,
        missing=ExecutionReason.TARGET_MISSING,
        drift=ExecutionReason.TARGET_DRIFT,
        matcher=_matches_directory_cleanup if directory_cleanup else None,
    )
    target = fs.resolve(target_root, operation.target_rel_path, must_exist=True)
    readonly_cleared = bool(
        operation.target_expected.metadata.attributes & _READONLY
    )
    _revalidate_target_root(fs, xset, target_root)
    mutation = _retain_mutation_attempt(
        state,
        operation,
        primary=target,
        primary_before=target_actual,
    )
    removed = False
    try:
        if readonly_cleared:
            fs.clear_readonly(target)
        if operation.target_expected.kind is EntryKind.DIRECTORY:
            fs.remove_directory(target)
        else:
            fs.remove_file(target)
        removed = True
        mutation.committed = True
    finally:
        if readonly_cleared and not removed:
            actual = _stat_target_path(fs, xset, target_root, target)
            if actual is not None:
                guarded_target = _resolve_target_path(
                    fs,
                    xset,
                    target_root,
                    target,
                    must_exist=True,
                )
                fs.apply_metadata(
                    guarded_target,
                    operation.target_expected,
                    preserve_created=True,
                    apply_readonly=True,
                )
    detail = _durability_detail(fs, target.parent)
    _record(
        state,
        detail,
        lambda: recorder.record_deleted(operation.op_id, operation.target_expected),
    )
    return _Settled(Outcome.SUCCEEDED, detail=detail)


def _noop(
    operation: PlanOperation,
    recorder: Recorder,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
) -> _Settled:
    if (
        operation.source_rel_path is None
        or operation.source_expected is None
        or operation.target_expected is None
    ):
        raise OperationFailure(
            ExecutionReason.SOURCE_DRIFT, "noop lacks matching two-sided evidence"
        )
    source = _guard_present(
        fs,
        source_root,
        operation.source_rel_path,
        operation.source_expected,
        missing=ExecutionReason.SOURCE_MISSING,
        drift=ExecutionReason.SOURCE_DRIFT,
    )
    target = _guard_present(
        fs,
        target_root,
        operation.target_rel_path,
        operation.target_expected,
        missing=ExecutionReason.TARGET_MISSING,
        drift=ExecutionReason.TARGET_DRIFT,
    )
    detail: dict[str, object] = {}
    _record(
        state,
        detail,
        lambda: recorder.record_noop(
            operation.op_id,
            _normalized_live_stat(source, operation.source_expected),
            _normalized_live_stat(target, operation.target_expected),
        ),
    )
    return _Settled(Outcome.SKIPPED, ExecutionReason.NOOP, detail)


def _start_directory(
    operation: PlanOperation,
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
    source_root: Path,
    target_root: Path,
    state: _ExecutionState,
) -> None:
    if operation.source_rel_path is None or operation.source_expected is None:
        raise OperationFailure(
            ExecutionReason.SOURCE_MISSING,
            "mkdir operation lacks source evidence",
        )
    _revalidate_source_root(fs, xset, source_root)
    _guard_present(
        fs,
        source_root,
        operation.source_rel_path,
        operation.source_expected,
        missing=ExecutionReason.SOURCE_MISSING,
        drift=ExecutionReason.SOURCE_DRIFT,
    )
    _guard_absent(fs, target_root, operation.target_rel_path)
    target = fs.resolve(target_root, operation.target_rel_path, must_exist=False)
    _revalidate_source_root(fs, xset, source_root)
    _revalidate_target_root(fs, xset, target_root)
    mutation = _retain_mutation_attempt(
        state,
        operation,
        primary=target,
        primary_before=None,
    )
    try:
        fs.mkdir_new(target)
    except FileExistsError as error:
        raise OperationFailure(
            ExecutionReason.DESTINATION_OCCUPIED,
            "directory appeared before conditional create",
            cause=error,
        ) from error
    mutation.committed = True
    state.pending_directories.append(operation)
    state.ready_directories.add(operation.op_id)


def _finalize_directories(
    xset: ExecutionSet,
    ctx: RunContext,
    recorder: Recorder,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
    progress: _ProgressTracker,
) -> None:
    pending = sorted(
        state.pending_directories,
        key=lambda operation: len(PureWindowsPath(operation.target_rel_path).parts),
        reverse=True,
    )
    state.pending_directories.clear()
    for operation in pending:
        try:
            intended = operation.intended or operation.source_expected
            if intended is None or intended.kind is not EntryKind.DIRECTORY:
                raise OperationFailure(
                    ExecutionReason.WRONG_TYPE,
                    "mkdir operation lacks intended directory metadata",
                )
            target = target_root.joinpath(
                *PureWindowsPath(operation.target_rel_path).parts
            )
            target = _resolve_target_path(
                fs,
                xset,
                target_root,
                target,
                must_exist=True,
            )
            fs.apply_metadata(
                target,
                intended,
                preserve_created=xset.plan.preservation.preserve_created,
                apply_readonly=True,
            )
            detail = _durability_detail(fs, target.parent)
            actual = _profiled_stat(
                _require_target_stat(fs, xset, target_root, target),
                xset.plan.target_profile.stable_file_identity,
            )
            _record(
                state,
                detail,
                lambda operation=operation, actual=actual: recorder.record_mkdir(
                    operation.op_id, actual
                ),
            )
            state.mutation_attempts.pop(operation.op_id, None)
            _settle(
                xset,
                state,
                progress,
                ctx,
                operation,
                _Settled(Outcome.SUCCEEDED, detail=detail),
            )
        except (Canceled, PauseRequested):
            raise
        except Exception as error:
            mutation_failure = _failed_after_mutation_settlement(
                operation,
                error,
                fs,
                state,
            )
            state.mutation_attempts.pop(operation.op_id, None)
            if mutation_failure is None:
                _settle_failure(xset, state, progress, ctx, operation, error)
            else:
                _settle(
                    xset,
                    state,
                    progress,
                    ctx,
                    operation,
                    mutation_failure,
                )
        finally:
            state.ready_directories.discard(operation.op_id)


def _restore_completed_directory_metadata(
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
) -> None:
    for operation in reversed(xset.plan.operations):
        if (
            operation.kind is not OperationKind.MKDIR
            or operation.op_id not in xset.selection
            or operation.op_id not in state.restore_directories
        ):
            continue
        intended = operation.intended or operation.source_expected
        if intended is None:
            continue
        target: Path | None = None
        try:
            target = target_root.joinpath(
                *PureWindowsPath(operation.target_rel_path).parts
            )
            target = _resolve_target_path(
                fs,
                xset,
                target_root,
                target,
                must_exist=True,
            )
            fs.apply_metadata(
                target,
                intended,
                preserve_created=xset.plan.preservation.preserve_created,
                apply_readonly=True,
            )
        except Exception:
            state.filesystem_failed = True
            if target is None:
                state.recording = RecordingStatus.DEGRADED
                continue
            try:
                actual = _stat_target_path(
                    fs,
                    xset,
                    target_root,
                    target,
                )
            except Exception:
                state.recording = RecordingStatus.DEGRADED
                continue
            if actual is None or not _matches_restored_directory_metadata(
                actual,
                intended,
                preserve_created=xset.plan.preservation.preserve_created,
            ):
                state.recording = RecordingStatus.DEGRADED


def _matches_restored_directory_metadata(
    actual: FileStat,
    intended: FileStat,
    *,
    preserve_created: bool,
) -> bool:
    return (
        actual.kind is EntryKind.DIRECTORY
        and actual.mtime_ns == intended.mtime_ns
        and (
            actual.metadata.attributes & MANAGED_FILE_ATTRIBUTE_MASK
        )
        == (intended.metadata.attributes & MANAGED_FILE_ATTRIBUTE_MASK)
        and (
            not preserve_created
            or intended.metadata.created_ns is None
            or os.name != "nt"
            or actual.metadata.created_ns == intended.metadata.created_ns
        )
    )


def _dependencies_succeeded(
    xset: ExecutionSet, state: _ExecutionState, operation: PlanOperation
) -> bool:
    return all(
        xset.status.get(dependency) is Outcome.SUCCEEDED
        or dependency in state.ready_directories
        for dependency in operation.dependencies
    )


def _settle(
    xset: ExecutionSet,
    state: _ExecutionState,
    progress: _ProgressTracker,
    ctx: RunContext,
    operation: PlanOperation,
    settled: _Settled,
) -> None:
    if operation.op_id in xset.status:
        return
    byte_producing = operation.kind in {
        OperationKind.COPY,
        OperationKind.UPDATE,
        OperationKind.MOVE_UPDATE,
    }
    evidence_required = (
        settled.outcome is Outcome.SUCCEEDED and byte_producing
    )
    if evidence_required and settled.published_evidence is None:
        raise RuntimeError(
            "successful byte-producing operation lacks published evidence"
        )
    if not evidence_required and settled.published_evidence is not None:
        raise RuntimeError(
            "published evidence belongs to an ineligible operation outcome"
        )
    if operation.op_id in xset.published_evidence:
        raise RuntimeError("published evidence already exists for operation")
    event = ItemOutcome(
        item_id=str(operation.op_id),
        kind=operation.kind.value,
        path=operation.target_rel_path,
        outcome=settled.outcome,
        reason=None if settled.reason is None else settled.reason.value,
        detail=settled.detail,
    )
    if settled.published_evidence is not None:
        xset.published_evidence[operation.op_id] = settled.published_evidence
    xset.status[operation.op_id] = settled.outcome
    state.outcomes[operation.op_id] = event
    ctx.emit(event)
    progress.settled(operation, settled.outcome)


def _settle_failure(
    xset: ExecutionSet,
    state: _ExecutionState,
    progress: _ProgressTracker,
    ctx: RunContext,
    operation: PlanOperation,
    error: Exception,
) -> None:
    reason, detail = _failure_reason_and_message(error)
    _settle(
        xset,
        state,
        progress,
        ctx,
        operation,
        _Settled(
            Outcome.FAILED,
            reason,
            {"error_type": type(error).__name__, "message": detail},
        ),
    )


def _failure_reason_and_message(
    error: Exception,
) -> tuple[ExecutionReason, str]:
    if isinstance(error, OperationFailure):
        return error.reason, error.detail
    if isinstance(error, UnsafeExecutionPath):
        return ExecutionReason.UNSAFE_PATH, logical_error_text(error)
    reason = (
        ExecutionReason.SHARING_VIOLATION
        if _find_winerror(error) in _SHARING_VIOLATIONS
        else ExecutionReason.IO_ERROR
    )
    return reason, logical_error_text(error)


def _failed_durable_settlement(
    operation: PlanOperation,
    error: Exception,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
) -> _Settled | None:
    published = _failed_after_publish_settlement(
        operation,
        error,
        fs,
        target_root,
        state,
    )
    if (
        published is not None
        and published.detail.get("publish_state") == "published"
    ):
        return published

    mutation = _failed_after_mutation_settlement(
        operation,
        error,
        fs,
        state,
    )
    if published is None:
        return mutation
    if mutation is None:
        return published

    detail = dict(published.detail)
    mutation_detail = dict(mutation.detail)
    for duplicate in ("error_type", "message", "publish_state"):
        mutation_detail.pop(duplicate, None)
    for duplicate in ("recording", "recording_error"):
        if duplicate in detail:
            mutation_detail.pop(duplicate, None)
    mutation_durable_state = mutation_detail.pop("durable_state", None)
    detail.update(mutation_detail)
    if mutation_durable_state is not None:
        detail["mutation_durable_state"] = mutation_durable_state
    return replace(published, detail=detail)


def _failed_after_publish_settlement(
    operation: PlanOperation,
    error: Exception,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
) -> _Settled | None:
    continuation = state.retry_continuations.get(operation.op_id)
    if continuation is None:
        return None

    reason, message = _failure_reason_and_message(error)
    detail = dict(continuation.detail)
    detail.update(
        {
            "error_type": type(error).__name__,
            "message": message,
            "publish_state": "published",
            "published_path": operation.target_rel_path,
        }
    )
    try:
        if isinstance(continuation, _UpdateContinuation):
            _describe_retained_update_backup(
                continuation,
                state.execution_set,
                fs,
                target_root,
                operation.target_rel_path,
                detail,
            )
            published = _update_publish_state(
                continuation,
                fs,
                state.execution_set,
                target_root,
                detail,
            )
        else:
            published = _new_publish_state(
                continuation,
                fs,
                state.execution_set,
                target_root,
                detail,
            )
    except Exception as state_error:
        detail["publish_state"] = "unverified"
        detail["durable_state"] = "publication-unverified"
        detail["state_error_type"] = type(state_error).__name__
        detail["state_error"] = logical_error_text(state_error)
        _mark_unrecorded_publish(
            state,
            detail,
            message=(
                "filesystem mutation may have published but durable state "
                "could not be verified"
            ),
        )
        return _Settled(Outcome.FAILED, reason, detail)
    if not published:
        if (
            isinstance(continuation, _UpdateContinuation)
            and continuation.backup is not None
            and detail.get("backup_state") == "retained"
        ):
            detail["publish_state"] = "not-published"
            detail.pop("published_path", None)
            detail.setdefault("durable_state", "target-not-published")
            return _Settled(Outcome.FAILED, reason, detail)
        return None

    target_durable_state = _published_target_durable_state(detail)
    if isinstance(continuation, _UpdateContinuation):
        detail["durable_state"] = target_durable_state
        if (
            target_durable_state == "target-published"
            and detail.get("backup_state") == "retained"
        ):
            detail["durable_state"] = "target-published-with-backup"
    elif isinstance(continuation, _MoveUpdateContinuation):
        if target_durable_state == "target-published":
            _describe_move_update_durable_state(
                continuation,
                state.execution_set,
                fs,
                target_root,
                detail,
            )
        else:
            detail["prior_path"] = continuation.old_relative_path
            if continuation.trash is not None:
                detail["trash_path"] = _target_relative_path(
                    continuation.trash,
                    target_root,
                )
            detail["durable_state"] = target_durable_state
    else:
        detail["durable_state"] = target_durable_state
    _mark_unrecorded_publish(
        state,
        detail,
        message="published filesystem mutation failed before ledger settlement",
    )
    return _Settled(Outcome.FAILED, reason, detail)


def _retain_mutation_attempt(
    state: _ExecutionState,
    operation: PlanOperation,
    *,
    primary: Path,
    primary_before: FileStat | None,
    secondary: Path | None = None,
    destination_relative: str | None = None,
    trash_source_relative: str | None = None,
) -> _MutationAttempt:
    stable_identity = state.execution_set.plan.target_profile.stable_file_identity
    normalized_before = (
        None
        if primary_before is None
        else _profiled_stat(primary_before, stable_identity)
    )
    existing = state.mutation_attempts.get(operation.op_id)
    if existing is None:
        attempt = _MutationAttempt(
            kind=operation.kind,
            primary=primary,
            primary_before=normalized_before,
            secondary=secondary,
            destination_relative=destination_relative,
            trash_source_relative=trash_source_relative,
        )
        state.mutation_attempts[operation.op_id] = attempt
        return attempt
    if (
        existing.kind is not operation.kind
        or existing.primary != primary
        or existing.primary_before != normalized_before
        or existing.secondary != secondary
        or existing.destination_relative != destination_relative
        or existing.trash_source_relative != trash_source_relative
    ):
        raise RuntimeError("executor mutation attempt changed during retry")
    return existing


def _failed_after_mutation_settlement(
    operation: PlanOperation,
    error: Exception,
    fs: ExecutorFileSystem,
    state: _ExecutionState,
    *,
    canceled: bool = False,
) -> _Settled | None:
    attempt = state.mutation_attempts.get(operation.op_id)
    if attempt is None:
        return None

    reason, message = _failure_reason_and_message(error)
    detail: dict[str, object] = {
        "error_type": type(error).__name__,
        "message": message,
    }
    if attempt.kind is OperationKind.UPDATE:
        detail["publish_state"] = "not-published"
    if attempt.destination_relative is not None:
        detail["mutation_destination"] = attempt.destination_relative
    if not _describe_mutation_attempt(attempt, fs, state, detail):
        return None

    if canceled:
        reason = ExecutionReason.CANCELED_AFTER_MUTATION
        detail["message"] = "cancellation interrupted settlement after a mutation attempt"
    _mark_unrecorded_mutation(
        state,
        detail,
        message="filesystem mutation may have committed before ledger settlement",
    )
    return _Settled(Outcome.FAILED, reason, detail)


def _stat_mutation_secondary(
    attempt: _MutationAttempt,
    fs: ExecutorFileSystem,
    state: _ExecutionState,
) -> FileStat | None:
    secondary = attempt.secondary
    if secondary is None:
        return None
    xset = state.execution_set
    target_root = Path(xset.plan.target_root.path)
    if attempt.kind is OperationKind.TRASH:
        if attempt.trash_source_relative is None:
            raise RuntimeError("trash mutation lacks its source-relative path")
        fs.revalidate_trash_destination(
            target_root,
            xset.run_id,
            attempt.trash_source_relative,
            secondary,
        )
    return _stat_target_path(fs, xset, target_root, secondary)


def _describe_mutation_attempt(
    attempt: _MutationAttempt,
    fs: ExecutorFileSystem,
    state: _ExecutionState,
    detail: dict[str, object],
) -> bool:
    committed_states = {
        OperationKind.MOVE: "target-renamed",
        OperationKind.TRASH: "target-trashed",
    }
    if attempt.kind is OperationKind.RECASE:
        # Both spellings address the same entry on Windows, so a path stat cannot
        # distinguish a committed case-only rename from its exact pre-state.
        detail["mutation_state"] = (
            "committed" if attempt.committed else "unverified"
        )
        detail["durable_state"] = "recase-state-unverified"
        return True

    stable_identity = state.execution_set.plan.target_profile.stable_file_identity
    target_root = Path(state.execution_set.plan.target_root.path)
    try:
        primary = _stat_target_path(
            fs,
            state.execution_set,
            target_root,
            attempt.primary,
        )
        primary = (
            None if primary is None else _profiled_stat(primary, stable_identity)
        )
        secondary = (
            None
            if attempt.secondary is None
            else _stat_mutation_secondary(attempt, fs, state)
        )
        secondary = (
            None
            if secondary is None
            else _profiled_stat(secondary, stable_identity)
        )
    except Exception as state_error:
        detail["mutation_state"] = (
            "committed" if attempt.committed else "unverified"
        )
        detail["durable_state"] = f"{attempt.kind.value}-state-unverified"
        detail["mutation_state_error"] = (
            f"{type(state_error).__name__}: {logical_error_text(state_error)}"
        )
        return True

    before = attempt.primary_before
    if attempt.kind in {OperationKind.MOVE, OperationKind.TRASH}:
        assert before is not None and attempt.secondary is not None
        primary_matches = primary is not None and _matches_expected(primary, before)
        secondary_matches = secondary is not None and _matches_expected(
            secondary, before
        )
        detail["source_state"] = (
            "reviewed" if primary_matches else "absent" if primary is None else "changed"
        )
        detail["destination_state"] = (
            "reviewed"
            if secondary_matches
            else "absent"
            if secondary is None
            else "changed"
        )
        if primary_matches and secondary is None:
            if attempt.committed:
                detail["mutation_state"] = "committed"
                detail["durable_state"] = (
                    "source-restored-after-move"
                    if attempt.kind is OperationKind.MOVE
                    else "source-restored-after-trash"
                )
                return True
            detail["mutation_state"] = "not-committed"
            detail["durable_state"] = "source-retained"
            return False
        if primary is None and secondary_matches:
            detail["mutation_state"] = "committed"
            detail["durable_state"] = committed_states[attempt.kind]
            return True
        detail["mutation_state"] = (
            "committed" if attempt.committed else "unverified"
        )
        detail["durable_state"] = f"{attempt.kind.value}-state-ambiguous"
        return True

    if attempt.kind is OperationKind.DELETE:
        assert before is not None
        if primary is not None and _matches_expected(primary, before):
            if attempt.committed:
                detail["mutation_state"] = "committed"
                detail["durable_state"] = "target-restored-after-delete"
                return True
            detail["mutation_state"] = "not-committed"
            detail["durable_state"] = "target-retained"
            return False
        detail["mutation_state"] = (
            "committed"
            if attempt.committed or primary is None
            else "unverified"
        )
        detail["durable_state"] = (
            "target-deleted"
            if primary is None
            else "target-changed-after-delete-attempt"
        )
        return True

    if attempt.kind is OperationKind.UPDATE:
        assert before is not None
        if primary is not None and _matches_expected(primary, before):
            detail["mutation_state"] = "not-committed"
            detail["durable_state"] = "target-retained"
            return False
        detail["mutation_state"] = "unverified"
        detail["durable_state"] = (
            "target-missing-before-publish"
            if primary is None
            else "target-metadata-changed-before-publish"
        )
        return True

    if attempt.kind is OperationKind.MKDIR:
        if primary is None:
            if attempt.committed:
                detail["mutation_state"] = "committed"
                detail["durable_state"] = "directory-missing-after-create"
                return True
            detail["mutation_state"] = "not-committed"
            detail["durable_state"] = "directory-absent"
            return False
        detail["mutation_state"] = (
            "committed"
            if attempt.committed
            else "unverified"
        )
        detail["durable_state"] = (
            "directory-created"
            if attempt.committed and primary.kind is EntryKind.DIRECTORY
            else "directory-present-after-create-attempt"
            if primary.kind is EntryKind.DIRECTORY
            else "mkdir-state-ambiguous"
        )
        return True

    raise RuntimeError(f"unsupported mutation attempt kind: {attempt.kind}")


def _cleanup_inflight(
    state: _ExecutionState, fs: ExecutorFileSystem
) -> Exception | None:
    if state.inflight_temp is None:
        return None
    temp = state.inflight_temp
    state.inflight_temp = None
    try:
        _revalidate_target_root(
            fs,
            state.execution_set,
            Path(state.execution_set.plan.target_root.path),
        )
        fs.remove_owned_temp(temp)
    except Exception as error:
        return error
    return None


def _retry_checkpoint(
    ctx: RunContext,
    state: _ExecutionState,
    op_id: OpId,
) -> None:
    """Latch pause while process-local state owns a prepared durable stage."""

    try:
        ctx.checkpoint()
    except PauseRequested:
        if (
            op_id not in state.retry_continuations
            and op_id not in state.mutation_attempts
        ):
            raise
        state.pause_latched = True


def _policy_stop_checkpoint(ctx: RunContext) -> None:
    """Keep Stop authoritative while allowing cancel to interrupt its sweep."""

    try:
        ctx.checkpoint()
    except PauseRequested:
        pass


def _canceled_durable_settlement(
    operation: PlanOperation,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
) -> _Settled | None:
    byte_settlement = _canceled_byte_settlement(
        operation,
        fs,
        target_root,
        state,
    )
    if (
        byte_settlement is not None
        and byte_settlement.detail.get("publish_state") == "published"
    ):
        return byte_settlement
    mutation_settlement = _failed_after_mutation_settlement(
        operation,
        state.retry_errors.get(operation.op_id) or Canceled(),
        fs,
        state,
        canceled=True,
    )
    if mutation_settlement is None:
        return byte_settlement
    if byte_settlement is None:
        return mutation_settlement

    detail = dict(byte_settlement.detail)
    mutation_detail = dict(mutation_settlement.detail)
    mutation_detail.pop("publish_state", None)
    mutation_durable_state = mutation_detail.pop("durable_state", None)
    detail.update(mutation_detail)
    if mutation_durable_state is not None:
        detail["mutation_durable_state"] = mutation_durable_state
    return replace(mutation_settlement, detail=detail)


def _canceled_byte_settlement(
    operation: PlanOperation,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
) -> _Settled | None:
    continuation = state.retry_continuations.get(operation.op_id)
    if continuation is None:
        return None

    detail: dict[str, object] = {}
    retry_error = state.retry_errors.get(operation.op_id)
    if retry_error is not None:
        detail["retry_error_type"] = type(retry_error).__name__
        detail["retry_error"] = logical_error_text(retry_error)

    try:
        if isinstance(continuation, _UpdateContinuation):
            detail.update(continuation.detail)
            _describe_retained_update_backup(
                continuation,
                state.execution_set,
                fs,
                target_root,
                operation.target_rel_path,
                detail,
            )
            published = _update_publish_state(
                continuation,
                fs,
                state.execution_set,
                target_root,
                detail,
            )
        else:
            published = _new_publish_state(
                continuation,
                fs,
                state.execution_set,
                target_root,
                detail,
            )
    except Exception as error:
        detail.setdefault("durable_state", "unverified")
        detail["publish_state"] = "unverified"
        detail["state_error_type"] = type(error).__name__
        detail["state_error"] = logical_error_text(error)
        return _Settled(
            Outcome.FAILED,
            (
                error.reason
                if isinstance(error, OperationFailure)
                else ExecutionReason.IO_ERROR
            ),
            detail,
        )

    if not published:
        detail["publish_state"] = "not-published"
        detail.setdefault("durable_state", "target-not-published")
        return _Settled(Outcome.CANCELED, ExecutionReason.CANCELED, detail)

    detail["publish_state"] = "published"
    target_durable_state = _published_target_durable_state(detail)
    if isinstance(continuation, _MoveUpdateContinuation):
        if target_durable_state == "target-published":
            _describe_move_update_durable_state(
                continuation,
                state.execution_set,
                fs,
                target_root,
                detail,
            )
        else:
            detail["prior_path"] = continuation.old_relative_path
            if continuation.trash is not None:
                detail["trash_path"] = _target_relative_path(
                    continuation.trash,
                    target_root,
                )
            detail["durable_state"] = target_durable_state
    elif isinstance(continuation, _UpdateContinuation):
        detail["durable_state"] = target_durable_state
        if (
            target_durable_state == "target-published"
            and detail.get("backup_state") == "retained"
        ):
            detail["durable_state"] = "target-published-with-backup"
    else:
        detail["durable_state"] = target_durable_state
    detail["published_path"] = operation.target_rel_path
    _mark_unrecorded_publish(state, detail)
    return _Settled(
        Outcome.FAILED,
        ExecutionReason.CANCELED_AFTER_PUBLISH,
        detail,
    )


def _new_publish_state(
    continuation: _CopyContinuation | _MoveUpdateContinuation,
    fs: ExecutorFileSystem,
    xset: ExecutionSet,
    target_root: Path,
    detail: dict[str, object],
) -> bool:
    prepared = continuation.prepared
    if continuation.published:
        _describe_published_target(
            prepared.target,
            continuation.published_stat or continuation.prepared_stat,
            fs,
            xset,
            target_root,
            detail,
        )
        return True

    temp = _stat_target_path(fs, xset, target_root, prepared.temp)
    target = _stat_target_path(fs, xset, target_root, prepared.target)
    if temp is not None and _same_file_version(temp, continuation.prepared_stat):
        if target is not None:
            detail["target_state"] = "unexpectedly-present-before-publish"
        return False
    if temp is not None and target is None:
        detail["temp_state"] = "changed-before-publish"
        detail["target_state"] = "absent-before-publish"
        return False
    if temp is None and target is not None:
        detail["target_state"] = (
            "published"
            if _same_file_version(
                target,
                continuation.published_stat or continuation.prepared_stat,
            )
            else "changed-after-publish"
        )
        return True
    detail["temp_state"] = "missing" if temp is None else "unexpected"
    detail["target_state"] = "missing" if target is None else "present"
    raise OperationFailure(
        (
            ExecutionReason.TARGET_MISSING
            if target is None
            else ExecutionReason.TARGET_DRIFT
        ),
        "cannot classify prepared versus published state during cancel settlement",
    )


def _update_publish_state(
    continuation: _UpdateContinuation,
    fs: ExecutorFileSystem,
    xset: ExecutionSet,
    target_root: Path,
    detail: dict[str, object],
) -> bool:
    prepared = continuation.prepared
    if continuation.published:
        _describe_published_target(
            prepared.target,
            continuation.published_stat or continuation.prepared_stat,
            fs,
            xset,
            target_root,
            detail,
        )
        return True

    temp = _stat_target_path(fs, xset, target_root, prepared.temp)
    target = _stat_target_path(fs, xset, target_root, prepared.target)
    if temp is not None and _same_file_version(temp, continuation.prepared_stat):
        if target is None:
            detail["target_state"] = "missing-before-publish"
        elif not _same_file_version(target, continuation.live_stat):
            detail["target_state"] = "changed-before-publish"
        return False
    if (
        temp is not None
        and target is not None
        and _same_file_version(target, continuation.live_stat)
    ):
        detail["temp_state"] = "changed-before-publish"
        detail["target_state"] = "retained-before-publish"
        return False
    if temp is None and target is not None:
        detail["target_state"] = (
            "published"
            if _same_file_version(
                target,
                continuation.published_stat or continuation.prepared_stat,
            )
            else "changed-after-publish"
        )
        return True
    detail["temp_state"] = "missing" if temp is None else "unexpected"
    detail["target_state"] = "missing" if target is None else "present"
    raise OperationFailure(
        (
            ExecutionReason.TARGET_MISSING
            if target is None
            else ExecutionReason.TARGET_DRIFT
        ),
        "cannot classify live versus published update during cancel settlement",
    )


def _describe_published_target(
    target: Path,
    expected: FileStat,
    fs: ExecutorFileSystem,
    xset: ExecutionSet,
    target_root: Path,
    detail: dict[str, object],
) -> None:
    try:
        actual = _stat_target_path(fs, xset, target_root, target)
    except Exception as error:
        detail["target_state"] = "unverified-after-publish"
        detail["target_state_error"] = (
            f"{type(error).__name__}: {logical_error_text(error)}"
        )
        return
    if actual is None:
        detail["target_state"] = "missing-after-publish"
    elif _same_file_version(actual, expected):
        detail["target_state"] = "published"
    else:
        detail["target_state"] = "changed-after-publish"


def _published_target_durable_state(detail: dict[str, object]) -> str:
    states = {
        "published": "target-published",
        "changed-after-publish": "target-changed-after-publish",
        "missing-after-publish": "target-missing-after-publish",
        "unverified-after-publish": "target-unverified-after-publish",
    }
    target_state = detail.get("target_state")
    if target_state not in states:
        raise RuntimeError("published target classification is incomplete")
    return states[target_state]


def _target_relative_path(path: Path, target_root: Path) -> str:
    return str(path.relative_to(target_root)).replace(os.sep, "\\")


def _revalidate_target_root(
    fs: ExecutorFileSystem,
    xset: ExecutionSet,
    target_root: Path,
) -> None:
    authority = _target_root_authority(xset)
    fs.revalidate_root(
        Path(authority.logical_root),
        trusted_anchor=(
            None
            if authority.reviewed_anchor is None
            else Path(authority.reviewed_anchor)
        ),
        expected_volume=authority.expected_volume_id,
    )


def _revalidate_source_root(
    fs: ExecutorFileSystem,
    xset: ExecutionSet,
    source_root: Path,
) -> None:
    authority = _source_root_authority(xset)
    fs.revalidate_root(
        Path(authority.logical_root),
        trusted_anchor=(
            None
            if authority.reviewed_anchor is None
            else Path(authority.reviewed_anchor)
        ),
        expected_volume=authority.expected_volume_id,
    )


def _target_root_authority(
    xset: ExecutionSet,
) -> RootAuthority:
    evidence = xset.plan.target_volume_evidence
    try:
        return RootAuthority(
            xset.plan.target_root.path,
            None if evidence is None else evidence.device_id,
            xset.plan.target_volume_id,
        )
    except PathValidationError as error:
        raise UnsafeExecutionPath(
            "reviewed root volume anchor changed before filesystem access"
        ) from error


def _source_root_authority(
    xset: ExecutionSet,
) -> RootAuthority:
    evidence = xset.plan.source_volume_evidence
    try:
        return RootAuthority(
            xset.plan.source_root.path,
            None if evidence is None else evidence.device_id,
            xset.plan.source_volume_id,
        )
    except PathValidationError as error:
        raise UnsafeExecutionPath(
            "reviewed root volume anchor changed before filesystem access"
        ) from error


def _stat_target_path(
    fs: ExecutorFileSystem,
    xset: ExecutionSet,
    target_root: Path,
    path: Path,
) -> FileStat | None:
    guarded = _resolve_target_path(
        fs,
        xset,
        target_root,
        path,
        must_exist=False,
    )
    return fs.stat_path(guarded)


def _resolve_target_path(
    fs: ExecutorFileSystem,
    xset: ExecutionSet,
    target_root: Path,
    path: Path,
    *,
    must_exist: bool,
) -> Path:
    _revalidate_target_root(fs, xset, target_root)
    relative = _target_relative_path(path, target_root)
    guarded = fs.resolve(target_root, relative, must_exist=must_exist)
    if os.path.normcase(str(guarded)) != os.path.normcase(str(path)):
        raise UnsafeExecutionPath(
            "retained target path changed during root-relative validation"
        )
    return guarded


def _require_target_stat(
    fs: ExecutorFileSystem,
    xset: ExecutionSet,
    target_root: Path,
    path: Path,
) -> FileStat:
    observed = _stat_target_path(fs, xset, target_root, path)
    if observed is None:
        raise FileNotFoundError(path)
    return observed


def _describe_retained_update_backup(
    continuation: _UpdateContinuation,
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
    target_root: Path,
    relative_path: str,
    detail: dict[str, object],
) -> None:
    backup = continuation.backup
    if backup is None:
        return
    detail["backup_path"] = _target_relative_path(backup.path, target_root)
    try:
        fs.revalidate_trash_destination(
            target_root,
            xset.run_id,
            relative_path,
            backup.path,
        )
        actual = _stat_target_path(
            fs,
            xset,
            target_root,
            backup.path,
        )
    except Exception as error:
        detail["backup_state"] = "unverified"
        detail["backup_state_error"] = (
            f"{type(error).__name__}: {logical_error_text(error)}"
        )
        return
    if actual is None:
        detail["backup_state"] = "absent"
        return
    stable_identity = xset.plan.target_profile.stable_file_identity
    if backup.published_stat is None:
        if backup.created_stat is None:
            detail["backup_state"] = "unverified"
            detail["backup_state_error"] = "creation evidence unavailable"
            return
        retained = _same_unrepaired_publication(
            actual,
            backup.created_stat,
            stable_identity,
        )
        detail["backup_metadata"] = "unrepaired"
    else:
        retained = _same_file_version(
            _profiled_stat(actual, stable_identity),
            backup.published_stat,
        )
    detail["backup_state"] = "retained" if retained else "changed"
    if retained:
        detail["durable_state"] = "backup-retained"


def _describe_move_update_durable_state(
    continuation: _MoveUpdateContinuation,
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
    target_root: Path,
    detail: dict[str, object],
) -> None:
    detail["prior_path"] = continuation.old_relative_path
    old_path = target_root.joinpath(
        *PureWindowsPath(continuation.old_relative_path).parts
    )
    if continuation.trash is None:
        try:
            old = _stat_target_path(fs, xset, target_root, old_path)
        except Exception as error:
            detail["durable_state"] = "new-and-old-unverified"
            detail["old_state_error"] = (
                f"{type(error).__name__}: {logical_error_text(error)}"
            )
            return
        detail["durable_state"] = (
            "new-and-old"
            if old is not None and _matches_expected(old, continuation.old_expected)
            else "new-and-old-unverified"
        )
        return
    detail["trash_path"] = _target_relative_path(
        continuation.trash,
        target_root,
    )
    try:
        old = _stat_target_path(fs, xset, target_root, old_path)
    except Exception as error:
        detail["durable_state"] = "new-and-old-unverified"
        detail["old_state_error"] = (
            f"{type(error).__name__}: {logical_error_text(error)}"
        )
        return
    try:
        fs.revalidate_trash_destination(
            target_root,
            xset.run_id,
            continuation.old_relative_path,
            continuation.trash,
        )
        trash = _stat_target_path(
            fs,
            xset,
            target_root,
            continuation.trash,
        )
    except Exception as error:
        detail["durable_state"] = "new-and-old-unverified"
        detail["trash_state_error"] = (
            f"{type(error).__name__}: {logical_error_text(error)}"
        )
        return
    if old is not None and _matches_expected(old, continuation.old_expected):
        detail["durable_state"] = (
            "new-and-old"
            if trash is None
            else "new-old-and-trash-unverified"
        )
    elif old is None and trash is not None and _matches_expected(
        trash,
        continuation.old_expected,
    ):
        detail["durable_state"] = "new-and-trash"
    else:
        detail["durable_state"] = "new-and-old-unverified"


def _mark_unrecorded_publish(
    state: _ExecutionState,
    detail: dict[str, object],
    *,
    message: str = "cancellation interrupted settlement of a published filesystem mutation",
) -> None:
    _mark_unrecorded_mutation(state, detail, message=message)


def _mark_unrecorded_mutation(
    state: _ExecutionState,
    detail: dict[str, object],
    *,
    message: str,
) -> None:
    state.recording = RecordingStatus.DEGRADED
    detail["recording"] = RecordingStatus.DEGRADED.value
    detail["recording_error"] = message


def _guard_present(
    fs: ExecutorFileSystem,
    root: Path,
    relative_path: str,
    expected: FileStat,
    *,
    missing: ExecutionReason,
    drift: ExecutionReason,
    matcher: Callable[[FileStat, FileStat], bool] | None = None,
) -> FileStat:
    try:
        actual = fs.stat(root, relative_path)
    except Exception as error:
        if isinstance(error, UnsafeExecutionPath):
            raise OperationFailure(
                ExecutionReason.UNSAFE_PATH,
                logical_error_text(error),
                cause=error,
            ) from error
        raise
    if actual is None:
        raise OperationFailure(missing, f"planned path is missing: {relative_path}")
    if not (matcher or _matches_expected)(actual, expected):
        reason = ExecutionReason.WRONG_TYPE if actual.kind is not expected.kind else drift
        raise OperationFailure(reason, f"planned evidence drifted: {relative_path}")
    return actual


def _matches_expected(actual: FileStat, expected: FileStat) -> bool:
    """Match every planned fact, without inventing absent identity evidence."""

    return (
        actual.kind is expected.kind
        and actual.size == expected.size
        and actual.mtime_ns == expected.mtime_ns
        and actual.nlink == expected.nlink
        and actual.metadata == expected.metadata
        and (
            expected.file_identity is None
            or actual.file_identity == expected.file_identity
        )
    )


def _matches_directory_cleanup(actual: FileStat, expected: FileStat) -> bool:
    """Match an emptied planned directory while ignoring child-induced churn."""

    return (
        actual.kind is EntryKind.DIRECTORY
        and expected.kind is EntryKind.DIRECTORY
        and actual.size == expected.size
        and actual.metadata == expected.metadata
        and (
            expected.file_identity is None
            or actual.file_identity == expected.file_identity
        )
    )


def _guard_path_stat(
    actual: FileStat,
    expected: FileStat,
    reason: ExecutionReason,
    detail: str,
) -> None:
    if not _matches_expected(actual, expected):
        raise OperationFailure(
            ExecutionReason.WRONG_TYPE if actual.kind is not expected.kind else reason,
            detail,
        )


def _same_file_version(actual: FileStat, expected: FileStat) -> bool:
    """Recognize one prepared file across rename and partial metadata steps."""

    return (
        actual.kind is expected.kind
        and actual.size == expected.size
        and actual.mtime_ns == expected.mtime_ns
        and (
            expected.file_identity is None
            or actual.file_identity == expected.file_identity
        )
    )


def _guard_absent(
    fs: ExecutorFileSystem, root: Path, relative_path: str
) -> None:
    if fs.stat(root, relative_path) is not None:
        raise OperationFailure(
            ExecutionReason.DESTINATION_OCCUPIED,
            f"planned absent destination is occupied: {relative_path}",
        )


def _guard_expected_target(
    fs: ExecutorFileSystem,
    target_root: Path,
    operation: PlanOperation,
) -> None:
    if operation.target_expected is None:
        _guard_absent(fs, target_root, operation.target_rel_path)
    else:
        _guard_present(
            fs,
            target_root,
            operation.target_rel_path,
            operation.target_expected,
            missing=ExecutionReason.TARGET_MISSING,
            drift=ExecutionReason.TARGET_DRIFT,
        )


def _prior_target(operation: PlanOperation) -> tuple[str, FileStat]:
    if (
        operation.prior_target_rel_path is None
        or operation.prior_target_expected is None
    ):
        raise OperationFailure(
            ExecutionReason.TARGET_MISSING,
            "move operation lacks prior-target evidence",
        )
    return operation.prior_target_rel_path, operation.prior_target_expected


def _require_stat_path(fs: ExecutorFileSystem, path: Path) -> FileStat:
    result = fs.stat_path(path)
    if result is None:
        raise OperationFailure(
            ExecutionReason.IO_ERROR, f"filesystem result disappeared: {path}"
        )
    return result


def _profiled_stat(stat: FileStat, stable_file_identity: bool) -> FileStat:
    if stable_file_identity or stat.file_identity is None:
        return stat
    return replace(stat, file_identity=None)


def _normalized_live_stat(actual: FileStat, expected: FileStat) -> FileStat:
    """Drop evidence the reviewed capability profile intentionally omitted."""

    if expected.file_identity is None and actual.file_identity is not None:
        return replace(actual, file_identity=None)
    return actual


def _attestation(
    digest: CopyDigest, subject: FileStat, clock: Clock
) -> Attestation:
    _guard_attestation_size(digest, subject)
    return Attestation(
        content=ContentEvidence(
            algorithm="xxh3_128",
            digest=digest.digest,
            size=digest.size,
            provenance=Provenance.COPY_ATTESTED,
            observed_at=clock.now(),
        ),
        subject=subject,
    )


def _guard_attestation_size(digest: CopyDigest, subject: FileStat) -> None:
    if subject.size != digest.size:
        raise OperationFailure(
            ExecutionReason.PUBLISHED_SIZE_MISMATCH,
            (
                "published target size does not match copied content: "
                f"{subject.size} != {digest.size}"
            ),
        )


def _record(
    state: _ExecutionState,
    detail: dict[str, object],
    command: Callable[[], object],
    *,
    identity_required: bool = False,
) -> RecordedCopyIdentity | None:
    try:
        result = command()
        if identity_required and not isinstance(result, RecordedCopyIdentity):
            raise TypeError(
                "copy recorder did not return a recorded copy identity"
            )
    except Exception as error:
        state.recording = RecordingStatus.DEGRADED
        detail["recording"] = RecordingStatus.DEGRADED.value
        detail["recording_error"] = (
            f"{type(error).__name__}: {logical_error_text(error)}"
        )
        return None
    return result if isinstance(result, RecordedCopyIdentity) else None


def _flush_before_destructive(
    recorder: Recorder, state: _ExecutionState
) -> None:
    try:
        recorder.flush()
    except Exception as error:
        state.recording = RecordingStatus.DEGRADED
        raise OperationFailure(
            ExecutionReason.RECORDER_FAILED,
            "recorder flush failed before destructive operation",
            cause=error,
        ) from error


def _durability_detail(
    fs: ExecutorFileSystem, *directories: Path
) -> dict[str, object]:
    warnings: list[str] = []
    seen: set[Path] = set()
    for directory in directories:
        if directory in seen:
            continue
        seen.add(directory)
        flushed = fs.flush_directory(directory)
        if not flushed:
            warnings.append(f"parent directory flush unsupported: {directory}")
    return {} if not warnings else {"durability_warnings": tuple(warnings)}
