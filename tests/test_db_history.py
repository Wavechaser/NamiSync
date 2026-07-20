from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from namisync.core.events import Envelope, ItemOutcome, SCHEMA_VERSION, StateChanged
from namisync.core.evidence import Outcome, RecordingStatus
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
        operations=(item,),
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

    assert snapshot.filesystem_status is SessionState.COMPLETED
    assert snapshot.recording is RecordingStatus.DEGRADED
    assert snapshot.audit is RecordingStatus.OK
    assert snapshot.disposition == Disposition.RAN.value
    assert snapshot.started_at == NOW
    assert snapshot.ended_at == NOW
    assert len(snapshot.operations) == 1
    assert snapshot.operations[0].event_seq == 2
    assert snapshot.operations[0].detail == {"bytes": 7}


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
    result = OperationResult(SessionState.COMPLETED, operations=(item,))

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

    assert snapshot.operations[0].outcome is Outcome.BLOCKED
    assert snapshot.operations[0].path == "junction"
    assert snapshot.operations[0].reason == "unsupported"
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
    assert snapshot.operations == ()


def test_history_duplicate_delivery_is_idempotent_but_conflict_is_diagnosed(
    tmp_path: Path,
) -> None:
    record = _record()
    context = HistoryContext("run-1", "host-1")
    item = ItemOutcome("op-1", "noop", "a.txt", Outcome.SKIPPED)
    result = OperationResult(SessionState.COMPLETED, operations=(item,))
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
                OperationResult(SessionState.FAILED, operations=(changed,))
            )


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
