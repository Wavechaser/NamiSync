from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

import namisync.workflows.plan_projection as projection_module
from namisync.core.models import EntryKind, ScanWarning, ScanWarningCode
from namisync.core.planning import OperationKind
from namisync.core.preflight import Refusal, RefusalCode, Verdict
from namisync.workflows.models import PlanArtifact, PlanRequest
from namisync.workflows.plan_projection import (
    PlanSortColumn,
    SortDirection,
    apply_plan_projection_selection,
    build_plan_projection,
    sort_plan_projection,
)
from namisync.workflows.selection import derive_execution_selection

from _db_fixtures import file_stat, operation, plan


REQUEST_ID = "1" * 32


def _ordered_nodes(order):
    return tuple(order.projection.nodes[position] for position in order.ordered_source_positions)


def _artifact(*operations, warnings=(), refusals=()) -> PlanArtifact:
    plan_value = plan(tuple(operations))
    request = PlanRequest(
        REQUEST_ID,
        plan_value.source_root.path,
        plan_value.target_root.path,
    )
    return PlanArtifact(
        request,
        SimpleNamespace(warnings=tuple(warnings)),
        SimpleNamespace(warnings=()),
        plan_value,
        Verdict(not refusals, tuple(refusals), SimpleNamespace()),
    )


def test_plan_projection_preserves_groups_selection_and_move_old_path_ancestry() -> None:
    copied = operation(
        OperationKind.COPY,
        source_path=r"source\one.txt",
        target_path=r"target\same.txt",
        source=file_stat(size=13, mtime_ns=31),
    )
    updated = operation(
        OperationKind.UPDATE,
        source_path=r"source\two.txt",
        target_path=r"target\same.txt",
        source=file_stat(size=17, mtime_ns=41, identity_index=2),
    )
    moved = operation(
        OperationKind.MOVE,
        source_path=r"source\new.txt",
        target_path=r"new\deep\name.txt",
        prior_target_path=r"old\deep\name.txt",
        target=file_stat(size=19, mtime_ns=51, identity_index=3),
    )
    projection = build_plan_projection(
        REQUEST_ID,
        _artifact(copied, updated, moved),
        user_deselected=frozenset({updated.op_id}),
    )

    group = next(node for node in projection.nodes if node.row_kind == "operation-group")
    assert group.is_container is True
    assert group.selection == "mixed"
    assert group.operation_count == 2
    assert group.selectable_operation_count == 2
    assert group.selected_operation_count == 1
    moved_node = projection.node_for_id(
        projection.operation_node_id_by_id[str(moved.op_id)]
    )
    assert moved_node.move_peer_id is not None
    prior = projection.node_for_id(moved_node.move_peer_id)
    assert prior.row_kind == "prior-operation"
    assert prior.selection == "disabled"
    assert prior.move_peer_id == moved_node.node_id
    assert any(
        node.row_kind == "prior-folder" and node.display == "old"
        for node in projection.nodes
    )


def test_plan_projection_reuses_exact_workflow_selection_membership() -> None:
    copied = operation(
        OperationKind.COPY,
        source_path="source.txt",
        target_path="target.txt",
        source=file_stat(identity_index=101),
    )
    artifact = _artifact(copied)
    user_deselected = frozenset()
    decision = derive_execution_selection(
        artifact.plan,
        user_deselected=user_deselected,
    )

    projection = build_plan_projection(
        REQUEST_ID,
        artifact,
        user_deselected=user_deselected,
        selection_decision=decision,
    )

    assert projection.selected_operation_ids is decision.selection

    equal_but_distinct_intent = frozenset({copied.op_id}) - {copied.op_id}
    assert equal_but_distinct_intent == user_deselected
    assert equal_but_distinct_intent is not user_deselected
    with pytest.raises(ValueError, match="different user intent"):
        build_plan_projection(
            REQUEST_ID,
            artifact,
            user_deselected=equal_but_distinct_intent,
            selection_decision=decision,
        )


def test_move_peers_are_assigned_before_node_materialization(monkeypatch) -> None:
    moved = operation(
        OperationKind.MOVE,
        source_path=r"source\new.txt",
        target_path=r"new\name.txt",
        prior_target_path=r"old\name.txt",
        target=file_stat(identity_index=12),
    )
    replacements = 0
    original = projection_module.replace

    def observed(value, **changes):
        nonlocal replacements
        replacements += 1
        return original(value, **changes)

    monkeypatch.setattr(projection_module, "replace", observed)

    projection = build_plan_projection(REQUEST_ID, _artifact(moved))
    moved_node = projection.node_for_id(
        projection.operation_node_id_by_id[str(moved.op_id)]
    )

    assert replacements == 0
    assert moved_node.move_peer_id is not None
    assert (
        projection.node_for_id(moved_node.move_peer_id).move_peer_id
        == moved_node.node_id
    )


