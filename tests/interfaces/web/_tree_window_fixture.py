"""Cross-layer production fixture for renderer-visible tree windows."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from namisync.core.pathing import normalize_relative_path
from namisync.interfaces.web.visible_sequence import (
    VisibleSequence,
    VisibleSequenceParameters,
    derive_visible_sequence,
    to_visible_window_view,
    window_visible_sequence,
)
from namisync.workflows.node_tree import (
    NodeTree,
    NodeTreeKind,
    NodeTreeMember,
    build_node_tree,
)


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
_WINDOW_KEYS = {"offset", "total", "rows"}


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
    """Derive every positive renderer window from one workflow tree."""

    tree = _build_source_tree()
    projection_id = tree.node_id_for_path_key(
        normalize_relative_path(PROJECTION_DISPLAY)
    )
    layout_control_id = tree.node_id_for_path_key(
        normalize_relative_path(LAYOUT_CONTROL_DISPLAY)
    )
    ordinary_id = tree.node_id_for_path_key(
        normalize_relative_path(ORDINARY_UNICODE_DISPLAY)
    )
    long_id = tree.node_id_for_path_key(
        normalize_relative_path(LONG_UNICODE_DISPLAY)
    )

    expanded = _derive(tree)
    collapsed = _derive(tree, collapsed=(projection_id,))
    projected_empty = _derive(tree, counts={projection_id: 1})
    empty = _derive(tree, counts={})
    layout_control = _derive(tree, counts={layout_control_id: 1})
    total = len(expanded.visible_positions)

    views = {
        "head": _view(tree, expanded, offset=0, limit=4),
        "next": _view(tree, expanded, offset=4, limit=4),
        "tail": _view(tree, expanded, offset=total - 4, limit=4),
        "empty": _view(tree, empty, offset=0, limit=4),
        "maximum": _view(tree, expanded, offset=0, limit=256),
        "pointer_expanded": _view(tree, expanded, offset=0, limit=3),
        "pointer_collapsed": _view(tree, collapsed, offset=0, limit=3),
        "projected_empty": _view(
            tree,
            projected_empty,
            offset=0,
            limit=3,
        ),
        "layout_control": _view(
            tree,
            layout_control,
            offset=0,
            limit=2,
        ),
    }
    manifest: dict[str, object] = {
        "schema": TREE_WINDOW_FIXTURE_SCHEMA,
        "node_ids": {
            "projection": projection_id,
            "layout_control": layout_control_id,
            "ordinary_unicode": ordinary_id,
            "long_unicode": long_id,
        },
        "views": views,
    }
    _assert_manifest(
        manifest,
        projection_id,
        layout_control_id,
        ordinary_id,
        long_id,
    )
    return manifest


def _build_source_tree() -> NodeTree:
    members = (
        _member("projection", PROJECTION_DISPLAY, is_container=True),
        _member("projection-child", f"{PROJECTION_DISPLAY}\\Child.txt"),
        _member("layout-control", LAYOUT_CONTROL_DISPLAY),
        _member("ordinary-unicode", ORDINARY_UNICODE_DISPLAY),
        _member("long-unicode", LONG_UNICODE_DISPLAY),
        *(
            _member(f"bulk-{index:03d}", f"Bulk-{index:03d}.txt")
            for index in range(270)
        ),
    )
    return build_node_tree(
        tree_kind=NodeTreeKind.PLAN,
        scope_identity="stage-6-cross-layer-fixture",
        members=members,
    )


def _member(
    member_id: str,
    rel_path: str,
    *,
    is_container: bool = False,
) -> NodeTreeMember:
    return NodeTreeMember(
        member_id=member_id,
        rel_path=rel_path,
        rel_path_key=normalize_relative_path(rel_path),
        is_container=is_container,
    )


def _derive(
    tree: NodeTree,
    *,
    collapsed: tuple[str, ...] = (),
    counts: dict[str, int] | None = None,
) -> VisibleSequence:
    sequence = derive_visible_sequence(
        tree.nodes,
        VisibleSequenceParameters(
            collapsed_node_ids=frozenset(collapsed),
            match_counts_by_node_id=counts,
        ),
    )
    assert sequence.nodes is tree.nodes
    return sequence


def _view(
    tree: NodeTree,
    sequence: VisibleSequence,
    *,
    offset: int,
    limit: int,
) -> dict[str, object]:
    window = window_visible_sequence(sequence, offset=offset, limit=limit)
    assert all(
        row.node is tree.nodes[row.node.position] for row in window.rows
    )
    return to_visible_window_view(window)


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
            isinstance(row, dict) and set(row) == _ROW_KEYS for row in rows
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
