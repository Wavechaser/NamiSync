from __future__ import annotations

from dataclasses import replace

import pytest

import namisync.interfaces.web.plan_review as plan_review_module
from namisync.interfaces.web.plan_review import PlanReviewState
from namisync.interfaces.ui_state import MAX_JAVASCRIPT_SAFE_INTEGER
from namisync.workflows import (
    PlanProjection,
    PlanProjectionNode,
    PlanSortColumn,
    SortDirection,
)


def _node(
    node_id: str,
    display: str,
    position: int,
    parent: int | None,
    end: int,
    *,
    container: bool = False,
    operation_id: str | None = None,
    kind: str | None = None,
    size: int | None = None,
) -> PlanProjectionNode:
    return PlanProjectionNode(
        node_id,
        display,
        display.upper(),
        position,
        0 if parent is None else 1 if parent == 0 else 2,
        parent,
        end,
        container,
        "folder" if operation_id is None else "operation",
        operation_id,
        kind,
        None,
        None,
        "disabled" if operation_id is None else "selected",
        0 if operation_id is None else 1,
        0 if operation_id is None else 1,
        0 if operation_id is None else 1,
        size,
        None,
        0,
        "none",
    )


def _projection() -> PlanProjection:
    nodes = (
        _node("root", "Plan", 0, None, 4, container=True),
        _node("folder", "Folder", 1, 0, 3, container=True),
        _node("copy", "beta.txt", 2, 1, 3, operation_id="1" * 32, kind="copy", size=3),
        _node("delete", "alpha.txt", 3, 0, 4, operation_id="2" * 32, kind="delete", size=9),
    )
    return PlanProjection(
        "a" * 32,
        nodes,
        {node.node_id: node.position for node in nodes},
        {"1" * 32: "copy", "2" * 32: "delete"},
        frozenset({"1" * 32, "2" * 32}),
    )


def test_plan_review_state_derives_revisioned_filters_windows_and_anchor() -> None:
    state = PlanReviewState(
        "task-" + "1" * 32,
        "a" * 32,
        _projection(),
        0,
        "reviewing",
        r"C:\source",
        r"D:\target",
    )
    assert state.summary()["visible_row_count"] == 4
    assert state.summary()["preflight_ready"] is True
    assert state.summary()["preflight_refusal_count"] == 0
    assert state.summary()["warning_count"] == 0
    changed = state.update(
        expected_revision=0,
        search_query="beta",
        filters=frozenset({"copy"}),
        sort_column=PlanSortColumn.SIZE,
        sort_direction=SortDirection.DESCENDING,
        collapse_node_id="folder",
        collapsed=True,
    )
    window = state.window(expected_revision=1, offset=0, limit=256)
    anchor = state.anchor(expected_revision=1, node_id="copy")

    assert changed["disposition"] == "applied"
    assert [row["node_id"] for row in window["rows"]] == ["root", "folder"]
    assert anchor == {
        "disposition": "current",
        "view_revision": 1,
        "node_id": "folder",
        "index": 1,
    }
    assert state.window(expected_revision=0, offset=0, limit=1)["disposition"] == "conflict"


def test_plan_review_state_refreshes_selection_without_resetting_view_gestures() -> None:
    state = PlanReviewState(
        "task-" + "1" * 32,
        "a" * 32,
        _projection(),
        0,
        "reviewing",
        "source",
        "target",
    )
    state.update(
        expected_revision=0,
        search_query="alpha",
        filters=frozenset({"delete"}),
        sort_column=PlanSortColumn.FILENAME,
        sort_direction=SortDirection.DESCENDING,
        collapse_node_id="folder",
        collapsed=True,
    )
    state.replace_selection(
        selected_operation_ids=frozenset({"1" * 32}),
        exclusion_reasons={"2" * 32: "user-deselected"},
        selection_revision=1,
        selection_state="reviewing",
        requires_destructive_confirmation=False,
        irreversible_update_count=0,
        destructive_operation_count=0,
        irreversible_operation_count=0,
        destructive_operation_counts={"update": 0, "move_update": 0, "trash": 0, "delete": 0},
        required_bytes="3",
    )

    summary = state.summary()
    assert summary["view_revision"] == 2
    assert summary["selection_revision"] == 1
    assert summary["search_query"] == "alpha"
    assert summary["filters"] == ["delete"]
    assert summary["sort_column"] == "filename"
    assert summary["sort_direction"] == "descending"
    assert summary["collapsed_count"] == 1
    assert summary["selected_operation_count"] == 1
    rows = state.window(expected_revision=2, offset=0, limit=256)["rows"]
    assert [row["node_id"] for row in rows] == ["root", "delete"]
    assert rows[1]["selection"] == "unselected"


