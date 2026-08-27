from __future__ import annotations

import gc
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event, Lock, Thread, current_thread, get_ident
from time import monotonic, sleep
from weakref import ref

import pytest

from namisync.core.evidence import RecordingStatus
from namisync.core.events import (
    Gap,
    ItemOutcome,
    PhaseChanged,
    StateChanged,
    Terminal,
    TerminalSummary,
)
from namisync.core.evidence import Outcome
from namisync.core.execution import (
    ItemRecordingReason,
    TaskRecordingIssue,
    TaskRecordingIssueReason,
)
from namisync.core.review import ReviewFactLimitExceeded
from namisync.core.session import (
    Canceled,
    Disposition,
    FailureDetail,
    OperationResult,
    PhaseResult,
    PhaseStatus,
    ResourceId,
    SessionId,
    SessionRecord,
    SessionState,
    StoredSessionRecord,
)
from namisync.dispatcher import (
    AdmissionClosed,
    ControlAction,
    ControlCode,
    Dispatcher,
    InProcessResourceLockProvider,
    PreparedSession,
    SessionCleanupPending,
    SessionNotFound,
    SessionNotTerminal,
    WorkflowRegistration,
)
from namisync.dispatcher.contracts import control_decision
from namisync.dispatcher.store import InMemorySessionStore


def wait_for(dispatcher: Dispatcher, session_id, state: SessionState, timeout=2.0):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        record = dispatcher.get(session_id)
        if record.state is state and (
            state not in (
                SessionState.COMPLETED,
                SessionState.FAILED,
                SessionState.CANCELED,
                SessionState.REFUSED,
            )
            or record.result is not None
        ):
            return record
        sleep(0.005)
    raise AssertionError(f"session did not reach {state}: {dispatcher.get(session_id)}")


def wait_for_admission_cleanup_attempt(
    dispatcher: Dispatcher,
    timeout: float = 2.0,
) -> None:
    deadline = monotonic() + timeout
    while True:
        with dispatcher._condition:
            attempt = dispatcher._admission_cleanup_attempt
        if attempt is None:
            return
        dispatcher._join_admission_cleanup_worker(attempt, deadline)
        if monotonic() >= deadline:
            raise AssertionError("admission cleanup worker did not retire")


@dataclass
class Invocation:
    run_fn: object
    snapshot_bytes: bytes = b"continued"

    def run(self, context):
        return self.run_fn(context)

    def snapshot(self) -> bytes:
        return self.snapshot_bytes


def registration(
    run_for_payload,
    *,
    supports_pause=False,
    resources=(),
    settle_canceled=None,
):
    def prepare(request):
        payload = request if isinstance(request, bytes) else str(request).encode()
        return PreparedSession(payload, frozenset(resources))

    return WorkflowRegistration(
        prepare=prepare,
        open=lambda payload: Invocation(run_for_payload(payload)),
        supports_pause=supports_pause,
        settle_canceled=settle_canceled,
    )


def completed(context):
    return OperationResult(SessionState.COMPLETED)


class RecordingSessionStore(InMemorySessionStore):
    def __init__(self) -> None:
        super().__init__()
        self.attempted: list[StoredSessionRecord] = []

    def put(self, record: StoredSessionRecord) -> None:
        self.attempted.append(record)
        super().put(record)


def assert_stored_record_matches(
    stored: StoredSessionRecord, live: SessionRecord
) -> None:
    assert type(stored) is StoredSessionRecord
    assert not hasattr(stored, "payload")
    assert stored.session_id == live.session_id
    assert stored.kind == live.kind
    assert stored.state is live.state
    assert stored.resources is live.resources
    assert stored.supports_pause is live.supports_pause
    assert stored.admission_order == live.admission_order
    assert stored.created_at == live.created_at
    assert stored.started_at == live.started_at
    assert stored.ended_at == live.ended_at
    assert stored.result is live.result


@pytest.mark.parametrize("accept_item", [False, True])
def test_failed_work_result_contains_only_accepted_items(accept_item: bool) -> None:
    item = ItemOutcome("e" * 32, "copy", "file.bin", Outcome.SUCCEEDED)
    original = OSError("reliable outcome sink failed")

    def run(context):
        if accept_item:
            context.emit(item)
        raise original

    dispatcher = Dispatcher({"sync": registration(lambda _payload: run)})
    session_id = dispatcher.submit("sync", b"payload")
    record = wait_for(dispatcher, session_id, SessionState.FAILED)

    assert record.result is not None
    assert record.result.status is SessionState.FAILED
    assert record.result.items == ((item,) if accept_item else ())
    assert record.result.error is not None
    assert record.result.error.type_name == "OSError"
    assert record.result.error.message == str(original)
    assert dispatcher.shutdown().complete


class GatedAcquireProvider:
    def __init__(self, gated_attempt: int = 1) -> None:
        self._gated_attempt = gated_attempt
        self.entered = Event()
        self.release = Event()
        self._lock = Lock()
        self._acquire_count = 0

    @property
    def acquire_count(self) -> int:
        with self._lock:
            return self._acquire_count

    def acquire(self, resources, canceled):
        with self._lock:
            self._acquire_count += 1
            attempt = self._acquire_count
        if attempt == self._gated_attempt:
            self.entered.set()
            assert self.release.wait(2)
            if canceled():
                raise Canceled()

        class Lease:
            def release(self) -> None:
                return None

        return Lease()


def test_disjoint_resources_overlap() -> None:
    active = 0
    maximum = 0
    active_lock = Lock()
    both_started = Event()
    release = Event()

    def run(context):
        nonlocal active, maximum
        with active_lock:
            active += 1
            maximum = max(maximum, active)
            if active == 2:
                both_started.set()
        assert release.wait(2)
        with active_lock:
            active -= 1
        return OperationResult(SessionState.COMPLETED)

    registry = {
        "a": registration(lambda payload: run, resources=(ResourceId("volume", "a"),)),
        "b": registration(lambda payload: run, resources=(ResourceId("volume", "b"),)),
    }
    dispatcher = Dispatcher(registry, lock_provider=InProcessResourceLockProvider())
    first = dispatcher.submit("a", b"first")
    second = dispatcher.submit("b", b"second")
    assert both_started.wait(2)
    release.set()
    wait_for(dispatcher, first, SessionState.COMPLETED)
    wait_for(dispatcher, second, SessionState.COMPLETED)
    assert maximum == 2
    assert dispatcher.shutdown().complete


def test_shared_resource_serializes_in_admission_order() -> None:
    first_started = Event()
    release_first = Event()
    second_started = Event()
    order: list[bytes] = []

    def run_for(payload):
        def run(context):
            order.append(payload)
            if payload == b"first":
                first_started.set()
                assert release_first.wait(2)
            else:
                second_started.set()
            return OperationResult(SessionState.COMPLETED)

        return run

    shared = ResourceId("volume", "shared")
    dispatcher = Dispatcher(
        {"hold": registration(run_for, resources=(shared,))},
        lock_provider=InProcessResourceLockProvider(),
    )
    first = dispatcher.submit("hold", b"first")
    second = dispatcher.submit("hold", b"second")
    assert first_started.wait(2)
    assert not second_started.wait(0.1)
    release_first.set()
    wait_for(dispatcher, first, SessionState.COMPLETED)
    wait_for(dispatcher, second, SessionState.COMPLETED)
    assert order == [b"first", b"second"]
    assert dispatcher.shutdown().complete


def test_scheduler_purges_stale_unschedulable_pending_entry() -> None:
    entered = Event()
    opened: list[bytes] = []
    provider = GatedAcquireProvider(gated_attempt=99)

    def pauseable_for(payload: bytes):
        opened.append(payload)

        def run(context):
            entered.set()
            while True:
                context.checkpoint()
                sleep(0.005)

        return run

    dispatcher = Dispatcher(
        {
            "pauseable": registration(
                pauseable_for,
                supports_pause=True,
                resources=(ResourceId("volume", "stale-pending"),),
            ),
            "probe": registration(
                lambda _payload: completed,
                resources=(ResourceId("volume", "scheduler-probe"),),
            ),
        },
        lock_provider=provider,
    )
    paused_id = dispatcher.submit("pauseable", b"paused")
    assert entered.wait(2)
    assert dispatcher.pause(paused_id).accepted
    wait_for(dispatcher, paused_id, SessionState.PAUSED)

    deadline = monotonic() + 2
    while monotonic() < deadline:
        with dispatcher._condition:
            if paused_id not in dispatcher._current_workers:
                dispatcher._pending.append(paused_id)
                dispatcher._condition.notify_all()
                break
        sleep(0.005)
    else:
        raise AssertionError("paused worker did not retire")

    probe_id = dispatcher.submit("probe", b"probe")
    wait_for(dispatcher, probe_id, SessionState.COMPLETED)

    assert dispatcher.get(paused_id).state is SessionState.PAUSED
    assert opened == [b"paused"]
    assert provider.acquire_count == 2
    with dispatcher._condition:
        assert paused_id not in dispatcher._pending
        assert paused_id not in dispatcher._current_workers
        assert all(key.session_id != paused_id for key in dispatcher._workers)
    assert dispatcher.shutdown().complete


def test_blocked_multi_resource_session_keeps_fifo_on_each_resource() -> None:
    x = ResourceId("volume", "fifo-x")
    y = ResourceId("volume", "fifo-y")
    holder_started = Event()
    release_holder = Event()
    later_started = Event()
    order: list[bytes] = []

    def hold(context):
        holder_started.set()
        assert release_holder.wait(2)
        return OperationResult(SessionState.COMPLETED)

    def record(payload):
        def run(context):
            order.append(payload)
            if payload == b"later":
                later_started.set()
            return OperationResult(SessionState.COMPLETED)

        return run

    dispatcher = Dispatcher(
        {
            "holder": registration(lambda payload: hold, resources=(x,)),
            "first": registration(record, resources=(x, y)),
            "later": registration(record, resources=(y,)),
        },
        lock_provider=InProcessResourceLockProvider(),
    )
    holder = dispatcher.submit("holder", b"holder")
    assert holder_started.wait(2)
    first = dispatcher.submit("first", b"first")
    later = dispatcher.submit("later", b"later")

    assert not later_started.wait(0.1)
    release_holder.set()
    wait_for(dispatcher, holder, SessionState.COMPLETED)
    wait_for(dispatcher, first, SessionState.COMPLETED)
    wait_for(dispatcher, later, SessionState.COMPLETED)
    assert order == [b"first", b"later"]
    assert dispatcher.shutdown().complete


def test_pause_releases_custody_and_resume_reopens_snapshotted_payload() -> None:
    entered = Event()
    opened: list[bytes] = []

    def run_for(payload):
        opened.append(payload)
        if payload == b"continued":
            return completed

        def pauseable(context):
            entered.set()
            while True:
                context.checkpoint()
                sleep(0.005)

        return pauseable

    resource = ResourceId("volume", "one")
    dispatcher = Dispatcher(
        {"pausable": registration(run_for, supports_pause=True, resources=(resource,))},
        lock_provider=InProcessResourceLockProvider(),
    )
    session_id = dispatcher.submit("pausable", b"initial")
    assert entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    paused = wait_for(dispatcher, session_id, SessionState.PAUSED)
    assert paused.payload == b"continued"
    assert dispatcher.resume(session_id).accepted
    completed_record = wait_for(
        dispatcher, session_id, SessionState.COMPLETED
    )
    assert completed_record.payload is None
    assert opened == [b"initial", b"continued"]
    assert dispatcher.shutdown().custody_released


@pytest.mark.parametrize(
    "terminal_state",
    [
        SessionState.COMPLETED,
        SessionState.FAILED,
        SessionState.CANCELED,
        SessionState.REFUSED,
    ],
)
def test_paused_resumed_terminal_paths_scrub_continuation_payload(
    terminal_state: SessionState,
) -> None:
    entered = Event()
    store = RecordingSessionStore()

    def run_for(payload):
        if payload == b"continued":
            return lambda context: OperationResult(
                terminal_state,
                disposition=(
                    Disposition.UNRUN
                    if terminal_state is SessionState.REFUSED
                    else Disposition.RAN
                ),
                canceled=terminal_state is SessionState.CANCELED,
            )

        def pauseable(context):
            entered.set()
            while True:
                context.checkpoint()
                sleep(0.005)

        return pauseable

    dispatcher = Dispatcher(
        {"pausable": registration(run_for, supports_pause=True)},
        store=store,
    )
    session_id = dispatcher.submit("pausable", b"initial")
    assert entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    paused = wait_for(dispatcher, session_id, SessionState.PAUSED)
    assert paused.payload == b"continued"
    assert_stored_record_matches(store.snapshot()[0], paused)
    assert dispatcher.resume(session_id).accepted

    terminal = wait_for(dispatcher, session_id, terminal_state)

    assert terminal.payload is None
    assert_stored_record_matches(store.snapshot()[0], terminal)
    assert all(type(record) is StoredSessionRecord for record in store.attempted)
    assert all(not hasattr(record, "payload") for record in store.attempted)
    assert dispatcher.shutdown().complete


def test_pause_settlement_and_live_event_wait_for_durable_audit_attempt() -> None:
    entered = Event()
    paused_seen = Event()
    flush_entered = Event()
    release_flush = Event()

    class Audit:
        def on_event(self, envelope) -> RecordingStatus:
            if (
                isinstance(envelope.body, StateChanged)
                and envelope.body.state is SessionState.PAUSED
            ):
                paused_seen.set()
            return RecordingStatus.OK

        def flush(self):
            if paused_seen.is_set():
                flush_entered.set()
                assert release_flush.wait(2)

        def finalize(self, result) -> RecordingStatus:
            return RecordingStatus.OK

        def close(self):
            pass

    def pauseable(context):
        entered.set()
        while True:
            context.checkpoint()
            sleep(0.005)

    dispatcher = Dispatcher(
        {
            "pausable": registration(
                lambda payload: pauseable,
                supports_pause=True,
            )
        },
        audit_observer_factory=lambda record: Audit(),
        audit_flush_interval=30.0,
        audit_timeout=1.0,
    )
    session_id = dispatcher.submit("pausable", b"payload")
    stream = dispatcher.subscribe(session_id)
    assert entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    assert flush_entered.wait(2)

    # Domain state leads the best-effort audit, but settlement and the live
    # PAUSED publication remain behind the durable-attempt barrier.
    assert dispatcher.get(session_id).state is SessionState.PAUSED
    assert session_id in dispatcher._current_workers
    visible_states = []
    while True:
        try:
            envelope = stream.next(0.05)
        except TimeoutError:
            break
        if isinstance(envelope.body, StateChanged):
            visible_states.append(envelope.body.state)
    assert SessionState.PAUSED not in visible_states

    release_flush.set()
    deadline = monotonic() + 2
    while session_id in dispatcher._current_workers and monotonic() < deadline:
        sleep(0.005)
    assert session_id not in dispatcher._current_workers
    assert stream.next(0.5).body == StateChanged(SessionState.PAUSED)

    assert dispatcher.cancel(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.CANCELED)
    assert dispatcher.shutdown().complete


