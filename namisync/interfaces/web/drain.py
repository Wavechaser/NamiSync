"""Bounded adapter-owned task identity and event-drain custody."""

from __future__ import annotations

import re
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from math import isfinite
from threading import Condition, Lock, get_ident
from time import monotonic
from traceback import clear_frames
from types import MappingProxyType
from typing import Never, Protocol
from uuid import uuid4

from namisync.interfaces.service import PlanSession, SessionUpdate
from namisync.workflows.views import (
    SessionEventView, SessionRecordView, validate_session_event_view,
    validate_session_record_view,
)


_CAPACITY = 64
_TASK_CAPACITY = 48
_CLOSE_RECEIPT_CAPACITY = 48
_DRAIN_WAIT_SECONDS = 25.0
_PROGRESS_LINGER_SECONDS = 0.150
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


_START_FAILURE_OBSERVATION_CONFLICT = "observation_conflict"
_START_FAILURE_TASK_UNAVAILABLE = "task_unavailable"
_START_FAILURE_INTERRUPTED = "interrupted"
_START_FAILURE_GENERIC = "start_failed"
_START_FAILURES = MappingProxyType(
    {
        _START_FAILURE_OBSERVATION_CONFLICT: (
            ObservationConflictError,
            "task start observation conflicted",
        ),
        _START_FAILURE_TASK_UNAVAILABLE: (
            TaskUnavailableError,
            "task became unavailable during start",
        ),
        _START_FAILURE_INTERRUPTED: (
            KeyboardInterrupt,
            "task start was interrupted",
        ),
        _START_FAILURE_GENERIC: (RuntimeError, "task start failed"),
    }
)

_RECOVERY_FAILURE_OBSERVATION_CONFLICT = "observation_conflict"
_RECOVERY_FAILURE_TASK_UNAVAILABLE = "task_unavailable"
_RECOVERY_FAILURE_INTERRUPTED = "interrupted"
_RECOVERY_FAILURE_GENERIC = "recovery_failed"
_RECOVERY_FAILURES = MappingProxyType(
    {
        _RECOVERY_FAILURE_OBSERVATION_CONFLICT: (
            ObservationConflictError,
            "task observation recovery conflicted",
        ),
        _RECOVERY_FAILURE_TASK_UNAVAILABLE: (
            TaskUnavailableError,
            "task became unavailable during observation recovery",
        ),
        _RECOVERY_FAILURE_INTERRUPTED: (
            KeyboardInterrupt,
            "task observation recovery was interrupted",
        ),
        _RECOVERY_FAILURE_GENERIC: (
            RuntimeError,
            "task observation recovery failed",
        ),
    }
)


def _classify_start_failure(error: BaseException) -> str:
    if isinstance(error, ObservationConflictError):
        return _START_FAILURE_OBSERVATION_CONFLICT
    if isinstance(error, TaskUnavailableError):
        return _START_FAILURE_TASK_UNAVAILABLE
    if not isinstance(error, Exception):
        return _START_FAILURE_INTERRUPTED
    return _START_FAILURE_GENERIC


def _raise_start_failure(failure_code: str) -> Never:
    try:
        failure_type, message = _START_FAILURES[failure_code]
    except KeyError:
        raise RuntimeError("task start failure code is invalid") from None
    raise failure_type(message) from None


def _classify_recovery_failure(error: BaseException) -> str:
    if isinstance(error, ObservationConflictError):
        return _RECOVERY_FAILURE_OBSERVATION_CONFLICT
    if isinstance(error, TaskUnavailableError):
        return _RECOVERY_FAILURE_TASK_UNAVAILABLE
    if not isinstance(error, Exception):
        return _RECOVERY_FAILURE_INTERRUPTED
    return _RECOVERY_FAILURE_GENERIC


def _retire_adapter_exception(error: BaseException) -> None:
    raw_traceback = BaseException.__getattribute__(error, "__traceback__")
    if raw_traceback is not None:
        clear_frames(raw_traceback)
    BaseException.with_traceback(error, None)
    BaseException.__setattr__(error, "__cause__", None)
    BaseException.__setattr__(error, "__context__", None)