def test_plan_review_state_replaces_authoritative_execution_facts() -> None:
    state = PlanReviewState(
        "task-" + "1" * 32,
        "a" * 32,
        _projection(),
        0,
        "reviewing",
        "source",
        "target",
        destructive_operation_count=1,
        irreversible_operation_count=1,
        destructive_operation_counts={
            "update": 0,
            "move_update": 0,
            "trash": 0,
            "delete": 1,
        },
        required_bytes="12",
        requires_destructive_confirmation=True,
    )

    state.replace_selection(
        selected_operation_ids=frozenset({"1" * 32}),
        exclusion_reasons={"2" * 32: "user-deselected"},
        selection_revision=1,
        selection_state="reviewing",
        destructive_operation_count=0,
        irreversible_operation_count=0,
        destructive_operation_counts={
            "update": 0,
            "move_update": 0,
            "trash": 0,
            "delete": 0,
        },
        required_bytes="3",
        requires_destructive_confirmation=False,
        irreversible_update_count=0,
    )

    summary = state.summary()
    assert summary["selection_revision"] == 1
    assert summary["destructive_operation_count"] == 0
    assert summary["irreversible_operation_count"] == 0
    assert summary["destructive_operation_counts"] == {
        "update": 0,
        "move_update": 0,
        "trash": 0,
        "delete": 0,
    }
    assert summary["required_bytes"] == "3"
    assert summary["requires_destructive_confirmation"] is False

    with pytest.raises(ValueError, match="breakdown disagrees"):
        state.replace_selection(
            selected_operation_ids=frozenset({"1" * 32}),
            exclusion_reasons={"2" * 32: "user-deselected"},
            selection_revision=2,
            selection_state="reviewing",
            destructive_operation_count=1,
            irreversible_operation_count=0,
            destructive_operation_counts={
                "update": 0,
                "move_update": 0,
                "trash": 0,
                "delete": 0,
            },
            required_bytes="3",
            requires_destructive_confirmation=True,
            irreversible_update_count=0,
        )
    assert state.summary() == summary


def test_plan_review_state_retains_complete_view_when_update_rebuild_fails(
    monkeypatch,
) -> None:
    state = PlanReviewState(
        "task-" + "1" * 32,
        "a" * 32,
        _projection(),
        0,
        "reviewing",
        "source",
        "target",
    )
    before = state.summary()
    before_window = state.window(expected_revision=0, offset=0, limit=256)

    def fail_sort(*_args, **_kwargs):
        raise RuntimeError("sort failed")

    monkeypatch.setattr(
        plan_review_module, "_sort_plan_projection_from_canonical", fail_sort
    )
    with pytest.raises(RuntimeError, match="sort failed"):
        state.update(
            expected_revision=0,
            search_query="alpha",
            filters=frozenset({"delete"}),
            sort_column=PlanSortColumn.FILENAME,
            sort_direction=SortDirection.DESCENDING,
            collapse_node_id=None,
            collapsed=None,
        )

    assert state.summary() == before
    assert state.window(expected_revision=0, offset=0, limit=256) == before_window


@pytest.mark.parametrize("changes", [
    {"depth": -1}, {"parent_index": 3}, {"subtree_end": 5},
    {"is_container": "yes"}, {"display": 1},
])
def test_plan_review_validates_projection_structure_at_acquisition(changes) -> None:
    projection = _projection()
    malformed = replace(
        projection,
        nodes=(projection.nodes[0], replace(projection.nodes[1], **changes),
               *projection.nodes[2:]),
    )
    with pytest.raises((TypeError, ValueError)):
        PlanReviewState("task-" + "1" * 32, "a" * 32, malformed, 0,
                        "reviewing", "source", "target")


def test_plan_review_uses_the_private_validated_visible_path(monkeypatch) -> None:
    def fail_revalidation(*_args, **_kwargs):
        raise AssertionError("validated projection should not be revalidated")

    monkeypatch.setattr(
        plan_review_module.VisibleSequence,
        "__post_init__",
        fail_revalidation,
    )

    state = PlanReviewState(
        "task-" + "1" * 32,
        "a" * 32,
        _projection(),
        0,
        "reviewing",
        "source",
        "target",
    )

    assert state.summary()["visible_row_count"] == 4


