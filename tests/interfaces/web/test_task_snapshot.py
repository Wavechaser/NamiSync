"""Independent presentation facts for the admitted task-update prefix."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from namisync.core.evidence import Outcome, RecordingStatus
from namisync.core.events import (
    CORE_EVENT_SCHEMA_VERSION, Envelope, Gap, ItemOutcome, PhaseChanged, Progress,
    StateChanged,
)
from namisync.core.execution import TaskRecordingIssue, TaskRecordingIssueReason
from namisync.core.session import (
    OperationResult, PhaseResult, PhaseStatus, SessionId, SessionState,
)
from namisync.interfaces.task_port import TaskEventUpdateView, TaskRecordUpdateView
from namisync.interfaces.web.task_snapshot import TaskPresentationState, TaskSnapshotStage
from namisync.workflows.views import (
    SessionRecordView, operation_result_view, session_event_view,
)


TASK = "task-" + "1" * 32
SESSION = "2" * 32
ITEM_A = "operation-" + "a" * 32
ITEM_B = "operation-" + "b" * 32
ATTEMPT_A = "a" * 32
ATTEMPT_B = "b" * 32


def _event(sequence: int, body: object) -> TaskEventUpdateView:
    view = session_event_view(Envelope(
        SessionId(SESSION), sequence,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        CORE_EVENT_SCHEMA_VERSION, body,
    ))
    return TaskEventUpdateView("event", view)


def _progress(
    *, done: int, total: int | None = 100, item: str | None = None,
    attempt: str | None = None, item_done: int | None = None,
    item_total: int | None = None, phase: str = "execute",
    items_done: int = 0, items_total: int | None = 2,
) -> Progress:
    return Progress(
        phase, items_done, items_total, done, total, None,
        item, "operation" if item is not None else None,
        attempt, item_done, item_total,
    )


def _state() -> TaskPresentationState:
    return TaskPresentationState(TASK, SESSION)


def test_reliable_phase_rejects_disagreement_and_gap_allows_self_described_tail() -> None:
    state = _state().advance(_event(1, PhaseChanged("execute")), 0)
    state = state.advance(_event(2, _progress(done=10)), 1)
    assert state.snapshot()["phase_authority"] == "phase_changed"
    with pytest.raises(ValueError, match="phase"):
        state.advance(_event(3, _progress(done=20, phase="verify")), 2)

    state = state.advance(_event(3, Gap(3)), 2)
    after_gap = state.snapshot()
    assert after_gap["gap_first_missed_seq"] == 3
    assert after_gap["progress"] is None
    assert after_gap["presentation"]["throughput_bytes_per_second"] is None
    state = state.advance(_event(4, _progress(done=5, phase="verify")), 3)
    assert state.snapshot()["phase"] == "verify"
    assert state.snapshot()["phase_authority"] == "progress"
    assert state.snapshot()["gap_first_missed_seq"] == 3


def test_attempt_advancement_high_water_and_lossy_directory_handoff() -> None:
    state = _state().advance(_event(1, _progress(
        done=20, item=ITEM_A, attempt=ATTEMPT_A, item_done=20, item_total=50,
    )), 0)
    state = state.advance(_event(2, _progress(
        done=40, item=ITEM_A, attempt=ATTEMPT_A, item_done=40, item_total=50,
    )), 1)
    with pytest.raises(ValueError, match="attempt regressed"):
        state.advance(_event(3, _progress(
            done=40, item=ITEM_A, attempt=ATTEMPT_A, item_done=30, item_total=50,
        )), 2)
    with pytest.raises(ValueError, match="aggregate regressed"):
        state.advance(_event(3, _progress(
            done=39, item=ITEM_A, attempt=ATTEMPT_A, item_done=39, item_total=50,
        )), 2)

    # Retrying the same item may reset its attempt counter, while its visible
    # item high water and the aggregate high water remain stable.
    state = state.advance(_event(3, _progress(
        done=40, item=ITEM_A, attempt=ATTEMPT_B, item_done=0, item_total=50,
    )), 2)
    assert state.snapshot()["presentation"]["item_percent"] == 80.0
    assert state.snapshot()["presentation"]["aggregate_percent"] == 40.0
    with pytest.raises(ValueError, match="changed item"):
        state.advance(_event(4, _progress(
            done=40, item=ITEM_B, attempt=ATTEMPT_B, item_done=0, item_total=50,
        )), 3)

    # The inactive directory snapshot can be coalesced away. A new identity
    # with its own attempt is a display handoff, not an inferred settlement.
    state = state.advance(_event(4, _progress(
        done=40, item=ITEM_B, attempt=ATTEMPT_A, item_done=0, item_total=50,
    )), 3)
    assert state.snapshot()["active_item"]["item_id"] == ITEM_B
    assert state.snapshot()["gap_first_missed_seq"] is None
    state = state.advance(_event(
        5, ItemOutcome(ITEM_B, "copy", "directory.bin", Outcome.SUCCEEDED),
    ), 4)
    assert state.snapshot()["active_item"] is None
    with pytest.raises(ValueError, match="reactivated"):
        state.advance(_event(6, _progress(
            done=40, item=ITEM_B, attempt=ATTEMPT_A, item_done=0, item_total=50,
        )), 5)


def test_large_byte_counters_stay_exact_decimal_strings() -> None:
    large = 9_007_199_254_740_993
    state = _state().advance(_event(1, _progress(
        done=large, total=large + 2, item=ITEM_A, attempt=ATTEMPT_A,
        item_done=large, item_total=large + 2,
    )), 0)
    snapshot = state.snapshot()
    assert snapshot["progress"]["bytes_done"] == str(large)
    assert snapshot["progress"]["bytes_total"] == str(large + 2)
    assert snapshot["active_item"]["item_bytes_done"] == str(large)
    state = state.advance(_event(2, _progress(
        done=large + 2, total=large + 2,
    )), 1)
    assert state.snapshot()["presentation"]["aggregate_percent"] == 100.0


def test_monotonic_rate_and_eta_reset_on_pause_attempt_gap_and_terminal() -> None:
    state = _state().advance(_event(1, _progress(
        done=0, item=ITEM_A, attempt=ATTEMPT_A, item_done=0, item_total=100,
    )), 0)
    state = state.advance(_event(2, _progress(
        done=20, item=ITEM_A, attempt=ATTEMPT_A, item_done=20, item_total=100,
    )), 2)
    presentation = state.snapshot()["presentation"]
    assert presentation["throughput_bytes_per_second"] == pytest.approx(10.0)
    assert presentation["eta_seconds"] == pytest.approx(8.0)

    state = state.advance(_event(3, StateChanged(SessionState.PAUSED)), 3)
    assert state.snapshot()["presentation"]["throughput_bytes_per_second"] is None
    state = state.advance(_event(4, StateChanged(SessionState.RUNNING)), 4)
    state = state.advance(_event(5, _progress(
        done=30, item=ITEM_A, attempt=ATTEMPT_A, item_done=30, item_total=100,
    )), 5)
    assert state.snapshot()["presentation"]["eta_seconds"] is None
    state = state.advance(_event(6, _progress(
        done=40, item=ITEM_A, attempt=ATTEMPT_A, item_done=40, item_total=100,
    )), 7)
    assert state.snapshot()["presentation"]["throughput_bytes_per_second"] == pytest.approx(5.0)

    state = state.advance(_event(7, _progress(
        done=40, item=ITEM_A, attempt=ATTEMPT_B, item_done=0, item_total=100,
    )), 8)
    assert state.snapshot()["presentation"]["eta_seconds"] is None
    state = state.advance(_event(8, Gap(8)), 9)
    assert state.snapshot()["presentation"]["throughput_bytes_per_second"] is None
    state = state.advance(_record(), 10)
    assert state.snapshot()["phase"] is None
    assert state.snapshot()["presentation"]["eta_seconds"] is None


def test_aggregate_rate_continues_across_item_handoffs_and_outcomes() -> None:
    item_c = "operation-" + "c" * 32
    state = _state().advance(_event(1, _progress(
        done=0, item=ITEM_A, items_total=10,
    )), 0)
    state = state.advance(_event(2, _progress(
        done=10, item=ITEM_A, attempt=ATTEMPT_A, item_done=10, item_total=10,
        items_total=10,
    )), 1)
    presentation = state.snapshot()["presentation"]
    assert presentation["throughput_bytes_per_second"] == pytest.approx(10.0)
    assert presentation["eta_seconds"] == pytest.approx(9.0)

    state = state.advance(_event(3, _progress(
        done=20, item=ITEM_B, attempt=ATTEMPT_B, item_done=10, item_total=10,
        items_done=1, items_total=10,
    )), 2)
    presentation = state.snapshot()["presentation"]
    assert presentation["throughput_bytes_per_second"] == pytest.approx(10.0)
    assert presentation["eta_seconds"] == pytest.approx(8.0)

    state = state.advance(_event(
        4, ItemOutcome(ITEM_B, "copy", "second.bin", Outcome.SUCCEEDED),
    ), 2.5)
    after_outcome = state.snapshot()["presentation"]
    assert after_outcome["throughput_bytes_per_second"] == presentation["throughput_bytes_per_second"]
    assert after_outcome["eta_seconds"] == presentation["eta_seconds"]
    state = state.advance(_event(5, _progress(
        done=30, item=item_c, attempt="c" * 32, item_done=10, item_total=10,
        items_done=2, items_total=10,
    )), 3)
    presentation = state.snapshot()["presentation"]
    assert presentation["throughput_bytes_per_second"] == pytest.approx(10.0)
    assert presentation["eta_seconds"] == pytest.approx(7.0)


def test_replay_of_old_prefix_keeps_newer_native_revision_and_rate() -> None:
    first = _event(1, _progress(done=10))
    second = _event(2, _progress(done=30))
    state = _state().advance(first, 1).advance(second, 3)
    ahead = state.snapshot()
    replayed = state.advance(first, 100).advance(second, 101)
    assert replayed is state
    assert replayed.snapshot() == ahead
    replayed = replayed.advance(_event(1, Gap(1)), 102)
    assert replayed.snapshot()["progress"]["bytes_done"] == "30"
    assert replayed.snapshot()["gap_first_missed_seq"] == 1
    assert replayed.snapshot()["presentation"]["throughput_bytes_per_second"] is None
    state = replayed.advance(_event(3, _progress(done=40)), 5)
    assert state.snapshot()["progress"]["bytes_done"] == "40"
    assert state.snapshot()["revision"] > ahead["revision"]


def _record() -> TaskRecordUpdateView:
    result = OperationResult(
        SessionState.FAILED,
        recording=RecordingStatus.DEGRADED,
        audit=RecordingStatus.DEGRADED,
        items=(ItemOutcome(ITEM_A, "copy", "file.bin", Outcome.FAILED),),
        phases=(PhaseResult("execute", PhaseStatus.FAILED, 0, 1, 0, 100),),
        bytes_done=0,
        bytes_total=100,
        recording_issues=(TaskRecordingIssue(TaskRecordingIssueReason.FINAL_FLUSH_FAILED),),
    )
    return TaskRecordUpdateView("record", SessionRecordView(
        SESSION, "sync-execution", "failed", True,
        "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:01+00:00",
        "2026-01-01T00:00:02+00:00", operation_result_view(result),
    ))


def test_gap_and_terminal_preserve_independent_axes_without_item_completeness() -> None:
    state = _state().advance(_event(1, Gap(1)), 0)
    state = state.advance(_record(), 1)
    snapshot = state.snapshot()
    result = snapshot["terminal_result"]
    assert snapshot["session_state"] == "failed"
    assert snapshot["gap_first_missed_seq"] == 1
    assert result["filesystem"] == "failed"
    assert result["recording"] == "degraded"
    assert result["audit"] == "degraded"
    assert len(result["phases"]) == 1
    assert len(result["recording_issues"]) == 1
    assert "items" not in result
    assert snapshot["active_item"] is None
    assert snapshot["ended_at"] == "2026-01-01T00:00:02+00:00"


def test_published_snapshot_detaches_progress_and_nested_terminal_facts() -> None:
    state = _state().advance(_event(1, _progress(
        done=10, item=ITEM_A, attempt=ATTEMPT_A, item_done=10, item_total=100,
    )), 0)
    published = state.snapshot()
    published["progress"]["bytes_done"] = "999"
    published["active_item"]["item_id"] = "foreign"
    fresh = state.snapshot()
    assert fresh["progress"]["bytes_done"] == "10"
    assert fresh["active_item"]["item_id"] == ITEM_A

    state = state.advance(_record(), 1)
    published = state.snapshot()
    published["terminal_result"]["phases"][0]["status"] = "completed"
    published["terminal_result"]["recording_issues"][0]["reason"] = "changed"
    fresh = state.snapshot()
    assert fresh["terminal_result"]["phases"][0]["status"] == "failed"
    assert fresh["terminal_result"]["recording_issues"][0]["reason"] != "changed"


def test_stage_does_not_change_retained_state_until_prefix_is_accepted() -> None:
    original = _state()
    stage = TaskSnapshotStage(original, lambda: 1.0)
    candidate = stage.consider(_event(1, _progress(done=20)))
    assert original.snapshot()["revision"] == 0
    assert stage.snapshot()["revision"] == 0
    stage.accept(candidate)
    assert stage.snapshot()["progress"]["bytes_done"] == "20"
