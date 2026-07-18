"""Bounded per-session sequencing, replay, subscription, and audit delivery."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from queue import Full, Queue
from threading import Condition, Event, Lock, Thread
from time import monotonic
from typing import Callable

from namisync.core.evidence import RecordingStatus
from namisync.core.events import (
    SCHEMA_VERSION,
    DeliveryClass,
    Envelope,
    Gap,
    Progress,
    StateChanged,
    Terminal,
    delivery_class,
)
from namisync.core.session import OperationResult, SessionId, SessionState
from namisync.dispatcher.contracts import AuditObserver


class UtcClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class EventStream:
    """Bounded blocking iterator with nonblocking producer offers."""

    def __init__(
        self,
        session_id: SessionId,
        capacity: int,
        current_state: SessionState,
        initial: tuple[Envelope, ...] = (),
    ) -> None:
        if capacity < 1:
            raise ValueError("subscriber capacity must be positive")
        self.session_id = session_id
        self.current_state = current_state
        self._capacity = capacity
        self._items: deque[Envelope] = deque(initial)
        self._condition = Condition()
        self._closed = False
        self._ejected = False

    @property
    def ejected(self) -> bool:
        with self._condition:
            return self._ejected

    def _offer(self, envelope: Envelope) -> None:
        with self._condition:
            if self._closed:
                return
            if delivery_class(envelope.body) is DeliveryClass.LOSSY:
                for index in range(len(self._items) - 1, -1, -1):
                    if isinstance(self._items[index].body, Progress):
                        del self._items[index]
                        break
                if len(self._items) >= self._capacity:
                    return
                self._items.append(envelope)
                self._condition.notify()
                return
            if len(self._items) >= self._capacity:
                first_missed_seq = envelope.seq
                for pending in self._items:
                    if isinstance(pending.body, Gap):
                        first_missed_seq = min(
                            first_missed_seq, pending.body.first_missed_seq
                        )
                    else:
                        first_missed_seq = min(first_missed_seq, pending.seq)
                self._items.clear()
                self._items.append(
                    Envelope(
                        session_id=envelope.session_id,
                        seq=envelope.seq,
                        at=envelope.at,
                        schema_version=envelope.schema_version,
                        body=Gap(first_missed_seq=first_missed_seq),
                    )
                )
                self._ejected = True
                self._closed = True
                self._condition.notify_all()
                return
            self._items.append(envelope)
            if isinstance(envelope.body, StateChanged):
                self.current_state = envelope.body.state
            self._condition.notify()

    def next(self, timeout: float | None = None) -> Envelope:
        deadline = None if timeout is None else monotonic() + timeout
        with self._condition:
            while not self._items:
                if self._closed:
                    raise StopIteration
                remaining = None if deadline is None else deadline - monotonic()
                if remaining is not None and remaining <= 0:
                    raise TimeoutError("event stream timed out")
                self._condition.wait(remaining)
            return self._items.popleft()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def __iter__(self):
        return self

    def __next__(self) -> Envelope:
        return self.next()


@dataclass(slots=True)
class _Finalize:
    result: OperationResult
    complete: Event
    succeeded: bool = False


class _Stop:
    pass


class _NullAuditObserver:
    def on_event(self, envelope: Envelope) -> None:
        pass

    def finalize(self, result: OperationResult) -> None:
        pass

    def close(self) -> None:
        pass


class _AuditPump:
    def __init__(self, observer: AuditObserver | None, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("audit capacity must be positive")
        self._observer = observer or _NullAuditObserver()
        self._queue: Queue[Envelope | _Finalize | _Stop] = Queue(maxsize=capacity)
        self._degraded = Event()
        self._closed = Event()
        self._thread = Thread(target=self._run, name="namisync-audit", daemon=True)
        self._thread.start()

    @property
    def degraded(self) -> bool:
        return self._degraded.is_set()

    def offer(self, envelope: Envelope, timeout: float) -> None:
        if self.degraded:
            return
        try:
            self._queue.put(envelope, timeout=timeout)
        except Full:
            self._degraded.set()

    def finalize(self, result: OperationResult, timeout: float) -> RecordingStatus:
        if self.degraded:
            try:
                self._queue.put_nowait(_Stop())
            except Full:
                pass
            return RecordingStatus.DEGRADED
        command = _Finalize(result=result, complete=Event())
        deadline = monotonic() + timeout
        try:
            self._queue.put(command, timeout=timeout)
        except Full:
            self._degraded.set()
            return RecordingStatus.DEGRADED
        remaining = deadline - monotonic()
        if remaining <= 0 or not command.complete.wait(remaining):
            self._degraded.set()
            return RecordingStatus.DEGRADED
        if not command.succeeded or self.degraded:
            return RecordingStatus.DEGRADED
        return RecordingStatus.OK

    def close(self, timeout: float) -> bool:
        if self._closed.is_set():
            return True
        try:
            self._queue.put(_Stop(), timeout=timeout)
        except Full:
            self._degraded.set()
            return False
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def _run(self) -> None:
        while True:
            command = self._queue.get()
            try:
                if isinstance(command, _Stop):
                    try:
                        self._observer.close()
                    except BaseException:
                        self._degraded.set()
                    self._closed.set()
                    return
                if isinstance(command, _Finalize):
                    if not self.degraded:
                        try:
                            self._observer.finalize(command.result)
                            self._observer.close()
                            command.succeeded = True
                        except BaseException:
                            self._degraded.set()
                    command.complete.set()
                    self._closed.set()
                    return
                if not self.degraded:
                    try:
                        self._observer.on_event(command)
                    except BaseException:
                        self._degraded.set()
            finally:
                self._queue.task_done()


class EventHub:
    """One session's gap-free sequencer and bounded fan-out."""

    def __init__(
        self,
        *,
        session_id: SessionId,
        initial_state: SessionState,
        clock,
        observer: AuditObserver | None,
        replay_capacity: int,
        subscriber_capacity: int,
        audit_capacity: int,
        audit_timeout: float,
    ) -> None:
        if replay_capacity < 1:
            raise ValueError("replay capacity must be positive")
        if subscriber_capacity < 1:
            raise ValueError("subscriber capacity must be positive")
        if audit_timeout <= 0:
            raise ValueError("audit timeout must be positive")
        self._session_id = session_id
        self._state = initial_state
        self._clock = clock
        self._replay_capacity = replay_capacity
        self._subscriber_capacity = subscriber_capacity
        self._audit_timeout = audit_timeout
        self._replay: deque[Envelope] = deque(maxlen=replay_capacity)
        self._subscribers: list[EventStream] = []
        self._seq = 0
        self._lock = Lock()
        self._audit = _AuditPump(observer, audit_capacity)

    @property
    def audit_degraded(self) -> bool:
        return self._audit.degraded

    def emit(self, body: object) -> Envelope:
        with self._lock:
            self._seq += 1
            envelope = Envelope(
                session_id=self._session_id,
                seq=self._seq,
                at=self._clock.now(),
                schema_version=SCHEMA_VERSION,
                body=body,
            )
            if isinstance(body, StateChanged):
                self._state = body.state
            if isinstance(body, Progress):
                for index in range(len(self._replay) - 1, -1, -1):
                    if isinstance(self._replay[index].body, Progress):
                        del self._replay[index]
                        break
            self._replay.append(envelope)
            if (
                delivery_class(body) is DeliveryClass.RELIABLE
                and not isinstance(body, Terminal)
            ):
                self._audit.offer(envelope, self._audit_timeout)
            live: list[EventStream] = []
            for stream in self._subscribers:
                stream._offer(envelope)
                if not stream.ejected:
                    live.append(stream)
            self._subscribers = live
            return envelope

    def subscribe(self, from_seq: int | None = None) -> EventStream:
        requested = 1 if from_seq is None else from_seq
        if requested < 1:
            raise ValueError("from_seq must be positive")
        with self._lock:
            selected = [event for event in self._replay if event.seq >= requested]
            gap_needed = self._seq >= requested and (
                not selected or selected[0].seq > requested
            )
            allowance = self._subscriber_capacity - (1 if gap_needed else 0)
            if allowance < 0:
                allowance = 0
            if len(selected) > allowance:
                selected = selected[-allowance:] if allowance else []
                gap_needed = True
            initial: list[Envelope] = []
            if gap_needed:
                initial.append(
                    Envelope(
                        session_id=self._session_id,
                        seq=requested,
                        at=self._clock.now(),
                        schema_version=SCHEMA_VERSION,
                        body=Gap(first_missed_seq=requested),
                    )
                )
            initial.extend(selected)
            stream = EventStream(
                self._session_id,
                self._subscriber_capacity,
                self._state,
                tuple(initial),
            )
            self._subscribers.append(stream)
            return stream

    def finalize_audit(self, result: OperationResult) -> RecordingStatus:
        return self._audit.finalize(result, self._audit_timeout)

    def close(self, timeout: float) -> bool:
        with self._lock:
            subscribers = tuple(self._subscribers)
            self._subscribers.clear()
        for stream in subscribers:
            stream.close()
        return self._audit.close(timeout)
