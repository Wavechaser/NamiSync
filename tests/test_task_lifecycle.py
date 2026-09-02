"""Baseline lifecycle stop detectors and observation barriers."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
import gc
import io
from threading import Event, Lock, Thread, current_thread
from time import monotonic
from weakref import ref

import pytest

from namisync.core.evidence import RecordingStatus
from namisync.core.events import (
    CORE_EVENT_SCHEMA_VERSION,
    DeliveryClass,
    Envelope,
    PhaseChanged,
    delivery_class,
)
from namisync.core.session import OperationResult, ResourceId, SessionState
from namisync.dispatcher import (
    Dispatcher,
    InMemorySessionStore,
    PreparedSession,
    SessionCleanupPending,
    WorkflowRegistration,
)
from namisync.interfaces import service as service_module
from namisync.interfaces import task_lifecycle as lifecycle_module
from namisync.interfaces.cli import EXIT_CANCELED, _exit_for_record, _wait_for_result
from namisync.interfaces.service import NamiSyncService
from namisync.interfaces.task_lifecycle import (
    LifecycleAssociationError,
    LifecycleReceiptConflictError,
    LifecycleTaskCapacityError,
    TASK_EFFECT_CAPACITY,
    TaskLifecycle,
)
from namisync.interfaces.task_port import TaskLifecyclePort
from namisync.interfaces.web.bridge import (
    BridgeResponseTooLargeError,
    _admit_task_drain_response_prefix,
    _consume_task_drain_response,
    _peek_task_drain_response,
)
from namisync.interfaces.web.drain import TaskRegistry, _TaskDrainResponseCodec
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
) -> NamiSyncService:
    monkeypatch.setattr(service_module, "_dispatcher", lambda _runtime: dispatcher)
    return NamiSyncService(
        tmp_path / "ledger.db",
        tmp_path / "history.db",
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


def _gap_event(
    session_id: str,
    sequence: int,
    first_missed_seq: int,
) -> SessionEventView:
    return SessionEventView(
        session_id,
        sequence,
        "2026-01-01T00:00:00+00:00",
        CORE_EVENT_SCHEMA_VERSION,
        "Gap",
        {"first_missed_seq": first_missed_seq},
    )


def test_disc_b2_adapter_shutdown_wakes_offer_before_service_observer_release(
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
    )
    shutdown_order: list[str] = []
    registry = TaskRegistry(
        service,
        response_codec=_TaskDrainResponseCodec(
            BridgeResponseTooLargeError,
            _admit_task_drain_response_prefix,
            _peek_task_drain_response,
            _consume_task_drain_response,
        ),
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
        assert service._observer._observations != {}
    finally:
        registry.begin_close()
        finish_workflow.set()
        producer.join(1)

    _wait_for_state(
        dispatcher,
        start.session_id,
        SessionState.COMPLETED,
    )
    assert service.close(timeout=2).complete
    shutdown_order.append("service.close.complete")
    assert service._observer._observations == {}
    assert shutdown_order == [
        "adapter.offer.withdrawn",
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


def _assert_ls_1_reliable_delivery(
    producer_by_sequence: dict[int, SessionEventView],
    events: list[SessionEventView],
) -> None:
    delivered_producer_events = [
        event for event in events if event.body_type != "Gap"
    ]
    delivered_sequences = [
        event.sequence for event in delivered_producer_events
    ]
    assert len(delivered_sequences) == len(set(delivered_sequences))
    for delivered in delivered_producer_events:
        produced = producer_by_sequence[delivered.sequence]
        assert (delivered.body_type, delivered.body) == (
            produced.body_type,
            produced.body,
        )

    missing = sorted(set(producer_by_sequence) - set(delivered_sequences))
    assert missing
    coverage: list[tuple[int, int]] = []
    for index, event in enumerate(events):
        if event.body_type != "Gap":
            continue
        following = next(
            (
                candidate.sequence
                for candidate in events[index + 1 :]
                if candidate.body_type != "Gap"
            ),
            None,
        )
        assert following is not None
        first = event.body["first_missed_seq"]
        # Gap.sequence is a synthetic marker. The next producer event closes
        # the finite interval whose unavailable prefix this Gap announced.
        last = following - 1
        if first <= last:
            coverage.append((first, last))
    assert all(
        any(first <= sequence <= last for first, last in coverage)
        for sequence in missing
    )


def test_ls_1_detector_rejects_duplicate_and_unannounced_loss() -> None:
    producer = {
        sequence: _task_event(_SESSION, sequence)
        for sequence in range(1, 4)
    }
    with pytest.raises(AssertionError):
        _assert_ls_1_reliable_delivery(
            producer,
            [
                producer[1],
                producer[1],
                _gap_event(_SESSION, 2, 2),
                producer[3],
            ],
        )
    with pytest.raises(AssertionError):
        _assert_ls_1_reliable_delivery(
            producer,
            [producer[1], producer[3]],
        )


def test_ls_1_delivery_has_no_silent_loss_or_duplicate(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callback_entered = Event()
    release_callback = Event()
    allow_workflow = Event()
    allow_flood = Event()
    flood_done = Event()
    allow_terminal = Event()
    recovery_subscribed = Event()
    recovery_tail_delivered = Event()
    recovery_from: list[int] = []
    audit = _TraceAudit()

    def run(_checkpoint):
        def action(context):
            assert allow_workflow.wait(10)
            context.emit(PhaseChanged("phase-0"))
            assert callback_entered.wait(10)
            assert allow_flood.wait(10)
            for index in range(1, 200):
                context.emit(PhaseChanged(f"phase-{index}"))
            flood_done.set()
            assert allow_terminal.wait(10)
            return OperationResult(SessionState.COMPLETED)

        return action

    dispatcher = Dispatcher(
        {PLAN_KIND: _registration(run)},
        audit_observer_factory=lambda _record: audit,
        audit_capacity=512,
    )
    service = _service_for_dispatcher(tmp_path, monkeypatch, dispatcher)
    subscribe = dispatcher.subscribe
    subscriptions = []

    def record_recovery_subscription(session_id, from_seq=None):
        stream = subscribe(session_id, from_seq)
        subscriptions.append((from_seq, stream))
        if from_seq is not None:
            recovery_from.append(from_seq)
            recovery_subscribed.set()
        return stream

    monkeypatch.setattr(dispatcher, "subscribe", record_recovery_subscription)
    deliveries: list[SessionEventView | SessionRecordView] = []

    def receive(update: SessionEventView | SessionRecordView) -> None:
        deliveries.append(update)
        if (
            type(update) is SessionEventView
            and update.body_type == "PhaseChanged"
            and update.body == {"phase": "phase-0"}
        ):
            callback_entered.set()
            assert release_callback.wait(10)
        if (
            type(update) is SessionEventView
            and update.body_type == "PhaseChanged"
            and update.body == {"phase": "phase-199"}
        ):
            recovery_tail_delivered.set()

    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    session = service.start_plan(str(source), str(target))
    service.observe(session.session_id, receive)
    try:
        assert len(subscriptions) == 1 and subscriptions[0][0] is None
        initial_stream = subscriptions[0][1]
        allow_workflow.set()
        assert callback_entered.wait(10)
        allow_flood.set()
        assert flood_done.wait(10)
        assert initial_stream.ejected
        release_callback.set()
        assert recovery_subscribed.wait(10)
        assert recovery_tail_delivered.wait(10)
        allow_terminal.set()
    finally:
        allow_workflow.set()
        allow_flood.set()
        release_callback.set()
        allow_terminal.set()

    terminal = service.wait(session.session_id)
    assert terminal.result is not None
    hub = dispatcher._hubs[session.session_id]
    reliable_producer_by_sequence = {
        envelope.seq: session_event_view(envelope)
        for envelope in (*audit.snapshot(), *tuple(hub._replay))
        if delivery_class(envelope.body) is DeliveryClass.RELIABLE
    }
    events = [
        update for update in deliveries if type(update) is SessionEventView
    ]
    records = [
        update for update in deliveries if type(update) is SessionRecordView
    ]
    gaps = [event for event in events if event.body_type == "Gap"]

    assert gaps
    assert recovery_from == [gaps[0].body["first_missed_seq"]]
    assert any(
        gap.body["first_missed_seq"] == recovery_from[0]
        for gap in gaps[1:]
    )
    assert len(records) == 1 and records[0] == terminal
    assert deliveries[-1] == records[0]
    assert [event.body_type for event in events].count("Terminal") == 1
    assert events[-1].body_type == "Terminal"
    _assert_ls_1_reliable_delivery(
        reliable_producer_by_sequence,
        events,
    )

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
    service._lifecycle = TaskLifecycle()
    first = str(dispatcher.submit("control", "first"))
    second = str(dispatcher.submit("control", "second"))
    _publish_lifecycle_session(service._lifecycle, first)
    _publish_lifecycle_session(service._lifecycle, second)
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
    retirement = service._lifecycle.begin_settlement(
        first,
        close_task=False,
    )
    retirement_work = service._lifecycle.confirm_settlement(retirement)
    assert (
        retirement_work.session_id,
        retirement_work.detail_owner,
        retirement_work.plan_token,
        retirement_work.replay,
    ) == (
        first,
        None,
        None,
        False,
    )
    service._lifecycle.complete_settlement(retirement_work)
    for operation in (service.pause, service.resume, service.cancel):
        result = operation(first)
        assert not result.accepted and result.code == "not-found"
        assert dispatcher.get(second).state is SessionState.RUNNING

    assert service.cancel(second).accepted
    _wait_for_state(dispatcher, second, SessionState.CANCELED)
    dispatcher.close(second)
    assert dispatcher.shutdown().complete


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


@pytest.mark.parametrize(
    "stage",
    ("D1", "D2", "D3", "D4"),
)
def test_ls_4_dispatcher_admission_cleanup_converges(stage: str) -> None:
    _exercise_dispatcher_cleanup_stage(stage)


def test_lifecycle_admission_rollback_claim_singleflights_concurrent_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle = TaskLifecycle()
    detail_owner = ("inventory", "request")
    admission = lifecycle.begin_admission(
        "inventory",
        f"{60_001:032x}",
        ("inventory",),
        detail_owner=detail_owner,
    )
    lifecycle.attach_session(admission, _SESSION)
    first_claimed = Event()
    release_first = Event()
    contender_waiting = Event()
    claims = []
    condition_type = type(lifecycle._condition)
    original_wait = condition_type.wait

    def observe_wait(condition, timeout=None):
        if condition is lifecycle._condition:
            contender_waiting.set()
        return original_wait(condition, timeout)

    monkeypatch.setattr(condition_type, "wait", observe_wait)

    def owner() -> None:
        claim = lifecycle.begin_admission_rollback(admission)
        assert claim is not None
        claims.append(claim)
        first_claimed.set()
        assert release_first.wait(2)
        lifecycle.complete_admission_rollback(claim)

    def contender() -> None:
        assert first_claimed.wait(2)
        claims.append(lifecycle.begin_admission_rollback(admission))

    first = Thread(target=owner)
    second = Thread(target=contender)
    first.start()
    assert first_claimed.wait(1)
    second.start()
    assert contender_waiting.wait(1)
    assert len(claims) == 1
    assert (claims[0].session_id, claims[0].detail_owner) == (
        _SESSION,
        detail_owner,
    )
    release_first.set()
    first.join(2)
    second.join(2)
    assert not first.is_alive()
    assert not second.is_alive()
    assert claims[1] is None
    assert lifecycle.begin_admission_rollback(admission) is None
    with pytest.raises(LifecycleAssociationError):
        lifecycle.require_session(_SESSION, live=False)


def test_whole_admission_rollback_close_wakes_waiter_but_retains_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle = TaskLifecycle()
    admission = lifecycle.begin_admission(
        "inventory",
        f"{60_101:032x}",
        ("inventory",),
        detail_owner=("inventory", f"{60_102:032x}"),
    )
    session_id = f"{60_103:032x}"
    lifecycle.attach_session(admission, session_id)
    owner = lifecycle.begin_admission_rollback(admission)
    assert owner is not None

    contender_waiting = Event()
    failures: list[BaseException] = []
    condition_type = type(lifecycle._condition)
    original_wait = condition_type.wait

    def observe_wait(condition, timeout=None):
        if (
            condition is lifecycle._condition
            and current_thread().name == "admission-close-contender"
        ):
            contender_waiting.set()
        return original_wait(condition, timeout)

    monkeypatch.setattr(condition_type, "wait", observe_wait)

    def contend() -> None:
        try:
            lifecycle.begin_admission_rollback(admission)
        except BaseException as error:
            failures.append(error)

    contender = Thread(target=contend, name="admission-close-contender")
    contender.start()
    assert contender_waiting.wait(1)

    lifecycle.close()
    contender.join(2)
    assert not contender.is_alive()
    assert len(failures) == 1
    assert type(failures[0]) is RuntimeError
    assert str(failures[0]) == "service is closed"

    lifecycle.abandon_admission_rollback(owner)
    retained_cleanup = lifecycle.begin_admission_rollback(admission)
    assert retained_cleanup is not None
    assert (
        retained_cleanup.session_id,
        retained_cleanup.detail_owner,
    ) == (owner.session_id, owner.detail_owner)
    lifecycle.complete_admission_rollback(retained_cleanup)
    assert lifecycle.begin_admission_rollback(admission) is None
    with pytest.raises(LifecycleAssociationError):
        lifecycle.require_session(session_id, live=False)


def test_lifecycle_whole_admission_claim_replays_exact_subject() -> None:
    lifecycle = TaskLifecycle()
    detail_owner = ("inventory", f"{61_001:032x}")
    admission = lifecycle.begin_admission(
        "inventory",
        f"{61_002:032x}",
        ("inventory",),
        detail_owner=detail_owner,
    )
    session_id = f"{61_003:032x}"
    lifecycle.attach_session(admission, session_id)

    first = lifecycle.begin_admission_rollback(admission)
    assert first is not None
    assert (first.session_id, first.detail_owner) == (
        session_id,
        detail_owner,
    )
    lifecycle.abandon_admission_rollback(first)

    retry = lifecycle.begin_admission_rollback(admission)
    assert retry is not None
    assert retry.claim_id != first.claim_id
    assert (retry.session_id, retry.detail_owner) == (
        first.session_id,
        first.detail_owner,
    )
    lifecycle.complete_admission_rollback(retry)
    lifecycle.complete_admission_rollback(retry)

    assert lifecycle.begin_admission_rollback(admission) is None
    with pytest.raises(LifecycleAssociationError):
        lifecycle.require_session(session_id, live=False)


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
    )
    service.observe(session.session_id, receive)
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


def _publish_lifecycle_session(
    lifecycle: TaskLifecycle,
    session_id: str,
    *,
    command_id: str | None = None,
):
    signature = ("source", "target", None)
    admission = lifecycle.begin_admission(
        "plan",
        command_id,
        signature,
    )
    lifecycle.attach_session(admission, session_id)
    token, _receipt = lifecycle.publish_start(
        admission,
        session_id,
        f"{int(session_id, 16) + 1:032x}",
    )
    return token


def _lifecycle_state_names() -> set[str]:
    state_names = set(TaskLifecycle().__dict__)
    for candidate in vars(lifecycle_module).values():
        if (
            isinstance(candidate, type)
            and candidate.__module__ == lifecycle_module.__name__
            and is_dataclass(candidate)
        ):
            state_names.update(field.name for field in fields(candidate))
    return state_names


def test_lifecycle_state_has_no_cleanup_step_or_marker_progress() -> None:
    state_names = _lifecycle_state_names()

    forbidden = (
        "cursor",
        "marker",
        "step",
        "last_completed",
        "progress",
        "reservation",
    )
    assert not {
        name
        for name in state_names
        if any(part in name.lower() for part in forbidden)
    }


def test_lifecycle_retained_state_has_no_delivery_or_observer_resources() -> None:
    state_names = _lifecycle_state_names()
    forbidden = (
        "sink",
        "stream",
        "callback",
        "thread",
        "subscription",
        "queue",
        "drain",
        "connection",
        "delivery",
        "response",
        "rollback_callback",
    )
    assert not {
        name
        for name in state_names
        if name.lower() in {"stop", "done"}
        or any(part in name.lower() for part in forbidden)
    }


def test_task_lifecycle_port_surface_is_exact() -> None:
    assert {
        name
        for name, value in TaskLifecyclePort.__dict__.items()
        if not name.startswith("_") and callable(value)
    } == {
        "start_task_plan",
        "reobserve_task",
        "release_task_session",
        "close_task",
    }


def test_lifecycle_signatures_retain_only_immutable_scalars() -> None:
    retained_resource = object()
    lifecycle = TaskLifecycle()
    with pytest.raises(TypeError, match="immutable scalars"):
        lifecycle.begin_task_start("start", (retained_resource,))
    with pytest.raises(TypeError, match="immutable scalars"):
        lifecycle.begin_admission(
            "plan",
            None,
            (retained_resource,),
        )
    token = _publish_lifecycle_session(
        lifecycle,
        f"{40_000:032x}",
    )
    plan = lifecycle.require_plan(f"{40_001:032x}")
    with pytest.raises(TypeError, match="immutable scalars"):
        lifecycle.begin_plan_mutation(plan, None, (retained_resource,))
    assert lifecycle.require_session(token.session_id, live=False) == token


def _publish_lifecycle_task(
    lifecycle: TaskLifecycle,
    command_id: str,
    session_id: str,
):
    signature = ("source", "target", None)
    task = lifecycle.begin_task_start(command_id, signature)
    admission = lifecycle.begin_admission(
        "task-plan",
        command_id,
        signature,
        task_id=task.task_id,
    )
    token = lifecycle.attach_session(admission, session_id)
    token, receipt = lifecycle.publish_start(
        admission,
        session_id,
        f"{int(session_id, 16) + 1:032x}",
    )
    return task, token, receipt


def test_lifecycle_command_guard_singleflights_equal_commands() -> None:
    lifecycle = TaskLifecycle()
    owner_entered = Event()
    release_owner = Event()
    contender_attempted = Event()
    contender_entered = Event()

    def owner() -> None:
        with lifecycle.command_guard("same-command"):
            owner_entered.set()
            assert release_owner.wait(2)

    def contender() -> None:
        assert owner_entered.wait(2)
        contender_attempted.set()
        with lifecycle.command_guard("same-command"):
            contender_entered.set()

    owner_thread = Thread(target=owner)
    contender_thread = Thread(target=contender)
    owner_thread.start()
    contender_thread.start()
    assert contender_attempted.wait(1)
    assert not contender_entered.wait(0.02)
    release_owner.set()
    owner_thread.join(2)
    contender_thread.join(2)
    assert not owner_thread.is_alive()
    assert not contender_thread.is_alive()
    assert contender_entered.is_set()


def test_lifecycle_command_guard_allows_disjoint_commands_to_overlap() -> None:
    lifecycle = TaskLifecycle()
    first_entered = Event()
    release_first = Event()
    second_entered = Event()

    def first() -> None:
        with lifecycle.command_guard("command-a"):
            first_entered.set()
            assert release_first.wait(2)

    def second() -> None:
        assert first_entered.wait(2)
        with lifecycle.command_guard("command-b"):
            second_entered.set()

    first_thread = Thread(target=first)
    second_thread = Thread(target=second)
    first_thread.start()
    second_thread.start()
    assert second_entered.wait(1)
    release_first.set()
    first_thread.join(2)
    second_thread.join(2)
    assert not first_thread.is_alive()
    assert not second_thread.is_alive()


def test_lifecycle_task_capacity_precedes_new_effect_but_not_replay() -> None:
    lifecycle = TaskLifecycle(task_capacity=1)
    command_id = f"{41_001:032x}"
    _task, _token, receipt = _publish_lifecycle_task(
        lifecycle,
        command_id,
        f"{41_002:032x}",
    )

    replay = lifecycle.begin_task_start(
        command_id,
        ("source", "target", None),
    )
    assert replay.replay == receipt
    with pytest.raises(LifecycleTaskCapacityError, match="capacity"):
        lifecycle.begin_task_start(
            f"{41_003:032x}",
            ("other-source", "other-target", None),
        )
    assert TASK_EFFECT_CAPACITY == 48


def test_lifecycle_capacity_singleflights_owner_and_joiner_at_limit() -> None:
    lifecycle = TaskLifecycle()
    signature = ("source", "target", None)
    for index in range(TASK_EFFECT_CAPACITY - 1):
        _publish_lifecycle_task(
            lifecycle,
            f"{49_000 + index:032x}",
            f"{50_000 + index:032x}",
        )

    command_id = f"{51_000:032x}"
    session_id = f"{51_001:032x}"
    owner_reserved = Event()
    joiner_attempted = Event()
    release_owner = Event()
    owner_results = []
    joiner_results = []

    def owner() -> None:
        with lifecycle.command_guard(command_id):
            task = lifecycle.begin_task_start(command_id, signature)
            owner_reserved.set()
            assert release_owner.wait(2)
            admission = lifecycle.begin_admission(
                "task-plan",
                command_id,
                signature,
                task_id=task.task_id,
            )
            lifecycle.attach_session(admission, session_id)
            _association, receipt = lifecycle.publish_start(
                admission,
                session_id,
                f"{51_002:032x}",
            )
            owner_results.append((task, receipt))

    def joiner() -> None:
        assert owner_reserved.wait(2)
        joiner_attempted.set()
        with lifecycle.command_guard(command_id):
            joiner_results.append(
                lifecycle.begin_task_start(command_id, signature)
            )

    owner_thread = Thread(target=owner)
    joiner_thread = Thread(target=joiner)
    owner_thread.start()
    joiner_thread.start()
    assert owner_reserved.wait(1)
    assert joiner_attempted.wait(1)
    assert joiner_results == []
    with pytest.raises(LifecycleTaskCapacityError, match="capacity"):
        lifecycle.begin_task_start(f"{51_003:032x}", signature)
    release_owner.set()
    owner_thread.join(2)
    joiner_thread.join(2)
    assert not owner_thread.is_alive()
    assert not joiner_thread.is_alive()
    assert len(owner_results) == 1
    assert len(joiner_results) == 1
    assert joiner_results[0].task_id == owner_results[0][0].task_id
    assert joiner_results[0].replay == owner_results[0][1]


def test_lifecycle_task_start_publication_replays_one_receipt() -> None:
    lifecycle = TaskLifecycle()
    command_id = f"{51_101:032x}"
    session_id = f"{51_102:032x}"
    request_id = f"{51_103:032x}"
    signature = ("source", "target", None)
    task = lifecycle.begin_task_start(command_id, signature)
    admission = lifecycle.begin_admission(
        "task-plan",
        command_id,
        signature,
        task_id=task.task_id,
    )
    lifecycle.attach_session(admission, session_id)
    association, receipt = lifecycle.publish_start(
        admission,
        session_id,
        request_id,
    )
    repeated_association, repeated_receipt = lifecycle.publish_start(
        admission,
        session_id,
        request_id,
    )
    assert repeated_association == association
    assert repeated_receipt == receipt
    replay = lifecycle.begin_task_start(command_id, signature)
    assert replay.task_id == task.task_id
    assert replay.replay == receipt
    assert len(lifecycle._tasks) == 1
    assert len(lifecycle._sessions) == 1
    assert len(lifecycle._plans) == 1
    assert list(lifecycle._start_receipts.values()) == [receipt]


def test_lifecycle_direct_replay_joins_close_and_refuses_sealed_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle = TaskLifecycle()
    command_id = f"{51_201:032x}"
    session_id = f"{51_202:032x}"
    _publish_lifecycle_session(
        lifecycle,
        session_id,
        command_id=command_id,
    )
    signature = ("source", "target", None)
    claim = lifecycle.begin_settlement(
        session_id,
        close_task=False,
    )
    replay_waiting = Event()
    condition_type = type(lifecycle._condition)
    original_wait = condition_type.wait

    def observe_wait(condition, timeout=None):
        if (
            condition is lifecycle._condition
            and current_thread().name == "direct-replay"
        ):
            replay_waiting.set()
        return original_wait(condition, timeout)

    monkeypatch.setattr(condition_type, "wait", observe_wait)
    replays = []
    replay_thread = Thread(
        target=lambda: replays.append(
            lifecycle.replay_start(command_id, "plan", signature)
        ),
        name="direct-replay",
    )
    replay_thread.start()
    assert replay_waiting.wait(1)
    settlement = lifecycle.confirm_settlement(claim)
    lifecycle.complete_settlement(settlement)
    replay_thread.join(2)
    assert not replay_thread.is_alive()
    assert replays == [None]

    sealed = TaskLifecycle()
    sealed_command = f"{51_211:032x}"
    sealed_session = f"{51_212:032x}"
    _publish_lifecycle_session(
        sealed,
        sealed_session,
        command_id=sealed_command,
    )
    claim = sealed.begin_settlement(
        sealed_session,
        close_task=False,
    )
    sealed.confirm_settlement(claim)
    sealed.abandon_settlement(claim)
    with pytest.raises(LifecycleAssociationError, match="remains pending"):
        sealed.replay_start(sealed_command, "plan", signature)


def test_lifecycle_task_replay_crosses_release_but_joins_task_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle = TaskLifecycle()
    command_id = f"{51_301:032x}"
    session_id = f"{51_302:032x}"
    task, _token, receipt = _publish_lifecycle_task(
        lifecycle,
        command_id,
        session_id,
    )
    signature = ("source", "target", None)
    terminal_digest = b"t" * 32
    release = lifecycle.begin_settlement(
        session_id,
        task_id=task.task_id,
        close_task=False,
    )
    release_work = lifecycle.confirm_settlement(
        release,
        terminal_digest=terminal_digest,
        dispatcher_truth_observed=True,
    )
    assert lifecycle.replay_start(command_id, "task-plan", signature) == receipt
    lifecycle.complete_settlement(release_work)
    assert lifecycle.replay_start(command_id, "task-plan", signature) == receipt

    close = lifecycle.begin_settlement(
        session_id,
        task_id=task.task_id,
        close_task=True,
    )
    replay_waiting = Event()
    condition_type = type(lifecycle._condition)
    original_wait = condition_type.wait

    def observe_wait(condition, timeout=None):
        if (
            condition is lifecycle._condition
            and current_thread().name == "task-close-replay"
        ):
            replay_waiting.set()
        return original_wait(condition, timeout)

    monkeypatch.setattr(condition_type, "wait", observe_wait)
    replays = []
    replay_thread = Thread(
        target=lambda: replays.append(
            lifecycle.replay_start(command_id, "task-plan", signature)
        ),
        name="task-close-replay",
    )
    replay_thread.start()
    assert replay_waiting.wait(1)
    close_work = lifecycle.confirm_settlement(
        close,
        terminal_digest=terminal_digest,
    )
    assert close_work.plan_token is not None
    retirement = lifecycle.begin_plan_retirement(close_work.plan_token)
    assert retirement is not None
    lifecycle.complete_plan_retirement(retirement)
    lifecycle.complete_settlement(close_work)
    replay_thread.join(2)
    assert not replay_thread.is_alive()
    assert replays == [None]


def test_lifecycle_admission_claim_owns_exact_liabilities() -> None:
    lifecycle = TaskLifecycle()
    detail_owner = ("execution", f"{41_101:032x}")
    pre_attach = lifecycle.begin_admission(
        "execution",
        f"{41_102:032x}",
        ("execution",),
        detail_owner=detail_owner,
    )
    retirement = lifecycle.begin_admission_rollback(pre_attach)
    assert retirement is not None
    assert (retirement.session_id, retirement.detail_owner) == (
        None,
        detail_owner,
    )
    lifecycle.complete_admission_rollback(retirement)
    assert lifecycle.begin_admission_rollback(pre_attach) is None

    bound = lifecycle.begin_admission(
        "execution",
        f"{41_103:032x}",
        ("execution",),
        detail_owner=detail_owner,
    )
    session_id = f"{41_104:032x}"
    association = lifecycle.attach_session(bound, session_id)
    retirement = lifecycle.begin_admission_rollback(bound)
    assert retirement is not None
    assert (retirement.session_id, retirement.detail_owner) == (
        session_id,
        detail_owner,
    )
    lifecycle.complete_admission_rollback(retirement)
    with pytest.raises(LifecycleAssociationError):
        lifecycle.require_session(association.session_id, live=False)


def test_lifecycle_whole_settlement_claim_excludes_reobserve_and_same_session_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle = TaskLifecycle()
    session_id = f"{42_001:032x}"
    _publish_lifecycle_session(lifecycle, session_id)
    disjoint_id = f"{42_002:032x}"
    _publish_lifecycle_session(lifecycle, disjoint_id)
    observation = lifecycle.begin_observation(session_id)
    claims = []
    failures: list[BaseException] = []
    owner_waiting = Event()
    peer_waiting = Event()
    condition_type = type(lifecycle._condition)
    original_wait = condition_type.wait

    def observe_wait(condition, timeout=None):
        if condition is lifecycle._condition:
            if current_thread().name == "settlement-owner":
                owner_waiting.set()
            elif current_thread().name == "settlement-peer":
                peer_waiting.set()
        return original_wait(condition, timeout)

    monkeypatch.setattr(condition_type, "wait", observe_wait)

    def settle(label: str) -> None:
        try:
            claims.append(
                (
                    label,
                    lifecycle.begin_settlement(
                        session_id,
                        close_task=False,
                    ),
                )
            )
        except BaseException as error:
            failures.append(error)

    owner = Thread(
        target=settle,
        args=("owner",),
        name="settlement-owner",
    )
    owner.start()
    assert owner_waiting.wait(1)

    peer = Thread(
        target=settle,
        args=("peer",),
        name="settlement-peer",
    )
    peer.start()
    assert peer_waiting.wait(1)
    assert claims == []

    disjoint = lifecycle.begin_settlement(
        disjoint_id,
        close_task=False,
    )
    lifecycle.abandon_settlement(disjoint)

    lifecycle.end_observation(observation)
    owner.join(2)
    assert not owner.is_alive()
    assert failures == []
    assert len(claims) == 1
    assert claims[0][0] == "owner"
    with pytest.raises(LifecycleAssociationError, match="retired"):
        lifecycle.begin_observation(session_id)
    assert peer.is_alive()

    lifecycle.abandon_settlement(claims[0][1])
    peer.join(2)
    assert not peer.is_alive()
    assert failures == []
    assert [label for label, _claim in claims] == ["owner", "peer"]
    lifecycle.abandon_settlement(claims[1][1])

    replacement = lifecycle.begin_observation(session_id)
    lifecycle.end_observation(replacement)


def test_observation_claim_retries_from_observer_truth_without_marker_history(
) -> None:
    lifecycle = TaskLifecycle()
    session_id = f"{42_101:032x}"
    _publish_lifecycle_session(lifecycle, session_id)
    first = lifecycle.begin_observation(session_id)
    lifecycle.end_observation(first)

    replacement = lifecycle.begin_observation(session_id)
    lifecycle.end_observation(first)
    with lifecycle._condition:
        assert lifecycle._sessions[session_id].observation_claim == replacement
    lifecycle.end_observation(replacement)

    settlement = lifecycle.begin_settlement(
        session_id,
        close_task=False,
    )
    work = lifecycle.confirm_settlement(settlement)
    assert (work.session_id, work.detail_owner, work.plan_token) == (
        session_id,
        None,
        None,
    )
    lifecycle.abandon_settlement(settlement)


def test_lifecycle_close_wakes_settlement_claim_waiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle = TaskLifecycle()
    session_id = f"{44_001:032x}"
    _publish_lifecycle_session(lifecycle, session_id)
    observation = lifecycle.begin_observation(session_id)
    failures: list[BaseException] = []
    settlement_waiting = Event()
    condition_type = type(lifecycle._condition)
    original_wait = condition_type.wait

    def observe_wait(condition, timeout=None):
        if (
            condition is lifecycle._condition
            and current_thread().name == "settlement-close-waiter"
        ):
            settlement_waiting.set()
        return original_wait(condition, timeout)

    monkeypatch.setattr(condition_type, "wait", observe_wait)

    def settle() -> None:
        try:
            lifecycle.begin_settlement(session_id, close_task=False)
        except BaseException as error:
            failures.append(error)

    waiter = Thread(target=settle, name="settlement-close-waiter")
    waiter.start()
    assert settlement_waiting.wait(1)
    lifecycle.close()
    waiter.join(2)
    assert not waiter.is_alive()
    assert len(failures) == 1
    assert type(failures[0]) is LifecycleAssociationError
    lifecycle.end_observation(observation)


def test_lifecycle_whole_settlement_claim_retries_exact_subject() -> None:
    lifecycle = TaskLifecycle()
    session_id = f"{45_001:032x}"
    _publish_lifecycle_session(lifecycle, session_id)

    first = lifecycle.begin_settlement(
        session_id,
        close_task=False,
    )
    first_work = lifecycle.confirm_settlement(first)
    assert (
        first_work.session_id,
        first_work.detail_owner,
        first_work.plan_token,
        first_work.replay,
    ) == (session_id, None, None, False)
    lifecycle.abandon_settlement(first)

    retry = lifecycle.begin_settlement(
        session_id,
        close_task=False,
    )
    retry_work = lifecycle.confirm_settlement(retry)
    assert retry_work.claim != first_work.claim
    assert (
        retry_work.session_id,
        retry_work.detail_owner,
        retry_work.plan_token,
        retry_work.replay,
    ) == (
        first_work.session_id,
        first_work.detail_owner,
        first_work.plan_token,
        first_work.replay,
    )
    lifecycle.complete_settlement(retry_work)
    with pytest.raises(LifecycleAssociationError):
        lifecycle.require_session(session_id, live=False)


def test_lifecycle_plan_token_scopes_receipts_and_rejects_revival() -> None:
    lifecycle = TaskLifecycle()
    request_id = f"{46_001:032x}"
    command_id = f"{46_002:032x}"
    signature = (0, ("operation-a",), ())
    session_id = f"{46_000:032x}"
    _publish_lifecycle_session(lifecycle, session_id)
    assert request_id == f"{int(session_id, 16) + 1:032x}"
    token = lifecycle.require_plan(request_id)
    mutation = lifecycle.begin_plan_mutation(token, command_id, signature)
    assert not mutation.replay
    lifecycle.complete_plan_mutation(mutation)
    assert lifecycle.begin_plan_mutation(
        token,
        command_id,
        signature,
    ).replay
    retirement = lifecycle.begin_plan_retirement(token)
    assert retirement is not None
    lifecycle.complete_plan_retirement(retirement)

    with pytest.raises(LifecycleAssociationError, match="retired"):
        lifecycle.begin_plan_mutation(token, command_id, signature)
    with pytest.raises(LifecycleAssociationError, match="retired"):
        lifecycle.require_plan(request_id)

    successor_session = f"{46_100:032x}"
    _publish_lifecycle_session(
        lifecycle,
        successor_session,
    )
    successor_request = f"{int(successor_session, 16) + 1:032x}"
    successor = lifecycle.require_plan(successor_request)
    assert lifecycle.begin_plan_retirement(token) is None
    fresh = lifecycle.begin_plan_mutation(successor, command_id, signature)
    assert not fresh.replay
    lifecycle.complete_plan_mutation(fresh)
    replay = lifecycle.begin_plan_mutation(successor, command_id, signature)
    assert replay.replay
    with pytest.raises(LifecycleReceiptConflictError, match="different"):
        lifecycle.begin_plan_mutation(
            successor,
            command_id,
            (1, ("operation-a",), ()),
        )


def test_lifecycle_plan_retirement_excludes_mutation_and_wakes_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle = TaskLifecycle()
    session_id = f"{47_000:032x}"
    _publish_lifecycle_session(lifecycle, session_id)
    token = lifecycle.require_plan(f"{47_001:032x}")
    mutation = lifecycle.begin_plan_mutation(
        token,
        f"{47_002:032x}",
        (0, ("operation-a",), ()),
    )
    waiter_entered = Event()
    second_retirement_waiting = Event()
    mutation_waiting = Event()
    reader_waiting = Event()
    retirements = []
    failures: list[BaseException] = []
    condition_type = type(lifecycle._condition)
    original_wait = condition_type.wait
    wait_condition = lifecycle._condition

    def observe_wait(condition, timeout=None):
        if condition is wait_condition:
            if current_thread().name == "second-plan-retirement":
                second_retirement_waiting.set()
            elif current_thread().name == "retirement-mutation-contender":
                mutation_waiting.set()
            elif current_thread().name == "retirement-plan-reader":
                reader_waiting.set()
            else:
                waiter_entered.set()
        return original_wait(condition, timeout)

    monkeypatch.setattr(condition_type, "wait", observe_wait)

    def retire() -> None:
        try:
            retirements.append(lifecycle.begin_plan_retirement(token))
        except BaseException as error:
            failures.append(error)

    waiter = Thread(target=retire)
    waiter.start()
    assert waiter_entered.wait(1)
    mutation_failures: list[BaseException] = []

    def mutate_during_retirement() -> None:
        try:
            lifecycle.begin_plan_mutation(
                token,
                f"{47_003:032x}",
                (1, ("operation-a",), ()),
            )
        except BaseException as error:
            mutation_failures.append(error)

    contender = Thread(
        target=mutate_during_retirement,
        name="retirement-mutation-contender",
    )
    contender.start()
    assert mutation_waiting.wait(1)
    reader_failures: list[BaseException] = []

    def read_during_retirement() -> None:
        try:
            lifecycle.require_plan(token.request_id)
        except BaseException as error:
            reader_failures.append(error)

    reader = Thread(
        target=read_during_retirement,
        name="retirement-plan-reader",
    )
    reader.start()
    assert reader_waiting.wait(1)
    lifecycle.complete_plan_mutation(mutation)
    waiter.join(2)
    assert not waiter.is_alive()
    assert failures == []
    assert len(retirements) == 1
    second_retirements = []
    second_retirement = Thread(
        target=lambda: second_retirements.append(
            lifecycle.begin_plan_retirement(token)
        ),
        name="second-plan-retirement",
    )
    second_retirement.start()
    assert second_retirement_waiting.wait(1)
    lifecycle.complete_plan_retirement(retirements[0])
    second_retirement.join(2)
    contender.join(2)
    reader.join(2)
    assert not second_retirement.is_alive()
    assert not contender.is_alive()
    assert not reader.is_alive()
    assert second_retirements == [None]
    assert len(mutation_failures) == 1
    assert type(mutation_failures[0]) is LifecycleAssociationError
    assert len(reader_failures) == 1
    assert type(reader_failures[0]) is LifecycleAssociationError
    lifecycle.complete_plan_retirement(retirements[0])
    with pytest.raises(LifecycleAssociationError, match="retired"):
        lifecycle.require_plan(token.request_id)

    closing = TaskLifecycle()
    closing_session = f"{47_100:032x}"
    _publish_lifecycle_session(closing, closing_session)
    closing_token = closing.require_plan(f"{47_101:032x}")
    closing_mutation = closing.begin_plan_mutation(
        closing_token,
        f"{47_102:032x}",
        (0, ("operation-b",), ()),
    )
    waiter_entered.clear()
    wait_condition = closing._condition
    closing_failures: list[BaseException] = []

    def retire_while_closing() -> None:
        try:
            closing.begin_plan_retirement(closing_token)
        except BaseException as error:
            closing_failures.append(error)

    closing_waiter = Thread(target=retire_while_closing)
    closing_waiter.start()
    assert waiter_entered.wait(1)
    closing.close()
    closing_waiter.join(2)
    assert not closing_waiter.is_alive()
    assert len(closing_failures) == 1
    assert type(closing_failures[0]) is RuntimeError
    closing.abandon_plan_mutation(closing_mutation)

    reopening = TaskLifecycle()
    reopening_session = f"{47_200:032x}"
    _publish_lifecycle_session(reopening, reopening_session)
    reopening_token = reopening.require_plan(f"{47_201:032x}")
    reopening_retirement = reopening.begin_plan_retirement(reopening_token)
    mutation_waiting.clear()
    wait_condition = reopening._condition
    resumed_mutations = []

    def mutate_after_abandon() -> None:
        resumed_mutations.append(
            reopening.begin_plan_mutation(
                reopening_token,
                f"{47_202:032x}",
                (0, ("operation-c",), ()),
            )
        )

    resumed = Thread(
        target=mutate_after_abandon,
        name="retirement-mutation-contender",
    )
    resumed.start()
    assert mutation_waiting.wait(1)
    reopening.abandon_plan_retirement(reopening_retirement)
    resumed.join(2)
    assert not resumed.is_alive()
    assert len(resumed_mutations) == 1
    assert not resumed_mutations[0].replay
    reopening.abandon_plan_mutation(resumed_mutations[0])
