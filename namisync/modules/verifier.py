"""Cache-honest baseline and integrity verification.

The verifier owns classification and hashing only.  Inventory refresh, ledger
transactions, session terminals, and audit persistence remain injected through
core protocols and the workflow/dispatcher layers.
"""

from __future__ import annotations

import ctypes
import ntpath
import os
from ctypes import wintypes
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, replace
from pathlib import Path, PureWindowsPath
from typing import Callable, Iterator

from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    HasherContractError,
    Provenance,
    RecordingStatus,
    finish_content_hasher,
    new_content_hasher,
    update_content_hasher,
)
from namisync.core.events import Progress
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityOutcome,
    IntegrityReason,
    IntegrityRecorder,
    IntegrityRecordCommand,
    IntegrityResult,
    IntegrityRunResult,
    IntegritySelection,
    IntegritySelectionItem,
    InventoryState,
    PostCopyCandidate,
    PostCopySelection,
    ReadStrategy,
    RecordDisposition,
    UnsupportedVerification,
    VerificationReader,
    VerificationInvalidationCommand,
    VerificationInvalidationReason,
    VerifierContext,
)
from namisync.core.models import (
    EntryKind,
    FileIdentity,
    FileStat,
    MetadataSnapshot,
)
from namisync.core.pathing import (
    lexical_absolute_path,
    logical_error_text,
    normalize_relative_path,
    to_extended_length_path,
    validate_relative_path,
)
from namisync.core.session import Canceled, PauseRequested
from namisync.core.root_authority import (
    RootAuthority,
    RootAuthorityError,
    RootAuthorityIssue,
    admit_root,
    admit_root_chain,
    is_placeholder_stat,
    is_reparse_stat,
)


_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_GENERIC_READ = 0x80000000
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_SHARE_DELETE = 0x00000004
_OPEN_EXISTING = 3
_FILE_FLAG_NO_BUFFERING = 0x20000000
_FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_MEM_COMMIT = 0x00001000
_MEM_RESERVE = 0x00002000
_MEM_RELEASE = 0x00008000
_PAGE_READWRITE = 0x04
_ERROR_FILE_NOT_FOUND = 2
_ERROR_PATH_NOT_FOUND = 3
_ERROR_ACCESS_DENIED = 5
_ERROR_INVALID_PARAMETER = 87
_WINDOWS_EPOCH_TICKS = 116_444_736_000_000_000


def _reader_for_context(
    ctx: VerifierContext,
    reader: VerificationReader | None,
) -> VerificationReader:
    if reader is None:
        if ctx.root_authority is None:
            raise ValueError(
                "the default verification reader requires root authority"
            )
        return WindowsUnbufferedReader(ctx.root_authority)
    if (
        ctx.root_authority is None
        and isinstance(reader, WindowsUnbufferedReader)
    ):
        raise ValueError(
            "the native verification reader requires root authority"
        )
    return reader


def _open_reader(
    reader: VerificationReader,
    root: Path,
    relative_path: str,
    ctx: VerifierContext,
) -> AbstractContextManager:
    if type(reader) is WindowsUnbufferedReader:
        authority = ctx.root_authority
        if authority is None:
            raise ValueError(
                "the native verification reader requires root authority"
            )
        return reader._open_with_authority(  # type: ignore[attr-defined]
            root,
            relative_path,
            authority,
        )
    return reader.open(root, relative_path)


def baseline(
    selection: IntegritySelection,
    ctx: VerifierContext,
    recorder: IntegrityRecorder,
    reader: VerificationReader | None = None,
) -> IntegrityRunResult:
    """Create evidence only for freshly selected rows without a baseline."""

    return _run(selection, ctx, recorder, reader, IntegrityMode.BASELINE)


def verify(
    selection: IntegritySelection,
    ctx: VerifierContext,
    recorder: IntegrityRecorder,
    reader: VerificationReader | None = None,
) -> IntegrityRunResult:
    """Classify selected rows against retained stat and XXH3-128 evidence."""

    return _run(selection, ctx, recorder, reader, IntegrityMode.VERIFY)


def rebaseline(
    selection: IntegritySelection,
    ctx: VerifierContext,
    recorder: IntegrityRecorder,
    reader: VerificationReader | None = None,
) -> IntegrityRunResult:
    """Explicitly accept freshly inventoried current content as new evidence."""

    return _run(selection, ctx, recorder, reader, IntegrityMode.REBASELINE)


def verify_post_copy(
    selection: PostCopySelection,
    ctx: VerifierContext,
    recorder: IntegrityRecorder,
    reader: VerificationReader | None = None,
) -> IntegrityRunResult:
    """Read back transient published targets without requiring ledger rows."""

    actual_reader = _reader_for_context(ctx, reader)
    emitted: list[IntegrityOutcome] = []
    reporter = _ProgressReporter(
        selection,
        ctx,
        items_total=len(selection.candidates),
        pending_sizes=tuple(
            candidate.expected_stat.size for candidate in selection.pending
        ),
    )

    try:
        for candidate in selection.pending:
            ctx.run.checkpoint()
            processed = _process_post_copy_candidate(
                candidate, ctx, recorder, actual_reader, reporter
            )
            _emit_and_complete_post_copy(
                selection, ctx, reporter, processed, emitted
            )
    except PauseRequested:
        raise
    except Canceled:
        for candidate in selection.pending:
            processed = _ProcessedItem(
                _post_copy_outcome(
                    candidate,
                    IntegrityResult.CANCELED,
                    IntegrityReason.CANCELED,
                    recording=(
                        RecordingStatus.OK
                        if candidate.recorded_identity is not None
                        else RecordingStatus.DEGRADED
                    ),
                )
            )
            _emit_and_complete_post_copy(
                selection,
                ctx,
                reporter,
                processed,
                emitted,
                emit_progress=False,
            )
        reporter.emit(current_path=None, force=True)
        raise

    recording = (
        RecordingStatus.DEGRADED
        if any(outcome.recording is RecordingStatus.DEGRADED for outcome in emitted)
        else RecordingStatus.OK
    )
    return IntegrityRunResult(tuple(emitted), recording)


