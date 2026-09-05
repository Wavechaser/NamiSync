from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

import pytest

from _event_v5_fixtures import (
    SESSION_ID,
    UTC_TIMESTAMP_CASES,
    UNICODE_TEXT_CASES,
    bodies,
    cancellation_terminal_cases,
    envelope,
    integrity_item_body,
    maximum_reliable_envelope,
    operation_item_body,
    review_limit_terminal_summary,
    terminal_summary,
)
from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.event_v5 import (
    EVENT_V5_SCHEMA_VERSION,
    MAX_RELIABLE_EVENT_CANONICAL_BYTES,
    validate_event_v5_envelope,
)
from namisync.core.events import (
    CORE_EVENT_SCHEMA_VERSION,
    Envelope,
    ItemOutcome,
    PhaseChanged,
    TerminalSummary,
    canonical_event_bytes,
    envelope_from_dict,
)
from namisync.core.execution import (
    ExecutionReason,
    ItemRecordingReason,
    TaskRecordingIssueReason,
    validate_item_recording_outcome,
)
from namisync.core.integrity import IntegrityReason
from namisync.core.planning import BlockedReason
from namisync.core.scalars import ScalarDomainError
from namisync.core.session import (
    Disposition,
    OperationResult,
    PhaseResult,
    PhaseStatus,
    SessionId,
    SessionState,
    validate_result_cancellation,
)

PROJECT_ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("body_type", tuple(bodies()))
def test_dormant_v5_consumers_accept_each_exact_body(body_type: str) -> None:
    validate_event_v5_envelope(envelope(body_type))


def test_dormant_v5_consumer_accepts_exact_review_limit_terminal() -> None:
    body = {"result": review_limit_terminal_summary()}
    validate_event_v5_envelope(envelope("Terminal", body=body))


def test_canonical_v5_projection_preserves_exact_literal_body_bytes() -> None:
    cases = {
        **{body_type: envelope(body_type) for body_type in bodies()},
        "Terminal.review-limit": envelope(
            "Terminal",
            body={"result": review_limit_terminal_summary()},
        ),
    }
    for name, expected in cases.items():
        expected_bytes = json.dumps(
            expected,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        actual_bytes = canonical_event_bytes(envelope_from_dict(expected))
        assert actual_bytes == expected_bytes, name


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("schema_version", 4),
        ("schema_version", 6),
        ("schema_version", True),
        ("session_id", "A" * 32),
        ("session_id", "0" * 31),
        ("seq", True),
        ("seq", 0),
        ("seq", 9_007_199_254_740_992),
        ("at", "2026-08-25T08:00:00+08:00"),
    ),
)
def test_dormant_v5_envelope_rejects_wrong_epoch_and_scalar_shapes(
    field: str, invalid: object
) -> None:
    value = envelope()
    value[field] = invalid
    with pytest.raises((TypeError, ValueError)):
        validate_event_v5_envelope(value)


def test_v5_envelope_and_decoder_require_an_exact_plain_shape() -> None:
    missing = envelope()
    del missing["at"]
    extra = envelope()
    extra["legacy"] = True
    for value in (missing, extra, tuple(envelope().items())):
        with pytest.raises((TypeError, ValueError)):
            validate_event_v5_envelope(value)

    with pytest.raises(ValueError, match="event envelope"):
        envelope_from_dict(extra)


@pytest.mark.parametrize(
    ("invalid", "error_type"),
    (
        (0, TypeError),
        (True, TypeError),
        ("01", ValueError),
        ("9223372036854775808", ScalarDomainError),
        pytest.param("9" * 5_000, ScalarDomainError, id="long-scalar64"),
    ),
)
def test_event_scalar64_routes_preserve_owner_error_family(
    invalid: object, error_type: type[Exception]
) -> None:
    value = envelope("Progress")
    value["body"]["bytes_done"] = invalid  # type: ignore[index]
    for route in (validate_event_v5_envelope, envelope_from_dict):
        with pytest.raises(error_type) as raised:
            route(deepcopy(value))
        assert type(raised.value) is error_type


@pytest.mark.parametrize(
    "mutation",
    (
        {"recording": "ok"},
        {"recording_reason": None},
        {"recording_detail": "x" * 1_025},
        {"recording_reason": "anonymous"},
        {"detail_omitted_count": True},
    ),
)
def test_dormant_v5_operation_item_rejects_recording_axis_drift(
    mutation: dict[str, object],
) -> None:
    item = operation_item_body()
    item.update(mutation)
    with pytest.raises((TypeError, ValueError)):
        validate_event_v5_envelope(envelope("ItemOutcome", body=item))


