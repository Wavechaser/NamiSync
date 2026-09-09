"""Service-owned lifetime for dispatcher event-stream subscriptions."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Lock, Thread, current_thread
from time import monotonic
from typing import Callable, Never

from namisync.dispatcher import (
    Dispatcher,
    EventStream,
    SessionCleanupPending,
    SessionNotFound,
    retire_exception_graph,
)
from namisync.workflows.views import (
    SessionEventView,
    SessionRecordView,
    session_event_view,
    session_record_view,
)


SessionUpdate = SessionEventView | SessionRecordView
SessionSink = Callable[[SessionUpdate], None]

_OBSERVER_CLEANUP_FAILURE = "session observer cleanup failed"
_OBSERVER_CLEANUP_INTERRUPTED = "session observer cleanup was interrupted"
_OBSERVER_JOIN_TIMEOUT = "session observers did not stop"
_OBSERVER_FAILURE_ORDINARY = "ordinary"
_OBSERVER_FAILURE_TIMEOUT = "timeout"
_OBSERVER_FAILURE_INTERRUPTED = "interrupted"


def _classify_observer_join_failure(error: BaseException) -> str:
    if isinstance(error, TimeoutError):
        return _OBSERVER_FAILURE_TIMEOUT
    if not isinstance(error, Exception):
        return _OBSERVER_FAILURE_INTERRUPTED
    return _OBSERVER_FAILURE_ORDINARY


def _raise_observer_cleanup_failure(failure_code: str) -> Never:
    if failure_code == _OBSERVER_FAILURE_TIMEOUT:
        raise TimeoutError(_OBSERVER_JOIN_TIMEOUT) from None
    if failure_code == _OBSERVER_FAILURE_INTERRUPTED:
        raise KeyboardInterrupt(_OBSERVER_CLEANUP_INTERRUPTED) from None
    if failure_code == _OBSERVER_FAILURE_ORDINARY:
        raise RuntimeError(_OBSERVER_CLEANUP_FAILURE) from None
    raise RuntimeError("observer cleanup failure code is invalid") from None


@dataclass(slots=True, eq=False)
class SessionSubscription:
    """One private physical observation owned by ``SessionObserver``."""

    session_id: str
    sink: SessionSink
    stream: EventStream
    from_sequence: int = 1
    stop: Event = field(default_factory=Event)
    done: Event = field(default_factory=Event)
    thread: Thread | None = None
    failed: bool = False


class SessionObserver:
    """Translate blocking dispatcher streams into sink-delivered views."""

    def __init__(self, dispatcher: Dispatcher, *, join_timeout: float = 2.0) -> None:
        if join_timeout <= 0:
            raise ValueError("observer join timeout must be positive")
        self._dispatcher = dispatcher
        self._join_timeout = join_timeout
        self._lock = Lock()
        self._subscriptions: dict[str, SessionSubscription] = {}
        self._retiring_subscriptions: dict[int, SessionSubscription] = {}
        self._closed = False

    def observe(self, session_id: str, sink: SessionSink) -> SessionRecordView:
        with self._lock:
            if self._closed:
                raise RuntimeError("session observer is closed")
            if session_id in self._subscriptions:
                raise ValueError(f"session is already observed: {session_id}")

        record = self._dispatcher.get(session_id)
        current = session_record_view(record)
        if current.result is not None:
            return current

        try:
            stream = self._dispatcher.subscribe(session_id)
        except (SessionCleanupPending, SessionNotFound):
            finished = session_record_view(self._dispatcher.get(session_id))
            if finished.result is None:
                raise
            return finished
        self.adopt(session_id, sink, stream)
        return current

    def adopt(
        self,
        session_id: str,
        sink: SessionSink,
        stream: EventStream,
        *,
        from_sequence: int = 1,
    ) -> None:
        """Adopt a preopened stream, closing it when adoption is rejected."""

        try:
            if not callable(sink):
                raise TypeError("session sink must be callable")
            self._require_positive_sequence(from_sequence)
        except BaseException:
            stream.close()
            raise
        subscription = SessionSubscription(
            session_id=session_id,
            sink=sink,
            stream=stream,
            from_sequence=from_sequence,
        )
        thread = Thread(
            target=self._run,
            args=(subscription,),
            name=f"namisync-observer-{session_id}",
            daemon=True,
        )
        subscription.thread = thread
        try:
            with self._lock:
                if self._closed:
                    raise RuntimeError("session observer is closed")
                if session_id in self._subscriptions:
                    raise ValueError(
                        f"session is already observed: {session_id}"
                    )
                self._subscriptions[session_id] = subscription
                try:
                    thread.start()
                except BaseException:
                    if self._subscriptions.get(session_id) is subscription:
                        self._subscriptions.pop(session_id, None)
                    raise
        except BaseException:
            with self._lock:
                subscription.stop.set()
            stream.close()
            raise

    def reobserve(
        self,
        session_id: str,
        sink: SessionSink,
        from_sequence: int,
    ) -> SessionRecordView:
        """Replace one subscription and replay from a positive first sequence."""

        if not callable(sink):
            raise TypeError("session sink must be callable")
        self._require_positive_sequence(from_sequence)
        self.release(session_id)
        with self._lock:
            if self._closed:
                raise RuntimeError("session observer is closed")

        record = self._dispatcher.get(session_id)
        current = session_record_view(record)
        if current.result is not None:
            return current
        try:
            stream = self._dispatcher.subscribe(session_id, from_sequence)
        except (SessionCleanupPending, SessionNotFound):
            finished = session_record_view(self._dispatcher.get(session_id))
            if finished.result is None:
                raise
            return finished
        self.adopt(
            session_id,
            sink,
            stream,
            from_sequence=from_sequence,
        )
        return current

    def release(self, session_id: str) -> None:
        """Idempotently release every physical subscription for the session."""

        with self._lock:
            active = self._subscriptions.get(session_id)
            subscriptions = (
                (() if active is None else (active,))
                + tuple(
                    subscription
                    for subscription in self._retiring_subscriptions.values()
                    if subscription.session_id == session_id
                    and subscription is not active
                )
            )
        if not subscriptions:
            return
        try:
            self._release_subscriptions(subscriptions)
        finally:
            del active, subscriptions

    def _release_subscription(self, subscription: SessionSubscription) -> None:
        try:
            self._release_subscriptions((subscription,))
        finally:
            del subscription

    def _release_subscriptions(
        self,
        subscriptions: tuple[SessionSubscription, ...],
    ) -> None:
        with self._lock:
            for subscription in subscriptions:
                subscription.stop.set()
            if subscriptions:
                del subscription
        close_failed = self._close_streams(subscriptions)
        join_failure = self._join_and_retire(subscriptions)
        del subscriptions
        if join_failure is not None:
            _raise_observer_cleanup_failure(join_failure)
        if close_failed:
            _raise_observer_cleanup_failure(_OBSERVER_FAILURE_ORDINARY)

    def wait(self, session_id: str) -> SessionRecordView:
        with self._lock:
            subscription = self._subscriptions.get(session_id)
        if subscription is None:
            current = session_record_view(self._dispatcher.get(session_id))
            if current.result is not None:
                return current
            raise KeyError(f"session is not observed: {session_id}")
        subscription.done.wait()
        if subscription.failed:
            raise RuntimeError("session observation failed") from None
        current = session_record_view(self._dispatcher.get(session_id))
        if current.result is None:
            raise RuntimeError(
                f"session observation stopped before terminal: {session_id}"
            )
        return current

    def close(self) -> None:
        with self._lock:
            if (
                self._closed
                and not self._subscriptions
                and not self._retiring_subscriptions
            ):
                return
            self._closed = True
            active = tuple(self._subscriptions.values())
            subscriptions = active + tuple(
                subscription
                for subscription in self._retiring_subscriptions.values()
                if subscription not in active
            )
            for subscription in subscriptions:
                subscription.stop.set()
            if subscriptions:
                del subscription
        close_failed = self._close_streams(subscriptions)
        join_failure = self._join_and_retire(subscriptions)
        del active, subscriptions
        if join_failure is not None:
            _raise_observer_cleanup_failure(join_failure)
        if close_failed:
            _raise_observer_cleanup_failure(_OBSERVER_FAILURE_ORDINARY)

    def _run(self, subscription: SessionSubscription) -> None:
        stream = subscription.stream
        next_sequence = subscription.from_sequence
        try:
            while not subscription.stop.is_set():
                try:
                    envelope = stream.next()
                except StopIteration:
                    if subscription.stop.is_set():
                        return
                    record = session_record_view(
                        self._dispatcher.get(subscription.session_id)
                    )
                    if record.result is not None:
                        subscription.sink(record)
                        return
                    replacement = self._dispatcher.subscribe(
                        subscription.session_id, next_sequence
                    )
                    with self._lock:
                        rejected = (
                            self._closed
                            or subscription.stop.is_set()
                            or self._subscriptions.get(subscription.session_id)
                            is not subscription
                        )
                        if not rejected:
                            subscription.stream = replacement
                    if rejected:
                        replacement.close()
                        return
                    stream.close()
                    stream = replacement
                    continue

                event = session_event_view(envelope)
                if event.body_type == "Gap":
                    missed = event.body.get("first_missed_seq")
                    if isinstance(missed, int):
                        next_sequence = max(next_sequence, missed)
                else:
                    next_sequence = max(next_sequence, event.sequence + 1)
                subscription.sink(event)
                if event.body_type == "Terminal":
                    subscription.sink(
                        session_record_view(
                            self._dispatcher.get(subscription.session_id)
                        )
                    )
                    return
        except BaseException as error:
            retire_exception_graph(error)
            subscription.failed = True
        finally:
            if self._close_streams((subscription,)):
                subscription.failed = True
            subscription.done.set()
            self._retire_finished_subscription(subscription)

    @staticmethod
    def _require_positive_sequence(from_sequence: int) -> None:
        if (
            isinstance(from_sequence, bool)
            or not isinstance(from_sequence, int)
            or from_sequence < 1
        ):
            raise ValueError("from_sequence must be a positive integer")

    def _close_streams(
        self,
        subscriptions: tuple[SessionSubscription, ...],
    ) -> bool:
        with self._lock:
            streams = tuple(
                (subscription, subscription.stream)
                for subscription in subscriptions
            )
        failed = False
        for subscription, stream in streams:
            try:
                stream.close()
            except BaseException as error:
                retire_exception_graph(error)
                subscription.failed = True
                failed = True
        return failed

    def _retire_stopped_subscriptions(
        self,
        subscriptions: tuple[SessionSubscription, ...],
    ) -> None:
        with self._lock:
            for subscription in subscriptions:
                thread = subscription.thread
                if thread is current_thread() and thread.is_alive():
                    if (
                        self._subscriptions.get(subscription.session_id)
                        is subscription
                    ):
                        self._subscriptions.pop(subscription.session_id, None)
                    self._retiring_subscriptions[id(subscription)] = subscription
                elif thread is None or not thread.is_alive():
                    if (
                        self._subscriptions.get(subscription.session_id)
                        is subscription
                    ):
                        self._subscriptions.pop(subscription.session_id, None)
                    self._retiring_subscriptions.pop(id(subscription), None)

    def _retire_finished_subscription(
        self,
        subscription: SessionSubscription,
    ) -> None:
        if not subscription.stop.is_set():
            return
        with self._lock:
            if (
                self._subscriptions.get(subscription.session_id)
                is subscription
            ):
                self._subscriptions.pop(subscription.session_id, None)
            self._retiring_subscriptions.pop(id(subscription), None)

    def _join_and_retire(
        self,
        subscriptions: tuple[SessionSubscription, ...],
    ) -> str | None:
        join_failure: str | None = None
        try:
            self._join_threads(subscriptions)
        except BaseException as error:
            join_failure = _classify_observer_join_failure(error)
            retire_exception_graph(error)
        finally:
            self._retire_stopped_subscriptions(subscriptions)
        return join_failure

    def _join_threads(
        self,
        subscriptions: tuple[SessionSubscription, ...],
    ) -> None:
        deadline = monotonic() + self._join_timeout
        alive: list[str] = []
        for subscription in subscriptions:
            thread = subscription.thread
            if thread is None or thread is current_thread():
                continue
            thread.join(max(0.0, deadline - monotonic()))
            if thread.is_alive():
                alive.append(subscription.session_id)
        if alive:
            joined = ", ".join(sorted(alive))
            raise TimeoutError(f"session observers did not stop: {joined}")


__all__ = ["SessionObserver", "SessionSink", "SessionUpdate"]
