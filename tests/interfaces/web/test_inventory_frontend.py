"""Production inventory pane and task routing, with bounded browser probes."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from _db_fixtures import NOW, attestation, file_stat
from _frontend_test_support import ASSET_ROOT, _node_executable, run_node_probe
from namisync.core.integrity import VerificationInvalidation, VerificationInvalidationReason
from namisync.core.models import EntryKind, ScanWarning, ScanWarningCode
from namisync.core.pathing import normalize_relative_path
from namisync.db.repositories import InventoryPresence, InventorySnapshot
from namisync.interfaces.web.inventory_review import InventoryReviewState
from namisync.workflows import PlanSortColumn, SortDirection, build_inventory_projection
from namisync.workflows.views import inventory_current_detail


PROJECT_ROOT = Path(__file__).parents[3]


def _fixture() -> dict[str, object]:
    stat = file_stat(size=9223372036854775807, mtime_ns=9223372036854775807)
    row = InventorySnapshot(
        "1", 1, r"folder\evidence.txt", normalize_relative_path(r"folder\evidence.txt"),
        EntryKind.FILE, InventoryPresence.PRESENT, stat, attestation(stat), NOW, NOW,
        "scope", None, None, None, None, None,
    )
    acknowledged = replace(row, row_id="2", rel_path=r"hidden\missing.txt",
        rel_path_key=normalize_relative_path(r"hidden\missing.txt"),
        presence=InventoryPresence.MISSING, acknowledged_at=NOW, missing_since=NOW)
    projection = build_inventory_projection(1, (row, acknowledged), (
        ScanWarning(ScanWarningCode.ACCESS_DENIED, "unreadable", "read failed"),))
    view = InventoryReviewState("task-" + "1" * 32, "2" * 32, projection, r"C:\root", False, 1, 1)
    views = {"default": {"summary": view.summary(), "window": view.window(expected_revision=0, offset=0, limit=256)}}
    for name, changes in (
        ("acknowledged", {"filters": frozenset({"acknowledged"})}),
        ("empty", {"search_query": "no matching path"}),
    ):
        view.update(expected_revision=view.view_revision, search_query=changes.get("search_query", ""),
            filters=changes.get("filters", frozenset()), sort_column=PlanSortColumn.PATH,
            sort_direction=SortDirection.ASCENDING, collapse_node_id=None, collapsed=None)
        views[name] = {"summary": view.summary(), "window": view.window(expected_revision=view.view_revision, offset=0, limit=256)}
    many = tuple(replace(row, row_id=str(index + 10), rel_path=rf"many\{index:03}.txt",
        rel_path_key=normalize_relative_path(rf"many\{index:03}.txt")) for index in range(300))
    maximum = InventoryReviewState(view.task_id, view.request_id, build_inventory_projection(1, many),
        r"C:\root", True, 300, 0)
    views["maximum"] = {"summary": maximum.summary(), "window": maximum.window(expected_revision=0, offset=0, limit=256)}
    invalidated = replace(row, invalidation=VerificationInvalidation(NOW, VerificationInvalidationReason.HASH_MISMATCH))
    detail = {"disposition": "current", "view_revision": 0, "node_id": projection.node_id_by_row_id["1"]}
    return {"views": views, "detail": {**detail, "detail": inventory_current_detail(row)},
        "invalidated_detail": {**detail, "detail": inventory_current_detail(invalidated)},
        "tail": maximum.window(expected_revision=0, offset=268, limit=256)}


def _run(probe: str, fixture: Path) -> None:
    node = _node_executable()
    assert node is not None, "Node.js is required for the inventory desktop witness"
    completed = run_node_probe([
        str(node), str(PROJECT_ROOT / "tests/assets" / probe),
        str(PROJECT_ROOT / ASSET_ROOT), str(fixture),
    ], timeout=15)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout == "ok\n"
    assert completed.stderr == ""


def test_inventory_pane_browses_server_views_and_current_evidence(tmp_path: Path) -> None:
    fixture = tmp_path / "inventory.json"
    fixture.write_text(json.dumps(_fixture()), encoding="utf-8")
    _run("inventory_review_probe.mjs", fixture)


def test_inventory_app_routes_released_tasks_and_rejects_stale_reads(tmp_path: Path) -> None:
    fixture = tmp_path / "inventory.json"
    fixture.write_text(json.dumps(_fixture()), encoding="utf-8")
    _run("inventory_app_probe.mjs", fixture)