@dataclass(frozen=True)
class _ProcessedItem:
    outcome: IntegrityOutcome
    bytes_read: int = 0


@dataclass(frozen=True)
class _SubjectClassification:
    """Ledger-neutral result of one guarded subject read."""

    result: IntegrityResult
    reason: IntegrityReason | None = None
    detail: str | None = None
    read_strategy: ReadStrategy | None = None
    bytes_read: int = 0
    attestation: Attestation | None = None


@dataclass(frozen=True, slots=True)
class _RecordingObservation:
    disposition: RecordDisposition | None = None
    error_detail: str | None = None


@dataclass(frozen=True, slots=True)
class _RecordingSettlement:
    reason: IntegrityReason | None
    detail: str | None
    recording: RecordingStatus
    record_disposition: RecordDisposition | None


class _ProgressReporter:
    def __init__(
        self,
        selection: IntegritySelection | PostCopySelection,
        ctx: VerifierContext,
        *,
        items_total: int,
        pending_sizes: tuple[int, ...],
    ) -> None:
        self._selection = selection
        self._ctx = ctx
        self._items_total = items_total
        self._last_emitted_at: float | None = None
        self._bytes_total = selection.processed_bytes + sum(pending_sizes)
        self.emit(current_path=None, force=True)

    def bytes_processed(self, size: int, current_path: str) -> None:
        self._selection.note_bytes_processed(size)
        if self._selection.processed_bytes > self._bytes_total:
            # A subject that grows during the read will later classify as drift,
            # but its lossy progress snapshots must remain constructible first.
            self._bytes_total = self._selection.processed_bytes
        self.emit(current_path=current_path, force=False)

    def item_completed(self, current_path: str) -> None:
        self.emit(current_path=current_path, force=True)

    def emit(self, current_path: str | None, force: bool) -> None:
        now = self._ctx.monotonic()
        if not force and self._last_emitted_at is not None:
            if now - self._last_emitted_at < self._ctx.progress_interval_seconds:
                return
        self._ctx.run.emit(
            Progress(
                items_done=self._selection.completed_count,
                items_total=self._items_total,
                bytes_done=self._selection.processed_bytes,
                bytes_total=self._bytes_total,
                current_path=current_path,
            )
        )
        self._last_emitted_at = now


def _run(
    selection: IntegritySelection,
    ctx: VerifierContext,
    recorder: IntegrityRecorder,
    reader: VerificationReader | None,
    mode: IntegrityMode,
) -> IntegrityRunResult:
    actual_reader = _reader_for_context(ctx, reader)
    emitted: list[IntegrityOutcome] = []
    reporter = _ProgressReporter(
        selection,
        ctx,
        items_total=len(selection.items),
        pending_sizes=tuple(
            item.expected_stat.size
            for item in selection.pending
            if item.expected_state is InventoryState.PRESENT
            and item.expected_stat is not None
        ),
    )

    try:
        for item in selection.pending:
            ctx.run.checkpoint()
            processed = _process_item(
                item, mode, ctx, recorder, actual_reader, reporter
            )
            _emit_and_complete(selection, ctx, reporter, processed, emitted)
    except PauseRequested:
        # Pending and in-flight items stay pending.  Their reliable outcomes are
        # emitted only when a resumed pass actually settles them.
        raise
    except Canceled:
        # The runner aggregates reliable events and cannot inspect module state.
        # Complete every still-pending row before the payload-free unwind leaves.
        for item in selection.pending:
            processed = _ProcessedItem(
                _outcome(
                    item,
                    mode,
                    IntegrityResult.CANCELED,
                    IntegrityReason.CANCELED,
                )
            )
            _emit_and_complete(
                selection, ctx, reporter, processed, emitted, emit_progress=False
            )
        reporter.emit(current_path=None, force=True)
        raise

    recording = (
        RecordingStatus.DEGRADED
        if any(outcome.recording is RecordingStatus.DEGRADED for outcome in emitted)
        else RecordingStatus.OK
    )
    return IntegrityRunResult(tuple(emitted), recording)


def _emit_and_complete(
    selection: IntegritySelection,
    ctx: VerifierContext,
    reporter: _ProgressReporter,
    processed: _ProcessedItem,
    emitted: list[IntegrityOutcome],
    *,
    emit_progress: bool = True,
) -> None:
    # Outcome first, continuation second: after a pause, completed status can
    # never exist without the reliable result that justifies skipping the row.
    ctx.run.emit(processed.outcome)
    selection.mark_completed(processed.outcome.item_id, processed.bytes_read)
    emitted.append(processed.outcome)
    if emit_progress:
        reporter.item_completed(processed.outcome.path)


def _emit_and_complete_post_copy(
    selection: PostCopySelection,
    ctx: VerifierContext,
    reporter: _ProgressReporter,
    processed: _ProcessedItem,
    emitted: list[IntegrityOutcome],
    *,
    emit_progress: bool = True,
) -> None:
    # Preserve the same reliable-event-before-continuation ordering as
    # standalone integrity selections.
    ctx.run.emit(processed.outcome)
    selection.mark_completed(processed.outcome.item_id, processed.bytes_read)
    emitted.append(processed.outcome)
    if emit_progress:
        reporter.item_completed(processed.outcome.path)


