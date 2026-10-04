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


def _task_shell_evidence_paths(root: Path) -> tuple[Path, Path]:
    confirmation = require_absolute_local_test_root(root / "execution-confirmation.png")
    return confirmation, confirmation.with_name("execution-confirmation-driver.json")


def test_task_shell_scenarios_own_disjoint_evidence_paths(tmp_path: Path) -> None:
    default = _task_shell_evidence_paths((tmp_path / "default" / "evidence").resolve())
    larger = _task_shell_evidence_paths((tmp_path / "larger" / "evidence").resolve())
    assert set(default).isdisjoint(larger)
    assert default[0].name == larger[0].name == "execution-confirmation.png"
    assert default[1].name == larger[1].name == "execution-confirmation-driver.json"


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
    assert "EvidencePublisher(" in source
    assert "CallDevToolsProtocolMethodAsync" in source
    assert '"Page.captureScreenshot"' in source
    assert '"Input.dispatchKeyEvent"' in source
    assert '"Input.dispatchMouseEvent"' in source
    assert "evaluate_js" not in source
    assert "ExecuteScriptAsync" not in source
    assert "scenario_deadline(" in launch
    assert "EvidenceReader(" in launch
    assert "wait_for_initial_evidence(" in launch
    assert "cwd=installed.root" in launch
    assert "terminate_process_tree(process, deadline=deadline)" in launch


def test_task_shell_move_fixture_reaches_real_cross_parent_planner(tmp_path: Path) -> None:
    from types import SimpleNamespace
    from namisync.core.planning import OperationKind, SyncOptions
    from namisync.core.session import RunContext
    from namisync.workflows import PlanRequest, build_plan_projection
    from namisync.workflows.runtime import LocalWorkflowRuntime

    runtime = LocalWorkflowRuntime(tmp_path / "ledger.db", tmp_path / "history.db")
    try:
        control = child._Control(None, tmp_path / "source", tmp_path / "target")
        control.service = SimpleNamespace(_runtime=runtime)
        control._start_plan_review()
        request = PlanRequest("a" * 32, str(control.source), str(control.target),
                              SyncOptions(propagate_source_casing=True))
        runtime.open_plan(runtime.prepare_plan(request).checkpoint).run(
            RunContext(lambda _event: None, lambda: None),
        )
        artifact = runtime.get_plan(request.request_id)
        moves = tuple(item for item in artifact.plan.operations if item.kind is OperationKind.MOVE)
        assert {(item.target_rel_path, item.prior_target_rel_path) for item in moves} == {
            ("ZzzMove.txt", r"old-root\ZzzMove.txt"),
            (r"move-parent\Move.txt", r"move-parent\old\Move.txt"),
        }
        projection = build_plan_projection(request.request_id, artifact)
        groups = tuple(node for node in projection.nodes if node.row_kind == "prior-group")
        assert {node.move_destination_path for node in groups} == {"", "move-parent"}
        nested = next(node for node in groups if node.move_destination_path == "move-parent")
        assert projection.nodes[nested.parent_index].display == "move-parent"
        assert all(projection.node_for_id(projection.operation_node_id_by_id[str(item.op_id)]).presentation_kind == "move"
                   for item in moves)
    finally:
        runtime.close()


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
        "live_service_state": "running", "review_pending": "",
        "pause_disabled": False, "pause_hidden": False, "resume_hidden": True, "controls_hidden": False,
        "last_driver_step": "wait_cancel",
        "last_method": "Runtime.evaluate",
        "page_confirmation_stage": "execute-ready",
        "preflight_hook_count": 0,
        "runtime_has_exception_details": True,
        "runtime_result_type": "object",
        "trusted_click_count": 0,
        "trusted_keydown_count": 1,
        "trusted_keyup_count": 1,
        "browser_async_error": {"type": "TypeError", "line": 1608},
        "move_bottom_gap": None,
    }
    child._write_driver_diagnostic(diagnostic_path, diagnostic)
    persisted = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    assert set(persisted) == child._DRIVER_DIAGNOSTIC_KEYS
    assert persisted == diagnostic
    assert "private" not in diagnostic_path.read_text(encoding="utf-8").casefold()
    assert child._sanitized_browser_error(
        {"type": "TypeError", "line": 1608, "stack": r"C:\private\sentinel"}
    ) is None
    assert child._sanitized_browser_error({"type": "TypeError", "line": 1608}) == {
        "type": "TypeError", "line": 1608,
    }


