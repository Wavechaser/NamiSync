from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

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

from _db_fixtures import file_stat, operation, plan


REQUEST_ID = "1" * 32


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
    ascending_root = [node.display for node in ascending.nodes if node.parent_index == 0]
    descending_root = [node.display for node in descending.nodes if node.parent_index == 0]
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
        for node in descending.nodes
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
    assert [node.display for node in ordered.nodes if node.parent_index == 0] == [
        "j.txt",
        "ı.txt",
    ]
