"""Installed-wheel headed journey for the rail's Pause all and Resume all."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

import _task_rail_bulk_headed_child as child
from _headed_evidence import EvidencePaths, EvidenceReader, require_host_final
from _headed_native import (
    clean_child_environment, close_window, require_absolute_local_test_root,
    scenario_deadline, start_headed_process, terminate_process_tree,
    wait_for_initial_evidence, wait_for_process, wait_for_window,
)
from conftest import HeadedInstalledWheel


_CHILD = Path(__file__).with_name("_task_rail_bulk_headed_child.py")


@pytest.mark.headed
@pytest.mark.background_headed
def test_installed_rail_pause_all_holds_queued_tasks_and_resume_all_completes_them(
    headed_installed_wheel: HeadedInstalledWheel, tmp_path: Path,
) -> None:
    deadline = scenario_deadline(180.0)
    root = require_absolute_local_test_root(tmp_path.resolve())
    evidence = require_absolute_local_test_root(root / "evidence")
    data = require_absolute_local_test_root(root / "data")
    source = require_absolute_local_test_root(root / "source")
    screenshot = require_absolute_local_test_root(evidence / "rail-bulk-held.png")
    for directory in (evidence, data):
        directory.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    title = f"NamiSync Rail Bulk {token}"
    args = (
        headed_installed_wheel.python, _CHILD, "--data-dir", data,
        "--evidence-dir", evidence, "--source", source, "--screenshot", screenshot,
        "--mutex", rf"Local\NamiSync.RailBulk.{token}", "--title", title,
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
            pytest.fail(f"rail bulk journey child failed: {initial}")
        assert milestone == "ready"
        report = initial["report"]

        # One scan runs behind a gate; two same-volume scans queue behind it.
        queued = report["queued"]
        assert queued["pauseEnabled"] is True and queued["resumeEnabled"] is False
        assert (queued["pauseName"], queued["pauseTooltip"]) == ("Pause all", "Pause all")
        assert (queued["resumeName"], queued["resumeTooltip"]) == ("Resume all", "Resume all")
        assert queued["noticeRole"] == "status"
        assert queued["notice"] == ""

        # Pause all holds the queued scans and reports the running scan that
        # cannot pause; held tasks read as not started.
        held = report["held"]
        assert held["notice"] == child._HELD_NOTICE
        assert sorted(held["titles"]).count(child._HELD_TITLE) == 2
        assert held["statuses"].count("Paused before it started. Use Resume all to start it.") == 2
        assert held["resumeEnabled"] is True
        assert held["pauseEnabled"] is False, "only a scan that cannot pause remains"
        assert report["capture_dimensions"][0] > 0 and screenshot.is_file()

        # Resume all releases both; nothing is labelled paused while they wait.
        resumed = report["resumed"]
        assert resumed["notice"] == child._RESUMED_NOTICE
        assert not any("paused" in (value or "").casefold() for value in resumed["titles"])
        assert report["queue_before_release"]["scanner_calls"] == 1, "held scans did not start early"

        completed = report["completed"]
        assert completed["titles"] == [child._COMPLETED_TITLE] * 3
        # Exactly one bulk request per press; a duplicate or extra request fails here.
        zero = dict.fromkeys(("paused", "held", "already_pausing", "still_running", "resumed"), 0)
        assert report["queue"]["controls"] == [
            {"action": "pause", "result": {**zero, "held": 2, "still_running": 1}},
            {"action": "resume", "result": {**zero, "resumed": 2}},
        ]
        assert report["queue"]["scanner_calls"] == 3
        assert len(report["queue"]["sessions"]) == 3

        close_window(window)
        closed = True
        completed_process = wait_for_process(process, deadline=deadline)
        final = reader.read_final()
        assert final is not None and require_host_final(final, exit_code=completed_process.returncode)
        reader.assert_consistent(require_final=True)
        assert completed_process.returncode == 0
    finally:
        try:
            if window is not None and not closed and process.poll() is None:
                close_window(window)
        finally:
            terminate_process_tree(process, deadline=deadline)
