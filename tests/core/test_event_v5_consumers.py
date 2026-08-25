from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest

from _event_v5_fixtures import (
    SESSION_ID,
    bodies,
    envelope,
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
    LEGACY_CORE_EVENT_SCHEMA_VERSION,
    SUPPORTED_CORE_EVENT_SCHEMA_VERSIONS,
    Envelope,
    PhaseChanged,
    envelope_from_dict,
)
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


def test_first_protocol_stop_keeps_every_live_python_route_on_v4() -> None:
    assert EVENT_V5_SCHEMA_VERSION == 5
    assert CORE_EVENT_SCHEMA_VERSION == 4
    assert LEGACY_CORE_EVENT_SCHEMA_VERSION == 3
    assert SUPPORTED_CORE_EVENT_SCHEMA_VERSIONS == frozenset({3, 4})
    with pytest.raises(ValueError, match="unsupported event schema version"):
        Envelope(
            SessionId(SESSION_ID),
            1,
            datetime.fromisoformat("2026-08-25T00:00:00+00:00"),
            5,
            PhaseChanged("execute"),
        )
    with pytest.raises(ValueError, match="unsupported event schema version"):
        envelope_from_dict(envelope("PhaseChanged"))

    imports = []
    for path in (PROJECT_ROOT / "namisync").rglob("*.py"):
        if path.name == "event_v5.py":
            continue
        if "event_v5" in path.read_text(encoding="utf-8"):
            imports.append(path.relative_to(PROJECT_ROOT).as_posix())
    assert imports == []


def test_dormant_reliable_ceiling_is_the_accepted_bound() -> None:
    assert MAX_RELIABLE_EVENT_CANONICAL_BYTES == 1_048_576
    value = envelope("ItemOutcome")
    validate_event_v5_envelope(deepcopy(value))
