"""Primitive-only workflow views shared by every interface."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from namisync.core.events import (
    Envelope,
    ItemOutcome,
    result_item_to_dict,
)
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityOutcome,
    IntegrityResult,
)
from namisync.core.session import OperationResult, ResultItem, SessionRecord
from namisync.db.repositories import InventorySnapshot


class ResultCategory(StrEnum):
    FAILED = "failed"
    PARTIAL = "partial"
    REFUSED = "refused"
    MISMATCH = "mismatch"
    CANCELED = "canceled"
    VERIFICATION_INCOMPLETE = "verification-incomplete"
    DEGRADED = "degraded"
    ALL_NOOP = "all-noop"
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class OperationItemView:
    item_type: str
    phase: str
    item_id: str
    kind: str
    path: str
    result: str
    reason: str | None
    detail: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class IntegrityOutcomeView:
    item_type: str
    phase: str
    item_id: str
    row_id: str
    location_id: str
    kind: str
    path: str
    result: str
    reason: str | None
    detail: str | None
    read_strategy: str | None
    recording: str
    record_disposition: str | None


ResultItemView = OperationItemView | IntegrityOutcomeView


@dataclass(frozen=True, slots=True)
class OperationResultView:
    headline: str
    filesystem: str
    integrity: str
    recording: str
    audit: str
    disposition: str
    canceled: bool
    items: tuple[ResultItemView, ...]
    bytes_done: int
    bytes_total: int
    error: str | None


@dataclass(frozen=True, slots=True)
class SessionEventView:
    session_id: str
    sequence: int
    at: str
    body_type: str
    body: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class SessionRecordView:
    session_id: str
    kind: str
    state: str
    supports_pause: bool
    created_at: str
    started_at: str | None
    ended_at: str | None
    result: OperationResultView | None


@dataclass(frozen=True, slots=True)
class InventoryRowView:
    row_id: str
    location_id: str
    path: str
    path_key: str
    entry_kind: str | None
    presence: str
    size: int | None
    mtime_ns: int | None
    has_baseline: bool
    last_observed_at: str | None
    last_verified_at: str | None
    missing_since: str | None
    acknowledged_at: str | None
    reappeared_at: str | None
    unsupported_reason: str | None


def result_item_view(item: ResultItem) -> ResultItemView:
    data = result_item_to_dict(item)
    if isinstance(item, ItemOutcome):
        detail = data["detail"]
        if not isinstance(detail, Mapping):
            raise TypeError("operation detail must be a mapping")
        return OperationItemView(
            item_type=str(data["item_type"]),
            phase=str(data["phase"]),
            item_id=str(data["item_id"]),
            kind=str(data["kind"]),
            path=str(data["path"]),
            result=str(data["result"]),
            reason=None if data["reason"] is None else str(data["reason"]),
            detail=dict(detail),
        )
    if isinstance(item, IntegrityOutcome):
        return IntegrityOutcomeView(
            item_type=str(data["item_type"]),
            phase=str(data["phase"]),
            item_id=str(data["item_id"]),
            row_id=str(data["row_id"]),
            location_id=str(data["location_id"]),
            kind=str(data["kind"]),
            path=str(data["path"]),
            result=str(data["result"]),
            reason=None if data["reason"] is None else str(data["reason"]),
            detail=None if data["detail"] is None else str(data["detail"]),
            read_strategy=(
                None
                if data["read_strategy"] is None
                else str(data["read_strategy"])
            ),
            recording=str(data["recording"]),
            record_disposition=(
                None
                if data["record_disposition"] is None
                else str(data["record_disposition"])
            ),
        )
    raise TypeError(f"unsupported result item: {type(item).__name__}")


def operation_result_view(result: OperationResult) -> OperationResultView:
    items = tuple(result_item_view(item) for item in result.items)
    integrity = _integrity_axis(result.items)
    return OperationResultView(
        headline=_headline(result, integrity).value,
        filesystem=result.status.value,
        integrity=integrity,
        recording=result.recording.value,
        audit=result.audit.value,
        disposition=result.disposition.value,
        canceled=result.canceled,
        items=items,
        bytes_done=result.bytes_done,
        bytes_total=result.bytes_total,
        error=(
            None
            if result.error is None
            else f"{result.error.type_name}: {result.error.message}"
        ),
    )


def session_event_view(envelope: Envelope) -> SessionEventView:
    body = envelope.body
    if isinstance(body, ResultItem):
        payload: Mapping[str, object] = result_item_to_dict(body)
    else:
        from namisync.core.events import envelope_to_dict

        raw = envelope_to_dict(envelope)["body"]
        if not isinstance(raw, Mapping):
            raise TypeError("serialized event body must be a mapping")
        payload = dict(raw)
    return SessionEventView(
        session_id=str(envelope.session_id),
        sequence=envelope.seq,
        at=envelope.at.isoformat(),
        body_type=type(body).__name__,
        body=payload,
    )


def session_record_view(record: SessionRecord) -> SessionRecordView:
    return SessionRecordView(
        session_id=str(record.session_id),
        kind=record.kind,
        state=record.state.value,
        supports_pause=record.supports_pause,
        created_at=record.created_at.isoformat(),
        started_at=None if record.started_at is None else record.started_at.isoformat(),
        ended_at=None if record.ended_at is None else record.ended_at.isoformat(),
        result=None if record.result is None else operation_result_view(record.result),
    )


def inventory_row_view(row: InventorySnapshot) -> InventoryRowView:
    observed = row.observed
    return InventoryRowView(
        row_id=row.row_id,
        location_id=str(row.location_id),
        path=row.rel_path,
        path_key=row.rel_path_key,
        entry_kind=None if row.entry_kind is None else row.entry_kind.value,
        presence=row.presence.value,
        size=None if observed is None else observed.size,
        mtime_ns=None if observed is None else observed.mtime_ns,
        has_baseline=row.attestation is not None,
        last_observed_at=(
            None if row.last_observed_at is None else row.last_observed_at.isoformat()
        ),
        last_verified_at=(
            None if row.last_verified_at is None else row.last_verified_at.isoformat()
        ),
        missing_since=(
            None if row.missing_since is None else row.missing_since.isoformat()
        ),
        acknowledged_at=(
            None if row.acknowledged_at is None else row.acknowledged_at.isoformat()
        ),
        reappeared_at=(
            None if row.reappeared_at is None else row.reappeared_at.isoformat()
        ),
        unsupported_reason=row.unsupported_reason,
    )


def _integrity_axis(items: tuple[ResultItem, ...]) -> str:
    results = [
        item.result for item in items if isinstance(item, IntegrityOutcome)
    ]
    if not results:
        return "not-run"
    if IntegrityResult.MISMATCHED in results:
        return "mismatch"
    if any(
        value
        in {
            IntegrityResult.ERROR,
            IntegrityResult.CANCELED,
            IntegrityResult.UNSUPPORTED,
        }
        for value in results
    ):
        return "incomplete"
    if IntegrityResult.MODIFIED in results:
        return "modified"
    if IntegrityResult.MISSING in results:
        return "missing"
    if IntegrityResult.BASELINED in results:
        return "baselined"
    return "verified"


def _headline(result: OperationResult, integrity: str) -> ResultCategory:
    operation_outcomes = [
        item.outcome for item in result.items if isinstance(item, ItemOutcome)
    ]
    verify_phase_baseline = any(
        isinstance(item, IntegrityOutcome)
        and item.phase == IntegrityMode.VERIFY.value
        and item.result is IntegrityResult.BASELINED
        for item in result.items
    )
    if result.status.value == "failed":
        return ResultCategory.FAILED
    if any(
        value in {Outcome.FAILED, Outcome.BLOCKED, Outcome.DEFERRED}
        for value in operation_outcomes
    ):
        return ResultCategory.PARTIAL
    if result.status.value == "refused":
        return ResultCategory.REFUSED
    if integrity == "mismatch":
        return ResultCategory.MISMATCH
    if result.canceled:
        return ResultCategory.CANCELED
    if integrity in {"incomplete", "modified", "missing"} or verify_phase_baseline:
        return ResultCategory.VERIFICATION_INCOMPLETE
    if (
        result.recording is RecordingStatus.DEGRADED
        or result.audit is RecordingStatus.DEGRADED
    ):
        return ResultCategory.DEGRADED
    if operation_outcomes and all(
        value is Outcome.SKIPPED for value in operation_outcomes
    ):
        return ResultCategory.ALL_NOOP
    return ResultCategory.SUCCESS