def _process_post_copy_candidate(
    candidate: PostCopyCandidate,
    ctx: VerifierContext,
    recorder: IntegrityRecorder,
    reader: VerificationReader,
    reporter: _ProgressReporter,
) -> _ProcessedItem:
    try:
        validated_path = validate_relative_path(candidate.display_path)
    except (OSError, ValueError) as exc:
        return _ProcessedItem(
            _post_copy_outcome(
                candidate,
                IntegrityResult.ERROR,
                IntegrityReason.PATH_INVALID,
                _error_detail(exc),
                recording=(
                    RecordingStatus.OK
                    if candidate.recorded_identity is not None
                    else RecordingStatus.DEGRADED
                ),
            )
        )
    try:
        _require_selected_root(candidate.root, ctx)
    except UnsupportedVerification as exc:
        return _ProcessedItem(
            _post_copy_outcome(
                candidate,
                IntegrityResult.UNSUPPORTED,
                IntegrityReason.UNSUPPORTED_READ,
                _error_detail(exc),
                recording=(
                    RecordingStatus.OK
                    if candidate.recorded_identity is not None
                    else RecordingStatus.DEGRADED
                ),
            )
        )

    classification = _classify_subject(
        root=candidate.root,
        relative_path=validated_path,
        expected_stat=candidate.expected_stat,
        baseline=candidate.copy_attestation,
        mode=IntegrityMode.VERIFY,
        ctx=ctx,
        reader=reader,
        on_bytes=lambda size: reporter.bytes_processed(
            size, candidate.display_path
        ),
        success_provenance=Provenance.READBACK_ATTESTED,
    )
    identity = candidate.recorded_identity
    if classification.attestation is None:
        if (
            identity is not None
            and classification.result
            in {
                IntegrityResult.MODIFIED,
                IntegrityResult.MISMATCHED,
                IntegrityResult.MISSING,
            }
        ):
            strategy = classification.read_strategy
            command = VerificationInvalidationCommand(
                item_id=candidate.item_id,
                row_id=identity.row_id,
                location_id=identity.location_id,
                rel_path_key=identity.rel_path_key,
                scope_token=identity.scope_token,
                expected_state=InventoryState.PRESENT,
                expected_stat=candidate.expected_stat,
                expected_baseline=candidate.copy_attestation,
                expected_invalidation=None,
                reason=_invalidation_reason(classification.result),
                invalidated_at=ctx.clock.now(),
            )
            return _record_post_copy_invalidation(
                candidate,
                classification.result,
                classification.reason,
                classification.detail,
                strategy,
                command,
                recorder,
                classification.bytes_read,
            )
        return _ProcessedItem(
            _post_copy_outcome(
                candidate,
                classification.result,
                classification.reason,
                classification.detail,
                read_strategy=classification.read_strategy,
                recording=(
                    RecordingStatus.OK
                    if identity is not None
                    else RecordingStatus.DEGRADED
                ),
            ),
            classification.bytes_read,
        )

    strategy = classification.read_strategy
    if strategy is None:
        raise RuntimeError("successful post-copy classification lacks a read strategy")
    if identity is None:
        return _ProcessedItem(
            _post_copy_outcome(
                candidate,
                classification.result,
                IntegrityReason.RECORDING_ERROR,
                "copy evidence was not durably recorded",
                read_strategy=strategy,
                recording=RecordingStatus.DEGRADED,
            ),
            classification.bytes_read,
        )

    command = IntegrityRecordCommand(
        mode=IntegrityMode.VERIFY,
        item_id=candidate.item_id,
        row_id=identity.row_id,
        location_id=identity.location_id,
        rel_path_key=identity.rel_path_key,
        scope_token=identity.scope_token,
        expected_state=InventoryState.PRESENT,
        expected_stat=candidate.expected_stat,
        expected_baseline=candidate.copy_attestation,
        attestation=classification.attestation,
        advances_last_verified=True,
        clear_reappeared=False,
        expected_invalidation=None,
    )
    return _record_post_copy_outcome(
        candidate,
        classification.result,
        strategy,
        command,
        recorder,
        classification.bytes_read,
    )


