"""Ordinary BR-G-33/SH-G-8 evidence for adapter task drains."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import gc
import json
from pathlib import Path
from threading import Condition, Event, Thread
from time import monotonic, sleep
from weakref import ref

import pytest

from _event_v5_fixtures import maximum_reliable_envelope
from namisync.core.events import (
    CORE_EVENT_SCHEMA_VERSION, Envelope, Gap, ItemOutcome, Progress, StateChanged,
    Terminal, TerminalSummary,
)
from namisync.core.evidence import Outcome
from namisync.core.session import OperationResult, SessionId, SessionState
from namisync.dispatcher import (
    Dispatcher,
    PreparedSession,
    SessionCleanupPending,
    SessionNotFound,
    WorkflowRegistration,
)
from namisync.dispatcher import event_bus as event_bus_module
from namisync.interfaces import service as service_module
from namisync.interfaces.service import NamiSyncService, PlanSession
from namisync.interfaces.web.bridge import BRIDGE_SCHEMA_VERSION, to_primitive_view
from namisync.interfaces.web import drain as drain_module
from namisync.interfaces.web.drain import (
    DrainBusyError,
    ObservationConflictError,
    TaskIntentConflictError,
    TaskCloseView,
    TaskDrainView,
    TaskRegistry,
    TaskSessionReleaseView,
    TaskStartView,
    TaskUnavailableError,
)
from namisync.workflows import PLAN_KIND
from namisync.workflows.views import (
    SessionEventView, SessionRecordView, operation_result_view, session_event_view,
)


REQUEST = "1" * 32
SESSION = "2" * 32
DRAIN = "3" * 32


def _attach_task_session(kwargs: dict[str, object], session_id: str) -> None:
    attachment = kwargs["session_attachment"]
    assert callable(attachment)
    rollback = attachment(session_id)
    assert callable(rollback)


def _raise_private_failure(
    references: list[object],
    *,
    exception_base: type[BaseException] = Exception,
    hostile_text: bool = False,
) -> None:
    payload_type = type("PrivatePayload", (), {})

    def render(_error: BaseException) -> str:
        raise AssertionError("private recovery failure text was rendered")

    failure_type = type(
        "PrivateFailure",
        (exception_base,),
        {"__str__": render} if hostile_text else {},
    )
    attached_payload = payload_type()
    cause_payload = payload_type()
    frame_only_payload = payload_type()
    cause = failure_type("private cause")
    cause.payload = cause_payload
    failure = failure_type("private failure")
    failure.payload = attached_payload
    references.extend(
        ref(value)
        for value in (
            payload_type,
            failure_type,
            attached_payload,
            cause_payload,
            frame_only_payload,
        )
    )
    raise failure from cause


def _private_malformed_recovery_record(
    references: list[object],
) -> SessionRecordView:
    payload_type = type("PrivateRecoveryPayload", (), {})
    string_type = type("PrivateRecoveryString", (str,), {})
    payload = payload_type()
    kind = string_type(PLAN_KIND)
    kind.payload = payload
    references.extend(ref(value) for value in (payload_type, string_type, payload))
    return replace(_record(), kind=kind)


def _private_invalid_plan(references: list[object]) -> object:
    payload_type = type("PrivatePlanPayload", (), {})
    plan_type = type("PrivatePlan", (), {})
    payload = payload_type()
    candidate = plan_type()
    candidate.payload = payload
    references.extend(
        ref(value) for value in (payload_type, plan_type, payload, candidate)
    )
    return candidate


def _private_plan_with_graph_string(references: list[object]) -> PlanSession:
    payload_type = type("PrivatePlanStringPayload", (), {})
    string_type = type("PrivatePlanString", (str,), {})
    payload = payload_type()
    request_id = string_type(REQUEST)
    request_id.payload = payload
    references.extend(
        ref(value) for value in (payload_type, string_type, payload)
    )
    return PlanSession(request_id, SESSION)


class _ManualClock:
    def __init__(self) -> None:
        self._condition = Condition()
        self._value = 0.0
        self._calls = 0

    def __call__(self) -> float:
        with self._condition:
            self._calls += 1
            self._condition.notify_all()
            return self._value

    @property
    def calls(self) -> int:
        with self._condition:
            return self._calls

    def advance_to(self, value: float) -> None:
        with self._condition:
            if value < self._value:
                raise ValueError("manual clock cannot move backward")
            self._value = value

    def wait_for_calls(self, expected: int) -> None:
        deadline = monotonic() + 1
        with self._condition:
            while self._calls < expected:
                remaining = deadline - monotonic()
                assert remaining > 0
                self._condition.wait(remaining)


def _event(sequence: int, body_type: str = "StateChanged") -> SessionEventView:
    bodies = {
        "StateChanged": StateChanged(SessionState.RUNNING),
        "Progress": Progress("execute", 0, None, 0, None, None),
        "Gap": Gap(1),
        "Terminal": Terminal(
            TerminalSummary.from_result(OperationResult(SessionState.COMPLETED))
        ),
    }
    return session_event_view(Envelope(
        SessionId(SESSION),
        sequence,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        CORE_EVENT_SCHEMA_VERSION,
        bodies[body_type],
    ))


def _record(*, terminal: bool = True) -> SessionRecordView:
    return SessionRecordView(
        SESSION,
        PLAN_KIND,
        "completed" if terminal else "pending",
        False,
        "2026-01-01T00:00:00+00:00",
        None,
        "2026-01-01T00:00:00+00:00" if terminal else None,
        operation_result_view(OperationResult(SessionState.COMPLETED))
        if terminal else None,
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
        _attach_task_session(kwargs, SESSION)
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


def _registry(
    service=None,
    *,
    clock=monotonic,
    drain_wait=0.2,
    progress_linger=drain_module._PROGRESS_LINGER_SECONDS,
    task_capacity=drain_module._TASK_CAPACITY,
):
    service = service or _Service()
    return TaskRegistry(
        service,
        token=lambda: "a" * 32,
        clock=clock,
        drain_wait=drain_wait,
        progress_linger=progress_linger,
        task_capacity=task_capacity,
    ), service


def _wake_task(registry: TaskRegistry, task_id: str) -> None:
    task = registry._tasks[task_id]
    with task.condition:
        task.condition.notify_all()


@dataclass
class _ProgressWait:
    clock: _ManualClock
    registry: TaskRegistry
    service: _Service
    task_id: str
    baseline_calls: int
    thread: Thread
    done: Event
    results: list[TaskDrainView]
    errors: list[BaseException]

    def finish(self) -> TaskDrainView:
        assert self.done.wait(1)
        self.thread.join(1)
        assert not self.errors
        assert len(self.results) == 1
        return self.results[0]

    def stop(self) -> None:
        if self.thread.is_alive():
            self.registry.begin_close()
            self.thread.join(1)


@contextmanager
def _progress_wait(
    *,
    drain_wait: float = 25.0,
    progress_linger: float = 10.0,
    progress_sequence: int | None = 2,
) -> Iterator[_ProgressWait]:
    clock = _ManualClock()
    registry, service = _registry(
        clock=clock,
        drain_wait=drain_wait,
        progress_linger=progress_linger,
    )
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)
    if progress_sequence is not None:
        service.sink(_event(progress_sequence, "Progress"))
    baseline_calls = clock.calls
    done = Event()
    results: list[TaskDrainView] = []
    errors: list[BaseException] = []

    def drain() -> None:
        try:
            results.append(
                registry.drain(
                    start.task_id,
                    SESSION,
                    "5" * 32,
                    replay_from=None,
                )
            )
        except BaseException as error:
            errors.append(error)
        finally:
            done.set()

    thread = Thread(target=drain)
    thread.start()
    waiting = _ProgressWait(
        clock,
        registry,
        service,
        start.task_id,
        baseline_calls,
        thread,
        done,
        results,
        errors,
    )
    try:
        clock.wait_for_calls(baseline_calls + 2)
        yield waiting
    finally:
        waiting.stop()


def _start(registry: TaskRegistry, command_id: str = "4" * 32):
    return registry.start_plan(
        "source",
        "target",
        deletion_policy=None,
        command_id=command_id,
    )


def test_maximum_reliable_head_drains_alone_below_the_bridge_response_wall() -> None:
    registry, service = _registry()
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)
    value = maximum_reliable_envelope()
    event = SessionEventView(
        SESSION,
        2,
        str(value["at"]),
        CORE_EVENT_SCHEMA_VERSION,
        str(value["body_type"]),
        value["body"],  # type: ignore[arg-type]
    )
    service.sink(event)

    drained = registry.drain(
        start.task_id,
        SESSION,
        "5" * 32,
        replay_from=None,
    )
    response = {
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "request_id": "6" * 32,
        "ok": True,
        "result": to_primitive_view(drained),
    }
    encoded = json.dumps(
        response,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert len(drained.updates) == 1
    assert drained.updates[0].event == event  # type: ignore[union-attr]
    assert len(encoded) < 8_388_608
    registry.begin_close()


def _envelope_item_id(run_index: int, tick: int, item_index: int) -> str:
    return f"{run_index * 1_000 + tick * 10 + item_index + 1:032x}"


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
                    "execute",
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
                    item_id=f"{index + 1:032x}",
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


@dataclass
class _EnvelopeRun:
    name: str
    index: int
    tick_releases: tuple[Event, ...]
    tick_emitted: tuple[Event, ...]
    abort: Event
    entered: Event
    progress_emitted: int = 0
    reliable_emitted: int = 0


@dataclass
class _EnvelopeInvocation:
    run_state: _EnvelopeRun

    def run(self, context):
        state = self.run_state
        state.entered.set()
        reliable_pattern = (3, 3, 2, 2)
        for tick in range(60):
            state.tick_releases[tick].wait()
            if state.abort.is_set():
                return OperationResult(SessionState.CANCELED, canceled=True)
            for offset in range(25):
                completed = tick * 25 + offset + 1
                context.emit(
                    Progress(
                        "execute",
                        items_done=completed,
                        items_total=1_500,
                        bytes_done=completed,
                        bytes_total=1_500,
                        current_path=f"{state.name}-progress-{completed}",
                    )
                )
                state.progress_emitted += 1
            reliable_count = reliable_pattern[(state.index + tick) % 4]
            for item_index in range(reliable_count):
                context.emit(
                    ItemOutcome(
                        item_id=_envelope_item_id(
                            state.index,
                            tick,
                            item_index,
                        ),
                        kind="copy",
                        path=f"{state.name}-{tick:02d}-{item_index}.txt",
                        outcome=Outcome.SUCCEEDED,
                    )
                )
                state.reliable_emitted += 1
            state.tick_emitted[tick].set()
        return OperationResult(SessionState.COMPLETED)

    def snapshot(self) -> bytes:
        return self.run_state.name.encode("utf-8")


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
        task.terminal_record = replace(_record(), session_id=start.session_id)
        task.terminal_pending = True
        task.condition.notify_all()
    drained = registry.drain(
        start.task_id,
        start.session_id,
        DRAIN,
        replay_from=None,
    )
    assert any(update.update_type == "record" for update in drained.updates)


def test_failed_admission_observer_retains_task_capacity_until_dispatcher_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initiating_failure = RuntimeError("pending publication failed")

    class FailingClock:
        def __init__(self) -> None:
            self.calls = 0

        def now(self):
            self.calls += 1
            if self.calls == 2:
                raise initiating_failure
            return datetime.now(timezone.utc)

    run_release = Event()
    run_release.set()
    run = _IntegratedRun(Event(), run_release)
    dispatcher = Dispatcher(
        {
            PLAN_KIND: WorkflowRegistration(
                prepare=lambda request: PreparedSession(
                    request.request_id.encode("utf-8")
                ),
                open=lambda payload: _IntegratedInvocation(
                    payload.decode("utf-8"),
                    run,
                ),
            ),
        },
        clock=FailingClock(),
        audit_timeout=0.05,
    )
    monkeypatch.setattr(service_module, "_dispatcher", lambda _runtime: dispatcher)
    service = NamiSyncService(tmp_path / "ledger.db", tmp_path / "history.db")

    class Observer:
        def __init__(self) -> None:
            self.allow_retirement = False
            self.observations: dict[str, tuple[object, object]] = {}
            self.rollback_attempts: list[tuple[str, object]] = []
            self.retired = Event()

        def adopt(self, session_id, sink, stream):
            del stream
            token = object()
            self.observations[session_id] = (sink, token)

            def rollback() -> None:
                current = self.observations.get(session_id)
                if current is None or current[1] is not token:
                    return
                self.rollback_attempts.append((session_id, token))
                if not self.allow_retirement:
                    raise TimeoutError("observer did not stop")
                self.observations.pop(session_id)
                self.retired.set()

            return rollback

        def retains_observation(self, session_id, sink):
            current = self.observations.get(session_id)
            return current is not None and current[0] is sink

        def unsubscribe(self, session_id):
            self.observations.pop(session_id, None)

        def close(self):
            self.observations.clear()

    observer = Observer()
    service._observer = observer
    service_failures: list[BaseException] = []

    class RecordingService:
        def start_plan(self, *args, **kwargs):
            try:
                return service.start_plan(*args, **kwargs)
            except BaseException as error:
                service_failures.append(error)
                raise

        def __getattr__(self, name):
            return getattr(service, name)

    registry = TaskRegistry(RecordingService(), task_capacity=1)
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    second_command = "b" * 32

    try:
        with pytest.raises(RuntimeError, match="task start failed"):
            registry.start_plan(
                str(source),
                str(target),
                deletion_policy=None,
                command_id="a" * 32,
            )

        assert service_failures == [initiating_failure]
        assert len(observer.rollback_attempts) == 1
        failed_session = observer.rollback_attempts[0][0]
        assert failed_session in observer.observations
        assert service._session_receipts == {}

        with pytest.raises(TaskUnavailableError, match="capacity"):
            registry.start_plan(
                str(source),
                str(target),
                deletion_policy=None,
                command_id=second_command,
            )

        observer.allow_retirement = True
        with pytest.raises(SessionCleanupPending):
            dispatcher.submit(PLAN_KIND, object())
        assert observer.retired.wait(1)
        deadline = monotonic() + 1
        while registry._reservations and monotonic() < deadline:
            sleep(0.001)
        assert registry._reservations == {}

        admitted = registry.start_plan(
            str(source),
            str(target),
            deletion_policy=None,
            command_id=second_command,
        )
        assert admitted.session_id != failed_session
        assert [item[0] for item in observer.rollback_attempts] == [
            failed_session,
            failed_session,
        ]
        assert admitted.session_id in observer.observations

        _wait_terminal(dispatcher, admitted.session_id)
        _mark_terminal_drained(registry, admitted)
        registry.close_task(admitted.task_id, admitted.session_id)
    finally:
        registry.begin_close()
        service.close(timeout=2)


def test_br_g_33_integrated_admission_and_visible_overflow_gap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adopt_entered = Event()
    adopt_release = Event()
    adopted_session_ids = []
    overflow_release = Event()
    overflow_finish = Event()
    overflow_done = Event()
    runs = {
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

        source, target = roots("overflow")
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
        assert not runs["overflow"].entered.wait(0.05)
        adopt_release.set()
        start_thread.join(2)
        assert not start_thread.is_alive()
        assert not start_errors
        overflow = start_results[0]
        assert runs["overflow"].entered.wait(1)
        pending = registry.drain(
            overflow.task_id,
            overflow.session_id,
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

        assert dispatcher.get(overflow.session_id).result is None
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
        emitted_item_ids = {f"{index + 1:032x}" for index in range(260)}
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
        full_result = dispatcher.get(overflow.session_id).result
        assert full_result is not None
        assert len(full_result.items) == 260
        assert any(
            update.update_type == "event" and update.event.body_type == "Terminal"
            for update in terminal_updates
        )
    finally:
        adopt_release.set()
        overflow_release.set()
        overflow_finish.set()
        registry.begin_close()
        registry.unsubscribe_all()
        service.close(timeout=2)


def test_sh_g_8_br_g_42_normal_event_envelope_is_bounded_and_lossless(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tick_releases = tuple(Event() for _ in range(60))
    abort = Event()
    runs = {
        f"envelope-{index}": _EnvelopeRun(
            f"envelope-{index}",
            index,
            tick_releases,
            tuple(Event() for _ in range(60)),
            abort,
            Event(),
        )
        for index in range(4)
    }

    def prepare_plan(request) -> PreparedSession:
        name = Path(request.source_path).name
        return PreparedSession(name.encode("utf-8"))

    def open_plan(payload: bytes) -> _EnvelopeInvocation:
        return _EnvelopeInvocation(runs[payload.decode("utf-8")])

    dispatcher = Dispatcher(
        {PLAN_KIND: WorkflowRegistration(prepare_plan, open_plan)}
    )
    monkeypatch.setattr(service_module, "_dispatcher", lambda _runtime: dispatcher)
    service = NamiSyncService(tmp_path / "ledger.db", tmp_path / "history.db")
    real_adopt = service._observer.adopt
    adopted_session_ids = []
    observed_adapter_queue_lengths = []
    observed_dispatcher_queue_lengths = []

    class _ObservedAdapterQueue(deque):
        def __init__(self, values=()):
            super().__init__(values)
            observed_adapter_queue_lengths.append(len(self))

        def append(self, value):
            super().append(value)
            observed_adapter_queue_lengths.append(len(self))

    class _ObservedDispatcherQueue(deque):
        def __init__(self, values=()):
            super().__init__(values)
            observed_dispatcher_queue_lengths.append(len(self))

        def append(self, value):
            super().append(value)
            observed_dispatcher_queue_lengths.append(len(self))

    def observed_adapter_deque(values=()):
        return _ObservedAdapterQueue(values)

    real_event_stream_init = event_bus_module.EventStream.__init__

    def instrumented_event_stream_init(stream, *args, **kwargs):
        real_event_stream_init(stream, *args, **kwargs)
        stream._items = _ObservedDispatcherQueue(stream._items)

    monkeypatch.setattr(drain_module, "deque", observed_adapter_deque)
    monkeypatch.setattr(
        event_bus_module.EventStream,
        "__init__",
        instrumented_event_stream_init,
    )

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
        adopted_session_ids.append(session_id)
        return rollback

    monkeypatch.setattr(service._observer, "adopt", instrumented_adopt)
    task_tokens = iter(f"{index:032x}" for index in range(1, 16))
    registry = TaskRegistry(
        service,
        token=lambda: next(task_tokens),
        drain_wait=0.1,
        progress_linger=0.001,
    )
    drain_ids = iter(f"{index:032x}" for index in range(100, 2_000))
    starts = []
    delivered_reliable: dict[str, list[str]] = {}
    delivered_progress: dict[str, list[int]] = {}
    terminal_records = {}

    try:
        for index in range(4):
            name = f"envelope-{index}"
            source = tmp_path / "sources" / name
            target = tmp_path / "targets" / name
            source.mkdir(parents=True)
            target.mkdir(parents=True)
            start = registry.start_plan(
                str(source),
                str(target),
                deletion_policy=None,
                command_id=f"{index + 1:032x}",
            )
            starts.append(start)
            task = registry._tasks[start.task_id]
            with task.condition:
                task.queue = _ObservedAdapterQueue(task.queue)
            delivered_reliable[start.session_id] = []
            delivered_progress[start.session_id] = []
            assert runs[name].entered.wait(1)

        assert set(adopted_session_ids) == {
            start.session_id for start in starts
        }
        assert len(adopted_session_ids) == 4
        assert dispatcher._subscriber_capacity == 64
        assert drain_module._CAPACITY == 64
        assert all(
            dispatcher.get(start.session_id).state is SessionState.RUNNING
            for start in starts
        )
        assert all(
            run.progress_emitted == 0 and run.reliable_emitted == 0
            for run in runs.values()
        )
        assert not any(release.is_set() for release in tick_releases)

        fixture_deadline = monotonic() + 15
        reliable_pattern = (3, 3, 2, 2)
        for tick in range(60):
            tick_releases[tick].set()
            for run in runs.values():
                remaining = fixture_deadline - monotonic()
                assert remaining > 0 and run.tick_emitted[tick].wait(remaining)
            for index, start in enumerate(starts):
                expected_ids = {
                    _envelope_item_id(index, tick, item_index)
                    for item_index in range(
                        reliable_pattern[(index + tick) % 4]
                    )
                }
                seen_this_tick: set[str] = set()
                while seen_this_tick != expected_ids:
                    assert monotonic() < fixture_deadline
                    batch = registry.drain(
                        start.task_id,
                        start.session_id,
                        next(drain_ids),
                        replay_from=None,
                    )
                    for update in batch.updates:
                        if update.update_type == "record":
                            terminal_records[start.session_id] = update.record
                            continue
                        event = update.event
                        assert event.body_type != "Gap"
                        if event.body_type == "ItemOutcome":
                            item_id = event.body["item_id"]
                            delivered_reliable[start.session_id].append(item_id)
                            if item_id in expected_ids:
                                seen_this_tick.add(item_id)
                        elif event.body_type == "Progress":
                            delivered_progress[start.session_id].append(
                                event.body["items_done"]
                            )
                assert seen_this_tick == expected_ids

        for start in starts:
            if start.session_id not in terminal_records:
                updates = _drain_until_record(
                    registry,
                    start.task_id,
                    start.session_id,
                    drain_ids,
                )
                for update in updates:
                    if update.update_type == "record":
                        terminal_records[start.session_id] = update.record
                    elif update.event.body_type == "Progress":
                        delivered_progress[start.session_id].append(
                            update.event.body["items_done"]
                        )
                    elif update.event.body_type == "ItemOutcome":
                        delivered_reliable[start.session_id].append(
                            update.event.body["item_id"]
                        )
                    else:
                        assert update.event.body_type != "Gap"

        assert sum(run.progress_emitted for run in runs.values()) == 6_000
        assert sum(run.reliable_emitted for run in runs.values()) == 600
        assert sum(map(len, delivered_reliable.values())) == 600
        for index, start in enumerate(starts):
            expected = [
                _envelope_item_id(index, tick, item_index)
                for tick in range(60)
                for item_index in range(reliable_pattern[(index + tick) % 4])
            ]
            assert delivered_reliable[start.session_id] == expected
            progress = delivered_progress[start.session_id]
            assert progress
            assert all(
                earlier < later
                for earlier, later in zip(progress, progress[1:], strict=False)
            )
            assert progress[-1] == 1_500
            record = terminal_records[start.session_id]
            assert record.state == "completed"
            assert record.started_at is not None
            assert record.ended_at is not None
            result = record.result
            assert result is not None
            assert result.filesystem == "completed"
            assert result.headline == "success"
            assert result.integrity == "not-run"
            assert result.recording == "ok"
            assert result.audit == "ok"
            assert result.disposition == "ran"
            assert result.canceled is False
            assert result.error is None
            full_result = dispatcher.get(start.session_id).result
            assert full_result is not None
            assert [item.item_id for item in full_result.items] == expected
            assert all(item.outcome is Outcome.SUCCEEDED for item in full_result.items)
        assert set(terminal_records) == {
            start.session_id for start in starts
        }
        assert observed_adapter_queue_lengths
        assert 1 <= max(observed_adapter_queue_lengths) <= 64
        assert observed_dispatcher_queue_lengths
        assert 1 <= max(observed_dispatcher_queue_lengths) <= 64
    finally:
        abort.set()
        for release in tick_releases:
            release.set()
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


@pytest.mark.parametrize(
    ("failure", "expected_type", "expected_message"),
    (
        (
            ObservationConflictError("private observation"),
            ObservationConflictError,
            "task start observation conflicted",
        ),
        (
            TaskUnavailableError("private availability"),
            TaskUnavailableError,
            "task became unavailable during start",
        ),
        (
            KeyboardInterrupt("private interruption"),
            KeyboardInterrupt,
            "task start was interrupted",
        ),
        (
            SystemExit("private exit"),
            KeyboardInterrupt,
            "task start was interrupted",
        ),
        (
            GeneratorExit("private generator exit"),
            KeyboardInterrupt,
            "task start was interrupted",
        ),
        (ValueError("private generic"), RuntimeError, "task start failed"),
    ),
)
def test_failed_start_raises_fresh_closed_failure_category(
    failure: BaseException,
    expected_type: type[BaseException],
    expected_message: str,
) -> None:
    class Service(_Service):
        def start_plan(self, source, target, **kwargs):
            del source, target, kwargs
            raise failure

    registry, _ = _registry(Service())

    with pytest.raises(expected_type) as raised:
        _start(registry)

    assert raised.value is not failure
    assert str(raised.value) == expected_message
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert registry._commands == {}
    assert registry._tasks == {}


def test_invalid_plan_return_cleans_only_independently_attached_session(
) -> None:
    graph_references: list[object] = []

    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.invalid = True

        def start_plan(self, source, target, **kwargs):
            del source, target
            _attach_task_session(kwargs, SESSION)
            if self.invalid:
                self.invalid = False
                return _private_invalid_plan(graph_references)
            return PlanSession(REQUEST, SESSION)

    service = Service()
    registry, _ = _registry(service, task_capacity=1)

    with pytest.raises(RuntimeError) as raised:
        _start(registry)

    assert str(raised.value) == "task start failed"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
    ]
    assert registry._commands == {}
    assert registry._tasks == {}
    assert registry._reservations == {}

    admitted = registry.start_plan(
        "other-source",
        "other-target",
        deletion_policy=None,
        command_id="5" * 32,
    )
    assert admitted.session_id == SESSION


def test_exact_plan_with_graph_string_is_rejected_and_released() -> None:
    graph_references: list[object] = []

    class Service(_Service):
        def start_plan(self, source, target, **kwargs):
            del source, target
            _attach_task_session(kwargs, SESSION)
            return _private_plan_with_graph_string(graph_references)

    service = Service()
    registry, _ = _registry(service)

    with pytest.raises(RuntimeError, match="task start failed") as raised:
        _start(registry)

    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
    ]
    assert registry._commands == {}
    assert registry._tasks == {}


def test_validated_plan_candidate_fields_are_not_reread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph_references: list[object] = []
    candidates: list[PlanSession] = []

    class Service(_Service):
        def start_plan(self, source, target, **kwargs):
            del source, target
            _attach_task_session(kwargs, SESSION)
            kwargs["observation_sink"](_event(1))
            candidate = PlanSession(REQUEST, SESSION)
            candidates.append(candidate)
            return candidate

    require_opaque_id = drain_module._require_opaque_id

    def mutate_after_request_validation(value: object, label: str) -> None:
        require_opaque_id(value, label)
        if label == "plan request id":
            candidate = candidates.pop()
            private = _private_plan_with_graph_string(graph_references)
            object.__setattr__(candidate, "request_id", private.request_id)

    monkeypatch.setattr(
        drain_module,
        "_require_opaque_id",
        mutate_after_request_validation,
    )
    service = Service()
    registry, _ = _registry(service)

    started = _start(registry)

    assert started == TaskStartView("task-" + "a" * 32, REQUEST, SESSION)
    assert candidates == []
    assert service.cleanup == []
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)


@pytest.mark.parametrize(
    "candidate",
    (
        PlanSession("invalid", SESSION),
        PlanSession(REQUEST, "invalid"),
    ),
)
def test_invalid_plan_ids_never_acquire_compensation_authority(
    candidate: PlanSession,
) -> None:
    class Service(_Service):
        def start_plan(self, source, target, **kwargs):
            del source, target, kwargs
            return candidate

    service = Service()
    registry, _ = _registry(service)

    with pytest.raises(RuntimeError, match="task start failed"):
        _start(registry)

    assert service.cleanup == []
    assert registry._commands == {}
    assert registry._tasks == {}


def test_concurrent_failed_start_retires_private_exception_graph() -> None:
    graph_references: list[object] = []

    class Service(_Service):
        def start_plan(self, source, target, **kwargs):
            del source, target, kwargs
            self.start_entered.set()
            assert self.release_start.wait(2)
            _raise_private_failure(graph_references)

    service = Service()
    service.release_start.clear()
    registry, _ = _registry(service)
    errors: list[BaseException] = []

    def start() -> None:
        try:
            _start(registry)
        except BaseException as error:
            errors.append(error)

    first = Thread(target=start)
    second = Thread(target=start)
    first.start()
    assert service.start_entered.wait(1)
    second.start()
    deadline = monotonic() + 1
    participants = 0
    while monotonic() < deadline:
        with registry._condition:
            participants = registry._commands["4" * 32].participants
        if participants == 2:
            break
        sleep(0.005)
    assert participants == 2
    service.release_start.set()
    first.join(1)
    second.join(1)

    assert not first.is_alive()
    assert not second.is_alive()
    assert len(errors) == 2
    assert errors[0] is not errors[1]
    assert all(type(error) is RuntimeError for error in errors)
    assert all(str(error) == "task start failed" for error in errors)
    assert all(error.__cause__ is None for error in errors)
    assert all(error.__context__ is None for error in errors)
    assert all(reference() is None for reference in graph_references[2:])
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)
    assert registry._commands == {}
    assert registry._tasks == {}


def test_br_g_33_progress_linger_default_and_constructor_boundary() -> None:
    assert TaskRegistry(_Service())._progress_linger == 0.150
    assert TaskRegistry(_Service(), progress_linger=1)._progress_linger == 1.0
    for value in (True, False, None, "0.150"):
        with pytest.raises(TypeError, match="progress linger"):
            TaskRegistry(_Service(), progress_linger=value)
    invalid_numbers = (
        0.0,
        -0.001,
        float("nan"),
        float("inf"),
        float("-inf"),
    )
    for value in invalid_numbers:
        with pytest.raises(ValueError, match="positive and finite"):
            TaskRegistry(_Service(), progress_linger=value)


def test_br_g_33_progress_only_linger_has_one_fixed_cadence_deadline() -> None:
    with _progress_wait() as waiting:
        waiting.clock.advance_to(9.0)
        waiting.service.sink(_event(3, "Progress"))
        waiting.clock.wait_for_calls(waiting.baseline_calls + 3)
        assert not waiting.done.is_set()

        waiting.clock.advance_to(10.0)
        waiting.service.sink(_event(4, "Progress"))
        result = waiting.finish()

        assert [update.event.sequence for update in result.updates] == [4]


def test_br_g_33_first_progress_may_wait_the_full_default_linger() -> None:
    with _progress_wait(
        progress_linger=0.150,
        progress_sequence=None,
    ) as waiting:
        waiting.clock.advance_to(1.0)
        waiting.service.sink(_event(2, "Progress"))
        waiting.clock.wait_for_calls(waiting.baseline_calls + 3)

        waiting.clock.advance_to(1.149)
        _wake_task(waiting.registry, waiting.task_id)
        waiting.clock.wait_for_calls(waiting.baseline_calls + 4)
        assert not waiting.done.is_set()

        waiting.clock.advance_to(1.150)
        _wake_task(waiting.registry, waiting.task_id)
        result = waiting.finish()

        assert [update.event.sequence for update in result.updates] == [2]


def test_br_g_33_prequeued_progress_keeps_its_first_availability_deadline() -> None:
    clock = _ManualClock()
    registry, service = _registry(
        clock=clock,
        drain_wait=25.0,
        progress_linger=0.150,
    )
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)
    service.sink(_event(2, "Progress"))

    clock.advance_to(0.151)
    drained = registry.drain(
        start.task_id,
        SESSION,
        "5" * 32,
        replay_from=None,
    )

    assert [update.event.sequence for update in drained.updates] == [2]


def test_br_g_33_progress_linger_starts_at_availability_and_keeps_outer_cap() -> None:
    with _progress_wait(
        drain_wait=12.0,
        progress_linger=10.0,
        progress_sequence=None,
    ) as waiting:
        waiting.clock.advance_to(5.0)
        waiting.service.sink(_event(2, "Progress"))
        waiting.clock.wait_for_calls(waiting.baseline_calls + 3)

        waiting.clock.advance_to(10.0)
        _wake_task(waiting.registry, waiting.task_id)
        waiting.clock.wait_for_calls(waiting.baseline_calls + 4)
        assert not waiting.done.is_set()

        waiting.clock.advance_to(12.0)
        _wake_task(waiting.registry, waiting.task_id)
        result = waiting.finish()

        assert [update.event.sequence for update in result.updates] == [2]


@pytest.mark.parametrize(
    "body_type",
    ["StateChanged", "Gap", "Terminal"],
)
def test_br_g_33_reliable_events_bypass_progress_linger(body_type: str) -> None:
    with _progress_wait() as waiting:
        waiting.service.sink(_event(3, body_type))
        result = waiting.finish()

        assert [
            (update.event.sequence, update.event.body_type)
            for update in result.updates
        ] == [(2, "Progress"), (3, body_type)]


def test_br_g_33_terminal_record_bypasses_progress_linger() -> None:
    with _progress_wait() as waiting:
        terminal = _record()
        waiting.service.sink(terminal)
        result = waiting.finish()

        assert [update.update_type for update in result.updates] == [
            "event",
            "record",
        ]
        assert result.updates[1].record is terminal
        assert waiting.registry._tasks[waiting.task_id].terminal_delivered


def test_br_g_33_recovered_progress_bypasses_progress_linger() -> None:
    class Service(_Service):
        def reobserve(self, session_id, sink, from_sequence):
            self.reobserve_calls.append((session_id, sink, from_sequence))
            sink(_event(from_sequence, "Progress"))
            return self.reobserve_result

    clock = _ManualClock()
    service = Service()
    registry, _ = _registry(
        service,
        clock=clock,
        drain_wait=25.0,
        progress_linger=10.0,
    )
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)
    baseline_calls = clock.calls

    recovered = registry.drain(
        start.task_id,
        SESSION,
        "5" * 32,
        replay_from=2,
    )

    assert clock.calls == baseline_calls + 2
    assert service.reobserve_calls[0][2] == 2
    assert [update.event.sequence for update in recovered.updates] == [2]


def test_br_g_33_progress_coalescing_keeps_numeric_holes_without_recovery() -> None:
    with _progress_wait() as waiting:
        waiting.service.sink(_event(4, "Progress"))
        waiting.service.sink(_event(5))
        result = waiting.finish()

        assert [update.event.sequence for update in result.updates] == [4, 5]
        assert all(
            update.event.body_type != "Gap" for update in result.updates
        )
        assert waiting.service.reobserve_calls == []


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
    assert service.reobserve_calls == []


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

    assert [item.event.sequence for item in first.updates] == list(range(2, 66))
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
    with _progress_wait(drain_wait=1.0) as waiting:
        with pytest.raises(DrainBusyError):
            waiting.registry.drain(
                waiting.task_id,
                SESSION,
                "6" * 32,
                replay_from=None,
            )
        superseded = waiting.finish()
        waiting.clock.advance_to(10.0)
        after = waiting.registry.drain(
            waiting.task_id,
            SESSION,
            "7" * 32,
            replay_from=None,
        )

        assert superseded.updates == ()
        assert [item.event.sequence for item in after.updates] == [2]


def test_br_g_33_competing_recovery_cannot_reobserve_before_busy_refusal() -> None:
    with _progress_wait(drain_wait=1.0) as waiting:
        with pytest.raises(DrainBusyError):
            waiting.registry.drain(
                waiting.task_id,
                SESSION,
                "6" * 32,
                replay_from=2,
            )

        assert waiting.finish().updates == ()
        assert waiting.service.reobserve_calls == []


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


def test_br_g_33_gap_retained_tail_and_terminal_record_remain_ordered() -> None:
    class Service(_Service):
        def reobserve(self, session_id, sink, from_sequence):
            self.reobserve_calls.append((session_id, sink, from_sequence))
            sink(
                SessionEventView(
                    session_id,
                    2,
                    "2026-01-01T00:00:00+00:00",
                    CORE_EVENT_SCHEMA_VERSION,
                    "Gap",
                    {"first_missed_seq": 2},
                )
            )
            sink(
                SessionEventView(
                    session_id,
                    4,
                    "2026-01-01T00:00:00+00:00",
                    CORE_EVENT_SCHEMA_VERSION,
                    "StateChanged",
                    {"state": "running"},
                )
            )
            return self.reobserve_result

    service = Service()
    terminal = _record()
    service.reobserve_result = terminal
    registry, _ = _registry(service)
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)

    drained = registry.drain(
        start.task_id,
        SESSION,
        "5" * 32,
        replay_from=2,
    )

    assert [update.update_type for update in drained.updates] == [
        "event",
        "event",
        "record",
    ]
    assert [
        update.event.body_type for update in drained.updates[:2]
    ] == ["Gap", "StateChanged"]
    assert drained.updates[0].event.body == {"first_missed_seq": 2}
    assert drained.updates[2].record is terminal


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

    with pytest.raises(ObservationConflictError) as raised:
        registry.drain(
            start.task_id,
            SESSION,
            "5" * 32,
            replay_from=2,
        )

    assert str(raised.value) == "task observation recovery conflicted"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None

    assert not registry._tasks[start.task_id].queue
    assert registry._tasks[start.task_id].terminal_record is None


@pytest.mark.parametrize(
    ("exception_base", "expected_type", "expected_message"),
    (
        (Exception, RuntimeError, "task observation recovery failed"),
        (
            ObservationConflictError,
            ObservationConflictError,
            "task observation recovery conflicted",
        ),
        (
            TaskUnavailableError,
            TaskUnavailableError,
            "task became unavailable during observation recovery",
        ),
        (
            KeyboardInterrupt,
            KeyboardInterrupt,
            "task observation recovery was interrupted",
        ),
        (
            SystemExit,
            KeyboardInterrupt,
            "task observation recovery was interrupted",
        ),
        (
            GeneratorExit,
            KeyboardInterrupt,
            "task observation recovery was interrupted",
        ),
    ),
    ids=(
        "exception",
        "observation-conflict",
        "task-unavailable",
        "keyboard-interrupt",
        "system-exit",
        "generator-exit",
    ),
)
def test_br_g_33_failed_recovery_retires_private_graph_and_invalidates_callbacks(
    exception_base: type[BaseException],
    expected_type: type[BaseException],
    expected_message: str,
) -> None:
    graph_references: list[object] = []

    class Service(_Service):
        recovery_sink = None

        def reobserve(self, session_id, sink, from_sequence):
            del session_id, from_sequence
            self.recovery_sink = sink
            _raise_private_failure(
                graph_references,
                exception_base=exception_base,
                hostile_text=True,
            )

    service = Service()
    registry, _ = _registry(service)
    start = _start(registry)
    registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)

    with pytest.raises(expected_type) as raised:
        registry.drain(
            start.task_id,
            SESSION,
            "5" * 32,
            replay_from=2,
        )
    assert str(raised.value) == expected_message
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    service.recovery_sink(_event(2))

    assert not registry._tasks[start.task_id].queue
    task = registry._tasks[start.task_id]
    assert not task.transition
    assert task.active_drain is None
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)


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
    with _progress_wait(drain_wait=1.0) as waiting:
        waiting.registry.begin_close()
        assert waiting.done.wait(1)
        waiting.thread.join(1)

        assert len(waiting.errors) == 1
        assert isinstance(waiting.errors[0], TaskUnavailableError)
        assert waiting.service.cleanup == []
        waiting.registry.unsubscribe_all()
        assert waiting.service.cleanup == [("unsubscribe", SESSION)]
        waiting.registry.unsubscribe_all()
        assert waiting.service.cleanup == [("unsubscribe", SESSION)]


def test_unsubscribe_all_retires_dependency_frames_and_preserves_retry() -> None:
    graph_references: list[object] = []

    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.unsubscribe_attempts = 0

        def unsubscribe(self, session_id):
            self.unsubscribe_attempts += 1
            if self.unsubscribe_attempts == 1:
                _raise_private_failure(
                    graph_references,
                    exception_base=BaseException,
                )
            super().unsubscribe(session_id)

    service = Service()
    registry, _ = _registry(service)
    _start(registry)
    registry.begin_close()

    with pytest.raises(BaseException) as raised:
        registry.unsubscribe_all()

    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert all(reference() is None for reference in graph_references[3:])
    registry.unsubscribe_all()
    assert service.cleanup == [("unsubscribe", SESSION)]
    del raised
    gc.collect()
    assert all(reference() is None for reference in graph_references)


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


def test_terminal_session_release_refuses_before_record_delivery() -> None:
    registry, service = _registry()
    start = _start(registry)

    with pytest.raises(TaskUnavailableError, match="terminal record"):
        registry.release_terminal_session(start.task_id, start.session_id)

    assert service.cleanup == []
    assert start.task_id in registry._tasks


def test_terminal_session_release_retains_plan_receipt_and_task_capacity() -> None:
    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.plans = {REQUEST: object()}

        def get_plan_review(self, request_id):
            return self.plans[request_id]

        def drop_plan(self, request_id):
            self.cleanup.append(("drop_plan", request_id))
            self.plans.pop(request_id, None)

    service = Service()
    registry = TaskRegistry(
        service,
        token=lambda: "a" * 32,
        task_capacity=1,
    )
    command_id = "4" * 32
    start = _start(registry, command_id)
    _mark_terminal_drained(registry, start)

    released = registry.release_terminal_session(
        start.task_id,
        start.session_id,
    )

    assert released == TaskSessionReleaseView(start.task_id, start.session_id)
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
    ]
    assert service.get_plan_review(REQUEST) is service.plans[REQUEST]
    assert start.task_id in registry._tasks
    assert command_id in registry._commands
    assert registry.replay_start(command_id, None) == start  # type: ignore[arg-type]
    with pytest.raises(TaskUnavailableError, match="capacity"):
        registry.start_plan(
            "other-source",
            "other-target",
            deletion_policy=None,
            command_id="5" * 32,
        )
    with pytest.raises(TaskUnavailableError):
        registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)


def test_terminal_session_release_lost_response_replay_is_idempotent() -> None:
    registry, service = _registry()
    start = _start(registry)
    _mark_terminal_drained(registry, start)

    first = registry.release_terminal_session(start.task_id, start.session_id)
    replay = registry.release_terminal_session(start.task_id, start.session_id)

    assert first == replay == TaskSessionReleaseView(
        start.task_id,
        start.session_id,
    )
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
    ]


def test_delayed_terminal_release_converges_from_close_receipt() -> None:
    registry, service = _registry()
    start = _start(registry)
    _mark_terminal_drained(registry, start)
    registry.close_task(start.task_id, start.session_id)

    released = registry.release_terminal_session(start.task_id, start.session_id)

    assert released == TaskSessionReleaseView(start.task_id, start.session_id)
    assert start.task_id not in registry._tasks
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("drop_plan", REQUEST),
    ]


def test_explicit_close_after_terminal_release_only_drops_plan() -> None:
    registry, service = _registry()
    start = _start(registry)
    _mark_terminal_drained(registry, start)
    registry.release_terminal_session(start.task_id, start.session_id)

    closed = registry.close_task(start.task_id, start.session_id)

    assert closed == TaskCloseView(start.task_id, start.session_id)
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("drop_plan", REQUEST),
    ]
    assert start.task_id not in registry._tasks


def test_release_retries_only_unfinished_session_step() -> None:
    graph_references: list[object] = []

    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.close_attempts = 0

        def close_session(self, session_id):
            self.close_attempts += 1
            self.cleanup.append(("close_session", session_id))
            if self.close_attempts == 1:
                _raise_private_failure(graph_references)

    service = Service()
    registry, _ = _registry(service)
    start = _start(registry)
    _mark_terminal_drained(registry, start)

    with pytest.raises(Exception, match="private failure") as raised:
        registry.release_terminal_session(start.task_id, start.session_id)
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert all(reference() is None for reference in graph_references[3:])
    task = registry._tasks[start.task_id]
    assert task.reservation.attached_session_id == start.session_id
    registry.release_terminal_session(start.task_id, start.session_id)

    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("close_session", SESSION),
    ]
    assert start.task_id in registry._tasks
    assert task.reservation.attached_session_id is None
    assert registry._reservations == {start.task_id: task.reservation}
    del raised
    gc.collect()
    assert all(reference() is None for reference in graph_references)


def test_close_drop_failure_still_proves_terminal_session_release() -> None:
    class Service(_Service):
        def drop_plan(self, request_id):
            self.cleanup.append(("drop_plan", request_id))
            raise OSError("injected drop failure")

    service = Service()
    registry, _ = _registry(service)
    start = _start(registry)
    _mark_terminal_drained(registry, start)

    with pytest.raises(OSError, match="drop failure"):
        registry.close_task(start.task_id, start.session_id)

    assert registry.release_terminal_session(
        start.task_id,
        start.session_id,
    ) == TaskSessionReleaseView(start.task_id, start.session_id)
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("drop_plan", REQUEST),
    ]


def test_release_and_close_race_runs_each_cleanup_step_once() -> None:
    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.unsubscribe_entered = Event()
            self.release_unsubscribe = Event()

        def unsubscribe(self, session_id):
            self.unsubscribe_entered.set()
            assert self.release_unsubscribe.wait(2)
            super().unsubscribe(session_id)

    service = Service()
    registry, _ = _registry(service)
    start = _start(registry)
    _mark_terminal_drained(registry, start)
    released = []
    closed = []
    errors = []

    def release() -> None:
        try:
            released.append(
                registry.release_terminal_session(start.task_id, start.session_id)
            )
        except BaseException as error:
            errors.append(error)

    def close() -> None:
        try:
            closed.append(registry.close_task(start.task_id, start.session_id))
        except BaseException as error:
            errors.append(error)

    releasing = Thread(target=release)
    closing = Thread(target=close)
    releasing.start()
    assert service.unsubscribe_entered.wait(1)
    closing.start()
    service.release_unsubscribe.set()
    releasing.join(1)
    closing.join(1)

    assert errors == []
    assert released == [TaskSessionReleaseView(start.task_id, start.session_id)]
    assert closed == [TaskCloseView(start.task_id, start.session_id)]
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("drop_plan", REQUEST),
    ]


def test_release_settles_a_stale_failed_recovery_without_deadlock() -> None:
    graph_references: list[object] = []

    class Service(_Service):
        def reobserve(self, session_id, sink, from_sequence):
            self.reobserve_calls.append((session_id, sink, from_sequence))
            self.reobserve_entered.set()
            assert self.release_reobserve.wait(2)
            _raise_private_failure(
                graph_references,
                hostile_text=True,
            )

    service = Service()
    service.release_reobserve.clear()
    registry, _ = _registry(service)
    start = _start(registry)
    _mark_terminal_drained(registry, start)
    drain_errors = []
    release_results = []
    release_errors = []

    def recover() -> None:
        try:
            registry.drain(
                start.task_id,
                start.session_id,
                "6" * 32,
                replay_from=1,
            )
        except BaseException as error:
            drain_errors.append(error)

    def release() -> None:
        try:
            release_results.append(
                registry.release_terminal_session(start.task_id, start.session_id)
            )
        except BaseException as error:
            release_errors.append(error)

    recovering = Thread(target=recover)
    releasing = Thread(target=release)
    recovering.start()
    assert service.reobserve_entered.wait(1)
    task = registry._tasks[start.task_id]
    assert task.terminal_record is None
    assert task.terminal_delivered
    releasing.start()
    service.release_reobserve.set()
    recovering.join(1)
    releasing.join(1)

    assert not recovering.is_alive()
    assert not releasing.is_alive()
    assert len(drain_errors) == 1
    assert type(drain_errors[0]) is RuntimeError
    assert str(drain_errors[0]) == "task observation recovery failed"
    assert drain_errors[0].__cause__ is None
    assert drain_errors[0].__context__ is None
    assert release_errors == []
    assert release_results == [
        TaskSessionReleaseView(start.task_id, start.session_id)
    ]
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
    ]
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)


def test_release_settles_stale_successful_recovery_with_one_unsubscribe() -> None:
    class Service(_Service):
        def reobserve(self, session_id, sink, from_sequence):
            self.reobserve_calls.append((session_id, sink, from_sequence))
            self.reobserve_entered.set()
            assert self.release_reobserve.wait(2)
            return _record(terminal=False)

    service = Service()
    service.release_reobserve.clear()
    registry, _ = _registry(service)
    start = _start(registry)
    _mark_terminal_drained(registry, start)
    drain_errors: list[BaseException] = []
    release_results = []

    def recover() -> None:
        try:
            registry.drain(
                start.task_id,
                start.session_id,
                "6" * 32,
                replay_from=1,
            )
        except BaseException as error:
            drain_errors.append(error)

    def release() -> None:
        release_results.append(
            registry.release_terminal_session(start.task_id, start.session_id)
        )

    recovering = Thread(target=recover)
    releasing = Thread(target=release)
    recovering.start()
    assert service.reobserve_entered.wait(1)
    releasing.start()
    service.release_reobserve.set()
    recovering.join(1)
    releasing.join(1)

    assert not recovering.is_alive()
    assert not releasing.is_alive()
    assert len(drain_errors) == 1
    assert type(drain_errors[0]) is TaskUnavailableError
    assert str(drain_errors[0]) == (
        "task became unavailable during observation recovery"
    )
    assert drain_errors[0].__cause__ is None
    assert drain_errors[0].__context__ is None
    assert release_results == [
        TaskSessionReleaseView(start.task_id, start.session_id)
    ]
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
    ]


def test_release_retries_unsubscribe_after_stale_successful_recovery_failure(
) -> None:
    graph_references: list[object] = []

    class Service(_Service):
        unsubscribe_attempts = 0

        def reobserve(self, session_id, sink, from_sequence):
            self.reobserve_calls.append((session_id, sink, from_sequence))
            self.reobserve_entered.set()
            assert self.release_reobserve.wait(2)
            return _record(terminal=False)

        def unsubscribe(self, session_id):
            self.unsubscribe_attempts += 1
            self.cleanup.append(("unsubscribe", session_id))
            if self.unsubscribe_attempts == 1:
                _raise_private_failure(
                    graph_references,
                    hostile_text=True,
                )

    service = Service()
    service.release_reobserve.clear()
    registry, _ = _registry(service)
    start = _start(registry)
    _mark_terminal_drained(registry, start)
    drain_errors: list[BaseException] = []
    release_errors: list[BaseException] = []
    release_results: list[TaskSessionReleaseView] = []

    def recover() -> None:
        try:
            registry.drain(
                start.task_id,
                start.session_id,
                "6" * 32,
                replay_from=1,
            )
        except BaseException as error:
            drain_errors.append(error)

    def release() -> None:
        try:
            release_results.append(
                registry.release_terminal_session(
                    start.task_id,
                    start.session_id,
                )
            )
        except BaseException as error:
            release_errors.append(error)

    recovering = Thread(target=recover)
    releasing = Thread(target=release)
    recovering.start()
    assert service.reobserve_entered.wait(1)
    releasing.start()
    service.release_reobserve.set()
    recovering.join(1)
    releasing.join(1)

    assert not recovering.is_alive()
    assert not releasing.is_alive()
    assert len(drain_errors) == 1
    assert type(drain_errors[0]) is RuntimeError
    assert str(drain_errors[0]) == "task observation recovery failed"
    assert drain_errors[0].__cause__ is None
    assert drain_errors[0].__context__ is None
    assert release_errors == []
    assert release_results == [
        TaskSessionReleaseView(start.task_id, start.session_id)
    ]
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
    ]
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)


def test_close_and_delayed_release_race_converges_through_close_receipt() -> None:
    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.drop_entered = Event()
            self.release_drop = Event()

        def drop_plan(self, request_id):
            self.drop_entered.set()
            assert self.release_drop.wait(2)
            super().drop_plan(request_id)

    service = Service()
    registry, _ = _registry(service)
    start = _start(registry)
    _mark_terminal_drained(registry, start)
    closed = []
    released = []

    closing = Thread(
        target=lambda: closed.append(
            registry.close_task(start.task_id, start.session_id)
        )
    )
    releasing = Thread(
        target=lambda: released.append(
            registry.release_terminal_session(start.task_id, start.session_id)
        )
    )
    closing.start()
    assert service.drop_entered.wait(1)
    releasing.start()
    service.release_drop.set()
    closing.join(1)
    releasing.join(1)

    assert closed == [TaskCloseView(start.task_id, start.session_id)]
    assert released == [TaskSessionReleaseView(start.task_id, start.session_id)]
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("drop_plan", REQUEST),
    ]


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
            self.return_mismatch = True

        def start_plan(self, source, target, **kwargs):
            del source, target
            _attach_task_session(kwargs, SESSION)
            kwargs["observation_sink"](_event(1))
            return PlanSession(
                REQUEST,
                "8" * 32 if self.return_mismatch else SESSION,
            )

        def close_session(self, session_id):
            self.close_attempts += 1
            self.cleanup.append(("close_session", session_id))
            if self.close_attempts == 1:
                raise OSError("injected cleanup failure")

    service = Service()
    registry, _ = _registry(service, task_capacity=1)

    with pytest.raises(ObservationConflictError):
        _start(registry)

    assert len(registry._tasks) == 1
    task = next(iter(registry._tasks.values()))
    assert task.cleanup_pending
    assert task.reservation.attached_session_id == SESSION
    assert registry._reservations == {task.task_id: task.reservation}
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
    ]

    with pytest.raises(TaskUnavailableError, match="capacity"):
        registry.start_plan(
            "other-source",
            "other-target",
            deletion_policy=None,
            command_id="5" * 32,
        )

    with pytest.raises(ObservationConflictError):
        registry.replay_start("4" * 32, None)  # type: ignore[arg-type]

    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("close_session", SESSION),
    ]
    assert registry._tasks == {}
    assert registry._commands == {}
    assert registry._reservations == {}
    service.return_mismatch = False
    admitted = registry.start_plan(
        "other-source",
        "other-target",
        deletion_policy=None,
        command_id="5" * 32,
    )
    assert admitted.session_id == SESSION


def test_coherent_return_grants_plan_cleanup_after_task_closes_during_start(
) -> None:
    registry = None

    class Service(_Service):
        def start_plan(self, source, target, **kwargs):
            del source, target
            _attach_task_session(kwargs, SESSION)
            assert registry is not None
            registry.begin_close()
            return PlanSession(REQUEST, SESSION)

    service = Service()
    registry, _ = _registry(service)

    with pytest.raises(TaskUnavailableError):
        _start(registry)

    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("drop_plan", REQUEST),
    ]
    assert registry._tasks == {}
    assert registry._commands == {}
    assert registry._reservations == {}


def test_compensation_interrupt_propagates_without_stranding_the_registry() -> None:
    class Service(_Service):
        def start_plan(self, source, target, **kwargs):
            del source, target
            _attach_task_session(kwargs, SESSION)
            kwargs["observation_sink"](_event(1))
            return PlanSession(REQUEST, "8" * 32)

        def close_session(self, session_id):
            raise KeyboardInterrupt(f"stop cleanup for {session_id}")

    registry, _ = _registry(Service())

    with pytest.raises(
        KeyboardInterrupt,
        match="task start was interrupted",
    ) as raised:
        _start(registry)

    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert len(registry._tasks) == 1
    task = next(iter(registry._tasks.values()))
    assert task.cleanup_pending


def test_cleanup_pending_start_retires_private_interruption_graph_before_replay(
) -> None:
    graph_references: list[object] = []

    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.close_attempts = 0

        def start_plan(self, source, target, **kwargs):
            del source, target
            _attach_task_session(kwargs, SESSION)
            kwargs["observation_sink"](_event(1))
            return PlanSession(REQUEST, "8" * 32)

        def close_session(self, session_id):
            self.close_attempts += 1
            self.cleanup.append(("close_session", session_id))
            if self.close_attempts == 1:
                _raise_private_failure(
                    graph_references,
                    exception_base=BaseException,
                )

    service = Service()
    registry, _ = _registry(service)

    with pytest.raises(KeyboardInterrupt) as initial:
        _start(registry)

    assert str(initial.value) == "task start was interrupted"
    assert initial.value.__cause__ is None
    assert initial.value.__context__ is None
    entry = registry._commands["4" * 32]
    assert type(entry.failure_code) is str
    assert entry.task.cleanup_pending
    del initial
    assert all(reference() is None for reference in graph_references[2:])
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)

    with pytest.raises(KeyboardInterrupt) as replayed:
        registry.replay_start("4" * 32, None)  # type: ignore[arg-type]

    assert str(replayed.value) == "task start was interrupted"
    assert replayed.value.__cause__ is None
    assert replayed.value.__context__ is None
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("close_session", SESSION),
    ]
    assert registry._commands == {}
    assert registry._tasks == {}


def test_replay_compensation_interruption_is_closed_and_remains_retryable(
) -> None:
    ordinary_graph_references: list[object] = []
    interruption_graph_references: list[object] = []

    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.close_attempts = 0

        def start_plan(self, source, target, **kwargs):
            del source, target
            _attach_task_session(kwargs, SESSION)
            kwargs["observation_sink"](_event(1))
            return PlanSession(REQUEST, "8" * 32)

        def close_session(self, session_id):
            self.close_attempts += 1
            self.cleanup.append(("close_session", session_id))
            if self.close_attempts == 1:
                _raise_private_failure(ordinary_graph_references)
            if self.close_attempts == 2:
                _raise_private_failure(
                    interruption_graph_references,
                    exception_base=BaseException,
                )

    service = Service()
    registry, _ = _registry(service)
    with pytest.raises(ObservationConflictError):
        _start(registry)
    assert all(
        reference() is None for reference in ordinary_graph_references[2:]
    )

    with pytest.raises(KeyboardInterrupt) as interrupted:
        registry.replay_start("4" * 32, None)  # type: ignore[arg-type]

    assert str(interrupted.value) == "task start was interrupted"
    assert interrupted.value.__cause__ is None
    assert interrupted.value.__context__ is None
    entry = registry._commands["4" * 32]
    assert entry.task.cleanup_pending
    del interrupted
    assert all(
        reference() is None
        for reference in interruption_graph_references[2:]
    )
    gc.collect()
    assert ordinary_graph_references
    assert interruption_graph_references
    assert all(reference() is None for reference in ordinary_graph_references)
    assert all(
        reference() is None for reference in interruption_graph_references
    )

    with pytest.raises(ObservationConflictError) as replayed:
        registry.replay_start("4" * 32, None)  # type: ignore[arg-type]

    assert str(replayed.value) == "task start observation conflicted"
    assert replayed.value.__cause__ is None
    assert replayed.value.__context__ is None
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("close_session", SESSION),
        ("close_session", SESSION),
    ]
    assert registry._commands == {}
    assert registry._tasks == {}


def test_concurrent_replays_single_flight_failed_admission_compensation() -> None:
    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.close_attempts = 0
            self.retry_entered = Event()
            self.release_retry = Event()

        def start_plan(self, source, target, **kwargs):
            del source, target
            _attach_task_session(kwargs, SESSION)
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
    assert errors[0] is not errors[1]
    assert all(
        str(error) == "task start observation conflicted" for error in errors
    )
    assert all(error.__cause__ is None for error in errors)
    assert all(error.__context__ is None for error in errors)
    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("close_session", SESSION),
    ]
    assert registry._tasks == {}
    assert registry._commands == {}


def test_br_g_33_close_task_retries_only_unfinished_cleanup_steps() -> None:
    graph_references: list[object] = []

    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.drop_attempts = 0

        def drop_plan(self, request_id):
            self.drop_attempts += 1
            self.cleanup.append(("drop_plan", request_id))
            if self.drop_attempts == 1:
                _raise_private_failure(graph_references)

    service = Service()
    registry, _ = _registry(service)
    start = _start(registry)

    _mark_terminal_drained(registry, start)
    with pytest.raises(Exception, match="private failure") as raised:
        registry.close_task(start.task_id, start.session_id)
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert all(reference() is None for reference in graph_references[3:])
    assert start.task_id in registry._tasks

    registry.close_task(start.task_id, start.session_id)

    assert service.cleanup == [
        ("unsubscribe", SESSION),
        ("close_session", SESSION),
        ("drop_plan", REQUEST),
        ("drop_plan", REQUEST),
    ]
    assert start.task_id not in registry._tasks
    del raised
    gc.collect()
    assert all(reference() is None for reference in graph_references)


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
            _attach_task_session(kwargs, command_id)
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


def test_close_refuses_session_attachment_before_lower_publication() -> None:
    class Service(_Service):
        def __init__(self) -> None:
            super().__init__()
            self.attach_entered = Event()
            self.release_attach = Event()
            self.published: list[str] = []

        def start_plan(self, source, target, **kwargs):
            del source, target
            self.attach_entered.set()
            assert self.release_attach.wait(2)
            _attach_task_session(kwargs, SESSION)
            self.published.append(SESSION)
            return PlanSession(REQUEST, SESSION)

    service = Service()
    registry, _ = _registry(service, task_capacity=1)
    failures: list[BaseException] = []

    def start() -> None:
        try:
            _start(registry)
        except BaseException as error:
            failures.append(error)

    worker = Thread(target=start)
    worker.start()
    assert service.attach_entered.wait(1)
    registry.begin_close()
    service.release_attach.set()
    worker.join(1)

    assert len(failures) == 1
    assert type(failures[0]) is TaskUnavailableError
    assert service.published == []
    assert registry._tasks == {}
    assert registry._commands == {}
    assert registry._reservations == {}


def test_repeated_task_close_bounds_active_state_and_close_receipts() -> None:
    class Service(_Service):
        def start_plan(self, source, target, **kwargs):
            del source, target
            command_id = kwargs["command_id"]
            _attach_task_session(kwargs, command_id)
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


def _malformed_task_updates():
    event = _event(2)
    record = _record()
    return [
        replace(event, schema_version=4),
        replace(event, body={}),
        replace(event, sequence=True),
        replace(event, at="2026-01-01T00:00:00Z"),
        replace(event, body={"state": "invented"}),
        replace(record, result=None),
        replace(record, state="pending", ended_at=None, result=None),
        replace(record, ended_at=None),
        replace(record, kind="sync-execute"),
        replace(record, supports_pause=True),
        replace(record, result=object()),
        replace(record, state="failed"),
        replace(record, result=replace(record.result, bytes_done=0)),
        replace(record, result=replace(record.result, recording="degraded")),
    ]


@pytest.mark.parametrize("update", _malformed_task_updates())
def test_task_offer_validates_before_queue_or_custody_mutation(update) -> None:
    registry, service = _registry()
    start = _start(registry)
    task = registry._tasks[start.task_id]
    service.sink(_event(2, "Progress"))
    before = (
        tuple(task.queue), task.progress_available_at, task.terminal_record,
        task.terminal_pending, task.terminal_delivered, task.cleanup,
    )

    with pytest.raises((TypeError, ValueError)):
        service.sink(update)

    assert (
        tuple(task.queue), task.progress_available_at, task.terminal_record,
        task.terminal_pending, task.terminal_delivered, task.cleanup,
    ) == before
    with pytest.raises(TaskUnavailableError):
        registry.release_terminal_session(start.task_id, SESSION)
    assert service.cleanup == []


@pytest.mark.parametrize("pending_record", [False, True])
def test_task_drain_validates_whole_candidate_before_consuming(pending_record) -> None:
    registry, service = _registry()
    start = _start(registry)
    task = registry._tasks[start.task_id]
    mutable = _event(2)
    service.sink(mutable)
    service.sink(_event(3, "Progress"))
    terminal = _record()
    if pending_record:
        task.terminal_record = terminal
        task.terminal_pending = True
    else:
        service.sink(terminal)
    # This mutation bypasses offer admission, as a retained collaborator can.
    mutable.body["state"] = "invented"
    before = (
        tuple(task.queue), task.progress_available_at, task.terminal_record,
        task.terminal_pending, task.terminal_delivered,
    )

    with pytest.raises((TypeError, ValueError)):
        registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)

    assert (
        tuple(task.queue), task.progress_available_at, task.terminal_record,
        task.terminal_pending, task.terminal_delivered,
    ) == before
    assert task.active_drain is None
    with pytest.raises(TaskUnavailableError):
        registry.release_terminal_session(start.task_id, SESSION)
    assert service.cleanup == []

    mutable.body["state"] = "running"
    drained = registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)
    assert [update.event.sequence for update in drained.updates[:-1]] == [1, 2, 3]
    assert drained.updates[-1].record is terminal
    registry.release_terminal_session(start.task_id, SESSION)
    assert service.cleanup == [("unsubscribe", SESSION), ("close_session", SESSION)]


@pytest.mark.parametrize("record", [
    replace(_record(), result=object()),
    replace(_record(), state="failed"),
    replace(_record(), ended_at=None),
    replace(_record(), result=replace(_record().result, bytes_done=0)),
])
def test_task_recovery_rejects_malformed_current_record_without_receipt(record) -> None:
    registry, service = _registry()
    start = _start(registry)
    service.reobserve_result = record
    with pytest.raises(RuntimeError) as raised:
        registry.drain(start.task_id, SESSION, DRAIN, replay_from=1)
    assert str(raised.value) == "task observation recovery failed"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    task = registry._tasks[start.task_id]
    assert not task.queue
    assert task.terminal_record is None
    assert not task.terminal_pending and not task.terminal_delivered
    assert task.active_drain is None and not task.transition
    with pytest.raises(TaskUnavailableError):
        registry.release_terminal_session(start.task_id, SESSION)
    assert service.cleanup == []


def test_task_recovery_drops_malformed_current_graph_before_reconciliation() -> None:
    graph_references: list[object] = []

    class Service(_Service):
        def reobserve(self, session_id, sink, from_sequence):
            del session_id, sink, from_sequence
            return _private_malformed_recovery_record(graph_references)

    registry, service = _registry(Service())
    start = _start(registry)

    with pytest.raises(RuntimeError) as raised:
        registry.drain(start.task_id, SESSION, DRAIN, replay_from=1)

    assert str(raised.value) == "task observation recovery failed"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    task = registry._tasks[start.task_id]
    assert not task.queue
    assert task.terminal_record is None
    assert not task.terminal_pending and not task.terminal_delivered
    assert task.active_drain is None and not task.transition
    assert service.cleanup == []
    gc.collect()
    assert graph_references
    assert all(reference() is None for reference in graph_references)


@pytest.mark.parametrize("record", [
    _record(terminal=False),
    replace(_record(terminal=False), state="running"),
    replace(_record(), result=None),
])
def test_result_free_reobservation_is_not_a_terminal_delivery_receipt(record) -> None:
    registry, service = _registry()
    start = _start(registry)
    service.reobserve_result = record
    assert not registry.drain(
        start.task_id, SESSION, DRAIN, replay_from=1,
    ).updates
    assert not registry._tasks[start.task_id].terminal_delivered
    with pytest.raises(TaskUnavailableError):
        registry.release_terminal_session(start.task_id, SESSION)
    assert service.cleanup == []


def test_invalid_pending_terminal_preserves_queued_events_and_pending_flag() -> None:
    registry, service = _registry()
    start = _start(registry)
    task = registry._tasks[start.task_id]
    task.terminal_record = replace(_record(), result=None)
    task.terminal_pending = True
    before = tuple(task.queue)
    with pytest.raises((TypeError, ValueError)):
        registry.drain(start.task_id, SESSION, DRAIN, replay_from=None)
    assert tuple(task.queue) == before
    assert task.terminal_pending and not task.terminal_delivered
    assert task.active_drain is None
    with pytest.raises(TaskUnavailableError):
        registry.release_terminal_session(start.task_id, SESSION)
    assert service.cleanup == []


def test_terminal_event_alone_does_not_earn_release_receipt() -> None:
    registry, service = _registry()
    start = _start(registry)
    service.sink(_event(2, "Terminal"))
    assert len(registry.drain(
        start.task_id, SESSION, DRAIN, replay_from=None,
    ).updates) == 2
    with pytest.raises(TaskUnavailableError):
        registry.release_terminal_session(start.task_id, SESSION)
    assert service.cleanup == []
