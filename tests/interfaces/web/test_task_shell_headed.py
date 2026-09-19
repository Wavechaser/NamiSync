"""Installed-wheel headed evidence for the M1-4 process-live task shell."""

from __future__ import annotations

import ast
from contextlib import nullcontext
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

import _task_shell_headed_child as child
from _headed_evidence import EvidencePaths, EvidenceReader, require_host_final
from _headed_native import (
    clean_child_environment,
    close_window,
    require_absolute_local_test_root,
    scenario_deadline,
    start_headed_process,
    terminate_process_tree,
    wait_for_accessible_text,
    wait_for_initial_evidence,
    wait_for_process,
    wait_for_window,
)
from conftest import HeadedInstalledWheel
from _plan_again_trace import (
    installed_plan_again_trace, validate_trace_snapshot, verify_restored_assets,
)


_CHILD = Path(__file__).with_name("_task_shell_headed_child.py")


def test_task_shell_child_preserves_the_production_stack_and_bounded_seams() -> None:
    source = _CHILD.read_text(encoding="utf-8")
    launch = inspect.getsource(_run_task_shell_scenario)
    tree = ast.parse(source)
    patched = {
        node.args[1].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "object"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    }

    assert patched == {"_configure_window_appearance", "_production_commands"}
    assert "if plan_again_trace is not None:" in source
    assert "headed_command_extension(host, extension)" in source
    assert "host.run_desktop(" in source
    assert "registry.create_task_shell" in source
    assert 'const freedTaskTitle = "Task 1";' in source
    assert 'freedTaskStatus !== "New task"' in source
    assert 'rows().length === 48 && rowByTitle("Task 49") !== undefined' in source
    assert 'if key == "Enter":' in source
    assert '"type": "keyDown", "text": "\\r", "unmodifiedText": "\\r"' in source
    assert "self._registry().start_plan(" in source
    assert "original_release(*args, **kwargs)" in source
    assert "original_observer_release(session_id)" in source
    assert 'location.reload();' in source
    assert '"Canceling and closing…"' in source
    assert "EvidencePublisher(" in source
    assert "CallDevToolsProtocolMethodAsync" in source
    assert '"Page.captureScreenshot"' in source
    assert '"Input.dispatchKeyEvent"' in source
    assert '"Input.dispatchMouseEvent"' in source
    assert '"rawKeyDown"' in source
    assert '"execution-confirmation-driver.json"' in source
    assert source.count("window.__namiConfirmationExitBarrier = dialog.animate") == 2
    assert source.count("window.__namiConfirmationExitBarrier.pause()") == 2
    assert source.count("window.__namiConfirmationExitBarrier?.finish()") == 2
    assert "window.__namiConfirmationInputEvidence?.liveEnterConfirmed === true" in source
    assert "driver_failure(error, task)" in source
    assert source.count("document.elementFromPoint(point.x, point.y) !== execute") == 3
    assert "evaluate_js" not in source
    assert "ExecuteScriptAsync" not in source
    assert "scenario_deadline(120.0)" in launch
    assert "EvidenceReader(" in launch
    assert "wait_for_initial_evidence(" in launch
    assert "cwd=installed.root" in launch
    assert "terminate_process_tree(process, deadline=deadline)" in launch


