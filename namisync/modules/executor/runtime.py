"""Guarded operations engine for reviewed sync plans."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum, StrEnum
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


class _TerminalKind(Enum):
    ORDINARY_FAILURE = "ordinary-failure"
    CANCELLATION = "cancellation"


class _PublicationClassification(Enum):
    NOT_PUBLISHED = "not-published"
    CONFIRMED = "confirmed"
    UNVERIFIED = "unverified"


class _MutationClassification(Enum):
    UNCHANGED = "unchanged"
    DURABLE = "durable"
    AMBIGUOUS = "ambiguous"
    UNREADABLE = "unreadable"


class _TargetState(StrEnum):
    UNEXPECTEDLY_PRESENT_BEFORE_PUBLISH = "unexpectedly-present-before-publish"
    ABSENT_BEFORE_PUBLISH = "absent-before-publish"
    MISSING_BEFORE_PUBLISH = "missing-before-publish"
    CHANGED_BEFORE_PUBLISH = "changed-before-publish"
    RETAINED_BEFORE_PUBLISH = "retained-before-publish"
    PUBLISHED = "published"
    CHANGED_AFTER_PUBLISH = "changed-after-publish"
    MISSING_AFTER_PUBLISH = "missing-after-publish"
    UNVERIFIED_AFTER_PUBLISH = "unverified-after-publish"
    MISSING = "missing"
    PRESENT = "present"


class _TempState(StrEnum):
    CHANGED_BEFORE_PUBLISH = "changed-before-publish"
    MISSING = "missing"
    UNEXPECTED = "unexpected"


class _BackupState(StrEnum):
    RETAINED = "retained"
    CHANGED = "changed"
    ABSENT = "absent"
    UNVERIFIED = "unverified"


class _MutationState(StrEnum):
    NOT_COMMITTED = "not-committed"
    COMMITTED = "committed"
    UNVERIFIED = "unverified"


class _EntryState(StrEnum):
    REVIEWED = "reviewed"
    ABSENT = "absent"
    CHANGED = "changed"


class _DurableState(StrEnum):
    UNVERIFIED = "unverified"
    PUBLICATION_UNVERIFIED = "publication-unverified"
    TARGET_NOT_PUBLISHED = "target-not-published"
    BACKUP_RETAINED = "backup-retained"
    TARGET_PUBLISHED = "target-published"
    TARGET_PUBLISHED_WITH_BACKUP = "target-published-with-backup"
    TARGET_CHANGED_AFTER_PUBLISH = "target-changed-after-publish"
    TARGET_MISSING_AFTER_PUBLISH = "target-missing-after-publish"
    TARGET_UNVERIFIED_AFTER_PUBLISH = "target-unverified-after-publish"
    NEW_AND_OLD = "new-and-old"
    NEW_AND_TRASH = "new-and-trash"
    NEW_OLD_AND_TRASH_UNVERIFIED = "new-old-and-trash-unverified"
    NEW_AND_OLD_UNVERIFIED = "new-and-old-unverified"
    RECASE_STATE_UNVERIFIED = "recase-state-unverified"
    MOVE_STATE_UNVERIFIED = "move-state-unverified"
    TRASH_STATE_UNVERIFIED = "trash-state-unverified"
    DELETE_STATE_UNVERIFIED = "delete-state-unverified"
    UPDATE_STATE_UNVERIFIED = "update-state-unverified"
    MKDIR_STATE_UNVERIFIED = "mkdir-state-unverified"
    SOURCE_RESTORED_AFTER_MOVE = "source-restored-after-move"
    SOURCE_RESTORED_AFTER_TRASH = "source-restored-after-trash"
    SOURCE_RETAINED = "source-retained"
    TARGET_RENAMED = "target-renamed"
    TARGET_TRASHED = "target-trashed"
    MOVE_STATE_AMBIGUOUS = "move-state-ambiguous"
    TRASH_STATE_AMBIGUOUS = "trash-state-ambiguous"
    TARGET_RESTORED_AFTER_DELETE = "target-restored-after-delete"
    TARGET_RETAINED = "target-retained"
    TARGET_DELETED = "target-deleted"
    TARGET_CHANGED_AFTER_DELETE_ATTEMPT = "target-changed-after-delete-attempt"
    TARGET_MISSING_BEFORE_PUBLISH = "target-missing-before-publish"
    TARGET_METADATA_CHANGED_BEFORE_PUBLISH = (
        "target-metadata-changed-before-publish"
    )
    DIRECTORY_MISSING_AFTER_CREATE = "directory-missing-after-create"
    DIRECTORY_ABSENT = "directory-absent"
    DIRECTORY_CREATED = "directory-created"
    DIRECTORY_PRESENT_AFTER_CREATE_ATTEMPT = (
        "directory-present-after-create-attempt"
    )
    MKDIR_STATE_AMBIGUOUS = "mkdir-state-ambiguous"


@dataclass(frozen=True, slots=True)
class _ProbeDiagnostic:
    reason: ExecutionReason
    type_name: str
    message: str


@dataclass(frozen=True, slots=True)
class _BackupVerdict:
    path: str
    state: _BackupState
    metadata: str | None = None
    state_error: str | None = None


@dataclass(frozen=True, slots=True)
class _MoveUpdateVerdict:
    prior_path: str
    durable_state: _DurableState
    trash_path: str | None = None
    old_state_error: _ProbeDiagnostic | None = None
    trash_state_error: _ProbeDiagnostic | None = None


@dataclass(frozen=True, slots=True)
class _PublicationVerdict:
    classification: _PublicationClassification
    kind: OperationKind
    published_path: str
    base_detail: dict[str, object]
    target_state: _TargetState | None = None
    target_state_error: _ProbeDiagnostic | None = None
    temp_state: _TempState | None = None
    backup: _BackupVerdict | None = None
    move_update: _MoveUpdateVerdict | None = None
    prior_path: str | None = None
    trash_path: str | None = None
    probe_error: _ProbeDiagnostic | None = None


@dataclass(frozen=True, slots=True)
class _MutationVerdict:
    classification: _MutationClassification
    kind: OperationKind
    mutation_state: _MutationState
    durable_state: _DurableState
    destination: str | None = None
    source_state: _EntryState | None = None
    destination_state: _EntryState | None = None
    probe_error: _ProbeDiagnostic | None = None


@dataclass(frozen=True, slots=True)
class _TerminalCause:
    kind: _TerminalKind
    reason: ExecutionReason
    error_type: str
    message: str
    retry_error_type: str | None = None
    retry_error: str | None = None


@dataclass(frozen=True, slots=True)
class _SettlementReduction:
    settled: _Settled
    degrade_recording: bool


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


_ByteEffect = _CopyContinuation | _UpdateContinuation | _MoveUpdateContinuation


@dataclass(frozen=True, slots=True)
class _EffectSnapshot:
    byte: _ByteEffect | None = None
    mutation: _MutationAttempt | None = None
    retry_error: Exception | None = None
    temporary_path: Path | None = None


@dataclass(slots=True)
class _EffectJournalEntry:
    byte: _ByteEffect | None = None
    mutation: _MutationAttempt | None = None
    retry_error: Exception | None = None
    temporary_path: Path | None = None
    settled: bool = False


@dataclass(slots=True)
class _EffectJournal:
    _entries: dict[OpId, _EffectJournalEntry] = field(default_factory=dict)

    def _active_entry(self, op_id: OpId) -> _EffectJournalEntry:
        entry = self._entries.setdefault(op_id, _EffectJournalEntry())
        if entry.settled:
            raise RuntimeError("executor effect journal entry is already settled")
        return entry

    def retained_byte(self, op_id: OpId) -> _ByteEffect | None:
        entry = self._entries.get(op_id)
        return None if entry is None else entry.byte

    def install_byte(self, op_id: OpId, effect: _ByteEffect) -> None:
        if not isinstance(
            effect,
            (_CopyContinuation, _UpdateContinuation, _MoveUpdateContinuation),
        ):
            raise TypeError("executor byte effect has an unsupported type")
        entry = self._active_entry(op_id)
        if entry.byte is not None:
            raise RuntimeError("executor byte effect is already installed")
        entry.byte = effect

    def retain_mutation(
        self,
        op_id: OpId,
        attempt: _MutationAttempt,
    ) -> _MutationAttempt:
        if not isinstance(attempt, _MutationAttempt):
            raise TypeError("executor mutation effect has an unsupported type")
        entry = self._active_entry(op_id)
        existing = entry.mutation
        if existing is None:
            entry.mutation = attempt
            return attempt
        if (
            existing.kind is not attempt.kind
            or existing.primary != attempt.primary
            or existing.primary_before != attempt.primary_before
            or existing.secondary != attempt.secondary
            or existing.destination_relative != attempt.destination_relative
            or existing.trash_source_relative != attempt.trash_source_relative
        ):
            raise RuntimeError("executor mutation attempt changed during retry")
        return existing

    def remember_retry_error(self, op_id: OpId, error: Exception) -> None:
        if not isinstance(error, Exception):
            raise TypeError("executor retry error must be an exception")
        self._active_entry(op_id).retry_error = error

    def has_retained_effect(self, op_id: OpId) -> bool:
        entry = self._entries.get(op_id)
        return entry is not None and (
            entry.byte is not None or entry.mutation is not None
        )

    def claim_temporary_path(self, op_id: OpId, path: Path) -> None:
        if not isinstance(path, Path):
            raise TypeError("executor temporary path must be a Path")
        for owner, entry in self._entries.items():
            if entry.temporary_path is not None:
                raise RuntimeError(
                    "executor already owns a temporary path "
                    f"for operation {owner}"
                )
        self._active_entry(op_id).temporary_path = path

    def release_temporary_path(
        self,
        op_id: OpId,
        *,
        expected: Path | None = None,
    ) -> Path | None:
        entry = self._entries.get(op_id)
        path = None if entry is None else entry.temporary_path
        if expected is not None and path != expected:
            raise RuntimeError("executor temporary path ownership changed")
        if entry is not None:
            if entry.settled:
                raise RuntimeError("executor effect journal entry is already settled")
            entry.temporary_path = None
        return path

    def snapshot(self, op_id: OpId) -> _EffectSnapshot:
        entry = self._entries.get(op_id)
        if entry is None:
            return _EffectSnapshot()
        return _EffectSnapshot(
            byte=entry.byte,
            mutation=entry.mutation,
            retry_error=entry.retry_error,
            temporary_path=entry.temporary_path,
        )

    def settle(self, op_id: OpId) -> None:
        entry = self._entries.get(op_id)
        if entry is None:
            return
        if entry.temporary_path is not None:
            raise RuntimeError(
                "executor effect journal still owns a terminal temporary path"
            )
        entry.settled = True

    def retire(self, op_id: OpId) -> None:
        entry = self._entries.get(op_id)
        if entry is None:
            return
        if not entry.settled:
            raise RuntimeError("executor effect journal entry is not settled")
        del self._entries[op_id]


@dataclass(slots=True)
class _ExecutionState:
    execution_set: ExecutionSet
    outcomes: dict[OpId, ItemOutcome]
    pending_directories: list[PlanOperation] = field(default_factory=list)
    ready_directories: set[OpId] = field(default_factory=set)
    restore_directories: set[OpId] = field(default_factory=set)
    effects: _EffectJournal = field(default_factory=_EffectJournal)
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
                    mutation_failure = _failed_durable_settlement(
                        operation,
                        error,
                        fs,
                        target_root,
                        state,
                        state.effects.snapshot(operation.op_id),
                    )
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
                        state.effects.remember_retry_error(operation.op_id, error)
                        retry_cleanup_error: Exception | None = None
                        if not state.effects.has_retained_effect(operation.op_id):
                            retry_cleanup_error = _cleanup_inflight(
                                state,
                                fs,
                                operation.op_id,
                            )
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
                        state.effects.snapshot(operation.op_id),
                    )
                    cleanup_error = _cleanup_inflight(
                        state,
                        fs,
                        operation.op_id,
                    )
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
                state.effects.snapshot(current.op_id),
            )
        )
        cleanup_error = _cleanup_inflight(
            state,
            fs,
            None if current is None else current.op_id,
        )
        if durable_settlement is not None and current is not None:
            detail = dict(durable_settlement.detail)
            if cleanup_error is not None:
                detail["cleanup_error"] = logical_error_text(cleanup_error)
                cleanup_error = None
            _settle(
                xset,
                state,
                progress,
                ctx,
                current,
                replace(durable_settlement, detail=detail),
            )
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
        _cleanup_inflight(
            state,
            fs,
            None if current is None else current.op_id,
        )
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
        _cleanup_inflight(
            state,
            fs,
            None if current is None else current.op_id,
        )
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
    state.effects.claim_temporary_path(operation.op_id, temp)
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
    existing = state.effects.retained_byte(operation.op_id)
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
        state.effects.install_byte(operation.op_id, continuation)
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
            state.effects.release_temporary_path(
                operation.op_id,
                expected=prepared.temp,
            )
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
            state.effects.release_temporary_path(
                operation.op_id,
                expected=prepared.temp,
            )
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
    existing = state.effects.retained_byte(operation.op_id)
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
        state.effects.install_byte(operation.op_id, continuation)
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
            state.effects.release_temporary_path(
                operation.op_id,
                expected=prepared.temp,
            )
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
                state.effects.release_temporary_path(
                    operation.op_id,
                    expected=prepared.temp,
                )
                continuation.published = True
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
    existing = state.effects.retained_byte(operation.op_id)
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
        state.effects.install_byte(operation.op_id, continuation)
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
            state.effects.release_temporary_path(
                operation.op_id,
                expected=prepared.temp,
            )
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
            state.effects.release_temporary_path(
                operation.op_id,
                expected=prepared.temp,
            )
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
            mutation_failure = _failed_durable_settlement(
                operation,
                error,
                fs,
                target_root,
                state,
                state.effects.snapshot(operation.op_id),
            )
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
        state.effects.settle(operation.op_id)
        state.effects.retire(operation.op_id)
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
    state.effects.settle(operation.op_id)
    state.effects.retire(operation.op_id)


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


def _probe_diagnostic(error: Exception) -> _ProbeDiagnostic:
    return _ProbeDiagnostic(
        reason=(
            error.reason
            if isinstance(error, OperationFailure)
            else ExecutionReason.IO_ERROR
        ),
        type_name=type(error).__name__,
        message=logical_error_text(error),
    )


def _observe_published_target(
    target: Path,
    expected: FileStat,
    fs: ExecutorFileSystem,
    xset: ExecutionSet,
    target_root: Path,
) -> tuple[_TargetState, _ProbeDiagnostic | None]:
    try:
        actual = _stat_target_path(fs, xset, target_root, target)
    except Exception as error:
        return _TargetState.UNVERIFIED_AFTER_PUBLISH, _probe_diagnostic(error)
    if actual is None:
        return _TargetState.MISSING_AFTER_PUBLISH, None
    if _same_file_version(actual, expected):
        return _TargetState.PUBLISHED, None
    return _TargetState.CHANGED_AFTER_PUBLISH, None


def _observe_update_backup(
    continuation: _UpdateContinuation,
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
    target_root: Path,
    relative_path: str,
) -> _BackupVerdict | None:
    backup = continuation.backup
    if backup is None:
        return None
    backup_path = _target_relative_path(backup.path, target_root)
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
        diagnostic = _probe_diagnostic(error)
        return _BackupVerdict(
            path=backup_path,
            state=_BackupState.UNVERIFIED,
            state_error=f"{diagnostic.type_name}: {diagnostic.message}",
        )
    if actual is None:
        return _BackupVerdict(backup_path, _BackupState.ABSENT)
    stable_identity = xset.plan.target_profile.stable_file_identity
    if backup.published_stat is None:
        if backup.created_stat is None:
            return _BackupVerdict(
                path=backup_path,
                state=_BackupState.UNVERIFIED,
                state_error="creation evidence unavailable",
            )
        retained = _same_unrepaired_publication(
            actual,
            backup.created_stat,
            stable_identity,
        )
        metadata = "unrepaired"
    else:
        retained = _same_file_version(
            _profiled_stat(actual, stable_identity),
            backup.published_stat,
        )
        metadata = None
    return _BackupVerdict(
        path=backup_path,
        state=(
            _BackupState.RETAINED if retained else _BackupState.CHANGED
        ),
        metadata=metadata,
    )


def _observe_new_publication(
    continuation: _CopyContinuation | _MoveUpdateContinuation,
    fs: ExecutorFileSystem,
    xset: ExecutionSet,
    target_root: Path,
) -> tuple[
    _PublicationClassification,
    _TargetState | None,
    _ProbeDiagnostic | None,
    _TempState | None,
    _ProbeDiagnostic | None,
]:
    prepared = continuation.prepared
    if continuation.published:
        target_state, target_error = _observe_published_target(
            prepared.target,
            continuation.published_stat or continuation.prepared_stat,
            fs,
            xset,
            target_root,
        )
        return (
            _PublicationClassification.CONFIRMED,
            target_state,
            target_error,
            None,
            None,
        )

    temp = _stat_target_path(fs, xset, target_root, prepared.temp)
    target = _stat_target_path(fs, xset, target_root, prepared.target)
    if temp is not None and _same_file_version(temp, continuation.prepared_stat):
        return (
            _PublicationClassification.NOT_PUBLISHED,
            (
                _TargetState.UNEXPECTEDLY_PRESENT_BEFORE_PUBLISH
                if target is not None
                else None
            ),
            None,
            None,
            None,
        )
    if temp is not None and target is None:
        return (
            _PublicationClassification.NOT_PUBLISHED,
            _TargetState.ABSENT_BEFORE_PUBLISH,
            None,
            _TempState.CHANGED_BEFORE_PUBLISH,
            None,
        )
    if temp is None and target is not None:
        return (
            _PublicationClassification.CONFIRMED,
            (
                _TargetState.PUBLISHED
                if _same_file_version(
                    target,
                    continuation.published_stat or continuation.prepared_stat,
                )
                else _TargetState.CHANGED_AFTER_PUBLISH
            ),
            None,
            None,
            None,
        )
    error = OperationFailure(
        ExecutionReason.TARGET_MISSING if target is None else ExecutionReason.TARGET_DRIFT,
        "cannot classify prepared versus published state during cancel settlement",
    )
    return (
        _PublicationClassification.UNVERIFIED,
        _TargetState.MISSING if target is None else _TargetState.PRESENT,
        None,
        _TempState.MISSING if temp is None else _TempState.UNEXPECTED,
        _probe_diagnostic(error),
    )


def _observe_update_publication(
    continuation: _UpdateContinuation,
    fs: ExecutorFileSystem,
    xset: ExecutionSet,
    target_root: Path,
) -> tuple[
    _PublicationClassification,
    _TargetState | None,
    _ProbeDiagnostic | None,
    _TempState | None,
    _ProbeDiagnostic | None,
]:
    prepared = continuation.prepared
    if continuation.published:
        target_state, target_error = _observe_published_target(
            prepared.target,
            continuation.published_stat or continuation.prepared_stat,
            fs,
            xset,
            target_root,
        )
        return (
            _PublicationClassification.CONFIRMED,
            target_state,
            target_error,
            None,
            None,
        )

    temp = _stat_target_path(fs, xset, target_root, prepared.temp)
    target = _stat_target_path(fs, xset, target_root, prepared.target)
    if temp is not None and _same_file_version(temp, continuation.prepared_stat):
        target_state = (
            _TargetState.MISSING_BEFORE_PUBLISH
            if target is None
            else _TargetState.CHANGED_BEFORE_PUBLISH
            if not _same_file_version(target, continuation.live_stat)
            else None
        )
        return (
            _PublicationClassification.NOT_PUBLISHED,
            target_state,
            None,
            None,
            None,
        )
    if (
        temp is not None
        and target is not None
        and _same_file_version(target, continuation.live_stat)
    ):
        return (
            _PublicationClassification.NOT_PUBLISHED,
            _TargetState.RETAINED_BEFORE_PUBLISH,
            None,
            _TempState.CHANGED_BEFORE_PUBLISH,
            None,
        )
    if temp is None and target is not None:
        return (
            _PublicationClassification.CONFIRMED,
            (
                _TargetState.PUBLISHED
                if _same_file_version(
                    target,
                    continuation.published_stat or continuation.prepared_stat,
                )
                else _TargetState.CHANGED_AFTER_PUBLISH
            ),
            None,
            None,
            None,
        )
    error = OperationFailure(
        ExecutionReason.TARGET_MISSING if target is None else ExecutionReason.TARGET_DRIFT,
        "cannot classify live versus published update during cancel settlement",
    )
    return (
        _PublicationClassification.UNVERIFIED,
        _TargetState.MISSING if target is None else _TargetState.PRESENT,
        None,
        _TempState.MISSING if temp is None else _TempState.UNEXPECTED,
        _probe_diagnostic(error),
    )


def _observe_move_update(
    continuation: _MoveUpdateContinuation,
    xset: ExecutionSet,
    fs: ExecutorFileSystem,
    target_root: Path,
) -> _MoveUpdateVerdict:
    old_path = target_root.joinpath(
        *PureWindowsPath(continuation.old_relative_path).parts
    )
    if continuation.trash is None:
        try:
            old = _stat_target_path(fs, xset, target_root, old_path)
        except Exception as error:
            return _MoveUpdateVerdict(
                prior_path=continuation.old_relative_path,
                durable_state=_DurableState.NEW_AND_OLD_UNVERIFIED,
                old_state_error=_probe_diagnostic(error),
            )
        return _MoveUpdateVerdict(
            prior_path=continuation.old_relative_path,
            durable_state=(
                _DurableState.NEW_AND_OLD
                if old is not None
                and _matches_expected(old, continuation.old_expected)
                else _DurableState.NEW_AND_OLD_UNVERIFIED
            ),
        )

    trash_path = _target_relative_path(continuation.trash, target_root)
    try:
        old = _stat_target_path(fs, xset, target_root, old_path)
    except Exception as error:
        return _MoveUpdateVerdict(
            prior_path=continuation.old_relative_path,
            trash_path=trash_path,
            durable_state=_DurableState.NEW_AND_OLD_UNVERIFIED,
            old_state_error=_probe_diagnostic(error),
        )
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
        return _MoveUpdateVerdict(
            prior_path=continuation.old_relative_path,
            trash_path=trash_path,
            durable_state=_DurableState.NEW_AND_OLD_UNVERIFIED,
            trash_state_error=_probe_diagnostic(error),
        )
    if old is not None and _matches_expected(old, continuation.old_expected):
        durable_state = (
            _DurableState.NEW_AND_OLD
            if trash is None
            else _DurableState.NEW_OLD_AND_TRASH_UNVERIFIED
        )
    elif old is None and trash is not None and _matches_expected(
        trash,
        continuation.old_expected,
    ):
        durable_state = _DurableState.NEW_AND_TRASH
    else:
        durable_state = _DurableState.NEW_AND_OLD_UNVERIFIED
    return _MoveUpdateVerdict(
        prior_path=continuation.old_relative_path,
        trash_path=trash_path,
        durable_state=durable_state,
    )


def _observe_publication(
    operation: PlanOperation,
    continuation: _ByteEffect,
    fs: ExecutorFileSystem,
    target_root: Path,
    xset: ExecutionSet,
) -> _PublicationVerdict:
    backup: _BackupVerdict | None = None
    try:
        if isinstance(continuation, _UpdateContinuation):
            backup = _observe_update_backup(
                continuation,
                xset,
                fs,
                target_root,
                operation.target_rel_path,
            )
            (
                classification,
                target_state,
                target_error,
                temp_state,
                probe_error,
            ) = (
                _observe_update_publication(
                    continuation,
                    fs,
                    xset,
                    target_root,
                )
            )
        else:
            (
                classification,
                target_state,
                target_error,
                temp_state,
                probe_error,
            ) = (
                _observe_new_publication(
                    continuation,
                    fs,
                    xset,
                    target_root,
                )
            )
    except Exception as error:
        return _PublicationVerdict(
            classification=_PublicationClassification.UNVERIFIED,
            kind=operation.kind,
            published_path=operation.target_rel_path,
            base_detail=dict(continuation.detail),
            backup=backup,
            probe_error=_probe_diagnostic(error),
        )

    move_update: _MoveUpdateVerdict | None = None
    prior_path: str | None = None
    trash_path: str | None = None
    if isinstance(continuation, _MoveUpdateContinuation):
        prior_path = continuation.old_relative_path
        if continuation.trash is not None:
            trash_path = _target_relative_path(continuation.trash, target_root)
        if (
            classification is _PublicationClassification.CONFIRMED
            and target_state is _TargetState.PUBLISHED
        ):
            move_update = _observe_move_update(
                continuation,
                xset,
                fs,
                target_root,
            )
    return _PublicationVerdict(
        classification=classification,
        kind=operation.kind,
        published_path=operation.target_rel_path,
        base_detail=dict(continuation.detail),
        target_state=target_state,
        target_state_error=target_error,
        temp_state=temp_state,
        backup=backup,
        move_update=move_update,
        prior_path=prior_path,
        trash_path=trash_path,
        probe_error=probe_error,
    )


def _failure_terminal_cause(error: Exception) -> _TerminalCause:
    reason, message = _failure_reason_and_message(error)
    return _TerminalCause(
        kind=_TerminalKind.ORDINARY_FAILURE,
        reason=reason,
        error_type=type(error).__name__,
        message=message,
    )


def _cancellation_terminal_cause(
    retry_error: Exception | None,
) -> _TerminalCause:
    error = retry_error or Canceled()
    return _TerminalCause(
        kind=_TerminalKind.CANCELLATION,
        reason=ExecutionReason.CANCELED,
        error_type=type(error).__name__,
        message=logical_error_text(error),
        retry_error_type=(
            None if retry_error is None else type(retry_error).__name__
        ),
        retry_error=(
            None if retry_error is None else logical_error_text(retry_error)
        ),
    )


def _inline_probe_error(error: _ProbeDiagnostic) -> str:
    return f"{error.type_name}: {error.message}"


def _add_publication_observations(
    detail: dict[str, object],
    verdict: _PublicationVerdict,
) -> None:
    if verdict.temp_state is not None:
        detail["temp_state"] = verdict.temp_state.value
    if verdict.target_state is not None:
        detail["target_state"] = verdict.target_state.value
    if verdict.target_state_error is not None:
        detail["target_state_error"] = _inline_probe_error(
            verdict.target_state_error
        )
    if verdict.backup is not None:
        detail["backup_path"] = verdict.backup.path
        detail["backup_state"] = verdict.backup.state.value
        if verdict.backup.metadata is not None:
            detail["backup_metadata"] = verdict.backup.metadata
        if verdict.backup.state_error is not None:
            detail["backup_state_error"] = verdict.backup.state_error


def _target_durable_state(target_state: _TargetState | None) -> _DurableState:
    states = {
        _TargetState.PUBLISHED: _DurableState.TARGET_PUBLISHED,
        _TargetState.CHANGED_AFTER_PUBLISH: (
            _DurableState.TARGET_CHANGED_AFTER_PUBLISH
        ),
        _TargetState.MISSING_AFTER_PUBLISH: (
            _DurableState.TARGET_MISSING_AFTER_PUBLISH
        ),
        _TargetState.UNVERIFIED_AFTER_PUBLISH: (
            _DurableState.TARGET_UNVERIFIED_AFTER_PUBLISH
        ),
    }
    try:
        return states[target_state]
    except KeyError as error:
        raise RuntimeError(
            "confirmed publication lacks a terminal target observation"
        ) from error


def _add_move_update_observations(
    detail: dict[str, object],
    verdict: _MoveUpdateVerdict,
) -> None:
    detail["prior_path"] = verdict.prior_path
    if verdict.trash_path is not None:
        detail["trash_path"] = verdict.trash_path
    detail["durable_state"] = verdict.durable_state.value
    if verdict.old_state_error is not None:
        detail["old_state_error"] = _inline_probe_error(
            verdict.old_state_error
        )
    if verdict.trash_state_error is not None:
        detail["trash_state_error"] = _inline_probe_error(
            verdict.trash_state_error
        )


def _reduce_publication(
    cause: _TerminalCause,
    verdict: _PublicationVerdict,
) -> _SettlementReduction | None:
    detail = (
        dict(verdict.base_detail)
        if cause.kind is _TerminalKind.ORDINARY_FAILURE
        or verdict.kind is OperationKind.UPDATE
        else {}
    )
    if cause.kind is _TerminalKind.ORDINARY_FAILURE:
        detail.update(
            {
                "error_type": cause.error_type,
                "message": cause.message,
            }
        )
    elif cause.retry_error_type is not None:
        detail["retry_error_type"] = cause.retry_error_type
        detail["retry_error"] = cause.retry_error or ""
    _add_publication_observations(detail, verdict)
    retained_backup = (
        verdict.backup is not None
        and verdict.backup.state is _BackupState.RETAINED
    )

    if verdict.classification is _PublicationClassification.NOT_PUBLISHED:
        if (
            cause.kind is _TerminalKind.ORDINARY_FAILURE
            and not retained_backup
        ):
            return None
        detail["publish_state"] = "not-published"
        detail["durable_state"] = (
            _DurableState.BACKUP_RETAINED.value
            if retained_backup
            else _DurableState.TARGET_NOT_PUBLISHED.value
        )
        return _SettlementReduction(
            _Settled(
                (
                    Outcome.FAILED
                    if cause.kind is _TerminalKind.ORDINARY_FAILURE
                    else Outcome.CANCELED
                ),
                cause.reason,
                detail,
            ),
            degrade_recording=False,
        )

    if verdict.classification is _PublicationClassification.UNVERIFIED:
        if verdict.probe_error is None:
            raise RuntimeError("unverified publication lacks its probe error")
        detail["publish_state"] = "unverified"
        if cause.kind is _TerminalKind.ORDINARY_FAILURE:
            detail["published_path"] = verdict.published_path
            detail["durable_state"] = _DurableState.PUBLICATION_UNVERIFIED.value
            detail["recording"] = RecordingStatus.DEGRADED.value
            detail["recording_error"] = (
                "filesystem mutation may have published but durable state "
                "could not be verified"
            )
            reason = cause.reason
            degrade = True
        else:
            detail["durable_state"] = (
                _DurableState.BACKUP_RETAINED.value
                if retained_backup
                else _DurableState.UNVERIFIED.value
            )
            reason = verdict.probe_error.reason
            degrade = False
        detail["state_error_type"] = verdict.probe_error.type_name
        detail["state_error"] = verdict.probe_error.message
        return _SettlementReduction(
            _Settled(Outcome.FAILED, reason, detail),
            degrade_recording=degrade,
        )

    if verdict.classification is not _PublicationClassification.CONFIRMED:
        raise RuntimeError("unsupported publication classification")
    detail["publish_state"] = "published"
    detail["published_path"] = verdict.published_path
    target_durable_state = _target_durable_state(verdict.target_state)
    if verdict.kind is OperationKind.UPDATE:
        detail["durable_state"] = target_durable_state.value
        if (
            target_durable_state is _DurableState.TARGET_PUBLISHED
            and verdict.backup is not None
            and verdict.backup.state is _BackupState.RETAINED
        ):
            detail["durable_state"] = (
                _DurableState.TARGET_PUBLISHED_WITH_BACKUP.value
            )
    elif verdict.kind is OperationKind.MOVE_UPDATE:
        if target_durable_state is _DurableState.TARGET_PUBLISHED:
            if verdict.move_update is None:
                raise RuntimeError(
                    "confirmed move-update lacks old/trash observation"
                )
            _add_move_update_observations(detail, verdict.move_update)
        else:
            if verdict.prior_path is None:
                raise RuntimeError("move-update lacks its prior path")
            detail["prior_path"] = verdict.prior_path
            if verdict.trash_path is not None:
                detail["trash_path"] = verdict.trash_path
            detail["durable_state"] = target_durable_state.value
    else:
        detail["durable_state"] = target_durable_state.value
    detail["recording"] = RecordingStatus.DEGRADED.value
    detail["recording_error"] = (
        "published filesystem mutation failed before ledger settlement"
        if cause.kind is _TerminalKind.ORDINARY_FAILURE
        else "cancellation interrupted settlement of a published filesystem mutation"
    )
    return _SettlementReduction(
        _Settled(
            Outcome.FAILED,
            (
                cause.reason
                if cause.kind is _TerminalKind.ORDINARY_FAILURE
                else ExecutionReason.CANCELED_AFTER_PUBLISH
            ),
            detail,
        ),
        degrade_recording=True,
    )


def _reduce_mutation(
    cause: _TerminalCause,
    verdict: _MutationVerdict,
) -> _SettlementReduction | None:
    if verdict.classification is _MutationClassification.UNCHANGED:
        return None
    if verdict.classification not in {
        _MutationClassification.DURABLE,
        _MutationClassification.AMBIGUOUS,
        _MutationClassification.UNREADABLE,
    }:
        raise RuntimeError("unsupported mutation classification")
    detail: dict[str, object] = {
        "error_type": cause.error_type,
        "message": (
            cause.message
            if cause.kind is _TerminalKind.ORDINARY_FAILURE
            else "cancellation interrupted settlement after a mutation attempt"
        ),
    }
    if verdict.kind is OperationKind.UPDATE:
        detail["publish_state"] = "not-published"
    if verdict.destination is not None:
        detail["mutation_destination"] = verdict.destination
    if verdict.source_state is not None:
        detail["source_state"] = verdict.source_state.value
    if verdict.destination_state is not None:
        detail["destination_state"] = verdict.destination_state.value
    detail["mutation_state"] = verdict.mutation_state.value
    detail["durable_state"] = verdict.durable_state.value
    if verdict.probe_error is not None:
        detail["mutation_state_error"] = _inline_probe_error(
            verdict.probe_error
        )
    detail["recording"] = RecordingStatus.DEGRADED.value
    detail["recording_error"] = (
        "filesystem mutation may have committed before ledger settlement"
    )
    return _SettlementReduction(
        _Settled(
            Outcome.FAILED,
            (
                cause.reason
                if cause.kind is _TerminalKind.ORDINARY_FAILURE
                else ExecutionReason.CANCELED_AFTER_MUTATION
            ),
            detail,
        ),
        degrade_recording=True,
    )


def _reduce_effect_settlement(
    cause: _TerminalCause,
    publication: _PublicationVerdict | None,
    mutation: _MutationVerdict | None,
) -> _SettlementReduction | None:
    publication_reduction = (
        None if publication is None else _reduce_publication(cause, publication)
    )
    if (
        publication is not None
        and publication.classification is _PublicationClassification.CONFIRMED
    ):
        return publication_reduction
    mutation_reduction = (
        None if mutation is None else _reduce_mutation(cause, mutation)
    )
    if publication_reduction is None:
        return mutation_reduction
    if mutation_reduction is None:
        return publication_reduction

    publication_detail = dict(publication_reduction.settled.detail)
    mutation_detail = dict(mutation_reduction.settled.detail)
    if cause.kind is _TerminalKind.ORDINARY_FAILURE:
        for duplicate in ("error_type", "message", "publish_state"):
            mutation_detail.pop(duplicate, None)
        if publication_reduction.degrade_recording:
            for duplicate in ("recording", "recording_error"):
                mutation_detail.pop(duplicate, None)
        mutation_durable_state = mutation_detail.pop("durable_state", None)
        publication_detail.update(mutation_detail)
        if mutation_durable_state is not None:
            publication_detail["mutation_durable_state"] = (
                mutation_durable_state
            )
        settled = replace(
            publication_reduction.settled,
            detail=publication_detail,
        )
    else:
        mutation_detail.pop("publish_state", None)
        mutation_durable_state = mutation_detail.pop("durable_state", None)
        publication_detail.update(mutation_detail)
        if mutation_durable_state is not None:
            publication_detail["mutation_durable_state"] = (
                mutation_durable_state
            )
        settled = replace(
            mutation_reduction.settled,
            detail=publication_detail,
        )
    return _SettlementReduction(
        settled=settled,
        degrade_recording=(
            publication_reduction.degrade_recording
            or mutation_reduction.degrade_recording
        ),
    )


def _apply_settlement_reduction(
    state: _ExecutionState,
    reduction: _SettlementReduction | None,
) -> _Settled | None:
    if reduction is None:
        return None
    if reduction.degrade_recording:
        state.recording = RecordingStatus.DEGRADED
    return reduction.settled


def _settle_durable_effects(
    operation: PlanOperation,
    cause: _TerminalCause,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
    effects: _EffectSnapshot,
) -> _Settled | None:
    publication = (
        None
        if effects.byte is None
        else _observe_publication(
            operation,
            effects.byte,
            fs,
            target_root,
            state.execution_set,
        )
    )
    mutation = (
        None
        if effects.mutation is None
        or (
            publication is not None
            and publication.classification
            is _PublicationClassification.CONFIRMED
        )
        else _observe_mutation(effects.mutation, fs, state)
    )
    return _apply_settlement_reduction(
        state,
        _reduce_effect_settlement(
            cause,
            publication,
            mutation,
        ),
    )


def _failed_durable_settlement(
    operation: PlanOperation,
    error: Exception,
    fs: ExecutorFileSystem,
    target_root: Path,
    state: _ExecutionState,
    effects: _EffectSnapshot,
) -> _Settled | None:
    return _settle_durable_effects(
        operation,
        _failure_terminal_cause(error),
        fs,
        target_root,
        state,
        effects,
    )


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
    return state.effects.retain_mutation(
        operation.op_id,
        _MutationAttempt(
            kind=operation.kind,
            primary=primary,
            primary_before=normalized_before,
            secondary=secondary,
            destination_relative=destination_relative,
            trash_source_relative=trash_source_relative,
        ),
    )


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


def _mutation_unreadable_state(kind: OperationKind) -> _DurableState:
    states = {
        OperationKind.MOVE: _DurableState.MOVE_STATE_UNVERIFIED,
        OperationKind.TRASH: _DurableState.TRASH_STATE_UNVERIFIED,
        OperationKind.DELETE: _DurableState.DELETE_STATE_UNVERIFIED,
        OperationKind.UPDATE: _DurableState.UPDATE_STATE_UNVERIFIED,
        OperationKind.MKDIR: _DurableState.MKDIR_STATE_UNVERIFIED,
    }
    return states[kind]


def _observed_entry_state(
    actual: FileStat | None,
    expected: FileStat,
) -> _EntryState:
    if actual is None:
        return _EntryState.ABSENT
    return (
        _EntryState.REVIEWED
        if _matches_expected(actual, expected)
        else _EntryState.CHANGED
    )


def _observe_mutation(
    attempt: _MutationAttempt,
    fs: ExecutorFileSystem,
    state: _ExecutionState,
) -> _MutationVerdict:
    if attempt.kind is OperationKind.RECASE:
        return _MutationVerdict(
            classification=(
                _MutationClassification.DURABLE
                if attempt.committed
                else _MutationClassification.AMBIGUOUS
            ),
            kind=attempt.kind,
            mutation_state=(
                _MutationState.COMMITTED
                if attempt.committed
                else _MutationState.UNVERIFIED
            ),
            durable_state=_DurableState.RECASE_STATE_UNVERIFIED,
        )

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
    except Exception as error:
        return _MutationVerdict(
            classification=_MutationClassification.UNREADABLE,
            kind=attempt.kind,
            mutation_state=(
                _MutationState.COMMITTED
                if attempt.committed
                else _MutationState.UNVERIFIED
            ),
            durable_state=_mutation_unreadable_state(attempt.kind),
            destination=attempt.destination_relative,
            probe_error=_probe_diagnostic(error),
        )

    before = attempt.primary_before
    if attempt.kind in {OperationKind.MOVE, OperationKind.TRASH}:
        assert before is not None and attempt.secondary is not None
        source_state = _observed_entry_state(primary, before)
        destination_state = _observed_entry_state(secondary, before)
        if (
            source_state is _EntryState.REVIEWED
            and destination_state is _EntryState.ABSENT
        ):
            if attempt.committed:
                return _MutationVerdict(
                    classification=_MutationClassification.DURABLE,
                    kind=attempt.kind,
                    mutation_state=_MutationState.COMMITTED,
                    durable_state=(
                        _DurableState.SOURCE_RESTORED_AFTER_MOVE
                        if attempt.kind is OperationKind.MOVE
                        else _DurableState.SOURCE_RESTORED_AFTER_TRASH
                    ),
                    destination=attempt.destination_relative,
                    source_state=source_state,
                    destination_state=destination_state,
                )
            return _MutationVerdict(
                classification=_MutationClassification.UNCHANGED,
                kind=attempt.kind,
                mutation_state=_MutationState.NOT_COMMITTED,
                durable_state=_DurableState.SOURCE_RETAINED,
                destination=attempt.destination_relative,
                source_state=source_state,
                destination_state=destination_state,
            )
        if (
            source_state is _EntryState.ABSENT
            and destination_state is _EntryState.REVIEWED
        ):
            return _MutationVerdict(
                classification=_MutationClassification.DURABLE,
                kind=attempt.kind,
                mutation_state=_MutationState.COMMITTED,
                durable_state=(
                    _DurableState.TARGET_RENAMED
                    if attempt.kind is OperationKind.MOVE
                    else _DurableState.TARGET_TRASHED
                ),
                destination=attempt.destination_relative,
                source_state=source_state,
                destination_state=destination_state,
            )
        return _MutationVerdict(
            classification=_MutationClassification.AMBIGUOUS,
            kind=attempt.kind,
            mutation_state=(
                _MutationState.COMMITTED
                if attempt.committed
                else _MutationState.UNVERIFIED
            ),
            durable_state=(
                _DurableState.MOVE_STATE_AMBIGUOUS
                if attempt.kind is OperationKind.MOVE
                else _DurableState.TRASH_STATE_AMBIGUOUS
            ),
            destination=attempt.destination_relative,
            source_state=source_state,
            destination_state=destination_state,
        )

    if attempt.kind is OperationKind.DELETE:
        assert before is not None
        if primary is not None and _matches_expected(primary, before):
            if attempt.committed:
                return _MutationVerdict(
                    classification=_MutationClassification.DURABLE,
                    kind=attempt.kind,
                    mutation_state=_MutationState.COMMITTED,
                    durable_state=_DurableState.TARGET_RESTORED_AFTER_DELETE,
                )
            return _MutationVerdict(
                classification=_MutationClassification.UNCHANGED,
                kind=attempt.kind,
                mutation_state=_MutationState.NOT_COMMITTED,
                durable_state=_DurableState.TARGET_RETAINED,
            )
        return _MutationVerdict(
            classification=(
                _MutationClassification.DURABLE
                if attempt.committed or primary is None
                else _MutationClassification.AMBIGUOUS
            ),
            kind=attempt.kind,
            mutation_state=(
                _MutationState.COMMITTED
                if attempt.committed or primary is None
                else _MutationState.UNVERIFIED
            ),
            durable_state=(
                _DurableState.TARGET_DELETED
                if primary is None
                else _DurableState.TARGET_CHANGED_AFTER_DELETE_ATTEMPT
            ),
        )

    if attempt.kind is OperationKind.UPDATE:
        assert before is not None
        if primary is not None and _matches_expected(primary, before):
            return _MutationVerdict(
                classification=_MutationClassification.UNCHANGED,
                kind=attempt.kind,
                mutation_state=_MutationState.NOT_COMMITTED,
                durable_state=_DurableState.TARGET_RETAINED,
            )
        return _MutationVerdict(
            classification=_MutationClassification.AMBIGUOUS,
            kind=attempt.kind,
            mutation_state=_MutationState.UNVERIFIED,
            durable_state=(
                _DurableState.TARGET_MISSING_BEFORE_PUBLISH
                if primary is None
                else _DurableState.TARGET_METADATA_CHANGED_BEFORE_PUBLISH
            ),
        )

    if attempt.kind is OperationKind.MKDIR:
        if primary is None:
            if attempt.committed:
                return _MutationVerdict(
                    classification=_MutationClassification.DURABLE,
                    kind=attempt.kind,
                    mutation_state=_MutationState.COMMITTED,
                    durable_state=_DurableState.DIRECTORY_MISSING_AFTER_CREATE,
                )
            return _MutationVerdict(
                classification=_MutationClassification.UNCHANGED,
                kind=attempt.kind,
                mutation_state=_MutationState.NOT_COMMITTED,
                durable_state=_DurableState.DIRECTORY_ABSENT,
            )
        directory = primary.kind is EntryKind.DIRECTORY
        return _MutationVerdict(
            classification=(
                _MutationClassification.DURABLE
                if attempt.committed and directory
                else _MutationClassification.AMBIGUOUS
            ),
            kind=attempt.kind,
            mutation_state=(
                _MutationState.COMMITTED
                if attempt.committed
                else _MutationState.UNVERIFIED
            ),
            durable_state=(
                _DurableState.DIRECTORY_CREATED
                if attempt.committed and directory
                else _DurableState.DIRECTORY_PRESENT_AFTER_CREATE_ATTEMPT
                if directory
                else _DurableState.MKDIR_STATE_AMBIGUOUS
            ),
        )

    raise RuntimeError(f"unsupported mutation attempt kind: {attempt.kind}")


def _cleanup_inflight(
    state: _ExecutionState,
    fs: ExecutorFileSystem,
    op_id: OpId | None,
) -> Exception | None:
    if op_id is None:
        return None
    temp = state.effects.release_temporary_path(op_id)
    if temp is None:
        return None
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
        if not state.effects.has_retained_effect(op_id):
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
    effects: _EffectSnapshot,
) -> _Settled | None:
    return _settle_durable_effects(
        operation,
        _cancellation_terminal_cause(effects.retry_error),
        fs,
        target_root,
        state,
        effects,
    )


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
