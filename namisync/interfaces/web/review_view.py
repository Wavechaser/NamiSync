"""Shared cache transitions and complete-query scope arithmetic for review views."""

from __future__ import annotations

from array import array
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from namisync.interfaces.ui_state import MAX_JAVASCRIPT_SAFE_INTEGER
from namisync.workflows import PlanSortColumn, SortDirection

from .row_highlight import HighlightState
from .visible_sequence import VisibleNodeLike, VisibleSequence


_OrderT = TypeVar("_OrderT")
_NodeT = TypeVar("_NodeT", bound=VisibleNodeLike)


@dataclass(slots=True)
class ScopeCounts:
    selectable: array
    selected: array
    selected_total: int

    @property
    def hidden_selected(self) -> int:
        return self.selected_total - self.selected[-1]

    def subtree(self, position: int, end: int) -> tuple[int, int]:
        return (self.selectable[end] - self.selectable[position],
                self.selected[end] - self.selected[position])


def count_scope(contributions: Iterable[tuple[bool, int, int]]) -> ScopeCounts:
    """Accumulate direct domain contributions, independently of visible windows."""
    selectable, selected = array("Q", [0]), array("Q", [0])
    selected_total = 0
    for matched, available, chosen in contributions:
        selectable.append(selectable[-1] + (available if matched else 0))
        selected.append(selected[-1] + (chosen if matched else 0))
        selected_total += chosen
    return ScopeCounts(selectable, selected, selected_total)


def covered_positions(count: int, ranges: Iterable[tuple[int, int]]) -> Iterator[int]:
    """Visit overlapping highlighted subtrees once in projection order."""
    deltas = [0] * (count + 1)
    for start, end in ranges:
        deltas[start] += 1
        deltas[end] -= 1
    covered = 0
    for position in range(count):
        covered += deltas[position]
        if covered:
            yield position


@dataclass(slots=True)
class ReviewView(Generic[_OrderT, _NodeT]):
    order: _OrderT
    visible: VisibleSequence[_NodeT]
    scope: ScopeCounts


class ReviewOwner(HighlightState, Protocol[_OrderT, _NodeT]):
    view_revision: int
    search_query: str
    filters: frozenset[str]
    sort_column: PlanSortColumn
    sort_direction: SortDirection
    collapsed_node_ids: frozenset[str]
    _view: ReviewView[_OrderT, _NodeT]

    def _sort(self, column: PlanSortColumn, direction: SortDirection) -> _OrderT: ...
    def _derive(self, order: _OrderT, search: str, filters: frozenset[str],
                collapsed: frozenset[str]) -> VisibleSequence[_NodeT]: ...
    def _scope(self, search: str, filters: frozenset[str]) -> ScopeCounts: ...


def next_revision(current: int) -> int:
    if current >= MAX_JAVASCRIPT_SAFE_INTEGER:
        raise OverflowError("view revision is exhausted")
    return current + 1


def update_review_view(
    owner: ReviewOwner[_OrderT, _NodeT], *, search_query: str, filters: frozenset[str],
    sort_column: PlanSortColumn, sort_direction: SortDirection,
    collapsed_node_ids: frozenset[str], visible: VisibleSequence[_NodeT] | None = None,
) -> str:
    """Stage one admitted domain view change completely before publishing it."""
    state = (search_query, filters, sort_column, sort_direction, collapsed_node_ids)
    if state == (owner.search_query, owner.filters, owner.sort_column,
                 owner.sort_direction, owner.collapsed_node_ids):
        return "noop"
    revision = next_revision(owner.view_revision)
    query_changed = (search_query, filters) != (owner.search_query, owner.filters)
    clear_highlight = query_changed and bool(
        owner.highlighted_node_ids or owner.highlight_anchor_node_id is not None
        or owner.highlight_focus_node_id is not None)
    highlight_revision = (next_revision(owner.highlight_revision) if clear_highlight
                          else owner.highlight_revision)
    order = (owner._view.order if (sort_column, sort_direction) ==
             (owner.sort_column, owner.sort_direction) else owner._sort(sort_column, sort_direction))
    if visible is None:
        visible = owner._derive(order, search_query, filters, collapsed_node_ids)
    scope = owner._scope(search_query, filters) if query_changed else owner._view.scope
    view = ReviewView(order, visible, scope)
    owner.search_query, owner.filters, owner.sort_column, owner.sort_direction, owner.collapsed_node_ids = state
    owner._view = view
    owner.view_revision = revision
    if clear_highlight:
        owner.highlighted_node_ids = frozenset()
        owner.highlight_anchor_node_id = owner.highlight_focus_node_id = None
        owner.highlight_revision = highlight_revision
    return "applied"
