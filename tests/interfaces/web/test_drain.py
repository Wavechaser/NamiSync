"""Ordinary BR-G-33/SH-G-8 evidence for adapter task drains."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from time import monotonic, sleep

import pytest

from namisync.core.events import ItemOutcome, Progress
from namisync.core.evidence import Outcome
from namisync.core.session import OperationResult, SessionState
from namisync.dispatcher import (
    Dispatcher,
    PreparedSession,
    SessionNotFound,
    WorkflowRegistration,
)
from namisync.interfaces import service as service_module
from namisync.interfaces.service import NamiSyncService, PlanSession
from namisync.interfaces.web import drain as drain_module
from namisync.interfaces.web.drain import (
    DrainBusyError,
    ObservationConflictError,
    TaskIntentConflictError,
    TaskCloseView,
    TaskRegistry,
    TaskUnavailableError,
)
from namisync.workflows import PLAN_KIND
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


@dataclass
class _IntegratedRun:
    entered: Event
    release: Event
    progress_count: int = 0
    reliable_count: int = 0
    flood_done: Event | None = None
    finish: Event | None = None


@dataclass
class _IntegratedInvocation:
    name: str
    run_state: _IntegratedRun

    def run(self, context):
        state = self.run_state
        state.entered.set()
        assert state.release.wait(2)
        for index in range(state.progress_count):
            context.emit(
                Progress(
                    items_done=index + 1,
                    items_total=state.progress_count,
                    bytes_done=index + 1,
                    bytes_total=state.progress_count,
                    current_path=f"{self.name}-progress-{index}",
                )
            )
        for index in range(state.reliable_count):
            context.emit(
                ItemOutcome(
                    item_id=f"{self.name}-item-{index}",
                    kind="copy",
                    path=f"{self.name}-{index}.txt",
                    outcome=Outcome.SUCCEEDED,
                )
            )
        if state.flood_done is not None:
            state.flood_done.set()
        if state.finish is not None:
            assert state.finish.wait(2)
        return OperationResult(SessionState.COMPLETED)

    def snapshot(self) -> bytes:
        return self.name.encode("utf-8")


def _wait_terminal(dispatcher: Dispatcher, session_id: str) -> None:
    deadline = monotonic() + 2
    while monotonic() < deadline:
        record = dispatcher.get(session_id)
        if record.result is not None:
            return
        sleep(0.005)
    raise AssertionError(f"session did not reach terminal truth: {session_id}")


def _drain_until_record(
    registry: TaskRegistry,
    task_id: str,
    session_id: str,
    drain_ids,
):
    updates = []
    for _ in range(8):
        batch = registry.drain(
            task_id,
            session_id,
            next(drain_ids),
            replay_from=None,
        )
        updates.extend(batch.updates)
        if any(update.update_type == "record" for update in batch.updates):
            return updates
    raise AssertionError("terminal task record was not drained")


def _mark_terminal_drained(registry: TaskRegistry, start) -> None:
    task = registry._tasks[start.task_id]
    with task.condition:
        task.terminal_record = _record()
        task.terminal_pending = True
        task.condition.notify_all()
    drained = registry.drain(
        start.task_id,
        start.session_id,
        DRAIN,
        replay_from=None,
    )
    assert any(update.update_type == "record" for update in drained.updates)


def test_br_g_33_sh_g_8_integrated_admission_envelope_and_visible_gap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adopt_entered = Event()
    adopt_release = Event()
    adopted_session_ids = []
    normal_release = Event()
    overflow_release = Event()
    overflow_finish = Event()
    overflow_done = Event()
    runs = {
        "normal-0": _IntegratedRun(Event(), normal_release, 25, 3),
        "normal-1": _IntegratedRun(Event(), normal_release, 25, 3),
        "normal-2": _IntegratedRun(Event(), normal_release, 25, 2),
        "normal-3": _IntegratedRun(Event(), normal_release, 25, 2),
        "overflow": _IntegratedRun(
            Event(),
            overflow_release,
            reliable_count=260,
            flood_done=overflow_done,
            finish=overflow_finish,
        ),
    }

    def prepare_plan(request) -> PreparedSession:
        name = Path(request.source_path).name
        return PreparedSession(name.encode("utf-8"))

    def open_plan(payload: bytes) -> _IntegratedInvocation:
        name = payload.decode("utf-8")
        return _IntegratedInvocation(name, runs[name])

    dispatcher = Dispatcher(
        {
            PLAN_KIND: WorkflowRegistration(prepare_plan, open_plan),
        }
    )
    monkeypatch.setattr(service_module, "_dispatcher", lambda _runtime: dispatcher)
    service = NamiSyncService(tmp_path / "ledger.db", tmp_path / "history.db")
    real_adopt = service._observer.adopt

    def instrumented_adopt(
        session_id,
        sink,
        stream,
        *,
        from_sequence=1,
    ):
        rollback = real_adopt(
            session_id,
            sink,
            stream,
            from_sequence=from_sequence,
        )
        if not adopt_entered.is_set():
            adopted_session_ids.append(session_id)
            adopt_entered.set()
            assert adopt_release.wait(2)
        return rollback

    monkeypatch.setattr(service._observer, "adopt", instrumented_adopt)
    task_tokens = iter(f"{index:032x}" for index in range(1, 32))
    registry = TaskRegistry(service, token=lambda: next(task_tokens), drain_wait=1.0)
    drain_ids = iter(f"{index:032x}" for index in range(100, 500))

    def roots(name: str) -> tuple[str, str]:
        source = tmp_path / "sources" / name
        target = tmp_path / "targets" / name
        source.mkdir(parents=True)
        target.mkdir(parents=True)
        return str(source), str(target)

    try:
        assert dispatcher._replay_capacity == 128
        assert dispatcher._subscriber_capacity == 64
        assert drain_module._CAPACITY == 64

        starts = []
        source, target = roots("normal-0")
        start_results = []
        start_errors = []

        def start_first() -> None:
            try:
                start_results.append(
                    registry.start_plan(
                        source,
                        target,
                        deletion_policy=None,
                        command_id=f"{1:032x}",
                    )
                )
            except BaseException as error:
                start_errors.append(error)

        start_thread = Thread(target=start_first)
        start_thread.start()
        assert adopt_entered.wait(1)
        assert start_thread.is_alive()
        with pytest.raises(SessionNotFound):
            dispatcher.get(adopted_session_ids[0])
        assert not runs["normal-0"].entered.wait(0.05)
        adopt_release.set()
        start_thread.join(2)
        assert not start_thread.is_alive()
        assert not start_errors
        attached = start_results[0]
        starts.append(attached)
        assert runs["normal-0"].entered.wait(1)
        pending = registry.drain(
            attached.task_id,
            attached.session_id,
            next(drain_ids),
            replay_from=None,
        )
        pending_events = [
            (update.event.body_type, update.event.body)
            for update in pending.updates
            if update.update_type == "event"
        ]
        assert pending_events[0] == ("StateChanged", {"state": "pending"})
        assert not any(body_type == "Gap" for body_type, _body in pending_events)

        for index in range(1, 4):
            source, target = roots(f"normal-{index}")
            starts.append(
                registry.start_plan(
                    source,
                    target,
                    deletion_policy=None,
                    command_id=f"{index + 1:032x}",
                )
            )
            assert runs[f"normal-{index}"].entered.wait(1)

        assert all(dispatcher.get(start.session_id).result is None for start in starts)

        normal_release.set()
        normal_updates = list(pending.updates)
        for start in starts:
            _wait_terminal(dispatcher, start.session_id)
            normal_updates.extend(
                _drain_until_record(
                    registry,
                    start.task_id,
                    start.session_id,
                    drain_ids,
                )
            )

        normal_events = [
            update.event
            for update in normal_updates
            if update.update_type == "event"
        ]
        assert not any(event.body_type == "Gap" for event in normal_events)
        assert sum(event.body_type == "ItemOutcome" for event in normal_events) == 10
        progress_events = [
            event for event in normal_events if event.body_type == "Progress"
        ]
        assert len(progress_events) == 4
        progress_by_session = {
            event.session_id: event.body for event in progress_events
        }
        assert set(progress_by_session) == {
            start.session_id for start in starts
        }
        for index, start in enumerate(starts):
            assert progress_by_session[start.session_id] == {
                "items_done": 25,
                "items_total": 25,
                "bytes_done": 25,
                "bytes_total": 25,
                "current_path": f"normal-{index}-progress-24",
            }
        assert all(
            len(registry._tasks[start.task_id].queue) <= 64 for start in starts
        )

        source, target = roots("overflow")
        overflow = registry.start_plan(
            source,
            target,
            deletion_policy=None,
            command_id=f"{5:032x}",
        )
        assert runs["overflow"].entered.wait(1)
        overflow_release.set()
        assert overflow_done.wait(2)
        assert dispatcher.get(overflow.session_id).result is None

        accepted_item_ids: set[str] = set()
        ordinary_gap = None
        first_batch = registry.drain(
            overflow.task_id,
            overflow.session_id,
            next(drain_ids),
            replay_from=None,
        )
        assert len(first_batch.updates) == 64
        for _ in range(4):
            batch = (
                first_batch
                if ordinary_gap is None and _ == 0
                else registry.drain(
                    overflow.task_id,
                    overflow.session_id,
                    next(drain_ids),
                    replay_from=None,
                )
            )
            for update in batch.updates:
                if update.update_type != "event":
                    continue
                if update.event.body_type == "Gap":
                    ordinary_gap = update.event
                    break
                if update.event.body_type == "ItemOutcome":
                    accepted_item_ids.add(update.event.body["item_id"])
            if ordinary_gap is not None:
                break
        assert ordinary_gap is not None
        first_missed = ordinary_gap.body["first_missed_seq"]

        recovery = registry.drain(
            overflow.task_id,
            overflow.session_id,
            next(drain_ids),
            replay_from=first_missed,
        )
        recovered_events = [
            update.event for update in recovery.updates if update.update_type == "event"
        ]
        assert len(recovery.updates) == 64
        assert recovered_events[0].body_type == "Gap"
        assert recovered_events[0].body == {"first_missed_seq": first_missed}
        retained_tail = [
            event for event in recovered_events[1:] if event.body_type == "ItemOutcome"
        ]
        assert retained_tail
        assert retained_tail[0].sequence > first_missed
        accepted_item_ids.update(event.body["item_id"] for event in retained_tail)
        emitted_item_ids = {f"overflow-item-{index}" for index in range(260)}
        assert emitted_item_ids - accepted_item_ids

        overflow_finish.set()
        _wait_terminal(dispatcher, overflow.session_id)
        terminal_updates = _drain_until_record(
            registry,
            overflow.task_id,
            overflow.session_id,
            drain_ids,
        )
        terminal = next(
            update.record
            for update in terminal_updates
            if update.update_type == "record"
        )
        assert terminal.state == "completed"
        assert terminal.result is not None
        assert len(terminal.result.items) == 260
        assert any(
            update.update_type == "event" and update.event.body_type == "Terminal"
            for update in terminal_updates
        )
    finally:
        adopt_release.set()
        normal_release.set()
        overflow_release.set()
        overflow_finish.set()
        registry.begin_close()
        registry.unsubscribe_all()
        service.close(timeout=2)


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

    _mark_terminal_drained(registry, start)
    closed = registry.close_task(start.task_id, start.session_id)

    assert closed == TaskCloseView(start.task_id, start.session_id)
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("drop_plan", REQUEST),
    ]
    with pytest.raises(TaskUnavailableError):
        registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)


def test_close_task_refuses_before_terminal_record_is_drained() -> None:
    registry, service = _registry()
    start = _start(registry)

    with pytest.raises(TaskUnavailableError, match="terminal record"):
        registry.close_task(start.task_id, start.session_id)

    assert service.cleanup == []
    assert start.task_id in registry._tasks


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

    with pytest.raises(ObservationConflictError):
        registry.replay_start("4" * 32, None)  # type: ignore[arg-type]

    assert service.cleanup == [
        ("unsubscribe", "8" * 32),
        ("close_session", "8" * 32),
        ("close_session", "8" * 32),
        ("drop_plan", REQUEST),
    ]
    assert registry._tasks == {}
    assert registry._commands == {}


def test_compensation_interrupt_propagates_without_stranding_the_registry() -> None:
    class Service(_Service):
        def start_plan(self, source, target, **kwargs):
            del source, target
            kwargs["observation_sink"](_event(1))
            return PlanSession(REQUEST, "8" * 32)

        def close_session(self, session_id):
            raise KeyboardInterrupt(f"stop cleanup for {session_id}")

    registry, _ = _registry(Service())

    with pytest.raises(KeyboardInterrupt, match="stop cleanup"):
        _start(registry)

    assert len(registry._tasks) == 1
    task = next(iter(registry._tasks.values()))
    assert task.cleanup_pending


def test_concurrent_replays_single_flight_failed_admission_compensation() -> None:
    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.close_attempts = 0
            self.retry_entered = Event()
            self.release_retry = Event()

        def start_plan(self, source, target, **kwargs):
            del source, target
            kwargs["observation_sink"](_event(1))
            return PlanSession(REQUEST, "8" * 32)

        def close_session(self, session_id):
            self.close_attempts += 1
            self.cleanup.append(("close_session", session_id))
            if self.close_attempts == 1:
                raise OSError("injected cleanup failure")
            self.retry_entered.set()
            assert self.release_retry.wait(2)

    service = Service()
    registry, _ = _registry(service)
    with pytest.raises(ObservationConflictError):
        _start(registry)

    errors: list[BaseException] = []

    def replay() -> None:
        try:
            registry.replay_start("4" * 32, None)  # type: ignore[arg-type]
        except BaseException as error:
            errors.append(error)

    first = Thread(target=replay)
    second = Thread(target=replay)
    first.start()
    assert service.retry_entered.wait(1)
    second.start()
    service.release_retry.set()
    first.join(1)
    second.join(1)

    assert len(errors) == 2
    assert all(isinstance(error, ObservationConflictError) for error in errors)
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

    _mark_terminal_drained(registry, start)
    with pytest.raises(OSError, match="drop failure"):
        registry.close_task(start.task_id, start.session_id)
    assert start.task_id in registry._tasks

    registry.close_task(start.task_id, start.session_id)

    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("drop_plan", REQUEST),
        ("drop_plan", REQUEST),
    ]
    assert start.task_id not in registry._tasks


def test_close_task_lost_response_retry_is_exact_and_idempotent() -> None:
    registry, service = _registry()
    start = _start(registry)

    _mark_terminal_drained(registry, start)
    first = registry.close_task(start.task_id, start.session_id)
    replay = registry.close_task(start.task_id, start.session_id)

    assert first == replay == TaskCloseView(start.task_id, start.session_id)
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("drop_plan", REQUEST),
    ]
    with pytest.raises(TaskUnavailableError):
        registry.close_task(start.task_id, "9" * 32)


def test_concurrent_task_close_runs_cleanup_once_and_echoes_both_callers() -> None:
    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.cleanup_entered = Event()
            self.release_cleanup = Event()

        def unsubscribe(self, session_id):
            self.cleanup_entered.set()
            assert self.release_cleanup.wait(2)
            super().unsubscribe(session_id)

    service = Service()
    registry, _ = _registry(service)
    start = _start(registry)
    results = []
    errors = []

    def close() -> None:
        try:
            results.append(registry.close_task(start.task_id, start.session_id))
        except BaseException as error:
            errors.append(error)

    _mark_terminal_drained(registry, start)
    first = Thread(target=close)
    second = Thread(target=close)
    first.start()
    assert service.cleanup_entered.wait(1)
    second.start()
    service.release_cleanup.set()
    first.join(1)
    second.join(1)

    assert errors == []
    assert results == [
        TaskCloseView(start.task_id, start.session_id),
        TaskCloseView(start.task_id, start.session_id),
    ]
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("drop_plan", REQUEST),
    ]


def test_task_capacity_is_hard_and_existing_command_replay_still_converges() -> None:
    assert drain_module._TASK_CAPACITY == 48
    assert drain_module._CLOSE_RECEIPT_CAPACITY == 48

    class Service(_Service):
        def start_plan(self, source, target, **kwargs):
            del source, target
            command_id = kwargs["command_id"]
            return PlanSession(command_id, command_id)

    tokens = iter(f"{value:032x}" for value in range(1, 10))
    registry = TaskRegistry(
        Service(),
        token=lambda: next(tokens),
        task_capacity=2,
    )
    first_command = "1" * 32
    second_command = "2" * 32
    third_command = "3" * 32
    first = registry.start_plan(
        "source-1",
        "target-1",
        deletion_policy=None,
        command_id=first_command,
    )
    registry.start_plan(
        "source-2",
        "target-2",
        deletion_policy=None,
        command_id=second_command,
    )

    assert registry.start_plan(
        "source-1",
        "target-1",
        deletion_policy=None,
        command_id=first_command,
    ) == first
    with pytest.raises(TaskUnavailableError, match="capacity"):
        registry.start_plan(
            "source-3",
            "target-3",
            deletion_policy=None,
            command_id=third_command,
        )

    _mark_terminal_drained(registry, first)
    registry.close_task(first.task_id, first.session_id)
    admitted = registry.start_plan(
        "source-3",
        "target-3",
        deletion_policy=None,
        command_id=third_command,
    )
    assert admitted.session_id == third_command


def test_concurrent_capacity_reserves_once_and_same_command_joins() -> None:
    service = _Service()
    service.release_start.clear()
    tokens = iter(f"{value:032x}" for value in range(1, 5))
    registry = TaskRegistry(
        service,
        token=lambda: next(tokens),
        task_capacity=1,
    )
    results = []
    errors = []

    def start(command_id: str) -> None:
        try:
            results.append(
                registry.start_plan(
                    "source",
                    "target",
                    deletion_policy=None,
                    command_id=command_id,
                )
            )
        except BaseException as error:
            errors.append(error)

    owner = Thread(target=start, args=("4" * 32,))
    owner.start()
    assert service.start_entered.wait(1)
    joiner = Thread(target=start, args=("4" * 32,))
    joiner.start()
    refused = Thread(target=start, args=("5" * 32,))
    refused.start()
    refused.join(1)
    service.release_start.set()
    owner.join(1)
    joiner.join(1)

    assert len(results) == 2
    assert results[0] == results[1]
    assert len(service.start_calls) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], TaskUnavailableError)


def test_repeated_task_close_bounds_active_state_and_close_receipts() -> None:
    class Service(_Service):
        def start_plan(self, source, target, **kwargs):
            del source, target
            command_id = kwargs["command_id"]
            return PlanSession(command_id, command_id)

    tokens = iter(f"{value:032x}" for value in range(1, 100))
    registry = TaskRegistry(
        Service(),
        token=lambda: next(tokens),
        task_capacity=1,
    )
    closed = []
    for value in range(drain_module._CLOSE_RECEIPT_CAPACITY + 1):
        command_id = f"{value + 1:032x}"
        started = registry.start_plan(
            f"source-{value}",
            f"target-{value}",
            deletion_policy=None,
            command_id=command_id,
        )
        _mark_terminal_drained(registry, started)
        closed.append(registry.close_task(started.task_id, started.session_id))

    assert registry._tasks == {}
    assert registry._commands == {}
    assert len(registry._close_receipts) == drain_module._CLOSE_RECEIPT_CAPACITY
    with pytest.raises(TaskUnavailableError):
        registry.close_task(closed[0].task_id, closed[0].session_id)
    assert registry.close_task(
        closed[-1].task_id,
        closed[-1].session_id,
    ) == closed[-1]
