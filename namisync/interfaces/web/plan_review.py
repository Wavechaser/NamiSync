"""Process-local state for bounded, server-authoritative plan review."""

from __future__ import annotations

from array import array
from collections.abc import Mapping
from dataclasses import dataclass, field
from threading import RLock
from types import MappingProxyType

from namisync.interfaces.ui_state import MAX_JAVASCRIPT_SAFE_INTEGER

from namisync.workflows import (
    _sort_plan_projection_from_canonical,
    PlanProjection,
    PlanProjectionNode,
    PlanProjectionOrder,
    PlanSortColumn,
    SortDirection,
    apply_plan_projection_selection,
    sort_plan_projection,
)

from .visible_sequence import (
    VisibleSequence,
    VisibleSequenceParameters,
    _derive_visible_sequence_from_validated,
    _validate_structure,
    resolve_visible_anchor,
    window_visible_sequence,
)


PLAN_FILTERS = frozenset(
    {
        "copy",
        "mkdir",
        "move",
        "recase",
        "update",
        "move_update",
        "trash",
        "delete",
        "noop",
        "blocked",
        "notice",
    }
)

# Keep the wire order stable even though PLAN_FILTERS is intentionally a set.
_PLAN_FILTER_COUNT_CATEGORIES = (
    "all",
    "copy",
    "mkdir",
    "move",
    "recase",
    "update",
    "move_update",
    "trash",
    "delete",
    "noop",
    "blocked",
    "notice",
)


