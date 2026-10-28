"""Process-local state for bounded, server-authoritative plan review."""

from __future__ import annotations

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

from .recall import recall_summary_wire
from .row_highlight import apply_row_highlight, highlight_visible_index
from .review_view import (
    ReviewView, ScopeCounts, count_scope, covered_positions,
    next_revision as _next_revision, update_review_view,
)
from .visible_sequence import (
    VisibleSequence,
    VisibleSequenceParameters,
    _derive_visible_sequence_from_validated,
    _validate_structure,
    resolve_visible_node_anchor,
    window_visible_sequence,
)


PLAN_FILTERS = frozenset(
    {
        "copy",
        "mkdir",
        "move",
        "rename",
        "update",
        "move_update",
        "trash",
        "delete",
        "noop",
        "blocked",
        "error",
        "unsupported",
        "notice",
        "recall",
    }
)

# Keep the wire order stable even though PLAN_FILTERS is intentionally a set.
_PLAN_FILTER_COUNT_CATEGORIES = (
    "all",
    "copy",
    "mkdir",
    "move",
    "rename",
    "update",
    "move_update",
    "trash",
    "delete",
    "noop",
    "blocked",
    "error",
    "unsupported",
    "notice",
    "recall",
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
    highlight_revision: int = 0
    highlighted_node_ids: frozenset[str] = field(default_factory=frozenset)
    highlight_anchor_node_id: str | None = None
    highlight_focus_node_id: str | None = None
    _canonical_order: PlanProjectionOrder | None = None
    _view: ReviewView[PlanProjectionOrder, PlanProjectionNode] = field(init=False, repr=False)
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
        order = self._sort(self.sort_column, self.sort_direction)
        self._view = ReviewView(
            order, self._derive(order, self.search_query, self.filters, self.collapsed_node_ids),
            self._scope(self.search_query, self.filters),
        )

    def _sort(self, column: PlanSortColumn, direction: SortDirection) -> PlanProjectionOrder:
        assert self._canonical_order is not None
        return (self._canonical_order if column is PlanSortColumn.PATH else
                _sort_plan_projection_from_canonical(self._canonical_order, column, direction))

    def _derive(self, order: PlanProjectionOrder, search: str, filters: frozenset[str],
                collapsed: frozenset[str]) -> VisibleSequence[PlanProjectionNode]:
        return _derive_view(order, search_query=search, filters=filters,
            collapsed_node_ids=collapsed)

    def _scope(self, search: str, filters: frozenset[str]) -> ScopeCounts:
        return _scope_prefixes(self.projection, search, filters)

    @property
    def canonical_order(self) -> PlanProjectionOrder:
        assert self._canonical_order is not None
        return self._canonical_order

    @property
    def current_order(self) -> PlanProjectionOrder:
        return self._view.order

    @property
    def current_sequence(self) -> VisibleSequence[PlanProjectionNode]:
        return self._view.visible

    def summary(self, *, disposition: str = "current") -> dict[str, object]:
        with self._lock:
            return self._summary(disposition=disposition)

    def _summary(self, *, disposition: str) -> dict[str, object]:
        root = self.projection.nodes[0]
        return {
            "disposition": disposition,
            "task_id": self.task_id,
            "request_id": self.request_id,
            "view_revision": self.view_revision,
            "selection_revision": self.selection_revision,
            "selection_state": self.selection_state,
            "highlight_revision": self.highlight_revision,
            "highlight_anchor_node_id": self.highlight_anchor_node_id,
            "highlight_focus_node_id": self.highlight_focus_node_id,
            "highlight_focus_visible_index": self._highlight_focus_visible_index(),
            "highlighted_count": len(self.highlighted_node_ids),
            "source_path": self.source_path,
            "target_path": self.target_path,
            "selected_operation_count": root.selected_operation_count,
            "selectable_operation_count": root.selectable_operation_count,
            "scope_selectable_operation_count": self._view.scope.selectable[-1],
            "scope_selected_operation_count": self._view.scope.selected[-1],
            "operation_count": root.operation_count,
            "filter_counts": dict(self._filter_counts),
            "recall": {"source": recall_summary_wire(self.projection.source_recall),
                       "target": recall_summary_wire(self.projection.target_recall)},
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
            "visible_row_count": max(0, len(self._view.visible.visible_positions) - 1),
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
                if self._view.scope.selectable[node.position + 1]
                > self._view.scope.selectable[node.position]
                if bounds is None or bounds[0] <= node.position < bounds[1]
            )

    def highlighted_selection_scope(
        self,
        *,
        expected_view_revision: int,
        expected_highlight_revision: int,
        expected_selection_revision: int,
    ) -> tuple[str, ...] | None:
        """Resolve highlighted rows to the current selectable operation scope.

        Multiple highlighted rows contribute only their own operations. A single
        highlighted container retains recursive scope. The active query and
        filters still decide which operation rows qualify.
        """

        with self._lock:
            if (
                expected_view_revision != self.view_revision
                or expected_highlight_revision != self.highlight_revision
                or expected_selection_revision != self.selection_revision
            ):
                return None
            nodes = self.projection.nodes
            recursive = len(self.highlighted_node_ids) == 1
            ranges = (
                (position, nodes[position].subtree_end if recursive else position + 1)
                for node_id in self.highlighted_node_ids
                if (position := self.projection.position_by_node_id.get(node_id)) is not None
            )
            operation_ids: list[str] = []
            seen: set[str] = set()
            for position in covered_positions(len(nodes), ranges):
                node = nodes[position]
                if (self._view.scope.selectable[position + 1] > self._view.scope.selectable[position]
                        and node.operation_id is not None and node.operation_id not in seen):
                    seen.add(node.operation_id)
                    operation_ids.append(node.operation_id)
            return tuple(operation_ids)

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
            disposition = update_review_view(self, search_query=search_query, filters=filters,
                sort_column=sort_column, sort_direction=sort_direction,
                collapsed_node_ids=frozen_collapsed)
            return self._summary(disposition=disposition)

    def mutate_highlight(
        self,
        *,
        expected_view_revision: int,
        expected_highlight_revision: int,
        gesture: str,
        node_id: str | None = None,
    ) -> dict[str, object]:
        """Apply a presentation-only highlight gesture under both revisions."""

        with self._lock:
            if (
                expected_view_revision != self.view_revision
                or expected_highlight_revision != self.highlight_revision
            ):
                return self._summary(disposition="conflict")
            disposition = apply_row_highlight(self, self._view.visible, gesture, node_id)
            return self._summary(disposition=disposition)

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
            assert self._canonical_order is not None
            canonical_order = self._canonical_order._rebind_selection(projection)
            order = (
                canonical_order
                if self._view.order is self._canonical_order
                else self._view.order._rebind_selection(projection)
            )
            visible = self._view.visible._rebind_nodes(
                projection.nodes,
                projection.position_by_node_id,
            )
            scope = _scope_prefixes(
                projection, self.search_query, self.filters
            )
            view = ReviewView(order, visible, scope)
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
            self._view = view
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
                    "highlight_revision": self.highlight_revision,
                    "offset": offset,
                    "total": 0,
                    "rows": [],
                }
            window = window_visible_sequence(self._view.visible, offset=offset + 1, limit=limit)
            return {
                "disposition": "current",
                "view_revision": self.view_revision,
                "highlight_revision": self.highlight_revision,
                "offset": offset,
                "total": max(0, window.total - 1),
                "rows": [
                    _row_view(
                        row, rootless=True,
                        selection=self._scoped_row_selection(row.node),
                        highlighted=row.node.node_id in self.highlighted_node_ids,
                    )
                    for row in window.rows
                ],
            }

    def _highlight_visible_index(self, node_id: str | None) -> int | None:
        return highlight_visible_index(self._view.visible, node_id)

    def _highlight_focus_visible_index(self) -> int | None:
        return self._highlight_visible_index(self.highlight_focus_node_id)

    def _scoped_row_selection(self, node: PlanProjectionNode) -> str:
        if not self.search_query and not self.filters:
            return node.selection
        selectable, selected = self._view.scope.subtree(node.position, node.subtree_end)
        if selectable == 0:
            return "disabled"
        if selected == selectable:
            return "selected"
        return "unselected" if selected == 0 else "mixed"

    def node_for_id(self, node_id: str) -> PlanProjectionNode:
        with self._lock:
            return self.projection.node_for_id(node_id)

    def detail(self, *, expected_revision: int, node_id: str) -> dict[str, object]:
        with self._lock:
            response: dict[str, object] = {
                "disposition": "conflict", "view_revision": self.view_revision,
                "node_id": node_id, "detail": None,
            }
            if expected_revision != self.view_revision:
                return response
            node = self.projection.node_for_id(node_id)
            if node.position == 0:
                raise ValueError("synthetic Plan root has no public detail")
            response["disposition"] = "current"
            response["detail"] = {
                "path": node.path, "prior_path": node.prior_path,
                "move_destination_path": node.move_destination_path,
                "path_origin": node.path_origin,
                "source_path": node.source_path,
                "notice": node.notice,
            }
            return response

    def reveal_move(self, *, expected_revision: int, node_id: str) -> dict[str, object]:
        """Reveal one informational group's server-owned canonical destination."""

        with self._lock:
            if expected_revision != self.view_revision:
                return {"summary": self._summary(disposition="conflict"), "node_id": None, "index": None}
            group = self.projection.node_for_id(node_id)
            if group.row_kind != "prior-group" or group.move_peer_id is None:
                raise ValueError("move reveal requires an informational move group")
            target = self.projection.node_for_id(group.move_peer_id)
            ancestors: set[str] = set()
            position = target.parent_index
            while position is not None:
                node = self.projection.nodes[position]
                ancestors.add(node.node_id)
                position = node.parent_index
            collapsed = self.collapsed_node_ids - ancestors
            query, filters = self.search_query, self.filters
            visible = None
            for next_query, next_filters in dict.fromkeys((
                (query, filters), ("", filters), (query, frozenset()), ("", frozenset()),
            )):
                candidate = _derive_view(
                    self._view.order, search_query=next_query, filters=next_filters,
                    collapsed_node_ids=collapsed,
                )
                if candidate.visible_index_by_source_position[target.position] < len(self.projection.nodes):
                    query, filters, visible = next_query, next_filters, candidate
                    break
            assert visible is not None
            disposition = update_review_view(self, search_query=query, filters=filters,
                sort_column=self.sort_column, sort_direction=self.sort_direction,
                collapsed_node_ids=collapsed, visible=visible)
            return {
                "summary": self._summary(disposition=disposition),
                "node_id": target.node_id,
                "index": visible.visible_index_by_source_position[target.position] - 1,
            }

    def operation_anchor(
        self, *, expected_revision: int, operation_id: str,
    ) -> dict[str, object]:
        with self._lock:
            if expected_revision != self.view_revision:
                return {
                    "disposition": "conflict", "view_revision": self.view_revision,
                    "node_id": None, "index": None,
                }
            node_id = self.projection.operation_node_id_by_id.get(operation_id)
            if node_id is None:
                raise ValueError("anchor operation id is unknown")
            return self.anchor(expected_revision=expected_revision, node_id=node_id)

    def anchor(self, *, expected_revision: int, node_id: str) -> dict[str, object]:
        with self._lock:
            if expected_revision != self.view_revision:
                return {
                "disposition": "conflict",
                "view_revision": self.view_revision,
                "node_id": None,
                "index": None,
                }
            anchor = resolve_visible_node_anchor(self._view.visible, node_id)
            if anchor is not None and anchor.index == 0:
                anchor = None
            return {
                "disposition": "current",
                "view_revision": self.view_revision,
                "node_id": None if anchor is None else anchor.node_id,
                "index": None if anchor is None else anchor.index - 1,
            }


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
    if node.recall and "recall" in filters and not node.row_kind.startswith("prior-"):
        return 1
    if node.row_kind.startswith("prior-"):
        return 0
    if node.operation_id is None:
        return 0
    if node.blocked_reason is not None:
        category = (
            "unsupported" if node.blocked_reason == "unsupported" else "blocked"
        )
        return int(category in filters)
    return int(node.presentation_kind in filters)


