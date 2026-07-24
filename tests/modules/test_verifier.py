"""Verifier classification, continuation, and cache-honesty tests."""

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

import pytest
from xxhash import xxh3_128

import namisync.modules.verifier as verifier_module
from namisync.core.evidence import (
    Attestation,
    ContentEvidence,
    HasherContractError,
    HasherFactory,
    Provenance,
    RecordingStatus,
)
from namisync.core.events import Progress
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityOutcome,
    IntegrityReason,
    IntegrityRecordCommand,
    IntegrityResult,
    IntegritySelection,
    IntegritySelectionItem,
    InventoryState,
    ReadStrategy,
    RecordDisposition,
    UnsupportedVerification,
    VerifierContext,
)
from namisync.core.models import EntryKind, FileIdentity, FileStat, MetadataSnapshot
from namisync.core.pathing import normalize_relative_path, validate_relative_path
from namisync.core.session import (
    Canceled,
    OperationResult,
    PauseRequested,
    RunContext,
    SessionState,
    run_session,
)
from namisync.modules.verifier import (
    WindowsUnbufferedReader,
    baseline,
    rebaseline,
    verify,
)


_NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return _NOW


@dataclass(frozen=True)
class _StreamSpec:
    before: FileStat
    chunks: tuple[bytes, ...]
    after: FileStat | None = None


class _FakeStream:
    strategy = ReadStrategy.WINDOWS_UNBUFFERED

    def __init__(self, spec: _StreamSpec) -> None:
        self._spec = spec
        self._stat_calls = 0

    def stat(self) -> FileStat:
        self._stat_calls += 1
        if self._stat_calls == 1 or self._spec.after is None:
            return self._spec.before
        return self._spec.after

    def iter_chunks(self, chunk_size: int) -> Iterator[bytes]:
        assert chunk_size > 0
        yield from self._spec.chunks


class _FakeReader:
    def __init__(self, entries: dict[str, _StreamSpec | BaseException]) -> None:
        self.entries = {
            validate_relative_path(path): entry for path, entry in entries.items()
        }
        self.opened: list[tuple[Path, str]] = []

    @contextmanager
    def open(self, root: Path, relative_path: str) -> Iterator[_FakeStream]:
        self.opened.append((root, relative_path))
        entry = self.entries[relative_path]
        if isinstance(entry, BaseException):
            raise entry
        yield _FakeStream(entry)


class _Recorder:
    def __init__(
        self,
        disposition: RecordDisposition = RecordDisposition.APPLIED,
        error: Exception | None = None,
    ) -> None:
        self.disposition = disposition
        self.error = error
        self.commands: list[IntegrityRecordCommand] = []

    def record_integrity(self, command: IntegrityRecordCommand) -> RecordDisposition:
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return self.disposition


def _stat(
    *,
    size: int = 3,
    mtime_ns: int = 100,
    identity: FileIdentity | None = FileIdentity("A1B2C3D4", 7),
) -> FileStat:
    return FileStat(
        kind=EntryKind.FILE,
        size=size,
        mtime_ns=mtime_ns,
        file_identity=identity,
        nlink=1,
        metadata=MetadataSnapshot(attributes=0, created_ns=50),
    )


def _attestation(
    data: bytes,
    subject: FileStat,
    provenance: Provenance = Provenance.VERIFY_ATTESTED,
) -> Attestation:
    return Attestation(
        content=ContentEvidence(
            algorithm="xxh3_128",
            digest=xxh3_128(data).digest(),
            size=len(data),
            provenance=provenance,
            observed_at=_NOW,
        ),
        subject=subject,
    )


def _item(
    root: Path,
    *,
    number: int = 1,
    path: str | None = None,
    location_id: str = "location-1",
    expected_state: InventoryState = InventoryState.PRESENT,
    expected_stat: FileStat | None = None,
    baseline_evidence: Attestation | None | object = ...,
    reappeared: bool = False,
) -> IntegritySelectionItem:
    display_path = path or f"Folder\\file-{number}.bin"
    stat = expected_stat or _stat()
    if baseline_evidence is ...:
        baseline_evidence = _attestation(b"abc", stat)
    return IntegritySelectionItem(
        item_id=f"item-{number}",
        row_id=f"row-{number}",
        location_id=location_id,
        root=root,
        rel_path_key=normalize_relative_path(display_path),
        display_path=display_path,
        expected_state=expected_state,
        expected_stat=stat if expected_state is InventoryState.PRESENT else None,
        baseline=baseline_evidence,
        scope_token="scope-1",
        reappeared_at=_NOW if reappeared else None,
    )