@dataclass(slots=True)
class PlanReviewState:
    task_id: str
    request_id: str
    projection: PlanProjection
    selection_revision: int
    selection_state: str
    source_path: str
    target_path: str
    requires_destructive_confirmation: bool = False
    irreversible_update_count: int = 0
    destructive_operation_count: int = 0
    irreversible_operation_count: int = 0
    destructive_operation_counts: Mapping[str, int] = field(
        default_factory=lambda: MappingProxyType(
            {"update": 0, "move_update": 0, "trash": 0, "delete": 0}
        )
    )
    required_bytes: str = "0"
    view_revision: int = 0
    search_query: str = ""
    filters: frozenset[str] = field(default_factory=frozenset)
    sort_column: PlanSortColumn = PlanSortColumn.PATH
    sort_direction: SortDirection = SortDirection.ASCENDING
    collapsed_node_ids: frozenset[str] = field(default_factory=frozenset)
    _canonical_order: PlanProjectionOrder | None = None
    _order: PlanProjectionOrder | None = None
    _visible: VisibleSequence[PlanProjectionNode] | None = None
    _scope_selectable: array | None = None
    _scope_selected: array | None = None
    _filter_counts: Mapping[str, int] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def __post_init__(self) -> None:
        _validate_structure(self.projection.nodes)
        self.destructive_operation_counts = _validate_execution_facts(
            self.requires_destructive_confirmation,
            self.irreversible_update_count,
            self.destructive_operation_count,
            self.irreversible_operation_count,
            self.destructive_operation_counts,
            self.required_bytes,
        )
        self._filter_counts = _plan_filter_counts(self.projection)
        self._canonical_order = sort_plan_projection(
            self.projection, PlanSortColumn.PATH, SortDirection.ASCENDING
        )
        self._order = (
            self._canonical_order
            if self.sort_column is PlanSortColumn.PATH
            else _sort_plan_projection_from_canonical(
                self._canonical_order, self.sort_column, self.sort_direction
            )
        )
        self._visible = _derive_view(
            self._order,
            search_query=self.search_query,
            filters=self.filters,
            sort_column=self.sort_column,
            sort_direction=self.sort_direction,
            collapsed_node_ids=self.collapsed_node_ids,
        )
        self._scope_selectable, self._scope_selected = _scope_prefixes(
            self.projection, self.search_query, self.filters
        )

    @property
    def canonical_order(self) -> PlanProjectionOrder:
        assert self._canonical_order is not None
        return self._canonical_order

    @property
    def current_order(self) -> PlanProjectionOrder:
        assert self._order is not None
        return self._order

    @property
    def current_sequence(self) -> VisibleSequence[PlanProjectionNode]:
        assert self._visible is not None
        return self._visible

    def summary(self, *, disposition: str = "current") -> dict[str, object]:
        with self._lock:
            return self._summary(disposition=disposition)

    def _summary(self, *, disposition: str) -> dict[str, object]:
        root = self.projection.nodes[0]
        assert self._visible is not None
        assert self._scope_selectable is not None and self._scope_selected is not None
        return {
            "disposition": disposition,
            "task_id": self.task_id,
            "request_id": self.request_id,
            "view_revision": self.view_revision,
            "selection_revision": self.selection_revision,
            "selection_state": self.selection_state,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "selected_operation_count": root.selected_operation_count,
            "selectable_operation_count": root.selectable_operation_count,
            "scope_selectable_operation_count": self._scope_selectable[-1],
            "scope_selected_operation_count": self._scope_selected[-1],
            "operation_count": root.operation_count,
            "filter_counts": dict(self._filter_counts),
            "preflight_ready": self.projection.preflight_ready,
            "preflight_refusal_count": self.projection.preflight_refusal_count,
            "warning_count": self.projection.warning_count,
            "requires_destructive_confirmation": self.requires_destructive_confirmation,
            "irreversible_update_count": self.irreversible_update_count,
            "destructive_operation_count": self.destructive_operation_count,
            "irreversible_operation_count": self.irreversible_operation_count,
            "destructive_operation_counts": dict(
                self.destructive_operation_counts
            ),
            "required_bytes": self.required_bytes,
            "visible_row_count": max(0, len(self._visible.visible_positions) - 1),
            "search_query": self.search_query,
            "filters": sorted(self.filters),
            "sort_column": self.sort_column.value,
            "sort_direction": self.sort_direction.value,
            "collapsed_count": len(self.collapsed_node_ids),
        }

    def selection_scope(
        self,
        *,
        expected_view_revision: int,
        expected_selection_revision: int,
        node_id: str | None = None,
    ) -> tuple[str, ...] | None:
        """Resolve the complete active query under both revision guards."""

        with self._lock:
            if (
                expected_view_revision != self.view_revision
                or expected_selection_revision != self.selection_revision
            ):
                return None
            bounds = None
            if node_id is not None:
                node = self.projection.node_for_id(node_id)
                if node.position == 0:
                    raise ValueError("synthetic Plan root is not a selectable row")
                if node.selection == "disabled" or node.row_kind.startswith("prior-"):
                    raise ValueError("plan row is not selectable")
                bounds = (node.position, node.subtree_end)
            return tuple(
                node.operation_id
                for node in self.projection.nodes
                if self._scope_selectable[node.position + 1]
                > self._scope_selectable[node.position]
                if bounds is None or bounds[0] <= node.position < bounds[1]
            )

    def update(
        self,
        *,
        expected_revision: int,
        search_query: str,
        filters: frozenset[str],
        sort_column: PlanSortColumn,
        sort_direction: SortDirection,
        collapse_node_id: str | None,
        collapsed: bool | None,
    ) -> dict[str, object]:
        with self._lock:
            if expected_revision != self.view_revision:
                return self._summary(disposition="conflict")
            if not filters <= PLAN_FILTERS:
                raise ValueError("plan filter is unknown")
            if (
                sort_column is PlanSortColumn.PATH
                and sort_direction is not SortDirection.ASCENDING
            ):
                raise ValueError("canonical path sort supports ascending only")
            next_collapsed = set(self.collapsed_node_ids)
            if collapse_node_id is None:
                if collapsed is not None:
                    raise ValueError("collapsed requires a node id")
            else:
                if type(collapsed) is not bool:
                    raise ValueError("collapse gesture requires a boolean")
                node = self.projection.node_for_id(collapse_node_id)
                if not node.is_container:
                    raise ValueError("only containers may be collapsed")
                if collapsed:
                    next_collapsed.add(collapse_node_id)
                else:
                    next_collapsed.discard(collapse_node_id)
            frozen_collapsed = frozenset(next_collapsed)
            changed = (
                search_query != self.search_query
                or filters != self.filters
                or sort_column is not self.sort_column
                or sort_direction is not self.sort_direction
                or frozen_collapsed != self.collapsed_node_ids
            )
            if changed:
                next_revision = _next_revision(self.view_revision)
                assert self._order is not None and self._canonical_order is not None
                if sort_column is self.sort_column and sort_direction is self.sort_direction:
                    order = self._order
                elif sort_column is PlanSortColumn.PATH:
                    order = self._canonical_order
                else:
                    order = _sort_plan_projection_from_canonical(
                        self._canonical_order, sort_column, sort_direction
                    )
                visible = _derive_view(
                    order,
                    search_query=search_query,
                    filters=filters,
                    sort_column=sort_column,
                    sort_direction=sort_direction,
                    collapsed_node_ids=frozen_collapsed,
                )
                selectable, selected = (
                    (self._scope_selectable, self._scope_selected)
                    if search_query == self.search_query and filters == self.filters
                    else _scope_prefixes(self.projection, search_query, filters)
                )
                self.search_query = search_query
                self.filters = filters
                self.sort_column = sort_column
                self.sort_direction = sort_direction
                self.collapsed_node_ids = frozen_collapsed
                self._order = order
                self._visible = visible
                self._scope_selectable = selectable
                self._scope_selected = selected
                self.view_revision = next_revision
            return self._summary(disposition="applied" if changed else "noop")

    def replace_selection(
        self,
        *,
        selected_operation_ids: frozenset[str],
        exclusion_reasons: dict[str, str | None],
        selection_revision: int,
        selection_state: str,
        requires_destructive_confirmation: bool,
        irreversible_update_count: int,
        destructive_operation_count: int,
        irreversible_operation_count: int,
        destructive_operation_counts: Mapping[str, int],
        required_bytes: str,
    ) -> None:
        with self._lock:
            frozen_counts = _validate_execution_facts(
                requires_destructive_confirmation,
                irreversible_update_count,
                destructive_operation_count,
                irreversible_operation_count,
                destructive_operation_counts,
                required_bytes,
            )
            next_revision = _next_revision(self.view_revision)
            projection = apply_plan_projection_selection(
                self.projection,
                selected_operation_ids=selected_operation_ids,
                exclusion_reasons=exclusion_reasons,
            )
            assert self._order is not None and self._canonical_order is not None and self._visible is not None
            canonical_order = self._canonical_order._rebind_selection(projection)
            order = (
                canonical_order
                if self._order is self._canonical_order
                else self._order._rebind_selection(projection)
            )
            visible = self._visible._rebind_nodes(
                projection.nodes,
                projection.position_by_node_id,
            )
            selectable, selected = _scope_prefixes(
                projection, self.search_query, self.filters
            )
            self.projection = projection
            self.selection_revision = selection_revision
            self.selection_state = selection_state
            self.requires_destructive_confirmation = (
                requires_destructive_confirmation
            )
            self.irreversible_update_count = irreversible_update_count
            self.destructive_operation_count = destructive_operation_count
            self.irreversible_operation_count = irreversible_operation_count
            self.destructive_operation_counts = frozen_counts
            self.required_bytes = required_bytes
            self._canonical_order = canonical_order
            self._order = order
            self._visible = visible
            self._scope_selectable = selectable
            self._scope_selected = selected
            self.view_revision = next_revision

    def mark_selection_committed(self) -> None:
        with self._lock:
            if self.selection_state == "committed":
                return
            next_revision = _next_revision(self.view_revision)
            self.selection_state = "committed"
            self.view_revision = next_revision

    def window(self, *, expected_revision: int, offset: int, limit: int) -> dict[str, object]:
        with self._lock:
            if expected_revision != self.view_revision:
                return {
                    "disposition": "conflict",
                    "view_revision": self.view_revision,
                    "offset": offset,
                    "total": 0,
                    "rows": [],
                }
            assert self._visible is not None
            window = window_visible_sequence(self._visible, offset=offset + 1, limit=limit)
            return {
                "disposition": "current",
                "view_revision": self.view_revision,
                "offset": offset,
                "total": max(0, window.total - 1),
                "rows": [
                    _row_view(
                        row, rootless=True,
                        selection=self._scoped_row_selection(row.node),
                    )
                    for row in window.rows
                ],
            }

    def _scoped_row_selection(self, node: PlanProjectionNode) -> str:
        if not self.search_query and not self.filters:
            return node.selection
        assert self._scope_selectable is not None and self._scope_selected is not None
        selectable = self._scope_selectable[node.subtree_end] - self._scope_selectable[node.position]
        selected = self._scope_selected[node.subtree_end] - self._scope_selected[node.position]
        if selectable == 0:
            return "disabled"
        if selected == selectable:
            return "selected"
        return "unselected" if selected == 0 else "mixed"

    def node_for_id(self, node_id: str) -> PlanProjectionNode:
        with self._lock:
            return self.projection.node_for_id(node_id)

    def anchor(self, *, expected_revision: int, node_id: str) -> dict[str, object]:
        with self._lock:
            if expected_revision != self.view_revision:
                return {
                "disposition": "conflict",
                "view_revision": self.view_revision,
                "node_id": None,
                "index": None,
                }
            assert self._visible is not None
            position = self.projection.position_by_node_id.get(node_id)
            if position is None:
                raise ValueError("anchor node id is unknown")
            chain: list[str] = []
            while position is not None:
                node = self.projection.nodes[position]
                chain.append(node.node_id)
                position = node.parent_index
            anchor = resolve_visible_anchor(self._visible, chain)
            if anchor is not None and anchor.index == 0:
                anchor = None
            return {
                "disposition": "current",
                "view_revision": self.view_revision,
                "node_id": None if anchor is None else anchor.node_id,
                "index": None if anchor is None else anchor.index - 1,
            }


