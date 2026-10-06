from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

import namisync.interfaces.web.plan_review as plan_review_module
from namisync.interfaces.web.plan_review import PlanReviewState
from namisync.interfaces.ui_state import MAX_JAVASCRIPT_SAFE_INTEGER
from namisync.core.planning import OperationKind
from namisync.core.preflight import Verdict
from namisync.workflows import (
    PlanProjection,
    PlanProjectionNode,
    PlanSortColumn,
    SortDirection,
    build_plan_projection,
)
from namisync.workflows.models import PlanArtifact, PlanRequest

from _db_fixtures import file_stat, operation, plan


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
        presentation_kind=kind,
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


def _file_fact_state(operations, *, complete=True) -> PlanReviewState:
    value = replace(plan(tuple(operations)), source_complete=complete)
    request = PlanRequest("b" * 32, value.source_root.path, value.target_root.path)
    artifact = PlanArtifact(
        request, SimpleNamespace(warnings=()), SimpleNamespace(warnings=(), directories=()),
        value, Verdict(True, (), SimpleNamespace()),
    )
    return PlanReviewState(
        "task-" + "1" * 32, "a" * 32,
        build_plan_projection(request.request_id, artifact),
        0, "reviewing", "source", "target",
    )


def test_plan_detail_keeps_original_paths_and_refuses_stale_or_root_reads() -> None:
    moved = operation(OperationKind.MOVE, target_path=r"New\Mixed.txt",
                      prior_target_path=r"Old\Mixed.txt", target=file_stat())
    state = _file_fact_state([moved])
    canonical = state.projection.operation_node_id_by_id[str(moved.op_id)]
    detail = state.detail(expected_revision=0, node_id=canonical)
    assert detail["detail"] == {
        "path": r"New\Mixed.txt", "prior_path": r"Old\Mixed.txt",
        "move_destination_path": None, "path_origin": "target",
        "notice": None,
    }
    group = next(node for node in state.projection.nodes if node.row_kind == "prior-group")
    assert state.detail(expected_revision=0, node_id=group.node_id)["detail"] == {
        "path": None, "prior_path": None,
        "move_destination_path": "New", "path_origin": None,
        "notice": None,
    }
    prior = next(node for node in state.projection.nodes if node.row_kind == "prior-operation")
    assert state.detail(expected_revision=0, node_id=prior.node_id)["detail"]["path"] == r"Old\Mixed.txt"
    assert state.detail(expected_revision=1, node_id="foreign")["detail"] is None
    with pytest.raises(KeyError):
        state.detail(expected_revision=0, node_id="foreign")
    with pytest.raises(ValueError, match="synthetic Plan root"):
        state.detail(expected_revision=0, node_id=state.projection.nodes[0].node_id)


def test_window_rename_name_and_group_destination_keep_utf16_bounds() -> None:
    old_name = "😀" * 125 + "a.txt"
    moved = operation(OperationKind.MOVE, target_path="new\\" + "😀" * 125 + "aaa",
                      prior_target_path="Old.txt", target=file_stat())
    renamed = operation(OperationKind.MOVE, target_path="Folder\\new.txt",
                        prior_target_path="Folder\\" + old_name, target=file_stat())
    state = _file_fact_state([moved, renamed])
    rows = state.window(expected_revision=0, offset=0, limit=256)["rows"]
    row = next(row for row in rows if row["operation_id"] == str(renamed.op_id))
    assert row["prior_name"] == old_name
    assert len(row["prior_name"].encode("utf-16-le")) // 2 == 255
    assert "prior_path" not in row
    # A maximum component behind an omitted ancestor still respects the hint bound.
    hint = plan_review_module._destination_display("outer\\" + old_name)
    assert hint.startswith("…\\") and len(hint.encode("utf-16-le")) // 2 <= 255
    assert not any(0xD800 <= ord(character) <= 0xDFFF for character in hint)
    assert plan_review_module._destination_display("") == ""


def test_window_scan_notice_keeps_side_code_and_complete_detail():
    from namisync.core.models import ScanWarning, ScanWarningCode
    warning = ScanWarning(ScanWarningCode.SCALAR_UNREPRESENTABLE,
                          "ancestor\\" + "😀" * 1000, "\x01" * 1024)
    value = plan(())
    request = PlanRequest("b" * 32, value.source_root.path, value.target_root.path)
    artifact = PlanArtifact(request, SimpleNamespace(warnings=(warning,)),
        SimpleNamespace(warnings=(), directories=()), value, Verdict(True, (), SimpleNamespace()))
    state = PlanReviewState("task-" + "1" * 32, "a" * 32,
        build_plan_projection(request.request_id, artifact), 0, "reviewing", "source", "target")
    row = state.window(expected_revision=0, offset=0, limit=256)["rows"][0]
    assert row["display"] == row["notice"]
    assert row["notice"].startswith("source: …") and " — scalar_unrepresentable — " in row["notice"]
    assert len(row["notice"].encode("utf-16-le")) // 2 <= 300
    detail = state.detail(expected_revision=0, node_id=row["node_id"])["detail"]
    assert detail["path"] == warning.rel_path
    assert detail["notice"].endswith(warning.detail)


