"""Installed-wheel headed evidence for frozen Setup and location flows."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import _setup_headed_child as child
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


_CHILD = Path(__file__).with_name("_setup_headed_child.py")


def test_setup_child_keeps_the_production_host_and_captures_real_screenshots() -> None:
    source = _CHILD.read_text(encoding="utf-8")
    launch = inspect.getsource(_run_setup_scenario)

    assert "host.run_desktop(" in source
    assert '"_production_commands"' in source
    assert "CallDevToolsProtocolMethodAsync" in source
    assert '"Page.captureScreenshot"' in source
    assert "evaluate_js" not in source
    assert "ExecuteScriptAsync" not in source
    assert "scenario_deadline(120.0)" in launch


@pytest.mark.headed
def test_m1_6_installed_setup_flow(
    headed_installed_wheel: HeadedInstalledWheel,
    tmp_path: Path,
) -> None:
    result = _run_setup_scenario(headed_installed_wheel, tmp_path)
    assert result["editable"] is True
    assert result["typed_refusal"] in {"invalid_path", "missing", "unavailable"}
    assert result["typed_retry_resolved"] is True
    assert result["hostile_filter_inert"] is True
    assert result["two_setup_cards"] is True
    assert result["segmented_keyboard"] is True
    assert result["recent_dropdown_keyboard"] is True
    assert result["disclosure_open"] is True
    assert result["inline_location_controls"] is True
    assert result["browse_outside_path_control"] is True
    assert result["dropdown_anchored"] is True
    assert result["dropdown_rerender_focus_restored"] is True
    assert result["picker_icon_only"] is True
    assert result["advanced_switches"] is True
    assert result["primary_options_visible"] is True
    assert result["sync_inapplicable_actions_hidden"] is True
    assert result["recent_pair_online_offline"] is True
    assert result["offline_pair_disabled"] is True
    assert result["pair_two_line_paths"] is True
    assert result["pair_paths_truncated"] is True
    assert result["availability_dots_distinct"] is True
    assert result["availability_text_neutral"] is True
    assert result["pair_button_focused"] is True
    assert result["frozen"] is True
    assert result["plan_again_visible"] is True
    assert result["plan_again_new_task"] is True
    assert result["picker_resolved"] is True
    assert result["frozen_switches_disabled"] is True
    assert result["frozen_pairs_disabled"] is True
    assert result["frozen_mode_hidden"] is True
    assert result["recent_activated"] is True
    assert result["recent_pair_activated"] is True
    assert result["recent_pair_native_button"] is True
    assert result["inventory_without_pair"] is True
    assert result["inventory_inapplicable_hidden"] is True
    assert result["mixed_batch"] is True
    assert result["navigation_retains_frozen"] is True
    assert result["picker_ambiguous"] is True
    assert result["picker_mount_index"] == 1
    assert result["picker_continued"] is True
    assert result["start_refused_before_choice"] is True
    assert result["frozen_before_capture"] is True
    assert result["reload_task_count"] == result["task_count_before_reload"]
    assert result["reload_frozen_reconstructed"] is True
    assert set(result["screenshots"]) == {"editable", "editable-expanded", "frozen"}


def _run_setup_scenario(
    installed: HeadedInstalledWheel,
    root: Path,
) -> dict[str, object]:
    deadline = scenario_deadline(120.0)
    root = require_absolute_local_test_root(root)
    data_root = require_absolute_local_test_root(root / "data")
    evidence_root = require_absolute_local_test_root(root / "evidence")
    screenshot_root = require_absolute_local_test_root(root / "screenshots")
    source = require_absolute_local_test_root(root / "source")
    target = require_absolute_local_test_root(root / "target")
    for directory in (root, data_root, evidence_root, screenshot_root, source, target):
        directory.mkdir(parents=True, exist_ok=True)
    paths = EvidencePaths(evidence_root)
    reader = EvidenceReader(paths)
    process = start_headed_process(
        (
            installed.python, _CHILD,
            "--data-dir", data_root,
            "--mutex", "Local\\NamiSync.SetupHeaded",
            "--title", "NamiSync Setup headed",
            "--evidence-dir", evidence_root,
            "--screenshot-dir", screenshot_root,
            "--source", source,
            "--target", target,
        ),
        cwd=installed.root,
        environment=clean_child_environment(),
        deadline=deadline,
    )
    try:
        window = wait_for_window(process, "NamiSync Setup headed", deadline=deadline)
        milestone, initial = wait_for_initial_evidence(reader, process, deadline=deadline)
        if milestone == "ready":
            wait_for_accessible_text(window, child._COMPLETE_TEXT, python=installed.python, deadline=deadline)
        close_window(window)
        completed = wait_for_process(process, deadline=deadline)
        final = reader.read_final()
    finally:
        if process.poll() is None:
            terminate_process_tree(process, deadline=deadline)
    if milestone == "failure":
        raise AssertionError(f"setup headed gate failed: {initial!r}")
    assert final is not None
    require_host_final(final, exit_code=completed.returncode)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    for name in initial["screenshots"]:
        assert (screenshot_root / f"{name}.png").is_file()
    return initial
