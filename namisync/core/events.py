"""Versioned event bodies and envelopes for generic sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import ClassVar, Mapping

from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityOutcome,
    IntegrityReason,
    IntegrityResult,
    ReadStrategy,
    RecordDisposition,
)
from namisync.core.session import ResultItem

SCHEMA_VERSION = 3


class DeliveryClass(StrEnum):
    LOSSY = "lossy"
    RELIABLE = "reliable"


@dataclass(frozen=True, slots=True)
class StateChanged:
    state: "SessionState"


@dataclass(frozen=True, slots=True)
class PhaseChanged:
    phase: str


@dataclass(frozen=True, slots=True)
class Progress:
    items_done: int
    items_total: int | None
    bytes_done: int
    bytes_total: int | None
    current_path: str | None

    def __post_init__(self) -> None:
        values = (self.items_done, self.bytes_done)
        totals = (self.items_total, self.bytes_total)
        if any(value < 0 for value in values):
            raise ValueError("progress counters cannot be negative")
        if any(value is not None and value < 0 for value in totals):
            raise ValueError("progress totals cannot be negative")
        if self.items_total is not None and self.items_done > self.items_total:
            raise ValueError("items_done cannot exceed items_total")
        if self.bytes_total is not None and self.bytes_done > self.bytes_total:
            raise ValueError("bytes_done cannot exceed bytes_total")


@dataclass(frozen=True, slots=True)
class ItemOutcome(ResultItem):
    item_type: ClassVar[str] = "operation"
    phase: ClassVar[str] = "execute"

    item_id: str
    kind: str
    path: str
    outcome: Outcome
    reason: str | None = None
    detail: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.item_id or not self.kind:
            raise ValueError("item_id and kind must be non-empty")


@dataclass(frozen=True, slots=True)
class Gap:
    first_missed_seq: int

    def __post_init__(self) -> None:
        if self.first_missed_seq < 1:
            raise ValueError("first_missed_seq must be positive")


@dataclass(frozen=True, slots=True)
class Terminal:
    result: "OperationResult"


EventBody = (
    StateChanged
    | PhaseChanged
    | Progress
    | ItemOutcome
    | IntegrityOutcome
    | Gap
    | Terminal
)


@dataclass(frozen=True, slots=True)
class Envelope:
    session_id: "SessionId"
    seq: int
    at: datetime
    schema_version: int
    body: object

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("session_id must be non-empty")
        if self.seq < 1:
            raise ValueError("event sequence must be positive")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported event schema version: {self.schema_version}")
        if self.at.tzinfo is None or self.at.utcoffset() is None:
            raise ValueError("event timestamp must be timezone-aware")
        if self.at.utcoffset() != timezone.utc.utcoffset(self.at):
            raise ValueError("event timestamp must be UTC")


def delivery_class(body: object) -> DeliveryClass:
    return DeliveryClass.LOSSY if isinstance(body, Progress) else DeliveryClass.RELIABLE


def envelope_to_dict(envelope: Envelope) -> dict[str, object]:
    """Serialize M0 core event bodies without interpreting domain details."""

    from namisync.core.session import OperationResult

    body = envelope.body
    if isinstance(body, StateChanged):
        body_data: dict[str, object] = {"state": body.state.value}
    elif isinstance(body, PhaseChanged):
        body_data = {"phase": body.phase}
    elif isinstance(body, Progress):
        body_data = {
            "items_done": body.items_done,
            "items_total": body.items_total,
            "bytes_done": body.bytes_done,
            "bytes_total": body.bytes_total,
            "current_path": body.current_path,
        }
    elif isinstance(body, ResultItem):
        body_data = result_item_to_dict(body)
    elif isinstance(body, Gap):
        body_data = {"first_missed_seq": body.first_missed_seq}
    elif isinstance(body, Terminal):
        body_data = {"result": _result_to_dict(body.result)}
    else:
        raise TypeError(f"unsupported event body: {type(body).__name__}")
    if isinstance(body, Terminal) and not isinstance(body.result, OperationResult):
        raise TypeError("Terminal result must be OperationResult")
    return {
        "session_id": str(envelope.session_id),
        "seq": envelope.seq,
        "at": envelope.at.isoformat(),
        "schema_version": envelope.schema_version,
        "body_type": type(body).__name__,
        "body": body_data,
    }


def envelope_from_dict(data: Mapping[str, object]) -> Envelope:
    """Deserialize an M0 envelope and reject unknown schema/body versions."""

    from namisync.core.session import (
        Disposition,
        FailureDetail,
        OperationResult,
        SessionId,
        SessionState,
    )

    version = int(data["schema_version"])
    if version != SCHEMA_VERSION:
        raise ValueError(f"unsupported event schema version: {version}")
    body_type = str(data["body_type"])
    raw = data["body"]
    if not isinstance(raw, Mapping):
        raise TypeError("event body must be a mapping")
    if body_type == "StateChanged":
        body: object = StateChanged(SessionState(str(raw["state"])))
    elif body_type == "PhaseChanged":
        body = PhaseChanged(str(raw["phase"]))
    elif body_type == "Progress":
        body = Progress(
            items_done=int(raw["items_done"]),
            items_total=_optional_int(raw["items_total"]),
            bytes_done=int(raw["bytes_done"]),
            bytes_total=_optional_int(raw["bytes_total"]),
            current_path=_optional_str(raw["current_path"]),
        )
    elif body_type in {"ItemOutcome", "IntegrityOutcome"}:
        body = result_item_from_dict(raw)
        if type(body).__name__ != body_type:
            raise ValueError("event body type disagrees with item_type")
    elif body_type == "Gap":
        body = Gap(int(raw["first_missed_seq"]))
    elif body_type == "Terminal":
        result_raw = raw["result"]
        if not isinstance(result_raw, Mapping):
            raise TypeError("terminal result must be a mapping")
        error_raw = result_raw.get("error")
        error = None
        if isinstance(error_raw, Mapping):
            error = FailureDetail(str(error_raw["type_name"]), str(error_raw["message"]))
        items_raw = result_raw.get("items", ())
        if not isinstance(items_raw, list):
            raise TypeError("terminal items must be a list")
        body = Terminal(
            OperationResult(
                status=SessionState(str(result_raw["status"])),
                recording=RecordingStatus(str(result_raw["recording"])),
                audit=RecordingStatus(str(result_raw["audit"])),
                disposition=Disposition(str(result_raw["disposition"])),
                canceled=bool(result_raw["canceled"]),
                items=tuple(result_item_from_dict(item) for item in items_raw),
                bytes_done=int(result_raw["bytes_done"]),
                bytes_total=int(result_raw["bytes_total"]),
                error=error,
            )
        )
    else:
        raise ValueError(f"unsupported event body type: {body_type}")
    return Envelope(
        session_id=SessionId(str(data["session_id"])),
        seq=int(data["seq"]),
        at=datetime.fromisoformat(str(data["at"])),
        schema_version=version,
        body=body,
    )


def result_item_to_dict(item: ResultItem) -> dict[str, object]:
    """Serialize one nominal result item with explicit type and phase tags."""

    if isinstance(item, ItemOutcome):
        return {
            "item_type": item.item_type,
            "phase": item.phase,
            "item_id": item.item_id,
            "kind": item.kind,
            "path": item.path,
            "result": item.outcome.value,
            "reason": item.reason,
            "detail": dict(item.detail),
        }
    if isinstance(item, IntegrityOutcome):
        return {
            "item_type": item.item_type,
            "phase": item.phase,
            "item_id": item.item_id,
            "row_id": item.row_id,
            "location_id": item.location_id,
            "kind": "integrity",
            "path": item.path,
            "result": item.result.value,
            "reason": None if item.reason is None else item.reason.value,
            "detail": item.detail,
            "read_strategy": (
                None if item.read_strategy is None else item.read_strategy.value
            ),
            "recording": item.recording.value,
            "record_disposition": (
                None
                if item.record_disposition is None
                else item.record_disposition.value
            ),
        }
    raise TypeError(f"unsupported result item: {type(item).__name__}")


def result_item_from_dict(data: Mapping[str, object]) -> ResultItem:
    """Deserialize a tagged result item and reject structural guessing."""

    item_type = str(data["item_type"])
    phase = str(data["phase"])
    if item_type == ItemOutcome.item_type:
        if phase != ItemOutcome.phase:
            raise ValueError("operation result item must use execute phase")
        detail = data.get("detail", {})
        if not isinstance(detail, Mapping):
            raise TypeError("operation item detail must be a mapping")
        return ItemOutcome(
            item_id=str(data["item_id"]),
            kind=str(data["kind"]),
            path=str(data["path"]),
            outcome=Outcome(str(data["result"])),
            reason=_optional_str(data.get("reason")),
            detail=dict(detail),
        )
    if item_type == IntegrityOutcome.item_type:
        if phase not in {mode.value for mode in IntegrityMode}:
            raise ValueError("integrity result item has an invalid phase")
        return IntegrityOutcome(
            item_id=str(data["item_id"]),
            row_id=str(data["row_id"]),
            location_id=str(data["location_id"]),
            path=str(data["path"]),
            result=IntegrityResult(str(data["result"])),
            reason=(
                None
                if data.get("reason") is None
                else IntegrityReason(str(data["reason"]))
            ),
            detail=_optional_str(data.get("detail")),
            read_strategy=(
                None
                if data.get("read_strategy") is None
                else ReadStrategy(str(data["read_strategy"]))
            ),
            recording=RecordingStatus(str(data["recording"])),
            record_disposition=(
                None
                if data.get("record_disposition") is None
                else RecordDisposition(str(data["record_disposition"]))
            ),
            phase=phase,
        )
    raise ValueError(f"unsupported result item type: {item_type}")


def _result_to_dict(result: "OperationResult") -> dict[str, object]:
    return {
        "status": result.status.value,
        "recording": result.recording.value,
        "audit": result.audit.value,
        "disposition": result.disposition.value,
        "canceled": result.canceled,
        "items": [result_item_to_dict(item) for item in result.items],
        "bytes_done": result.bytes_done,
        "bytes_total": result.bytes_total,
        "error": (
            None
            if result.error is None
            else {"type_name": result.error.type_name, "message": result.error.message}
        ),
    }


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from namisync.core.session import OperationResult, SessionId, SessionState
