"""Installed-wheel headed evidence for the M1-4 process-live task shell."""

from __future__ import annotations

import ast
import importlib.metadata
import inspect
import json
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

    assert patched == {"_configure_window_appearance"}
    assert "headed_command_extension(host, extension)" in source
    assert "host.run_desktop(" in source
    assert "registry.create_task_shell" in source
    assert "self._registry().start_plan(" in source
    assert "original_release(*args, **kwargs)" in source
    assert "original_observer_release(session_id)" in source
    assert 'location.reload();' in source
    assert '"Canceling and closing…"' in source
    assert "EvidencePublisher(" in source
    assert "CallDevToolsProtocolMethodAsync" in source
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


@pytest.mark.headed
def test_m1_4_installed_task_shell_navigation_closure_and_recovery(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path: Path,
) -> None:
    result = _run_task_shell_scenario(headed_installed_wheel, tmp_path)
    report = result["report"]

    assert report["initial"] == {
        "newest": ["Task 48", "Task 47", "Task 46"],
        "setupVisible": True,
        "refusedCount": 48,
        "retainedAfterFailure": True,
        "navigationStayed": True,
        "olderSelectionCleared": True,
        "olderAppearance": {
            "current": "page",
            "persistentFill": True,
            "markerWidth": "3px",
            "markerAccent": True,
            "closeText": "Close",
            "closeEnabled": True,
        },
        "newerAppearance": {
            "current": "page",
            "persistentFill": True,
            "markerWidth": "3px",
            "markerAccent": True,
            "closeText": "Close",
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


def _run_task_shell_scenario(
    installed: HeadedInstalledWheel,
    root: Path,
) -> dict[str, object]:
    deadline = scenario_deadline(120.0)
    root = require_absolute_local_test_root(root)
    data_root = require_absolute_local_test_root(root / "data")
    evidence_root = require_absolute_local_test_root(root / "evidence")
    source = require_absolute_local_test_root(root / "source")
    target = require_absolute_local_test_root(root / "target")
    for directory in (root, data_root, evidence_root, source, target):
        directory.mkdir(parents=True, exist_ok=True)
    paths = EvidencePaths(evidence_root)
    reader = EvidenceReader(paths)
    token = uuid4().hex
    title = f"NamiSync Task Shell {token}"
    process = start_headed_process(
        (
            installed.python,
            _CHILD,
            "--data-dir", data_root,
            "--mutex", rf"Local\NamiSync.TaskShell.{token}",
            "--title", title,
            "--evidence-dir", evidence_root,
            "--source", source,
            "--target", target,
        ),
        cwd=installed.root,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    try:
        window = wait_for_window(process, title, deadline=deadline)
        milestone, initial = wait_for_initial_evidence(reader, process, deadline=deadline)
        if milestone == "ready":
            wait_for_accessible_text(
                window,
                child._COMPLETE_TEXT,
                python=installed.python,
                deadline=deadline,
            )
        close_window(window)
        completed = wait_for_process(process, deadline=deadline)
        final = reader.read_final()
        reader.assert_consistent(require_final=milestone == "ready")
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)

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
    return initial
