"""Installed-wheel headed evidence for the Slice 4 SH-G-7 shell."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

import _shell_gate_child as shell_child
from _headed_evidence import EvidencePaths, EvidenceReader, require_host_final
from _tree_window_fixture import (
    TREE_WINDOW_FIXTURE_SCHEMA,
    TreeWindowFixture,
)
from conftest import HeadedInstalledWheel
from namisync.version import VERSION
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


_CHILD = Path(__file__).with_name("_shell_gate_child.py")
_WHEEL_PREFIX = "namisync/interfaces/web/assets/"


@dataclass(slots=True)
class _ShellGate:
    installed: HeadedInstalledWheel
    root: Path
    fixture: TreeWindowFixture
    result_value: dict[str, object] | None = None

    def result(self) -> dict[str, object]:
        if self.result_value is None:
            self.result_value = _run_shell_scenario(
                self.installed,
                self.root,
                self.fixture,
            )
        return self.result_value


@pytest.fixture
def shell_gate_evidence(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path_factory: pytest.TempPathFactory,
    tree_window_fixture: TreeWindowFixture,
) -> _ShellGate:
    root = require_absolute_local_test_root(
        tmp_path_factory.mktemp("shell-gate")
    )
    return _ShellGate(
        headed_installed_wheel,
        root,
        tree_window_fixture,
    )


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
    assert "original(window, *appearance_args, **appearance_kwargs)" in source
    assert '"Input.dispatchKeyEvent"' in source
    assert source.count('press("Tab", "Tab", 9,') == 2
    assert 'document.querySelector("#theme-mode")' in source
    assert '"Input.dispatchMouseEvent"' in source
    assert '"type": "mouseWheel"' in source
    assert "wheel(value, 112, after_scroll_wheel)" in source
    assert "root.style.blockSize = `${2 * ROW_H}px`;" in source
    assert "root.style.blockSize = `${4 * ROW_H}px`;" in source
    assert "request: state.requests[0] ?? null" in source
    assert "state.controller.dispose();" in source
    assert source.index("state.controller.dispose();") < source.index(
        "root.remove();"
    )
    assert '"Emulation.setEmulatedMedia"' in source
    assert '"Accessibility.getFullAXTree"' in source
    assert "ZoomFactor = 2.0" in source
    assert 'await import("/tree.js")' in source
    assert 'parser.add_argument("--tree-fixture", required=True' in source
    assert "resolved.read_bytes()" in source
    assert 'content.decode("utf-8", errors="strict")' in source
    assert "const fixtureText = __TREE_FIXTURE_TEXT__;" in source
    assert "await sha256(fixtureText)" in source
    assert "fingerprint === JSON.stringify(treeFingerprint(treeRoot))" in source
    assert source.index("controller.commitWindow(currentTwo") < source.index(
        "const secondStaleResult = controller.commitWindow(currentOne"
    )
    assert "CallDevToolsProtocolMethodAsync" in source
    assert "EvidencePublisher(" in source
    assert 'parser.add_argument("--evidence-dir"' in source
    assert 'parser.add_argument("--output"' not in source
    assert "evaluate_js" not in source
    assert "ExecuteScriptAsync" not in source
    assert "SetForegroundWindow" not in source
    assert "set_foreground" not in source.casefold()
    assert "scenario_deadline(75.0)" in launch
    assert launch.count("require_absolute_local_test_root(") >= 2
    assert "start_headed_process(" in launch
    assert "EvidenceReader(" in launch
    assert "wait_for_initial_evidence(" in launch
    assert "read_text(" not in launch
    assert '"--tree-fixture"' in launch
    assert "fixture.path.resolve()" in launch
    assert "cwd=installed.root" in launch
    assert "terminate_process_tree(process, deadline=deadline)" in launch


def test_shell_gate_report_refuses_private_error_text(tmp_path: Path) -> None:
    paths = EvidencePaths(tmp_path.resolve())
    recorder = shell_child._Recorder(paths)
    recorder.failure("private-path", RuntimeError("C:\\private\\sentinel"))
    result = EvidenceReader(paths).read_failure()

    assert result == {
        "failure": {"stage": "child", "type": "RuntimeError"}
    }
    assert _sanitized_failure_record(result) == result["failure"]
    assert "private" not in json.dumps(result).casefold()
    assert "sentinel" not in json.dumps(result).casefold()


def test_shell_gate_retains_a_sanitized_post_ready_failure(
    tmp_path: Path,
) -> None:
    paths = EvidencePaths(tmp_path.resolve())
    recorder = shell_child._Recorder(paths)
    recorder.complete({})

    recorder.failure("page_probe", RuntimeError("C:\\private\\late"))
    recorder.failure("child", ValueError("discarded second failure"))
    recorder.finish(0, host_returned=True)

    reader = EvidenceReader(paths)
    assert reader.read_ready() is not None
    final = reader.read_final()
    assert final == {
        "host_returned": True,
        "exit_code": 0,
        "post_ready_failure": {
            "stage": "page_probe",
            "type": "RuntimeError",
        },
    }
    assert "private" not in json.dumps(final).casefold()
    reader.assert_consistent(require_final=True)


def test_shell_gate_child_hashes_exact_fixture_bytes(
    tree_window_fixture: TreeWindowFixture,
) -> None:
    text, manifest, evidence = shell_child._load_tree_fixture(
        tree_window_fixture.path.resolve()
    )

    assert text == tree_window_fixture.text
    assert manifest == json.loads(tree_window_fixture.text)
    assert evidence == {
        "size": tree_window_fixture.size,
        "sha256": tree_window_fixture.sha256,
    }
    with pytest.raises(ValueError, match="must be absolute"):
        shell_child._load_tree_fixture(Path("relative-fixture.json"))


def test_accessibility_evidence_preserves_incomplete_normalized_facts() -> None:
    assert shell_child._accessibility_evidence({"nodes": []}) == {
        "tree_count": 0,
        "treeitem_count": 0,
        "keyboard_tree_named": False,
        "presentation_tree_named": False,
        "layout_label_exact": False,
        "layout_controls_absent": False,
        "ordinary_label_exact": False,
        "long_label_exact": False,
        "supplemental_layout_label_exact": False,
        "supplemental_hostile_label_exact": False,
        "supplemental_long_label_exact": False,
        "active_descendant_exposed": False,
    }


@pytest.mark.headed
def test_sh_g_7_installed_shell_tree_keyboard_reflow_and_forced_colors(
    shell_gate_evidence: _ShellGate,
) -> None:
    result = shell_gate_evidence.result()
    fixture = shell_gate_evidence.fixture
    manifest = json.loads(fixture.text)
    views = manifest["views"]
    node_ids = manifest["node_ids"]
    keyboard_root_id = views["pointer_collapsed"]["rows"][0]["node_id"]
    projection_id = node_ids["projection"]
    layout_source = next(
        row["display"]
        for row in views["layout_control"]["rows"]
        if row["node_id"] == node_ids["layout_control"]
    )
    layout_rendered = shell_child._visible_filesystem_text(layout_source)
    ordinary_source = views["next"]["rows"][0]["display"]
    long_source = views["next"]["rows"][1]["display"]
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
    assert page["keyboard_tree"] == {
        "row_count": 3,
        "tab_index": 0,
        "client_height": 28,
        "row_h": 28,
        "fixture_schema": TREE_WINDOW_FIXTURE_SCHEMA,
        "active_node": keyboard_root_id,
    }
    assert page["theme_focus"] == {
        "active": True,
        "associated_label": "Theme",
        "disabled": False,
        "id": "theme-mode",
        "tag": "SELECT",
        "value": "system",
        "visible": True,
    }
    assert page["first_focus"] == {
        "label": "Keyboard tree evidence",
        "tag": "DIV",
        "active_node": keyboard_root_id,
        "scroll_top": 0,
        "client_height": 28,
        "fully_visible": True,
    }
    assert page["second_focus"] == {
        "label": "Keyboard tree evidence",
        "tag": "DIV",
        "active_node": projection_id,
        "scroll_top": 28,
        "client_height": 28,
        "fully_visible": True,
    }
    assert page["disclosure_click"] == {
        "toggles": [[projection_id, True]],
        "activations": [],
        "focus_is_tree": True,
        "active_node": projection_id,
    }
    assert page["label_click"] == {
        "toggles": [[projection_id, True]],
        "activations": [projection_id],
        "focus_is_tree": True,
        "active_node": projection_id,
    }
    assert page["scroll_tree"] == {
        "active_node": views["maximum"]["rows"][7]["node_id"],
        "activations": [],
        "commits": [
            {"accepted": True, "generation": 2, "offset": 0},
            {"accepted": True, "generation": 3, "offset": 4},
        ],
        "disposal": {
            "commits_unchanged": True,
            "requests_unchanged": True,
        },
        "fully_visible_active": True,
        "focus_is_tree": True,
        "initial": {
            "accepted": True,
            "client_height": 56,
            "generation": 1,
            "fixture_schema": TREE_WINDOW_FIXTURE_SCHEMA,
            "row_count": 2,
            "row_h": 28,
            "total": views["maximum"]["total"],
        },
        "nonblank_viewport": True,
        "rendered_indices": [4, 5, 6, 7, 8],
        "resize": {
            "client_height": 112,
            "nonblank_viewport": True,
            "rendered_indices": [0, 1, 2, 3, 4],
            "request": {"generation": 2, "index": 3},
            "row_count": 5,
            "scroll_top": 0,
            "scroll_unchanged": True,
        },
        "requests": [
            {"generation": 2, "index": 3},
            {"generation": 3, "index": 7},
        ],
        "row_count": 5,
        "scroll_top": 112,
    }
    assert page["controller_zoom"] == 2.0
    assert final["focused_before_tree"] == "Keyboard tree evidence"
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
    assert tree["known_leaf_expanded"] is False
    assert tree["stale_reads"] == 0
    assert tree["stale_results"] == [False, False]
    assert tree["stale_unchanged"] is True
    assert tree["text"] == {
        "layout_exact": True,
        "layout_controls_absent": True,
        "layout_bytes": len(layout_rendered.encode("utf-8")),
        "layout_sha256": hashlib.sha256(
            layout_rendered.encode("utf-8")
        ).hexdigest(),
        "ordinary_exact": True,
        "ordinary_bytes": len(ordinary_source.encode("utf-8")),
        "ordinary_sha256": hashlib.sha256(
            ordinary_source.encode("utf-8")
        ).hexdigest(),
        "long_exact": True,
        "long_bytes": len(long_source.encode("utf-8")),
        "long_sha256": hashlib.sha256(
            long_source.encode("utf-8")
        ).hexdigest(),
        "tri_state": ["true", "false", None],
        "callback_ids": {
            "toggles": [[projection_id, True]],
            "activations": [projection_id],
            "dataset_node_id": projection_id,
        },
        "supplemental": {
            "layout_exact": True,
            "layout_controls_absent": True,
            "hostile_exact": True,
            "long_exact": True,
        },
    }
    assert tree["view_coverage"] == {
        "head": {
            "accepted": True,
            "offset": views["head"]["offset"],
            "total": views["head"]["total"],
            "row_count": len(views["head"]["rows"]),
            "first_node_id": views["head"]["rows"][0]["node_id"],
            "last_node_id": views["head"]["rows"][-1]["node_id"],
        },
        "tail": {
            "accepted": True,
            "offset": views["tail"]["offset"],
            "total": views["tail"]["total"],
            "row_count": len(views["tail"]["rows"]),
            "first_node_id": views["tail"]["rows"][0]["node_id"],
            "last_node_id": views["tail"]["rows"][-1]["node_id"],
        },
        "empty": {
            "accepted": True,
            "offset": 0,
            "total": 0,
            "row_count": 0,
            "first_node_id": None,
            "last_node_id": None,
        },
    }
    assert final["fixture"] == {
        "schema": TREE_WINDOW_FIXTURE_SCHEMA,
        "size": fixture.size,
        "sha256": fixture.sha256,
    }
    assert result["tree_fixture"] == {
        "size": fixture.size,
        "sha256": fixture.sha256,
    }
    assert final["complete_text"] == shell_child._COMPLETE_TEXT
    assert page["accessibility"] == {
        "tree_count": 3,
        "treeitem_count": 262,
        "keyboard_tree_named": True,
        "presentation_tree_named": True,
        "layout_label_exact": True,
        "layout_controls_absent": True,
        "ordinary_label_exact": True,
        "long_label_exact": True,
        "supplemental_layout_label_exact": True,
        "supplemental_hostile_label_exact": True,
        "supplemental_long_label_exact": True,
        "active_descendant_exposed": True,
    }
    assert page["native"] == {
        "ui_thread": True,
        "window_style": {
            "caption": True,
            "thickframe": True,
            "sysmenu": True,
        },
    }


def _sanitized_failure_record(value: object) -> dict[str, str]:
    if type(value) is not dict or set(value) != {"failure"}:
        raise AssertionError("shell failure evidence is invalid")
    failure = value["failure"]
    if (
        type(failure) is not dict
        or set(failure) != {"stage", "type"}
        or failure.get("stage") not in shell_child._FAILURE_STAGES
        or failure.get("type") not in shell_child._FAILURE_TYPES
    ):
        raise AssertionError("shell failure evidence is invalid")
    return failure


def _run_shell_scenario(
    installed: HeadedInstalledWheel,
    root: Path,
    fixture: TreeWindowFixture,
) -> dict[str, object]:
    deadline = scenario_deadline(75.0)
    root = require_absolute_local_test_root(root)
    root.mkdir(parents=True, exist_ok=True)
    data_root = require_absolute_local_test_root(root / "data")
    evidence_root = require_absolute_local_test_root(root / "evidence")
    evidence_root.mkdir()
    evidence_paths = EvidencePaths(evidence_root)
    evidence_reader = EvidenceReader(evidence_paths)
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
            "--evidence-dir",
            evidence_root,
            "--tree-fixture",
            fixture.path.resolve(),
        ),
        cwd=installed.root,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    try:
        window = wait_for_window(process, title, deadline=deadline)
        milestone, initial = wait_for_initial_evidence(
            evidence_reader,
            process,
            deadline=deadline,
        )
        if milestone == "ready":
            wait_for_accessible_text(
                window,
                shell_child._COMPLETE_TEXT,
                python=installed.python,
                deadline=deadline,
            )
        close_window(window)
        completed = wait_for_process(process, deadline=deadline)
        final = evidence_reader.read_final()
        evidence_reader.assert_consistent(require_final=milestone == "ready")
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)

    if final is not None:
        require_host_final(final, exit_code=completed.returncode)
    if milestone == "failure":
        failure = _sanitized_failure_record(initial)
        raise AssertionError(f"shell gate failed: {failure!r}")
    assert final is not None
    assert final["host_returned"] is True
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout == ""
    assert completed.stderr == ""
    result = dict(initial)
    result["exit_code"] = final["exit_code"]
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
        "tree_fixture",
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
    assert type(result["tree_fixture"]) is dict
    assert set(result["tree_fixture"]) == {"size", "sha256"}
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
        "keyboard_tree",
        "theme_focus",
        "first_focus",
        "second_focus",
        "disclosure_click",
        "label_click",
        "scroll_tree",
        "controller_zoom",
        "final",
        "accessibility",
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
    assert set(result["page"]["keyboard_tree"]) == {
        "row_count",
        "tab_index",
        "client_height",
        "row_h",
        "fixture_schema",
        "active_node",
    }
    assert set(result["page"]["theme_focus"]) == {
        "active",
        "associated_label",
        "disabled",
        "id",
        "tag",
        "value",
        "visible",
    }
    for focus_name in ("first_focus", "second_focus"):
        assert set(result["page"][focus_name]) == {
            "label",
            "tag",
            "active_node",
            "scroll_top",
            "client_height",
            "fully_visible",
        }
    for pointer_name in ("disclosure_click", "label_click"):
        assert set(result["page"][pointer_name]) == {
            "toggles",
            "activations",
            "focus_is_tree",
            "active_node",
        }
    assert set(result["page"]["scroll_tree"]) == {
        "active_node",
        "activations",
        "commits",
        "disposal",
        "fully_visible_active",
        "focus_is_tree",
        "initial",
        "nonblank_viewport",
        "rendered_indices",
        "resize",
        "requests",
        "row_count",
        "scroll_top",
    }
    assert set(result["page"]["scroll_tree"]["initial"]) == {
        "accepted",
        "client_height",
        "generation",
        "fixture_schema",
        "row_count",
        "row_h",
        "total",
    }
    assert set(result["page"]["scroll_tree"]["resize"]) == {
        "client_height",
        "nonblank_viewport",
        "rendered_indices",
        "request",
        "row_count",
        "scroll_top",
        "scroll_unchanged",
    }
    assert set(result["page"]["scroll_tree"]["disposal"]) == {
        "commits_unchanged",
        "requests_unchanged",
    }
    final = result["page"]["final"]
    assert set(final) == {
        "focused_before_tree",
        "zoom",
        "forced",
        "tree",
        "fixture",
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
    assert set(final["fixture"]) == {"schema", "size", "sha256"}
    assert set(final["tree"]) == {
        "row_h",
        "role",
        "row_count",
        "spacer_count",
        "child_count",
        "every_row_28",
        "first_level",
        "first_expanded",
        "known_leaf_expanded",
        "stale_reads",
        "stale_results",
        "stale_unchanged",
        "text",
        "view_coverage",
    }
    assert set(final["tree"]["view_coverage"]) == {
        "head",
        "tail",
        "empty",
    }
    assert all(
        set(evidence) == {
            "accepted",
            "offset",
            "total",
            "row_count",
            "first_node_id",
            "last_node_id",
        }
        for evidence in final["tree"]["view_coverage"].values()
    )
    assert set(final["tree"]["text"]) == {
        "layout_exact",
        "layout_controls_absent",
        "layout_bytes",
        "layout_sha256",
        "ordinary_exact",
        "ordinary_bytes",
        "ordinary_sha256",
        "long_exact",
        "long_bytes",
        "long_sha256",
        "tri_state",
        "callback_ids",
        "supplemental",
    }
    assert set(final["tree"]["text"]["callback_ids"]) == {
        "toggles",
        "activations",
        "dataset_node_id",
    }
    assert set(final["tree"]["text"]["supplemental"]) == {
        "layout_exact",
        "layout_controls_absent",
        "hostile_exact",
        "long_exact",
    }
    assert set(result["page"]["accessibility"]) == {
        "tree_count",
        "treeitem_count",
        "keyboard_tree_named",
        "presentation_tree_named",
        "layout_label_exact",
        "layout_controls_absent",
        "ordinary_label_exact",
        "long_label_exact",
        "supplemental_layout_label_exact",
        "supplemental_hostile_label_exact",
        "supplemental_long_label_exact",
        "active_descendant_exposed",
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