def _context(
    events: list[object],
    checkpoint=lambda: None,
    monotonic=lambda: 0.0,
    hasher_factory: HasherFactory = xxh3_128,
) -> VerifierContext:
    return VerifierContext(
        run=RunContext(emit=events.append, checkpoint=checkpoint),
        clock=_Clock(),
        hasher_factory=hasher_factory,
        monotonic=monotonic,
        chunk_size=1,
        progress_interval_seconds=0.1,
    )


def _integrity_events(events: list[object]) -> list[IntegrityOutcome]:
    return [event for event in events if isinstance(event, IntegrityOutcome)]


def test_xxh3_128_digest_encoding_is_raw_canonical_big_endian() -> None:
    hasher = xxh3_128()

    assert hasher.digest().hex() == "99aa06d3014798d86001c324468d497f"
    assert hasher.digest() == hasher.intdigest().to_bytes(16, "big")


@pytest.mark.parametrize(
    ("live_stat", "content", "expected_result"),
    [
        (_stat(size=4), b"abcd", IntegrityResult.MODIFIED),
        (_stat(mtime_ns=101), b"abc", IntegrityResult.MODIFIED),
        (
            _stat(identity=FileIdentity("A1B2C3D4", 8)),
            b"abc",
            IntegrityResult.MODIFIED,
        ),
        (_stat(), b"abd", IntegrityResult.MISMATCHED),
        (_stat(), b"abc", IntegrityResult.VERIFIED),
    ],
)
def test_verify_classifies_stat_drift_before_digest_mismatch(
    tmp_path: Path,
    live_stat: FileStat,
    content: bytes,
    expected_result: IntegrityResult,
) -> None:
    item = _item(tmp_path)
    selection = IntegritySelection((item,))
    reader = _FakeReader(
        {item.display_path: _StreamSpec(live_stat, (content,), live_stat)}
    )
    recorder = _Recorder()
    events: list[object] = []

    result = verify(selection, _context(events), recorder, reader)

    assert result.outcomes[0].result is expected_result
    assert len(_integrity_events(events)) == 1
    assert len(recorder.commands) == (1 if expected_result is IntegrityResult.VERIFIED else 0)


def test_valid_different_xxh3_digest_remains_a_hash_mismatch(tmp_path: Path) -> None:
    item = _item(tmp_path)
    recorder = _Recorder()

    result = verify(
        IntegritySelection((item,)),
        _context([]),
        recorder,
        _FakeReader(
            {item.display_path: _StreamSpec(item.expected_stat, (b"abd",))}  # type: ignore[arg-type]
        ),
    )

    assert result.outcomes[0].result is IntegrityResult.MISMATCHED
    assert result.outcomes[0].reason is IntegrityReason.HASH_MISMATCH
    assert recorder.commands == []


def test_wrong_length_hasher_digest_raises_contract_error_before_comparison(
    tmp_path: Path,
) -> None:
    class WrongLengthHasher:
        def update(self, data: bytes) -> None:
            del data

        def digest(self) -> bytes:
            return b"x" * 15

    item = _item(tmp_path)
    recorder = _Recorder()
    events: list[object] = []

    with pytest.raises(HasherContractError, match="exactly 16 bytes"):
        verify(
            IntegritySelection((item,)),
            _context(events, hasher_factory=WrongLengthHasher),
            recorder,
            _FakeReader(
                {item.display_path: _StreamSpec(item.expected_stat, (b"xyz",))}  # type: ignore[arg-type]
            ),
        )

    assert _integrity_events(events) == []
    assert recorder.commands == []


@pytest.mark.parametrize(
    ("mode", "runner", "baseline_evidence"),
    [
        (IntegrityMode.BASELINE, baseline, None),
        (IntegrityMode.VERIFY, verify, ...),
        (IntegrityMode.REBASELINE, rebaseline, ...),
    ],
)
def test_outcomes_carry_the_active_integrity_phase(
    tmp_path: Path,
    mode: IntegrityMode,
    runner,
    baseline_evidence: Attestation | None | object,
) -> None:
    item = _item(tmp_path, baseline_evidence=baseline_evidence)

    result = runner(
        IntegritySelection((item,)),
        _context([]),
        _Recorder(),
        _FakeReader(
            {item.display_path: _StreamSpec(item.expected_stat, (b"abc",))}  # type: ignore[arg-type]
        ),
    )

    assert result.outcomes[0].phase == mode.value