def _raise_recovery_failure(failure_code: str) -> Never:
    try:
        failure_type, message = _RECOVERY_FAILURES[failure_code]
    except KeyError:
        raise RuntimeError("task recovery failure code is invalid") from None
    raise failure_type(message) from None


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
class TaskCloseView:
    task_id: str
    session_id: str

    def __post_init__(self) -> None:
        if type(self.task_id) is not str or _TASK_ID.fullmatch(self.task_id) is None:
            raise ValueError("task id is invalid")
        _require_opaque_id(self.session_id, "task session id")


@dataclass(frozen=True, slots=True)
class TaskSessionReleaseView:
    task_id: str
    session_id: str

    def __post_init__(self) -> None:
        if type(self.task_id) is not str or _TASK_ID.fullmatch(self.task_id) is None:
            raise ValueError("task id is invalid")
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


def _validate_task_observation(
    update: object, *, expected_session_id: str | None = None,
) -> None:
    if type(update) is SessionEventView:
        validate_session_event_view(update, expected_session_id=expected_session_id)
    elif type(update) is SessionRecordView:
        validate_session_record_view(update, expected_session_id=expected_session_id)
        if update.kind != "sync-plan" or update.supports_pause or update.result is None:
            raise ValueError("task record requires a terminal sync-plan result")
    else:
        raise TypeError("task updates must be exact service view types")


def validate_task_update_view(
    value: object, *, expected_session_id: str | None = None,
) -> None:
    if (
        type(value) is TaskEventUpdateView
        and type(value.update_type) is str
        and value.update_type == "event"
    ):
        update = value.event
        if type(update) is not SessionEventView:
            raise TypeError("task event update has an invalid view")
    elif (
        type(value) is TaskRecordUpdateView
        and type(value.update_type) is str
        and value.update_type == "record"
    ):
        update = value.record
        if type(update) is not SessionRecordView:
            raise TypeError("task record update has an invalid view")
    else:
        raise TypeError("task update tag or view is invalid")
    _validate_task_observation(update, expected_session_id=expected_session_id)


def validate_task_drain_view(value: object) -> None:
    if type(value) is not TaskDrainView:
        raise TypeError("task drain must be an exact view")
    # Recheck the outer contract as well as mutable nested collaborator data.
    value.__post_init__()
    for update in value.updates:
        validate_task_update_view(update, expected_session_id=value.session_id)


def _is_progress_update(update: SessionUpdate) -> bool:
    return type(update) is SessionEventView and update.body_type == "Progress"


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
    def session_complete(self) -> bool:
        return self.unsubscribe_done and self.close_done

    @property
    def complete(self) -> bool:
        return self.session_complete and self.drop_done


@dataclass(slots=True)
class _TaskState:
    task_id: str
    command_id: str
    intent: tuple[str, str, str | None]
    clock: Callable[[], float]
    condition: Condition = field(default_factory=Condition)
    session_id: str | None = None
    request_id: str | None = None
    generation: int = 0
    queue: deque[SessionUpdate] = field(default_factory=deque)
    progress_available_at: float | None = None
    terminal_record: SessionRecordView | None = None
    terminal_pending: bool = False
    active_drain: _DrainClaim | None = None
    transition: bool = False
    closing: bool = False
    observation_unsubscribed: bool = False
    cleanup_pending: bool = False
    compensation: _Compensation | None = None
    compensation_in_progress: bool = False
    cleanup: _TaskCleanup | None = None
    cleanup_in_progress: bool = False
    closed: bool = False
    terminal_delivered: bool = False
    session_release_started: bool = False
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
            _validate_task_observation(update, expected_session_id=self.session_id)
            if type(update) is SessionRecordView:
                self.terminal_record = update
                self.terminal_pending = False
            if _is_progress_update(update):
                replacing_progress = any(
                    _is_progress_update(item) for item in self.queue
                )
                self.queue = deque(
                    item
                    for item in self.queue
                    if not _is_progress_update(item)
                )
                if len(self.queue) >= _CAPACITY:
                    self.progress_available_at = None
                    return
                if self.queue:
                    self.progress_available_at = None
                elif not replacing_progress or self.progress_available_at is None:
                    self.progress_available_at = self.clock()
                self.queue.append(update)
                self.condition.notify_all()
                return

            if len(self.queue) >= _CAPACITY:
                self.queue = deque(
                    item
                    for item in self.queue
                    if not _is_progress_update(item)
                )
                self.progress_available_at = None
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
            self.progress_available_at = None
            self.condition.notify_all()