def _plan_filter_counts(projection: PlanProjection) -> Mapping[str, int]:
    """Count direct filter categories across the complete immutable plan.

    Container rollups, prior-path context rows, and other structural rows are
    not categories. Unsupported blocked operations are counted separately from
    other blocked operations. Execution errors are not present in the immutable
    plan projection, so ``error`` remains zero until an error-bearing projection
    exists. Each notice is counted as ``notice``. ``all`` is therefore the sum
    of the mutually exclusive operation/notice categories. Recall is an
    overlapping advisory and also matches directly observed directory rows.
    """

    counts = {category: 0 for category in _PLAN_FILTER_COUNT_CATEGORIES}
    for node in projection.nodes:
        if node.row_kind == "notice":
            category = "notice"
        elif node.row_kind.startswith("prior-") or node.operation_id is None:
            continue
        elif node.blocked_reason is not None:
            category = (
                "unsupported" if node.blocked_reason == "unsupported" else "blocked"
            )
        else:
            category = node.presentation_kind
        if category not in PLAN_FILTERS:
            raise ValueError("plan projection contains an unknown filter category")
        counts[category] += 1
        counts["all"] += 1
    counts["recall"] = sum(node.recall for node in projection.nodes
                           if not node.row_kind.startswith("prior-"))
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
) -> ScopeCounts:
    nodes = projection.nodes
    child_selectable = [0] * len(nodes)
    child_selected = [0] * len(nodes)
    for node in nodes[1:]:
        assert node.parent_index is not None
        child_selectable[node.parent_index] += node.selectable_operation_count
        child_selected[node.parent_index] += node.selected_operation_count
    query = search_query.casefold()
    return count_scope(
        (_matches_scope_query(node, query, filters),
         node.selectable_operation_count - child_selectable[node.position],
         node.selected_operation_count - child_selected[node.position])
        for node in nodes
    )


