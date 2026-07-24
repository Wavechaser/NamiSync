from __future__ import annotations

import pytest

from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.events import ItemOutcome
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityOutcome,
    IntegrityReason,
    IntegrityResult,
)
from namisync.core.session import (
    Disposition,
    OperationResult,
    SessionState,
)
from namisync.workflows.views import operation_result_view


def _operation(outcome: Outcome) -> ItemOutcome:
    return ItemOutcome("operation", "copy", "file.txt", outcome)


def _integrity(
    result: IntegrityResult,
    *,
    phase: str = IntegrityMode.VERIFY.value,
) -> IntegrityOutcome:
    return IntegrityOutcome(
        "integrity",
        "row",
        "location",
        "file.txt",
        result,
        (
            IntegrityReason.HASH_MISMATCH
            if result is IntegrityResult.MISMATCHED
            else None
        ),
        phase=phase,
    )


@pytest.mark.parametrize(
    ("result", "headline"),
    [
        (
            OperationResult(
                SessionState.FAILED,
                items=(_integrity(IntegrityResult.MISMATCHED),),
            ),
            "failed",
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                items=(
                    _operation(Outcome.BLOCKED),
                    _integrity(IntegrityResult.MISMATCHED),
                ),
            ),
            "partial",
        ),
        (
            OperationResult(
                SessionState.REFUSED,
                disposition=Disposition.UNRUN,
                items=(_integrity(IntegrityResult.MISMATCHED),),
            ),
            "refused",
        ),
        (
            OperationResult(
                SessionState.CANCELED,
                canceled=True,
                items=(_integrity(IntegrityResult.MISMATCHED),),
            ),
            "mismatch",
        ),
        (
            OperationResult(
                SessionState.CANCELED,
                canceled=True,
                items=(_integrity(IntegrityResult.CANCELED),),
            ),
            "canceled",
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                recording=RecordingStatus.DEGRADED,
                items=(_integrity(IntegrityResult.ERROR),),
            ),
            "verification-incomplete",
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                recording=RecordingStatus.DEGRADED,
                items=(_integrity(IntegrityResult.MODIFIED),),
            ),
            "verification-incomplete",
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                audit=RecordingStatus.DEGRADED,
                items=(_integrity(IntegrityResult.MISSING),),
            ),
            "verification-incomplete",
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                recording=RecordingStatus.DEGRADED,
                items=(_integrity(IntegrityResult.BASELINED),),
            ),
            "verification-incomplete",
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                items=(
                    _integrity(
                        IntegrityResult.BASELINED,
                        phase=IntegrityMode.BASELINE.value,
                    ),
                ),
            ),
            "success",
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                items=(
                    _integrity(
                        IntegrityResult.BASELINED,
                        phase=IntegrityMode.REBASELINE.value,
                    ),
                ),
            ),
            "success",
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                recording=RecordingStatus.DEGRADED,
                items=(_integrity(IntegrityResult.MISMATCHED),),
            ),
            "mismatch",
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                recording=RecordingStatus.DEGRADED,
                items=(_operation(Outcome.SKIPPED),),
            ),
            "degraded",
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                items=(_operation(Outcome.SKIPPED),),
            ),
            "all-noop",
        ),
        (
            OperationResult(
                SessionState.COMPLETED,
                items=(_operation(Outcome.SUCCEEDED),),
            ),
            "success",
        ),
    ],
)
def test_result_category_precedence(
    result: OperationResult, headline: str
) -> None:
    assert operation_result_view(result).headline == headline


def test_result_view_keeps_order_tags_and_independent_truth_axes() -> None:
    operation = _operation(Outcome.SUCCEEDED)
    integrity = _integrity(IntegrityResult.MISMATCHED)
    view = operation_result_view(
        OperationResult(
            SessionState.COMPLETED,
            recording=RecordingStatus.DEGRADED,
            audit=RecordingStatus.DEGRADED,
            items=(operation, integrity),
        )
    )

    assert [(item.item_type, item.phase) for item in view.items] == [
        ("operation", "execute"),
        ("integrity", "verify"),
    ]
    assert view.filesystem == "completed"
    assert view.integrity == "mismatch"
    assert view.recording == "degraded"
    assert view.audit == "degraded"
    assert view.headline == "mismatch"