def test_plan_review_passes_filters_as_a_positional_byte_mask(monkeypatch) -> None:
    original = plan_review_module._derive_visible_sequence_from_validated
    calls = []

    def observed(nodes, position_by_id, parameters, **kwargs):
        calls.append((parameters.match_counts_by_node_id, kwargs))
        return original(nodes, position_by_id, parameters, **kwargs)

    monkeypatch.setattr(
        plan_review_module,
        "_derive_visible_sequence_from_validated",
        observed,
    )
    state = PlanReviewState(
        "task-" + "1" * 32,
        "a" * 32,
        _projection(),
        0,
        "reviewing",
        "source",
        "target",
    )
    state.update(
        expected_revision=0,
        search_query="",
        filters=frozenset({"delete"}),
        sort_column=PlanSortColumn.FILENAME,
        sort_direction=SortDirection.DESCENDING,
        collapse_node_id=None,
        collapsed=None,
    )

    assert calls[0][0] is None
    assert calls[0][1]["match_mask_by_position"] is None
    assert tuple(calls[0][1]["ordered_source_positions"]) == (0, 3, 1, 2)
    filtered_counts, filtered_kwargs = calls[1]
    assert filtered_counts is None
    mask = filtered_kwargs["match_mask_by_position"]
    assert type(mask) is bytes
    assert len(mask) == len(state.current_order.projection.nodes)
    assert [
        node.node_id
        for position, node in enumerate(state.current_order.projection.nodes)
        if mask[position]
    ] == ["delete"]
    window = state.window(expected_revision=1, offset=0, limit=256)
    assert [row["node_id"] for row in window["rows"]] == ["root", "delete"]


def test_plan_review_validates_structure_once_then_reuses_it_for_view_changes(
    monkeypatch,
) -> None:
    original = plan_review_module._validate_structure
    calls = 0

    def observed(nodes):
        nonlocal calls
        calls += 1
        return original(nodes)

    monkeypatch.setattr(plan_review_module, "_validate_structure", observed)
    state = PlanReviewState(
        "task-" + "1" * 32,
        "a" * 32,
        _projection(),
        0,
        "reviewing",
        "source",
        "target",
    )
    state.update(
        expected_revision=0,
        search_query="alpha",
        filters=frozenset({"delete"}),
        sort_column=PlanSortColumn.FILENAME,
        sort_direction=SortDirection.ASCENDING,
        collapse_node_id=None,
        collapsed=None,
    )

    assert calls == 1


def test_plan_review_reuses_order_for_search_filter_and_collapse(monkeypatch) -> None:
    state = PlanReviewState("task-" + "1" * 32, "a" * 32, _projection(), 0, "reviewing", "source", "target")
    current = state.current_order

    def fail_sort(*_args, **_kwargs):
        raise AssertionError("view-only changes must reuse the current order")

    monkeypatch.setattr(plan_review_module, "sort_plan_projection", fail_sort)
    state.update(
        expected_revision=0,
        search_query="beta",
        filters=frozenset({"copy"}),
        sort_column=PlanSortColumn.PATH,
        sort_direction=SortDirection.ASCENDING,
        collapse_node_id="folder",
        collapsed=True,
    )

    assert state.current_order is current


def test_plan_review_privately_publishes_sort_from_validated_canonical_order(
    monkeypatch,
) -> None:
    state = PlanReviewState(
        "task-" + "1" * 32,
        "a" * 32,
        _projection(),
        0,
        "reviewing",
        "source",
        "target",
    )
    monkeypatch.setattr(
        plan_review_module.PlanProjectionOrder,
        "__post_init__",
        lambda self: (_ for _ in ()).throw(
            AssertionError("trusted order was publicly revalidated")
        ),
    )

    state.update(
        expected_revision=0,
        search_query="",
        filters=frozenset(),
        sort_column=PlanSortColumn.SIZE,
        sort_direction=SortDirection.DESCENDING,
        collapse_node_id=None,
        collapsed=None,
    )

    assert tuple(state.current_order.ordered_source_positions) == (0, 3, 1, 2)
    assert tuple(state.current_order.order_rank_by_source_position) == (0, 2, 3, 1)


