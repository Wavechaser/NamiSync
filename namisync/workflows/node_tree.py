"""Pure, scope-qualified hierarchy construction for workflow projections."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import blake2b
from types import MappingProxyType
from typing import Iterable, Mapping

from namisync.core.pathing import (
    normalize_relative_path,
    relative_path_depth,
    relative_path_parent,
    validate_relative_path,
)


class NodeTreeKind(StrEnum):
    """Workflow projection families with independent node-id domains."""

    PLAN = "plan"
    INVENTORY = "inventory"


@dataclass(frozen=True, slots=True)
class NodeTreeMember:
    """One domain member attached to its canonical relative-path node."""

    member_id: str
    rel_path: str
    rel_path_key: str
    is_container: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.member_id, str) or not self.member_id:
            raise ValueError("member_id must be a nonempty string")
        canonical = validate_relative_path(self.rel_path, allow_root=True)
        if self.rel_path_key != normalize_relative_path(
            canonical,
            allow_root=True,
        ):
            raise ValueError("member path key is not canonical")
        if type(self.is_container) is not bool:
            raise TypeError("is_container must be a bool")


@dataclass(frozen=True, slots=True)
class NodeTreeNode:
    """One node in a pre-order, parent-indexed tree array."""

    node_id: str
    rel_path: str
    rel_path_key: str
    member_ids: tuple[str, ...]
    is_container: bool
    position: int
    depth: int
    parent_index: int | None
    subtree_end: int
    subtree_member_count: int

    @property
    def display(self) -> str:
        """Return the workflow-owned display form of this relative path."""

        return self.rel_path or "All items"

    @property
    def subtree_extent(self) -> tuple[int, int]:
        """Return this node's half-open pre-order interval."""

        return self.position, self.subtree_end

    @property
    def synthetic(self) -> bool:
        """Return whether the node exists only to carry hierarchy."""

        return not self.member_ids


@dataclass(frozen=True, slots=True)
class NodeTree:
    """Immutable nodes plus authoritative identity and path indexes."""

    tree_kind: NodeTreeKind
    scope_identity: str
    nodes: tuple[NodeTreeNode, ...]
    _position_by_node_id: Mapping[str, int]
    _position_by_path_key: Mapping[str, int]

    @property
    def root_node_id(self) -> str:
        return self.nodes[0].node_id

    @property
    def node_positions(self) -> Mapping[str, int]:
        return self._position_by_node_id

    @property
    def path_positions(self) -> Mapping[str, int]:
        return self._position_by_path_key

    def node_for_id(self, node_id: str) -> NodeTreeNode:
        return self.nodes[self.position_for_node_id(node_id)]

    def position_for_node_id(self, node_id: str) -> int:
        return self._position_by_node_id[node_id]

    def node_id_for_path_key(self, rel_path_key: str) -> str:
        canonical = normalize_relative_path(rel_path_key, allow_root=True)
        if canonical != rel_path_key:
            raise ValueError("node lookup path key is not canonical")
        return self.nodes[self._position_by_path_key[canonical]].node_id

    def rel_path_for_node_id(self, node_id: str) -> str:
        return self.node_for_id(node_id).rel_path

    def rel_path_key_for_node_id(self, node_id: str) -> str:
        return self.node_for_id(node_id).rel_path_key

    def subtree_positions(self, node_id: str) -> range:
        node = self.node_for_id(node_id)
        return range(node.position, node.subtree_end)

    def subtree_member_ids(self, node_id: str) -> tuple[str, ...]:
        member_ids: list[str] = []
        for position in self.subtree_positions(node_id):
            member_ids.extend(self.nodes[position].member_ids)
        return tuple(member_ids)


