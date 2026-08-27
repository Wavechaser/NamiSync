from __future__ import annotations

import inspect

import pytest

import namisync.workflows.node_tree as node_tree_module
from namisync.core.pathing import (
    is_relative_path_descendant,
    normalize_relative_path,
    relative_path_depth,
    relative_path_parent,
    strip_common_relative_path_suffix,
)
from namisync.modules import planner
from namisync.workflows.node_tree import (
    NODE_TREE_ROW_LIMIT,
    NodeTreeKind,
    NodeTreeMember,
    NodeTreePopulationLimitError,
    build_node_tree,
)


def _member(
    member_id: str,
    path: str,
    *,
    is_container: bool = False,
) -> NodeTreeMember:
    return NodeTreeMember(
        member_id=member_id,
        rel_path=path,
        rel_path_key=normalize_relative_path(path, allow_root=True),
        is_container=is_container,
    )


def test_br_g_1_node_ids_are_scope_qualified_stable_and_order_independent() -> None:
    members = (
        _member("row-doc", r"docs\a.txt"),
        _member("row-hostile", r"100%_[x]\a&b.txt"),
    )

    first = build_node_tree(
        tree_kind=NodeTreeKind.INVENTORY,
        scope_identity="location-1",
        members=members,
    )
    rebuilt = build_node_tree(
        tree_kind=NodeTreeKind.INVENTORY,
        scope_identity="location-1",
        members=reversed(members),
    )
    foreign = build_node_tree(
        tree_kind=NodeTreeKind.INVENTORY,
        scope_identity="location-2",
        members=members,
    )
    plan_domain = build_node_tree(
        tree_kind=NodeTreeKind.PLAN,
        scope_identity="location-1",
        members=members,
    )

    docs_key = normalize_relative_path("docs")
    assert first.node_id_for_path_key(docs_key) == rebuilt.node_id_for_path_key(
        docs_key
    )
    assert first.node_id_for_path_key(docs_key) != foreign.node_id_for_path_key(
        docs_key
    )
    assert tuple(node.node_id for node in first.nodes) == tuple(
        node.node_id for node in rebuilt.nodes
    )
    foreign_docs_id = foreign.node_id_for_path_key(docs_key)
    with pytest.raises(KeyError):
        first.node_for_id(foreign_docs_id)
    assert first.node_id_for_path_key(docs_key) != plan_domain.node_id_for_path_key(
        docs_key
    )

    hostile_key = normalize_relative_path(r"100%_[x]\a&b.txt")
    hostile_node = first.node_for_id(
        first.node_id_for_path_key(hostile_key)
    )
    assert hostile_node.rel_path == r"100%_[x]\a&b.txt"
    assert "100%" not in hostile_node.node_id


def test_br_g_2_ordered_array_contains_complete_structure_and_indexes() -> None:
    members = (
        _member("same-b", r"A\B\first.txt"),
        _member("same-a", r"a\b\FIRST.TXT"),
        _member("child-c", r"a\c.txt"),
        _member("sibling", r"a-x\peer.txt"),
        _member("empty-directory", "empty", is_container=True),
    )
    tree = build_node_tree(
        tree_kind=NodeTreeKind.INVENTORY,
        scope_identity="location-1",
        members=members,
    )

    expected_keys = (
        "",
        "A",
        r"A\B",
        r"A\B\FIRST.TXT",
        r"A\C.TXT",
        "A-X",
        r"A-X\PEER.TXT",
        "EMPTY",
    )
    assert tuple(node.rel_path_key for node in tree.nodes) == expected_keys
    assert tuple(node.position for node in tree.nodes) == tuple(
        range(len(expected_keys))
    )
    assert tuple(node.depth for node in tree.nodes) == (0, 1, 2, 3, 2, 1, 2, 1)
    assert tuple(node.parent_index for node in tree.nodes) == (
        None,
        0,
        1,
        2,
        1,
        0,
        5,
        0,
    )
    assert tuple(node.subtree_end for node in tree.nodes) == (
        8,
        5,
        4,
        4,
        5,
        7,
        7,
        8,
    )
    assert all(
        node.subtree_extent == (node.position, node.subtree_end)
        for node in tree.nodes
    )

    a_node_id = tree.node_id_for_path_key("A")
    a_position = tree.position_for_node_id(a_node_id)
    assert a_position == 1
    assert tree.node_for_id(a_node_id) is tree.nodes[a_position]
    assert tree.rel_path_key_for_node_id(a_node_id) == "A"
    assert tree.rel_path_for_node_id(a_node_id) in {"A", "a"}
    assert tree.subtree_member_ids(a_node_id) == (
        "same-a",
        "same-b",
        "child-c",
    )
    assert tree.nodes[a_position].subtree_member_count == 3
    assert "sibling" not in tree.subtree_member_ids(a_node_id)

    empty = tree.node_for_id(tree.node_id_for_path_key("EMPTY"))
    assert empty.is_container
    assert empty.member_ids == ("empty-directory",)


def test_br_g_2_rejects_ambiguous_members_instead_of_corrupting_indexes() -> None:
    duplicate_id = (
        _member("row", r"a\one.txt"),
        _member("row", r"b\two.txt"),
    )
    with pytest.raises(ValueError, match="member_id"):
        build_node_tree(
            tree_kind=NodeTreeKind.INVENTORY,
            scope_identity="location-1",
            members=duplicate_id,
        )

    with pytest.raises(ValueError, match="canonical"):
        NodeTreeMember(
            member_id="bad-key",
            rel_path=r"a\one.txt",
            rel_path_key="WRONG",
        )


