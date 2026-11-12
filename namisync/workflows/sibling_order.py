"""Sibling ordering shared by workflow-owned presentation projections."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol


class SortableNode(Protocol):
    parent_index: int | None
    rel_path_key: str
    node_id: str
    row_kind: str
    is_directory: bool
    filename_key: str | None
    size: int | None
    mtime_ns: int | None


def canonical_siblings(nodes: Sequence[SortableNode]) -> dict[int, list[int]]:
    children: dict[int, list[int]] = {}
    for position, node in enumerate(nodes[1:], 1):
        assert node.parent_index is not None
        children.setdefault(node.parent_index, []).append(position)
    for siblings in children.values():
        siblings.sort(key=lambda position: (nodes[position].rel_path_key, nodes[position].node_id))
    return children


def sorted_siblings(
    nodes: Sequence[SortableNode],
    canonical_positions: Sequence[int],
    column: str,
    *,
    descending: bool,
) -> dict[int, list[int]]:
    """Keep canonical ties and unavailable-last semantics in both directions."""
    children: dict[int, list[int]] = {}
    for position in canonical_positions:
        if position == 0:
            continue
        parent = nodes[position].parent_index
        assert parent is not None
        children.setdefault(parent, []).append(position)
    for parent, siblings in children.items():
        if column == "size":
            buckets: tuple[list[int], list[int], list[int]] = ([], [], [])
            for position in siblings:
                node = nodes[position]
                if node.row_kind == "notice" or node.row_kind.startswith("prior-"):
                    bucket = 2
                elif node.row_kind == "folder" or node.is_directory:
                    bucket = 1
                else:
                    bucket = 0
                buckets[bucket].append(position)
            ordered: list[int] = []
            for bucket in buckets[:2]:
                available = [position for position in bucket if nodes[position].size is not None]
                unavailable = [position for position in bucket if nodes[position].size is None]
                available.sort(key=lambda position: nodes[position].size, reverse=descending)
                ordered.extend((*available, *unavailable))
            ordered.extend(buckets[2])
            children[parent] = ordered
            continue
        available: list[int] = []
        unavailable: list[int] = []
        for position in siblings:
            value = nodes[position].filename_key if column == "filename" else nodes[position].mtime_ns
            (unavailable if value is None else available).append(position)
        available.sort(
            key=lambda position: nodes[position].filename_key if column == "filename" else nodes[position].mtime_ns,
            reverse=descending,
        )
        children[parent] = available + unavailable
    return children


def preorder_positions(children: Mapping[int, Sequence[int]]) -> tuple[list[int], list[int]]:
    ordered: list[int] = []
    pending = [0]
    while pending:
        current = pending.pop()
        ordered.append(current)
        pending.extend(reversed(children.get(current, ())))
    inverse = [0] * len(ordered)
    for rank, position in enumerate(ordered):
        inverse[position] = rank
    return ordered, inverse