@dataclass(slots=True)
class _StartEntry:
    command_id: str
    intent: tuple[str, str, str | None]
    wire_intent: tuple[str, str, str | None] | None
    task: _TaskState
    participants: int = 0
    complete: bool = False
    result: TaskStartView | None = None
    failure_code: str | None = None


class TaskRegistry:
    """Own adapter task identity, observation generations, and bounded drains."""

    def __init__(
        self,
        service: _TaskService,
        *,
        token: Callable[[], str] | None = None,
        clock: Callable[[], float] = monotonic,
        drain_wait: float = _DRAIN_WAIT_SECONDS,
        progress_linger: float = _PROGRESS_LINGER_SECONDS,
        task_capacity: int = _TASK_CAPACITY,
    ) -> None:
        if not callable(token) and token is not None:
            raise TypeError("task token factory must be callable")
        if not callable(clock):
            raise TypeError("task clock must be callable")
        if drain_wait <= 0:
            raise ValueError("task drain wait must be positive")
        if isinstance(progress_linger, bool) or not isinstance(
            progress_linger, (int, float)
        ):
            raise TypeError("task progress linger must be a number")
        try:
            normalized_progress_linger = float(progress_linger)
        except OverflowError:
            normalized_progress_linger = float("inf")
        if (
            not isfinite(normalized_progress_linger)
            or normalized_progress_linger <= 0
        ):
            raise ValueError("task progress linger must be positive and finite")
        if isinstance(task_capacity, bool) or not isinstance(task_capacity, int):
            raise TypeError("task capacity must be an integer")
        if task_capacity <= 0 or task_capacity > _TASK_CAPACITY:
            raise ValueError(f"task capacity must be between 1 and {_TASK_CAPACITY}")
        self._service = service
        self._token = token if token is not None else _new_token
        self._clock = clock
        self._drain_wait = drain_wait
        self._progress_linger = normalized_progress_linger
        self._task_capacity = task_capacity
        self._condition = Condition(Lock())
        self._tasks: dict[str, _TaskState] = {}
        self._commands: dict[str, _StartEntry] = {}
        self._close_receipts: OrderedDict[
            tuple[str, str], TaskCloseView
        ] = OrderedDict()
        self._closing = False

    def start_plan(
        self,
        source: str,
        target: str,
        *,
        deletion_policy: str | None,
        command_id: str,
        wire_intent: tuple[str, str, str | None] | None = None,
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
                if len(self._tasks) >= self._task_capacity:
                    raise TaskUnavailableError("task capacity is exhausted")
                task_id = self._mint_task_id()
                task = _TaskState(task_id, command_id, intent, self._clock)
                entry = _StartEntry(command_id, intent, wire_intent, task)
                self._commands[command_id] = entry
                self._tasks[task_id] = task
                owner = True
            elif entry.intent != intent:
                raise TaskIntentConflictError("task command intent conflicts")
            entry.participants += 1

        try:
            if owner:
                self._start_owner(entry, source, target, deletion_policy)
            return self._await_start_entry(entry)
        finally:
            self._leave_start_entry(entry)

    def replay_start(
        self,
        command_id: str,
        wire_intent: tuple[str, str, str | None],
    ) -> TaskStartView | None:
        """Return an exact retained wire replay before volatile slots resolve."""

        _require_opaque_id(command_id, "task command id")
        with self._condition:
            if self._closing:
                raise TaskUnavailableError("task registry is closing")
            entry = self._commands.get(command_id)
            if entry is None:
                return None
            if entry.wire_intent != wire_intent:
                if entry.intent[2] != wire_intent[2]:
                    raise TaskIntentConflictError("task command intent conflicts")
                return None
            entry.participants += 1
        try:
            if entry.complete and entry.result is None and entry.task.cleanup_pending:
                retry_failure_code: str | None = None
                try:
                    self._retry_compensation(entry.task)
                except BaseException as error:
                    retry_failure_code = _classify_start_failure(error)
                if retry_failure_code is not None:
                    _raise_start_failure(retry_failure_code)
            return self._await_start_entry(entry)
        finally:
            self._leave_start_entry(entry)

    def _await_start_entry(self, entry: _StartEntry) -> TaskStartView:
        with self._condition:
            while not entry.complete:
                self._condition.wait()
            if entry.result is not None:
                return entry.result
            assert entry.failure_code is not None
            _raise_start_failure(entry.failure_code)

    def _leave_start_entry(self, entry: _StartEntry) -> None:
        with self._condition:
            entry.participants -= 1
            if (
                entry.complete
                and entry.result is None
                and entry.participants == 0
                and not entry.task.cleanup_pending
            ):
                if self._commands.get(entry.command_id) is entry:
                    self._commands.pop(entry.command_id, None)
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
        failure_code: str | None = None
        try:
            candidate = self._service.start_plan(
                source,
                target,
                deletion_policy=deletion_policy,
                command_id=entry.command_id,
                observation_sink=task.sink(task.generation),
            )
            if type(candidate) is not PlanSession:
                raise RuntimeError("planning service returned invalid task data")
            request_id = candidate.request_id
            session_id = candidate.session_id
            _require_opaque_id(request_id, "plan request id")
            _require_opaque_id(session_id, "plan session id")
            plan = PlanSession(request_id, session_id)
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
            failure_code = _classify_start_failure(error)
            if plan is not None:
                task.compensation = _Compensation(plan)
                try:
                    self._attempt_compensation(task)
                except BaseException as cleanup_error:
                    failure_code = _classify_start_failure(cleanup_error)
            result = None

        with self._condition:
            entry.result = result
            entry.failure_code = failure_code
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
                while not claim.superseded and not task.closing:
                    if replay_from is not None or task.terminal_pending or any(
                        not _is_progress_update(update) for update in task.queue
                    ):
                        break
                    now = self._clock()
                    if task.queue:
                        if task.progress_available_at is None:
                            task.progress_available_at = now
                        wake_deadline = min(
                            deadline,
                            task.progress_available_at + self._progress_linger,
                        )
                    else:
                        task.progress_available_at = None
                        wake_deadline = deadline
                    remaining = wake_deadline - now
                    if remaining <= 0:
                        break
                    task.condition.wait(remaining)
                if task.closing:
                    raise TaskUnavailableError("task is closing")
                count = 0 if claim.superseded else min(_CAPACITY, len(task.queue))
                drained = list(task.queue)[:count]
                include_terminal = (
                    not claim.superseded
                    and len(drained) < _CAPACITY
                    and task.terminal_pending
                    and task.terminal_record is not None
                )
                if include_terminal:
                    drained.append(task.terminal_record)
                result = TaskDrainView(
                    task_id, session_id, drain_id,
                    tuple(_tag_update(update) for update in drained),
                )
                validate_task_drain_view(result)
                if not claim.superseded:
                    for _ in range(count):
                        task.queue.popleft()
                    if include_terminal:
                        task.terminal_pending = False
                    if not any(
                        _is_progress_update(update) for update in task.queue
                    ):
                        task.progress_available_at = None
                    if any(type(update) is SessionRecordView for update in drained):
                        task.terminal_delivered = True
                    task.condition.notify_all()
        finally:
            with task.condition:
                if task.active_drain is claim:
                    task.active_drain = None
                task.condition.notify_all()

        return result

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
            task.progress_available_at = None
            task.terminal_record = None
            task.terminal_pending = False
            task.condition.notify_all()

        terminal: SessionRecordView | None = None
        failure_code: str | None = None
        current: object | None = None
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
            validate_session_record_view(current, expected_session_id=session_id)
            if current.result is not None:
                _validate_task_observation(current, expected_session_id=session_id)
                terminal = current
        except BaseException as error:
            failure_code = _classify_recovery_failure(error)
            _retire_adapter_exception(error)
        finally:
            current = None

        stale = False
        with task.condition:
            stale = task.closing or task.generation != generation
            if task.recovery_caller == get_ident():
                task.recovery_caller = None
            if not stale and failure_code is not None:
                task.generation += 1
                task.transition = False
                task.queue.clear()
                task.progress_available_at = None
                task.terminal_record = None
                task.terminal_pending = False
            if not stale and failure_code is None and terminal is not None:
                task.terminal_record = terminal
                task.progress_available_at = None
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
                if failure_code is None:
                    try:
                        self._service.unsubscribe(session_id)
                    except BaseException as error:
                        failure_code = _classify_recovery_failure(error)
                        _retire_adapter_exception(error)
                    else:
                        with task.condition:
                            task.observation_unsubscribed = True
            finally:
                with task.condition:
                    if (
                        task.generation == generation
                        or task.closing
                        or task.session_release_started
                    ):
                        task.transition = False
                    task.condition.notify_all()
            if failure_code is None:
                failure_code = _RECOVERY_FAILURE_TASK_UNAVAILABLE
        if failure_code is not None:
            terminal = None
            _raise_recovery_failure(failure_code)

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
                cleanup = task.cleanup
                already = task.observation_unsubscribed or (
                    cleanup is not None and cleanup.unsubscribe_done
                )
            if session_id is None or already:
                continue
            self._service.unsubscribe(session_id)
            with task.condition:
                if task.session_id == session_id:
                    task.observation_unsubscribed = True
                    if task.cleanup is not None:
                        task.cleanup.unsubscribe_done = True

    def release_terminal_session(
        self,
        task_id: str,
        session_id: str,
    ) -> TaskSessionReleaseView:
        """Release terminal stream authority while retaining the task and plan."""

        self._require_task_identity(task_id, session_id)
        receipt_key = (task_id, session_id)
        with self._condition:
            close_receipt = self._close_receipts.get(receipt_key)
            if close_receipt is not None:
                self._close_receipts.move_to_end(receipt_key)
                return TaskSessionReleaseView(task_id, session_id)
            task = self._tasks.get(task_id)
        if task is None or task.compensation is not None:
            raise TaskUnavailableError("task is unavailable")

        with task.condition:
            if task.session_id != session_id:
                raise TaskUnavailableError("task is unavailable")
            if not task.terminal_delivered:
                raise TaskUnavailableError("task terminal record was not drained")
            while task.cleanup_in_progress:
                task.condition.wait()
            cleanup = task.cleanup
            if task.closed or (
                cleanup is not None and cleanup.session_complete
            ):
                return TaskSessionReleaseView(task_id, session_id)
            task.cleanup_in_progress = True
            task.session_release_started = True
            task.generation += 1
            if task.active_drain is not None:
                task.active_drain.superseded = True
            task.condition.notify_all()
            while task.transition:
                task.condition.wait()
            request_id = task.request_id
            if request_id is None:
                task.cleanup_in_progress = False
                task.condition.notify_all()
                raise TaskUnavailableError("task has not completed admission")
            cleanup = task.cleanup
            if cleanup is None:
                cleanup = _TaskCleanup(
                    session_id,
                    request_id,
                    unsubscribe_done=task.observation_unsubscribed,
                )
                task.cleanup = cleanup

        try:
            self._attempt_session_release(task, cleanup)
            if not cleanup.session_complete:
                raise TaskUnavailableError("task session release remains pending")
        except BaseException:
            with task.condition:
                task.cleanup_in_progress = False
                task.condition.notify_all()
            raise

        with task.condition:
            task.cleanup_in_progress = False
            task.condition.notify_all()
        return TaskSessionReleaseView(task_id, session_id)

    def close_task(self, task_id: str, session_id: str) -> TaskCloseView:
        """Explicitly release one terminal task and its retained plan."""

        self._require_task_identity(task_id, session_id)
        receipt_key = (task_id, session_id)
        with self._condition:
            receipt = self._close_receipts.get(receipt_key)
            if receipt is not None:
                self._close_receipts.move_to_end(receipt_key)
                return receipt
            task = self._tasks.get(task_id)
        if task is None:
            raise TaskUnavailableError("task is unavailable")
        if task.compensation is not None:
            self._attempt_compensation(task)
            if task.cleanup_pending:
                raise TaskUnavailableError("task cleanup remains pending")
            self._discard_failed_task(task)
            raise TaskUnavailableError("task is unavailable")
        with task.condition:
            if task.session_id != session_id:
                raise TaskUnavailableError("task is unavailable")
            if not task.terminal_delivered:
                raise TaskUnavailableError("task terminal record was not drained")
            while task.cleanup_in_progress:
                task.condition.wait()
            if task.closed:
                return TaskCloseView(task_id, session_id)
            task.cleanup_in_progress = True
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
            with task.condition:
                task.cleanup_in_progress = False
                task.condition.notify_all()
            raise TaskUnavailableError("task has not completed admission")
        with task.condition:
            cleanup = task.cleanup
            if cleanup is None:
                cleanup = _TaskCleanup(
                    session_id,
                    request_id,
                    unsubscribe_done=task.observation_unsubscribed,
                )
                task.cleanup = cleanup
        try:
            self._attempt_task_cleanup(task, cleanup)
            if not cleanup.complete:
                raise TaskUnavailableError("task cleanup remains pending")
        except BaseException:
            with task.condition:
                task.cleanup_in_progress = False
                task.condition.notify_all()
            raise
        result = TaskCloseView(task_id, session_id)
        with self._condition:
            if self._tasks.get(task_id) is task:
                self._tasks.pop(task_id, None)
            if self._commands.get(task.command_id, None) is not None:
                self._commands.pop(task.command_id, None)
            self._close_receipts[receipt_key] = result
            self._close_receipts.move_to_end(receipt_key)
            while len(self._close_receipts) > _CLOSE_RECEIPT_CAPACITY:
                self._close_receipts.popitem(last=False)
            self._condition.notify_all()
        with task.condition:
            task.closed = True
            task.cleanup_in_progress = False
            task.condition.notify_all()
        return result

    def _require_task(self, task_id: str, session_id: str) -> _TaskState:
        self._require_task_identity(task_id, session_id)
        with self._condition:
            task = self._tasks.get(task_id)
        if task is None:
            raise TaskUnavailableError("task is unavailable")
        with task.condition:
            self._require_live_locked(task, session_id)
        return task

    @staticmethod
    def _require_live_locked(task: _TaskState, session_id: str) -> None:
        if (
            task.closing
            or task.session_release_started
            or task.session_id != session_id
        ):
            raise TaskUnavailableError("task is unavailable")

    @staticmethod
    def _require_task_identity(task_id: str, session_id: str) -> None:
        if type(task_id) is not str or _TASK_ID.fullmatch(task_id) is None:
            raise TaskUnavailableError("task is unavailable")
        if type(session_id) is not str or _OPAQUE_ID.fullmatch(session_id) is None:
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
        except Exception:
            task.cleanup_pending = True
            return
        except BaseException:
            task.cleanup_pending = True
            raise
        task.cleanup_pending = not compensation.complete

    def _retry_compensation(self, task: _TaskState) -> None:
        with task.condition:
            while task.compensation_in_progress:
                task.condition.wait()
            if not task.cleanup_pending:
                return
            task.compensation_in_progress = True
        try:
            self._attempt_compensation(task)
        finally:
            with task.condition:
                task.compensation_in_progress = False
                task.condition.notify_all()

    def _attempt_session_release(
        self,
        task: _TaskState,
        cleanup: _TaskCleanup,
    ) -> None:
        if not cleanup.unsubscribe_done:
            self._service.unsubscribe(cleanup.session_id)
            cleanup.unsubscribe_done = True
            with task.condition:
                task.observation_unsubscribed = True
        if not cleanup.close_done:
            self._service.close_session(cleanup.session_id)
            cleanup.close_done = True

    def _attempt_task_cleanup(
        self,
        task: _TaskState,
        cleanup: _TaskCleanup,
    ) -> None:
        self._attempt_session_release(task, cleanup)
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
    "TaskCloseView",
    "TaskEventUpdateView",
    "TaskIntentConflictError",
    "TaskRecordUpdateView",
    "TaskRegistry",
    "TaskSessionReleaseView",
    "TaskStartView",
    "TaskUnavailableError",
]
