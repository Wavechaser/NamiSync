"""Ordinary BR-G-33/SH-G-8 evidence for adapter task drains."""

from __future__ import annotations

from threading import Event, Thread
from time import monotonic

import pytest

from namisync.interfaces.service import PlanSession
from namisync.interfaces.web.drain import (
    DrainBusyError,
    ObservationConflictError,
    TaskIntentConflictError,
    TaskRegistry,
    TaskUnavailableError,
)
from namisync.workflows.views import SessionEventView, SessionRecordView


REQUEST = "1" * 32
SESSION = "2" * 32
DRAIN = "3" * 32


def _event(sequence: int, body_type: str = "StateChanged") -> SessionEventView:
    return SessionEventView(SESSION, sequence, "2026-01-01T00:00:00Z", body_type, {})


def _record(*, terminal: bool = True) -> SessionRecordView:
    return SessionRecordView(
        SESSION,
        "plan",
        "completed" if terminal else "pending",
        False,
        "2026-01-01T00:00:00Z",
        None,
        None,
        object() if terminal else None,  # type: ignore[arg-type]
    )


class _Service:
    def __init__(self) -> None:
        self.sink = None
        self.start_calls = []
        self.reobserve_calls = []
        self.cleanup = []
        self.start_entered = Event()
        self.release_start = Event()
        self.release_start.set()
        self.reobserve_entered = Event()
        self.release_reobserve = Event()
        self.release_reobserve.set()
        self.reobserve_result = _record(terminal=False)

    def start_plan(self, source, target, **kwargs):
        self.start_calls.append((source, target, kwargs))
        self.sink = kwargs["observation_sink"]
        self.sink(_event(1))
        self.start_entered.set()
        assert self.release_start.wait(2)
        return PlanSession(REQUEST, SESSION)

    def reobserve(self, session_id, sink, from_sequence):
        self.reobserve_calls.append((session_id, sink, from_sequence))
        self.reobserve_entered.set()
        assert self.release_reobserve.wait(2)
        return self.reobserve_result

    def unsubscribe(self, session_id):
        self.cleanup.append(("unsubscribe", session_id))

    def close_session(self, session_id):
        self.cleanup.append(("close_session", session_id))

    def drop_plan(self, request_id):
        self.cleanup.append(("drop_plan", request_id))


def _registry(service=None, *, drain_wait=0.2):
    service = service or _Service()
    return TaskRegistry(
        service,
        token=lambda: "a" * 32,
        drain_wait=drain_wait,
    ), service


def _start(registry: TaskRegistry, command_id: str = "4" * 32):
    return registry.start_plan(
        "source",
        "target",
        deletion_policy=None,
        command_id=command_id,
    )


def test_sh_g_8_observation_attaches_before_start_returns_and_pending_is_drained() -> None:
    registry, service = _registry()
    service.release_start.clear()
    results = []
    thread = Thread(target=lambda: results.append(_start(registry)))
    thread.start()

    assert service.start_entered.wait(1)
    assert service.sink is not None
    service.release_start.set()
    thread.join(1)
    start = results[0]
    drained = registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)

    assert start.task_id == "task-" + "a" * 32
    assert [item.event.sequence for item in drained.updates] == [1]
    assert all(item.update_type == "event" for item in drained.updates)


def test_br_g_33_start_is_singleflight_and_changed_intent_conflicts() -> None:
    registry, service = _registry()
    service.release_start.clear()
    results = []
    errors = []

    def call(source="source"):
        try:
            results.append(
                registry.start_plan(
                    source,
                    "target",
                    deletion_policy=None,
                    command_id="4" * 32,
                )
            )
        except BaseException as error:
            errors.append(error)

    first = Thread(target=call)
    second = Thread(target=call)
    first.start()
    assert service.start_entered.wait(1)
    second.start()
    with pytest.raises(TaskIntentConflictError):
        registry.start_plan(
            "different",
            "target",
            deletion_policy=None,
            command_id="4" * 32,
        )
    service.release_start.set()
    first.join(1)
    second.join(1)

    assert not errors
    assert len(service.start_calls) == 1
    assert results == [results[0], results[0]]


def test_br_g_33_progress_coalesces_and_reliable_never_drops_or_reorders() -> None:
    registry, service = _registry()
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)

    for sequence in range(2, 1002):
        service.sink(_event(sequence, "Progress"))
    service.sink(_event(1002, "StateChanged"))
    drained = registry.drain(start.task_id, SESSION, "5" * 32, replay_from=None)

    assert [(item.event.sequence, item.event.body_type) for item in drained.updates] == [
        (1001, "Progress"),
        (1002, "StateChanged"),
    ]


def test_br_g_33_progress_yields_to_a_full_reliable_queue() -> None:
    registry, service = _registry()
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)
    for sequence in range(2, 66):
        service.sink(_event(sequence))

    service.sink(_event(66, "Progress"))
    drained = registry.drain(start.task_id, SESSION, "5" * 32, replay_from=None)

    assert len(drained.updates) == 64
    assert all(item.event.body_type != "Progress" for item in drained.updates)