@pytest.mark.parametrize("after_handoff", [False, True])
def test_immediate_resume_waits_for_paused_generation_retirement(
    monkeypatch, after_handoff: bool,
) -> None:
    first_entered = Event()
    retire_entered = Event()
    release_retirement = Event()
    probe_entered = Event()
    opened: list[bytes] = []
    session_ids = []

    def run_for(payload):
        opened.append(payload)
        if payload == b"continued":
            return completed

        def pauseable(context):
            first_entered.set()
            while True:
                context.checkpoint()
                sleep(0.005)

        return pauseable

    dispatcher = Dispatcher(
        {
            "pausable": registration(
                run_for,
                supports_pause=True,
                resources=(ResourceId("volume", "resume-gate"),),
            ),
            "probe": registration(
                lambda payload: lambda context: (
                    probe_entered.set()
                    or OperationResult(SessionState.COMPLETED)
                ),
                resources=(ResourceId("volume", "probe"),),
            ),
        }
    )
    original_worker_done = dispatcher._worker_done

    def gated_worker_done(key):
        if (
            session_ids
            and key.session_id == session_ids[0]
            and not retire_entered.is_set()
        ):
            if after_handoff:
                original_worker_done(key)
            retire_entered.set()
            assert release_retirement.wait(2)
            if after_handoff:
                return
        return original_worker_done(key)

    monkeypatch.setattr(dispatcher, "_worker_done", gated_worker_done)
    session_id = dispatcher.submit("pausable", b"initial")
    session_ids.append(session_id)
    assert first_entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.PAUSED)
    assert retire_entered.wait(2)

    try:
        with dispatcher._condition:
            old_key = dispatcher._current_workers[session_id]
        assert dispatcher.resume(session_id).accepted
        probe = dispatcher.submit("probe", b"probe")
        wait_for(dispatcher, probe, SessionState.COMPLETED)
        assert probe_entered.is_set()
        with dispatcher._condition:
            assert dispatcher._current_workers[session_id] == old_key
            assert tuple(
                key for key in dispatcher._workers if key.session_id == session_id
            ) == (old_key,)
        assert opened == [b"initial"]
    finally:
        release_retirement.set()

    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert opened == [b"initial", b"continued"]
    assert dispatcher.shutdown().complete


@pytest.mark.parametrize("after_handoff", [False, True])
def test_cancel_visible_paused_before_retirement_hands_off_once(
    monkeypatch, after_handoff: bool,
) -> None:
    first_entered = Event()
    retire_entered = Event()
    release_retirement = Event()
    probe_entered = Event()
    settled = []
    session_ids = []

    def pauseable(context):
        first_entered.set()
        while True:
            context.checkpoint()
            sleep(0.005)

    def settle_canceled(payload, disposition):
        settled.append((payload, disposition))
        return OperationResult(
            SessionState.CANCELED,
            disposition=disposition,
            canceled=True,
        )

    dispatcher = Dispatcher(
        {
            "pausable": registration(
                lambda payload: pauseable,
                supports_pause=True,
                resources=(ResourceId("volume", "cancel-pause-gate"),),
                settle_canceled=settle_canceled,
            ),
            "probe": registration(
                lambda payload: lambda context: (
                    probe_entered.set()
                    or OperationResult(SessionState.COMPLETED)
                ),
                resources=(ResourceId("volume", "cancel-probe"),),
            ),
        }
    )
    original_worker_done = dispatcher._worker_done

    def gated_worker_done(key):
        if (
            session_ids
            and key.session_id == session_ids[0]
            and not retire_entered.is_set()
        ):
            if after_handoff:
                original_worker_done(key)
            retire_entered.set()
            assert release_retirement.wait(2)
            if after_handoff:
                return
        return original_worker_done(key)

    monkeypatch.setattr(dispatcher, "_worker_done", gated_worker_done)
    session_id = dispatcher.submit("pausable", b"initial")
    session_ids.append(session_id)
    assert first_entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.PAUSED)
    assert retire_entered.wait(2)

    try:
        assert dispatcher.cancel(session_id).accepted
        wait_for(dispatcher, session_id, SessionState.CANCELING)
        probe = dispatcher.submit("probe", b"probe")
        wait_for(dispatcher, probe, SessionState.COMPLETED)
        assert probe_entered.is_set()
        assert settled == []
        with dispatcher._condition:
            assert sum(
                key.session_id == session_id for key in dispatcher._workers
            ) == 1
    finally:
        release_retirement.set()

    canceled = wait_for(dispatcher, session_id, SessionState.CANCELED)
    assert canceled.result is not None
    assert canceled.result.disposition is Disposition.RAN
    assert settled == [(b"continued", Disposition.RAN)]
    assert dispatcher.shutdown().complete


@pytest.mark.parametrize("exception_hook", [False, True])
def test_terminal_close_waits_for_actual_worker_exit(
    monkeypatch, exception_hook: bool,
) -> None:
    entered = Event()
    release_work = Event()
    retiring = Event()
    release_retirement = Event()
    invocation_refs = []
    session_ids = []
    hook_types = []
    store = InMemorySessionStore()

    class WorkerExit(BaseException):
        pass

    def run(context):
        entered.set()
        assert release_work.wait(2)
        return OperationResult(SessionState.COMPLETED)

    def open_invocation(payload):
        invocation = Invocation(run, payload)
        invocation_refs.append(ref(invocation))
        return invocation

    dispatcher = Dispatcher(
        {
            "held": WorkflowRegistration(
                lambda payload: PreparedSession(payload, frozenset()),
                open_invocation,
            ),
            "probe": registration(lambda _payload: completed),
        },
        store=store,
        audit_timeout=0.05,
    )
    original_worker_done = dispatcher._worker_done

    def gated_worker_done(key):
        original_worker_done(key)
        if key.session_id == session_ids[0]:
            if exception_hook:
                raise WorkerExit()
            retiring.set()
            assert release_retirement.wait(2)

    def hook(args):
        hook_types.append(args.exc_type)
        retiring.set()
        assert release_retirement.wait(2)

    monkeypatch.setattr(dispatcher, "_worker_done", gated_worker_done)
    if exception_hook:
        monkeypatch.setattr(threading, "excepthook", hook)
    try:
        session_id = dispatcher.submit("held", b"private invocation payload")
        session_ids.append(session_id)
        assert entered.wait(2)
        release_work.set()
        wait_for(dispatcher, session_id, SessionState.COMPLETED)
        assert retiring.wait(2)
        assert invocation_refs[0]() is not None

        probe = dispatcher.submit("probe", b"probe")
        wait_for(dispatcher, probe, SessionState.COMPLETED)
        with pytest.raises(TimeoutError, match="worker.*retir"):
            dispatcher.close(session_id)
        assert dispatcher.get(session_id).result is not None
        assert any(row.session_id == session_id for row in store.snapshot())
        assert session_id not in dispatcher._closing
        assert session_id not in dispatcher._cleanup_irreversible
        stream = dispatcher.subscribe(session_id)
        stream.close()

        shutdown = dispatcher.shutdown(0.03)
        assert not shutdown.complete
        assert session_id in shutdown.unfinished
        assert shutdown.custody_released
    finally:
        release_work.set()
        release_retirement.set()
        assert dispatcher.shutdown().complete

    dispatcher.close(session_id)
    with pytest.raises(SessionNotFound):
        dispatcher.get(session_id)
    gc.collect()
    assert invocation_refs[0]() is None
    assert hook_types == ([WorkerExit] if exception_hook else [])


def test_worker_self_close_is_retryable_without_dropping_session(monkeypatch) -> None:
    attempted = Event()
    close_outcomes = []
    dispatcher = Dispatcher({"work": registration(lambda _payload: completed)})
    original_worker_done = dispatcher._worker_done

    def close_from_worker(key):
        original_worker_done(key)
        try:
            dispatcher.close(key.session_id)
        except TimeoutError as error:
            close_outcomes.append(str(error))
        else:
            close_outcomes.append("closed")
        attempted.set()

    monkeypatch.setattr(dispatcher, "_worker_done", close_from_worker)
    try:
        session_id = dispatcher.submit("work", b"payload")
        assert attempted.wait(2)
        assert len(close_outcomes) == 1
        assert "own worker" in close_outcomes[0]
        assert dispatcher.get(session_id).result is not None
        dispatcher.close(session_id)
    finally:
        assert dispatcher.shutdown().complete


def test_terminal_close_releases_payload_while_scheduler_stays_alive() -> None:
    payload_refs = []

    class Payload(bytes):
        pass

    class PrivateGraph:
        pass

    def prepare(_request):
        payload = Payload(b"private continuation")
        payload.graph = PrivateGraph()
        payload_refs.append(ref(payload.graph))
        return PreparedSession(payload)

    dispatcher = Dispatcher(
        {"work": WorkflowRegistration(prepare, lambda _payload: Invocation(completed))}
    )
    try:
        session_id = dispatcher.submit("work", None)
        wait_for(dispatcher, session_id, SessionState.COMPLETED)
        dispatcher.close(session_id)
        assert dispatcher._scheduler.is_alive()
        gc.collect()
        assert payload_refs[0]() is None
    finally:
        assert dispatcher.shutdown().complete


def test_registered_unstarted_worker_is_not_reaped(monkeypatch) -> None:
    start_entered = Event()
    release_start = Event()
    original_start = Thread.start

    def gated_start(thread):
        if thread.name.startswith("namisync-session-"):
            start_entered.set()
            assert release_start.wait(2)
        original_start(thread)

    monkeypatch.setattr(Thread, "start", gated_start)
    dispatcher = Dispatcher({"work": registration(lambda _payload: completed)})
    try:
        session_id = dispatcher.submit("work", b"payload")
        assert start_entered.wait(2)
        with dispatcher._condition:
            key = dispatcher._current_workers[session_id]
            attempt = dispatcher._workers[key]
        assert attempt.thread.ident is None
        assert not attempt.thread.is_alive()

        shutdown = dispatcher.shutdown(0.03)
        assert not shutdown.complete
        assert session_id in shutdown.unfinished
        with dispatcher._condition:
            assert dispatcher._current_workers[session_id] == key
            assert dispatcher._workers[key] is attempt
    finally:
        release_start.set()
        assert dispatcher.shutdown().complete


def test_state_change_publication_cannot_fall_behind_a_later_transition(
    monkeypatch,
) -> None:
    entered = Event()
    pausing_emit_entered = Event()
    paused_emit_entered = Event()
    release_pausing_emit = Event()

    def pauseable(context):
        entered.set()
        while True:
            context.checkpoint()
            sleep(0.005)

    dispatcher = Dispatcher(
        {
            "pausable": registration(
                lambda payload: pauseable,
                supports_pause=True,
            )
        }
    )
    session_id = dispatcher.submit("pausable", b"payload")
    stream = dispatcher.subscribe(session_id)
    assert entered.wait(2)
    hub = dispatcher._hubs[session_id]
    original_emit = hub.emit

    def blocking_emit(body):
        if (
            isinstance(body, StateChanged)
            and body.state is SessionState.PAUSING
        ):
            pausing_emit_entered.set()
            assert release_pausing_emit.wait(2)
        elif (
            isinstance(body, StateChanged)
            and body.state is SessionState.PAUSED
        ):
            paused_emit_entered.set()
        return original_emit(body)

    monkeypatch.setattr(hub, "emit", blocking_emit)
    pause_result = []
    pause_thread = Thread(
        target=lambda: pause_result.append(dispatcher.pause(session_id))
    )
    pause_thread.start()
    assert pausing_emit_entered.wait(2)
    try:
        assert not paused_emit_entered.wait(0.1)
        assert dispatcher.get(session_id).state is SessionState.PAUSING
    finally:
        release_pausing_emit.set()
        pause_thread.join(2)

    assert not pause_thread.is_alive()
    assert pause_result[0].accepted
    wait_for(dispatcher, session_id, SessionState.PAUSED)
    assert dispatcher.cancel(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.CANCELED)

    states = []
    while True:
        try:
            envelope = stream.next(0.05)
        except (TimeoutError, StopIteration):
            break
        if isinstance(envelope.body, StateChanged):
            states.append(envelope.body.state)
    assert states == [
        SessionState.PENDING,
        SessionState.RUNNING,
        SessionState.PAUSING,
        SessionState.PAUSED,
        SessionState.CANCELING,
        SessionState.CANCELED,
    ]
    assert dispatcher.shutdown().complete


def test_pause_before_invocation_run_snapshots_before_later_cancel(
    monkeypatch,
) -> None:
    run_core_entered = Event()
    release_run_core = Event()
    invocation_run_entered = Event()
    settled_payloads = []

    def run(context):
        invocation_run_entered.set()
        return OperationResult(SessionState.COMPLETED)

    def settle_canceled(payload, disposition):
        settled_payloads.append(payload)
        if payload != b"continued":
            raise ValueError("pause did not retain the continuation")
        return OperationResult(
            SessionState.CANCELED,
            disposition=disposition,
            canceled=True,
        )

    dispatcher = Dispatcher(
        {
            "pausable": registration(
                lambda payload: run,
                supports_pause=True,
                settle_canceled=settle_canceled,
            )
        }
    )
    original_run_core = dispatcher._run_core

    def blocking_run_core(*args, **kwargs):
        run_core_entered.set()
        assert release_run_core.wait(2)
        return original_run_core(*args, **kwargs)

    monkeypatch.setattr(dispatcher, "_run_core", blocking_run_core)
    session_id = dispatcher.submit("pausable", b"initial")
    assert run_core_entered.wait(2)
    assert dispatcher.get(session_id).state is SessionState.RUNNING
    assert dispatcher.pause(session_id).accepted
    release_run_core.set()
    wait_for(dispatcher, session_id, SessionState.PAUSED)

    deadline = monotonic() + 2
    while monotonic() < deadline:
        with dispatcher._condition:
            if session_id not in dispatcher._current_workers:
                break
        sleep(0.005)
    else:
        raise AssertionError("paused worker did not finish")

    assert dispatcher.cancel(session_id).accepted
    record = wait_for(dispatcher, session_id, SessionState.CANCELED)
    assert record.payload is None
    assert record.result is not None
    assert record.result.disposition is Disposition.RAN
    assert settled_payloads == [b"continued"]
    assert not invocation_run_entered.is_set()
    assert dispatcher.shutdown().complete


def test_resume_canceled_before_invocation_run_uses_retained_settlement(
    monkeypatch,
) -> None:
    first_entered = Event()
    resumed_run_core = Event()
    release_run_core = Event()
    resumed_invocation = Event()
    settled: list[tuple[bytes, Disposition]] = []

    def run_for(payload):
        if payload == b"initial":
            def pauseable(context):
                first_entered.set()
                while True:
                    context.checkpoint()
                    sleep(0.005)

            return pauseable

        def should_not_run(context):
            resumed_invocation.set()
            return OperationResult(SessionState.COMPLETED)

        return should_not_run

    def settle_canceled(payload, disposition):
        settled.append((payload, disposition))
        return OperationResult(
            SessionState.CANCELED,
            disposition=disposition,
            canceled=True,
        )

    dispatcher = Dispatcher(
        {
            "pausable": registration(
                run_for,
                supports_pause=True,
                settle_canceled=settle_canceled,
            )
        }
    )
    session_id = dispatcher.submit("pausable", b"initial")
    assert first_entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.PAUSED)

    deadline = monotonic() + 2
    while monotonic() < deadline:
        with dispatcher._condition:
            if session_id not in dispatcher._current_workers:
                break
        sleep(0.005)
    else:
        raise AssertionError("paused worker did not finish")

    original_run_core = dispatcher._run_core

    def blocking_run_core(*args, **kwargs):
        resumed_run_core.set()
        assert release_run_core.wait(2)
        return original_run_core(*args, **kwargs)

    monkeypatch.setattr(dispatcher, "_run_core", blocking_run_core)
    assert dispatcher.resume(session_id).accepted
    assert resumed_run_core.wait(2)
    assert dispatcher.get(session_id).state is SessionState.RUNNING
    assert dispatcher.cancel(session_id).accepted
    release_run_core.set()
    record = wait_for(dispatcher, session_id, SessionState.CANCELED)

    assert settled == [(b"continued", Disposition.RAN)]
    assert record.result is not None
    assert record.result.disposition is Disposition.RAN
    assert not resumed_invocation.is_set()
    assert dispatcher.shutdown().complete