def test_private_classifier_needs_no_ledger_identity_or_recorder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _stat(size=8)
    path = "detached.bin"
    progress: list[int] = []

    def forbidden_command(*_args, **_kwargs):
        raise AssertionError("ledger command construction is not classification")

    monkeypatch.setattr(
        verifier_module, "IntegrityRecordCommand", forbidden_command
    )
    classification = verifier_module._classify_subject(
        root=tmp_path,
        relative_path=path,
        expected_stat=expected,
        baseline=None,
        mode=IntegrityMode.BASELINE,
        ctx=_context([]),
        reader=_FakeReader(
            {path: _StreamSpec(expected, (b"detached",), expected)}
        ),
        on_bytes=progress.append,
    )

    assert classification.result is IntegrityResult.BASELINED
    assert classification.reason is None
    assert classification.bytes_read == 8
    assert classification.read_strategy is ReadStrategy.WINDOWS_UNBUFFERED
    assert classification.attestation is not None
    assert (
        classification.attestation.content.digest
        == xxh3_128(b"detached").digest()
    )
    assert progress == [8]


def test_null_hash_verify_baselines_with_verify_provenance_atomically(
    tmp_path: Path,
) -> None:
    item = _item(tmp_path, baseline_evidence=None, reappeared=True)
    reader = _FakeReader(
        {item.display_path: _StreamSpec(item.expected_stat, (b"abc",))}  # type: ignore[arg-type]
    )
    recorder = _Recorder()

    result = verify(IntegritySelection((item,)), _context([]), recorder, reader)

    assert result.outcomes[0].result is IntegrityResult.BASELINED
    command = recorder.commands[0]
    assert command.mode is IntegrityMode.BASELINE
    assert command.attestation.content.provenance is Provenance.VERIFY_ATTESTED
    assert command.advances_last_verified is False
    assert command.clear_reappeared is True


def test_copy_evidence_advances_verification_only_after_independent_read(
    tmp_path: Path,
) -> None:
    stat = _stat()
    item = _item(
        tmp_path,
        expected_stat=stat,
        baseline_evidence=_attestation(b"abc", stat, Provenance.COPY_ATTESTED),
    )
    recorder = _Recorder()

    verify(
        IntegritySelection((item,)),
        _context([]),
        recorder,
        _FakeReader({item.display_path: _StreamSpec(stat, (b"abc",))}),
    )

    command = recorder.commands[0]
    assert command.expected_baseline.content.provenance is Provenance.COPY_ATTESTED
    assert command.attestation.content.provenance is Provenance.VERIFY_ATTESTED
    assert command.advances_last_verified is True


def test_untrusted_filesystem_identity_is_not_promoted_from_reader_handle(
    tmp_path: Path,
) -> None:
    expected = _stat(identity=None)
    handle_stat = _stat(identity=FileIdentity("A1B2C3D4", 99))
    item = _item(
        tmp_path,
        expected_stat=expected,
        baseline_evidence=_attestation(b"abc", expected),
    )
    recorder = _Recorder()

    result = verify(
        IntegritySelection((item,)),
        _context([]),
        recorder,
        _FakeReader({item.display_path: _StreamSpec(handle_stat, (b"abc",))}),
    )

    assert result.outcomes[0].result is IntegrityResult.VERIFIED
    assert recorder.commands[0].attestation.subject.file_identity is None


def test_baseline_refuses_to_overwrite_established_evidence(tmp_path: Path) -> None:
    item = _item(tmp_path)
    reader = _FakeReader({})
    recorder = _Recorder()

    result = baseline(IntegritySelection((item,)), _context([]), recorder, reader)

    assert result.outcomes[0].result is IntegrityResult.ERROR
    assert result.outcomes[0].reason is IntegrityReason.BASELINE_EXISTS
    assert reader.opened == []
    assert recorder.commands == []


def test_rebaseline_accepts_fresh_current_stat_without_calling_it_verified(
    tmp_path: Path,
) -> None:
    old_stat = _stat(mtime_ns=100)
    current_stat = _stat(mtime_ns=200)
    item = _item(
        tmp_path,
        expected_stat=current_stat,
        baseline_evidence=_attestation(b"old", old_stat),
        reappeared=True,
    )
    recorder = _Recorder()

    result = rebaseline(
        IntegritySelection((item,)),
        _context([]),
        recorder,
        _FakeReader({item.display_path: _StreamSpec(current_stat, (b"new",))}),
    )

    assert result.outcomes[0].result is IntegrityResult.BASELINED
    command = recorder.commands[0]
    assert command.mode is IntegrityMode.REBASELINE
    assert command.expected_baseline.content.digest == xxh3_128(b"old").digest()
    assert command.advances_last_verified is False
    assert command.clear_reappeared is True


