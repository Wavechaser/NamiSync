from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

import namisync.db.history as history_module
from namisync.core.events import (
    Envelope,
    Gap,
    ItemOutcome,
    PhaseChanged,
    SCHEMA_VERSION,
    StateChanged,
    envelope_to_dict,
)
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.integrity import (
    IntegrityOutcome,
    IntegrityReason,
    IntegrityResult,
)
from namisync.core.session import (
    Disposition,
    FailureDetail,
    OperationResult,
    PhaseResult,
    PhaseStatus,
    SessionId,
    SessionRecord,
    SessionState,
)
from namisync.db.connections import (
    connect_history_reader,
    connect_history_writer,
)
from namisync.db.history import (
    MAX_HISTORY_ERROR_MESSAGE_BYTES,
    MAX_HISTORY_ERROR_TYPE_BYTES,
    MAX_HISTORY_PAGE_SIZE,
    MAX_HISTORY_PHASE_NAME_BYTES,
    MAX_HISTORY_PHASES,
    HistoryClassificationAggregate,
    HistoryContext,
    HistoryIntegrityError,
    HistoryRepository,
    HistoryStore,
    HistoryWindowPolicy,
)
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


def _item(seq: int, outcome: Outcome = Outcome.SUCCEEDED) -> ItemOutcome:
    return ItemOutcome(
        f"op-{seq}",
        "copy",
        f"{seq}.bin",
        outcome,
        detail={"bytes": seq},
    )


def _allow_history_event_updates(connection: sqlite3.Connection) -> None:
    connection.execute("DROP TRIGGER history_events_append_only_update")


def _allow_finalized_run_updates(connection: sqlite3.Connection) -> None:
    connection.execute("DROP TRIGGER history_runs_finalized_update")