def test_resume_reenters_at_back_of_contended_resource_queue() -> None:
    first_entered = Event()
    second_entered = Event()
    release_second = Event()
    opened: list[bytes] = []

    def run_for(payload):
        opened.append(payload)
        if payload == b"first":
            def pauseable(context):
                first_entered.set()
                while True:
                    context.checkpoint()
                    sleep(0.005)
            return pauseable
        if payload == b"continued":
            return completed

        def hold(context):
            second_entered.set()
            assert release_second.wait(2)
            return OperationResult(SessionState.COMPLETED)

        return hold

    resource = ResourceId("volume", "shared-resume")
    dispatcher = Dispatcher(
        {"pausable": registration(run_for, supports_pause=True, resources=(resource,))},
        lock_provider=InProcessResourceLockProvider(),
    )
    first = dispatcher.submit("pausable", b"first")
    assert first_entered.wait(2)
    assert dispatcher.pause(first).accepted
    second = dispatcher.submit("pausable", b"second")
    wait_for(dispatcher, first, SessionState.PAUSED)
    assert dispatcher.resume(first).accepted
    assert second_entered.wait(2)
    assert dispatcher.get(first).state is SessionState.PENDING
    release_second.set()
    wait_for(dispatcher, second, SessionState.COMPLETED)
    wait_for(dispatcher, first, SessionState.COMPLETED)
    assert opened == [b"first", b"second", b"continued"]
    assert dispatcher.shutdown().complete


def test_pause_resume_cancel_terminal_retains_pre_pause_item_outcome() -> None:
    first_entered = Event()
    resumed = Event()

    def run_for(payload):
        if payload == b"initial":
            def first_attempt(context):
                context.emit(
                    ItemOutcome("e" * 32, "copy", "file", Outcome.SUCCEEDED)
                )
                first_entered.set()
                while True:
                    context.checkpoint()
                    sleep(0.005)
            return first_attempt

        def second_attempt(context):
            resumed.set()
            while True:
                context.checkpoint()
                sleep(0.005)

        return second_attempt

    dispatcher = Dispatcher(
        {"pausable": registration(run_for, supports_pause=True)}
    )
    session_id = dispatcher.submit("pausable", b"initial")
    assert first_entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.PAUSED)
    assert dispatcher.resume(session_id).accepted
    assert resumed.wait(2)
    assert dispatcher.cancel(session_id).accepted
    record = wait_for(dispatcher, session_id, SessionState.CANCELED)
    assert record.result is not None
    assert len(record.result.items) == 1
    earned = record.result.items[0]
    assert isinstance(earned, ItemOutcome)
    assert earned.item_id == "e" * 32
    assert dispatcher.shutdown().complete


def test_cancel_paused_uses_registration_owned_axis_preserving_settlement() -> None:
    entered = Event()
    opened: list[bytes] = []
    settled: list[tuple[bytes, Disposition]] = []

    def run_for(payload):
        opened.append(payload)

        def pauseable(context):
            context.emit(
                ItemOutcome("e" * 32, "copy", "file.bin", Outcome.SUCCEEDED)
            )
            entered.set()
            while True:
                context.checkpoint()
                sleep(0.005)

        return pauseable

    def settle_canceled(payload, disposition):
        settled.append((payload, disposition))
        return OperationResult(
            SessionState.COMPLETED,
            disposition=disposition,
            canceled=True,
            phases=(
                PhaseResult(
                    "execute", PhaseStatus.COMPLETED, 1, 1, 7, 7
                ),
                PhaseResult(
                    "verify", PhaseStatus.CANCELED, 0, 1, 0, 7
                ),
            ),
            bytes_done=7,
            bytes_total=7,
        )

    dispatcher = Dispatcher(
        {
            "compound": registration(
                run_for,
                supports_pause=True,
                settle_canceled=settle_canceled,
            )
        }
    )
    session_id = dispatcher.submit("compound", b"initial")
    stream = dispatcher.subscribe(session_id)
    assert entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    paused = wait_for(dispatcher, session_id, SessionState.PAUSED)
    assert paused.payload == b"continued"
    assert dispatcher.cancel(session_id).accepted
    record = wait_for(dispatcher, session_id, SessionState.CANCELED)

    assert settled == [(b"continued", Disposition.RAN)]
    assert opened == [b"initial"]
    assert record.result is not None
    assert record.result.status is SessionState.COMPLETED
    assert record.result.canceled is True
    assert [item.item_id for item in record.result.items] == ["e" * 32]
    assert [phase.status for phase in record.result.phases] == [
        PhaseStatus.COMPLETED,
        PhaseStatus.CANCELED,
    ]
    terminals = []
    while True:
        try:
            envelope = stream.next(0.05)
        except (TimeoutError, StopIteration):
            break
        if isinstance(envelope.body, Terminal):
            terminals.append(envelope.body)
    assert len(terminals) == 1
    assert terminals[0].result == TerminalSummary.from_result(record.result)
    assert dispatcher.shutdown().complete


def test_cancel_during_pausing_snapshot_drain_settles_once_and_releases_custody() -> None:
    entered = Event()
    snapshot_entered = Event()
    release_snapshot = Event()
    follower_entered = Event()
    settled: list[tuple[bytes, Disposition]] = []
    resource = ResourceId("volume", "pausing-drain")

    class BlockingSnapshot(Invocation):
        def snapshot(self) -> bytes:
            snapshot_entered.set()
            assert release_snapshot.wait(2)
            return b"continued"

    def pauseable(context):
        context.emit(
            ItemOutcome("e" * 32, "copy", "file.bin", Outcome.SUCCEEDED)
        )
        entered.set()
        while True:
            context.checkpoint()
            sleep(0.005)

    def settle_canceled(payload, disposition):
        settled.append((payload, disposition))
        return OperationResult(
            SessionState.CANCELED,
            disposition=disposition,
            canceled=True,
        )

    def follower(context):
        follower_entered.set()
        return OperationResult(SessionState.COMPLETED)

    dispatcher = Dispatcher(
        {
            "compound": WorkflowRegistration(
                prepare=lambda request: PreparedSession(
                    b"initial", frozenset({resource})
                ),
                open=lambda payload: BlockingSnapshot(pauseable),
                supports_pause=True,
                settle_canceled=settle_canceled,
            ),
            "follower": registration(
                lambda payload: follower,
                resources=(resource,),
            ),
        },
        lock_provider=InProcessResourceLockProvider(),
    )
    session_id = dispatcher.submit("compound", object())
    stream = dispatcher.subscribe(session_id)
    assert entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    assert snapshot_entered.wait(2)
    assert dispatcher.get(session_id).state is SessionState.PAUSING

    cancel = dispatcher.cancel(session_id)
    assert cancel.accepted
    assert cancel.before is SessionState.PAUSING
    assert cancel.after is SessionState.PAUSING
    assert dispatcher.get(session_id).state is SessionState.PAUSING
    release_snapshot.set()

    record = wait_for(dispatcher, session_id, SessionState.CANCELED)
    assert settled == [(b"continued", Disposition.RAN)]
    assert record.started_at is not None
    assert record.payload is None
    assert record.result is not None
    assert [item.item_id for item in record.result.items] == ["e" * 32]
    assert dispatcher.cancel(session_id).code is ControlCode.ILLEGAL_STATE
    assert settled == [(b"continued", Disposition.RAN)]

    follower_id = dispatcher.submit("follower", b"next")
    assert follower_entered.wait(2)
    wait_for(dispatcher, follower_id, SessionState.COMPLETED)

    terminals = []
    while True:
        try:
            envelope = stream.next(0.05)
        except (TimeoutError, StopIteration):
            break
        if isinstance(envelope.body, Terminal):
            terminals.append(envelope.body)
    assert len(terminals) == 1
    assert terminals[0].result == TerminalSummary.from_result(record.result)
    shutdown = dispatcher.shutdown()
    assert shutdown.complete
    assert shutdown.custody_released


def test_malformed_canceled_settlement_fails_loudly_once() -> None:
    entered = Event()
    settled: list[tuple[bytes, Disposition]] = []

    def pauseable(context):
        entered.set()
        while True:
            context.checkpoint()
            sleep(0.005)

    def malformed_settlement(payload, disposition):
        settled.append((payload, disposition))
        return OperationResult(SessionState.COMPLETED)

    dispatcher = Dispatcher(
        {
            "compound": registration(
                lambda payload: pauseable,
                supports_pause=True,
                settle_canceled=malformed_settlement,
            )
        }
    )
    session_id = dispatcher.submit("compound", b"initial")
    stream = dispatcher.subscribe(session_id)
    assert entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.PAUSED)
    assert dispatcher.cancel(session_id).accepted
    record = wait_for(dispatcher, session_id, SessionState.FAILED)

    assert settled == [(b"continued", Disposition.RAN)]
    assert record.result is not None
    assert record.result.canceled is False
    assert record.result.error is not None
    assert record.result.error.type_name == "ValueError"
    assert (
        record.result.error.message
        == "canceled settlement must project to CANCELED"
    )
    assert dispatcher.cancel(session_id).code is ControlCode.ILLEGAL_STATE
    assert settled == [(b"continued", Disposition.RAN)]

    terminals = []
    while True:
        try:
            envelope = stream.next(0.05)
        except (TimeoutError, StopIteration):
            break
        if isinstance(envelope.body, Terminal):
            terminals.append(envelope.body)
    assert len(terminals) == 1
    assert terminals[0].result == TerminalSummary.from_result(record.result)
    shutdown = dispatcher.shutdown()
    assert shutdown.complete
    assert shutdown.custody_released


def test_cancel_resumed_pending_uses_started_settlement_once() -> None:
    first_entered = Event()
    blocker_entered = Event()
    release_blocker = Event()
    settled: list[tuple[bytes, Disposition]] = []
    resource = ResourceId("volume", "shared")
    store = RecordingSessionStore()

    def compound_for(payload):
        def run(context):
            if payload == b"initial":
                first_entered.set()
                while True:
                    context.checkpoint()
                    sleep(0.005)
            pytest.fail("resumed invocation ran before pending cancellation")

        return run

    def blocker_for(payload):
        del payload

        def run(context):
            blocker_entered.set()
            assert release_blocker.wait(2)
            return OperationResult(SessionState.COMPLETED)

        return run

    def settle_canceled(payload, disposition):
        settled.append((payload, disposition))
        return OperationResult(
            SessionState.COMPLETED,
            disposition=disposition,
            canceled=True,
            phases=(
                PhaseResult(
                    "execute", PhaseStatus.COMPLETED, 1, 1, 7, 7
                ),
                PhaseResult(
                    "verify", PhaseStatus.CANCELED, 0, 1, 0, 7
                ),
            ),
            bytes_done=7,
            bytes_total=7,
        )

    dispatcher = Dispatcher(
        {
            "compound": registration(
                compound_for,
                supports_pause=True,
                resources=(resource,),
                settle_canceled=settle_canceled,
            ),
            "blocker": registration(
                blocker_for,
                resources=(resource,),
            ),
        },
        store=store,
        lock_provider=InProcessResourceLockProvider(),
    )
    session_id = dispatcher.submit("compound", b"initial")
    assert first_entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.PAUSED)

    blocker = dispatcher.submit("blocker", b"blocker")
    assert blocker_entered.wait(2)
    assert dispatcher.resume(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.PENDING)
    assert dispatcher.cancel(session_id).accepted
    record = wait_for(dispatcher, session_id, SessionState.CANCELED)

    assert settled == [(b"continued", Disposition.RAN)]
    stored = next(row for row in store.snapshot() if row.session_id == session_id)
    assert_stored_record_matches(stored, record)
    assert any(
        row.session_id == session_id
        and row.state is SessionState.PENDING
        and row.started_at is not None
        for row in store.attempted
    )
    assert all(type(row) is StoredSessionRecord for row in store.attempted)
    assert all(not hasattr(row, "payload") for row in store.attempted)
    assert record.result is not None
    assert record.result.status is SessionState.COMPLETED
    assert dispatcher.cancel(session_id).code is ControlCode.ILLEGAL_STATE
    assert settled == [(b"continued", Disposition.RAN)]

    release_blocker.set()
    wait_for(dispatcher, blocker, SessionState.COMPLETED)
    assert dispatcher.shutdown().complete


def test_cancel_running_session_emits_one_terminal_and_releases_custody() -> None:
    entered = Event()

    def run(context):
        entered.set()
        while True:
            context.checkpoint()
            sleep(0.005)

    dispatcher = Dispatcher(
        {
            "pausable": registration(
                lambda payload: run,
                supports_pause=True,
                resources=(ResourceId("volume", "one"),),
            )
        },
        lock_provider=InProcessResourceLockProvider(),
    )
    session_id = dispatcher.submit("pausable", b"payload")
    stream = dispatcher.subscribe(session_id)
    assert entered.wait(2)
    assert dispatcher.cancel(session_id).accepted
    record = wait_for(dispatcher, session_id, SessionState.CANCELED)
    terminals = []
    while True:
        try:
            envelope = stream.next(0.05)
        except (TimeoutError, StopIteration):
            break
        if isinstance(envelope.body, Terminal):
            terminals.append(envelope.body)
    assert len(terminals) == 1
    assert record.result is not None
    assert record.result.disposition is Disposition.RAN
    assert dispatcher.shutdown().custody_released


def test_cancel_after_scheduler_dequeue_keeps_single_worker_and_reservation() -> None:
    provider = GatedAcquireProvider()
    follower_started = Event()
    resource = ResourceId("volume", "dequeue-race")

    def run_for(payload):
        if payload == b"follower":
            def run(context):
                follower_started.set()
                return OperationResult(SessionState.COMPLETED)

            return run
        return completed

    dispatcher = Dispatcher(
        {"sync": registration(run_for, resources=(resource,))},
        lock_provider=provider,
    )
    original = dispatcher.submit("sync", b"original")
    stream = dispatcher.subscribe(original)
    assert provider.entered.wait(2)
    assert dispatcher.cancel(original).accepted
    follower = dispatcher.submit("sync", b"follower")
    wait_for(dispatcher, original, SessionState.CANCELING)

    sleep(0.05)
    assert provider.acquire_count == 1
    assert not follower_started.is_set()

    provider.release.set()
    canceled = wait_for(dispatcher, original, SessionState.CANCELED)
    wait_for(dispatcher, follower, SessionState.COMPLETED)
    terminals = []
    while True:
        try:
            envelope = stream.next(0.05)
        except (TimeoutError, StopIteration):
            break
        if isinstance(envelope.body, Terminal):
            terminals.append(envelope.body)

    assert canceled.result is not None
    assert canceled.result.disposition is Disposition.UNRUN
    assert len(terminals) == 1
    assert provider.acquire_count == 2
    shutdown = dispatcher.shutdown()
    assert shutdown.complete
    assert shutdown.custody_released
    assert dispatcher._workers == {}
    assert dispatcher._current_workers == {}
    assert dispatcher._leases == {}
    assert dispatcher._reserved == {}