def _row_view(
    row,
    *,
    rootless: bool = False,
    selection: str | None = None,
    highlighted: bool = False,
) -> dict[str, object]:
    node = row.node
    destination_display = (
        None if node.move_destination_path is None
        else _destination_display(node.move_destination_path)
    )
    parent_visible = row.parent_visible_index
    if rootless and parent_visible == 0:
        parent_visible = None
    elif rootless and parent_visible is not None:
        parent_visible -= 1
    return {
        "node_id": node.node_id,
        "display": (
            f"{node.move_item_count} {'item' if node.move_item_count == 1 else 'items'} moved to {destination_display or 'root'}"
            if node.row_kind == "prior-group" else _notice_display(node)
            if node.scan_warning is not None else _tail_text(node.display, 300)
        ),
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
        "presentation_kind": node.presentation_kind,
        "prior_name": (
            _tail_text(node.prior_path.replace('/', '\\').rsplit('\\', 1)[-1], 255)
            if node.prior_path is not None and node.presentation_kind == "rename"
            else None
        ),
        "reason": node.reason,
        "blocked_reason": node.blocked_reason,
        "selection": node.selection if selection is None else selection,
        "highlighted": highlighted,
        "recall": node.recall,
        "selectable_operation_count": node.selectable_operation_count,
        "selected_operation_count": node.selected_operation_count,
        "operation_count": node.operation_count,
        "size": None if node.size is None else str(node.size),
        "mtime_ns": None if node.mtime_ns is None else str(node.mtime_ns),
        "dependency_count": node.dependency_count,
        "risk": node.risk,
        "move_peer_id": node.move_peer_id,
        "move_group": None if node.move_destination_path is None else {
            "count": node.move_item_count, "destination_display": destination_display,
        },
        "notice": None if node.notice is None else _notice_display(node),
        "selection_exclusion_reason": node.selection_exclusion_reason,
    }


def _notice_display(node: PlanProjectionNode) -> str:
    warning = node.scan_warning
    if warning is None:
        return _tail_text(node.notice or "", 300)
    display = f"{node.path_origin}: {_tail_text(warning.rel_path or 'root', 120)} — {warning.code.value}"
    if warning.detail:
        display += f" — {_tail_text(warning.detail, 100)}"
    return display


def _tail_text(value: str, maximum_units: int) -> str:
    if len(value.encode("utf-16-le")) // 2 <= maximum_units:
        return value
    units = 1
    tail: list[str] = []
    for character in reversed(value):
        width = 2 if ord(character) > 0xFFFF else 1
        if units + width > maximum_units:
            break
        tail.append(character)
        units += width
    return "…" + "".join(reversed(tail))


def _destination_display(path: str) -> str:
    canonical = path.replace('/', '\\')
    if '\\' not in canonical:
        return _tail_text(canonical, 255)
    return "…\\" + _tail_text(canonical.rsplit('\\', 1)[-1], 253)


__all__ = ["PLAN_FILTERS", "PlanReviewState"]
