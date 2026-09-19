from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

import namisync.workflows.plan_projection as projection_module
from namisync.core.models import EntryKind, ScanWarning, ScanWarningCode
from namisync.core.planning import BlockedReason, OpId, OperationKind
from namisync.core.scalars import MAX_SIGNED_64
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
    assert folder.size == 0
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


@pytest.mark.parametrize("folder", ["folder", "long-component-" * 12 + "\\" + "nested-" * 18])
def test_selection_refresh_preserves_operation_bearing_directory(folder: str) -> None:
    directory = operation(
        OperationKind.MKDIR, source_path=folder, target_path=folder,
        source=replace(file_stat(identity_index=20), kind=EntryKind.DIRECTORY),
    )
    child = operation(
        OperationKind.COPY, source_path=folder + r"\child.txt", target_path=folder + r"\child.txt",
        source=file_stat(identity_index=21),
    )
    projection = build_plan_projection(REQUEST_ID, _artifact(directory, child))
    directory_node = projection.node_for_id(projection.operation_node_id_by_id[str(directory.op_id)])
    assert directory_node.selectable_operation_count == 2
    updated = apply_plan_projection_selection(
        projection, selected_operation_ids=frozenset({str(directory.op_id)}),
        exclusion_reasons={str(child.op_id): "user-deselected"},
    )
    assert updated.nodes[0].selected_operation_count == 1
    restored = apply_plan_projection_selection(
        updated, selected_operation_ids=projection.selected_operation_ids, exclusion_reasons={},
    )
    assert restored.nodes[0].selected_operation_count == 2


def test_selection_refresh_does_not_borrow_child_eligibility_for_blocked_parent() -> None:
    directory = operation(
        OperationKind.MKDIR, source_path="folder", target_path="folder",
        source=replace(file_stat(identity_index=20), kind=EntryKind.DIRECTORY),
    )
    child = operation(
        OperationKind.COPY, source_path=r"folder\child.txt", target_path=r"folder\child.txt",
        source=file_stat(identity_index=21),
    )
    projection = build_plan_projection(REQUEST_ID, _artifact(directory, child))
    node = projection.node_for_id(projection.operation_node_id_by_id[str(directory.op_id)])
    # Isolate the projection's own-operation guard from workflow quarantine:
    # a descendant rollup must never authorize the parent's operation.
    projection = replace(
        projection,
        nodes=tuple(replace(item, selectable_operation_count=1, selected_operation_count=1)
                    if item.position in (0, node.position) else item
                    for item in projection.nodes),
        selected_operation_ids=frozenset({str(child.op_id)}),
    )
    node = projection.node_for_id(node.node_id)
    assert node.selectable_operation_count == 1
    with pytest.raises(ValueError, match="unavailable operation"):
        apply_plan_projection_selection(
            projection, selected_operation_ids=frozenset({str(directory.op_id)}),
            exclusion_reasons={},
        )
    updated = apply_plan_projection_selection(
        projection, selected_operation_ids=frozenset({str(child.op_id)}),
        exclusion_reasons={str(directory.op_id): "unsupported"},
    )
    assert updated.nodes[0].selected_operation_count == 1


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