@pytest.mark.parametrize(
    ("entry", "expected", "reason"),
    [
        (FileNotFoundError("gone"), IntegrityResult.MISSING, IntegrityReason.NOT_FOUND),
        (
            UnsupportedVerification("no honest strategy"),
            IntegrityResult.UNSUPPORTED,
            IntegrityReason.UNSUPPORTED_READ,
        ),
        (OSError("read failed"), IntegrityResult.ERROR, IntegrityReason.READ_ERROR),
    ],
)
def test_missing_unsupported_and_read_errors_emit_once_without_writes(
    tmp_path: Path,
    entry: BaseException,
    expected: IntegrityResult,
    reason: IntegrityReason,
) -> None:
    item = _item(tmp_path)
    recorder = _Recorder()
    events: list[object] = []

    result = verify(
        IntegritySelection((item,)),
        _context(events),
        recorder,
        _FakeReader({item.display_path: entry}),
    )

    assert result.outcomes[0].result is expected
    assert result.outcomes[0].reason is reason
    assert len(_integrity_events(events)) == 1
    assert recorder.commands == []


def test_expected_missing_and_unsupported_rows_are_never_opened(tmp_path: Path) -> None:
    missing = _item(tmp_path, number=1, expected_state=InventoryState.MISSING)
    unsupported = _item(tmp_path, number=2, expected_state=InventoryState.UNSUPPORTED)
    reader = _FakeReader({})

    result = verify(
        IntegritySelection((missing, unsupported)),
        _context([]),
        _Recorder(),
        reader,
    )

    assert [outcome.result for outcome in result.outcomes] == [
        IntegrityResult.MISSING,
        IntegrityResult.UNSUPPORTED,
    ]
    assert reader.opened == []


def test_read_drift_prevents_the_recorder_call(tmp_path: Path) -> None:
    before = _stat()
    after = _stat(mtime_ns=101)
    item = _item(tmp_path, expected_stat=before)
    recorder = _Recorder()

    result = verify(
        IntegritySelection((item,)),
        _context([]),
        recorder,
        _FakeReader({item.display_path: _StreamSpec(before, (b"abc",), after)}),
    )

    assert result.outcomes[0].result is IntegrityResult.MODIFIED
    assert result.outcomes[0].reason is IntegrityReason.READ_DRIFT
    assert recorder.commands == []


@pytest.mark.parametrize(
    ("recorder", "reason", "disposition"),
    [
        (
            _Recorder(RecordDisposition.STALE),
            IntegrityReason.RECORDING_STALE,
            RecordDisposition.STALE,
        ),
        (
            _Recorder(RecordDisposition.CONFLICT),
            IntegrityReason.RECORDING_CONFLICT,
            RecordDisposition.CONFLICT,
        ),
        (_Recorder(error=OSError("sqlite unavailable")), IntegrityReason.RECORDING_ERROR, None),
    ],
)
def test_conditional_recording_drift_and_errors_degrade_only_recording_axis(
    tmp_path: Path,
    recorder: _Recorder,
    reason: IntegrityReason,
    disposition: RecordDisposition | None,
) -> None:
    item = _item(tmp_path)

    result = verify(
        IntegritySelection((item,)),
        _context([]),
        recorder,
        _FakeReader({item.display_path: _StreamSpec(item.expected_stat, (b"abc",))}),  # type: ignore[arg-type]
    )

    outcome = result.outcomes[0]
    assert outcome.result is IntegrityResult.VERIFIED
    assert outcome.recording is RecordingStatus.DEGRADED
    assert outcome.reason is reason
    assert outcome.record_disposition is disposition
    assert result.recording is RecordingStatus.DEGRADED
    assert len(recorder.commands) == 1


def test_canonical_key_validation_prevents_wrong_target_open(tmp_path: Path) -> None:
    item = replace(
        _item(tmp_path, path="Folder/File.bin"),
        rel_path_key=normalize_relative_path("Other/File.bin"),
    )
    reader = _FakeReader({})

    result = verify(
        IntegritySelection((item,)), _context([]), _Recorder(), reader
    )

    assert result.outcomes[0].reason is IntegrityReason.PATH_INVALID
    assert reader.opened == []


def test_same_canonical_path_in_two_locations_keeps_row_identity(tmp_path: Path) -> None:
    other_root = tmp_path / "other"
    item_1 = _item(tmp_path, number=1, path="Folder/File.bin", location_id="one")
    item_2 = _item(other_root, number=2, path="folder\\file.bin", location_id="two")
    reader = _FakeReader(
        {
            item_1.display_path: _StreamSpec(item_1.expected_stat, (b"abc",)),  # type: ignore[arg-type]
            item_2.display_path: _StreamSpec(item_2.expected_stat, (b"abc",)),  # type: ignore[arg-type]
        }
    )
    recorder = _Recorder()

    verify(
        IntegritySelection((item_1, item_2)), _context([]), recorder, reader
    )

    assert [(command.location_id, command.row_id) for command in recorder.commands] == [
        ("one", "row-1"),
        ("two", "row-2"),
    ]