def test_plan_review_selection_rebinds_cached_orders_with_one_projection_clone(monkeypatch) -> None:
    state = PlanReviewState("task-" + "1" * 32, "a" * 32, _projection(), 0, "reviewing", "source", "target")
    original = plan_review_module.apply_plan_projection_selection
    calls = 0

    def observed(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(plan_review_module, "apply_plan_projection_selection", observed)
    monkeypatch.setattr(
        plan_review_module.PlanProjectionOrder,
        "__post_init__",
        lambda self: (_ for _ in ()).throw(AssertionError("selection revalidated order")),
    )
    monkeypatch.setattr(
        plan_review_module.VisibleSequence,
        "__post_init__",
        lambda self: (_ for _ in ()).throw(AssertionError("selection revalidated visibility")),
    )
    state.replace_selection(
        selected_operation_ids=frozenset({"1" * 32}), exclusion_reasons={"2" * 32: "user-deselected"},
        selection_revision=1, selection_state="reviewing", requires_destructive_confirmation=False,
        irreversible_update_count=0, destructive_operation_count=0, irreversible_operation_count=0,
        destructive_operation_counts={"update": 0, "move_update": 0, "trash": 0, "delete": 0}, required_bytes="3",
    )

    assert calls == 1
    assert state.current_order.projection is state.projection
    assert state.canonical_order.projection is state.projection
    assert state.current_sequence.nodes is state.projection.nodes


def test_plan_review_selection_transform_failure_preserves_complete_view(monkeypatch) -> None:
    state = PlanReviewState("task-" + "1" * 32, "a" * 32, _projection(), 0, "reviewing", "source", "target")
    before = state.summary()
    before_window = state.window(expected_revision=0, offset=0, limit=256)

    def fail_selection(*_args, **_kwargs):
        raise RuntimeError("selection transform failed")

    monkeypatch.setattr(plan_review_module, "apply_plan_projection_selection", fail_selection)
    with pytest.raises(RuntimeError, match="selection transform failed"):
        state.replace_selection(
            selected_operation_ids=frozenset({"1" * 32}),
            exclusion_reasons={"2" * 32: "user-deselected"},
            selection_revision=1,
            selection_state="reviewing",
            requires_destructive_confirmation=False,
            irreversible_update_count=0,
            destructive_operation_count=0,
            irreversible_operation_count=0,
            destructive_operation_counts={"update": 0, "move_update": 0, "trash": 0, "delete": 0},
            required_bytes="3",
        )

    assert state.summary() == before
    assert state.window(expected_revision=0, offset=0, limit=256) == before_window


def test_plan_review_fresh_acquisition_has_independent_orders() -> None:
    first = PlanReviewState("task-" + "1" * 32, "a" * 32, _projection(), 0, "reviewing", "source", "target")
    second = PlanReviewState("task-" + "1" * 32, "a" * 32, _projection(), 0, "reviewing", "source", "target")

    assert second.canonical_order is not first.canonical_order
    assert second.current_order is not first.current_order
    assert second.current_sequence is not first.current_sequence
    assert second.current_order.projection is second.projection


def test_plan_review_state_refuses_revision_exhaustion_before_selection() -> None:
    state = PlanReviewState(
        "task-" + "1" * 32,
        "a" * 32,
        _projection(),
        0,
        "reviewing",
        "source",
        "target",
        view_revision=MAX_JAVASCRIPT_SAFE_INTEGER,
    )
    before = state.summary()
    before_window = state.window(expected_revision=MAX_JAVASCRIPT_SAFE_INTEGER, offset=0, limit=256)

    with pytest.raises(OverflowError, match="revision is exhausted"):
        state.replace_selection(
            selected_operation_ids=frozenset({"1" * 32}),
            exclusion_reasons={"2" * 32: "user-deselected"},
            selection_revision=1,
            selection_state="reviewing",
            requires_destructive_confirmation=False,
            irreversible_update_count=0,
            destructive_operation_count=0,
            irreversible_operation_count=0,
            destructive_operation_counts={"update": 0, "move_update": 0, "trash": 0, "delete": 0},
            required_bytes="3",
        )

    assert state.summary() == before
    assert state.window(expected_revision=MAX_JAVASCRIPT_SAFE_INTEGER, offset=0, limit=256) == before_window


def test_plan_review_state_refuses_revision_exhaustion_before_view_or_commit() -> None:
    state = PlanReviewState(
        "task-" + "1" * 32, "a" * 32, _projection(), 0,
        "reviewing", "source", "target",
        view_revision=MAX_JAVASCRIPT_SAFE_INTEGER,
    )
    before = state.summary()
    before_window = state.window(expected_revision=MAX_JAVASCRIPT_SAFE_INTEGER, offset=0, limit=256)

    with pytest.raises(OverflowError, match="revision is exhausted"):
        state.update(
            expected_revision=MAX_JAVASCRIPT_SAFE_INTEGER,
            search_query="alpha",
            filters=frozenset({"delete"}),
            sort_column=PlanSortColumn.FILENAME,
            sort_direction=SortDirection.ASCENDING,
            collapse_node_id="folder",
            collapsed=True,
        )
    assert state.summary() == before
    assert state.window(expected_revision=MAX_JAVASCRIPT_SAFE_INTEGER, offset=0, limit=256) == before_window

    with pytest.raises(OverflowError, match="revision is exhausted"):
        state.mark_selection_committed()
    assert state.summary() == before
    assert state.window(expected_revision=MAX_JAVASCRIPT_SAFE_INTEGER, offset=0, limit=256) == before_window
