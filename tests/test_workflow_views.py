from __future__ import annotations

from datetime import datetime, timezone

import pytest

from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.events import SCHEMA_VERSION, Envelope, ItemOutcome, Progress
from namisync.core.integrity import (
    IntegrityMode,
    IntegrityOutcome,
    IntegrityReason,
    IntegrityResult,
)
from namisync.core.session import (
    Disposition,
    OperationResult,
    PhaseResult,
    PhaseStatus,
    SessionId,
    SessionState,
)
from namisync.workflows.views import operation_result_view, session_event_view


def _operation(outcome: Outcome, *, kind: str = "copy") -> ItemOutcome:
    return ItemOutcome("operation", kind, "file.txt", outcome)


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


def test_session_event_view_preserves_expanded_progress_body() -> None:
    progress = Progress(
        1,
        2,
        7,
        20,
        "folder\\file.bin",
        item_id="operation-1",
        item_type="operation",
        item_bytes_done=7,
        item_bytes_total=10,
    )
    envelope = Envelope(
        SessionId("a" * 32),
        3,
        datetime(2026, 8, 21, tzinfo=timezone.utc),
        SCHEMA_VERSION,
        progress,
    )

    view = session_event_view(envelope)

    assert view.body == {
        "items_done": 1,
        "items_total": 2,
        "bytes_done": 7,
        "bytes_total": 20,
        "current_path": "folder\\file.bin",
        "item_id": "operation-1",
        "item_type": "operation",
        "item_bytes_done": 7,
        "item_bytes_total": 10,
    }


def test_rowless_post_copy_integrity_view_preserves_absent_identity() -> None:
    item = IntegrityOutcome(
        item_id="rowless",
        row_id=None,
        location_id=None,
        path="file.txt",
        result=IntegrityResult.VERIFIED,
        reason=IntegrityReason.RECORDING_ERROR,
        recording=RecordingStatus.DEGRADED,
    )

    view = operation_result_view(
        OperationResult(
            SessionState.COMPLETED,
            recording=RecordingStatus.DEGRADED,
            items=(item,),
        )
    )

    assert view.items[0].row_id is None
    assert view.items[0].location_id is None
    assert view.integrity == "verified"
    assert view.recording == "degraded"


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
                items=(_operation(Outcome.SKIPPED, kind="noop"),),
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


def test_compound_headline_boundaries_and_phase_wide_incomplete_truth() -> None:
    execute = PhaseResult(
        "execute", PhaseStatus.COMPLETED, 1, 1, 7, 7
    )
    canceled_verify = PhaseResult(
        "verify", PhaseStatus.CANCELED, 1, 2, 7, 14
    )
    mismatch = operation_result_view(
        OperationResult(
            SessionState.COMPLETED,
            canceled=True,
            items=(_integrity(IntegrityResult.MISMATCHED),),
            phases=(execute, canceled_verify),
            bytes_done=7,
            bytes_total=7,
        )
    )
    canceled = operation_result_view(
        OperationResult(
            SessionState.COMPLETED,
            canceled=True,
            items=(_integrity(IntegrityResult.CANCELED),),
            phases=(execute, canceled_verify),
            bytes_done=7,
            bytes_total=7,
        )
    )
    incomplete = operation_result_view(
        OperationResult(
            SessionState.COMPLETED,
            phases=(
                execute,
                PhaseResult(
                    "verify",
                    PhaseStatus.INCOMPLETE,
                    0,
                    1,
                    0,
                    7,
                    "RuntimeError: verifier failed before item 1",
                ),
            ),
            bytes_done=7,
            bytes_total=7,
        )
    )

    assert mismatch.headline == "mismatch"
    assert canceled.headline == "canceled"
    assert incomplete.headline == "verification-incomplete"
    assert incomplete.integrity == "incomplete"
    assert incomplete.phases[1].error == (
        "RuntimeError: verifier failed before item 1"
    )


def test_partial_precedes_mismatch_without_hiding_secondary_axes() -> None:
    view = operation_result_view(
        OperationResult(
            SessionState.COMPLETED,
            recording=RecordingStatus.DEGRADED,
            audit=RecordingStatus.DEGRADED,
            items=(
                _operation(Outcome.BLOCKED),
                _integrity(IntegrityResult.MISMATCHED),
            ),
            phases=(
                PhaseResult(
                    "execute", PhaseStatus.COMPLETED, 1, 1, 7, 7
                ),
                PhaseResult(
                    "verify", PhaseStatus.COMPLETED, 1, 1, 7, 7
                ),
            ),
            bytes_done=7,
            bytes_total=7,
        )
    )

    assert view.headline == "partial"
    assert view.filesystem == "completed"
    assert view.integrity == "mismatch"
    assert view.recording == "degraded"
    assert view.audit == "degraded"