@pytest.mark.parametrize("completed_before_cancel", [0, 1, 2])
def test_cancellation_emits_exactly_one_outcome_for_every_selected_row(
    tmp_path: Path, completed_before_cancel: int
) -> None:
    items = tuple(_item(tmp_path, number=number) for number in range(1, 4))
    events: list[object] = []

    def checkpoint() -> None:
        if len(_integrity_events(events)) >= completed_before_cancel:
            raise Canceled

    reader = _FakeReader(
        {
            item.display_path: _StreamSpec(item.expected_stat, (b"abc",))  # type: ignore[arg-type]
            for item in items
        }
    )
    selection = IntegritySelection(items)
    recorder = _Recorder()

    with pytest.raises(Canceled):
        verify(selection, _context(events, checkpoint), recorder, reader)

    outcomes = _integrity_events(events)
    assert len(outcomes) == len(items)
    assert len({outcome.item_id for outcome in outcomes}) == len(items)
    assert [outcome.result for outcome in outcomes[:completed_before_cancel]] == [
        IntegrityResult.VERIFIED
    ] * completed_before_cancel
    assert all(
        outcome.result is IntegrityResult.CANCELED
        for outcome in outcomes[completed_before_cancel:]
    )
    assert selection.completed_count == len(items)
    assert len(recorder.commands) == completed_before_cancel


def test_pause_resume_preserves_completed_rows_without_duplicates(tmp_path: Path) -> None:
    items = tuple(_item(tmp_path, number=number) for number in range(1, 4))
    events: list[object] = []

    def pause_after_one() -> None:
        if len(_integrity_events(events)) >= 1:
            raise PauseRequested

    reader = _FakeReader(
        {
            item.display_path: _StreamSpec(item.expected_stat, (b"abc",))  # type: ignore[arg-type]
            for item in items
        }
    )
    selection = IntegritySelection(items)
    recorder = _Recorder()

    with pytest.raises(PauseRequested):
        verify(selection, _context(events, pause_after_one), recorder, reader)
    assert selection.completed_count == 1
    assert len(_integrity_events(events)) == 1

    resumed = verify(selection, _context(events), recorder, reader)

    outcomes = _integrity_events(events)
    assert len(outcomes) == len(items)
    assert len({outcome.item_id for outcome in outcomes}) == len(items)
    assert len(resumed.outcomes) == 2
    assert selection.completed_count == len(items)
    assert len(recorder.commands) == len(items)


def test_cancellation_during_hash_marks_in_flight_item_canceled(tmp_path: Path) -> None:
    item = _item(tmp_path)
    calls = 0
    events: list[object] = []

    def checkpoint() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:  # entry, first chunk, then cancel on the second chunk
            raise Canceled

    selection = IntegritySelection((item,))
    recorder = _Recorder()

    with pytest.raises(Canceled):
        verify(
            selection,
            _context(events, checkpoint),
            recorder,
            _FakeReader(
                {
                    item.display_path: _StreamSpec(
                        item.expected_stat, (b"a", b"b", b"c")  # type: ignore[arg-type]
                    )
                }
            ),
        )

    outcomes = _integrity_events(events)
    assert [outcome.result for outcome in outcomes] == [IntegrityResult.CANCELED]
    assert selection.completed_count == 1
    assert selection.processed_bytes == 1
    assert recorder.commands == []


def test_pause_during_hash_restarts_pending_item_without_outcome_or_progress_regression(
    tmp_path: Path,
) -> None:
    item = _item(tmp_path)
    calls = 0
    events: list[object] = []

    def checkpoint() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise PauseRequested

    selection = IntegritySelection((item,))
    recorder = _Recorder()
    reader = _FakeReader(
        {
            item.display_path: _StreamSpec(
                item.expected_stat, (b"a", b"b", b"c")  # type: ignore[arg-type]
            )
        }
    )

    with pytest.raises(PauseRequested):
        verify(selection, _context(events, checkpoint), recorder, reader)

    assert _integrity_events(events) == []
    assert selection.completed_count == 0
    assert selection.processed_bytes == 1
    assert recorder.commands == []

    result = verify(selection, _context(events), recorder, reader)

    assert result.outcomes[0].result is IntegrityResult.VERIFIED
    assert len(_integrity_events(events)) == 1
    progress = [event.bytes_done for event in events if isinstance(event, Progress)]
    assert progress == sorted(progress)
    assert selection.processed_bytes == 4
    assert len(recorder.commands) == 1


