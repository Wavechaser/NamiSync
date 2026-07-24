from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock, Thread
from time import monotonic, sleep

import pytest

from namisync.core.evidence import RecordingStatus
from namisync.core.events import ItemOutcome, PhaseChanged, Terminal
from namisync.core.evidence import Outcome
from namisync.core.session import (
    Disposition,
    OperationResult,
    ResourceId,
    SessionState,
)
from namisync.dispatcher import (
    AdmissionClosed,
    ControlAction,
    ControlCode,
    Dispatcher,
    InProcessResourceLockProvider,
    PreparedSession,
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


@dataclass
class Invocation:
    run_fn: object
    snapshot_bytes: bytes = b"continued"

    def run(self, context):
        return self.run_fn(context)

    def snapshot(self) -> bytes:
        return self.snapshot_bytes


def registration(run_for_payload, *, supports_pause=False, resources=()):
    def prepare(request):
        payload = request if isinstance(request, bytes) else str(request).encode()
        return PreparedSession(payload, frozenset(resources))

    return WorkflowRegistration(
        prepare=prepare,
        open=lambda payload: Invocation(run_for_payload(payload)),
        supports_pause=supports_pause,
    )


def completed(context):
    return OperationResult(SessionState.COMPLETED)


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
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert opened == [b"initial", b"continued"]
    assert dispatcher.shutdown().custody_released


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
                    ItemOutcome("earned", "dummy", "file", Outcome.SUCCEEDED)
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
    assert earned.item_id == "earned"
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
    dispatcher = Dispatcher(
        {"hold": registration(run_for, resources=(resource,))},
        lock_provider=InProcessResourceLockProvider(),
    )
    first = dispatcher.submit("hold", b"first")
    second = dispatcher.submit("hold", b"second")
    assert first_started.wait(2)
    assert dispatcher.cancel(second).accepted
    record = wait_for(dispatcher, second, SessionState.CANCELED)
    assert record.result is not None
    assert record.result.disposition is Disposition.UNRUN
    with pytest.raises(SessionNotTerminal):
        dispatcher.close(first)
    dispatcher.close(second)
    assert all(item.session_id != second for item in dispatcher.list())
    release.set()
    wait_for(dispatcher, first, SessionState.COMPLETED)
    assert dispatcher.shutdown().complete


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


def test_payload_is_passed_to_adapter_and_store_without_dispatcher_decoding() -> None:
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
    assert record.payload == opaque
    assert opened == [opaque]
    assert dispatcher.shutdown().complete


def test_in_memory_store_is_honest_about_absent_restart_state() -> None:
    store = InMemorySessionStore()
    dispatcher = Dispatcher({"opaque": registration(lambda payload: completed)}, store=store)
    session_id = dispatcher.submit("opaque", b"payload")
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert store.snapshot()[0].payload == b"payload"
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
        def on_event(self, envelope):
            pass

        def finalize(self, result):
            observed_results.append(result)
            finalized.set()

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


def test_terminal_record_never_exposes_provisional_audit_ok() -> None:
    finalize_entered = Event()
    release_finalize = Event()

    class DelayedObserver:
        def on_event(self, envelope):
            pass

        def finalize(self, result):
            finalize_entered.set()
            assert release_finalize.wait(2)

        def close(self):
            pass

    dispatcher = Dispatcher(
        {"observed": registration(lambda payload: completed)},
        audit_observer_factory=lambda record: DelayedObserver(),
        audit_timeout=1,
    )
    session_id = dispatcher.submit("observed", b"payload")
    assert finalize_entered.wait(2)
    provisional = dispatcher.get(session_id)
    assert provisional.state is SessionState.COMPLETED
    assert provisional.result is None
    with pytest.raises(SessionNotTerminal):
        dispatcher.close(session_id)
    release_finalize.set()
    final = wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert final.result is not None
    assert final.result.audit is RecordingStatus.OK
    dispatcher.close(session_id)
    assert dispatcher.shutdown().complete


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
