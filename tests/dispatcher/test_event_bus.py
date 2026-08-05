from __future__ import annotations

from datetime import datetime, timezone
from threading import Condition, Event, Thread
from time import monotonic, sleep

import pytest

import namisync.dispatcher.event_bus as event_bus
from namisync.core.evidence import RecordingStatus
from namisync.core.events import Gap, PhaseChanged, Progress, StateChanged, Terminal
from namisync.core.session import OperationResult, SessionId, SessionState
from namisync.dispatcher.event_bus import EventHub


class FixedClock:
    def now(self):
        return datetime(2026, 7, 18, tzinfo=timezone.utc)


class Observer:
    def __init__(self) -> None:
        self.events = []
        self.flushes = 0
        self.results = []
        self.closed = False
        self.close_count = 0

    def on_event(self, envelope) -> None:
        self.events.append(envelope)

    def flush(self) -> None:
        self.flushes += 1

    def finalize(self, result) -> None:
        self.results.append(result)

    def close(self) -> None:
        self.closed = True
        self.close_count += 1


def make_hub(**overrides) -> EventHub:
    options = {
        "session_id": SessionId("a" * 32),
        "initial_state": SessionState.PENDING,
        "clock": FixedClock(),
        "observer": Observer(),
        "replay_capacity": 8,
        "subscriber_capacity": 4,
        "audit_capacity": 4,
        "audit_timeout": 0.2,
        "audit_flush_interval": 1.0,
    }
    options.update(overrides)
    # Offer backpressure defaults to the finalization bound so existing cases
    # keep their original single-timeout behavior; tests that care about the
    # split pass it explicitly.
    options.setdefault("audit_offer_timeout", options["audit_timeout"])
    return EventHub(**options)


def test_audit_flush_interval_must_be_positive() -> None:
    with pytest.raises(ValueError, match="audit flush interval must be positive"):
        make_hub(audit_flush_interval=0)


def test_progress_flood_is_coalesced_and_never_ejects_slow_stream() -> None:
    hub = make_hub(subscriber_capacity=1)
    stream = hub.subscribe(from_seq=1)
    started = monotonic()
    for index in range(1000):
        hub.emit(Progress(index, 1000, index, 1000, None))
    elapsed = monotonic() - started
    envelope = stream.next(0.1)
    assert isinstance(envelope.body, Progress)
    assert envelope.body.items_done == 999
    assert not stream.ejected
    assert elapsed < 2.0
    assert hub.close(0.5)


def test_reliable_overrun_ejects_with_gap_as_first_visible_event() -> None:
    hub = make_hub(subscriber_capacity=1)
    stream = hub.subscribe(from_seq=1)
    hub.emit(PhaseChanged("one"))
    hub.emit(PhaseChanged("two"))
    envelope = stream.next(0.1)
    assert isinstance(envelope.body, Gap)
    assert envelope.body.first_missed_seq == 1
    assert stream.ejected
    assert hub._subscribers == []
    stream.close()
    assert hub._subscribers == []
    assert hub.close(0.5)


def test_late_subscriber_gets_current_state_bounded_tail_and_gap() -> None:
    hub = make_hub(replay_capacity=2, subscriber_capacity=4)
    hub.emit(StateChanged(SessionState.RUNNING))
    hub.emit(PhaseChanged("one"))
    hub.emit(PhaseChanged("two"))
    hub.emit(PhaseChanged("three"))
    stream = hub.subscribe(from_seq=1)
    assert stream.current_state is SessionState.RUNNING
    assert isinstance(stream.next(0.1).body, Gap)
    assert stream.next(0.1).body == PhaseChanged("two")
    assert stream.next(0.1).body == PhaseChanged("three")
    assert hub.close(0.5)


def test_explicit_stream_close_unsubscribes_immediately_and_idempotently() -> None:
    hub = make_hub()

    for _ in range(20):
        stream = hub.subscribe()
        assert len(hub._subscribers) == 1
        stream.close()
        stream.close()
        assert hub._subscribers == []

    assert hub.close(0.5)


