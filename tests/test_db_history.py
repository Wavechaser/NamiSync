from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from namisync.core.events import Envelope, ItemOutcome, SCHEMA_VERSION, StateChanged
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.integrity import (
    IntegrityOutcome,
    IntegrityReason,
    IntegrityResult,
    ReadStrategy,
    RecordDisposition,
)
from namisync.core.session import (
    Disposition,
    OperationResult,
    SessionId,
    SessionRecord,
    SessionState,
)
from namisync.db.history import (
    HistoryContext,
    HistoryIntegrityError,
    HistoryRepository,
    HistoryStore,
)
from namisync.db.connections import connect_history_reader
from namisync.db.writer import RecordingError, TokenConflictError

from _db_fixtures import FakeClock, NOW


def _record(session_id: str = "session-1", *, kind: str = "sync") -> SessionRecord:
    return SessionRecord(
        SessionId(session_id),
        kind,
        SessionState.PENDING,
        (),
        b"opaque",
        True,
        1,
        NOW,
    )


def _envelope(record: SessionRecord, seq: int, body: object) -> Envelope:
    return Envelope(record.session_id, seq, NOW, SCHEMA_VERSION, body)


def test_history_round_trips_sync_axes_and_ordered_operations(tmp_path: Path) -> None:
    record = _record()
    context = HistoryContext(
        "run-1", "host-1", source_context="source", target_context="target"
    )
    item = ItemOutcome(
        "op-1",
        "copy",
        "a.txt",
        Outcome.SUCCEEDED,
        detail={"bytes": 7},
    )
    result = OperationResult(
        SessionState.COMPLETED,
        recording=RecordingStatus.DEGRADED,
        audit=RecordingStatus.OK,
        disposition=Disposition.RAN,
        items=(item,),
        bytes_done=7,
        bytes_total=7,
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.on_event(_envelope(record, 1, StateChanged(SessionState.RUNNING)))
        observer.on_event(_envelope(record, 2, item))
        observer.on_event(_envelope(record, 2, item))
        observer.finalize(result)

        with HistoryRepository(store.path) as repository:
            snapshot = repository.get("run-1")
        connection = connect_history_reader(store.path)
        try:
            stored_item = connection.execute(
                "SELECT item_type, phase, result FROM history_items"
            ).fetchone()
            phase_count = int(
                connection.execute("SELECT COUNT(*) FROM history_phases").fetchone()[0]
            )
        finally:
            connection.close()

    assert snapshot.filesystem_status is SessionState.COMPLETED
    assert snapshot.recording is RecordingStatus.DEGRADED
    assert snapshot.audit is RecordingStatus.OK
    assert snapshot.disposition == Disposition.RAN.value
    assert snapshot.started_at == NOW
    assert snapshot.ended_at == NOW
    assert len(snapshot.items) == 1
    assert snapshot.items[0].event_seq == 2
    assert snapshot.items[0].item == item
    assert tuple(stored_item) == ("operation", "execute", Outcome.SUCCEEDED.value)
    assert phase_count == 0


def test_history_hash_and_detail_json_escape_unpaired_surrogates(
    tmp_path: Path,
) -> None:
    record = _record("session-hostile-detail")
    context = HistoryContext("run-hostile-detail", "host-1")
    hostile = "bad_\udcff"
    item = ItemOutcome(
        "op-hostile",
        "noop",
        "safe.txt",
        Outcome.SKIPPED,
        detail={"message": hostile},
    )
    result = OperationResult(SessionState.COMPLETED, items=(item,))

    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.on_event(_envelope(record, 1, item))
        observer.finalize(result)
        with HistoryRepository(store.path) as repository:
            snapshot = repository.get("run-hostile-detail")

    assert snapshot.items[0].item == item


def test_history_records_blocked_outcome_and_aggregate(tmp_path: Path) -> None:
    record = _record("session-blocked")
    context = HistoryContext("run-blocked", "host-1")
    item = ItemOutcome(
        "op-blocked",
        "noop",
        "junction",
        Outcome.BLOCKED,
        reason="unsupported",
    )
    result = OperationResult(SessionState.COMPLETED, items=(item,))

    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.on_event(_envelope(record, 1, item))
        observer.finalize(result)
        with HistoryRepository(store.path) as repository:
            snapshot = repository.get("run-blocked")
        connection = connect_history_reader(store.path)
        try:
            blocked_count = connection.execute(
                "SELECT blocked_count FROM history_runs WHERE run_token = ?",
                ("run-blocked",),
            ).fetchone()[0]
        finally:
            connection.close()

    assert snapshot.items[0].item == item
    assert blocked_count == 1


def test_history_keeps_noop_refusal_browseable(tmp_path: Path) -> None:
    record = _record("session-refused")
    context = HistoryContext("run-refused", "host-1")
    result = OperationResult(
        SessionState.REFUSED,
        disposition=Disposition.UNRUN,
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        store.observer(record, context).finalize(result)
        with HistoryRepository(store.path) as repository:
            snapshot = repository.get("run-refused")

    assert snapshot.filesystem_status is SessionState.REFUSED
    assert snapshot.disposition == Disposition.UNRUN.value
    assert snapshot.items == ()


def test_history_duplicate_delivery_is_idempotent_but_conflict_is_diagnosed(
    tmp_path: Path,
) -> None:
    record = _record()
    context = HistoryContext("run-1", "host-1")
    item = ItemOutcome("op-1", "noop", "a.txt", Outcome.SKIPPED)
    result = OperationResult(SessionState.COMPLETED, items=(item,))
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        first = store.observer(record, context)
        first.on_event(_envelope(record, 1, item))
        first.finalize(result)

        duplicate = store.observer(record, context)
        duplicate.on_event(_envelope(record, 1, item))
        duplicate.finalize(result)

        conflicting = store.observer(record, context)
        changed = replace(item, outcome=Outcome.FAILED)
        conflicting.on_event(_envelope(record, 1, changed))
        with pytest.raises(TokenConflictError):
            conflicting.finalize(
                OperationResult(SessionState.FAILED, items=(changed,))
            )


def test_history_round_trips_integrity_item_and_rejects_unknown_body(
    tmp_path: Path,
) -> None:
    record = _record("session-integrity", kind="integrity-verify")
    context = HistoryContext(
        "run-integrity",
        "host-1",
        activity_kind="integrity-verify",
        subject_kind="location",
        subject_id="8",
        target_context=r"C:\library",
    )
    item = IntegrityOutcome(
        item_id="row-12",
        row_id="12",
        location_id="8",
        path="asset.bin",
        result=IntegrityResult.MISMATCHED,
        reason=IntegrityReason.HASH_MISMATCH,
        detail="digest differs",
        read_strategy=ReadStrategy.WINDOWS_UNBUFFERED,
        recording=RecordingStatus.DEGRADED,
        record_disposition=RecordDisposition.STALE,
    )
    result = OperationResult(
        SessionState.COMPLETED,
        recording=RecordingStatus.DEGRADED,
        items=(item,),
        bytes_done=7,
        bytes_total=7,
    )

    @dataclass(frozen=True)
    class UnknownBody:
        value: str

    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.on_event(_envelope(record, 1, item))
        with pytest.raises(HistoryIntegrityError, match="unsupported reliable"):
            observer.on_event(_envelope(record, 2, UnknownBody("unknown")))
        observer.finalize(result)
        with HistoryRepository(store.path) as repository:
            snapshot = repository.get("run-integrity")
        connection = connect_history_reader(store.path)
        try:
            stored = connection.execute(
                """SELECT item_type, phase, result, reason
                     FROM history_items"""
            ).fetchone()
            phase_count = connection.execute(
                "SELECT count(*) FROM history_phases"
            ).fetchone()[0]
        finally:
            connection.close()

    assert snapshot.items[0].item == item
    assert tuple(stored) == (
        "integrity",
        "verify",
        "mismatched",
        "hash-mismatch",
    )
    assert phase_count == 0


def test_conflicting_duplicate_event_sequence_is_rejected_before_storage(
    tmp_path: Path,
) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(
            _envelope(record, 1, ItemOutcome("op", "copy", "a", Outcome.SUCCEEDED))
        )
        with pytest.raises(HistoryIntegrityError):
            observer.on_event(
                _envelope(record, 1, ItemOutcome("op", "copy", "b", Outcome.SUCCEEDED))
            )


def test_history_failure_does_not_mutate_domain_result(tmp_path: Path) -> None:
    record = _record()
    result = OperationResult(SessionState.COMPLETED)
    store = HistoryStore(tmp_path / "history.db", clock=FakeClock())
    observer = store.observer(record, HistoryContext("run-1", "host-1"))
    store.close()

    with pytest.raises(RecordingError):
        observer.finalize(result)
    assert result.status is SessionState.COMPLETED
    assert result.recording is RecordingStatus.OK
    assert result.audit is RecordingStatus.OK
