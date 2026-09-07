"""Bounded, incrementally durable sync history and readback."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Callable, Mapping

from namisync.core.clock import Clock
from namisync.core.event_v5 import validate_event_v5_envelope
from namisync.core.exception_graph import retire_exception_graph
from namisync.core.events import (
    CORE_EVENT_SCHEMA_VERSION,
    Envelope,
    Gap,
    ItemOutcome,
    PhaseChanged,
    Progress,
    StateChanged,
    Terminal,
    TerminalSummary,
    envelope_from_dict,
    envelope_to_dict,
    result_item_to_dict,
    terminal_summary_to_dict,
)
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.execution import TaskRecordingIssue, TaskRecordingIssueReason
from namisync.core.integrity import IntegrityMode, IntegrityResult
from namisync.core.session import (
    Disposition,
    FailureDetail,
    OperationResult,
    PhaseResult,
    PhaseStatus,
    ResultItem,
    SessionRecord,
    SessionState,
    result_terminal_state,
)
from namisync.core.review import (
    ReviewFactLimitExceeded,
    ReviewLimitAxis,
    ReviewPopulation,
    ReviewTreeKind,
)
from namisync.core.scalars import require_safe_int

from .connections import (
    DEFAULT_BUSY_TIMEOUT_MS,
    connect_history_reader,
    connect_history_writer,
)
from .contracts import require_database_file_contract
from .schema import (
    MAX_HISTORY_ERROR_MESSAGE_BYTES,
    MAX_HISTORY_ERROR_TYPE_BYTES,
    MAX_HISTORY_PHASE_NAME_BYTES,
    initialize_history,
    validate_history_reader_contract,
)
from .timestamps import decode_utc, encode_utc
from .writer import (
    DEFAULT_RETRY_TIMEOUT_SECONDS,
    RecordingError,
    SerializedWriter,
    TokenConflictError,
)


MAX_HISTORY_PAGE_SIZE = 256
MAX_HISTORY_PHASES = 3
_EMPTY_EVENT_CHAIN = hashlib.sha256(b"").digest()
_HISTORY_BODY_TYPES = frozenset(
    {
        "StateChanged",
        "PhaseChanged",
        "Progress",
        "ItemOutcome",
        "IntegrityOutcome",
        "Gap",
        "Terminal",
    }
)


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"history JSON contains duplicate key: {key}")
        result[key] = value
    return result

class HistoryIntegrityError(RecordingError):
    """The reliable event prefix violates the history integrity contract."""


class HistoryEventDisposition(StrEnum):
    RECORDED = "recorded"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


EVENT_TOO_LARGE = "event-too-large"


@dataclass(frozen=True, slots=True)
class HistoryWindowPolicy:
    """Hard bounds and the dispatcher-facing age target for one window."""

    max_events: int = 256
    max_bytes: int = 1_048_576
    max_event_bytes: int = 1_048_576
    max_age_seconds: float = 1.0

    def __post_init__(self) -> None:
        integer_bounds = (self.max_events, self.max_bytes, self.max_event_bytes)
        if any(type(value) is not int or value < 1 for value in integer_bounds):
            raise ValueError("history window count and byte bounds must be positive")
        if self.max_event_bytes > self.max_bytes:
            raise ValueError("one history event cannot exceed the window byte bound")
        if (
            isinstance(self.max_age_seconds, bool)
            or not isinstance(self.max_age_seconds, (int, float))
            or not math.isfinite(self.max_age_seconds)
            or self.max_age_seconds <= 0
        ):
            raise ValueError("history window age must be positive")


DEFAULT_HISTORY_WINDOW_POLICY = HistoryWindowPolicy()


@dataclass(frozen=True, slots=True)
class HistoryContext:
    run_token: str
    host_key: str
    activity_kind: str | None = None
    subject_kind: str | None = None
    subject_id: str | None = None
    source_context: str | None = None
    target_context: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.run_token, str) or not isinstance(
            self.host_key, str
        ):
            raise TypeError("history run token and host key must be strings")
        if not self.run_token or not self.host_key:
            raise ValueError("history run token and host key are required")
        for field_name in (
            "activity_kind",
            "subject_kind",
            "subject_id",
            "source_context",
            "target_context",
        ):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"history {field_name} must be text or None")
        if self.activity_kind == "":
            raise ValueError("history activity kind must be non-empty")


@dataclass(frozen=True, slots=True)
class HistoryItemSnapshot:
    item_order: int
    event_seq: int
    item: ResultItem


@dataclass(frozen=True, slots=True)
class HistoryEventSnapshot:
    event_seq: int
    event_at: datetime
    schema_version: int
    body_type: str
    disposition: HistoryEventDisposition
    envelope: Envelope | None
    payload_hash: bytes
    receipt_hash: bytes
    duplicate_of_seq: int | None = None
    rejection_reason: str | None = None


@dataclass(frozen=True, slots=True)
class HistoryPhaseSnapshot:
    phase_order: int
    phase: PhaseResult


@dataclass(frozen=True, slots=True)
class HistoryClassificationQuery:
    """Workflow-owned predicates for fixed-size summary aggregates."""

    excluded_operation_reasons: tuple[str, ...] = ()
    noop_operation_kind: str = "noop"

    def __post_init__(self) -> None:
        reasons = self.excluded_operation_reasons
        if not isinstance(reasons, tuple) or any(
            not isinstance(reason, str) or not reason for reason in reasons
        ):
            raise TypeError("history exclusion reasons must be non-empty strings")
        if reasons != tuple(sorted(set(reasons))):
            raise ValueError("history exclusion reasons must be unique and sorted")
        if len(reasons) > MAX_HISTORY_PAGE_SIZE:
            raise ValueError(
                f"history supports at most {MAX_HISTORY_PAGE_SIZE} exclusion reasons"
            )
        if (
            not isinstance(self.noop_operation_kind, str)
            or not self.noop_operation_kind
        ):
            raise TypeError("history noop operation kind must be a non-empty string")


DEFAULT_HISTORY_CLASSIFICATION_QUERY = HistoryClassificationQuery()


@dataclass(frozen=True, slots=True)
class HistoryClassificationAggregate:
    operation_results: frozenset[str]
    selected_operation_count: int
    selected_other_operation_count: int
    integrity_results: frozenset[str]
    verify_phase_baseline: bool


@dataclass(frozen=True, slots=True)
class _ClassificationCounts:
    selected_operation_count: int
    selected_other_operation_count: int
    integrity_results: frozenset[str]
    verify_phase_baseline: bool


@dataclass(frozen=True, slots=True)
class HistoryRunSummary:
    run_token: str
    session_id: str
    activity_kind: str
    host_key: str
    subject_kind: str | None
    subject_id: str | None
    source_context: str | None
    target_context: str | None
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    current_state: SessionState
    current_phase: str | None
    last_committed_seq: int
    item_count: int
    duplicate_item_count: int
    rejected_event_count: int
    last_committed_at: datetime | None
    finalized: bool
    filesystem_status: SessionState | None
    recording: RecordingStatus | None
    audit: RecordingStatus | None
    disposition: str | None
    canceled: bool | None
    bytes_done: int | None
    bytes_total: int | None
    recording_degraded_items: int | None
    recording_issues: tuple[TaskRecordingIssue, ...]
    omitted_detail_count: int | None
    review_fact_limit: ReviewFactLimitExceeded | None
    succeeded_count: int
    skipped_count: int
    failed_count: int
    canceled_count: int
    deferred_count: int
    blocked_count: int
    phases: tuple[HistoryPhaseSnapshot, ...]
    classification: HistoryClassificationAggregate
    error_type: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class HistoryItemPage:
    run_token: str
    through_order: int
    items: tuple[HistoryItemSnapshot, ...]
    next_after_order: int
    has_more: bool


@dataclass(frozen=True, slots=True)
class HistoryEventPage:
    run_token: str
    session_id: str
    through_seq: int
    events: tuple[HistoryEventSnapshot, ...]
    next_after_seq: int
    has_more: bool


def _primitive(value: object) -> object:
    if isinstance(value, bytes):
        return {"$bytes": value.hex()}
    if isinstance(value, datetime):
        return encode_utc(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            field.name: _primitive(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): _primitive(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_primitive(item) for item in value]
    return value


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        _primitive(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8", errors="strict")


def _hash(value: object) -> bytes:
    return hashlib.sha256(_json_bytes(value)).digest()


def _advance_event_chain(chain: bytes, receipt_hash: bytes) -> bytes:
    return hashlib.sha256(chain + receipt_hash).digest()


def _receipt_hash(
    *,
    event_seq: int,
    event_at: str,
    schema_version: int,
    body_type: str,
    disposition: HistoryEventDisposition,
    payload_hash: bytes,
    item_identity_hash: bytes | None = None,
    item_payload_hash: bytes | None = None,
    duplicate_of_seq: int | None = None,
    rejection_reason: str | None = None,
    item_order: int | None = None,
) -> bytes:
    return _hash(
        {
            "event_seq": event_seq,
            "event_at": event_at,
            "schema_version": schema_version,
            "body_type": body_type,
            "disposition": disposition.value,
            "payload_hash": payload_hash,
            "item_identity_hash": item_identity_hash,
            "item_payload_hash": item_payload_hash,
            "duplicate_of_seq": duplicate_of_seq,
            "rejection_reason": rejection_reason,
            "item_order": item_order,
        }
    )


def _rejection_receipt_size(
    envelope: Envelope,
    payload_hash: bytes,
    reason: str,
    item_identity_hash: bytes | None,
    item_payload_hash: bytes | None,
) -> int:
    receipt_hash = _receipt_hash(
        event_seq=envelope.seq,
        event_at=encode_utc(envelope.at),
        schema_version=envelope.schema_version,
        body_type=type(envelope.body).__name__,
        disposition=HistoryEventDisposition.REJECTED,
        payload_hash=payload_hash,
        item_identity_hash=item_identity_hash,
        item_payload_hash=item_payload_hash,
        rejection_reason=reason,
    )
    return len(
        _json_bytes(
            {
                "event_seq": envelope.seq,
                "event_at": envelope.at,
                "schema_version": envelope.schema_version,
                "body_type": type(envelope.body).__name__,
                "disposition": HistoryEventDisposition.REJECTED,
                "payload_hash": payload_hash,
                "receipt_hash": receipt_hash,
                "item_identity_hash": item_identity_hash,
                "item_payload_hash": item_payload_hash,
                "rejection_reason": reason,
            }
        )
    )


def _context_payload(
    record: SessionRecord, context: HistoryContext
) -> dict[str, object]:
    return {
        "run_token": context.run_token,
        "session_id": str(record.session_id),
        "activity_kind": context.activity_kind or record.kind,
        "host_key": context.host_key,
        "subject_kind": context.subject_kind,
        "subject_id": context.subject_id,
        "source_context": context.source_context,
        "target_context": context.target_context,
        "created_at": record.created_at,
    }


def _terminal_result_payload(result: TerminalSummary) -> dict[str, object]:
    return terminal_summary_to_dict(result)


def _recording_issues_json(issues: tuple[TaskRecordingIssue, ...]) -> str:
    return json.dumps(
        [
            {"reason": issue.reason.value, "detail": issue.detail}
            for issue in issues
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _recording_issues_from_json(value: object) -> tuple[TaskRecordingIssue, ...]:
    if type(value) is not str:
        raise HistoryIntegrityError("history recording issues must be JSON text")
    try:
        raw = json.loads(value, object_pairs_hook=_unique_json_object)
    except (TypeError, ValueError) as error:
        raise HistoryIntegrityError(
            "history recording issues are invalid JSON"
        ) from error
    if type(raw) is not list:
        raise HistoryIntegrityError("history recording issues must be an array")
    issues: list[TaskRecordingIssue] = []
    try:
        for item in raw:
            if type(item) is not dict or set(item) != {"reason", "detail"}:
                raise HistoryIntegrityError(
                    "history recording issue shape is invalid"
                )
            detail = item["detail"]
            if detail is not None and type(detail) is not str:
                raise HistoryIntegrityError(
                    "history recording issue detail is invalid"
                )
            issues.append(
                TaskRecordingIssue(
                    TaskRecordingIssueReason(item["reason"]),
                    detail,
                )
            )
    except HistoryIntegrityError:
        raise
    except (TypeError, ValueError) as error:
        raise HistoryIntegrityError(
            "history recording issue value is invalid"
        ) from error
    result = tuple(issues)
    if _recording_issues_json(result) != value:
        raise HistoryIntegrityError(
            "history recording issues are not canonically encoded"
        )
    return result


def _review_fact_values(
    fact: ReviewFactLimitExceeded | None,
) -> tuple[object, object, object, object, object, object]:
    if fact is None:
        return (None, None, None, None, None, None)
    return (
        fact.reason,
        fact.tree_kind.value,
        fact.population.value,
        fact.axis.value,
        fact.row_limit,
        fact.byte_limit,
    )


def _review_fact_from_row(row: sqlite3.Row) -> ReviewFactLimitExceeded | None:
    values = (
        row["review_reason"],
        row["review_tree_kind"],
        row["review_population"],
        row["review_axis"],
        row["review_row_limit"],
        row["review_byte_limit"],
    )
    if all(value is None for value in values):
        return None
    if any(value is None for value in values[:4]):
        raise HistoryIntegrityError("history review-limit columns disagree")
    try:
        return ReviewFactLimitExceeded(
            reason=str(values[0]),
            tree_kind=ReviewTreeKind(str(values[1])),
            population=ReviewPopulation(str(values[2])),
            axis=ReviewLimitAxis(str(values[3])),
            row_limit=None if values[4] is None else int(values[4]),
            byte_limit=None if values[5] is None else int(values[5]),
        )
    except (TypeError, ValueError) as error:
        raise HistoryIntegrityError(
            "history review-limit columns are invalid"
        ) from error


def _prefix_projection_hash(
    context_hash: bytes,
    event_chain_hash: bytes,
    *,
    started_at: datetime | None,
    current_state: str,
    current_phase: str | None,
    last_committed_seq: int,
    item_count: int,
    last_committed_at: datetime | None,
    duplicate_item_count: int,
    rejected_event_count: int,
    succeeded_count: int,
    skipped_count: int,
    failed_count: int,
    canceled_count: int,
    deferred_count: int,
    blocked_count: int,
) -> bytes:
    return _hash(
        {
            "context_hash": context_hash,
            "event_chain_hash": event_chain_hash,
            "started_at": started_at,
            "current_state": current_state,
            "current_phase": current_phase,
            "last_committed_seq": last_committed_seq,
            "item_count": item_count,
            "last_committed_at": last_committed_at,
            "duplicate_item_count": duplicate_item_count,
            "rejected_event_count": rejected_event_count,
            "outcome_counts": {
                Outcome.SUCCEEDED.value: succeeded_count,
                Outcome.SKIPPED.value: skipped_count,
                Outcome.FAILED.value: failed_count,
                Outcome.CANCELED.value: canceled_count,
                Outcome.DEFERRED.value: deferred_count,
                Outcome.BLOCKED.value: blocked_count,
            },
        }
    )


def _terminal_payload_hash(
    context_hash: bytes,
    prefix_projection_hash: bytes,
    ended_at: datetime,
    result: TerminalSummary,
) -> bytes:
    return _hash(
        {
            "context_hash": context_hash,
            "prefix_projection_hash": prefix_projection_hash,
            "ended_at": ended_at,
            "result": _terminal_result_payload(result),
        }
    )


def _validate_terminal_text(result: OperationResult | TerminalSummary) -> None:
    for phase in result.phases:
        _validate_bounded_text(
            phase.phase,
            MAX_HISTORY_PHASE_NAME_BYTES,
            "terminal phase name",
        )
        if phase.error is not None:
            _validate_bounded_text(
                phase.error,
                MAX_HISTORY_ERROR_MESSAGE_BYTES,
                "terminal phase error",
            )
    if result.error is not None:
        _validate_bounded_text(
            result.error.type_name,
            MAX_HISTORY_ERROR_TYPE_BYTES,
            "terminal error type",
        )
        _validate_bounded_text(
            result.error.message,
            MAX_HISTORY_ERROR_MESSAGE_BYTES,
            "terminal error message",
        )


def _validate_bounded_text(value: object, maximum: int, field: str) -> str:
    if not isinstance(value, str):
        raise HistoryIntegrityError(f"{field} must be text")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise HistoryIntegrityError(f"{field} must be valid Unicode") from error
    if len(encoded) > maximum:
        raise HistoryIntegrityError(f"{field} exceeds its UTF-8 byte bound")
    return value


def _history_safe_int(value: object, field: str) -> int:
    try:
        return require_safe_int(value, field)
    except (TypeError, ValueError) as error:
        raise HistoryIntegrityError(f"{field} is invalid") from error


@dataclass(frozen=True, slots=True)
class _ExistingRun:
    context_hash: bytes
    last_committed_seq: int
    terminal_payload_hash: bytes | None


@dataclass(frozen=True, slots=True)
class _PendingEvent:
    event_seq: int
    event_at: datetime
    schema_version: int
    body_type: str
    envelope: Envelope | None
    envelope_json: str | None
    encoded_size: int
    payload_hash: bytes
    item_identity_hash: bytes | None
    item_payload_hash: bytes | None
    rejection_reason: str | None = None


@dataclass(frozen=True, slots=True)
class _AppendResult:
    event_chain_hash: bytes
    prefix_projection_hash: bytes
    started_at: datetime | None
    committed_at: datetime
    terminal_payload_hash: bytes | None
    duplicate_item_count: int
    rejected_event_count: int


@dataclass(slots=True)
class _CanonicalItemIndex:
    by_identity: dict[tuple[str, str], tuple[int, bytes]]
    by_identity_hash: dict[bytes, tuple[int, bytes]]


@dataclass(frozen=True, slots=True)
class _ValidatedReceipt:
    event_seq: int
    event_at_text: str
    event_at: datetime
    schema_version: int
    body_type: str
    disposition: HistoryEventDisposition
    payload_hash: bytes
    receipt_hash: bytes
    item_identity_hash: bytes | None
    item_payload_hash: bytes | None
    duplicate_of_seq: int | None
    rejection_reason: str | None
    item_order: int | None


class HistoryStore:
    def __init__(
        self,
        path: str | Path,
        *,
        clock: Clock,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        retry_timeout_seconds: float = DEFAULT_RETRY_TIMEOUT_SECONDS,
        retry_interval_seconds: float = 0.025,
        managed_roots: tuple[str | Path, ...] = (),
        window_policy: HistoryWindowPolicy = DEFAULT_HISTORY_WINDOW_POLICY,
    ) -> None:
        self.path = initialize_history(
            path,
            busy_timeout_ms=busy_timeout_ms,
            managed_roots=managed_roots,
        )
        if not isinstance(window_policy, HistoryWindowPolicy):
            raise TypeError("window_policy must be HistoryWindowPolicy")
        self._clock = clock
        self._busy_timeout_ms = busy_timeout_ms
        self._retry_timeout_seconds = retry_timeout_seconds
        self._retry_interval_seconds = retry_interval_seconds
        self._window_policy = window_policy
        self._writer = SerializedWriter(
            self.path,
            connect_history_writer,
            busy_timeout_ms=busy_timeout_ms,
            retry_timeout_seconds=retry_timeout_seconds,
            retry_interval_seconds=retry_interval_seconds,
        )

    def observer(
        self,
        record: SessionRecord,
        context: HistoryContext,
        *,
        window_policy: HistoryWindowPolicy | None = None,
    ) -> HistoryObserver:
        return HistoryObserver(
            self,
            record,
            context,
            window_policy or self._window_policy,
        )

    def _load_existing(self, run_token: str) -> _ExistingRun | None:
        try:
            connection = connect_history_reader(
                self.path, busy_timeout_ms=self._busy_timeout_ms
            )
            try:
                connection.execute("BEGIN")
                row = connection.execute(
                    """SELECT run.*,
                              COALESCE((
                                  SELECT tail.event_seq
                                    FROM history_events AS tail
                                   WHERE tail.run_id = run.id
                                   ORDER BY tail.event_seq DESC LIMIT 1
                              ), 0) AS actual_last_event_seq,
                              COALESCE((
                                  SELECT tail.item_order
                                    FROM history_events AS tail
                                   WHERE tail.run_id = run.id
                                     AND tail.item_order IS NOT NULL
                                   ORDER BY tail.item_order DESC LIMIT 1
                              ), 0) AS actual_last_item_order
                         FROM history_runs AS run
                        WHERE run.run_token = ?""",
                    (run_token,),
                ).fetchone()
                if row is not None:
                    run_id = int(row["id"])
                    phases = _load_phase_snapshots(connection, (run_id,))[run_id]
                    _validate_terminal_snapshot(row, tuple(phases))
                    _validate_physical_watermarks(row)
            finally:
                if connection.in_transaction:
                    connection.rollback()
                connection.close()
        except sqlite3.Error as error:
            raise RecordingError(str(error)) from error
        if row is None:
            return None
        return _ExistingRun(
            context_hash=bytes(row["context_hash"]),
            last_committed_seq=int(row["last_committed_seq"]),
            terminal_payload_hash=(
                None
                if row["terminal_payload_hash"] is None
                else bytes(row["terminal_payload_hash"])
            ),
        )

    def _load_event_receipt(
        self, run_token: str, event_seq: int
    ) -> tuple[bytes, HistoryEventDisposition] | None:
        deadline = time.monotonic() + self._retry_timeout_seconds
        attempted = False
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 and (
                attempted or self._retry_timeout_seconds > 0
            ):
                raise RecordingError(
                    "history replay lookup remained busy for "
                    f"{self._retry_timeout_seconds:.3f}s"
                ) from None
            connection: sqlite3.Connection | None = None
            failure_in_flight = False
            try:
                connection = connect_history_reader(
                    self.path,
                    busy_timeout_ms=min(
                        self._busy_timeout_ms,
                        max(0, int(max(remaining, 0.0) * 1_000)),
                    ),
                )
                row = connection.execute(
                    """SELECT event.*
                         FROM history_events AS event
                         JOIN history_runs AS run ON run.id = event.run_id
                        WHERE run.run_token = ? AND event.event_seq = ?""",
                    (run_token, event_seq),
                ).fetchone()
                if row is None:
                    return None
                receipt = _validated_receipt(row)
                return (
                    receipt.payload_hash,
                    receipt.disposition,
                )
            except sqlite3.OperationalError as error:
                failure_in_flight = True
                try:
                    detail = str(error)
                finally:
                    retire_exception_graph(error)
                normalized_detail = detail.lower()
                busy = "locked" in normalized_detail or "busy" in normalized_detail
                del normalized_detail
                if not busy:
                    raise RecordingError(detail) from None
                del detail
                attempted = True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RecordingError(
                        "history replay lookup remained busy for "
                        f"{self._retry_timeout_seconds:.3f}s"
                    ) from None
                time.sleep(min(self._retry_interval_seconds, remaining))
                failure_in_flight = False
            except (TypeError, ValueError) as error:
                failure_in_flight = True
                retire_exception_graph(error)
                raise HistoryIntegrityError(
                    "history replay receipt is invalid"
                ) from None
            except sqlite3.Error as error:
                failure_in_flight = True
                try:
                    detail = str(error)
                finally:
                    retire_exception_graph(error)
                raise RecordingError(detail) from None
            except BaseException:
                failure_in_flight = True
                raise
            finally:
                if connection is not None:
                    try:
                        connection.close()
                    except BaseException as close_error:
                        retire_exception_graph(close_error)
                        if not failure_in_flight:
                            raise

    def close(self) -> None:
        self._writer.close()

    def __enter__(self) -> HistoryStore:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


class HistoryObserver:
    """Consumes reliable envelopes into bounded, atomic history windows."""

    def __init__(
        self,
        store: HistoryStore,
        record: SessionRecord,
        context: HistoryContext,
        policy: HistoryWindowPolicy,
    ) -> None:
        self._store = store
        self._record = record
        self._context = context
        self._policy = policy
        self._context_hash = _hash(_context_payload(record, context))
        existing = store._load_existing(context.run_token)
        if existing is not None and existing.context_hash != self._context_hash:
            raise TokenConflictError("history run token context changed")
        self._event_hashes: dict[int, bytes] = {}
        self._highest_event_seq = (
            None if existing is None or existing.last_committed_seq == 0
            else existing.last_committed_seq
        )
        self._existing_terminal_hash = (
            None if existing is None else existing.terminal_payload_hash
        )
        self._pending: list[_PendingEvent] = []
        self._pending_rejections: set[int] = set()
        self._pending_bytes = 0
        self._closed = False
        self._failed = False
        self._finalized = False

    @property
    def pending_event_count(self) -> int:
        return len(self._pending)

    @property
    def pending_bytes(self) -> int:
        return self._pending_bytes

    def on_event(self, envelope: Envelope) -> RecordingStatus:
        self._require_accepting()
        try:
            return self._admit(envelope)
        except BaseException as error:
            self._failed = True
            retire_exception_graph(error)
            raise

    def _admit(self, envelope: Envelope) -> RecordingStatus:
        if str(envelope.session_id) != str(self._record.session_id):
            raise HistoryIntegrityError("event belongs to another session")
        if isinstance(envelope.body, (Terminal, Progress)):
            raise HistoryIntegrityError(
                "history receives reliable preterminal events only"
            )
        if not isinstance(
            envelope.body, (StateChanged, PhaseChanged, Gap, ResultItem)
        ):
            raise HistoryIntegrityError(
                f"unsupported reliable event body: {type(envelope.body).__name__}"
            )

        projection = envelope_to_dict(envelope)
        try:
            validate_event_v5_envelope(projection)
        except (TypeError, ValueError) as error:
            raise HistoryIntegrityError(
                "history event projection is invalid"
            ) from error
        encoded = _json_bytes(projection)
        encoded_size = len(encoded)
        digest = hashlib.sha256(encoded).digest()
        item_identity_hash = (
            None
            if not isinstance(envelope.body, ResultItem)
            else _item_identity_hash(envelope.body)
        )
        item_payload_hash = (
            None
            if not isinstance(envelope.body, ResultItem)
            else _hash(result_item_to_dict(envelope.body))
        )
        prior = self._event_hashes.get(envelope.seq)
        if prior is not None:
            if prior != digest:
                raise HistoryIntegrityError(
                    "event sequence was reused with another payload"
                )
            return (
                RecordingStatus.DEGRADED
                if envelope.seq in self._pending_rejections
                else RecordingStatus.OK
            )
        if (
            self._highest_event_seq is not None
            and envelope.seq <= self._highest_event_seq
        ):
            durable = self._store._load_event_receipt(
                self._context.run_token, envelope.seq
            )
            if durable is None:
                raise HistoryIntegrityError("reliable events arrived out of order")
            durable_hash, disposition = durable
            if durable_hash != digest:
                raise HistoryIntegrityError(
                    "event sequence was reused with another payload"
                )
            return (
                RecordingStatus.DEGRADED
                if disposition is HistoryEventDisposition.REJECTED
                else RecordingStatus.OK
            )
        if self._existing_terminal_hash is not None:
            raise HistoryIntegrityError("finalized history cannot accept new events")

        rejection_reason = (
            EVENT_TOO_LARGE
            if encoded_size > self._policy.max_event_bytes
            else None
        )
        retained_size = (
            encoded_size
            if rejection_reason is None
            else _rejection_receipt_size(
                envelope,
                digest,
                rejection_reason,
                item_identity_hash,
                item_payload_hash,
            )
        )

        if self._pending and (
            len(self._pending) + 1 > self._policy.max_events
            or self._pending_bytes + retained_size > self._policy.max_bytes
        ):
            self.flush()

        pending = _PendingEvent(
            event_seq=envelope.seq,
            event_at=envelope.at,
            schema_version=envelope.schema_version,
            body_type=type(envelope.body).__name__,
            envelope=None if rejection_reason is not None else envelope,
            envelope_json=(
                None
                if rejection_reason is not None
                else encoded.decode("utf-8")
            ),
            encoded_size=retained_size,
            payload_hash=digest,
            item_identity_hash=item_identity_hash,
            item_payload_hash=item_payload_hash,
            rejection_reason=rejection_reason,
        )
        self._pending.append(pending)
        self._pending_bytes += retained_size
        self._event_hashes[envelope.seq] = digest
        if rejection_reason is not None:
            self._pending_rejections.add(envelope.seq)
        self._highest_event_seq = envelope.seq
        if (
            len(self._pending) >= self._policy.max_events
            or self._pending_bytes >= self._policy.max_bytes
            or rejection_reason is not None
            or (
                isinstance(envelope.body, StateChanged)
                and envelope.body.state is SessionState.PAUSED
            )
        ):
            self.flush()
        return (
            RecordingStatus.DEGRADED
            if rejection_reason is not None
            else RecordingStatus.OK
        )

    def flush(self) -> None:
        """Commit the current window once; repeated empty flushes are no-ops."""

        if self._closed or self._finalized:
            return
        if self._failed:
            raise HistoryIntegrityError("history observer is degraded")
        if not self._pending:
            return
        try:
            self._commit_window(None)
        except BaseException as error:
            self._failed = True
            retire_exception_graph(error)
            raise
        self._accept_commit()

    def finalize(self, result: OperationResult) -> RecordingStatus:
        if self._closed:
            raise HistoryIntegrityError("history observer is closed")
        if self._failed:
            raise HistoryIntegrityError("history observer is degraded")
        if len(result.phases) > MAX_HISTORY_PHASES:
            self._failed = True
            raise HistoryIntegrityError(
                f"history supports at most {MAX_HISTORY_PHASES} terminal phases"
            )
        try:
            terminal_summary = TerminalSummary.from_result(result)
            _validate_terminal_text(terminal_summary)
        except BaseException as error:
            self._failed = True
            if isinstance(error, HistoryIntegrityError):
                retire_exception_graph(error)
                raise
            retire_exception_graph(error)
            raise HistoryIntegrityError("history terminal summary is invalid") from None
        try:
            _, payload_hash, audit = self._commit_window(result)
        except BaseException as error:
            self._failed = True
            retire_exception_graph(error)
            raise
        self._accept_commit()
        self._existing_terminal_hash = payload_hash
        self._finalized = True
        if audit is None:
            raise HistoryIntegrityError("history terminal audit status is missing")
        return audit

    def _commit_window(
        self, result: OperationResult | None
    ) -> tuple[_AppendResult, bytes | None, RecordingStatus | None]:
        pending = tuple(self._pending)

        def apply(
            connection: sqlite3.Connection,
        ) -> tuple[_AppendResult, bytes | None, RecordingStatus | None]:
            # Sample only after SerializedWriter owns BEGIN IMMEDIATE. Sampling
            # before writer admission lets a later transaction carry an older
            # timestamp than the watermark it advances.
            sampled_at = self._store._clock.now()
            run_id = self._ensure_run(connection)
            append = self._append_events(
                connection, run_id, pending, sampled_at
            )
            if result is None:
                return append, None, None
            durable_result = (
                replace(result, audit=RecordingStatus.DEGRADED)
                if append.rejected_event_count > 0
                else result
            )
            terminal_summary = TerminalSummary.from_result(durable_result)
            terminal_state = result_terminal_state(durable_result).value
            projection_row = connection.execute(
                "SELECT * FROM history_runs WHERE id = ?", (run_id,)
            ).fetchone()
            ended_at = (
                decode_utc(projection_row["ended_at"])
                if append.terminal_payload_hash is not None
                else append.committed_at
            )
            terminal_prefix_hash = _prefix_projection_hash_from_row(
                projection_row,
                current_state=terminal_state,
            )
            payload_hash = _terminal_payload_hash(
                self._context_hash,
                terminal_prefix_hash,
                ended_at,
                terminal_summary,
            )
            if append.terminal_payload_hash is not None:
                stored_phases = _load_phase_snapshots(connection, (run_id,))[run_id]
                _validate_terminal_snapshot(
                    projection_row,
                    tuple(stored_phases),
                )
                if append.terminal_payload_hash != payload_hash:
                    raise TokenConflictError("history run token payload changed")
                return append, payload_hash, terminal_summary.audit
            started_at = append.started_at
            if ended_at < (started_at or self._record.created_at):
                raise RecordingError("history end precedes actual start")

            connection.executemany(
                """INSERT INTO history_phases(
                       run_id, phase_order, phase, status, items_done,
                       items_total, bytes_done, bytes_total, error
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    (
                        run_id,
                        order,
                        phase.phase,
                        phase.status.value,
                        phase.items_done,
                        phase.items_total,
                        phase.bytes_done,
                        phase.bytes_total,
                        phase.error,
                    )
                    for order, phase in enumerate(terminal_summary.phases)
                ),
            )
            connection.execute(
                """UPDATE history_runs
                      SET started_at = ?, ended_at = ?, current_state = ?,
                          filesystem_status = ?, recording_status = ?,
                          audit_status = ?, disposition = ?, canceled = ?,
                          bytes_done = ?, bytes_total = ?, error_type = ?,
                          error_message = ?, recording_degraded_items = ?,
                          recording_issues_json = ?, omitted_detail_count = ?,
                          review_reason = ?, review_tree_kind = ?,
                          review_population = ?, review_axis = ?,
                          review_row_limit = ?, review_byte_limit = ?,
                          prefix_projection_hash = ?, terminal_payload_hash = ?
                    WHERE id = ?""",
                (
                    None if started_at is None else encode_utc(started_at),
                    encode_utc(ended_at),
                    terminal_state,
                    terminal_summary.status.value,
                    terminal_summary.recording.value,
                    terminal_summary.audit.value,
                    terminal_summary.disposition.value,
                    int(terminal_summary.canceled),
                    terminal_summary.bytes_done,
                    terminal_summary.bytes_total,
                    (
                        None
                        if terminal_summary.error is None
                        else terminal_summary.error.type_name
                    ),
                    (
                        None
                        if terminal_summary.error is None
                        else terminal_summary.error.message
                    ),
                    terminal_summary.recording_degraded_items,
                    _recording_issues_json(terminal_summary.recording_issues),
                    terminal_summary.omitted_detail_count,
                    *_review_fact_values(terminal_summary.review_fact_limit),
                    terminal_prefix_hash,
                    payload_hash,
                    run_id,
                ),
            )
            return (
                _AppendResult(
                    event_chain_hash=append.event_chain_hash,
                    started_at=started_at,
                    committed_at=append.committed_at,
                    terminal_payload_hash=payload_hash,
                    prefix_projection_hash=terminal_prefix_hash,
                    duplicate_item_count=append.duplicate_item_count,
                    rejected_event_count=append.rejected_event_count,
                ),
                payload_hash,
                terminal_summary.audit,
            )

        return self._store._writer.transact(apply)

    def _ensure_run(self, connection: sqlite3.Connection) -> int:
        row = connection.execute(
            """SELECT run.*,
                      COALESCE((
                          SELECT tail.event_seq
                            FROM history_events AS tail
                           WHERE tail.run_id = run.id
                           ORDER BY tail.event_seq DESC LIMIT 1
                      ), 0) AS actual_last_event_seq,
                      COALESCE((
                          SELECT tail.item_order
                            FROM history_events AS tail
                           WHERE tail.run_id = run.id
                             AND tail.item_order IS NOT NULL
                           ORDER BY tail.item_order DESC LIMIT 1
                      ), 0) AS actual_last_item_order
                 FROM history_runs AS run
                WHERE run.run_token = ?""",
            (self._context.run_token,),
        ).fetchone()
        if row is not None:
            _validate_context_snapshot(row)
            _validate_prefix_snapshot(row)
            _validate_physical_watermarks(row)
            if bytes(row["context_hash"]) != self._context_hash:
                raise TokenConflictError("history run token context changed")
            if (
                row["started_at"] is not None
                and self._record.started_at is not None
                and decode_utc(row["started_at"]) != self._record.started_at
            ):
                raise TokenConflictError("history run start changed")
            return int(row["id"])
        context = self._context
        prefix_projection_hash = _prefix_projection_hash(
            self._context_hash,
            _EMPTY_EVENT_CHAIN,
            started_at=self._record.started_at,
            current_state=self._record.state.value,
            current_phase=None,
            last_committed_seq=0,
            item_count=0,
            last_committed_at=None,
            duplicate_item_count=0,
            rejected_event_count=0,
            succeeded_count=0,
            skipped_count=0,
            failed_count=0,
            canceled_count=0,
            deferred_count=0,
            blocked_count=0,
        )
        return int(
            connection.execute(
                """INSERT INTO history_runs(
                       run_token, session_id, activity_kind, host_key,
                       subject_kind, subject_id, source_context, target_context,
                       created_at, started_at, current_state, current_phase,
                       last_committed_seq, item_count, last_committed_at,
                       context_hash, event_chain_hash, prefix_projection_hash
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, 0, NULL,
                             ?, ?, ?) RETURNING id""",
                (
                    context.run_token,
                    str(self._record.session_id),
                    context.activity_kind or self._record.kind,
                    context.host_key,
                    context.subject_kind,
                    context.subject_id,
                    context.source_context,
                    context.target_context,
                    encode_utc(self._record.created_at),
                    (
                        None
                        if self._record.started_at is None
                        else encode_utc(self._record.started_at)
                    ),
                    self._record.state.value,
                    self._context_hash,
                    _EMPTY_EVENT_CHAIN,
                    prefix_projection_hash,
                ),
            ).fetchone()["id"]
        )

    def _append_events(
        self,
        connection: sqlite3.Connection,
        run_id: int,
        pending: tuple[_PendingEvent, ...],
        committed_at: datetime,
    ) -> _AppendResult:
        row = connection.execute(
            """SELECT context_hash, last_committed_seq, item_count,
                      event_chain_hash, prefix_projection_hash,
                      started_at, current_state, current_phase, last_committed_at,
                      terminal_payload_hash, succeeded_count, skipped_count,
                      failed_count, canceled_count, deferred_count, blocked_count,
                      duplicate_item_count, rejected_event_count
                 FROM history_runs WHERE id = ?""",
            (run_id,),
        ).fetchone()
        _validate_prefix_snapshot(row)
        last_seq = int(row["last_committed_seq"])
        item_count = int(row["item_count"])
        chain = bytes(row["event_chain_hash"])
        started_at = _optional_utc(row["started_at"])
        prior_committed_at = _optional_utc(row["last_committed_at"])
        current_state = str(row["current_state"])
        current_phase = row["current_phase"]
        duplicate_item_count = int(row["duplicate_item_count"])
        rejected_event_count = int(row["rejected_event_count"])
        terminal_hash = (
            None
            if row["terminal_payload_hash"] is None
            else bytes(row["terminal_payload_hash"])
        )
        counts = {
            Outcome.SUCCEEDED.value: int(row["succeeded_count"]),
            Outcome.SKIPPED.value: int(row["skipped_count"]),
            Outcome.FAILED.value: int(row["failed_count"]),
            Outcome.CANCELED.value: int(row["canceled_count"]),
            Outcome.DEFERRED.value: int(row["deferred_count"]),
            Outcome.BLOCKED.value: int(row["blocked_count"]),
        }
        inserted = False
        latest_inserted_at: datetime | None = None
        canonical_items = _canonical_items_for_window(
            connection, run_id, last_seq, pending
        )
        for event in pending:
            if event.event_seq <= last_seq:
                prior = connection.execute(
                    """SELECT payload_hash FROM history_events
                        WHERE run_id = ? AND event_seq = ?""",
                    (run_id, event.event_seq),
                ).fetchone()
                if prior is None:
                    raise HistoryIntegrityError(
                        "reliable events arrived out of order"
                    )
                if bytes(prior["payload_hash"]) != event.payload_hash:
                    raise HistoryIntegrityError(
                        "event sequence was reused with another payload"
                    )
                continue
            if terminal_hash is not None:
                raise TokenConflictError("finalized history cannot accept new events")

            envelope = event.envelope
            projection = (
                None if envelope is None else _item_projection(envelope.body)
            )
            item_order = None
            item_identity_hash = event.item_identity_hash
            item_payload_hash = event.item_payload_hash
            duplicate_of_seq = None
            disposition = HistoryEventDisposition.RECORDED
            if item_identity_hash is not None:
                if item_payload_hash is None:
                    raise HistoryIntegrityError(
                        "history item semantic hash is missing"
                    )
                prior_receipt = canonical_items.by_identity_hash.get(
                    item_identity_hash
                )
                if prior_receipt is not None:
                    _, prior_item_hash = prior_receipt
                    if item_payload_hash != prior_item_hash:
                        raise HistoryIntegrityError(
                            "result item identity was reused with another payload"
                        )
            if event.rejection_reason is not None:
                disposition = HistoryEventDisposition.REJECTED
                rejected_event_count += 1
                if item_identity_hash is not None:
                    if prior_receipt is None:
                        canonical_items.by_identity_hash[item_identity_hash] = (
                            event.event_seq,
                            item_payload_hash,
                        )
                    else:
                        duplicate_of_seq, _ = prior_receipt
            elif projection is not None:
                if item_identity_hash is None or item_payload_hash is None:
                    raise HistoryIntegrityError(
                        "history canonical item hashes are missing"
                    )
                identity = (
                    str(projection["item_type"]),
                    str(projection["item_id"]),
                )
                prior_item = canonical_items.by_identity.get(identity)
                if prior_item is None:
                    prior_receipt = canonical_items.by_identity_hash.get(
                        item_identity_hash
                    )
                    if prior_receipt is None:
                        item_count += 1
                        item_order = item_count
                        value = (event.event_seq, item_payload_hash)
                        canonical_items.by_identity[identity] = value
                        canonical_items.by_identity_hash[item_identity_hash] = value
                    else:
                        duplicate_of_seq, _ = prior_receipt
                        disposition = HistoryEventDisposition.DUPLICATE
                        duplicate_item_count += 1
                else:
                    prior_seq, prior_item_hash = prior_item
                    if item_payload_hash != prior_item_hash:
                        raise HistoryIntegrityError(
                            "result item identity was reused with another payload"
                        )
                    disposition = HistoryEventDisposition.DUPLICATE
                    duplicate_of_seq = prior_seq
                    duplicate_item_count += 1
            stored_identity_hash = item_identity_hash
            stored_item_payload_hash = item_payload_hash
            event_at_text = encode_utc(event.event_at)
            receipt_hash = _receipt_hash(
                event_seq=event.event_seq,
                event_at=event_at_text,
                schema_version=event.schema_version,
                body_type=event.body_type,
                disposition=disposition,
                payload_hash=event.payload_hash,
                item_identity_hash=stored_identity_hash,
                item_payload_hash=stored_item_payload_hash,
                duplicate_of_seq=duplicate_of_seq,
                rejection_reason=event.rejection_reason,
                item_order=item_order,
            )
            connection.execute(
                """INSERT INTO history_events(
                       run_id, event_seq, event_at, schema_version, body_type,
                       event_disposition, envelope_json, payload_hash,
                       receipt_hash, item_identity_hash, item_payload_hash,
                       duplicate_of_seq, rejection_reason, item_order,
                       item_type, phase, item_id, kind, path, result, reason,
                       recording, recording_reason, recording_detail,
                       detail_omitted_count
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                             ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    event.event_seq,
                    event_at_text,
                    event.schema_version,
                    event.body_type,
                    disposition.value,
                    event.envelope_json,
                    event.payload_hash,
                    receipt_hash,
                    stored_identity_hash,
                    stored_item_payload_hash,
                    duplicate_of_seq,
                    event.rejection_reason,
                    item_order,
                    None if projection is None else projection["item_type"],
                    None if projection is None else projection["phase"],
                    None if projection is None else projection["item_id"],
                    None if projection is None else projection["kind"],
                    None if projection is None else projection["path"],
                    None if projection is None else projection["result"],
                    None if projection is None else projection["reason"],
                    None if projection is None else projection["recording"],
                    (
                        None
                        if projection is None
                        else projection["recording_reason"]
                    ),
                    (
                        None
                        if projection is None
                        else projection["recording_detail"]
                    ),
                    (
                        None
                        if projection is None
                        else projection["detail_omitted_count"]
                    ),
                ),
            )
            if (
                disposition is HistoryEventDisposition.RECORDED
                and envelope is not None
                and isinstance(envelope.body, ItemOutcome)
            ):
                counts[envelope.body.outcome.value] += 1
            elif envelope is not None and isinstance(envelope.body, StateChanged):
                current_state = envelope.body.state.value
                if (
                    envelope.body.state is SessionState.RUNNING
                    and started_at is None
                ):
                    started_at = event.event_at
            elif envelope is not None and isinstance(envelope.body, PhaseChanged):
                current_phase = envelope.body.phase
            last_seq = event.event_seq
            chain = _advance_event_chain(chain, receipt_hash)
            inserted = True
            latest_inserted_at = max(
                value
                for value in (latest_inserted_at, event.event_at)
                if value is not None
            )

        # Wall time can move backward. This field is a durable watermark, so a
        # logical nondecreasing timestamp is more honest than regressing it or
        # degrading an otherwise valid window. The first commit must also not
        # precede admission or any event made durable in this window.
        effective_committed_at = max(
            value
            for value in (
                committed_at,
                prior_committed_at,
                self._record.created_at,
                started_at,
                latest_inserted_at,
            )
            if value is not None
        )

        prefix_projection_hash = _prefix_projection_hash(
            bytes(row["context_hash"]),
            chain,
            started_at=started_at,
            current_state=current_state,
            current_phase=(
                None if current_phase is None else str(current_phase)
            ),
            last_committed_seq=last_seq,
            item_count=item_count,
            last_committed_at=(
                effective_committed_at if inserted else prior_committed_at
            ),
            duplicate_item_count=duplicate_item_count,
            rejected_event_count=rejected_event_count,
            succeeded_count=counts[Outcome.SUCCEEDED.value],
            skipped_count=counts[Outcome.SKIPPED.value],
            failed_count=counts[Outcome.FAILED.value],
            canceled_count=counts[Outcome.CANCELED.value],
            deferred_count=counts[Outcome.DEFERRED.value],
            blocked_count=counts[Outcome.BLOCKED.value],
        )

        if inserted:
            connection.execute(
                """UPDATE history_runs
                      SET started_at = ?, current_state = ?, current_phase = ?,
                          last_committed_seq = ?, item_count = ?,
                          last_committed_at = ?, event_chain_hash = ?,
                          succeeded_count = ?, skipped_count = ?,
                          failed_count = ?, canceled_count = ?,
                          deferred_count = ?, blocked_count = ?,
                          duplicate_item_count = ?, rejected_event_count = ?,
                          prefix_projection_hash = ?
                    WHERE id = ?""",
                (
                    None if started_at is None else encode_utc(started_at),
                    current_state,
                    current_phase,
                    last_seq,
                    item_count,
                    encode_utc(effective_committed_at),
                    chain,
                    counts[Outcome.SUCCEEDED.value],
                    counts[Outcome.SKIPPED.value],
                    counts[Outcome.FAILED.value],
                    counts[Outcome.CANCELED.value],
                    counts[Outcome.DEFERRED.value],
                    counts[Outcome.BLOCKED.value],
                    duplicate_item_count,
                    rejected_event_count,
                    prefix_projection_hash,
                    run_id,
                ),
            )
        return _AppendResult(
            event_chain_hash=chain,
            prefix_projection_hash=prefix_projection_hash,
            started_at=started_at,
            committed_at=effective_committed_at,
            terminal_payload_hash=terminal_hash,
            duplicate_item_count=duplicate_item_count,
            rejected_event_count=rejected_event_count,
        )

    def _accept_commit(self) -> None:
        """Release the window only after its transaction is durable."""

        self._pending.clear()
        self._event_hashes.clear()
        self._pending_rejections.clear()
        self._pending_bytes = 0

    def close(self) -> None:
        if self._closed:
            return
        try:
            if not self._failed and not self._finalized:
                self.flush()
        finally:
            self._closed = True

    def _require_accepting(self) -> None:
        if self._closed or self._finalized:
            raise HistoryIntegrityError("history observer is not accepting events")
        if self._failed:
            raise HistoryIntegrityError("history observer is degraded")


class HistoryObserverFactory:
    """Composition-root adapter matching the dispatcher's audit factory shape."""

    def __init__(
        self,
        store: HistoryStore,
        context_provider: Callable[[SessionRecord], HistoryContext | None],
    ) -> None:
        self._store = store
        self._context_provider = context_provider

    def __call__(self, record: SessionRecord) -> HistoryObserver | None:
        context = self._context_provider(record)
        if context is None:
            return None
        return self._store.observer(record, context)


class HistoryRepository:
    def __init__(
        self,
        path: str | Path,
        *,
        classification_query: HistoryClassificationQuery = (
            DEFAULT_HISTORY_CLASSIFICATION_QUERY
        ),
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> None:
        self.path = Path(path).resolve()
        if not isinstance(classification_query, HistoryClassificationQuery):
            raise TypeError("classification_query must be HistoryClassificationQuery")
        self._classification_query = classification_query
        require_database_file_contract(self.path, history=True)
        self._connection = connect_history_reader(
            self.path, busy_timeout_ms=busy_timeout_ms
        )
        try:
            validate_history_reader_contract(self._connection)
        except BaseException:
            self._connection.close()
            raise

    def list_summaries(self, limit: int = 50) -> tuple[HistoryRunSummary, ...]:
        _validate_summary_limit(limit)
        self._begin_read()
        try:
            rows = tuple(
                self._connection.execute(
                    """WITH selected AS (
                           SELECT * FROM history_runs
                            ORDER BY COALESCE(started_at, created_at) DESC, id DESC
                            LIMIT ?
                       )
                       SELECT selected.*,
                              COALESCE((
                                  SELECT tail.event_seq
                                    FROM history_events AS tail
                                   WHERE tail.run_id = selected.id
                                   ORDER BY tail.event_seq DESC LIMIT 1
                              ), 0) AS actual_last_event_seq,
                              COALESCE((
                                  SELECT tail.item_order
                                    FROM history_events AS tail
                                   WHERE tail.run_id = selected.id
                                     AND tail.item_order IS NOT NULL
                                   ORDER BY tail.item_order DESC LIMIT 1
                              ), 0) AS actual_last_item_order,
                              CASE WHEN selected.terminal_payload_hash IS NOT NULL
                                   THEN selected.duplicate_item_count
                                   ELSE COALESCE(SUM(CASE
                                       WHEN event.event_disposition = 'duplicate'
                                       THEN 1 ELSE 0 END), 0) END
                                  AS durable_duplicate_item_count,
                              CASE WHEN selected.terminal_payload_hash IS NOT NULL
                                   THEN selected.rejected_event_count
                                   ELSE COALESCE(SUM(CASE
                                       WHEN event.event_disposition = 'rejected'
                                       THEN 1 ELSE 0 END), 0) END
                                  AS durable_rejected_event_count
                         FROM selected
                         LEFT JOIN history_events AS event
                           ON event.run_id = selected.id
                          AND selected.terminal_payload_hash IS NULL
                          AND event.event_seq <= selected.last_committed_seq
                        GROUP BY selected.id
                        ORDER BY COALESCE(selected.started_at, selected.created_at)
                                 DESC, selected.id DESC""",
                    (limit,),
                )
            )
            return self._summaries(rows)
        finally:
            self._end_read()

    def get_summary(self, run_token: str) -> HistoryRunSummary:
        self._begin_read()
        try:
            row = self._connection.execute(
                """SELECT run.*,
                          COALESCE((
                              SELECT tail.event_seq
                                FROM history_events AS tail
                               WHERE tail.run_id = run.id
                               ORDER BY tail.event_seq DESC LIMIT 1
                          ), 0) AS actual_last_event_seq,
                          COALESCE((
                              SELECT tail.item_order
                                FROM history_events AS tail
                               WHERE tail.run_id = run.id
                                 AND tail.item_order IS NOT NULL
                               ORDER BY tail.item_order DESC LIMIT 1
                          ), 0) AS actual_last_item_order,
                          CASE WHEN run.terminal_payload_hash IS NOT NULL
                               THEN run.duplicate_item_count
                               ELSE COALESCE(SUM(CASE
                                   WHEN event.event_disposition = 'duplicate'
                                   THEN 1 ELSE 0 END), 0) END
                              AS durable_duplicate_item_count,
                          CASE WHEN run.terminal_payload_hash IS NOT NULL
                               THEN run.rejected_event_count
                               ELSE COALESCE(SUM(CASE
                                   WHEN event.event_disposition = 'rejected'
                                   THEN 1 ELSE 0 END), 0) END
                              AS durable_rejected_event_count
                     FROM history_runs AS run
                     LEFT JOIN history_events AS event
                       ON event.run_id = run.id
                      AND run.terminal_payload_hash IS NULL
                      AND event.event_seq <= run.last_committed_seq
                    WHERE run.run_token = ?
                    GROUP BY run.id""",
                (run_token,),
            ).fetchone()
            if row is None:
                raise KeyError(run_token)
            return self._summaries((row,))[0]
        finally:
            self._end_read()

    def get_item_page(
        self,
        run_token: str,
        *,
        after_order: int = 0,
        through_order: int | None = None,
        limit: int = MAX_HISTORY_PAGE_SIZE,
    ) -> HistoryItemPage:
        _validate_page_arguments(after_order, through_order, limit, "item")
        self._begin_read()
        try:
            run = self._connection.execute(
                """SELECT run.*,
                          COALESCE((
                              SELECT tail.event_seq
                                FROM history_events AS tail
                               WHERE tail.run_id = run.id
                               ORDER BY tail.event_seq DESC LIMIT 1
                          ), 0) AS actual_last_event_seq,
                          COALESCE((
                              SELECT tail.item_order
                                FROM history_events AS tail
                               WHERE tail.run_id = run.id
                                 AND tail.item_order IS NOT NULL
                               ORDER BY tail.item_order DESC LIMIT 1
                          ), 0) AS actual_last_item_order
                     FROM history_runs AS run
                    WHERE run.run_token = ?""",
                (run_token,),
            ).fetchone()
            if run is None:
                raise KeyError(run_token)
            _validate_context_snapshot(run)
            _validate_prefix_snapshot(run)
            _validate_physical_watermarks(run)
            session_id = str(run["session_id"])
            durable = int(run["item_count"])
            through = durable if through_order is None else through_order
            _validate_watermark(after_order, through, durable, "item")
            rows = tuple(
                self._connection.execute(
                    """SELECT * FROM history_events
                        WHERE run_id = ? AND item_order > ? AND item_order <= ?
                        ORDER BY item_order LIMIT ?""",
                    (run["id"], after_order, through, limit),
                )
            )
            items = tuple(_history_item(row, session_id) for row in rows)
            next_after = after_order if not items else items[-1].item_order
            has_more = _dense_page_has_more(
                len(items), limit, next_after, through, "item"
            )
            return HistoryItemPage(
                run_token=run_token,
                through_order=through,
                items=items,
                next_after_order=next_after,
                has_more=has_more,
            )
        finally:
            self._end_read()

    def get_event_page(
        self,
        run_token: str,
        *,
        after_seq: int = 0,
        through_seq: int | None = None,
        limit: int = MAX_HISTORY_PAGE_SIZE,
    ) -> HistoryEventPage:
        _validate_page_arguments(after_seq, through_seq, limit, "event")
        self._begin_read()
        try:
            run = self._connection.execute(
                """SELECT run.*,
                          COALESCE((
                              SELECT tail.event_seq
                                FROM history_events AS tail
                               WHERE tail.run_id = run.id
                               ORDER BY tail.event_seq DESC LIMIT 1
                          ), 0) AS actual_last_event_seq,
                          COALESCE((
                              SELECT tail.item_order
                                FROM history_events AS tail
                               WHERE tail.run_id = run.id
                                 AND tail.item_order IS NOT NULL
                               ORDER BY tail.item_order DESC LIMIT 1
                          ), 0) AS actual_last_item_order
                     FROM history_runs AS run
                    WHERE run.run_token = ?""",
                (run_token,),
            ).fetchone()
            if run is None:
                raise KeyError(run_token)
            _validate_context_snapshot(run)
            _validate_prefix_snapshot(run)
            _validate_physical_watermarks(run)
            session_id = str(run["session_id"])
            durable = int(run["last_committed_seq"])
            through = durable if through_seq is None else through_seq
            if through_seq is None and after_seq > durable:
                return HistoryEventPage(
                    run_token=run_token,
                    session_id=session_id,
                    through_seq=durable,
                    events=(),
                    next_after_seq=after_seq,
                    has_more=False,
                )
            _validate_watermark(after_seq, through, durable, "event")
            rows = tuple(
                self._connection.execute(
                    """SELECT event.*,
                              canonical.event_disposition
                                  AS canonical_disposition,
                              canonical.event_seq AS canonical_event_seq,
                              canonical.event_at AS canonical_event_at,
                              canonical.schema_version
                                  AS canonical_schema_version,
                              canonical.body_type AS canonical_body_type,
                              canonical.payload_hash AS canonical_payload_hash,
                              canonical.receipt_hash AS canonical_receipt_hash,
                              canonical.duplicate_of_seq
                                  AS canonical_duplicate_of_seq,
                              canonical.rejection_reason
                                  AS canonical_rejection_reason,
                              canonical.item_order AS canonical_item_order,
                              canonical.item_type AS canonical_item_type,
                              canonical.item_id AS canonical_item_id,
                              canonical.item_identity_hash
                                  AS canonical_item_identity_hash,
                              canonical.item_payload_hash
                                  AS canonical_item_payload_hash
                         FROM history_events AS event
                         LEFT JOIN history_events AS canonical
                           ON canonical.run_id = event.run_id
                          AND canonical.event_seq = event.duplicate_of_seq
                        WHERE event.run_id = ? AND event.event_seq > ?
                          AND event.event_seq <= ?
                        ORDER BY event.event_seq LIMIT ?""",
                    (run["id"], after_seq, through, limit + 1),
                )
            )
            events = tuple(
                _history_event_with_duplicate_link(row, session_id)
                for row in rows[:limit]
            )
            next_after = after_seq if not events else events[-1].event_seq
            return HistoryEventPage(
                run_token=run_token,
                session_id=session_id,
                through_seq=through,
                events=events,
                next_after_seq=next_after,
                has_more=len(rows) > limit,
            )
        finally:
            self._end_read()

    def _summaries(
        self, rows: tuple[sqlite3.Row, ...]
    ) -> tuple[HistoryRunSummary, ...]:
        if not rows:
            return ()
        run_ids = tuple(int(row["id"]) for row in rows)
        placeholders = ",".join("?" for _ in run_ids)
        phases = _load_phase_snapshots(self._connection, run_ids)
        aggregates = self._classification_aggregates(run_ids, placeholders)
        return tuple(
            _history_summary(
                row,
                tuple(phases[int(row["id"])]),
                aggregates[int(row["id"])],
                (
                    int(row["durable_duplicate_item_count"]),
                    int(row["durable_rejected_event_count"]),
                ),
            )
            for row in rows
        )

    def _classification_aggregates(
        self, run_ids: tuple[int, ...], placeholders: str
    ) -> dict[int, _ClassificationCounts]:
        query = self._classification_query
        reasons = query.excluded_operation_reasons
        reason_predicate = ""
        if reasons:
            reason_placeholders = ",".join("?" for _ in reasons)
            reason_predicate = (
                " AND (event.reason IS NULL OR event.reason NOT IN "
                f"({reason_placeholders}))"
            )
        selected = f"event.item_type = 'operation'{reason_predicate}"
        integrity_results = tuple(result.value for result in IntegrityResult)
        integrity_columns = ",\n".join(
            f"SUM(CASE WHEN event.item_type = 'integrity' AND event.result = ? "
            f"THEN 1 ELSE 0 END) AS integrity_{index}"
            for index, _ in enumerate(integrity_results)
        )
        rows = self._connection.execute(
            f"""SELECT event.run_id,
                       SUM(CASE WHEN {selected} THEN 1 ELSE 0 END)
                           AS selected_operation_count,
                       SUM(CASE WHEN {selected} AND event.kind <> ? THEN 1 ELSE 0 END)
                           AS selected_other_operation_count,
                       {integrity_columns},
                       SUM(CASE WHEN event.item_type = 'integrity'
                                     AND event.phase = ? AND event.result = ?
                                THEN 1 ELSE 0 END) AS verify_phase_baseline_count
                  FROM history_events AS event
                       INDEXED BY history_events_run_item_aggregate_idx
                  JOIN history_runs AS run ON run.id = event.run_id
                 WHERE event.run_id IN ({placeholders})
                   AND event.item_order IS NOT NULL
                   AND event.event_seq <= run.last_committed_seq
                   AND event.item_order <= run.item_count
                 GROUP BY event.run_id""",
            (
                *reasons,
                *reasons,
                query.noop_operation_kind,
                *integrity_results,
                IntegrityMode.VERIFY.value,
                IntegrityResult.BASELINED.value,
                *run_ids,
            ),
        )
        by_run = {
            run_id: _empty_classification_aggregate() for run_id in run_ids
        }
        for row in rows:
            run_id = int(row["run_id"])
            selected_count = _history_safe_int(
                row["selected_operation_count"],
                "history selected operation count",
            )
            selected_other_count = _history_safe_int(
                row["selected_other_operation_count"],
                "history selected other operation count",
            )
            if not 0 <= selected_other_count <= selected_count:
                raise HistoryIntegrityError(
                    "history selected-operation aggregate is inconsistent"
                )
            by_run[run_id] = _ClassificationCounts(
                selected_operation_count=selected_count,
                selected_other_operation_count=selected_other_count,
                integrity_results=frozenset(
                    result
                    for index, result in enumerate(integrity_results)
                    if int(row[f"integrity_{index}"]) > 0
                ),
                verify_phase_baseline=(
                    int(row["verify_phase_baseline_count"]) > 0
                ),
            )
        return by_run

    def _begin_read(self) -> None:
        self._connection.execute("BEGIN")

    def _end_read(self) -> None:
        if self._connection.in_transaction:
            self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> HistoryRepository:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def _item_identity_hash(item: ResultItem) -> bytes:
    return _hash(
        {
            "item_type": item.item_type,
            "item_id": item.item_id,
        }
    )


def _item_projection(body: object) -> dict[str, object] | None:
    if not isinstance(body, ResultItem):
        return None
    data = result_item_to_dict(body)
    return {
        "item_type": str(data["item_type"]),
        "phase": str(data["phase"]),
        "item_id": str(data["item_id"]),
        "kind": str(data["kind"]),
        "path": str(data["path"]),
        "result": str(data["result"]),
        "reason": None if data["reason"] is None else str(data["reason"]),
        "recording": str(data["recording"]),
        "recording_reason": (
            None
            if data.get("recording_reason") is None
            else str(data["recording_reason"])
        ),
        "recording_detail": (
            None
            if data.get("recording_detail") is None
            else str(data["recording_detail"])
        ),
        "detail_omitted_count": int(data["detail_omitted_count"]),
    }


def _canonical_items_for_window(
    connection: sqlite3.Connection,
    run_id: int,
    through_seq: int,
    pending: tuple[_PendingEvent, ...],
) -> _CanonicalItemIndex:
    identity_hashes = tuple(
        dict.fromkeys(
            event.item_identity_hash
            for event in pending
            if event.item_identity_hash is not None
        )
    )
    by_identity: dict[tuple[str, str], tuple[int, bytes]] = {}
    by_identity_hash: dict[bytes, tuple[int, bytes]] = {}
    for offset in range(0, len(identity_hashes), 400):
        chunk = identity_hashes[offset : offset + 400]
        requested = ",".join("?" for _ in chunk)
        for row in connection.execute(
            f"""SELECT event_seq AS first_seq,
                       event_disposition AS first_disposition,
                       item_order AS first_item_order,
                       item_type AS first_item_type,
                       item_id AS first_item_id,
                       item_identity_hash,
                       item_payload_hash AS first_item_payload_hash
                  FROM history_events
                       INDEXED BY history_events_run_identity_hash_idx
                 WHERE run_id = ?
                   AND item_identity_hash IN ({requested})
                   AND (
                       event_disposition = 'recorded'
                       OR (
                           event_disposition = 'rejected'
                           AND duplicate_of_seq IS NULL
                       )
                   )
                   AND event_seq <= ?""",
            (run_id, *chunk, through_seq),
        ):
            first_seq = int(row["first_seq"])
            stored_identity_hash = bytes(row["item_identity_hash"])
            item_hash = row["first_item_payload_hash"]
            if item_hash is None:
                raise HistoryIntegrityError(
                    "history canonical item hashes are missing"
                )
            value = (first_seq, bytes(item_hash))
            by_identity_hash[stored_identity_hash] = value
            try:
                disposition = HistoryEventDisposition(
                    str(row["first_disposition"])
                )
            except ValueError as error:
                raise HistoryIntegrityError(
                    "history item receipt disposition is invalid"
                ) from error
            if disposition is HistoryEventDisposition.RECORDED:
                if row["first_item_order"] is None:
                    raise HistoryIntegrityError(
                        "history canonical item order is missing"
                    )
                identity = (
                    str(row["first_item_type"]),
                    str(row["first_item_id"]),
                )
                if stored_identity_hash != _hash(
                    {"item_type": identity[0], "item_id": identity[1]}
                ):
                    raise HistoryIntegrityError(
                        "history canonical item identity hash disagrees"
                    )
                if identity in by_identity:
                    raise HistoryIntegrityError(
                        "history contains repeated canonical item identities"
                    )
                by_identity[identity] = value
            elif disposition is not HistoryEventDisposition.REJECTED:
                raise HistoryIntegrityError(
                    "history item representative disposition is invalid"
                )
    return _CanonicalItemIndex(by_identity, by_identity_hash)


def _load_phase_snapshots(
    connection: sqlite3.Connection,
    run_ids: tuple[int, ...],
) -> dict[int, list[HistoryPhaseSnapshot]]:
    phases: dict[int, list[HistoryPhaseSnapshot]] = {
        run_id: [] for run_id in run_ids
    }
    if not run_ids:
        return phases
    placeholders = ",".join("?" for _ in run_ids)
    for row in connection.execute(
        f"""SELECT * FROM history_phases
             WHERE run_id IN ({placeholders})
             ORDER BY run_id, phase_order""",
        run_ids,
    ):
        run_id = int(row["run_id"])
        snapshots = phases[run_id]
        if len(snapshots) >= MAX_HISTORY_PHASES:
            raise HistoryIntegrityError("history terminal phase count exceeds bound")
        snapshots.append(
            HistoryPhaseSnapshot(
                phase_order=int(row["phase_order"]),
                phase=_history_phase_from_columns(row),
            )
        )
    return phases


def _validated_receipt(row: sqlite3.Row) -> _ValidatedReceipt:
    try:
        disposition = HistoryEventDisposition(str(row["event_disposition"]))
        event_seq = int(row["event_seq"])
        event_at_text = str(row["event_at"])
        event_at = decode_utc(event_at_text)
        schema_version = int(row["schema_version"])
        body_type = str(row["body_type"])
        payload_hash = bytes(row["payload_hash"])
        receipt_hash = bytes(row["receipt_hash"])
        item_identity_hash = (
            None
            if row["item_identity_hash"] is None
            else bytes(row["item_identity_hash"])
        )
        item_payload_hash = (
            None
            if row["item_payload_hash"] is None
            else bytes(row["item_payload_hash"])
        )
        duplicate_of_seq = (
            None
            if row["duplicate_of_seq"] is None
            else int(row["duplicate_of_seq"])
        )
        rejection_reason = (
            None
            if row["rejection_reason"] is None
            else str(row["rejection_reason"])
        )
        item_order = (
            None if row["item_order"] is None else int(row["item_order"])
        )
    except (TypeError, ValueError) as error:
        raise HistoryIntegrityError(
            "history event receipt metadata is invalid"
        ) from error
    try:
        _history_safe_int(event_seq, "history event sequence")
        if event_seq < 1:
            raise ValueError("history event sequence must be positive")
        if duplicate_of_seq is not None:
            _history_safe_int(
                duplicate_of_seq,
                "history duplicate sequence",
            )
            if duplicate_of_seq < 1:
                raise ValueError("history duplicate sequence must be positive")
        if item_order is not None:
            _history_safe_int(item_order, "history item order")
            if item_order < 1:
                raise ValueError("history item order must be positive")
        if schema_version != CORE_EVENT_SCHEMA_VERSION:
            raise ValueError("history event schema version is unsupported")
        if body_type not in _HISTORY_BODY_TYPES:
            raise ValueError("history event body type is unsupported")
    except (TypeError, ValueError) as error:
        raise HistoryIntegrityError(
            "history event receipt counters are invalid"
        ) from error
    expected_receipt_hash = _receipt_hash(
        event_seq=event_seq,
        event_at=event_at_text,
        schema_version=schema_version,
        body_type=body_type,
        disposition=disposition,
        payload_hash=payload_hash,
        item_identity_hash=item_identity_hash,
        item_payload_hash=item_payload_hash,
        duplicate_of_seq=duplicate_of_seq,
        rejection_reason=rejection_reason,
        item_order=item_order,
    )
    if receipt_hash != expected_receipt_hash:
        raise HistoryIntegrityError("history event receipt hash disagrees")
    return _ValidatedReceipt(
        event_seq=event_seq,
        event_at_text=event_at_text,
        event_at=event_at,
        schema_version=schema_version,
        body_type=body_type,
        disposition=disposition,
        payload_hash=payload_hash,
        receipt_hash=receipt_hash,
        item_identity_hash=item_identity_hash,
        item_payload_hash=item_payload_hash,
        duplicate_of_seq=duplicate_of_seq,
        rejection_reason=rejection_reason,
        item_order=item_order,
    )


def _history_event_with_duplicate_link(
    row: sqlite3.Row,
    expected_session_id: str,
) -> HistoryEventSnapshot:
    disposition = HistoryEventDisposition(str(row["event_disposition"]))
    linked_rejected = (
        disposition is HistoryEventDisposition.REJECTED
        and row["duplicate_of_seq"] is not None
    )
    if disposition is HistoryEventDisposition.DUPLICATE or linked_rejected:
        canonical = _validated_receipt(
            {
                "event_seq": row["canonical_event_seq"],
                "event_at": row["canonical_event_at"],
                "schema_version": row["canonical_schema_version"],
                "body_type": row["canonical_body_type"],
                "event_disposition": row["canonical_disposition"],
                "payload_hash": row["canonical_payload_hash"],
                "receipt_hash": row["canonical_receipt_hash"],
                "item_identity_hash": row["canonical_item_identity_hash"],
                "item_payload_hash": row["canonical_item_payload_hash"],
                "duplicate_of_seq": row["canonical_duplicate_of_seq"],
                "rejection_reason": row["canonical_rejection_reason"],
                "item_order": row["canonical_item_order"],
            }
        )
        recorded_link = (
            canonical.disposition is HistoryEventDisposition.RECORDED
            and canonical.item_order is not None
            and canonical.duplicate_of_seq is None
            and canonical.rejection_reason is None
            and (
                linked_rejected
                or (
                    str(row["canonical_item_type"]) == str(row["item_type"])
                    and str(row["canonical_item_id"]) == str(row["item_id"])
                )
            )
        )
        rejected_link = (
            canonical.disposition is HistoryEventDisposition.REJECTED
            and canonical.item_order is None
            and canonical.duplicate_of_seq is None
            and canonical.rejection_reason == EVENT_TOO_LARGE
        )
        if (
            not (recorded_link or rejected_link)
            or canonical.item_identity_hash is None
            or canonical.item_identity_hash
            != bytes(row["item_identity_hash"])
            or canonical.item_payload_hash is None
            or canonical.item_payload_hash
            != bytes(row["item_payload_hash"])
        ):
            raise HistoryIntegrityError(
                "history duplicate receipt link disagrees with canonical item"
            )
    return _history_event(row, expected_session_id)


def _history_event(
    row: sqlite3.Row,
    expected_session_id: str,
) -> HistoryEventSnapshot:
    receipt = _validated_receipt(row)
    disposition = receipt.disposition
    payload_hash = receipt.payload_hash
    item_identity_hash = receipt.item_identity_hash
    item_payload_hash = receipt.item_payload_hash
    duplicate_of_seq = receipt.duplicate_of_seq
    rejection_reason = receipt.rejection_reason
    receipt_hash = receipt.receipt_hash
    event_seq = receipt.event_seq
    event_at = receipt.event_at
    body_type = receipt.body_type
    if disposition is HistoryEventDisposition.REJECTED:
        if row["envelope_json"] is not None:
            raise HistoryIntegrityError(
                "history rejected receipt retained an envelope"
            )
        if rejection_reason != EVENT_TOO_LARGE:
            raise HistoryIntegrityError(
                "history rejected receipt reason is invalid"
            )
        return HistoryEventSnapshot(
            event_seq=event_seq,
            event_at=event_at,
            schema_version=receipt.schema_version,
            body_type=body_type,
            disposition=disposition,
            envelope=None,
            payload_hash=payload_hash,
            receipt_hash=receipt_hash,
            duplicate_of_seq=duplicate_of_seq,
            rejection_reason=rejection_reason,
        )

    if row["envelope_json"] is None:
        raise HistoryIntegrityError("history event envelope is missing")
    envelope_text = str(row["envelope_json"])
    if hashlib.sha256(envelope_text.encode("utf-8")).digest() != payload_hash:
        raise HistoryIntegrityError("history event payload hash disagrees")
    try:
        raw = json.loads(
            envelope_text,
            object_pairs_hook=_unique_json_object,
        )
    except (TypeError, ValueError) as error:
        raise HistoryIntegrityError("history event payload is invalid JSON") from error
    if not isinstance(raw, Mapping):
        raise HistoryIntegrityError("history event payload must be an object")
    try:
        envelope = envelope_from_dict(raw)
    except (KeyError, TypeError, ValueError) as error:
        raise HistoryIntegrityError("history event payload is invalid") from error
    if (
        str(envelope.session_id) != expected_session_id
        or envelope.seq != event_seq
        or envelope.schema_version != receipt.schema_version
        or type(envelope.body).__name__ != str(row["body_type"])
        or envelope.at != event_at
    ):
        raise HistoryIntegrityError("history event columns disagree with payload")
    projection = _item_projection(envelope.body)
    expected = (
        {
            "item_type": row["item_type"],
            "phase": row["phase"],
            "item_id": row["item_id"],
            "kind": row["kind"],
            "path": row["path"],
            "result": row["result"],
            "reason": row["reason"],
            "recording": row["recording"],
            "recording_reason": row["recording_reason"],
            "recording_detail": row["recording_detail"],
            "detail_omitted_count": row["detail_omitted_count"],
        }
        if row["item_type"] is not None
        else None
    )
    if projection != expected:
        raise HistoryIntegrityError("history item columns disagree with payload")
    expected_item_hash = (
        None
        if not isinstance(envelope.body, ResultItem)
        else _hash(result_item_to_dict(envelope.body))
    )
    if item_payload_hash != expected_item_hash:
        raise HistoryIntegrityError("history item payload hash disagrees")
    expected_identity_hash = (
        None
        if not isinstance(envelope.body, ResultItem)
        else _item_identity_hash(envelope.body)
    )
    if item_identity_hash != expected_identity_hash:
        raise HistoryIntegrityError("history item identity hash disagrees")
    if disposition is HistoryEventDisposition.RECORDED:
        if (projection is None) != (row["item_order"] is None):
            raise HistoryIntegrityError(
                "history canonical item order disagrees with payload"
            )
        if duplicate_of_seq is not None or rejection_reason is not None:
            raise HistoryIntegrityError("history recorded receipt metadata disagrees")
    else:
        if (
            disposition is not HistoryEventDisposition.DUPLICATE
            or projection is None
            or row["item_order"] is not None
            or duplicate_of_seq is None
            or duplicate_of_seq >= event_seq
            or rejection_reason is not None
        ):
            raise HistoryIntegrityError("history duplicate receipt metadata disagrees")
    return HistoryEventSnapshot(
        event_seq=event_seq,
        event_at=event_at,
        schema_version=receipt.schema_version,
        body_type=body_type,
        disposition=disposition,
        envelope=envelope,
        payload_hash=payload_hash,
        receipt_hash=receipt_hash,
        duplicate_of_seq=duplicate_of_seq,
    )


def _history_item(
    row: sqlite3.Row,
    expected_session_id: str,
) -> HistoryItemSnapshot:
    event = _history_event(row, expected_session_id)
    if event.envelope is None or not isinstance(event.envelope.body, ResultItem):
        raise HistoryIntegrityError("history item row does not contain a result item")
    if row["item_order"] is None:
        raise HistoryIntegrityError("history item order is missing")
    item_order = _history_safe_int(
        row["item_order"],
        "history item order",
    )
    return HistoryItemSnapshot(
        item_order=item_order,
        event_seq=event.event_seq,
        item=event.envelope.body,
    )


def _history_summary(
    row: sqlite3.Row,
    phases: tuple[HistoryPhaseSnapshot, ...],
    aggregate: _ClassificationCounts,
    receipt_counts: tuple[int, int],
) -> HistoryRunSummary:
    finalized = row["terminal_payload_hash"] is not None
    _validate_terminal_snapshot(row, phases)
    _validate_physical_watermarks(row)
    if receipt_counts != (
        int(row["duplicate_item_count"]),
        int(row["rejected_event_count"]),
    ):
        raise HistoryIntegrityError(
            "history receipt counts disagree with durable rows"
        )
    return HistoryRunSummary(
        run_token=str(row["run_token"]),
        session_id=str(row["session_id"]),
        activity_kind=str(row["activity_kind"]),
        host_key=str(row["host_key"]),
        subject_kind=(
            None if row["subject_kind"] is None else str(row["subject_kind"])
        ),
        subject_id=None if row["subject_id"] is None else str(row["subject_id"]),
        source_context=(
            None
            if row["source_context"] is None
            else str(row["source_context"])
        ),
        target_context=(
            None
            if row["target_context"] is None
            else str(row["target_context"])
        ),
        created_at=decode_utc(row["created_at"]),
        started_at=_optional_utc(row["started_at"]),
        ended_at=_optional_utc(row["ended_at"]),
        current_state=SessionState(str(row["current_state"])),
        current_phase=(
            None if row["current_phase"] is None else str(row["current_phase"])
        ),
        last_committed_seq=int(row["last_committed_seq"]),
        item_count=int(row["item_count"]),
        duplicate_item_count=int(row["duplicate_item_count"]),
        rejected_event_count=int(row["rejected_event_count"]),
        last_committed_at=_optional_utc(row["last_committed_at"]),
        finalized=finalized,
        filesystem_status=(
            None
            if row["filesystem_status"] is None
            else SessionState(str(row["filesystem_status"]))
        ),
        recording=(
            None
            if row["recording_status"] is None
            else RecordingStatus(str(row["recording_status"]))
        ),
        audit=(
            None
            if row["audit_status"] is None
            else RecordingStatus(str(row["audit_status"]))
        ),
        disposition=(
            None if row["disposition"] is None else str(row["disposition"])
        ),
        canceled=None if row["canceled"] is None else bool(row["canceled"]),
        bytes_done=None if row["bytes_done"] is None else int(row["bytes_done"]),
        bytes_total=(
            None if row["bytes_total"] is None else int(row["bytes_total"])
        ),
        recording_degraded_items=(
            None
            if row["recording_degraded_items"] is None
            else int(row["recording_degraded_items"])
        ),
        recording_issues=(
            ()
            if row["recording_issues_json"] is None
            else _recording_issues_from_json(row["recording_issues_json"])
        ),
        omitted_detail_count=(
            None
            if row["omitted_detail_count"] is None
            else int(row["omitted_detail_count"])
        ),
        review_fact_limit=_review_fact_from_row(row),
        succeeded_count=int(row["succeeded_count"]),
        skipped_count=int(row["skipped_count"]),
        failed_count=int(row["failed_count"]),
        canceled_count=int(row["canceled_count"]),
        deferred_count=int(row["deferred_count"]),
        blocked_count=int(row["blocked_count"]),
        phases=phases,
        classification=HistoryClassificationAggregate(
            operation_results=_operation_results(row),
            selected_operation_count=aggregate.selected_operation_count,
            selected_other_operation_count=(
                aggregate.selected_other_operation_count
            ),
            integrity_results=aggregate.integrity_results,
            verify_phase_baseline=aggregate.verify_phase_baseline,
        ),
        error_type=None if row["error_type"] is None else str(row["error_type"]),
        error_message=(
            None if row["error_message"] is None else str(row["error_message"])
        ),
    )


def _operation_results(row: sqlite3.Row) -> frozenset[str]:
    counts = {
        Outcome.SUCCEEDED.value: int(row["succeeded_count"]),
        Outcome.SKIPPED.value: int(row["skipped_count"]),
        Outcome.FAILED.value: int(row["failed_count"]),
        Outcome.CANCELED.value: int(row["canceled_count"]),
        Outcome.DEFERRED.value: int(row["deferred_count"]),
        Outcome.BLOCKED.value: int(row["blocked_count"]),
    }
    return frozenset(result for result, count in counts.items() if count > 0)


def _empty_classification_aggregate() -> _ClassificationCounts:
    return _ClassificationCounts(0, 0, frozenset(), False)


def _phase_to_dict(phase: PhaseResult) -> dict[str, object]:
    return {
        "phase": phase.phase,
        "status": phase.status.value,
        "items_done": phase.items_done,
        "items_total": phase.items_total,
        "bytes_done": phase.bytes_done,
        "bytes_total": phase.bytes_total,
        "error": phase.error,
    }


def _validate_terminal_snapshot(
    row: sqlite3.Row,
    phases: tuple[HistoryPhaseSnapshot, ...],
) -> None:
    _validate_context_snapshot(row)
    _validate_prefix_snapshot(row)
    stored_hash = row["terminal_payload_hash"]
    if stored_hash is None:
        if phases:
            raise HistoryIntegrityError(
                "incomplete history contains terminal phase summaries"
            )
        return
    if len(phases) > MAX_HISTORY_PHASES or any(
        snapshot.phase_order != order
        for order, snapshot in enumerate(phases)
    ):
        raise HistoryIntegrityError("history terminal phase ordering is invalid")
    try:
        error_type = row["error_type"]
        error_message = row["error_message"]
        if (error_type is None) != (error_message is None):
            raise HistoryIntegrityError("history terminal error columns disagree")
        error = None
        if error_type is not None:
            error = FailureDetail(
                _validate_bounded_text(
                    error_type,
                    MAX_HISTORY_ERROR_TYPE_BYTES,
                    "terminal error type",
                ),
                _validate_bounded_text(
                    error_message,
                    MAX_HISTORY_ERROR_MESSAGE_BYTES,
                    "terminal error message",
                ),
            )
        canceled = int(row["canceled"])
        if canceled not in (0, 1):
            raise HistoryIntegrityError("history terminal canceled flag is invalid")
        result = TerminalSummary(
            status=SessionState(str(row["filesystem_status"])),
            recording=RecordingStatus(str(row["recording_status"])),
            audit=RecordingStatus(str(row["audit_status"])),
            disposition=Disposition(str(row["disposition"])),
            canceled=bool(canceled),
            phases=tuple(snapshot.phase for snapshot in phases),
            bytes_done=int(row["bytes_done"]),
            bytes_total=int(row["bytes_total"]),
            error=error,
            recording_degraded_items=int(row["recording_degraded_items"]),
            recording_issues=_recording_issues_from_json(
                row["recording_issues_json"]
            ),
            omitted_detail_count=int(row["omitted_detail_count"]),
            review_fact_limit=_review_fact_from_row(row),
        )
        if (
            int(row["rejected_event_count"]) > 0
            and result.audit is not RecordingStatus.DEGRADED
        ):
            raise HistoryIntegrityError(
                "history rejected receipts require degraded audit status"
            )
        _validate_terminal_text(result)
        terminal_state = (
            SessionState.CANCELED if result.canceled else result.status
        )
        if terminal_state is not SessionState(str(row["current_state"])):
            raise HistoryIntegrityError(
                "history terminal lifecycle disagrees with its result"
            )
        expected_hash = _terminal_payload_hash(
            bytes(row["context_hash"]),
            bytes(row["prefix_projection_hash"]),
            decode_utc(row["ended_at"]),
            result,
        )
        if expected_hash != bytes(stored_hash):
            raise HistoryIntegrityError(
                "history terminal payload hash disagrees with stored summary"
            )
    except HistoryIntegrityError:
        raise
    except (TypeError, ValueError) as error:
        raise HistoryIntegrityError(
            "history terminal summary is invalid"
        ) from error


def _prefix_projection_hash_from_row(
    row: sqlite3.Row,
    *,
    current_state: str | None = None,
) -> bytes:
    return _prefix_projection_hash(
        bytes(row["context_hash"]),
        bytes(row["event_chain_hash"]),
        started_at=_optional_utc(row["started_at"]),
        current_state=(
            str(row["current_state"])
            if current_state is None
            else current_state
        ),
        current_phase=(
            None if row["current_phase"] is None else str(row["current_phase"])
        ),
        last_committed_seq=int(row["last_committed_seq"]),
        item_count=int(row["item_count"]),
        last_committed_at=_optional_utc(row["last_committed_at"]),
        duplicate_item_count=int(row["duplicate_item_count"]),
        rejected_event_count=int(row["rejected_event_count"]),
        succeeded_count=int(row["succeeded_count"]),
        skipped_count=int(row["skipped_count"]),
        failed_count=int(row["failed_count"]),
        canceled_count=int(row["canceled_count"]),
        deferred_count=int(row["deferred_count"]),
        blocked_count=int(row["blocked_count"]),
    )


def _validate_prefix_snapshot(row: sqlite3.Row) -> None:
    try:
        for column in (
            "last_committed_seq",
            "item_count",
            "duplicate_item_count",
            "rejected_event_count",
            "succeeded_count",
            "skipped_count",
            "failed_count",
            "canceled_count",
            "deferred_count",
            "blocked_count",
        ):
            _history_safe_int(
                row[column],
                f"history {column}",
            )
        expected_hash = _prefix_projection_hash_from_row(row)
        if expected_hash != bytes(row["prefix_projection_hash"]):
            raise HistoryIntegrityError(
                "history prefix projection hash disagrees with stored summary"
            )
    except HistoryIntegrityError:
        raise
    except (TypeError, ValueError) as error:
        raise HistoryIntegrityError(
            "history prefix projection is invalid"
        ) from error


def _validate_physical_watermarks(row: sqlite3.Row) -> None:
    try:
        if (
            int(row["actual_last_event_seq"])
            != int(row["last_committed_seq"])
            or int(row["actual_last_item_order"]) != int(row["item_count"])
        ):
            raise HistoryIntegrityError(
                "history event watermark and item watermark disagree "
                "with durable rows"
            )
    except HistoryIntegrityError:
        raise
    except (IndexError, TypeError, ValueError) as error:
        raise HistoryIntegrityError(
            "history durable watermarks are invalid"
        ) from error


def _validate_context_snapshot(row: sqlite3.Row) -> None:
    try:
        payload = {
            "run_token": str(row["run_token"]),
            "session_id": str(row["session_id"]),
            "activity_kind": str(row["activity_kind"]),
            "host_key": str(row["host_key"]),
            "subject_kind": (
                None
                if row["subject_kind"] is None
                else str(row["subject_kind"])
            ),
            "subject_id": (
                None if row["subject_id"] is None else str(row["subject_id"])
            ),
            "source_context": (
                None
                if row["source_context"] is None
                else str(row["source_context"])
            ),
            "target_context": (
                None
                if row["target_context"] is None
                else str(row["target_context"])
            ),
            "created_at": decode_utc(row["created_at"]),
        }
        if _hash(payload) != bytes(row["context_hash"]):
            raise HistoryIntegrityError(
                "history context hash disagrees with stored context"
            )
    except HistoryIntegrityError:
        raise
    except (TypeError, ValueError) as error:
        raise HistoryIntegrityError("history stored context is invalid") from error


def _history_phase_from_columns(row: sqlite3.Row) -> PhaseResult:
    return PhaseResult(
        phase=_validate_bounded_text(
            row["phase"],
            MAX_HISTORY_PHASE_NAME_BYTES,
            "terminal phase name",
        ),
        status=PhaseStatus(str(row["status"])),
        items_done=int(row["items_done"]),
        items_total=(
            None if row["items_total"] is None else int(row["items_total"])
        ),
        bytes_done=int(row["bytes_done"]),
        bytes_total=(
            None if row["bytes_total"] is None else int(row["bytes_total"])
        ),
        error=(
            None
            if row["error"] is None
            else _validate_bounded_text(
                row["error"],
                MAX_HISTORY_ERROR_MESSAGE_BYTES,
                "terminal phase error",
            )
        ),
    )


def _optional_utc(value: object) -> datetime | None:
    return None if value is None else decode_utc(str(value))


def _validate_summary_limit(limit: int) -> None:
    if type(limit) is not int or not 1 <= limit <= MAX_HISTORY_PAGE_SIZE:
        raise ValueError(
            f"history summary limit must be between 1 and {MAX_HISTORY_PAGE_SIZE}"
        )


def _validate_page_arguments(
    after: int, through: int | None, limit: int, kind: str
) -> None:
    require_safe_int(after, f"history {kind} cursor")
    if through is not None:
        require_safe_int(through, f"history {kind} watermark")
    if type(limit) is not int or not 1 <= limit <= MAX_HISTORY_PAGE_SIZE:
        raise ValueError(
            f"history {kind} page limit must be between 1 and "
            f"{MAX_HISTORY_PAGE_SIZE}"
        )


def _validate_watermark(after: int, through: int, durable: int, kind: str) -> None:
    if through > durable:
        raise ValueError(f"history {kind} watermark exceeds durable history")
    if after > through:
        raise ValueError(f"history {kind} cursor exceeds its fixed watermark")


def _dense_page_has_more(
    row_count: int, limit: int, next_after: int, through: int, kind: str
) -> bool:
    if next_after >= through:
        return False
    if row_count < limit:
        raise HistoryIntegrityError(
            f"history {kind} watermark has no matching durable row"
        )
    return True