def test_task_shell_failure_records_do_not_expose_private_text(tmp_path: Path) -> None:
    paths = EvidencePaths(tmp_path.resolve())
    recorder = child._Recorder(paths)
    recorder.failure("page_probe", RuntimeError(r"C:\private\sentinel"))

    result = EvidenceReader(paths).read_failure()
    assert result == {"failure": {"stage": "page_probe", "type": "RuntimeError"}}
    assert "private" not in json.dumps(result).casefold()

    diagnostic_path = tmp_path / "execution-confirmation-driver.json"
    diagnostic = {
        "actual_control_checkpoint": "plan_ack",
        "active_element": "execute",
        "authoritative_selection_state": "reviewing",
        "task_delivery_session_changed": False,
        "task_delivery_session_released": True,
        "task_delivery_session_state": "completed",
        "task_delivery_start_identity_count": 1,
        "service_session_state": "retired",
        "task_delivery_active_drain_present": False,
        "task_delivery_terminal_delivered": True,
        "task_delivery_terminal_record_present": True,
        "cdp_canceled": False,
        "cdp_faulted": False,
        "dialog_open": False,
        "document_has_focus": True,
        "execute_disabled": False,
        "execute_focused": True,
        "execute_hidden": False,
        "last_driver_step": "wait_cancel",
        "last_method": "Runtime.evaluate",
        "page_confirmation_stage": "execute-ready",
        "preflight_hook_count": 0,
        "runtime_has_exception_details": True,
        "runtime_result_type": "object",
        "trusted_click_count": 0,
        "trusted_keydown_count": 1,
        "trusted_keyup_count": 1,
    }
    child._write_driver_diagnostic(diagnostic_path, diagnostic)
    persisted = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    assert set(persisted) == child._DRIVER_DIAGNOSTIC_KEYS
    assert persisted == diagnostic
    assert "private" not in diagnostic_path.read_text(encoding="utf-8").casefold()


