"""Physical-disk scheduling keys: dispatcher contract and scheduler (M2-A8).

Readers are injected; the dispatcher sees only opaque hashable keys. Tests
wait on events and on counted scheduler passes, never on elapsed time; the
deadlines below only bound a failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Condition, Event, Lock, Thread
from time import monotonic
from uuid import uuid4

import pytest

from namisync.core.evidence import RecordingStatus
from namisync.core.session import (
    Canceled,
    OperationResult,
    ResourceId,
    SessionState,
)
from namisync.dispatcher import (
    Dispatcher,
    InMemorySessionStore,
    PreparedSession,
    WorkflowRegistration,
)

_LIMIT = 5.0


@dataclass(frozen=True)
class Job:
    name: str
    keys: object = frozenset()
    resources: tuple[ResourceId, ...] = ()


class NoLease:
    def release(self) -> None:
        return None


class NoLockProvider:
    """Keys are not custody; resource locking is irrelevant to these tests."""

    def acquire(self, resources, canceled):
        return NoLease()


class GatedFirstAcquire:
    """Block the first acquisition until released, then honor withdrawal."""

    def __init__(self) -> None:
        self.entered = Event()
        self.release = Event()
        self._lock = Lock()
        self._count = 0

    def acquire(self, resources, canceled):
        with self._lock:
            self._count += 1
            first = self._count == 1
        if first:
            self.entered.set()
            assert self.release.wait(_LIMIT)
            if canceled():
                raise Canceled()
        return NoLease()


class KeyReader:
    """Injected reader that counts calls per job and checks the lock."""

    def __init__(self, keys_for=lambda job: job.keys) -> None:
        self._keys_for = keys_for
        self._condition = Condition()
        self.calls: list[Job] = []
        self.under_lock: list[bool] = []
        self.dispatcher: Dispatcher | None = None

    def __call__(self, checkpoint):
        if self.dispatcher is not None:
            self.under_lock.append(self.dispatcher._condition._is_owned())
        with self._condition:
            self.calls.append(checkpoint)
            self._condition.notify_all()
        return self._keys_for(checkpoint)

    def count(self, name: str) -> int:
        with self._condition:
            return sum(1 for job in self.calls if job.name == name)

    def wait_count(self, name: str, count: int, timeout: float) -> bool:
        with self._condition:
            return self._condition.wait_for(
                lambda: sum(1 for job in self.calls if job.name == name) >= count,
                timeout,
            )


class Runs:
    """Each run records its start, then waits for its own release."""

    def __init__(self) -> None:
        self._condition = Condition()
        self.order: list[str] = []
        self._released: set[str] = set()
        self._fail: set[str] = set()

    def run_for(self, job: Job):
        def run(context):
            with self._condition:
                self.order.append(job.name)
                self._condition.notify_all()
            while True:
                with self._condition:
                    self._condition.wait_for(
                        lambda: job.name in self._released or job.name in self._fail,
                        0.005,
                    )
                    if job.name in self._fail:
                        raise OSError("injected run failure")
                    if job.name in self._released:
                        return OperationResult(SessionState.COMPLETED)
                context.checkpoint()

        return run

    def started(self, name: str, times: int = 1) -> bool:
        with self._condition:
            return self._condition.wait_for(
                lambda: self.order.count(name) >= times, _LIMIT
            )

    def release(self, name: str) -> None:
        with self._condition:
            self._released.add(name)
            self._condition.notify_all()

    def fail(self, name: str) -> None:
        with self._condition:
            self._fail.add(name)
            self._condition.notify_all()


def keyed(runs: Runs, reader, *, supports_pause=False, snapshot_for=None):
    @dataclass
    class Invocation:
        job: Job

        def run(self, context):
            return runs.run_for(self.job)(context)

        def snapshot(self):
            return snapshot_for(self.job) if snapshot_for else self.job

    return WorkflowRegistration(
        prepare=lambda job: PreparedSession(job, frozenset(job.resources)),
        open=Invocation,
        supports_pause=supports_pause,
        read_scheduling_keys=reader,
    )


def make(registry, *, lock_provider=None, **kwargs) -> Dispatcher:
    dispatcher = Dispatcher(
        registry,
        lock_provider=lock_provider or NoLockProvider(),
        **kwargs,
    )
    for registration in registry.values():
        reader = registration.read_scheduling_keys
        if isinstance(reader, KeyReader):
            reader.dispatcher = dispatcher
    return dispatcher


def wait_for(dispatcher: Dispatcher, session_id, state: SessionState):
    deadline = monotonic() + _LIMIT
    with dispatcher._condition:
        while True:
            record = dispatcher._records[session_id]
            if record.state is state and (
                state
                not in (
                    SessionState.COMPLETED,
                    SessionState.FAILED,
                    SessionState.CANCELED,
                )
                or record.result is not None
            ):
                return record
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise AssertionError(f"session did not reach {state}: {record}")
            dispatcher._condition.wait(remaining)


def complete_passes(dispatcher: Dispatcher, reader: KeyReader, name: str, passes=2):
    """Return after ``passes`` more scheduler readings of ``name``.

    Each pass reads every queued pending session once, so the second reading
    proves the first reading's selection has finished.
    """

    target = reader.count(name) + passes
    deadline = monotonic() + _LIMIT
    while not reader.wait_count(name, target, 0.01):
        assert monotonic() < deadline, "scheduler made no further pass"
        with dispatcher._condition:
            dispatcher._condition.notify_all()


def reserved_keys(dispatcher: Dispatcher) -> set:
    with dispatcher._condition:
        return set(dispatcher._reserved_keys)


def finish(dispatcher: Dispatcher) -> None:
    result = dispatcher.shutdown(_LIMIT)
    assert result.complete, result
    assert reserved_keys(dispatcher) == set()


def test_registration_without_reader_is_inert(monkeypatch) -> None:
    def no_read(requests):
        raise AssertionError("a registration without a reader was read")

    monkeypatch.setattr(Dispatcher, "_read_scheduling_keys", staticmethod(no_read))
    runs = Runs()
    shared = ResourceId("volume", "inert-shared")
    registration = keyed(runs, None)
    assert WorkflowRegistration(prepare=None, open=None).read_scheduling_keys is None
    dispatcher = make({"job": registration})
    first = dispatcher.submit("job", Job("first", resources=(shared,)))
    second = dispatcher.submit("job", Job("second", resources=(shared,)))
    other = dispatcher.submit("job", Job("other", resources=(ResourceId("volume", "x"),)))
    assert runs.started("first")
    assert runs.started("other")
    assert dispatcher.get(second).state is SessionState.PENDING
    assert reserved_keys(dispatcher) == set()
    for name in ("first", "second", "other"):
        runs.release(name)
    for session_id in (first, second, other):
        wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert runs.order.index("first") < runs.order.index("second")
    finish(dispatcher)


def test_equal_keys_serialize_in_admission_order() -> None:
    runs = Runs()
    reader = KeyReader()
    dispatcher = make({"job": keyed(runs, reader)})
    disk = frozenset({"disk-0"})
    ids = {}
    ids["a"] = dispatcher.submit("job", Job("a", disk))
    assert runs.started("a")
    ids["b"] = dispatcher.submit("job", Job("b", disk))
    ids["c"] = dispatcher.submit("job", Job("c", disk))
    for current, waiting in (("a", ("b", "c")), ("b", ("c",))):
        complete_passes(dispatcher, reader, waiting[-1])
        for name in waiting:
            assert dispatcher.get(ids[name]).state is SessionState.PENDING
        assert reserved_keys(dispatcher) == {"disk-0"}
        runs.release(current)
        assert runs.started(waiting[0])
    runs.release("c")
    for session_id in ids.values():
        wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert runs.order == ["a", "b", "c"]
    assert not any(reader.under_lock)
    finish(dispatcher)


def test_disjoint_keys_overlap() -> None:
    runs = Runs()
    reader = KeyReader()
    dispatcher = make({"job": keyed(runs, reader)})
    first = dispatcher.submit("job", Job("a", frozenset({"disk-0"})))
    second = dispatcher.submit("job", Job("b", frozenset({"disk-1"})))
    assert runs.started("a") and runs.started("b")
    assert reserved_keys(dispatcher) == {"disk-0", "disk-1"}
    runs.release("a")
    runs.release("b")
    wait_for(dispatcher, first, SessionState.COMPLETED)
    wait_for(dispatcher, second, SessionState.COMPLETED)
    finish(dispatcher)


def test_later_session_on_another_partition_cannot_overtake() -> None:
    runs = Runs()
    reader = KeyReader()
    dispatcher = make({"job": keyed(runs, reader)})
    j = ResourceId("volume", "partition-j")
    m = ResourceId("volume", "partition-m")
    disk = frozenset({"disk-0"})
    # The holder has no key, so only the waiting set can stop ``later``.
    holder = dispatcher.submit("job", Job("holder", resources=(j,)))
    assert runs.started("holder")
    first = dispatcher.submit("job", Job("first", disk, (j,)))
    later = dispatcher.submit("job", Job("later", disk, (m,)))
    complete_passes(dispatcher, reader, "later")
    assert dispatcher.get(first).state is SessionState.PENDING
    assert dispatcher.get(later).state is SessionState.PENDING
    runs.release("holder")
    assert runs.started("first")
    complete_passes(dispatcher, reader, "later")
    assert dispatcher.get(later).state is SessionState.PENDING
    runs.release("first")
    assert runs.started("later")
    runs.release("later")
    for session_id in (holder, first, later):
        wait_for(dispatcher, session_id, SessionState.COMPLETED)
    assert runs.order == ["holder", "first", "later"]
    finish(dispatcher)


def test_resume_reads_keys_again_from_the_current_checkpoint() -> None:
    runs = Runs()
    reader = KeyReader()
    moved = Job("p", frozenset({"disk-1"}))
    dispatcher = make(
        {
            "job": keyed(
                runs, reader, supports_pause=True, snapshot_for=lambda job: moved
            )
        }
    )
    session_id = dispatcher.submit("job", Job("p", frozenset({"disk-0"})))
    assert runs.started("p")
    assert reserved_keys(dispatcher) == {"disk-0"}
    reads_before = reader.count("p")
    assert dispatcher.pause(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.PAUSED)
    assert reserved_keys(dispatcher) == set()
    assert dispatcher.resume(session_id).accepted
    assert runs.started("p", times=2)
    assert reader.count("p") > reads_before
    assert any(job is moved for job in reader.calls)
    assert reserved_keys(dispatcher) == {"disk-1"}
    runs.release("p")
    wait_for(dispatcher, session_id, SessionState.COMPLETED)
    finish(dispatcher)


@pytest.mark.parametrize(
    "answer",
    ["raises", "set", "list", "none", "string"],
)
def test_failed_or_malformed_reading_means_no_keys(answer: str) -> None:
    def bad(job: Job):
        if answer == "raises":
            raise RuntimeError("volume query failed")
        return {
            "set": {"disk-0"},
            "list": ["disk-0"],
            "none": None,
            "string": "disk-0",
        }[answer]

    runs = Runs()
    good_reader = KeyReader()
    bad_reader = KeyReader(bad)
    dispatcher = make(
        {"good": keyed(runs, good_reader), "bad": keyed(runs, bad_reader)}
    )
    good = dispatcher.submit("good", Job("good", frozenset({"disk-0"})))
    assert runs.started("good")
    unknown = dispatcher.submit("bad", Job("bad"))
    assert runs.started("bad")
    assert reserved_keys(dispatcher) == {"disk-0"}
    runs.release("good")
    runs.release("bad")
    record = wait_for(dispatcher, unknown, SessionState.COMPLETED)
    assert record.result is not None
    assert record.result.status is SessionState.COMPLETED
    wait_for(dispatcher, good, SessionState.COMPLETED)
    finish(dispatcher)


@pytest.mark.parametrize("exit_path", ["pause", "cancel", "failure"])
def test_keys_are_released_on_pause_cancel_and_failure(exit_path: str) -> None:
    runs = Runs()
    reader = KeyReader()
    dispatcher = make({"job": keyed(runs, reader, supports_pause=True)})
    disk = frozenset({"disk-0"})
    first = dispatcher.submit("job", Job("first", disk))
    assert runs.started("first")
    second = dispatcher.submit("job", Job("second", disk))
    complete_passes(dispatcher, reader, "second")
    assert dispatcher.get(second).state is SessionState.PENDING
    if exit_path == "pause":
        assert dispatcher.pause(first).accepted
        settled = SessionState.PAUSED
    elif exit_path == "cancel":
        assert dispatcher.cancel(first).accepted
        settled = SessionState.CANCELED
    else:
        runs.fail("first")
        settled = SessionState.FAILED
    wait_for(dispatcher, first, settled)
    assert runs.started("second")
    with dispatcher._condition:
        owners = {key.session_id for key in dispatcher._reserved_keys.values()}
    assert owners == {second}
    runs.release("second")
    wait_for(dispatcher, second, SessionState.COMPLETED)
    if exit_path == "pause":
        assert dispatcher.cancel(first).accepted
        wait_for(dispatcher, first, SessionState.CANCELED)
    finish(dispatcher)


def test_scheduling_keys_never_reach_records_stores_or_events() -> None:
    marker = f"scheduling-key-marker-{uuid4().hex}"
    stored: list[object] = []
    audited: list[object] = []

    class Store(InMemorySessionStore):
        def put(self, record) -> None:
            stored.append(record)
            super().put(record)

    class Observer:
        def on_event(self, envelope):
            audited.append(envelope)
            return RecordingStatus.OK

        def flush(self) -> None:
            return None

        def finalize(self, result):
            return RecordingStatus.OK

        def close(self) -> None:
            return None

    runs = Runs()
    reader = KeyReader()
    dispatcher = make(
        {"job": keyed(runs, reader, supports_pause=True)},
        store=Store(),
        audit_observer_factory=lambda record: Observer(),
    )
    session_id = dispatcher.submit("job", Job("p", frozenset({(marker,)})))
    stream = dispatcher.subscribe(session_id, 1)
    assert runs.started("p")
    assert reserved_keys(dispatcher) == {(marker,)}
    assert dispatcher.pause(session_id).accepted
    wait_for(dispatcher, session_id, SessionState.PAUSED)
    assert dispatcher.resume(session_id).accepted
    assert runs.started("p", times=2)
    runs.release("p")
    record = wait_for(dispatcher, session_id, SessionState.COMPLETED)
    events = []
    while True:
        try:
            events.append(stream.next(0.05))
        except (TimeoutError, StopIteration):
            break
    assert events and audited and stored
    assert all(isinstance(resource, ResourceId) for resource in record.resources)
    for value in (*dispatcher.list(), *stored, *events, *audited, record.result):
        assert marker not in repr(value)
    finish(dispatcher)


@pytest.mark.parametrize("released", [False, True])
def test_hold_during_a_blocked_read_discards_the_reading(released: bool) -> None:
    entered = Event()
    gate = Event()
    first_read = Lock()
    readings = iter((frozenset({"stale"}),))

    def blocking(job: Job):
        if job.name == "held" and first_read.acquire(blocking=False):
            entered.set()
            assert gate.wait(_LIMIT)
            return next(readings)
        return job.keys

    runs = Runs()
    reader = KeyReader(blocking)
    dispatcher = make({"job": keyed(runs, reader)})
    held = dispatcher.submit("job", Job("held", frozenset({"fresh"})))
    assert entered.wait(_LIMIT)

    def bulk() -> None:
        assert dispatcher.pause_all().held == 1
        if released:
            assert dispatcher.resume_all().resumed == 1

    controller = Thread(target=bulk, daemon=True)
    controller.start()
    controller.join(_LIMIT)
    assert not controller.is_alive(), "bulk control waited on a key reading"
    gate.set()
    if released:
        assert runs.started("held")
        assert reader.count("held") >= 2
        assert reserved_keys(dispatcher) == {"fresh"}
        runs.release("held")
        wait_for(dispatcher, held, SessionState.COMPLETED)
    else:
        probe = dispatcher.submit("job", Job("probe"))
        runs.release("probe")
        wait_for(dispatcher, probe, SessionState.COMPLETED)
        assert dispatcher.get(held).state is SessionState.PAUSED
        assert "held" not in runs.order
        assert reader.count("held") == 1
        with dispatcher._condition:
            assert held not in dispatcher._current_workers
        assert dispatcher.cancel(held).accepted
        wait_for(dispatcher, held, SessionState.CANCELED)
    assert not any(reader.under_lock)
    finish(dispatcher)


def test_withdrawn_attempt_keeps_its_keys_until_it_retires() -> None:
    provider = GatedFirstAcquire()
    runs = Runs()
    reader = KeyReader()
    dispatcher = make({"job": keyed(runs, reader)}, lock_provider=provider)
    disk = frozenset({"disk-0"})
    first = dispatcher.submit("job", Job("first", disk))
    assert provider.entered.wait(_LIMIT)
    assert dispatcher.pause_all().held == 1
    second = dispatcher.submit("job", Job("second", disk))
    complete_passes(dispatcher, reader, "second")
    assert dispatcher.get(second).state is SessionState.PENDING
    assert reserved_keys(dispatcher) == {"disk-0"}
    provider.release.set()
    assert runs.started("second")
    runs.release("second")
    wait_for(dispatcher, second, SessionState.COMPLETED)
    assert dispatcher.get(first).state is SessionState.PAUSED
    assert "first" not in runs.order
    assert dispatcher.cancel(first).accepted
    wait_for(dispatcher, first, SessionState.CANCELED)
    finish(dispatcher)


@pytest.mark.parametrize("held", [False, True])
def test_worker_start_failure_releases_its_keys(monkeypatch, held: bool) -> None:
    runs = Runs()
    reader = KeyReader()
    dispatcher = make({"job": keyed(runs, reader)})
    original_start = Thread.start
    armed = [True]

    def failing_start(thread) -> None:
        if armed[0] and thread.name.startswith("namisync-session-"):
            armed[0] = False
            if held:
                # Withdrawn before start: nothing settles, only retirement
                # can release the attempt's keys.
                assert dispatcher.pause_all().held == 1
            raise RuntimeError("cannot start thread")
        original_start(thread)

    monkeypatch.setattr(Thread, "start", failing_start)
    disk = frozenset({"disk-0"})
    first = dispatcher.submit("job", Job("first", disk))
    if held:
        wait_for(dispatcher, first, SessionState.PAUSED)
    else:
        record = wait_for(dispatcher, first, SessionState.FAILED)
        assert record.result is not None
    second = dispatcher.submit("job", Job("second", disk))
    assert runs.started("second")
    runs.release("second")
    wait_for(dispatcher, second, SessionState.COMPLETED)
    assert "first" not in runs.order
    if held:
        assert dispatcher.cancel(first).accepted
        wait_for(dispatcher, first, SessionState.CANCELED)
    finish(dispatcher)


def test_resumed_session_awaiting_its_paused_generation_keeps_key_order(
    monkeypatch,
) -> None:
    runs = Runs()
    reader = KeyReader()
    dispatcher = make({"job": keyed(runs, reader, supports_pause=True)})
    retire_entered = Event()
    release_retirement = Event()
    original_worker_done = dispatcher._worker_done
    paused_ids = []

    def gated_worker_done(key):
        if paused_ids and key.session_id == paused_ids[0] and not retire_entered.is_set():
            retire_entered.set()
            assert release_retirement.wait(_LIMIT)
        return original_worker_done(key)

    monkeypatch.setattr(dispatcher, "_worker_done", gated_worker_done)
    disk = frozenset({"disk-0"})
    first = dispatcher.submit("job", Job("first", disk))
    paused_ids.append(first)
    assert runs.started("first")
    assert dispatcher.pause(first).accepted
    wait_for(dispatcher, first, SessionState.PAUSED)
    assert retire_entered.wait(_LIMIT)
    try:
        assert dispatcher.resume(first).accepted
        later = dispatcher.submit("job", Job("later", disk))
        complete_passes(dispatcher, reader, "later")
        assert dispatcher.get(later).state is SessionState.PENDING
        assert runs.order == ["first"]
    finally:
        release_retirement.set()
    assert runs.started("first", times=2)
    complete_passes(dispatcher, reader, "later")
    assert dispatcher.get(later).state is SessionState.PENDING
    runs.release("first")
    assert runs.started("later")
    runs.release("later")
    wait_for(dispatcher, first, SessionState.COMPLETED)
    wait_for(dispatcher, later, SessionState.COMPLETED)
    assert runs.order == ["first", "first", "later"]
    finish(dispatcher)