def test_br_g_33_reliable_capacity_blocks_until_drain_and_close_wakes() -> None:
    registry, service = _registry()
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)
    for sequence in range(2, 66):
        service.sink(_event(sequence))
    offered = Event()

    def offer() -> None:
        service.sink(_event(66))
        offered.set()

    producer = Thread(target=offer)
    producer.start()
    assert not offered.wait(0.05)
    first = registry.drain(start.task_id, SESSION, "5" * 32, replay_from=None)
    assert offered.wait(1)
    producer.join(1)
    second = registry.drain(start.task_id, SESSION, "6" * 32, replay_from=None)

    assert len(first.updates) == 64
    assert [item.event.sequence for item in second.updates] == [66]

    for sequence in range(67, 131):
        service.sink(_event(sequence))
    blocked = Event()
    closer_producer = Thread(
        target=lambda: (service.sink(_event(131)), blocked.set())
    )
    closer_producer.start()
    assert not blocked.wait(0.05)
    registry.begin_close()
    assert blocked.wait(1)
    closer_producer.join(1)


def test_br_g_33_superseding_drain_consumes_nothing_and_busy_waits_for_release() -> None:
    registry, service = _registry(drain_wait=1.0)
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)
    first_results = []
    first = Thread(
        target=lambda: first_results.append(
            registry.drain(start.task_id, SESSION, "5" * 32, replay_from=None)
        )
    )
    first.start()
    deadline = monotonic() + 1
    while registry._tasks[start.task_id].active_drain is None:
        assert monotonic() < deadline

    with pytest.raises(DrainBusyError):
        registry.drain(start.task_id, SESSION, "6" * 32, replay_from=None)
    first.join(1)
    service.sink(_event(2))
    after = registry.drain(start.task_id, SESSION, "7" * 32, replay_from=None)

    assert first_results[0].updates == ()
    assert [item.event.sequence for item in after.updates] == [2]


def test_br_g_33_competing_recovery_cannot_reobserve_before_busy_refusal() -> None:
    registry, service = _registry(drain_wait=1.0)
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)
    first_results = []
    first = Thread(
        target=lambda: first_results.append(
            registry.drain(start.task_id, SESSION, "5" * 32, replay_from=None)
        )
    )
    first.start()
    deadline = monotonic() + 1
    while registry._tasks[start.task_id].active_drain is None:
        assert monotonic() < deadline

    with pytest.raises(DrainBusyError):
        registry.drain(
            start.task_id,
            SESSION,
            "6" * 32,
            replay_from=2,
        )
    first.join(1)

    assert first_results[0].updates == ()
    assert service.reobserve_calls == []


def test_br_g_33_recovery_clears_uncertain_queue_and_calls_facade_outside_lock() -> None:
    registry, service = _registry()
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)
    service.sink(_event(2))
    service.release_reobserve.clear()
    results = []
    recovery = Thread(
        target=lambda: results.append(
            registry.drain(
                start.task_id,
                SESSION,
                "5" * 32,
                replay_from=2,
            )
        )
    )
    recovery.start()
    assert service.reobserve_entered.wait(1)
    acquired = registry._tasks[start.task_id].condition.acquire(timeout=0.2)
    assert acquired
    registry._tasks[start.task_id].condition.release()
    service.release_reobserve.set()
    recovery.join(1)

    assert service.reobserve_calls[0][2] == 2
    assert results[0].updates == ()


def test_br_g_33_terminal_recovery_enqueues_record_and_stops_at_truth() -> None:
    registry, service = _registry()
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)
    terminal = _record()
    service.reobserve_result = terminal

    drained = registry.drain(
        start.task_id,
        SESSION,
        "5" * 32,
        replay_from=2,
    )

    assert len(drained.updates) == 1
    assert drained.updates[0].update_type == "record"
    assert drained.updates[0].record is terminal


def test_br_g_33_terminal_recovery_never_exceeds_the_queue_or_batch_cap() -> None:
    class Service(_Service):
        def reobserve(self, session_id, sink, from_sequence):
            self.reobserve_calls.append((session_id, sink, from_sequence))
            for sequence in range(2, 66):
                sink(_event(sequence))
            return _record()

    service = Service()
    registry, _ = _registry(service)
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)

    replay = registry.drain(
        start.task_id,
        SESSION,
        "5" * 32,
        replay_from=2,
    )
    before_terminal = monotonic()
    terminal = registry.drain(
        start.task_id,
        SESSION,
        "6" * 32,
        replay_from=None,
    )
    terminal_elapsed = monotonic() - before_terminal

    assert len(replay.updates) == 64
    assert all(update.update_type == "event" for update in replay.updates)
    assert len(terminal.updates) == 1
    assert terminal.updates[0].update_type == "record"
    assert terminal_elapsed < 0.1


