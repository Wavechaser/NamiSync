"""Real Inventory view specimens shared by browser probes and the gallery."""

from __future__ import annotations

from dataclasses import replace

from _db_fixtures import NOW, attestation, file_stat
from namisync.core.integrity import VerificationInvalidation, VerificationInvalidationReason
from namisync.core.models import EntryKind, ScanWarning, ScanWarningCode
from namisync.core.pathing import normalize_relative_path
from namisync.db.repositories import InventoryPresence, InventorySnapshot
from namisync.interfaces.web.inventory_review import InventoryReviewState
from namisync.workflows import PlanSortColumn, SortDirection, build_inventory_projection
from namisync.workflows.views import inventory_current_detail


def inventory_probe_fixture() -> dict[str, object]:
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
    view = InventoryReviewState("task-" + "1" * 32, "2" * 32, projection, r"C:\root", False, 1, 1, scan_request_id="2" * 32)
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
        r"C:\root", True, 300, 0, scan_request_id=view.request_id)
    views["maximum"] = {"summary": maximum.summary(), "window": maximum.window(expected_revision=0, offset=0, limit=256)}
    views["middle"] = {"summary": maximum.summary(), "window": maximum.window(expected_revision=0, offset=240, limit=256)}
    invalidated = replace(row, invalidation=VerificationInvalidation(NOW, VerificationInvalidationReason.HASH_MISMATCH))
    missing_folder = replace(row, row_id="3", rel_path="missing_folder",
        rel_path_key=normalize_relative_path("missing_folder"), entry_kind=EntryKind.DIRECTORY,
        presence=InventoryPresence.MISSING, observed=replace(stat, kind=EntryKind.DIRECTORY),
        attestation=None, last_verified_at=None, missing_since=NOW)
    folder_view = InventoryReviewState(view.task_id, view.request_id,
        build_inventory_projection(1, (missing_folder,)), r"C:\root", True, 0, 1, scan_request_id=view.request_id)
    detail = {"disposition": "current", "view_revision": 0, "node_id": projection.node_id_by_row_id["1"],
              "snapshot": {"path": row.rel_path, "warning": None}}
    snapshots = {node.node_id: {"disposition": "current", "view_revision": 0, "node_id": node.node_id,
        "detail": None, "snapshot": {"path": node.warning.rel_path if node.warning else node.rel_path,
            "warning": None if node.warning is None else {"code": node.warning.code.value, "detail": node.warning.detail}}}
        for node in projection.nodes if node.position != 0 and node.row is None}
    return {"views": views, "missing_folder": {"summary": folder_view.summary(),
        "window": folder_view.window(expected_revision=0, offset=0, limit=256)},
        "detail": {**detail, "detail": inventory_current_detail(row)},
        "invalidated_detail": {**detail, "detail": inventory_current_detail(invalidated)},
        "snapshots": snapshots, "tail": maximum.window(expected_revision=0, offset=268, limit=256)}


def inventory_gallery_fixture() -> dict[str, object]:
    stat = file_stat(size=10, mtime_ns=1000000000)
    baseline = attestation(stat)
    baseline = replace(baseline, content=replace(baseline.content,
        digest=bytes.fromhex("0123456789abcdef0123456789abcdef")))
    row = InventorySnapshot(
        "1", 1, "evidence-0.txt", normalize_relative_path("evidence-0.txt"),
        EntryKind.FILE, InventoryPresence.PRESENT, stat, baseline,
        NOW.replace(month=12, day=31, hour=23, minute=4, second=59, microsecond=999999),
        NOW, "scope", None, None, None, None, None,
    )
    rows = tuple(replace(row, row_id=str(index + 1), rel_path=f"evidence-{index}.txt",
        rel_path_key=normalize_relative_path(f"evidence-{index}.txt")) for index in range(300))
    view = InventoryReviewState("task-" + "2" * 32, "1" * 32,
        build_inventory_projection(1, rows), r"C:\recorded", True, 300, 0,
        scan_scope=("location", None), scan_request_id="1" * 32)
    first = view.window(expected_revision=0, offset=0, limit=256)
    tail = view.window(expected_revision=0, offset=256, limit=256)
    return {"summary": view.summary(), "window": first,
        "rows": first["rows"] + tail["rows"], "detail": inventory_current_detail(row)}
