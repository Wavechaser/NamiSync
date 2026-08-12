"""Bounded adapter-owned task identity and event-drain custody."""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Condition, Lock, get_ident
from time import monotonic
from typing import Protocol
from uuid import uuid4

from namisync.interfaces.service import PlanSession, SessionUpdate
from namisync.workflows.views import SessionEventView, SessionRecordView


_CAPACITY = 64
_DRAIN_WAIT_SECONDS = 25.0
_OPAQUE_ID = re.compile(r"[0-9a-f]{32}")
_TASK_ID = re.compile(r"task-[0-9a-f]{32}")


class TaskUnavailableError(LookupError):
    """A task is absent, closed, or does not own the supplied session."""


class DrainBusyError(RuntimeError):
    """A superseded event request has released the task drain claim."""


class ObservationConflictError(RuntimeError):
    """A task observation is already changing generation."""


class TaskIntentConflictError(RuntimeError):
    """A task command id was reused for a different resolved intent."""


class _TaskService(Protocol):
    def start_plan(
        self,
        source: str,
        target: str,
        *,
        deletion_policy: str | None = None,
        command_id: str | None = None,
        observation_sink: Callable[[SessionUpdate], None] | None = None,
    ) -> PlanSession: ...

    def reobserve(
        self,
        session_id: str,
        sink: Callable[[SessionUpdate], None],
        from_sequence: int,
    ) -> SessionRecordView: ...

    def unsubscribe(self, session_id: str) -> None: ...

    def close_session(self, session_id: str) -> None: ...

    def drop_plan(self, request_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class TaskStartView:
    task_id: str
    request_id: str
    session_id: str

    def __post_init__(self) -> None:
        if type(self.task_id) is not str or _TASK_ID.fullmatch(self.task_id) is None:
            raise ValueError("task id is invalid")
        _require_opaque_id(self.request_id, "task request id")
        _require_opaque_id(self.session_id, "task session id")


@dataclass(frozen=True, slots=True)
class TaskEventUpdateView:
    update_type: str
    event: SessionEventView

    def __post_init__(self) -> None:
        if self.update_type != "event" or type(self.event) is not SessionEventView:
            raise ValueError("task event update is invalid")


@dataclass(frozen=True, slots=True)
class TaskRecordUpdateView:
    update_type: str
    record: SessionRecordView

    def __post_init__(self) -> None:
        if self.update_type != "record" or type(self.record) is not SessionRecordView:
            raise ValueError("task record update is invalid")


TaskUpdateView = TaskEventUpdateView | TaskRecordUpdateView


@dataclass(frozen=True, slots=True)
class TaskDrainView:
    task_id: str
    session_id: str
    drain_id: str
    updates: tuple[TaskUpdateView, ...]

    def __post_init__(self) -> None:
        if type(self.task_id) is not str or _TASK_ID.fullmatch(self.task_id) is None:
            raise ValueError("task id is invalid")
        _require_opaque_id(self.session_id, "task session id")
        _require_opaque_id(self.drain_id, "task drain id")
        if type(self.updates) is not tuple or len(self.updates) > _CAPACITY:
            raise ValueError("task drain updates are invalid")


@dataclass(slots=True)
class _DrainClaim:
    drain_id: str
    superseded: bool = False


@dataclass(slots=True)
class _Compensation:
    plan: PlanSession
    unsubscribe_done: bool = False
    close_done: bool = False
    drop_done: bool = False

    @property
    def complete(self) -> bool:
        return self.unsubscribe_done and self.close_done and self.drop_done


@dataclass(slots=True)
class _TaskCleanup:
    session_id: str
    request_id: str
    unsubscribe_done: bool = False
    close_done: bool = False
    drop_done: bool = False

    @property
    def complete(self) -> bool:
        return self.unsubscribe_done and self.close_done and self.drop_done


@dataclass(slots=True)
class _TaskState:
    task_id: str
    command_id: str
    intent: tuple[str, str, str | None]
    condition: Condition = field(default_factory=Condition)
    session_id: str | None = None
    request_id: str | None = None
    generation: int = 0
    queue: deque[SessionUpdate] = field(default_factory=deque)
    terminal_record: SessionRecordView | None = None
    terminal_pending: bool = False
    active_drain: _DrainClaim | None = None
    transition: bool = False
    closing: bool = False
    observation_unsubscribed: bool = False
    cleanup_pending: bool = False
    compensation: _Compensation | None = None
    cleanup: _TaskCleanup | None = None
    recovery_caller: int | None = None

    def sink(self, generation: int) -> Callable[[SessionUpdate], None]:
        def accept(update: SessionUpdate) -> None:
            self._offer(generation, update)

        return accept

    def _offer(self, generation: int, update: SessionUpdate) -> None:
        if type(update) not in {SessionEventView, SessionRecordView}:
            raise TypeError("task updates must be exact service view types")
        update_session = update.session_id
        with self.condition:
            if self.closing or generation != self.generation:
                return
            if self.session_id is not None and update_session != self.session_id:
                raise ObservationConflictError(
                    "task observation delivered a mismatched session"
                )
            if type(update) is SessionRecordView:
                self.terminal_record = update
                self.terminal_pending = False
            if type(update) is SessionEventView and update.body_type == "Progress":
                self.queue = deque(
                    item
                    for item in self.queue
                    if not (
                        type(item) is SessionEventView
                        and item.body_type == "Progress"
                    )
                )
                if len(self.queue) >= _CAPACITY:
                    return
                self.queue.append(update)
                self.condition.notify_all()
                return

            if len(self.queue) >= _CAPACITY:
                self.queue = deque(
                    item
                    for item in self.queue
                    if not (
                        type(item) is SessionEventView
                        and item.body_type == "Progress"
                    )
                )
            while (
                len(self.queue) >= _CAPACITY
                and not self.closing
                and generation == self.generation
            ):
                if self.recovery_caller == get_ident():
                    raise ObservationConflictError(
                        "recovery delivered reliable updates synchronously"
                    )
                self.condition.wait()
            if self.closing or generation != self.generation:
                return
            self.queue.append(update)
            self.condition.notify_all()


@dataclass(slots=True)
class _StartEntry:
    command_id: str
    intent: tuple[str, str, str | None]
    task: _TaskState
    participants: int = 0
    complete: bool = False
    result: TaskStartView | None = None
    failure: BaseException | None = None


class TaskRegistry:
    """Own adapter task identity, observation generations, and bounded drains."""

    def __init__(
        self,
        service: _TaskService,
        *,
        token: Callable[[], str] | None = None,
        clock: Callable[[], float] = monotonic,
        drain_wait: float = _DRAIN_WAIT_SECONDS,
    ) -> None:
        if not callable(token) and token is not None:
            raise TypeError("task token factory must be callable")
        if not callable(clock):
            raise TypeError("task clock must be callable")
        if drain_wait <= 0:
            raise ValueError("task drain wait must be positive")
        self._service = service
        self._token = token if token is not None else _new_token
        self._clock = clock
        self._drain_wait = drain_wait
        self._condition = Condition(Lock())
        self._tasks: dict[str, _TaskState] = {}
        self._commands: dict[str, _StartEntry] = {}
        self._closing = False

    def start_plan(
        self,
        source: str,
        target: str,
        *,
        deletion_policy: str | None,
        command_id: str,
    ) -> TaskStartView:
        """Single-flight one resolved plan gesture and attach before scheduling."""

        _require_opaque_id(command_id, "task command id")
        intent = (source, target, deletion_policy)
        owner = False
        with self._condition:
            if self._closing:
                raise TaskUnavailableError("task registry is closing")
            entry = self._commands.get(command_id)
            if entry is None:
                task_id = self._mint_task_id()
                task = _TaskState(task_id, command_id, intent)
                entry = _StartEntry(command_id, intent, task)
                self._commands[command_id] = entry
                self._tasks[task_id] = task
                owner = True
            elif entry.intent != intent:
                raise TaskIntentConflictError("task command intent conflicts")
            entry.participants += 1

        try:
            if owner:
                self._start_owner(entry, source, target, deletion_policy)
            with self._condition:
                while not entry.complete:
                    self._condition.wait()
                if entry.result is not None:
                    return entry.result
                assert entry.failure is not None
                raise entry.failure
        finally:
            with self._condition:
                entry.participants -= 1
                if (
                    entry.complete
                    and entry.result is None
                    and entry.participants == 0
                    and not entry.task.cleanup_pending
                ):
                    if self._commands.get(command_id) is entry:
                        self._commands.pop(command_id, None)
                    if self._tasks.get(entry.task.task_id) is entry.task:
                        self._tasks.pop(entry.task.task_id, None)
                self._condition.notify_all()

    def _start_owner(
        self,
        entry: _StartEntry,
        source: str,
        target: str,
        deletion_policy: str | None,
    ) -> None:
        task = entry.task
        plan: PlanSession | None = None
        failure: BaseException | None = None
        try:
            plan = self._service.start_plan(
                source,
                target,
                deletion_policy=deletion_policy,
                command_id=entry.command_id,
                observation_sink=task.sink(task.generation),
            )
            if type(plan) is not PlanSession:
                raise RuntimeError("planning service returned invalid task data")
            _require_opaque_id(plan.request_id, "plan request id")
            _require_opaque_id(plan.session_id, "plan session id")
            with task.condition:
                if task.closing:
                    raise TaskUnavailableError("task registry closed during start")
                for update in task.queue:
                    if update.session_id != plan.session_id:
                        raise ObservationConflictError(
                            "task observation does not match admitted session"
                        )
                task.request_id = plan.request_id
                task.session_id = plan.session_id
                task.condition.notify_all()
            result = TaskStartView(task.task_id, plan.request_id, plan.session_id)
        except BaseException as error:
            failure = error
            if plan is not None:
                task.compensation = _Compensation(plan)
                self._attempt_compensation(task)
            result = None

        with self._condition:
            entry.result = result
            entry.failure = failure
            entry.complete = True
            self._condition.notify_all()

    def drain(
        self,
        task_id: str,
        session_id: str,
        drain_id: str,
        *,
        replay_from: int | None,
    ) -> TaskDrainView:
        _require_opaque_id(drain_id, "task drain id")
        task = self._require_task(task_id, session_id)
        deadline = self._clock() + self._drain_wait
        claim = _DrainClaim(drain_id)
        with task.condition:
            self._require_live_locked(task, session_id)
            if task.transition:
                raise ObservationConflictError("task observation is changing")
            incumbent = task.active_drain
            if incumbent is not None:
                incumbent.superseded = True
                task.condition.notify_all()
                while task.active_drain is incumbent:
                    remaining = deadline - self._clock()
                    if remaining <= 0:
                        break
                    task.condition.wait(remaining)
                raise DrainBusyError("task already has an event request")
            task.active_drain = claim

        try:
            if replay_from is not None:
                self._recover(task, session_id, replay_from)
            with task.condition:
                while (
                    not task.queue
                    and not task.terminal_pending
                    and not claim.superseded
                    and not task.closing
                ):
                    remaining = deadline - self._clock()
                    if remaining <= 0:
                        break
                    task.condition.wait(remaining)
                if task.closing:
                    raise TaskUnavailableError("task is closing")
                if claim.superseded:
                    updates: tuple[SessionUpdate, ...] = ()
                else:
                    count = min(_CAPACITY, len(task.queue))
                    drained = [task.queue.popleft() for _ in range(count)]
                    if (
                        len(drained) < _CAPACITY
                        and task.terminal_pending
                        and task.terminal_record is not None
                    ):
                        drained.append(task.terminal_record)
                        task.terminal_pending = False
                    updates = tuple(drained)
                    task.condition.notify_all()
        finally:
            with task.condition:
                if task.active_drain is claim:
                    task.active_drain = None
                task.condition.notify_all()

        return TaskDrainView(
            task_id,
            session_id,
            drain_id,
            tuple(_tag_update(update) for update in updates),
        )

    def _recover(
        self,
        task: _TaskState,
        session_id: str,
        replay_from: int,
    ) -> None:
        if isinstance(replay_from, bool) or not isinstance(replay_from, int) or replay_from < 1:
            raise ValueError("replay_from must be a positive integer")
        with task.condition:
            self._require_live_locked(task, session_id)
            if task.transition:
                raise ObservationConflictError("task observation is changing")
            task.transition = True
            task.generation += 1
            generation = task.generation
            task.recovery_caller = get_ident()
            task.queue.clear()
            task.terminal_record = None
            task.terminal_pending = False
            task.condition.notify_all()

        terminal: SessionRecordView | None = None
        failure: BaseException | None = None
        try:
            current = self._service.reobserve(
                session_id,
                task.sink(generation),
                replay_from,
            )
            if type(current) is not SessionRecordView:
                raise RuntimeError("reobserve returned invalid task data")
            if current.session_id != session_id:
                raise ObservationConflictError(
                    "reobserve returned a mismatched session"
                )
            if current.result is not None:
                terminal = current
        except BaseException as error:
            failure = error

        stale = False
        with task.condition:
            stale = task.closing or task.generation != generation
            if task.recovery_caller == get_ident():
                task.recovery_caller = None
            if not stale and failure is not None:
                task.generation += 1
                task.transition = False
                task.queue.clear()
                task.terminal_record = None
                task.terminal_pending = False
            if not stale and failure is None and terminal is not None:
                task.terminal_record = terminal
                if len(task.queue) < _CAPACITY:
                    task.queue.append(terminal)
                    task.terminal_pending = False
                else:
                    task.terminal_pending = True
            if not stale and task.generation == generation:
                task.transition = False
            task.condition.notify_all()
        if stale:
            try:
                if failure is None:
                    self._service.unsubscribe(session_id)
            finally:
                with task.condition:
                    if task.generation == generation or task.closing:
                        task.transition = False
                    task.condition.notify_all()
            if failure is None:
                raise TaskUnavailableError("task closed during observation recovery")
        if failure is not None:
            raise failure

    def begin_close(self) -> None:
        """Reject tasks and wake drains/producers without detaching observations."""

        with self._condition:
            self._closing = True
            tasks = tuple(self._tasks.values())
            self._condition.notify_all()
        for task in tasks:
            with task.condition:
                task.closing = True
                task.generation += 1
                if task.active_drain is not None:
                    task.active_drain.superseded = True
                task.condition.notify_all()

    def unsubscribe_all(self) -> None:
        """Detach task observations after admitted bridge handlers have left."""

        with self._condition:
            tasks = tuple(self._tasks.values())
        for task in tasks:
            if task.compensation is not None:
                self._attempt_compensation(task)
                if not task.cleanup_pending:
                    self._discard_failed_task(task)
                continue
            with task.condition:
                session_id = task.session_id
                already = task.observation_unsubscribed
            if session_id is None or already:
                continue
            self._service.unsubscribe(session_id)
            with task.condition:
                if task.session_id == session_id:
                    task.observation_unsubscribed = True

    def close_task(self, task_id: str) -> None:
        """Release one task's observer, terminal session, plan, and receipt."""

        with self._condition:
            task = self._tasks.get(task_id)
        if task is None:
            raise TaskUnavailableError("task is unavailable")
        if task.compensation is not None:
            self._attempt_compensation(task)
            if task.cleanup_pending:
                raise TaskUnavailableError("task cleanup remains pending")
            self._discard_failed_task(task)
            return
        with task.condition:
            task.closing = True
            task.generation += 1
            if task.active_drain is not None:
                task.active_drain.superseded = True
            task.condition.notify_all()
            while task.transition:
                task.condition.wait()
            session_id = task.session_id
            request_id = task.request_id
        if session_id is None or request_id is None:
            raise TaskUnavailableError("task has not completed admission")
        with task.condition:
            cleanup = task.cleanup
            if cleanup is None:
                cleanup = _TaskCleanup(session_id, request_id)
                task.cleanup = cleanup
        self._attempt_task_cleanup(cleanup)
        if not cleanup.complete:
            raise TaskUnavailableError("task cleanup remains pending")
        with self._condition:
            if self._tasks.get(task_id) is task:
                self._tasks.pop(task_id, None)
            if self._commands.get(task.command_id, None) is not None:
                self._commands.pop(task.command_id, None)
            self._condition.notify_all()

    def _require_task(self, task_id: str, session_id: str) -> _TaskState:
        if type(task_id) is not str or _TASK_ID.fullmatch(task_id) is None:
            raise TaskUnavailableError("task is unavailable")
        if type(session_id) is not str or _OPAQUE_ID.fullmatch(session_id) is None:
            raise TaskUnavailableError("task is unavailable")
        with self._condition:
            task = self._tasks.get(task_id)
        if task is None:
            raise TaskUnavailableError("task is unavailable")
        with task.condition:
            self._require_live_locked(task, session_id)
        return task

    @staticmethod
    def _require_live_locked(task: _TaskState, session_id: str) -> None:
        if task.closing or task.session_id != session_id:
            raise TaskUnavailableError("task is unavailable")

    def _mint_task_id(self) -> str:
        while True:
            token = self._token()
            if type(token) is not str or _OPAQUE_ID.fullmatch(token) is None:
                raise ValueError("task token must be 32 lowercase hex digits")
            task_id = f"task-{token}"
            if task_id not in self._tasks:
                return task_id

    def _attempt_compensation(self, task: _TaskState) -> None:
        compensation = task.compensation
        assert compensation is not None
        try:
            if not compensation.unsubscribe_done:
                self._service.unsubscribe(compensation.plan.session_id)
                compensation.unsubscribe_done = True
            if not compensation.close_done:
                self._service.close_session(compensation.plan.session_id)
                compensation.close_done = True
            if not compensation.drop_done:
                self._service.drop_plan(compensation.plan.request_id)
                compensation.drop_done = True
        except BaseException:
            task.cleanup_pending = True
            return
        task.cleanup_pending = not compensation.complete

    def _attempt_task_cleanup(self, cleanup: _TaskCleanup) -> None:
        if not cleanup.unsubscribe_done:
            self._service.unsubscribe(cleanup.session_id)
            cleanup.unsubscribe_done = True
        if not cleanup.close_done:
            self._service.close_session(cleanup.session_id)
            cleanup.close_done = True
        if not cleanup.drop_done:
            self._service.drop_plan(cleanup.request_id)
            cleanup.drop_done = True

    def _discard_failed_task(self, task: _TaskState) -> None:
        with self._condition:
            entry = self._commands.get(task.command_id)
            if entry is not None and entry.task is task and entry.participants == 0:
                self._commands.pop(task.command_id, None)
            if self._tasks.get(task.task_id) is task:
                self._tasks.pop(task.task_id, None)
            self._condition.notify_all()


def _tag_update(update: SessionUpdate) -> TaskUpdateView:
    if type(update) is SessionEventView:
        return TaskEventUpdateView("event", update)
    if type(update) is SessionRecordView:
        return TaskRecordUpdateView("record", update)
    raise TypeError("task updates must be exact service view types")


def _require_opaque_id(value: object, label: str) -> None:
    if type(value) is not str or _OPAQUE_ID.fullmatch(value) is None:
        raise RuntimeError(f"{label} is invalid")


def _new_token() -> str:
    return uuid4().hex


__all__ = [
    "DrainBusyError",
    "ObservationConflictError",
    "TaskDrainView",
    "TaskEventUpdateView",
    "TaskIntentConflictError",
    "TaskRecordUpdateView",
    "TaskRegistry",
    "TaskStartView",
    "TaskUnavailableError",
]