def test_runner_aggregates_typed_integrity_outcomes_on_cancel(tmp_path: Path) -> None:
    items = (_item(tmp_path, number=1), _item(tmp_path, number=2))
    selection = IntegritySelection(items)
    published: list[OperationResult] = []
    emitted: list[object] = []
    settled: list[tuple[SessionState, OperationResult | None]] = []

    def work(run_ctx: RunContext) -> OperationResult:
        verify(
            selection,
            VerifierContext(
                run=run_ctx,
                clock=_Clock(),
                hasher_factory=xxh3_128,
                chunk_size=1,
            ),
            _Recorder(),
            _FakeReader({}),
        )
        raise AssertionError("cancellation must unwind before a workflow result")

    outcome = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: (_ for _ in ()).throw(Canceled()),
        settle=lambda state, result: settled.append((state, result)),
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=published.append,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.CANCELED
    assert len(outcome.result.items) == len(items)
    assert all(isinstance(item, IntegrityOutcome) for item in outcome.result.items)
    assert [item.result for item in outcome.result.items] == [
        IntegrityResult.CANCELED,
        IntegrityResult.CANCELED,
    ]
    assert len(published) == 1
    assert settled[-1][0] is SessionState.CANCELED


def test_runner_can_finalize_cancellation_after_partial_byte_progress(
    tmp_path: Path,
) -> None:
    item = _item(tmp_path)
    selection = IntegritySelection((item,))
    calls = 0

    def checkpoint() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise Canceled

    def work(run_ctx: RunContext) -> OperationResult:
        verify(
            selection,
            VerifierContext(
                run=run_ctx,
                clock=_Clock(),
                hasher_factory=xxh3_128,
                chunk_size=1,
                progress_interval_seconds=0,
            ),
            _Recorder(),
            _FakeReader(
                {
                    item.display_path: _StreamSpec(
                        item.expected_stat, (b"a", b"b", b"c")  # type: ignore[arg-type]
                    )
                }
            ),
        )
        raise AssertionError("cancellation must unwind")

    outcome = run_session(
        work,
        emit=lambda event: None,
        checkpoint=checkpoint,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
    )

    assert outcome.result is not None
    assert outcome.result.status is SessionState.CANCELED
    assert outcome.result.bytes_done == 1
    assert outcome.result.bytes_total == 3
    assert len(outcome.result.items) == 1


def test_runner_retains_verifier_outcomes_across_pause_then_cancel(
    tmp_path: Path,
) -> None:
    items = tuple(_item(tmp_path, number=number) for number in range(1, 4))
    selection = IntegritySelection(items)
    emitted: list[object] = []
    accumulated: list[object] = []
    recorder = _Recorder()
    reader = _FakeReader(
        {
            item.display_path: _StreamSpec(item.expected_stat, (b"abc",))  # type: ignore[arg-type]
            for item in items
        }
    )

    def work(run_ctx: RunContext) -> OperationResult:
        integrity = verify(
            selection,
            VerifierContext(
                run=run_ctx,
                clock=_Clock(),
                hasher_factory=xxh3_128,
                chunk_size=1,
            ),
            recorder,
            reader,
        )
        return OperationResult(
            status=SessionState.COMPLETED,
            recording=integrity.recording,
            items=integrity.outcomes,
            bytes_done=selection.processed_bytes,
            bytes_total=selection.processed_bytes,
        )

    def pause_after_one() -> None:
        if len(_integrity_events(emitted)) >= 1:
            raise PauseRequested

    paused = run_session(
        work,
        emit=emitted.append,
        checkpoint=pause_after_one,
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
        item_accumulator=accumulated,
    )

    assert paused.paused is True
    assert len(accumulated) == 1
    assert selection.completed_count == 1

    canceled = run_session(
        work,
        emit=emitted.append,
        checkpoint=lambda: (_ for _ in ()).throw(Canceled()),
        settle=lambda state, result: None,
        finalize_audit=lambda result: RecordingStatus.OK,
        publish_result=lambda result: None,
        item_accumulator=accumulated,
    )

    assert canceled.result is not None
    assert canceled.result.status is SessionState.CANCELED
    assert [item.result for item in canceled.result.items] == [
        IntegrityResult.VERIFIED,
        IntegrityResult.CANCELED,
        IntegrityResult.CANCELED,
    ]
    assert len({item.item_id for item in canceled.result.items}) == 3