@pytest.mark.parametrize(
    ("outcome", "reason"),
    (
        ("succeeded", ItemRecordingReason.RECORD_WRITE_FAILED),
        ("failed", ItemRecordingReason.UNRECORDED_MUTATION),
        ("failed", ItemRecordingReason.RECORDING_PREREQUISITE_FAILED),
    ),
)
def test_dormant_v5_operation_item_accepts_every_recording_reason(
    outcome: str, reason: ItemRecordingReason,
) -> None:
    item = operation_item_body()
    item["result"] = outcome
    item["recording_reason"] = reason.value
    decoded = envelope_from_dict(envelope("ItemOutcome", body=item))

    assert isinstance(decoded.body, ItemOutcome)
    assert decoded.body.outcome is Outcome(outcome)
    assert decoded.body.recording_reason is reason


@pytest.mark.parametrize(
    "reason",
    (
        *(reason.value for reason in ExecutionReason),
        *(reason.value for reason in BlockedReason),
        "blocked-correspondence",
        "blocked-dependency",
        "incomplete-scan",
        "user-deselected",
    ),
)
def test_dormant_v5_operation_item_accepts_every_outcome_reason(reason: str) -> None:
    item = operation_item_body()
    item["reason"] = reason
    validate_event_v5_envelope(envelope("ItemOutcome", body=item))


@pytest.mark.parametrize("reason", tuple(IntegrityReason))
def test_dormant_v5_integrity_item_accepts_every_reason(
    reason: IntegrityReason,
) -> None:
    item = integrity_item_body()
    item["reason"] = reason.value
    validate_event_v5_envelope(envelope("IntegrityOutcome", body=item))


@pytest.mark.parametrize(
    ("key", "value"),
    (
        *((key, "value") for key in (
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
        )),
        *((key, "folder\\file.bin") for key in (
            "backup_path",
            "mutation_destination",
            "prior_path",
            "published_path",
            "trash_path",
        )),
        ("continued", True),
        ("durability_warnings", ["warning"]),
        ("incomplete_sides", ["source", "target"]),
        ("excluded_dependencies", ["0" * 32]),
    ),
)
def test_dormant_v5_operation_detail_accepts_every_declared_key(
    key: str,
    value: object,
) -> None:
    item = operation_item_body()
    item["detail"] = {key: value}
    validate_event_v5_envelope(envelope("ItemOutcome", body=item))


def test_dormant_v5_operation_detail_accepts_exact_leaf_and_path_bounds() -> None:
    item = operation_item_body()
    item["detail"] = {"durability_warnings": ["warning"] * 32}
    validate_event_v5_envelope(envelope("ItemOutcome", body=item))

    item["detail"] = {
        "backup_path": "x" * 32_767,
        "mutation_destination": "x" * 32_767,
        "prior_path": "x" * 32_767,
        "published_path": "x" * 32_767,
        "trash_path": "x" * 32_767,
    }
    validate_event_v5_envelope(envelope("ItemOutcome", body=item))

    item["detail"] = {"durability_warnings": ["warning"] * 33}
    with pytest.raises(ValueError, match="cardinality|leaf"):
        validate_event_v5_envelope(envelope("ItemOutcome", body=item))
    item["detail"] = {"published_path": "x" * 32_768}
    with pytest.raises(ValueError, match="UTF-16"):
        validate_event_v5_envelope(envelope("ItemOutcome", body=item))


@pytest.mark.parametrize(
    "detail",
    (
        {"undeclared": "value"},
        {"message": {"nested": "object"}},
        {"message": Path("collaborator.txt")},
        {"message": 42},
        {"message": "x" * 1_025},
        {"published_path": "\ud800"},
        {"excluded_dependencies": ["0" * 32] * 33},
    ),
)
def test_dormant_v5_operation_detail_rejects_unbounded_or_arbitrary_values(
    detail: object,
) -> None:
    item = operation_item_body()
    item["detail"] = detail
    with pytest.raises((TypeError, ValueError)):
        validate_event_v5_envelope(envelope("ItemOutcome", body=item))


