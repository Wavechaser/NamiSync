"""BR-G-34 evidence for the pure shared visible-sequence core."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType

import pytest

from namisync.core.pathing import normalize_relative_path
from namisync.interfaces.web import visible_sequence as visible_module
from namisync.interfaces.web.visible_sequence import (
    VisibleAnchor,
    VisibleSequenceParameters,
    derive_visible_sequence,
    resolve_visible_anchor,
    to_visible_window_view,
    window_visible_sequence,
)
from namisync.workflows.node_tree import (
    NodeTree,
    NodeTreeKind,
    NodeTreeMember,
    build_node_tree,
)


MODULE = Path(__file__).parents[3] / "namisync/interfaces/web/visible_sequence.py"


@dataclass(frozen=True, slots=True)
class _Node:
    node_id: str
    display: str
    position: int
    depth: int
    parent_index: int | None
    subtree_end: int
    is_container: bool


class _ObservedNode:
    __slots__ = ("_node", "_reads")

    def __init__(self, node: _Node, reads: list[int]) -> None:
        self._node = node
        self._reads = reads

    def __getattr__(self, name: str):
        self._reads[0] += 1
        return getattr(self._node, name)


def _nodes() -> tuple[_Node, ...]:
    # root
    #   Alpha
    #     Straße.txt
    #     composed-é.txt
    #   Beta
    #     literal-[.*].txt
    return (
        _Node("root", "All items", 0, 0, None, 6, True),
        _Node("alpha", "Alpha", 1, 1, 0, 4, True),
        _Node("street", "Straße.txt", 2, 2, 1, 3, False),
        _Node("composed", "composed-é.txt", 3, 2, 1, 4, False),
        _Node("beta", "Beta", 4, 1, 0, 6, True),
        _Node("literal", "literal-[.*].txt", 5, 2, 4, 6, False),
    )


def _parameters(
    *,
    collapsed=(),
    search="",
    counts=None,
) -> VisibleSequenceParameters:
    return VisibleSequenceParameters(
        collapsed_node_ids=collapsed,
        search_query=search,
        match_counts_by_node_id=counts,
    )


def _tree(kind: NodeTreeKind) -> NodeTree:
    return build_node_tree(
        tree_kind=kind,
        scope_identity=f"{kind.value}-scope",
        members=(
            NodeTreeMember(
                "member-a",
                "Alpha\\One.txt",
                normalize_relative_path("Alpha\\One.txt"),
            ),
            NodeTreeMember(
                "member-b",
                "Beta\\Two.txt",
                normalize_relative_path("Beta\\Two.txt"),
            ),
        ),
    )


def _ids(sequence) -> tuple[str, ...]:
    return tuple(
        sequence.nodes[position].node_id
        for position in sequence.visible_positions
    )


@pytest.mark.parametrize("kind", [NodeTreeKind.PLAN, NodeTreeKind.INVENTORY])
def test_br_g_34_real_workflow_tree_is_used_directly_without_dto_copy(
    kind: NodeTreeKind,
) -> None:
    tree = _tree(kind)

    sequence = derive_visible_sequence(tree.nodes, _parameters())
    window = window_visible_sequence(sequence, offset=1, limit=2)

    assert sequence.nodes is tree.nodes
    assert sequence.visible_positions == tuple(range(len(tree.nodes)))
    assert _ids(sequence) == tuple(node.node_id for node in tree.nodes)
    assert tree.nodes[0].display == "All items"
    assert tree.nodes[1].display == tree.nodes[1].rel_path
    assert tuple(row.node for row in window.rows) == tree.nodes[1:3]
    assert all(
        row.node is tree.nodes[row.node.position] for row in window.rows
    )
    assert not hasattr(visible_module, "VisibleSequenceNode")
    assert sequence.filtered_item_count is None


def test_br_g_34_empty_workflow_projection_keeps_its_single_root() -> None:
    tree = build_node_tree(
        tree_kind=NodeTreeKind.INVENTORY,
        scope_identity="empty-location",
        members=(),
    )

    sequence = derive_visible_sequence(tree.nodes, _parameters())

    assert sequence.nodes is tree.nodes
    assert _ids(sequence) == (tree.root_node_id,)
    assert tree.nodes[0].display == "All items"
    assert sequence.has_retained_children == (False,)
    assert window_visible_sequence(
        sequence,
        offset=0,
        limit=1,
    ).rows[0].expanded is None


def test_br_g_2_stage_6_visible_core_imports_no_project_or_path_helper() -> None:
    source = MODULE.read_text(encoding="utf-8")
    parsed = ast.parse(source)
    imports = [
        node
        for node in ast.walk(parsed)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]

    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("namisync")
        for node in imports
    )
    assert "path" not in source.casefold()
    assert "regex" not in source.casefold()
    assert "glob" not in source.casefold()


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        (lambda nodes: (), ValueError),
        (lambda nodes: (replace(nodes[0], position=True),), TypeError),
        (lambda nodes: (replace(nodes[0], position=1),), ValueError),
        (lambda nodes: (replace(nodes[0], depth=1),), ValueError),
        (lambda nodes: (replace(nodes[0], parent_index=0),), ValueError),
        (lambda nodes: (replace(nodes[0], subtree_end=1), *nodes[1:]), ValueError),
        (lambda nodes: (*nodes[:-1], replace(nodes[-1], position=4)), ValueError),
        (lambda nodes: (*nodes[:-1], replace(nodes[-1], node_id="root")), ValueError),
        (lambda nodes: (*nodes[:4], replace(nodes[4], depth=0), nodes[5]), ValueError),
        (
            lambda nodes: (
                *nodes[:4],
                replace(nodes[4], parent_index=None),
                nodes[5],
            ),
            ValueError,
        ),
        (
            lambda nodes: (
                *nodes[:4],
                replace(nodes[4], parent_index=1),
                nodes[5],
            ),
            ValueError,
        ),
        (lambda nodes: (*nodes[:5], replace(nodes[5], depth=3)), ValueError),
        (lambda nodes: (*nodes[:5], replace(nodes[5], parent_index=5)), ValueError),
        (lambda nodes: (*nodes[:5], replace(nodes[5], subtree_end=7)), ValueError),
        (
            lambda nodes: (
                *nodes[:2],
                replace(nodes[2], subtree_end=4),
                *nodes[3:],
            ),
            ValueError,
        ),
        (
            lambda nodes: (
                nodes[0],
                replace(nodes[1], subtree_end=5),
                *nodes[2:],
            ),
            ValueError,
        ),
        (
            lambda nodes: (
                nodes[0],
                replace(nodes[1], is_container=False),
                *nodes[2:],
            ),
            ValueError,
        ),
    ],
)
def test_br_g_34_malformed_preorder_structure_is_refused(mutation, error) -> None:
    with pytest.raises(error):
        changed = mutation(_nodes())
        derive_visible_sequence(changed, _parameters())


@pytest.mark.parametrize(
    "arguments",
    [
        {"node_id": ""},
        {"node_id": "bad\ud800"},
        {"display": "bad\ud800"},
        {"position": True},
        {"depth": True},
        {"parent_index": True},
        {"subtree_end": True},
        {"is_container": 1},
    ],
)
def test_br_g_34_structural_node_fields_are_validated(arguments) -> None:
    node = replace(_nodes()[0], **arguments)

    with pytest.raises((TypeError, ValueError)):
        derive_visible_sequence((node,), _parameters())


def test_br_g_34_structural_node_must_supply_every_required_field() -> None:
    class _MissingDisplay:
        node_id = "root"
        position = 0
        depth = 0
        parent_index = None
        subtree_end = 1
        is_container = True

    with pytest.raises(TypeError, match="provide display"):
        derive_visible_sequence((_MissingDisplay(),), _parameters())


class _PoisonNodes:
    def __iter__(self):
        raise AssertionError("nodes were traversed before search refusal")

    def __len__(self):
        raise AssertionError("nodes were measured before search refusal")

    def __getitem__(self, index):
        raise AssertionError("nodes were read before search refusal")


def test_br_g_34_search_cap_is_utf8_bytes_and_checked_before_traversal() -> None:
    assert len("x" * 257) == 257
    derive_visible_sequence(_nodes(), _parameters(search="x" * 257))

    boundaries = ("x" * 65_536, chr(0x1F600) * 16_384)
    for boundary in boundaries:
        accepted = _parameters(search=boundary)
        assert len(accepted.search_query.encode("utf-8")) == 65_536
        derive_visible_sequence(_nodes(), accepted)

    refused = boundaries[1] + "a"
    with pytest.raises(ValueError, match="65,536 UTF-8 bytes"):
        _parameters(search=refused)

    poisoned = _parameters()
    object.__setattr__(poisoned, "search_query", refused)
    with pytest.raises(ValueError, match="65,536 UTF-8 bytes"):
        derive_visible_sequence(_PoisonNodes(), poisoned)  # type: ignore[arg-type]


def test_br_g_34_search_type_and_unicode_are_checked_before_traversal() -> None:
    class _StringSubclass(str):
        pass

    for refused in (_StringSubclass("query"), "bad\ud800"):
        parameters = _parameters()
        object.__setattr__(parameters, "search_query", refused)
        with pytest.raises((TypeError, ValueError)):
            derive_visible_sequence(  # type: ignore[arg-type]
                _PoisonNodes(),
                parameters,
            )


@pytest.mark.parametrize("query", [".", "[", ".*+?^$(){}|\\"])
def test_br_g_34_search_is_literal_display_only(query: str) -> None:
    sequence = derive_visible_sequence(_nodes(), _parameters(search=query))
    expected = {
        ".": ("root", "alpha", "street", "composed", "beta", "literal"),
        "[": ("root", "beta", "literal"),
        ".*+?^$(){}|\\": (),
    }[query]

    assert _ids(sequence) == expected


def test_br_g_34_search_casefolds_without_trimming_or_normalization() -> None:
    nodes = _nodes()

    assert _ids(derive_visible_sequence(nodes, _parameters(search="STRASSE"))) == (
        "root",
        "alpha",
        "street",
    )
    assert _ids(derive_visible_sequence(nodes, _parameters(search=" Alpha "))) == ()
    assert _ids(derive_visible_sequence(nodes, _parameters(search="e\u0301"))) == ()
    with pytest.raises(ValueError, match="valid Unicode"):
        _parameters(search="bad\ud800")


def test_br_g_34_filesystem_layout_controls_stay_raw_until_rendering() -> None:
    control_display = "report-\u202eabc.txt-\u200b"
    marker_display = "literal-⟦U+202E⟧.txt"
    nodes = (
        _Node("root", "All items", 0, 0, None, 3, True),
        _Node("control", control_display, 1, 1, 0, 2, False),
        _Node("marker", marker_display, 2, 1, 0, 3, False),
    )

    sequence = derive_visible_sequence(nodes, _parameters())
    view = to_visible_window_view(
        window_visible_sequence(sequence, offset=0, limit=3)
    )

    assert sequence.nodes is nodes
    assert sequence.nodes[1].display == control_display
    assert sequence.nodes[2].display == marker_display
    assert view["rows"][1]["display"] == control_display
    assert view["rows"][2]["display"] == marker_display
    assert _ids(
        derive_visible_sequence(nodes, _parameters(search="\u202e"))
    ) == ("root", "control")
    assert _ids(
        derive_visible_sequence(nodes, _parameters(search="⟦U+202E⟧"))
    ) == ("root", "marker")


def test_br_g_34_filter_retention_precedes_collapse_and_counting() -> None:
    counts = {"street": 2, "literal": 3}
    sequence = derive_visible_sequence(
        _nodes(),
        _parameters(collapsed={"alpha"}, search="t", counts=counts),
    )

    assert _ids(sequence) == ("root", "alpha", "beta", "literal")
    assert sequence.filtered_item_count == 5
    assert "street" not in sequence.visible_index_by_node_id
    assert sequence.source_position_by_node_id["street"] == 2


def test_br_g_34_sparse_filter_and_search_are_conjunctive() -> None:
    no_filter = derive_visible_sequence(_nodes(), _parameters(search="beta"))
    empty_filter = derive_visible_sequence(_nodes(), _parameters(counts={}))
    filtered = derive_visible_sequence(
        _nodes(),
        _parameters(search="strasse", counts={"alpha": 20, "street": 2}),
    )

    assert _ids(no_filter) == ("root", "beta")
    assert no_filter.filtered_item_count is None
    assert _ids(empty_filter) == ()
    assert empty_filter.filtered_item_count == 0
    assert _ids(filtered) == ("root", "alpha", "street")
    assert filtered.filtered_item_count == 2


@pytest.mark.parametrize(
    "counts",
    [
        {"missing": 0},
        {"street": True},
        {"street": -1},
        {"street": 1.0},
    ],
)
def test_br_g_34_filter_mapping_refuses_unknown_and_nonexact_counts(counts) -> None:
    with pytest.raises((TypeError, ValueError)):
        derive_visible_sequence(_nodes(), _parameters(counts=counts))


@pytest.mark.parametrize("collapsed", [{"missing"}, {"street"}])
def test_br_g_34_collapsed_ids_must_name_known_containers(collapsed) -> None:
    with pytest.raises(ValueError):
        derive_visible_sequence(_nodes(), _parameters(collapsed=collapsed))


def test_br_g_34_active_tree_metadata_is_global_and_filter_aware() -> None:
    expanded = derive_visible_sequence(_nodes(), _parameters())
    collapsed = derive_visible_sequence(
        _nodes(),
        _parameters(collapsed={"alpha"}),
    )
    filtered = derive_visible_sequence(
        _nodes(),
        _parameters(search="strasse"),
    )

    assert expanded.parent_visible_indexes == (None, 0, 1, 1, 0, 4)
    assert expanded.first_child_visible_indexes == (1, 2, None, None, 5, None)
    assert expanded.has_retained_children == (
        True,
        True,
        False,
        False,
        True,
        False,
    )
    assert expanded.positions_in_set == (1, 1, 1, 2, 2, 1)
    assert expanded.set_sizes == (1, 2, 2, 2, 2, 1)

    assert collapsed.parent_visible_indexes == (None, 0, 0, 2)
    assert collapsed.first_child_visible_indexes == (1, None, 3, None)
    assert collapsed.has_retained_children == (True, True, True, False)
    assert collapsed.positions_in_set == (1, 1, 2, 1)
    assert collapsed.set_sizes == (1, 2, 2, 1)
    collapsed_rows = window_visible_sequence(collapsed, offset=0, limit=4).rows
    assert tuple(row.expanded for row in collapsed_rows) == (
        True,
        False,
        True,
        None,
    )

    assert _ids(filtered) == ("root", "alpha", "street")
    assert filtered.parent_visible_indexes == (None, 0, 1)
    assert filtered.has_retained_children == (True, True, False)
    assert filtered.positions_in_set == (1, 1, 1)
    assert filtered.set_sizes == (1, 1, 1)


def test_br_g_34_projected_empty_container_is_an_accessibility_end_node() -> None:
    sequence = derive_visible_sequence(
        _nodes(),
        _parameters(search="alpha"),
    )

    assert _ids(sequence) == ("root", "alpha")
    assert sequence.has_retained_children == (True, False)
    rows = window_visible_sequence(sequence, offset=0, limit=2).rows
    assert tuple(row.expanded for row in rows) == (True, None)
    assert rows[1].node.is_container is True
    assert rows[1].first_child_visible_index is None


def test_br_g_34_retained_child_metadata_rejects_invalid_shapes() -> None:
    sequence = derive_visible_sequence(_nodes(), _parameters())

    with pytest.raises(ValueError, match="match visible positions"):
        replace(sequence, has_retained_children=(True,))
    with pytest.raises(TypeError, match="contain bools"):
        replace(
            sequence,
            has_retained_children=(True, True, 0, False, True, False),
        )
    with pytest.raises(ValueError, match="only containers"):
        replace(
            sequence,
            has_retained_children=(True, True, True, False, True, False),
        )
    with pytest.raises(ValueError, match="requires a retained child"):
        replace(
            sequence,
            has_retained_children=(False,) * len(sequence.visible_positions),
        )


def test_br_g_34_inputs_indexes_and_results_are_immutable_snapshots() -> None:
    collapsed = {"alpha"}
    counts = {"street": 2}
    node_list = list(_nodes())
    parameters = _parameters(collapsed=collapsed, counts=counts)
    sequence = derive_visible_sequence(node_list, parameters)
    before = _ids(sequence)

    collapsed.clear()
    counts.clear()
    node_list.clear()

    assert parameters.collapsed_node_ids == frozenset({"alpha"})
    assert dict(parameters.match_counts_by_node_id or {}) == {"street": 2}
    assert _ids(sequence) == before
    assert type(sequence.source_position_by_node_id) is MappingProxyType
    assert type(sequence.visible_index_by_node_id) is MappingProxyType
    assert type(sequence.has_retained_children) is tuple
    with pytest.raises(TypeError):
        sequence.source_position_by_node_id["new"] = 9  # type: ignore[index]
    with pytest.raises(TypeError):
        sequence.visible_index_by_node_id["new"] = 9  # type: ignore[index]


def test_br_g_34_window_is_exact_bounded_and_wraps_only_requested_rows() -> None:
    nodes = tuple(
        _Node(
            node_id=f"node-{position}",
            display=f"Node {position}",
            position=position,
            depth=0 if position == 0 else 1,
            parent_index=None if position == 0 else 0,
            subtree_end=257 if position == 0 else position + 1,
            is_container=position == 0,
        )
        for position in range(257)
    )
    sequence = derive_visible_sequence(nodes, _parameters())

    first = window_visible_sequence(sequence, offset=0, limit=256)
    end = window_visible_sequence(sequence, offset=257, limit=1)
    beyond = window_visible_sequence(sequence, offset=999, limit=1)

    assert len(first.rows) == 256
    assert first.total == 257
    assert all(row.node is nodes[row.visible_index] for row in first.rows)
    assert first.rows[0].first_child_visible_index == 1
    assert first.rows[255].position_in_set == 255
    assert first.rows[255].set_size == 256
    assert end.rows == () and end.total == 257 and end.offset == 257
    assert beyond.rows == () and beyond.total == 257 and beyond.offset == 999
    for value in (True, -1):
        with pytest.raises((TypeError, ValueError)):
            window_visible_sequence(sequence, offset=value, limit=1)
    for value in (True, 0, 257):
        with pytest.raises((TypeError, ValueError)):
            window_visible_sequence(sequence, offset=0, limit=value)


def test_br_g_34_window_wire_view_is_exact_bounded_and_authority_free() -> None:
    tree = _tree(NodeTreeKind.PLAN)
    sequence = derive_visible_sequence(tree.nodes, _parameters())
    window = window_visible_sequence(sequence, offset=0, limit=3)

    view = to_visible_window_view(window)

    assert set(view) == {"offset", "total", "rows"}
    assert type(view["offset"]) is int
    assert type(view["total"]) is int
    assert type(view["rows"]) is list
    rows = view["rows"]
    assert len(rows) == 3
    expected_row_keys = {
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
    assert all(
        type(row) is dict and set(row) == expected_row_keys for row in rows
    )
    assert rows[0]["display"] == "All items"
    assert rows[0]["expanded"] is True
    assert rows[2]["expanded"] is None
    forbidden_fields = {
        "rel_path",
        "rel_path_key",
        "member_ids",
        "position",
        "parent_index",
        "subtree_end",
        "subtree_extent",
        "subtree_member_count",
    }
    assert all(forbidden_fields.isdisjoint(row) for row in rows)
    assert json.loads(json.dumps(view, ensure_ascii=False)) == view

    with pytest.raises(TypeError, match="VisibleWindow"):
        to_visible_window_view(object())  # type: ignore[arg-type]


def test_br_g_34_sequence_metadata_is_derived_once(monkeypatch) -> None:
    original = visible_module._derive_visible_metadata
    calls = 0

    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(visible_module, "_derive_visible_metadata", observed)

    derive_visible_sequence(_nodes(), _parameters())

    assert calls == 1


def test_br_g_34_anchor_requires_exact_deepest_to_root_chain() -> None:
    sequence = derive_visible_sequence(
        _nodes(),
        _parameters(collapsed={"alpha"}),
    )

    assert resolve_visible_anchor(sequence, ()) is None
    assert resolve_visible_anchor(
        sequence,
        ("street", "alpha", "root"),
    ) == VisibleAnchor(
        # The hidden leaf anchors to its nearest visible ancestor.
        "alpha",
        1,
    )
    assert resolve_visible_anchor(
        derive_visible_sequence(_nodes(), _parameters(counts={})),
        ("street", "alpha", "root"),
    ) is None
    for chain in (
        ("missing",),
        ("root", "alpha"),
        ("street", "root"),
        ("street", "beta", "root"),
        ("street", "alpha", "alpha", "root"),
        ("street", "alpha"),
    ):
        with pytest.raises(ValueError):
            resolve_visible_anchor(sequence, chain)


def test_br_g_34_anchor_reads_only_the_supplied_chain() -> None:
    sequence = derive_visible_sequence(_nodes(), _parameters())

    class _ObservedNodes(tuple):
        reads = 0

        def __iter__(self):
            raise AssertionError("anchor resolution iterated the node array")

        def __getitem__(self, index):
            type(self).reads += 1
            return super().__getitem__(index)

    observed = _ObservedNodes(sequence.nodes)
    object.__setattr__(sequence, "nodes", observed)

    anchor = resolve_visible_anchor(sequence, ("street", "alpha", "root"))

    assert anchor == VisibleAnchor("street", 2)
    assert observed.reads == 3


def test_br_g_34_120k_projection_populates_every_retained_family() -> None:
    node_count = 120_000
    folder_count = 19_999
    file_count = 100_000
    built = [_Node("root", "All Nodes", 0, 0, None, node_count, True)]
    for folder_index in range(folder_count):
        folder_position = len(built)
        child_count = 6 if folder_index < 5 else 5
        built.append(
            _Node(
                f"folder-{folder_index}",
                f"Folder {folder_index}",
                folder_position,
                1,
                0,
                folder_position + child_count + 1,
                True,
            )
        )
        for child_index in range(child_count):
            position = len(built)
            built.append(
                _Node(
                    f"file-{folder_index}-{child_index}",
                    f"File {folder_index}-{child_index}",
                    position,
                    2,
                    folder_position,
                    position + 1,
                    False,
                )
            )
    nodes = tuple(built)

    sequence = derive_visible_sequence(nodes, _parameters())
    window = window_visible_sequence(sequence, offset=60_000, limit=256)

    assert len(nodes) == node_count
    assert sum(node.is_container for node in nodes) == folder_count + 1
    assert sum(not node.is_container for node in nodes) == file_count
    assert sequence.nodes is nodes
    assert len(sequence.visible_positions) == node_count
    assert len(sequence.source_position_by_node_id) == node_count
    assert len(sequence.visible_index_by_node_id) == node_count
    assert len(sequence.parent_visible_indexes) == node_count
    assert len(sequence.first_child_visible_indexes) == node_count
    assert len(sequence.has_retained_children) == node_count
    assert len(sequence.positions_in_set) == node_count
    assert len(sequence.set_sizes) == node_count
    assert sum(sequence.has_retained_children) == folder_count + 1
    assert sequence.collapsed_node_ids == frozenset()
    assert sequence.filtered_item_count is None
    assert len(window.rows) == 256
    assert window.rows[0].node is nodes[60_000]
    assert window.rows[-1].node is nodes[60_255]


def test_br_g_34_node_field_accesses_have_a_linear_scaling_guard() -> None:
    def observed_reads(node_count: int) -> int:
        plain = (
            _Node("root", "All Nodes", 0, 0, None, node_count, True),
            *(
                _Node(
                    f"node-{position}",
                    f"Node {position}",
                    position,
                    1,
                    0,
                    position + 1,
                    False,
                )
                for position in range(1, node_count)
            ),
        )
        reads = [0]
        observed = tuple(_ObservedNode(node, reads) for node in plain)

        sequence = derive_visible_sequence(observed, _parameters())

        assert len(sequence.visible_positions) == node_count
        return reads[0]

    smaller = observed_reads(512)
    larger = observed_reads(1_024)

    assert larger > smaller
    assert larger <= (2 * smaller) + 64


def test_br_g_34_module_retains_no_active_sequence_or_cache_family() -> None:
    parsed = ast.parse(MODULE.read_text(encoding="utf-8"))
    assigned_names = {
        target.id
        for node in parsed.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets if isinstance(node, ast.Assign) else (node.target,)
        )
        if isinstance(target, ast.Name)
    }

    assert assigned_names == {
        "_MAX_SEARCH_BYTES",
        "_MAX_WINDOW_ROWS",
        "_VisibleNodeT",
    }
