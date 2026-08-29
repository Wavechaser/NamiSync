"""Domain-blind M0 session admission, scheduling, control, and custody."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from threading import Condition, Event, Lock, Thread, current_thread
from time import monotonic
from typing import Callable
from uuid import uuid4

from namisync.core.exception_graph import (
    retire_exception_graph,
    retired_failure_detail,
)
from namisync.core.evidence import RecordingStatus
from namisync.core.events import StateChanged
from namisync.core.session import (
    Canceled,
    Disposition,
    FailureDetail,
    OperationResult,
    PauseRequested,
    ResourceId,
    ResultItem,
    SessionId,
    SessionRecord,
    SessionState,
    SessionStore,
    StoredSessionRecord,
    is_terminal,
    normalize_result_diagnostics,
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
_WORKER_RETIRE_POLL_SECONDS = 0.01


class AdmissionAttachment:
    """Expose one retryable rollback even when attachment itself raises."""

    __slots__ = ("_callbacks",)

    def __init__(
        self,
        attach: _AdmissionAttach,
        rollback: _AdmissionRollback,
    ) -> None:
        if not callable(attach) or not callable(rollback):
            raise TypeError("admission attachment callbacks must be callable")
        self._callbacks = (attach, rollback)

    def capture(self) -> tuple[_AdmissionAttach, _AdmissionRollback]:
        """Return one validated callback-pair snapshot."""

        if type(self) is not AdmissionAttachment:
            raise TypeError("admission attachment subclasses are not accepted")
        callbacks = self._callbacks
        if type(callbacks) is not tuple or len(callbacks) != 2:
            raise TypeError("admission attachment callbacks are invalid")
        attach, rollback = callbacks
        if not callable(attach) or not callable(rollback):
            raise TypeError("admission attachment callbacks must be callable")
        return attach, rollback

    def __call__(
        self,
        session_id: SessionId,
        stream: EventStream,
    ) -> _AdmissionRollback:
        attach, rollback = self.capture()
        attached_rollback = attach(session_id, stream)
        if attached_rollback is not rollback:
            raise TypeError(
                "admission attachment returned a different rollback callback"
            )
        return attached_rollback


def _stored_record(record: SessionRecord) -> StoredSessionRecord:
    return StoredSessionRecord(
        session_id=record.session_id,
        kind=record.kind,
        state=record.state,
        resources=record.resources,
        supports_pause=record.supports_pause,
        admission_order=record.admission_order,
        created_at=record.created_at,
        started_at=record.started_at,
        ended_at=record.ended_at,
        result=record.result,
    )


def _project_worker_exception(
    error: Exception,
    disposition: Disposition,
) -> tuple[OperationResult | None, bool]:
    """Replace a raw pre-run failure with fixed terminal or control truth."""

    if isinstance(error, Canceled):
        retire_exception_graph(error)
        return None, False
    if isinstance(error, PauseRequested):
        retire_exception_graph(error)
        return None, True
    try:
        result = normalize_result_diagnostics(
            OperationResult(
                status=SessionState.FAILED,
                disposition=disposition,
                error=retired_failure_detail(error),
            )
        )
    except Exception as diagnostic_error:
        retire_exception_graph(diagnostic_error)
        result = OperationResult(
            status=SessionState.FAILED,
            disposition=disposition,
            omitted_detail_count=1,
        )
    except BaseException as diagnostic_fatal:
        retire_exception_graph(diagnostic_fatal)
        raise
    return result, False


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

    def on_event(self, envelope) -> RecordingStatus:
        raise RuntimeError("audit observer is unavailable") from None

    def flush(self) -> None:
        pass

    def finalize(self, result: OperationResult) -> RecordingStatus:
        raise RuntimeError("audit observer is unavailable") from None

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
    hub: EventHub | None
    stream: EventStream | None
    rollback: _AdmissionRollback | None
    store_pending: bool
    failure_seen: bool = False

    @property
    def complete(self) -> bool:
        return (
            self.rollback is None
            and self.stream is None
            and self.hub is None
            and not self.store_pending
        )


@dataclass(slots=True)
class _AdmissionLiability:
    transferred: bool = False


@dataclass(frozen=True, slots=True)
class _AdmissionCleanupAttempt:
    cleanup: _AdmissionCleanup
    thread: Thread
    start_complete: Event


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
        self._retiring_workers: set[_WorkerKey] = set()
        self._admitting = 0
        self._admission_order = 0
        self._accepting = True
        self._admission_liability_claimed = False
        self._admission_cleanups: dict[SessionId, _AdmissionCleanup] = {}
        self._admission_cleanup_attempt: _AdmissionCleanupAttempt | None = None
        self._store_failed = False
        self._custody_failed = False
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
        attach: _AdmissionAttach | AdmissionAttachment | None = None,
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
            attachment_rollback: _AdmissionRollback | None = None
            if isinstance(attach, AdmissionAttachment):
                captured_attach, attachment_rollback = attach.capture()
            else:
                captured_attach = attach
                if captured_attach is not None and not callable(captured_attach):
                    raise TypeError("admission attach callback must be callable")
            return self._admit(
                kind,
                request,
                registration,
                attach=captured_attach,
                attachment_rollback=attachment_rollback,
            )
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
        attachment_rollback: _AdmissionRollback | None,
    ) -> SessionId:
        if not self._claim_admission_liability():
            self._start_admission_cleanup_worker(self._audit_timeout)
            raise self._admission_cleanup_pending()
        liability = _AdmissionLiability()
        try:
            prepared = registration.prepare(request)
            resources = tuple(sorted(prepared.resources))
            return self._admit_owned(
                kind,
                prepared.payload,
                resources,
                registration,
                attach=attach,
                attachment_rollback=attachment_rollback,
                liability=liability,
            )
        finally:
            if not liability.transferred:
                self._release_admission_liability()

    def _claim_admission_liability(self) -> bool:
        with self._condition:
            if not self._accepting:
                raise AdmissionClosed("dispatcher stopped during admission")
            self._reap_admission_cleanup_attempt_locked()
            if (
                self._admission_liability_claimed
                or self._admission_cleanup_attempt is not None
            ):
                return False
            self._admission_liability_claimed = True
            return True

    def _release_admission_liability(self) -> None:
        with self._condition:
            assert self._admission_liability_claimed
            self._admission_liability_claimed = False
            self._condition.notify_all()

    def _admit_owned(
        self,
        kind: str,
        payload: bytes,
        resources: tuple[ResourceId, ...],
        registration: WorkflowRegistration,
        *,
        attach: _AdmissionAttach | None,
        attachment_rollback: _AdmissionRollback | None,
        liability: _AdmissionLiability,
    ) -> SessionId:
        session_id = SessionId(uuid4().hex)
        created_at = self._now()
        with self._condition:
            if not self._accepting:
                raise AdmissionClosed("dispatcher stopped during admission")
            admission_order = self._admission_order
            self._admission_order += 1
        record = SessionRecord(
            session_id=session_id,
            kind=kind,
            state=SessionState.PENDING,
            resources=resources,
            payload=payload,
            supports_pause=registration.supports_pause,
            admission_order=admission_order,
            created_at=created_at,
        )
        try:
            observer = self._audit_factory(record)
        except BaseException as error:
            retire_exception_graph(error)
            observer = _DegradedAuditObserver()
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
        attachment_started = False
        store_touched = False
        publication_lock = Lock()
        try:
            store_touched = True
            self._store.put(_stored_record(record))
            if attach is not None:
                stream = hub.subscribe()
                attachment_started = True
                attached_rollback = attach(session_id, stream)
                if not callable(attached_rollback):
                    raise TypeError(
                        "admission attach callback must return a rollback callback"
                    )
                if (
                    attachment_rollback is not None
                    and attached_rollback is not attachment_rollback
                ):
                    raise TypeError(
                        "admission attachment returned a different rollback callback"
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
        except BaseException as error:
            retire_exception_graph(error)
            if rollback is None and attachment_started:
                rollback = attachment_rollback
            cleanup = _AdmissionCleanup(
                session_id=session_id,
                hub=hub,
                stream=stream,
                rollback=rollback,
                store_pending=store_touched,
            )
            with self._condition:
                assert self._admission_liability_claimed
                assert not self._admission_cleanups
                self._admission_cleanups[session_id] = cleanup
                liability.transferred = True
                self._condition.notify_all()
            attempt = self._start_admission_cleanup_worker(self._audit_timeout)
            if attempt is not None:
                try:
                    self._join_admission_cleanup_worker(
                        attempt,
                        monotonic() + max(0.0, self._audit_timeout),
                    )
                except BaseException as cleanup_error:
                    retire_exception_graph(cleanup_error)
            raise
        return session_id

    def _attempt_admission_cleanup(
        self,
        cleanup: _AdmissionCleanup,
        timeout: float,
    ) -> None:
        if cleanup.rollback is not None:
            try:
                cleanup.rollback()
            except BaseException as error:
                cleanup.failure_seen = True
                retire_exception_graph(error)
            else:
                cleanup.rollback = None
        if cleanup.stream is not None:
            try:
                cleanup.stream.close()
            except BaseException as error:
                cleanup.failure_seen = True
                retire_exception_graph(error)
            else:
                cleanup.stream = None
        if cleanup.hub is not None:
            try:
                close_status = cleanup.hub.close(timeout)
            except BaseException as error:
                cleanup.failure_seen = True
                retire_exception_graph(error)
            else:
                if close_status is EventHubCloseStatus.COMPLETE:
                    cleanup.hub = None
                else:
                    cleanup.failure_seen = True
        if cleanup.store_pending:
            try:
                self._store.drop(cleanup.session_id)
            except BaseException as error:
                cleanup.failure_seen = True
                retire_exception_graph(error)
            else:
                cleanup.store_pending = False

    def _start_admission_cleanup_worker(
        self,
        timeout: float,
    ) -> _AdmissionCleanupAttempt | None:
        start_complete = Event()
        with self._condition:
            self._reap_admission_cleanup_attempt_locked()
            current = self._admission_cleanup_attempt
            if current is not None:
                return current
            pending = tuple(self._admission_cleanups.values())
            assert len(pending) <= 1
            if not pending:
                return None
            cleanup = pending[0]
            thread = Thread(
                target=self._run_admission_cleanup_worker,
                args=(cleanup, max(0.0, timeout), start_complete),
                name=f"namisync-admission-cleanup-{cleanup.session_id}",
                daemon=True,
            )
            attempt = _AdmissionCleanupAttempt(cleanup, thread, start_complete)
            self._admission_cleanup_attempt = attempt
        try:
            thread.start()
        except BaseException as error:
            cleanup.failure_seen = True
            started = thread.ident is not None
            retire_exception_graph(error)
            with self._condition:
                if not started and self._admission_cleanup_attempt is attempt:
                    self._admission_cleanup_attempt = None
                self._condition.notify_all()
            start_complete.set()
            return attempt if started else None
        start_complete.set()
        return attempt

    def _run_admission_cleanup_worker(
        self,
        cleanup: _AdmissionCleanup,
        timeout: float,
        start_complete: Event,
    ) -> None:
        start_complete.wait()
        try:
            self._attempt_admission_cleanup(cleanup, timeout)
        finally:
            with self._condition:
                attempt = self._admission_cleanup_attempt
                assert attempt is not None
                assert attempt.thread is current_thread()
                assert attempt.cleanup is cleanup
                if (
                    cleanup.complete
                    and self._admission_cleanups.get(cleanup.session_id) is cleanup
                ):
                    self._admission_cleanups.pop(cleanup.session_id, None)
                    assert self._admission_liability_claimed
                    self._admission_liability_claimed = False
                self._condition.notify_all()

    def _join_admission_cleanup_worker(
        self,
        attempt: _AdmissionCleanupAttempt,
        deadline: float,
    ) -> None:
        if attempt.thread is current_thread():
            return
        remaining = max(0.0, deadline - monotonic())
        if not attempt.start_complete.wait(remaining):
            return
        if attempt.thread.ident is None:
            return
        attempt.thread.join(max(0.0, deadline - monotonic()))
        with self._condition:
            self._reap_admission_cleanup_attempt_locked()

    def _reap_admission_cleanup_attempt_locked(self) -> None:
        attempt = self._admission_cleanup_attempt
        if (
            attempt is None
            or not attempt.start_complete.is_set()
            or attempt.thread.ident is None
            or attempt.thread.is_alive()
        ):
            return
        self._admission_cleanup_attempt = None
        self._condition.notify_all()

    def _retry_admission_cleanups(self, deadline: float) -> None:
        attempt = self._start_admission_cleanup_worker(
            max(0.0, deadline - monotonic())
        )
        if attempt is not None:
            self._join_admission_cleanup_worker(attempt, deadline)

    def get(self, session_id: SessionId) -> SessionRecord:
        with self._condition:
            record = self._records.get(session_id)
        if record is None:
            raise SessionNotFound(str(session_id))
        return record

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
                retire_exception_graph(error)
            raise SessionNotFound(str(session_id)) from None

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
        deadline = monotonic() + self._audit_timeout
        if not self._condition.acquire(timeout=max(0.0, deadline - monotonic())):
            raise TimeoutError(
                "dispatcher state did not quiesce; "
                f"cleanup did not start: {session_id}"
            )
        try:
            record = self._records.get(session_id)
            if record is None:
                raise SessionNotFound(str(session_id))
            if not self._is_settled(record):
                raise SessionNotTerminal(str(session_id))
            key = self._current_workers.get(session_id)
            attempt = self._workers.get(key) if key is not None else None
            publication_lock = self._state_publication_locks[session_id]
        finally:
            self._condition.release()
        if attempt is not None:
            if attempt.thread is current_thread():
                raise TimeoutError(
                    "session cannot close from its own worker; "
                    f"retry after retirement: {session_id}"
                )
            if attempt.thread.ident is None:
                with self._condition:
                    while self._workers.get(key) is attempt:
                        remaining = deadline - monotonic()
                        if remaining <= 0:
                            raise TimeoutError(
                                "session worker retirement is pending; "
                                f"cleanup did not start: {session_id}"
                            )
                        self._condition.wait(remaining)
            else:
                attempt.thread.join(max(0.0, deadline - monotonic()))
            if attempt.thread.ident is not None and attempt.thread.is_alive():
                raise TimeoutError(
                    "session worker retirement is pending; "
                    f"cleanup did not start: {session_id}"
                )
        if not publication_lock.acquire(timeout=max(0.0, deadline - monotonic())):
            raise TimeoutError(
                f"session publication did not quiesce; cleanup did not start: {session_id}"
            )
        try:
            if not self._condition.acquire(timeout=max(0.0, deadline - monotonic())):
                raise TimeoutError(
                    "dispatcher state did not quiesce; "
                    f"cleanup did not start: {session_id}"
                )
            try:
                self._reap_retired_workers_locked()
                record = self._records.get(session_id)
                if record is None:
                    raise SessionNotFound(str(session_id))
                if not self._is_settled(record):
                    raise SessionNotTerminal(str(session_id))
                self._closing.add(session_id)
                hub = self._hubs[session_id]
            finally:
                self._condition.release()
            close_status = hub.close(max(0.0, deadline - monotonic()))
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
        finally:
            publication_lock.release()

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
            self._reap_admission_cleanup_attempt_locked()
            admitting = self._admitting
            workers_retired = not self._workers and not self._current_workers
            custody_released = not self._leases and not self._reserved
            admissions_clean = (
                not self._admission_cleanups
                and self._admission_cleanup_attempt is None
                and not self._admission_liability_claimed
            )
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
                    self._reap_retired_workers_locked()
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
                    record = None
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
                        self._condition.wait(
                            _WORKER_RETIRE_POLL_SECONDS
                            if self._retiring_workers else None
                        )
            for attempt in launches:
                unstarted = False
                try:
                    attempt.thread.start()
                except BaseException as error:
                    started = attempt.thread.ident is not None
                    retire_exception_graph(error)
                    unstarted = not started
                if unstarted:
                    self._complete_unstarted_attempt(attempt)
            del attempt

    def _complete_unstarted_attempt(
        self,
        attempt: _WorkerAttempt,
    ) -> None:
        with self._condition:
            record = self._require_current_worker_locked(attempt.key)
            registration = self._registry[record.kind]
        try:
            if record.state is SessionState.CANCELING:
                self._run_canceled(attempt.key, registration, record)
            else:
                result = OperationResult(
                    status=SessionState.FAILED,
                    disposition=self._disposition(record),
                    error=FailureDetail(
                        "RuntimeError",
                        "session worker could not start",
                    ),
                )
                self._run_core(
                    attempt.key,
                    attempt.resources,
                    registration,
                    invocation=None,
                    disposition=result.disposition,
                    fixed_result=result,
                )
        finally:
            self._release_custody(attempt.key, attempt.resources)
            self._worker_done(attempt.key)

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
            projected_failure = None
            try:
                lease = self._lock_provider.acquire(
                    resources, control.cancel_requested
                )
            except Canceled as error:
                retire_exception_graph(error)
                with self._condition:
                    current = self._require_current_worker_locked(key)
                self._run_canceled(key, registration, current)
                return
            except Exception as error:
                projected_failure = _project_worker_exception(
                    error,
                    Disposition.UNRUN,
                )
            if projected_failure is not None:
                fixed_result, pre_run_pause = projected_failure
                self._run_core(
                    key,
                    resources,
                    registration,
                    invocation=None,
                    disposition=Disposition.UNRUN,
                    fixed_result=fixed_result,
                    pre_run_pause=pre_run_pause,
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
                    retire_exception_graph(error)
                    with self._condition:
                        self._custody_failed = True
                return
            assert current is not None
            if current.state is SessionState.CANCELING:
                self._run_canceled(key, registration, current)
                return
            projected_failure = None
            try:
                if current.payload is None:
                    raise RuntimeError(
                        "nonterminal session lost its continuation payload"
                    )
                invocation = registration.open(current.payload)
            except Exception as error:
                projected_failure = _project_worker_exception(
                    error,
                    Disposition.UNRUN,
                )
            if projected_failure is not None:
                fixed_result, pre_run_pause = projected_failure
                self._run_core(
                    key,
                    resources,
                    registration,
                    invocation=None,
                    disposition=Disposition.UNRUN,
                    fixed_result=fixed_result,
                    pre_run_pause=pre_run_pause,
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
        try:
            fixed_result = self._settled_cancellation(
                registration,
                record,
                disposition,
            )
        except Exception as error:
            fixed_result, pre_run_pause = _project_worker_exception(
                error,
                disposition,
            )
        else:
            pre_run_pause = False
        self._run_core(
            key,
            record.resources,
            registration,
            invocation=None,
            disposition=disposition,
            fixed_result=fixed_result,
            pre_run_pause=pre_run_pause,
        )

    def _run_core(
        self,
        key: _WorkerKey,
        resources: tuple[ResourceId, ...],
        registration: WorkflowRegistration,
        *,
        invocation: WorkflowInvocation | None,
        disposition: Disposition,
        fixed_result: OperationResult | None = None,
        pre_run_pause: bool = False,
        settle_pre_run_canceled: bool = False,
    ) -> None:
        session_id = key.session_id
        with self._condition:
            self._require_current_worker_locked(key)
            control = self._controls[session_id]
            hub = self._hubs[session_id]

        def work(context):
            if fixed_result is not None:
                return fixed_result
            if pre_run_pause:
                raise PauseRequested()
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
        if record.payload is None:
            raise RuntimeError(
                "nonterminal canceled session lost its continuation payload"
            )
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
            payload=None if is_terminal(state) else record.payload,
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
            self._store.put(_stored_record(record))
        except BaseException as error:
            self._store_failed = True
            retire_exception_graph(error)

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
            retire_exception_graph(error)
            with self._condition:
                self._custody_failed = True
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
                self._mark_worker_done_locked(key)
                self._condition.notify_all()
            return
        transition: tuple[SessionRecord, EventHub] | None = None
        with publication_lock:
            try:
                with self._condition:
                    if not self._is_current_worker_locked(key):
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
                    self._mark_worker_done_locked(key)
                    self._condition.notify_all()

    def _mark_worker_done_locked(self, key: _WorkerKey) -> None:
        attempt = self._workers.get(key)
        if attempt is None:
            return
        if attempt.thread.ident is None:
            if self._current_workers.get(key.session_id) == key:
                self._current_workers.pop(key.session_id)
            self._workers.pop(key)
            self._retiring_workers.discard(key)
            return
        self._retiring_workers.add(key)

    def _reap_retired_workers_locked(self) -> None:
        for key in tuple(self._retiring_workers):
            attempt = self._workers[key]
            # Registered-but-unstarted threads are retired synchronously.
            if attempt.thread.ident is None or attempt.thread.is_alive():
                continue
            if self._current_workers.get(key.session_id) == key:
                self._current_workers.pop(key.session_id)
            self._workers.pop(key)
            self._retiring_workers.remove(key)
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
    def _admission_cleanup_pending() -> SessionCleanupPending:
        return SessionCleanupPending(
            "another admission or failed-admission cleanup is in progress; "
            "retry admission later"
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
