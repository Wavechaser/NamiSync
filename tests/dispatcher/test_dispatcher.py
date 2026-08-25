from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event, Lock, Thread, get_ident
from time import monotonic, sleep

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
from namisync.core.session import (
    Canceled,
    Disposition,
    OperationResult,
    PhaseResult,
    PhaseStatus,
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
    store = InMemorySessionStore()

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
    assert dispatcher.resume(session_id).accepted

    terminal = wait_for(dispatcher, session_id, terminal_state)

    assert terminal.payload is None
    assert store.snapshot()[0].payload is None
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


def test_immediate_resume_waits_for_paused_generation_retirement(
    monkeypatch,
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
            retire_entered.set()
            assert release_retirement.wait(2)
        return original_worker_done(key)

    monkeypatch.setattr(dispatcher, "_worker_done", gated_worker_done)
    session_id = dispatcher.submit("pausable", b"initial")
    session_ids.append(session_id)
    assert first_entered.wait(2)
    assert dispatcher.pause(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.PAUSED)
    assert retire_entered.wait(2)
    with dispatcher._condition:
        old_key = dispatcher._current_workers[session_id]

    try:
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


def test_cancel_visible_paused_before_retirement_hands_off_once(
    monkeypatch,
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
            retire_entered.set()
            assert release_retirement.wait(2)
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
    assert record.payload is None
    assert opened == [opaque]
    assert dispatcher.shutdown().complete


def test_in_memory_store_is_honest_about_absent_restart_state() -> None:
    store = InMemorySessionStore()
    dispatcher = Dispatcher({"opaque": registration(lambda payload: completed)}, store=store)
    session_id = dispatcher.submit("opaque", b"payload")
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert store.snapshot()[0].payload is None
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
    def unavailable_history(record):
        raise OSError("history database cannot be opened")

    dispatcher = Dispatcher(
        {"observed": registration(lambda payload: completed)},
        audit_observer_factory=unavailable_history,
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
        audit_observer_factory=lambda record: DelayedObserver(),
        audit_timeout=1,
    )
    session_id = dispatcher.submit("observed", b"payload")
    assert finalize_entered.wait(2)
    provisional = dispatcher.get(session_id)
    assert provisional.state is SessionState.COMPLETED
    assert provisional.result is None
    assert provisional.payload is None
    with pytest.raises(SessionNotTerminal):
        dispatcher.close(session_id)
    release_finalize.set()
    final = wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert final.payload is None
    assert final.result is not None
    assert final.result.audit is RecordingStatus.OK
    dispatcher.close(session_id)
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