def test_dormant_v5_terminal_recording_is_derived_from_exact_witnesses() -> None:
    clean = terminal_summary()
    clean["recording"] = "ok"
    clean["recording_degraded_items"] = 0
    clean["recording_issues"] = []
    validate_event_v5_envelope(
        envelope("Terminal", body={"result": clean})
    )

    for mutation in (
        {"recording": "ok"},
        {"recording_degraded_items": 0, "recording_issues": []},
        {
            "recording_issues": [
                {"reason": "final-flush-failed", "detail": None},
                {"reason": "final-flush-failed", "detail": "again"},
            ]
        },
    ):
        invalid = terminal_summary()
        invalid.update(mutation)
        with pytest.raises((TypeError, ValueError)):
            validate_event_v5_envelope(
                envelope("Terminal", body={"result": invalid})
            )


@pytest.mark.parametrize("reason", tuple(TaskRecordingIssueReason))
def test_dormant_v5_terminal_accepts_every_task_recording_issue_reason(
    reason: TaskRecordingIssueReason,
) -> None:
    result = terminal_summary()
    result["recording_degraded_items"] = 0
    result["recording_issues"] = [{"reason": reason.value, "detail": None}]
    validate_event_v5_envelope(envelope("Terminal", body={"result": result}))


@pytest.mark.parametrize(
    ("tree_kind", "population", "axis", "row_limit", "byte_limit"),
    (
        *(
            (tree_kind, population, "rows", 120_000, None)
            for tree_kind in ("plan", "inventory")
            for population in ("domain", "informational")
        ),
        ("plan", "domain", "retained-bytes", None, "134217728"),
        ("plan", "informational", "retained-bytes", None, "201326592"),
        ("inventory", "domain", "retained-bytes", None, "201326592"),
        ("inventory", "informational", "retained-bytes", None, "201326592"),
        (
            "plan",
            "domain",
            "logical-bytes",
            None,
            "9223372036854775807",
        ),
    ),
)
def test_dormant_v5_accepts_every_review_limit_population_and_axis(
    tree_kind: str,
    population: str,
    axis: str,
    row_limit: int | None,
    byte_limit: str | None,
) -> None:
    result = review_limit_terminal_summary()
    result["review_fact_limit"] = {
        "reason": "review_fact_limit_exceeded",
        "tree_kind": tree_kind,
        "population": population,
        "axis": axis,
        "row_limit": row_limit,
        "byte_limit": byte_limit,
    }
    validate_event_v5_envelope(envelope("Terminal", body={"result": result}))


@pytest.mark.parametrize(
    "fact",
    (
        {
            "reason": "review_fact_limit_exceeded",
            "tree_kind": "plan",
            "population": "domain",
            "axis": "rows",
            "row_limit": None,
            "byte_limit": None,
        },
        {
            "reason": "review_fact_limit_exceeded",
            "tree_kind": "plan",
            "population": "domain",
            "axis": "retained-bytes",
            "row_limit": 120_000,
            "byte_limit": "134217728",
        },
        {
            "reason": "review_fact_limit_exceeded",
            "tree_kind": "inventory",
            "population": "domain",
            "axis": "logical-bytes",
            "row_limit": None,
            "byte_limit": "9223372036854775807",
        },
    ),
)
def test_dormant_v5_rejects_invalid_review_limit_nullability_and_axis(
    fact: dict[str, object],
) -> None:
    result = review_limit_terminal_summary()
    result["review_fact_limit"] = fact
    with pytest.raises((TypeError, ValueError)):
        validate_event_v5_envelope(envelope("Terminal", body={"result": result}))


@pytest.mark.parametrize(
    "mutation",
    (
        {"status": "completed"},
        {"disposition": "ran"},
        {"bytes_total": "1"},
        {"recording_degraded_items": 1, "recording": "degraded"},
        {"omitted_detail_count": 1},
        {"error": {"type_name": "Limit", "message": "wrong axis"}},
    ),
)
def test_dormant_v5_review_limit_requires_exact_refused_unrun_truth(
    mutation: dict[str, object],
) -> None:
    result = review_limit_terminal_summary()
    result.update(mutation)
    with pytest.raises((TypeError, ValueError)):
        validate_event_v5_envelope(
            envelope("Terminal", body={"result": result})
        )


def test_python_event_protocol_uses_current_v5_contract() -> None:
    assert EVENT_V5_SCHEMA_VERSION == 5
    assert CORE_EVENT_SCHEMA_VERSION == 5
    assert {outcome.value for outcome in Outcome} == {
        "succeeded", "skipped", "failed", "canceled", "deferred", "blocked",
    }
    expected = Envelope(
        SessionId(SESSION_ID),
        3,
        datetime.fromisoformat("2026-08-25T00:00:00+00:00"),
        5,
        PhaseChanged("execute"),
    )
    assert envelope_from_dict(envelope("PhaseChanged")) == expected


