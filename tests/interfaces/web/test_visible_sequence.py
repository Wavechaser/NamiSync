"""BR-G-34 evidence for the pure shared visible-sequence core."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

from namisync.core.pathing import normalize_relative_path
from namisync.interfaces.web.visible_sequence import (
    VisibleAnchor,
    VisibleSequenceNode,
    VisibleSequenceParameters,
    derive_visible_sequence,
    resolve_visible_anchor,
    window_visible_sequence,
)
from namisync.workflows.node_tree import (
    NodeTree,
    NodeTreeKind,
    NodeTreeMember,
    build_node_tree,
)


MODULE = Path(__file__).parents[3] / "namisync/interfaces/web/visible_sequence.py"


def _nodes() -> tuple[VisibleSequenceNode, ...]:
    # root
    #   Alpha
    #     Straße.txt
    #     composed-é.txt
    #   Beta
    #     literal-[.*].txt
    return (
        VisibleSequenceNode("root", "All items", 0, 0, None, 6, True),
        VisibleSequenceNode("alpha", "Alpha", 1, 1, 0, 4, True),
        VisibleSequenceNode("street", "Straße.txt", 2, 2, 1, 3, False),
        VisibleSequenceNode("composed", "composed-é.txt", 3, 2, 1, 4, False),
        VisibleSequenceNode("beta", "Beta", 4, 1, 0, 6, True),
        VisibleSequenceNode("literal", "literal-[.*].txt", 5, 2, 4, 6, False),
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


def _adapt(tree: NodeTree) -> tuple[VisibleSequenceNode, ...]:
    return tuple(
        VisibleSequenceNode(
            node_id=node.node_id,
            display=node.rel_path or "All items",
            position=node.position,
            depth=node.depth,
            parent_index=node.parent_index,
            subtree_end=node.subtree_end,
            is_container=node.is_container,
        )
        for node in tree.nodes
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
def test_br_g_34_real_workflow_trees_supply_all_structure_without_path_logic(
    kind: NodeTreeKind,
) -> None:
    tree = _tree(kind)
    nodes = _adapt(tree)

    sequence = derive_visible_sequence(nodes, _parameters())

    assert sequence.nodes == nodes
    assert all(left is right for left, right in zip(sequence.nodes, nodes))
    assert sequence.visible_positions == tuple(range(len(nodes)))
    assert _ids(sequence) == tuple(node.node_id for node in nodes)
    assert sequence.filtered_item_count is None


def test_br_g_34_empty_workflow_projection_keeps_its_single_root() -> None:
    tree = build_node_tree(
        tree_kind=NodeTreeKind.INVENTORY,
        scope_identity="empty-location",
        members=(),
    )
    nodes = _adapt(tree)

    sequence = derive_visible_sequence(nodes, _parameters())

    assert len(nodes) == 1
    assert _ids(sequence) == (tree.root_node_id,)


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
        {"depth": True},
        {"parent_index": True},
        {"subtree_end": True},
        {"is_container": 1},
    ],
)
def test_br_g_34_node_fields_use_exact_types_and_valid_unicode(arguments) -> None:
    values = {
        "node_id": "node",
        "display": "display",
        "position": 0,
        "depth": 0,
        "parent_index": None,
        "subtree_end": 1,
        "is_container": True,
    }
    values.update(arguments)

    with pytest.raises((TypeError, ValueError)):
        VisibleSequenceNode(**values)


class _PoisonNodes:
    def __iter__(self):
        raise AssertionError("nodes were traversed before search refusal")

    def __len__(self):
        raise AssertionError("nodes were measured before search refusal")

    def __getitem__(self, index):
        raise AssertionError("nodes were read before search refusal")


def test_br_g_34_search_cap_is_utf8_bytes_and_checked_before_traversal() -> None:
    accepted = _parameters(search="😀" * 64)
    assert len(accepted.search_query.encode("utf-8")) == 256
    derive_visible_sequence(_nodes(), accepted)

    with pytest.raises(ValueError, match="256 UTF-8 bytes"):
        _parameters(search=("😀" * 63) + "abcde")

    poisoned = _parameters()
    object.__setattr__(poisoned, "search_query", ("😀" * 63) + "abcde")
    with pytest.raises(ValueError, match="256 UTF-8 bytes"):
        derive_visible_sequence(_PoisonNodes(), poisoned)  # type: ignore[arg-type]


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


def test_br_g_34_filter_retention_precedes_collapse_and_counting() -> None:
    counts = {"street": 2, "literal": 3}
    sequence = derive_visible_sequence(
        _nodes(),
        _parameters(collapsed={"alpha"}, search="t", counts=counts),
    )

    assert _ids(sequence) == ("root", "alpha", "beta", "literal")
    assert sequence.filtered_item_count == 5
    assert "street" not in sequence.visible_index_by_node_id


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


def test_br_g_34_inputs_and_results_are_immutable_snapshots() -> None:
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
    assert type(sequence.visible_index_by_node_id) is MappingProxyType
    with pytest.raises(TypeError):
        sequence.visible_index_by_node_id["new"] = 9  # type: ignore[index]


def test_br_g_34_window_is_exact_bounded_and_never_truncates_a_bad_limit() -> None:
    nodes = tuple(
        VisibleSequenceNode(
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

    assert len(first.nodes) == 256
    assert first.total == 257
    assert end.nodes == () and end.total == 257 and end.offset == 257
    assert beyond.nodes == () and beyond.total == 257 and beyond.offset == 999
    for value in (True, -1):
        with pytest.raises((TypeError, ValueError)):
            window_visible_sequence(sequence, offset=value, limit=1)
    for value in (True, 0, 257):
        with pytest.raises((TypeError, ValueError)):
            window_visible_sequence(sequence, offset=0, limit=value)


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

    assert assigned_names == {"_MAX_SEARCH_BYTES", "_MAX_WINDOW_ROWS"}
