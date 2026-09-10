"""Task lifecycle contract and exact adapter-facing task views."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from namisync.workflows.inventory import LocationCandidate
from namisync.workflows.views import (
    SessionEventView,
    SessionRecordView,
    SetupOptionsView,
    validate_session_record_view,
)


_TASK_DRAIN_CAPACITY = 64
_OPAQUE_ID = re.compile(r"[0-9a-f]{32}")
_TASK_ID = re.compile(r"task-[0-9a-f]{32}")

TaskDeliveryUpdate = SessionEventView | SessionRecordView
TaskDeliverySink = Callable[[TaskDeliveryUpdate], None]
TaskDeliveryFactory = Callable[[str], TaskDeliverySink]
TaskShellDeliveryFactory = Callable[[str], None]


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
class TaskSetupLocationView:
    display: str
    location_id: str | None

    def __post_init__(self) -> None:
        if type(self.display) is not str or not self.display:
            raise TypeError("Setup location display must be text")
        self.display.encode("utf-8")
        if self.location_id is not None and (
            type(self.location_id) is not str
            or not self.location_id.isascii()
            or not self.location_id.isdecimal()
            or str(int(self.location_id)) != self.location_id
            or not 1 <= int(self.location_id) <= (1 << 63) - 1
        ):
            raise ValueError("Setup location id must be canonical decimal text")


@dataclass(frozen=True, slots=True)
class PlanAgainReadinessView:
    source_state: str
    source_candidates: tuple[str, ...]
    target_state: str
    target_candidates: tuple[str, ...]

    def __post_init__(self) -> None:
        states = {"resolved", "offline", "ambiguous", "missing", "unavailable", "changed"}
        if self.source_state not in states or self.target_state not in states:
            raise ValueError("Plan-again readiness state is invalid")
        for candidates in (self.source_candidates, self.target_candidates):
            if type(candidates) is not tuple or not all(
                type(item) is str and bool(item) for item in candidates
            ):
                raise TypeError("Plan-again readiness candidates are invalid")


@dataclass(frozen=True, slots=True)
class TaskSetupSnapshotView:
    setup_state: str
    task_kind: str | None
    source: TaskSetupLocationView | None
    target: TaskSetupLocationView | None
    root: TaskSetupLocationView | None
    options: SetupOptionsView | None
    plan_again: PlanAgainReadinessView | None = None

    def __post_init__(self) -> None:
        if self.setup_state not in {"default", "frozen"}:
            raise ValueError("Setup snapshot state is invalid")
        if self.task_kind not in {None, "sync-plan", "inventory"}:
            raise ValueError("Setup snapshot task kind is invalid")
        for value in (self.source, self.target, self.root):
            if value is not None and type(value) is not TaskSetupLocationView:
                raise TypeError("Setup snapshot location is invalid")
        if self.options is not None and type(self.options) is not SetupOptionsView:
            raise TypeError("Setup snapshot options are invalid")
        if self.plan_again is not None and type(self.plan_again) is not PlanAgainReadinessView:
            raise TypeError("Plan-again readiness is invalid")
        if self.plan_again is not None:
            self.plan_again.__post_init__()
        if self.setup_state == "default" and (
            self.task_kind is not None
            or any(value is not None for value in (self.source, self.target, self.root))
            or self.options is None
            or self.plan_again is not None
        ):
            raise ValueError("default Setup snapshot is inconsistent")
        if self.setup_state == "frozen" and self.task_kind == "sync-plan" and (
            self.source is None
            or self.target is None
            or self.root is not None
            or self.options is None
        ):
            raise ValueError("frozen plan Setup snapshot is inconsistent")
        if self.setup_state == "frozen" and self.task_kind == "inventory" and (
            self.root is None
            or self.source is not None
            or self.target is not None
            or self.options is not None
            or self.plan_again is not None
        ):
            raise ValueError("frozen inventory Setup snapshot is inconsistent")


@dataclass(frozen=True, slots=True)
class TaskStartOutcome:
    start: TaskStartView
    snapshot: TaskSetupSnapshotView

    def __post_init__(self) -> None:
        if type(self.start) is not TaskStartView:
            raise TypeError("task start outcome has invalid identity")
        if type(self.snapshot) is not TaskSetupSnapshotView:
            raise TypeError("task start outcome has invalid Setup snapshot")


@dataclass(frozen=True, slots=True)
class TaskShellView:
    task_id: str

    def __post_init__(self) -> None:
        _require_task_id(self.task_id)


@dataclass(frozen=True, slots=True)
class TaskSummaryView:
    task_id: str
    session_id: str | None
    session_state: str | None
    session_released: bool
    task_kind: str | None = None
    request_id: str | None = None

    def __post_init__(self) -> None:
        _require_task_id(self.task_id)
        if self.session_id is not None:
            _require_opaque_id(self.session_id, "task session id")
        if self.session_state not in {
            None,
            "active",
            "completed",
            "failed",
            "canceled",
            "refused",
        }:
            raise ValueError("task summary state is invalid")
        if type(self.session_released) is not bool:
            raise TypeError("task summary release state is invalid")
        if (self.session_state is None) != (self.session_id is None):
            raise ValueError("task summary session state is inconsistent")
        if self.session_released and self.session_state in {None, "active"}:
            raise ValueError("released task requires terminal session truth")
        if self.task_kind not in {None, "sync-plan", "inventory"}:
            raise ValueError("task summary kind is invalid")
        if self.request_id is not None:
            _require_opaque_id(self.request_id, "task request id")
        if (self.task_kind is None) != (self.request_id is None):
            raise ValueError("task summary request identity is inconsistent")


@dataclass(frozen=True, slots=True)
class TaskListView:
    tasks: tuple[TaskSummaryView, ...]

    def __post_init__(self) -> None:
        if type(self.tasks) is not tuple or len(self.tasks) > 48:
            raise ValueError("task list is invalid")
        seen: set[str] = set()
        for task in self.tasks:
            if type(task) is not TaskSummaryView:
                raise TypeError("task list item is invalid")
            task.__post_init__()
            if task.task_id in seen:
                raise ValueError("task list repeats an identity")
            seen.add(task.task_id)


@dataclass(frozen=True, slots=True)
class TaskCloseRequestView:
    task_id: str
    session_id: str | None
    disposition: str

    def __post_init__(self) -> None:
        _require_task_id(self.task_id)
        if self.session_id is not None:
            _require_opaque_id(self.session_id, "task session id")
        if self.disposition not in {"pending", "closed"}:
            raise ValueError("task close disposition is invalid")
        if self.session_id is None and self.disposition != "closed":
            raise ValueError("blank task close cannot remain pending")


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

    def create_task_shell(
        self,
        command_id: str,
        delivery_factory: TaskShellDeliveryFactory,
    ) -> TaskShellView: ...

    def close_task_shell(self, task_id: str) -> TaskShellView: ...

    def cancel_task_session(self, task_id: str, session_id: str) -> object: ...

    def start_task_plan(
        self,
        source: str,
        target: str,
        *,
        deletion_policy: str | None,
        command_id: str,
        delivery_factory: TaskDeliveryFactory,
    ) -> TaskStartView: ...

    def read_setup_options(self) -> SetupOptionsView: ...

    def prepare_setup_options(self, value: SetupOptionsView) -> SetupOptionsView: ...

    def start_task_setup_plan(
        self,
        task_id: str,
        source: LocationCandidate,
        target: LocationCandidate,
        options: SetupOptionsView,
        *,
        command_id: str,
        signature: tuple[object, ...],
        delivery_factory: TaskDeliveryFactory,
    ) -> TaskStartView | TaskStartOutcome: ...

    def start_task_setup_inventory(
        self,
        task_id: str,
        root: LocationCandidate,
        *,
        command_id: str,
        signature: tuple[object, ...],
        delivery_factory: TaskDeliveryFactory,
    ) -> TaskStartView | TaskStartOutcome: ...

    def start_task_plan_again(
        self,
        old_task_id: str,
        request_id: str,
        *,
        source_mount: str | None,
        target_mount: str | None,
        command_id: str,
        signature: tuple[object, ...],
        delivery_factory: TaskDeliveryFactory,
    ) -> TaskStartView | TaskStartOutcome: ...

    def read_plan_setup(self, request_id: str) -> TaskSetupSnapshotView: ...

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
            update.kind not in {"sync-plan", "inventory"}
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
    "TaskCloseRequestView",
    "TaskDeliveryFactory",
    "TaskDeliverySink",
    "TaskDeliveryUpdate",
    "TaskDrainView",
    "TaskEventUpdateView",
    "TaskIntentConflictError",
    "TaskLifecyclePort",
    "TaskListView",
    "TaskRecordUpdateView",
    "TaskSessionReleaseView",
    "TaskShellDeliveryFactory",
    "TaskShellView",
    "TaskStartView",
    "TaskSummaryView",
    "TaskTerminalDelivery",
    "TaskUnavailableError",
    "TaskUpdateView",
    "validate_task_drain_view",
    "validate_task_update_view",
]
