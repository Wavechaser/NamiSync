"""Domain-blind M0 session admission, scheduling, control, and custody."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from threading import Condition, Lock, Thread
from time import monotonic
from typing import Callable
from uuid import uuid4

from namisync.core.evidence import RecordingStatus
from namisync.core.events import StateChanged
from namisync.core.session import (
    Canceled,
    Disposition,
    OperationResult,
    PauseRequested,
    ResourceId,
    ResultItem,
    SessionId,
    SessionRecord,
    SessionState,
    SessionStore,
    is_terminal,
    require_transition,
    result_terminal_state,
    run_session,
)
from namisync.dispatcher.contracts import (
    AdmissionClosed,
    AuditObserverFactory,
    ControlCode,
    ControlAction,
    ControlResult,
    Registry,
    SessionCleanupPending,
    SessionNotFound,
    SessionNotTerminal,
    ShutdownResult,
    UnknownWorkflowKind,
    WorkflowInvocation,
    WorkflowRegistration,
    control_decision,
)
from namisync.dispatcher.custody import (
    ResourceLease,
    ResourceLockProvider,
    default_lock_provider,
)
from namisync.dispatcher.event_bus import (
    EventHub,
    EventHubCloseStatus,
    EventStream,
    UtcClock,
)
from namisync.dispatcher.store import InMemorySessionStore


_AdmissionRollback = Callable[[], None]
_AdmissionAttach = Callable[[SessionId, EventStream], _AdmissionRollback]


class _Control:
    def __init__(self) -> None:
        self._pause = False
        self._cancel = False
        self._lock = Lock()

    def request_pause(self) -> None:
        with self._lock:
            self._pause = True

    def request_cancel(self) -> None:
        with self._lock:
            self._cancel = True

    def reset(self) -> None:
        with self._lock:
            self._pause = False
            self._cancel = False

    def cancel_requested(self) -> bool:
        with self._lock:
            return self._cancel

    def checkpoint(self) -> None:
        with self._lock:
            cancel = self._cancel
            pause = self._pause
        if cancel:
            raise Canceled()
        if pause:
            raise PauseRequested()


class _DegradedAuditObserver:
    """Sentinel that projects observer-construction failure onto audit status."""

    def __init__(self, failure: BaseException) -> None:
        self._failure = failure

    def on_event(self, envelope) -> RecordingStatus:
        raise RuntimeError("audit observer is unavailable") from self._failure

    def flush(self) -> None:
        pass

    def finalize(self, result: OperationResult) -> RecordingStatus:
        raise RuntimeError("audit observer is unavailable") from self._failure

    def close(self) -> None:
        pass


@dataclass(frozen=True, slots=True)
class _WorkerKey:
    session_id: SessionId
    generation: int


@dataclass(frozen=True, slots=True)
class _WorkerAttempt:
    key: _WorkerKey
    resources: tuple[ResourceId, ...]
    thread: Thread


@dataclass(slots=True)
class _AdmissionCleanup:
    """Retained ownership for an unpublished admission that failed cleanup."""

    session_id: SessionId
    hub: EventHub
    stream: EventStream | None
    rollback: _AdmissionRollback | None
    rollback_done: bool
    stream_done: bool
    hub_done: bool
    store_done: bool
    failures: tuple[BaseException, ...] = ()

    @property
    def complete(self) -> bool:
        return (
            self.rollback_done
            and self.stream_done
            and self.hub_done
            and self.store_done
        )


class _StaleWorkerAttempt(BaseException):
    """Stop a superseded private worker without creating a second result."""


class Dispatcher:
    """Schedule generic registered sessions by their required resources."""

    def __init__(
        self,
        registry: Registry,
        *,
        store: SessionStore | None = None,
        lock_provider: ResourceLockProvider | None = None,
        clock=None,
        audit_observer_factory: AuditObserverFactory | None = None,
        replay_capacity: int = 128,
        subscriber_capacity: int = 64,
        audit_capacity: int = 64,
        audit_timeout: float = 5.0,
        audit_offer_timeout: float = 5.0,
        audit_flush_interval: float = 1.0,
    ) -> None:
        self._registry = dict(registry)
        self._store = store if store is not None else InMemorySessionStore()
        self._lock_provider = (
            lock_provider if lock_provider is not None else default_lock_provider()
        )
        self._clock = clock if clock is not None else UtcClock()
        self._audit_factory = audit_observer_factory or (lambda record: None)
        self._replay_capacity = replay_capacity
        self._subscriber_capacity = subscriber_capacity
        self._audit_capacity = audit_capacity
        self._audit_timeout = audit_timeout
        self._audit_offer_timeout = audit_offer_timeout
        self._audit_flush_interval = audit_flush_interval

        self._condition = Condition()
        self._records: dict[SessionId, SessionRecord] = {}
        self._controls: dict[SessionId, _Control] = {}
        self._hubs: dict[SessionId, EventHub] = {}
        self._state_publication_locks: dict[SessionId, Lock] = {}
        self._closing: set[SessionId] = set()
        self._cleanup_irreversible: set[SessionId] = set()
        self._item_events: dict[SessionId, list[ResultItem]] = {}
        self._pending: deque[SessionId] = deque()
        self._worker_generation = 0
        self._reserved: dict[ResourceId, _WorkerKey] = {}
        self._leases: dict[_WorkerKey, ResourceLease] = {}
        self._workers: dict[_WorkerKey, _WorkerAttempt] = {}
        self._current_workers: dict[SessionId, _WorkerKey] = {}
        self._admitting = 0
        self._admission_order = 0
        self._accepting = True
        self._admission_cleanups: dict[SessionId, _AdmissionCleanup] = {}
        self._store_failures: list[BaseException] = []
        self._custody_failures: list[BaseException] = []
        self._scheduler = Thread(
            target=self._schedule,
            name="namisync-dispatcher",
            daemon=True,
        )
        self._scheduler.start()

    def submit(
        self,
        kind: str,
        request: object,
        *,
        attach: _AdmissionAttach | None = None,
    ) -> SessionId:
        with self._condition:
            if not self._accepting:
                raise AdmissionClosed("dispatcher is no longer accepting sessions")
            registration = self._registry.get(kind)
            if registration is not None:
                self._admitting += 1
        if registration is None:
            raise UnknownWorkflowKind(kind)
        try:
            return self._admit(kind, request, registration, attach=attach)
        finally:
            with self._condition:
                self._admitting -= 1
                self._condition.notify_all()

    def _admit(
        self,
        kind: str,
        request: object,
        registration: WorkflowRegistration,
        *,
        attach: _AdmissionAttach | None,
    ) -> SessionId:
        prepared = registration.prepare(request)
        resources = tuple(sorted(prepared.resources))
        session_id = SessionId(uuid4().hex)
        created_at = self._now()
        with self._condition:
            admission_order = self._admission_order
            self._admission_order += 1
        record = SessionRecord(
            session_id=session_id,
            kind=kind,
            state=SessionState.PENDING,
            resources=resources,
            payload=prepared.payload,
            supports_pause=registration.supports_pause,
            admission_order=admission_order,
            created_at=created_at,
        )
        try:
            observer = self._audit_factory(record)
        except BaseException as error:
            observer = _DegradedAuditObserver(error)
        hub = EventHub(
            session_id=session_id,
            initial_state=record.state,
            clock=self._clock,
            observer=observer,
            replay_capacity=self._replay_capacity,
            subscriber_capacity=self._subscriber_capacity,
            audit_capacity=self._audit_capacity,
            audit_timeout=self._audit_timeout,
            audit_offer_timeout=self._audit_offer_timeout,
            audit_flush_interval=self._audit_flush_interval,
        )
        stream: EventStream | None = None
        rollback: _AdmissionRollback | None = None
        store_touched = False
        publication_lock = Lock()
        try:
            store_touched = True
            self._store.put(record)
            if attach is not None:
                stream = hub.subscribe()
                attached_rollback = attach(session_id, stream)
                if not callable(attached_rollback):
                    raise TypeError(
                        "admission attach callback must return a rollback callback"
                    )
                rollback = attached_rollback
            with publication_lock:
                with self._condition:
                    if not self._accepting:
                        raise AdmissionClosed(
                            "dispatcher stopped during admission"
                        )
                    # Keep the acceptance decision, first observable event,
                    # and map/pending publication in one transaction.  An
                    # adopted sink may react to PENDING immediately; any
                    # dispatcher lookup it makes must wait until publication
                    # completes instead of observing an unpublished session.
                    hub.emit(StateChanged(SessionState.PENDING))
                    try:
                        self._records[session_id] = record
                        self._controls[session_id] = _Control()
                        self._hubs[session_id] = hub
                        self._state_publication_locks[session_id] = publication_lock
                        self._item_events[session_id] = []
                        self._pending.append(session_id)
                    except BaseException:
                        self._pending = deque(
                            item for item in self._pending if item != session_id
                        )
                        self._item_events.pop(session_id, None)
                        self._state_publication_locks.pop(session_id, None)
                        self._hubs.pop(session_id, None)
                        self._controls.pop(session_id, None)
                        self._records.pop(session_id, None)
                        raise
                    self._condition.notify_all()
        except BaseException:
            cleanup = _AdmissionCleanup(
                session_id=session_id,
                hub=hub,
                stream=stream,
                rollback=rollback,
                rollback_done=rollback is None,
                stream_done=stream is None,
                hub_done=False,
                store_done=not store_touched,
            )
            self._attempt_admission_cleanup(cleanup, self._audit_timeout)
            if not cleanup.complete:
                with self._condition:
                    self._admission_cleanups[session_id] = cleanup
                    self._condition.notify_all()
            raise
        return session_id

    def _attempt_admission_cleanup(
        self,
        cleanup: _AdmissionCleanup,
        timeout: float,
    ) -> None:
        failures: list[BaseException] = []
        if not cleanup.rollback_done:
            assert cleanup.rollback is not None
            try:
                cleanup.rollback()
            except BaseException as error:
                failures.append(error)
            else:
                cleanup.rollback_done = True
        if not cleanup.stream_done:
            assert cleanup.stream is not None
            try:
                cleanup.stream.close()
            except BaseException as error:
                failures.append(error)
            else:
                cleanup.stream_done = True
        if not cleanup.hub_done:
            try:
                close_status = cleanup.hub.close(timeout)
            except BaseException as error:
                failures.append(error)
            else:
                if close_status is EventHubCloseStatus.COMPLETE:
                    cleanup.hub_done = True
                else:
                    failures.append(
                        TimeoutError(
                            "failed admission event cleanup remains pending: "
                            f"{cleanup.session_id}"
                        )
                    )
        if not cleanup.store_done:
            try:
                self._store.drop(cleanup.session_id)
            except BaseException as error:
                failures.append(error)
            else:
                cleanup.store_done = True
        cleanup.failures = tuple(failures)

    def _retry_admission_cleanups(self, deadline: float) -> None:
        with self._condition:
            pending = tuple(self._admission_cleanups.values())
        for cleanup in pending:
            self._attempt_admission_cleanup(
                cleanup,
                max(0.0, deadline - monotonic()),
            )
            if cleanup.complete:
                with self._condition:
                    if self._admission_cleanups.get(cleanup.session_id) is cleanup:
                        self._admission_cleanups.pop(cleanup.session_id, None)
                    self._condition.notify_all()

    def get(self, session_id: SessionId) -> SessionRecord:
        with self._condition:
            try:
                return self._records[session_id]
            except KeyError:
                raise SessionNotFound(str(session_id)) from None

    def list(
        self, query: Callable[[SessionRecord], bool] | None = None
    ) -> tuple[SessionRecord, ...]:
        with self._condition:
            records = tuple(
                sorted(self._records.values(), key=lambda item: item.admission_order)
            )
        if query is None:
            return records
        return tuple(record for record in records if query(record))

    def subscribe(
        self, session_id: SessionId, from_seq: int | None = None
    ) -> EventStream:
        with self._condition:
            while (
                session_id in self._closing
                and self._accepting
                and session_id not in self._cleanup_irreversible
            ):
                self._condition.wait()
            if session_id in self._closing:
                raise self._cleanup_pending(session_id)
            publication_lock = self._state_publication_locks.get(session_id)
            if publication_lock is None:
                raise SessionNotFound(str(session_id))
        with publication_lock:
            with self._condition:
                if session_id in self._closing:
                    raise self._cleanup_pending(session_id)
                hub = self._hubs.get(session_id)
                if hub is None:
                    raise SessionNotFound(str(session_id))
            try:
                return hub.subscribe(from_seq)
            except RuntimeError as error:
                raise SessionNotFound(str(session_id)) from error

    def pause(self, session_id: SessionId) -> ControlResult:
        publication_lock = self._publication_lock_for(session_id)
        if publication_lock is None:
            return self._missing_control(session_id)
        with publication_lock:
            with self._condition:
                record = self._records.get(session_id)
                if record is None:
                    return self._missing_control(session_id)
                decision = control_decision(
                    ControlAction.PAUSE, record.state, record.supports_pause
                )
                if decision is ControlCode.UNSUPPORTED:
                    return ControlResult(
                        ControlCode.UNSUPPORTED,
                        session_id,
                        record.state,
                        record.state,
                        "this registered session kind does not support pause",
                    )
                if decision is not ControlCode.ACCEPTED:
                    return self._illegal_control(record, "pause")
                self._controls[session_id].request_pause()
                updated, hub = self._transition_locked(
                    session_id, SessionState.PAUSING
                )
            hub.emit(StateChanged(updated.state))
        return ControlResult(
            ControlCode.ACCEPTED,
            session_id,
            record.state,
            updated.state,
            "pause requested; custody releases after the next checkpoint",
        )

    def resume(self, session_id: SessionId) -> ControlResult:
        publication_lock = self._publication_lock_for(session_id)
        if publication_lock is None:
            return self._missing_control(session_id)
        with publication_lock:
            with self._condition:
                record = self._records.get(session_id)
                if record is None:
                    return self._missing_control(session_id)
                if control_decision(
                    ControlAction.RESUME, record.state, record.supports_pause
                ) is not ControlCode.ACCEPTED:
                    return self._illegal_control(record, "resume")
                self._controls[session_id].reset()
                updated, hub = self._transition_locked(
                    session_id, SessionState.PENDING
                )
                self._enqueue_once_locked(session_id)
                self._condition.notify_all()
            hub.emit(StateChanged(updated.state))
        return ControlResult(
            ControlCode.ACCEPTED,
            session_id,
            record.state,
            updated.state,
            "session returned to the back of resource admission",
        )

    def cancel(self, session_id: SessionId) -> ControlResult:
        publication_lock = self._publication_lock_for(session_id)
        if publication_lock is None:
            return self._missing_control(session_id)
        with publication_lock:
            return self._cancel_with_publication_lock(session_id)

    def _cancel_with_publication_lock(
        self,
        session_id: SessionId,
    ) -> ControlResult:
        with self._condition:
            record = self._records.get(session_id)
            if record is None:
                return self._missing_control(session_id)
            if control_decision(
                ControlAction.CANCEL, record.state, record.supports_pause
            ) is not ControlCode.ACCEPTED:
                return self._illegal_control(record, "cancel")
            control = self._controls[session_id]
            control.request_cancel()
            if record.state is SessionState.PAUSING:
                return ControlResult(
                    ControlCode.ACCEPTED,
                    session_id,
                    record.state,
                    record.state,
                    "cancel will settle after the in-progress pause drain",
                )
            updated, hub = self._transition_locked(
                session_id, SessionState.CANCELING
            )
            if record.state in (
                SessionState.PENDING,
                SessionState.PAUSED,
                SessionState.INTERRUPTED,
            ) and session_id not in self._pending:
                self._enqueue_once_locked(session_id)
            self._condition.notify_all()
        hub.emit(StateChanged(updated.state))
        return ControlResult(
            ControlCode.ACCEPTED,
            session_id,
            record.state,
            updated.state,
            "cancellation requested",
        )

    def _cancel_before_deadline(
        self,
        session_id: SessionId,
        deadline: float,
        *,
        wait: bool,
    ) -> bool:
        """Cancel while the caller owns the session publication lock.

        Shutdown cannot first persist ``CANCELING`` and then wait without a
        bound for the hub lock needed to publish its matching reliable event.
        Reserve both sides before changing state so expiry leaves the session
        unchanged and retryable.
        """

        hub = None
        publication_reserved = False
        changed: StateChanged | None = None
        try:
            remaining = deadline - monotonic()
            if wait:
                condition_acquired = (
                    remaining > 0
                    and self._condition.acquire(timeout=remaining)
                )
            else:
                condition_acquired = self._condition.acquire(blocking=False)
            if not condition_acquired:
                return False
            try:
                record = self._records.get(session_id)
                if record is None:
                    return True
                if control_decision(
                    ControlAction.CANCEL, record.state, record.supports_pause
                ) is not ControlCode.ACCEPTED:
                    return True
                hub = self._hubs.get(session_id)
                if hub is None:
                    return True
            finally:
                self._condition.release()

            remaining = deadline - monotonic()
            hub_timeout = max(0.0, remaining) if wait else 0.0
            if (wait and remaining <= 0) or not hub._reserve_publication(
                hub_timeout
            ):
                return False
            publication_reserved = True

            remaining = deadline - monotonic()
            if wait:
                condition_acquired = (
                    remaining > 0
                    and self._condition.acquire(timeout=remaining)
                )
            else:
                condition_acquired = self._condition.acquire(blocking=False)
            if not condition_acquired:
                return False
            try:
                record = self._records.get(session_id)
                if record is None or self._hubs.get(session_id) is not hub:
                    return True
                if control_decision(
                    ControlAction.CANCEL, record.state, record.supports_pause
                ) is not ControlCode.ACCEPTED:
                    return True
                control = self._controls[session_id]
                control.request_cancel()
                if record.state is SessionState.PAUSING:
                    return True
                updated, _ = self._transition_locked(
                    session_id, SessionState.CANCELING
                )
                if record.state in (
                    SessionState.PENDING,
                    SessionState.PAUSED,
                    SessionState.INTERRUPTED,
                ):
                    self._enqueue_once_locked(session_id)
                self._condition.notify_all()
                changed = StateChanged(updated.state)
            finally:
                self._condition.release()
            if changed is not None:
                hub._emit_reserved(changed, audit_offer_timeout=0.0)
            return True
        finally:
            if publication_reserved:
                assert hub is not None
                hub._release_publication()

    def close(self, session_id: SessionId) -> None:
        publication_lock = self._publication_lock_for(session_id)
        if publication_lock is None:
            raise SessionNotFound(str(session_id))
        with publication_lock:
            with self._condition:
                record = self._records.get(session_id)
                if record is None:
                    raise SessionNotFound(str(session_id))
                if not self._is_settled(record):
                    raise SessionNotTerminal(str(session_id))
                self._closing.add(session_id)
                hub = self._hubs[session_id]
            close_status = hub.close(self._audit_timeout)
            if close_status is EventHubCloseStatus.PUBLICATION_TIMEOUT:
                with self._condition:
                    # Shutdown owns its close claim once admission stops.
                    if self._accepting:
                        self._closing.discard(session_id)
                        self._cleanup_irreversible.discard(session_id)
                    self._condition.notify_all()
                raise TimeoutError(
                    "session terminal settlement is complete; event "
                    "publication did not quiesce, so cleanup did not "
                    f"start: {session_id}"
                )
            if close_status is EventHubCloseStatus.AUDIT_CLEANUP_PENDING:
                with self._condition:
                    self._cleanup_irreversible.add(session_id)
                    self._condition.notify_all()
                raise TimeoutError(
                    "session terminal settlement is complete; subscriptions "
                    f"are closed and only cleanup remains pending: {session_id}"
                )
            with self._condition:
                self._cleanup_irreversible.add(session_id)
                self._condition.notify_all()
            self._store.drop(session_id)
            with self._condition:
                self._hubs.pop(session_id)
                self._records.pop(session_id, None)
                self._controls.pop(session_id, None)
                self._state_publication_locks.pop(session_id, None)
                self._closing.discard(session_id)
                self._cleanup_irreversible.discard(session_id)
                self._item_events.pop(session_id, None)
                self._condition.notify_all()

    def shutdown(self, timeout: float = 10.0) -> ShutdownResult:
        if timeout < 0:
            raise ValueError("shutdown timeout cannot be negative")
        deadline = monotonic() + timeout
        with self._condition:
            self._accepting = False
            candidates = tuple(
                (
                    record.session_id,
                    self._state_publication_locks.get(record.session_id),
                )
                for record in self._records.values()
                if not is_terminal(record.state)
            )
            self._condition.notify_all()
        blocked: list[tuple[SessionId, Lock]] = []
        for session_id, publication_lock in candidates:
            if monotonic() >= deadline:
                break
            if publication_lock is None:
                continue
            if not publication_lock.acquire(blocking=False):
                blocked.append((session_id, publication_lock))
                continue
            try:
                canceled = self._cancel_before_deadline(
                    session_id,
                    deadline,
                    wait=False,
                )
            finally:
                publication_lock.release()
            if not canceled:
                blocked.append((session_id, publication_lock))
        for session_id, publication_lock in blocked:
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            if not publication_lock.acquire(timeout=remaining):
                break
            try:
                self._cancel_before_deadline(
                    session_id,
                    deadline,
                    wait=True,
                )
            finally:
                publication_lock.release()

        with self._condition:
            while True:
                unfinished = tuple(
                    record.session_id
                    for record in self._records.values()
                    if not self._is_settled(record)
                )
                if not unfinished and not self._workers and self._admitting == 0:
                    break
                remaining = deadline - monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)

        self._retry_admission_cleanups(deadline)

        with self._condition:
            unfinished = tuple(
                dict.fromkeys(
                    (
                        record.session_id
                        for record in self._records.values()
                        if not self._is_settled(record)
                    ),
                )
            )
            worker_unfinished = tuple(
                dict.fromkeys(key.session_id for key in self._workers)
            )
            admission_cleanup_unfinished = tuple(self._admission_cleanups)
            unfinished = tuple(
                dict.fromkeys(
                    (
                        *unfinished,
                        *worker_unfinished,
                        *admission_cleanup_unfinished,
                    )
                )
            )
            custody_released = not self._leases and not self._reserved

        remaining = max(0.0, deadline - monotonic())
        self._scheduler.join(remaining)
        observer_incomplete: list[SessionId] = []
        with self._condition:
            terminal_hubs = tuple(
                (
                    session_id,
                    self._hubs.get(session_id),
                    self._state_publication_locks.get(session_id),
                )
                for session_id, record in self._records.items()
                if self._is_settled(record)
            )
            self._closing.update(session_id for session_id, _, _ in terminal_hubs)
        for session_id, hub, publication_lock in terminal_hubs:
            if hub is None or publication_lock is None:
                observer_incomplete.append(session_id)
                continue
            remaining = max(0.0, deadline - monotonic())
            if not publication_lock.acquire(timeout=remaining):
                observer_incomplete.append(session_id)
                continue
            try:
                with self._condition:
                    still_owned = (
                        self._hubs.get(session_id) is hub
                        and self._records.get(session_id) is not None
                    )
                if not still_owned:
                    continue
                remaining = max(0.0, deadline - monotonic())
                if hub.close(remaining) is not EventHubCloseStatus.COMPLETE:
                    observer_incomplete.append(session_id)
            finally:
                publication_lock.release()
        all_unfinished = tuple(dict.fromkeys((*unfinished, *observer_incomplete)))
        with self._condition:
            admitting = self._admitting
            workers_retired = not self._workers and not self._current_workers
            custody_released = not self._leases and not self._reserved
            admissions_clean = not self._admission_cleanups
        complete = (
            not all_unfinished
            and custody_released
            and workers_retired
            and not self._scheduler.is_alive()
            and admitting == 0
            and admissions_clean
        )
        return ShutdownResult(complete, all_unfinished, custody_released)

    def _enqueue_once_locked(self, session_id: SessionId) -> None:
        if session_id not in self._pending:
            self._pending.append(session_id)

    def _is_current_worker_locked(self, key: _WorkerKey) -> bool:
        return self._current_workers.get(key.session_id) == key

    def _require_current_worker_locked(self, key: _WorkerKey) -> SessionRecord:
        if not self._is_current_worker_locked(key):
            raise _StaleWorkerAttempt()
        record = self._records.get(key.session_id)
        if record is None:
            raise _StaleWorkerAttempt()
        return record

    def _register_attempt_locked(
        self,
        record: SessionRecord,
        *,
        reserve: bool,
    ) -> _WorkerAttempt:
        session_id = record.session_id
        if session_id in self._current_workers:
            raise RuntimeError("session already has a current worker generation")
        self._worker_generation += 1
        key = _WorkerKey(session_id, self._worker_generation)
        thread = Thread(
            target=self._run_worker,
            args=(key, record.resources),
            name=f"namisync-session-{session_id}-{key.generation}",
            daemon=True,
        )
        attempt = _WorkerAttempt(key, record.resources, thread)
        self._workers[key] = attempt
        self._current_workers[session_id] = key
        if reserve:
            for resource in record.resources:
                if resource in self._reserved:
                    raise RuntimeError("dispatcher resource was reserved twice")
                self._reserved[resource] = key
        return attempt

    def _schedule(self) -> None:
        while True:
            launches: list[_WorkerAttempt] = []
            with self._condition:
                while not launches:
                    selected: list[SessionId] = []
                    waiting_resources: set[ResourceId] = set()
                    for session_id in tuple(self._pending):
                        record = self._records.get(session_id)
                        if record is None or record.state not in {
                            SessionState.PENDING,
                            SessionState.CANCELING,
                        }:
                            selected.append(session_id)
                            continue
                        if session_id in self._current_workers:
                            if record.state is SessionState.PENDING:
                                waiting_resources.update(record.resources)
                            continue
                        if record.state is SessionState.CANCELING:
                            launches.append(
                                self._register_attempt_locked(record, reserve=False)
                            )
                            selected.append(session_id)
                            continue
                        if any(
                            resource in self._reserved
                            or resource in waiting_resources
                            for resource in record.resources
                        ):
                            waiting_resources.update(record.resources)
                            continue
                        launches.append(
                            self._register_attempt_locked(record, reserve=True)
                        )
                        selected.append(session_id)
                    if selected:
                        selected_set = set(selected)
                        self._pending = deque(
                            item for item in self._pending if item not in selected_set
                        )
                    if launches:
                        break
                    if not self._accepting and not self._pending and not self._workers:
                        return
                    if not selected:
                        self._condition.wait()
            for attempt in launches:
                attempt.thread.start()

    def _run_worker(
        self,
        key: _WorkerKey,
        resources: tuple[ResourceId, ...],
    ) -> None:
        session_id = key.session_id
        try:
            with self._condition:
                record = self._require_current_worker_locked(key)
                registration = self._registry[record.kind]
                control = self._controls[session_id]
                publication_lock = self._state_publication_locks[session_id]
            if record.state is SessionState.CANCELING:
                self._run_canceled(key, registration, record)
                return
            try:
                lease = self._lock_provider.acquire(
                    resources, control.cancel_requested
                )
            except Canceled:
                with self._condition:
                    current = self._require_current_worker_locked(key)
                self._run_canceled(key, registration, current)
                return
            except BaseException as error:
                self._run_core(
                    key,
                    resources,
                    registration,
                    invocation=None,
                    disposition=Disposition.UNRUN,
                    failure=error,
                )
                return
            with self._condition:
                if self._is_current_worker_locked(key):
                    self._leases[key] = lease
                    current = self._require_current_worker_locked(key)
                    stale = False
                else:
                    stale = True
                    current = None
            if stale:
                try:
                    lease.release()
                except BaseException as error:
                    with self._condition:
                        self._custody_failures.append(error)
                return
            assert current is not None
            if current.state is SessionState.CANCELING:
                self._run_canceled(key, registration, current)
                return
            try:
                invocation = registration.open(current.payload)
            except BaseException as error:
                self._run_core(
                    key,
                    resources,
                    registration,
                    invocation=None,
                    disposition=Disposition.UNRUN,
                    failure=error,
                )
                return
            resumed_attempt = current.started_at is not None
            with publication_lock:
                with self._condition:
                    current = self._require_current_worker_locked(key)
                    if current.state is not SessionState.CANCELING:
                        updated, hub = self._transition_locked(
                            session_id, SessionState.RUNNING
                        )
                    else:
                        updated = None
                        hub = None
                if updated is not None and hub is not None:
                    hub.emit(StateChanged(updated.state))
            if updated is None:
                self._run_canceled(key, registration, current)
                return
            self._run_core(
                key,
                resources,
                registration,
                invocation=invocation,
                disposition=Disposition.RAN,
                failure=None,
                settle_pre_run_canceled=resumed_attempt,
            )
        except _StaleWorkerAttempt:
            return
        finally:
            self._release_custody(key, resources)
            self._worker_done(key)

    def _run_canceled(
        self,
        key: _WorkerKey,
        registration: WorkflowRegistration,
        record: SessionRecord,
    ) -> None:
        session_id = key.session_id
        with self._condition:
            self._require_current_worker_locked(key)
        disposition = self._disposition(record)
        failure = None
        try:
            canceled_result = self._settled_cancellation(
                registration,
                record,
                disposition,
            )
        except Exception as error:
            canceled_result = None
            failure = error
        self._run_core(
            key,
            record.resources,
            registration,
            invocation=None,
            disposition=disposition,
            failure=failure,
            canceled_result=canceled_result,
        )

    def _run_core(
        self,
        key: _WorkerKey,
        resources: tuple[ResourceId, ...],
        registration: WorkflowRegistration,
        *,
        invocation: WorkflowInvocation | None,
        disposition: Disposition,
        failure: BaseException | None,
        canceled_result: OperationResult | None = None,
        settle_pre_run_canceled: bool = False,
    ) -> None:
        session_id = key.session_id
        with self._condition:
            self._require_current_worker_locked(key)
            control = self._controls[session_id]
            hub = self._hubs[session_id]

        def work(context):
            if canceled_result is not None:
                return canceled_result
            if failure is not None:
                raise failure
            try:
                try:
                    context.checkpoint()
                except Canceled:
                    if not settle_pre_run_canceled:
                        raise
                    with self._condition:
                        current = self._require_current_worker_locked(key)
                    settled = self._settled_cancellation(
                        registration,
                        current,
                        disposition,
                    )
                    if settled is None:
                        raise
                    return settled
                if invocation is None:
                    raise Canceled()
                return invocation.run(context)
            except PauseRequested:
                if invocation is None:
                    raise
                if not registration.supports_pause:
                    raise RuntimeError("registered invocation paused without capability")
                self._replace_payload(key, invocation.snapshot())
                raise

        try:
            outcome = run_session(
                work,
                emit=hub.emit,
                checkpoint=control.checkpoint,
                settle=lambda state, result: self._settle(
                    key, resources, state, result
                ),
                finalize_audit=hub.finalize_audit,
                publish_result=lambda result: self._publish_result(key, result),
                disposition=disposition,
                item_accumulator=self._item_events[session_id],
            )
        except _StaleWorkerAttempt:
            return
        if not outcome.paused:
            with self._condition:
                self._item_events.pop(session_id, None)

    @staticmethod
    def _settled_cancellation(
        registration: WorkflowRegistration,
        record: SessionRecord,
        disposition: Disposition,
    ) -> OperationResult | None:
        if record.started_at is None or registration.settle_canceled is None:
            return None
        result = registration.settle_canceled(record.payload, disposition)
        if result_terminal_state(result) is not SessionState.CANCELED:
            raise ValueError("canceled settlement must project to CANCELED")
        return result

    def _settle(
        self,
        key: _WorkerKey,
        resources: tuple[ResourceId, ...],
        state: SessionState,
        result: OperationResult | None,
    ) -> None:
        session_id = key.session_id
        self._release_custody(key, resources)
        # The audit axis is not settled yet. A terminal record may be visible
        # briefly without a result, but it must never expose provisional
        # ``audit=OK`` before the observer acknowledges finalization.
        transition_result = None if is_terminal(state) else result
        publication_lock = self._publication_lock_for(session_id)
        if publication_lock is None:
            raise _StaleWorkerAttempt()
        with publication_lock:
            with self._condition:
                self._require_current_worker_locked(key)
                updated, hub = self._transition_locked(
                    session_id, state, transition_result
                )
            hub.emit(StateChanged(updated.state))

    def _publish_result(self, key: _WorkerKey, result: OperationResult) -> None:
        with self._condition:
            record = self._require_current_worker_locked(key)
            updated = replace(record, result=result)
            self._records[key.session_id] = updated
            self._persist_locked(updated)
            self._condition.notify_all()

    def _replace_payload(self, key: _WorkerKey, payload: bytes) -> None:
        if not isinstance(payload, bytes):
            raise TypeError("workflow continuation snapshot must be bytes")
        with self._condition:
            record = self._require_current_worker_locked(key)
            updated = replace(record, payload=payload)
            self._records[key.session_id] = updated
            self._persist_locked(updated)

    def _transition_locked(
        self,
        session_id: SessionId,
        state: SessionState,
        result: OperationResult | None = None,
    ) -> tuple[SessionRecord, EventHub]:
        record = self._records[session_id]
        require_transition(record.state, state)
        now = self._now()
        started_at = record.started_at
        if state is SessionState.RUNNING and started_at is None:
            started_at = now
        ended_at = now if is_terminal(state) else None
        updated = replace(
            record,
            state=state,
            started_at=started_at,
            ended_at=ended_at,
            result=result,
        )
        self._records[session_id] = updated
        self._persist_locked(updated)
        self._condition.notify_all()
        return updated, self._hubs[session_id]

    def _persist_locked(self, record: SessionRecord) -> None:
        try:
            self._store.put(record)
        except BaseException as error:
            self._store_failures.append(error)

    def _release_custody(
        self,
        key: _WorkerKey,
        resources: tuple[ResourceId, ...],
    ) -> None:
        with self._condition:
            lease = self._leases.pop(key, None)
        try:
            if lease is not None:
                lease.release()
        except BaseException as error:
            with self._condition:
                self._custody_failures.append(error)
        finally:
            with self._condition:
                for resource in resources:
                    if self._reserved.get(resource) == key:
                        del self._reserved[resource]
                self._condition.notify_all()

    def _worker_done(self, key: _WorkerKey) -> None:
        session_id = key.session_id
        publication_lock = self._publication_lock_for(session_id)
        if publication_lock is None:
            with self._condition:
                self._workers.pop(key, None)
                if self._current_workers.get(session_id) == key:
                    self._current_workers.pop(session_id, None)
                self._condition.notify_all()
            return
        transition: tuple[SessionRecord, EventHub] | None = None
        with publication_lock:
            try:
                with self._condition:
                    if not self._is_current_worker_locked(key):
                        self._workers.pop(key, None)
                        self._condition.notify_all()
                        return
                    record = self._records.get(session_id)
                    control = self._controls.get(session_id)
                    if (
                        record is not None
                        and control is not None
                        and record.state is SessionState.PAUSED
                        and control.cancel_requested()
                    ):
                        transition = self._transition_locked(
                            session_id, SessionState.CANCELING
                        )
                        record = transition[0]
                    if record is not None and record.state in {
                        SessionState.PENDING,
                        SessionState.CANCELING,
                    }:
                        self._enqueue_once_locked(session_id)
                    self._condition.notify_all()
                if transition is not None:
                    updated, hub = transition
                    hub.emit(StateChanged(updated.state))
            finally:
                with self._condition:
                    if self._current_workers.get(session_id) == key:
                        self._current_workers.pop(session_id, None)
                    self._workers.pop(key, None)
                    self._condition.notify_all()

    def _publication_lock_for(self, session_id: SessionId):
        # Never wait for a publication lock while holding ``_condition``.
        # Each lock spans one persisted lifecycle transition and its matching
        # reliable event without blocking unrelated sessions.
        with self._condition:
            return self._state_publication_locks.get(session_id)

    @staticmethod
    def _disposition(record: SessionRecord) -> Disposition:
        return Disposition.RAN if record.started_at is not None else Disposition.UNRUN

    @staticmethod
    def _is_settled(record: SessionRecord) -> bool:
        return is_terminal(record.state) and record.result is not None

    @staticmethod
    def _missing_control(session_id: SessionId) -> ControlResult:
        return ControlResult(
            ControlCode.NOT_FOUND,
            session_id,
            None,
            None,
            "session does not exist",
        )

    @staticmethod
    def _cleanup_pending(session_id: SessionId) -> SessionCleanupPending:
        return SessionCleanupPending(
            "session terminal settlement is complete; only cleanup remains "
            f"pending: {session_id}"
        )

    @staticmethod
    def _illegal_control(record: SessionRecord, operation: str) -> ControlResult:
        return ControlResult(
            ControlCode.ILLEGAL_STATE,
            record.session_id,
            record.state,
            record.state,
            f"cannot {operation} a session in {record.state.value}",
        )

    def _now(self) -> datetime:
        value = self._clock.now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        if value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("clock must return UTC")
        return value