def test_folder_size_rollup_nested_empty_duplicate_move_and_selection_independent() -> None:
    nested = operation(
        OperationKind.COPY,
        target_path=r"folder\deep\large.bin",
        source=file_stat(size=9, identity_index=100),
    )
    sibling = operation(
        OperationKind.COPY,
        target_path=r"folder\small.bin",
        source=file_stat(size=3, identity_index=101),
    )
    duplicate = operation(
        OperationKind.UPDATE,
        source_path="other.bin",
        target_path=r"folder\small.bin",
        source=file_stat(size=3, identity_index=102),
    )
    moved = operation(
        OperationKind.MOVE,
        target_path=r"folder\moved.bin",
        prior_target_path=r"old\moved.bin",
        target=file_stat(size=5, identity_index=103),
    )
    empty = operation(OperationKind.MKDIR, target_path=r"folder\empty")
    artifact = _artifact(nested, sibling, duplicate, moved, empty)
    selected = build_plan_projection(REQUEST_ID, artifact)
    deselected = build_plan_projection(
        REQUEST_ID,
        artifact,
        user_deselected=frozenset({nested.op_id}),
    )
    by_path = {node.rel_path_key: node for node in selected.nodes}
    assert by_path["FOLDER"].size == 17
    assert by_path["FOLDER\\DEEP"].size == 9
    assert by_path["FOLDER\\EMPTY"].size == 0
    assert next(node for node in selected.nodes if node.row_kind == "operation-group").size == 3
    assert by_path["FOLDER"].size == {
        node.rel_path_key: node for node in deselected.nodes
    }["FOLDER"].size
    assert all(
        node.size is None
        for node in selected.nodes
        if node.row_kind.startswith("prior-")
    )


