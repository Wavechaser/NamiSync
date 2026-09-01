"""Baseline lifecycle stop detectors and observation barriers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import gc
import io
from threading import Event, Lock, Thread
from time import monotonic
from weakref import ref

import pytest

from namisync.core.evidence import RecordingStatus
from namisync.core.events import CORE_EVENT_SCHEMA_VERSION, Envelope, PhaseChanged
from namisync.core.session import OperationResult, ResourceId, SessionState
from namisync.dispatcher import (
    Dispatcher,
    InMemorySessionStore,
    PreparedSession,
    SessionCleanupPending,
    WorkflowRegistration,
)
from namisync.interfaces import service as service_module
from namisync.interfaces.cli import EXIT_CANCELED, _exit_for_record, _wait_for_result
from namisync.interfaces.service import NamiSyncService
from namisync.interfaces.web.drain import TaskRegistry
from namisync.workflows import PLAN_KIND
from namisync.workflows.views import (
    SessionEventView,
    SessionRecordView,
    session_event_view,
)


_SESSION = "2" * 32


@dataclass
class _Invocation:
    run_action: object
    checkpoint: object

    def run(self, context):
        return self.run_action(context)

    def snapshot(self) -> object:
        return self.checkpoint


def _registration(
    run_for_checkpoint,
    *,
    supports_pause: bool = False,
    resources_for_checkpoint=lambda _checkpoint: frozenset(),
) -> WorkflowRegistration:
    def prepare(request: object) -> PreparedSession:
        checkpoint = getattr(request, "request_id", request)
        return PreparedSession(
            checkpoint,
            frozenset(resources_for_checkpoint(checkpoint)),
        )

    return WorkflowRegistration(
        prepare=prepare,
        open=lambda checkpoint: _Invocation(
            run_for_checkpoint(checkpoint),
            checkpoint,
        ),
        supports_pause=supports_pause,
    )


def _wait_for_state(
    dispatcher: Dispatcher,
    session_id: str,
    state: SessionState,
    *,
    timeout: float = 2.0,
):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        record = dispatcher.get(session_id)
        if record.state is state and (
            state
            not in {
                SessionState.COMPLETED,
                SessionState.FAILED,
                SessionState.CANCELED,
                SessionState.REFUSED,
            }
            or record.result is not None
        ):
            return record
        Event().wait(0.002)
    raise AssertionError(
        f"session did not reach {state.value}: {dispatcher.get(session_id)}"
    )


def _service_for_dispatcher(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    dispatcher: Dispatcher,
    *,
    require_session_attachment: bool = False,
) -> NamiSyncService:
    monkeypatch.setattr(service_module, "_dispatcher", lambda _runtime: dispatcher)
    return NamiSyncService(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
        require_session_attachment=require_session_attachment,
    )


class _BlockingOutput(io.StringIO):
    def __init__(self, entered: Event, release: Event) -> None:
        super().__init__()
        self._entered = entered
        self._release = release
        self._blocked = False

    def write(self, value: str) -> int:
        written = super().write(value)
        if "Phase: running" in value and not self._blocked:
            self._blocked = True
            self._entered.set()
            assert self._release.wait(2)
        return written


def test_disc_b1_blocked_cli_callback_preserves_cancel_responsiveness(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callback_entered = Event()
    release_callback = Event()
    cancel_issued = Event()
    workflow_entered = Event()

    def run(_checkpoint):
        def action(context):
            workflow_entered.set()
            context.emit(PhaseChanged("running"))
            assert cancel_issued.wait(2)
            context.checkpoint()
            raise AssertionError("cancellation checkpoint unexpectedly returned")

        return action

    dispatcher = Dispatcher({PLAN_KIND: _registration(run)})
    service = _service_for_dispatcher(tmp_path, monkeypatch, dispatcher)
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    session = service.start_plan(str(source), str(target))
    assert workflow_entered.wait(1)
    deliveries: list[str] = []
    controls = []

    class InterruptingService:
        interrupted = False

        def observe(self, session_id, sink):
            def receive(update):
                if type(update) is SessionEventView:
                    deliveries.append(f"event:{update.body_type}")
                else:
                    deliveries.append("record")
                sink(update)

            return service.observe(session_id, receive)

        def wait(self, session_id):
            if not self.interrupted:
                self.interrupted = True
                assert callback_entered.wait(1)
                raise KeyboardInterrupt
            return service.wait(session_id)

        def cancel(self, session_id):
            result = service.cancel(session_id)
            controls.append(result)
            cancel_issued.set()
            return result

        def unsubscribe(self, session_id):
            service.unsubscribe(session_id)

    stdout = _BlockingOutput(callback_entered, release_callback)
    stderr = io.StringIO()
    records: list[SessionRecordView] = []
    failures: list[BaseException] = []

    def wait_for_result() -> None:
        try:
            records.append(
                _wait_for_result(
                    InterruptingService(),
                    session.session_id,
                    stdout,
                    stderr,
                )
            )
        except BaseException as error:
            failures.append(error)

    worker = Thread(target=wait_for_result)
    worker.start()
    try:
        assert callback_entered.wait(1)
        assert cancel_issued.wait(1)
        terminal = _wait_for_state(
            dispatcher,
            session.session_id,
            SessionState.CANCELED,
        )
        assert worker.is_alive()
        assert terminal.result is not None and terminal.result.canceled
        assert len(controls) == 1 and controls[0].accepted
    finally:
        cancel_issued.set()
        release_callback.set()
        worker.join(2)

    assert not worker.is_alive()
    assert failures == []
    assert len(records) == 1
    assert _exit_for_record(records[0]) == EXIT_CANCELED
    assert deliveries.count("event:Terminal") == 1
    assert deliveries.count("record") == 1
    assert deliveries.index("event:PhaseChanged") < deliveries.index("event:Terminal")
    assert stdout.getvalue() == "Phase: running\n"
    assert stderr.getvalue() == (
        "Cancellation requested; waiting for cleanup and custody release.\n"
    )
    service.close_session(session.session_id)
    assert service.close(timeout=2).complete


def _task_event(session_id: str, sequence: int) -> SessionEventView:
    return SessionEventView(
        session_id,
        sequence,
        "2026-01-01T00:00:00+00:00",
        CORE_EVENT_SCHEMA_VERSION,
        "PhaseChanged",
        {"phase": f"blocked-{sequence}"},
    )


def test_disc_b2_adapter_shutdown_wakes_offer_before_baseline_unsubscribe(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_entered = Event()
    finish_workflow = Event()

    def run(_checkpoint):
        def action(_context):
            workflow_entered.set()
            assert finish_workflow.wait(2)
            return OperationResult(SessionState.COMPLETED)

        return action

    dispatcher = Dispatcher({PLAN_KIND: _registration(run)})
    service = _service_for_dispatcher(
        tmp_path,
        monkeypatch,
        dispatcher,
        require_session_attachment=True,
    )
    shutdown_order: list[str] = []
    unsubscribe_calls: list[str] = []

    class RecordingService:
        def unsubscribe(self, session_id):
            unsubscribe_calls.append(session_id)
            service.unsubscribe(session_id)
            shutdown_order.append("adapter.unsubscribe.complete")

        def __getattr__(self, name):
            return getattr(service, name)

    registry = TaskRegistry(
        RecordingService(),
        token=lambda: "a" * 32,
        drain_wait=0.05,
    )
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    start = registry.start_plan(
        str(source),
        str(target),
        deletion_policy=None,
        command_id="b" * 32,
    )
    assert workflow_entered.wait(1)
    task = registry._tasks[start.task_id]
    deadline = monotonic() + 1
    while monotonic() < deadline:
        with task.condition:
            if len(task.queue) >= 2:
                break
            task.condition.wait(0.01)
    registry.drain(
        start.task_id,
        start.session_id,
        "c" * 32,
        replay_from=None,
    )
    sink = task.sink(task.generation)
    for sequence in range(100, 164):
        sink(_task_event(start.session_id, sequence))
    offer_entered = Event()
    offer_returned = Event()

    def offer() -> None:
        offer_entered.set()
        sink(_task_event(start.session_id, 164))
        offer_returned.set()

    producer = Thread(target=offer)
    producer.start()
    try:
        assert offer_entered.wait(1)
        assert not offer_returned.wait(0.05)
        generation = task.generation
        registry.begin_close()
        assert offer_returned.wait(1)
        shutdown_order.append("adapter.offer.withdrawn")
        producer.join(1)
        with task.condition:
            assert task.closing
            assert task.generation == generation + 1
        assert unsubscribe_calls == []

        registry.unsubscribe_all()
        assert unsubscribe_calls == [start.session_id]
        assert service._observer._observations == {}
        registry.unsubscribe_all()
        assert unsubscribe_calls == [start.session_id]
    finally:
        registry.begin_close()
        finish_workflow.set()
        producer.join(1)

    _wait_for_state(
        dispatcher,
        start.session_id,
        SessionState.COMPLETED,
    )
    service.close_session(start.session_id)
    shutdown_order.append("service.session_close.complete")
    assert service.close(timeout=2).complete
    shutdown_order.append("service.close.complete")
    assert shutdown_order == [
        "adapter.offer.withdrawn",
        "adapter.unsubscribe.complete",
        "service.session_close.complete",
        "service.close.complete",
    ]


class _TraceAudit:
    def __init__(self) -> None:
        self._lock = Lock()
        self._events: list[Envelope] = []

    def on_event(self, envelope: Envelope) -> RecordingStatus:
        with self._lock:
            self._events.append(envelope)
        return RecordingStatus.OK

    def flush(self) -> None:
        pass

    def finalize(self, _result: OperationResult) -> RecordingStatus:
        return RecordingStatus.OK

    def close(self) -> None:
        pass

    def snapshot(self) -> tuple[Envelope, ...]:
        with self._lock:
            return tuple(self._events)


def test_ls_1_delivery_has_no_silent_loss_or_duplicate(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callback_entered = Event()
    release_callback = Event()
    flood_done = Event()
    audit = _TraceAudit()

    def run(_checkpoint):
        def action(context):
            context.emit(PhaseChanged("phase-0"))
            assert callback_entered.wait(2)
            for index in range(1, 200):
                context.emit(PhaseChanged(f"phase-{index}"))
            flood_done.set()
            return OperationResult(SessionState.COMPLETED)

        return action

    dispatcher = Dispatcher(
        {PLAN_KIND: _registration(run)},
        audit_observer_factory=lambda _record: audit,
        audit_capacity=512,
    )
    service = _service_for_dispatcher(tmp_path, monkeypatch, dispatcher)
    deliveries: list[SessionEventView | SessionRecordView] = []

    def receive(update: SessionEventView | SessionRecordView) -> None:
        deliveries.append(update)
        if (
            type(update) is SessionEventView
            and update.body_type == "PhaseChanged"
            and update.body == {"phase": "phase-0"}
        ):
            callback_entered.set()
            assert release_callback.wait(2)

    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    session = service.start_plan(
        str(source),
        str(target),
        observation_sink=receive,
    )
    try:
        assert callback_entered.wait(1)
        assert flood_done.wait(2)
    finally:
        release_callback.set()

    terminal = service.wait(session.session_id)
    assert terminal.result is not None
    hub = dispatcher._hubs[session.session_id]
    producer_by_sequence = {
        envelope.seq: session_event_view(envelope)
        for envelope in (*audit.snapshot(), *tuple(hub._replay))
    }
    events = [
        update for update in deliveries if type(update) is SessionEventView
    ]
    records = [
        update for update in deliveries if type(update) is SessionRecordView
    ]
    sequences = [event.sequence for event in events]
    gaps = [event for event in events if event.body_type == "Gap"]
    non_gap = [event for event in events if event.body_type != "Gap"]

    assert len(sequences) == len(set(sequences))
    assert sequences == sorted(sequences)
    assert gaps
    assert len(records) == 1 and records[0] == terminal
    assert deliveries[-1] == records[0]
    assert [event.body_type for event in events].count("Terminal") <= 1
    if any(event.body_type == "Terminal" for event in events):
        assert events[-1].body_type == "Terminal"
    for delivered in non_gap:
        produced = producer_by_sequence[delivered.sequence]
        assert (delivered.body_type, delivered.body) == (
            produced.body_type,
            produced.body,
        )

    delivered_sequences = {event.sequence for event in non_gap}
    missing = sorted(set(producer_by_sequence) - delivered_sequences)
    assert missing
    coverage: list[tuple[int, int]] = []
    maximum = max(producer_by_sequence)
    for index, event in enumerate(events):
        if event.body_type != "Gap":
            continue
        following = next(
            (
                candidate.sequence
                for candidate in events[index + 1 :]
                if candidate.body_type != "Gap"
            ),
            maximum + 1,
        )
        coverage.append((event.body["first_missed_seq"], following - 1))
    covered = {
        sequence
        for first, last in coverage
        for sequence in range(first, last + 1)
    }
    assert covered == set(missing)

    service.unsubscribe(session.session_id)
    service.close_session(session.session_id)
    assert service.close(timeout=2).complete


def test_ls_2_session_control_reaches_only_corresponding_dispatcher_record() -> None:
    entered: dict[str, Event] = {}

    def run(checkpoint):
        def action(context):
            entered.setdefault(str(checkpoint), Event()).set()
            while True:
                context.checkpoint()
                Event().wait(0.002)

        return action

    dispatcher = Dispatcher(
        {
            "control": _registration(
                run,
                supports_pause=True,
                resources_for_checkpoint=lambda checkpoint: {
                    ResourceId("test", str(checkpoint))
                },
            )
        }
    )
    service = object.__new__(NamiSyncService)
    service._dispatcher = dispatcher
    first = str(dispatcher.submit("control", "first"))
    second = str(dispatcher.submit("control", "second"))
    assert entered.setdefault("first", Event()).wait(3)
    assert entered.setdefault("second", Event()).wait(3)
    _wait_for_state(dispatcher, first, SessionState.RUNNING)
    _wait_for_state(dispatcher, second, SessionState.RUNNING)

    assert service.pause(first).accepted
    _wait_for_state(dispatcher, first, SessionState.PAUSED)
    assert dispatcher.get(second).state is SessionState.RUNNING
    assert service.resume(first).accepted
    _wait_for_state(dispatcher, first, SessionState.RUNNING)
    assert dispatcher.get(second).state is SessionState.RUNNING
    assert service.cancel(first).accepted
    _wait_for_state(dispatcher, first, SessionState.CANCELED)
    assert dispatcher.get(second).state is SessionState.RUNNING

    unknown = "f" * 32
    for operation in (service.pause, service.resume, service.cancel):
        result = operation(unknown)
        assert not result.accepted and result.code == "not-found"
        assert dispatcher.get(second).state is SessionState.RUNNING

    dispatcher.close(first)
    for operation in (service.pause, service.resume, service.cancel):
        result = operation(first)
        assert not result.accepted and result.code == "not-found"
        assert dispatcher.get(second).state is SessionState.RUNNING

    assert service.cancel(second).accepted
    _wait_for_state(dispatcher, second, SessionState.CANCELED)
    dispatcher.close(second)
    assert dispatcher.shutdown().complete


@dataclass
class _LifecycleCounts:
    attachment_attempts: int = 0
    attachment_successes: int = 0
    stream_close_attempts: int = 0
    stream_close_successes: int = 0
    observer_adopt_attempts: int = 0
    observer_adopt_successes: int = 0
    publication_attempts: int = 0
    publication_successes: int = 0
    application_rollback_attempts: int = 0
    application_rollback_successes: int = 0
    observer_rollback_attempts: int = 0
    observer_rollback_successes: int = 0
    owner_rollback_attempts: int = 0
    owner_rollback_successes: int = 0


class _LifecycleStream:
    def __init__(self, counts: _LifecycleCounts, *, fail_once: bool = False) -> None:
        self._counts = counts
        self._failures = 1 if fail_once else 0
        self.closed = False

    def close(self) -> None:
        self._counts.stream_close_attempts += 1
        if self._failures:
            self._failures -= 1
            raise OSError("sinkless stream retirement failed")
        if not self.closed:
            self.closed = True
            self._counts.stream_close_successes += 1


class _CountingOwners(dict[str, tuple[str, str]]):
    def __init__(self, stage: str) -> None:
        super().__init__()
        self.stage = stage
        self.install_attempts = 0
        self.install_successes = 0
        self.retire_attempts = 0
        self.retire_successes = 0

    def __setitem__(self, key: str, value: tuple[str, str]) -> None:
        self.install_attempts += 1
        if self.stage == "F2":
            raise RuntimeError("detail owner install failed")
        super().__setitem__(key, value)
        self.install_successes += 1

    def pop(self, key, *default):
        self.retire_attempts += 1
        if self.stage == "R3" and self.retire_attempts == 1:
            raise RuntimeError("detail owner rollback failed")
        value = super().pop(key, *default)
        self.retire_successes += 1
        return value


class _LifecycleObserver:
    def __init__(
        self,
        stage: str,
        counts: _LifecycleCounts,
        *,
        retry_entered: Event | None = None,
        release_retry: Event | None = None,
    ) -> None:
        self.stage = stage
        self.counts = counts
        self.retry_entered = retry_entered
        self.release_retry = release_retry
        self.observations: dict[str, tuple[object, object]] = {}

    def _count_real_stream_close(self, stream: object) -> None:
        if isinstance(stream, _LifecycleStream):
            return
        original_close = stream.close

        def close() -> None:
            self.counts.stream_close_attempts += 1
            was_closed = stream._closed
            original_close()
            if not was_closed and stream._closed:
                self.counts.stream_close_successes += 1

        stream.close = close

    def adopt(self, session_id, sink, stream):
        self._count_real_stream_close(stream)
        self.counts.observer_adopt_attempts += 1
        if self.stage == "F4":
            stream.close()
            raise RuntimeError("observer adoption failed")
        self.observations[session_id] = (sink, stream)
        self.counts.observer_adopt_successes += 1

        def rollback() -> None:
            self.counts.observer_rollback_attempts += 1
            attempt = self.counts.observer_rollback_attempts
            if self.stage == "R1" and attempt == 1:
                raise TimeoutError("observer rollback retained the sink")
            if self.stage == "R1" and attempt == 2 and self.retry_entered:
                self.retry_entered.set()
                assert self.release_retry is not None
                assert self.release_retry.wait(3)
            retained = self.observations.pop(session_id, None)
            if retained is not None:
                retained[1].close()
                self.counts.observer_rollback_successes += 1
            if self.stage == "R2" and attempt == 1:
                raise TimeoutError("observer rollback retired before raising")

        return rollback

    def retains_observation(self, session_id, sink) -> bool:
        retained = self.observations.get(session_id)
        return retained is not None and retained[0] is sink


class _LifecycleDispatcher:
    def __init__(
        self,
        stage: str,
        counts: _LifecycleCounts,
        stream: _LifecycleStream,
    ) -> None:
        self.stage = stage
        self.counts = counts
        self.stream = stream
        self.rollback = None
        self.cleanup_pending = False

    def submit(self, _kind, _request, *, attach):
        attach_callback, rollback = attach.capture()
        self.rollback = rollback
        try:
            attached = attach_callback(_SESSION, self.stream)
            assert attached is rollback
            self.counts.publication_attempts += 1
            raise RuntimeError("dispatcher publication failed")
        except BaseException:
            self.counts.application_rollback_attempts += 1
            try:
                rollback()
            except BaseException:
                self.cleanup_pending = True
            else:
                self.counts.application_rollback_successes += 1
            try:
                self.stream.close()
            except BaseException:
                self.cleanup_pending = True
            raise

    def retry(self) -> None:
        assert self.rollback is not None
        self.counts.application_rollback_attempts += 1
        self.rollback()
        self.counts.application_rollback_successes += 1
        self.cleanup_pending = False


def _lifecycle_service(dispatcher, observer, owners) -> NamiSyncService:
    service = object.__new__(NamiSyncService)
    service._closed = False
    service._lock = Lock()
    service._session_receipt_lifecycle = Lock()
    service._runtime_detail_retirement_started = False
    service._detail_owners_by_session = owners
    service._dispatcher = dispatcher
    service._observer = observer
    return service


def _lifecycle_attachment(
    stage: str,
    counts: _LifecycleCounts,
    owners: _CountingOwners,
):
    retired = False

    def attach(_session_id: str):
        counts.attachment_attempts += 1
        if stage == "F1":
            raise RuntimeError("session attachment failed")
        counts.attachment_successes += 1

        def rollback() -> None:
            nonlocal retired
            counts.owner_rollback_attempts += 1
            if stage == "R4" and counts.owner_rollback_attempts == 1:
                raise RuntimeError("owner rollback failed")
            assert _SESSION not in owners
            if not retired:
                retired = True
                counts.owner_rollback_successes += 1

        return rollback

    return attach


def _assert_lifecycle_terminal_state(
    observer: _LifecycleObserver,
    owners: _CountingOwners,
    counts: _LifecycleCounts,
) -> None:
    assert observer.observations == {}
    assert owners == {}
    assert counts.stream_close_successes == 1
    assert counts.owner_rollback_successes == counts.attachment_successes


@dataclass
class _DispatcherCleanupCounts:
    rollback_attempts: int = 0
    rollback_successes: int = 0
    stream_attempts: int = 0
    stream_successes: int = 0
    hub_attempts: int = 0
    hub_successes: int = 0
    store_attempts: int = 0
    store_successes: int = 0


class _CleanupStore(InMemorySessionStore):
    def __init__(
        self,
        stage: str,
        counts: _DispatcherCleanupCounts,
        retry_entered: Event,
        release_retry: Event,
    ) -> None:
        super().__init__()
        self.stage = stage
        self.counts = counts
        self.retry_entered = retry_entered
        self.release_retry = release_retry
        self.failed_session_id = None

    def drop(self, session_id) -> None:
        if session_id != self.failed_session_id:
            super().drop(session_id)
            return
        self.counts.store_attempts += 1
        attempt = self.counts.store_attempts
        if self.stage == "D4" and attempt == 1:
            raise OSError("dispatcher store retirement failed")
        if self.stage == "D4" and attempt == 2:
            self.retry_entered.set()
            assert self.release_retry.wait(3)
        super().drop(session_id)
        self.counts.store_successes += 1


def _concurrent_cleanup_stimuli(
    dispatcher: Dispatcher,
    retry_entered: Event,
) -> tuple[BaseException, BaseException]:
    start_retry = Event()
    retry_errors: list[BaseException] = []

    def retry_stimulus() -> None:
        assert start_retry.wait(3)
        try:
            dispatcher.submit(PLAN_KIND, object())
        except BaseException as error:
            retry_errors.append(error)

    callers = (Thread(target=retry_stimulus), Thread(target=retry_stimulus))
    for caller in callers:
        caller.start()
    start_retry.set()
    assert retry_entered.wait(3)
    for caller in callers:
        caller.join(3)
        assert not caller.is_alive()
    assert len(retry_errors) == 2
    assert all(type(error) is SessionCleanupPending for error in retry_errors)
    assert all("another admission" in str(error) for error in retry_errors)
    return retry_errors[0], retry_errors[1]


def _dispatcher_cleanup_pairs(
    counts: _DispatcherCleanupCounts,
) -> dict[str, tuple[int, int]]:
    return {
        "D1": (counts.rollback_attempts, counts.rollback_successes),
        "D2": (counts.stream_attempts, counts.stream_successes),
        "D3": (counts.hub_attempts, counts.hub_successes),
        "D4": (counts.store_attempts, counts.store_successes),
    }


def _exercise_dispatcher_cleanup_stage(stage: str) -> None:
    counts = _DispatcherCleanupCounts()
    retry_entered = Event()
    release_retry = Event()
    store = _CleanupStore(stage, counts, retry_entered, release_retry)
    clock_calls = 0
    prepare_calls = 0

    class PublicationClock:
        def now(self):
            nonlocal clock_calls
            clock_calls += 1
            if clock_calls == 2:
                raise RuntimeError("dispatcher publication failed")
            return datetime(2026, 1, 1, tzinfo=timezone.utc)

    def prepare(request: object) -> PreparedSession:
        nonlocal prepare_calls
        prepare_calls += 1
        return PreparedSession(request)

    dispatcher = Dispatcher(
        {
            PLAN_KIND: WorkflowRegistration(
                prepare=prepare,
                open=lambda checkpoint: _Invocation(
                    lambda _context: OperationResult(SessionState.COMPLETED),
                    checkpoint,
                ),
            )
        },
        store=store,
        clock=PublicationClock(),
        audit_timeout=0.2,
    )

    def block_selected_retry(selected: str, attempt: int) -> None:
        if stage == selected and attempt == 2:
            retry_entered.set()
            assert release_retry.wait(3)

    def attach(session_id, stream):
        store.failed_session_id = session_id
        original_stream_close = stream.close

        def stream_close() -> None:
            counts.stream_attempts += 1
            attempt = counts.stream_attempts
            if stage == "D2" and attempt == 1:
                raise OSError("dispatcher subscribed stream retirement failed")
            block_selected_retry("D2", attempt)
            original_stream_close()
            counts.stream_successes += 1

        stream.close = stream_close
        hub = stream._on_close.__self__
        original_hub_close = hub.close

        def hub_close(timeout):
            counts.hub_attempts += 1
            attempt = counts.hub_attempts
            if stage == "D3" and attempt == 1:
                raise OSError("dispatcher hub retirement failed")
            block_selected_retry("D3", attempt)
            status = original_hub_close(timeout)
            counts.hub_successes += 1
            return status

        hub.close = hub_close

        def rollback() -> None:
            counts.rollback_attempts += 1
            attempt = counts.rollback_attempts
            if stage == "D1" and attempt == 1:
                raise OSError("dispatcher attachment rollback failed")
            block_selected_retry("D1", attempt)
            counts.rollback_successes += 1

        return rollback

    try:
        with pytest.raises(RuntimeError, match="dispatcher publication failed"):
            dispatcher.submit(PLAN_KIND, object(), attach=attach)

        (cleanup,) = dispatcher._admission_cleanups.values()
        assert cleanup.failure_seen
        assert (
            cleanup.rollback is not None,
            cleanup.stream is not None,
            cleanup.hub is not None,
            cleanup.store_pending,
        ) == tuple(candidate == stage for candidate in ("D1", "D2", "D3", "D4"))
        initial_pairs = _dispatcher_cleanup_pairs(counts)
        assert initial_pairs[stage] == (1, 0)
        assert all(
            pair == (1, 1)
            for candidate, pair in initial_pairs.items()
            if candidate != stage
        )

        _concurrent_cleanup_stimuli(dispatcher, retry_entered)
        assert prepare_calls == 1
        attempt = dispatcher._admission_cleanup_attempt
        assert attempt is not None and attempt.thread.is_alive()
        assert dispatcher._admission_cleanups == {cleanup.session_id: cleanup}
        assert dispatcher._admission_liability_claimed
        during_retry = _dispatcher_cleanup_pairs(counts)
        assert during_retry[stage] == (2, 0)
        assert all(
            pair == (1, 1)
            for candidate, pair in during_retry.items()
            if candidate != stage
        )

        release_retry.set()
        attempt.thread.join(3)
        assert not attempt.thread.is_alive()
        assert dispatcher._admission_cleanups == {}
        assert not dispatcher._admission_liability_claimed
        completed = _dispatcher_cleanup_pairs(counts)
        assert completed[stage] == (2, 1)
        assert all(
            pair == (1, 1)
            for candidate, pair in completed.items()
            if candidate != stage
        )

        successor = dispatcher.submit(PLAN_KIND, object())
        _wait_for_state(dispatcher, str(successor), SessionState.COMPLETED)
        dispatcher.close(successor)
        assert prepare_calls == 2
    finally:
        release_retry.set()
        assert dispatcher.shutdown(timeout=3).complete


def _exercise_real_concurrent_cleanup_retry() -> None:
    counts = _LifecycleCounts()
    owners = _CountingOwners("R1")
    retry_entered = Event()
    release_retry = Event()
    observer = _LifecycleObserver(
        "R1",
        counts,
        retry_entered=retry_entered,
        release_retry=release_retry,
    )
    clock_calls = 0
    prepare_calls = 0

    class PublicationClock:
        def now(self):
            nonlocal clock_calls
            clock_calls += 1
            if clock_calls == 2:
                counts.publication_attempts += 1
                raise RuntimeError("dispatcher publication failed")
            return datetime(2026, 1, 1, tzinfo=timezone.utc)

    def prepare(request: object) -> PreparedSession:
        nonlocal prepare_calls
        prepare_calls += 1
        return PreparedSession(request)

    dispatcher = Dispatcher(
        {
            PLAN_KIND: WorkflowRegistration(
                prepare=prepare,
                open=lambda checkpoint: _Invocation(
                    lambda _context: OperationResult(SessionState.COMPLETED),
                    checkpoint,
                ),
            )
        },
        clock=PublicationClock(),
        audit_timeout=0.2,
    )
    service = _lifecycle_service(dispatcher, observer, owners)
    attachment = _lifecycle_attachment("R1", counts, owners)
    sink = lambda _update: None
    try:
        with pytest.raises(RuntimeError, match="dispatcher publication failed"):
            service._submit_session(
                PLAN_KIND,
                object(),
                detail_owner=("inventory", "request"),
                observation_sink=sink,
                session_attachment=attachment,
            )

        (cleanup,) = dispatcher._admission_cleanups.values()
        assert cleanup.failure_seen
        assert cleanup.rollback is not None
        assert cleanup.stream is None
        assert cleanup.hub is None
        assert not cleanup.store_pending
        assert observer.retains_observation(str(cleanup.session_id), sink)
        assert owners == {}
        assert (counts.observer_rollback_attempts, counts.observer_rollback_successes) == (1, 0)
        assert (counts.owner_rollback_attempts, counts.owner_rollback_successes) == (0, 0)

        start_retry = Event()
        retry_errors: list[BaseException] = []

        def retry_stimulus() -> None:
            assert start_retry.wait(3)
            try:
                dispatcher.submit(PLAN_KIND, object())
            except BaseException as error:
                retry_errors.append(error)

        callers = (Thread(target=retry_stimulus), Thread(target=retry_stimulus))
        for caller in callers:
            caller.start()
        start_retry.set()
        assert retry_entered.wait(3)
        for caller in callers:
            caller.join(3)
            assert not caller.is_alive()
        assert len(retry_errors) == 2
        assert all(type(error) is SessionCleanupPending for error in retry_errors)
        assert prepare_calls == 1
        assert dispatcher._admission_cleanups == {cleanup.session_id: cleanup}
        assert counts.observer_rollback_attempts == 2
        attempt = dispatcher._admission_cleanup_attempt
        assert attempt is not None and attempt.thread.is_alive()
        assert dispatcher._admission_liability_claimed

        release_retry.set()
        deadline = monotonic() + 3
        while monotonic() < deadline:
            with dispatcher._condition:
                if not dispatcher._admission_cleanups:
                    break
                dispatcher._condition.wait(0.01)
        assert dispatcher._admission_cleanups == {}
        assert not dispatcher._admission_liability_claimed
        _assert_lifecycle_terminal_state(observer, owners, counts)
        assert (counts.attachment_attempts, counts.attachment_successes) == (1, 1)
        assert (owners.install_attempts, owners.install_successes) == (1, 1)
        assert (counts.observer_adopt_attempts, counts.observer_adopt_successes) == (1, 1)
        assert (counts.publication_attempts, counts.publication_successes) == (1, 0)
        assert (counts.observer_rollback_attempts, counts.observer_rollback_successes) == (2, 1)
        assert (owners.retire_attempts, owners.retire_successes) == (1, 1)
        assert (counts.owner_rollback_attempts, counts.owner_rollback_successes) == (1, 1)
        assert (counts.stream_close_attempts, counts.stream_close_successes) == (2, 1)

        successor = dispatcher.submit(PLAN_KIND, object())
        _wait_for_state(dispatcher, str(successor), SessionState.COMPLETED)
        dispatcher.close(successor)
        assert prepare_calls == 2
        assert dispatcher._admission_cleanup_attempt is None
    finally:
        release_retry.set()
        assert dispatcher.shutdown(timeout=3).complete


@pytest.mark.parametrize(
    "stage",
    (
        "F1",
        "F2",
        "F3",
        "F4",
        "F5",
        "R1",
        "R2",
        "R3",
        "R4",
        "D1",
        "D2",
        "D3",
        "D4",
    ),
)
def test_ls_4a_submit_session_rollback_converges(stage: str) -> None:
    if stage.startswith("D"):
        _exercise_dispatcher_cleanup_stage(stage)
        return
    if stage == "R1":
        _exercise_real_concurrent_cleanup_retry()
        return

    counts = _LifecycleCounts()
    owners = _CountingOwners(stage)
    stream = _LifecycleStream(counts, fail_once=stage == "F3")
    observer = _LifecycleObserver(stage, counts)
    dispatcher = _LifecycleDispatcher(stage, counts, stream)
    service = _lifecycle_service(dispatcher, observer, owners)
    sink = None if stage == "F3" else lambda _update: None

    with pytest.raises((OSError, RuntimeError)):
        service._submit_session(
            PLAN_KIND,
            object(),
            detail_owner=("inventory", "request"),
            observation_sink=sink,
            session_attachment=_lifecycle_attachment(stage, counts, owners),
        )

    retained = (
        bool(observer.observations),
        _SESSION in owners,
        counts.attachment_successes > counts.owner_rollback_successes,
        dispatcher.cleanup_pending,
    )
    expected_retained = {
        "F1": (False, False, False, False),
        "F2": (False, False, False, False),
        "F3": (False, False, False, False),
        "F4": (False, False, False, False),
        "F5": (False, False, False, False),
        "R2": (False, False, False, False),
        "R3": (False, True, True, True),
        "R4": (False, False, True, True),
    }
    assert retained == expected_retained[stage]

    if dispatcher.cleanup_pending:
        dispatcher.retry()
    _assert_lifecycle_terminal_state(observer, owners, counts)

    assert (
        counts.application_rollback_attempts,
        counts.application_rollback_successes,
    ) == ((2, 1) if stage in {"R3", "R4"} else (1, 1))
    assert (counts.attachment_attempts, counts.attachment_successes) == (
        (1, 0) if stage == "F1" else (1, 1)
    )
    assert (owners.install_attempts, owners.install_successes) == {
        "F1": (0, 0),
        "F2": (1, 0),
    }.get(stage, (1, 1))
    assert (counts.observer_adopt_attempts, counts.observer_adopt_successes) == {
        "F1": (0, 0),
        "F2": (0, 0),
        "F3": (0, 0),
        "F4": (1, 0),
    }.get(stage, (1, 1))
    assert (counts.publication_attempts, counts.publication_successes) == (
        (1, 0) if stage in {"F5", "R2", "R3", "R4"} else (0, 0)
    )
    assert (counts.observer_rollback_attempts, counts.observer_rollback_successes) == {
        "F1": (0, 0),
        "F2": (0, 0),
        "F3": (0, 0),
        "F4": (0, 0),
    }.get(stage, (1, 1))
    assert (owners.retire_attempts, owners.retire_successes) == {
        "F1": (0, 0),
        "F2": (0, 0),
        "R3": (2, 1),
    }.get(stage, (1, 1))
    assert (counts.owner_rollback_attempts, counts.owner_rollback_successes) == {
        "F1": (0, 0),
        "R4": (2, 1),
    }.get(stage, (1, 1))
    assert (counts.stream_close_attempts, counts.stream_close_successes) == (
        (3, 1) if stage == "F3" else (2, 1)
    )


class _SinkOwner:
    pass


def test_ls_5_release_retires_stream_and_callback(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_entered = Event()
    emit_after_release = Event()
    emitted = Event()

    def run(_checkpoint):
        def action(context):
            workflow_entered.set()
            assert emit_after_release.wait(2)
            context.emit(PhaseChanged("after-release"))
            emitted.set()
            return OperationResult(SessionState.COMPLETED)

        return action

    dispatcher = Dispatcher({PLAN_KIND: _registration(run)})
    service = _service_for_dispatcher(tmp_path, monkeypatch, dispatcher)
    callback_seen = Event()
    callbacks: list[object] = []
    owner = _SinkOwner()
    owner_reference = ref(owner)

    def receive(update, retained_owner=owner) -> None:
        assert retained_owner is owner_reference()
        callbacks.append(update)
        callback_seen.set()

    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    session = service.start_plan(
        str(source),
        str(target),
        observation_sink=receive,
    )
    assert workflow_entered.wait(1)
    assert callback_seen.wait(1)
    service.unsubscribe(session.session_id)
    service.unsubscribe(session.session_id)
    callback_count = len(callbacks)
    assert service._observer._observations == {}
    assert dispatcher._hubs[session.session_id]._subscribers == []

    del receive, owner
    gc.collect()
    assert owner_reference() is None

    emit_after_release.set()
    assert emitted.wait(1)
    _wait_for_state(
        dispatcher,
        session.session_id,
        SessionState.COMPLETED,
    )
    Event().wait(0.02)
    assert len(callbacks) == callback_count
    service.close_session(session.session_id)
    assert service.close(timeout=2).complete
