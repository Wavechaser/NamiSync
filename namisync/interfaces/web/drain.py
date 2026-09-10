"""Bounded adapter-owned task identity and event-drain custody."""

from __future__ import annotations

import re
from collections import OrderedDict, deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from itertools import chain, islice
from math import isfinite
from threading import Condition, Lock, get_ident
from time import monotonic
from types import MappingProxyType
from typing import Never

from namisync.interfaces.task_port import (
    _validate_task_observation,
    TaskCloseRequestView,
    TaskCloseView,
    TaskDeliveryFactory,
    TaskDeliveryUpdate,
    TaskDrainView,
    TaskEventUpdateView,
    TaskIntentConflictError,
    TaskLifecyclePort,
    TaskListView,
    TaskRecordUpdateView,
    TaskSessionReleaseView,
    TaskShellView,
    TaskStartView,
    TaskStartOutcome,
    TaskSetupSnapshotView,
    TaskSummaryView,
    TaskTerminalDelivery,
    TaskUnavailableError,
    TaskUpdateView,
)
from namisync.workflows.views import (
    SessionEventView,
    SessionRecordView,
    SetupOptionsView,
    validate_session_record_view,
)
from namisync.workflows.inventory import LocationCandidate, RememberedLocations

from ._exception_graph import retire_exception_graph as _retire_exception_graph


_CAPACITY = 64
_START_RESPONSE_CAPACITY = 48
_CLOSE_RECEIPT_CAPACITY = 48
_DRAIN_WAIT_SECONDS = 25.0
_PROGRESS_LINGER_SECONDS = 0.150
_OPAQUE_ID = re.compile(r"[0-9a-f]{32}")
_TASK_ID = re.compile(r"task-[0-9a-f]{32}")


class DrainBusyError(RuntimeError):
    """A superseded event request has released the task drain claim."""


class ObservationConflictError(RuntimeError):
    """A task observation is already changing generation."""


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


def _raise_recovery_failure(failure_code: str) -> Never:
    try:
        failure_type, message = _RECOVERY_FAILURES[failure_code]
    except KeyError:
        raise RuntimeError("task recovery failure code is invalid") from None
    raise failure_type(message) from None


def _is_progress_update(update: TaskDeliveryUpdate) -> bool:
    return type(update) is SessionEventView and update.body_type == "Progress"


@dataclass(slots=True)
class _DrainClaim:
    drain_id: str
    superseded: bool = False


@dataclass(slots=True)
class _TaskState:
    task_id: str
    command_id: str
    clock: Callable[[], float]
    condition: Condition = field(default_factory=Condition)
    session_id: str | None = None
    generation: int = 0
    queue: deque[TaskDeliveryUpdate] = field(default_factory=deque)
    progress_available_at: float | None = None
    terminal_record: SessionRecordView | None = None
    terminal_pending: bool = False
    delivered_terminal_event: SessionEventView | None = None
    delivered_terminal_record: SessionRecordView | None = None
    session_released: bool = False
    active_drain: _DrainClaim | None = None
    transition: bool = False
    closing: bool = False
    recovery_caller: int | None = None
    response_capture_caller: int | None = None
    start_command_id: str | None = None
    task_kind: str | None = None
    request_id: str | None = None
    setup: TaskSetupSnapshotView | None = None

    def sink(self, generation: int) -> Callable[[TaskDeliveryUpdate], None]:
        def accept(update: TaskDeliveryUpdate) -> None:
            self._offer(generation, update)

        return accept

    def require_no_response_capture_reentry(self) -> None:
        if self.response_capture_caller == get_ident():
            raise ObservationConflictError(
                "task operation reentered response capture"
            )

    def _offer(self, generation: int, update: TaskDeliveryUpdate) -> None:
        if type(update) not in {SessionEventView, SessionRecordView}:
            raise TypeError("task updates must be exact service view types")
        update_session = update.session_id
        with self.condition:
            if self.closing or generation != self.generation:
                return
            self.require_no_response_capture_reentry()
            expected_session_id = self.session_id
            if (
                expected_session_id is not None
                and update_session != expected_session_id
            ):
                raise ObservationConflictError(
                    "task observation delivered a mismatched session"
                )
            _validate_task_observation(
                update,
                expected_session_id=expected_session_id,
            )
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
class _StartResponse:
    command_id: str
    wire_intent: tuple[object, ...] | None
    participants: int = 0
    complete: bool = False
    delivery_retiring: bool = False
    result: TaskStartView | None = None
    failure_code: str | None = None


