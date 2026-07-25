from __future__ import annotations

import io
from collections import deque
from types import SimpleNamespace
from threading import Event, Lock

import pytest

from namisync.core.events import (
    Envelope,
    Gap,
    PhaseChanged,
    SCHEMA_VERSION,
    Terminal,
)
from namisync.core.session import (
    OperationResult,
    SessionId,
    SessionRecord,
    SessionState,
)
from namisync.dispatcher import SessionNotFound
from namisync.interfaces import main as package_main
from namisync.interfaces.service import (
    NamiSyncService,
    SessionEventView,
    SessionObserver,
    SessionRecordView,
)

from _db_fixtures import NOW


def _record(
    session_id: str,
    *,
    terminal: bool = False,
) -> SessionRecord:
    state = SessionState.COMPLETED if terminal else SessionState.RUNNING
    return SessionRecord(
        SessionId(session_id),
        "test",
        state,
        (),
        b"payload",
        True,
        0,
        NOW,
        started_at=NOW,
        ended_at=NOW if terminal else None,
        result=OperationResult(SessionState.COMPLETED) if terminal else None,
    )


def _envelope(session_id: str, sequence: int, body: object) -> Envelope:
    return Envelope(
        SessionId(session_id),
        sequence,
        NOW,
        SCHEMA_VERSION,
        body,
    )


class _SequenceStream:
    def __init__(self, *items: Envelope) -> None:
        self._items = deque(items)
        self.closed = False
        self.next_arguments: list[tuple[object, ...]] = []

    def next(self, *args) -> Envelope:
        self.next_arguments.append(args)
        if self.closed or not self._items:
            raise StopIteration
        return self._items.popleft()

    def close(self) -> None:
        self.closed = True


class _BlockingStream:
    def __init__(
        self,
        name: str,
        *,
        close_log: list[str] | None = None,
        all_closed: Event | None = None,
        close_count: list[int] | None = None,
        close_lock: Lock | None = None,
    ) -> None:
        self.name = name
        self.entered = Event()
        self.released = Event()
        self.closed = False
        self.next_arguments: list[tuple[object, ...]] = []
        self._close_log = close_log
        self._all_closed = all_closed
        self._close_count = close_count
        self._close_lock = close_lock

    def next(self, *args) -> Envelope:
        self.next_arguments.append(args)
        self.entered.set()
        self.released.wait(2.0)
        if self._all_closed is not None:
            self._all_closed.wait(2.0)
        raise StopIteration

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self._close_log is not None:
            self._close_log.append(f"close:{self.name}")
        if self._close_count is not None and self._close_lock is not None:
            with self._close_lock:
                self._close_count[0] += 1
                if (
                    self._all_closed is not None
                    and self._close_count[0] == 2
                ):
                    self._all_closed.set()
        self.released.set()


def test_observe_returns_finished_record_without_subscribing() -> None:
    class Dispatcher:
        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id, terminal=True)

        def subscribe(self, session_id: str, from_seq=None):
            raise AssertionError("finished session must not subscribe")

    observer = SessionObserver(Dispatcher())
    updates = []

    current = observer.observe("finished", updates.append)

    assert current.result is not None
    assert updates == []
    observer.close()


def test_interfaces_package_preserves_lazy_main_entry_point() -> None:
    stderr = io.StringIO()

    result = package_main([], stdout=io.StringIO(), stderr=stderr)

    assert result == 2
    assert "usage:" in stderr.getvalue()


def test_finish_between_get_and_subscribe_returns_terminal_record() -> None:
    class Dispatcher:
        def __init__(self) -> None:
            self.get_count = 0

        def get(self, session_id: str) -> SessionRecord:
            self.get_count += 1
            return _record(session_id, terminal=self.get_count > 1)

        def subscribe(self, session_id: str, from_seq=None):
            raise SessionNotFound(session_id)

    observer = SessionObserver(Dispatcher())

    current = observer.observe("raced", lambda _update: None)

    assert current.result is not None
    observer.close()


def test_unsubscribe_closes_blocking_stream_and_uses_no_poll_timeout() -> None:
    stream = _BlockingStream("live")

    class Dispatcher:
        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id)

        def subscribe(self, session_id: str, from_seq=None):
            return stream

    observer = SessionObserver(Dispatcher())
    observer.observe("live", lambda _update: None)
    assert stream.entered.wait(0.5)

    observer.unsubscribe("live")
    observer.unsubscribe("live")

    assert stream.closed
    assert stream.next_arguments == [()]
    observer.close()


def test_close_closes_every_stream_before_joining_observers() -> None:
    log: list[str] = []
    all_closed = Event()
    close_count = [0]
    close_lock = Lock()
    streams = {
        name: _BlockingStream(
            name,
            close_log=log,
            all_closed=all_closed,
            close_count=close_count,
            close_lock=close_lock,
        )
        for name in ("one", "two")
    }

    class Dispatcher:
        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id)

        def subscribe(self, session_id: str, from_seq=None):
            return streams[session_id]

    observer = SessionObserver(Dispatcher())
    for session_id in streams:
        observer.observe(session_id, lambda _update: None)
    assert all(stream.entered.wait(0.5) for stream in streams.values())

    observer.close()
    observer.close()

    assert log[:2] == ["close:one", "close:two"]
    assert all(stream.closed for stream in streams.values())


