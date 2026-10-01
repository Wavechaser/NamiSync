from __future__ import annotations

from dataclasses import replace

import pytest

import namisync.interfaces.web.inventory_review as review_module
from namisync.core.models import EntryKind, ScanWarning, ScanWarningCode
from namisync.core.pathing import normalize_relative_path
from namisync.db.repositories import InventoryPresence, InventorySnapshot
from namisync.interfaces.web.inventory_review import InventoryReviewState
from namisync.workflows import PlanSortColumn, SortDirection, build_inventory_projection
from _db_fixtures import NOW, file_stat


def _row(row_id, path, **changes):
    return replace(InventorySnapshot(
        row_id, 1, path, normalize_relative_path(path), EntryKind.FILE,
        InventoryPresence.PRESENT, file_stat(), None, NOW, None, "scope",
        None, None, None, None, None,
    ), **changes)


def _view():
    projection = build_inventory_projection(1, (
        _row("1", r"a\z.txt", observed=file_stat(size=9)),
        _row("2", r"a\b.txt", observed=file_stat(size=2)),
        _row("3", "gone.txt", presence=InventoryPresence.MISSING, acknowledged_at=NOW),
    ), (ScanWarning(ScanWarningCode.ACCESS_DENIED, "unreadable", "read failed"),))
    return InventoryReviewState("task-" + "1" * 32, "2" * 32, projection, r"C:\root", False, 2, 0)


def _update(view, **changes):
    values = dict(expected_revision=view.view_revision, search_query=view.search_query,
                  filters=view.filters, sort_column=view.sort_column, sort_direction=view.sort_direction,
                  collapse_node_id=None, collapsed=None)
    values.update(changes)
    return view.update(**values)


def test_complete_view_of_incomplete_scan_keeps_warnings_ack_hiding_and_rollups():
    view = _view()
    rows = view.window(expected_revision=0, offset=0, limit=256)["rows"]
    assert [row["display"] for row in rows] == ["a", r"a\b.txt", r"a\z.txt", "unreadable"]
    assert rows[-1]["row_kind"] == "notice" and rows[-1]["row_id"] is None
    assert view.summary()["scan_complete"] is False
    rollup = view.summary()["rollup"]
    assert rollup["domain_count"] == 3 and rollup["acknowledged"] == 1
    _update(view, filters=frozenset({"acknowledged"}))
    assert [row["row_id"] for row in view.window(expected_revision=1, offset=0, limit=256)["rows"]] == ["3"]
    assert view.summary()["rollup"] == rollup


def test_search_collapse_sort_reset_and_exact_generic_row_frame():
    view = _view()
    folder_id = view.projection.nodes[view.projection.position_by_path_key["A"]].node_id
    _update(view, sort_column=PlanSortColumn.SIZE, sort_direction=SortDirection.DESCENDING)
    rows = view.window(expected_revision=1, offset=0, limit=256)["rows"]
    assert [row["row_id"] for row in rows[1:3]] == ["1", "2"]
    assert rows[0]["depth"] == 0 and rows[0]["parent_visible_index"] is None
    assert rows[0]["first_child_visible_index"] == 1
    assert rows[1]["parent_visible_index"] == 0 and rows[1]["position_in_set"] == 1
    _update(view, collapse_node_id=folder_id, collapsed=True)
    assert view.window(expected_revision=2, offset=0, limit=256)["rows"][0]["expanded"] is False
    _update(view, search_query="b.txt", collapse_node_id=folder_id, collapsed=False,
            sort_column=PlanSortColumn.PATH, sort_direction=SortDirection.ASCENDING)
    assert [row["row_id"] for row in view.window(expected_revision=3, offset=0, limit=256)["rows"]] == [None, "2"]
    assert view.window(expected_revision=2, offset=0, limit=256)["disposition"] == "conflict"


def test_windows_reuse_sequence_and_failed_update_retains_complete_view(monkeypatch):
    view = _view()
    previous = view.summary()
    sequence = view._visible
    def refuse(*args, **kwargs):
        raise ValueError("derivation refused")
    monkeypatch.setattr(review_module, "_derive_visible_sequence_from_validated", refuse)
    for offset in range(5):
        assert len(view.window(expected_revision=0, offset=offset, limit=1)["rows"]) <= 1
    with pytest.raises(ValueError, match="refused"):
        _update(view, search_query="new")
    assert view.summary() == previous and view._visible is sequence
    assert _update(view)["disposition"] == "noop"
    with pytest.raises(ValueError, match="256"):
        view.window(expected_revision=0, offset=0, limit=257)


def test_empty_search_has_no_synthetic_ancestors_and_warning_cannot_collapse():
    view = _view()
    _update(view, search_query="no match")
    assert view.window(expected_revision=1, offset=0, limit=256)["total"] == 0
    warning = next(node for node in view.projection.nodes if node.warning)
    with pytest.raises(ValueError, match="folders"):
        _update(view, collapse_node_id=warning.node_id, collapsed=True)
    assert view.view_revision == 1


def test_acknowledged_folder_remains_only_as_required_ancestor_context():
    folder = _row("1", "folder", entry_kind=EntryKind.DIRECTORY,
                  observed=replace(file_stat(), kind=EntryKind.DIRECTORY),
                  presence=InventoryPresence.MISSING, acknowledged_at=NOW)
    child = _row("2", r"folder\missing.txt", presence=InventoryPresence.MISSING)
    view = InventoryReviewState("task-" + "1" * 32, "2" * 32,
        build_inventory_projection(1, (folder, child)), r"C:\root", True, 0, 1)
    _update(view, filters=frozenset({"missing"}))
    rows = view.window(expected_revision=1, offset=0, limit=256)["rows"]
    assert [(row["row_id"], row["acknowledged"]) for row in rows] == [("1", True), ("2", False)]
    _update(view, search_query="no matching descendant")
    assert view.window(expected_revision=2, offset=0, limit=256)["rows"] == []