def test_br_g_2_indexes_are_read_only_and_input_is_consumed_once() -> None:
    members = (
        _member("first", r"a\one.txt"),
        _member("second", r"a\two.txt"),
    )

    class OneShotMembers:
        def __init__(self) -> None:
            self.iterations = 0

        def __iter__(self):
            self.iterations += 1
            if self.iterations != 1:
                raise AssertionError("member input was iterated more than once")
            return iter(members)

    one_shot = OneShotMembers()
    tree = build_node_tree(
        tree_kind=NodeTreeKind.INVENTORY,
        scope_identity="location-1",
        members=one_shot,
    )
    expected = build_node_tree(
        tree_kind=NodeTreeKind.INVENTORY,
        scope_identity="location-1",
        members=members,
    )

    assert one_shot.iterations == 1
    assert tree.nodes == expected.nodes
    with pytest.raises(TypeError):
        tree.node_positions[tree.root_node_id] = 99  # type: ignore[index]
    with pytest.raises(TypeError):
        tree.path_positions[""] = 99  # type: ignore[index]


def test_br_g_2_empty_tree_retains_an_addressable_root() -> None:
    tree = build_node_tree(
        tree_kind=NodeTreeKind.INVENTORY,
        scope_identity="empty-location",
        members=(),
    )

    assert len(tree.nodes) == 1
    root = tree.nodes[0]
    assert root.node_id == tree.root_node_id
    assert root.rel_path == root.rel_path_key == ""
    assert root.position == root.depth == 0
    assert root.parent_index is None
    assert root.subtree_extent == (0, 1)
    assert root.subtree_member_count == 0
    assert root.is_container


def test_tree_refuses_first_excess_member() -> None:
    with pytest.raises(NodeTreePopulationLimitError) as raised:
        build_node_tree(
            tree_kind=NodeTreeKind.INVENTORY,
            scope_identity="bounded-location",
            members=(
                _member(f"member-{index}", "same")
                for index in range(NODE_TREE_ROW_LIMIT + 1)
            ),
        )

    assert raised.value.tree_kind is NodeTreeKind.INVENTORY


def test_tree_member_wall_does_not_charge_synthetic_ancestors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(node_tree_module, "NODE_TREE_ROW_LIMIT", 2)

    tree = build_node_tree(
        tree_kind=NodeTreeKind.PLAN,
        scope_identity="bounded-plan",
        members=(
            _member("one", r"shared\one"),
            _member("two", r"shared\two"),
        ),
    )

    assert tuple(node.rel_path_key for node in tree.nodes) == (
        "",
        "SHARED",
        r"SHARED\ONE",
        r"SHARED\TWO",
    )
    assert tree.nodes[0].subtree_member_count == 2
    assert tree.nodes[1].synthetic


@pytest.mark.parametrize("malformed_kind", ("object", "duplicate", "subclass", "forged"))
def test_first_excess_member_is_refused_before_collaborator_access(
    monkeypatch: pytest.MonkeyPatch,
    malformed_kind: str,
) -> None:
    monkeypatch.setattr(node_tree_module, "NODE_TREE_ROW_LIMIT", 1)

    if malformed_kind == "object":
        malformed: object = object()
    elif malformed_kind == "duplicate":
        malformed = _member("valid", "")
    elif malformed_kind == "subclass":
        class HostileMember(NodeTreeMember):
            pass

        malformed = HostileMember("hostile", "", "")
    else:
        malformed = _member("hostile", "")
        object.__setattr__(malformed, "rel_path_key", "not-canonical")

    with pytest.raises(NodeTreePopulationLimitError):
        build_node_tree(
            tree_kind=NodeTreeKind.INVENTORY,
            scope_identity="hostile-member",
            members=(_member("valid", ""), malformed),
        )


def test_case_variant_paths_keep_the_lexicographic_minimum_display() -> None:
    tree = build_node_tree(
        tree_kind=NodeTreeKind.INVENTORY,
        scope_identity="case-variants",
        members=(
            _member("upper", r"FOLDER\FILE.txt"),
            _member("mixed", r"Folder\File.txt"),
            _member("lower", r"folder\file.TXT"),
        ),
    )

    assert len(tree.nodes) == 3
    folder = tree.nodes[tree.path_positions["FOLDER"]]
    leaf = tree.nodes[tree.path_positions[r"FOLDER\FILE.TXT"]]
    assert folder.rel_path == "FOLDER"
    assert leaf.rel_path == r"FOLDER\FILE.txt"
    assert leaf.member_ids == ("lower", "mixed", "upper")


def test_br_g_3_planner_uses_the_promoted_helpers_without_private_copies() -> None:
    source = inspect.getsource(planner)
    assert "def _depth(" not in source
    assert "def _parent(" not in source
    assert "def _is_descendant(" not in source
    assert planner.relative_path_depth is relative_path_depth
    assert planner.relative_path_parent is relative_path_parent
    assert planner.is_relative_path_descendant is is_relative_path_descendant


def test_common_relative_path_suffix_is_segment_aware_and_preserves_spelling() -> None:
    assert strip_common_relative_path_suffix(
        r"Old\Nested\File.TXT",
        r"New\nested\file.txt",
    ) == ("Old", "New")
    assert strip_common_relative_path_suffix(
        r"folder\a.txt",
        r"folder-a\a.txt",
    ) == ("folder", "folder-a")
    assert strip_common_relative_path_suffix(
        r"left\a.txt",
        r"right\b.txt",
    ) == (r"left\a.txt", r"right\b.txt")
    assert strip_common_relative_path_suffix("cat.txt", "at.txt") == (
        "cat.txt",
        "at.txt",
    )
    assert strip_common_relative_path_suffix("same.txt", "SAME.TXT") == ("", "")