def test_cancel_resumed_attempt_during_acquire_settles_continuation_once() -> None:
    provider = GatedAcquireProvider(gated_attempt=2)
    first_entered = Event()
    resumed_invocation = Event()
    probe_entered = Event()
    settled = []
    resource = ResourceId("volume", "resumed-acquire")

    def run_for(payload):
        if payload == b"initial":
            def pauseable(context):
                first_entered.set()
                while True:
                    context.checkpoint()
                    sleep(0.005)

            return pauseable

        def should_not_run(context):
            resumed_invocation.set()
            return OperationResult(SessionState.COMPLETED)

        return should_not_run

    def settle_canceled(payload, disposition):
        settled.append((payload, disposition))
        return OperationResult(
            SessionState.CANCELED,
            disposition=disposition,
            canceled=True,
        )

    dispatcher = Dispatcher(
        {
            "pausable": registration(
                run_for,
                supports_pause=True,
                resources=(resource,),
                settle_canceled=settle_canceled,
            ),
            "probe": registration(
                lambda payload: lambda context: (
                    probe_entered.set()
                    or OperationResult(SessionState.COMPLETED)
                ),
                resources=(ResourceId("volume", "resumed-probe"),),
            ),
        },
        lock_provider=provider,
    )
    session_id = dispatcher.submit("pausable", b"initial")
    stream = dispatcher.subscribe(session_id)
    assert first_entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.PAUSED)
    deadline = monotonic() + 2
    while monotonic() < deadline:
        with dispatcher._condition:
            if session_id not in dispatcher._current_workers:
                break
        sleep(0.005)
    else:
        raise AssertionError("paused worker did not retire")

    assert dispatcher.resume(session_id).accepted
    assert provider.entered.wait(2)
    assert dispatcher.get(session_id).state is SessionState.PENDING
    assert dispatcher.cancel(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.CANCELING)
    probe = dispatcher.submit("probe", b"probe")
    wait_for(dispatcher, probe, SessionState.COMPLETED)

    assert probe_entered.is_set()
    assert settled == []
    assert not resumed_invocation.is_set()
    with dispatcher._condition:
        key = dispatcher._current_workers[session_id]
        assert dispatcher._reserved[resource] == key
        assert sum(
            worker_key.session_id == session_id
            for worker_key in dispatcher._workers
        ) == 1

    provider.release.set()
    canceled = wait_for(dispatcher, session_id, SessionState.CANCELED)
    shutdown = dispatcher.shutdown()
    terminals = []
    while True:
        try:
            envelope = stream.next(0.05)
        except (TimeoutError, StopIteration):
            break
        if isinstance(envelope.body, Terminal):
            terminals.append(envelope.body)

    assert shutdown.complete
    assert canceled.result is not None
    assert canceled.result.disposition is Disposition.RAN
    assert settled == [(b"continued", Disposition.RAN)]
    assert not resumed_invocation.is_set()
    assert len(terminals) == 1


def test_stale_generation_cleanup_cannot_touch_successor() -> None:
    class TrackingLease:
        def __init__(self) -> None:
            self.acquired_thread = get_ident()
            self.released_thread = None
            self.release_count = 0

        def release(self) -> None:
            self.released_thread = get_ident()
            self.release_count += 1

    class TrackingProvider:
        def __init__(self) -> None:
            self.leases = []

        def acquire(self, resources, canceled):
            if canceled():
                raise Canceled()
            lease = TrackingLease()
            self.leases.append(lease)
            return lease

    provider = TrackingProvider()
    first_entered = Event()
    second_entered = Event()
    release_second = Event()
    resource = ResourceId("volume", "stale-cleanup")

    def run_for(payload):
        if payload == b"initial":
            def pauseable(context):
                first_entered.set()
                while True:
                    context.checkpoint()
                    sleep(0.005)

            return pauseable

        def hold(context):
            second_entered.set()
            assert release_second.wait(2)
            return OperationResult(SessionState.COMPLETED)

        return hold

    dispatcher = Dispatcher(
        {
            "pausable": registration(
                run_for,
                supports_pause=True,
                resources=(resource,),
            )
        },
        lock_provider=provider,
    )
    session_id = dispatcher.submit("pausable", b"initial")
    assert first_entered.wait(2)
    with dispatcher._condition:
        old_key = dispatcher._current_workers[session_id]
    assert dispatcher.pause(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.PAUSED)
    deadline = monotonic() + 2
    while monotonic() < deadline:
        with dispatcher._condition:
            if session_id not in dispatcher._current_workers:
                break
        sleep(0.005)
    else:
        raise AssertionError("paused worker did not retire")

    assert dispatcher.resume(session_id).accepted
    assert second_entered.wait(2)
    with dispatcher._condition:
        new_key = dispatcher._current_workers[session_id]
        new_lease = dispatcher._leases[new_key]
    assert new_key != old_key

    dispatcher._release_custody(old_key, (resource,))
    dispatcher._worker_done(old_key)
    with dispatcher._condition:
        assert dispatcher._current_workers[session_id] == new_key
        assert dispatcher._leases[new_key] is new_lease
        assert dispatcher._reserved[resource] == new_key
    assert new_lease.release_count == 0

    release_second.set()
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert dispatcher.shutdown().complete
    assert len(provider.leases) == 2
    for lease in provider.leases:
        assert lease.release_count == 1
        assert lease.released_thread == lease.acquired_thread


def test_queued_cancel_is_unrun_and_terminal_record_survives_until_close() -> None:
    release = Event()
    first_started = Event()

    def run_for(payload):
        if payload == b"first":
            def hold(context):
                first_started.set()
                release.wait(2)
                return OperationResult(SessionState.COMPLETED)
            return hold
        return completed

    resource = ResourceId("volume", "shared")
    canceled_settlements: list[bytes] = []
    dispatcher = Dispatcher(
        {
            "hold": registration(
                run_for,
                resources=(resource,),
                settle_canceled=lambda payload, disposition: (
                    canceled_settlements.append(payload)
                    or OperationResult(
                        SessionState.CANCELED,
                        disposition=disposition,
                        canceled=True,
                    )
                ),
            )
        },
        lock_provider=InProcessResourceLockProvider(),
    )
    first = dispatcher.submit("hold", b"first")
    second = dispatcher.submit("hold", b"second")
    assert first_started.wait(2)
    assert dispatcher.cancel(second).accepted
    record = wait_for(dispatcher, second, SessionState.CANCELED)
    assert record.result is not None
    assert record.result.disposition is Disposition.UNRUN
    assert canceled_settlements == []
    with pytest.raises(SessionNotTerminal):
        dispatcher.close(first)
    dispatcher.close(second)
    assert all(item.session_id != second for item in dispatcher.list())
    release.set()
    wait_for(dispatcher, first, SessionState.COMPLETED)
    assert dispatcher.shutdown().complete


def test_subscribe_and_terminal_close_cannot_leave_an_orphan_stream(
    monkeypatch,
) -> None:
    dispatcher = Dispatcher({"short": registration(lambda payload: completed)})
    session_id = dispatcher.submit("short", b"payload")
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    hub = dispatcher._hubs[session_id]
    original_subscribe = hub.subscribe
    subscribe_entered = Event()
    release_subscribe = Event()
    close_done = Event()
    streams = []
    failures = []

    def blocking_subscribe(from_seq=None):
        subscribe_entered.set()
        assert release_subscribe.wait(2)
        return original_subscribe(from_seq)

    def subscribe():
        try:
            streams.append(dispatcher.subscribe(session_id))
        except BaseException as error:
            failures.append(error)

    def close():
        try:
            dispatcher.close(session_id)
        finally:
            close_done.set()

    monkeypatch.setattr(hub, "subscribe", blocking_subscribe)
    subscribe_thread = Thread(target=subscribe)
    close_thread = Thread(target=close)
    subscribe_thread.start()
    assert subscribe_entered.wait(2)
    close_thread.start()
    try:
        assert not close_done.wait(0.1)
    finally:
        release_subscribe.set()
        subscribe_thread.join(2)
        close_thread.join(2)

    assert not subscribe_thread.is_alive()
    assert not close_thread.is_alive()
    assert failures == []
    assert len(streams) == 1
    stream = streams[0]
    while True:
        try:
            stream.next(0)
        except StopIteration:
            break
    assert dispatcher.shutdown().complete


def test_terminal_close_retains_ownership_until_audit_cleanup_finishes() -> None:
    close_entered = Event()
    release_close = Event()
    close_count = 0

    class BlockingCloseObserver:
        def on_event(self, envelope) -> RecordingStatus:
            return RecordingStatus.OK

        def flush(self):
            pass

        def finalize(self, result):
            pass

        def close(self):
            nonlocal close_count
            close_count += 1
            close_entered.set()
            assert release_close.wait(2)

    store = InMemorySessionStore()
    dispatcher = Dispatcher(
        {"short": registration(lambda payload: completed)},
        store=store,
        audit_observer_factory=lambda record: BlockingCloseObserver(),
        audit_timeout=0.05,
    )
    session_id = dispatcher.submit("short", b"payload")
    retained = wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert close_entered.wait(2)

    try:
        with pytest.raises(
            TimeoutError,
            match="terminal settlement is complete; subscriptions are closed and only cleanup remains pending",
        ):
            dispatcher.close(session_id)

        assert dispatcher.get(session_id) is retained
        assert session_id in dispatcher._hubs
        assert session_id in dispatcher._controls
        assert session_id in dispatcher._state_publication_locks
        assert [record.session_id for record in store.snapshot()] == [session_id]
        with pytest.raises(
            SessionCleanupPending,
            match="terminal settlement is complete; only cleanup remains pending",
        ):
            dispatcher.subscribe(session_id)
    finally:
        release_close.set()

    assert dispatcher._hubs[session_id]._audit._closed.wait(2)
    hub = dispatcher._hubs[session_id]
    assert hub._reserve_publication(0.1)
    try:
        with pytest.raises(
            TimeoutError,
            match="terminal settlement is complete; subscriptions are closed and only cleanup remains pending",
        ):
            dispatcher.close(session_id)
        with pytest.raises(SessionCleanupPending):
            dispatcher.subscribe(session_id)
    finally:
        hub._release_publication()
    dispatcher.close(session_id)
    with pytest.raises(SessionNotFound):
        dispatcher.get(session_id)
    assert store.snapshot() == ()
    assert close_count == 1
    assert dispatcher.shutdown().complete


def test_terminal_close_publication_timeout_reopens_subscriptions() -> None:
    dispatcher = Dispatcher(
        {"short": registration(lambda payload: completed)},
        audit_timeout=0.05,
    )
    session_id = dispatcher.submit("short", b"payload")
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    hub = dispatcher._hubs[session_id]
    assert hub._reserve_publication(0.1)
    try:
        with pytest.raises(
            TimeoutError,
            match="terminal settlement is complete; event publication did not quiesce",
        ):
            dispatcher.close(session_id)
        assert session_id not in dispatcher._closing
    finally:
        hub._release_publication()

    stream = dispatcher.subscribe(session_id)
    stream.close()
    dispatcher.close(session_id)
    assert dispatcher.shutdown().complete


def test_subscribe_waits_for_a_tentative_close_to_release_its_claim() -> None:
    dispatcher = Dispatcher(
        {"short": registration(lambda payload: completed)},
        audit_timeout=0.1,
    )
    session_id = dispatcher.submit("short", b"payload")
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    hub = dispatcher._hubs[session_id]
    assert hub._reserve_publication(0.1)
    close_done = Event()
    subscribe_done = Event()
    close_errors: list[BaseException] = []
    subscribe_errors: list[BaseException] = []
    streams = []

    def close_session() -> None:
        try:
            dispatcher.close(session_id)
        except BaseException as error:
            close_errors.append(error)
        finally:
            close_done.set()

    def subscribe() -> None:
        try:
            streams.append(dispatcher.subscribe(session_id))
        except BaseException as error:
            subscribe_errors.append(error)
        finally:
            subscribe_done.set()

    close_thread = Thread(target=close_session)
    close_thread.start()
    subscribe_thread = Thread(target=subscribe)
    subscribe_started = False
    try:
        deadline = monotonic() + 1
        while session_id not in dispatcher._closing and monotonic() < deadline:
            sleep(0.001)
        assert session_id in dispatcher._closing

        subscribe_thread.start()
        subscribe_started = True
        assert not subscribe_done.wait(0.05)
        assert close_done.wait(1)
        assert len(close_errors) == 1
        assert isinstance(close_errors[0], TimeoutError)
        assert session_id not in dispatcher._closing
        assert not subscribe_done.is_set()
    finally:
        hub._release_publication()
        if subscribe_started:
            subscribe_thread.join(2)
        close_thread.join(2)

    assert not subscribe_thread.is_alive()
    assert not close_thread.is_alive()
    assert subscribe_errors == []
    assert len(streams) == 1
    streams[0].close()

    dispatcher.close(session_id)
    assert dispatcher.shutdown().complete


def test_publication_timeout_preserves_an_orderly_shutdown_close_claim() -> None:
    dispatcher = Dispatcher(
        {"short": registration(lambda payload: completed)},
        audit_timeout=0.05,
    )
    session_id = dispatcher.submit("short", b"payload")
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    hub = dispatcher._hubs[session_id]
    assert hub._reserve_publication(0.1)
    with dispatcher._condition:
        dispatcher._accepting = False
        dispatcher._condition.notify_all()
    try:
        with pytest.raises(TimeoutError, match="cleanup did not start"):
            dispatcher.close(session_id)
        assert session_id in dispatcher._closing
        with pytest.raises(SessionCleanupPending):
            dispatcher.subscribe(session_id)
    finally:
        hub._release_publication()

    assert dispatcher.shutdown(timeout=2).complete


def test_terminal_close_store_failure_stays_cleanup_pending_for_retry() -> None:
    class FailOnceDropStore(InMemorySessionStore):
        def __init__(self) -> None:
            super().__init__()
            self.failed = False

        def drop(self, session_id):
            if not self.failed:
                self.failed = True
                raise RuntimeError("store drop failed")
            super().drop(session_id)

    store = FailOnceDropStore()
    dispatcher = Dispatcher(
        {"short": registration(lambda payload: completed)},
        store=store,
    )
    session_id = dispatcher.submit("short", b"payload")
    wait_for(dispatcher, session_id, SessionState.COMPLETED)

    with pytest.raises(RuntimeError, match="store drop failed"):
        dispatcher.close(session_id)
    with pytest.raises(
        SessionCleanupPending,
        match="terminal settlement is complete; only cleanup remains pending",
    ):
        dispatcher.subscribe(session_id)

    dispatcher.close(session_id)
    assert store.snapshot() == ()
    assert dispatcher.shutdown().complete