def test_gap_recovery_resubscribes_from_first_undelivered_sequence() -> None:
    session_id = "gap"
    terminal_result = OperationResult(SessionState.COMPLETED)
    first = _SequenceStream(
        _envelope(session_id, 1, PhaseChanged("one")),
        _envelope(session_id, 3, Gap(first_missed_seq=2)),
    )
    second = _SequenceStream(
        _envelope(session_id, 2, PhaseChanged("two")),
        _envelope(session_id, 4, Terminal(terminal_result)),
    )
    terminal_record = _record(session_id, terminal=True)

    class Dispatcher:
        def __init__(self) -> None:
            self.subscribe_calls: list[int | None] = []
            self.finished = False

        def get(self, requested: str) -> SessionRecord:
            return terminal_record if self.finished else _record(requested)

        def subscribe(self, requested: str, from_seq=None):
            self.subscribe_calls.append(from_seq)
            if len(self.subscribe_calls) == 1:
                return first
            return second

    dispatcher = Dispatcher()
    observer = SessionObserver(dispatcher)
    updates: list[SessionEventView | SessionRecordView] = []
    completed = Event()

    def receive(update: SessionEventView | SessionRecordView) -> None:
        updates.append(update)
        if isinstance(update, SessionEventView) and update.body_type == "Terminal":
            dispatcher.finished = True
        if isinstance(update, SessionRecordView) and update.result is not None:
            completed.set()

    observer.observe(session_id, receive)
    assert completed.wait(0.5)
    observer.close()

    events = [item for item in updates if isinstance(item, SessionEventView)]
    assert dispatcher.subscribe_calls == [None, 2]
    assert [item.body_type for item in events] == [
        "PhaseChanged",
        "Gap",
        "PhaseChanged",
        "Terminal",
    ]
    assert [
        item.body["phase"]
        for item in events
        if item.body_type == "PhaseChanged"
    ] == ["one", "two"]


def test_sink_exception_closes_stream_and_does_not_block_shutdown() -> None:
    stream = _SequenceStream(_envelope("sink", 1, PhaseChanged("explode")))
    closed = Event()
    original_close = stream.close

    def close() -> None:
        original_close()
        closed.set()

    stream.close = close

    class Dispatcher:
        def get(self, session_id: str) -> SessionRecord:
            return _record(session_id)

        def subscribe(self, session_id: str, from_seq=None):
            return stream

    observer = SessionObserver(Dispatcher())

    def explode(_update) -> None:
        raise RuntimeError("sink failed")

    observer.observe("sink", explode)
    assert closed.wait(0.5)
    with pytest.raises(RuntimeError, match="session observation failed") as raised:
        observer.wait("sink")
    assert isinstance(raised.value.__cause__, RuntimeError)
    assert str(raised.value.__cause__) == "sink failed"
    observer.close()


def test_service_shutdown_orders_observer_dispatcher_and_runtime() -> None:
    log: list[str] = []

    class Observer:
        def close(self) -> None:
            log.append("observer")

    class Dispatcher:
        def shutdown(self, timeout: float):
            log.append("dispatcher")
            return SimpleNamespace(
                complete=True,
                unfinished=(),
                custody_released=True,
            )

    class Runtime:
        def close(self) -> None:
            log.append("runtime")

    service = object.__new__(NamiSyncService)
    service._observer = Observer()
    service._dispatcher = Dispatcher()
    service._runtime = Runtime()
    service._lock = Lock()
    service._closed = False
    service._shutdown = None

    first = service.close()
    second = service.close()

    assert log == ["observer", "dispatcher", "runtime"]
    assert first is second
    assert first.complete


def test_service_execution_opt_in_reaches_runtime_without_changing_default() -> None:
    calls: list[tuple[str, bool]] = []

    class Runtime:
        def commit_plan(
            self,
            request_id: str,
            *,
            verify_after_execute: bool = False,
        ):
            calls.append((request_id, verify_after_execute))
            return SimpleNamespace(
                execution_set=SimpleNamespace(run_id=f"run-{request_id}")
            )

    class Dispatcher:
        def submit(self, kind: str, request: object):
            assert kind == "sync-execution"
            return f"session-{len(calls)}"

    service = object.__new__(NamiSyncService)
    service._runtime = Runtime()
    service._dispatcher = Dispatcher()

    default = service.start_execution("default")
    verified = service.start_execution(
        "verified",
        verify_after_execute=True,
    )

    assert calls == [("default", False), ("verified", True)]
    assert (default.run_id, default.session_id) == (
        "run-default",
        "session-1",
    )
    assert (verified.run_id, verified.session_id) == (
        "run-verified",
        "session-2",
    )