def test_task_shell_page_failure_releases_held_fixture_workers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from types import SimpleNamespace
    import sys

    monkeypatch.setitem(sys.modules, "System", SimpleNamespace(Action=lambda callback: callback))
    paths = EvidencePaths(tmp_path.resolve())
    recorder = child._Recorder(paths)
    control = child._Control(recorder, tmp_path / "source", tmp_path / "target")
    control.stage = "busy"
    task = SimpleNamespace(GetAwaiter=lambda: SimpleNamespace(OnCompleted=lambda callback: callback()))
    core = SimpleNamespace(CallDevToolsProtocolMethodAsync=lambda *_args: task)
    native = SimpleNamespace(
        InvokeRequired=False,
        browser=SimpleNamespace(webview=SimpleNamespace(CoreWebView2=core)),
        BeginInvoke=lambda callback: callback(),
    )

    def failed_page(_task: object) -> object:
        raise RuntimeError("busy page probe failed")

    monkeypatch.setattr(child, "_runtime_value", failed_page)
    monkeypatch.setattr(child, "failure_site", lambda _task: {"exception": "Error", "lines": [42]})
    child._begin_probe(
        SimpleNamespace(native=native), recorder, control, [], tmp_path / "execution-confirmation.png",
    )

    assert EvidenceReader(paths).read_failure() == {
        "failure": {"stage": "page_busy", "type": "RuntimeError"},
    }
    assert all(gate.is_set() for gate in (
        control.create_gate, control.busy_gate, control.release_gate,
        control.follow_release, control.execution_release,
    ))


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
        "refusedCloseBeforeEffect": True,
        "singleCloseAfterRetry": True,
        "failureDetail": "Close was refused. Retry close.",
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
    busy = report["busy"]
    assert busy["retainedPending"] is True
    assert busy["pending"]["busy_state"] == "canceling"
    assert busy["pending"]["busy_present"] is True
    assert busy["recovered"]["busy_drain_failures"] == 1
    assert busy["recovered"]["busy_reobservations"] >= 1
    assert busy["recovered"]["busy_present"] is True
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
    assert second["retained"]["release_calls"] == first["before"]["release_calls"]
    assert second["retained"]["terminal_present"] is True
    assert second["retained"]["session_released"] is False
    assert second["released"]["terminal_present"] is True
    assert second["released"]["session_released"] is True
    assert second["released"]["observer_release_calls"] >= 1
    assert second["closed"]["terminal_present"] is False
    assert second["closed"]["task_count"] == 46

    plan_review = report["plan_review"]
    details = plan_review["detailsLayout"]
    assert details["focusRestored"] is True
    assert details["foldedWidths"] == pytest.approx([details["foldedWidths"][0]] * 3, abs=1)
    assert details["expandedWidths"] == pytest.approx([details["expandedWidths"][0]] * 3, abs=1)
    assert details["foldedWidths"][0] > details["expandedWidths"][0] > 0
    header, summary, table, pane = details["rectangles"]
    assert pane[1] == pytest.approx(header[1], abs=1)
    assert pane[3] == pytest.approx(table[3], abs=1)
    assert pane[0] > max(header[2], summary[2], table[2])
    assert 0 < pane[2] - pane[0] <= 24 * details["rem"] + 1
    move_pill = plan_review["movePill"]
    geometry = move_pill["geometry"]
    tolerance = 1 / geometry["devicePixelRatio"]
    assert geometry["row"]["top"] >= geometry["viewport"]["top"] - tolerance
    assert geometry["row"]["bottom"] <= geometry["viewport"]["bottom"] + tolerance
    assert abs(geometry["row"]["height"] - geometry["expectedRowHeight"]) <= tolerance
    assert geometry["firstIndex"] <= geometry["targetIndex"] <= geometry["lastIndex"]
    assert (move_pill["background"], move_pill["foreground"]) in {
        ("rgb(187, 136, 238)", "rgb(51, 17, 85)"),
        ("rgb(51, 17, 85)", "rgb(187, 136, 238)"),
    }
    assert {key: value for key, value in move_pill.items()
            if key not in {"background", "foreground", "geometry"}} == {
        "badgeText": "1 item moved to", "destinationText": "move-parent",
        "destinationInBadge": True, "initiallyCollapsed": True,
        "selectionAbsent": True, "accessibleLabel": "1 item moved to move-parent",
        "collapsed": True, "revealedParent": "move-parent", "rootReveal": True, "filteredFarScroll": True,
    }
    sizing = plan_review["initial"]["passiveSizing"]
    fitted, widened, restored, overflow = (
        sizing[key] for key in ("fitted", "widened", "restored", "overflow")
    )
    width_delta = widened["usableWidth"] - fitted["usableWidth"]
    assert width_delta > 32
    assert widened["widths"][1] - fitted["widths"][1] == pytest.approx(width_delta, abs=1)
    for index in (0, 2, 3, 4, 5, 6):
        assert widened["widths"][index] == pytest.approx(fitted["widths"][index], abs=0.5)
    assert restored["widths"] == pytest.approx(fitted["widths"], abs=0.5)
    for observed in sizing.values():
        assert len(observed["widths"]) == 7
        assert observed["headerLefts"] == pytest.approx(observed["rowLefts"], abs=0.5)
    assert overflow["scrollWidth"] > overflow["clientWidth"]
    assert overflow["scrollLeft"] > 0
    assert {key: value for key, value in plan_review["initial"].items()
            if key != "passiveSizing"} == {
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
        "selectedBeforeBackgroundInput": "Task 53",
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
    assert "Execution preflight refused." in plan_review["refused"]["message"]
    assert "The target has insufficient free space. Free space on its drive." in plan_review["refused"]["message"]
    assert "Resolve these issues, then click Plan again." in plan_review["refused"]["message"]
    assert plan_review["refused"]["executionHeader"] == "Execution did not start"
    assert "Disposition: Unrun" in plan_review["refused"]["executionAxes"]
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
        "newTaskTitle": "Task 54",
    }
    assert plan_review["followNavigation"] == {
        "automaticMoved": True, "nativeOverride": True, "goStayedManual": True,
        "explicitEnable": True, "focusPreserved": True, "selectionPreserved": True,
    }
    assert plan_review["paused"] is True
    assert plan_review["resumed"] is True
    assert plan_review["controlsAppearance"] == {
        "runningNeutral": True, "pauseRegular": True, "sameToggle": True,
        "pausedAccent": True, "playRegular": True, "cancelNeutral": True,
        "stopRegular": True, "cancelArmed": True, "firstClickDidNotCancel": True,
    }
    assert plan_review["canceled"] is True
    assert "Filesystem: Canceled" in plan_review["canceledExecutionHeader"]
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
    screenshot, driver_diagnostic = _task_shell_evidence_paths(evidence_root)
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    screenshot.unlink(missing_ok=True)
    driver_diagnostic.unlink(missing_ok=True)
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
        phases = {"task-52-53", "task-53-54"}
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


