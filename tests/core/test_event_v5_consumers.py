from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

import pytest

from _event_v5_fixtures import (
    SESSION_ID,
    bodies,
    envelope,
    integrity_item_body,
    maximum_reliable_envelope,
    operation_item_body,
    review_limit_terminal_summary,
    session_event_view,
    terminal_summary,
)
from namisync.core.event_v5 import (
    EVENT_V5_SCHEMA_VERSION,
    MAX_RELIABLE_EVENT_CANONICAL_BYTES,
    validate_event_v5_envelope,
    validate_session_event_view_v5,
)
from namisync.core.events import (
    CORE_EVENT_SCHEMA_VERSION,
    Envelope,
    PhaseChanged,
    envelope_from_dict,
)
from namisync.core.execution import (
    ExecutionReason,
    ItemRecordingReason,
    TaskRecordingIssueReason,
)
from namisync.core.integrity import IntegrityReason
from namisync.core.planning import BlockedReason
from namisync.core.session import SessionId


PROJECT_ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("body_type", tuple(bodies()))
def test_dormant_v5_consumers_accept_each_exact_body(body_type: str) -> None:
    validate_event_v5_envelope(envelope(body_type))
    validate_session_event_view_v5(
        session_event_view(body_type), expected_session_id=SESSION_ID
    )


def test_dormant_v5_consumer_accepts_exact_review_limit_terminal() -> None:
    body = {"result": review_limit_terminal_summary()}
    validate_event_v5_envelope(envelope("Terminal", body=body))
    validate_session_event_view_v5(
        session_event_view("Terminal", body=body),
        expected_session_id=SESSION_ID,
    )


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


def test_dormant_v5_envelope_requires_an_exact_plain_shape() -> None:
    missing = envelope()
    del missing["at"]
    extra = envelope()
    extra["legacy"] = True
    for value in (missing, extra, tuple(envelope().items())):
        with pytest.raises((TypeError, ValueError)):
            validate_event_v5_envelope(value)


@pytest.mark.parametrize(
    "invalid",
    (
        0,
        True,
        -1,
        "-1",
        "+1",
        "01",
        "1.0",
        "1e3",
        "9223372036854775808",
    ),
)
def test_dormant_v5_progress_rejects_noncanonical_scalar64(
    invalid: object,
) -> None:
    value = envelope("Progress")
    value["body"]["bytes_done"] = invalid  # type: ignore[index]
    with pytest.raises((TypeError, ValueError)):
        validate_event_v5_envelope(value)


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


@pytest.mark.parametrize("reason", tuple(ItemRecordingReason))
def test_dormant_v5_operation_item_accepts_every_recording_reason(
    reason: ItemRecordingReason,
) -> None:
    item = operation_item_body()
    item["recording_reason"] = reason.value
    validate_event_v5_envelope(envelope("ItemOutcome", body=item))


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


def test_dormant_v5_session_view_rejects_another_session() -> None:
    with pytest.raises(ValueError, match="another session"):
        validate_session_event_view_v5(
            session_event_view(), expected_session_id="f" * 32
        )


def test_second_protocol_stop_switches_every_live_python_route_to_v5() -> None:
    assert EVENT_V5_SCHEMA_VERSION == 5
    assert CORE_EVENT_SCHEMA_VERSION == 5
    expected = Envelope(
        SessionId(SESSION_ID),
        3,
        datetime.fromisoformat("2026-08-25T00:00:00+00:00"),
        5,
        PhaseChanged("execute"),
    )
    assert envelope_from_dict(envelope("PhaseChanged")) == expected


@pytest.mark.parametrize("version", (3, 4, 6, True))
def test_live_python_route_refuses_every_non_v5_epoch(version: object) -> None:
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
