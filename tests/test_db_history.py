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
        with pytest.raises(HistoryIntegrityError, match="per-event byte bound"):
            observer.on_event(event)
        assert observer.pending_event_count == 0
        assert observer.pending_bytes == 0
        observer.close()
        with HistoryRepository(store.path) as repository:
            with pytest.raises(KeyError):
                repository.get_summary("run-1")


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

        def counted(row):
            decoded.append(int(row["event_seq"]))
            return original(row)

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
    selects = [statement for statement in statements if statement.startswith("SELECT")]
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
        connection.execute(
            "UPDATE history_events SET envelope_json = envelope_json || ' '")
    finally:
        connection.close()
    with HistoryRepository(path) as repository:
        with pytest.raises(HistoryIntegrityError, match="payload hash"):
            repository.get_event_page("run-1")


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
    finally:
        connection.close()
    assert "history_events_run_item_order_idx" in item_plan
    assert "sqlite_autoindex_history_events_1" in event_plan
    assert "sqlite_autoindex_history_events_1" in event_watermark_plan
    assert "history_events_run_item_aggregate_idx" in aggregate_plan


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