@dataclass(frozen=True, slots=True)
class _TaskDrainResponseCodec:
    """Narrow bridge-response capability supplied by the web composition root."""

    response_too_large_error: type[Exception]
    admit: Callable[
        [str, str, str, Iterable[TaskUpdateView]],
        object,
    ]
    peek: Callable[[object], TaskDrainView]
    consume: Callable[[object], TaskDrainView]

    def __post_init__(self) -> None:
        error_type = self.response_too_large_error
        if (
            not isinstance(error_type, type)
            or not issubclass(error_type, Exception)
        ):
            raise TypeError("task drain response error must be an exception type")
        if not all(
            callable(value)
            for value in (self.admit, self.peek, self.consume)
        ):
            raise TypeError("task drain response codec members must be callable")


class TaskRegistry:
    """Own adapter delivery generations, response replay, and bounded drains."""

    def __init__(
        self,
        lifecycle: TaskLifecyclePort,
        *,
        response_codec: _TaskDrainResponseCodec | None = None,
        clock: Callable[[], float] = monotonic,
        drain_wait: float = _DRAIN_WAIT_SECONDS,
        progress_linger: float = _PROGRESS_LINGER_SECONDS,
    ) -> None:
        if not callable(clock):
            raise TypeError("task clock must be callable")
        if response_codec is not None:
            if type(response_codec) is not _TaskDrainResponseCodec:
                raise TypeError("task drain response codec must be exact")
            response_codec.__post_init__()
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
        self._lifecycle = lifecycle
        self._response_codec = response_codec
        self._clock = clock
        self._drain_wait = drain_wait
        self._progress_linger = normalized_progress_linger
        self._condition = Condition(Lock())
        self._tasks: dict[str, _TaskState] = {}
        self._provisional: dict[str, _TaskState] = {}
        self._start_responses: OrderedDict[str, _StartResponse] = OrderedDict()
        self._close_receipts: OrderedDict[
            tuple[str, str | None], TaskCloseView | TaskShellView
        ] = OrderedDict()
        self._closing = False

    def bind_response_codec(
        self,
        response_codec: _TaskDrainResponseCodec,
    ) -> None:
        """Install the one adapter response policy before bridge dispatch."""

        if type(response_codec) is not _TaskDrainResponseCodec:
            raise TypeError("task drain response codec must be exact")
        response_codec.__post_init__()
        with self._condition:
            current = self._response_codec
            if current is None:
                self._response_codec = response_codec
                return
            if not (
                current.response_too_large_error
                is response_codec.response_too_large_error
                and current.admit is response_codec.admit
                and current.peek is response_codec.peek
                and current.consume is response_codec.consume
            ):
                raise RuntimeError("task drain response codec is already bound")

    def _require_response_codec(self) -> _TaskDrainResponseCodec:
        with self._condition:
            response_codec = self._response_codec
        if response_codec is None:
            raise RuntimeError("task drain response codec is not bound")
        return response_codec

    def create_task_shell(self, command_id: str) -> TaskShellView:
        """Publish one lifecycle-owned task without a session or domain result."""

        _require_opaque_id(command_id, "task command id")
        registered: _TaskState | None = None

        def delivery_factory(task_id: str) -> None:
            nonlocal registered
            if type(task_id) is not str or _TASK_ID.fullmatch(task_id) is None:
                raise RuntimeError("application task id is invalid")
            with self._condition:
                if self._closing:
                    raise TaskUnavailableError("task registry is closing")
                while task_id in self._provisional and not self._closing:
                    self._condition.wait()
                if self._closing:
                    raise TaskUnavailableError("task registry is closing")
                existing = self._tasks.get(task_id)
                if existing is not None:
                    if existing.command_id != command_id or existing.session_id is not None:
                        raise RuntimeError("application reused an adapter task id")
                    return
                task = _TaskState(task_id, command_id, self._clock)
                self._provisional[task_id] = task
                registered = task
                self._condition.notify_all()

        try:
            result = self._lifecycle.create_task_shell(command_id, delivery_factory)
            if type(result) is not TaskShellView:
                raise RuntimeError("task lifecycle returned invalid shell data")
            result.__post_init__()
            with self._condition:
                if registered is not None:
                    if self._provisional.get(result.task_id) is not registered:
                        raise RuntimeError("task shell publication is unavailable")
                    self._provisional.pop(result.task_id, None)
                    self._tasks[result.task_id] = registered
                    self._condition.notify_all()
                task = self._tasks.get(result.task_id)
                if (
                    task is None
                    or task.command_id != command_id
                    or task.session_id is not None
                ):
                    raise RuntimeError("task shell publication is unavailable")
            return result
        except BaseException:
            if registered is not None:
                with self._condition:
                    if self._provisional.get(registered.task_id) is registered:
                        self._provisional.pop(registered.task_id, None)
                    self._condition.notify_all()
            raise

    def list_tasks(self) -> TaskListView:
        with self._condition:
            if self._closing:
                raise TaskUnavailableError("task registry is closing")
            tasks = tuple(self._task_summary(task) for task in self._tasks.values())
        return TaskListView(tasks)

    @staticmethod
    def _task_summary(task: _TaskState) -> TaskSummaryView:
        with task.condition:
            if task.session_id is None:
                session_state = None
            elif task.delivered_terminal_record is not None:
                session_state = task.delivered_terminal_record.state
            else:
                session_state = "active"
            return TaskSummaryView(
                task.task_id,
                task.session_id,
                session_state,
                task.session_released,
                task.task_kind,
                task.request_id,
            )

    def start_plan(
        self,
        source: str,
        target: str,
        *,
        deletion_policy: str | None,
        command_id: str,
        wire_intent: tuple[str, str, str | None] | None = None,
    ) -> TaskStartView:
        """Bind application-owned admission to adapter-local delivery state."""

        _require_opaque_id(command_id, "task command id")
        retained: _StartResponse | None
        with self._condition:
            if self._closing:
                raise TaskUnavailableError("task registry is closing")
            retained = self._start_responses.get(command_id)
            if retained is not None and retained.wire_intent == wire_intent:
                retained.participants += 1
            elif retained is not None and _wire_policy_conflicts(
                retained.wire_intent,
                wire_intent,
            ):
                raise TaskIntentConflictError("task command intent conflicts")

        if retained is not None and retained.wire_intent == wire_intent:
            try:
                return self._await_start_response(retained)
            finally:
                self._leave_start_response(retained)

        response: _StartResponse | None = None
        provisional: _TaskState | None = None

        def delivery_factory(task_id: str) -> Callable[[TaskDeliveryUpdate], None]:
            nonlocal provisional, response
            if type(task_id) is not str or _TASK_ID.fullmatch(task_id) is None:
                raise RuntimeError("application task id is invalid")
            with self._condition:
                if self._closing:
                    raise TaskUnavailableError("task registry is closing")
                if task_id in self._tasks or task_id in self._provisional:
                    raise RuntimeError("application reused an adapter task id")
                if command_id in self._start_responses:
                    raise RuntimeError("application repeated a task delivery factory")
                while (
                    len(self._start_responses) >= _START_RESPONSE_CAPACITY
                    and not self._closing
                ):
                    if not any(
                        entry.delivery_retiring
                        for entry in self._start_responses.values()
                    ):
                        raise RuntimeError(
                            "application exceeded adapter response capacity"
                        )
                    self._condition.wait()
                if self._closing:
                    raise TaskUnavailableError("task registry is closing")
                response = _StartResponse(
                    command_id,
                    wire_intent,
                    participants=1,
                )
                provisional = _TaskState(task_id, command_id, self._clock)
                self._start_responses[command_id] = response
                self._provisional[task_id] = provisional
                self._condition.notify_all()
                return provisional.sink(provisional.generation)

        failure_code: str | None = None
        result: TaskStartView | None = None
        candidate: object | None = None
        try:
            candidate = self._lifecycle.start_task_plan(
                source,
                target,
                deletion_policy=deletion_policy,
                command_id=command_id,
                delivery_factory=delivery_factory,
            )
            result = self._validate_and_publish_start(
                command_id,
                candidate,
                provisional,
            )
        except BaseException as error:
            if response is None:
                raise
            failure_code = _classify_start_failure(error)
            _retire_exception_graph(error)
            candidate = None
            if provisional is not None:
                self._discard_provisional(provisional)

        if response is None:
            assert result is not None
            return result

        with self._condition:
            response.result = result
            response.failure_code = failure_code
            response.complete = True
            self._condition.notify_all()
        try:
            if result is not None:
                return result
            assert failure_code is not None
            _raise_start_failure(failure_code)
        finally:
            self._leave_start_response(response)

    def replay_start(
        self,
        command_id: str,
        wire_intent: tuple[object, ...],
    ) -> TaskStartView | None:
        """Return an exact retained wire replay before volatile slots resolve."""

        _require_opaque_id(command_id, "task command id")
        with self._condition:
            if self._closing:
                raise TaskUnavailableError("task registry is closing")
            entry = self._start_responses.get(command_id)
            if entry is None:
                return None
            if entry.wire_intent != wire_intent:
                if _wire_policy_conflicts(entry.wire_intent, wire_intent):
                    raise TaskIntentConflictError("task command intent conflicts")
                return None
            entry.participants += 1
            self._start_responses.move_to_end(command_id)
        try:
            return self._await_start_response(entry)
        finally:
            self._leave_start_response(entry)

    def read_setup_options(self) -> SetupOptionsView:
        return self._lifecycle.read_setup_options()

    def prepare_setup_options(self, value: SetupOptionsView) -> SetupOptionsView:
        return self._lifecycle.prepare_setup_options(value)

    def remembered_locations(self) -> RememberedLocations:
        return self._lifecycle.remembered_locations()

    def admit_location_candidate(self, candidate: LocationCandidate):
        return self._lifecycle.admit_location_candidate(candidate)

    def read_task_setup(self, task_id: str) -> TaskSetupSnapshotView:
        if type(task_id) is not str or _TASK_ID.fullmatch(task_id) is None:
            raise TaskUnavailableError("task is unavailable")
        with self._condition:
            if self._closing:
                raise TaskUnavailableError("task registry is closing")
            task = self._tasks.get(task_id)
        if task is None:
            raise TaskUnavailableError("task is unavailable")
        with task.condition:
            snapshot = task.setup
            request_id = task.request_id
            kind = task.task_kind
        if snapshot is None:
            return TaskSetupSnapshotView(
                "default",
                None,
                None,
                None,
                None,
                self._lifecycle.read_setup_options(),
            )
        if kind == "sync-plan" and request_id is not None:
            try:
                return self._lifecycle.read_plan_setup(request_id)
            except KeyError:
                pass
        return snapshot

    def start_setup_plan(
        self,
        task_id: str,
        source: LocationCandidate,
        target: LocationCandidate,
        options: SetupOptionsView,
        *,
        command_id: str,
        wire_intent: tuple[object, ...],
    ) -> TaskStartView:
        return self._start_existing_task(
            task_id,
            command_id,
            wire_intent,
            lambda factory: self._lifecycle.start_task_setup_plan(
                task_id,
                source,
                target,
                options,
                command_id=command_id,
                signature=wire_intent,
                delivery_factory=factory,
            ),
        )

    def start_setup_inventory(
        self,
        task_id: str,
        root: LocationCandidate,
        *,
        command_id: str,
        wire_intent: tuple[object, ...],
    ) -> TaskStartView:
        return self._start_existing_task(
            task_id,
            command_id,
            wire_intent,
            lambda factory: self._lifecycle.start_task_setup_inventory(
                task_id,
                root,
                command_id=command_id,
                signature=wire_intent,
                delivery_factory=factory,
            ),
        )

    def start_plan_again(
        self,
        old_task_id: str,
        *,
        source_mount: str | None,
        target_mount: str | None,
        command_id: str,
        wire_intent: tuple[object, ...],
    ) -> TaskStartView:
        with self._condition:
            old = self._tasks.get(old_task_id)
        if old is None:
            raise TaskUnavailableError("task is unavailable")
        with old.condition:
            if old.task_kind != "sync-plan" or old.request_id is None:
                raise TaskUnavailableError("task is unavailable")
            request_id = old.request_id
        return self._start_new_task(
            command_id,
            wire_intent,
            lambda factory: self._lifecycle.start_task_plan_again(
                old_task_id,
                request_id,
                source_mount=source_mount,
                target_mount=target_mount,
                command_id=command_id,
                signature=wire_intent,
                delivery_factory=factory,
            ),
        )

    def _start_existing_task(
        self,
        task_id: str,
        command_id: str,
        wire_intent: tuple[object, ...],
        starter: Callable[[TaskDeliveryFactory], object],
    ) -> TaskStartView:
        _require_opaque_id(command_id, "task command id")
        with self._condition:
            if self._closing:
                raise TaskUnavailableError("task registry is closing")
            retained = self._start_responses.get(command_id)
            if retained is not None:
                if retained.wire_intent != wire_intent:
                    raise TaskIntentConflictError("task command intent conflicts")
                retained.participants += 1
        if retained is not None:
            try:
                return self._await_start_response(retained)
            finally:
                self._leave_start_response(retained)
        response: _StartResponse | None = None
        with self._condition:
            task = self._tasks.get(task_id)
        if task is None:
            raise TaskUnavailableError("task is unavailable")

        def delivery_factory(delivered_task_id: str):
            nonlocal response
            if delivered_task_id != task_id:
                raise ObservationConflictError("task lifecycle changed its task")
            with self._condition:
                if self._closing or self._tasks.get(task_id) is not task:
                    raise TaskUnavailableError("task is unavailable")
                if command_id in self._start_responses:
                    raise RuntimeError("application repeated a task delivery factory")
                response = _StartResponse(command_id, wire_intent, participants=1)
                self._start_responses[command_id] = response
                self._condition.notify_all()
            with task.condition:
                if task.session_id is not None or task.closing:
                    raise TaskUnavailableError("task is unavailable")
                task.transition = True
                task.start_command_id = command_id
                return task.sink(task.generation)

        candidate: object | None = None
        result: TaskStartView | None = None
        failure_code: str | None = None
        try:
            candidate = starter(delivery_factory)
            result = self._publish_setup_start(command_id, candidate, task)
        except BaseException as error:
            if response is None:
                raise
            failure_code = _classify_start_failure(error)
            _retire_exception_graph(error)
            with task.condition:
                task.transition = False
                task.start_command_id = None
                task.condition.notify_all()
        if response is None:
            if type(candidate) is TaskStartView:
                return self._validate_and_publish_start(
                    command_id,
                    candidate,
                    None,
                )
            assert result is not None
            return result
        with self._condition:
            response.result = result
            response.failure_code = failure_code
            response.complete = True
            self._condition.notify_all()
        try:
            if result is not None:
                return result
            assert failure_code is not None
            _raise_start_failure(failure_code)
        finally:
            self._leave_start_response(response)

    def _start_new_task(
        self,
        command_id: str,
        wire_intent: tuple[object, ...],
        starter: Callable[[TaskDeliveryFactory], object],
    ) -> TaskStartView:
        retained = self.replay_start(command_id, wire_intent)
        if retained is not None:
            return retained
        response: _StartResponse | None = None
        provisional: _TaskState | None = None

        def delivery_factory(task_id: str):
            nonlocal response, provisional
            with self._condition:
                if self._closing:
                    raise TaskUnavailableError("task registry is closing")
                response = _StartResponse(command_id, wire_intent, participants=1)
                provisional = _TaskState(task_id, command_id, self._clock)
                provisional.start_command_id = command_id
                self._start_responses[command_id] = response
                self._provisional[task_id] = provisional
                self._condition.notify_all()
                return provisional.sink(provisional.generation)

        result: TaskStartView | None = None
        failure_code: str | None = None
        try:
            candidate = starter(delivery_factory)
            if type(candidate) is TaskStartOutcome:
                assert provisional is not None
                provisional.setup = candidate.snapshot
                provisional.task_kind = candidate.snapshot.task_kind
                provisional.request_id = candidate.start.request_id
                candidate = candidate.start
            result = self._validate_and_publish_start(
                command_id,
                candidate,
                provisional,
            )
        except BaseException as error:
            if response is None:
                raise
            failure_code = _classify_start_failure(error)
            _retire_exception_graph(error)
            if provisional is not None:
                self._discard_provisional(provisional)
        if response is None:
            assert result is not None
            return result
        with self._condition:
            response.result = result
            response.failure_code = failure_code
            response.complete = True
            self._condition.notify_all()
        try:
            if result is not None:
                return result
            assert failure_code is not None
            _raise_start_failure(failure_code)
        finally:
            self._leave_start_response(response)

    def _publish_setup_start(
        self,
        command_id: str,
        candidate: object,
        task: _TaskState,
    ) -> TaskStartView:
        if type(candidate) is not TaskStartOutcome:
            if type(candidate) is TaskStartView:
                return self._validate_and_publish_start(command_id, candidate, None)
            raise RuntimeError("task lifecycle returned invalid Setup data")
        candidate.__post_init__()
        result = candidate.start
        if result.task_id != task.task_id:
            raise ObservationConflictError("task lifecycle changed its task")
        with task.condition:
            if task.closing:
                raise TaskUnavailableError("task is unavailable")
            for update in task.queue:
                if update.session_id != result.session_id:
                    raise ObservationConflictError(
                        "task observation does not match admitted session"
                    )
            task.session_id = result.session_id
            task.task_kind = candidate.snapshot.task_kind
            task.request_id = result.request_id
            task.setup = candidate.snapshot
            task.transition = False
            task.condition.notify_all()
        return result

    def _await_start_response(self, entry: _StartResponse) -> TaskStartView:
        with self._condition:
            while not entry.complete:
                self._condition.wait()
            if entry.result is not None:
                return entry.result
            assert entry.failure_code is not None
            _raise_start_failure(entry.failure_code)

    def _leave_start_response(self, entry: _StartResponse) -> None:
        with self._condition:
            entry.participants -= 1
            if (
                entry.complete
                and entry.participants == 0
                and (entry.result is None or self._closing)
            ):
                if self._start_responses.get(entry.command_id) is entry:
                    self._start_responses.pop(entry.command_id, None)
            self._condition.notify_all()

    def _validate_and_publish_start(
        self,
        command_id: str,
        candidate: object,
        provisional: _TaskState | None,
    ) -> TaskStartView:
        if type(candidate) is not TaskStartView:
            raise RuntimeError("planning lifecycle returned invalid task data")
        candidate.__post_init__()
        if provisional is None:
            pending: _StartResponse | None = None
            with self._condition:
                task = self._tasks.get(candidate.task_id)
                if task is None:
                    pending = self._start_responses.get(command_id)
                    if pending is not None:
                        pending.participants += 1
            if pending is not None:
                try:
                    replay = self._await_start_response(pending)
                finally:
                    self._leave_start_response(pending)
                if replay != candidate:
                    raise RuntimeError("task lifecycle replay changed its result")
                with self._condition:
                    task = self._tasks.get(candidate.task_id)
            if (
                task is None
                or task.command_id != command_id
                or task.session_id != candidate.session_id
            ):
                raise RuntimeError("task lifecycle replay has no delivery state")
            return candidate

        if provisional.task_id != candidate.task_id:
            raise ObservationConflictError(
                "planning lifecycle returned a different task"
            )
        with provisional.condition:
            if provisional.closing:
                raise TaskUnavailableError("task registry closed during start")
            for update in provisional.queue:
                if update.session_id != candidate.session_id:
                    raise ObservationConflictError(
                        "task observation does not match admitted session"
                    )
            if (
                provisional.terminal_record is not None
                and provisional.terminal_record.session_id
                != candidate.session_id
            ):
                raise ObservationConflictError(
                    "task terminal record does not match admitted session"
                )
            provisional.session_id = candidate.session_id
            if provisional.task_kind is None:
                provisional.task_kind = "sync-plan"
            provisional.request_id = candidate.request_id
            provisional.condition.notify_all()
        with self._condition:
            if self._closing:
                raise TaskUnavailableError("task registry closed during start")
            if self._provisional.get(provisional.task_id) is not provisional:
                raise RuntimeError("provisional task delivery is unavailable")
            if provisional.task_id in self._tasks:
                raise RuntimeError("task delivery publication was repeated")
            self._provisional.pop(provisional.task_id, None)
            self._tasks[provisional.task_id] = provisional
            self._condition.notify_all()
        return candidate

    def _discard_provisional(self, task: _TaskState) -> None:
        with task.condition:
            task.closing = True
            task.generation += 1
            if task.active_drain is not None:
                task.active_drain.superseded = True
            task.condition.notify_all()
        with self._condition:
            if self._provisional.get(task.task_id) is task:
                self._provisional.pop(task.task_id, None)
            self._condition.notify_all()

    def drain(
        self,
        task_id: str,
        session_id: str,
        drain_id: str,
        *,
        replay_from: int | None,
    ) -> TaskDrainView:
        response_codec = self._require_response_codec()
        return response_codec.consume(
            self._drain_admitted(
                task_id,
                session_id,
                drain_id,
                replay_from=replay_from,
                response_codec=response_codec,
            )
        )

    def drain_for_bridge(
        self,
        task_id: str,
        session_id: str,
        drain_id: str,
        *,
        replay_from: int | None,
    ) -> object:
        """Transfer one byte-admitted drain to the bridge without recopying it."""

        response_codec = self._require_response_codec()
        return self._drain_admitted(
            task_id,
            session_id,
            drain_id,
            replay_from=replay_from,
            response_codec=response_codec,
        )

    def _drain_admitted(
        self,
        task_id: str,
        session_id: str,
        drain_id: str,
        *,
        replay_from: int | None,
        response_codec: _TaskDrainResponseCodec,
    ) -> object:
        _require_opaque_id(drain_id, "task drain id")
        task = self._require_task(task_id, session_id)
        deadline = self._clock() + self._drain_wait
        claim = _DrainClaim(drain_id)
        with task.condition:
            task.require_no_response_capture_reentry()
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
                queued = (
                    ()
                    if claim.superseded
                    else tuple(islice(task.queue, _CAPACITY))
                )
                terminal = (
                    task.terminal_record
                    if (
                        not claim.superseded
                        and len(queued) < _CAPACITY
                        and task.terminal_pending
                    )
                    else None
                )
                source = iter(queued)
                if terminal is not None:
                    source = chain(source, (terminal,))
                task.response_capture_caller = get_ident()
                try:
                    admitted = response_codec.admit(
                        task_id,
                        session_id,
                        drain_id,
                        (_tag_update(update) for update in source),
                    )
                except response_codec.response_too_large_error as error:
                    _retire_exception_graph(error)
                    raise RuntimeError(
                        "one task update exceeds the bridge response ceiling"
                    ) from None
                finally:
                    if task.response_capture_caller == get_ident():
                        task.response_capture_caller = None
                result = response_codec.peek(admitted)
                count = min(len(result.updates), len(queued))
                include_terminal = (
                    not claim.superseded
                    and terminal is not None
                    and len(result.updates) > count
                )
                if not claim.superseded:
                    for _ in range(count):
                        task.queue.popleft()
                    if include_terminal:
                        task.terminal_pending = False
                    if not any(
                        _is_progress_update(update) for update in task.queue
                    ):
                        task.progress_available_at = None
                    for update in result.updates:
                        if (
                            type(update) is TaskEventUpdateView
                            and update.event.body_type == "Terminal"
                        ):
                            task.delivered_terminal_event = update.event
                        elif type(update) is TaskRecordUpdateView:
                            task.delivered_terminal_record = update.record
                    task.condition.notify_all()
        finally:
            with task.condition:
                if task.active_drain is claim:
                    task.active_drain = None
                task.condition.notify_all()

        return admitted

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
            current = self._lifecycle.reobserve_task(
                task.task_id,
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
            _retire_exception_graph(error)
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
            with task.condition:
                if task.generation == generation or task.closing:
                    task.transition = False
                task.condition.notify_all()
            if failure_code is None:
                failure_code = _RECOVERY_FAILURE_TASK_UNAVAILABLE
        if failure_code is not None:
            terminal = None
            _raise_recovery_failure(failure_code)

    def begin_close(self) -> None:
        """Reject tasks and withdraw adapter-local delivery state."""

        with self._condition:
            self._closing = True
            tasks = tuple(self._tasks.values()) + tuple(self._provisional.values())
            for command_id, response in tuple(self._start_responses.items()):
                if (
                    response.complete
                    and response.participants == 0
                    and not response.delivery_retiring
                ):
                    self._start_responses.pop(command_id, None)
            self._condition.notify_all()
        for task in tasks:
            with task.condition:
                task.closing = True
                task.generation += 1
                if task.active_drain is not None:
                    task.active_drain.superseded = True
                task.condition.notify_all()

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
        if task is None:
            raise TaskUnavailableError("task is unavailable")

        with task.condition:
            task.require_no_response_capture_reentry()
            if task.session_id != session_id:
                raise TaskUnavailableError("task is unavailable")
            delivery = self._terminal_delivery_locked(task)
            task.closing = True
            task.generation += 1
            if task.active_drain is not None:
                task.active_drain.superseded = True
            task.condition.notify_all()
            while task.transition:
                task.condition.wait()

        while True:
            try:
                result = self._lifecycle.release_task_session(
                    task_id,
                    session_id,
                    delivery,
                )
            except TaskUnavailableError as error:
                _retire_exception_graph(error)
                waited_for_close = False
                with self._condition:
                    while True:
                        close_receipt = self._close_receipts.get(receipt_key)
                        if close_receipt is not None:
                            self._close_receipts.move_to_end(receipt_key)
                            return TaskSessionReleaseView(task_id, session_id)
                        response = self._start_responses.get(
                            task.start_command_id or task.command_id
                        )
                        if (
                            self._closing
                            or response is None
                            or not response.delivery_retiring
                        ):
                            break
                        waited_for_close = True
                        self._condition.wait()
                if waited_for_close and not self._closing:
                    continue
                raise
            except BaseException as error:
                _retire_exception_graph(error)
                raise
            break
        if (
            type(result) is not TaskSessionReleaseView
            or result.task_id != task_id
            or result.session_id != session_id
        ):
            raise RuntimeError("task lifecycle returned invalid release data")
        result.__post_init__()
        with task.condition:
            task.session_released = True
            task.condition.notify_all()
        return result

    def request_task_close(
        self,
        task_id: str,
        session_id: str | None,
    ) -> TaskCloseRequestView:
        """Cancel a busy session or close one exact task when it is ready."""

        if session_id is None:
            return self._close_task_shell(task_id)
        self._require_task_identity(task_id, session_id)
        receipt_key = (task_id, session_id)
        with self._condition:
            receipt = self._close_receipts.get(receipt_key)
            if receipt is not None:
                if type(receipt) is not TaskCloseView:
                    raise RuntimeError("task close receipt has invalid ownership")
                self._close_receipts.move_to_end(receipt_key)
                return TaskCloseRequestView(task_id, session_id, "closed")
            task = self._tasks.get(task_id)
        if task is None:
            raise TaskUnavailableError("task is unavailable")
        with task.condition:
            task.require_no_response_capture_reentry()
            if task.session_id != session_id:
                raise TaskUnavailableError("task is unavailable")
            terminal_delivered = task.delivered_terminal_record is not None
        if not terminal_delivered:
            try:
                self._lifecycle.cancel_task_session(task_id, session_id)
            except TaskUnavailableError:
                with task.condition:
                    terminal_delivered = task.delivered_terminal_record is not None
                if not terminal_delivered:
                    raise
            else:
                return TaskCloseRequestView(task_id, session_id, "pending")
        result = self.close_task(task_id, session_id)
        return TaskCloseRequestView(result.task_id, result.session_id, "closed")

    def _close_task_shell(self, task_id: str) -> TaskCloseRequestView:
        if type(task_id) is not str or _TASK_ID.fullmatch(task_id) is None:
            raise TaskUnavailableError("task is unavailable")
        receipt_key = (task_id, None)
        with self._condition:
            receipt = self._close_receipts.get(receipt_key)
            if receipt is not None:
                if type(receipt) is not TaskShellView:
                    raise RuntimeError("task shell close receipt has invalid ownership")
                self._close_receipts.move_to_end(receipt_key)
                return TaskCloseRequestView(task_id, None, "closed")
            task = self._tasks.get(task_id)
        if task is None:
            raise TaskUnavailableError("task is unavailable")
        with task.condition:
            if task.session_id is not None:
                raise TaskUnavailableError("task is unavailable")
            task.closing = True
            task.generation += 1
            task.condition.notify_all()
        try:
            result = self._lifecycle.close_task_shell(task_id)
            if type(result) is not TaskShellView or result.task_id != task_id:
                raise RuntimeError("task lifecycle returned invalid shell close data")
            result.__post_init__()
        except BaseException:
            with task.condition:
                task.closing = False
                task.condition.notify_all()
            raise
        with self._condition:
            if self._tasks.get(task_id) is task:
                self._tasks.pop(task_id, None)
            self._close_receipts[receipt_key] = result
            self._close_receipts.move_to_end(receipt_key)
            while len(self._close_receipts) > _CLOSE_RECEIPT_CAPACITY:
                self._close_receipts.popitem(last=False)
            self._condition.notify_all()
        return TaskCloseRequestView(task_id, None, "closed")

    def close_task(self, task_id: str, session_id: str) -> TaskCloseView:
        """Explicitly release one terminal task and its retained plan."""

        self._require_task_identity(task_id, session_id)
        receipt_key = (task_id, session_id)
        with self._condition:
            receipt = self._close_receipts.get(receipt_key)
            if receipt is not None:
                if type(receipt) is not TaskCloseView:
                    raise RuntimeError("task close receipt has invalid ownership")
                self._close_receipts.move_to_end(receipt_key)
                return receipt
            task = self._tasks.get(task_id)
        if task is None:
            raise TaskUnavailableError("task is unavailable")
        with task.condition:
            task.require_no_response_capture_reentry()
            if task.session_id != session_id:
                raise TaskUnavailableError("task is unavailable")
            delivery = self._terminal_delivery_locked(task)
            task.closing = True
            task.generation += 1
            if task.active_drain is not None:
                task.active_drain.superseded = True
            task.condition.notify_all()
            while task.transition:
                task.condition.wait()

        response: _StartResponse | None = None
        with self._condition:
            while True:
                receipt = self._close_receipts.get(receipt_key)
                if receipt is not None:
                    if type(receipt) is not TaskCloseView:
                        raise RuntimeError("task close receipt has invalid ownership")
                    self._close_receipts.move_to_end(receipt_key)
                    return receipt
                if self._closing:
                    raise TaskUnavailableError("task registry is closing")
                response_key = task.start_command_id or task.command_id
                response = self._start_responses.get(response_key)
                if response is None:
                    raise RuntimeError("task start response is unavailable")
                if not response.delivery_retiring:
                    response.delivery_retiring = True
                    self._condition.notify_all()
                    break
                self._condition.wait()

        try:
            result = self._lifecycle.close_task(
                task_id,
                session_id,
                delivery,
            )
            if (
                type(result) is not TaskCloseView
                or result.task_id != task_id
                or result.session_id != session_id
            ):
                raise RuntimeError("task lifecycle returned invalid close data")
            result.__post_init__()
        except BaseException as error:
            _retire_exception_graph(error)
            with self._condition:
                response.delivery_retiring = False
                if (
                    self._closing
                    and self._start_responses.get(response_key) is response
                ):
                    self._start_responses.pop(response_key, None)
                self._condition.notify_all()
            raise
        with self._condition:
            self._close_receipts[receipt_key] = result
            self._close_receipts.move_to_end(receipt_key)
            while len(self._close_receipts) > _CLOSE_RECEIPT_CAPACITY:
                self._close_receipts.popitem(last=False)
            if self._tasks.get(task_id) is task:
                self._tasks.pop(task_id, None)
            response.delivery_retiring = False
            if self._start_responses.get(response_key) is response:
                self._start_responses.pop(response_key, None)
            self._condition.notify_all()
        return result

    @staticmethod
    def _terminal_delivery_locked(task: _TaskState) -> TaskTerminalDelivery:
        record = task.delivered_terminal_record
        if record is None:
            raise TaskUnavailableError("task terminal record was not drained")
        return TaskTerminalDelivery(
            record,
            task.delivered_terminal_event,
        )

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
        if task.closing or task.session_id != session_id:
            raise TaskUnavailableError("task is unavailable")

    @staticmethod
    def _require_task_identity(task_id: str, session_id: str) -> None:
        if type(task_id) is not str or _TASK_ID.fullmatch(task_id) is None:
            raise TaskUnavailableError("task is unavailable")
        if type(session_id) is not str or _OPAQUE_ID.fullmatch(session_id) is None:
            raise TaskUnavailableError("task is unavailable")


def _tag_update(update: TaskDeliveryUpdate) -> TaskUpdateView:
    if type(update) is SessionEventView:
        return TaskEventUpdateView("event", update)
    if type(update) is SessionRecordView:
        return TaskRecordUpdateView("record", update)
    raise TypeError("task updates must be exact service view types")


def _wire_policy_conflicts(
    first: tuple[object, ...] | None,
    second: tuple[object, ...] | None,
) -> bool:
    if first is None or second is None:
        return False
    if len(first) == len(second) == 3:
        return first[2] != second[2]
    return first != second


def _require_opaque_id(value: object, label: str) -> None:
    if type(value) is not str or _OPAQUE_ID.fullmatch(value) is None:
        raise RuntimeError(f"{label} is invalid")


__all__ = [
    "DrainBusyError",
    "ObservationConflictError",
    "TaskRegistry",
]