@pytest.mark.headed
@pytest.mark.parametrize("large_window", [False, True], ids=["default", "larger"])
def test_m1_4_installed_task_shell_navigation_closure_and_recovery(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path: Path,
    large_window: bool,
) -> None:
    result = _run_task_shell_scenario(headed_installed_wheel, tmp_path, large_window=large_window)
    report = result["report"]

    assert report["initial"] == {
        "newest": ["Task 48", "Task 47", "Task 46"],
        "setupVisible": True,
        "refusedCount": 48,
        "retainedAfterFailure": True,
        "navigationStayed": True,
        "olderSelectionCleared": True,
        "idleGeometry": {
            "fullWidth": True,
            "closeInset": True,
            "siblingDismiss": True,
            "dismissTransparent": True,
            "createAligned": True,
            "createLargeIcon": True,
        },
        "pointerFocusHidden": True,
        "keyboardFocusVisible": True,
        "independentRail": True,
        "settingsSurface": True,
        "settingsDraftRetained": True,
        "olderAppearance": {
            "current": "page",
            "persistentFill": True,
            "markerWidth": "3px",
            "markerHeight": "32px",
            "markerAccent": True,
            "closeLabel": "Close Task 47",
            "closeEnabled": True,
        },
        "newerAppearance": {
            "current": "page",
            "persistentFill": True,
            "markerWidth": "3px",
            "markerHeight": "32px",
            "markerAccent": True,
            "closeLabel": "Close Task 48",
            "closeEnabled": True,
        },
    }
    assert report["reinjected"] == {
        "count": 47,
        "newest": "Task 47",
        "selected": "Task 47",
        "work": "Task 47",
    }
    busy = report["busy"]
    assert busy["retainedPending"] is True
    assert busy["pending"]["busy_state"] == "canceling"
    assert busy["pending"]["busy_present"] is True
    assert busy["settled"]["busy_present"] is False
    assert busy["settled"]["busy_state"] == "retired"
    assert busy["settled"]["observer_release_calls"] >= 1

    first = report["terminal_first"]
    assert first["count"] == 47
    assert first["status"] == "Completed"
    assert first["before"]["terminal_present"] is True
    assert first["before"]["session_released"] is False
    assert first["before"]["release_waiting"] is True

    second = report["terminal_second"]
    assert second["count_before_close"] == 47
    assert second["status_before_close"] == "Completed"
    assert second["retained"]["release_calls"] > first["before"]["release_calls"]
    assert second["retained"]["terminal_present"] is True
    assert second["retained"]["session_released"] is False
    assert second["released"]["terminal_present"] is True
    assert second["released"]["session_released"] is True
    assert second["released"]["observer_release_calls"] >= 1
    assert second["closed"]["terminal_present"] is False
    assert second["closed"]["task_count"] == 46

    plan_review = report["plan_review"]
    assert plan_review["initial"] == {
        "planningIssuesVisible": True,
        "refusalNotice": True,
        "redundantStatusCountsAbsent": True,
        "requiredBytesVisible": True,
        "rowRiskVisible": False,
        "persistentAcknowledgmentAbsent": True,
        "executeReady": False,
            "rowHeight": "24px",
            "spacerAligned": True,
            "columnsAligned": True,
            "columnOrder": "selection,name,primary,secondary,size,secondary,notes",
            "sortTargetFillsCell": True,
            "headerScrollClear": True,
            "pointerResizeWorked": True,
            "keyboardResizeWorked": True,
            "chevronsVisible": True,
            "changedSortStartsAscending": True,
            "planGeometry": {
                "documentFitsViewport": True,
                "workBodyFitsViewport": True,
                "tableAbsorbsHeight": True,
                "statusActionsVisible": True,
                "actionsShareTitleRow": True,
                "feedbackSharesDetailRow": True,
                "tableHasNoFooter": True,
                "semanticSettingsVisible": True,
                "semanticSettingsAligned": True,
                "searchButtonInset": True,
            },
    }
    assert plan_review["confirmationInput"] == {
        "nativeModal": True,
        "nativeExecuteFocused": True,
        "nativeExecutePointInViewport": True,
        "nativeExecuteHitTested": True,
        "cancelInitiallyFocused": True,
        "appInert": True,
        "popupInert": True,
        "escapeCanceled": True,
        "escapeReturnedFocus": True,
        "reopenExecuteFocused": True,
        "reopenExecutePointInViewport": True,
        "reopenExecuteHitTested": True,
        "reopenCancelInitiallyFocused": True,
        "selectedBeforeBackgroundInput": "Task 48",
        "railScrollBeforeBackgroundInput": 120,
        "firstTabFocusedConfirm": True,
        "secondTabFocusedCancel": True,
        "backgroundPointerBlocked": True,
        "backgroundWheelBlocked": True,
        "focusContained": True,
        "modalStayedOpen": True,
        "closingPointerBlocked": True,
        "liveEnterFocusedConfirm": True,
        "liveEnterConfirmed": True,
        "liveExecuteFocused": True,
        "liveExecutePointInViewport": True,
        "liveExecuteHitTested": True,
    }
    assert plan_review["refused"]["committed"] is True
    assert plan_review["refused"]["unrun"] is True
    assert plan_review["refused"]["message"]
    assert plan_review["planAgainChangedSource"] is True
    assert plan_review["planAgainChangedTarget"] is True
    assert plan_review["capacitySlot"] == {
        "closedTitle": "Task 1",
        "closedStatus": "New task",
        "closedWasSelected": False,
        "closedIdentityRemoved": True,
        "retainedSelectedTask": True,
        "countBeforePlanAgain": 47,
        "countAfterPlanAgain": 48,
        "newTaskTitle": "Task 49",
    }
    assert plan_review["paused"] is True
    assert plan_review["resumed"] is True
    assert plan_review["canceled"] is True
    assert plan_review["emptyPlanMessage"] is True
    assert plan_review["emptyPlanGeometry"] == {
        "documentFitsViewport": True,
        "workBodyFitsViewport": True,
        "tableAbsorbsHeight": True,
        "statusActionsVisible": True,
        "actionsShareTitleRow": True,
        "feedbackSharesDetailRow": True,
        "tableHasNoFooter": True,
        "semanticSettingsVisible": True,
        "semanticSettingsAligned": True,
        "searchButtonInset": True,
    }