def _process_item(
    item: IntegritySelectionItem,
    mode: IntegrityMode,
    ctx: VerifierContext,
    recorder: IntegrityRecorder,
    reader: VerificationReader,
    reporter: _ProgressReporter,
) -> _ProcessedItem:
    try:
        validated_path = validate_relative_path(item.display_path)
        if normalize_relative_path(validated_path) != item.rel_path_key:
            raise ValueError("display path does not match the selected canonical key")
    except (OSError, ValueError) as exc:
        return _ProcessedItem(
            _outcome(
                item,
                mode,
                IntegrityResult.ERROR,
                IntegrityReason.PATH_INVALID,
                _error_detail(exc),
            )
        )
    try:
        _require_selected_root(item.root, ctx)
    except UnsupportedVerification as exc:
        return _ProcessedItem(
            _outcome(
                item,
                mode,
                IntegrityResult.UNSUPPORTED,
                IntegrityReason.UNSUPPORTED_READ,
                _error_detail(exc),
            )
        )

    if item.expected_state is InventoryState.MISSING:
        return _ProcessedItem(
            _outcome(
                item,
                mode,
                IntegrityResult.MISSING,
                IntegrityReason.INVENTORY_MISSING,
            )
        )
    if item.expected_state is InventoryState.UNSUPPORTED:
        return _ProcessedItem(
            _outcome(
                item,
                mode,
                IntegrityResult.UNSUPPORTED,
                IntegrityReason.INVENTORY_UNSUPPORTED,
            )
        )
    if mode is IntegrityMode.BASELINE and item.baseline is not None:
        return _ProcessedItem(
            _outcome(
                item,
                mode,
                IntegrityResult.ERROR,
                IntegrityReason.BASELINE_EXISTS,
            )
        )

    expected_stat = item.expected_stat
    if expected_stat is None:  # guarded by IntegritySelectionItem; defensive only
        return _ProcessedItem(
            _outcome(
                item, mode, IntegrityResult.ERROR, IntegrityReason.STAT_CHANGED
            )
        )

    classification = _classify_subject(
        root=item.root,
        relative_path=validated_path,
        expected_stat=expected_stat,
        baseline=item.baseline,
        mode=mode,
        ctx=ctx,
        reader=reader,
        on_bytes=lambda size: reporter.bytes_processed(
            size, item.display_path
        ),
        success_provenance=Provenance.VERIFY_ATTESTED,
    )
    if classification.attestation is None:
        if (
            item.baseline is not None
            and classification.result
            in {
                IntegrityResult.MODIFIED,
                IntegrityResult.MISMATCHED,
                IntegrityResult.MISSING,
            }
        ):
            strategy = classification.read_strategy
            command = VerificationInvalidationCommand(
                item_id=item.item_id,
                row_id=item.row_id,
                location_id=item.location_id,
                rel_path_key=item.rel_path_key,
                scope_token=item.scope_token,
                expected_state=item.expected_state,
                expected_stat=expected_stat,
                expected_baseline=item.baseline,
                expected_invalidation=item.invalidation,
                reason=_invalidation_reason(classification.result),
                invalidated_at=ctx.clock.now(),
            )
            return _record_invalidation_outcome(
                item,
                mode,
                classification.result,
                classification.reason,
                classification.detail,
                strategy,
                command,
                recorder,
                classification.bytes_read,
            )
        return _ProcessedItem(
            _outcome(
                item,
                mode,
                classification.result,
                classification.reason,
                classification.detail,
                read_strategy=classification.read_strategy,
            ),
            classification.bytes_read,
        )

    result = classification.result
    command_mode = (
        IntegrityMode.REBASELINE
        if mode is IntegrityMode.REBASELINE
        else (
            IntegrityMode.VERIFY
            if result is IntegrityResult.VERIFIED
            else IntegrityMode.BASELINE
        )
    )
    command = IntegrityRecordCommand(
        mode=command_mode,
        item_id=item.item_id,
        row_id=item.row_id,
        location_id=item.location_id,
        rel_path_key=item.rel_path_key,
        scope_token=item.scope_token,
        expected_state=item.expected_state,
        expected_stat=expected_stat,
        expected_baseline=item.baseline,
        attestation=classification.attestation,
        advances_last_verified=result is IntegrityResult.VERIFIED,
        clear_reappeared=item.reappeared_at is not None,
        expected_invalidation=item.invalidation,
    )
    strategy = classification.read_strategy
    if strategy is None:
        raise RuntimeError("successful integrity classification lacks a read strategy")
    return _record_outcome(
        item,
        mode,
        result,
        strategy,
        command,
        recorder,
        classification.bytes_read,
    )


def _classify_subject(
    *,
    root: Path,
    relative_path: str,
    expected_stat: FileStat,
    baseline: Attestation | None,
    mode: IntegrityMode,
    ctx: VerifierContext,
    reader: VerificationReader,
    on_bytes: Callable[[int], None],
    success_provenance: Provenance = Provenance.VERIFY_ATTESTED,
) -> _SubjectClassification:
    """Guard, hash, and classify bytes without ledger row identity or writes."""

    try:
        _admit_verification_root(root, ctx)
        with _open_reader(reader, root, relative_path, ctx) as stream:
            before = stream.stat()
            _require_reviewed_open_volume(before, ctx)
            if not _matches_expected_stat(expected_stat, before):
                return _SubjectClassification(
                    result=IntegrityResult.MODIFIED,
                    reason=IntegrityReason.STAT_CHANGED,
                    read_strategy=stream.strategy,
                )
            if (
                mode is IntegrityMode.VERIFY
                and baseline is not None
                and not _matches_expected_stat(baseline.subject, before)
            ):
                return _SubjectClassification(
                    result=IntegrityResult.MODIFIED,
                    reason=IntegrityReason.STAT_CHANGED,
                    read_strategy=stream.strategy,
                )

            digest = new_content_hasher(ctx.hasher_factory)
            bytes_read = 0
            for chunk in stream.iter_chunks(ctx.chunk_size):
                ctx.run.checkpoint()
                if not chunk:
                    continue
                update_content_hasher(digest, chunk)
                bytes_read += len(chunk)
                on_bytes(len(chunk))

            after = stream.stat()
            if not _same_open_subject(before, after):
                return _SubjectClassification(
                    result=IntegrityResult.MODIFIED,
                    reason=IntegrityReason.READ_DRIFT,
                    read_strategy=stream.strategy,
                    bytes_read=bytes_read,
                )
            if bytes_read != before.size:
                return _SubjectClassification(
                    result=IntegrityResult.ERROR,
                    reason=IntegrityReason.READ_ERROR,
                    detail=(
                        f"read {bytes_read} bytes from a "
                        f"{before.size}-byte subject"
                    ),
                    read_strategy=stream.strategy,
                    bytes_read=bytes_read,
                )

            actual_digest = finish_content_hasher(digest)
            if (
                mode is IntegrityMode.VERIFY
                and baseline is not None
                and actual_digest != baseline.content.digest
            ):
                return _SubjectClassification(
                    result=IntegrityResult.MISMATCHED,
                    reason=IntegrityReason.HASH_MISMATCH,
                    read_strategy=stream.strategy,
                    bytes_read=bytes_read,
                )

            observed_at = ctx.clock.now()
            content = ContentEvidence(
                algorithm="xxh3_128",
                digest=actual_digest,
                size=bytes_read,
                provenance=success_provenance,
                observed_at=observed_at,
            )
            subject = (
                after
                if expected_stat.file_identity is not None
                else replace(after, file_identity=None)
            )
            attestation = Attestation(content=content, subject=subject)
            result = (
                IntegrityResult.VERIFIED
                if mode is IntegrityMode.VERIFY and baseline is not None
                else IntegrityResult.BASELINED
            )
            return _SubjectClassification(
                result=result,
                read_strategy=stream.strategy,
                bytes_read=bytes_read,
                attestation=attestation,
            )
    except (Canceled, PauseRequested, HasherContractError):
        raise
    except FileNotFoundError as exc:
        return _SubjectClassification(
            result=IntegrityResult.MISSING,
            reason=IntegrityReason.NOT_FOUND,
            detail=_error_detail(exc),
        )
    except UnsupportedVerification as exc:
        return _SubjectClassification(
            result=IntegrityResult.UNSUPPORTED,
            reason=IntegrityReason.UNSUPPORTED_READ,
            detail=_error_detail(exc),
        )
    except OSError as exc:
        return _SubjectClassification(
            result=IntegrityResult.ERROR,
            reason=IntegrityReason.READ_ERROR,
            detail=_error_detail(exc),
        )


