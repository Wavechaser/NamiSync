"""One cached, revisioned view of a complete immutable inventory projection."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from namisync.workflows import (
    RecallSummary, InventoryDetails, InventoryProjection, InventoryProjectionNode, InventoryProjectionOrder, InventoryRollup,
    PlanSortColumn, SortDirection,
    sort_inventory_projection,
)
from .visible_sequence import (
    VisibleSequence, VisibleSequenceParameters, _derive_visible_sequence_from_validated,
    window_visible_sequence, resolve_visible_node_anchor,
)
from .plan_review import _tail_text
from .recall import recall_summary_wire
from .row_highlight import apply_row_highlight, highlight_visible_index
from .review_view import (
    ReviewView, ScopeCounts, count_scope, covered_positions, next_revision, update_review_view,
)


INVENTORY_FILTERS = frozenset({
    "present", "unverified", "verified", "modified", "reappeared",
    "unsupported", "missing", "mismatched", "acknowledged", "notice", "recall",
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
    if node.recall:
        categories.add("recall")
    return frozenset(categories)


@dataclass(slots=True)
class InventoryReviewState:
    task_id: str
    request_id: str
    projection: InventoryProjection
    root_path: str | None
    scan_complete: bool | None
    observed_count: int | None
    missing_count: int | None
    scan_scope: tuple[str, str | None] | None = field(default=("location", None), kw_only=True)
    scan_request_id: str | None = field(default=None, kw_only=True)
    recall: RecallSummary | None = field(default=None, kw_only=True)
    selected_row_ids: frozenset[str] = field(default_factory=frozenset, kw_only=True)
    highlight_revision: int = field(default=0, kw_only=True)
    highlighted_node_ids: frozenset[str] = field(default_factory=frozenset, kw_only=True)
    highlight_anchor_node_id: str | None = field(default=None, kw_only=True)
    highlight_focus_node_id: str | None = field(default=None, kw_only=True)
    view_revision: int = 0
    search_query: str = ""
    filters: frozenset[str] = field(default_factory=frozenset)
    sort_column: PlanSortColumn = PlanSortColumn.PATH
    sort_direction: SortDirection = SortDirection.ASCENDING
    collapsed_node_ids: frozenset[str] = field(default_factory=frozenset)
    _view: ReviewView[InventoryProjectionOrder, InventoryProjectionNode] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if (self.scan_request_id is None) != (self.recall is None):
            raise ValueError("inventory scan identity and recall summary must agree")
        order = self._sort(self.sort_column, self.sort_direction)
        self._view = ReviewView(
            order, self._derive(order, self.search_query, self.filters, self.collapsed_node_ids),
            self._scope(self.search_query, self.filters),
        )

    def _sort(self, column: PlanSortColumn, direction: SortDirection) -> InventoryProjectionOrder:
        return sort_inventory_projection(self.projection, column, direction)

    def _scope(self, search: str, filters: frozenset[str], *,
               selected_row_ids: frozenset[str] | None = None) -> ScopeCounts:
        selected = self.selected_row_ids if selected_row_ids is None else selected_row_ids
        query = search.casefold()

        def contributions():
            for node in self.projection.nodes:
                file = (node.row is not None and node.row.entry_kind is not None
                        and node.row.entry_kind.value == "file")
                yield (file and self._matches(node, query, filters), int(file),
                       int(file and node.row.row_id in selected))
        return count_scope(contributions())

    def _matches(self, node: InventoryProjectionNode, query: str,
                 filters: frozenset[str] | None = None) -> bool:
        filters = self.filters if filters is None else filters
        categories = _categories(node)
        return (("acknowledged" not in categories or "acknowledged" in filters)
                and (bool(categories & filters) if filters else bool(categories))
                and query in node.display.casefold())

    def _selection(self, node: InventoryProjectionNode) -> dict[str, object]:
        count, selected = self._view.scope.subtree(node.position, node.subtree_end)
        return {"selectable": count > 0,
                "selection": "none" if selected == 0 else "all" if selected == count else "partial"}

    def set_selection(self, *, request_id: str, expected_revision: int,
                      node_id: str | None, selected: bool) -> dict[str, object]:
        if request_id != self.request_id or expected_revision != self.view_revision:
            return self.summary(disposition="conflict")
        if type(selected) is not bool:
            raise TypeError("inventory selection must be a boolean")
        node = self.projection.nodes[0] if node_id is None else self.projection.node_for_id(node_id)
        if node.warning is not None:
            raise ValueError("inventory warnings cannot be selected")
        query = self.search_query.casefold()
        scope = frozenset(
            item.row.row_id for item in self.projection.nodes[node.position:node.subtree_end]
            if item.row is not None and item.row.entry_kind is not None
            and item.row.entry_kind.value == "file"
            and self._matches(item, query)
        )
        return self._assign_selection(scope, selected)

    def _assign_selection(self, scope: frozenset[str], selected: bool) -> dict[str, object]:
        result = self.selected_row_ids | scope if selected else self.selected_row_ids - scope
        if result == self.selected_row_ids:
            return self.summary(disposition="noop")
        revision = next_revision(self.view_revision)
        scope_counts = self._scope(self.search_query, self.filters, selected_row_ids=result)
        view = ReviewView(self._view.order, self._view.visible, scope_counts)
        self.selected_row_ids = result
        self._view = view
        self.view_revision = revision
        return self.summary()

    def mutate_highlight(self, *, expected_view_revision: int, expected_highlight_revision: int,
                         gesture: str, node_id: str | None) -> dict[str, object]:
        if expected_view_revision != self.view_revision or expected_highlight_revision != self.highlight_revision:
            return self.summary(disposition="conflict")
        disposition = apply_row_highlight(self, self._view.visible, gesture, node_id)
        return self.summary(disposition="current" if disposition == "applied" else disposition)

    def set_highlighted_selection(self, *, request_id: str, expected_revision: int,
                                  expected_highlight_revision: int, selected: bool) -> dict[str, object]:
        if (request_id != self.request_id or expected_revision != self.view_revision
                or expected_highlight_revision != self.highlight_revision):
            return self.summary(disposition="conflict")
        if type(selected) is not bool:
            raise TypeError("inventory selection must be a boolean")
        nodes = self.projection.nodes
        recursive = len(self.highlighted_node_ids) == 1
        ranges = ((node.position, node.subtree_end if recursive else node.position + 1) for node in (
            self.projection.node_for_id(node_id) for node_id in self.highlighted_node_ids))
        scope = frozenset(nodes[position].row.row_id
            for position in covered_positions(len(nodes), ranges)
            if self._view.scope.selectable[position + 1] > self._view.scope.selectable[position])
        return self._assign_selection(scope, selected)

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
            "highlight_revision": self.highlight_revision,
            "highlight_anchor_node_id": self.highlight_anchor_node_id,
            "highlight_focus_node_id": self.highlight_focus_node_id,
            "highlight_focus_visible_index": highlight_visible_index(self._view.visible, self.highlight_focus_node_id),
            "highlighted_count": len(self.highlighted_node_ids),
            "scan_request_id": self.scan_request_id,
            "recall": None if self.recall is None else recall_summary_wire(self.recall),
            "recall_item_count": self.projection.recall_item_count,
            "scan_complete": self.scan_complete, "observed_count": self.observed_count,
            "scan_scope": None if self.scan_scope is None else {"kind": self.scan_scope[0], "path": self.scan_scope[1]},
            "missing_count": self.missing_count, "warning_count": self.projection.warning_count,
            "rollup": inventory_rollup_wire(self.projection.nodes[0].rollup),
            "visible_row_count": max(0, len(self._view.visible.visible_positions) - 1),
            "search_query": self.search_query, "filters": sorted(self.filters),
            "sort_column": self.sort_column.value, "sort_direction": self.sort_direction.value,
            "collapsed_count": len(self.collapsed_node_ids),
            "selected_file_count": self._view.scope.selected_total,
            "selectable_file_count": self.projection.nodes[0].rollup.file_count,
            "hidden_selected_file_count": self._view.scope.hidden_selected,
            "scope_selectable_file_count": self._view.scope.selectable[-1],
            "scope_selected_file_count": self._view.scope.selected[-1],
            "selection": self._selection(self.projection.nodes[0])["selection"],
        }

    def replacement(self, request_id: str, projection: InventoryProjection,
                    root_path: str | None, scan_complete: bool | None,
                    observed_count: int | None, missing_count: int | None, *,
                    scan_scope: tuple[str, str | None] | None,
                    scan_request_id: str | None = None,
                    recall: RecallSummary | None = None) -> InventoryReviewState:
        """Stage one complete replacement while preserving surviving gestures."""
        revision = next_revision(self.view_revision)
        collapsed = frozenset(
            node_id for node_id in self.collapsed_node_ids
            if node_id in projection.position_by_node_id
            and projection.node_for_id(node_id).is_container
        )
        retained = (projection.position_by_node_id
                    if projection.location_id == self.projection.location_id else {})
        return InventoryReviewState(
            self.task_id, request_id, projection, root_path, scan_complete,
            observed_count, missing_count, revision,
            self.search_query, self.filters, self.sort_column, self.sort_direction, collapsed,
            scan_scope=scan_scope,
            scan_request_id=scan_request_id,
            recall=recall,
            highlight_revision=next_revision(self.highlight_revision),
            highlighted_node_ids=self.highlighted_node_ids.intersection(retained),
            highlight_anchor_node_id=(self.highlight_anchor_node_id
                if self.highlight_anchor_node_id in retained else None),
            highlight_focus_node_id=(self.highlight_focus_node_id
                if self.highlight_focus_node_id in retained else None),
            selected_row_ids=frozenset(
                row_id for row_id in self.selected_row_ids
                if row_id in projection.node_id_by_row_id
                and projection.row_for_id(row_id).entry_kind is not None
                and projection.row_for_id(row_id).entry_kind.value == "file"),
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
        disposition = update_review_view(self, search_query=search_query, filters=filters,
            sort_column=sort_column, sort_direction=sort_direction,
            collapsed_node_ids=next_collapsed)
        return self.summary(disposition="current" if disposition == "applied" else disposition)

    def row_anchor(self, *, expected_revision: int, row_id: str) -> dict[str, object]:
        result = {"disposition": "current", "view_revision": self.view_revision,
                  "node_id": None, "index": None}
        if expected_revision != self.view_revision:
            return {**result, "disposition": "conflict"}
        node_id = self.projection.node_id_by_row_id.get(row_id)
        if node_id is not None:
            anchor = resolve_visible_node_anchor(self._view.visible, node_id)
            if anchor is not None and anchor.index > 0:
                result.update(node_id=anchor.node_id, index=anchor.index - 1)
        return result

    def window(self, *, expected_revision: int, offset: int, limit: int,
               anchor_node_id: str | None = None) -> dict[str, object]:
        anchor = {} if anchor_node_id is None else {
            "anchor_node_id": anchor_node_id,
            "anchor_visible_index": None if expected_revision != self.view_revision
                else highlight_visible_index(self._view.visible, anchor_node_id),
        }
        if expected_revision != self.view_revision:
            return {"disposition": "conflict", "view_revision": self.view_revision,
                    "highlight_revision": self.highlight_revision,
                    "offset": offset, "total": 0, "rows": [], **anchor}
        window = window_visible_sequence(self._view.visible, offset=offset + 1, limit=limit)
        rows = []
        for frame in window.rows:
            node, row = frame.node, frame.node.row
            rows.append({
                "node_id": node.node_id, "display": (
                    f"{node.warning.code.value}: {_tail_text(node.warning.rel_path or 'root', 255)}"
                    if node.warning is not None
                    else _tail_text(node.rel_path.replace('/', '\\').rsplit('\\', 1)[-1], 300)
                ),
                "depth": node.depth - 1, "is_container": node.is_container,
                "visible_index": frame.visible_index - 1,
                "parent_visible_index": None if frame.parent_visible_index in (None, 0) else frame.parent_visible_index - 1,
                "first_child_visible_index": None if frame.first_child_visible_index is None else frame.first_child_visible_index - 1,
                "position_in_set": frame.position_in_set, "set_size": frame.set_size,
                "expanded": frame.expanded, "row_kind": node.row_kind,
                **self._selection(node),
                "highlighted": node.node_id in self.highlighted_node_ids,
                "row_id": None if row is None else row.row_id,
                "presence": None if row is None else row.presence.value,
                "verification_state": None if row is None else row.verification_state.value,
                "has_baseline": row is not None and row.attestation is not None,
                "recorded_checksum": None if row is None or row.attestation is None else row.attestation.content.digest.hex(),
                "acknowledged": row is not None and row.acknowledged_at is not None,
                "recall": node.recall,
                "reappeared": row is not None and row.reappeared_at is not None,
                "size": None if node.size is None else str(node.size),
                "mtime_ns": None if node.mtime_ns is None else str(node.mtime_ns),
                "rollup": inventory_rollup_wire(node.rollup),
                "warning": None if node.warning is None else {
                    "code": node.warning.code.value,
                    "detail": _tail_text(node.warning.detail, 300),
                },
            })
        return {"disposition": "current", "view_revision": self.view_revision,
                "highlight_revision": self.highlight_revision,
                "offset": offset, "total": max(0, window.total - 1), "rows": rows, **anchor}
