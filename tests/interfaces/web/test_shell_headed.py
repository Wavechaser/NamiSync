"""Installed-wheel headed evidence for the Slice 4 SH-G-7 shell."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

import _shell_gate_child as shell_child
from conftest import HeadedInstalledWheel
from namisync.version import VERSION
from _headed_native import (
    clean_child_environment,
    close_window,
    read_text,
    require_absolute_local_test_root,
    scenario_deadline,
    start_headed_process,
    terminate_process_tree,
    wait_for_accessible_text,
    wait_for_process,
    wait_for_window,
)


_CHILD = Path(__file__).with_name("_shell_gate_child.py")
_WHEEL_PREFIX = "namisync/interfaces/web/assets/"


@dataclass(slots=True)
class _ShellGate:
    installed: HeadedInstalledWheel
    root: Path
    result_value: dict[str, object] | None = None

    def result(self) -> dict[str, object]:
        if self.result_value is None:
            self.result_value = _run_shell_scenario(self.installed, self.root)
        return self.result_value


@pytest.fixture(scope="session")
def shell_gate_evidence(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path_factory: pytest.TempPathFactory,
) -> _ShellGate:
    root = require_absolute_local_test_root(
        tmp_path_factory.mktemp("shell-gate")
    )
    return _ShellGate(headed_installed_wheel, root)


def test_shell_gate_child_preserves_the_production_stack_and_is_bounded() -> None:
    source = _CHILD.read_text(encoding="utf-8")
    launch = inspect.getsource(_run_shell_scenario)
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
    assert "host.run_desktop(" in source
    assert "AppPaths.from_root(arguments.data_dir)" in source
    assert "DesktopInstanceIdentity(arguments.mutex, arguments.title)" in source
    assert "original(window)" in source
    assert '"Input.dispatchKeyEvent"' in source
    assert '"Emulation.setEmulatedMedia"' in source
    assert "ZoomFactor = 2.0" in source
    assert 'await import("/tree.js")' in source
    assert "fingerprint === JSON.stringify(treeFingerprint(treeRoot))" in source
    assert source.index("controller.commitWindow(currentTwo") < source.index(
        "const secondStaleResult = controller.commitWindow(currentOne"
    )
    assert "CallDevToolsProtocolMethodAsync" in source
    assert "evaluate_js" not in source
    assert "ExecuteScriptAsync" not in source
    assert "SetForegroundWindow" not in source
    assert "set_foreground" not in source.casefold()
    assert "scenario_deadline(75.0)" in launch
    assert launch.count("require_absolute_local_test_root(") >= 2
    assert "start_headed_process(" in launch
    assert "cwd=installed.root" in launch
    assert "terminate_process_tree(process, deadline=deadline)" in launch


def test_shell_gate_report_refuses_private_error_text(tmp_path: Path) -> None:
    recorder = shell_child._Recorder(tmp_path / "result.json")
    recorder.failure("private-path", RuntimeError("C:\\private\\sentinel"))
    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))

    assert result["failure"] == {"stage": "child", "type": "RuntimeError"}
    assert "private" not in json.dumps(result).casefold()
    assert "sentinel" not in json.dumps(result).casefold()


@pytest.mark.headed
def test_sh_g_7_installed_shell_tree_keyboard_reflow_and_forced_colors(
    shell_gate_evidence: _ShellGate,
) -> None:
    result = shell_gate_evidence.result()
    page = result["page"]
    initial = page["initial"]
    final = page["final"]
    tree = final["tree"]

    assert set(initial) == {
        "status",
        "app_live",
        "status_role",
        "status_live",
        "rail_label",
        "rail_heading",
        "rail_empty",
        "work_label",
        "work_heading",
        "work_empty",
        "work_guidance",
        "initial_tree_rows",
        "initial_task_ids",
        "initial_session_ids",
        "active_tag",
        "layout",
    }
    assert {name: value for name, value in initial.items() if name != "layout"} == {
        "status": "Ready",
        "app_live": None,
        "status_role": "status",
        "status_live": "polite",
        "rail_label": "Task navigation",
        "rail_heading": "Tasks",
        "rail_empty": "No tasks are available.",
        "work_label": "Work area",
        "work_heading": "Work area",
        "work_empty": "No task selected.",
        "work_guidance": (
            "Task details will appear here when a task is available."
        ),
        "initial_tree_rows": 0,
        "initial_task_ids": 0,
        "initial_session_ids": 0,
        "active_tag": "BODY",
    }
    layout = initial["layout"]
    assert set(layout) == {
        "rail_left",
        "rail_right",
        "rail_top",
        "rail_bottom",
        "work_left",
        "work_right",
        "work_top",
        "work_bottom",
    }
    assert layout["rail_right"] <= layout["work_left"]
    assert layout["rail_bottom"] > layout["rail_top"]
    assert layout["work_bottom"] > layout["work_top"]
    assert page["first_focus"] == {"label": "Task navigation", "tag": "NAV"}
    assert page["second_focus"] == {"label": "Work area", "tag": "SECTION"}
    assert page["controller_zoom"] == 2.0
    assert final["focused_before_tree"] == "Work area"
    assert final["zoom"] == {
        "stacked": True,
        "cards_positive": True,
        "cards_in_viewport": True,
        "no_horizontal_overflow": True,
        "focused_visible": True,
    }
    assert final["forced"]["active"] is True
    assert final["forced"]["focus_token"] == "Highlight"
    assert final["forced"]["outline_style"] != "none"
    assert float(final["forced"]["outline_width"].removesuffix("px")) >= 2
    assert tree["row_h"] == 28
    assert tree["role"] == "tree"
    assert tree["row_count"] == 256
    assert tree["spacer_count"] == 2
    assert tree["child_count"] == 258
    assert tree["every_row_28"] is True
    assert tree["first_level"] == "1"
    assert tree["first_expanded"] == "true"
    assert tree["leaf_expanded"] is False
    assert tree["stale_reads"] == 0
    assert tree["stale_results"] == [False, False]
    assert tree["stale_unchanged"] is True
    assert tree["text"] == {
        "hostile_exact": True,
        "hostile_bytes": len(shell_child._HOSTILE.encode("utf-8")),
        "hostile_sha256": hashlib.sha256(
            shell_child._HOSTILE.encode("utf-8")
        ).hexdigest(),
        "long_exact": True,
        "long_bytes": len(shell_child._LONG.encode("utf-8")),
        "long_sha256": hashlib.sha256(
            shell_child._LONG.encode("utf-8")
        ).hexdigest(),
    }
    assert final["complete_text"] == shell_child._COMPLETE_TEXT
    assert page["native"] == {
        "ui_thread": True,
        "window_style": {
            "caption": True,
            "thickframe": True,
            "sysmenu": True,
        },
    }


def _run_shell_scenario(
    installed: HeadedInstalledWheel,
    root: Path,
) -> dict[str, object]:
    deadline = scenario_deadline(75.0)
    root = require_absolute_local_test_root(root)
    root.mkdir(parents=True, exist_ok=True)
    data_root = require_absolute_local_test_root(root / "data")
    output = require_absolute_local_test_root(root / "result.json")
    token = uuid4().hex
    title = f"NamiSync Shell {token}"
    process = start_headed_process(
        (
            installed.python,
            _CHILD,
            "--data-dir",
            data_root,
            "--mutex",
            rf"Local\NamiSync.Shell.{token}",
            "--title",
            title,
            "--output",
            output,
        ),
        cwd=installed.root,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    try:
        window = wait_for_window(process, title, deadline=deadline)
        while not output.exists():
            deadline.remaining()
            if process.poll() is not None:
                completed = wait_for_process(process, deadline=deadline)
                raise AssertionError(
                    "shell child exited before reporting; "
                    f"returncode={completed.returncode}"
                )
            time.sleep(0.025)
        interim = json.loads(read_text(output, deadline=deadline))
        if interim.get("phase") == "failure":
            raise AssertionError(f"shell gate failed: {interim.get('failure')!r}")
        assert interim.get("phase") == "complete", interim
        wait_for_accessible_text(
            window,
            shell_child._COMPLETE_TEXT,
            python=installed.python,
            deadline=deadline,
        )
        close_window(window)
        completed = wait_for_process(process, deadline=deadline)
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert completed.stdout == ""
        assert completed.stderr == ""
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)

    result = json.loads(read_text(output, deadline=deadline))
    _assert_report_schema(result)
    assert result["phase"] == "complete"
    assert result["exit_code"] == 0
    assert result["startup_errors"] == []
    assert result["runtime"]["versions"] == {
        "namisync": VERSION,
        "pywebview": "6.2.1",
        "pythonnet": "3.1.0",
    }
    assert Path(result["runtime"]["executable"]).resolve().is_relative_to(
        installed.root.resolve()
    )
    assert Path(result["runtime"]["namisync_file"]).resolve().is_relative_to(
        installed.root.resolve()
    )
    _assert_installed_assets(installed, result["installed_assets"])
    return result


def _assert_report_schema(result: object) -> None:
    assert type(result) is dict
    assert set(result) == {
        "schema_version",
        "phase",
        "startup_errors",
        "runtime",
        "installed_assets",
        "page",
        "exit_code",
    }
    assert type(result["schema_version"]) is int
    assert result["schema_version"] == 1
    assert result["phase"] == "complete"
    assert type(result["exit_code"]) is int
    assert type(result["startup_errors"]) is list
    assert type(result["runtime"]) is dict
    assert type(result["installed_assets"]) is dict
    assert type(result["page"]) is dict
    assert set(result["runtime"]) == {
        "executable",
        "namisync_file",
        "versions",
    }
    assert set(result["runtime"]["versions"]) == {
        "namisync",
        "pywebview",
        "pythonnet",
    }
    assert set(result["page"]) == {
        "initial",
        "first_focus",
        "second_focus",
        "controller_zoom",
        "final",
        "native",
    }
    initial = result["page"]["initial"]
    assert set(initial) == {
        "status",
        "app_live",
        "status_role",
        "status_live",
        "rail_label",
        "rail_heading",
        "rail_empty",
        "work_label",
        "work_heading",
        "work_empty",
        "work_guidance",
        "initial_tree_rows",
        "initial_task_ids",
        "initial_session_ids",
        "active_tag",
        "layout",
    }
    assert set(initial["layout"]) == {
        "rail_left",
        "rail_right",
        "rail_top",
        "rail_bottom",
        "work_left",
        "work_right",
        "work_top",
        "work_bottom",
    }
    for focus_name in ("first_focus", "second_focus"):
        assert set(result["page"][focus_name]) == {"label", "tag"}
    final = result["page"]["final"]
    assert set(final) == {
        "focused_before_tree",
        "zoom",
        "forced",
        "tree",
        "complete_text",
    }
    assert set(final["zoom"]) == {
        "stacked",
        "cards_positive",
        "cards_in_viewport",
        "no_horizontal_overflow",
        "focused_visible",
    }
    assert set(final["forced"]) == {
        "active",
        "focus_token",
        "outline_style",
        "outline_width",
    }
    assert set(final["tree"]) == {
        "row_h",
        "role",
        "row_count",
        "spacer_count",
        "child_count",
        "every_row_28",
        "first_level",
        "first_expanded",
        "leaf_expanded",
        "stale_reads",
        "stale_results",
        "stale_unchanged",
        "text",
    }
    assert set(final["tree"]["text"]) == {
        "hostile_exact",
        "hostile_bytes",
        "hostile_sha256",
        "long_exact",
        "long_bytes",
        "long_sha256",
    }
    assert set(result["page"]["native"]) == {"ui_thread", "window_style"}
    assert set(result["page"]["native"]["window_style"]) == {
        "caption",
        "thickframe",
        "sysmenu",
    }


def _assert_installed_assets(
    installed: HeadedInstalledWheel,
    assets: object,
) -> None:
    assert type(assets) is dict
    assert set(assets) == set(shell_child._ASSETS)
    with zipfile.ZipFile(installed.wheel) as archive:
        for name, evidence in assets.items():
            assert set(evidence) == {"path", "size", "sha256"}
            content = archive.read(_WHEEL_PREFIX + name)
            assert evidence["size"] == len(content)
            assert evidence["sha256"] == hashlib.sha256(content).hexdigest()
            assert Path(evidence["path"]).resolve().is_relative_to(
                installed.root.resolve()
            )