def _next_revision(current: int) -> int:
    if current >= MAX_JAVASCRIPT_SAFE_INTEGER:
        raise OverflowError("plan view revision is exhausted")
    return current + 1


def _validate_execution_facts(
    requires_destructive_confirmation: bool,
    irreversible_update_count: int,
    destructive_operation_count: int,
    irreversible_operation_count: int,
    destructive_operation_counts: Mapping[str, int],
    required_bytes: str,
) -> Mapping[str, int]:
    if type(requires_destructive_confirmation) is not bool:
        raise TypeError("destructive confirmation requirement must be a bool")
    for label, value in (
        ("irreversible update count", irreversible_update_count),
        ("destructive operation count", destructive_operation_count),
        ("irreversible operation count", irreversible_operation_count),
    ):
        if (
            type(value) is not int
            or value < 0
            or value > MAX_JAVASCRIPT_SAFE_INTEGER
        ):
            raise ValueError(f"{label} must be a nonnegative SafeInt")
    if irreversible_update_count > destructive_operation_count:
        raise ValueError("irreversible update count exceeds destructive operations")
    if not isinstance(destructive_operation_counts, Mapping):
        raise TypeError("destructive operation counts must be a mapping")
    counts = dict(destructive_operation_counts)
    if set(counts) != {"update", "move_update", "trash", "delete"}:
        raise ValueError("destructive operation counts have invalid keys")
    for value in counts.values():
        if (
            type(value) is not int
            or value < 0
            or value > MAX_JAVASCRIPT_SAFE_INTEGER
        ):
            raise ValueError("destructive operation breakdown must use SafeInts")
    if sum(counts.values()) != destructive_operation_count:
        raise ValueError("destructive operation breakdown disagrees with total")
    if irreversible_update_count > counts["update"]:
        raise ValueError("irreversible update count exceeds selected updates")
    if irreversible_operation_count != (
        irreversible_update_count + counts["delete"]
    ):
        raise ValueError("irreversible operation count disagrees with breakdown")
    if requires_destructive_confirmation != (destructive_operation_count > 0):
        raise ValueError("destructive confirmation requirement disagrees with count")
    if (
        type(required_bytes) is not str
        or not required_bytes
        or any(character not in "0123456789" for character in required_bytes)
        or (len(required_bytes) > 1 and required_bytes.startswith("0"))
    ):
        raise ValueError("required bytes must be canonical scalar text")
    return MappingProxyType(counts)


