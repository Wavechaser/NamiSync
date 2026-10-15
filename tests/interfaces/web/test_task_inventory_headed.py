"""Installed-wheel native inventory action journey."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

import _task_inventory_headed_child as child
from _headed_evidence import EvidencePaths, EvidenceReader, require_host_final
from _headed_native import (
    clean_child_environment, close_window, require_absolute_local_test_root,
    scenario_deadline, start_headed_process, terminate_process_tree,
    wait_for_initial_evidence, wait_for_process, wait_for_window,
)
from conftest import HeadedInstalledWheel


_CHILD = Path(__file__).with_name("_task_inventory_headed_child.py")
_INTEGRITY_INPUT = {name: True for name in (
    "range-anchor", "range-toggle", "range-end", "range-checkbox", "range-clear",
    "select-folder", "select-location-clear", "select-location", "baseline", "verify", "pause", "resume",
    "verify-cancel", "cancel", "rebaseline-cancel-open", "rebaseline-cancel", "rebaseline-open", "rebaseline-confirm",
)}


def test_inventory_confirmation_exit_diagnostic_is_exact_and_bounded() -> None:
    facts = {
        "closed": True,
        "app_active": True,
        "theme_active": True,
        "scroll_restored": True,
        "focus_restored": False,
        "trigger_connected": True,
        "trigger_disabled": False,
        "trigger_hidden": False,
        "active_category": "inventory",
    }
    diagnostic = {"last_close": {**facts, "closed": False, "active_category": "dialog"},
                  "timeout": facts}

    assert child._bounded_confirmation_exit_diagnostic(diagnostic) == {
        "last_close": {key: diagnostic["last_close"][key] for key in sorted(facts)},
        "timeout": {key: facts[key] for key in sorted(facts)},
    }
    assert child._bounded_confirmation_exit_diagnostic(
        {**diagnostic, "path": r"C:\private"},
    ) is None
    assert child._bounded_confirmation_exit_diagnostic(
        {**diagnostic, "timeout": {**facts, "closed": 1}},
    ) is None
    assert child._bounded_confirmation_exit_diagnostic(
        {**diagnostic, "timeout": {**facts, "active_category": r"C:\private"}},
    ) is None
    assert child._bounded_confirmation_exit_diagnostic(
        {"last_close": None, "timeout": None},
    ) == {"last_close": None, "timeout": None}


def test_inventory_custody_failure_diagnostic_excludes_dom_and_unbounded_values() -> None:
    facts = {"checkbox_custody": True, "range_custody": False,
        "cancel_preserved_result": True, "scan_selected": True,
        "range_scroll_before": 7000, "range_scroll_after": 7000,
        "range_checkbox_focused": False, "range_checkbox_connected": True,
        "range_checkbox_disabled": False, "range_active_category": "body"}
    assert child._bounded_integrity_custody_diagnostic(facts) == facts
    for invalid in ({**facts, "path": r"C:\private"},
                    {**facts, "range_active_category": r"C:\private"},
                    {**facts, "range_checkbox_focused": 0},
                    {**facts, "range_scroll_after": float("inf")},
                    {**facts, "range_scroll_after": -1}):
        assert child._bounded_integrity_custody_diagnostic(invalid) is None
    assert child._bounded_integrity_custody_diagnostic(None) is None


@pytest.mark.headed
def test_installed_inventory_refresh_acknowledge_restore_and_close(
    headed_installed_wheel: HeadedInstalledWheel, tmp_path: Path,
) -> None:
    deadline = scenario_deadline(180.0)
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
            "context-open": True, "context-escape": True, "context-keyboard": True,
            "context-keyboard-escape": True, "context-menu": True,
            "context-acknowledge": True, "context-restore-details": True, "context-restore": True,
            "selected-activate": True, "selected-arrow-first": True,
            "selected-arrow-second": True, "selected-refresh": True,
            **_INTEGRITY_INPUT,
        }
        assert initial["report"]["foreground_owned"] == {
            "refresh": True, "filter-open": True, "filter-present": True,
            "filter-escape": True, "filter-reopen": True, "filter-all": True,
            "details": True, "acknowledge": True, "restore-details": True, "restore": True,
            "context-open": True, "context-escape": True, "context-keyboard": True,
            "context-keyboard-escape": True, "context-menu": True,
            "context-acknowledge": True, "context-restore-details": True, "context-restore": True,
            "selected-activate": True, "selected-arrow-first": True,
            "selected-arrow-second": True, "selected-refresh": True,
            **_INTEGRITY_INPUT,
        }
        assert initial["report"]["filter_menu"] == {
            "neutral": True, "staysOpen": True, "accented": True, "escapeFocus": True,
            "allKeepsOpen": True, "allNoCount": True, "focusAwayClosed": True,
            "firstReachable": True, "lastReachable": True, "popupInside": True,
        }
        assert initial["report"]["results"]["refresh"]["request_id"] != initial["report"]["initial"]["request_id"]
        assert initial["report"]["results"]["acknowledge"]["applied"] == 1
        assert initial["report"]["results"]["restore"]["applied"] == 1
        assert initial["report"]["results"]["context_acknowledge"] == {
            "node_id": initial["report"]["fixture"]["missing_node_id"], "applied": 1,
        }
        assert initial["report"]["results"]["context_restore"] == {
            "node_id": initial["report"]["fixture"]["folder_node_id"], "applied": 1,
        }
        row_menu = initial["report"]["row_menu"]
        assert {key: value for key, value in row_menu.items()
                if key not in {"rectangles", "raw_rectangles"}} == {
            "other_detail_preserved": True, "active_missing": True, "popup_inside": True,
            "escape_focus": True, "own_missing_actions": True,
            "acknowledged_hidden": True, "restored_missing": True,
        }
        assert len(row_menu["rectangles"]) == len(row_menu["raw_rectangles"]) == 2
        for observed, raw in zip(row_menu["rectangles"], row_menu["raw_rectangles"], strict=True):
            assert len(observed) == len(raw) == 4
            assert observed == pytest.approx(raw, rel=0, abs=0.0005)
        menu_edges, work_edges = row_menu["rectangles"]
        assert menu_edges[0] >= work_edges[0] and menu_edges[2] <= work_edges[2]
        assert menu_edges[1] >= work_edges[1] and menu_edges[3] <= work_edges[3]
        keyboard_input = initial["report"]["keyboard_input"]
        table = initial["report"]["table_appearance"]
        assert table["headers"] == ["", "Filename", "Presence", "Checksum", "Size", "Modified", "Notes"]
        assert table["row_height"] == pytest.approx(24, abs=0.5)
        assert initial["report"]["fixture"]["domain_count"] == 304
        assert table["row_count"] == 256
        assert table["header_control_count"] == 1
        assert len(table["row_checkboxes"]) == table["row_count"]
        assert all(item["control_count"] == 1 for item in table["row_checkboxes"])
        checkboxes = [table["header_checkbox"],
                      *(item["appearance"] for item in table["row_checkboxes"])]
        assert all(checkbox is not None for checkbox in checkboxes)
        enabled_nodes = {initial["report"]["fixture"][key]
                         for key in ("folder_node_id", "first_node_id", "missing_node_id")}
        assert not table["header_checkbox"]["disabled"]
        for row in table["row_checkboxes"]:
            assert row["appearance"]["disabled"] is (row["node_id"] not in enabled_nodes)
        for checkbox in checkboxes:
            assert not checkbox["checked"] and not checkbox["mixed"]
            assert [checkbox["width"], checkbox["height"]] == pytest.approx([16, 16], abs=0.5)
        for header_left, header_right, row_left, row_right in table["column_edges"]:
            assert [row_left, row_right] == pytest.approx([header_left, header_right], abs=1)
        assert [item["name"] for item in keyboard_input] == ["context-keyboard", "context-menu"]
        for item, key in zip(keyboard_input, ("F10", "ContextMenu"), strict=True):
            assert item["popup_visible"] and item["stable_focus"] and item["stable_position"], item
            events = item["events"]
            assert all(event["trusted"] for event in events), events
            assert [event["key"] for event in events if event["type"] == "keydown"] == [key], events
            assert [event["key"] for event in events if event["type"] == "keyup"] == [key], events
            assert all(event["default_prevented"] for event in events
                       if event["type"] in {"keydown", "contextmenu"}), events
        selected_refresh = initial["report"]["results"]["selected_refresh"]
        assert selected_refresh["node_id"] == initial["report"]["fixture"]["missing_node_id"]
        assert selected_refresh["prior_request_id"] == initial["report"]["results"]["refresh"]["request_id"]
        assert selected_refresh["request_id"] != selected_refresh["prior_request_id"]
        assert initial["report"]["selected_refresh"] == {
            "details_hidden": True, "card_preserved": True,
            "active_node_id": selected_refresh["node_id"],
        }
        commands = initial["report"]["integrity_commands"]
        starts = commands["starts"]
        assert starts[0]["request_id"] == selected_refresh["request_id"]
        assert initial["report"]["publication"]["request_id"] == starts[-1]["next_request_id"]
        assert [item["mode"] for item in starts] == ["baseline", "verify", "verify", "rebaseline"]
        assert [item["accept_current_evidence"] for item in starts] == [False, False, False, True]
        assert len({item["command_id"] for item in starts}) == 4
        assert [item["request_id"] for item in starts[1:]] == [item["next_request_id"] for item in starts[:-1]]
        assert [item["selected"] for item in commands["selections"]] == [True, False, True]
        assert [item["result"]["selected_file_count"] for item in commands["selections"]] == [3, 2, 3]
        assert [item["result"]["hidden_selected_file_count"] for item in commands["selections"]] == [0, 2, 2]
        assert [item["result"]["selected_file_count"] for item in commands["highlighted_selections"]] == [3, 0]
        assert commands["selections"][0]["node_id"] == initial["report"]["fixture"]["folder_node_id"]
        assert commands["selections"][1]["node_id"] is commands["selections"][2]["node_id"] is None
        assert [item["action"] for item in commands["controls"]] == ["pause", "resume", "cancel"]
        assert commands["runner_entry_controls"] == ["pause", "cancel"]
        assert [item["session_id"] for item in commands["controls"]] == [starts[1]["session_id"], starts[1]["session_id"], starts[2]["session_id"]]
        assert all(item["result"]["accepted"] for item in commands["controls"])
        journey = initial["report"]["integrity_journey"]
        assert journey["checkbox_custody"] and journey["range_custody"] and journey["cancel_preserved_result"] and journey["scan_selected"]
        assert journey["range_scroll"] > 256 * 24
        assert journey["cancel_confirmation_restored"] == {
            "closed": True, "app_active": True, "theme_active": True,
            "scroll_restored": True, "focus_required": True, "focus_restored": True,
            "trigger_connected_at_close": True, "trigger_disabled_at_close": False,
            "trigger_hidden_at_close": False,
        }
        confirmation = journey["confirmation_restored"]
        assert {key: confirmation[key] for key in (
            "closed", "app_active", "theme_active", "scroll_restored",
            "trigger_connected_at_close",
        )} == {key: True for key in (
            "closed", "app_active", "theme_active", "scroll_restored",
            "trigger_connected_at_close",
        )}
        assert confirmation["trigger_hidden_at_close"] is False
        assert confirmation["focus_required"] == (
            confirmation["trigger_connected_at_close"]
            and not confirmation["trigger_disabled_at_close"]
        )
        assert not confirmation["focus_required"] or confirmation["focus_restored"]
        assert "3 of 3 files selected" in journey["hidden_selection"]
        assert "2 hidden by filters or search" in journey["hidden_selection"]
        assert "3" in journey["confirmation_text"] and "2" in journey["confirmation_text"]
        assert journey["terminal_presentations"] == [
            {"text": "Baseline retained results · 1 window result",
             "states": ["baselined"], "current_scan": True},
            {"text": "Verification retained results · 1 window result",
             "states": ["verified"], "current_scan": True},
            {"text": "Verification retained results · 0 window results",
             "states": [], "current_scan": True},
            {"text": "Rebaseline retained results · 1 window result",
             "states": ["baselined"], "current_scan": True},
        ]
        results = initial["report"]["integrity_results"]
        assert len(results) == 4
        from xxhash import xxh3_128
        expected_digest = xxh3_128(b"NamiSync native inventory fixture\r\n").hexdigest()
        for index, (result, start) in enumerate(zip(results, starts, strict=True)):
            assert result["scan_scope"] == {"kind": "selection", "path": None}
            assert result["scan_request_id"] == start["next_request_id"]
            overlay = result["integrity"]
            assert overlay["session_id"] == start["session_id"]
            assert overlay["request_id"] == start["next_request_id"]
            assert overlay["complete"] and not overlay["gap"]
            assert sorted(item["result"] for item in overlay["items"]) == (
                ["baselined", "baselined", "missing"] if index in {0, 3}
                else ["missing", "verified", "verified"] if index == 1 else []
            )
            assert len(result["visible_integrity"]["items"]) == (0 if index == 2 else 1)
            present = [row for row in result["ledger"] if row["presence"] == "present" and row["digest"] is not None]
            assert {row["path"] for row in present} == {r"folder\one.txt", r"folder\zz.txt"}
            assert all(row["algorithm"] == "xxh3_128" and row["digest"] == expected_digest for row in present)
            assert all(row["verification_state"] == ("verified" if index in {1, 2} else "unverified") for row in present)
            assert all((row["last_verified_at"] is not None) == (index in {1, 2}) for row in present)
        assert results[1]["ledger"] == results[2]["ledger"]
        before_rebaseline = {row["path"]: row["evidence_at"] for row in results[2]["ledger"]}
        assert all(row["evidence_at"] != before_rebaseline[row["path"]] for row in results[3]["ledger"] if row["digest"] is not None)
        assert initial["report"]["publication"]["scan_scope"] == {
            "kind": "selection", "path": None,
        }
        assert initial["report"]["publication"]["scan_request_id"] == starts[-1]["next_request_id"]
        assert initial["report"]["pane_visible"] is True
        assert initial["report"]["blank_scanning_shell"] is True
        assert initial["report"]["refreshed_missing"] is True
        assert initial["report"]["acknowledged_hidden"] is True
        assert initial["report"]["restored_missing"] is True
        assert initial["report"]["status"] == {
            "feedback_lines": 1, "has_scope": True, "track_height": 8,
            "animation": "none", "value": "0%",
        }
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
