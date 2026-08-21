"""Bounded per-session sequencing, replay, subscription, and audit delivery."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from queue import Empty, Full, Queue
from threading import Condition, Event, Lock, Thread
from time import monotonic
from typing import Callable

from namisync.core.evidence import RecordingStatus
from namisync.core.events import (
    CORE_EVENT_SCHEMA_VERSION,
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


class EventHubCloseStatus(StrEnum):
    """Progress made by one bounded EventHub cleanup attempt."""

    COMPLETE = "complete"
    PUBLICATION_TIMEOUT = "publication-timeout"
    AUDIT_CLEANUP_PENDING = "audit-cleanup-pending"

    def __bool__(self) -> bool:
        """Preserve the former completed/not-completed close check."""

        return self is EventHubCloseStatus.COMPLETE


class EventStream:
    """Bounded blocking iterator with nonblocking producer offers."""

    def __init__(
        self,
        session_id: SessionId,
        capacity: int,
        current_state: SessionState,
        initial: tuple[Envelope, ...] = (),
        on_close: Callable[[EventStream], None] | None = None,
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
        self._on_close = on_close

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
                self._on_close = None
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
        callback = None
        with self._condition:
            if self._closed:
                return
            self._closed = True
            callback = self._on_close
            self._on_close = None
            self._condition.notify_all()
        if callback is not None:
            callback(self)

    def _close_from_hub(self) -> None:
        """Close after the owning hub has already detached this stream."""

        with self._condition:
            self._closed = True
            self._on_close = None
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
    recording: RecordingStatus = RecordingStatus.DEGRADED
    _lock: Lock = field(default_factory=Lock, repr=False)
    _decided: bool = False
    _timed_out: bool = False

    def claim(self, timed_out: bool) -> bool:
        with self._lock:
            if self._decided:
                return False
            self._decided = True
            self._timed_out = timed_out
            return True

    @property
    def timed_out(self) -> bool:
        with self._lock:
            if not self._decided:
                raise RuntimeError("audit finalization is not decided")
            return self._timed_out


class _Stop:
    pass


@dataclass(slots=True)
class _Flush:
    complete: Event
    succeeded: bool = False


class _NullAuditObserver:
    def on_event(self, envelope: Envelope) -> RecordingStatus:
        return RecordingStatus.OK

    def flush(self) -> None:
        pass

    def finalize(self, result: OperationResult) -> RecordingStatus:
        return result.audit

    def close(self) -> None:
        pass


class _AuditPump:
    def __init__(
        self,
        observer: AuditObserver | None,
        capacity: int,
        flush_interval: float,
    ) -> None:
        if capacity < 1:
            raise ValueError("audit capacity must be positive")
        if flush_interval <= 0:
            raise ValueError("audit flush interval must be positive")
        self._observer = observer or _NullAuditObserver()
        self._queue: Queue[Envelope | _Flush | _Finalize | _Stop] = Queue(
            maxsize=capacity
        )
        self._flush_interval = flush_interval
        self._degraded = Event()
        self._prefix_broken = Event()
        self._closed = Event()
        self._submission_condition = Condition()
        self._accepting = True
        self._active_submissions = 0
        self._thread = Thread(target=self._run, name="namisync-audit", daemon=True)
        self._thread.start()

    @property
    def degraded(self) -> bool:
        return self._degraded.is_set()

    def offer(self, envelope: Envelope, timeout: float) -> None:
        if self._prefix_broken.is_set():
            return
        accepted, full = self._enqueue(envelope, timeout)
        if not accepted and full:
            self._break_prefix()

    def finalize(self, result: OperationResult, timeout: float) -> RecordingStatus:
        if self._prefix_broken.is_set():
            self._enqueue(_Stop(), 0.0)
            return RecordingStatus.DEGRADED
        command = _Finalize(result=result, complete=Event())
        deadline = monotonic() + timeout
        accepted, _ = self._enqueue(command, timeout)
        if not accepted:
            self._degraded.set()
            return RecordingStatus.DEGRADED
        remaining = deadline - monotonic()
        if remaining > 0 and command.complete.wait(remaining):
            return self._final_status(command)
        if command.claim(timed_out=True):
            self._degraded.set()
            return RecordingStatus.DEGRADED
        # Pump ownership still waits because scheduling/SQLite calls can outlive a retry bound.
        command.complete.wait()
        return self._final_status(command)

    def flush(self, timeout: float) -> RecordingStatus:
        if self._prefix_broken.is_set():
            return RecordingStatus.DEGRADED
        command = _Flush(complete=Event())
        deadline = monotonic() + timeout
        accepted, full = self._enqueue(command, timeout)
        if not accepted:
            self._degraded.set()
            if full:
                self._break_prefix()
            return RecordingStatus.DEGRADED
        remaining = deadline - monotonic()
        if remaining > 0 and command.complete.wait(remaining):
            return (
                RecordingStatus.OK
                if command.succeeded and not self.degraded
                else RecordingStatus.DEGRADED
            )
        self._break_prefix()
        return RecordingStatus.DEGRADED

    def _final_status(self, command: _Finalize) -> RecordingStatus:
        if not command.succeeded:
            return RecordingStatus.DEGRADED
        return command.recording

    def close(self, timeout: float) -> bool:
        if self._closed.is_set():
            return True
        deadline = monotonic() + timeout
        remaining = max(0.0, deadline - monotonic())
        accepted, full = self._enqueue(_Stop(), remaining)
        if not accepted and full:
            self._degraded.set()
        remaining = max(0.0, deadline - monotonic())
        self._thread.join(remaining)
        return not self._thread.is_alive()

    def _enqueue(
        self,
        command: Envelope | _Flush | _Finalize | _Stop,
        timeout: float,
    ) -> tuple[bool, bool]:
        """Return ``(accepted, queue_full)`` under the close/admission gate."""

        with self._submission_condition:
            if not self._accepting:
                return False, False
            self._active_submissions += 1
        try:
            try:
                self._queue.put(command, timeout=timeout)
            except Full:
                return False, True
            return True, False
        finally:
            with self._submission_condition:
                self._active_submissions -= 1
                self._submission_condition.notify_all()

    def _break_prefix(self) -> None:
        self._degraded.set()
        self._prefix_broken.set()
        # The worker may have passed its last prefix check just as the caller
        # detected overflow/timeout. Wake an otherwise idle Queue.get; if the
        # queue is full, its existing command provides the same wakeup.
        self._enqueue(_Stop(), 0.0)

    def _run(self) -> None:
        flush_deadline: float | None = None
        try:
            while True:
                timeout = None
                if flush_deadline is not None:
                    timeout = max(0.0, flush_deadline - monotonic())
                try:
                    command = self._queue.get(timeout=timeout)
                except Empty:
                    if not self._flush():
                        return
                    flush_deadline = None
                    continue
                try:
                    if isinstance(command, _Stop):
                        if not self._prefix_broken.is_set():
                            self._flush()
                        return
                    if isinstance(command, _Finalize):
                        self._finalize(command)
                        return
                    if isinstance(command, _Flush):
                        if self._prefix_broken.is_set():
                            command.complete.set()
                            return
                        command.succeeded = self._flush()
                        command.complete.set()
                        flush_deadline = None
                        if (
                            not command.succeeded
                            or self._prefix_broken.is_set()
                        ):
                            return
                        continue
                    if self._prefix_broken.is_set():
                        return
                    if (
                        flush_deadline is not None
                        and monotonic() >= flush_deadline
                    ):
                        if not self._flush():
                            return
                        flush_deadline = None
                    if flush_deadline is None:
                        flush_deadline = monotonic() + self._flush_interval
                    try:
                        status = self._observer.on_event(command)
                        if not isinstance(status, RecordingStatus):
                            raise TypeError(
                                "audit observer returned an invalid status"
                            )
                    except BaseException:
                        self._degraded.set()
                        self._prefix_broken.set()
                        return
                    if status is RecordingStatus.DEGRADED:
                        self._degraded.set()
                    if self._prefix_broken.is_set():
                        return
                    if monotonic() >= flush_deadline:
                        if not self._flush():
                            return
                        flush_deadline = None
                finally:
                    self._queue.task_done()
        finally:
            with self._submission_condition:
                self._accepting = False
                while self._active_submissions:
                    self._drain_queue()
                    self._submission_condition.wait()
                self._drain_queue()
            try:
                self._observer.close()
            except BaseException:
                self._degraded.set()
            finally:
                self._closed.set()

    def _drain_queue(self) -> None:
        while True:
            try:
                command = self._queue.get_nowait()
            except Empty:
                return
            try:
                if isinstance(command, (_Flush, _Finalize)):
                    command.complete.set()
            finally:
                self._queue.task_done()

    def _flush(self) -> bool:
        try:
            self._observer.flush()
        except BaseException:
            self._degraded.set()
            self._prefix_broken.set()
            return False
        return True

    def _finalize(self, command: _Finalize) -> None:
        result = command.result
        pump_owned = command.claim(timed_out=False)
        if self._prefix_broken.is_set():
            command.complete.set()
            return
        if self.degraded or (not pump_owned and command.timed_out):
            result = replace(result, audit=RecordingStatus.DEGRADED)
        try:
            status = self._observer.finalize(result)
            if not isinstance(status, RecordingStatus):
                raise TypeError("audit observer returned an invalid status")
        except BaseException:
            self._degraded.set()
            self._prefix_broken.set()
        else:
            command.recording = (
                RecordingStatus.DEGRADED
                if RecordingStatus.DEGRADED in (result.audit, status)
                else RecordingStatus.OK
            )
            if command.recording is RecordingStatus.DEGRADED:
                self._degraded.set()
            command.succeeded = True
        command.complete.set()


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
        audit_offer_timeout: float,
        audit_flush_interval: float = 1.0,
    ) -> None:
        if replay_capacity < 1:
            raise ValueError("replay capacity must be positive")
        if subscriber_capacity < 1:
            raise ValueError("subscriber capacity must be positive")
        if audit_timeout <= 0:
            raise ValueError("audit timeout must be positive")
        if audit_offer_timeout <= 0:
            raise ValueError("audit offer timeout must be positive")
        if audit_flush_interval <= 0:
            raise ValueError("audit flush interval must be positive")
        self._session_id = session_id
        self._state = initial_state
        self._clock = clock
        self._replay_capacity = replay_capacity
        self._subscriber_capacity = subscriber_capacity
        self._audit_timeout = audit_timeout
        self._audit_offer_timeout = audit_offer_timeout
        self._replay: deque[Envelope] = deque(maxlen=replay_capacity)
        self._subscribers: list[EventStream] = []
        self._seq = 0
        self._lock = Lock()
        self._subscriptions_closed = False
        self._detached = Event()
        self._audit = _AuditPump(observer, audit_capacity, audit_flush_interval)

    @property
    def audit_degraded(self) -> bool:
        return self._audit.degraded

    @property
    def detached(self) -> bool:
        """Whether stream/replay cleanup crossed its irreversible boundary."""

        return self._detached.is_set()

    def emit(
        self,
        body: object,
        *,
        audit_offer_timeout: float | None = None,
    ) -> Envelope:
        if audit_offer_timeout is not None and audit_offer_timeout < 0:
            raise ValueError("audit offer timeout cannot be negative")
        with self._lock:
            return self._emit_reserved(
                body,
                audit_offer_timeout=audit_offer_timeout,
            )

    def _reserve_publication(self, timeout: float) -> bool:
        if timeout < 0:
            raise ValueError("publication timeout cannot be negative")
        return self._lock.acquire(timeout=timeout)

    def _release_publication(self) -> None:
        self._lock.release()

    def _emit_reserved(
        self,
        body: object,
        *,
        audit_offer_timeout: float | None = None,
    ) -> Envelope:
        """Emit while the caller owns the hub publication reservation."""

        if audit_offer_timeout is not None and audit_offer_timeout < 0:
            raise ValueError("audit offer timeout cannot be negative")
        self._seq += 1
        envelope = Envelope(
            session_id=self._session_id,
            seq=self._seq,
            at=self._clock.now(),
            schema_version=CORE_EVENT_SCHEMA_VERSION,
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
            # Producer backpressure, not durable finalization: this bound
            # exists only to stop a wedged audit writer from stalling the
            # emitting workflow thread, so it is deliberately independent
            # of the finalization cutoff that must outlast a writer retry.
            offer_timeout = (
                self._audit_offer_timeout
                if audit_offer_timeout is None
                else min(self._audit_offer_timeout, audit_offer_timeout)
            )
            self._audit.offer(envelope, offer_timeout)
            if (
                isinstance(body, StateChanged)
                and body.state is SessionState.PAUSED
            ):
                self._audit.flush(self._audit_timeout)
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
            if self._subscriptions_closed:
                raise RuntimeError("event hub is closed")
            selected = [event for event in self._replay if event.seq >= requested]
            gap_needed = self._seq >= requested and (
                not selected or selected[0].seq > requested
            )
            allowance = self._subscriber_capacity - (1 if gap_needed else 0)
            if allowance < 0:
                allowance = 0
            if len(selected) > allowance:
                # Truncating the tail is itself what creates the gap, so the
                # gap envelope must claim a slot inside the subscriber bound
                # instead of being handed out on top of a full buffer.
                gap_needed = True
                allowance = max(0, self._subscriber_capacity - 1)
                selected = selected[-allowance:] if allowance else []
            initial: list[Envelope] = []
            if gap_needed:
                initial.append(
                    Envelope(
                        session_id=self._session_id,
                        seq=requested,
                        at=self._clock.now(),
                        schema_version=CORE_EVENT_SCHEMA_VERSION,
                        body=Gap(first_missed_seq=requested),
                    )
                )
            initial.extend(selected)
            stream = EventStream(
                self._session_id,
                self._subscriber_capacity,
                self._state,
                tuple(initial),
                self._unsubscribe,
            )
            self._subscribers.append(stream)
            return stream

    def _unsubscribe(self, stream: EventStream) -> None:
        with self._lock:
            self._subscribers = [
                candidate
                for candidate in self._subscribers
                if candidate is not stream
            ]

    def finalize_audit(self, result: OperationResult) -> RecordingStatus:
        return self._audit.finalize(result, self._audit_timeout)

    def close(self, timeout: float) -> EventHubCloseStatus:
        if timeout < 0:
            raise ValueError("close timeout cannot be negative")
        deadline = monotonic() + timeout
        remaining = max(0.0, deadline - monotonic())
        if not self._lock.acquire(timeout=remaining):
            if self.detached:
                return EventHubCloseStatus.AUDIT_CLEANUP_PENDING
            return EventHubCloseStatus.PUBLICATION_TIMEOUT
        try:
            subscribers = tuple(self._subscribers)
            self._subscribers.clear()
            self._replay.clear()
            for stream in subscribers:
                stream._close_from_hub()
            self._subscriptions_closed = True
            self._detached.set()
        finally:
            self._lock.release()

        return self._finish_audit_close(deadline)

    def _finish_audit_close(self, deadline: float) -> EventHubCloseStatus:
        remaining = max(0.0, deadline - monotonic())
        if self._audit.close(remaining):
            return EventHubCloseStatus.COMPLETE
        return EventHubCloseStatus.AUDIT_CLEANUP_PENDING
