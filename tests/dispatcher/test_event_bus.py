from __future__ import annotations

from datetime import datetime, timezone
from threading import Event, Thread
from time import monotonic

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