def _derive_view(
    order: PlanProjectionOrder,
    *,
    search_query: str,
    filters: frozenset[str],
    sort_column: PlanSortColumn,
    sort_direction: SortDirection,
    collapsed_node_ids: frozenset[str],
) -> VisibleSequence[PlanProjectionNode]:
    projection = order.projection
    match_mask = None
    if filters:
        match_mask = bytes(
            _direct_filter_count(node, filters) for node in projection.nodes
        )
    visible = _derive_visible_sequence_from_validated(
        projection.nodes,
        projection.position_by_node_id,
        VisibleSequenceParameters(
            collapsed_node_ids=collapsed_node_ids,
            search_query=search_query,
        ),
        ordered_source_positions=order.ordered_source_positions,
        order_rank_by_source_position=order.order_rank_by_source_position,
        match_mask_by_position=match_mask,
    )
    return visible


def _direct_filter_count(node: PlanProjectionNode, filters: frozenset[str]) -> int:
    if node.row_kind == "notice":
        return int("notice" in filters)
    if node.row_kind.startswith("prior-"):
        return 0
    if node.operation_id is None:
        return 0
    if node.blocked_reason is not None:
        return int("blocked" in filters)
    return int(node.operation_kind in filters)


def _plan_filter_counts(projection: PlanProjection) -> Mapping[str, int]:
    """Count direct filter categories across the complete immutable plan.

    Container rollups, prior-path context rows, and other structural rows are
    not categories.  A blocked operation is counted only as ``blocked`` (not
    again under its underlying operation kind), while each notice is counted
    as ``notice``.  ``all`` is therefore the sum of the mutually exclusive
    operation/notice categories.
    """

    counts = {category: 0 for category in _PLAN_FILTER_COUNT_CATEGORIES}
    for node in projection.nodes:
        if node.row_kind == "notice":
            category = "notice"
        elif node.row_kind.startswith("prior-") or node.operation_id is None:
            continue
        elif node.blocked_reason is not None:
            category = "blocked"
        else:
            category = node.operation_kind
        if category not in PLAN_FILTERS:
            raise ValueError("plan projection contains an unknown filter category")
        counts[category] += 1
        counts["all"] += 1
    return MappingProxyType(counts)