def test_br_g_33_synchronous_recovery_cannot_deadlock_at_reliable_capacity() -> None:
    class Service(_Service):
        def reobserve(self, session_id, sink, from_sequence):
            del session_id, from_sequence
            for sequence in range(2, 67):
                sink(_event(sequence))
            return _record(terminal=False)

    service = Service()
    registry, _ = _registry(service)
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)

    with pytest.raises(ObservationConflictError, match="synchronously"):
        registry.drain(
            start.task_id,
            SESSION,
            "5" * 32,
            replay_from=2,
        )

    assert not registry._tasks[start.task_id].queue
    assert registry._tasks[start.task_id].terminal_record is None


def test_br_g_33_failed_recovery_invalidates_late_generation_callbacks() -> None:
    class Service(_Service):
        recovery_sink = None

        def reobserve(self, session_id, sink, from_sequence):
            del session_id, from_sequence
            self.recovery_sink = sink
            raise RuntimeError("injected recovery failure")

    service = Service()
    registry, _ = _registry(service)
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)

    with pytest.raises(RuntimeError, match="recovery failure"):
        registry.drain(
            start.task_id,
            SESSION,
            "5" * 32,
            replay_from=2,
        )
    service.recovery_sink(_event(2))

    assert not registry._tasks[start.task_id].queue


def test_br_g_33_task_session_mismatch_and_concurrent_recovery_are_named() -> None:
    registry, service = _registry()
    start = _start(registry)
    with pytest.raises(TaskUnavailableError):
        registry.drain(start.task_id, "9" * 32, DRAIN, replay_from=None)

    service.release_reobserve.clear()
    errors = []
    first = Thread(
        target=lambda: registry.drain(
            start.task_id,
            SESSION,
            "5" * 32,
            replay_from=2,
        )
    )
    first.start()
    assert service.reobserve_entered.wait(1)
    with pytest.raises(ObservationConflictError):
        registry.drain(
            start.task_id,
            SESSION,
            "6" * 32,
            replay_from=2,
        )
    service.release_reobserve.set()
    first.join(1)


def test_br_g_33_shutdown_wakes_then_unsubscribes_after_handler_barrier() -> None:
    registry, service = _registry(drain_wait=1.0)
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)
    errors = []

    def drain() -> None:
        try:
            registry.drain(start.task_id, SESSION, "5" * 32, replay_from=None)
        except BaseException as error:
            errors.append(error)

    waiting = Thread(target=drain)
    waiting.start()
    deadline = monotonic() + 1
    while registry._tasks[start.task_id].active_drain is None:
        assert monotonic() < deadline
    registry.begin_close()
    waiting.join(1)

    assert isinstance(errors[0], TaskUnavailableError)
    assert service.cleanup == []
    registry.unsubscribe_all()
    assert service.cleanup == [("unsubscribe", SESSION)]
    registry.unsubscribe_all()
    assert service.cleanup == [("unsubscribe", SESSION)]


def test_br_g_33_close_task_cleanup_order_and_retry_authority() -> None:
    registry, service = _registry()
    start = _start(registry)

    registry.close_task(start.task_id)

    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("drop_plan", REQUEST),
    ]
    with pytest.raises(TaskUnavailableError):
        registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)


def test_br_g_33_failed_binding_retains_and_retries_compensation_in_order() -> None:
    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.close_attempts = 0

        def start_plan(self, source, target, **kwargs):
            del source, target
            kwargs["observation_sink"](_event(1))
            return PlanSession(REQUEST, "8" * 32)

        def close_session(self, session_id):
            self.close_attempts += 1
            self.cleanup.append(("close_session", session_id))
            if self.close_attempts == 1:
                raise OSError("injected cleanup failure")

    service = Service()
    registry, _ = _registry(service)

    with pytest.raises(ObservationConflictError):
        _start(registry)

    assert len(registry._tasks) == 1
    task = next(iter(registry._tasks.values()))
    assert task.cleanup_pending
    assert service.cleanup == [
        ("unsubscribe", "8" * 32),
        ("close_session", "8" * 32),
    ]

    registry.begin_close()
    registry.unsubscribe_all()

    assert service.cleanup == [
        ("unsubscribe", "8" * 32),
        ("close_session", "8" * 32),
        ("close_session", "8" * 32),
        ("drop_plan", REQUEST),
    ]
    assert registry._tasks == {}
    assert registry._commands == {}


def test_br_g_33_close_task_retries_only_unfinished_cleanup_steps() -> None:
    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.drop_attempts = 0

        def drop_plan(self, request_id):
            self.drop_attempts += 1
            self.cleanup.append(("drop_plan", request_id))
            if self.drop_attempts == 1:
                raise OSError("injected drop failure")

    service = Service()
    registry, _ = _registry(service)
    start = _start(registry)

    with pytest.raises(OSError, match="drop failure"):
        registry.close_task(start.task_id)
    assert start.task_id in registry._tasks

    registry.close_task(start.task_id)

    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("drop_plan", REQUEST),
        ("drop_plan", REQUEST),
    ]
    assert start.task_id not in registry._tasks