@pytest.mark.parametrize("checkpoint", ["plan_surface", "plan_offset", "plan_ack"])
def test_driver_failure_reports_actual_checkpoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, checkpoint: str,
) -> None:
    from types import SimpleNamespace
    import sys

    monkeypatch.setitem(sys.modules, "System", SimpleNamespace(Action=lambda fn: fn))
    transport = SimpleNamespace(evaluate=lambda *_args: None)
    monkeypatch.setattr(child, "NativeCdp", lambda *_args: transport)

    def unavailable(*_args):
        raise RuntimeError("diagnostic transport unavailable")

    paths = EvidencePaths(tmp_path.resolve())
    recorder = child._Recorder(paths)
    control = child._Control(recorder, tmp_path / "source", tmp_path / "target")
    control.checkpoint = checkpoint
    fail = child._drive_plan_confirmation(
        object(), SimpleNamespace(CallDevToolsProtocolMethodAsync=unavailable),
        recorder, control, [], tmp_path / "capture.png",
    )
    fail(RuntimeError("private diagnostic must remain hidden"))
    assert all(gate.is_set() for gate in (
        control.create_gate, control.busy_gate, control.release_gate,
        control.follow_release, control.execution_release,
    ))
    control.checkpoint = "plan_execute"
    fail(ValueError("later timeout must not replace first failure"))
    assert EvidenceReader(paths).read_failure() == {
        "failure": {"stage": f"page_plan_review_{checkpoint}", "type": "RuntimeError"},
    }
    diagnostic = json.loads((tmp_path / "execution-confirmation-driver.json").read_text())
    assert diagnostic["actual_control_checkpoint"] == checkpoint
    assert diagnostic["last_driver_step"] == "wait_move_pill"
    assert "private" not in json.dumps(diagnostic)
