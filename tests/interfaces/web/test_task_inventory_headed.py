"""Installed-wheel native inventory action journey."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from _headed_evidence import EvidencePaths, EvidenceReader, require_host_final
from _headed_native import (
    clean_child_environment, close_window, require_absolute_local_test_root,
    scenario_deadline, start_headed_process, terminate_process_tree,
    wait_for_initial_evidence, wait_for_process, wait_for_window,
)
from conftest import HeadedInstalledWheel


_CHILD = Path(__file__).with_name("_task_inventory_headed_child.py")


@pytest.mark.headed
def test_installed_inventory_refresh_acknowledge_restore_and_close(
    headed_installed_wheel: HeadedInstalledWheel, tmp_path: Path,
) -> None:
    deadline = scenario_deadline(120.0)
    root = require_absolute_local_test_root(tmp_path.resolve())
    evidence = require_absolute_local_test_root(root / "evidence")
    data = require_absolute_local_test_root(root / "data")
    source = require_absolute_local_test_root(root / "source")
    screenshot = require_absolute_local_test_root(evidence / "inventory-actions.png")
    for directory in (evidence, data, source):
        directory.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    title = f"NamiSync Inventory Actions {token}"
    args = (
        headed_installed_wheel.python, _CHILD, "--data-dir", data,
        "--evidence-dir", evidence, "--source", source,
        "--screenshot", screenshot, "--mutex", rf"Local\NamiSync.InventoryActions.{token}",
        "--title", title,
    )
    reader = EvidenceReader(EvidencePaths(evidence))
    process = start_headed_process(
        args, cwd=headed_installed_wheel.root,
        environment=clean_child_environment(), deadline=deadline,
    )
    window = None
    closed = False
    try:
        window = wait_for_window(process, title, deadline=deadline)
        milestone, initial = wait_for_initial_evidence(reader, process, deadline=deadline)
        if milestone == "failure":
            pytest.fail(f"inventory journey child failed: {initial}")
        assert milestone == "ready"
        assert initial["report"]["native_clicks"] == {
            "refresh": True, "filter-open": True, "filter-present": True,
            "filter-escape": True, "filter-reopen": True, "filter-all": True,
            "details": True, "acknowledge": True, "restore-details": True, "restore": True,
        }
        assert initial["report"]["foreground_owned"] == {
            "refresh": True, "filter-open": True, "filter-present": True,
            "filter-escape": True, "filter-reopen": True, "filter-all": True,
            "details": True, "acknowledge": True, "restore-details": True, "restore": True,
        }
        assert initial["report"]["filter_menu"] == {
            "neutral": True, "staysOpen": True, "accented": True, "escapeFocus": True,
            "allKeepsOpen": True, "allNoCount": True, "focusAwayClosed": True,
            "firstReachable": True, "lastReachable": True, "popupInside": True,
        }
        assert initial["report"]["results"]["refresh"]["request_id"] != initial["report"]["initial"]["request_id"]
        assert initial["report"]["results"]["acknowledge"]["applied"] == 1
        assert initial["report"]["results"]["restore"]["applied"] == 1
        assert initial["report"]["publication"]["request_id"] == initial["report"]["results"]["refresh"]["request_id"]
        assert initial["report"]["pane_visible"] is True
        assert initial["report"]["refreshed_missing"] is True
        assert initial["report"]["acknowledged_hidden"] is True
        assert initial["report"]["restored_missing"] is True
        assert initial["report"]["task_closed"] is True
        assert screenshot.is_file()
        close_window(window)
        closed = True
        completed = wait_for_process(process, deadline=deadline)
        final = reader.read_final()
        assert final is not None and require_host_final(final, exit_code=completed.returncode)
        reader.assert_consistent(require_final=True)
        assert completed.returncode == 0
    finally:
        try:
            if window is not None and not closed and process.poll() is None:
                close_window(window)
        finally:
            terminate_process_tree(process, deadline=deadline)