def test_complete_plan_256_row_envelope_including_execution_has_response_margin():
    import json
    from namisync.interfaces.web.bridge import snapshot_bridge_response_result
    from namisync.interfaces.web.drain import TaskRegistry, _decorate_execution_window
    from namisync.core.planning import BlockedReason, OperationReason
    from namisync.core.preflight import RefusalCode
    from namisync.core.execution import ExecutionReason, ItemRecordingReason, TaskRecordingIssueReason
    from namisync.core.evidence import Outcome, Provenance, RecordingStatus
    from namisync.core.integrity import IntegrityReason, IntegrityResult, RecordDisposition
    from namisync.core.session import MAX_OPERATION_RESULT_PHASES, Disposition, PhaseStatus
    from namisync.workflows.selection import SELECTION_EXCLUSION_REASONS
    from namisync.workflows.views import OperationResultView, PhaseResultView, RecordingIssueView

    def longest(values):
        return max((member.value for member in values), key=len)

    prefix = "\\".join(["文" * 250] * 100)
    state = _file_fact_state([operation(OperationKind.COPY, target_path=prefix + rf"\item-{index:03}.txt",
        source=file_stat()) for index in range(256)])
    actual = state.window(expected_revision=0, offset=100, limit=256)
    assert len(actual["rows"]) == 256
    snapshot_bridge_response_result(actual, "3" * 32)
    row = dict(actual["rows"][0])
    assert set(row) == {"node_id", "display", "depth", "is_container", "visible_index",
        "parent_visible_index", "first_child_visible_index", "position_in_set", "set_size", "expanded",
        "row_kind", "operation_id", "operation_kind", "presentation_kind", "prior_name", "reason",
        "blocked_reason", "selection", "highlighted", "selectable_operation_count", "selected_operation_count",
        "operation_count", "size", "mtime_ns", "dependency_count", "risk", "move_peer_id", "move_group",
        "notice", "selection_exclusion_reason"}
    # Conservatively combine mutually exclusive optional fields into one row.
    # All varying text reaches its producer ceiling with six-byte JSON control
    # escaping; identities remain fixed ASCII, enums use their longest member.
    row.update(display="\x01" * 300, notice="\x01" * 300, prior_name="\x01" * 255,
        move_peer_id="node-" + "f" * 32,
        move_group={"count": 9007199254740991, "destination_display": "\x01" * 255},
        reason=max(OperationReason, key=lambda value: len(value.value)).value,
        blocked_reason=max(BlockedReason, key=lambda value: len(value.value)).value,
        selection_exclusion_reason=max(SELECTION_EXCLUSION_REASONS, key=len),
        operation_kind="move_update", presentation_kind="move_update", row_kind="prior-operation-group",
        selection="unselected", risk="irreversible", size="9" * 19, mtime_ns="9" * 19)
    for key, value in tuple(row.items()):
        if type(value) is int or key in {"parent_visible_index", "first_child_visible_index"}:
            row[key] = 9007199254740991
        elif type(value) is bool or key == "expanded":
            row[key] = False
    stamp = "9999-12-31T23:59:59.999999+00:00"
    operation_view = {"result": longest(Outcome), "reason": max(longest(ExecutionReason), longest(BlockedReason), max(SELECTION_EXCLUSION_REASONS, key=len), key=len), "recording": longest(RecordingStatus),
        "recording_reason": longest(ItemRecordingReason), "detail_omitted_count": 9007199254740991}
    integrity = {"result": longest(IntegrityResult), "reason": longest(IntegrityReason), "recording": longest(RecordingStatus),
        "record_disposition": longest(RecordDisposition), "detail_omitted_count": 9007199254740991}
    evidence = {"state": "already-verified", "content": {"algorithm": "xxh3_128", "digest": "f" * 32,
        "size": "9" * 19, "provenance": longest(Provenance), "observed_at": stamp}}
    # Result error, three phase errors/names, five recording issue details and
    # review refusal are bounded independently of rows; no item diagnostics
    # or per-item paths appear in compact execution overlays.
    result = {"headline": "verification-incomplete", "filesystem": "completed", "integrity": "incomplete",
        "recording": longest(RecordingStatus), "audit": longest(RecordingStatus), "disposition": longest(Disposition), "canceled": False,
        "phases": [{"phase": "\x01" * 1024, "status": longest(PhaseStatus), "items_done": 9007199254740991,
            "items_total": 9007199254740991, "bytes_done": "9" * 19, "bytes_total": "9" * 19,
            "error": "\x01" * 1024}] * MAX_OPERATION_RESULT_PHASES,
        "bytes_done": "9" * 19, "bytes_total": "9" * 19, "error": "\x01" * 1024,
        "recording_degraded_items": 9007199254740991,
        "recording_issues": [{"reason": longest(TaskRecordingIssueReason), "detail": "\x01" * 1024}] * len(TaskRecordingIssueReason),
        "omitted_detail_count": 9007199254740991, "presentation_omitted_detail_count": 9007199254740991,
        "review_refusal": {"reason": "review_fact_limit_exceeded", "tree_kind": "inventory",
            "population": "informational", "axis": "retained-bytes", "row_limit": 9007199254740991, "byte_limit": "9" * 19}}
    execution = {"execution_revision": 9007199254740991, "session_id": "f" * 32, "result": result,
        "failed_operation_count": 9007199254740991, "disk_capacity_failure_count": 9007199254740991,
        "gap": {"minimum_first_missed_seq": 9007199254740991, "maximum_first_missed_seq": 9007199254740991},
        "trash_location": "\x01" * 32767, "started_at": stamp, "ended_at": stamp,
        "refusal": {"origin": "commitment", "codes": [member.value for member in RefusalCode]}}
    assert set(result) == set(OperationResultView.__dataclass_fields__)
    assert set(result["phases"][0]) == set(PhaseResultView.__dataclass_fields__)
    assert set(result["recording_issues"][0]) == set(RecordingIssueView.__dataclass_fields__)
    empty_task = SimpleNamespace(execution_summary=None, delivered_terminal_record=None,
        execution_gap_minimum=None, execution_revision=0, execution_session_id=None)
    assert set(execution) == set(TaskRegistry._execution_summary_locked(empty_task))
    window = {**actual, "view_revision": 9007199254740991, "highlight_revision": 9007199254740991,
              "offset": 9007199254740991, "total": 9007199254740991, "rows": [row] * 256}
    bounded = _decorate_execution_window(window, execution, {row["operation_id"]: operation_view},
        {row["operation_id"]: integrity}, {row["operation_id"]: evidence})
    assert set(bounded) == {"disposition", "view_revision", "highlight_revision", "offset", "total", "rows", "execution"}
    assert set(bounded["rows"][0]["execution"]) == {"operation", "automatic_verification", "evidence"}
    envelope = {"schema_version": 1, "request_id": "3" * 32, "ok": True, "result": bounded}
    size = len(json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    assert size < 3 * 1024 * 1024  # Conservative proof margin, not a runtime wall.
    snapshot_bridge_response_result(bounded, "3" * 32)


@pytest.mark.parametrize("extra", [1, 2])
def test_folder_size_boundary_survives_row_serialization(extra: int) -> None:
    maximum = (1 << 63) - 1
    state = _file_fact_state([
        operation(OperationKind.NOOP, target_path=r"outer\inner\large.bin",
                  source=file_stat(size=maximum - 1)),
        operation(OperationKind.NOOP, target_path=r"outer\inner\small.bin",
                  source=file_stat(size=extra, identity_index=2)),
        operation(OperationKind.NOOP, target_path=r"sibling\ok.bin",
                  source=file_stat(size=5, identity_index=3)),
    ])
    rows = state.window(expected_revision=0, offset=0, limit=256)["rows"]
    for name in ("outer", "inner"):
        row = next(row for row in rows if row["display"] == name)
        assert row["size"] == (str(maximum) if extra == 1 else None)
        if extra == 1:
            assert row["notice"] is None
        else:
            assert "overflow" in row["notice"].lower()
    sibling = next(row for row in rows if row["display"] == "sibling")
    assert sibling["size"] == "5"
    assert sibling["notice"] is None
    large = next(row for row in rows if row["display"] == "large.bin")
    assert large["size"] == str(maximum - 1)


def test_partial_folder_size_keeps_known_bytes_in_window() -> None:
    state = _file_fact_state([
        operation(OperationKind.COPY, target_path=r"folder\known.bin",
                  source=file_stat(size=13)),
    ], complete=False)
    folder = state.window(expected_revision=0, offset=0, limit=256)["rows"][0]
    assert folder["display"] == "folder"
    assert folder["size"] == "13"
    assert "partial" in folder["notice"].lower()


def test_folder_size_ignores_selection_query_collapse_and_window() -> None:
    state = _file_fact_state([
        operation(OperationKind.COPY, source_path=rf"folder\{index:03}.bin",
                  target_path=rf"folder\{index:03}.bin",
                  source=file_stat(size=index + 1, identity_index=index + 1))
        for index in range(300)
    ] + [operation(OperationKind.UPDATE, target_path=r"folder\hidden.bin",
                   source=file_stat(size=7, identity_index=301))])
    total = str(sum(range(1, 301)) + 7)
    first_window = state.window(expected_revision=0, offset=0, limit=256)
    folder = first_window["rows"][0]
    assert first_window["total"] == 302
    assert len(first_window["rows"]) == 256
    assert folder["size"] == total
    assert len(state.window(expected_revision=0, offset=256, limit=256)["rows"]) == 46
    state.replace_selection(
        selected_operation_ids=frozenset(), exclusion_reasons={},
        selection_revision=1, selection_state="reviewing",
        requires_destructive_confirmation=False, irreversible_update_count=0,
        destructive_operation_count=0, irreversible_operation_count=0,
        destructive_operation_counts={"update": 0, "move_update": 0, "trash": 0, "delete": 0},
        required_bytes="0",
    )
    for query, filters, collapsed in [
        ("", frozenset({"copy"}), True),
        ("000.bin", frozenset({"copy"}), False),
        ("", frozenset(), False),
    ]:
        result = state.update(
            expected_revision=state.view_revision, search_query=query, filters=filters,
            sort_column=PlanSortColumn.SIZE, sort_direction=SortDirection.DESCENDING,
            collapse_node_id=folder["node_id"], collapsed=collapsed,
        )
        assert result["disposition"] == "applied"
        rows = state.window(expected_revision=state.view_revision, offset=0, limit=256)["rows"]
        assert rows[0]["size"] == total
        assert rows[0]["notice"] is None
        assert result["selected_operation_count"] == 0
        if collapsed:
            assert len(rows) == 1
        elif query:
            assert len(rows) == 2


@pytest.mark.parametrize("query,filters,kept_query,kept_filters", [
    ("moved", frozenset(), "", frozenset()),
    ("destination", frozenset({"copy"}), "destination", frozenset()),
    ("destination", frozenset(), "destination", frozenset()),
    ("missing", frozenset({"copy"}), "", frozenset()),
])
def test_move_reveal_expands_destination_and_clears_only_obstructing_query(query, filters, kept_query, kept_filters) -> None:
    state = _file_fact_state([
        operation(OperationKind.MOVE, target_path=r"outer\destination\file", prior_target_path=r"old\file", target=file_stat()),
        operation(OperationKind.COPY, target_path=r"other\copy", source=file_stat()),
    ])
    group = next(node for node in state.projection.nodes if node.row_kind == "prior-group")
    outer = next(node for node in state.projection.nodes if node.rel_path_key == "OUTER")
    state.update(expected_revision=0, search_query=query, filters=filters,
                 sort_column=PlanSortColumn.FILENAME, sort_direction=SortDirection.DESCENDING,
                 collapse_node_id=outer.node_id, collapsed=True)
    selected = state.projection.selected_operation_ids
    before = state.summary()
    assert state.reveal_move(expected_revision=0, node_id=group.node_id)["summary"]["disposition"] == "conflict"
    assert state.summary() == before
    result = state.reveal_move(expected_revision=state.view_revision, node_id=group.node_id)
    assert result["node_id"] == group.move_peer_id
    assert result["summary"]["search_query"] == kept_query
    assert result["summary"]["filters"] == sorted(kept_filters)
    assert result["summary"]["sort_direction"] == "descending"
    assert state.projection.selected_operation_ids == selected
    assert outer.node_id not in state.collapsed_node_ids
    window = state.window(expected_revision=state.view_revision, offset=result["index"], limit=1)
    assert window["rows"][0]["node_id"] == group.move_peer_id
    assert state.reveal_move(expected_revision=state.view_revision, node_id=group.node_id)["summary"]["disposition"] == "noop"
    with pytest.raises(ValueError, match="informational"):
        state.reveal_move(expected_revision=state.view_revision, node_id=outer.node_id)


def test_rename_filters_own_labels_counts_and_complete_offwindow_selection() -> None:
    renames = [
        operation(OperationKind.MOVE, target_path=rf"folder\new-{index:03}.bin",
                  prior_target_path=rf"FOLDER\old-{index:03}.bin",
                  target=file_stat(size=1, identity_index=index + 1))
        for index in range(300)
    ]
    recase = operation(OperationKind.RECASE, target_path=r"folder\case.bin",
                       prior_target_path=r"folder\CASE.bin", target=file_stat())
    moved = operation(OperationKind.MOVE, target_path=r"folder\moved.bin",
                      prior_target_path=r"old\moved.bin", target=file_stat())
    updated = operation(OperationKind.MOVE_UPDATE, target_path=r"folder\updated.bin",
                        prior_target_path=r"folder\previous.bin",
                        source=file_stat(size=13), target=file_stat(size=7))
    state = _file_fact_state([*renames, recase, moved, updated])
    counts = state.summary()["filter_counts"]
    assert counts["rename"] == 301
    assert counts["move"] == counts["move_update"] == 1
    assert counts["all"] == 303
    assert "recase" not in counts
    folder = next(node for node in state.projection.nodes if node.rel_path_key == "FOLDER")
    expected = {
        "rename": {str(item.op_id) for item in (*renames, recase)},
        "move": {str(moved.op_id)},
        "move_update": {str(updated.op_id)},
    }
    for category, identifiers in expected.items():
        summary = state.update(
            expected_revision=state.view_revision, search_query="",
            filters=frozenset({category}), sort_column=PlanSortColumn.FILENAME,
            sort_direction=SortDirection.DESCENDING,
            collapse_node_id=None, collapsed=None,
        )
        assert summary["scope_selectable_operation_count"] == len(identifiers)
        rows = []
        for offset in range(0, summary["visible_row_count"], 256):
            rows.extend(state.window(expected_revision=state.view_revision,
                                     offset=offset, limit=256)["rows"])
        operation_rows = [row for row in rows if row["operation_id"] is not None]
        assert {row["operation_id"] for row in operation_rows} == identifiers
        assert all(row["presentation_kind"] == category for row in operation_rows)
        assert all((row["prior_name"] is not None) == (category == "rename")
                   for row in operation_rows)
        assert all("prior_path" not in row for row in operation_rows)
        assert set(state.selection_scope(expected_view_revision=state.view_revision,
                                         expected_selection_revision=0)) == identifiers
        if category == "rename":
            assert {row["operation_kind"] for row in operation_rows} == {"move", "recase"}
            state.update(expected_revision=state.view_revision, search_query="",
                         filters=frozenset({category}), sort_column=PlanSortColumn.PATH,
                         sort_direction=SortDirection.ASCENDING,
                         collapse_node_id=folder.node_id, collapsed=True)
            assert set(state.selection_scope(expected_view_revision=state.view_revision,
                                             expected_selection_revision=0)) == identifiers
            state.update(expected_revision=state.view_revision, search_query="",
                         filters=frozenset({category}), sort_column=PlanSortColumn.PATH,
                         sort_direction=SortDirection.ASCENDING,
                         collapse_node_id=folder.node_id, collapsed=False)
    assert state.projection.selected_operation_ids == frozenset().union(*expected.values())
    assert state.summary()["filter_counts"] == counts


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
    assert state.summary()["visible_row_count"] == 3
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
    assert [row["node_id"] for row in window["rows"]] == ["folder"]
    assert window["total"] == 1
    assert window["rows"][0]["visible_index"] == 0
    assert window["rows"][0]["parent_visible_index"] is None
    assert window["rows"][0]["depth"] == 0
    assert anchor == {
        "disposition": "current",
        "view_revision": 1,
        "node_id": "folder",
        "index": 0,
    }
    assert state.window(expected_revision=0, offset=0, limit=1)["disposition"] == "conflict"


def test_plan_summary_filter_counts_are_complete_direct_categories() -> None:
    nodes = list(_projection().nodes)
    nodes[0] = replace(nodes[0], subtree_end=5)
    nodes[2] = replace(nodes[2], blocked_reason="permission")
    nodes[3] = replace(nodes[3], blocked_reason="unsupported")
    notice = replace(
        _node("notice", "planning notice", 4, 0, 5),
        row_kind="notice",
        selection="disabled",
        operation_count=0,
        notice="insufficient space",
    )
    nodes.append(notice)
    projection = PlanProjection(
        "a" * 32,
        tuple(nodes),
        {node.node_id: node.position for node in nodes},
        {"1" * 32: "copy", "2" * 32: "delete"},
        frozenset({"1" * 32}),
    )
    state = PlanReviewState(
        "task-" + "1" * 32, "a" * 32, projection, 0, "reviewing", "source", "target"
    )
    expected = {
        "all": 3,
        "copy": 0,
        "mkdir": 0,
        "move": 0,
        "rename": 0,
        "update": 0,
        "move_update": 0,
        "trash": 0,
        "delete": 0,
        "noop": 0,
        "blocked": 1,
        "error": 0,
        "unsupported": 1,
        "notice": 1,
    }
    assert state.summary()["filter_counts"] == expected
    for revision, (category, expected_node) in enumerate(
        (("blocked", nodes[2].node_id), ("unsupported", nodes[3].node_id), ("error", None))
    ):
        state.update(
            expected_revision=revision,
            search_query="",
            filters=frozenset({category}),
            sort_column=PlanSortColumn.PATH,
            sort_direction=SortDirection.ASCENDING,
            collapse_node_id=None,
            collapsed=None,
        )
        window = state.window(expected_revision=revision + 1, offset=0, limit=256)
        matching = [row["node_id"] for row in window["rows"] if row["operation_id"] is not None]
        assert matching == ([] if expected_node is None else [expected_node])
        assert state.summary()["filter_counts"] == expected
    state.update(
        expected_revision=3,
        search_query="does-not-match",
        filters=frozenset({"copy"}),
        sort_column=PlanSortColumn.SIZE,
        sort_direction=SortDirection.DESCENDING,
        collapse_node_id="folder",
        collapsed=True,
    )
    assert state.summary()["filter_counts"] == expected


def test_plan_selection_scope_follows_query_not_collapse_sort_or_navigation() -> None:
    projection = _projection()
    nodes = list(projection.nodes)
    nodes[0] = replace(nodes[0], selection="selected", selectable_operation_count=2,
                       selected_operation_count=2, operation_count=2)
    nodes[1] = replace(nodes[1], selection="selected", selectable_operation_count=1,
                       selected_operation_count=1, operation_count=1)
    state = PlanReviewState("task-" + "1" * 32, "a" * 32,
                            replace(projection, nodes=tuple(nodes)), 0,
                            "reviewing", "source", "target")
    initial = state.summary()
    assert initial["scope_selectable_operation_count"] == 2
    assert initial["scope_selected_operation_count"] == 2
    state.update(expected_revision=0, search_query="BETA",
                 filters=frozenset({"copy"}), sort_column=PlanSortColumn.SIZE,
                 sort_direction=SortDirection.DESCENDING,
                 collapse_node_id="folder", collapsed=True)
    assert state.summary()["selection_revision"] == 0
    assert [row["node_id"] for row in state.window(expected_revision=1, offset=0, limit=1)["rows"]] == ["folder"]
    assert state.selection_scope(expected_view_revision=1, expected_selection_revision=0) == ("1" * 32,)
    assert state.selection_scope(expected_view_revision=1, expected_selection_revision=0,
                                 node_id="folder") == ("1" * 32,)
    assert state.selection_scope(expected_view_revision=0, expected_selection_revision=0) is None
    assert state.selection_scope(expected_view_revision=1, expected_selection_revision=1) is None
    state.replace_selection(
        selected_operation_ids=frozenset({"2" * 32}),
        exclusion_reasons={"1" * 32: "user-deselected"},
        selection_revision=1, selection_state="reviewing",
        requires_destructive_confirmation=True, irreversible_update_count=0,
        destructive_operation_count=1, irreversible_operation_count=1,
        destructive_operation_counts={"update": 0, "move_update": 0,
                                      "trash": 0, "delete": 1},
        required_bytes="0",
    )
    assert state.summary()["selected_operation_count"] == 1
    assert state.summary()["scope_selected_operation_count"] == 0
    assert state.window(expected_revision=2, offset=0, limit=1)["rows"][0]["selection"] == "unselected"
    state.update(expected_revision=2, search_query="", filters=frozenset(),
                 sort_column=PlanSortColumn.PATH,
                 sort_direction=SortDirection.ASCENDING,
                 collapse_node_id=None, collapsed=None)
    assert state.summary()["selection_revision"] == 1
    assert state.selection_scope(expected_view_revision=3, expected_selection_revision=1,
                                 node_id="folder") == ("1" * 32,)


def test_plan_selection_scope_includes_off_window_matches() -> None:
    total = 300
    root = replace(_node("root", "Plan", 0, None, total + 1, container=True),
                   selection="selected", selectable_operation_count=total,
                   selected_operation_count=total, operation_count=total)
    leaves = tuple(
        _node(f"node-{index:032x}", f"copy-{index:03}.txt", index + 1, 0,
              index + 2, operation_id=f"{index:032x}", kind="copy")
        for index in range(total)
    )
    nodes = (root, *leaves)
    projection = PlanProjection("a" * 32, nodes,
                                {node.node_id: node.position for node in nodes},
                                {node.operation_id: node.node_id for node in leaves},
                                frozenset(node.operation_id for node in leaves))
    state = PlanReviewState("task-" + "1" * 32, "a" * 32, projection,
                            0, "reviewing", "source", "target")
    assert len(state.window(expected_revision=0, offset=0, limit=256)["rows"]) == 256
    scope = state.selection_scope(expected_view_revision=0, expected_selection_revision=0)
    assert len(scope) == total
    assert f"{total - 1:032x}" in scope


def test_operation_anchor_resolves_collapsed_sorted_and_excluded_views() -> None:
    state = PlanReviewState("task-" + "1" * 32, "a" * 32, _projection(),
                            0, "reviewing", "source", "target")
    assert state.operation_anchor(expected_revision=0, operation_id="1" * 32) == {
        "disposition": "current", "view_revision": 0, "node_id": "copy", "index": 2,
    }
    before_selection = state.summary()["selection_revision"]
    state.update(expected_revision=0, search_query="", filters=frozenset(),
                 sort_column=PlanSortColumn.SIZE, sort_direction=SortDirection.DESCENDING,
                 collapse_node_id="folder", collapsed=True)
    assert state.operation_anchor(expected_revision=1, operation_id="1" * 32) == (
        state.anchor(expected_revision=1, node_id="folder")
    )
    assert state.operation_anchor(expected_revision=0, operation_id="1" * 32) == {
        "disposition": "conflict", "view_revision": 1, "node_id": None, "index": None,
    }
    state.update(expected_revision=1, search_query="no matches", filters=frozenset(),
                 sort_column=PlanSortColumn.PATH, sort_direction=SortDirection.ASCENDING,
                 collapse_node_id=None, collapsed=None)
    assert state.operation_anchor(expected_revision=2, operation_id="1" * 32) == {
        "disposition": "current", "view_revision": 2, "node_id": None, "index": None,
    }
    with pytest.raises(ValueError, match="operation id is unknown"):
        state.operation_anchor(expected_revision=2, operation_id="f" * 32)
    assert state.summary()["selection_revision"] == before_selection


def test_plan_rootless_window_offsets_and_anchor_preserve_children() -> None:
    state = PlanReviewState("task-" + "1" * 32, "a" * 32, _projection(),
                            0, "reviewing", "source", "target")
    window = state.window(expected_revision=0, offset=0, limit=256)
    assert window["total"] == 3
    assert [row["node_id"] for row in window["rows"]] == ["delete", "folder", "copy"]
    assert [row["visible_index"] for row in window["rows"]] == [0, 1, 2]
    assert [row["parent_visible_index"] for row in window["rows"]] == [None, None, 1]
    assert [row["depth"] for row in window["rows"]] == [0, 0, 1]
    assert window["rows"][1]["first_child_visible_index"] == 2
    assert state.window(expected_revision=0, offset=2, limit=1)["rows"][0]["node_id"] == "copy"
    assert state.anchor(expected_revision=0, node_id="copy")["index"] == 2
    assert state.anchor(expected_revision=0, node_id="root")["index"] is None
    state.update(expected_revision=0, search_query="no matches",
                 filters=frozenset(), sort_column=PlanSortColumn.PATH,
                 sort_direction=SortDirection.ASCENDING,
                 collapse_node_id=None, collapsed=None)
    assert state.window(expected_revision=1, offset=0, limit=256)["total"] == 0
    assert state.anchor(expected_revision=1, node_id="copy")["index"] is None


def test_plan_highlights_are_independent_revisioned_ranges_and_window_flags() -> None:
    state = PlanReviewState("task-" + "1" * 32, "a" * 32, _projection(),
                            0, "reviewing", "source", "target")
    summary = state.summary()
    assert summary["highlight_revision"] == 0
    assert summary["highlighted_count"] == 0
    applied = state.mutate_highlight(
        expected_view_revision=0, expected_highlight_revision=0,
        gesture="replace", node_id="delete",
    )
    assert applied["highlight_revision"] == 1
    assert applied["highlight_anchor_node_id"] == "delete"
    assert applied["highlight_focus_node_id"] == "delete"
    assert state.window(expected_revision=0, offset=0, limit=1)["rows"][0]["highlighted"]

    extended = state.mutate_highlight(
        expected_view_revision=0, expected_highlight_revision=1,
        gesture="extend", node_id="copy",
    )
    assert extended["highlighted_count"] == 3
    assert [row["highlighted"] for row in state.window(expected_revision=0, offset=0, limit=3)["rows"]] == [True, True, True]
    assert state.mutate_highlight(
        expected_view_revision=0, expected_highlight_revision=1,
        gesture="toggle", node_id="copy",
    )["disposition"] == "conflict"

    toggled = state.mutate_highlight(
        expected_view_revision=0, expected_highlight_revision=2,
        gesture="toggle", node_id="copy",
    )
    assert toggled["highlighted_count"] == 2
    added = state.mutate_highlight(
        expected_view_revision=0, expected_highlight_revision=3,
        gesture="add-range", node_id="copy",
    )
    assert added["highlighted_count"] == 3


def test_plan_highlights_persist_through_collapse_and_clear_on_query_or_filter() -> None:
    state = PlanReviewState("task-" + "1" * 32, "a" * 32, _projection(),
                            0, "reviewing", "source", "target")
    state.mutate_highlight(expected_view_revision=0, expected_highlight_revision=0,
                           gesture="replace", node_id="copy")
    collapsed = state.update(
        expected_revision=0, search_query="", filters=frozenset(),
        sort_column=PlanSortColumn.PATH, sort_direction=SortDirection.ASCENDING,
        collapse_node_id="folder", collapsed=True,
    )
    assert collapsed["highlighted_count"] == 1
    assert collapsed["highlight_focus_node_id"] == "copy"
    assert collapsed["highlight_focus_visible_index"] is None
    assert not state.window(expected_revision=1, offset=0, limit=256)["rows"][-1]["highlighted"]
    reopened = state.update(
        expected_revision=1, search_query="beta", filters=frozenset(),
        sort_column=PlanSortColumn.PATH, sort_direction=SortDirection.ASCENDING,
        collapse_node_id="folder", collapsed=False,
    )
    assert reopened["highlighted_count"] == 0
    assert reopened["highlight_revision"] == 2
    assert reopened["highlight_anchor_node_id"] is None


def test_highlighted_selection_scope_deduplicates_overlapping_folder_and_operation() -> None:
    state = PlanReviewState("task-" + "1" * 32, "a" * 32, _projection(),
                            0, "reviewing", "source", "target")
    state.mutate_highlight(expected_view_revision=0, expected_highlight_revision=0,
                           gesture="replace", node_id="folder")
    state.mutate_highlight(expected_view_revision=0, expected_highlight_revision=1,
                           gesture="toggle", node_id="copy")
    assert state.highlighted_selection_scope(
        expected_view_revision=0,
        expected_highlight_revision=2,
        expected_selection_revision=0,
    ) == ("1" * 32,)


def test_highlighted_selection_scope_keeps_collapsed_off_window_descendants() -> None:
    state = PlanReviewState("task-" + "1" * 32, "a" * 32, _projection(),
                            0, "reviewing", "source", "target",
                            search_query="beta", filters=frozenset({"copy"}))
    state.mutate_highlight(expected_view_revision=0, expected_highlight_revision=0,
                           gesture="replace", node_id="copy")
    state.update(
        expected_revision=0, search_query="beta", filters=frozenset({"copy"}),
        sort_column=PlanSortColumn.PATH, sort_direction=SortDirection.ASCENDING,
        collapse_node_id="folder", collapsed=True,
    )
    assert state.highlighted_selection_scope(
        expected_view_revision=1,
        expected_highlight_revision=1,
        expected_selection_revision=0,
    ) == ("1" * 32,)


def test_highlighted_selection_scope_rejects_stale_revisions_and_empty_is_noop() -> None:
    state = PlanReviewState("task-" + "1" * 32, "a" * 32, _projection(),
                            0, "reviewing", "source", "target")
    assert state.highlighted_selection_scope(
        expected_view_revision=0,
        expected_highlight_revision=0,
        expected_selection_revision=0,
    ) == ()
    state.mutate_highlight(expected_view_revision=0, expected_highlight_revision=0,
                           gesture="replace", node_id="delete")
    assert state.highlighted_selection_scope(
        expected_view_revision=1,
        expected_highlight_revision=1,
        expected_selection_revision=0,
    ) is None
    assert state.highlighted_selection_scope(
        expected_view_revision=0,
        expected_highlight_revision=0,
        expected_selection_revision=0,
    ) is None
    assert state.highlighted_selection_scope(
        expected_view_revision=0,
        expected_highlight_revision=1,
        expected_selection_revision=1,
    ) is None


def test_plan_highlight_arrow_gestures_seed_and_preserve_range() -> None:
    state = PlanReviewState("task-" + "1" * 32, "a" * 32, _projection(),
                            0, "reviewing", "source", "target")
    first = state.mutate_highlight(
        expected_view_revision=0, expected_highlight_revision=0,
        gesture="move_down",
    )
    assert first["highlight_focus_node_id"] == "delete"
    second = state.mutate_highlight(
        expected_view_revision=0, expected_highlight_revision=1,
        gesture="move_down_extend",
    )
    assert second["highlighted_count"] == 2
    assert second["highlight_focus_node_id"] == "folder"
    third = state.mutate_highlight(
        expected_view_revision=0, expected_highlight_revision=2,
        gesture="move_down_extend",
    )
    assert third["highlighted_count"] == 3
    assert third["highlight_focus_node_id"] == "copy"
    cleared = state.mutate_highlight(
        expected_view_revision=0, expected_highlight_revision=3,
        gesture="clear",
    )
    assert cleared["highlighted_count"] == 0


def test_scoped_counts_use_container_own_operation_not_mixed_rollup() -> None:
    nodes = (
        replace(_node("root", "Plan", 0, None, 3, container=True),
                selection="mixed", selectable_operation_count=2,
                selected_operation_count=1, operation_count=2),
        replace(_node("parent", "parent", 1, 0, 3, container=True,
                      operation_id="1" * 32, kind="copy"),
                selection="mixed", selectable_operation_count=2,
                selected_operation_count=1, operation_count=2),
        replace(_node("child", "child", 2, 1, 3,
                      operation_id="2" * 32, kind="delete"),
                selection="unselected", selected_operation_count=0),
    )
    projection = PlanProjection("a" * 32, nodes,
                                {node.node_id: node.position for node in nodes},
                                {"1" * 32: "parent", "2" * 32: "child"},
                                frozenset({"1" * 32}))
    state = PlanReviewState("task-" + "1" * 32, "a" * 32, projection,
                            0, "reviewing", "source", "target")
    summary = state.update(
        expected_revision=0, search_query="", filters=frozenset({"copy"}),
        sort_column=PlanSortColumn.PATH, sort_direction=SortDirection.ASCENDING,
        collapse_node_id=None, collapsed=None,
    )
    assert summary["scope_selectable_operation_count"] == 1
    assert summary["scope_selected_operation_count"] == 1
    assert state.selection_scope(expected_view_revision=1,
                                 expected_selection_revision=0) == ("1" * 32,)
    assert state.selection_scope(expected_view_revision=1,
                                 expected_selection_revision=0,
                                 node_id="parent") == ("1" * 32,)
    assert state.window(expected_revision=1, offset=0, limit=1)["rows"][0]["selection"] == "selected"


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
    assert [row["node_id"] for row in rows] == ["delete"]
    assert rows[0]["selection"] == "unselected"


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

    assert state.summary()["visible_row_count"] == 3


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
    assert [row["node_id"] for row in window["rows"]] == ["delete"]


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
