"""Independent M0 sync history store and dispatcher-facing observer."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
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
    result_item_from_dict,
    result_item_to_dict,
)
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.session import (
    OperationResult,
    ResultItem,
    SessionRecord,
    SessionState,
)

from .connections import (
    DEFAULT_BUSY_TIMEOUT_MS,
    connect_history_reader,
    connect_history_writer,
)
from .schema import validate_history_reader_contract
from .schema import initialize_history
from .timestamps import decode_utc, encode_utc
from .writer import RecordingError, SerializedWriter, TokenConflictError


class Clock(Protocol):
    def now(self) -> datetime: ...


class HistoryIntegrityError(RecordingError):
    """The reliable event stream was duplicated or reordered inconsistently."""


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
    event_seq: int | None
    item: ResultItem


@dataclass(frozen=True, slots=True)
class HistoryRunSnapshot:
    run_token: str
    session_id: str
    activity_kind: str
    host_key: str
    subject_kind: str | None
    subject_id: str | None
    source_context: str | None
    target_context: str | None
    started_at: datetime
    ended_at: datetime
    filesystem_status: SessionState
    recording: RecordingStatus
    audit: RecordingStatus
    disposition: str
    canceled: bool
    bytes_done: int
    bytes_total: int
    items: tuple[HistoryItemSnapshot, ...]
    error_type: str | None
    error_message: str | None


def _primitive(value: object) -> object:
    if isinstance(value, bytes):
        return {"$bytes": value.hex()}
    if isinstance(value, datetime):
        return encode_utc(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: _primitive(getattr(value, field.name)) for field in fields(value)}
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


def _json_text(value: object) -> str:
    return _json_bytes(value).decode("utf-8")


def _hash(value: object) -> bytes:
    return hashlib.sha256(_json_bytes(value)).digest()


class HistoryStore:
    def __init__(
        self,
        path: str | Path,
        *,
        clock: Clock,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        retry_timeout_seconds: float = 10.0,
        retry_interval_seconds: float = 0.025,
        managed_roots: tuple[str | Path, ...] = (),
    ) -> None:
        self.path = initialize_history(
            path,
            busy_timeout_ms=busy_timeout_ms,
            managed_roots=managed_roots,
        )
        self._clock = clock
        self._writer = SerializedWriter(
            self.path,
            connect_history_writer,
            busy_timeout_ms=busy_timeout_ms,
            retry_timeout_seconds=retry_timeout_seconds,
            retry_interval_seconds=retry_interval_seconds,
        )

    def observer(
        self, record: SessionRecord, context: HistoryContext
    ) -> HistoryObserver:
        return HistoryObserver(self, record, context)

    def close(self) -> None:
        self._writer.close()

    def __enter__(self) -> HistoryStore:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


class HistoryObserver:
    """Consumes reliable preterminal envelopes and acknowledges final storage."""

    def __init__(
        self, store: HistoryStore, record: SessionRecord, context: HistoryContext
    ) -> None:
        self._store = store
        self._record = record
        self._context = context
        self._event_hashes: dict[int, bytes] = {}
        self._items: list[tuple[int, ResultItem]] = []
        self._running_at: datetime | None = record.started_at
        self._closed = False
        self._finalized = False
        self._final_payload_hash: bytes | None = None

    def on_event(self, envelope: Envelope) -> None:
        if self._closed or self._finalized:
            raise HistoryIntegrityError("history observer is not accepting events")
        if str(envelope.session_id) != str(self._record.session_id):
            raise HistoryIntegrityError("event belongs to another session")
        if isinstance(envelope.body, (Terminal, Progress)):
            raise HistoryIntegrityError("history receives reliable preterminal events only")
        digest = _hash(envelope)
        prior = self._event_hashes.get(envelope.seq)
        if prior is not None:
            if prior != digest:
                raise HistoryIntegrityError("event sequence was reused with another payload")
            return
        if self._event_hashes and envelope.seq < max(self._event_hashes):
            raise HistoryIntegrityError("reliable events arrived out of order")
        self._event_hashes[envelope.seq] = digest
        if (
            isinstance(envelope.body, StateChanged)
            and envelope.body.state is SessionState.RUNNING
            and self._running_at is None
        ):
            self._running_at = envelope.at
        if isinstance(envelope.body, ResultItem):
            self._items.append((envelope.seq, envelope.body))
        elif not isinstance(envelope.body, (StateChanged, PhaseChanged, Gap)):
            raise HistoryIntegrityError(
                f"unsupported reliable event body: {type(envelope.body).__name__}"
            )

    def finalize(self, result: OperationResult) -> None:
        if self._closed:
            raise HistoryIntegrityError("history observer is closed")
        started_at = self._running_at or self._record.created_at
        context = self._context
        payload_hash = _hash(
            {
                "run_token": context.run_token,
                "session_id": str(self._record.session_id),
                "activity_kind": context.activity_kind or self._record.kind,
                "host_key": context.host_key,
                "subject_kind": context.subject_kind,
                "subject_id": context.subject_id,
                "source_context": context.source_context,
                "target_context": context.target_context,
                "started_at": started_at,
                "result": result,
                "items": self._items,
            }
        )
        if self._finalized:
            if payload_hash != self._final_payload_hash:
                raise TokenConflictError("history finalize payload changed")
            return
        ended_at = self._store._clock.now()
        if ended_at < started_at:
            raise RecordingError("history end precedes actual start")

        def apply(connection: sqlite3.Connection) -> None:
            prior = connection.execute(
                "SELECT payload_hash FROM history_runs WHERE run_token = ?",
                (context.run_token,),
            ).fetchone()
            if prior is not None:
                if bytes(prior["payload_hash"]) != payload_hash:
                    raise TokenConflictError("history run token payload changed")
                return
            counts = Counter(
                item.outcome
                for _, item in self._items
                if isinstance(item, ItemOutcome)
            )
            run_id = int(
                connection.execute(
                    """INSERT INTO history_runs(
                           run_token, session_id, activity_kind, host_key,
                           subject_kind, subject_id, source_context, target_context,
                           started_at, ended_at, filesystem_status,
                           recording_status, audit_status, disposition, canceled,
                           bytes_done, bytes_total, succeeded_count, skipped_count,
                           failed_count, canceled_count, deferred_count, blocked_count,
                           error_type, error_message, payload_hash
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                 ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
                    (
                        context.run_token,
                        str(self._record.session_id),
                        context.activity_kind or self._record.kind,
                        context.host_key,
                        context.subject_kind,
                        context.subject_id,
                        context.source_context,
                        context.target_context,
                        encode_utc(started_at),
                        encode_utc(ended_at),
                        result.status.value,
                        result.recording.value,
                        RecordingStatus.OK.value,
                        result.disposition.value,
                        int(result.canceled),
                        result.bytes_done,
                        result.bytes_total,
                        counts[Outcome.SUCCEEDED],
                        counts[Outcome.SKIPPED],
                        counts[Outcome.FAILED],
                        counts[Outcome.CANCELED],
                        counts[Outcome.DEFERRED],
                        counts[Outcome.BLOCKED],
                        None if result.error is None else result.error.type_name,
                        None if result.error is None else result.error.message,
                        payload_hash,
                    ),
                ).fetchone()["id"]
            )
            connection.executemany(
                """INSERT INTO history_items(
                       run_id, item_order, event_seq, item_type, phase,
                       item_id, kind, path, result, reason, detail_json
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    (
                        run_id,
                        order,
                        seq,
                        item.item_type,
                        item.phase,
                        item.item_id,
                        (
                            item.kind
                            if isinstance(item, ItemOutcome)
                            else item.item_type
                        ),
                        item.path,
                        (
                            item.outcome.value
                            if isinstance(item, ItemOutcome)
                            else item.result.value
                        ),
                        (
                            item.reason
                            if isinstance(item, ItemOutcome)
                            else None if item.reason is None else item.reason.value
                        ),
                        _json_text(result_item_to_dict(item)),
                    )
                    for order, (seq, item) in enumerate(self._items)
                ),
            )

        self._store._writer.transact(apply)
        self._final_payload_hash = payload_hash
        self._finalized = True

    def close(self) -> None:
        self._closed = True


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
        self, path: str | Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
    ) -> None:
        self.path = Path(path).resolve()
        self._connection = connect_history_reader(
            self.path, busy_timeout_ms=busy_timeout_ms
        )
        try:
            validate_history_reader_contract(self._connection)
        except BaseException:
            self._connection.close()
            raise

    def get(self, run_token: str) -> HistoryRunSnapshot:
        row = self._connection.execute(
            "SELECT * FROM history_runs WHERE run_token = ?", (run_token,)
        ).fetchone()
        if row is None:
            raise KeyError(run_token)
        items = tuple(
            HistoryItemSnapshot(
                item_order=int(item["item_order"]),
                event_seq=None if item["event_seq"] is None else int(item["event_seq"]),
                item=_history_item(item),
            )
            for item in self._connection.execute(
                """SELECT * FROM history_items
                    WHERE run_id = ?
                    ORDER BY item_order""",
                (row["id"],),
            )
        )
        return HistoryRunSnapshot(
            run_token=row["run_token"],
            session_id=row["session_id"],
            activity_kind=row["activity_kind"],
            host_key=row["host_key"],
            subject_kind=row["subject_kind"],
            subject_id=row["subject_id"],
            source_context=row["source_context"],
            target_context=row["target_context"],
            started_at=decode_utc(row["started_at"]),
            ended_at=decode_utc(row["ended_at"]),
            filesystem_status=SessionState(row["filesystem_status"]),
            recording=RecordingStatus(row["recording_status"]),
            audit=RecordingStatus(row["audit_status"]),
            disposition=row["disposition"],
            canceled=bool(row["canceled"]),
            bytes_done=int(row["bytes_done"]),
            bytes_total=int(row["bytes_total"]),
            items=items,
            error_type=row["error_type"],
            error_message=row["error_message"],
        )

    def list_recent(self, limit: int = 50) -> tuple[HistoryRunSnapshot, ...]:
        if limit < 0:
            raise ValueError("history limit cannot be negative")
        tokens = [
            row[0]
            for row in self._connection.execute(
                "SELECT run_token FROM history_runs ORDER BY started_at DESC, id DESC LIMIT ?",
                (limit,),
            )
        ]
        return tuple(self.get(token) for token in tokens)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> HistoryRepository:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def _history_item(row: sqlite3.Row) -> ResultItem:
    raw = json.loads(row["detail_json"])
    if not isinstance(raw, Mapping):
        raise HistoryIntegrityError("history item payload must be an object")
    item = result_item_from_dict(raw)
    data = result_item_to_dict(item)
    expected = {
        "item_type": row["item_type"],
        "phase": row["phase"],
        "item_id": row["item_id"],
        "kind": row["kind"],
        "path": row["path"],
        "result": row["result"],
        "reason": row["reason"],
    }
    actual = {
        "item_type": data["item_type"],
        "phase": data["phase"],
        "item_id": data["item_id"],
        "kind": data["kind"],
        "path": data["path"],
        "result": data["result"],
        "reason": data["reason"],
    }
    if actual != expected:
        raise HistoryIntegrityError("history item columns disagree with payload")
    return item
