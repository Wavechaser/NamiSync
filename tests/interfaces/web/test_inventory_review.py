from __future__ import annotations

from dataclasses import replace

import pytest

import namisync.interfaces.web.inventory_review as review_module
from namisync.core.models import EntryKind, ScanWarning, ScanWarningCode
from namisync.core.pathing import normalize_relative_path
from namisync.db.repositories import InventoryPresence, InventorySnapshot
from namisync.interfaces.web.inventory_review import InventoryReviewState
from namisync.workflows import PlanSortColumn, SortDirection, build_inventory_projection
from _db_fixtures import NOW, attestation, file_stat


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
    assert [row["display"] for row in rows] == ["a", "b.txt", "z.txt", "access_denied: unreadable"]
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


@pytest.mark.parametrize("state", ["present", "missing", "modified", "reappeared", "mismatched"])
def test_window_keeps_recorded_checksum_independent_of_observation_state(state):
    from namisync.core.integrity import VerificationInvalidation, VerificationInvalidationReason
    stat = file_stat()
    changes = {"attestation": attestation(stat)}
    if state == "missing":
        changes.update(presence=InventoryPresence.MISSING, observed=None)
    elif state in {"modified", "mismatched"}:
        changes["invalidation"] = VerificationInvalidation(NOW,
            VerificationInvalidationReason.METADATA_DRIFT if state == "modified"
            else VerificationInvalidationReason.HASH_MISMATCH)
    elif state == "reappeared":
        changes["reappeared_at"] = NOW
    row = _row("1", r"folder\subject.txt", **changes)
    view = InventoryReviewState("task-" + "1" * 32, "2" * 32,
        build_inventory_projection(1, (row, _row("2", "unverified.txt")), (
            ScanWarning(ScanWarningCode.ACCESS_DENIED, "unreadable", "read failed"),)),
        r"C:\root", True, 2, 0)
    rows = view.window(expected_revision=0, offset=0, limit=256)["rows"]
    assert next(item for item in rows if item["row_id"] == "1")["recorded_checksum"] == row.attestation.content.digest.hex()
    assert all(item["recorded_checksum"] is None for item in rows if item["row_id"] != "1")


def test_compact_windows_keep_complete_path_search_and_bound_unicode_labels():
    path = "ancestor\\" + "😀" * 1000 + ".txt"
    warning = ScanWarning(ScanWarningCode.SCALAR_UNREPRESENTABLE, path, "\x01" * 1024)
    view = InventoryReviewState("task-" + "1" * 32, "2" * 32,
        build_inventory_projection(1, (_row("1", path),), (warning,)), r"C:\root", False, 1, 0)
    _update(view, search_query="ancestor")
    rows = view.window(expected_revision=1, offset=0, limit=256)["rows"]
    assert any(row["row_id"] == "1" for row in rows)
    assert all(len(row["display"].encode("utf-16-le")) // 2 <= 300 for row in rows)
    notice = next(row for row in rows if row["warning"])
    assert notice["display"].startswith("scalar_unrepresentable: …")
    assert set(notice["warning"]) == {"code", "detail"}
    assert len(notice["warning"]["detail"].encode("utf-16-le")) // 2 == 300


def test_complete_inventory_256_row_envelope_has_margin_under_response_wall():
    import json
    from namisync.interfaces.web.bridge import snapshot_bridge_response_result

    # This valid projection exercises the former repeated-full-path failure.
    prefix = "\\".join(["文" * 250] * 100)
    paths = [prefix + rf"\item-{index:03}.txt" for index in range(256)]
    projection = build_inventory_projection(1, (), tuple(
        ScanWarning(ScanWarningCode.SCALAR_UNREPRESENTABLE, path, "\x01" * 1024) for path in paths))
    view = InventoryReviewState("task-" + "1" * 32, "2" * 32, projection, r"C:\root", False, 0, 0)
    actual = view.window(expected_revision=0, offset=0, limit=256)
    assert len(actual["rows"]) == 256
    snapshot_bridge_response_result(actual, "3" * 32)

    # A conservative all-fields row upper bound also covers ledger rows and
    # synthetic folders. Control escaping is six bytes per UTF-16 unit; IDs
    # stay 37 ASCII bytes (BLAKE2b), SQLite ids/scalars stay <=19 decimal bytes,
    # and view/frame/count integers are <= the 16-digit JavaScript safe maximum.
    row = _view().window(expected_revision=0, offset=1, limit=1)["rows"][0]
    assert set(row) == {"node_id", "display", "depth", "is_container", "visible_index",
        "parent_visible_index", "first_child_visible_index", "position_in_set", "set_size", "expanded",
        "row_kind", "row_id", "presence", "verification_state", "has_baseline", "recorded_checksum",
        "acknowledged", "reappeared", "size", "mtime_ns", "rollup", "warning"}
    assert set(row["rollup"]) == {"domain_count", "file_count", "present", "unverified", "verified", "modified",
        "reappeared", "unsupported", "missing", "mismatched", "acknowledged", "size", "size_overflow", "size_partial"}
    assert set(actual) == {"disposition", "view_revision", "offset", "total", "rows"}
    assert set(actual["rows"][0]["warning"]) == {"code", "detail"}
    row.update(display="\x01" * 300, row_id="9" * 19, recorded_checksum="f" * 32,
               size="9" * 19, mtime_ns="9" * 19, presence="unsupported",
               verification_state="unverified", warning={"code": "scalar_unrepresentable", "detail": "\x01" * 300})
    row["rollup"] = {key: "9" * 19 if key == "size" else False if type(value) is bool else 9007199254740991
                     for key, value in row["rollup"].items()}
    for key, value in tuple(row.items()):
        if type(value) is int or key in {"parent_visible_index", "first_child_visible_index"}:
            row[key] = 9007199254740991
        elif type(value) is bool or key == "expanded":
            row[key] = False
    bounded = {**actual, "view_revision": 9007199254740991, "offset": 9007199254740991,
               "total": 9007199254740991, "rows": [row] * 256}
    envelope = {"schema_version": 1, "request_id": "3" * 32, "ok": True, "result": bounded}
    size = len(json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    assert size < 2 * 1024 * 1024  # Derived margin, not a new runtime wall.
    snapshot_bridge_response_result(bounded, "3" * 32)
