"""Exact core-event v5 bodies, envelopes, and bounded projections."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import json
import re
from typing import ClassVar

from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.event_v5 import (
    EVENT_V5_SCHEMA_VERSION,
    MAX_DETAIL_LEAVES,
    MAX_DETAIL_PATH_LEAVES,
    validate_event_v5_envelope,
)
from namisync.core.execution import (
    ExecutionReason,
    ItemRecordingReason,
    TaskRecordingIssue,
    TaskRecordingIssueReason,
    validate_item_recording_outcome,
)
from namisync.core.integrity import (
    IntegrityOutcome,
    IntegrityReason,
    IntegrityResult,
    ReadStrategy,
    RecordDisposition,
)
from namisync.core.planning import BlockedReason, OperationKind
from namisync.core.review import (
    ReviewFactLimitExceeded,
    ReviewLimitAxis,
    ReviewPopulation,
    ReviewTreeKind,
)
from namisync.core.scalars import (
    bounded_utf8_text,
    require_safe_int,
    require_signed_64,
    require_utf16_path,
    scalar_64_from_text,
    scalar_64_to_text,
)
from namisync.core.session import (
    Disposition,
    FailureDetail,
    OperationResult,
    PhaseResult,
    PhaseStatus,
    ResultItem,
    SessionId,
    SessionState,
    normalize_result_diagnostics,
    validate_result_cancellation,
)


CORE_EVENT_SCHEMA_VERSION = EVENT_V5_SCHEMA_VERSION

_HEX_ID = re.compile(r"[0-9a-f]{32}\Z")
_DETAIL_TEXT_KEYS = frozenset(
    {
        "backup",
        "backup_metadata",
        "backup_state",
        "backup_state_error",
        "blocked_reason",
        "cleanup_error",
        "destination_state",
        "durable_state",
        "error_type",
        "message",
        "mutation_durable_state",
        "mutation_state",
        "mutation_state_error",
        "old_state_error",
        "publish_state",
        "retry_error",
        "retry_error_type",
        "source_state",
        "state_error",
        "state_error_type",
        "target_state",
        "target_state_error",
        "temp_state",
        "trash_state_error",
    }
)
_DETAIL_PATH_KEYS = frozenset(
    {
        "backup_path",
        "mutation_destination",
        "prior_path",
        "published_path",
        "trash_path",
    }
)
_DETAIL_BOOLEAN_KEYS = frozenset({"continued"})
_DETAIL_TEXT_ARRAY_KEYS = frozenset({"durability_warnings"})
_DETAIL_SIDE_ARRAY_KEYS = frozenset({"incomplete_sides"})
_DETAIL_ID_ARRAY_KEYS = frozenset({"excluded_dependencies"})
_DETAIL_KEYS = frozenset(
    {
        *_DETAIL_TEXT_KEYS,
        *_DETAIL_PATH_KEYS,
        *_DETAIL_BOOLEAN_KEYS,
        *_DETAIL_TEXT_ARRAY_KEYS,
        *_DETAIL_SIDE_ARRAY_KEYS,
        *_DETAIL_ID_ARRAY_KEYS,
    }
)
_OPERATION_REASONS = frozenset(
    {
        *(reason.value for reason in ExecutionReason),
        *(reason.value for reason in BlockedReason),
        "blocked-correspondence",
        "blocked-dependency",
        "incomplete-scan",
        "user-deselected",
    }
)


class DeliveryClass(StrEnum):
    LOSSY = "lossy"
    RELIABLE = "reliable"


@dataclass(frozen=True, slots=True)
class StateChanged:
    state: SessionState


@dataclass(frozen=True, slots=True)
class PhaseChanged:
    phase: str

    def __post_init__(self) -> None:
        _require_nonempty_text(self.phase, "phase")


@dataclass(frozen=True, slots=True)
class Progress:
    phase: str
    items_done: int
    items_total: int | None
    bytes_done: int
    bytes_total: int | None
    current_path: str | None
    item_id: str | None = None
    item_type: str | None = None
    item_attempt_id: str | None = None
    item_bytes_done: int | None = None
    item_bytes_total: int | None = None

    def __post_init__(self) -> None:
        _require_nonempty_text(self.phase, "progress phase")
        require_safe_int(self.items_done, "progress items_done")
        require_signed_64(self.bytes_done, "progress bytes_done")
        if self.items_total is not None:
            require_safe_int(self.items_total, "progress items_total")
        if self.bytes_total is not None:
            require_signed_64(self.bytes_total, "progress bytes_total")
        if self.current_path is not None:
            require_utf16_path(self.current_path, "progress current_path")
        if self.items_total is not None and self.items_done > self.items_total:
            raise ValueError("items_done cannot exceed items_total")
        if self.bytes_total is not None and self.bytes_done > self.bytes_total:
            raise ValueError("bytes_done cannot exceed bytes_total")
        if (self.item_id is None) != (self.item_type is None):
            raise ValueError("progress item identity must be present as a pair")
        if self.item_id is not None:
            _require_nonempty_text(self.item_id, "progress item_id")
            if self.item_type not in {"operation", "integrity"}:
                raise ValueError("progress item_type is unsupported")
            if self.items_total is not None and self.items_done >= self.items_total:
                raise ValueError(
                    "active progress item requires an unsettled selected item"
                )
        if self.item_attempt_id is not None:
            if self.item_id is None or _HEX_ID.fullmatch(self.item_attempt_id) is None:
                raise ValueError(
                    "progress item_attempt_id requires 32 lowercase hex characters"
                )
        if (self.item_bytes_done is None) != (self.item_bytes_total is None):
            raise ValueError("progress item byte counters must be present as a pair")
        if self.item_bytes_done is not None:
            if self.item_attempt_id is None:
                raise ValueError("progress item byte counters require an item attempt")
            require_signed_64(self.item_bytes_done, "progress item_bytes_done")
            require_signed_64(self.item_bytes_total, "progress item_bytes_total")
            if self.item_bytes_done > self.item_bytes_total:
                raise ValueError("item_bytes_done cannot exceed item_bytes_total")
            if self.item_bytes_done > self.bytes_done:
                raise ValueError("item_bytes_done cannot exceed bytes_done")
            if self.bytes_total is not None and self.item_bytes_total > self.bytes_total:
                raise ValueError("item_bytes_total cannot exceed bytes_total")


DetailValue = str | bool | tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DetailProjection(Mapping[str, DetailValue]):
    """One closed, immutable executor detail snapshot."""

    entries: tuple[tuple[str, DetailValue], ...] = ()

    def __iter__(self) -> Iterator[str]:
        return (key for key, _value in self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, key: str) -> DetailValue:
        for candidate, value in self.entries:
            if candidate == key:
                return value
        raise KeyError(key)

    def to_wire(self) -> dict[str, object]:
        return {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in self.entries
        }


@dataclass(frozen=True, slots=True)
class ItemOutcome(ResultItem):
    item_type: ClassVar[str] = "operation"
    phase: ClassVar[str] = "execute"

    item_id: str
    kind: OperationKind | str
    path: str
    outcome: Outcome
    reason: str | None = None
    detail: Mapping[str, object] | DetailProjection = field(default_factory=dict)
    recording: RecordingStatus = RecordingStatus.OK
    recording_reason: ItemRecordingReason | None = None
    recording_detail: str | None = None
    detail_omitted_count: int = 0

    def __post_init__(self) -> None:
        if not self.item_id:
            raise ValueError("item_id must be non-empty")
        kind = self.kind
        if isinstance(kind, str):
            try:
                kind = OperationKind(kind)
            except ValueError as error:
                raise ValueError("operation item kind is unsupported") from error
            object.__setattr__(self, "kind", kind)
        if not isinstance(kind, OperationKind):
            raise TypeError("operation item kind must be OperationKind")
        require_utf16_path(self.path, "operation path")
        if self.reason is not None and self.reason not in _OPERATION_REASONS:
            raise ValueError("operation item reason is unsupported")
        projection, omitted = project_detail(self.detail)
        object.__setattr__(self, "detail", projection)
        require_safe_int(
            self.detail_omitted_count,
            "operation detail_omitted_count",
        )
        bounded_recording = bounded_utf8_text(
            self.recording_detail,
            "operation recording_detail",
        )
        if self.recording_detail is not None and bounded_recording is None:
            omitted += 1
            object.__setattr__(self, "recording_detail", None)
        object.__setattr__(
            self,
            "detail_omitted_count",
            require_safe_int(
                self.detail_omitted_count + omitted,
                "operation detail_omitted_count",
            ),
        )
        if self.recording is RecordingStatus.OK:
            if self.recording_reason is not None or self.recording_detail is not None:
                raise ValueError("recording ok requires null reason and detail")
        elif self.recording is RecordingStatus.DEGRADED:
            if not isinstance(self.recording_reason, ItemRecordingReason):
                raise ValueError("degraded recording requires an item reason")
            validate_item_recording_outcome(self.outcome, self.recording_reason)
        else:
            raise TypeError("operation recording has the wrong type")


@dataclass(frozen=True, slots=True)
class Gap:
    first_missed_seq: int

    def __post_init__(self) -> None:
        require_safe_int(self.first_missed_seq, "first_missed_seq")
        if self.first_missed_seq < 1:
            raise ValueError("first_missed_seq must be positive")


@dataclass(frozen=True, slots=True)
class TerminalSummary:
    """Bounded item-free terminal truth transported in event v5."""

    status: SessionState
    recording: RecordingStatus
    audit: RecordingStatus
    disposition: Disposition
    canceled: bool
    phases: tuple[PhaseResult, ...]
    bytes_done: int
    bytes_total: int
    error: FailureDetail | None
    recording_degraded_items: int
    recording_issues: tuple[TaskRecordingIssue, ...]
    omitted_detail_count: int
    review_fact_limit: ReviewFactLimitExceeded | None

    def __post_init__(self) -> None:
        if self.status not in {
            SessionState.COMPLETED,
            SessionState.FAILED,
            SessionState.CANCELED,
            SessionState.REFUSED,
        }:
            raise ValueError("terminal summary status must be terminal")
        if type(self.canceled) is not bool:
            raise TypeError("terminal canceled must be a boolean")
        if not isinstance(self.phases, tuple) or len(self.phases) > 3:
            raise ValueError("terminal phases exceed their bound")
        if len({phase.phase for phase in self.phases}) != len(self.phases):
            raise ValueError("terminal phase names must be unique")
        require_signed_64(self.bytes_done, "terminal bytes_done")
        require_signed_64(self.bytes_total, "terminal bytes_total")
        if self.bytes_done > self.bytes_total:
            raise ValueError("terminal bytes_done cannot exceed bytes_total")
        require_safe_int(
            self.recording_degraded_items,
            "terminal recording_degraded_items",
        )
        if not isinstance(self.recording_issues, tuple) or len(self.recording_issues) > 5:
            raise ValueError("terminal recording issues exceed their bound")
        if any(not isinstance(issue, TaskRecordingIssue) for issue in self.recording_issues):
            raise TypeError("terminal recording issues have the wrong type")
        if len({issue.reason for issue in self.recording_issues}) != len(
            self.recording_issues
        ):
            raise ValueError("terminal recording issue reasons must be unique")
        require_safe_int(self.omitted_detail_count, "terminal omitted_detail_count")
        expected_recording = (
            RecordingStatus.DEGRADED
            if self.recording_degraded_items or self.recording_issues
            else RecordingStatus.OK
        )
        if self.recording is not expected_recording:
            raise ValueError("terminal recording aggregate contradicts its witnesses")
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
            and not self.phases
            and self.bytes_done == 0
            and self.bytes_total == 0
            and self.error is None
            and self.recording_degraded_items == 0
            and not self.recording_issues
            and self.omitted_detail_count == 0
        ):
            raise ValueError("review-limit terminal summary has contradictory facts")

    @classmethod
    def from_result(cls, result: OperationResult) -> "TerminalSummary":
        result = normalize_result_diagnostics(result)
        omitted = result.omitted_detail_count
        degraded_items = 0
        for item in result.items:
            omitted = require_safe_int(
                omitted + item.detail_omitted_count,
                "terminal omitted_detail_count",
            )
            if item.recording is RecordingStatus.DEGRADED:
                degraded_items += 1
        degraded_items = require_safe_int(
            degraded_items,
            "terminal recording_degraded_items",
        )
        expected_recording = (
            RecordingStatus.DEGRADED
            if degraded_items or result.recording_issues
            else RecordingStatus.OK
        )
        if result.recording is not expected_recording:
            raise ValueError("operation recording aggregate contradicts its witnesses")
        return cls(
            status=result.status,
            recording=result.recording,
            audit=result.audit,
            disposition=result.disposition,
            canceled=result.canceled,
            phases=result.phases,
            bytes_done=result.bytes_done,
            bytes_total=result.bytes_total,
            error=result.error,
            recording_degraded_items=degraded_items,
            recording_issues=result.recording_issues,
            omitted_detail_count=omitted,
            review_fact_limit=result.review_fact_limit,
        )


@dataclass(frozen=True, slots=True)
class Terminal:
    result: TerminalSummary | OperationResult

    def __post_init__(self) -> None:
        if not isinstance(self.result, (TerminalSummary, OperationResult)):
            raise TypeError("Terminal result has the wrong type")


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
    session_id: SessionId
    seq: int
    at: datetime
    schema_version: int
    body: object

    def __post_init__(self) -> None:
        if type(self.session_id) is not str or _HEX_ID.fullmatch(self.session_id) is None:
            raise ValueError("session_id must be 32 lowercase hexadecimal characters")
        require_safe_int(self.seq, "event sequence")
        if self.seq < 1:
            raise ValueError("event sequence must be positive")
        if type(self.schema_version) is not int or self.schema_version != 5:
            raise ValueError("event schema version must be exactly 5")
        _require_utc(self.at, "event timestamp")


def delivery_class(body: object) -> DeliveryClass:
    return DeliveryClass.LOSSY if isinstance(body, Progress) else DeliveryClass.RELIABLE


def project_detail(
    value: Mapping[str, object] | DetailProjection,
) -> tuple[DetailProjection, int]:
    """Snapshot one declared detail map and omit only oversized diagnostics."""

    if isinstance(value, DetailProjection):
        return value, 0
    if not isinstance(value, Mapping):
        raise TypeError("operation detail must be a mapping")
    entries: list[tuple[str, DetailValue]] = []
    leaves = 0
    path_leaves = 0
    omitted = 0
    for key, raw in value.items():
        if type(key) is not str:
            raise TypeError("operation detail keys must be strings")
        try:
            encoded_key = key.encode("ascii")
        except UnicodeEncodeError as error:
            raise ValueError("operation detail keys must be ASCII") from error
        if not encoded_key or len(encoded_key) > 64 or key not in _DETAIL_KEYS:
            raise ValueError(f"operation detail key is undeclared: {key!r}")
        if key in _DETAIL_TEXT_KEYS:
            if type(raw) is not str:
                raise TypeError(f"operation detail {key} must be text")
            bounded = bounded_utf8_text(raw, f"operation detail {key}")
            if bounded is None:
                omitted += 1
                continue
            projected: DetailValue = bounded
            leaves += 1
        elif key in _DETAIL_PATH_KEYS:
            projected = require_utf16_path(raw, f"operation detail {key}")
            leaves += 1
            path_leaves += 1
        elif key in _DETAIL_BOOLEAN_KEYS:
            if type(raw) is not bool:
                raise TypeError(f"operation detail {key} must be a boolean")
            projected = raw
            leaves += 1
        else:
            if type(raw) not in {list, tuple}:
                raise TypeError(f"operation detail {key} must be a bounded array")
            if len(raw) > 32:
                raise ValueError(f"operation detail {key} exceeds its array bound")
            members: list[str] = []
            omit_array = False
            for member in raw:
                if key in _DETAIL_SIDE_ARRAY_KEYS:
                    if member not in {"source", "target"}:
                        raise ValueError(f"operation detail {key} has an invalid side")
                    members.append(member)
                elif key in _DETAIL_ID_ARRAY_KEYS:
                    if type(member) is not str or _HEX_ID.fullmatch(member) is None:
                        raise ValueError(f"operation detail {key} has an invalid id")
                    members.append(member)
                else:
                    if type(member) is not str:
                        raise TypeError(
                            f"operation detail {key} members must be text"
                        )
                    bounded = bounded_utf8_text(member, f"operation detail {key}")
                    if bounded is None:
                        omit_array = True
                        break
                    members.append(bounded)
            if omit_array:
                omitted += 1
                continue
            projected = tuple(members)
            leaves += len(members)
        if leaves > MAX_DETAIL_LEAVES:
            raise ValueError("operation detail exceeds its primitive-leaf bound")
        if path_leaves > MAX_DETAIL_PATH_LEAVES:
            raise ValueError("operation detail exceeds its path-leaf bound")
        entries.append((key, projected))
    return DetailProjection(tuple(entries)), omitted


def envelope_to_dict(envelope: Envelope) -> dict[str, object]:
    """Serialize and validate one exact core-event v5 envelope."""

    body = envelope.body
    if isinstance(body, StateChanged):
        body_data: dict[str, object] = {"state": body.state.value}
    elif isinstance(body, PhaseChanged):
        body_data = {"phase": body.phase}
    elif isinstance(body, Progress):
        body_data = _progress_to_dict(body)
    elif isinstance(body, ResultItem):
        body_data = result_item_to_dict(body)
    elif isinstance(body, Gap):
        body_data = {"first_missed_seq": body.first_missed_seq}
    elif isinstance(body, Terminal):
        if not isinstance(body.result, TerminalSummary):
            raise TypeError("live Terminal must contain TerminalSummary")
        body_data = {"result": terminal_summary_to_dict(body.result)}
    else:
        raise TypeError(f"unsupported event body: {type(body).__name__}")
    value = {
        "session_id": str(envelope.session_id),
        "seq": envelope.seq,
        "at": envelope.at.isoformat(),
        "schema_version": CORE_EVENT_SCHEMA_VERSION,
        "body_type": type(body).__name__,
        "body": body_data,
    }
    validate_event_v5_envelope(value)
    return value


def canonical_event_bytes(envelope: Envelope) -> bytes:
    """Return the exact bytes used for reliable-event admission."""

    return json.dumps(
        envelope_to_dict(envelope),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def envelope_from_dict(data: Mapping[str, object]) -> Envelope:
    """Decode only the exact current core-event version."""

    plain = dict(data)
    validate_event_v5_envelope(plain)
    raw = _plain_object(plain["body"], "event body")
    body_type = _text(plain["body_type"], "event body type")
    if body_type == "StateChanged":
        body: object = StateChanged(SessionState(_text(raw["state"], "state")))
    elif body_type == "PhaseChanged":
        body = PhaseChanged(_text(raw["phase"], "phase"))
    elif body_type == "Progress":
        body = Progress(
            phase=_text(raw["phase"], "progress phase"),
            items_done=_int(raw["items_done"], "progress items_done"),
            items_total=_optional_int(raw["items_total"], "progress items_total"),
            bytes_done=scalar_64_from_text(raw["bytes_done"], "progress bytes_done"),
            bytes_total=_optional_scalar(raw["bytes_total"], "progress bytes_total"),
            current_path=_optional_text(raw["current_path"], "progress current_path"),
            item_id=_optional_text(raw["item_id"], "progress item_id"),
            item_type=_optional_text(raw["item_type"], "progress item_type"),
            item_attempt_id=_optional_text(raw["item_attempt_id"], "progress item_attempt_id"),
            item_bytes_done=_optional_scalar(raw["item_bytes_done"], "progress item_bytes_done"),
            item_bytes_total=_optional_scalar(raw["item_bytes_total"], "progress item_bytes_total"),
        )
    elif body_type in {"ItemOutcome", "IntegrityOutcome"}:
        body = result_item_from_dict(raw)
        if type(body).__name__ != body_type:
            raise ValueError("event body type disagrees with item_type")
    elif body_type == "Gap":
        body = Gap(_int(raw["first_missed_seq"], "gap first_missed_seq"))
    elif body_type == "Terminal":
        body = Terminal(
            terminal_summary_from_dict(
                _plain_object(raw["result"], "terminal result")
            )
        )
    else:
        raise ValueError(f"unsupported event body type: {body_type}")
    return Envelope(
        session_id=SessionId(_text(plain["session_id"], "event session_id")),
        seq=_int(plain["seq"], "event sequence"),
        at=_datetime(plain["at"], "event timestamp"),
        schema_version=CORE_EVENT_SCHEMA_VERSION,
        body=body,
    )


def result_item_to_dict(item: ResultItem) -> dict[str, object]:
    """Serialize one exact v5 result item."""

    if isinstance(item, ItemOutcome):
        detail = item.detail
        if not isinstance(detail, DetailProjection):
            raise TypeError("operation detail was not projected")
        kind = item.kind
        if not isinstance(kind, OperationKind):
            raise TypeError("operation kind was not normalized")
        return {
            "item_type": item.item_type,
            "phase": item.phase,
            "item_id": item.item_id,
            "kind": kind.value,
            "path": item.path,
            "result": item.outcome.value,
            "reason": item.reason,
            "detail": detail.to_wire(),
            "recording": item.recording.value,
            "recording_reason": (
                None if item.recording_reason is None else item.recording_reason.value
            ),
            "recording_detail": item.recording_detail,
            "detail_omitted_count": item.detail_omitted_count,
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
            "read_strategy": None if item.read_strategy is None else item.read_strategy.value,
            "recording": item.recording.value,
            "record_disposition": (
                None if item.record_disposition is None else item.record_disposition.value
            ),
            "detail_omitted_count": item.detail_omitted_count,
        }
    raise TypeError(f"unsupported result item: {type(item).__name__}")


def result_item_from_dict(data: Mapping[str, object]) -> ResultItem:
    item_type = _text(data["item_type"], "result item type")
    phase = _text(data["phase"], "result item phase")
    if item_type == "operation":
        return ItemOutcome(
            item_id=_text(data["item_id"], "operation item id"),
            kind=OperationKind(_text(data["kind"], "operation kind")),
            path=_text(data["path"], "operation path"),
            outcome=Outcome(_text(data["result"], "operation result")),
            reason=_optional_text(data["reason"], "operation reason"),
            detail=_plain_object(data["detail"], "operation detail"),
            recording=RecordingStatus(_text(data["recording"], "operation recording")),
            recording_reason=(
                None
                if data["recording_reason"] is None
                else ItemRecordingReason(
                    _text(data["recording_reason"], "operation recording reason")
                )
            ),
            recording_detail=_optional_text(
                data["recording_detail"], "operation recording detail"
            ),
            detail_omitted_count=_int(
                data["detail_omitted_count"], "operation detail_omitted_count"
            ),
        )
    if item_type == "integrity":
        return IntegrityOutcome(
            item_id=_text(data["item_id"], "integrity item id"),
            row_id=_optional_text(data["row_id"], "integrity row_id"),
            location_id=_optional_text(data["location_id"], "integrity location_id"),
            path=_text(data["path"], "integrity path"),
            result=IntegrityResult(_text(data["result"], "integrity result")),
            reason=(
                None
                if data["reason"] is None
                else IntegrityReason(_text(data["reason"], "integrity reason"))
            ),
            detail=_optional_text(data["detail"], "integrity detail"),
            read_strategy=(
                None
                if data["read_strategy"] is None
                else ReadStrategy(_text(data["read_strategy"], "integrity read strategy"))
            ),
            recording=RecordingStatus(_text(data["recording"], "integrity recording")),
            record_disposition=(
                None
                if data["record_disposition"] is None
                else RecordDisposition(
                    _text(data["record_disposition"], "integrity record disposition")
                )
            ),
            phase=phase,
            detail_omitted_count=_int(
                data["detail_omitted_count"], "integrity detail_omitted_count"
            ),
        )
    raise ValueError(f"unsupported result item type: {item_type}")


def terminal_summary_to_dict(result: TerminalSummary) -> dict[str, object]:
    return {
        "status": result.status.value,
        "recording": result.recording.value,
        "audit": result.audit.value,
        "disposition": result.disposition.value,
        "canceled": result.canceled,
        "phases": [_phase_to_dict(phase) for phase in result.phases],
        "bytes_done": scalar_64_to_text(result.bytes_done, "terminal bytes_done"),
        "bytes_total": scalar_64_to_text(result.bytes_total, "terminal bytes_total"),
        "error": (
            None
            if result.error is None
            else {"type_name": result.error.type_name, "message": result.error.message}
        ),
        "recording_degraded_items": result.recording_degraded_items,
        "recording_issues": [
            {"reason": issue.reason.value, "detail": issue.detail}
            for issue in result.recording_issues
        ],
        "omitted_detail_count": result.omitted_detail_count,
        "review_fact_limit": (
            None
            if result.review_fact_limit is None
            else _review_fact_to_dict(result.review_fact_limit)
        ),
    }


def terminal_summary_from_dict(data: Mapping[str, object]) -> TerminalSummary:
    error_raw = data["error"]
    error = None
    if error_raw is not None:
        error_value = _plain_object(error_raw, "terminal error")
        error = FailureDetail(
            _text(error_value["type_name"], "terminal error type"),
            _text(error_value["message"], "terminal error message"),
        )
    phases_raw = _plain_list(data["phases"], "terminal phases")
    issues_raw = _plain_list(data["recording_issues"], "terminal recording issues")
    review_raw = data["review_fact_limit"]
    return TerminalSummary(
        status=SessionState(_text(data["status"], "terminal status")),
        recording=RecordingStatus(_text(data["recording"], "terminal recording")),
        audit=RecordingStatus(_text(data["audit"], "terminal audit")),
        disposition=Disposition(_text(data["disposition"], "terminal disposition")),
        canceled=_bool(data["canceled"], "terminal canceled"),
        phases=tuple(
            _phase_from_dict(_plain_object(value, "terminal phase"))
            for value in phases_raw
        ),
        bytes_done=scalar_64_from_text(data["bytes_done"], "terminal bytes_done"),
        bytes_total=scalar_64_from_text(data["bytes_total"], "terminal bytes_total"),
        error=error,
        recording_degraded_items=_int(
            data["recording_degraded_items"], "terminal recording_degraded_items"
        ),
        recording_issues=tuple(
            _recording_issue_from_dict(
                _plain_object(value, "terminal recording issue")
            )
            for value in issues_raw
        ),
        omitted_detail_count=_int(
            data["omitted_detail_count"], "terminal omitted_detail_count"
        ),
        review_fact_limit=(
            None
            if review_raw is None
            else _review_fact_from_dict(_plain_object(review_raw, "review fact limit"))
        ),
    )


def _recording_issue_from_dict(data: Mapping[str, object]) -> TaskRecordingIssue:
    return TaskRecordingIssue(
        TaskRecordingIssueReason(_text(data["reason"], "recording issue reason")),
        _optional_text(data["detail"], "recording issue detail"),
    )


def _progress_to_dict(progress: Progress) -> dict[str, object]:
    return {
        "phase": progress.phase,
        "items_done": progress.items_done,
        "items_total": progress.items_total,
        "bytes_done": scalar_64_to_text(progress.bytes_done, "progress bytes_done"),
        "bytes_total": (
            None
            if progress.bytes_total is None
            else scalar_64_to_text(progress.bytes_total, "progress bytes_total")
        ),
        "current_path": progress.current_path,
        "item_id": progress.item_id,
        "item_type": progress.item_type,
        "item_attempt_id": progress.item_attempt_id,
        "item_bytes_done": (
            None
            if progress.item_bytes_done is None
            else scalar_64_to_text(progress.item_bytes_done, "progress item_bytes_done")
        ),
        "item_bytes_total": (
            None
            if progress.item_bytes_total is None
            else scalar_64_to_text(progress.item_bytes_total, "progress item_bytes_total")
        ),
    }


def _phase_to_dict(phase: PhaseResult) -> dict[str, object]:
    return {
        "phase": phase.phase,
        "status": phase.status.value,
        "items_done": phase.items_done,
        "items_total": phase.items_total,
        "bytes_done": scalar_64_to_text(phase.bytes_done, "phase bytes_done"),
        "bytes_total": (
            None
            if phase.bytes_total is None
            else scalar_64_to_text(phase.bytes_total, "phase bytes_total")
        ),
        "error": phase.error,
    }


def _phase_from_dict(data: Mapping[str, object]) -> PhaseResult:
    return PhaseResult(
        phase=_text(data["phase"], "phase name"),
        status=PhaseStatus(_text(data["status"], "phase status")),
        items_done=_int(data["items_done"], "phase items_done"),
        items_total=_optional_int(data["items_total"], "phase items_total"),
        bytes_done=scalar_64_from_text(data["bytes_done"], "phase bytes_done"),
        bytes_total=_optional_scalar(data["bytes_total"], "phase bytes_total"),
        error=_optional_text(data["error"], "phase error"),
    )


def _review_fact_to_dict(value: ReviewFactLimitExceeded) -> dict[str, object]:
    return {
        "reason": value.reason,
        "tree_kind": value.tree_kind.value,
        "population": value.population.value,
        "axis": value.axis.value,
        "row_limit": value.row_limit,
        "byte_limit": (
            None
            if value.byte_limit is None
            else scalar_64_to_text(value.byte_limit, "review byte_limit")
        ),
    }


def _review_fact_from_dict(data: Mapping[str, object]) -> ReviewFactLimitExceeded:
    return ReviewFactLimitExceeded(
        reason=_text(data["reason"], "review reason"),
        tree_kind=ReviewTreeKind(_text(data["tree_kind"], "review tree_kind")),
        population=ReviewPopulation(_text(data["population"], "review population")),
        axis=ReviewLimitAxis(_text(data["axis"], "review axis")),
        row_limit=_optional_int(data["row_limit"], "review row_limit"),
        byte_limit=_optional_scalar(data["byte_limit"], "review byte_limit"),
    )


def _require_nonempty_text(value: object, context: str) -> str:
    result = _text(value, context)
    if not result:
        raise ValueError(f"{context} must be non-empty")
    return result


def _text(value: object, context: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{context} must be text")
    return value


def _optional_text(value: object, context: str) -> str | None:
    return None if value is None else _text(value, context)


def _int(value: object, context: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{context} must be a non-Boolean integer")
    return value


def _optional_int(value: object, context: str) -> int | None:
    return None if value is None else _int(value, context)


def _optional_scalar(value: object, context: str) -> int | None:
    return None if value is None else scalar_64_from_text(value, context)


def _bool(value: object, context: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{context} must be a boolean")
    return value


def _datetime(value: object, context: str) -> datetime:
    try:
        result = datetime.fromisoformat(_text(value, context))
    except ValueError as error:
        raise ValueError(f"{context} must be an ISO-8601 datetime") from error
    _require_utc(result, context)
    return result


def _require_utc(value: datetime, context: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{context} must be a datetime")
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError(f"{context} must be UTC")


def _plain_object(value: object, context: str) -> dict[str, object]:
    if type(value) is not dict:
        raise TypeError(f"{context} must be a plain object")
    return value


def _plain_list(value: object, context: str) -> list[object]:
    if type(value) is not list:
        raise TypeError(f"{context} must be an array")
    return value
