"""Generic session lifecycle, records, checkpoint, and runner."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable, NewType, Protocol, Sequence

from namisync.core.evidence import RecordingStatus

SessionId = NewType("SessionId", str)


class SessionState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    CANCELING = "canceling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUSED = "refused"
    INTERRUPTED = "interrupted"


TERMINAL_STATES = frozenset(
    {
        SessionState.COMPLETED,
        SessionState.FAILED,
        SessionState.CANCELED,
        SessionState.REFUSED,
    }
)

LEGAL_TRANSITIONS: dict[SessionState, frozenset[SessionState]] = {
    SessionState.PENDING: frozenset(
        {SessionState.RUNNING, SessionState.CANCELING, SessionState.FAILED}
    ),
    SessionState.RUNNING: frozenset(
        {
            SessionState.PAUSING,
            SessionState.CANCELING,
            SessionState.COMPLETED,
            SessionState.FAILED,
            SessionState.CANCELED,
            SessionState.REFUSED,
        }
    ),
    SessionState.PAUSING: frozenset(
        {
            SessionState.PAUSED,
            SessionState.CANCELING,
            SessionState.COMPLETED,
            SessionState.FAILED,
            SessionState.CANCELED,
            SessionState.REFUSED,
        }
    ),
    SessionState.PAUSED: frozenset(
        {SessionState.PENDING, SessionState.CANCELING}
    ),
    SessionState.CANCELING: frozenset(
        {
            SessionState.COMPLETED,
            SessionState.FAILED,
            SessionState.CANCELED,
            SessionState.REFUSED,
        }
    ),
    SessionState.COMPLETED: frozenset(),
    SessionState.FAILED: frozenset(),
    SessionState.CANCELED: frozenset(),
    SessionState.REFUSED: frozenset(),
    SessionState.INTERRUPTED: frozenset(
        {SessionState.PENDING, SessionState.CANCELING}
    ),
}


class IllegalTransition(ValueError):
    """Raised when a lifecycle edge is not part of the frozen state machine."""

    def __init__(self, current: SessionState, requested: SessionState) -> None:
        super().__init__(f"cannot transition from {current.value} to {requested.value}")
        self.current = current
        self.requested = requested


def is_terminal(state: SessionState) -> bool:
    return state in TERMINAL_STATES


def require_transition(current: SessionState, requested: SessionState) -> None:
    if requested not in LEGAL_TRANSITIONS[current]:
        raise IllegalTransition(current, requested)


class Canceled(Exception):
    """Payload-free cooperative cancellation signal."""


class PauseRequested(Exception):
    """Payload-free cooperative pause signal."""


class Checkpoint(Protocol):
    def __call__(self) -> None: ...


@dataclass(frozen=True, slots=True)
class RunContext:
    emit: Callable[[object], None]
    checkpoint: Checkpoint


class Disposition(StrEnum):
    RAN = "ran"
    UNRUN = "unrun"


@dataclass(frozen=True, slots=True)
class FailureDetail:
    type_name: str
    message: str


@dataclass(frozen=True, slots=True)
class OperationResult:
    """Axis-separated terminal truth for a generic operation session."""

    status: SessionState
    recording: RecordingStatus = RecordingStatus.OK
    audit: RecordingStatus = RecordingStatus.OK
    disposition: Disposition = Disposition.RAN
    canceled: bool = False
    operations: tuple[object, ...] = ()
    bytes_done: int = 0
    bytes_total: int = 0
    error: FailureDetail | None = None

    def __post_init__(self) -> None:
        if not is_terminal(self.status):
            raise ValueError("operation result status must be terminal")
        if self.bytes_done < 0 or self.bytes_total < 0:
            raise ValueError("result byte counts cannot be negative")
        if self.bytes_done > self.bytes_total:
            raise ValueError("bytes_done cannot exceed bytes_total")
        if self.canceled != (self.status is SessionState.CANCELED):
            raise ValueError("canceled must agree with the terminal status")
        if self.status is SessionState.REFUSED and self.disposition is not Disposition.UNRUN:
            raise ValueError("refused sessions must have unrun disposition")


@dataclass(frozen=True, order=True, slots=True)
class ResourceId:
    """Stable generic resource key used for admission and custody."""

    namespace: str
    key: str

    def __post_init__(self) -> None:
        if not self.namespace or not self.key:
            raise ValueError("resource namespace and key must be non-empty")


def _require_utc(value: datetime | None, field_name: str) -> None:
    if value is None:
        return
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError(f"{field_name} must be UTC")


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: SessionId
    kind: str
    state: SessionState
    resources: tuple[ResourceId, ...]
    payload: bytes
    supports_pause: bool
    admission_order: int
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    result: OperationResult | None = None

    def __post_init__(self) -> None:
        if not self.session_id or not self.kind:
            raise ValueError("session id and kind must be non-empty")
        if tuple(sorted(set(self.resources))) != self.resources:
            raise ValueError("resources must be unique and deterministically sorted")
        if not isinstance(self.payload, bytes):
            raise TypeError("workflow payload must be opaque bytes")
        if self.admission_order < 0:
            raise ValueError("admission order cannot be negative")
        _require_utc(self.created_at, "created_at")
        _require_utc(self.started_at, "started_at")
        _require_utc(self.ended_at, "ended_at")
        if is_terminal(self.state) != (self.ended_at is not None):
            raise ValueError("terminal state and ended_at must agree")
        if self.result is not None and self.result.status is not self.state:
            raise ValueError("record result status must agree with session state")


class SessionStore(Protocol):
    def put(self, record: SessionRecord) -> None: ...

    def load_all(self) -> Sequence[SessionRecord]: ...

    def drop(self, session_id: SessionId) -> None: ...


Settle = Callable[[SessionState, OperationResult | None], None]
FinalizeAudit = Callable[[OperationResult], RecordingStatus]


@dataclass(frozen=True, slots=True)
class RunOutcome:
    paused: bool
    result: OperationResult | None


def run_session(
    work: Callable[[RunContext], OperationResult],
    *,
    emit: Callable[[object], None],
    checkpoint: Checkpoint,
    settle: Settle,
    finalize_audit: FinalizeAudit,
    publish_result: Callable[[OperationResult], None],
    disposition: Disposition = Disposition.RAN,
    item_accumulator: list[object] | None = None,
) -> RunOutcome:
    """Run one workflow and emit its sole terminal event.

    ``settle`` is supplied by the dispatcher so it can release custody before
    publishing PAUSED or terminal state. Callback implementations must contain
    their own storage/observer failures; lifecycle callbacks cannot be allowed
    to create a second terminal path.
    """

    from namisync.core.events import ItemOutcome, Progress, Terminal

    items = item_accumulator if item_accumulator is not None else []
    latest_progress: Progress | None = None

    def observed_emit(body: object) -> None:
        nonlocal latest_progress
        if isinstance(body, Terminal):
            raise ValueError("workflow code cannot emit Terminal")
        if isinstance(body, ItemOutcome) or (
            hasattr(body, "item_id") and hasattr(body, "path")
        ):
            items.append(body)
        elif isinstance(body, Progress):
            latest_progress = body
        emit(body)

    context = RunContext(emit=observed_emit, checkpoint=checkpoint)
    try:
        result = work(context)
        if not isinstance(result, OperationResult):
            raise TypeError("workflow must return OperationResult")
    except PauseRequested:
        settle(SessionState.PAUSED, None)
        return RunOutcome(paused=True, result=None)
    except Canceled:
        bytes_done = latest_progress.bytes_done if latest_progress else 0
        bytes_total = (
            latest_progress.bytes_total
            if latest_progress and latest_progress.bytes_total is not None
            else bytes_done
        )
        result = OperationResult(
            status=SessionState.CANCELED,
            disposition=disposition,
            canceled=True,
            operations=tuple(items),
            bytes_done=bytes_done,
            bytes_total=bytes_total,
        )
    except BaseException as error:
        bytes_done = latest_progress.bytes_done if latest_progress else 0
        bytes_total = (
            latest_progress.bytes_total
            if latest_progress and latest_progress.bytes_total is not None
            else bytes_done
        )
        result = OperationResult(
            status=SessionState.FAILED,
            disposition=disposition,
            operations=tuple(items),
            bytes_done=bytes_done,
            bytes_total=bytes_total,
            error=FailureDetail(type(error).__name__, str(error)),
        )

    settle(result.status, result)
    try:
        audit = finalize_audit(result)
    except BaseException:
        audit = RecordingStatus.DEGRADED
    final_result = replace(result, audit=audit)
    publish_result(final_result)
    emit(Terminal(final_result))
    return RunOutcome(paused=False, result=final_result)