def test_plan_projection_keeps_notices_and_raw_sort_facts_distinct() -> None:
    directory_stat = replace(
        file_stat(size=0, mtime_ns=80),
        kind=EntryKind.DIRECTORY,
    )
    directory = operation(
        OperationKind.MKDIR,
        source_path="folder",
        target_path="folder",
        intended=directory_stat,
    )
    small = operation(
        OperationKind.COPY,
        source_path="small.txt",
        target_path="small.txt",
        source=file_stat(size=3, mtime_ns=30, identity_index=2),
    )
    large = operation(
        OperationKind.COPY,
        source_path="large.txt",
        target_path="large.txt",
        source=file_stat(size=9, mtime_ns=20, identity_index=3),
    )
    warning = ScanWarning(
        ScanWarningCode.ACCESS_DENIED,
        "private",
        "scan detail",
    )
    refusal = Refusal(RefusalCode.SOURCE_DRIFT, detail="review changed")
    projection = build_plan_projection(
        REQUEST_ID,
        _artifact(
            directory,
            small,
            large,
            warnings=(warning,),
            refusals=(refusal,),
        ),
    )

    folder = projection.node_for_id(
        projection.operation_node_id_by_id[str(directory.op_id)]
    )
    notice = next(node for node in projection.nodes if node.row_kind == "notice")
    assert folder.size is None
    assert folder.mtime_ns == 80
    assert notice.size is None and notice.mtime_ns is None
    assert projection.preflight_ready is False
    assert projection.preflight_refusal_count == 1
    assert projection.warning_count == 1
    assert {node.notice for node in projection.nodes if node.notice is not None} == {
        "source: private — access_denied — scan detail",
        "plan: source_drift — review changed",
    }
    ascending = sort_plan_projection(
        projection,
        PlanSortColumn.SIZE,
        SortDirection.ASCENDING,
    )
    descending = sort_plan_projection(
        projection,
        PlanSortColumn.SIZE,
        SortDirection.DESCENDING,
    )
    ascending_root = [node.display for node in _ordered_nodes(ascending) if node.parent_index == 0]
    descending_root = [node.display for node in _ordered_nodes(descending) if node.parent_index == 0]
    assert ascending_root[:2] == ["small.txt", "large.txt"]
    assert descending_root[:2] == ["large.txt", "small.txt"]
    unavailable = {
        "folder",
        "source: private — access_denied — scan detail",
        "plan: source_drift — review changed",
    }
    assert set(ascending_root[2:]) == unavailable
    assert set(descending_root[2:]) == unavailable
    assert all(
        node.subtree_end > node.position
        and (node.parent_index is None or node.parent_index < node.position)
        for node in _ordered_nodes(descending)
    )


def test_plan_projection_separates_safety_eligibility_from_current_selection() -> None:
    dependency = operation(
        OperationKind.COPY,
        source_path="dependency.txt",
        target_path="dependency.txt",
        source=file_stat(identity_index=4),
    )
    dependent = replace(
        operation(
            OperationKind.MOVE_UPDATE,
            source_path="dependent.txt",
            target_path="dependent.txt",
            prior_target_path="old-dependent.txt",
            source=file_stat(identity_index=5),
        ),
        dependencies=frozenset({dependency.op_id}),
    )
    projection = build_plan_projection(
        REQUEST_ID,
        _artifact(dependency, dependent),
        user_deselected=frozenset({dependency.op_id}),
    )

    dependency_node = projection.node_for_id(
        projection.operation_node_id_by_id[str(dependency.op_id)]
    )
    dependent_node = projection.node_for_id(
        projection.operation_node_id_by_id[str(dependent.op_id)]
    )
    assert dependency_node.selection == "unselected"
    assert dependency_node.selection_exclusion_reason == "user-deselected"
    assert dependent_node.selection == "unselected"
    assert dependent_node.selectable_operation_count == 1
    assert dependent_node.selection_exclusion_reason == "blocked-dependency"
    assert dependent_node.risk == "reversible"

    selected = frozenset({str(dependency.op_id), str(dependent.op_id)})
    updated = apply_plan_projection_selection(
        projection,
        selected_operation_ids=selected,
        exclusion_reasons={},
    )
    assert updated.nodes[0].selected_operation_count == 2
    assert all(
        updated.node_for_id(updated.operation_node_id_by_id[item]).selection
        == "selected"
        for item in selected
    )