def test_concurrent_emission_assigns_unique_gap_free_sequences() -> None:
    hub = make_hub(replay_capacity=256)
    envelopes = []

    def emit_batch(offset: int) -> None:
        for index in range(50):
            envelopes.append(hub.emit(PhaseChanged(f"{offset + index}")))

    threads = [Thread(target=emit_batch, args=(batch * 50,)) for batch in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(envelope.seq for envelope in envelopes) == list(range(1, 201))
    assert hub.close(0.5)


def test_audit_observer_receives_reliable_preterminal_events_and_finalizes() -> None:
    observer = Observer()
    hub = make_hub(observer=observer)
    hub.emit(PhaseChanged("one"))
    hub.emit(Progress(0, 1, 0, 1, None))
    result = OperationResult(SessionState.COMPLETED)
    assert hub.finalize_audit(result) is RecordingStatus.OK
    hub.emit(Terminal(result))
    assert [type(envelope.body) for envelope in observer.events] == [PhaseChanged]
    assert observer.results == [result]
    assert observer.flushes == 0
    assert hub.close(0.5)


def test_audit_flushes_an_idle_window_by_its_original_deadline() -> None:
    flushed = Event()

    class TrackingObserver(Observer):
        def flush(self) -> None:
            super().flush()
            flushed.set()

    observer = TrackingObserver()
    hub = make_hub(observer=observer, audit_flush_interval=0.03)
    hub.emit(PhaseChanged("one"))

    assert flushed.wait(1)
    assert observer.flushes == 1
    assert hub.close(0.5)
    assert observer.close_count == 1


def test_continuous_events_do_not_postpone_the_audit_flush_deadline() -> None:
    flushed = Event()

    class TrackingObserver(Observer):
        def flush(self) -> None:
            super().flush()
            flushed.set()

    observer = TrackingObserver()
    hub = make_hub(
        observer=observer,
        audit_capacity=64,
        audit_flush_interval=0.04,
    )
    deadline = monotonic() + 0.3
    index = 0
    while monotonic() < deadline and not flushed.is_set():
        hub.emit(PhaseChanged(str(index)))
        index += 1
        sleep(0.005)

    assert flushed.is_set()
    assert index > 1
    assert hub.close(0.5)


def test_paused_event_publication_waits_for_the_audit_flush_barrier() -> None:
    flush_entered = Event()
    release_flush = Event()
    emission_complete = Event()

    class BlockingFlush(Observer):
        def flush(self) -> None:
            flush_entered.set()
            assert release_flush.wait(2)
            super().flush()

    observer = BlockingFlush()
    hub = make_hub(
        observer=observer,
        audit_timeout=1.0,
        audit_flush_interval=30.0,
    )
    stream = hub.subscribe()

    def emit_pause() -> None:
        hub.emit(StateChanged(SessionState.PAUSED))
        emission_complete.set()

    thread = Thread(target=emit_pause)
    thread.start()
    assert flush_entered.wait(1)
    assert not emission_complete.wait(0.05)
    with pytest.raises(TimeoutError):
        stream.next(0.05)

    release_flush.set()
    assert emission_complete.wait(1)
    thread.join(1)
    assert not thread.is_alive()
    assert stream.next(0.1).body == StateChanged(SessionState.PAUSED)
    assert observer.flushes == 1
    assert hub.close(0.5)


def test_failed_paused_flush_degrades_without_hiding_domain_event() -> None:
    class FailedFlush(Observer):
        def flush(self) -> None:
            raise RuntimeError("history window failed")

    hub = make_hub(observer=FailedFlush(), audit_flush_interval=30.0)
    stream = hub.subscribe()

    envelope = hub.emit(StateChanged(SessionState.PAUSED))

    assert envelope.body == StateChanged(SessionState.PAUSED)
    assert stream.next(0.1) == envelope
    assert hub.audit_degraded
    assert hub.close(0.5)


def test_timed_out_paused_flush_never_delivers_a_later_audit_tail() -> None:
    flush_entered = Event()
    release_flush = Event()

    class DelayedFlush(Observer):
        def flush(self) -> None:
            flush_entered.set()
            assert release_flush.wait(2)
            super().flush()

    observer = DelayedFlush()
    hub = make_hub(
        observer=observer,
        audit_timeout=0.1,
        audit_flush_interval=30.0,
    )

    paused = hub.emit(StateChanged(SessionState.PAUSED))

    assert flush_entered.is_set()
    assert paused.body == StateChanged(SessionState.PAUSED)
    assert hub.audit_degraded
    hub.emit(PhaseChanged("must-not-be-audited"))
    assert (
        hub.finalize_audit(OperationResult(SessionState.COMPLETED))
        is RecordingStatus.DEGRADED
    )

    release_flush.set()
    assert hub._audit._closed.wait(1)
    assert [envelope.body for envelope in observer.events] == [
        StateChanged(SessionState.PAUSED)
    ]
    assert observer.results == []
    assert hub.close(0.5)


def test_timed_out_flush_exits_after_the_inflight_flush_returns() -> None:
    flush_entered = Event()
    release_flush = Event()

    class DelayedFlush(Observer):
        def flush(self) -> None:
            flush_entered.set()
            assert release_flush.wait(2)

    hub = make_hub(
        observer=DelayedFlush(),
        audit_timeout=0.05,
        audit_flush_interval=30.0,
    )

    hub.emit(StateChanged(SessionState.PAUSED))
    assert flush_entered.is_set()
    assert hub.audit_degraded

    release_flush.set()
    assert hub._audit._closed.wait(2)
    assert hub.close(0.5)


def test_external_prefix_break_wakes_an_idle_audit_pump() -> None:
    hub = make_hub(observer=Observer(), audit_flush_interval=30.0)

    hub._audit._break_prefix()

    assert hub._audit._closed.wait(2)
    assert hub.audit_degraded
    assert hub.close(0.5)


def test_clean_stop_forces_one_flush_and_closes_exactly_once() -> None:
    observer = Observer()
    hub = make_hub(observer=observer)

    assert hub.close(0.5)
    assert observer.flushes == 1
    assert observer.close_count == 1
    assert hub.close(0.5)
    assert observer.flushes == 1
    assert observer.close_count == 1


def test_flush_failure_degrades_and_closes_without_finalizing_tail() -> None:
    class FailedFlush(Observer):
        def flush(self) -> None:
            raise RuntimeError("history window failed")

    observer = FailedFlush()
    hub = make_hub(observer=observer, audit_flush_interval=0.02)
    hub.emit(PhaseChanged("one"))

    assert hub._audit._closed.wait(1)
    assert hub.audit_degraded
    assert (
        hub.finalize_audit(OperationResult(SessionState.COMPLETED))
        is RecordingStatus.DEGRADED
    )
    assert observer.results == []
    assert observer.close_count == 1
    assert hub.close(0.5)


def test_cleanup_failure_does_not_rewrite_successful_finalization() -> None:
    class FailedClose(Observer):
        def close(self) -> None:
            self.close_count += 1
            raise RuntimeError("history cleanup failed")

    observer = FailedClose()
    hub = make_hub(observer=observer)
    result = OperationResult(SessionState.COMPLETED)

    assert hub.finalize_audit(result) is RecordingStatus.OK
    assert hub._audit._closed.wait(1)
    assert hub.audit_degraded
    assert observer.results == [result]
    assert observer.close_count == 1
    assert hub.close(0.5)


def test_caller_timeout_wins_and_pump_conforms_persisted_result() -> None:
    release_event = Event()
    event_entered = Event()
    finalized = Event()

    class DelayedEvent(Observer):
        def on_event(self, envelope) -> None:
            event_entered.set()
            assert release_event.wait(2)
            super().on_event(envelope)

        def finalize(self, result) -> None:
            super().finalize(result)
            finalized.set()

    observer = DelayedEvent()
    hub = make_hub(observer=observer, audit_timeout=0.05)
    hub.emit(PhaseChanged("one"))
    assert event_entered.wait(2)

    status = hub.finalize_audit(OperationResult(SessionState.COMPLETED))

    assert status is RecordingStatus.DEGRADED
    release_event.set()
    assert finalized.wait(2)
    assert observer.results[0].audit is RecordingStatus.DEGRADED
    assert hub.close(0.5)
    assert observer.close_count == 1


def test_queued_finalize_does_not_write_after_prior_event_failure() -> None:
    event_entered = Event()
    release_event = Event()
    complete = Event()
    statuses: list[RecordingStatus] = []

    class FailedEvent(Observer):
        def on_event(self, envelope) -> None:
            del envelope
            event_entered.set()
            assert release_event.wait(2)
            raise RuntimeError("history event failed")

    observer = FailedEvent()
    hub = make_hub(observer=observer, audit_timeout=0.5)
    hub.emit(PhaseChanged("one"))
    assert event_entered.wait(2)

    def finalize() -> None:
        statuses.append(
            hub.finalize_audit(OperationResult(SessionState.COMPLETED))
        )
        complete.set()

    thread = Thread(target=finalize)
    thread.start()
    deadline = monotonic() + 2
    while hub._audit._queue.empty() and monotonic() < deadline:
        sleep(0.001)
    assert not hub._audit._queue.empty()
    release_event.set()
    assert complete.wait(2)
    thread.join()

    assert statuses == [RecordingStatus.DEGRADED]
    assert observer.results == []
    assert hub._audit._queue.empty()
    assert hub._audit._queue.unfinished_tasks == 0
    assert hub.close(0.5)
    assert observer.close_count == 1


def test_broken_audit_prefix_releases_every_queued_envelope() -> None:
    event_entered = Event()
    release_event = Event()
    close_entered = Event()
    release_close = Event()

    class FailedEvent(Observer):
        def on_event(self, envelope) -> None:
            del envelope
            event_entered.set()
            assert release_event.wait(2)
            raise RuntimeError("history event failed")

        def close(self) -> None:
            self.close_count += 1
            close_entered.set()
            assert release_close.wait(2)

    observer = FailedEvent()
    hub = make_hub(
        observer=observer,
        audit_capacity=3,
        audit_offer_timeout=0.1,
    )
    hub.emit(PhaseChanged("active"))
    assert event_entered.wait(2)
    hub.emit(PhaseChanged("queued-1"))
    hub.emit(PhaseChanged("queued-2"))
    hub.emit(PhaseChanged("queued-3"))
    assert hub._audit._queue.full()

    release_event.set()
    assert close_entered.wait(2)

    assert hub.audit_degraded
    assert hub._audit._queue.empty()
    assert hub._audit._queue.unfinished_tasks == 0
    assert not hub._audit._closed.is_set()

    release_close.set()
    assert hub._audit._closed.wait(2)
    assert hub.close(0.5)
    assert observer.close_count == 1


def test_pump_claim_before_deadline_waits_for_late_success() -> None:
    finalize_entered = Event()
    release_finalize = Event()
    complete = Event()
    statuses: list[RecordingStatus] = []

    class DelayedFinalize(Observer):
        def finalize(self, result) -> None:
            finalize_entered.set()
            assert release_finalize.wait(2)
            super().finalize(result)

    observer = DelayedFinalize()
    hub = make_hub(observer=observer, audit_timeout=0.05)

    def finalize() -> None:
        statuses.append(
            hub.finalize_audit(OperationResult(SessionState.COMPLETED))
        )
        complete.set()

    thread = Thread(target=finalize)
    thread.start()
    assert finalize_entered.wait(2)
    assert not complete.wait(0.1)
    assert not hub.audit_degraded
    release_finalize.set()
    assert complete.wait(2)
    thread.join()

    assert statuses == [RecordingStatus.OK]
    assert observer.results[0].audit is RecordingStatus.OK
    assert hub.close(0.5)


def test_pump_claim_before_deadline_reports_late_commit_failure() -> None:
    finalize_entered = Event()
    release_finalize = Event()
    complete = Event()
    statuses: list[RecordingStatus] = []

    class FailedFinalize(Observer):
        def finalize(self, result) -> None:
            del result
            finalize_entered.set()
            assert release_finalize.wait(2)
            raise RuntimeError("history commit failed")

    hub = make_hub(observer=FailedFinalize(), audit_timeout=0.05)

    def finalize() -> None:
        statuses.append(
            hub.finalize_audit(OperationResult(SessionState.COMPLETED))
        )
        complete.set()

    thread = Thread(target=finalize)
    thread.start()
    assert finalize_entered.wait(2)
    assert not complete.wait(0.1)
    release_finalize.set()
    assert complete.wait(2)
    thread.join()

    assert statuses == [RecordingStatus.DEGRADED]
    assert hub.audit_degraded
    assert hub.close(0.5)


def test_producer_backpressure_uses_the_offer_bound_not_the_finalization_bound() -> None:
    """A long finalization cutoff must not stall the emitting workflow thread.

    Finalization has to outlast the history writer's retry bound so a late but
    legitimate commit is not falsely degraded. Offer is the opposite concern:
    it exists only so a wedged audit writer degrades quickly instead of
    freezing live progress. Sharing one knob made raising the former silently
    multiply the latter.
    """

    release = Event()

    class Stalled(Observer):
        def on_event(self, envelope) -> None:
            del envelope
            release.wait(5)

    hub = make_hub(
        observer=Stalled(),
        audit_capacity=1,
        audit_timeout=30.0,
        audit_offer_timeout=0.05,
    )
    hub.emit(PhaseChanged("one"))
    hub.emit(PhaseChanged("two"))
    started = monotonic()
    hub.emit(PhaseChanged("three"))
    elapsed = monotonic() - started

    assert hub.audit_degraded
    assert elapsed < 1.0
    release.set()
    assert hub.close(1.0)


def test_stalled_audit_is_timeout_bounded_and_degrades() -> None:
    release = Event()

    class Stalled(Observer):
        def on_event(self, envelope) -> None:
            release.wait(1)

    hub = make_hub(observer=Stalled(), audit_capacity=1, audit_timeout=0.05)
    hub.emit(PhaseChanged("one"))
    hub.emit(PhaseChanged("two"))
    started = monotonic()
    hub.emit(PhaseChanged("three"))
    elapsed = monotonic() - started
    assert hub.audit_degraded
    assert elapsed < 0.5
    assert hub.finalize_audit(OperationResult(SessionState.COMPLETED)) is RecordingStatus.DEGRADED
    release.set()
    assert hub.close(0.5)


def test_close_deadline_includes_waiting_for_the_publication_lock() -> None:
    hub = make_hub()
    stream = hub.subscribe()
    hub.emit(PhaseChanged("retained-until-close"))
    assert hub._reserve_publication(0.1)
    try:
        started = monotonic()
        assert not hub.close(0.05)
        assert monotonic() - started < 0.5
        assert hub._replay
        assert hub._subscribers == [stream]
    finally:
        hub._release_publication()

    assert hub.close(0.5)
    assert not hub._replay
    assert not hub._subscribers
    assert stream._closed


def test_close_detaches_replay_and_subscribers_before_observer_cleanup() -> None:
    close_entered = Event()
    release_close = Event()

    class BlockingClose(Observer):
        def close(self) -> None:
            close_entered.set()
            assert release_close.wait(2)
            super().close()

    hub = make_hub(observer=BlockingClose(), audit_timeout=1.0)
    stream = hub.subscribe()
    hub.emit(PhaseChanged("durable"))
    results: list[bool] = []
    thread = Thread(target=lambda: results.append(hub.close(1.0)))
    thread.start()
    assert close_entered.wait(2)
    try:
        assert not hub._replay
        assert not hub._subscribers
        assert stream._closed
        with pytest.raises(RuntimeError, match="event hub is closed"):
            hub.subscribe()
    finally:
        release_close.set()
        thread.join(2)

    assert not thread.is_alive()
    assert results == [True]


def test_audit_close_spends_one_deadline_across_enqueue_and_join(
    monkeypatch,
) -> None:
    class QueueProbe:
        def __init__(self) -> None:
            self.timeouts: list[float] = []

        def put(self, command, *, timeout: float) -> None:
            assert isinstance(command, event_bus._Stop)
            self.timeouts.append(timeout)

    class ThreadProbe:
        def __init__(self) -> None:
            self.timeouts: list[float] = []

        def join(self, timeout: float) -> None:
            self.timeouts.append(timeout)

        def is_alive(self) -> bool:
            return True

    times = iter((10.0, 10.025, 10.075))
    monkeypatch.setattr(event_bus, "monotonic", lambda: next(times))
    pump = object.__new__(event_bus._AuditPump)
    pump._closed = Event()
    pump._degraded = Event()
    pump._queue = QueueProbe()
    pump._submission_condition = Condition()
    pump._accepting = True
    pump._active_submissions = 0
    pump._thread = ThreadProbe()

    assert not pump.close(0.1)
    assert pump._queue.timeouts == [pytest.approx(0.075)]
    assert pump._thread.timeouts == [pytest.approx(0.025)]
