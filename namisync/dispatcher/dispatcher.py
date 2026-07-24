"""Domain-blind M0 session admission, scheduling, control, and custody."""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from datetime import datetime, timezone
from threading import Condition, Lock, Thread
from time import monotonic
from typing import Callable
from uuid import uuid4

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
    run_session,
)
from namisync.dispatcher.contracts import (
    AdmissionClosed,
    AuditObserverFactory,
    ControlCode,
    ControlAction,
    ControlResult,
    Registry,
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
from namisync.dispatcher.event_bus import EventHub, EventStream, UtcClock
from namisync.dispatcher.store import InMemorySessionStore


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

        self._condition = Condition()
        self._records: dict[SessionId, SessionRecord] = {}
        self._controls: dict[SessionId, _Control] = {}
        self._hubs: dict[SessionId, EventHub] = {}
        self._item_events: dict[SessionId, list[ResultItem]] = {}
        self._pending: deque[SessionId] = deque()
        self._reserved: set[ResourceId] = set()
        self._leases: dict[SessionId, ResourceLease] = {}
        self._workers: dict[SessionId, Thread] = {}
        self._admitting = 0
        self._admission_order = 0
        self._accepting = True
        self._store_failures: list[BaseException] = []
        self._custody_failures: list[BaseException] = []
        self._scheduler = Thread(
            target=self._schedule,
            name="namisync-dispatcher",
            daemon=True,
        )
        self._scheduler.start()

    def submit(self, kind: str, request: object) -> SessionId:
        with self._condition:
            if not self._accepting:
                raise AdmissionClosed("dispatcher is no longer accepting sessions")
            registration = self._registry.get(kind)
            if registration is not None:
                self._admitting += 1
        if registration is None:
            raise UnknownWorkflowKind(kind)
        try:
            return self._admit(kind, request, registration)
        finally:
            with self._condition:
                self._admitting -= 1
                self._condition.notify_all()

    def _admit(
        self, kind: str, request: object, registration: WorkflowRegistration
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
        observer = self._audit_factory(record)
        hub = EventHub(
            session_id=session_id,
            initial_state=record.state,
            clock=self._clock,
            observer=observer,
            replay_capacity=self._replay_capacity,
            subscriber_capacity=self._subscriber_capacity,
            audit_capacity=self._audit_capacity,
            audit_timeout=self._audit_timeout,
        )
        try:
            self._store.put(record)
        except BaseException:
            hub.close(self._audit_timeout)
            raise
        with self._condition:
            stopped = not self._accepting
            if not stopped:
                self._records[session_id] = record
                self._controls[session_id] = _Control()
                self._hubs[session_id] = hub
                self._item_events[session_id] = []
                self._pending.append(session_id)
        if stopped:
            try:
                self._store.drop(session_id)
            finally:
                hub.close(self._audit_timeout)
            raise AdmissionClosed("dispatcher stopped during admission")
        hub.emit(StateChanged(SessionState.PENDING))
        with self._condition:
            self._condition.notify_all()
        return session_id

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
            hub = self._hubs.get(session_id)
            if hub is None:
                raise SessionNotFound(str(session_id))
        return hub.subscribe(from_seq)

    def pause(self, session_id: SessionId) -> ControlResult:
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
            updated, hub = self._transition_locked(session_id, SessionState.PAUSING)
        hub.emit(StateChanged(updated.state))
        return ControlResult(
            ControlCode.ACCEPTED,
            session_id,
            record.state,
            updated.state,
            "pause requested; custody releases after the next checkpoint",
        )

    def resume(self, session_id: SessionId) -> ControlResult:
        with self._condition:
            record = self._records.get(session_id)
            if record is None:
                return self._missing_control(session_id)
            if control_decision(
                ControlAction.RESUME, record.state, record.supports_pause
            ) is not ControlCode.ACCEPTED:
                return self._illegal_control(record, "resume")
            self._controls[session_id].reset()
            updated, hub = self._transition_locked(session_id, SessionState.PENDING)
            self._pending.append(session_id)
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
            updated, hub = self._transition_locked(session_id, SessionState.CANCELING)
            if record.state in (
                SessionState.PENDING,
                SessionState.PAUSED,
                SessionState.INTERRUPTED,
            ) and session_id not in self._pending:
                self._pending.append(session_id)
            self._condition.notify_all()
        hub.emit(StateChanged(updated.state))
        return ControlResult(
            ControlCode.ACCEPTED,
            session_id,
            record.state,
            updated.state,
            "cancellation requested",
        )

    def close(self, session_id: SessionId) -> None:
        with self._condition:
            record = self._records.get(session_id)
            if record is None:
                raise SessionNotFound(str(session_id))
            if not self._is_settled(record):
                raise SessionNotTerminal(str(session_id))
        self._store.drop(session_id)
        with self._condition:
            hub = self._hubs.pop(session_id)
            self._records.pop(session_id, None)
            self._controls.pop(session_id, None)
            self._item_events.pop(session_id, None)
        hub.close(self._audit_timeout)

    def shutdown(self, timeout: float = 10.0) -> ShutdownResult:
        if timeout < 0:
            raise ValueError("shutdown timeout cannot be negative")
        deadline = monotonic() + timeout
        with self._condition:
            self._accepting = False
            candidates = tuple(
                record.session_id
                for record in self._records.values()
                if not is_terminal(record.state)
            )
            self._condition.notify_all()
        for session_id in candidates:
            self.cancel(session_id)

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
            unfinished = tuple(
                record.session_id
                for record in self._records.values()
                if not self._is_settled(record)
            )
            custody_released = not self._leases and not self._reserved

        remaining = max(0.0, deadline - monotonic())
        self._scheduler.join(remaining)
        observer_incomplete: list[SessionId] = []
        terminal_hubs = tuple(
            (session_id, self._hubs[session_id])
            for session_id, record in self._records.items()
            if self._is_settled(record)
        )
        for session_id, hub in terminal_hubs:
            remaining = max(0.0, deadline - monotonic())
            if not hub.close(remaining):
                observer_incomplete.append(session_id)
        all_unfinished = tuple(dict.fromkeys((*unfinished, *observer_incomplete)))
        complete = (
            not all_unfinished
            and custody_released
            and not self._scheduler.is_alive()
            and self._admitting == 0
        )
        return ShutdownResult(complete, all_unfinished, custody_released)

    def _schedule(self) -> None:
        while True:
            launches: list[Thread] = []
            with self._condition:
                while not launches:
                    selected: list[SessionId] = []
                    waiting_resources: set[ResourceId] = set()
                    for session_id in tuple(self._pending):
                        record = self._records.get(session_id)
                        if record is None:
                            selected.append(session_id)
                            continue
                        if record.state is SessionState.CANCELING:
                            selected.append(session_id)
                            continue
                        if record.state is not SessionState.PENDING:
                            selected.append(session_id)
                            continue
                        if any(
                            resource in self._reserved
                            or resource in waiting_resources
                            for resource in record.resources
                        ):
                            waiting_resources.update(record.resources)
                            continue
                        self._reserved.update(record.resources)
                        selected.append(session_id)
                    if selected:
                        selected_set = set(selected)
                        self._pending = deque(
                            item for item in self._pending if item not in selected_set
                        )
                        for session_id in selected:
                            if session_id not in self._records:
                                continue
                            worker = Thread(
                                target=self._run_worker,
                                args=(session_id,),
                                name=f"namisync-session-{session_id}",
                                daemon=True,
                            )
                            self._workers[session_id] = worker
                            launches.append(worker)
                    elif not self._accepting and not self._pending and not self._workers:
                        return
                    else:
                        self._condition.wait()
            for worker in launches:
                worker.start()

    def _run_worker(self, session_id: SessionId) -> None:
        try:
            with self._condition:
                record = self._records[session_id]
                registration = self._registry[record.kind]
                control = self._controls[session_id]
            if record.state is SessionState.CANCELING:
                self._run_core(
                    session_id,
                    registration,
                    invocation=None,
                    disposition=self._disposition(record),
                    failure=None,
                )
                return
            try:
                lease = self._lock_provider.acquire(
                    record.resources, control.cancel_requested
                )
            except Canceled:
                self._run_core(
                    session_id,
                    registration,
                    invocation=None,
                    disposition=self._disposition(record),
                    failure=None,
                )
                return
            except BaseException as error:
                self._run_core(
                    session_id,
                    registration,
                    invocation=None,
                    disposition=Disposition.UNRUN,
                    failure=error,
                )
                return
            with self._condition:
                self._leases[session_id] = lease
                current = self._records[session_id]
            if current.state is SessionState.CANCELING:
                self._run_core(
                    session_id,
                    registration,
                    invocation=None,
                    disposition=self._disposition(current),
                    failure=None,
                )
                return
            try:
                invocation = registration.open(current.payload)
            except BaseException as error:
                self._run_core(
                    session_id,
                    registration,
                    invocation=None,
                    disposition=Disposition.UNRUN,
                    failure=error,
                )
                return
            with self._condition:
                current = self._records[session_id]
                if current.state is not SessionState.CANCELING:
                    updated, hub = self._transition_locked(
                        session_id, SessionState.RUNNING
                    )
                else:
                    updated = None
                    hub = None
            if updated is not None and hub is not None:
                hub.emit(StateChanged(updated.state))
            self._run_core(
                session_id,
                registration,
                invocation=invocation if updated is not None else None,
                disposition=(Disposition.RAN if updated is not None else self._disposition(current)),
                failure=None,
            )
        finally:
            self._release_custody(session_id)
            self._worker_done(session_id)

    def _run_core(
        self,
        session_id: SessionId,
        registration: WorkflowRegistration,
        *,
        invocation: WorkflowInvocation | None,
        disposition: Disposition,
        failure: BaseException | None,
    ) -> None:
        with self._condition:
            control = self._controls[session_id]
            hub = self._hubs[session_id]

        def work(context):
            context.checkpoint()
            if failure is not None:
                raise failure
            if invocation is None:
                raise Canceled()
            try:
                return invocation.run(context)
            except PauseRequested:
                if not registration.supports_pause:
                    raise RuntimeError("registered invocation paused without capability")
                self._replace_payload(session_id, invocation.snapshot())
                raise

        outcome = run_session(
            work,
            emit=hub.emit,
            checkpoint=control.checkpoint,
            settle=lambda state, result: self._settle(session_id, state, result),
            finalize_audit=hub.finalize_audit,
            publish_result=lambda result: self._publish_result(session_id, result),
            disposition=disposition,
            item_accumulator=self._item_events[session_id],
        )
        if not outcome.paused:
            with self._condition:
                self._item_events.pop(session_id, None)

    def _settle(
        self,
        session_id: SessionId,
        state: SessionState,
        result: OperationResult | None,
    ) -> None:
        self._release_custody(session_id)
        # The audit axis is not settled yet. A terminal record may be visible
        # briefly without a result, but it must never expose provisional
        # ``audit=OK`` before the observer acknowledges finalization.
        transition_result = None if is_terminal(state) else result
        updated, hub = self._transition(session_id, state, transition_result)
        hub.emit(StateChanged(updated.state))

    def _publish_result(self, session_id: SessionId, result: OperationResult) -> None:
        with self._condition:
            record = self._records[session_id]
            updated = replace(record, result=result)
            self._records[session_id] = updated
            self._persist_locked(updated)
            self._condition.notify_all()

    def _replace_payload(self, session_id: SessionId, payload: bytes) -> None:
        if not isinstance(payload, bytes):
            raise TypeError("workflow continuation snapshot must be bytes")
        with self._condition:
            record = self._records[session_id]
            updated = replace(record, payload=payload)
            self._records[session_id] = updated
            self._persist_locked(updated)

    def _transition(
        self,
        session_id: SessionId,
        state: SessionState,
        result: OperationResult | None = None,
    ) -> tuple[SessionRecord, EventHub]:
        with self._condition:
            return self._transition_locked(session_id, state, result)

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

    def _release_custody(self, session_id: SessionId) -> None:
        with self._condition:
            lease = self._leases.pop(session_id, None)
            record = self._records.get(session_id)
        if lease is not None:
            try:
                lease.release()
            except BaseException as error:
                with self._condition:
                    self._custody_failures.append(error)
        with self._condition:
            if record is not None:
                self._reserved.difference_update(record.resources)
            self._condition.notify_all()

    def _worker_done(self, session_id: SessionId) -> None:
        transition: tuple[SessionRecord, EventHub] | None = None
        with self._condition:
            self._workers.pop(session_id, None)
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
                self._pending.append(session_id)
            self._condition.notify_all()
        if transition is not None:
            updated, hub = transition
            hub.emit(StateChanged(updated.state))

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