def _invalidation_reason(
    result: IntegrityResult,
) -> VerificationInvalidationReason:
    if result is IntegrityResult.MISMATCHED:
        return VerificationInvalidationReason.HASH_MISMATCH
    if result is IntegrityResult.MODIFIED:
        return VerificationInvalidationReason.METADATA_DRIFT
    if result is IntegrityResult.MISSING:
        return VerificationInvalidationReason.METADATA_DRIFT
    raise ValueError("only missing, modified, or mismatched results invalidate verification")


def _observe_recording(
    call: Callable[[], RecordDisposition | None],
) -> _RecordingObservation:
    try:
        disposition = call()
    except Exception as exc:
        return _RecordingObservation(error_detail=_error_detail(exc))
    return _RecordingObservation(disposition=disposition)


def _reduce_recording(
    observation: _RecordingObservation,
    *,
    reason: IntegrityReason | None,
    detail: str | None,
) -> _RecordingSettlement:
    """Reduce one recorder observation without performing I/O."""

    if observation.error_detail is not None:
        return _RecordingSettlement(
            IntegrityReason.RECORDING_ERROR,
            observation.error_detail,
            RecordingStatus.DEGRADED,
            None,
        )
    if observation.disposition in {
        RecordDisposition.STALE,
        RecordDisposition.CONFLICT,
    }:
        return _RecordingSettlement(
            (
                IntegrityReason.RECORDING_STALE
                if observation.disposition is RecordDisposition.STALE
                else IntegrityReason.RECORDING_CONFLICT
            ),
            None,
            RecordingStatus.DEGRADED,
            observation.disposition,
        )
    return _RecordingSettlement(
        reason,
        detail,
        RecordingStatus.OK,
        observation.disposition,
    )


def _record_invalidation_outcome(
    item: IntegritySelectionItem,
    mode: IntegrityMode,
    result: IntegrityResult,
    reason: IntegrityReason | None,
    detail: str | None,
    strategy: ReadStrategy | None,
    command: VerificationInvalidationCommand,
    recorder: IntegrityRecorder,
    bytes_read: int,
) -> _ProcessedItem:
    settlement = _reduce_recording(
        _observe_recording(
            lambda: recorder.record_verification_invalidation(command)
        ),
        reason=reason,
        detail=detail,
    )
    return _ProcessedItem(
        _outcome(
            item,
            mode,
            result,
            settlement.reason,
            settlement.detail,
            read_strategy=strategy,
            recording=settlement.recording,
            record_disposition=settlement.record_disposition,
        ),
        bytes_read,
    )


def _record_outcome(
    item: IntegritySelectionItem,
    mode: IntegrityMode,
    result: IntegrityResult,
    strategy: ReadStrategy,
    command: IntegrityRecordCommand,
    recorder: IntegrityRecorder,
    bytes_read: int,
) -> _ProcessedItem:
    settlement = _reduce_recording(
        _observe_recording(lambda: recorder.record_integrity(command)),
        reason=None,
        detail=None,
    )
    return _ProcessedItem(
        _outcome(
            item,
            mode,
            result,
            settlement.reason,
            settlement.detail,
            read_strategy=strategy,
            recording=settlement.recording,
            record_disposition=settlement.record_disposition,
        ),
        bytes_read,
    )


def _record_post_copy_outcome(
    candidate: PostCopyCandidate,
    result: IntegrityResult,
    strategy: ReadStrategy,
    command: IntegrityRecordCommand,
    recorder: IntegrityRecorder,
    bytes_read: int,
) -> _ProcessedItem:
    identity = candidate.recorded_identity
    if identity is None:  # guarded by the caller; defensive only
        raise RuntimeError("post-copy recording requires a durable identity")
    settlement = _reduce_recording(
        _observe_recording(lambda: recorder.record_integrity(command)),
        reason=None,
        detail=None,
    )
    return _ProcessedItem(
        _post_copy_outcome(
            candidate,
            result,
            settlement.reason,
            settlement.detail,
            read_strategy=strategy,
            recording=settlement.recording,
            record_disposition=settlement.record_disposition,
        ),
        bytes_read,
    )