def test_subscribe_rejects_immediately_while_detached_store_drop_blocks() -> None:
    drop_entered = Event()
    release_drop = Event()

    class BlockingDropStore(InMemorySessionStore):
        def drop(self, session_id):
            drop_entered.set()
            assert release_drop.wait(2)
            super().drop(session_id)

    dispatcher = Dispatcher(
        {"short": registration(lambda payload: completed)},
        store=BlockingDropStore(),
    )
    session_id = dispatcher.submit("short", b"payload")
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    hub = dispatcher._hubs[session_id]
    assert hub._reserve_publication(0.1)
    hub_reserved = True
    close_errors: list[BaseException] = []
    subscribe_errors: list[BaseException] = []
    subscribe_done = Event()

    def close_session() -> None:
        try:
            dispatcher.close(session_id)
        except BaseException as error:
            close_errors.append(error)

    def subscribe() -> None:
        try:
            dispatcher.subscribe(session_id)
        except BaseException as error:
            subscribe_errors.append(error)
        finally:
            subscribe_done.set()

    close_thread = Thread(target=close_session)
    subscribe_thread = Thread(target=subscribe)
    subscribe_started = False
    close_thread.start()
    try:
        deadline = monotonic() + 1
        while session_id not in dispatcher._closing and monotonic() < deadline:
            sleep(0.001)
        assert session_id in dispatcher._closing

        subscribe_thread.start()
        subscribe_started = True
        assert not subscribe_done.wait(0.05)
        hub._release_publication()
        hub_reserved = False
        assert drop_entered.wait(2)
        assert hub.detached
        assert subscribe_done.wait(0.5)
        assert len(subscribe_errors) == 1
        assert isinstance(subscribe_errors[0], SessionCleanupPending)
    finally:
        if hub_reserved:
            hub._release_publication()
        release_drop.set()
        if subscribe_started:
            subscribe_thread.join(2)
        close_thread.join(2)

    assert not subscribe_thread.is_alive()
    assert not close_thread.is_alive()
    assert close_errors == []
    with pytest.raises(SessionNotFound):
        dispatcher.get(session_id)
    assert dispatcher.shutdown().complete


def test_concurrent_terminal_close_and_shutdown_share_cleanup_ownership() -> None:
    drop_entered = Event()
    release_drop = Event()

    class BlockingDropStore(InMemorySessionStore):
        def drop(self, session_id):
            drop_entered.set()
            assert release_drop.wait(2)
            super().drop(session_id)

    store = BlockingDropStore()
    dispatcher = Dispatcher(
        {"short": registration(lambda payload: completed)},
        store=store,
    )
    session_id = dispatcher.submit("short", b"payload")
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    close_errors = []
    shutdown_errors = []
    shutdown_results = []
    shutdown_done = Event()

    def close_session() -> None:
        try:
            dispatcher.close(session_id)
        except BaseException as error:
            close_errors.append(error)

    def shutdown() -> None:
        try:
            shutdown_results.append(dispatcher.shutdown(timeout=1.0))
        except BaseException as error:
            shutdown_errors.append(error)
        finally:
            shutdown_done.set()

    close_thread = Thread(target=close_session)
    shutdown_thread = Thread(target=shutdown)
    close_thread.start()
    assert drop_entered.wait(2)
    shutdown_thread.start()
    try:
        assert not shutdown_done.wait(0.05)
    finally:
        release_drop.set()
    close_thread.join(2)
    shutdown_thread.join(2)

    assert not close_thread.is_alive()
    assert not shutdown_thread.is_alive()
    assert close_errors == []
    assert shutdown_errors == []
    assert len(shutdown_results) == 1
    assert shutdown_results[0].complete
    assert dispatcher.list() == ()
    assert store.snapshot() == ()


def test_control_rejections_do_not_change_state() -> None:
    release = Event()
    entered = Event()

    def run(context):
        entered.set()
        release.wait(2)
        return OperationResult(SessionState.COMPLETED)

    dispatcher = Dispatcher({"short": registration(lambda payload: run)})
    session_id = dispatcher.submit("short", b"payload")
    assert entered.wait(2)
    result = dispatcher.pause(session_id)
    assert result.code is ControlCode.UNSUPPORTED
    assert dispatcher.get(session_id).state is SessionState.RUNNING
    assert dispatcher.resume(session_id).code is ControlCode.ILLEGAL_STATE
    assert dispatcher.get(session_id).state is SessionState.RUNNING
    release.set()
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert dispatcher.cancel(session_id).code is ControlCode.ILLEGAL_STATE
    assert dispatcher.shutdown().complete


def test_control_matrix_is_exhaustive_and_state_preserving_on_rejection() -> None:
    for state in SessionState:
        for supports_pause in (False, True):
            pause = control_decision(ControlAction.PAUSE, state, supports_pause)
            expected_pause = (
                ControlCode.UNSUPPORTED
                if not supports_pause
                else (
                    ControlCode.ACCEPTED
                    if state is SessionState.RUNNING
                    else ControlCode.ILLEGAL_STATE
                )
            )
            assert pause is expected_pause
            resume = control_decision(ControlAction.RESUME, state, supports_pause)
            assert (resume is ControlCode.ACCEPTED) == (
                state in (SessionState.PAUSED, SessionState.INTERRUPTED)
            )
            cancel = control_decision(ControlAction.CANCEL, state, supports_pause)
            assert (cancel is ControlCode.ACCEPTED) == (
                state not in (
                    SessionState.COMPLETED,
                    SessionState.FAILED,
                    SessionState.CANCELED,
                    SessionState.REFUSED,
                    SessionState.CANCELING,
                )
            )


def test_payload_is_passed_to_adapter_without_dispatcher_decoding() -> None:
    opaque = b"\x80not-a-valid-domain-encoding\x00"
    opened: list[bytes] = []

    def open_payload(payload):
        opened.append(payload)
        return Invocation(completed)

    registration_value = WorkflowRegistration(
        prepare=lambda request: PreparedSession(request),
        open=open_payload,
    )
    dispatcher = Dispatcher({"opaque": registration_value})
    session_id = dispatcher.submit("opaque", opaque)
    record = wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert record.payload is None
    assert opened == [opaque]
    assert dispatcher.shutdown().complete


def test_in_memory_store_is_honest_about_absent_restart_state() -> None:
    store = InMemorySessionStore()
    dispatcher = Dispatcher({"opaque": registration(lambda payload: completed)}, store=store)
    session_id = dispatcher.submit("opaque", b"payload")
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert type(store.snapshot()[0]) is StoredSessionRecord
    assert not hasattr(store.snapshot()[0], "payload")
    assert store.load_all() == ()
    assert dispatcher.shutdown().complete


def test_later_store_failure_does_not_leak_custody_or_duplicate_terminal() -> None:
    class FailingStore(InMemorySessionStore):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def put(self, record):
            self.calls += 1
            if self.calls > 1:
                raise OSError("store unavailable")
            super().put(record)

    dispatcher = Dispatcher(
        {
            "stored": registration(
                lambda payload: completed,
                resources=(ResourceId("volume", "store-fault"),),
            )
        },
        store=FailingStore(),
    )
    session_id = dispatcher.submit("stored", b"payload")
    stream = dispatcher.subscribe(session_id)
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    terminals = []
    while True:
        try:
            event = stream.next(0.05)
        except (TimeoutError, StopIteration):
            break
        if isinstance(event.body, Terminal):
            terminals.append(event.body)
    assert len(terminals) == 1
    assert dispatcher.shutdown().custody_released


@pytest.mark.parametrize("failure_owner", ("store", "custody"))
def test_contained_failure_does_not_retain_exception_owned_graph_after_close(
    failure_owner: str,
) -> None:
    class PrivateGraph:
        pass

    retained = []

    def fail() -> None:
        graph = PrivateGraph()
        retained.append(ref(graph))
        error = OSError("contained dependency failure")
        error.private_graph = graph
        raise error

    class FailingStore(InMemorySessionStore):
        def put(self, record):
            if failure_owner == "store" and record.state is not SessionState.PENDING:
                fail()
            super().put(record)

    class LockProvider:
        def __init__(self):
            self.delegate = InProcessResourceLockProvider()

        def acquire(self, resources, canceled):
            lease = self.delegate.acquire(resources, canceled)

            class Lease:
                def release(self):
                    lease.release()
                    if failure_owner == "custody":
                        fail()

            return Lease()

    dispatcher = Dispatcher(
        {"stored": registration(lambda _payload: completed)},
        store=FailingStore(),
        lock_provider=LockProvider(),
    )
    try:
        for _ in range(3):
            session_id = dispatcher.submit("stored", b"private continuation")
            wait_for(dispatcher, session_id, SessionState.COMPLETED)
            dispatcher.close(session_id)
    finally:
        assert dispatcher.shutdown().complete

    assert retained
    gc.collect()
    assert all(graph() is None for graph in retained)


def test_failed_terminal_store_write_does_not_retain_workflow_payload() -> None:
    class FailingStore(InMemorySessionStore):
        def __init__(self):
            super().__init__()
            self.attempted = []

        def put(self, record):
            self.attempted.append(record)
            if len(self.attempted) > 1:
                raise OSError("store unavailable")
            super().put(record)

    store = FailingStore()
    dispatcher = Dispatcher(
        {
            "stored": registration(
                lambda payload: completed,
                resources=(ResourceId("volume", "store-payload"),),
            )
        },
        store=store,
        lock_provider=InProcessResourceLockProvider(),
    )
    try:
        session_id = dispatcher.submit("stored", b"private workflow continuation")
        stream = dispatcher.subscribe(session_id)
        record = wait_for(dispatcher, session_id, SessionState.COMPLETED)
        terminals = []
        while True:
            try:
                event = stream.next(0.05)
            except (TimeoutError, StopIteration):
                break
            if isinstance(event.body, Terminal):
                terminals.append(event.body)
        assert len(terminals) == 1
    finally:
        shutdown = dispatcher.shutdown()

    assert shutdown.complete
    assert shutdown.custody_released
    assert record.payload is None
    assert len(store.attempted) > 1
    (retained,) = store.snapshot()
    assert retained is store.attempted[0]
    assert retained.session_id == session_id
    assert retained.state is SessionState.PENDING
    assert getattr(retained, "payload", None) is None
    assert all(getattr(attempt, "payload", None) is None for attempt in store.attempted)
    assert all(type(attempt) is StoredSessionRecord for attempt in store.attempted)


@pytest.mark.parametrize("final_action", ["resume", "cancel"])
@pytest.mark.parametrize("filesystem_status", [SessionState.COMPLETED, SessionState.FAILED])
def test_store_failures_keep_latest_successive_pause_for_resume_or_cancel(
    final_action: str, filesystem_status: SessionState
) -> None:
    class FailingStore(RecordingSessionStore):
        def put(self, record):
            if self.attempted:
                self.attempted.append(record)
                raise OSError("store unavailable")
            super().put(record)

    store = FailingStore()
    entered = (Event(), Event())
    opened: list[bytes] = []
    settled: list[tuple[bytes, Disposition]] = []
    earned = (
        ItemOutcome("1" * 32, "copy", "first.bin", Outcome.SUCCEEDED),
        ItemOutcome("2" * 32, "copy", "second.bin", Outcome.SUCCEEDED),
    )
    execute_status = (
        PhaseStatus.COMPLETED
        if filesystem_status is SessionState.COMPLETED
        else PhaseStatus.FAILED
    )
    result = OperationResult(
        filesystem_status,
        canceled=final_action == "cancel",
        phases=(
            PhaseResult("execute", execute_status, 2, 2, 7, 7),
            PhaseResult(
                "verify",
                PhaseStatus.CANCELED if final_action == "cancel" else PhaseStatus.COMPLETED,
                0 if final_action == "cancel" else 2, 2,
                0 if final_action == "cancel" else 7, 7,
            ),
        ),
        bytes_done=7,
        bytes_total=7,
    )

    def open_payload(payload):
        opened.append(payload)
        if payload == b"pause-2":
            return Invocation(lambda context: result)
        attempt = {b"initial": 0, b"pause-1": 1}[payload]

        def pauseable(context):
            context.emit(earned[attempt])
            entered[attempt].set()
            while True:
                context.checkpoint()
                sleep(0.005)

        return Invocation(pauseable, (b"pause-1", b"pause-2")[attempt])

    def settle_canceled(payload, disposition):
        settled.append((payload, disposition))
        return result

    resource = ResourceId("volume", "successive-pause")
    dispatcher = Dispatcher(
        {
            "pausable": WorkflowRegistration(
                prepare=lambda request: PreparedSession(request, frozenset({resource})),
                open=open_payload,
                supports_pause=True,
                settle_canceled=settle_canceled,
            )
        },
        store=store,
        lock_provider=InProcessResourceLockProvider(),
    )
    try:
        session_id = dispatcher.submit("pausable", b"initial")
        stream = dispatcher.subscribe(session_id)
        for attempt, snapshot in enumerate((b"pause-1", b"pause-2")):
            assert entered[attempt].wait(2)
            assert dispatcher.pause(session_id).accepted
            paused = wait_for(dispatcher, session_id, SessionState.PAUSED)
            assert paused.payload == snapshot
            assert dispatcher._leases == {}
            assert dispatcher._reserved == {}
            assert store.snapshot()[0].state is SessionState.PENDING
            if attempt == 0:
                assert dispatcher.resume(session_id).accepted

        if final_action == "resume":
            assert dispatcher.resume(session_id).accepted
            terminal_state = filesystem_status
        else:
            assert dispatcher.cancel(session_id).accepted
            terminal_state = SessionState.CANCELED
        terminal = wait_for(dispatcher, session_id, terminal_state)
        terminals = []
        while True:
            try:
                envelope = stream.next(0.05)
            except (TimeoutError, StopIteration):
                break
            if isinstance(envelope.body, Terminal):
                terminals.append(envelope.body)
        assert len(terminals) == 1
        assert terminal.result is not None
        assert terminals[0].result == TerminalSummary.from_result(terminal.result)
    finally:
        shutdown = dispatcher.shutdown()

    assert shutdown.complete
    assert shutdown.custody_released
    assert opened == (
        [b"initial", b"pause-1", b"pause-2"]
        if final_action == "resume" else [b"initial", b"pause-1"]
    )
    assert settled == ([(b"pause-2", Disposition.RAN)] if final_action == "cancel" else [])
    assert terminal.payload is None
    assert terminal.result.status is filesystem_status
    assert terminal.result.canceled is (final_action == "cancel")
    assert terminal.result.disposition is Disposition.RAN
    assert terminal.result.items == earned
    assert terminal.result.phases is result.phases
    assert terminal.result.bytes_done == terminal.result.bytes_total == 7
    assert sum(row.state is SessionState.PAUSED for row in store.attempted) == 2
    assert all(type(row) is StoredSessionRecord for row in store.attempted)
    assert all(not hasattr(row, "payload") for row in store.attempted)
    assert store.snapshot() == (store.attempted[0],)
    assert store.snapshot()[0].result is None
    assert_stored_record_matches(store.attempted[-1], terminal)