def test_filename_sort_uses_raw_basename_casefold_before_path_normalization() -> None:
    dotless_i = operation(
        OperationKind.COPY,
        source_path="ı.txt",
        target_path="ı.txt",
        source=file_stat(identity_index=6),
    )
    latin_j = operation(
        OperationKind.COPY,
        source_path="j.txt",
        target_path="j.txt",
        source=file_stat(identity_index=7),
    )
    projection = build_plan_projection(
        REQUEST_ID,
        _artifact(dotless_i, latin_j),
    )

    dotless_node = projection.node_for_id(
        projection.operation_node_id_by_id[str(dotless_i.op_id)]
    )
    assert dotless_node.filename_key == "ı.txt".casefold()
    ordered = sort_plan_projection(
        projection,
        PlanSortColumn.FILENAME,
        SortDirection.ASCENDING,
    )
    assert [node.display for node in _ordered_nodes(ordered) if node.parent_index == 0] == [
        "j.txt",
        "ı.txt",
    ]


def test_canonical_sort_reuses_source_nodes_and_returns_inverse_ranks() -> None:
    first = operation(
        OperationKind.COPY,
        source_path="alpha.txt",
        target_path="alpha.txt",
        source=file_stat(identity_index=8),
    )
    second = operation(
        OperationKind.COPY,
        source_path="beta.txt",
        target_path="beta.txt",
        source=file_stat(identity_index=9),
    )
    projection = build_plan_projection(REQUEST_ID, _artifact(first, second))

    canonical = sort_plan_projection(projection, PlanSortColumn.PATH, SortDirection.ASCENDING)
    assert canonical.projection is projection
    assert tuple(canonical.ordered_source_positions) == tuple(range(len(projection.nodes)))
    reversed_projection = sort_plan_projection(
        projection,
        PlanSortColumn.FILENAME,
        SortDirection.DESCENDING,
    )
    restored = sort_plan_projection(
        projection,
        PlanSortColumn.PATH,
        SortDirection.ASCENDING,
    )
    assert restored.projection.nodes is projection.nodes
    assert [node.display for node in _ordered_nodes(restored) if node.parent_index == 0] == [
        "alpha.txt",
        "beta.txt",
    ]


def test_real_sort_clones_no_source_nodes(monkeypatch) -> None:
    first = operation(
        OperationKind.COPY,
        source_path="alpha.txt",
        target_path="alpha.txt",
        source=file_stat(size=1, identity_index=10),
    )
    second = operation(
        OperationKind.COPY,
        source_path="beta.txt",
        target_path="beta.txt",
        source=file_stat(size=2, identity_index=11),
    )
    projection = build_plan_projection(REQUEST_ID, _artifact(first, second))
    original = projection_module.replace
    calls = 0

    def observed(value, **changes):
        nonlocal calls
        calls += 1
        return original(value, **changes)

    monkeypatch.setattr(projection_module, "replace", observed)

    ordered = sort_plan_projection(
        projection,
        PlanSortColumn.SIZE,
        SortDirection.DESCENDING,
    )

    assert calls == 0
    assert ordered.projection.nodes is projection.nodes
    assert [node.display for node in _ordered_nodes(ordered) if node.parent_index == 0] == [
        "beta.txt",
        "alpha.txt",
    ]


def test_canonical_order_does_not_assume_source_preorder_is_lexical() -> None:
    first = operation(OperationKind.COPY, source_path="alpha.txt", target_path="alpha.txt", source=file_stat(identity_index=12))
    second = operation(OperationKind.COPY, source_path="beta.txt", target_path="beta.txt", source=file_stat(identity_index=13))
    projection = build_plan_projection(REQUEST_ID, _artifact(first, second))
    nonlexical = replace(
        projection,
        nodes=(projection.nodes[0], replace(projection.nodes[1], rel_path_key="Z"), replace(projection.nodes[2], rel_path_key="A")),
    )

    order = sort_plan_projection(nonlexical, PlanSortColumn.PATH, SortDirection.ASCENDING)

    assert tuple(order.ordered_source_positions) == (0, 2, 1)
    assert tuple(order.order_rank_by_source_position) == (0, 2, 1)
    assert order.projection.nodes is nonlexical.nodes
    with pytest.raises(TypeError):
        order.ordered_source_positions[0] = 2  # type: ignore[index]


def test_canonical_order_breaks_equal_path_keys_by_node_id() -> None:
    first = operation(OperationKind.COPY, source_path="alpha.txt", target_path="alpha.txt", source=file_stat(identity_index=40))
    second = operation(OperationKind.COPY, source_path="beta.txt", target_path="beta.txt", source=file_stat(identity_index=41))
    projection = build_plan_projection(REQUEST_ID, _artifact(first, second))
    tied = replace(
        projection,
        nodes=(projection.nodes[0], replace(projection.nodes[1], rel_path_key="same", node_id="node-z"), replace(projection.nodes[2], rel_path_key="same", node_id="node-a")),
        position_by_node_id={projection.nodes[0].node_id: 0, "node-z": 1, "node-a": 2},
    )

    order = sort_plan_projection(tied, PlanSortColumn.PATH, SortDirection.ASCENDING)

    assert tuple(order.ordered_source_positions) == (0, 2, 1)
    assert tuple(order.order_rank_by_source_position) == (0, 2, 1)


