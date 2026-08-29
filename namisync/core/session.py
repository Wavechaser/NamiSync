"""Generic session lifecycle, records, checkpoint, and runner."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable, NewType, Protocol, Sequence

from namisync.core.exception_graph import retire_exception_graph
from namisync.core.evidence import RecordingStatus
from namisync.core.execution import TaskRecordingIssue
from namisync.core.review import (
    ReviewFactLimitExceeded,
    snapshot_review_fact_limit,
)
from namisync.core.scalars import (
    bounded_utf8_text,
    require_safe_int,
    require_signed_64,
)

SessionId = NewType("SessionId", str)
MAX_SESSION_RESULT_ITEMS = 240_000
MAX_OPERATION_RESULT_PHASES = 3

_RESULT_ITEM_ACCUMULATOR_TYPE = "TypeError"
_RESULT_ITEM_EXACT_LIST_MESSAGE = "item accumulator must be an exact list"
_RESULT_ITEM_CONTENT_MESSAGE = (
    "item accumulator must contain only ResultItem values"
)
_RESULT_ITEM_LIMIT_TYPE = "RuntimeError"
_RESULT_ITEM_LIMIT_MESSAGE = "session result items exceed their session bound"
_RESULT_ITEM_MUTATION_TYPE = "RuntimeError"
_RESULT_ITEM_MUTATION_MESSAGE = (
    "session result item accumulator changed during emission"
)


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

    def __post_init__(self) -> None:
        if type(self.type_name) is not str:
            raise TypeError("failure type name must be text")
        if type(self.message) is not str:
            raise TypeError("failure message must be text")


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
        if type(self.phase) is not str:
            raise TypeError("phase result name must be text")
        if not self.phase:
            raise ValueError("phase result name must be non-empty")
        if type(self.status) is not PhaseStatus:
            raise TypeError("phase result status has the wrong type")
        if self.error is not None and type(self.error) is not str:
            raise TypeError("phase result error must be text or None")
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
        if type(self.status) is not SessionState or not is_terminal(self.status):
            raise ValueError("operation result status must be terminal")
        if type(self.recording) is not RecordingStatus:
            raise TypeError("operation result recording has the wrong type")
        if type(self.audit) is not RecordingStatus:
            raise TypeError("operation result audit has the wrong type")
        if type(self.disposition) is not Disposition:
            raise TypeError("operation result disposition has the wrong type")
        if type(self.canceled) is not bool:
            raise TypeError("operation result canceled must be a boolean")
        if not isinstance(self.items, tuple):
            raise TypeError("operation result items must be a tuple")
        if any(not isinstance(item, ResultItem) for item in self.items):
            raise TypeError("operation result items must implement ResultItem")
        if not isinstance(self.phases, tuple):
            raise TypeError("operation result phases must be a tuple")
        if any(not isinstance(phase, PhaseResult) for phase in self.phases):
            raise TypeError("operation result phases must contain PhaseResult values")
        if len(self.phases) > MAX_OPERATION_RESULT_PHASES:
            raise ValueError("operation result phases exceed their bound")
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


def _snapshot_phase_result(value: object) -> PhaseResult:
    if not isinstance(value, PhaseResult):
        raise TypeError("operation result phases must contain PhaseResult values")
    phase = value.phase
    status = value.status
    items_done = value.items_done
    items_total = value.items_total
    bytes_done = value.bytes_done
    bytes_total = value.bytes_total
    error = value.error
    return PhaseResult(
        phase,
        status,
        items_done,
        items_total,
        bytes_done,
        bytes_total,
        error,
    )


def _snapshot_failure_detail(value: object | None) -> FailureDetail | None:
    if value is None:
        return None
    if not isinstance(value, FailureDetail):
        raise TypeError("operation result error must be FailureDetail or None")
    type_name = value.type_name
    message = value.message
    return FailureDetail(type_name, message)


def _snapshot_recording_issue(value: object) -> TaskRecordingIssue:
    if not isinstance(value, TaskRecordingIssue):
        raise TypeError(
            "result recording_issues must contain TaskRecordingIssue values"
        )
    reason = value.reason
    detail = value.detail
    return TaskRecordingIssue(reason, detail)


def snapshot_result_item(value: object) -> ResultItem:
    """Detach one supported producer item into its exact public base shape."""

    from namisync.core.events import ItemOutcome, snapshot_item_outcome
    from namisync.core.integrity import IntegrityOutcome

    if isinstance(value, ItemOutcome):
        return snapshot_item_outcome(
            value,
            item_id=value.item_id,
            kind=value.kind,
            path=value.path,
        )
    if isinstance(value, IntegrityOutcome):
        phase = value.phase
        from namisync.core.integrity import snapshot_integrity_outcome

        return snapshot_integrity_outcome(
            value,
            item_id=value.item_id,
            row_id=value.row_id,
            location_id=value.location_id,
            path=value.path,
            phase=phase,
        )
    raise TypeError(f"unsupported result item: {type(value).__name__}")


def snapshot_operation_result(
    value: object,
    *,
    emitted_items: tuple[ResultItem, ...] | None = None,
) -> OperationResult:
    """Return exact terminal truth detached from a producer-owned result graph.

    ``emitted_items`` is reserved for a boundary's already-detached reliable
    stream. Those exact objects remain the authority instead of being copied a
    second time from a collaborator's return tuple.
    """

    if not isinstance(value, OperationResult):
        raise TypeError("workflow must return OperationResult")
    status = value.status
    recording = value.recording
    audit = value.audit
    disposition = value.disposition
    canceled = value.canceled
    source_items = value.items if emitted_items is None else emitted_items
    phases = value.phases
    bytes_done = value.bytes_done
    bytes_total = value.bytes_total
    error = value.error
    recording_issues = value.recording_issues
    omitted_detail_count = value.omitted_detail_count
    review_fact_limit = value.review_fact_limit
    if type(source_items) is not tuple:
        raise TypeError("operation result items must be a tuple")
    if len(source_items) > MAX_SESSION_RESULT_ITEMS:
        raise ValueError(_RESULT_ITEM_LIMIT_MESSAGE)
    if type(phases) is not tuple:
        raise TypeError("operation result phases must be a tuple")
    if len(phases) > MAX_OPERATION_RESULT_PHASES:
        raise ValueError("operation result phases exceed their bound")
    if type(recording_issues) is not tuple:
        raise TypeError("result recording_issues must be a tuple")
    if len(recording_issues) > 5:
        raise ValueError("result recording issues exceed their bound")
    if emitted_items is None:
        owned_items = tuple(snapshot_result_item(item) for item in source_items)
    else:
        from namisync.core.events import ItemOutcome
        from namisync.core.integrity import IntegrityOutcome

        if any(
            type(item) not in {ItemOutcome, IntegrityOutcome}
            for item in source_items
        ):
            raise TypeError("emitted result items must have exact public shapes")
        owned_items = source_items
    return OperationResult(
        status=status,
        recording=recording,
        audit=audit,
        disposition=disposition,
        canceled=canceled,
        items=owned_items,
        phases=tuple(_snapshot_phase_result(phase) for phase in phases),
        bytes_done=bytes_done,
        bytes_total=bytes_total,
        error=_snapshot_failure_detail(error),
        recording_issues=tuple(
            _snapshot_recording_issue(issue) for issue in recording_issues
        ),
        omitted_detail_count=omitted_detail_count,
        review_fact_limit=(
            None
            if review_fact_limit is None
            else snapshot_review_fact_limit(review_fact_limit)
        ),
    )


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

    boundary_failure_type: str | None = None
    boundary_failure_message: str | None = None
    external_items: list[ResultItem] | None = None
    if item_accumulator is None:
        items: list[ResultItem] = []
    elif type(item_accumulator) is not list:
        items = []
        boundary_failure_type = _RESULT_ITEM_ACCUMULATOR_TYPE
        boundary_failure_message = _RESULT_ITEM_EXACT_LIST_MESSAGE
    elif len(item_accumulator) > MAX_SESSION_RESULT_ITEMS:
        items = []
        boundary_failure_type = "ValueError"
        boundary_failure_message = _RESULT_ITEM_LIMIT_MESSAGE
    elif any(not isinstance(item, ResultItem) for item in item_accumulator):
        items = []
        boundary_failure_type = _RESULT_ITEM_ACCUMULATOR_TYPE
        boundary_failure_message = _RESULT_ITEM_CONTENT_MESSAGE
    else:
        external_items = item_accumulator
        try:
            items = [snapshot_result_item(item) for item in external_items]
        except Exception as error:
            retire_exception_graph(error)
            items = []
            external_items = None
            boundary_failure_type = _RESULT_ITEM_ACCUMULATOR_TYPE
            boundary_failure_message = _RESULT_ITEM_CONTENT_MESSAGE
        else:
            external_items.clear()
    admitted_item_count = len(items)
    latest_progress: Progress | None = None

    def set_boundary_failure(type_name: str, message: str) -> None:
        nonlocal boundary_failure_type, boundary_failure_message
        if boundary_failure_type is None:
            boundary_failure_type = type_name
            boundary_failure_message = message

    def detect_accumulator_mutation() -> bool:
        if external_items is None or not external_items:
            return False
        set_boundary_failure(
            _RESULT_ITEM_MUTATION_TYPE,
            _RESULT_ITEM_MUTATION_MESSAGE,
        )
        external_items.clear()
        return True

    def republish_accumulator() -> None:
        if external_items is None:
            return
        external_items[:] = [snapshot_result_item(item) for item in items]

    def observed_emit(body: object) -> None:
        nonlocal admitted_item_count, latest_progress
        if boundary_failure_type is not None:
            raise RuntimeError(boundary_failure_message)
        if detect_accumulator_mutation():
            raise RuntimeError(_RESULT_ITEM_MUTATION_MESSAGE)
        if isinstance(body, Terminal):
            raise ValueError("workflow code cannot emit Terminal")
        if isinstance(body, ResultItem):
            if admitted_item_count >= MAX_SESSION_RESULT_ITEMS:
                set_boundary_failure(
                    _RESULT_ITEM_LIMIT_TYPE,
                    _RESULT_ITEM_LIMIT_MESSAGE,
                )
                raise RuntimeError(_RESULT_ITEM_LIMIT_MESSAGE)
            snapshot = snapshot_result_item(body)
            try:
                emit(snapshot)
            except BaseException as error:
                if detect_accumulator_mutation():
                    retire_exception_graph(error)
                    raise RuntimeError(_RESULT_ITEM_MUTATION_MESSAGE) from None
                raise
            accumulator_mutated = detect_accumulator_mutation()
            items.append(snapshot)
            admitted_item_count += 1
            if accumulator_mutated:
                raise RuntimeError(_RESULT_ITEM_MUTATION_MESSAGE)
        elif isinstance(body, Progress):
            snapshot = Progress(
                phase=body.phase,
                items_done=body.items_done,
                items_total=body.items_total,
                bytes_done=body.bytes_done,
                bytes_total=body.bytes_total,
                current_path=body.current_path,
                item_id=body.item_id,
                item_type=body.item_type,
                item_attempt_id=body.item_attempt_id,
                item_bytes_done=body.item_bytes_done,
                item_bytes_total=body.item_bytes_total,
            )
            public_snapshot = Progress(
                phase=snapshot.phase,
                items_done=snapshot.items_done,
                items_total=snapshot.items_total,
                bytes_done=snapshot.bytes_done,
                bytes_total=snapshot.bytes_total,
                current_path=snapshot.current_path,
                item_id=snapshot.item_id,
                item_type=snapshot.item_type,
                item_attempt_id=snapshot.item_attempt_id,
                item_bytes_done=snapshot.item_bytes_done,
                item_bytes_total=snapshot.item_bytes_total,
            )
            emit(public_snapshot)
            latest_progress = snapshot
            if detect_accumulator_mutation():
                raise RuntimeError(_RESULT_ITEM_MUTATION_MESSAGE)
        else:
            emit(body)
            if detect_accumulator_mutation():
                raise RuntimeError(_RESULT_ITEM_MUTATION_MESSAGE)

    def boundary_failure_result() -> OperationResult:
        assert boundary_failure_type is not None
        assert boundary_failure_message is not None
        bytes_done = latest_progress.bytes_done if latest_progress else 0
        bytes_total = (
            latest_progress.bytes_total
            if latest_progress and latest_progress.bytes_total is not None
            else bytes_done
        )
        return OperationResult(
            status=SessionState.FAILED,
            disposition=disposition,
            items=tuple(items),
            bytes_done=bytes_done,
            bytes_total=bytes_total,
            error=FailureDetail(
                boundary_failure_type,
                boundary_failure_message,
            ),
        )

    context = RunContext(emit=observed_emit, checkpoint=checkpoint)
    if boundary_failure_type is not None:
        result = boundary_failure_result()
    else:
        try:
            returned = work(context)
            detect_accumulator_mutation()
            if boundary_failure_type is not None:
                del returned
                result = boundary_failure_result()
            else:
                try:
                    result = snapshot_operation_result(
                        returned,
                        emitted_items=tuple(items),
                    )
                finally:
                    del returned
        except PauseRequested as error:
            detect_accumulator_mutation()
            retire_exception_graph(error)
            if boundary_failure_type is None:
                republish_accumulator()
                try:
                    settle(SessionState.PAUSED, None)
                finally:
                    republish_accumulator()
                return RunOutcome(paused=True, result=None)
            result = boundary_failure_result()
        except Canceled as error:
            detect_accumulator_mutation()
            retire_exception_graph(error)
            if boundary_failure_type is not None:
                result = boundary_failure_result()
            else:
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
            detect_accumulator_mutation()
            if boundary_failure_type is not None:
                retire_exception_graph(error)
                result = boundary_failure_result()
            else:
                bytes_done = latest_progress.bytes_done if latest_progress else 0
                bytes_total = (
                    latest_progress.bytes_total
                    if latest_progress and latest_progress.bytes_total is not None
                    else bytes_done
                )
                try:
                    try:
                        detail = _bounded_failure_detail(
                            FailureDetail(type(error).__name__, str(error))
                        )
                    except Exception as diagnostic_error:
                        retire_exception_graph(diagnostic_error)
                        detail = None
                finally:
                    retire_exception_graph(error)
                result = OperationResult(
                    status=SessionState.FAILED,
                    disposition=disposition,
                    items=tuple(items),
                    bytes_done=bytes_done,
                    bytes_total=bytes_total,
                    error=detail,
                    omitted_detail_count=1 if detail is None else 0,
                )
        except BaseException as error:
            detect_accumulator_mutation()
            if boundary_failure_type is None:
                republish_accumulator()
                raise
            retire_exception_graph(error)
            result = boundary_failure_result()

    recording = (
        RecordingStatus.DEGRADED
        if result.recording_issues
        or any(
            item.recording is RecordingStatus.DEGRADED
            for item in result.items
        )
        else RecordingStatus.OK
    )
    result = normalize_result_diagnostics(replace(result, recording=recording))

    try:
        settle(result_terminal_state(result), result)
        try:
            audit = finalize_audit(result)
            if type(audit) is not RecordingStatus:
                raise TypeError("audit finalizer must return RecordingStatus")
        except Exception as error:
            retire_exception_graph(error)
            audit = RecordingStatus.DEGRADED
        final_result = replace(result, audit=audit)
        publish_result(final_result)
        summary = TerminalSummary.from_result(final_result)
        emit(Terminal(summary))
        return RunOutcome(paused=False, result=final_result)
    finally:
        republish_accumulator()