@pytest.mark.parametrize("filesystem_status", [SessionState.COMPLETED, SessionState.FAILED])
def test_stored_record_preserves_full_compound_result_axes_and_identity(
    filesystem_status: SessionState,
) -> None:
    store = RecordingSessionStore()
    item = ItemOutcome(
        "3" * 32, "copy", "file.bin", Outcome.SUCCEEDED,
        recording=RecordingStatus.DEGRADED,
        recording_reason=ItemRecordingReason.RECORD_WRITE_FAILED,
        detail_omitted_count=2,
    )
    issues = (TaskRecordingIssue(TaskRecordingIssueReason.FINAL_FLUSH_FAILED, "flush"),)
    error = (
        FailureDetail("OSError", "execution failed")
        if filesystem_status is SessionState.FAILED else None
    )
    phases = (
        PhaseResult(
            "execute",
            PhaseStatus.FAILED if error is not None else PhaseStatus.COMPLETED,
            1, 1, 7, 7,
            error="execution failed" if error is not None else None,
        ),
        PhaseResult("verify", PhaseStatus.CANCELED, 0, 1, 0, 7),
    )

    def run(context):
        context.emit(item)
        return OperationResult(
            filesystem_status,
            canceled=True,
            phases=phases,
            bytes_done=7,
            bytes_total=7,
            error=error,
            recording_issues=issues,
            omitted_detail_count=3,
        )

    class DegradedAudit:
        def on_event(self, envelope):
            return RecordingStatus.OK

        def flush(self):
            pass

        def finalize(self, result):
            return RecordingStatus.DEGRADED

        def close(self):
            pass

    dispatcher = Dispatcher(
        {"compound": registration(lambda payload: run, supports_pause=True)},
        store=store,
        audit_observer_factory=lambda record: DegradedAudit(),
    )
    try:
        session_id = dispatcher.submit("compound", b"private continuation")
        terminal = wait_for(dispatcher, session_id, SessionState.CANCELED)
        stored = store.snapshot()[0]
    finally:
        shutdown = dispatcher.shutdown()

    assert shutdown.complete
    assert_stored_record_matches(stored, terminal)
    result = stored.result
    assert result == OperationResult(
        filesystem_status,
        recording=RecordingStatus.DEGRADED,
        audit=RecordingStatus.DEGRADED,
        disposition=Disposition.RAN,
        canceled=True,
        items=(item,),
        phases=phases,
        bytes_done=7,
        bytes_total=7,
        error=error,
        recording_issues=issues,
        omitted_detail_count=3,
        review_fact_limit=None,
    )
    assert result.items[0] is item
    assert result.phases is phases
    assert result.error is error
    assert result.recording_issues is issues
    assert all(type(row) is StoredSessionRecord for row in store.attempted)
    assert all(not hasattr(row, "payload") for row in store.attempted)


def test_stored_record_preserves_review_limit_refusal_witness_and_identity() -> None:
    store = RecordingSessionStore()
    witness = ReviewFactLimitExceeded.plan_logical_bytes()

    def refuse(context):
        return OperationResult(
            SessionState.REFUSED,
            disposition=Disposition.UNRUN,
            review_fact_limit=witness,
        )

    dispatcher = Dispatcher(
        {"bounded": registration(lambda payload: refuse)},
        store=store,
    )
    try:
        session_id = dispatcher.submit("bounded", b"private continuation")
        terminal = wait_for(dispatcher, session_id, SessionState.REFUSED)
    finally:
        shutdown = dispatcher.shutdown()

    assert shutdown.complete
    assert_stored_record_matches(store.snapshot()[0], terminal)
    result = terminal.result
    assert result == OperationResult(
        SessionState.REFUSED,
        disposition=Disposition.UNRUN,
        review_fact_limit=witness,
    )
    assert result.review_fact_limit is witness
    assert all(type(row) is StoredSessionRecord for row in store.attempted)
    assert all(not hasattr(row, "payload") for row in store.attempted)


def test_lock_acquisition_failure_is_failed_unrun_terminal() -> None:
    class BrokenLocks:
        def acquire(self, resources, canceled):
            raise OSError("lock unavailable")

    dispatcher = Dispatcher(
        {
            "locked": registration(
                lambda payload: completed,
                resources=(ResourceId("volume", "broken"),),
            )
        },
        lock_provider=BrokenLocks(),
    )
    session_id = dispatcher.submit("locked", b"payload")
    record = wait_for(dispatcher, session_id, SessionState.FAILED)
    assert record.result is not None
    assert record.result.disposition is Disposition.UNRUN
    assert record.result.error is not None
    assert record.result.error.type_name == "OSError"
    assert dispatcher.shutdown().custody_released


@pytest.mark.parametrize(
    ("failure_stage", "hostile_diagnostic"),
    (
        ("acquire", False),
        ("open", False),
        ("settle", False),
        ("acquire", True),
    ),
)
def test_pre_run_failure_retires_raw_graph_before_terminal_store(
    failure_stage: str,
    hostile_diagnostic: bool,
) -> None:
    class PrivateGraph:
        pass

    retained = []
    raw_errors = []
    retirement = []
    collected = []

    class DiagnosticFailure(Exception):
        pass

    class CauseFailure(Exception):
        pass

    class RawFailure(Exception):
        def __str__(self) -> str:
            if not hostile_diagnostic:
                return "fixed public detail"
            graph = PrivateGraph()
            error = DiagnosticFailure("diagnostic rendering failed")
            error.private_graph = graph
            retained.extend((ref(error), ref(graph)))
            raise error

    def fail() -> None:
        graph = PrivateGraph()
        cause = CauseFailure("private cause")
        error = RawFailure()
        error.private_graph = graph
        raw_errors.append(error)
        retained.extend((ref(error), ref(graph), ref(cause)))
        try:
            raise LookupError("private context")
        except LookupError:
            raise error from cause

    class WitnessStore(InMemorySessionStore):
        def put(self, record):
            if record.state is SessionState.FAILED:
                error = raw_errors.pop()
                retirement.append(
                    (
                        error.__traceback__ is None,
                        error.__cause__ is None,
                        error.__context__ is None,
                    )
                )
                del error
                gc.collect()
                collected.append(all(owner() is None for owner in retained))
            super().put(record)

    class LockProvider:
        def __init__(self) -> None:
            self._delegate = InProcessResourceLockProvider()

        def acquire(self, resources, canceled):
            if failure_stage == "acquire":
                fail()
            return self._delegate.acquire(resources, canceled)

    entered = Event()

    def run(context):
        if failure_stage != "settle":
            return OperationResult(SessionState.COMPLETED)
        entered.set()
        while True:
            context.checkpoint()
            sleep(0.005)

    def open_invocation(payload):
        if failure_stage == "open":
            fail()
        return Invocation(run)

    def settle_canceled(payload, disposition):
        del payload, disposition
        if failure_stage == "settle":
            fail()
        return None

    dispatcher = Dispatcher(
        {
            "broken": WorkflowRegistration(
                prepare=lambda request: PreparedSession(
                    b"opaque",
                    frozenset({ResourceId("volume", "raw-pre-run-failure")}),
                ),
                open=open_invocation,
                supports_pause=failure_stage == "settle",
                settle_canceled=settle_canceled,
            )
        },
        store=WitnessStore(),
        lock_provider=LockProvider(),
    )
    session_id = dispatcher.submit("broken", object())
    if failure_stage == "settle":
        assert entered.wait(2)
        assert dispatcher.pause(session_id).accepted
        wait_for(dispatcher, session_id, SessionState.PAUSED)
        assert dispatcher.cancel(session_id).accepted
    record = wait_for(dispatcher, session_id, SessionState.FAILED)

    assert retirement == [(True, True, True)]
    assert collected == [True]
    assert record.result is not None
    assert record.result.disposition is (
        Disposition.RAN if failure_stage == "settle" else Disposition.UNRUN
    )
    if hostile_diagnostic:
        assert record.result.error is None
        assert record.result.omitted_detail_count == 1
    else:
        assert record.result.error == FailureDetail(
            "RawFailure", "fixed public detail"
        )
    assert dispatcher.shutdown().complete


@pytest.mark.parametrize("failure_stage", ("acquire", "open"))
def test_pre_run_process_fatal_is_not_normalized_and_retries(
    monkeypatch,
    failure_stage: str,
) -> None:
    class WorkerExit(BaseException):
        pass

    fatal = WorkerExit("stop worker")
    fault_calls = 0
    fatal_seen = Event()
    hook_values = []

    def fail_once() -> None:
        nonlocal fault_calls
        fault_calls += 1
        if fault_calls == 1:
            raise fatal

    class LockProvider:
        def __init__(self) -> None:
            self._delegate = InProcessResourceLockProvider()

        def acquire(self, resources, canceled):
            if failure_stage == "acquire":
                fail_once()
            return self._delegate.acquire(resources, canceled)

    def open_invocation(payload):
        if failure_stage == "open":
            fail_once()
        return Invocation(completed)

    def exception_hook(args) -> None:
        hook_values.append((args.exc_type, args.exc_value))
        fatal_seen.set()

    monkeypatch.setattr(threading, "excepthook", exception_hook)
    dispatcher = Dispatcher(
        {
            "work": WorkflowRegistration(
                prepare=lambda request: PreparedSession(
                    b"opaque",
                    frozenset({ResourceId("volume", "fatal-pre-run-failure")}),
                ),
                open=open_invocation,
            )
        },
        lock_provider=LockProvider(),
    )
    session_id = dispatcher.submit("work", object())

    assert fatal_seen.wait(2)
    record = wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert hook_values == [(WorkerExit, fatal)]
    assert fault_calls == 2
    assert record.result is not None
    assert record.result.error is None
    assert dispatcher.shutdown().complete


def test_workflow_exception_is_contained_as_one_failed_terminal() -> None:
    def broken(context):
        raise RuntimeError("broken")

    dispatcher = Dispatcher({"broken": registration(lambda payload: broken)})
    session_id = dispatcher.submit("broken", b"payload")
    stream = dispatcher.subscribe(session_id)
    record = wait_for(dispatcher, session_id, SessionState.FAILED)
    assert record.result is not None
    assert record.result.error is not None
    assert record.result.error.type_name == "RuntimeError"
    terminals = []
    while True:
        try:
            event = stream.next(0.05)
        except (TimeoutError, StopIteration):
            break
        if isinstance(event.body, Terminal):
            terminals.append(event.body)
    assert len(terminals) == 1
    assert dispatcher.shutdown().complete


def test_invocation_open_failure_is_failed_unrun_and_releases() -> None:
    def broken_open(payload):
        raise ValueError("cannot decode")

    dispatcher = Dispatcher(
        {
            "broken": WorkflowRegistration(
                prepare=lambda request: PreparedSession(
                    b"opaque", frozenset({ResourceId("volume", "open-fault")})
                ),
                open=broken_open,
            )
        }
    )
    session_id = dispatcher.submit("broken", object())
    record = wait_for(dispatcher, session_id, SessionState.FAILED)
    assert record.result is not None
    assert record.result.disposition is Disposition.UNRUN
    assert record.result.error is not None
    assert record.result.error.type_name == "ValueError"
    assert dispatcher.shutdown().custody_released


def test_pause_snapshot_failure_becomes_one_failed_terminal_and_releases() -> None:
    entered = Event()

    class BrokenSnapshot(Invocation):
        def snapshot(self) -> bytes:
            raise OSError("snapshot failed")

    def run(context):
        entered.set()
        while True:
            context.checkpoint()
            sleep(0.005)

    value = WorkflowRegistration(
        prepare=lambda request: PreparedSession(
            b"opaque", frozenset({ResourceId("volume", "snapshot-fault")})
        ),
        open=lambda payload: BrokenSnapshot(run),
        supports_pause=True,
    )
    dispatcher = Dispatcher({"pausable": value})
    session_id = dispatcher.submit("pausable", object())
    stream = dispatcher.subscribe(session_id)
    assert entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    record = wait_for(dispatcher, session_id, SessionState.FAILED)
    assert record.result is not None
    assert record.result.error is not None
    assert record.result.error.type_name == "OSError"
    terminals = []
    while True:
        try:
            event = stream.next(0.05)
        except (TimeoutError, StopIteration):
            break
        if isinstance(event.body, Terminal):
            terminals.append(event.body)
    assert len(terminals) == 1
    assert dispatcher.shutdown().custody_released


def test_admission_failures_leave_no_live_session() -> None:
    def broken_prepare(request):
        raise ValueError("invalid request")

    dispatcher = Dispatcher(
        {"broken": WorkflowRegistration(prepare=broken_prepare, open=lambda payload: None)}
    )
    with pytest.raises(ValueError, match="invalid request"):
        dispatcher.submit("broken", object())
    assert dispatcher.list() == ()
    assert dispatcher.shutdown().complete


def test_admission_store_accepts_then_raises_and_failed_drop_keeps_metadata_only() -> None:
    original = OSError("admission write accepted then failed")

    class FailingStore(RecordingSessionStore):
        def __init__(self):
            super().__init__()
            self.allow_drop = False
            self.drop_calls = 0

        def put(self, record):
            super().put(record)
            raise original

        def drop(self, session_id):
            self.drop_calls += 1
            if not self.allow_drop:
                raise OSError("drop unavailable")
            super().drop(session_id)

    store = FailingStore()
    published = []
    finalized: list[OperationResult] = []
    attached = []
    opened = []
    observer_closed = Event()

    class Audit:
        def on_event(self, envelope):
            published.append(envelope.body)
            return RecordingStatus.OK

        def flush(self):
            pass

        def finalize(self, result):
            finalized.append(result)
            return RecordingStatus.OK

        def close(self):
            observer_closed.set()

    def open_payload(payload):
        opened.append(payload)
        return Invocation(completed)

    def attach(session_id, stream):
        attached.append(session_id)
        return stream.close

    dispatcher = Dispatcher(
        {
            "rejected": WorkflowRegistration(
                prepare=lambda request: PreparedSession(
                    request, frozenset({ResourceId("volume", "admission-fault")})
                ),
                open=open_payload,
            )
        },
        store=store,
        lock_provider=InProcessResourceLockProvider(),
        audit_observer_factory=lambda record: Audit(),
    )
    try:
        with pytest.raises(OSError) as caught:
            dispatcher.submit("rejected", b"private continuation", attach=attach)

        assert caught.value is original
        assert len(store.attempted) == 1
        (retained,) = store.snapshot()
        assert retained is store.attempted[0]
        assert type(retained) is StoredSessionRecord
        assert not hasattr(retained, "payload")
        assert retained.state is SessionState.PENDING
        assert retained.result is None
        session_id = retained.session_id
        assert published == attached == opened == []
        assert observer_closed.is_set()
        assert dispatcher.list() == ()
        assert dispatcher._hubs == {}
        assert dispatcher._controls == {}
        assert dispatcher._workers == {}
        assert dispatcher._leases == {}
        assert dispatcher._reserved == {}
        assert not dispatcher._pending
        assert set(dispatcher._admission_cleanups) == {session_id}
        cleanup = dispatcher._admission_cleanups[session_id]

        incomplete = dispatcher.shutdown(timeout=1)

        assert not incomplete.complete
        assert incomplete.custody_released
        assert incomplete.unfinished == (session_id,)
        assert dispatcher._admission_cleanups[session_id] is cleanup
        assert store.snapshot() == (retained,)
        assert store.drop_calls == 2
        assert published == attached == opened == []
    finally:
        store.allow_drop = True
        shutdown = dispatcher.shutdown(timeout=2)

    assert shutdown.complete
    assert shutdown.custody_released
    assert store.snapshot() == ()
    assert dispatcher._admission_cleanups == {}
    assert finalized == []
    assert not dispatcher._scheduler.is_alive()


