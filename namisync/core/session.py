"""Generic session lifecycle, records, checkpoint, and runner."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable, NewType, Protocol, Sequence

from namisync.core.evidence import RecordingStatus
from namisync.core.execution import TaskRecordingIssue
from namisync.core.review import ReviewFactLimitExceeded
from namisync.core.scalars import (
    bounded_utf8_text,
    require_safe_int,
    require_signed_64,
)

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


class PhaseStatus(StrEnum):
    """Terminal truth for one entered phase of a compound workflow."""

    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class FailureDetail:
    type_name: str
    message: str


@dataclass(frozen=True, slots=True)
class PhaseResult:
    """Phase-local counters and failures that must never be summed."""

    phase: str
    status: PhaseStatus
    items_done: int
    items_total: int | None
    bytes_done: int
    bytes_total: int | None
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.phase:
            raise ValueError("phase result name must be non-empty")
        require_safe_int(self.items_done, "phase items_done")
        require_signed_64(self.bytes_done, "phase bytes_done")
        if self.items_total is not None:
            require_safe_int(self.items_total, "phase items_total")
            if self.items_total < self.items_done:
                raise ValueError("phase items_done cannot exceed items_total")
        if self.bytes_total is not None:
            require_signed_64(self.bytes_total, "phase bytes_total")
            if self.bytes_total < self.bytes_done:
                raise ValueError("phase bytes_done cannot exceed bytes_total")


class ResultItem:
    """Nominal marker for reliable, ordered session result items."""

    __slots__ = ()

    item_id: str
    item_type: str
    phase: str
    recording: RecordingStatus = RecordingStatus.OK
    detail_omitted_count: int = 0


def validate_result_cancellation(
    status: SessionState,
    disposition: Disposition,
    canceled: bool,
    execute_status: PhaseStatus | None,
    verify_status: PhaseStatus | None,
) -> None:
    """Keep filesystem and phase truth intact across terminal projections."""

    if status is SessionState.CANCELED and not canceled:
        raise ValueError("canceled filesystem status requires canceled=True")
    if canceled and status is SessionState.REFUSED:
        raise ValueError("a refused result cannot also be canceled")
    if status is SessionState.CANCELED and execute_status is PhaseStatus.COMPLETED:
        raise ValueError("execute cancellation cannot carry a completed execute phase")
    if canceled and status in {SessionState.COMPLETED, SessionState.FAILED}:
        if disposition is not Disposition.RAN:
            raise ValueError("compound cancellation must have run disposition")
        expected_execute = (
            PhaseStatus.COMPLETED
            if status is SessionState.COMPLETED
            else PhaseStatus.FAILED
        )
        if execute_status is not expected_execute:
            raise ValueError("compound cancellation must preserve matching execute truth")
        if verify_status is not PhaseStatus.CANCELED:
            raise ValueError("compound cancellation must carry a canceled verify phase")
    if status is SessionState.REFUSED and disposition is not Disposition.UNRUN:
        raise ValueError("refused sessions must have unrun disposition")


@dataclass(frozen=True, slots=True)
class OperationResult:
    """Axis-separated terminal truth for a generic operation session."""

    status: SessionState
    recording: RecordingStatus = RecordingStatus.OK
    audit: RecordingStatus = RecordingStatus.OK
    disposition: Disposition = Disposition.RAN
    canceled: bool = False
    items: tuple[ResultItem, ...] = ()
    phases: tuple[PhaseResult, ...] = ()
    bytes_done: int = 0
    bytes_total: int = 0
    error: FailureDetail | None = None
    recording_issues: tuple[TaskRecordingIssue, ...] = ()
    omitted_detail_count: int = 0
    review_fact_limit: ReviewFactLimitExceeded | None = None

    def __post_init__(self) -> None:
        if not is_terminal(self.status):
            raise ValueError("operation result status must be terminal")
        if not isinstance(self.items, tuple):
            raise TypeError("operation result items must be a tuple")
        if any(not isinstance(item, ResultItem) for item in self.items):
            raise TypeError("operation result items must implement ResultItem")
        if not isinstance(self.phases, tuple):
            raise TypeError("operation result phases must be a tuple")
        if any(not isinstance(phase, PhaseResult) for phase in self.phases):
            raise TypeError("operation result phases must contain PhaseResult values")
        phase_names = [phase.phase for phase in self.phases]
        if len(phase_names) != len(set(phase_names)):
            raise ValueError("operation result phases must be unique")
        require_signed_64(self.bytes_done, "result bytes_done")
        require_signed_64(self.bytes_total, "result bytes_total")
        if self.bytes_done > self.bytes_total:
            raise ValueError("bytes_done cannot exceed bytes_total")
        if not isinstance(self.recording_issues, tuple) or any(
            not isinstance(issue, TaskRecordingIssue)
            for issue in self.recording_issues
        ):
            raise TypeError(
                "result recording_issues must contain TaskRecordingIssue values"
            )
        issue_reasons = tuple(issue.reason for issue in self.recording_issues)
        if len(issue_reasons) != len(set(issue_reasons)):
            raise ValueError("result recording issue reasons must be unique")
        if len(self.recording_issues) > 5:
            raise ValueError("result recording issues exceed their bound")
        require_safe_int(
            self.omitted_detail_count,
            "result omitted_detail_count",
        )
        if self.review_fact_limit is not None and not isinstance(
            self.review_fact_limit,
            ReviewFactLimitExceeded,
        ):
            raise TypeError(
                "result review_fact_limit must be ReviewFactLimitExceeded or None"
            )
        validate_result_cancellation(
            self.status,
            self.disposition,
            self.canceled,
            next((phase.status for phase in self.phases if phase.phase == "execute"), None),
            next((phase.status for phase in self.phases if phase.phase == "verify"), None),
        )
        if self.review_fact_limit is not None and not (
            self.status is SessionState.REFUSED
            and self.disposition is Disposition.UNRUN
            and not self.canceled
            and not self.items
            and not self.phases
            and self.bytes_done == 0
            and self.bytes_total == 0
            and self.error is None
            and not self.recording_issues
            and self.omitted_detail_count == 0
            and self.recording is RecordingStatus.OK
        ):
            raise ValueError("review fact limit contradicts result truth")


def _bounded_failure_detail(error: FailureDetail | None) -> FailureDetail | None:
    if error is None:
        return None
    type_name = bounded_utf8_text(error.type_name, "terminal error type")
    message = bounded_utf8_text(error.message, "terminal error message")
    return error if type_name and message is not None else None


def normalize_result_diagnostics(result: OperationResult) -> OperationResult:
    """Bound full-result header diagnostics without changing domain truth."""

    omitted = result.omitted_detail_count
    phases: list[PhaseResult] = []
    for phase in result.phases:
        bounded = bounded_utf8_text(phase.error, "terminal phase error")
        if phase.error is not None and bounded is None:
            omitted = require_safe_int(omitted + 1, "terminal omitted_detail_count")
            phases.append(replace(phase, error=None))
        else:
            phases.append(phase)
    error = _bounded_failure_detail(result.error)
    if result.error is not None and error is None:
        omitted = require_safe_int(omitted + 1, "terminal omitted_detail_count")
    if omitted == result.omitted_detail_count:
        return result
    return replace(
        result,
        phases=tuple(phases),
        error=error,
        omitted_detail_count=omitted,
    )


def result_terminal_state(result: OperationResult) -> SessionState:
    """Project axis-separated result truth onto dispatcher lifecycle state."""

    return SessionState.CANCELED if result.canceled else result.status


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
    payload: bytes | None
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
        if is_terminal(self.state):
            if self.payload is not None:
                raise ValueError("terminal session payload must be cleared")
        elif not isinstance(self.payload, bytes):
            raise TypeError("nonterminal workflow payload must be opaque bytes")
        if self.admission_order < 0:
            raise ValueError("admission order cannot be negative")
        _require_utc(self.created_at, "created_at")
        _require_utc(self.started_at, "started_at")
        _require_utc(self.ended_at, "ended_at")
        if is_terminal(self.state) != (self.ended_at is not None):
            raise ValueError("terminal state and ended_at must agree")
        if (
            self.result is not None
            and result_terminal_state(self.result) is not self.state
        ):
            raise ValueError(
                "record result terminal projection must agree with session state"
            )


@dataclass(frozen=True, slots=True)
class StoredSessionRecord:
    """Session metadata/result without a continuation or live-record reference."""

    session_id: SessionId
    kind: str
    state: SessionState
    resources: tuple[ResourceId, ...]
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
        if self.admission_order < 0:
            raise ValueError("admission order cannot be negative")
        _require_utc(self.created_at, "created_at")
        _require_utc(self.started_at, "started_at")
        _require_utc(self.ended_at, "ended_at")
        if is_terminal(self.state) != (self.ended_at is not None):
            raise ValueError("terminal state and ended_at must agree")
        if (
            self.result is not None
            and result_terminal_state(self.result) is not self.state
        ):
            raise ValueError(
                "record result terminal projection must agree with session state"
            )


class SessionStore(Protocol):
    """Metadata storage accepting exact StoredSessionRecord values only."""

    def put(self, record: StoredSessionRecord) -> None: ...

    def load_all(self) -> Sequence[StoredSessionRecord]: ...

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
    item_accumulator: list[ResultItem] | None = None,
) -> RunOutcome:
    """Run one workflow and emit its sole terminal event.

    ``settle`` is supplied by the dispatcher so it can release custody before
    publishing PAUSED or terminal state. Callback implementations must contain
    their own storage/observer failures; lifecycle callbacks cannot be allowed
    to create a second terminal path.
    """

    from namisync.core.events import Progress, Terminal, TerminalSummary

    if item_accumulator is not None and any(
        not isinstance(item, ResultItem) for item in item_accumulator
    ):
        raise TypeError("item accumulator must contain only ResultItem values")
    items = item_accumulator if item_accumulator is not None else []
    latest_progress: Progress | None = None

    def observed_emit(body: object) -> None:
        nonlocal latest_progress
        if isinstance(body, Terminal):
            raise ValueError("workflow code cannot emit Terminal")
        emit(body)
        if isinstance(body, ResultItem):
            items.append(body)
        elif isinstance(body, Progress):
            latest_progress = body

    context = RunContext(emit=observed_emit, checkpoint=checkpoint)
    try:
        result = work(context)
        if not isinstance(result, OperationResult):
            raise TypeError("workflow must return OperationResult")
        result = replace(result, items=tuple(items))
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
            items=tuple(items),
            bytes_done=bytes_done,
            bytes_total=bytes_total,
        )
    except Exception as error:
        bytes_done = latest_progress.bytes_done if latest_progress else 0
        bytes_total = (
            latest_progress.bytes_total
            if latest_progress and latest_progress.bytes_total is not None
            else bytes_done
        )
        try:
            detail = _bounded_failure_detail(
                FailureDetail(type(error).__name__, str(error))
            )
        except Exception:
            detail = None
        result = OperationResult(
            status=SessionState.FAILED,
            disposition=disposition,
            items=tuple(items),
            bytes_done=bytes_done,
            bytes_total=bytes_total,
            error=detail,
            omitted_detail_count=1 if detail is None else 0,
        )

    recording = (
        RecordingStatus.DEGRADED
        if result.recording_issues
        or any(item.recording is RecordingStatus.DEGRADED for item in items)
        else RecordingStatus.OK
    )
    result = normalize_result_diagnostics(replace(result, recording=recording))

    settle(result_terminal_state(result), result)
    try:
        audit = finalize_audit(result)
    except Exception:
        audit = RecordingStatus.DEGRADED
    final_result = replace(result, audit=audit)
    publish_result(final_result)
    emit(Terminal(TerminalSummary.from_result(final_result)))
    return RunOutcome(paused=False, result=final_result)
