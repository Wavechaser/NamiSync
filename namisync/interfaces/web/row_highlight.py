"""Shared presentation-only row highlighting over a server-owned visible tree."""

from __future__ import annotations

from typing import Protocol

from namisync.interfaces.ui_state import MAX_JAVASCRIPT_SAFE_INTEGER

from .visible_sequence import VisibleSequence


class HighlightState(Protocol):
    highlight_revision: int
    highlighted_node_ids: frozenset[str]
    highlight_anchor_node_id: str | None
    highlight_focus_node_id: str | None


def highlight_visible_index(sequence: VisibleSequence, node_id: str | None) -> int | None:
    if node_id is None:
        return None
    position = sequence.source_position_by_node_id.get(node_id)
    if position is None:
        return None
    index = sequence.visible_index_by_source_position[position]
    return index - 1 if 0 < index < len(sequence.nodes) else None


def apply_row_highlight(
    state: HighlightState, sequence: VisibleSequence, gesture: str, node_id: str | None,
) -> str:
    """Apply one admitted gesture; the caller owns lifecycle and revision admission."""
    if gesture not in {
        "clear", "replace", "toggle", "extend", "add-range",
        "move_up", "move_down", "move_up_extend", "move_down_extend",
    }:
        raise ValueError("highlight gesture is unknown")
    if gesture == "clear":
        highlighted = frozenset()
        anchor = focus = None
    else:
        if gesture.startswith("move_"):
            current = state.highlight_focus_node_id
            count = len(sequence.visible_source_positions) - 1
            if current is None:
                next_index = 0 if gesture.startswith("move_down") else count - 1
            else:
                current_index = highlight_visible_index(sequence, current)
                if current_index is None:
                    return "noop"
                next_index = current_index + (1 if gesture.startswith("move_down") else -1)
            if not 0 <= next_index < count:
                return "noop"
            node_id = sequence.nodes[sequence.visible_source_positions[next_index + 1]].node_id
            gesture = "extend" if current is not None and gesture.endswith("_extend") else "replace"
        if node_id is None or highlight_visible_index(sequence, node_id) is None:
            raise ValueError("highlight node must be a visible row")
        if gesture == "replace":
            highlighted = frozenset((node_id,))
            anchor = focus = node_id
        elif gesture == "toggle":
            highlighted = (state.highlighted_node_ids - {node_id} if node_id in state.highlighted_node_ids
                           else state.highlighted_node_ids | {node_id})
            anchor = state.highlight_anchor_node_id or node_id
            focus = node_id
        else:
            anchor = state.highlight_anchor_node_id
            anchor_index = highlight_visible_index(sequence, anchor)
            focus_index = highlight_visible_index(sequence, node_id)
            if anchor_index is None or focus_index is None:
                return "noop"
            start, end = sorted((anchor_index, focus_index))
            selected_range = frozenset(
                sequence.nodes[sequence.visible_source_positions[index + 1]].node_id
                for index in range(start, end + 1)
            )
            highlighted = selected_range if gesture == "extend" else state.highlighted_node_ids | selected_range
            focus = node_id
    if (highlighted, anchor, focus) == (
        state.highlighted_node_ids, state.highlight_anchor_node_id, state.highlight_focus_node_id,
    ):
        return "noop"
    if state.highlight_revision >= MAX_JAVASCRIPT_SAFE_INTEGER:
        raise OverflowError("highlight revision is exhausted")
    state.highlighted_node_ids = frozenset(highlighted)
    state.highlight_anchor_node_id, state.highlight_focus_node_id = anchor, focus
    state.highlight_revision += 1
    return "applied"