@pytest.mark.parametrize("version", (3, 4, 6, True))
def test_live_python_route_refuses_each_non_v5_version_class(
    version: object,
) -> None:
    value = envelope("PhaseChanged")
    value["schema_version"] = version
    with pytest.raises((TypeError, ValueError), match="schema version|exactly 5"):
        envelope_from_dict(value)


def test_dormant_reliable_ceiling_accepts_the_exact_bound_and_refuses_one_more() -> None:
    assert MAX_RELIABLE_EVENT_CANONICAL_BYTES == 1_048_576
    value = maximum_reliable_envelope()
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert len(encoded) == MAX_RELIABLE_EVENT_CANONICAL_BYTES
    validate_event_v5_envelope(deepcopy(value))

    oversized = deepcopy(value)
    oversized["body"]["path"] += "x"  # type: ignore[index,operator]
    with pytest.raises(ValueError, match="canonical byte ceiling"):
        validate_event_v5_envelope(oversized)


@pytest.mark.parametrize(
    ("reason", "accepted_outcomes"),
    (
        (ItemRecordingReason.RECORD_WRITE_FAILED,
         frozenset({Outcome.SUCCEEDED, Outcome.SKIPPED})),
        (ItemRecordingReason.UNRECORDED_MUTATION, frozenset({Outcome.FAILED})),
        (ItemRecordingReason.RECORDING_PREREQUISITE_FAILED,
         frozenset({Outcome.FAILED})),
    ),
    ids=("record-write-failed", "unrecorded-mutation", "prerequisite-failed"),
)
def test_item_recording_reason_allows_exact_outcomes(
    reason: ItemRecordingReason,
    accepted_outcomes: frozenset[Outcome],
) -> None:
    for outcome in (*Outcome, None):
        with (
            nullcontext()
            if outcome in accepted_outcomes
            else pytest.raises(ValueError, match="contradicts")
        ):
            validate_item_recording_outcome(outcome, reason)


@pytest.mark.parametrize(
    ("recording", "reason", "detail", "accepted"),
    (
        (RecordingStatus.OK, None, None, True),
        (RecordingStatus.OK, ItemRecordingReason.RECORD_WRITE_FAILED, None, False),
        (RecordingStatus.OK, None, "detail", False),
        (RecordingStatus.DEGRADED, None, None, False),
        (RecordingStatus.DEGRADED,
         ItemRecordingReason.RECORD_WRITE_FAILED, None, True),
        (RecordingStatus.DEGRADED,
         ItemRecordingReason.RECORD_WRITE_FAILED, "detail", True),
        (RecordingStatus.DEGRADED,
         ItemRecordingReason.UNRECORDED_MUTATION, None, False),
    ),
    ids=(
        "ok", "ok-with-reason", "ok-with-detail", "degraded-without-reason",
        "degraded", "degraded-with-detail", "degraded-outcome-mismatch",
    ),
)
def test_item_outcome_enforces_recording_shape_and_policy(
    recording: RecordingStatus,
    reason: ItemRecordingReason | None,
    detail: str | None,
    accepted: bool,
) -> None:
    with nullcontext() if accepted else pytest.raises(ValueError):
        ItemOutcome(
            item_id="1" * 32,
            kind="copy",
            path="file.bin",
            outcome=Outcome.SUCCEEDED,
            recording=recording,
            recording_reason=reason,
            recording_detail=detail,
        )


def test_event_item_applies_recording_outcome_policy() -> None:
    item = operation_item_body()
    item["recording_reason"] = ItemRecordingReason.UNRECORDED_MUTATION.value

    with pytest.raises(ValueError, match="contradicts"):
        validate_event_v5_envelope(envelope("ItemOutcome", body=item))


def _cancellation_phases(summary: dict[str, object]) -> tuple[PhaseResult, ...]:
    return tuple(
        PhaseResult(phase["phase"], PhaseStatus(phase["status"]), 0, 0, 0, 0)
        for phase in summary["phases"]
    )