def test_fast_chunk_flood_is_throttled_and_progress_is_monotonic(tmp_path: Path) -> None:
    data = b"x" * 100
    stat = _stat(size=len(data))
    item = _item(
        tmp_path,
        expected_stat=stat,
        baseline_evidence=_attestation(data, stat),
    )
    events: list[object] = []

    verify(
        IntegritySelection((item,)),
        _context(events, monotonic=lambda: 0.0),
        _Recorder(),
        _FakeReader(
            {item.display_path: _StreamSpec(stat, tuple(b"x" for _ in range(100)))}
        ),
    )

    progress = [event for event in events if isinstance(event, Progress)]
    assert len(progress) == 2
    assert [event.bytes_done for event in progress] == sorted(
        event.bytes_done for event in progress
    )
    assert progress[-1].bytes_done == len(data)


@pytest.mark.skipif(os.name != "nt", reason="Windows cache-honest integration")
def test_windows_reader_uses_read_only_share_and_cache_honest_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "payload.bin"
    path.write_bytes(b"flag contract")
    expected = _stat(
        size=path.stat().st_size,
        mtime_ns=path.stat().st_mtime_ns,
        identity=None,
    )
    calls: list[tuple[object, ...]] = []
    closed: list[int] = []
    native_api = verifier_module._WindowsApi

    class _Kernel32:
        def CreateFileW(self, *args: object) -> int:
            calls.append(args)
            return 73

    class _CapturingApi(native_api):
        def __init__(self) -> None:
            self._kernel32 = _Kernel32()

        def sector_size(self, candidate: Path) -> int:
            assert candidate == path
            return 4096

        def require_expected_final_path(
            self, root: Path, relative_path: str, file_handle: int
        ) -> None:
            assert root == tmp_path.resolve()
            assert relative_path == path.name
            assert file_handle == 73

        def stat(self, handle: int) -> FileStat:
            assert handle == 73
            return expected

        def close(self, handle: int) -> None:
            closed.append(handle)

    monkeypatch.setattr(verifier_module, "_WindowsApi", _CapturingApi)

    with WindowsUnbufferedReader().open(tmp_path, path.name) as stream:
        assert stream.strategy is ReadStrategy.WINDOWS_UNBUFFERED

    assert len(calls) == 1
    (
        opened_path,
        desired_access,
        share_mode,
        security_attributes,
        creation_disposition,
        flags,
        template,
    ) = calls[0]
    assert opened_path == verifier_module._extended_path(path)
    assert desired_access == verifier_module._GENERIC_READ
    assert share_mode == verifier_module._FILE_SHARE_READ
    assert share_mode & verifier_module._FILE_SHARE_WRITE == 0
    assert share_mode & verifier_module._FILE_SHARE_DELETE == 0
    assert security_attributes is None
    assert creation_disposition == verifier_module._OPEN_EXISTING
    assert flags == (
        verifier_module._FILE_FLAG_NO_BUFFERING
        | verifier_module._FILE_FLAG_SEQUENTIAL_SCAN
        | verifier_module._FILE_FLAG_OPEN_REPARSE_POINT
    )
    assert template is None
    assert closed == [73]


@pytest.mark.skipif(os.name != "nt", reason="Windows cache-honest integration")
def test_windows_reader_verifies_externally_flushed_file_without_cached_fallback(
    tmp_path: Path,
) -> None:
    payload = (b"NamiSync cache-honest verifier\n" * 262_144) + b"tail"
    path = tmp_path / "payload.bin"
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os, sys\n"
                "payload = (b'NamiSync cache-honest verifier\\n' * 262_144)"
                " + b'tail'\n"
                "with open(sys.argv[1], 'wb') as handle:\n"
                "    handle.write(payload)\n"
                "    handle.flush()\n"
                "    os.fsync(handle.fileno())\n"
            ),
            str(path),
        ],
        check=True,
    )
    os_stat = path.stat()
    expected = _stat(
        size=len(payload),
        mtime_ns=os_stat.st_mtime_ns,
        identity=None,
    )
    events: list[object] = []
    context = VerifierContext(
        run=RunContext(emit=events.append, checkpoint=lambda: None),
        clock=_Clock(),
        hasher_factory=xxh3_128,
    )
    assert context.chunk_size == 4 * 1024 * 1024
    reader = WindowsUnbufferedReader()
    item = _item(
        tmp_path,
        path="payload.bin",
        expected_stat=expected,
        baseline_evidence=_attestation(payload, expected),
    )

    result = verify(
        IntegritySelection((item,)),
        context,
        _Recorder(),
        reader,
    )

    outcome = result.outcomes[0]
    assert outcome.result is IntegrityResult.VERIFIED
    assert outcome.reason is None
    assert outcome.read_strategy is ReadStrategy.WINDOWS_UNBUFFERED


