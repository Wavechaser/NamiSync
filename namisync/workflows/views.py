"""Primitive-only workflow views shared by every interface."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from namisync.core.event_v5 import (
    validate_operation_result_view_v5,
    validate_session_event_view_v5,
    validate_session_record_view_v5,
)
from namisync.core.events import (
    Envelope,
    ItemOutcome,
    TerminalSummary,
    result_item_to_dict,
)
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityOutcome,
    IntegrityResult,
)
from namisync.core.planning import OperationKind
from namisync.core.session import (
    OperationResult,
    PhaseResult,
    PhaseStatus,
    ResultItem,
    SessionRecord,
)
from namisync.core.scalars import bounded_utf8_text, scalar_64_to_text
from namisync.db.repositories import InventorySnapshot

from .selection import SELECTION_EXCLUSION_REASONS


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
class ResultClassificationFacts:
    """Primitive facts shared by live and retained result classification."""

    filesystem: str
    recording: str
    audit: str
    canceled: bool
    operation_results: frozenset[str]
    selected_operation_count: int
    selected_other_operation_count: int
    integrity_results: frozenset[str]
    verify_phase_status: str | None
    verify_phase_baseline: bool


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
    recording: str
    recording_reason: str | None
    recording_detail: str | None
    detail_omitted_count: int


@dataclass(frozen=True, slots=True)
class IntegrityOutcomeView:
    item_type: str
    phase: str
    item_id: str
    row_id: str | None
    location_id: str | None
    kind: str
    path: str
    result: str
    reason: str | None
    detail: str | None
    read_strategy: str | None
    recording: str
    record_disposition: str | None
    detail_omitted_count: int


ResultItemView = OperationItemView | IntegrityOutcomeView


@dataclass(frozen=True, slots=True)
class PhaseResultView:
    phase: str
    status: str
    items_done: int
    items_total: int | None
    bytes_done: str
    bytes_total: str | None
    error: str | None


@dataclass(frozen=True, slots=True)
class RecordingIssueView:
    reason: str
    detail: str | None


@dataclass(frozen=True, slots=True)
class ReviewFactLimitView:
    reason: str
    tree_kind: str
    population: str
    axis: str
    row_limit: int | None
    byte_limit: str | None


@dataclass(frozen=True, slots=True)
class OperationResultView:
    headline: str
    filesystem: str
    integrity: str
    recording: str
    audit: str
    disposition: str
    canceled: bool
    phases: tuple[PhaseResultView, ...]
    bytes_done: str
    bytes_total: str
    error: str | None
    recording_degraded_items: int
    recording_issues: tuple[RecordingIssueView, ...]
    omitted_detail_count: int
    presentation_omitted_detail_count: int
    review_refusal: ReviewFactLimitView | None


@dataclass(frozen=True, slots=True)
class SessionEventView:
    session_id: str
    sequence: int
    at: str
    schema_version: int
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


def validate_session_event_view(
    value: object, *, expected_session_id: str | None = None,
) -> None:
    if type(value) is not SessionEventView or not isinstance(value.body, Mapping):
        raise TypeError("session event must be an exact view with a body mapping")
    validate_session_event_view_v5({
        "session_id": value.session_id, "sequence": value.sequence,
        "at": value.at, "schema_version": value.schema_version,
        "body_type": value.body_type, "body": dict(value.body),
    }, expected_session_id=expected_session_id)


def _operation_result_view_data(value: object) -> dict[str, object]:
    if type(value) is not OperationResultView:
        raise TypeError("result must be an exact operation result view")
    if type(value.phases) is not tuple or len(value.phases) > 3:
        raise TypeError("result phases must be a bounded tuple")
    if any(type(phase) is not PhaseResultView for phase in value.phases):
        raise TypeError("result phases must be exact phase result views")
    if type(value.recording_issues) is not tuple or len(value.recording_issues) > 5:
        raise TypeError("recording issues must be a bounded tuple")
    if any(type(issue) is not RecordingIssueView for issue in value.recording_issues):
        raise TypeError("recording issues must be exact recording issue views")
    review = value.review_refusal
    if review is not None and type(review) is not ReviewFactLimitView:
        raise TypeError("review refusal must be an exact review fact limit view")
    return {
        "headline": value.headline, "filesystem": value.filesystem,
        "integrity": value.integrity, "recording": value.recording,
        "audit": value.audit, "disposition": value.disposition,
        "canceled": value.canceled,
        "phases": [{
            "phase": phase.phase, "status": phase.status,
            "items_done": phase.items_done, "items_total": phase.items_total,
            "bytes_done": phase.bytes_done, "bytes_total": phase.bytes_total,
            "error": phase.error,
        } for phase in value.phases],
        "bytes_done": value.bytes_done, "bytes_total": value.bytes_total,
        "error": value.error, "recording_degraded_items": value.recording_degraded_items,
        "recording_issues": [{
            "reason": issue.reason, "detail": issue.detail,
        } for issue in value.recording_issues],
        "omitted_detail_count": value.omitted_detail_count,
        "presentation_omitted_detail_count": value.presentation_omitted_detail_count,
        "review_refusal": None if review is None else {
            "reason": review.reason, "tree_kind": review.tree_kind,
            "population": review.population, "axis": review.axis,
            "row_limit": review.row_limit, "byte_limit": review.byte_limit,
        },
    }


def validate_operation_result_view(value: object) -> None:
    validate_operation_result_view_v5(_operation_result_view_data(value))


def validate_session_record_view(
    value: object, *, expected_session_id: str | None = None,
) -> None:
    if type(value) is not SessionRecordView:
        raise TypeError("session record must be an exact view")
    validate_session_record_view_v5({
        "session_id": value.session_id, "kind": value.kind,
        "state": value.state, "supports_pause": value.supports_pause,
        "created_at": value.created_at, "started_at": value.started_at,
        "ended_at": value.ended_at,
        "result": None if value.result is None else _operation_result_view_data(value.result),
    }, expected_session_id=expected_session_id)


@dataclass(frozen=True, slots=True)
class InventoryRowView:
    row_id: str
    location_id: str
    path: str
    path_key: str
    entry_kind: str | None
    presence: str
    size: str | None
    mtime_ns: str | None
    has_baseline: bool
    last_observed_at: str | None
    last_verified_at: str | None
    missing_since: str | None
    acknowledged_at: str | None
    reappeared_at: str | None
    unsupported_reason: str | None
    verification_state: str
    verification_invalidated_at: str | None
    verification_invalidated_reason: str | None


@dataclass(frozen=True, slots=True)
class PreservationSettingsView:
    preserve_ads: bool
    preserve_created: bool
    preserve_acl: bool

    def __post_init__(self) -> None:
        _require_exact_bool(self.preserve_ads, "preserve_ads")
        _require_exact_bool(self.preserve_created, "preserve_created")
        _require_exact_bool(self.preserve_acl, "preserve_acl")


@dataclass(frozen=True, slots=True)
class SemanticSettingsView:
    filters: tuple[str, ...]
    deletion_policy: str
    trash_on_update: bool
    preservation: PreservationSettingsView
    propagate_source_casing: bool

    def __post_init__(self) -> None:
        _require_filter_tuple(self.filters)
        _require_deletion_policy(self.deletion_policy)
        _require_exact_bool(self.trash_on_update, "trash_on_update")
        if not isinstance(self.preservation, PreservationSettingsView):
            raise TypeError(
                "preservation must be PreservationSettingsView"
            )
        _require_exact_bool(
            self.propagate_source_casing,
            "propagate_source_casing",
        )


@dataclass(frozen=True, slots=True)
class SemanticSettingsPatchView:
    filters: tuple[str, ...] | None = None
    deletion_policy: str | None = None
    trash_on_update: bool | None = None
    preservation: PreservationSettingsView | None = None
    propagate_source_casing: bool | None = None

    def __post_init__(self) -> None:
        if self.filters is not None:
            _require_filter_tuple(self.filters)
        if self.deletion_policy is not None:
            _require_deletion_policy(self.deletion_policy)
        if self.trash_on_update is not None:
            _require_exact_bool(self.trash_on_update, "trash_on_update")
        if (
            self.preservation is not None
            and not isinstance(
                self.preservation,
                PreservationSettingsView,
            )
        ):
            raise TypeError(
                "preservation must be PreservationSettingsView or None"
            )
        if self.propagate_source_casing is not None:
            _require_exact_bool(
                self.propagate_source_casing,
                "propagate_source_casing",
            )


def _require_exact_bool(value: object, field_name: str) -> None:
    if type(value) is not bool:
        raise TypeError(f"{field_name} must be a bool")


def _require_filter_tuple(value: object) -> None:
    if not isinstance(value, tuple) or not all(
        isinstance(pattern, str) for pattern in value
    ):
        raise TypeError("filters must be a tuple of strings")


def _require_deletion_policy(value: object) -> None:
    if not isinstance(value, str) or value not in {"trash", "additive"}:
        raise ValueError("deletion_policy must be trash or additive")


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
            recording=str(data["recording"]),
            recording_reason=(
                None
                if data["recording_reason"] is None
                else str(data["recording_reason"])
            ),
            recording_detail=(
                None
                if data["recording_detail"] is None
                else str(data["recording_detail"])
            ),
            detail_omitted_count=int(data["detail_omitted_count"]),
        )
    if isinstance(item, IntegrityOutcome):
        return IntegrityOutcomeView(
            item_type=str(data["item_type"]),
            phase=str(data["phase"]),
            item_id=str(data["item_id"]),
            row_id=(
                None if data["row_id"] is None else str(data["row_id"])
            ),
            location_id=(
                None
                if data["location_id"] is None
                else str(data["location_id"])
            ),
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
            detail_omitted_count=int(data["detail_omitted_count"]),
        )
    raise TypeError(f"unsupported result item: {type(item).__name__}")


def operation_result_view(result: OperationResult) -> OperationResultView:
    integrity, headline = classify_result_facts(
        _result_classification_facts(result)
    )
    summary = TerminalSummary.from_result(result)
    error = (
        None
        if summary.error is None
        else f"{summary.error.type_name}: {summary.error.message}"
    )
    bounded_error = bounded_utf8_text(error, "result summary error")
    presentation_omitted = int(error is not None and bounded_error is None)
    return OperationResultView(
        headline=headline.value,
        filesystem=summary.status.value,
        integrity=integrity,
        recording=summary.recording.value,
        audit=summary.audit.value,
        disposition=summary.disposition.value,
        canceled=summary.canceled,
        phases=tuple(phase_result_view(phase) for phase in summary.phases),
        bytes_done=scalar_64_to_text(summary.bytes_done, "result bytes_done"),
        bytes_total=scalar_64_to_text(summary.bytes_total, "result bytes_total"),
        error=bounded_error,
        recording_degraded_items=summary.recording_degraded_items,
        recording_issues=tuple(
            RecordingIssueView(issue.reason.value, issue.detail)
            for issue in summary.recording_issues
        ),
        omitted_detail_count=summary.omitted_detail_count,
        presentation_omitted_detail_count=presentation_omitted,
        review_refusal=(
            None
            if summary.review_fact_limit is None
            else ReviewFactLimitView(
                reason=summary.review_fact_limit.reason,
                tree_kind=summary.review_fact_limit.tree_kind.value,
                population=summary.review_fact_limit.population.value,
                axis=summary.review_fact_limit.axis.value,
                row_limit=summary.review_fact_limit.row_limit,
                byte_limit=(
                    None
                    if summary.review_fact_limit.byte_limit is None
                    else scalar_64_to_text(
                        summary.review_fact_limit.byte_limit,
                        "review byte_limit",
                    )
                ),
            )
        ),
    )


def phase_result_view(phase: PhaseResult) -> PhaseResultView:
    return PhaseResultView(
        phase=phase.phase,
        status=phase.status.value,
        items_done=phase.items_done,
        items_total=phase.items_total,
        bytes_done=scalar_64_to_text(phase.bytes_done, "phase bytes_done"),
        bytes_total=(
            None
            if phase.bytes_total is None
            else scalar_64_to_text(phase.bytes_total, "phase bytes_total")
        ),
        error=phase.error,
    )


def session_event_view(envelope: Envelope) -> SessionEventView:
    from namisync.core.events import envelope_to_dict

    body = envelope.body
    raw = envelope_to_dict(envelope)["body"]
    if not isinstance(raw, Mapping):
        raise TypeError("serialized event body must be a mapping")
    payload: Mapping[str, object] = dict(raw)
    return SessionEventView(
        session_id=str(envelope.session_id),
        sequence=envelope.seq,
        at=envelope.at.isoformat(),
        schema_version=envelope.schema_version,
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
        size=(
            None
            if observed is None
            else scalar_64_to_text(observed.size, "inventory size")
        ),
        mtime_ns=(
            None
            if observed is None
            else scalar_64_to_text(observed.mtime_ns, "inventory mtime_ns")
        ),
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
        verification_state=row.verification_state.value,
        verification_invalidated_at=(
            None if row.invalidation is None else row.invalidation.at.isoformat()
        ),
        verification_invalidated_reason=(
            None if row.invalidation is None else row.invalidation.reason.value
        ),
    )


def _result_classification_facts(
    result: OperationResult,
) -> ResultClassificationFacts:
    operation_items = tuple(
        item for item in result.items if isinstance(item, ItemOutcome)
    )
    integrity_items = tuple(
        item for item in result.items if isinstance(item, IntegrityOutcome)
    )
    selected_operation_items = tuple(
        item
        for item in operation_items
        if item.reason not in SELECTION_EXCLUSION_REASONS
    )
    verify_phase = next(
        (
            phase
            for phase in result.phases
            if phase.phase == IntegrityMode.VERIFY.value
        ),
        None,
    )
    return ResultClassificationFacts(
        filesystem=result.status.value,
        recording=result.recording.value,
        audit=result.audit.value,
        canceled=result.canceled,
        operation_results=frozenset(
            item.outcome.value for item in operation_items
        ),
        selected_operation_count=len(selected_operation_items),
        selected_other_operation_count=sum(
            item.kind != OperationKind.NOOP.value
            for item in selected_operation_items
        ),
        integrity_results=frozenset(
            item.result.value for item in integrity_items
        ),
        verify_phase_status=(
            None if verify_phase is None else verify_phase.status.value
        ),
        verify_phase_baseline=any(
            item.phase == IntegrityMode.VERIFY.value
            and item.result is IntegrityResult.BASELINED
            for item in integrity_items
        ),
    )


def classify_result_facts(
    facts: ResultClassificationFacts,
) -> tuple[str, ResultCategory]:
    """Derive the shared integrity axis and single headline from facts."""

    results = facts.integrity_results
    if IntegrityResult.MISMATCHED.value in results:
        integrity = "mismatch"
    elif facts.verify_phase_status in {
        PhaseStatus.FAILED.value,
        PhaseStatus.CANCELED.value,
        PhaseStatus.INCOMPLETE.value,
    }:
        integrity = "incomplete"
    elif not results:
        integrity = "not-run"
    elif results & {
        IntegrityResult.ERROR.value,
        IntegrityResult.CANCELED.value,
        IntegrityResult.UNSUPPORTED.value,
    }:
        integrity = "incomplete"
    elif IntegrityResult.MODIFIED.value in results:
        integrity = "modified"
    elif IntegrityResult.MISSING.value in results:
        integrity = "missing"
    elif IntegrityResult.BASELINED.value in results:
        integrity = "baselined"
    else:
        integrity = "verified"

    operation_results = facts.operation_results
    if facts.filesystem == "failed":
        headline = ResultCategory.FAILED
    elif operation_results & {
        Outcome.FAILED.value,
        Outcome.BLOCKED.value,
        Outcome.DEFERRED.value,
    }:
        headline = ResultCategory.PARTIAL
    elif facts.filesystem == "refused":
        headline = ResultCategory.REFUSED
    elif integrity == "mismatch":
        headline = ResultCategory.MISMATCH
    elif facts.canceled:
        headline = ResultCategory.CANCELED
    elif (
        integrity in {"incomplete", "modified", "missing"}
        or facts.verify_phase_baseline
    ):
        headline = ResultCategory.VERIFICATION_INCOMPLETE
    elif (
        facts.recording == RecordingStatus.DEGRADED.value
        or facts.audit == RecordingStatus.DEGRADED.value
    ):
        headline = ResultCategory.DEGRADED
    elif (
        facts.selected_operation_count > 0
        and facts.selected_other_operation_count == 0
    ):
        headline = ResultCategory.ALL_NOOP
    else:
        headline = ResultCategory.SUCCESS
    return integrity, headline
