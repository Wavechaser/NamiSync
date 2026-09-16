from __future__ import annotations

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
        sort_direction=SortDirection.ASCENDING,
        collapse_node_id=None,
        collapsed=None,
    )
    state.replace_projection(
        _projection(),
        selection_revision=1,
        selection_state="reviewing",
    )

    summary = state.summary()
    assert summary["view_revision"] == 2
    assert summary["selection_revision"] == 1
    assert summary["search_query"] == "alpha"
    assert summary["filters"] == ["delete"]
    assert summary["sort_column"] == "filename"


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

    monkeypatch.setattr(plan_review_module, "sort_plan_projection", fail_sort)
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


def test_plan_review_state_refuses_revision_exhaustion_before_replacement() -> None:
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

    with pytest.raises(OverflowError, match="revision is exhausted"):
        state.replace_projection(
            _projection(),
            selection_revision=1,
            selection_state="reviewing",
        )

    assert state.summary() == before