@pytest.mark.parametrize(
    ("name", "accepted", "summary"),
    cancellation_terminal_cases(),
    ids=[case[0] for case in cancellation_terminal_cases()],
)
def test_result_cancellation_policy_owns_every_declared_case(
    name: str,
    accepted: bool,
    summary: dict[str, object],
) -> None:
    phases = _cancellation_phases(summary)
    with nullcontext() if accepted else pytest.raises(ValueError):
        validate_result_cancellation(
            SessionState(summary["status"]),
            Disposition(summary["disposition"]),
            summary["canceled"],
            next((p.status for p in phases if p.phase == "execute"), None),
            next((p.status for p in phases if p.phase == "verify"), None),
        )


_CANCELLATION_CONSUMER_CASES = (
    "plain-completed", "plain-refused", "unrun-cancel", "compound-failed",
    "compound-reversed", "compound-third-phase", "canceled-without-flag",
    "refused-canceled", "refused-ran", "canceled-completed-execute",
    "unrun-completed-cancel", "compound-wrong-execute",
    "failed-wrong-execute", "compound-missing-verify",
)


@pytest.mark.parametrize("route", ("result", "summary", "envelope", "decoder"))
def test_cancellation_consumers_preserve_policy_axes(route: str) -> None:
    cases = {
        name: (accepted, summary)
        for name, accepted, summary in cancellation_terminal_cases()
    }
    for name in _CANCELLATION_CONSUMER_CASES:
        accepted, summary = cases[name]
        phases = _cancellation_phases(summary)
        fields = {
            "status": SessionState(summary["status"]),
            "recording": RecordingStatus.OK,
            "audit": RecordingStatus.OK,
            "disposition": Disposition(summary["disposition"]),
            "canceled": summary["canceled"],
            "phases": phases,
            "bytes_done": 0,
            "bytes_total": 0,
            "error": None,
            "recording_issues": (),
            "omitted_detail_count": 0,
            "review_fact_limit": None,
        }
        serialized = envelope("Terminal", body={"result": summary})
        with nullcontext() if accepted else pytest.raises(ValueError):
            if route == "result":
                OperationResult(**fields)
            elif route == "summary":
                TerminalSummary(recording_degraded_items=0, **fields)
            elif route == "envelope":
                validate_event_v5_envelope(serialized)
            else:
                decoded = envelope_from_dict(serialized)
                expected = json.dumps(
                    serialized,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                assert canonical_event_bytes(decoded) == expected, name


@pytest.mark.parametrize(
    ("name", "timestamp", "accepted"),
    UTC_TIMESTAMP_CASES,
    ids=[case[0] for case in UTC_TIMESTAMP_CASES],
)
def test_v5_timestamp_grammar_and_calendar_are_exact(
    name: str, timestamp: object, accepted: bool
) -> None:
    value = envelope("PhaseChanged")
    value["at"] = timestamp
    with nullcontext() if accepted else pytest.raises((TypeError, ValueError)):
        validate_event_v5_envelope(value)


def test_v5_decoder_translates_every_accepted_timestamp() -> None:
    for name, timestamp, accepted in UTC_TIMESTAMP_CASES:
        if not accepted:
            continue
        value = envelope("PhaseChanged")
        value["at"] = timestamp

        decoded = envelope_from_dict(value)

        assert decoded.at == datetime.fromisoformat(timestamp), name


@pytest.mark.parametrize("field", ("path", "detail-message"))
@pytest.mark.parametrize(
    ("name", "value", "accepted"),
    UNICODE_TEXT_CASES,
    ids=[case[0] for case in UNICODE_TEXT_CASES],
)
def test_reliable_v5_canonical_bytes_require_real_unicode(
    field: str, name: str, value: str, accepted: bool
) -> None:
    event = envelope("ItemOutcome")
    if field == "detail-message":
        event["body"]["detail"] = {"message": value}
    else:
        event["body"][field] = value
    with nullcontext() if accepted else pytest.raises(ValueError, match="valid Unicode"):
        validate_event_v5_envelope(event)


@pytest.mark.parametrize(
    ("name", "value", "accepted"),
    tuple(
        case
        for case in UNICODE_TEXT_CASES
        if case[0] in {"non-bmp", "lone-high"}
    ),
    ids=("non-bmp", "lone-high"),
)
def test_recording_detail_consumer_invokes_unicode_policy(
    name: str,
    value: str,
    accepted: bool,
) -> None:
    item = operation_item_body()
    item["recording_detail"] = value
    serialized = envelope("ItemOutcome", body=item)
    with nullcontext() if accepted else pytest.raises(ValueError, match="valid Unicode"):
        decoded = envelope_from_dict(serialized)
        assert isinstance(decoded.body, ItemOutcome)
        assert decoded.body.recording_detail == value, name
