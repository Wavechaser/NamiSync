"""Cache-honest baseline and integrity verification.

The verifier owns classification and hashing only.  Inventory refresh, ledger
transactions, session terminals, and audit persistence remain injected through
core protocols and the workflow/dispatcher layers.
"""

from __future__ import annotations

import os
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Literal
from uuid import uuid4

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
    AuthorityBoundVerificationReader,
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
    matches_expected_stat,
)
from namisync.core.models import FileStat
from namisync.core.pathing import (
    fold_validated_path,
    lexical_absolute_path,
    logical_error_text,
    validate_relative_path,
)
from namisync.core.session import Canceled, PauseRequested
from namisync.core.root_authority import (
    RootAuthority,
    RootAuthorityError,
    RootAuthorityIssue,
    admit_root,
)
from namisync.core.scalars import (
    checked_add_signed_64,
    require_safe_int,
    require_signed_64,
)

from .native import WindowsUnbufferedReader


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
    if ctx.root_authority is None and isinstance(
        reader, AuthorityBoundVerificationReader
    ):
        raise ValueError(
            "the authority-bound verification reader requires root authority"
        )
    return reader


def _open_reader(
    reader: VerificationReader,
    root: Path,
    relative_path: str,
    ctx: VerifierContext,
) -> AbstractContextManager:
    if isinstance(reader, AuthorityBoundVerificationReader):
        authority = ctx.root_authority
        if authority is None:
            raise ValueError(
                "the authority-bound verification reader requires root authority"
            )
        return reader.open_with_authority(
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

    emitted: list[IntegrityOutcome] = []
    items_total = (
        len(selection.candidates)
        if ctx.post_copy_items_total is None
        else ctx.post_copy_items_total
    )
    bytes_total = (
        selection.physical_bytes_total()
        if ctx.post_copy_bytes_total is None
        else ctx.post_copy_bytes_total
    )
    reporter = _ProgressReporter(
        selection,
        ctx,
        items_total=items_total,
        pending_sizes=tuple(
            candidate.expected_stat.size for candidate in selection.pending
        ),
        phase=IntegrityMode.VERIFY.value,
        item_type="operation",
        bytes_total=bytes_total,
    )

    try:
        actual_reader = _reader_for_context(ctx, reader)
        for candidate in selection.pending:
            ctx.run.checkpoint()
            reporter.item_started(candidate.item_id, candidate.display_path)
            processed = _process_post_copy_candidate(
                candidate, ctx, recorder, actual_reader, reporter
            )
            _emit_and_complete_post_copy(
                selection, ctx, reporter, processed, emitted
            )
    except PauseRequested:
        reporter.pause_completed()
        raise
    except Canceled:
        try:
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
            reporter.cancellation_completed()
        except Exception as error:
            reporter.failure_completed(error)
            raise
        raise
    except Exception as error:
        reporter.failure_completed(error)
        raise

    reporter.run_completed()
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
        phase: str,
        item_type: Literal["integrity", "operation"],
        bytes_total: int | None = None,
    ) -> None:
        self._selection = selection
        self._ctx = ctx
        self._items_total = require_safe_int(
            items_total,
            "verifier items_total",
        )
        self._last_emitted_at: float | None = None
        candidate_bytes_total = selection.processed_bytes
        for size in pending_sizes:
            candidate_bytes_total = checked_add_signed_64(
                candidate_bytes_total,
                size,
                "verifier admitted bytes",
            )
        if bytes_total is not None:
            require_signed_64(bytes_total, "post-copy progress byte budget")
        if bytes_total is not None and bytes_total < candidate_bytes_total:
            raise ValueError(
                "post-copy progress byte budget cannot exclude candidate work"
            )
        self._live_bytes_total = (
            candidate_bytes_total if bytes_total is None else bytes_total
        )
        if isinstance(selection, IntegritySelection):
            selection.advance_bytes_total_high_water(self._live_bytes_total)
            self._bytes_total = selection.bytes_total_high_water
        else:
            self._bytes_total = self._live_bytes_total
        self._phase = phase
        self._item_type = item_type
        self._selected_item_ids = selection.known_item_ids
        if self._items_total < len(self._selected_item_ids):
            raise ValueError(
                "progress item admission cannot exclude selected verifier items"
            )
        self._outcome_item_ids = set(selection.completed_bytes)
        self._items_done = require_safe_int(
            len(self._outcome_item_ids),
            "verifier items_done",
        )
        self._item_id: str | None = None
        self._item_attempt_id: str | None = None
        self._current_path: str | None = None
        self._item_bytes_done: int | None = None
        self._item_bytes_total: int | None = None
        self._item_settled_bytes: int | None = None
        self.emit(force=True)

    def item_started(self, item_id: str, current_path: str) -> None:
        if self._item_id is not None:
            raise RuntimeError("integrity progress item is already active")
        self._item_id = item_id
        self._current_path = current_path
        self.emit(force=False)

    def stream_started(self, size: int) -> None:
        if self._item_id is None:
            raise RuntimeError("integrity byte stream has no active item")
        if self._item_bytes_done is not None:
            raise RuntimeError("integrity byte stream is already active")
        require_signed_64(size, "verifier item byte total")
        self._item_attempt_id = uuid4().hex
        self._item_bytes_done = 0
        self._item_bytes_total = size
        self.emit(force=False)

    def bytes_processed(self, size: int) -> None:
        if (
            self._item_id is None
            or self._item_bytes_done is None
            or self._item_bytes_total is None
        ):
            raise RuntimeError("integrity bytes arrived outside an active stream")
        self._selection.note_bytes_processed(size)
        previous_overrun = max(
            0, self._item_bytes_done - self._item_bytes_total
        )
        self._item_bytes_done = checked_add_signed_64(
            self._item_bytes_done,
            size,
            "verifier item bytes_done",
        )
        current_overrun = max(
            0, self._item_bytes_done - self._item_bytes_total
        )
        self._advance_bytes_total(current_overrun - previous_overrun)
        self.emit(force=False)

    def item_completed(self, item_id: str) -> None:
        if self._item_id != item_id:
            raise RuntimeError("integrity settlement does not match the active item")
        if item_id not in self._outcome_item_ids:
            raise RuntimeError("integrity settlement lacks a reliable item outcome")
        self._close_active_attempt_budget()
        self._clear_item()
        self.emit(force=False)

    def item_settlement_recorded(self, item_id: str, bytes_read: int) -> None:
        if self._item_id != item_id:
            return
        require_signed_64(bytes_read, "settled verifier bytes")
        self._item_settled_bytes = bytes_read

    def item_outcome_emitted(self, item_id: str) -> None:
        if item_id not in self._selected_item_ids:
            raise RuntimeError("integrity outcome does not name a selected item")
        if item_id in self._outcome_item_ids:
            raise RuntimeError("integrity item outcome was emitted more than once")
        self._outcome_item_ids.add(item_id)
        self._items_done = require_safe_int(
            self._items_done + 1,
            "verifier items_done",
        )

    def run_completed(self) -> None:
        if self._item_id is not None:
            raise RuntimeError("integrity run completed with an active item")
        self.emit(force=True)

    def cancellation_completed(self) -> None:
        self._close_active_attempt_budget()
        self._clear_item()
        self._current_path = None
        self.emit(force=True)

    def pause_completed(self) -> None:
        self._close_active_attempt_budget()
        self.emit(force=True)

    def failure_completed(self, error: Exception) -> None:
        self._close_active_attempt_budget()
        self._clear_item()
        self._current_path = None
        try:
            self.emit(force=True)
        except Exception as progress_error:
            error.add_note(
                "verifier terminal progress emission also failed: "
                f"{logical_error_text(progress_error)}"
            )

    def _close_active_attempt_budget(self) -> None:
        if (
            self._item_id is None
            or self._item_bytes_done is None
            or self._item_bytes_total is None
        ):
            return
        admitted_work = min(self._item_bytes_done, self._item_bytes_total)
        settled_work = min(
            0 if self._item_settled_bytes is None else self._item_settled_bytes,
            self._item_bytes_total,
        )
        self._advance_bytes_total(max(0, admitted_work - settled_work))

    def _advance_bytes_total(self, amount: int) -> None:
        self._live_bytes_total = checked_add_signed_64(
            self._live_bytes_total,
            amount,
            "verifier bytes_total",
        )
        if isinstance(self._selection, IntegritySelection):
            self._selection.advance_bytes_total_high_water(
                self._live_bytes_total
            )
            self._bytes_total = self._selection.bytes_total_high_water
        else:
            self._bytes_total = self._live_bytes_total

    def _clear_item(self) -> None:
        self._item_id = None
        self._item_attempt_id = None
        self._item_bytes_done = None
        self._item_bytes_total = None
        self._item_settled_bytes = None

    def emit(self, *, force: bool) -> None:
        now = self._ctx.monotonic()
        if not force and self._last_emitted_at is not None:
            if now - self._last_emitted_at < self._ctx.progress_interval_seconds:
                return
        item_bytes_done = self._item_bytes_done
        item_bytes_total = self._item_bytes_total
        if (
            item_bytes_done is not None
            and item_bytes_total is not None
            and item_bytes_done > item_bytes_total
        ):
            item_bytes_done = None
            item_bytes_total = None
        self._ctx.run.emit(
            Progress(
                phase=self._phase,
                items_done=self._items_done,
                items_total=self._items_total,
                bytes_done=self._selection.processed_bytes,
                bytes_total=self._bytes_total,
                current_path=self._current_path,
                item_id=self._item_id,
                item_type=None if self._item_id is None else self._item_type,
                item_attempt_id=self._item_attempt_id,
                item_bytes_done=item_bytes_done,
                item_bytes_total=item_bytes_total,
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
    if ctx.post_copy_items_total is not None:
        raise ValueError(
            "post-copy progress admission cannot be used for standalone verification"
        )
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
        phase=mode.value,
        item_type="integrity",
    )

    try:
        actual_reader = _reader_for_context(ctx, reader)
        for item in selection.pending:
            ctx.run.checkpoint()
            reporter.item_started(item.item_id, item.display_path)
            processed = _process_item(
                item, mode, ctx, recorder, actual_reader, reporter
            )
            _emit_and_complete(selection, ctx, reporter, processed, emitted)
    except PauseRequested:
        # Pending and in-flight items stay pending.  Their reliable outcomes are
        # emitted only when a resumed pass actually settles them.
        reporter.pause_completed()
        raise
    except Canceled:
        # The runner aggregates reliable events and cannot inspect module state.
        # Complete every still-pending row before the payload-free unwind leaves.
        try:
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
                    selection,
                    ctx,
                    reporter,
                    processed,
                    emitted,
                    emit_progress=False,
                )
            reporter.cancellation_completed()
        except Exception as error:
            reporter.failure_completed(error)
            raise
        raise
    except Exception as error:
        reporter.failure_completed(error)
        raise

    reporter.run_completed()
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
    reporter.item_outcome_emitted(processed.outcome.item_id)
    selection.mark_completed(processed.outcome.item_id, processed.bytes_read)
    reporter.item_settlement_recorded(
        processed.outcome.item_id, processed.bytes_read
    )
    emitted.append(processed.outcome)
    if emit_progress:
        reporter.item_completed(processed.outcome.item_id)


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
    reporter.item_outcome_emitted(processed.outcome.item_id)
    selection.mark_completed(processed.outcome.item_id, processed.bytes_read)
    reporter.item_settlement_recorded(
        processed.outcome.item_id, processed.bytes_read
    )
    emitted.append(processed.outcome)
    if emit_progress:
        reporter.item_completed(processed.outcome.item_id)


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
        on_stream_start=reporter.stream_started,
        on_bytes=reporter.bytes_processed,
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
        if fold_validated_path(validated_path) != item.rel_path_key:
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
        on_stream_start=reporter.stream_started,
        on_bytes=reporter.bytes_processed,
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
    on_stream_start: Callable[[int], None],
    on_bytes: Callable[[int], None],
    success_provenance: Provenance = Provenance.VERIFY_ATTESTED,
) -> _SubjectClassification:
    """Guard, hash, and classify bytes without ledger row identity or writes."""

    try:
        _admit_verification_root(root, ctx)
        with _open_reader(reader, root, relative_path, ctx) as stream:
            before = stream.stat()
            _require_reviewed_open_volume(before, ctx)
            if not matches_expected_stat(expected_stat, before):
                return _SubjectClassification(
                    result=IntegrityResult.MODIFIED,
                    reason=IntegrityReason.STAT_CHANGED,
                    read_strategy=stream.strategy,
                )
            if (
                mode is IntegrityMode.VERIFY
                and baseline is not None
                and not matches_expected_stat(baseline.subject, before)
            ):
                return _SubjectClassification(
                    result=IntegrityResult.MODIFIED,
                    reason=IntegrityReason.STAT_CHANGED,
                    read_strategy=stream.strategy,
                )

            digest = new_content_hasher(ctx.hasher_factory)
            on_stream_start(before.size)
            bytes_read = 0
            for chunk in stream.iter_chunks(ctx.chunk_size):
                ctx.run.checkpoint()
                if not chunk:
                    continue
                update_content_hasher(digest, chunk)
                bytes_read = checked_add_signed_64(
                    bytes_read,
                    len(chunk),
                    "verified bytes",
                )
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


def _same_logical_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(
        os.path.normpath(right)
    )


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
