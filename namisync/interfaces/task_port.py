"""Task lifecycle contract and exact adapter-facing task views."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from namisync.workflows.views import (
    SessionEventView,
    SessionRecordView,
    validate_session_record_view,
)


_TASK_DRAIN_CAPACITY = 64
_OPAQUE_ID = re.compile(r"[0-9a-f]{32}")
_TASK_ID = re.compile(r"task-[0-9a-f]{32}")

TaskDeliveryUpdate = SessionEventView | SessionRecordView
TaskDeliverySink = Callable[[TaskDeliveryUpdate], None]
TaskDeliveryFactory = Callable[[str], TaskDeliverySink]


class TaskUnavailableError(LookupError):
    """A task is absent, closed, or does not own the supplied session."""


class TaskIntentConflictError(RuntimeError):
    """A task command id was reused for a different resolved intent."""


@dataclass(frozen=True, slots=True)
class TaskStartView:
    task_id: str
    request_id: str
    session_id: str

    def __post_init__(self) -> None:
        _require_task_id(self.task_id)
        _require_opaque_id(self.request_id, "task request id")
        _require_opaque_id(self.session_id, "task session id")


@dataclass(frozen=True, slots=True)
class TaskCloseView:
    task_id: str
    session_id: str

    def __post_init__(self) -> None:
        _require_task_id(self.task_id)
        _require_opaque_id(self.session_id, "task session id")


@dataclass(frozen=True, slots=True)
class TaskSessionReleaseView:
    task_id: str
    session_id: str

    def __post_init__(self) -> None:
        _require_task_id(self.task_id)
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
        _require_task_id(self.task_id)
        _require_opaque_id(self.session_id, "task session id")
        _require_opaque_id(self.drain_id, "task drain id")
        if (
            type(self.updates) is not tuple
            or len(self.updates) > _TASK_DRAIN_CAPACITY
        ):
            raise ValueError("task drain updates are invalid")


@dataclass(frozen=True, slots=True)
class TaskTerminalDelivery:
    """Exact terminal delivery fact supplied to application settlement."""

    record: SessionRecordView
    terminal_event: SessionEventView | None = None

    def __post_init__(self) -> None:
        _validate_task_observation(self.record)
        event = self.terminal_event
        if event is None:
            return
        _validate_task_observation(
            event,
            expected_session_id=self.record.session_id,
        )
        if event.body_type != "Terminal":
            raise ValueError("task terminal delivery event is not terminal")


class TaskLifecyclePort(Protocol):
    """Narrow task-bound application lifecycle surface for adapters."""

    def start_task_plan(
        self,
        source: str,
        target: str,
        *,
        deletion_policy: str | None,
        command_id: str,
        delivery_factory: TaskDeliveryFactory,
    ) -> TaskStartView: ...

    def reobserve_task(
        self,
        task_id: str,
        session_id: str,
        sink: TaskDeliverySink,
        from_sequence: int,
    ) -> SessionRecordView: ...

    def release_task_session(
        self,
        task_id: str,
        session_id: str,
        delivery: TaskTerminalDelivery,
    ) -> TaskSessionReleaseView: ...

    def close_task(
        self,
        task_id: str,
        session_id: str,
        delivery: TaskTerminalDelivery,
    ) -> TaskCloseView: ...


def _validate_task_observation(
    update: object,
    *,
    expected_session_id: str | None = None,
) -> None:
    if type(update) is SessionEventView:
        if (
            expected_session_id is not None
            and update.session_id != expected_session_id
        ):
            raise ValueError("session event belongs to another session")
        if type(update.sequence) is not int:
            raise TypeError("task event sequence must be an exact integer")
        if update.sequence < 1:
            raise ValueError("task event sequence must be positive")
    elif type(update) is SessionRecordView:
        validate_session_record_view(
            update,
            expected_session_id=expected_session_id,
        )
        if (
            update.kind != "sync-plan"
            or update.supports_pause
            or update.result is None
        ):
            raise ValueError("task record requires a terminal sync-plan result")
    else:
        raise TypeError("task updates must be exact service view types")


def validate_task_update_view(
    value: object,
    *,
    expected_session_id: str | None = None,
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
    _validate_task_observation(
        update,
        expected_session_id=expected_session_id,
    )


def validate_task_drain_view(value: object) -> None:
    if type(value) is not TaskDrainView:
        raise TypeError("task drain must be an exact view")
    # Recheck the outer contract as well as mutable nested collaborator data.
    value.__post_init__()
    for update in value.updates:
        validate_task_update_view(
            update,
            expected_session_id=value.session_id,
        )


def _require_opaque_id(value: object, label: str) -> None:
    if type(value) is not str or _OPAQUE_ID.fullmatch(value) is None:
        raise RuntimeError(f"{label} is invalid")


def _require_task_id(value: object) -> None:
    if type(value) is not str or _TASK_ID.fullmatch(value) is None:
        raise ValueError("task id is invalid")


__all__ = [
    "TaskCloseView",
    "TaskDeliveryFactory",
    "TaskDeliverySink",
    "TaskDeliveryUpdate",
    "TaskDrainView",
    "TaskEventUpdateView",
    "TaskIntentConflictError",
    "TaskLifecyclePort",
    "TaskRecordUpdateView",
    "TaskSessionReleaseView",
    "TaskStartView",
    "TaskTerminalDelivery",
    "TaskUnavailableError",
    "TaskUpdateView",
    "validate_task_drain_view",
    "validate_task_update_view",
]