def _insert_history_event(
    connection: sqlite3.Connection,
    run_id: int,
    envelope: Envelope,
    *,
    item_order: int | None = None,
) -> None:
    encoded = history_module._json_bytes(envelope_to_dict(envelope))
    payload_hash = history_module.hashlib.sha256(encoded).digest()
    projection = history_module._item_projection(envelope.body)
    item_identity_hash = (
        None
        if projection is None
        else history_module._item_identity_hash(envelope.body)
    )
    item_payload_hash = (
        None
        if projection is None
        else history_module._hash(
            history_module.result_item_to_dict(envelope.body)
        )
    )
    receipt_hash = history_module._receipt_hash(
        event_seq=envelope.seq,
        event_at=history_module.encode_utc(envelope.at),
        schema_version=envelope.schema_version,
        body_type=type(envelope.body).__name__,
        disposition=history_module.HistoryEventDisposition.RECORDED,
        payload_hash=payload_hash,
        item_identity_hash=item_identity_hash,
        item_payload_hash=item_payload_hash,
        item_order=item_order,
    )
    connection.execute(
        """INSERT INTO history_events(
               run_id, event_seq, event_at, schema_version, body_type,
               event_disposition, envelope_json, payload_hash, receipt_hash,
               item_identity_hash, item_payload_hash, duplicate_of_seq,
               rejection_reason, item_order,
               item_type, phase, item_id, kind, path, result, reason
           ) VALUES (?, ?, ?, ?, ?, 'recorded', ?, ?, ?, ?, ?, NULL, NULL, ?,
                     ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            envelope.seq,
            history_module.encode_utc(envelope.at),
            envelope.schema_version,
            type(envelope.body).__name__,
            encoded.decode("utf-8"),
            payload_hash,
            receipt_hash,
            item_identity_hash,
            item_payload_hash,
            item_order,
            None if projection is None else projection["item_type"],
            None if projection is None else projection["phase"],
            None if projection is None else projection["item_id"],
            None if projection is None else projection["kind"],
            None if projection is None else projection["path"],
            None if projection is None else projection["result"],
            None if projection is None else projection["reason"],
        ),
    )


@pytest.mark.parametrize(
    "arguments",
    (
        (1, "host-1", {}),
        ("run-1", 1, {}),
        ("run-1", "host-1", {"subject_id": 1}),
    ),
)
def test_history_context_rejects_non_string_identifiers(arguments: tuple) -> None:
    run_token, host_key, options = arguments
    with pytest.raises(TypeError):
        HistoryContext(run_token, host_key, **options)


def test_history_window_policy_freezes_balanced_defaults_and_rejects_bad_bounds() -> None:
    assert HistoryWindowPolicy() == HistoryWindowPolicy(
        max_events=256,
        max_bytes=1_048_576,
        max_event_bytes=1_048_576,
        max_age_seconds=1.0,
    )
    for values in (
        {"max_events": 0},
        {"max_bytes": 0},
        {"max_event_bytes": 0},
        {"max_bytes": 10, "max_event_bytes": 11},
        {"max_age_seconds": 0},
        {"max_age_seconds": float("nan")},
        {"max_age_seconds": float("inf")},
    ):
        with pytest.raises(ValueError):
            HistoryWindowPolicy(**values)


def test_history_finalization_round_trips_summary_items_events_and_phases(
    tmp_path: Path,
) -> None:
    record = _record()
    context = HistoryContext(
        "run-1", "host-1", source_context="source", target_context="target"
    )
    item = ItemOutcome(
        "op-1", "copy", "a.txt", Outcome.SUCCEEDED, detail={"bytes": 7}
    )
    phases = (PhaseResult("execute", PhaseStatus.COMPLETED, 1, 1, 7, 7),)
    result = OperationResult(
        SessionState.COMPLETED,
        recording=RecordingStatus.DEGRADED,
        audit=RecordingStatus.OK,
        disposition=Disposition.RAN,
        items=(item,),
        phases=phases,
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
            summary = repository.get_summary("run-1")
            items = repository.get_item_page("run-1")
            events = repository.get_event_page("run-1")

    assert summary.finalized
    assert summary.current_state is SessionState.COMPLETED
    assert summary.filesystem_status is SessionState.COMPLETED
    assert summary.recording is RecordingStatus.DEGRADED
    assert summary.audit is RecordingStatus.OK
    assert summary.started_at == NOW
    assert summary.ended_at == NOW
    assert summary.last_committed_seq == 2
    assert summary.item_count == 1
    assert summary.succeeded_count == 1
    assert summary.phases[0].phase == phases[0]
    assert summary.classification == HistoryClassificationAggregate(
        operation_results=frozenset({"succeeded"}),
        selected_operation_count=1,
        selected_other_operation_count=1,
        integrity_results=frozenset(),
        verify_phase_baseline=False,
    )
    assert items.through_order == 1
    assert items.items[0].item_order == 1
    assert items.items[0].event_seq == 2
    assert items.items[0].item == item
    assert [event.event_seq for event in events.events] == [1, 2]
    assert events.events[1].envelope.body == item


def test_count_bound_flushes_complete_windows_and_exposes_incomplete_summary(
    tmp_path: Path,
) -> None:
    policy = HistoryWindowPolicy(max_events=2)
    record = _record()
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        assert observer.pending_event_count == 1
        observer.on_event(_envelope(record, 2, _item(2)))
        assert observer.pending_event_count == 0
        assert observer.pending_bytes == 0

        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-1")
        assert not summary.finalized
        assert summary.last_committed_seq == 2
        assert summary.item_count == 2

        observer.on_event(_envelope(record, 3, _item(3)))
        with HistoryRepository(store.path) as repository:
            assert repository.get_summary("run-1").last_committed_seq == 2
        observer.flush()
        with HistoryRepository(store.path) as repository:
            assert repository.get_summary("run-1").last_committed_seq == 3


def test_byte_bound_flushes_before_an_incoming_event_would_exceed_it(
    tmp_path: Path,
) -> None:
    record = _record()
    first = _envelope(record, 1, _item(1))
    second = _envelope(record, 2, _item(2))
    sizes = [
        len(history_module._json_bytes(envelope_to_dict(event)))
        for event in (first, second)
    ]
    bound = max(sizes) + 1
    assert sum(sizes) > bound
    policy = HistoryWindowPolicy(
        max_events=256,
        max_bytes=bound,
        max_event_bytes=bound,
    )
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(first)
        observer.on_event(second)

        assert observer.pending_event_count == 1
        assert observer.pending_bytes == sizes[1]
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-1")
        assert summary.last_committed_seq == 1
        assert summary.item_count == 1


def test_oversized_single_event_degrades_without_violating_memory_bound(
    tmp_path: Path,
) -> None:
    record = _record()
    event = _envelope(record, 1, _item(1))
    size = len(history_module._json_bytes(envelope_to_dict(event)))
    policy = HistoryWindowPolicy(
        max_bytes=size - 1,
        max_event_bytes=size - 1,
    )
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        assert observer.on_event(event) is RecordingStatus.DEGRADED
        assert observer.pending_event_count == 0
        assert observer.pending_bytes == 0
        replay = store.observer(record, HistoryContext("run-1", "host-1"))
        assert replay.on_event(event) is RecordingStatus.DEGRADED
        conflict = store.observer(record, HistoryContext("run-1", "host-1"))
        with pytest.raises(HistoryIntegrityError, match="another payload"):
            conflict.on_event(_envelope(record, 1, _item(2)))
        later = _envelope(record, 2, PhaseChanged("execute"))
        assert observer.on_event(later) is RecordingStatus.OK
        assert (
            observer.finalize(OperationResult(SessionState.COMPLETED))
            is RecordingStatus.DEGRADED
        )
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-1")
            page = repository.get_event_page("run-1")

    assert summary.last_committed_seq == 2
    assert summary.item_count == 0
    assert summary.rejected_event_count == 1
    assert summary.audit is RecordingStatus.DEGRADED
    assert page.events[0].envelope is None
    assert page.events[0].rejection_reason == history_module.EVENT_TOO_LARGE
    assert page.events[1].envelope == later


def test_oversized_item_reuse_still_enforces_semantic_identity(
    tmp_path: Path,
) -> None:
    record = _record()
    original = _item(1)
    changed = replace(original, detail={"message": "x" * 2_000})
    policy = HistoryWindowPolicy(
        max_events=1,
        max_bytes=512,
        max_event_bytes=512,
    )
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-oversized-conflict", "host-1")
        )
        observer.on_event(_envelope(record, 1, original))

        with pytest.raises(HistoryIntegrityError, match="identity was reused"):
            observer.on_event(_envelope(record, 2, changed))

        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-oversized-conflict")

    assert summary.item_count == 1
    assert summary.rejected_event_count == 0


def test_rejected_oversized_item_still_guards_later_identity_reuse(
    tmp_path: Path,
) -> None:
    record = _record()
    first = replace(_item(1), detail={"message": "x" * 2_000})
    changed = _item(1, Outcome.FAILED)
    policy = HistoryWindowPolicy(
        max_events=1,
        max_bytes=512,
        max_event_bytes=512,
    )
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-rejected-conflict", "host-1")
        )
        assert (
            observer.on_event(_envelope(record, 1, first))
            is RecordingStatus.DEGRADED
        )
        with pytest.raises(HistoryIntegrityError, match="identity was reused"):
            observer.on_event(_envelope(record, 2, changed))

        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-rejected-conflict")

    assert summary.item_count == 0
    assert summary.rejected_event_count == 1


def test_rejected_first_exact_reuse_is_a_bounded_noncounting_duplicate(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    context = HistoryContext("run-rejected-repeat", "host-1")
    item = replace(_item(1), detail={"message": "x" * 2_000})
    low_policy = HistoryWindowPolicy(
        max_events=1,
        max_bytes=512,
        max_event_bytes=512,
    )
    with HistoryStore(
        path,
        clock=FakeClock(),
        window_policy=low_policy,
    ) as store:
        observer = store.observer(record, context)
        for seq in range(1, 33):
            assert (
                observer.on_event(_envelope(record, seq, item))
                is RecordingStatus.DEGRADED
            )

    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, context)
        assert observer.on_event(_envelope(record, 33, item)) is RecordingStatus.OK
        assert (
            observer.finalize(OperationResult(SessionState.COMPLETED))
            is RecordingStatus.DEGRADED
        )
        with HistoryRepository(path) as repository:
            summary = repository.get_summary(context.run_token)
            events = repository.get_event_page(context.run_token)
            items = repository.get_item_page(context.run_token)

    assert summary.item_count == 0
    assert summary.duplicate_item_count == 1
    assert summary.rejected_event_count == 32
    assert items.items == ()
    assert events.events[0].duplicate_of_seq is None
    assert all(
        event.duplicate_of_seq == 1 for event in events.events[1:32]
    )
    assert (
        events.events[-1].disposition
        is history_module.HistoryEventDisposition.DUPLICATE
    )
    assert events.events[-1].duplicate_of_seq == 1


def test_duplicate_page_authenticates_a_linked_rejected_receipt(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    context = HistoryContext("run-rejected-link", "host-1")
    item = replace(_item(1), detail={"message": "x" * 2_000})
    with HistoryStore(
        path,
        clock=FakeClock(),
        window_policy=HistoryWindowPolicy(max_bytes=512, max_event_bytes=512),
    ) as store:
        store.observer(record, context).on_event(_envelope(record, 1, item))
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.on_event(_envelope(record, 2, item))
        observer.flush()

    connection = connect_history_writer(path)
    try:
        _allow_history_event_updates(connection)
        connection.execute(
            """UPDATE history_events
                  SET event_at = '2026-01-02T03:04:06.123456Z'
                WHERE event_seq = 1"""
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="receipt hash"):
            repository.get_event_page(context.run_token, after_seq=1)


def test_oversized_exact_item_reuse_remains_a_contained_rejection(
    tmp_path: Path,
) -> None:
    record = _record()
    item = _item(1)
    canonical = _envelope(record, 9, item)
    oversized = _envelope(record, 10, item)
    bound = len(history_module._json_bytes(envelope_to_dict(canonical)))
    assert len(history_module._json_bytes(envelope_to_dict(oversized))) > bound
    policy = HistoryWindowPolicy(
        max_events=1,
        max_bytes=bound,
        max_event_bytes=bound,
    )
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-oversized-repeat", "host-1")
        )
        assert observer.on_event(canonical) is RecordingStatus.OK
        assert observer.on_event(oversized) is RecordingStatus.DEGRADED
        observer.finalize(OperationResult(SessionState.COMPLETED, items=(item,)))

        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-oversized-repeat")
            events = repository.get_event_page("run-oversized-repeat")

    assert summary.item_count == 1
    assert summary.duplicate_item_count == 0
    assert summary.rejected_event_count == 1
    assert events.events[-1].disposition.value == "rejected"
    assert events.events[-1].duplicate_of_seq == 9


def test_pause_barrier_and_clean_close_flush_the_pending_prefix(tmp_path: Path) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        paused = store.observer(
            record, HistoryContext("run-paused", "host-1")
        )
        paused.on_event(
            _envelope(record, 1, StateChanged(SessionState.PAUSED))
        )
        with HistoryRepository(store.path) as repository:
            paused_summary = repository.get_summary("run-paused")
        assert paused_summary.current_state is SessionState.PAUSED

        closed = store.observer(
            _record("session-close"), HistoryContext("run-close", "host-1")
        )
        closed.on_event(_envelope(_record("session-close"), 1, _item(1)))
        closed.close()
        closed.close()

        with HistoryRepository(store.path) as repository:
            assert (
                repository.get_summary("run-paused").current_state
                is SessionState.PAUSED
            )
            assert repository.get_summary("run-close").last_committed_seq == 1


def test_crash_loses_only_the_uncommitted_tail_window(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    policy = HistoryWindowPolicy(max_events=2)
    record = _record()
    store = HistoryStore(path, clock=FakeClock(), window_policy=policy)
    observer = store.observer(record, HistoryContext("run-1", "host-1"))
    observer.on_event(_envelope(record, 1, _item(1)))
    observer.on_event(_envelope(record, 2, _item(2)))
    observer.on_event(_envelope(record, 3, _item(3)))
    assert observer.pending_event_count == 1
    store.close()

    with HistoryRepository(path) as repository:
        summary = repository.get_summary("run-1")
        page = repository.get_item_page("run-1")
    assert not summary.finalized
    assert summary.last_committed_seq == 2
    assert summary.item_count == 2
    assert [snapshot.item.item_id for snapshot in page.items] == ["op-1", "op-2"]


def test_failed_finalization_rolls_back_tail_and_keeps_pending_window(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    policy = HistoryWindowPolicy(max_events=2)
    record = _record()
    result = OperationResult(SessionState.COMPLETED, items=(_item(1), _item(2), _item(3)))
    with HistoryStore(path, clock=FakeClock(), window_policy=policy) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.on_event(_envelope(record, 2, _item(2)))
        observer.on_event(_envelope(record, 3, _item(3)))
        pending_count = observer.pending_event_count
        pending_bytes = observer.pending_bytes
        pending_events = tuple(observer._pending)
        pending_hashes = dict(observer._event_hashes)

        connection = connect_history_writer(path)
        try:
            connection.executescript(
                """CREATE TRIGGER reject_history_terminal
                   BEFORE UPDATE OF terminal_payload_hash ON history_runs
                   WHEN NEW.terminal_payload_hash IS NOT NULL
                   BEGIN
                       SELECT RAISE(ABORT, 'terminal write rejected');
                   END;"""
            )
        finally:
            connection.close()

        with pytest.raises(RecordingError, match="terminal write rejected"):
            observer.finalize(result)
        assert observer.pending_event_count == pending_count == 1
        assert observer.pending_bytes == pending_bytes
        assert tuple(observer._pending) == pending_events
        assert observer._event_hashes == pending_hashes
        with HistoryRepository(path) as repository:
            summary = repository.get_summary("run-1")
            items = repository.get_item_page("run-1")

    assert not summary.finalized
    assert summary.last_committed_seq == 2
    assert summary.item_count == 2
    assert [item.event_seq for item in items.items] == [1, 2]
    assert result.status is SessionState.COMPLETED
    assert result.audit is RecordingStatus.OK


def test_failed_window_commit_is_absent_and_keeps_its_bounded_pending_data(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    policy = HistoryWindowPolicy(max_events=1)
    with HistoryStore(path, clock=FakeClock(), window_policy=policy) as store:
        connection = connect_history_writer(path)
        try:
            connection.executescript(
                """CREATE TRIGGER reject_history_event
                   BEFORE INSERT ON history_events
                   BEGIN
                       SELECT RAISE(ABORT, 'event write rejected');
                   END;"""
            )
        finally:
            connection.close()

        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        with pytest.raises(RecordingError, match="event write rejected"):
            observer.on_event(_envelope(record, 1, _item(1)))

        assert observer.pending_event_count == 1
        assert 0 < observer.pending_bytes <= policy.max_bytes
        with HistoryRepository(path) as repository:
            with pytest.raises(KeyError):
                repository.get_summary("run-1")


def test_durable_duplicates_are_idempotent_but_conflicts_and_late_events_fail(
    tmp_path: Path,
) -> None:
    record = _record()
    context = HistoryContext("run-1", "host-1")
    policy = HistoryWindowPolicy(max_events=1)
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(record, context)
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.on_event(_envelope(record, 3, _item(3)))
        observer.on_event(_envelope(record, 1, _item(1)))

        late = store.observer(record, context)
        with pytest.raises(HistoryIntegrityError, match="out of order"):
            late.on_event(_envelope(record, 2, _item(2)))

        conflict = store.observer(record, context)
        with pytest.raises(HistoryIntegrityError, match="another payload"):
            conflict.on_event(
                _envelope(record, 1, _item(1, Outcome.FAILED))
            )

        with HistoryRepository(store.path) as repository:
            page = repository.get_event_page("run-1")
    assert [event.event_seq for event in page.events] == [1, 3]


@pytest.mark.parametrize(
    "max_events",
    (1, 256),
    ids=("durable-canonical", "same-window-canonical"),
)
def test_new_sequence_exact_item_duplicate_is_a_noncounting_receipt(
    tmp_path: Path, max_events: int,
) -> None:
    record = _record()
    item = _item(1)
    with HistoryStore(
        tmp_path / "history.db",
        clock=FakeClock(),
        window_policy=HistoryWindowPolicy(max_events=max_events),
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-duplicate", "host-1")
        )
        assert observer.on_event(_envelope(record, 1, item)) is RecordingStatus.OK
        assert observer.on_event(_envelope(record, 2, item)) is RecordingStatus.OK
        assert (
            observer.on_event(_envelope(record, 3, PhaseChanged("verify")))
            is RecordingStatus.OK
        )
        assert (
            observer.finalize(
                OperationResult(SessionState.COMPLETED, items=(item,))
            )
            is RecordingStatus.OK
        )

        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-duplicate")
            items = repository.get_item_page("run-duplicate")
            events = repository.get_event_page("run-duplicate")

    assert summary.last_committed_seq == 3
    assert summary.item_count == 1
    assert summary.duplicate_item_count == 1
    assert summary.rejected_event_count == 0
    assert summary.succeeded_count == 1
    assert summary.audit is RecordingStatus.OK
    assert len(items.items) == 1
    assert [event.disposition.value for event in events.events] == [
        "recorded",
        "duplicate",
        "recorded",
    ]
    assert events.events[1].duplicate_of_seq == 1
    assert events.events[1].envelope is not None
    assert events.events[1].envelope.body == item


def test_new_sequence_conflicting_item_identity_breaks_the_prefix(
    tmp_path: Path,
) -> None:
    record = _record()
    original = _item(1)
    changed = replace(original, detail={"bytes": 99})
    policy = HistoryWindowPolicy(max_events=1)
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-conflict", "host-1")
        )
        observer.on_event(_envelope(record, 1, original))
        with pytest.raises(HistoryIntegrityError, match="identity was reused"):
            observer.on_event(_envelope(record, 2, changed))
        with pytest.raises(HistoryIntegrityError, match="observer is degraded"):
            observer.on_event(_envelope(record, 3, PhaseChanged("verify")))
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-conflict")
            events = repository.get_event_page("run-conflict")

    assert summary.last_committed_seq == 1
    assert summary.item_count == 1
    assert summary.duplicate_item_count == 0
    assert [event.event_seq for event in events.events] == [1]


def test_same_window_conflicting_item_identity_rolls_back_the_window(
    tmp_path: Path,
) -> None:
    record = _record()
    original = _item(1)
    changed = replace(original, reason="changed-semantics")
    with HistoryStore(
        tmp_path / "history-same-window-conflict.db",
        clock=FakeClock(),
        window_policy=HistoryWindowPolicy(max_events=2),
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-same-window-conflict", "host-1")
        )
        observer.on_event(_envelope(record, 1, original))
        with pytest.raises(HistoryIntegrityError, match="identity was reused"):
            observer.on_event(_envelope(record, 2, changed))
        assert observer.pending_event_count == 2
        with HistoryRepository(store.path) as repository:
            with pytest.raises(KeyError):
                repository.get_summary("run-same-window-conflict")


def test_replay_lookup_retries_transient_busy_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _record()
    path = tmp_path / "history.db"
    with HistoryStore(
        path,
        clock=FakeClock(),
        retry_timeout_seconds=0.1,
        retry_interval_seconds=0,
        window_policy=HistoryWindowPolicy(max_events=1),
    ) as store:
        observer = store.observer(record, HistoryContext("run-retry", "host-1"))
        event = _envelope(record, 1, _item(1))
        observer.on_event(event)
        connect = history_module.connect_history_reader
        attempts = 0

        def transient(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise sqlite3.OperationalError("database is locked")
            return connect(*args, **kwargs)

        monkeypatch.setattr(history_module, "connect_history_reader", transient)
        assert observer.on_event(event) is RecordingStatus.OK

    assert attempts == 2


@pytest.mark.parametrize(
    ("error_message", "expected"),
    (
        ("database is locked", "remained busy"),
        ("disk I/O error", "disk I/O error"),
    ),
)
def test_replay_lookup_exhaustion_or_nonretryable_read_is_fail_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_message: str,
    expected: str,
) -> None:
    record = _record()
    path = tmp_path / f"history-{error_message[:4]}.db"
    with HistoryStore(
        path,
        clock=FakeClock(),
        retry_timeout_seconds=0,
        retry_interval_seconds=0,
        window_policy=HistoryWindowPolicy(max_events=1),
    ) as store:
        observer = store.observer(record, HistoryContext("run-read-fail", "host-1"))
        event = _envelope(record, 1, _item(1))
        observer.on_event(event)
        connect = history_module.connect_history_reader

        def fail(*args, **kwargs):
            raise sqlite3.OperationalError(error_message)

        monkeypatch.setattr(history_module, "connect_history_reader", fail)
        with pytest.raises(RecordingError, match=expected):
            observer.on_event(event)
        with pytest.raises(HistoryIntegrityError, match="observer is degraded"):
            observer.on_event(_envelope(record, 2, PhaseChanged("verify")))
        monkeypatch.setattr(history_module, "connect_history_reader", connect)
        with HistoryRepository(path) as repository:
            summary = repository.get_summary("run-read-fail")

    assert summary.last_committed_seq == 1
    assert summary.item_count == 1


def test_oversized_final_tail_receipt_still_allows_terminal_commit(
    tmp_path: Path,
) -> None:
    record = _record()
    oversized = _envelope(
        record,
        2,
        ItemOutcome(
            "oversized-item",
            "copy",
            "large.bin",
            Outcome.SUCCEEDED,
            detail={"message": "x" * 2_000},
        ),
    )
    policy = HistoryWindowPolicy(max_bytes=512, max_event_bytes=512)
    result = OperationResult(SessionState.COMPLETED)
    with HistoryStore(
        tmp_path / "history-tail.db",
        clock=FakeClock(),
        window_policy=policy,
    ) as store:
        observer = store.observer(record, HistoryContext("run-tail", "host-1"))
        observer.on_event(_envelope(record, 1, PhaseChanged("execute")))
        assert observer.on_event(oversized) is RecordingStatus.DEGRADED
        assert (
            observer.finalize(result)
            is RecordingStatus.DEGRADED
        )
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-tail")
            events = repository.get_event_page("run-tail")

    assert summary.last_committed_seq == 2
    assert summary.rejected_event_count == 1
    assert summary.audit is RecordingStatus.DEGRADED
    assert result.audit is RecordingStatus.OK
    assert events.events[-1].envelope is None
    assert events.events[-1].rejection_reason == history_module.EVENT_TOO_LARGE


def test_repeated_finalization_and_cross_observer_replay_are_idempotent(
    tmp_path: Path,
) -> None:
    record = _record()
    context = HistoryContext("run-1", "host-1")
    item = _item(1)
    result = OperationResult(SessionState.COMPLETED, items=(item,))
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.on_event(_envelope(record, 1, item))
        observer.finalize(result)
        observer.finalize(result)
        with pytest.raises(TokenConflictError):
            observer.finalize(replace(result, audit=RecordingStatus.DEGRADED))

        replay = store.observer(record, context)
        replay.on_event(_envelope(record, 1, item))
        replay.finalize(result)


def test_compound_cancellation_preserves_canceled_lifecycle_and_filesystem_axis(
    tmp_path: Path,
) -> None:
    record = _record()
    result = OperationResult(
        SessionState.COMPLETED,
        canceled=True,
        phases=(
            PhaseResult("execute", PhaseStatus.COMPLETED, 1, 1, 1, 1),
            PhaseResult("verify", PhaseStatus.CANCELED, 0, 1, 0, 1),
        ),
        bytes_done=1,
        bytes_total=1,
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.finalize(result)
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-1")

    assert summary.current_state is SessionState.CANCELED
    assert summary.filesystem_status is SessionState.COMPLETED
    assert summary.canceled is True


def test_unrun_finalization_preserves_absent_start_time(tmp_path: Path) -> None:
    record = _record()
    result = OperationResult(
        SessionState.CANCELED,
        disposition=Disposition.UNRUN,
        canceled=True,
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(
            record, HistoryContext("run-unrun", "host-1")
        )
        observer.finalize(result)
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-unrun")

    assert summary.finalized
    assert summary.current_state is SessionState.CANCELED
    assert summary.disposition == Disposition.UNRUN.value
    assert summary.started_at is None
    assert summary.ended_at == NOW


def test_reopened_zero_event_finalization_is_idempotent_after_clock_regression(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    context = HistoryContext("run-unrun", "host-1")
    result = OperationResult(
        SessionState.CANCELED,
        disposition=Disposition.UNRUN,
        canceled=True,
    )
    with HistoryStore(path, clock=FakeClock()) as store:
        store.observer(record, context).finalize(result)

    regressed = FakeClock(NOW - timedelta(seconds=1))
    with HistoryStore(path, clock=regressed) as store:
        store.observer(record, context).finalize(result)
        with HistoryRepository(path) as repository:
            summary = repository.get_summary("run-unrun")

    assert summary.started_at is None
    assert summary.ended_at == NOW


def test_stale_concurrent_observers_accept_exact_replay_and_reject_reordering(
    tmp_path: Path,
) -> None:
    record = _record()
    context = HistoryContext("run-1", "host-1")
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        first = store.observer(record, context)
        exact = store.observer(record, context)
        reordered = store.observer(record, context)
        first.on_event(_envelope(record, 1, _item(1)))
        first.on_event(_envelope(record, 3, _item(3)))
        exact.on_event(_envelope(record, 1, _item(1)))
        exact.on_event(_envelope(record, 3, _item(3)))
        reordered.on_event(_envelope(record, 1, _item(1)))
        reordered.on_event(_envelope(record, 2, _item(2)))

        first.flush()
        exact.flush()
        with pytest.raises(HistoryIntegrityError, match="out of order"):
            reordered.flush()

        with HistoryRepository(store.path) as repository:
            assert [
                event.event_seq
                for event in repository.get_event_page("run-1").events
            ] == [1, 3]


def test_commit_timestamp_is_sampled_under_writer_ownership_and_never_regresses(
    tmp_path: Path,
) -> None:
    class GuardedClock:
        def __init__(self) -> None:
            self.values = [
                NOW + timedelta(seconds=2),
                NOW + timedelta(seconds=1),
                NOW,
            ]
            self.writer_owned = False

        def now(self):
            assert self.writer_owned, "history sampled time before writer ownership"
            return self.values.pop(0)

    clock = GuardedClock()
    record = _record()
    context = HistoryContext("run-timestamps", "host-1")
    with HistoryStore(tmp_path / "history.db", clock=clock) as store:
        original_transact = store._writer.transact

        def tracked_transact(operation):
            def writer_owned(connection):
                clock.writer_owned = True
                try:
                    return operation(connection)
                finally:
                    clock.writer_owned = False

            return original_transact(writer_owned)

        store._writer.transact = tracked_transact

        # Both observers admit against the same empty durable state. Their
        # flush order advances the watermark while the supplied wall clock
        # moves backward, reproducing the stale-observer interleaving.
        first = store.observer(record, context)
        second = store.observer(record, context)
        first.on_event(_envelope(record, 1, _item(1)))
        second.on_event(_envelope(record, 2, _item(2)))
        first.flush()
        second.flush()

        with HistoryRepository(store.path) as repository:
            after_second = repository.get_summary("run-timestamps")
        assert after_second.last_committed_seq == 2
        assert after_second.last_committed_at == NOW + timedelta(seconds=2)

        second.on_event(_envelope(record, 3, _item(3)))
        second.finalize(OperationResult(SessionState.COMPLETED))
        with HistoryRepository(store.path) as repository:
            finalized = repository.get_summary("run-timestamps")

    assert clock.values == []
    assert finalized.last_committed_seq == 3
    assert finalized.last_committed_at == NOW + timedelta(seconds=2)
    assert finalized.ended_at == finalized.last_committed_at


def test_first_commit_clamps_clock_rollback_to_the_observed_start(
    tmp_path: Path,
) -> None:
    record = _record()
    started_at = NOW + timedelta(seconds=2)
    running = Envelope(
        record.session_id,
        1,
        started_at,
        SCHEMA_VERSION,
        StateChanged(SessionState.RUNNING),
    )
    with HistoryStore(
        tmp_path / "history.db",
        clock=FakeClock(NOW + timedelta(seconds=1)),
    ) as store:
        observer = store.observer(
            record, HistoryContext("run-clock-rollback", "host-1")
        )
        observer.on_event(running)
        observer.finalize(OperationResult(SessionState.COMPLETED))
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-clock-rollback")

    assert summary.started_at == started_at
    assert summary.last_committed_at == started_at
    assert summary.ended_at == started_at


@pytest.mark.parametrize(
    "body",
    (
        PhaseChanged("verify"),
        _item(2),
    ),
)
def test_later_event_timestamp_bounds_commit_and_terminal_time_during_rollback(
    tmp_path: Path,
    body: object,
) -> None:
    clock = FakeClock(NOW + timedelta(seconds=2))
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=clock) as store:
        observer = store.observer(
            record, HistoryContext("run-later-event", "host-1")
        )
        observer.on_event(
            Envelope(
                record.session_id,
                1,
                NOW + timedelta(seconds=1),
                SCHEMA_VERSION,
                StateChanged(SessionState.RUNNING),
            )
        )
        observer.flush()

        event_at = NOW + timedelta(seconds=10)
        observer.on_event(
            Envelope(record.session_id, 2, event_at, SCHEMA_VERSION, body)
        )
        clock.value = NOW + timedelta(seconds=3)
        observer.finalize(OperationResult(SessionState.COMPLETED))
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-later-event")

    assert summary.last_committed_at == event_at
    assert summary.ended_at == event_at


def test_context_token_conflict_is_rejected_before_new_events(tmp_path: Path) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        first = store.observer(record, HistoryContext("run-1", "host-1"))
        first.on_event(_envelope(record, 1, _item(1)))
        first.flush()
        with pytest.raises(TokenConflictError, match="context changed"):
            store.observer(record, HistoryContext("run-1", "host-2"))


def test_item_and_event_pages_use_fixed_keyset_watermarks(tmp_path: Path) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        for seq in range(1, 6):
            observer.on_event(_envelope(record, seq, _item(seq)))
        observer.flush()

        with HistoryRepository(store.path) as repository:
            first_items = repository.get_item_page("run-1", limit=2)
            first_events = repository.get_event_page("run-1", limit=2)
            assert first_items.through_order == 5
            assert first_events.through_seq == 5

            observer.on_event(_envelope(record, 6, _item(6)))
            observer.flush()

            second_items = repository.get_item_page(
                "run-1",
                after_order=first_items.next_after_order,
                through_order=first_items.through_order,
                limit=MAX_HISTORY_PAGE_SIZE,
            )
            second_events = repository.get_event_page(
                "run-1",
                after_seq=first_events.next_after_seq,
                through_seq=first_events.through_seq,
                limit=MAX_HISTORY_PAGE_SIZE,
            )
            latest = repository.get_item_page("run-1")

    assert [item.item_order for item in first_items.items] == [1, 2]
    assert [item.item_order for item in second_items.items] == [3, 4, 5]
    assert not second_items.has_more
    assert [event.event_seq for event in second_events.events] == [3, 4, 5]
    assert latest.through_order == 6
    assert latest.items[-1].item_order == 6


def test_fresh_event_traversal_can_start_ahead_of_durability(
    tmp_path: Path,
) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, PhaseChanged("scan")))
        observer.flush()

        with HistoryRepository(store.path) as repository:
            ahead = repository.get_event_page("run-1", after_seq=2)

            observer.on_event(_envelope(record, 3, PhaseChanged("execute")))
            observer.flush()

            caught_up = repository.get_event_page("run-1", after_seq=2)
            with pytest.raises(ValueError, match="cursor exceeds"):
                repository.get_event_page(
                    "run-1",
                    after_seq=ahead.next_after_seq,
                    through_seq=ahead.through_seq,
                )

    assert ahead.through_seq == 1
    assert ahead.next_after_seq == 2
    assert ahead.events == ()
    assert not ahead.has_more
    assert caught_up.through_seq == 3
    assert caught_up.next_after_seq == 3
    assert [event.event_seq for event in caught_up.events] == [3]
    assert not caught_up.has_more


@pytest.mark.parametrize("limit", [0, 257])
def test_read_limits_reject_unbounded_requests(tmp_path: Path, limit: int) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
        with HistoryRepository(store.path) as repository:
            with pytest.raises(ValueError):
                repository.list_summaries(limit)
            with pytest.raises(ValueError):
                repository.get_item_page("run-1", limit=limit)
            with pytest.raises(ValueError):
                repository.get_event_page("run-1", limit=limit)


def test_read_limits_accept_one_and_256(tmp_path: Path) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
        with HistoryRepository(store.path) as repository:
            assert len(repository.list_summaries(1)) == 1
            assert len(repository.list_summaries(256)) == 1
            assert len(repository.get_item_page("run-1", limit=1).items) == 1
            assert len(repository.get_item_page("run-1", limit=256).items) == 1
            assert len(repository.get_event_page("run-1", limit=1).events) == 1
            assert len(repository.get_event_page("run-1", limit=256).events) == 1


def test_pages_decode_no_more_than_the_requested_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        for sequence in range(1, 5):
            observer.on_event(_envelope(record, sequence, _item(sequence)))
        observer.flush()

        original = history_module._history_event
        decoded: list[int] = []

        def counted(row, expected_session_id):
            decoded.append(int(row["event_seq"]))
            return original(row, expected_session_id)

        monkeypatch.setattr(history_module, "_history_event", counted)
        with HistoryRepository(store.path) as repository:
            item_page = repository.get_item_page("run-1", limit=2)
            assert len(item_page.items) == 2
            assert len(decoded) == 2

            decoded.clear()
            event_page = repository.get_event_page("run-1", limit=2)
            assert len(event_page.events) == 2
            assert len(decoded) == 2
            assert event_page.has_more


def test_summary_listing_uses_fixed_queries_and_never_decodes_event_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "history.db"
    with HistoryStore(path, clock=FakeClock()) as store:
        for index in range(3):
            record = _record(f"session-{index}")
            observer = store.observer(
                record, HistoryContext(f"run-{index}", "host-1")
            )
            observer.on_event(_envelope(record, 1, _item(index + 1)))
            observer.finalize(OperationResult(SessionState.COMPLETED))

    def reject_decode(_raw):
        raise AssertionError("summary listing decoded an event payload")

    monkeypatch.setattr(history_module, "envelope_from_dict", reject_decode)
    with HistoryRepository(path) as repository:
        statements: list[str] = []
        repository._connection.set_trace_callback(statements.append)
        summaries = repository.list_summaries(3)
    selects = [
        statement
        for statement in statements
        if statement.startswith(("SELECT", "WITH"))
    ]
    assert len(summaries) == 3
    assert len(selects) == 3


def test_event_pages_round_trip_nonitem_reliable_events_and_sequence_gaps(
    tmp_path: Path,
) -> None:
    record = _record()
    bodies = (
        StateChanged(SessionState.RUNNING),
        PhaseChanged("scan"),
        Gap(4),
    )
    sequences = (1, 3, 5)
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        for sequence, body in zip(sequences, bodies, strict=True):
            observer.on_event(_envelope(record, sequence, body))
        observer.flush()
        with HistoryRepository(store.path) as repository:
            page = repository.get_event_page("run-1")
            first = repository.get_event_page(
                "run-1", through_seq=4, limit=1
            )
            second = repository.get_event_page(
                "run-1",
                after_seq=first.next_after_seq,
                through_seq=first.through_seq,
                limit=1,
            )
            before_history = repository.get_event_page(
                "run-1", through_seq=0
            )
    assert [event.event_seq for event in page.events] == list(sequences)
    assert [event.envelope.body for event in page.events] == list(bodies)
    assert [event.event_seq for event in first.events] == [1]
    assert first.through_seq == 4
    assert first.has_more
    assert [event.event_seq for event in second.events] == [3]
    assert second.next_after_seq == 3
    assert second.through_seq == 4
    assert not second.has_more
    assert before_history.events == ()
    assert before_history.next_after_seq == 0
    assert before_history.through_seq == 0
    assert not before_history.has_more


def test_event_readback_detects_payload_tampering(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        _allow_history_event_updates(connection)
        connection.execute(
            "UPDATE history_events SET envelope_json = envelope_json || ' '")
    finally:
        connection.close()
    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="payload hash"):
            repository.get_event_page("run-1")


def test_history_event_rows_are_append_only_and_item_projections_are_validated(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-guarded", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute(
                "UPDATE history_events SET envelope_json = envelope_json"
            )
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute("DELETE FROM history_events")
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute(
                "INSERT INTO history_events(result) VALUES ('failed')"
            )
        _allow_history_event_updates(connection)
        connection.execute("UPDATE history_events SET result = 'failed'")
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="columns disagree"):
            repository.get_event_page("run-guarded")


def test_replace_cannot_overwrite_a_durable_history_event(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    item = _item(1)
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-replace", "host-1"))
        observer.on_event(_envelope(record, 1, item))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute("PRAGMA recursive_triggers = OFF")
        with pytest.raises(sqlite3.IntegrityError, match="writable tail"):
            connection.execute(
                """INSERT OR REPLACE INTO history_events(
                       run_id, event_seq, event_at, schema_version, body_type,
                       event_disposition, envelope_json, payload_hash,
                       receipt_hash, item_identity_hash, item_payload_hash,
                       duplicate_of_seq, rejection_reason, item_order,
                       item_type, phase, item_id, kind, path, result, reason
                   ) SELECT run_id, event_seq, event_at, schema_version,
                            body_type, event_disposition, envelope_json,
                            payload_hash, receipt_hash, item_identity_hash,
                            item_payload_hash, duplicate_of_seq,
                            rejection_reason, item_order, item_type, phase,
                            item_id, kind, path, result, reason
                       FROM history_events WHERE event_seq = 1"""
            )
        with pytest.raises(sqlite3.OperationalError, match="rowid"):
            connection.execute(
                """INSERT OR REPLACE INTO history_events(
                       rowid, run_id, event_seq, event_at, schema_version,
                       body_type, event_disposition, envelope_json,
                       payload_hash, receipt_hash, item_identity_hash,
                       item_payload_hash, duplicate_of_seq, rejection_reason,
                       item_order, item_type, phase, item_id, kind, path,
                       result, reason
                   ) SELECT rowid, run_id, event_seq + 1, event_at,
                            schema_version, body_type, event_disposition,
                            envelope_json, payload_hash, receipt_hash,
                            item_identity_hash, item_payload_hash,
                            duplicate_of_seq, rejection_reason, item_order + 1,
                            item_type, phase, item_id, kind, path, result, reason
                       FROM history_events WHERE event_seq = 1"""
            )
        with pytest.raises(sqlite3.IntegrityError, match="writable tail"):
            connection.execute(
                """INSERT OR REPLACE INTO history_events(
                       run_id, event_seq, event_at, schema_version, body_type,
                       event_disposition, envelope_json, payload_hash,
                       receipt_hash, item_identity_hash, item_payload_hash,
                       duplicate_of_seq, rejection_reason, item_order,
                       item_type, phase, item_id, kind, path, result, reason
                   ) SELECT run_id, event_seq + 1, event_at, schema_version,
                            body_type, event_disposition, envelope_json,
                            payload_hash, receipt_hash, zeroblob(32),
                            item_payload_hash, duplicate_of_seq,
                            rejection_reason, item_order + 1, item_type, phase,
                            item_id, kind, path, result, reason
                       FROM history_events WHERE event_seq = 1"""
            )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        assert repository.get_item_page("run-replace").items[0].item == item


def test_finalized_run_refuses_event_insert_reopen_delete_and_replace(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    context = HistoryContext("run-finalized", "host-1")
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.on_event(_envelope(record, 1, PhaseChanged("execute")))
        observer.finalize(OperationResult(SessionState.COMPLETED))
    connection = connect_history_writer(path)
    try:
        run_id = int(
            connection.execute(
                "SELECT id FROM history_runs WHERE run_token = 'run-finalized'"
            ).fetchone()["id"]
        )
        with pytest.raises(sqlite3.IntegrityError, match="writable tail"):
            _insert_history_event(
                connection,
                run_id,
                _envelope(record, 2, PhaseChanged("verify")),
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                """UPDATE history_runs
                      SET terminal_payload_hash = NULL, ended_at = NULL,
                          filesystem_status = NULL, recording_status = NULL,
                          audit_status = NULL, disposition = NULL,
                          canceled = NULL, bytes_done = NULL, bytes_total = NULL,
                          error_type = NULL, error_message = NULL
                    WHERE id = ?""",
                (run_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            connection.execute("DELETE FROM history_runs WHERE id = ?", (run_id,))
        connection.execute("PRAGMA recursive_triggers = OFF")
        with pytest.raises(sqlite3.IntegrityError, match="cannot be replaced"):
            connection.execute(
                "INSERT OR REPLACE INTO history_runs SELECT * FROM history_runs"
            )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        assert repository.get_summary("run-finalized").finalized


def test_incomplete_runs_refuse_delete_insert_replace_and_update_replace(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        for seq, token in enumerate(("run-first", "run-second"), 1):
            observer = store.observer(record, HistoryContext(token, "host-1"))
            observer.on_event(_envelope(record, seq, PhaseChanged(token)))
            observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute("PRAGMA recursive_triggers = OFF")
        with pytest.raises(sqlite3.IntegrityError, match="replace another run"):
            connection.execute(
                """UPDATE OR REPLACE history_runs SET run_token = 'run-second'
                    WHERE run_token = 'run-first'"""
            )
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            connection.execute(
                "DELETE FROM history_runs WHERE run_token = 'run-first'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="cannot be replaced"):
            connection.execute(
                """INSERT OR REPLACE INTO history_runs
                    SELECT * FROM history_runs WHERE run_token = 'run-first'"""
            )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        assert {summary.run_token for summary in repository.list_summaries()} == {
            "run-first",
            "run-second",
        }


def test_summary_rejects_an_uncommitted_external_event_tail(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-tail", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        run_id = int(connection.execute("SELECT id FROM history_runs").fetchone()["id"])
        _insert_history_event(
            connection,
            run_id,
            _envelope(record, 2, _item(2, Outcome.FAILED)),
            item_order=2,
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="watermark"):
            repository.get_summary("run-tail")
        with pytest.raises(HistoryIntegrityError, match="watermark"):
            repository.list_summaries()
        with pytest.raises(HistoryIntegrityError, match="watermark"):
            repository.get_item_page("run-tail")
        with pytest.raises(HistoryIntegrityError, match="watermark"):
            repository.get_event_page("run-tail")
    with HistoryStore(path, clock=FakeClock()) as store:
        with pytest.raises(HistoryIntegrityError, match="watermark"):
            store.observer(record, HistoryContext("run-tail", "host-1"))


def test_event_and_item_pages_validate_run_context(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-context", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute(
            "UPDATE history_runs SET session_id = 'forged-session'"
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="context hash"):
            repository.get_event_page("run-context")
        with pytest.raises(HistoryIntegrityError, match="context hash"):
            repository.get_item_page("run-context")


def test_event_and_item_pages_reject_envelope_session_misattribution(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-session", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        _allow_history_event_updates(connection)
        row = connection.execute(
            "SELECT * FROM history_events WHERE event_seq = 1"
        ).fetchone()
        raw = history_module.json.loads(str(row["envelope_json"]))
        raw["session_id"] = "forged-session"
        envelope_json = history_module._json_bytes(raw).decode("utf-8")
        payload_hash = history_module.hashlib.sha256(
            envelope_json.encode("utf-8")
        ).digest()
        receipt_hash = history_module._receipt_hash(
            event_seq=int(row["event_seq"]),
            event_at=str(row["event_at"]),
            schema_version=int(row["schema_version"]),
            body_type=str(row["body_type"]),
            disposition=history_module.HistoryEventDisposition.RECORDED,
            payload_hash=payload_hash,
            item_identity_hash=bytes(row["item_identity_hash"]),
            item_payload_hash=bytes(row["item_payload_hash"]),
            item_order=int(row["item_order"]),
        )
        connection.execute(
            """UPDATE history_events
                  SET envelope_json = ?, payload_hash = ?, receipt_hash = ?
                WHERE event_seq = 1""",
            (envelope_json, payload_hash, receipt_hash),
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="columns disagree"):
            repository.get_event_page("run-session")
        with pytest.raises(HistoryIntegrityError, match="columns disagree"):
            repository.get_item_page("run-session")


@pytest.mark.parametrize(
    "tamper_sql",
    (
        "UPDATE history_events SET event_at = "
        "'2026-01-02T03:04:06.123456Z' WHERE event_seq = 1",
        "UPDATE history_events SET schema_version = 2 WHERE event_seq = 1",
        "UPDATE history_events SET body_type = 'IntegrityOutcome' "
        "WHERE event_seq = 1",
        "UPDATE history_events SET event_seq = 2 WHERE event_seq = 1; "
        "UPDATE history_runs SET last_committed_seq = 2",
    ),
)
def test_rejected_receipt_binds_retained_event_metadata(
    tmp_path: Path,
    tamper_sql: str,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    event = _envelope(
        record,
        1,
        replace(_item(1), detail={"message": "x" * 2_000}),
    )
    with HistoryStore(
        path,
        clock=FakeClock(),
        window_policy=HistoryWindowPolicy(max_bytes=512, max_event_bytes=512),
    ) as store:
        observer = store.observer(record, HistoryContext("run-rejected", "host-1"))
        assert observer.on_event(event) is RecordingStatus.DEGRADED
    connection = connect_history_writer(path)
    try:
        _allow_history_event_updates(connection)
        connection.executescript(tamper_sql)
        if "last_committed_seq" in tamper_sql:
            run = connection.execute("SELECT * FROM history_runs").fetchone()
            connection.execute(
                "UPDATE history_runs SET prefix_projection_hash = ?",
                (history_module._prefix_projection_hash_from_row(run),),
            )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="receipt hash"):
            repository.get_event_page("run-rejected")


def test_replay_rejects_tampered_rejected_receipt_metadata(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    record = _record()
    event = _envelope(
        record,
        1,
        replace(_item(1), detail={"message": "x" * 2_000}),
    )
    with HistoryStore(
        path,
        clock=FakeClock(),
        window_policy=HistoryWindowPolicy(max_bytes=512, max_event_bytes=512),
    ) as store:
        observer = store.observer(record, HistoryContext("run-replay", "host-1"))
        observer.on_event(event)
        connection = connect_history_writer(path)
        try:
            _allow_history_event_updates(connection)
            connection.execute(
                "UPDATE history_events SET body_type = 'IntegrityOutcome'"
            )
        finally:
            connection.close()

        replay = store.observer(record, HistoryContext("run-replay", "host-1"))
        with pytest.raises(HistoryIntegrityError, match="receipt hash"):
            replay.on_event(event)


def test_item_page_rejects_item_order_tampering(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-order", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.on_event(_envelope(record, 2, _item(2)))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        _allow_history_event_updates(connection)
        connection.execute(
            "UPDATE history_events SET item_order = 3 WHERE event_seq = 1"
        )
        connection.execute(
            "UPDATE history_events SET item_order = 1 WHERE event_seq = 2"
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(
            HistoryIntegrityError, match="receipt hash|item watermark"
        ):
            repository.get_item_page("run-order")


def test_item_identity_hash_is_validated_against_the_envelope(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-identity", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        _allow_history_event_updates(connection)
        row = connection.execute(
            "SELECT * FROM history_events WHERE event_seq = 1"
        ).fetchone()
        altered_identity_hash = b"x" * 32
        receipt_hash = history_module._receipt_hash(
            event_seq=int(row["event_seq"]),
            event_at=str(row["event_at"]),
            schema_version=int(row["schema_version"]),
            body_type=str(row["body_type"]),
            disposition=history_module.HistoryEventDisposition.RECORDED,
            payload_hash=bytes(row["payload_hash"]),
            item_identity_hash=altered_identity_hash,
            item_payload_hash=bytes(row["item_payload_hash"]),
            item_order=int(row["item_order"]),
        )
        connection.execute(
            """UPDATE history_events
                  SET item_identity_hash = ?, receipt_hash = ?
                WHERE event_seq = 1""",
            (altered_identity_hash, receipt_hash),
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="identity hash"):
            repository.get_event_page("run-identity")


def test_summary_detects_receipt_counter_tampering(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    record = _record()
    item = _item(1)
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-counts", "host-1"))
        observer.on_event(_envelope(record, 1, item))
        observer.on_event(_envelope(record, 2, item))
        observer.finalize(OperationResult(SessionState.COMPLETED, items=(item,)))
    connection = connect_history_writer(path)
    try:
        _allow_finalized_run_updates(connection)
        connection.execute(
            """UPDATE history_runs SET duplicate_item_count = 0
                WHERE run_token = 'run-counts'"""
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(
            HistoryIntegrityError,
            match="receipt counts|payload hash|prefix projection",
        ):
            repository.get_summary("run-counts")


@pytest.mark.parametrize(
    "column",
    (
        "item_count",
        "succeeded_count",
        "skipped_count",
        "failed_count",
        "canceled_count",
        "deferred_count",
        "blocked_count",
    ),
)
def test_terminal_hash_binds_item_and_outcome_counts(
    tmp_path: Path,
    column: str,
) -> None:
    path = tmp_path / f"history-{column}.db"
    record = _record()
    items = tuple(_item(index + 1, outcome) for index, outcome in enumerate(Outcome))
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-count-hash", "host-1"))
        for seq, item in enumerate(items, 1):
            observer.on_event(_envelope(record, seq, item))
        observer.finalize(OperationResult(SessionState.COMPLETED, items=items))
    connection = connect_history_writer(path)
    try:
        _allow_finalized_run_updates(connection)
        connection.execute(
            f"UPDATE history_runs SET {column} = {column} + 1"
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(
            HistoryIntegrityError, match="payload hash|prefix projection"
        ):
            repository.get_summary("run-count-hash")


@pytest.mark.parametrize("column", ("item_count", "failed_count"))
def test_incomplete_summary_validates_item_and_outcome_counts(
    tmp_path: Path,
    column: str,
) -> None:
    path = tmp_path / f"history-incomplete-{column}.db"
    record = _record()
    item = _item(1, Outcome.FAILED)
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-incomplete", "host-1"))
        observer.on_event(_envelope(record, 1, item))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute(
            f"UPDATE history_runs SET {column} = {column} + 1"
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="prefix projection"):
            repository.get_summary("run-incomplete")


@pytest.mark.parametrize(
    "column",
    ("current_state", "current_phase", "started_at", "last_committed_at"),
)
def test_incomplete_summary_binds_derived_prefix_fields(
    tmp_path: Path,
    column: str,
) -> None:
    path = tmp_path / f"history-incomplete-{column}.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-prefix", "host-1"))
        observer.on_event(_envelope(record, 1, StateChanged(SessionState.RUNNING)))
        observer.on_event(_envelope(record, 2, PhaseChanged("execute")))
        observer.flush()
    values = {
        "current_state": "paused",
        "current_phase": "forged",
        "started_at": "2026-01-02T03:04:04.123456Z",
        "last_committed_at": "2026-01-02T03:04:06.123456Z",
    }
    connection = connect_history_writer(path)
    try:
        connection.execute(
            f"UPDATE history_runs SET {column} = ?",
            (values[column],),
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="prefix projection"):
            repository.get_summary("run-prefix")


def test_fresh_observer_rejects_a_tampered_incomplete_prefix(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    context = HistoryContext("run-prefix-replay", "host-1")
    event = _envelope(record, 1, PhaseChanged("execute"))
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.on_event(event)
        observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute("UPDATE history_runs SET current_phase = 'forged'")
    finally:
        connection.close()

    with HistoryStore(path, clock=FakeClock()) as store:
        with pytest.raises(HistoryIntegrityError, match="prefix projection"):
            store.observer(record, context)


def test_event_readback_validates_duplicate_link_against_canonical_item(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    first = _item(1)
    second = _item(2)
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-link", "host-1"))
        observer.on_event(_envelope(record, 1, first))
        observer.on_event(_envelope(record, 2, second))
        observer.on_event(_envelope(record, 3, first))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        row = connection.execute(
            """SELECT payload_hash, item_payload_hash FROM history_events
                WHERE event_seq = 3"""
        ).fetchone()
        receipt_hash = history_module._receipt_hash(
            event_seq=3,
            event_at=history_module.encode_utc(NOW),
            schema_version=SCHEMA_VERSION,
            body_type="ItemOutcome",
            disposition=history_module.HistoryEventDisposition.DUPLICATE,
            payload_hash=bytes(row["payload_hash"]),
            item_identity_hash=history_module._hash(
                {"item_type": first.item_type, "item_id": first.item_id}
            ),
            item_payload_hash=bytes(row["item_payload_hash"]),
            duplicate_of_seq=2,
        )
        _allow_history_event_updates(connection)
        connection.execute("DROP TRIGGER history_events_duplicate_link_update")
        connection.execute(
            """UPDATE history_events
                  SET duplicate_of_seq = 2, receipt_hash = ?
                WHERE event_seq = 3""",
            (receipt_hash,),
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="canonical item"):
            repository.get_event_page("run-link")


def test_page_readback_rejects_a_watermark_past_its_durable_rows(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, _item(1)))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute(
            """UPDATE history_runs
                  SET last_committed_seq = 2, item_count = 2
                WHERE run_token = 'run-1'"""
        )
        run = connection.execute("SELECT * FROM history_runs").fetchone()
        connection.execute(
            "UPDATE history_runs SET prefix_projection_hash = ?",
            (history_module._prefix_projection_hash_from_row(run),),
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="item watermark"):
            repository.get_item_page("run-1")
        with pytest.raises(HistoryIntegrityError, match="event watermark"):
            repository.get_event_page("run-1")
        with pytest.raises(HistoryIntegrityError, match="event watermark"):
            repository.get_event_page("run-1", through_seq=1)
        with pytest.raises(HistoryIntegrityError, match="event watermark"):
            repository.get_event_page("run-1", after_seq=3)


def test_event_page_rejects_rows_past_an_official_zero_watermark(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, PhaseChanged("scan")))
        observer.flush()
    connection = connect_history_writer(path)
    try:
        connection.execute(
            """UPDATE history_runs SET last_committed_seq = 0
                WHERE run_token = 'run-1'"""
        )
        run = connection.execute("SELECT * FROM history_runs").fetchone()
        connection.execute(
            "UPDATE history_runs SET prefix_projection_hash = ?",
            (history_module._prefix_projection_hash_from_row(run),),
        )
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="event watermark"):
            repository.get_event_page("run-1")


def test_event_page_accepts_an_official_zero_watermark(tmp_path: Path) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.finalize(OperationResult(SessionState.COMPLETED))
        with HistoryRepository(store.path) as repository:
            page = repository.get_event_page("run-1")

    assert page.through_seq == 0
    assert page.next_after_seq == 0
    assert page.events == ()
    assert not page.has_more


def test_history_sequence_admission_does_not_scan_prior_hashes(tmp_path: Path) -> None:
    class NonIterableHashes(dict[int, bytes]):
        def __iter__(self):
            raise AssertionError("sequence admission scanned all prior hashes")

        def keys(self):
            raise AssertionError("sequence admission scanned all prior hashes")

        def values(self):
            raise AssertionError("sequence admission scanned all prior hashes")

        def items(self):
            raise AssertionError("sequence admission scanned all prior hashes")

    record = _record()
    policy = HistoryWindowPolicy(max_events=256)
    with HistoryStore(
        tmp_path / "history.db", clock=FakeClock(), window_policy=policy
    ) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer._event_hashes = NonIterableHashes()
        for sequence in range(1, 101):
            observer.on_event(_envelope(record, sequence, _item(sequence)))
        assert observer._highest_event_seq == 100


def test_unpaired_surrogate_round_trips_through_canonical_event_json(
    tmp_path: Path,
) -> None:
    record = _record("session-hostile")
    hostile = "bad_\udcff"
    item = ItemOutcome(
        "op-hostile",
        "noop",
        "safe.txt",
        Outcome.SKIPPED,
        detail={"message": hostile},
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(
            record, HistoryContext("run-hostile", "host-1")
        )
        observer.on_event(_envelope(record, 1, item))
        observer.finalize(OperationResult(SessionState.COMPLETED, items=(item,)))
        with HistoryRepository(store.path) as repository:
            page = repository.get_item_page("run-hostile")
    assert page.items[0].item == item


def test_summary_primitive_aggregates_cover_operation_and_integrity_results(
    tmp_path: Path,
) -> None:
    record = _record()
    blocked = _item(1, Outcome.BLOCKED)
    integrity = IntegrityOutcome(
        item_id="row-1",
        row_id="1",
        location_id="8",
        path="1.bin",
        result=IntegrityResult.MISMATCHED,
        reason=IntegrityReason.HASH_MISMATCH,
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        observer.on_event(_envelope(record, 1, blocked))
        observer.on_event(_envelope(record, 2, integrity))
        observer.finalize(
            OperationResult(SessionState.COMPLETED, items=(blocked, integrity))
        )
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-1")
    assert summary.blocked_count == 1
    assert summary.classification == HistoryClassificationAggregate(
        operation_results=frozenset({"blocked"}),
        selected_operation_count=1,
        selected_other_operation_count=1,
        integrity_results=frozenset({"mismatched"}),
        verify_phase_baseline=False,
    )


def test_summary_classification_objects_are_bounded_for_free_form_item_fields(
    tmp_path: Path,
) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-1", "host-1"))
        for sequence in range(1, 301):
            observer.on_event(
                _envelope(
                    record,
                    sequence,
                    ItemOutcome(
                        f"op-{sequence}",
                        f"kind-{sequence}",
                        f"{sequence}.bin",
                        Outcome.SKIPPED,
                        reason=f"reason-{sequence}",
                    ),
                )
            )
        observer.finalize(OperationResult(SessionState.COMPLETED))
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-1")

    assert summary.classification.operation_results == frozenset({"skipped"})
    assert summary.classification.selected_operation_count == 300
    assert summary.classification.selected_other_operation_count == 300


def test_terminal_phase_count_is_bounded_before_persistence(tmp_path: Path) -> None:
    accepted = tuple(
        PhaseResult(f"phase-{index}", PhaseStatus.COMPLETED, 0, 0, 0, 0)
        for index in range(MAX_HISTORY_PHASES)
    )
    rejected = tuple(
        PhaseResult(f"phase-{index}", PhaseStatus.COMPLETED, 0, 0, 0, 0)
        for index in range(MAX_HISTORY_PHASES + 1)
    )
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        allowed = store.observer(record, HistoryContext("run-allowed", "host-1"))
        allowed.finalize(
            OperationResult(SessionState.COMPLETED, phases=accepted)
        )
        observer = store.observer(record, HistoryContext("run-rejected", "host-1"))
        with pytest.raises(HistoryIntegrityError, match="terminal phases"):
            observer.finalize(
                OperationResult(SessionState.COMPLETED, phases=rejected)
            )
        with HistoryRepository(store.path) as repository:
            assert len(repository.get_summary("run-allowed").phases) == 256
            with pytest.raises(KeyError):
                repository.get_summary("run-rejected")


def test_terminal_summary_text_accepts_exact_utf8_byte_bounds(
    tmp_path: Path,
) -> None:
    phase = PhaseResult(
        "p" * MAX_HISTORY_PHASE_NAME_BYTES,
        PhaseStatus.FAILED,
        0,
        0,
        0,
        0,
        "\N{LATIN SMALL LETTER E WITH ACUTE}"
        * (MAX_HISTORY_ERROR_MESSAGE_BYTES // 2),
    )
    error = FailureDetail(
        "E" * MAX_HISTORY_ERROR_TYPE_BYTES,
        "\N{LATIN SMALL LETTER E WITH ACUTE}"
        * (MAX_HISTORY_ERROR_MESSAGE_BYTES // 2),
    )
    result = OperationResult(
        SessionState.FAILED,
        phases=(phase,),
        error=error,
    )
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        store.observer(
            record, HistoryContext("run-bounded", "host-1")
        ).finalize(result)
        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-bounded")

    assert summary.phases[0].phase == phase
    assert summary.error_type == error.type_name
    assert summary.error_message == error.message


@pytest.mark.parametrize(
    ("result", "message"),
    (
        (
            OperationResult(
                SessionState.FAILED,
                phases=(
                    PhaseResult(
                        "p" * (MAX_HISTORY_PHASE_NAME_BYTES + 1),
                        PhaseStatus.FAILED,
                        0,
                        0,
                        0,
                        0,
                    ),
                ),
            ),
            "terminal phase name",
        ),
        (
            OperationResult(
                SessionState.FAILED,
                phases=(
                    PhaseResult(
                        "execute",
                        PhaseStatus.FAILED,
                        0,
                        0,
                        0,
                        0,
                        "x" * (MAX_HISTORY_ERROR_MESSAGE_BYTES + 1),
                    ),
                ),
            ),
            "terminal phase error",
        ),
        (
            OperationResult(
                SessionState.FAILED,
                error=FailureDetail(
                    "E" * (MAX_HISTORY_ERROR_TYPE_BYTES + 1),
                    "failed",
                ),
            ),
            "terminal error type",
        ),
        (
            OperationResult(
                SessionState.FAILED,
                error=FailureDetail(
                    "Error",
                    "x" * (MAX_HISTORY_ERROR_MESSAGE_BYTES + 1),
                ),
            ),
            "terminal error message",
        ),
    ),
)
def test_oversized_terminal_summary_text_degrades_before_terminal_write(
    tmp_path: Path,
    result: OperationResult,
    message: str,
) -> None:
    record = _record()
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(
            record, HistoryContext("run-oversized", "host-1")
        )
        observer.on_event(
            _envelope(record, 1, StateChanged(SessionState.RUNNING))
        )
        observer.flush()

        with pytest.raises(HistoryIntegrityError, match=message):
            observer.finalize(result)

        with HistoryRepository(store.path) as repository:
            summary = repository.get_summary("run-oversized")

    assert not summary.finalized
    assert summary.last_committed_seq == 1
    assert summary.phases == ()


@pytest.mark.parametrize(
    "tamper_sql",
    (
        "UPDATE history_runs SET error_message = 'changed' "
        "WHERE run_token = 'run-tampered'",
        "UPDATE history_phases SET error = 'changed' WHERE phase_order = 0",
    ),
)
def test_summary_and_repeat_finalize_reject_tampered_terminal_payload(
    tmp_path: Path,
    tamper_sql: str,
) -> None:
    record = _record()
    context = HistoryContext("run-tampered", "host-1")
    result = OperationResult(
        SessionState.FAILED,
        phases=(
            PhaseResult(
                "execute",
                PhaseStatus.FAILED,
                0,
                0,
                0,
                0,
                "original phase failure",
            ),
        ),
        error=FailureDetail("OSError", "original terminal failure"),
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.finalize(result)
        connection = connect_history_writer(store.path)
        try:
            _allow_finalized_run_updates(connection)
            connection.execute(tamper_sql)
        finally:
            connection.close()

        with HistoryRepository(store.path) as repository:
            with pytest.raises(
                HistoryIntegrityError, match="payload hash disagrees"
            ):
                repository.get_summary("run-tampered")
            with pytest.raises(
                HistoryIntegrityError, match="payload hash disagrees"
            ):
                repository.list_summaries()

        with pytest.raises(
            HistoryIntegrityError, match="payload hash disagrees"
        ):
            observer.finalize(result)


@pytest.mark.parametrize(
    "tamper_sql",
    (
        "UPDATE history_runs SET current_phase = 'forged'",
        "UPDATE history_runs SET started_at = "
        "'2026-01-02T03:04:04.123456Z'",
        "UPDATE history_runs SET last_committed_at = "
        "'2026-01-02T03:04:06.123456Z'",
        "UPDATE history_runs SET ended_at = "
        "'2026-01-02T03:04:06.123456Z'",
    ),
)
def test_finalized_summary_binds_derived_state_and_timestamps(
    tmp_path: Path,
    tamper_sql: str,
) -> None:
    path = tmp_path / "history-derived.db"
    record = _record()
    with HistoryStore(path, clock=FakeClock()) as store:
        observer = store.observer(record, HistoryContext("run-derived", "host-1"))
        observer.on_event(_envelope(record, 1, StateChanged(SessionState.RUNNING)))
        observer.on_event(_envelope(record, 2, PhaseChanged("execute")))
        observer.finalize(OperationResult(SessionState.COMPLETED))
    connection = connect_history_writer(path)
    try:
        _allow_finalized_run_updates(connection)
        connection.execute(tamper_sql)
    finally:
        connection.close()

    with HistoryRepository(path) as repository:
        with pytest.raises(
            HistoryIntegrityError, match="prefix projection|payload hash"
        ):
            repository.get_summary("run-derived")
    with HistoryStore(path, clock=FakeClock()) as store:
        with pytest.raises(
            HistoryIntegrityError, match="prefix projection|payload hash"
        ):
            store.observer(record, HistoryContext("run-derived", "host-1"))


@pytest.mark.parametrize(
    "tamper_sql",
    (
        "UPDATE history_runs SET host_key = 'other-host' "
        "WHERE run_token = 'run-context-tampered'",
        "UPDATE history_runs SET source_context = NULL "
        "WHERE run_token = 'run-context-tampered'",
    ),
)
def test_summary_and_repeat_finalize_reject_tampered_context_columns(
    tmp_path: Path,
    tamper_sql: str,
) -> None:
    record = _record()
    context = HistoryContext(
        "run-context-tampered",
        "host-1",
        subject_kind="mapping",
        subject_id="mapping-1",
        source_context="source",
        target_context="target",
    )
    result = OperationResult(SessionState.COMPLETED)
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        observer = store.observer(record, context)
        observer.finalize(result)
        connection = connect_history_writer(store.path)
        try:
            _allow_finalized_run_updates(connection)
            connection.execute(tamper_sql)
        finally:
            connection.close()

        with HistoryRepository(store.path) as repository:
            with pytest.raises(
                HistoryIntegrityError, match="context hash disagrees"
            ):
                repository.get_summary("run-context-tampered")
            with pytest.raises(
                HistoryIntegrityError, match="context hash disagrees"
            ):
                repository.list_summaries()

        with pytest.raises(
            HistoryIntegrityError, match="context hash disagrees"
        ):
            observer.finalize(result)


def test_schema_rejects_terminal_summary_text_beyond_byte_bounds(
    tmp_path: Path,
) -> None:
    record = _record()
    result = OperationResult(
        SessionState.FAILED,
        phases=(
            PhaseResult(
                "execute",
                PhaseStatus.FAILED,
                0,
                0,
                0,
                0,
                "phase failure",
            ),
        ),
        error=FailureDetail("OSError", "terminal failure"),
    )
    with HistoryStore(tmp_path / "history.db", clock=FakeClock()) as store:
        store.observer(
            record, HistoryContext("run-schema-bounds", "host-1")
        ).finalize(result)
        connection = connect_history_writer(store.path)
        try:
            _allow_finalized_run_updates(connection)
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE history_runs SET error_message = ?",
                    ("x" * (MAX_HISTORY_ERROR_MESSAGE_BYTES + 1),),
                )
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE history_phases SET phase = ?",
                    ("x" * (MAX_HISTORY_PHASE_NAME_BYTES + 1),),
                )
        finally:
            connection.close()


def test_history_page_queries_use_paging_and_aggregate_indexes(tmp_path: Path) -> None:
    path = tmp_path / "history.db"
    with HistoryStore(path, clock=FakeClock()):
        pass
    connection = connect_history_reader(path)
    try:
        item_plan = " ".join(
            str(column)
            for row in connection.execute(
                """EXPLAIN QUERY PLAN SELECT * FROM history_events
                    WHERE run_id = 1 AND item_order > 0 AND item_order <= 10
                    ORDER BY item_order LIMIT 10"""
            )
            for column in row
        )
        event_plan = " ".join(
            str(column)
            for row in connection.execute(
                """EXPLAIN QUERY PLAN SELECT * FROM history_events
                    WHERE run_id = 1 AND event_seq > 0 AND event_seq <= 10
                    ORDER BY event_seq LIMIT 11"""
            )
            for column in row
        )
        event_watermark_plan = " ".join(
            str(column)
            for row in connection.execute(
                """EXPLAIN QUERY PLAN SELECT event_seq FROM history_events
                    WHERE run_id = 1
                    ORDER BY event_seq DESC LIMIT 1"""
            )
            for column in row
        )
        aggregate_plan = " ".join(
            str(column)
            for row in connection.execute(
                """EXPLAIN QUERY PLAN
                   SELECT run_id,
                          SUM(CASE WHEN item_type = 'operation'
                                   THEN 1 ELSE 0 END)
                         FROM history_events
                              INDEXED BY history_events_run_item_aggregate_idx
                    WHERE run_id = 1 AND item_order IS NOT NULL
                    GROUP BY run_id"""
            )
            for column in row
        )
        identity_plan = " ".join(
            str(column)
            for row in connection.execute(
                """EXPLAIN QUERY PLAN
                   SELECT event_seq FROM history_events
                        INDEXED BY history_events_run_identity_hash_idx
                    WHERE run_id = 1
                      AND item_identity_hash IN (zeroblob(32), randomblob(32))
                      AND (
                          event_disposition = 'recorded'
                          OR (
                              event_disposition = 'rejected'
                              AND duplicate_of_seq IS NULL
                          )
                      )
                      AND event_seq <= 10
                    """
            )
            for column in row
        )
    finally:
        connection.close()
    assert "history_events_run_item_order_idx" in item_plan
    assert "USING PRIMARY KEY" in event_plan
    assert "USING PRIMARY KEY" in event_watermark_plan
    assert "history_events_run_item_aggregate_idx" in aggregate_plan
    assert "history_events_run_identity_hash_idx" in identity_plan


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
