"""Bounded, incrementally durable sync history and readback."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping, Protocol

from namisync.core.events import (
    Envelope,
    Gap,
    ItemOutcome,
    PhaseChanged,
    Progress,
    StateChanged,
    Terminal,
    envelope_from_dict,
    envelope_to_dict,
    result_item_to_dict,
)
from namisync.core.evidence import Outcome, RecordingStatus
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

from .connections import (
    DEFAULT_BUSY_TIMEOUT_MS,
    connect_history_reader,
    connect_history_writer,
)
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
MAX_HISTORY_PHASES = 256
_EMPTY_EVENT_CHAIN = hashlib.sha256(b"").digest()


class Clock(Protocol):
    def now(self) -> datetime: ...


class HistoryIntegrityError(RecordingError):
    """The reliable event stream was duplicated or reordered inconsistently."""


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
        if not self.run_token or not self.host_key:
            raise ValueError("history run token and host key are required")


@dataclass(frozen=True, slots=True)
class HistoryItemSnapshot:
    item_order: int
    event_seq: int
    item: ResultItem


@dataclass(frozen=True, slots=True)
class HistoryEventSnapshot:
    event_seq: int
    envelope: Envelope
    payload_hash: bytes


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
    last_committed_at: datetime | None
    finalized: bool
    filesystem_status: SessionState | None
    recording: RecordingStatus | None
    audit: RecordingStatus | None
    disposition: str | None
    canceled: bool | None
    bytes_done: int | None
    bytes_total: int | None
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
    ).encode("utf-8", errors="backslashreplace")


def _hash(value: object) -> bytes:
    return hashlib.sha256(_json_bytes(value)).digest()


def _advance_event_chain(chain: bytes, payload_hash: bytes) -> bytes:
    return hashlib.sha256(chain + payload_hash).digest()


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


def _terminal_result_payload(result: OperationResult) -> dict[str, object]:
    return {
        "status": result.status.value,
        "recording": result.recording.value,
        "audit": result.audit.value,
        "disposition": result.disposition.value,
        "canceled": result.canceled,
        "phases": [_phase_to_dict(phase) for phase in result.phases],
        "bytes_done": result.bytes_done,
        "bytes_total": result.bytes_total,
        "error": (
            None
            if result.error is None
            else {
                "type_name": result.error.type_name,
                "message": result.error.message,
            }
        ),
    }


def _terminal_payload_hash(
    context_hash: bytes, event_chain_hash: bytes, result: OperationResult
) -> bytes:
    return _hash(
        {
            "context_hash": context_hash,
            "event_chain_hash": event_chain_hash,
            "result": _terminal_result_payload(result),
        }
    )


def _validate_terminal_text(result: OperationResult) -> None:
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
    if len(value.encode("utf-8", errors="backslashreplace")) > maximum:
        raise HistoryIntegrityError(f"{field} exceeds its UTF-8 byte bound")
    return value


@dataclass(frozen=True, slots=True)
class _ExistingRun:
    context_hash: bytes
    last_committed_seq: int
    event_chain_hash: bytes
    terminal_payload_hash: bytes | None


@dataclass(frozen=True, slots=True)
class _PendingEvent:
    envelope: Envelope
    envelope_json: str
    encoded_size: int
    payload_hash: bytes


@dataclass(frozen=True, slots=True)
class _AppendResult:
    event_chain_hash: bytes
    started_at: datetime | None
    committed_at: datetime
    terminal_payload_hash: bytes | None


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
                row = connection.execute(
                    """SELECT context_hash, last_committed_seq,
                              event_chain_hash, terminal_payload_hash
                         FROM history_runs WHERE run_token = ?""",
                    (run_token,),
                ).fetchone()
            finally:
                connection.close()
        except sqlite3.Error as error:
            raise RecordingError(str(error)) from error
        if row is None:
            return None
        return _ExistingRun(
            context_hash=bytes(row["context_hash"]),
            last_committed_seq=int(row["last_committed_seq"]),
            event_chain_hash=bytes(row["event_chain_hash"]),
            terminal_payload_hash=(
                None
                if row["terminal_payload_hash"] is None
                else bytes(row["terminal_payload_hash"])
            ),
        )

    def _load_event_hash(self, run_token: str, event_seq: int) -> bytes | None:
        try:
            connection = connect_history_reader(
                self.path, busy_timeout_ms=self._busy_timeout_ms
            )
            try:
                row = connection.execute(
                    """SELECT event.payload_hash
                         FROM history_events AS event
                         JOIN history_runs AS run ON run.id = event.run_id
                        WHERE run.run_token = ? AND event.event_seq = ?""",
                    (run_token, event_seq),
                ).fetchone()
            finally:
                connection.close()
        except sqlite3.Error as error:
            raise RecordingError(str(error)) from error
        return None if row is None else bytes(row["payload_hash"])

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
        self._event_chain_hash = (
            _EMPTY_EVENT_CHAIN if existing is None else existing.event_chain_hash
        )
        self._existing_terminal_hash = (
            None if existing is None else existing.terminal_payload_hash
        )
        self._pending: list[_PendingEvent] = []
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

    def on_event(self, envelope: Envelope) -> None:
        self._require_accepting()
        try:
            self._admit(envelope)
        except BaseException:
            self._failed = True
            raise

    def _admit(self, envelope: Envelope) -> None:
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

        encoded = _json_bytes(envelope_to_dict(envelope))
        encoded_size = len(encoded)
        if encoded_size > self._policy.max_event_bytes:
            raise HistoryIntegrityError(
                "reliable history event exceeds the per-event byte bound"
            )
        digest = hashlib.sha256(encoded).digest()
        prior = self._event_hashes.get(envelope.seq)
        if prior is not None:
            if prior != digest:
                raise HistoryIntegrityError(
                    "event sequence was reused with another payload"
                )
            return
        if (
            self._highest_event_seq is not None
            and envelope.seq <= self._highest_event_seq
        ):
            durable = self._store._load_event_hash(
                self._context.run_token, envelope.seq
            )
            if durable is None:
                raise HistoryIntegrityError("reliable events arrived out of order")
            if durable != digest:
                raise HistoryIntegrityError(
                    "event sequence was reused with another payload"
                )
            return
        if self._existing_terminal_hash is not None:
            raise HistoryIntegrityError("finalized history cannot accept new events")

        if self._pending and (
            len(self._pending) + 1 > self._policy.max_events
            or self._pending_bytes + encoded_size > self._policy.max_bytes
        ):
            self.flush()

        pending = _PendingEvent(
            envelope=envelope,
            envelope_json=encoded.decode("utf-8"),
            encoded_size=encoded_size,
            payload_hash=digest,
        )
        self._pending.append(pending)
        self._pending_bytes += encoded_size
        self._event_hashes[envelope.seq] = digest
        self._highest_event_seq = envelope.seq
        if (
            len(self._pending) >= self._policy.max_events
            or self._pending_bytes >= self._policy.max_bytes
            or (
                isinstance(envelope.body, StateChanged)
                and envelope.body.state is SessionState.PAUSED
            )
        ):
            self.flush()

    def flush(self) -> None:
        """Commit the current window once; repeated empty flushes are no-ops."""

        if self._closed or self._finalized:
            return
        if self._failed:
            raise HistoryIntegrityError("history observer is degraded")
        if not self._pending:
            return
        try:
            result, _ = self._commit_window(None)
        except BaseException:
            self._failed = True
            raise
        self._accept_commit(result)

    def finalize(self, result: OperationResult) -> None:
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
            _validate_terminal_text(result)
        except BaseException:
            self._failed = True
            raise
        try:
            append, payload_hash = self._commit_window(result)
        except BaseException:
            self._failed = True
            raise
        self._accept_commit(append)
        self._existing_terminal_hash = payload_hash
        self._finalized = True

    def _commit_window(
        self, result: OperationResult | None
    ) -> tuple[_AppendResult, bytes | None]:
        pending = tuple(self._pending)

        def apply(
            connection: sqlite3.Connection,
        ) -> tuple[_AppendResult, bytes | None]:
            # Sample only after SerializedWriter owns BEGIN IMMEDIATE. Sampling
            # before writer admission lets a later transaction carry an older
            # timestamp than the watermark it advances.
            sampled_at = self._store._clock.now()
            run_id = self._ensure_run(connection)
            append = self._append_events(
                connection, run_id, pending, sampled_at
            )
            if result is None:
                return append, None
            payload_hash = _terminal_payload_hash(
                self._context_hash, append.event_chain_hash, result
            )
            if append.terminal_payload_hash is not None:
                stored_row = connection.execute(
                    "SELECT * FROM history_runs WHERE id = ?", (run_id,)
                ).fetchone()
                stored_phases = _load_phase_snapshots(connection, (run_id,))[run_id]
                _validate_terminal_snapshot(
                    stored_row,
                    tuple(stored_phases),
                )
                if append.terminal_payload_hash != payload_hash:
                    raise TokenConflictError("history run token payload changed")
                return append, payload_hash
            ended_at = append.committed_at
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
                    for order, phase in enumerate(result.phases)
                ),
            )
            connection.execute(
                """UPDATE history_runs
                      SET started_at = ?, ended_at = ?, current_state = ?,
                          filesystem_status = ?, recording_status = ?,
                          audit_status = ?, disposition = ?, canceled = ?,
                          bytes_done = ?, bytes_total = ?, error_type = ?,
                          error_message = ?, terminal_payload_hash = ?
                    WHERE id = ?""",
                (
                    None if started_at is None else encode_utc(started_at),
                    encode_utc(ended_at),
                    result_terminal_state(result).value,
                    result.status.value,
                    result.recording.value,
                    result.audit.value,
                    result.disposition.value,
                    int(result.canceled),
                    result.bytes_done,
                    result.bytes_total,
                    None if result.error is None else result.error.type_name,
                    None if result.error is None else result.error.message,
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
                ),
                payload_hash,
            )

        return self._store._writer.transact(apply)

    def _ensure_run(self, connection: sqlite3.Connection) -> int:
        row = connection.execute(
            "SELECT * FROM history_runs WHERE run_token = ?",
            (self._context.run_token,),
        ).fetchone()
        if row is not None:
            _validate_context_snapshot(row)
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
        return int(
            connection.execute(
                """INSERT INTO history_runs(
                       run_token, session_id, activity_kind, host_key,
                       subject_kind, subject_id, source_context, target_context,
                       created_at, started_at, current_state, current_phase,
                       last_committed_seq, item_count, last_committed_at,
                       context_hash, event_chain_hash
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, 0, NULL,
                             ?, ?) RETURNING id""",
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
            """SELECT last_committed_seq, item_count, event_chain_hash,
                      started_at, current_state, current_phase, last_committed_at,
                      terminal_payload_hash, succeeded_count, skipped_count,
                      failed_count, canceled_count, deferred_count, blocked_count
                 FROM history_runs WHERE id = ?""",
            (run_id,),
        ).fetchone()
        last_seq = int(row["last_committed_seq"])
        item_count = int(row["item_count"])
        chain = bytes(row["event_chain_hash"])
        started_at = _optional_utc(row["started_at"])
        prior_committed_at = _optional_utc(row["last_committed_at"])
        current_state = str(row["current_state"])
        current_phase = row["current_phase"]
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
        for event in pending:
            envelope = event.envelope
            if envelope.seq <= last_seq:
                prior = connection.execute(
                    """SELECT payload_hash FROM history_events
                        WHERE run_id = ? AND event_seq = ?""",
                    (run_id, envelope.seq),
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

            projection = _item_projection(envelope.body)
            item_order = None
            if projection is not None:
                item_count += 1
                item_order = item_count
            connection.execute(
                """INSERT INTO history_events(
                       run_id, event_seq, event_at, schema_version, body_type,
                       envelope_json, payload_hash, item_order, item_type, phase,
                       item_id, kind, path, result, reason
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    envelope.seq,
                    encode_utc(envelope.at),
                    envelope.schema_version,
                    type(envelope.body).__name__,
                    event.envelope_json,
                    event.payload_hash,
                    item_order,
                    None if projection is None else projection["item_type"],
                    None if projection is None else projection["phase"],
                    None if projection is None else projection["item_id"],
                    None if projection is None else projection["kind"],
                    None if projection is None else projection["path"],
                    None if projection is None else projection["result"],
                    None if projection is None else projection["reason"],
                ),
            )
            if isinstance(envelope.body, ItemOutcome):
                counts[envelope.body.outcome.value] += 1
            elif isinstance(envelope.body, StateChanged):
                current_state = envelope.body.state.value
                if (
                    envelope.body.state is SessionState.RUNNING
                    and started_at is None
                ):
                    started_at = envelope.at
            elif isinstance(envelope.body, PhaseChanged):
                current_phase = envelope.body.phase
            last_seq = envelope.seq
            chain = _advance_event_chain(chain, event.payload_hash)
            inserted = True
            latest_inserted_at = max(
                value
                for value in (latest_inserted_at, envelope.at)
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

        if inserted:
            connection.execute(
                """UPDATE history_runs
                      SET started_at = ?, current_state = ?, current_phase = ?,
                          last_committed_seq = ?, item_count = ?,
                          last_committed_at = ?, event_chain_hash = ?,
                          succeeded_count = ?, skipped_count = ?,
                          failed_count = ?, canceled_count = ?,
                          deferred_count = ?, blocked_count = ?
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
                    run_id,
                ),
            )
        return _AppendResult(
            event_chain_hash=chain,
            started_at=started_at,
            committed_at=effective_committed_at,
            terminal_payload_hash=terminal_hash,
        )

    def _accept_commit(self, result: _AppendResult) -> None:
        self._pending.clear()
        self._event_hashes.clear()
        self._pending_bytes = 0
        self._event_chain_hash = result.event_chain_hash

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
                    """SELECT * FROM history_runs
                        ORDER BY COALESCE(started_at, created_at) DESC, id DESC
                        LIMIT ?""",
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
                "SELECT * FROM history_runs WHERE run_token = ?", (run_token,)
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
                "SELECT id, item_count FROM history_runs WHERE run_token = ?",
                (run_token,),
            ).fetchone()
            if run is None:
                raise KeyError(run_token)
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
            items = tuple(_history_item(row) for row in rows)
            next_after = after_order if not items else items[-1].item_order
            has_more = _page_has_more(
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
                """SELECT id, last_committed_seq FROM history_runs
                    WHERE run_token = ?""",
                (run_token,),
            ).fetchone()
            if run is None:
                raise KeyError(run_token)
            durable = int(run["last_committed_seq"])
            through = durable if through_seq is None else through_seq
            _validate_watermark(after_seq, through, durable, "event")
            rows = tuple(
                self._connection.execute(
                    """SELECT * FROM history_events
                        WHERE run_id = ? AND event_seq > ? AND event_seq <= ?
                        ORDER BY event_seq LIMIT ?""",
                    (run["id"], after_seq, through, limit),
                )
            )
            events = tuple(_history_event(row) for row in rows)
            next_after = after_seq if not events else events[-1].event_seq
            has_more = _page_has_more(
                len(events), limit, next_after, through, "event"
            )
            return HistoryEventPage(
                run_token=run_token,
                through_seq=through,
                events=events,
                next_after_seq=next_after,
                has_more=has_more,
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
                f" AND (reason IS NULL OR reason NOT IN ({reason_placeholders}))"
            )
        selected = f"item_type = 'operation'{reason_predicate}"
        integrity_results = tuple(result.value for result in IntegrityResult)
        integrity_columns = ",\n".join(
            f"SUM(CASE WHEN item_type = 'integrity' AND result = ? "
            f"THEN 1 ELSE 0 END) AS integrity_{index}"
            for index, _ in enumerate(integrity_results)
        )
        rows = self._connection.execute(
            f"""SELECT run_id,
                       SUM(CASE WHEN {selected} THEN 1 ELSE 0 END)
                           AS selected_operation_count,
                       SUM(CASE WHEN {selected} AND kind <> ? THEN 1 ELSE 0 END)
                           AS selected_other_operation_count,
                       {integrity_columns},
                       SUM(CASE WHEN item_type = 'integrity'
                                     AND phase = ? AND result = ?
                                THEN 1 ELSE 0 END) AS verify_phase_baseline_count
                  FROM history_events
                       INDEXED BY history_events_run_item_aggregate_idx
                 WHERE run_id IN ({placeholders}) AND item_order IS NOT NULL
                 GROUP BY run_id""",
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
            selected_count = int(row["selected_operation_count"])
            selected_other_count = int(row["selected_other_operation_count"])
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
    }


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


def _history_event(row: sqlite3.Row) -> HistoryEventSnapshot:
    envelope_text = str(row["envelope_json"])
    payload_hash = hashlib.sha256(envelope_text.encode("utf-8")).digest()
    if payload_hash != bytes(row["payload_hash"]):
        raise HistoryIntegrityError("history event payload hash disagrees")
    try:
        raw = json.loads(envelope_text)
    except (TypeError, ValueError) as error:
        raise HistoryIntegrityError("history event payload is invalid JSON") from error
    if not isinstance(raw, Mapping):
        raise HistoryIntegrityError("history event payload must be an object")
    try:
        envelope = envelope_from_dict(raw)
    except (KeyError, TypeError, ValueError) as error:
        raise HistoryIntegrityError("history event payload is invalid") from error
    if (
        envelope.seq != int(row["event_seq"])
        or envelope.schema_version != int(row["schema_version"])
        or type(envelope.body).__name__ != str(row["body_type"])
        or envelope.at != decode_utc(row["event_at"])
    ):
        raise HistoryIntegrityError("history event columns disagree with payload")
    projection = _item_projection(envelope.body)
    expected = (
        None
        if row["item_order"] is None
        else {
            "item_type": row["item_type"],
            "phase": row["phase"],
            "item_id": row["item_id"],
            "kind": row["kind"],
            "path": row["path"],
            "result": row["result"],
            "reason": row["reason"],
        }
    )
    if projection != expected:
        raise HistoryIntegrityError("history item columns disagree with payload")
    return HistoryEventSnapshot(envelope.seq, envelope, payload_hash)


def _history_item(row: sqlite3.Row) -> HistoryItemSnapshot:
    event = _history_event(row)
    if not isinstance(event.envelope.body, ResultItem):
        raise HistoryIntegrityError("history item row does not contain a result item")
    if row["item_order"] is None:
        raise HistoryIntegrityError("history item order is missing")
    return HistoryItemSnapshot(
        item_order=int(row["item_order"]),
        event_seq=event.event_seq,
        item=event.envelope.body,
    )


def _history_summary(
    row: sqlite3.Row,
    phases: tuple[HistoryPhaseSnapshot, ...],
    aggregate: _ClassificationCounts,
) -> HistoryRunSummary:
    finalized = row["terminal_payload_hash"] is not None
    _validate_terminal_snapshot(row, phases)
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
        result = OperationResult(
            status=SessionState(str(row["filesystem_status"])),
            recording=RecordingStatus(str(row["recording_status"])),
            audit=RecordingStatus(str(row["audit_status"])),
            disposition=Disposition(str(row["disposition"])),
            canceled=bool(canceled),
            phases=tuple(snapshot.phase for snapshot in phases),
            bytes_done=int(row["bytes_done"]),
            bytes_total=int(row["bytes_total"]),
            error=error,
        )
        _validate_terminal_text(result)
        if result_terminal_state(result) is not SessionState(
            str(row["current_state"])
        ):
            raise HistoryIntegrityError(
                "history terminal lifecycle disagrees with its result"
            )
        expected_hash = _terminal_payload_hash(
            bytes(row["context_hash"]),
            bytes(row["event_chain_hash"]),
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
    if type(after) is not int or after < 0:
        raise ValueError(f"history {kind} cursor must be a non-negative integer")
    if through is not None and (type(through) is not int or through < 0):
        raise ValueError(f"history {kind} watermark must be a non-negative integer")
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


def _page_has_more(
    row_count: int, limit: int, next_after: int, through: int, kind: str
) -> bool:
    if next_after >= through:
        return False
    if row_count < limit:
        raise HistoryIntegrityError(
            f"history {kind} watermark has no matching durable row"
        )
    return True