def test_admission_cleanup_releases_graphs_and_refuses_recursive_submit() -> None:
    class PrivateGraph:
        pass

    completed_owner_refs = []
    failure_refs = []
    recursive_errors: list[tuple[type[BaseException], str]] = []
    reader_done = Event()
    prepare_calls = 0

    class Audit:
        def __init__(self):
            self.graph = PrivateGraph()
            completed_owner_refs.append(ref(self.graph))

        def on_event(self, envelope):
            del envelope
            return RecordingStatus.OK

        def flush(self):
            pass

        def finalize(self, result):
            del result
            return RecordingStatus.OK

        def close(self):
            pass

    class FailingStore(InMemorySessionStore):
        def __init__(self):
            super().__init__()
            self.allow_drop = False

        def drop(self, session_id):
            if not self.allow_drop:
                graph = PrivateGraph()
                failure_refs.append(ref(graph))
                error = OSError("drop unavailable")
                error.private_graph = graph
                raise error
            super().drop(session_id)

    calls = 0

    class FailingClock:
        def now(self):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("pending clock failed")
            return datetime.now(timezone.utc)

    def prepare(request):
        nonlocal prepare_calls
        prepare_calls += 1
        return PreparedSession(request)

    def recursive_submit() -> None:
        try:
            dispatcher.submit("observed", b"must remain unpublished")
        except BaseException as error:
            recursive_errors.append((type(error), str(error)))

    def attach(session_id, stream):
        del session_id
        graph = PrivateGraph()
        completed_owner_refs.append(ref(graph))
        recursive_submit()

        def read() -> None:
            try:
                stream.next()
            except StopIteration:
                pass
            finally:
                reader_done.set()

        thread = Thread(target=read)
        thread.start()

        def rollback() -> None:
            assert graph is not None
            recursive_submit()
            stream.close()
            thread.join(1)
            assert not thread.is_alive()

        return rollback

    store = FailingStore()
    dispatcher = Dispatcher(
        {
            "observed": WorkflowRegistration(
                prepare=prepare,
                open=lambda _payload: Invocation(completed),
            )
        },
        store=store,
        clock=FailingClock(),
        audit_observer_factory=lambda _record: Audit(),
    )
    try:
        with pytest.raises(RuntimeError, match="pending clock failed"):
            dispatcher.submit("observed", b"private continuation", attach=attach)

        assert prepare_calls == 1
        assert len(recursive_errors) == 2
        assert all(
            error_type is SessionCleanupPending
            for error_type, _detail in recursive_errors
        )
        assert all(
            "another admission" in detail
            for _error_type, detail in recursive_errors
        )
        assert len(dispatcher._admission_cleanups) == 1
        (cleanup,) = dispatcher._admission_cleanups.values()
        assert cleanup.failure_seen
        assert cleanup.rollback is None
        assert cleanup.stream is None
        assert cleanup.hub is None
        assert cleanup.store_pending
        assert reader_done.wait(1)

        with pytest.raises(SessionCleanupPending, match="another admission"):
            dispatcher.submit("observed", b"must not be admitted")
        wait_for_admission_cleanup_attempt(dispatcher)
        assert prepare_calls == 1
        gc.collect()
        assert all(graph() is None for graph in completed_owner_refs)
        assert len(failure_refs) == 2
        assert all(graph() is None for graph in failure_refs)
    finally:
        store.allow_drop = True
        assert dispatcher.shutdown().complete


def test_admission_liability_refuses_concurrent_submit_without_waiting() -> None:
    attach_entered = Event()
    release_attach = Event()
    prepare_calls = 0
    submitted: list[SessionId] = []
    errors: list[BaseException] = []

    def prepare(request):
        nonlocal prepare_calls
        prepare_calls += 1
        return PreparedSession(request)

    def attach(session_id, stream):
        del session_id
        attach_entered.set()
        assert release_attach.wait(2)
        return stream.close

    dispatcher = Dispatcher(
        {
            "work": WorkflowRegistration(
                prepare=prepare,
                open=lambda _payload: Invocation(completed),
            )
        }
    )

    def submit() -> None:
        try:
            submitted.append(
                dispatcher.submit("work", b"first", attach=attach)
            )
        except BaseException as error:
            errors.append(error)

    thread = Thread(target=submit)
    thread.start()
    try:
        assert attach_entered.wait(1)
        started = monotonic()
        with pytest.raises(SessionCleanupPending, match="another admission"):
            dispatcher.submit("work", b"second")
        assert monotonic() - started < 0.2
        assert prepare_calls == 1

        release_attach.set()
        thread.join(2)
        assert not thread.is_alive()
        assert errors == []
        assert len(submitted) == 1
        session_id = submitted[0]
        wait_for(dispatcher, session_id, SessionState.COMPLETED)
        dispatcher.close(session_id)
        assert dispatcher._workers == {}
        assert dispatcher._current_workers == {}
        assert dispatcher._retiring_workers == set()
    finally:
        release_attach.set()
        assert dispatcher.shutdown().complete


def test_failed_admission_cleanup_caps_churn_retries_and_releases() -> None:
    class FailingStore(InMemorySessionStore):
        def __init__(self):
            super().__init__()
            self.allow_put = False
            self.allow_drop = False
            self.put_calls = 0
            self.drop_calls = 0

        def put(self, record):
            self.put_calls += 1
            super().put(record)
            if not self.allow_put:
                raise OSError("admission write accepted then failed")

        def drop(self, session_id):
            self.drop_calls += 1
            if not self.allow_drop:
                raise OSError("drop unavailable")
            super().drop(session_id)

    store = FailingStore()
    dispatcher = Dispatcher(
        {"work": registration(lambda _payload: completed)},
        store=store,
    )
    try:
        with pytest.raises(OSError, match="admission write accepted then failed"):
            dispatcher.submit("work", b"first")
        (failed_session_id,) = dispatcher._admission_cleanups

        for _ in range(12):
            with pytest.raises(SessionCleanupPending, match="another admission"):
                dispatcher.submit("work", b"must not be admitted")
            wait_for_admission_cleanup_attempt(dispatcher)

        assert tuple(dispatcher._admission_cleanups) == (failed_session_id,)
        assert store.put_calls == 1
        assert store.drop_calls == 13
        assert len(store.snapshot()) == 1
        assert dispatcher.list() == ()
        assert dispatcher._workers == {}

        with pytest.raises(SessionNotFound):
            dispatcher.close(failed_session_id)

        store.allow_drop = True
        store.allow_put = True
        with pytest.raises(SessionCleanupPending, match="another admission"):
            dispatcher.submit("work", b"cleanup trigger")
        wait_for_admission_cleanup_attempt(dispatcher)
        assert dispatcher._admission_cleanups == {}
        assert not dispatcher._admission_liability_claimed

        session_id = dispatcher.submit("work", b"admitted after cleanup")
        wait_for(dispatcher, session_id, SessionState.COMPLETED)
        dispatcher.close(session_id)
        assert dispatcher._workers == {}
        assert dispatcher._current_workers == {}
        assert dispatcher._retiring_workers == set()
    finally:
        store.allow_drop = True
        store.allow_put = True
        assert dispatcher.shutdown().complete


def test_shutdown_joins_one_blocked_admission_cleanup_worker_to_deadline() -> None:
    cleanup_entered = Event()
    release_cleanup = Event()

    class BlockingStore(InMemorySessionStore):
        def __init__(self):
            super().__init__()
            self.put_calls = 0
            self.drop_calls = 0

        def put(self, record):
            self.put_calls += 1
            super().put(record)
            raise OSError("admission write accepted then failed")

        def drop(self, session_id):
            self.drop_calls += 1
            cleanup_entered.set()
            release_cleanup.wait(2)
            super().drop(session_id)

    store = BlockingStore()
    dispatcher = Dispatcher(
        {"work": registration(lambda _payload: completed)},
        store=store,
        audit_timeout=0.02,
    )
    try:
        started = monotonic()
        with pytest.raises(OSError, match="admission write accepted then failed"):
            dispatcher.submit("work", b"first")
        assert monotonic() - started < 0.2
        assert cleanup_entered.is_set()
        (failed_session_id,) = dispatcher._admission_cleanups
        attempt = dispatcher._admission_cleanup_attempt
        assert attempt is not None
        assert attempt.thread.is_alive()

        with pytest.raises(SessionNotFound):
            dispatcher.close(failed_session_id)

        for _ in range(2):
            started = monotonic()
            incomplete = dispatcher.shutdown(0.03)
            assert monotonic() - started < 0.2
            assert not incomplete.complete
            assert incomplete.unfinished == (failed_session_id,)
            assert incomplete.custody_released
            assert dispatcher._admission_cleanup_attempt is attempt
            assert attempt.thread.is_alive()
            assert store.drop_calls == 1

        release_cleanup.set()
        assert dispatcher.shutdown(2).complete
        assert store.put_calls == 1
        assert store.drop_calls == 1
        assert store.snapshot() == ()
        assert dispatcher._admission_cleanups == {}
        assert dispatcher._admission_cleanup_attempt is None
        assert not dispatcher._admission_liability_claimed
    finally:
        release_cleanup.set()
        dispatcher.shutdown(2)


@pytest.mark.parametrize("accepted_before_failure", (False, True))
def test_admission_cleanup_worker_start_failure_preserves_exact_owner(
    monkeypatch,
    accepted_before_failure: bool,
) -> None:
    original_start = Thread.start
    cleanup_start_calls = 0

    def start(thread):
        nonlocal cleanup_start_calls
        if thread.name.startswith("namisync-admission-cleanup-"):
            cleanup_start_calls += 1
            if cleanup_start_calls == 1:
                if accepted_before_failure:
                    original_start(thread)
                raise OSError("cleanup worker start failed")
        original_start(thread)

    class FailingStore(InMemorySessionStore):
        def put(self, record):
            super().put(record)
            raise RuntimeError("initiating admission failure")

    monkeypatch.setattr(Thread, "start", start)
    dispatcher = Dispatcher(
        {"work": registration(lambda _payload: completed)},
        store=FailingStore(),
    )
    try:
        with pytest.raises(RuntimeError, match="initiating admission failure"):
            dispatcher.submit("work", b"payload")

        if not accepted_before_failure:
            assert len(dispatcher._admission_cleanups) == 1
            assert dispatcher._admission_cleanup_attempt is None
            with pytest.raises(SessionCleanupPending, match="another admission"):
                dispatcher.submit("work", b"retry trigger")
            wait_for_admission_cleanup_attempt(dispatcher)

        assert dispatcher._admission_cleanups == {}
        assert dispatcher._admission_cleanup_attempt is None
        assert not dispatcher._admission_liability_claimed
        assert cleanup_start_calls == (1 if accepted_before_failure else 2)
    finally:
        assert dispatcher.shutdown().complete


def test_admission_cleanup_worker_does_not_join_itself_during_shutdown() -> None:
    calls = 0
    attached_session_ids = []
    shutdown_results = []
    shutdown_errors: list[BaseException] = []
    cleanup_threads = []
    rollback_steps = []
    rollback_finished = Event()

    class FailingClock:
        def now(self):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("pending clock failed")
            return datetime.now(timezone.utc)

    def attach(session_id, stream):
        attached_session_ids.append(session_id)

        def rollback() -> None:
            try:
                rollback_steps.append("entered")
                cleanup_threads.append(current_thread())
                try:
                    result = dispatcher.shutdown(0.0)
                except BaseException as error:
                    shutdown_errors.append(error)
                else:
                    shutdown_results.append(result)
                rollback_steps.append("shutdown-returned")
                stream.close()
            finally:
                rollback_finished.set()

        return rollback

    dispatcher = Dispatcher(
        {"observed": registration(lambda _payload: completed)},
        clock=FailingClock(),
        audit_timeout=0.2,
    )

    with pytest.raises(RuntimeError, match="pending clock failed"):
        dispatcher.submit("observed", b"private continuation", attach=attach)

    assert rollback_finished.wait(1)
    assert rollback_steps == ["entered", "shutdown-returned"]
    assert shutdown_errors == []
    assert len(shutdown_results) == 1
    assert not shutdown_results[0].complete
    assert shutdown_results[0].unfinished == (attached_session_ids[0],)
    assert cleanup_threads[0].name.startswith("namisync-admission-cleanup-")
    assert dispatcher._admission_cleanups == {}
    assert dispatcher._admission_cleanup_attempt is None
    assert not dispatcher._admission_liability_claimed
    assert dispatcher.shutdown(2).complete


def test_observed_admission_emits_pending_before_workflow_can_enter() -> None:
    attached = Event()
    pending_seen = Event()
    workflow_entered = Event()
    reader_done = Event()
    bodies: list[object] = []

    def run(context):
        del context
        assert attached.is_set()
        workflow_entered.set()
        assert pending_seen.wait(1)
        return OperationResult(SessionState.COMPLETED)

    def attach(session_id, stream):
        attached.set()

        def read() -> None:
            try:
                while True:
                    envelope = stream.next()
                    assert envelope.session_id == session_id
                    bodies.append(envelope.body)
                    if (
                        isinstance(envelope.body, StateChanged)
                        and envelope.body.state is SessionState.PENDING
                    ):
                        pending_seen.set()
                    if isinstance(envelope.body, Terminal):
                        return
            finally:
                reader_done.set()

        thread = Thread(target=read, daemon=True)
        thread.start()

        def rollback() -> None:
            stream.close()
            thread.join(1)

        return rollback

    dispatcher = Dispatcher({"observed": registration(lambda payload: run)})
    session_id = dispatcher.submit("observed", b"payload", attach=attach)

    assert workflow_entered.wait(1)
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert reader_done.wait(1)
    assert isinstance(bodies[0], StateChanged)
    assert bodies[0].state is SessionState.PENDING
    assert not any(isinstance(body, Gap) for body in bodies)
    assert dispatcher.shutdown().complete


def test_observed_attach_failure_is_never_published_or_scheduled() -> None:
    ran = Event()
    captured = []

    def run(context):
        del context
        ran.set()
        return OperationResult(SessionState.COMPLETED)

    def reject(session_id, stream):
        captured.append((session_id, stream))
        raise ValueError("attach refused")

    store = InMemorySessionStore()
    dispatcher = Dispatcher(
        {"observed": registration(lambda payload: run)},
        store=store,
    )

    with pytest.raises(ValueError, match="attach refused"):
        dispatcher.submit("observed", b"payload", attach=reject)

    assert not ran.wait(0.05)
    assert dispatcher.list() == ()
    assert store.snapshot() == ()
    with pytest.raises(StopIteration):
        captured[0][1].next()
    assert dispatcher.shutdown().complete


def test_shutdown_racing_observed_attach_rolls_back_without_scheduling() -> None:
    attach_entered = Event()
    release_attach = Event()
    rollback_called = Event()
    ran = Event()
    errors: list[BaseException] = []
    adopted_streams = []

    def run(context):
        del context
        ran.set()
        return OperationResult(SessionState.COMPLETED)

    def attach(session_id, stream):
        del session_id
        adopted_streams.append(stream)
        attach_entered.set()
        assert release_attach.wait(2)

        def rollback() -> None:
            rollback_called.set()
            stream.close()

        return rollback

    dispatcher = Dispatcher({"observed": registration(lambda payload: run)})

    def submit() -> None:
        try:
            dispatcher.submit("observed", b"payload", attach=attach)
        except BaseException as error:
            errors.append(error)

    thread = Thread(target=submit)
    thread.start()
    assert attach_entered.wait(1)
    first_shutdown = dispatcher.shutdown(timeout=0.05)
    assert not first_shutdown.complete
    release_attach.set()
    thread.join(2)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], AdmissionClosed)
    assert rollback_called.is_set()
    with pytest.raises(StopIteration):
        adopted_streams[0].next()
    assert not ran.is_set()
    assert dispatcher.list() == ()
    assert dispatcher.shutdown(timeout=2).complete