def _record_post_copy_invalidation(
    candidate: PostCopyCandidate,
    result: IntegrityResult,
    reason: IntegrityReason | None,
    detail: str | None,
    strategy: ReadStrategy | None,
    command: VerificationInvalidationCommand,
    recorder: IntegrityRecorder,
    bytes_read: int,
) -> _ProcessedItem:
    settlement = _reduce_recording(
        _observe_recording(
            lambda: recorder.record_verification_invalidation(command)
        ),
        reason=reason,
        detail=detail,
    )
    return _ProcessedItem(
        _post_copy_outcome(
            candidate,
            result,
            settlement.reason,
            settlement.detail,
            read_strategy=strategy,
            recording=settlement.recording,
            record_disposition=settlement.record_disposition,
        ),
        bytes_read,
    )


def _outcome(
    item: IntegritySelectionItem,
    mode: IntegrityMode,
    result: IntegrityResult,
    reason: IntegrityReason | None = None,
    detail: str | None = None,
    *,
    read_strategy: ReadStrategy | None = None,
    recording: RecordingStatus = RecordingStatus.OK,
    record_disposition: RecordDisposition | None = None,
) -> IntegrityOutcome:
    return IntegrityOutcome(
        item_id=item.item_id,
        row_id=item.row_id,
        location_id=item.location_id,
        path=item.display_path,
        phase=mode.value,
        result=result,
        reason=reason,
        detail=detail,
        read_strategy=read_strategy,
        recording=recording,
        record_disposition=record_disposition,
    )


def _post_copy_outcome(
    candidate: PostCopyCandidate,
    result: IntegrityResult,
    reason: IntegrityReason | None = None,
    detail: str | None = None,
    *,
    read_strategy: ReadStrategy | None = None,
    recording: RecordingStatus = RecordingStatus.OK,
    record_disposition: RecordDisposition | None = None,
) -> IntegrityOutcome:
    identity = candidate.recorded_identity
    return IntegrityOutcome(
        item_id=candidate.item_id,
        row_id=None if identity is None else identity.row_id,
        location_id=None if identity is None else identity.location_id,
        path=candidate.display_path,
        phase=IntegrityMode.VERIFY.value,
        result=result,
        reason=reason,
        detail=detail,
        read_strategy=read_strategy,
        recording=recording,
        record_disposition=record_disposition,
    )


def _matches_expected_stat(expected: FileStat, actual: FileStat) -> bool:
    if expected.kind is not actual.kind:
        return False
    if expected.size != actual.size or expected.mtime_ns != actual.mtime_ns:
        return False
    return expected.file_identity is None or expected.file_identity == actual.file_identity


def _same_open_subject(before: FileStat, after: FileStat) -> bool:
    if before.kind is not after.kind:
        return False
    if before.size != after.size or before.mtime_ns != after.mtime_ns:
        return False
    if before.file_identity is None and after.file_identity is None:
        return True
    return before.file_identity == after.file_identity


def _error_detail(exc: BaseException) -> str:
    detail = logical_error_text(exc)
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


class WindowsUnbufferedReader:
    """Read one Windows file through ``FILE_FLAG_NO_BUFFERING``.

    There is deliberately no buffered fallback.  A filesystem, subject, or
    alignment condition that cannot honor the declared strategy produces
    ``UnsupportedVerification`` and can never be rendered as verified.
    """

    def __init__(self, root_authority: RootAuthority | None = None) -> None:
        self._root_authority = root_authority

    @contextmanager
    def open(self, root: Path, relative_path: str) -> Iterator[_WindowsStream]:
        with self._open_with_authority(
            root,
            relative_path,
            self._root_authority,
        ) as stream:
            yield stream

    @contextmanager
    def _open_with_authority(
        self,
        root: Path,
        relative_path: str,
        root_authority: RootAuthority | None,
    ) -> Iterator[_WindowsStream]:
        if os.name != "nt":
            raise UnsupportedVerification(
                "cache-honest verification is implemented only for Windows"
            )

        normalized = validate_relative_path(relative_path)
        root_path = Path(lexical_absolute_path(root))
        authority = root_authority or RootAuthority(str(root_path))
        if not _same_logical_path(str(root_path), authority.logical_root):
            raise UnsupportedVerification(
                "verification selection root does not match its reviewed root"
            )
        candidate = root_path.joinpath(*PureWindowsPath(normalized).parts)
        _reject_reparse_components(authority, normalized)

        api = _WindowsApi()
        sector_size = api.sector_size(candidate)
        handle = api.open_file(candidate)
        try:
            api.require_expected_final_path(root_path, normalized, handle)
            stream = _WindowsStream(api, handle, sector_size)
            stream.stat()  # reject directories/reparse points before yielding
            yield stream
        finally:
            api.close(handle)


def _reject_reparse_components(
    authority: RootAuthority,
    normalized_path: str,
) -> None:
    try:
        admit_root_chain(
            authority,
            lstat=_verification_lstat,
        )
    except RootAuthorityError as error:
        _raise_verification_root_admission(error)

    current = Path(authority.logical_root)
    for component in PureWindowsPath(normalized_path).parts:
        current = current / component
        observed = _verification_lstat(str(current))
        if is_placeholder_stat(observed) or is_reparse_stat(observed):
            raise UnsupportedVerification(
                f"verification refuses reparse component: {component}"
            )


def _verification_lstat(path: str) -> os.stat_result:
    return os.lstat(to_extended_length_path(path))