def _run_task_shell_scenario(
    installed: HeadedInstalledWheel,
    root: Path,
    *,
    large_window: bool = False,
) -> dict[str, object]:
    deadline = scenario_deadline(120.0)
    root = require_absolute_local_test_root(root)
    data_root = require_absolute_local_test_root(root / "data")
    evidence_root = require_absolute_local_test_root(root / "evidence")
    source = require_absolute_local_test_root(root / "source")
    target = require_absolute_local_test_root(root / "target")
    screenshot = require_absolute_local_test_root(
        Path(__file__).resolve().parents[3]
        / "build" / "evidence" / "execution-confirmation.png"
    )
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    screenshot.unlink(missing_ok=True)
    screenshot.with_name("execution-confirmation-driver.json").unlink(missing_ok=True)
    for directory in (root, data_root, evidence_root, source, target):
        directory.mkdir(parents=True, exist_ok=True)
    paths = EvidencePaths(evidence_root)
    reader = EvidenceReader(paths)
    token = uuid4().hex
    title = f"NamiSync Task Shell {token}"
    trace_enabled = os.environ.get("NAMISYNC_PLAN_AGAIN_TRACE") == "1"
    trace_context = installed_plan_again_trace(installed.root) if trace_enabled else nullcontext(None)
    with trace_context as trace_assets:
        if trace_assets is not None:
            (evidence_root / "plan-again-trace-assets.json").write_text(
                json.dumps(trace_assets, sort_keys=True), encoding="utf-8",
            )
        child_arguments = (
            installed.python,
            _CHILD,
            "--data-dir", data_root,
            "--mutex", rf"Local\NamiSync.TaskShell.{token}",
            "--title", title,
            "--evidence-dir", evidence_root,
            "--source", source,
            "--target", target,
            "--screenshot", screenshot,
        ) + (("--plan-again-trace",) if trace_enabled else ()) + (("--large-window",) if large_window else ())
        process = start_headed_process(
            child_arguments, cwd=installed.root,
            environment=clean_child_environment(), deadline=deadline,
        )
        try:
            window = wait_for_window(process, title, deadline=deadline)
            milestone, initial = wait_for_initial_evidence(reader, process, deadline=deadline)
            if milestone == "ready":
                wait_for_accessible_text(
                    window, child._COMPLETE_TEXT, python=installed.python, deadline=deadline,
                )
            close_window(window)
            completed = wait_for_process(process, deadline=deadline)
            final = reader.read_final()
            reader.assert_consistent(require_final=milestone == "ready")
        finally:
            if process.poll() is None:
                terminate_process_tree(process, deadline=deadline)

    if trace_enabled:
        verify_restored_assets(installed.root, trace_assets)
        phases = {"task-47-48", "task-48-49"}
        if "plan_again_browser_trace" in initial:
            validate_trace_snapshot(initial["plan_again_browser_trace"], phases)
            validate_trace_snapshot(initial["plan_again_host_trace"], phases, allow_empty=True)
        elif milestone != "failure" or initial.get("failure", {}).get("stage") not in {
            "page_plan_review_plan_surface", "page_plan_review_plan_offset",
            "page_plan_review_plan_notice", "page_plan_review_plan_force",
            "page_plan_review_plan_ack",
        }:
            raise AssertionError("task-shell Plan-again trace is missing")

    if final is not None:
        require_host_final(final, exit_code=completed.returncode)
    if milestone == "failure":
        raise AssertionError(f"task shell gate failed: {initial!r}")
    assert final is not None
    assert final["host_returned"] is True
    assert "post_ready_failure" not in final
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout == ""
    if completed.stderr:
        raise AssertionError(completed.stderr)
    assert initial["schema_version"] == 1
    assert initial["phase"] == "complete"
    assert initial["startup_errors"] == []
    assert Path(initial["runtime"]["executable"]).resolve().is_relative_to(
        installed.root.resolve()
    )
    assert Path(initial["runtime"]["namisync_file"]).resolve().is_relative_to(
        installed.root.resolve()
    )
    assert initial["runtime"]["versions"] == {
        "namisync": importlib.metadata.version("namisync"),
        "pywebview": "6.2.1",
        "pythonnet": "3.1.0",
    }
    assert screenshot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    return initial