def _matches_scope_query(
    node: PlanProjectionNode, query: str, filters: frozenset[str]
) -> bool:
    return (
        node.operation_id is not None
        and not node.row_kind.startswith("prior-")
        and (not filters or bool(_direct_filter_count(node, filters)))
        and (not query or query in node.display.casefold())
    )


def _scope_prefixes(
    projection: PlanProjection,
    search_query: str,
    filters: frozenset[str],
) -> tuple[array, array]:
    nodes = projection.nodes
    child_selectable = [0] * len(nodes)
    child_selected = [0] * len(nodes)
    for node in nodes[1:]:
        assert node.parent_index is not None
        child_selectable[node.parent_index] += node.selectable_operation_count
        child_selected[node.parent_index] += node.selected_operation_count
    selectable = array("Q", [0])
    selected = array("Q", [0])
    query = search_query.casefold()
    for node in nodes:
        matched = _matches_scope_query(node, query, filters)
        direct_selectable = node.selectable_operation_count - child_selectable[node.position]
        direct_selected = node.selected_operation_count - child_selected[node.position]
        selectable.append(selectable[-1] + (direct_selectable if matched else 0))
        selected.append(selected[-1] + (direct_selected if matched else 0))
    return selectable, selected


def _row_view(row, *, rootless: bool = False, selection: str | None = None) -> dict[str, object]:
    node = row.node
    parent_visible = row.parent_visible_index
    if rootless and parent_visible == 0:
        parent_visible = None
    elif rootless and parent_visible is not None:
        parent_visible -= 1
    return {
        "node_id": node.node_id,
        "display": node.display,
        "depth": node.depth - int(rootless),
        "is_container": node.is_container,
        "visible_index": row.visible_index - int(rootless),
        "parent_visible_index": parent_visible,
        "first_child_visible_index": (
            None if row.first_child_visible_index is None
            else row.first_child_visible_index - int(rootless)
        ),
        "position_in_set": row.position_in_set,
        "set_size": row.set_size,
        "expanded": row.expanded,
        "row_kind": node.row_kind,
        "operation_id": node.operation_id,
        "operation_kind": node.operation_kind,
        "reason": node.reason,
        "blocked_reason": node.blocked_reason,
        "selection": node.selection if selection is None else selection,
        "selectable_operation_count": node.selectable_operation_count,
        "selected_operation_count": node.selected_operation_count,
        "operation_count": node.operation_count,
        "size": None if node.size is None else str(node.size),
        "mtime_ns": None if node.mtime_ns is None else str(node.mtime_ns),
        "dependency_count": node.dependency_count,
        "risk": node.risk,
        "move_peer_id": node.move_peer_id,
        "notice": node.notice,
        "selection_exclusion_reason": node.selection_exclusion_reason,
    }


__all__ = ["PLAN_FILTERS", "PlanReviewState"]