def _raise_verification_root_admission(error: RootAuthorityError) -> None:
    if error.issue is RootAuthorityIssue.COMPONENT_UNAVAILABLE:
        cause = error.__cause__
        if isinstance(cause, OSError):
            raise cause from error
    if error.issue in {
        RootAuthorityIssue.PLACEHOLDER_COMPONENT,
        RootAuthorityIssue.REPARSE_COMPONENT,
    }:
        raise UnsupportedVerification(
            "verification refuses a reparse location root chain"
        ) from error
    if error.issue is RootAuthorityIssue.NON_DIRECTORY_COMPONENT:
        raise UnsupportedVerification(
            "verification location root chain is not an ordinary directory"
        ) from error
    raise UnsupportedVerification(logical_error_text(error)) from error


def _same_logical_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(
        os.path.normpath(right)
    )


def _require_selected_root(
    root: Path,
    ctx: VerifierContext,
) -> RootAuthority | None:
    authority = ctx.root_authority
    if authority is None:
        return None
    try:
        selected = lexical_absolute_path(root)
    except (OSError, ValueError) as error:
        raise UnsupportedVerification(logical_error_text(error)) from error
    if not _same_logical_path(selected, authority.logical_root):
        raise UnsupportedVerification(
            "verification selection root does not match its reviewed root"
        )
    return authority


def _admit_verification_root(root: Path, ctx: VerifierContext) -> None:
    authority = _require_selected_root(root, ctx)
    if authority is None:
        return
    try:
        admit_root(authority)
    except RootAuthorityError as error:
        detail = {
            RootAuthorityIssue.ANCHOR_CHANGED: (
                "verification root volume anchor changed after review"
            ),
            RootAuthorityIssue.VOLUME_CHANGED: (
                "verification root volume identity changed after review"
            ),
            RootAuthorityIssue.PLACEHOLDER_COMPONENT: (
                "verification refuses a reparse location root chain"
            ),
            RootAuthorityIssue.REPARSE_COMPONENT: (
                "verification refuses a reparse location root chain"
            ),
            RootAuthorityIssue.NON_DIRECTORY_COMPONENT: (
                "verification location root chain is not an ordinary directory"
            ),
        }.get(error.issue, logical_error_text(error))
        raise UnsupportedVerification(detail) from error


def _require_reviewed_open_volume(
    opened: FileStat,
    ctx: VerifierContext,
) -> None:
    authority = ctx.root_authority
    expected = None if authority is None else authority.expected_volume_id
    identity = opened.file_identity
    if expected is None:
        return
    if identity is None:
        raise UnsupportedVerification(
            "opened verification subject has no volume identity"
        )
    if identity.volume_serial.casefold() != expected.serial.casefold():
        raise UnsupportedVerification(
            "opened verification subject is on a different volume"
        )


class _FileTime(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", ctypes.c_uint32),
        ("ftCreationTime", _FileTime),
        ("ftLastAccessTime", _FileTime),
        ("ftLastWriteTime", _FileTime),
        ("dwVolumeSerialNumber", ctypes.c_uint32),
        ("nFileSizeHigh", ctypes.c_uint32),
        ("nFileSizeLow", ctypes.c_uint32),
        ("nNumberOfLinks", ctypes.c_uint32),
        ("nFileIndexHigh", ctypes.c_uint32),
        ("nFileIndexLow", ctypes.c_uint32),
    ]