def test_folder_size_conflict_unknown_blocked_and_incomplete_notes() -> None:
    conflict_a = operation(
        OperationKind.COPY,
        target_path=r"folder\conflict.bin",
        source=file_stat(size=4, identity_index=110),
    )
    conflict_b = operation(
        OperationKind.UPDATE,
        source_path="other.bin",
        target_path=r"folder\conflict.bin",
        source=file_stat(size=5, identity_index=111),
    )
    unknown = operation(OperationKind.COPY, target_path=r"folder\unknown.bin")
    blocked = replace(
        operation(
            OperationKind.COPY,
            target_path=r"folder\blocked.bin",
            source=file_stat(size=6, identity_index=112),
        ),
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    projection = build_plan_projection(
        REQUEST_ID,
        _artifact(conflict_a, conflict_b, unknown, blocked),
    )
    folder = next(node for node in projection.nodes if node.rel_path_key == "FOLDER")
    group = next(
        node for node in projection.nodes if node.row_kind == "operation-group"
    )
    assert group.size is None
    assert group.notice == "Partial size: conflicting facts"
    assert folder.size == 6
    assert folder.notice == "Partial size: incomplete file facts"

    incomplete = replace(
        _artifact(conflict_a),
        plan=replace(plan((conflict_a,)), source_complete=False),
    )
    incomplete_folder = next(
        node
        for node in build_plan_projection(REQUEST_ID, incomplete).nodes
        if node.rel_path_key == "FOLDER"
    )
    assert incomplete_folder.notice == "Partial size: incomplete file facts"


def test_folder_size_overflow_is_null_with_explicit_note() -> None:
    first = operation(
        OperationKind.NOOP,
        target_path=r"folder\first.bin",
        intended=file_stat(size=MAX_SIGNED_64, identity_index=120),
    )
    second = operation(
        OperationKind.NOOP,
        target_path=r"folder\second.bin",
        intended=file_stat(size=1, identity_index=121),
    )
    folder = next(
        node
        for node in build_plan_projection(REQUEST_ID, _artifact(first, second)).nodes
        if node.rel_path_key == "FOLDER"
    )
    assert folder.size is None
    assert folder.notice == "Partial size: overflow exceeds supported range"


def test_directory_cleanup_stat_is_a_zero_sized_folder_without_disclosure_change() -> None:
    directory_stat = replace(
        file_stat(size=0, identity_index=130),
        kind=EntryKind.DIRECTORY,
    )
    cleanup = operation(
        OperationKind.DELETE,
        source_path=None,
        target_path="empty",
        target=directory_stat,
    )
    row = next(
        node
        for node in build_plan_projection(REQUEST_ID, _artifact(cleanup)).nodes
        if node.rel_path_key == "EMPTY"
    )
    assert row.size == 0
    assert row.is_container is False
    assert row.is_directory is True


def test_size_sort_groups_known_unknown_files_then_directory_folders_both_directions() -> None:
    known = operation(
        OperationKind.NOOP,
        target_path="known.bin",
        intended=file_stat(size=2, identity_index=140),
    )
    unknown = operation(OperationKind.COPY, target_path="unknown.bin")
    nested = operation(
        OperationKind.NOOP,
        target_path=r"folder\nested.bin",
        intended=file_stat(size=5, identity_index=141),
    )
    directory_stat = replace(
        file_stat(size=0, identity_index=142),
        kind=EntryKind.DIRECTORY,
    )
    cleanup = operation(
        OperationKind.DELETE,
        source_path=None,
        target_path="empty",
        target=directory_stat,
    )
    projection = build_plan_projection(
        REQUEST_ID,
        _artifact(known, unknown, nested, cleanup),
    )
    for direction, expected in (
        (SortDirection.ASCENDING, ["KNOWN.BIN", "UNKNOWN.BIN", "EMPTY", "FOLDER"]),
        (SortDirection.DESCENDING, ["KNOWN.BIN", "UNKNOWN.BIN", "FOLDER", "EMPTY"]),
    ):
        order = sort_plan_projection(projection, PlanSortColumn.SIZE, direction)
        assert [
            node.rel_path_key
            for node in _ordered_nodes(order)
            if node.parent_index == 0
        ] == expected


def test_each_partial_size_cause_is_reported_independently() -> None:
    known = operation(
        OperationKind.COPY,
        target_path=r"folder\known.bin",
        source=file_stat(size=6, identity_index=150),
    )
    blocked = replace(
        known,
        blocked_reason=BlockedReason.UNSUPPORTED,
    )
    unknown = operation(OperationKind.COPY, target_path=r"folder\unknown.bin")
    conflict_a = operation(
        OperationKind.COPY,
        target_path=r"folder\conflict.bin",
        source=file_stat(size=1, identity_index=151),
    )
    conflict_b = operation(
        OperationKind.UPDATE,
        source_path="other.bin",
        target_path=r"folder\conflict.bin",
        source=file_stat(size=2, identity_index=152),
    )
    for operations, expected in (
        ((blocked,), "Partial size: incomplete file facts"),
        ((unknown,), "Partial size: incomplete file facts"),
        ((conflict_a, conflict_b), "Partial size: incomplete file facts"),
    ):
        projection = build_plan_projection(REQUEST_ID, _artifact(*operations))
        folder = next(node for node in projection.nodes if node.rel_path_key == "FOLDER")
        assert folder.notice == expected


def test_later_directory_member_cannot_erase_an_unknown_file_fact() -> None:
    unknown = replace(
        operation(OperationKind.DELETE, target_path=r"folder\same", source_path=None),
        op_id=OpId("1" * 32),
    )
    directory = replace(
        operation(OperationKind.MKDIR, target_path=r"folder\same"),
        op_id=OpId("2" * 32),
    )
    projection = build_plan_projection(REQUEST_ID, _artifact(unknown, directory))
    folder = next(node for node in projection.nodes if node.rel_path_key == "FOLDER")
    assert folder.size == 0
    assert folder.notice == "Partial size: incomplete file facts"


def test_overflow_folder_sorts_last_within_folders_in_both_directions() -> None:
    artifact = _artifact(
        operation(OperationKind.NOOP, target_path=r"overflow\large",
                  intended=file_stat(size=MAX_SIGNED_64)),
        operation(OperationKind.NOOP, target_path=r"overflow\extra",
                  intended=file_stat(size=1, identity_index=2)),
        operation(OperationKind.DELETE, target_path=r"small\removed", source_path=None,
                  target=file_stat(size=7, identity_index=3)),
        operation(OperationKind.COPY, target_path="unknown"),
    )
    projection = build_plan_projection(REQUEST_ID, artifact)
    small = next(node for node in projection.nodes if node.rel_path_key == "SMALL")
    assert small.size == 7
    for direction in (SortDirection.ASCENDING, SortDirection.DESCENDING):
        ordered = sort_plan_projection(projection, PlanSortColumn.SIZE, direction)
        assert [node.rel_path_key for node in _ordered_nodes(ordered)
                if node.parent_index == 0] == ["UNKNOWN", "SMALL", "OVERFLOW"]