@pytest.mark.parametrize("count", [0, 1])
def test_canonical_order_handles_empty_and_single_child(count: int) -> None:
    operations = () if count == 0 else (
        operation(OperationKind.COPY, source_path="only.txt", target_path="only.txt", source=file_stat(identity_index=42)),
    )
    projection = build_plan_projection(REQUEST_ID, _artifact(*operations))

    order = sort_plan_projection(projection, PlanSortColumn.PATH, SortDirection.ASCENDING)

    assert tuple(order.ordered_source_positions) == tuple(range(len(projection.nodes)))
    assert tuple(order.order_rank_by_source_position) == tuple(range(len(projection.nodes)))


def test_sort_refuses_invalid_source_tree_before_publishing_order() -> None:
    first = operation(OperationKind.COPY, source_path="alpha.txt", target_path="alpha.txt", source=file_stat(identity_index=14))
    projection = build_plan_projection(REQUEST_ID, _artifact(first))
    malformed = replace(
        projection,
        nodes=(replace(projection.nodes[0], is_container=False), projection.nodes[1]),
    )

    with pytest.raises(ValueError, match="leaf spans descendants"):
        sort_plan_projection(malformed, PlanSortColumn.PATH, SortDirection.ASCENDING)

    broken_parent = replace(
        projection,
        nodes=(projection.nodes[0], replace(projection.nodes[1], parent_index=99)),
    )
    with pytest.raises(ValueError, match="parent/subtree closure"):
        sort_plan_projection(broken_parent, PlanSortColumn.SIZE, SortDirection.DESCENDING)

    with pytest.raises(ValueError, match="permutation"):
        projection_module.PlanProjectionOrder(
            projection,
            projection_module.CompactUnsignedIntegers((0, 0), maximum=1),
            projection_module.CompactUnsignedIntegers((0, 1), maximum=1),
        )


@pytest.mark.parametrize(
    ("column", "direction", "expected"),
    [
        (PlanSortColumn.FILENAME, SortDirection.ASCENDING, (0, 1, 2, 3, 4)),
        (PlanSortColumn.FILENAME, SortDirection.DESCENDING, (0, 3, 2, 1, 4)),
        (PlanSortColumn.SIZE, SortDirection.ASCENDING, (0, 1, 2, 3, 4)),
        (PlanSortColumn.SIZE, SortDirection.DESCENDING, (0, 2, 3, 1, 4)),
        (PlanSortColumn.MTIME, SortDirection.ASCENDING, (0, 3, 2, 1, 4)),
        (PlanSortColumn.MTIME, SortDirection.DESCENDING, (0, 2, 1, 3, 4)),
    ],
)
def test_trusted_sort_matches_explicit_orders_for_all_real_sorts(
    column,
    direction,
    expected,
) -> None:
    first = operation(
        OperationKind.COPY,
        source_path="Å.txt",
        target_path="Å.txt",
        source=file_stat(size=7, mtime_ns=10, identity_index=15),
    )
    second = operation(
        OperationKind.COPY,
        source_path="z.txt",
        target_path="z.txt",
        source=file_stat(size=7, mtime_ns=20, identity_index=16),
    )
    third = operation(
        OperationKind.COPY,
        source_path="Beta.txt",
        target_path="Beta.txt",
        source=file_stat(size=3, mtime_ns=20, identity_index=17),
    )
    warning = ScanWarning(ScanWarningCode.ACCESS_DENIED, "unavailable", "detail")
    projection = build_plan_projection(
        REQUEST_ID, _artifact(first, second, third, warnings=(warning,))
    )
    root_children = [
        node for node in projection.nodes if node.parent_index == 0
    ]
    replacements = {
        root_children[0].position: "Z",
        root_children[1].position: "A",
        root_children[2].position: "M",
        root_children[3].position: "N",
    }
    nonlexical = replace(
        projection,
        nodes=tuple(
            replace(node, rel_path_key=replacements[node.position])
            if node.position in replacements
            else node
            for node in projection.nodes
        ),
    )
    canonical = sort_plan_projection(
        nonlexical, PlanSortColumn.PATH, SortDirection.ASCENDING
    )

    trusted = projection_module._sort_plan_projection_from_canonical(
        canonical, column, direction
    )

    assert tuple(trusted.ordered_source_positions) == expected
    assert tuple(trusted.order_rank_by_source_position)[0] == 0
    assert nonlexical.nodes[trusted.ordered_source_positions[-1]].row_kind == "notice"