class _WindowsApi:
    def __init__(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32 = kernel32
        self._configure_signatures()

    def _configure_signatures(self) -> None:
        k32 = self._kernel32
        k32.CreateFileW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        k32.CreateFileW.restype = ctypes.c_void_p
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        k32.CloseHandle.restype = ctypes.c_int
        k32.GetFileInformationByHandle.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_ByHandleFileInformation),
        ]
        k32.GetFileInformationByHandle.restype = ctypes.c_int
        k32.ReadFile.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_void_p,
        ]
        k32.ReadFile.restype = ctypes.c_int
        k32.VirtualAlloc.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_uint32,
            ctypes.c_uint32,
        ]
        k32.VirtualAlloc.restype = ctypes.c_void_p
        k32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
        k32.VirtualFree.restype = ctypes.c_int
        k32.GetFinalPathNameByHandleW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
        ]
        k32.GetFinalPathNameByHandleW.restype = ctypes.c_uint32
        k32.GetVolumePathNameW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
        ]
        k32.GetVolumePathNameW.restype = ctypes.c_int
        k32.GetDiskFreeSpaceW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
        ]
        k32.GetDiskFreeSpaceW.restype = ctypes.c_int

    def open_file(self, path: Path) -> int:
        handle = self._kernel32.CreateFileW(
            _extended_path(path),
            _GENERIC_READ,
            # Keep the attested path bound to this subject for the whole read.
            # Existing or new writers/deleters must not be able to replace the
            # selected name while this handle still refers to the old file.
            _FILE_SHARE_READ,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_NO_BUFFERING
            | _FILE_FLAG_SEQUENTIAL_SCAN
            | _FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        if handle == ctypes.c_void_p(-1).value:
            self._raise_open_error(path)
        return handle

    def open_directory(self, path: Path) -> int:
        handle = self._kernel32.CreateFileW(
            _extended_path(path),
            0,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if handle == ctypes.c_void_p(-1).value:
            self._raise_open_error(path)
        return handle

    def _raise_open_error(self, path: Path) -> None:
        error = ctypes.get_last_error()
        if error in (_ERROR_FILE_NOT_FOUND, _ERROR_PATH_NOT_FOUND):
            raise FileNotFoundError(error, os.strerror(error), str(path))
        if error == _ERROR_ACCESS_DENIED:
            raise PermissionError(error, os.strerror(error), str(path))
        raise OSError(error, os.strerror(error), str(path))

    def close(self, handle: int) -> None:
        self._kernel32.CloseHandle(handle)

    def stat(self, handle: int) -> FileStat:
        info = _ByHandleFileInformation()
        if not self._kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            error = ctypes.get_last_error()
            raise OSError(error, os.strerror(error))
        if info.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            raise UnsupportedVerification("verification refuses a reparse subject")
        if info.dwFileAttributes & _FILE_ATTRIBUTE_DIRECTORY:
            raise UnsupportedVerification("verification selections must name files")

        size = (info.nFileSizeHigh << 32) | info.nFileSizeLow
        file_index = (info.nFileIndexHigh << 32) | info.nFileIndexLow
        identity = FileIdentity(
            volume_serial=f"{info.dwVolumeSerialNumber:08X}",
            file_index=file_index,
        )
        return FileStat(
            kind=EntryKind.FILE,
            size=size,
            mtime_ns=_filetime_to_unix_ns(info.ftLastWriteTime),
            file_identity=identity,
            nlink=info.nNumberOfLinks,
            metadata=MetadataSnapshot(
                attributes=info.dwFileAttributes,
                created_ns=_filetime_to_unix_ns(info.ftCreationTime),
            ),
        )

    def sector_size(self, path: Path) -> int:
        volume_buffer = ctypes.create_unicode_buffer(32768)
        if not self._kernel32.GetVolumePathNameW(
            _extended_path(path), volume_buffer, len(volume_buffer)
        ):
            error = ctypes.get_last_error()
            raise UnsupportedVerification(
                f"cannot identify the verification volume (Windows error {error})"
            )
        sectors_per_cluster = ctypes.c_uint32()
        bytes_per_sector = ctypes.c_uint32()
        free_clusters = ctypes.c_uint32()
        total_clusters = ctypes.c_uint32()
        if not self._kernel32.GetDiskFreeSpaceW(
            volume_buffer.value,
            ctypes.byref(sectors_per_cluster),
            ctypes.byref(bytes_per_sector),
            ctypes.byref(free_clusters),
            ctypes.byref(total_clusters),
        ):
            error = ctypes.get_last_error()
            raise UnsupportedVerification(
                f"cannot determine unbuffered-read alignment (Windows error {error})"
            )
        if bytes_per_sector.value <= 0:
            raise UnsupportedVerification("volume reported an invalid sector size")
        return bytes_per_sector.value

    def require_expected_final_path(
        self, root: Path, relative_path: str, file_handle: int
    ) -> None:
        root_handle = self.open_directory(root)
        try:
            root_final = self.final_path(root_handle).rstrip("\\/")
        finally:
            self.close(root_handle)
        expected = root_final + "\\" + relative_path
        actual = self.final_path(file_handle)
        if ntpath.normcase(expected) != ntpath.normcase(actual):
            raise UnsupportedVerification(
                "the opened handle does not resolve to the selected root-relative path"
            )

    def final_path(self, handle: int) -> str:
        size = 512
        while True:
            buffer = ctypes.create_unicode_buffer(size)
            length = self._kernel32.GetFinalPathNameByHandleW(handle, buffer, size, 0)
            if length == 0:
                error = ctypes.get_last_error()
                raise OSError(error, os.strerror(error))
            if length < size:
                return buffer.value
            size = length + 1

    def read(self, handle: int, address: int, size: int) -> int:
        bytes_read = ctypes.c_uint32()
        if not self._kernel32.ReadFile(
            handle, address, size, ctypes.byref(bytes_read), None
        ):
            error = ctypes.get_last_error()
            if error == _ERROR_INVALID_PARAMETER:
                raise UnsupportedVerification(
                    "the volume rejected an aligned unbuffered read"
                )
            raise OSError(error, os.strerror(error))
        return bytes_read.value

    def allocate(self, size: int) -> int:
        address = self._kernel32.VirtualAlloc(
            None, size, _MEM_COMMIT | _MEM_RESERVE, _PAGE_READWRITE
        )
        if not address:
            error = ctypes.get_last_error()
            raise OSError(error, os.strerror(error))
        return address

    def release(self, address: int) -> None:
        if not self._kernel32.VirtualFree(address, 0, _MEM_RELEASE):
            error = ctypes.get_last_error()
            raise OSError(error, os.strerror(error))


class _WindowsStream:
    strategy = ReadStrategy.WINDOWS_UNBUFFERED

    def __init__(self, api: _WindowsApi, handle: int, sector_size: int) -> None:
        self._api = api
        self._handle = handle
        self._sector_size = sector_size

    def stat(self) -> FileStat:
        return self._api.stat(self._handle)

    def iter_chunks(self, chunk_size: int) -> Iterator[bytes]:
        subject_size = self.stat().size
        if subject_size == 0:
            return
        aligned_size = _align_up(chunk_size, self._sector_size)
        address = self._api.allocate(aligned_size)
        total = 0
        try:
            while total < subject_size:
                count = self._api.read(self._handle, address, aligned_size)
                if count == 0:
                    break
                total += count
                yield ctypes.string_at(address, count)
        finally:
            self._api.release(address)


def _align_up(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _filetime_to_unix_ns(value: _FileTime) -> int:
    ticks = (value.dwHighDateTime << 32) | value.dwLowDateTime
    return (ticks - _WINDOWS_EPOCH_TICKS) * 100


def _extended_path(path: Path) -> str:
    return to_extended_length_path(str(path))
