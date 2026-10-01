"""Complete immutable inventory facts, separate from desktop view state."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import blake2b
from types import MappingProxyType

from namisync.core.integrity import InventoryVerificationState
from namisync.core.models import EntryKind, ScanWarning
from namisync.core.review import MAX_PLAN_REVIEW_ROWS
from namisync.core.scalars import MAX_SIGNED_64, require_signed_64
from namisync.db.repositories import InventoryPresence, InventorySnapshot

from .node_tree import NodeTreeKind, NodeTreeMember, build_node_tree
from .plan_projection import CompactUnsignedIntegers, PlanSortColumn, SortDirection
from .sibling_order import canonical_siblings, preorder_positions, sorted_siblings


class InventoryProjectionPopulationLimitError(ValueError):
    """One independent inventory source population exceeded its existing wall."""

    def __init__(self, population: str) -> None:
        super().__init__(f"inventory projection {population} population exceeds its row limit")
        self.population = population


@dataclass(frozen=True, slots=True)
class InventoryRollup:
    domain_count: int = 0
    file_count: int = 0
    present: int = 0
    unverified: int = 0
    verified: int = 0
    modified: int = 0
    reappeared: int = 0
    unsupported: int = 0
    missing: int = 0
    mismatched: int = 0
    acknowledged: int = 0
    size: int | None = 0
    size_overflow: bool = False
    size_partial: bool = False


@dataclass(frozen=True, slots=True)
class InventoryProjectionNode:
    node_id: str
    display: str
    rel_path: str
    rel_path_key: str
    position: int
    depth: int
    parent_index: int | None
    subtree_end: int
    is_container: bool
    row_kind: str
    is_directory: bool
    filename_key: str | None
    size: int | None
    mtime_ns: int | None
    row: InventorySnapshot | None
    warning: ScanWarning | None
    rollup: InventoryRollup


@dataclass(frozen=True, slots=True)
class InventoryProjection:
    location_id: int
    nodes: tuple[InventoryProjectionNode, ...]
    position_by_node_id: Mapping[str, int]
    position_by_path_key: Mapping[str, int]
    node_id_by_row_id: Mapping[str, str]
    warning_count: int

    def __post_init__(self) -> None:
        require_signed_64(self.location_id, "inventory projection location id")
        if self.location_id < 1:
            raise ValueError("inventory projection location id must be positive")
        nodes = tuple(self.nodes)
        positions = dict(self.position_by_node_id)
        paths = dict(self.position_by_path_key)
        rows = dict(self.node_id_by_row_id)
        if not nodes or len(positions) != len(nodes):
            raise ValueError("inventory projection node index is incomplete")
        expected_paths: dict[str, int] = {}
        expected_rows: dict[str, str] = {}
        warning_count = 0
        ancestors: list[InventoryProjectionNode] = []
        for position, node in enumerate(nodes):
            if type(node) is not InventoryProjectionNode:
                raise TypeError("inventory nodes must be exact projection nodes")
            if node.position != position or positions.get(node.node_id) != position:
                raise ValueError("inventory projection node index is inconsistent")
            while ancestors and position >= ancestors[-1].subtree_end:
                ancestors.pop()
            parent = ancestors[-1] if ancestors else None
            if (
                node.parent_index != (None if parent is None else parent.position)
                or node.depth != len(ancestors)
                or not position < node.subtree_end <= len(nodes)
                or (parent is not None and node.subtree_end > parent.subtree_end)
                or (position > 0 and parent is None)
            ):
                raise ValueError("inventory projection topology is inconsistent")
            ancestors.append(node)
            if node.warning is not None:
                warning_count += 1
                if node.row is not None or node.is_container or node.rollup != InventoryRollup():
                    raise ValueError("inventory warning has domain facts")
                continue
            if node.rel_path_key in expected_paths:
                raise ValueError("inventory projection path index has duplicates")
            expected_paths[node.rel_path_key] = position
            if node.row is not None:
                if node.row.location_id != self.location_id:
                    raise ValueError("inventory projection row belongs to another location")
                expected_rows[node.row.row_id] = node.node_id
        if paths != expected_paths or rows != expected_rows or self.warning_count != warning_count:
            raise ValueError("inventory projection domain indexes are inconsistent")
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "position_by_node_id", MappingProxyType(positions))
        object.__setattr__(self, "position_by_path_key", MappingProxyType(paths))
        object.__setattr__(self, "node_id_by_row_id", MappingProxyType(rows))

    def node_for_id(self, node_id: str) -> InventoryProjectionNode:
        return self.nodes[self.position_by_node_id[node_id]]

    def row_for_id(self, row_id: str) -> InventorySnapshot:
        row = self.node_for_id(self.node_id_by_row_id[row_id]).row
        assert row is not None
        return row

    def domain_row_ids(self, node_id: str) -> tuple[str, ...]:
        """Resolve complete folder membership without any visible-view state."""
        node = self.node_for_id(node_id)
        if node.warning is not None:
            raise ValueError("inventory warnings are not domain subjects")
        return tuple(
            self.nodes[position].row.row_id
            for position in range(node.position, node.subtree_end)
            if self.nodes[position].row is not None
        )


@dataclass(frozen=True, slots=True)
class InventoryProjectionOrder:
    projection: InventoryProjection
    ordered_source_positions: CompactUnsignedIntegers
    order_rank_by_source_position: CompactUnsignedIntegers

    def __post_init__(self) -> None:
        if type(self.projection) is not InventoryProjection:
            raise TypeError("ordered inventory requires an exact projection")
        count = len(self.projection.nodes)
        if type(self.ordered_source_positions) is not CompactUnsignedIntegers or type(self.order_rank_by_source_position) is not CompactUnsignedIntegers:
            raise TypeError("inventory order indexes must be compact integers")
        if len(self.ordered_source_positions) != count or len(self.order_rank_by_source_position) != count:
            raise ValueError("inventory order must cover every node")
        ancestors: list[int] = []
        seen = bytearray(count)
        for rank, position in enumerate(self.ordered_source_positions):
            if position >= count or seen[position] or self.order_rank_by_source_position[position] != rank:
                raise ValueError("inventory order must be an invertible permutation")
            seen[position] = 1
            node = self.projection.nodes[position]
            while len(ancestors) > node.depth:
                ancestors.pop()
            if len(ancestors) != node.depth or node.parent_index != (ancestors[-1] if ancestors else None):
                raise ValueError("inventory order breaks parent closure")
            ancestors.append(position)


def build_inventory_projection(
    location_id: int,
    rows: Iterable[InventorySnapshot],
    warnings: Iterable[ScanWarning] = (),
) -> InventoryProjection:
    """Build all facts before publication; source populations are charged apart."""
    require_signed_64(location_id, "inventory projection location id")
    if location_id < 1:
        raise ValueError("inventory projection location id must be positive")
    rows_by_id: dict[str, InventorySnapshot] = {}
    path_keys: set[str] = set()
    for index, row in enumerate(rows):
        if index >= MAX_PLAN_REVIEW_ROWS:
            raise InventoryProjectionPopulationLimitError("domain")
        if type(row) is not InventorySnapshot:
            raise TypeError("inventory projection requires exact inventory snapshots")
        if row.location_id != location_id:
            raise ValueError("inventory row belongs to another location")
        if row.row_id in rows_by_id or row.rel_path_key in path_keys:
            raise ValueError("inventory subjects must have unique row ids and paths")
        rows_by_id[row.row_id] = row
        path_keys.add(row.rel_path_key)
    retained_warnings: list[ScanWarning] = []
    for index, warning in enumerate(warnings):
        if index >= MAX_PLAN_REVIEW_ROWS:
            raise InventoryProjectionPopulationLimitError("informational")
        if type(warning) is not ScanWarning:
            raise TypeError("inventory warnings must be exact ScanWarning values")
        retained_warnings.append(warning)
    tree = build_node_tree(
        tree_kind=NodeTreeKind.INVENTORY,
        scope_identity=str(location_id),
        members=(NodeTreeMember(row.row_id, row.rel_path, row.rel_path_key, row.entry_kind is EntryKind.DIRECTORY) for row in rows_by_id.values()),
    )
    # Accumulate raw integer totals once; null is published only after aggregation.
    counters = [_row_counters(rows_by_id[node.member_ids[0]]) if node.member_ids else [0] * 13 for node in tree.nodes]
    for node in reversed(tree.nodes[1:]):
        assert node.parent_index is not None
        parent = counters[node.parent_index]
        for index, value in enumerate(counters[node.position]):
            parent[index] += value
    nodes: list[InventoryProjectionNode] = []
    node_ids_by_row: dict[str, str] = {}
    for node, counts in zip(tree.nodes, counters):
        row = rows_by_id[node.member_ids[0]] if node.member_ids else None
        stat = None if row is None else row.observed
        own_path = node.rel_path if row is None else row.rel_path
        size = counts[-2]
        rollup = InventoryRollup(*counts[:-2], None if size > MAX_SIGNED_64 else size, size > MAX_SIGNED_64, bool(counts[-1]))
        nodes.append(InventoryProjectionNode(
            node.node_id, node.display, node.rel_path, node.rel_path_key, node.position,
            node.depth, node.parent_index, len(tree.nodes) + len(retained_warnings) if node.position == 0 else node.subtree_end,
            node.is_container, "folder" if node.is_container else "subject",
            row is not None and row.entry_kind is EntryKind.DIRECTORY,
            own_path.rsplit("\\", 1)[-1].casefold() if own_path else None,
            None if stat is None else stat.size, None if stat is None else stat.mtime_ns,
            row, None, rollup,
        ))
        if row is not None:
            node_ids_by_row[row.row_id] = node.node_id
    for ordinal, warning in enumerate(retained_warnings):
        position = len(nodes)
        warning_id = _warning_id(location_id, ordinal, warning)
        nodes.append(InventoryProjectionNode(
            warning_id, warning.rel_path or warning.code.value, "", "", position,
            1, 0, position + 1, False, "notice", False, None, None, None,
            None, warning, InventoryRollup(),
        ))
    return InventoryProjection(
        location_id, tuple(nodes), {node.node_id: node.position for node in nodes},
        {node.rel_path_key: node.position for node in nodes if node.warning is None},
        node_ids_by_row, len(retained_warnings),
    )


def sort_inventory_projection(
    projection: InventoryProjection,
    column: PlanSortColumn,
    direction: SortDirection,
) -> InventoryProjectionOrder:
    if type(projection) is not InventoryProjection:
        raise TypeError("inventory sort requires an exact projection")
    if type(column) is not PlanSortColumn or type(direction) is not SortDirection:
        raise TypeError("inventory sort must use exact enums")
    if column is PlanSortColumn.PATH and direction is not SortDirection.ASCENDING:
        raise ValueError("canonical path sort supports ascending only")
    children = canonical_siblings(projection.nodes)
    # Warnings are an independent attachment-order tail, never canonical paths.
    warnings = [node.position for node in projection.nodes if node.warning is not None]
    children[0] = [position for position in children.get(0, ()) if projection.nodes[position].warning is None] + warnings
    canonical, _ = preorder_positions(children)
    if column is not PlanSortColumn.PATH:
        children = sorted_siblings(projection.nodes, canonical, column.value, descending=direction is SortDirection.DESCENDING)
    ordered, inverse = preorder_positions(children)
    maximum = len(projection.nodes) - 1
    return InventoryProjectionOrder(projection, CompactUnsignedIntegers(ordered, maximum=maximum), CompactUnsignedIntegers(inverse, maximum=maximum))


def _row_counters(row: InventorySnapshot) -> list[int]:
    state = row.verification_state
    missing = row.presence is InventoryPresence.MISSING
    acknowledged = missing and row.acknowledged_at is not None
    file = row.entry_kind is EntryKind.FILE
    return [
        1, int(file), int(row.presence is InventoryPresence.PRESENT),
        int(state is InventoryVerificationState.UNVERIFIED), int(state is InventoryVerificationState.VERIFIED),
        int(state is InventoryVerificationState.MODIFIED), int(row.reappeared_at is not None),
        int(row.presence is InventoryPresence.UNSUPPORTED), int(missing and not acknowledged),
        int(state is InventoryVerificationState.MISMATCHED), int(acknowledged),
        row.observed.size if file and row.observed is not None else 0,
        int(row.entry_kind is None or (file and row.observed is None)),
    ]


def _warning_id(location_id: int, ordinal: int, warning: ScanWarning) -> str:
    digest = blake2b(digest_size=16, person=b"NamiSyncWarnV1")
    for value in (str(location_id), str(ordinal), warning.code.value, warning.rel_path or "", warning.detail):
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return f"node-{digest.hexdigest()}"