def test_pending_emission_failure_preserves_error_and_rolls_back_attach() -> None:
    rollback_attempts = 0
    calls = 0
    attached_session_ids = []

    class FailingClock:
        def now(self):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("pending clock failed")
            return datetime.now(timezone.utc)

    def attach(session_id, stream):
        attached_session_ids.append(session_id)

        def rollback() -> None:
            nonlocal rollback_attempts
            rollback_attempts += 1
            if rollback_attempts < 3:
                raise OSError("rollback cleanup failed")
            stream.close()

        return rollback

    store = InMemorySessionStore()
    dispatcher = Dispatcher(
        {"observed": registration(lambda payload: completed)},
        store=store,
        clock=FailingClock(),
    )

    with pytest.raises(RuntimeError, match="pending clock failed"):
        dispatcher.submit("observed", b"payload", attach=attach)

    assert rollback_attempts == 1
    assert dispatcher.list() == ()
    assert store.snapshot() == ()
    assert len(dispatcher._admission_cleanups) == 1
    incomplete = dispatcher.shutdown(timeout=1)
    assert not incomplete.complete
    assert incomplete.unfinished == (attached_session_ids[0],)
    assert rollback_attempts == 2
    assert dispatcher.shutdown(timeout=2).complete
    assert rollback_attempts == 3
    assert dispatcher._admission_cleanups == {}


def test_shutdown_reports_inflight_admission_and_waits_for_cleanup() -> None:
    prepare_entered = Event()
    release_prepare = Event()
    errors = []

    def prepare(request):
        prepare_entered.set()
        assert release_prepare.wait(2)
        return PreparedSession(b"opaque")

    dispatcher = Dispatcher(
        {
            "slow": WorkflowRegistration(
                prepare=prepare,
                open=lambda payload: Invocation(completed),
            )
        }
    )

    def submit() -> None:
        try:
            dispatcher.submit("slow", object())
        except BaseException as error:
            errors.append(error)

    thread = Thread(target=submit)
    thread.start()
    assert prepare_entered.wait(2)
    incomplete = dispatcher.shutdown(timeout=0.05)
    assert not incomplete.complete
    assert incomplete.custody_released
    release_prepare.set()
    thread.join(2)
    assert len(errors) == 1
    assert isinstance(errors[0], AdmissionClosed)
    assert dispatcher.list() == ()
    assert dispatcher.shutdown(timeout=2).complete


def test_queued_discard_is_finalized_by_audit_before_explicit_close() -> None:
    finalized = Event()
    observed_results = []

    class Audit:
        def on_event(self, envelope) -> RecordingStatus:
            return RecordingStatus.OK

        def flush(self):
            pass

        def finalize(self, result) -> RecordingStatus:
            observed_results.append(result)
            finalized.set()
            return RecordingStatus.OK

        def close(self):
            pass

    release = Event()
    entered = Event()

    def run_for(payload):
        if payload == b"first":
            def hold(context):
                entered.set()
                release.wait(2)
                return OperationResult(SessionState.COMPLETED)
            return hold
        return completed

    resource = ResourceId("volume", "discard-audit")
    dispatcher = Dispatcher(
        {"hold": registration(run_for, resources=(resource,))},
        audit_observer_factory=lambda record: Audit(),
    )
    first = dispatcher.submit("hold", b"first")
    second = dispatcher.submit("hold", b"second")
    assert entered.wait(2)
    assert dispatcher.cancel(second).accepted
    wait_for(dispatcher, second, SessionState.CANCELED)
    assert finalized.wait(2)
    discarded = [
        result
        for result in observed_results
        if result.status is SessionState.CANCELED
    ]
    assert discarded and discarded[0].disposition is Disposition.UNRUN
    dispatcher.close(second)
    release.set()
    wait_for(dispatcher, first, SessionState.COMPLETED)
    assert dispatcher.shutdown().complete


def test_observer_failure_degrades_audit_without_rewriting_filesystem_status() -> None:
    class BrokenObserver:
        def on_event(self, envelope):
            raise RuntimeError("history unavailable")

        def flush(self):
            raise RuntimeError("history unavailable")

        def finalize(self, result):
            raise RuntimeError("history unavailable")

        def close(self):
            pass

    def run(context):
        context.emit(PhaseChanged("one"))
        return OperationResult(SessionState.COMPLETED)

    dispatcher = Dispatcher(
        {"observed": registration(lambda payload: run)},
        audit_observer_factory=lambda record: BrokenObserver(),
        audit_timeout=0.05,
    )
    session_id = dispatcher.submit("observed", b"payload")
    record = wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert record.result is not None
    assert record.result.status is SessionState.COMPLETED
    assert record.result.audit is RecordingStatus.DEGRADED
    assert dispatcher.shutdown().complete


def test_late_history_after_caller_timeout_matches_live_degraded_axis() -> None:
    event_entered = Event()
    release_event = Event()
    finalized = Event()
    retained_results = []

    class LateObserver:
        def on_event(self, envelope) -> RecordingStatus:
            del envelope
            event_entered.set()
            assert release_event.wait(2)
            return RecordingStatus.OK

        def flush(self):
            pass

        def finalize(self, result) -> RecordingStatus:
            retained_results.append(result)
            finalized.set()
            return RecordingStatus.OK

        def close(self):
            pass

    def run(context):
        context.emit(PhaseChanged("one"))
        return OperationResult(SessionState.COMPLETED)

    dispatcher = Dispatcher(
        {"observed": registration(lambda payload: run)},
        audit_observer_factory=lambda record: LateObserver(),
        audit_timeout=0.05,
    )
    session_id = dispatcher.submit("observed", b"payload")
    assert event_entered.wait(2)

    record = wait_for(dispatcher, session_id, SessionState.COMPLETED)

    assert record.result is not None
    assert record.result.audit is RecordingStatus.DEGRADED
    release_event.set()
    assert finalized.wait(2)
    assert retained_results[0].audit is record.result.audit
    assert dispatcher.shutdown().complete


def test_observer_factory_failure_degrades_audit_without_aborting_admission() -> None:
    class PrivateGraph:
        pass

    retained = []
    entered = Event()
    release = Event()

    def unavailable_history(record):
        graph = PrivateGraph()
        retained.append(ref(graph))
        error = OSError("history database cannot be opened")
        error.private_graph = graph
        raise error

    def run(context):
        entered.set()
        assert release.wait(2)
        return OperationResult(SessionState.COMPLETED)

    dispatcher = Dispatcher(
        {"observed": registration(lambda payload: run)},
        audit_observer_factory=unavailable_history,
    )
    try:
        session_id = dispatcher.submit("observed", b"payload")
        assert entered.wait(2)
        gc.collect()
        assert len(retained) == 1
        assert retained[0]() is None
        release.set()
        record = wait_for(dispatcher, session_id, SessionState.COMPLETED)

        assert record.result is not None
        assert record.result.status is SessionState.COMPLETED
        assert record.result.audit is RecordingStatus.DEGRADED
    finally:
        release.set()
        assert dispatcher.shutdown().complete


def test_terminal_record_never_exposes_provisional_audit_ok() -> None:
    finalize_entered = Event()
    release_finalize = Event()
    store = RecordingSessionStore()

    class DelayedObserver:
        def on_event(self, envelope) -> RecordingStatus:
            return RecordingStatus.OK

        def flush(self):
            pass

        def finalize(self, result) -> RecordingStatus:
            finalize_entered.set()
            assert release_finalize.wait(2)
            return RecordingStatus.OK

        def close(self):
            pass

    dispatcher = Dispatcher(
        {"observed": registration(lambda payload: completed)},
        store=store,
        audit_observer_factory=lambda record: DelayedObserver(),
        audit_timeout=1,
    )
    session_id = dispatcher.submit("observed", b"payload")
    assert finalize_entered.wait(2)
    provisional = dispatcher.get(session_id)
    assert provisional.state is SessionState.COMPLETED
    assert provisional.result is None
    assert provisional.payload is None
    assert_stored_record_matches(store.snapshot()[0], provisional)
    with pytest.raises(SessionNotTerminal):
        dispatcher.close(session_id)
    release_finalize.set()
    final = wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert final.payload is None
    assert final.result is not None
    assert final.result.audit is RecordingStatus.OK
    assert_stored_record_matches(store.snapshot()[0], final)
    assert any(
        row.state is SessionState.COMPLETED and row.result is None
        for row in store.attempted
    )
    assert all(type(row) is StoredSessionRecord for row in store.attempted)
    assert all(not hasattr(row, "payload") for row in store.attempted)
    dispatcher.close(session_id)
    assert store.snapshot() == ()
    assert dispatcher.shutdown().complete


def test_shutdown_deadline_does_not_wait_for_a_blocked_publication_lock() -> None:
    entered = Event()
    release_work = Event()

    def run(context):
        del context
        entered.set()
        assert release_work.wait(2)
        return OperationResult(SessionState.COMPLETED)

    dispatcher = Dispatcher({"blocked": registration(lambda payload: run)})
    session_id = dispatcher.submit("blocked", b"payload")
    assert entered.wait(2)
    publication_lock = dispatcher._state_publication_locks[session_id]
    assert publication_lock.acquire(timeout=1)
    results = []
    failures = []
    stopped = Event()

    def shutdown() -> None:
        try:
            results.append(dispatcher.shutdown(timeout=0.05))
        except BaseException as error:
            failures.append(error)
        finally:
            stopped.set()

    thread = Thread(target=shutdown)
    thread.start()
    try:
        assert stopped.wait(0.5)
    finally:
        publication_lock.release()
        release_work.set()
        thread.join(2)

    assert not thread.is_alive()
    assert failures == []
    assert len(results) == 1
    assert not results[0].complete
    assert results[0].unfinished == (session_id,)
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert dispatcher.shutdown(timeout=2).complete


def test_shutdown_deadline_includes_a_hub_blocked_on_audit_delivery() -> None:
    audit_entered = Event()
    release_audit = Event()
    workflow_emit_started = Event()

    class BlockingAudit:
        def on_event(self, envelope) -> None:
            del envelope
            audit_entered.set()
            assert release_audit.wait(2)

        def flush(self) -> None:
            pass

        def finalize(self, result) -> None:
            del result

        def close(self) -> None:
            pass

    def run(context):
        workflow_emit_started.set()
        context.emit(PhaseChanged("blocked-offer"))
        return OperationResult(SessionState.COMPLETED)

    dispatcher = Dispatcher(
        {"blocked-audit": registration(lambda payload: run)},
        audit_observer_factory=lambda record: BlockingAudit(),
        audit_capacity=1,
        audit_offer_timeout=1.0,
    )
    session_id = dispatcher.submit("blocked-audit", b"payload")
    assert audit_entered.wait(2)
    assert workflow_emit_started.wait(2)
    hub = dispatcher._hubs[session_id]
    unexpectedly_reserved = hub._reserve_publication(0.05)
    if unexpectedly_reserved:
        hub._release_publication()
    assert not unexpectedly_reserved

    started = monotonic()
    result = dispatcher.shutdown(timeout=0.05)
    elapsed = monotonic() - started

    assert not result.complete
    assert result.unfinished == (session_id,)
    assert elapsed < 0.5

    release_audit.set()
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert dispatcher.shutdown(timeout=2).complete


def test_shutdown_cancels_other_sessions_before_waiting_on_a_blocked_hub() -> None:
    first_entered = Event()
    second_entered = Event()
    release_first = Event()

    def run_first(context):
        del context
        first_entered.set()
        assert release_first.wait(2)
        return OperationResult(SessionState.COMPLETED)

    def run_second(context):
        second_entered.set()
        while True:
            context.checkpoint()
            sleep(0.005)

    dispatcher = Dispatcher(
        {
            "first": registration(lambda payload: run_first),
            "second": registration(lambda payload: run_second),
        }
    )
    first = dispatcher.submit("first", b"first")
    second = dispatcher.submit("second", b"second")
    assert first_entered.wait(2)
    assert second_entered.wait(2)
    first_hub = dispatcher._hubs[first]
    assert first_hub._reserve_publication(1.0)
    try:
        started = monotonic()
        result = dispatcher.shutdown(timeout=0.1)
        assert monotonic() - started < 0.5
    finally:
        first_hub._release_publication()

    assert not result.complete
    wait_for(dispatcher, second, SessionState.CANCELED)
    release_first.set()
    wait_for(dispatcher, first, SessionState.COMPLETED)
    assert dispatcher.shutdown(timeout=2).complete


def test_shutdown_gates_subscriptions_before_terminal_hub_cleanup(
    monkeypatch,
) -> None:
    dispatcher = Dispatcher({"short": registration(lambda payload: completed)})
    session_id = dispatcher.submit("short", b"payload")
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    hub = dispatcher._hubs[session_id]
    original_close = hub.close
    close_entered = Event()
    release_close = Event()
    stopped = Event()
    results = []
    failures = []

    def blocking_close(timeout: float):
        close_entered.set()
        assert release_close.wait(2)
        return original_close(timeout)

    def shutdown() -> None:
        try:
            results.append(dispatcher.shutdown(timeout=1.0))
        except BaseException as error:
            failures.append(error)
        finally:
            stopped.set()

    monkeypatch.setattr(hub, "close", blocking_close)
    thread = Thread(target=shutdown)
    thread.start()
    assert close_entered.wait(2)
    try:
        with pytest.raises(SessionCleanupPending):
            dispatcher.subscribe(session_id)
        assert hub._subscribers == []
    finally:
        release_close.set()
        thread.join(2)

    assert not thread.is_alive()
    assert stopped.is_set()
    assert failures == []
    assert len(results) == 1
    assert results[0].complete


def test_orderly_shutdown_cancels_and_releases() -> None:
    entered = Event()

    def run(context):
        entered.set()
        while True:
            context.checkpoint()
            sleep(0.005)

    dispatcher = Dispatcher(
        {
            "long": registration(
                lambda payload: run,
                resources=(ResourceId("volume", "one"),),
            )
        }
    )
    dispatcher.submit("long", b"payload")
    assert entered.wait(2)
    result = dispatcher.shutdown(timeout=2)
    assert result.complete
    assert result.custody_released
    assert not result.unfinished


def test_shutdown_deadline_reports_noncooperative_session_then_recovers() -> None:
    entered = Event()
    release = Event()

    def run(context):
        entered.set()
        release.wait(2)
        return OperationResult(SessionState.COMPLETED)

    dispatcher = Dispatcher(
        {
            "blocked": registration(
                lambda payload: run,
                resources=(ResourceId("volume", "noncooperative"),),
            )
        }
    )
    session_id = dispatcher.submit("blocked", b"payload")
    assert entered.wait(2)
    incomplete = dispatcher.shutdown(timeout=0.05)
    assert not incomplete.complete
    assert incomplete.unfinished == (session_id,)
    assert not incomplete.custody_released
    release.set()
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert dispatcher.shutdown(timeout=2).complete


def test_shutdown_reports_canceled_acquisition_until_owner_retires() -> None:
    provider = GatedAcquireProvider()
    dispatcher = Dispatcher(
        {
            "blocked-acquire": registration(
                lambda payload: completed,
                resources=(ResourceId("volume", "blocked-acquire"),),
            )
        },
        lock_provider=provider,
    )
    session_id = dispatcher.submit("blocked-acquire", b"payload")
    assert provider.entered.wait(2)

    incomplete = dispatcher.shutdown(timeout=0.05)
    assert not incomplete.complete
    assert incomplete.unfinished == (session_id,)
    assert not incomplete.custody_released

    provider.release.set()
    wait_for(dispatcher, session_id, SessionState.CANCELED)
    complete = dispatcher.shutdown(timeout=2)
    assert complete.complete
    assert complete.custody_released
    assert complete.unfinished == ()
