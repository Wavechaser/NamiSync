"""Cross-layer production fixture for renderer-visible tree windows."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

from _db_fixtures import NOW, file_stat, operation, plan
from namisync.core.models import EntryKind
from namisync.core.pathing import normalize_relative_path
from namisync.core.planning import OperationKind
from namisync.core.preflight import Verdict
from namisync.db.repositories import InventoryPresence, InventorySnapshot
from namisync.interfaces.web.inventory_review import InventoryReviewState
from namisync.interfaces.web.plan_review import PlanReviewState
from namisync.workflows import (
    PlanSortColumn, SortDirection, build_inventory_projection, build_plan_projection,
)
from namisync.workflows.models import PlanArtifact, PlanRequest
from namisync.workflows.node_tree import NodeTreeKind


TREE_WINDOW_FIXTURE_SCHEMA = "namisync-tree-window-fixture-v1"
PROJECTION_DISPLAY = "00 Projected container"
LAYOUT_CONTROL_DISPLAY = "01 Layout-\u202eRLO-\u2066LRI-\u27e6marker\u27e7.txt"
ORDINARY_UNICODE_DISPLAY = (
    "02 Wave-\U0001f30a\ufe0f-e\u0301-"
    "\u0627\u0644\u0639\u0631\u0628\u064a\u0629-\u05e2\u05d1\u05e8\u05d9\u05ea-"
    "A\u200cB\u200dC-\U000e0020-&-\u6d77.txt"
)
LONG_UNICODE_DISPLAY = f"03 Long-{'\u6ce2' * 200}.txt"
_FILENAME = "tree-window-fixture.json"
_ROW_KEYS = {
    "node_id",
    "display",
    "depth",
    "is_container",
    "visible_index",
    "parent_visible_index",
    "first_child_visible_index",
    "position_in_set",
    "set_size",
    "expanded",
}
_WINDOW_KEYS = {
    "offset", "total", "rows", "disposition", "view_revision", "highlight_revision",
}


@dataclass(frozen=True, slots=True)
class TreeWindowFixture:
    """The exact temporary manifest supplied to JavaScript evidence."""

    path: Path
    text: str
    size: int
    sha256: str


def write_tree_window_fixture(directory: Path) -> TreeWindowFixture:
    """Write one canonical UTF-8 manifest beneath an existing directory."""

    manifest = build_tree_window_manifest()
    text = json.dumps(
        manifest,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    encoded = text.encode("utf-8")
    assert json.loads(text) == manifest
    assert all(
        character.encode("utf-8") in encoded
        for character in "\u202e\u2066\u27e6\u27e7"
    )
    path = directory / _FILENAME
    path.write_bytes(encoded)
    assert path.read_bytes() == encoded
    return TreeWindowFixture(
        path=path,
        text=text,
        size=len(encoded),
        sha256=hashlib.sha256(encoded).hexdigest(),
    )


def build_tree_window_manifest() -> dict[str, object]:
    """Produce renderer windows through the real Plan review owner."""

    review = _build_review(NodeTreeKind.PLAN)
    ids = {
        label: next(
            node.node_id for node in review.projection.nodes
            if node.rel_path_key == normalize_relative_path("Fixture\\" + display)
        )
        for label, display in (
            ("projection", PROJECTION_DISPLAY),
            ("layout_control", LAYOUT_CONTROL_DISPLAY),
            ("ordinary_unicode", ORDINARY_UNICODE_DISPLAY),
            ("long_unicode", LONG_UNICODE_DISPLAY),
        )
    }
    total = review.summary()["visible_row_count"]
    views = {
        name: review.window(expected_revision=0, offset=offset, limit=limit)
        for name, offset, limit in (
            ("head", 0, 4), ("next", 4, 4), ("tail", total - 4, 4),
            ("maximum", 0, 256), ("pointer_expanded", 0, 3),
        )
    }
    _update(review, collapse_node_id=ids["projection"], collapsed=True)
    views["pointer_collapsed"] = review.window(
        expected_revision=review.view_revision, offset=0, limit=3,
    )
    # The directory operation matches while its COPY child is filtered out.
    _update(review, filters=frozenset({"mkdir"}))
    views["projected_empty"] = review.window(
        expected_revision=review.view_revision, offset=0, limit=3,
    )
    _update(review, search_query="no matching path")
    views["empty"] = review.window(
        expected_revision=review.view_revision, offset=0, limit=4,
    )
    _update(review, search_query=LAYOUT_CONTROL_DISPLAY)
    views["layout_control"] = review.window(
        expected_revision=review.view_revision, offset=0, limit=2,
    )
    manifest = {"schema": TREE_WINDOW_FIXTURE_SCHEMA, "node_ids": ids, "views": views}
    _assert_manifest(
        manifest, ids["projection"], ids["layout_control"],
        ids["ordinary_unicode"], ids["long_unicode"],
    )
    return manifest


def _build_review(kind: NodeTreeKind) -> PlanReviewState | InventoryReviewState:
    """Build domain facts, project them, and let the review owner serialize."""

    paths = (
        (PROJECTION_DISPLAY, True),
        (f"{PROJECTION_DISPLAY}\\Child.txt", False),
        (LAYOUT_CONTROL_DISPLAY, False),
        (ORDINARY_UNICODE_DISPLAY, False),
        (LONG_UNICODE_DISPLAY, False),
        *((f"Bulk-{index:03d}.txt", False) for index in range(270)),
    )
    paths = tuple(("Fixture\\" + path, container) for path, container in paths)
    stat = file_stat(size=7, mtime_ns=9223372036854775807)
    request_id = "3" * 32
    if kind is NodeTreeKind.PLAN:
        operations = tuple(
            operation(
                OperationKind.MKDIR if container else OperationKind.COPY,
                source_path=path, target_path=path,
                source=replace(stat, kind=EntryKind.DIRECTORY) if container else stat,
                intended=replace(stat, kind=EntryKind.DIRECTORY) if container else stat,
            )
            for path, container in paths
        )
        value = plan(operations)
        request = PlanRequest(request_id, value.source_root.path, value.target_root.path)
        scan = SimpleNamespace(files=(), directories=(), unsupported=(), warnings=())
        artifact = PlanArtifact(
            request, scan, scan, value, Verdict(True, (), SimpleNamespace()),
        )
        return PlanReviewState(
            "task-" + request_id, request_id,
            build_plan_projection(request_id, artifact),
            0, "reviewing", "source", "target",
        )
    rows = tuple(
        InventorySnapshot(
            str(index), 1, path, normalize_relative_path(path),
            EntryKind.DIRECTORY if container else EntryKind.FILE,
            InventoryPresence.PRESENT,
            replace(stat, kind=EntryKind.DIRECTORY) if container else stat,
            None, NOW, None, "scope", None, None, None, None, None,
        )
        for index, (path, container) in enumerate(paths, 1)
    )
    return InventoryReviewState(
        "task-" + request_id, request_id,
        build_inventory_projection(1, rows), r"C:\root", True, len(rows), 0,
    )


def _update(
    review, *, search_query="", filters=frozenset(),
    collapse_node_id=None, collapsed=None,
):
    return review.update(
        expected_revision=review.view_revision,
        search_query=search_query, filters=filters,
        sort_column=PlanSortColumn.PATH, sort_direction=SortDirection.ASCENDING,
        collapse_node_id=collapse_node_id, collapsed=collapsed,
    )


def _assert_manifest(
    manifest: dict[str, object],
    projection_id: str,
    layout_control_id: str,
    ordinary_id: str,
    long_id: str,
) -> None:
    assert set(manifest) == {"schema", "node_ids", "views"}
    assert manifest["schema"] == TREE_WINDOW_FIXTURE_SCHEMA
    assert manifest["node_ids"] == {
        "projection": projection_id,
        "layout_control": layout_control_id,
        "ordinary_unicode": ordinary_id,
        "long_unicode": long_id,
    }
    views = manifest["views"]
    assert isinstance(views, dict)
    assert set(views) == {
        "head",
        "next",
        "tail",
        "empty",
        "maximum",
        "pointer_expanded",
        "pointer_collapsed",
        "projected_empty",
        "layout_control",
    }
    for view in views.values():
        assert isinstance(view, dict) and set(view) == _WINDOW_KEYS
        rows = view["rows"]
        assert isinstance(rows, list)
        assert all(
            isinstance(row, dict) and _ROW_KEYS <= set(row) for row in rows
        )
        assert all(
            re.fullmatch(r"node-[0-9a-f]{32}", row["node_id"])
            for row in rows
        )

    maximum = views["maximum"]
    assert len(maximum["rows"]) == 256
    assert maximum["total"] > 256
    assert views["head"]["total"] == maximum["total"]
    assert views["next"]["offset"] == 4
    tail = views["tail"]
    assert tail["offset"] + len(tail["rows"]) == tail["total"]
    assert tail["rows"][-1]["visible_index"] == tail["total"] - 1
    assert views["empty"]["offset"] == 0
    assert views["empty"]["total"] == 0
    assert views["empty"]["rows"] == []

    states = []
    for name in (
        "pointer_expanded",
        "pointer_collapsed",
        "projected_empty",
    ):
        row = next(
            row
            for row in views[name]["rows"]
            if row["node_id"] == projection_id
        )
        states.append(row["expanded"])
    assert states == [True, False, None]

    layout_rows = views["layout_control"]["rows"]
    layout_row = next(
        row for row in layout_rows if row["node_id"] == layout_control_id
    )
    assert layout_row["display"] == LAYOUT_CONTROL_DISPLAY
    assert all(
        character in layout_row["display"]
        for character in "\u202e\u2066\u27e6\u27e7"
    )
    next_rows = views["next"]["rows"]
    assert [row["node_id"] for row in next_rows[:2]] == [
        ordinary_id,
        long_id,
    ]
    assert [row["display"] for row in next_rows[:2]] == [
        ORDINARY_UNICODE_DISPLAY,
        LONG_UNICODE_DISPLAY,
    ]
    assert len(ORDINARY_UNICODE_DISPLAY.encode("utf-8")) > len(
        ORDINARY_UNICODE_DISPLAY
    )
    assert len(LONG_UNICODE_DISPLAY.encode("utf-8")) > 256
