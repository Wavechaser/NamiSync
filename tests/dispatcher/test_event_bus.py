from __future__ import annotations

from datetime import datetime, timezone
from threading import Event, Thread
from time import monotonic, sleep

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
        self.results = []
        self.closed = False

    def on_event(self, envelope) -> None:
        self.events.append(envelope)

    def finalize(self, result) -> None:
        self.results.append(result)

    def close(self) -> None:
        self.closed = True


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
    }
    options.update(overrides)
    return EventHub(**options)


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
    assert hub.close(0.5)


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