@pytest.mark.skipif(os.name != "nt", reason="Windows cache-honest integration")
@pytest.mark.parametrize("rejection", ["reparse", "alignment", "containment"])
def test_windows_reader_safety_rejections_classify_unsupported_never_verified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rejection: str,
) -> None:
    payload = b"guarded subject"
    path = tmp_path / "payload.bin"
    path.write_bytes(payload)
    expected = _stat(
        size=len(payload),
        mtime_ns=path.stat().st_mtime_ns,
        identity=None,
    )
    closed: list[int] = []
    native_api = verifier_module._WindowsApi

    if rejection == "reparse":
        original_reject = verifier_module._reject_reparse_components
        original_lstat = verifier_module.os.lstat

        def report_reparse(root: Path, relative_path: str) -> None:
            class _ReportedReparse:
                st_file_attributes = verifier_module._FILE_ATTRIBUTE_REPARSE_POINT

            def reparse_lstat(current: Path):
                original_lstat(current)
                return _ReportedReparse()

            with monkeypatch.context() as patch:
                patch.setattr(verifier_module.os, "lstat", reparse_lstat)
                original_reject(root, relative_path)

        monkeypatch.setattr(
            verifier_module, "_reject_reparse_components", report_reparse
        )
        expected_detail = "verification refuses reparse component"

        class _RejectingApi:
            def __init__(self) -> None:
                raise AssertionError("reparse rejection must precede Windows API setup")

    elif rejection == "alignment":
        expected_detail = "volume reported an invalid sector size"

        class _Kernel32:
            def GetVolumePathNameW(
                self, _path: str, volume_buffer, _size: int
            ) -> int:
                volume_buffer.value = tmp_path.anchor
                return 1

            def GetDiskFreeSpaceW(self, *_args: object) -> int:
                return 1

        class _RejectingApi(native_api):
            def __init__(self) -> None:
                self._kernel32 = _Kernel32()

    else:
        expected_detail = (
            "the opened handle does not resolve to the selected root-relative path"
        )

        class _RejectingApi(native_api):
            def __init__(self) -> None:
                pass

            def sector_size(self, candidate: Path) -> int:
                assert candidate == path
                return 4096

            def open_file(self, candidate: Path) -> int:
                assert candidate == path
                return 73

            def open_directory(self, root: Path) -> int:
                assert root == tmp_path.resolve()
                return 74

            def final_path(self, handle: int) -> str:
                return (
                    r"\\?\C:\selected-root"
                    if handle == 74
                    else r"\\?\C:\escaped-root\payload.bin"
                )

            def close(self, handle: int) -> None:
                closed.append(handle)

    monkeypatch.setattr(verifier_module, "_WindowsApi", _RejectingApi)
    recorder = _Recorder()
    item = _item(
        tmp_path,
        path=path.name,
        expected_stat=expected,
        baseline_evidence=_attestation(payload, expected),
    )

    result = verify(
        IntegritySelection((item,)),
        _context([]),
        recorder,
        WindowsUnbufferedReader(),
    )

    outcome = result.outcomes[0]
    assert outcome.result is IntegrityResult.UNSUPPORTED
    assert outcome.result is not IntegrityResult.VERIFIED
    assert outcome.reason is IntegrityReason.UNSUPPORTED_READ
    assert outcome.detail is not None and expected_detail in outcome.detail
    assert recorder.commands == []
    assert closed == ([74, 73] if rejection == "containment" else [])


@pytest.mark.skipif(os.name != "nt", reason="Windows cache-honest integration")
def test_windows_reader_holds_selected_path_against_write_and_replacement(
    tmp_path: Path,
) -> None:
    path = tmp_path / "payload.bin"
    replacement = tmp_path / "replacement.bin"
    path.write_bytes(b"selected subject")
    replacement.write_bytes(b"replacement subject")

    reader = WindowsUnbufferedReader()
    try:
        with reader.open(tmp_path, path.name) as stream:
            with pytest.raises(PermissionError):
                path.write_bytes(b"overwritten")
            with pytest.raises(PermissionError):
                os.replace(replacement, path)
            assert stream.stat().size == len(b"selected subject")
    except UnsupportedVerification as exc:
        pytest.skip(f"unbuffered strategy unavailable: {exc}")

    assert path.read_bytes() == b"selected subject"
    assert replacement.read_bytes() == b"replacement subject"
