from __future__ import annotations

import pytest

from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.events import ItemOutcome
from namisync.core.integrity import (
    IntegrityOutcome,
    IntegrityReason,
    IntegrityResult,
)
from namisync.core.session import (
    Disposition,
    OperationResult,
    PhaseResult,
    PhaseStatus,
    SessionState,
)
from namisync.interfaces.cli import (
    EXIT_CANCELED,
    EXIT_DEGRADED,
    EXIT_FAILED,
    EXIT_MISMATCH,
    EXIT_PARTIAL,
    EXIT_REFUSED,
    EXIT_SUCCESS,
    EXIT_VERIFICATION_INCOMPLETE,
    _exit_for_record,
)
from namisync.interfaces.service import SessionRecordView, classify_result
from namisync.workflows.views import operation_result_view


def _operation(
    outcome: Outcome,
    *,
    kind: str = "copy",
    reason: str | None = None,
) -> ItemOutcome:
    return ItemOutcome("operation", kind, "file.bin", outcome, reason=reason)


def _integrity(result: IntegrityResult) -> IntegrityOutcome:
    return IntegrityOutcome(
        "integrity",
        "row",
        "location",
        "file.bin",
        result,
        (
            IntegrityReason.HASH_MISMATCH
            if result is IntegrityResult.MISMATCHED
            else None
        ),
    )


def _incomplete_phase() -> PhaseResult:
    return PhaseResult(
        "verify",
        PhaseStatus.INCOMPLETE,
        0,
        1,
        0,
        7,
        "RuntimeError: verification did not finish",
    )


_EXIT_BY_HEADLINE = {
    "success": EXIT_SUCCESS,
    "all-noop": EXIT_SUCCESS,
    "refused": EXIT_REFUSED,
    "failed": EXIT_FAILED,
    "canceled": EXIT_CANCELED,
    "partial": EXIT_PARTIAL,
    "degraded": EXIT_DEGRADED,
    "mismatch": EXIT_MISMATCH,
    "verification-incomplete": EXIT_VERIFICATION_INCOMPLETE,
}


def _record(result: OperationResult) -> SessionRecordView:
    return SessionRecordView(
        session_id="classification",
        kind="test",
        state="canceled" if result.canceled else result.status.value,
        supports_pause=False,
        created_at="2026-07-25T00:00:00+00:00",
        started_at=None,
        ended_at="2026-07-25T00:00:00+00:00",
        result=operation_result_view(result),
    )


@pytest.mark.parametrize(
    ("boundary", "higher", "lower", "higher_headline", "lower_headline"),
    [
        (
            "failed > partial",
            OperationResult(
                SessionState.FAILED,
                items=(_operation(Outcome.BLOCKED),),
            ),
            OperationResult(
                SessionState.COMPLETED,
                items=(_operation(Outcome.BLOCKED),),
            ),
            "failed",
            "partial",
        ),
        (
            "partial > refused",
            OperationResult(
                SessionState.REFUSED,
                disposition=Disposition.UNRUN,
                items=(_operation(Outcome.BLOCKED),),
            ),
            OperationResult(
                SessionState.REFUSED,
                disposition=Disposition.UNRUN,
            ),
            "partial",
            "refused",
        ),
        (
            "refused > mismatch",
            OperationResult(
                SessionState.REFUSED,
                disposition=Disposition.UNRUN,
                items=(_integrity(IntegrityResult.MISMATCHED),),
            ),
            OperationResult(
                SessionState.COMPLETED,
                items=(_integrity(IntegrityResult.MISMATCHED),),
            ),
            "refused",
            "mismatch",
        ),
        (
            "mismatch > canceled",
            OperationResult(
                SessionState.CANCELED,
                canceled=True,
                items=(_integrity(IntegrityResult.MISMATCHED),),
            ),
            OperationResult(SessionState.CANCELED, canceled=True),
            "mismatch",
            "canceled",
        ),
        (
            "canceled > verification-incomplete",
            OperationResult(
                SessionState.CANCELED,
                canceled=True,
                items=(_integrity(IntegrityResult.ERROR),),
            ),
            OperationResult(
                SessionState.COMPLETED,
                items=(_integrity(IntegrityResult.ERROR),),
            ),
            "canceled",
            "verification-incomplete",
        ),
        (
            "verification-incomplete > degraded",
            OperationResult(
                SessionState.COMPLETED,
                recording=RecordingStatus.DEGRADED,
                phases=(_incomplete_phase(),),
            ),
            OperationResult(
                SessionState.COMPLETED,
                recording=RecordingStatus.DEGRADED,
            ),
            "verification-incomplete",
            "degraded",
        ),
        (
            "degraded > all-noop",
            OperationResult(
                SessionState.COMPLETED,
                recording=RecordingStatus.DEGRADED,
                items=(_operation(Outcome.SKIPPED, kind="noop"),),
            ),
            OperationResult(
                SessionState.COMPLETED,
                items=(_operation(Outcome.SKIPPED, kind="noop"),),
            ),
            "degraded",
            "all-noop",
        ),
    ],
)
def test_each_adjacent_headline_boundary_flips_when_higher_is_removed(
    boundary: str,
    higher: OperationResult,
    lower: OperationResult,
    higher_headline: str,
    lower_headline: str,
) -> None:
    higher_category = classify_result(operation_result_view(higher))
    lower_category = classify_result(operation_result_view(lower))

    assert higher_category.headline == higher_headline, boundary
    assert lower_category.headline == lower_headline, boundary
    assert _exit_for_record(_record(higher)) == _EXIT_BY_HEADLINE[higher_headline]
    assert _exit_for_record(_record(lower)) == _EXIT_BY_HEADLINE[lower_headline]


def test_all_noop_falls_back_to_success_when_no_noop_set_exists() -> None:
    all_noop = OperationResult(
        SessionState.COMPLETED,
        items=(_operation(Outcome.SKIPPED, kind="noop"),),
    )
    success = OperationResult(
        SessionState.COMPLETED,
        items=(_operation(Outcome.SUCCEEDED),),
    )

    assert classify_result(
        operation_result_view(all_noop)
    ).headline == "all-noop"
    assert classify_result(operation_result_view(success)).headline == "success"
    assert _exit_for_record(_record(all_noop)) == EXIT_SUCCESS
    assert _exit_for_record(_record(success)) == EXIT_SUCCESS


def test_compound_partial_keeps_every_secondary_axis_renderable() -> None:
    live = operation_result_view(
        OperationResult(
            SessionState.COMPLETED,
            recording=RecordingStatus.DEGRADED,
            audit=RecordingStatus.DEGRADED,
            items=(
                _operation(Outcome.BLOCKED),
                _integrity(IntegrityResult.MISMATCHED),
            ),
        )
    )

    category = classify_result(live)

    assert category.headline == "partial"
    assert category.filesystem == "completed"
    assert category.integrity == "mismatch"
    assert category.recording == "degraded"
    assert category.audit == "degraded"


def test_zero_bytes_never_replace_typed_disposition_or_headline() -> None:
    ran = classify_result(
        operation_result_view(OperationResult(SessionState.COMPLETED))
    )
    unrun = classify_result(
        operation_result_view(
            OperationResult(
                SessionState.REFUSED,
                disposition=Disposition.UNRUN,
            )
        )
    )

    assert ran.headline == "success"
    assert ran.disposition == "ran"
    assert unrun.headline == "refused"
    assert unrun.disposition == "unrun"