def build_node_tree(
    *,
    tree_kind: NodeTreeKind,
    scope_identity: str,
    members: Iterable[NodeTreeMember],
) -> NodeTree:
    """Build one deterministic tree and its subtree/member indexes."""

    if not isinstance(tree_kind, NodeTreeKind):
        raise TypeError("tree_kind must be a NodeTreeKind")
    if not isinstance(scope_identity, str) or not scope_identity:
        raise ValueError("scope_identity must be a nonempty string")

    display_paths: dict[str, set[str]] = {"": {""}}
    direct_member_ids: dict[str, list[str]] = {}
    explicit_containers: set[str] = set()
    seen_member_ids: set[str] = set()

    for member in members:
        if not isinstance(member, NodeTreeMember):
            raise TypeError("members must contain NodeTreeMember values")
        if member.member_id in seen_member_ids:
            raise ValueError(f"duplicate member_id: {member.member_id}")
        seen_member_ids.add(member.member_id)
        direct_member_ids.setdefault(member.rel_path_key, []).append(
            member.member_id
        )
        if member.is_container:
            explicit_containers.add(member.rel_path_key)

        path = member.rel_path
        path_key = member.rel_path_key
        while True:
            display_paths.setdefault(path_key, set()).add(path)
            if path_key == "":
                break
            parent = relative_path_parent(path)
            parent_key = relative_path_parent(path_key)
            path = "" if parent is None else parent
            path_key = "" if parent_key is None else parent_key

    children_by_path_key: dict[str, list[str]] = {
        path_key: [] for path_key in display_paths
    }
    for path_key in display_paths:
        if path_key == "":
            continue
        parent_key = relative_path_parent(path_key)
        children_by_path_key["" if parent_key is None else parent_key].append(
            path_key
        )
    for child_keys in children_by_path_key.values():
        child_keys.sort()

    ordered_path_keys: list[str] = []
    pending = [""]
    while pending:
        path_key = pending.pop()
        ordered_path_keys.append(path_key)
        pending.extend(reversed(children_by_path_key[path_key]))

    position_by_path_key = {
        path_key: position
        for position, path_key in enumerate(ordered_path_keys)
    }
    subtree_ends = [
        position + 1 for position in range(len(ordered_path_keys))
    ]
    subtree_member_counts = [
        len(direct_member_ids.get(path_key, ()))
        for path_key in ordered_path_keys
    ]
    for position in range(len(ordered_path_keys) - 1, 0, -1):
        path_key = ordered_path_keys[position]
        parent_key = relative_path_parent(path_key)
        parent_position = position_by_path_key[
            "" if parent_key is None else parent_key
        ]
        subtree_ends[parent_position] = max(
            subtree_ends[parent_position],
            subtree_ends[position],
        )
        subtree_member_counts[parent_position] += subtree_member_counts[
            position
        ]

    nodes: list[NodeTreeNode] = []
    position_by_node_id: dict[str, int] = {}
    for position, path_key in enumerate(ordered_path_keys):
        parent_key = (
            None if path_key == "" else relative_path_parent(path_key)
        )
        parent_index = (
            None
            if path_key == ""
            else position_by_path_key[
                "" if parent_key is None else parent_key
            ]
        )
        node_id = _node_id(tree_kind, scope_identity, path_key)
        if node_id in position_by_node_id:
            raise RuntimeError("deterministic node-id collision")
        position_by_node_id[node_id] = position
        nodes.append(
            NodeTreeNode(
                node_id=node_id,
                rel_path=min(display_paths[path_key]),
                rel_path_key=path_key,
                member_ids=tuple(
                    sorted(direct_member_ids.get(path_key, ()))
                ),
                is_container=(
                    path_key == ""
                    or path_key in explicit_containers
                    or bool(children_by_path_key[path_key])
                ),
                position=position,
                depth=relative_path_depth(path_key),
                parent_index=parent_index,
                subtree_end=subtree_ends[position],
                subtree_member_count=subtree_member_counts[position],
            )
        )

    return NodeTree(
        tree_kind=tree_kind,
        scope_identity=scope_identity,
        nodes=tuple(nodes),
        _position_by_node_id=MappingProxyType(position_by_node_id),
        _position_by_path_key=MappingProxyType(position_by_path_key),
    )


def _node_id(
    tree_kind: NodeTreeKind,
    scope_identity: str,
    rel_path_key: str,
) -> str:
    digest = blake2b(digest_size=16, person=b"NamiSyncNodeV1")
    for value in (tree_kind.value, scope_identity, rel_path_key):
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return f"node-{digest.hexdigest()}"
