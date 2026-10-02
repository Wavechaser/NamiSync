"""One cached, revisioned view of a complete immutable inventory projection."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from namisync.interfaces.ui_state import MAX_JAVASCRIPT_SAFE_INTEGER
from namisync.workflows import (
    InventoryDetails, InventoryProjection, InventoryProjectionNode, InventoryProjectionOrder, InventoryRollup,
    PlanSortColumn, SortDirection,
    sort_inventory_projection,
)
from .visible_sequence import (
    VisibleSequence, VisibleSequenceParameters, _derive_visible_sequence_from_validated,
    window_visible_sequence,
)


INVENTORY_FILTERS = frozenset({
    "present", "unverified", "verified", "modified", "reappeared",
    "unsupported", "missing", "mismatched", "acknowledged", "notice",
})


def inventory_scan_scope(details: InventoryDetails) -> tuple[str, str | None]:
    """Describe the producing scan without serializing its full path population."""
    if not details.selected_paths and not details.subtree_roots:
        return "location", None
    if len(details.selected_paths) == 1 and not details.subtree_roots:
        return "item", details.selected_paths[0]
    if len(details.subtree_roots) == 1 and not details.selected_paths:
        return "folder", details.subtree_roots[0]
    return "selection", None


def inventory_rollup_wire(rollup: InventoryRollup) -> dict[str, object]:
    value = asdict(rollup)
    value["size"] = None if rollup.size is None else str(rollup.size)
    return value


def _categories(node: InventoryProjectionNode) -> frozenset[str]:
    if node.warning is not None:
        return frozenset({"notice"})
    row = node.row
    if row is None:
        return frozenset()
    categories = {row.presence.value, row.verification_state.value}
    if row.presence.value == "missing" and row.acknowledged_at is not None:
        categories.discard("missing")
        categories.add("acknowledged")
    if row.reappeared_at is not None:
        categories.add("reappeared")
    return frozenset(categories)


@dataclass(slots=True)
class InventoryReviewState:
    task_id: str
    request_id: str
    projection: InventoryProjection
    root_path: str | None
    scan_complete: bool
    observed_count: int
    missing_count: int
    scan_scope: tuple[str, str | None] = field(default=("location", None), kw_only=True)
    view_revision: int = 0
    search_query: str = ""
    filters: frozenset[str] = field(default_factory=frozenset)
    sort_column: PlanSortColumn = PlanSortColumn.PATH
    sort_direction: SortDirection = SortDirection.ASCENDING
    collapsed_node_ids: frozenset[str] = field(default_factory=frozenset)
    _order: InventoryProjectionOrder = field(init=False, repr=False)
    _visible: VisibleSequence[InventoryProjectionNode] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._order = sort_inventory_projection(self.projection, self.sort_column, self.sort_direction)
        self._visible = self._derive(self._order, self.search_query, self.filters, self.collapsed_node_ids)

    def _derive(self, order: InventoryProjectionOrder, search: str,
                filters: frozenset[str], collapsed: frozenset[str]) -> VisibleSequence[InventoryProjectionNode]:
        mask = bytes(
            int(("acknowledged" not in categories or "acknowledged" in filters)
                and (bool(categories & filters) if filters else bool(categories)))
            for categories in map(_categories, self.projection.nodes)
        )
        return _derive_visible_sequence_from_validated(
            self.projection.nodes, self.projection.position_by_node_id,
            VisibleSequenceParameters(search_query=search, collapsed_node_ids=collapsed),
            ordered_source_positions=order.ordered_source_positions,
            order_rank_by_source_position=order.order_rank_by_source_position,
            match_mask_by_position=mask,
        )

    def summary(self, *, disposition: str = "current") -> dict[str, object]:
        return {
            "disposition": disposition, "task_id": self.task_id,
            "request_id": self.request_id, "location_id": str(self.projection.location_id),
            "view_revision": self.view_revision, "root_path": self.root_path,
            "scan_complete": self.scan_complete, "observed_count": self.observed_count,
            "scan_scope": {"kind": self.scan_scope[0], "path": self.scan_scope[1]},
            "missing_count": self.missing_count, "warning_count": self.projection.warning_count,
            "rollup": inventory_rollup_wire(self.projection.nodes[0].rollup),
            "visible_row_count": max(0, len(self._visible.visible_positions) - 1),
            "search_query": self.search_query, "filters": sorted(self.filters),
            "sort_column": self.sort_column.value, "sort_direction": self.sort_direction.value,
            "collapsed_count": len(self.collapsed_node_ids),
        }

    def replacement(self, request_id: str, projection: InventoryProjection,
                    root_path: str | None, scan_complete: bool,
                    observed_count: int, missing_count: int, *,
                    scan_scope: tuple[str, str | None]) -> InventoryReviewState:
        """Stage one complete replacement while preserving surviving gestures."""
        if self.view_revision >= MAX_JAVASCRIPT_SAFE_INTEGER:
            raise OverflowError("inventory view revision is exhausted")
        collapsed = frozenset(
            node_id for node_id in self.collapsed_node_ids
            if node_id in projection.position_by_node_id
            and projection.node_for_id(node_id).is_container
        )
        return InventoryReviewState(
            self.task_id, request_id, projection, root_path, scan_complete,
            observed_count, missing_count, self.view_revision + 1,
            self.search_query, self.filters, self.sort_column, self.sort_direction, collapsed,
            scan_scope=scan_scope,
        )

    def update(self, *, expected_revision: int, search_query: str, filters: frozenset[str],
               sort_column: PlanSortColumn, sort_direction: SortDirection,
               collapse_node_id: str | None, collapsed: bool | None) -> dict[str, object]:
        if expected_revision != self.view_revision:
            return self.summary(disposition="conflict")
        if type(filters) is not frozenset or not filters <= INVENTORY_FILTERS:
            raise ValueError("inventory filters are invalid")
        if (collapse_node_id is None) != (collapsed is None):
            raise ValueError("inventory collapse gesture is invalid")
        next_collapsed = set(self.collapsed_node_ids)
        if collapse_node_id is not None:
            node = self.projection.node_for_id(collapse_node_id)
            if not node.is_container or node.warning is not None:
                raise ValueError("only inventory folders may collapse")
            if collapsed:
                next_collapsed.add(collapse_node_id)
            else:
                next_collapsed.discard(collapse_node_id)
        next_collapsed = frozenset(next_collapsed)
        state = (search_query, filters, sort_column, sort_direction, next_collapsed)
        if state == (self.search_query, self.filters, self.sort_column, self.sort_direction, self.collapsed_node_ids):
            return self.summary(disposition="noop")
        if self.view_revision >= MAX_JAVASCRIPT_SAFE_INTEGER:
            raise OverflowError("inventory view revision is exhausted")
        order = self._order if (sort_column, sort_direction) == (self.sort_column, self.sort_direction) else sort_inventory_projection(self.projection, sort_column, sort_direction)
        visible = self._derive(order, search_query, filters, next_collapsed)
        self.search_query, self.filters, self.sort_column, self.sort_direction, self.collapsed_node_ids = state
        self._order, self._visible = order, visible
        self.view_revision += 1
        return self.summary()

    def window(self, *, expected_revision: int, offset: int, limit: int) -> dict[str, object]:
        if expected_revision != self.view_revision:
            return {"disposition": "conflict", "view_revision": self.view_revision,
                    "offset": offset, "total": 0, "rows": []}
        window = window_visible_sequence(self._visible, offset=offset + 1, limit=limit)
        rows = []
        for frame in window.rows:
            node, row = frame.node, frame.node.row
            rows.append({
                "node_id": node.node_id, "display": node.display,
                "depth": node.depth - 1, "is_container": node.is_container,
                "visible_index": frame.visible_index - 1,
                "parent_visible_index": None if frame.parent_visible_index in (None, 0) else frame.parent_visible_index - 1,
                "first_child_visible_index": None if frame.first_child_visible_index is None else frame.first_child_visible_index - 1,
                "position_in_set": frame.position_in_set, "set_size": frame.set_size,
                "expanded": frame.expanded, "row_kind": node.row_kind,
                "row_id": None if row is None else row.row_id,
                "presence": None if row is None else row.presence.value,
                "verification_state": None if row is None else row.verification_state.value,
                "has_baseline": row is not None and row.attestation is not None,
                "acknowledged": row is not None and row.acknowledged_at is not None,
                "reappeared": row is not None and row.reappeared_at is not None,
                "size": None if node.size is None else str(node.size),
                "mtime_ns": None if node.mtime_ns is None else str(node.mtime_ns),
                "rollup": inventory_rollup_wire(node.rollup),
                "warning": None if node.warning is None else {
                    "code": node.warning.code.value, "path": node.warning.rel_path,
                    "detail": node.warning.detail,
                },
            })
        return {"disposition": "current", "view_revision": self.view_revision,
                "offset": offset, "total": max(0, window.total - 1), "rows": rows}
