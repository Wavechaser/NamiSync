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
        if not isinstance(self.session_id, str) or not self.session_id:
            raise ValueError("session_id must be non-empty")
        if type(self.seq) is not int or self.seq < 1:
            raise ValueError("event sequence must be positive")
        if (
            type(self.schema_version) is not int
            or self.schema_version != SCHEMA_VERSION
        ):
            raise ValueError(f"unsupported event schema version: {self.schema_version}")
        if not isinstance(self.at, datetime):
            raise TypeError("event timestamp must be a datetime")
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
        PhaseResult,
        PhaseStatus,
        SessionId,
        SessionState,
    )

    version = _integer(data["schema_version"], "event schema version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"unsupported event schema version: {version}")
    body_type = _string(data["body_type"], "event body type")
    raw = data["body"]
    if not isinstance(raw, Mapping):
        raise TypeError("event body must be a mapping")
    if body_type == "StateChanged":
        body: object = StateChanged(
            SessionState(_string(raw["state"], "state event state"))
        )
    elif body_type == "PhaseChanged":
        body = PhaseChanged(_string(raw["phase"], "phase event phase"))
    elif body_type == "Progress":
        body = Progress(
            items_done=_integer(
                raw["items_done"], "progress items_done"
            ),
            items_total=_optional_int(
                raw["items_total"], "progress items_total"
            ),
            bytes_done=_integer(
                raw["bytes_done"], "progress bytes_done"
            ),
            bytes_total=_optional_int(
                raw["bytes_total"], "progress bytes_total"
            ),
            current_path=_optional_str(
                raw["current_path"], "progress current_path"
            ),
        )
    elif body_type in {"ItemOutcome", "IntegrityOutcome"}:
        body = result_item_from_dict(raw)
        if type(body).__name__ != body_type:
            raise ValueError("event body type disagrees with item_type")
    elif body_type == "Gap":
        body = Gap(
            _integer(raw["first_missed_seq"], "gap first_missed_seq")
        )
    elif body_type == "Terminal":
        result_raw = raw["result"]
        if not isinstance(result_raw, Mapping):
            raise TypeError("terminal result must be a mapping")
        error_raw = result_raw.get("error")
        error = None
        if error_raw is not None:
            if not isinstance(error_raw, Mapping):
                raise ValueError("terminal result error must be an object or null")
            error = FailureDetail(
                _string(error_raw["type_name"], "terminal error type_name"),
                _string(error_raw["message"], "terminal error message"),
            )
        items_raw = result_raw.get("items", ())
        if not isinstance(items_raw, list):
            raise TypeError("terminal items must be a list")
        phases_raw = result_raw["phases"]
        if not isinstance(phases_raw, list):
            raise TypeError("terminal phases must be a list")
        body = Terminal(
            OperationResult(
                status=SessionState(
                    _string(result_raw["status"], "terminal status")
                ),
                recording=RecordingStatus(
                    _string(result_raw["recording"], "terminal recording")
                ),
                audit=RecordingStatus(
                    _string(result_raw["audit"], "terminal audit")
                ),
                disposition=Disposition(
                    _string(
                        result_raw["disposition"],
                        "terminal disposition",
                    )
                ),
                canceled=_boolean(
                    result_raw["canceled"], "terminal canceled"
                ),
                items=tuple(result_item_from_dict(item) for item in items_raw),
                phases=tuple(
                    PhaseResult(
                        phase=_string(
                            _mapping_value(phase, "phase"),
                            "terminal phase name",
                        ),
                        status=PhaseStatus(
                            _string(
                                _mapping_value(phase, "status"),
                                "terminal phase status",
                            )
                        ),
                        items_done=_integer(
                            _mapping_value(phase, "items_done"),
                            "terminal phase items_done",
                        ),
                        items_total=_optional_int(
                            _mapping_value(phase, "items_total"),
                            "terminal phase items_total",
                        ),
                        bytes_done=_integer(
                            _mapping_value(phase, "bytes_done"),
                            "terminal phase bytes_done",
                        ),
                        bytes_total=_optional_int(
                            _mapping_value(phase, "bytes_total"),
                            "terminal phase bytes_total",
                        ),
                        error=_optional_str(
                            _mapping_value(phase, "error"),
                            "terminal phase error",
                        ),
                    )
                    for phase in phases_raw
                ),
                bytes_done=_integer(
                    result_raw["bytes_done"], "terminal bytes_done"
                ),
                bytes_total=_integer(
                    result_raw["bytes_total"], "terminal bytes_total"
                ),
                error=error,
            )
        )
    else:
        raise ValueError(f"unsupported event body type: {body_type}")
    return Envelope(
        session_id=SessionId(
            _string(data["session_id"], "event session_id")
        ),
        seq=_integer(data["seq"], "event sequence"),
        at=_datetime(data["at"], "event timestamp"),
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

    item_type = _string(data["item_type"], "result item type")
    phase = _string(data["phase"], "result item phase")
    if item_type == ItemOutcome.item_type:
        if phase != ItemOutcome.phase:
            raise ValueError("operation result item must use execute phase")
        detail = data.get("detail", {})
        if not isinstance(detail, Mapping):
            raise TypeError("operation item detail must be a mapping")
        return ItemOutcome(
            item_id=_string(data["item_id"], "operation item id"),
            kind=_string(data["kind"], "operation item kind"),
            path=_string(data["path"], "operation item path"),
            outcome=Outcome(
                _string(data["result"], "operation item result")
            ),
            reason=_optional_str(
                data.get("reason"), "operation item reason"
            ),
            detail=dict(detail),
        )
    if item_type == IntegrityOutcome.item_type:
        if phase not in {mode.value for mode in IntegrityMode}:
            raise ValueError("integrity result item has an invalid phase")
        return IntegrityOutcome(
            item_id=_string(data["item_id"], "integrity item id"),
            row_id=_optional_str(
                data["row_id"], "integrity item row_id"
            ),
            location_id=_optional_str(
                data["location_id"], "integrity item location_id"
            ),
            path=_string(data["path"], "integrity item path"),
            result=IntegrityResult(
                _string(data["result"], "integrity item result")
            ),
            reason=(
                None
                if data.get("reason") is None
                else IntegrityReason(
                    _string(data["reason"], "integrity item reason")
                )
            ),
            detail=_optional_str(
                data.get("detail"), "integrity item detail"
            ),
            read_strategy=(
                None
                if data.get("read_strategy") is None
                else ReadStrategy(
                    _string(
                        data["read_strategy"],
                        "integrity item read_strategy",
                    )
                )
            ),
            recording=RecordingStatus(
                _string(data["recording"], "integrity item recording")
            ),
            record_disposition=(
                None
                if data.get("record_disposition") is None
                else RecordDisposition(
                    _string(
                        data["record_disposition"],
                        "integrity item record_disposition",
                    )
                )
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
        "phases": [
            {
                "phase": phase.phase,
                "status": phase.status.value,
                "items_done": phase.items_done,
                "items_total": phase.items_total,
                "bytes_done": phase.bytes_done,
                "bytes_total": phase.bytes_total,
                "error": phase.error,
            }
            for phase in result.phases
        ],
        "bytes_done": result.bytes_done,
        "bytes_total": result.bytes_total,
        "error": (
            None
            if result.error is None
            else {"type_name": result.error.type_name, "message": result.error.message}
        ),
    }


def _integer(value: object, context: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{context} must be an integer")
    return value


def _optional_int(value: object, context: str) -> int | None:
    return None if value is None else _integer(value, context)


def _string(value: object, context: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{context} must be a string")
    return value


def _optional_str(value: object, context: str) -> str | None:
    return None if value is None else _string(value, context)


def _boolean(value: object, context: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{context} must be a boolean")
    return value


def _datetime(value: object, context: str) -> datetime:
    try:
        return datetime.fromisoformat(_string(value, context))
    except ValueError as error:
        raise ValueError(f"{context} must be an ISO-8601 datetime") from error


def _mapping_value(value: object, key: str) -> object:
    if not isinstance(value, Mapping):
        raise TypeError("terminal phase must be a mapping")
    return value[key]


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from namisync.core.session import OperationResult, SessionId, SessionState
