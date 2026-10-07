"""Plan fixture, action and counted-scale controls for optional measurements."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from functools import cache
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from types import SimpleNamespace

import pytest

from namisync.core.planning import OperationKind
from namisync.core.events import CORE_EVENT_SCHEMA_VERSION, Envelope, ItemOutcome
from namisync.core.evidence import Outcome
from namisync.core.session import SessionId
from namisync.interfaces.task_port import TaskEventUpdateView
from namisync.interfaces.web.bridge import snapshot_task_drain_response_prefix
from namisync.interfaces.web.task_snapshot import TaskPresentationState, TaskSnapshotStage
from namisync.workflows.views import session_event_view
from tools.performance import plan as benchmark
from tools.performance.plan import build_fixture_manifest, build_plan_fixture
from namisync.interfaces.web import drain as drain_module
from namisync.workflows.plan_projection import (
    PlanSortColumn, SortDirection, build_plan_projection, sort_plan_projection,
)
from namisync.workflows.selection import apply_selection_mutation, derive_execution_selection

CONTRACT_PATH = Path(__file__).with_name("m1_7_plan_compact_contract.json")
AUTHORITY_PATH = CONTRACT_PATH.with_name("m1_7_plan_compact_authority.json")
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = REPOSITORY_ROOT / "tools" / "performance" / "plan.py"
def test_scoped_selection_120k_server_mutation_cost() -> None:
    artifact = build_plan_fixture(information_heavy=False)
    state = benchmark.make_plan_review_state(artifact)
    initial = state.window(expected_revision=0, offset=0, limit=256)
    assert initial["total"] == len(state.current_sequence.visible_positions) - 1
    assert initial["rows"][0]["node_id"] != state.projection.nodes[0].node_id
    assert initial["rows"][0]["visible_index"] == 0
    viewed = state.update(
        expected_revision=0, search_query="", filters=frozenset({"copy"}),
        sort_column=PlanSortColumn.PATH,
        sort_direction=SortDirection.ASCENDING,
        collapse_node_id=None, collapsed=None,
    )
    started = perf_counter()
    identifiers = state.selection_scope(
        expected_view_revision=viewed["view_revision"],
        expected_selection_revision=0,
    )
    deselected = apply_selection_mutation(
        artifact.plan, frozenset(), deselect=frozenset(identifiers),
    )
    decision = derive_execution_selection(
        artifact.plan, user_deselected=deselected,
    )
    state.replace_selection(
        selected_operation_ids=frozenset(str(identifier) for identifier in decision.selection),
        exclusion_reasons={}, selection_revision=1, selection_state="reviewing",
        requires_destructive_confirmation=decision.requires_destructive_confirmation,
        irreversible_update_count=decision.irreversible_update_count,
        destructive_operation_count=decision.destructive_operation_count,
        irreversible_operation_count=decision.irreversible_operation_count,
        destructive_operation_counts=benchmark._selection_count_mapping(decision),
        required_bytes=decision.required_bytes,
    )
    elapsed = perf_counter() - started
    print(f"scoped-selection-120k: {len(identifiers)} ids, {elapsed:.3f}s")
    assert len(identifiers) == 16_667
    assert len(set(identifiers)) == len(identifiers)
    assert set(identifiers) == {
        str(operation.op_id)
        for operation in artifact.plan.operations
        if operation.kind is OperationKind.COPY
    }
    assert len(decision.selection) < len(artifact.plan.operations)
    assert state.summary()["selection_revision"] == 1
    assert state.summary()["scope_selected_operation_count"] == 0



def test_highlighted_selection_120k_server_mutation_cost() -> None:
    artifact = build_plan_fixture(information_heavy=False)
    state = benchmark.make_plan_review_state(artifact)
    window = state.window(expected_revision=0, offset=0, limit=256)
    row = next(row for row in window["rows"] if row["operation_id"] is not None)
    highlighted = state.mutate_highlight(
        expected_view_revision=0, expected_highlight_revision=0,
        gesture="replace", node_id=row["node_id"],
    )
    started = perf_counter()
    identifiers = state.highlighted_selection_scope(
        expected_view_revision=0,
        expected_highlight_revision=highlighted["highlight_revision"],
        expected_selection_revision=0,
    )
    deselected = apply_selection_mutation(
        artifact.plan, frozenset(), deselect=frozenset(identifiers),
    )
    decision = derive_execution_selection(
        artifact.plan, user_deselected=deselected,
    )
    state.replace_selection(
        selected_operation_ids=frozenset(str(identifier) for identifier in decision.selection),
        exclusion_reasons={}, selection_revision=1, selection_state="reviewing",
        requires_destructive_confirmation=decision.requires_destructive_confirmation,
        irreversible_update_count=decision.irreversible_update_count,
        destructive_operation_count=decision.destructive_operation_count,
        irreversible_operation_count=decision.irreversible_operation_count,
        destructive_operation_counts=benchmark._selection_count_mapping(decision),
        required_bytes=decision.required_bytes,
    )
    elapsed = perf_counter() - started
    print(f"highlight-selection-120k: {len(identifiers)} ids, {elapsed:.3f}s")
    assert identifiers == (row["operation_id"],)
    assert state.summary()["selection_revision"] == 1



def test_headed_fixture_publishes_stable_exact_task_summaries_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry = drain_module.TaskRegistry(object())
    rows = [
        {
            "plan_session_id": f"{ordinal + 20:032x}",
            "task_id": f"task-{ordinal:032x}",
            "request_id": f"{ordinal + 10:032x}",
            "source_path": rf"C:\fixture\{ordinal}\source",
            "target_path": rf"D:\fixture\{ordinal}\target",
        }
        for ordinal in (1, 2)
    ]
    for row in rows:
        task = drain_module._TaskState(
            row["task_id"],
            "f" * 32,
            registry._clock,
            session_id=row["plan_session_id"],
            delivered_terminal_record=SimpleNamespace(state="completed"),
            session_released=True,
            task_kind="sync-plan",
            request_id=row["request_id"],
        )
        registry._tasks[row["task_id"]] = task

    controller = benchmark._HeadedFixtureController(
        {"id": "ui_start_execution_click_feedback", "sample_kind": "cold"},
        tmp_path,
        2,
    )
    pending_rows = iter(rows)
    monkeypatch.setattr(benchmark, "build_plan_fixture", lambda **_kwargs: object())
    monkeypatch.setattr(
        controller,
        "_create_review",
        lambda _registry: next(pending_rows),
    )
    settlement_calls = []

    def open_plan_view(task_id: str) -> dict[str, object]:
        row = next(item for item in rows if item["task_id"] == task_id)
        settlement_calls.append(("open", task_id))
        return {
            "disposition": "opened",
            "request_id": row["request_id"],
            "source_path": row["source_path"],
            "target_path": row["target_path"],
            "task_id": task_id,
            "view_revision": 0,
        }

    def get_plan_window(
        task_id: str, *, expected_revision: int, offset: int, limit: int
    ) -> dict[str, object]:
        row = next(item for item in rows if item["task_id"] == task_id)
        settlement_calls.append(
            ("window", task_id, expected_revision, offset, limit)
        )
        return {
            "disposition": "current",
            "offset": 0,
            "rows": [
                {
                    "node_id": benchmark._expected_plan_root_node_id(
                        row["request_id"]
                    ),
                    "operation_id": None,
                    "visible_index": 0,
                },
                *({} for _ in range(255)),
            ],
            "total": 120_000,
            "view_revision": 0,
        }

    monkeypatch.setattr(registry, "open_plan_view", open_plan_view)
    monkeypatch.setattr(registry, "get_plan_window", get_plan_window)

    controller.bind(registry)
    initial = registry.list_tasks()
    metadata = controller.command({})

    assert [task.task_kind for task in initial.tasks] == ["sync-plan", "sync-plan"]
    assert [task.request_id for task in initial.tasks] == [
        rows[0]["request_id"],
        rows[1]["request_id"],
    ]
    assert [task.task_kind for task in registry.list_tasks().tasks] == [
        "sync-plan",
        "sync-plan",
    ]
    assert [task.request_id for task in registry.list_tasks().tasks] == [
        rows[0]["request_id"],
        rows[1]["request_id"],
    ]
    assert metadata["published_plan_count"] == 2
    assert all(row["fresh_execution_unused"] for row in metadata["rows"])
    assert controller.published_fixture is not None
    assert all(
        row["execution_unused"]
        for row in controller.published_fixture["rows"]
    )
    assert settlement_calls == [
        ("open", rows[0]["task_id"]),
        ("window", rows[0]["task_id"], 0, 0, 256),
        ("open", rows[1]["task_id"]),
        ("window", rows[1]["task_id"], 0, 0, 256),
    ]
    assert all(
        row["initial_view_settlement"]["window_total"] == 120_000
        for row in controller.published_fixture["rows"]
    )
    with pytest.raises(ValueError, match="command is invalid"):
        controller.command({"activate": 1})



def test_headed_identity_timeout_records_one_bounded_production_read() -> None:
    script = benchmark._headed_probe_script("ui_start_execution_click_feedback")

    identity_wait = script[script.index("let selectionRecoveryUsed = false;") :]
    identity_wait = identity_wait[: identity_wait.index("} catch (error)")]
    assert (
        'const currentReview = document.querySelector(".nami-plan-review");'
        in identity_wait
    )
    assert "currentReview?.isConnected === true" in identity_wait
    assert "?.textContent.includes(expectedSource)" in identity_wait
    assert "return currentReview;" in identity_wait
    recovery = identity_wait[
        identity_wait.index("if (\n            selectionRecoveryUsed === false") :
    ]
    recovery = recovery[: recovery.index("\n          }")]
    assert "selectionRecoveryUsed === false" in recovery
    assert "selected === button" in recovery
    assert "currentReview === null" in recovery
    assert (
        'selectedTaskStatus\n              === "Plan review could not be loaded. '
        'Select the task to retry."'
        in recovery
    )
    assert recovery.count("selectionRecoveryUsed = true;") == 1
    assert recovery.index("selectionRecoveryUsed = true;") < recovery.index(
        "button.click();"
    )

    for field in (
        "expected_index",
        "expected_request_id",
        "expected_source_path",
        "expected_task_id",
        "expected_target_path",
        "selected_task_matches_expected",
        "selected_task_title",
        "selected_task_status",
        "actual_paths",
        "actual_facts",
        "actual_status",
        "toolbar_hidden",
        "footer_hidden",
        "review_connected",
        "captured_review_connected",
        "task_card_count",
        "bridge_attempt",
    ):
        assert f"{field}:" in script
    retry_guard = script[script.index("if (\n        selected === button") :]
    retry_guard = retry_guard[: retry_guard.index(") {")]
    assert "selected === button" in retry_guard
    assert "initialReview.isConnected === false" in retry_guard
    assert "currentReview === null" in retry_guard
    assert (
        'selectedTaskStatus\n          === "Plan review could not be loaded. '
        'Select the task to retry."'
        in retry_guard
    )
    assert 'let bridgeStage = "open-plan-view";' in script
    assert 'bridgeStage = "get-plan-window";' in script
    assert (
        "diagnostic.row.task_id, summary.view_revision, 0, 256," in script
    )
    assert 'outcome: "success"' in script
    assert 'outcome: "error"' in script
    assert "summary_request_id: summary.request_id" in script
    assert "window_row_count: window.rows.length" in script
    assert "first_row: first === null ? null" in script
    error_receipt = script[script.index("const errorName = bridgeError?.name;") :]
    error_receipt = error_receipt[: error_receipt.index("};")]
    assert "bridgeError.message" not in error_receipt
    assert "stage: bridgeStage" in error_receipt
    assert "classification," in error_receipt
    assert "code:" in error_receipt
    for classification in (
        "bridge-transport",
        "bridge-command",
        "type-error",
        "unexpected",
    ):
        assert f'"{classification}"' in error_receipt



def test_selection_feedback_uses_public_operation_and_settlement_witness(
    tmp_path: Path,
) -> None:
    script = benchmark._headed_probe_script(
        "ui_mutate_plan_selection_click_feedback"
    )
    selection = script[script.index(
        '} else if (metric === "ui_mutate_plan_selection_click_feedback") {'
    ):]
    selection = selection[:selection.index(
        '} else if (metric === "ui_start_execution_click_feedback") {'
    )]

    assert "boxes[0]" not in selection
    assert "currentBoxes[1]" not in selection
    assert "initialWindow.rows.find" in selection
    assert 'typeof row.operation_id === "string"' in selection
    assert 'row.selection === "selected"' in selection
    assert "candidate.dataset.nodeId === targetRow.node_id" in selection
    assert "checkbox.disabled === false" in selection
    assert "checkbox.indeterminate === false" in selection
    assert "checkbox.checked === checked" in selection
    assert selection.index("warmupCheckbox.click();") < selection.index(
        'document.querySelector(".nami-plan-review")?.dataset.pending '
        '!== "selection"'
    )
    assert "warmupSummary.selection_revision !== initialSummary.selection_revision + 1" in selection
    assert 'warmupRow.selection !== "unselected"' in selection
    assert 'const elapsed = await timedClick(measuredCheckbox, "selection")' in selection
    assert "measuredSummary.selection_revision !== warmupSummary.selection_revision + 1" in selection
    assert 'measuredRow.selection !== "selected"' in selection
    assert "const repetitions = 6;" in script
    assert "return { samples };" in script

    helper_start = selection.index("const operationCheckbox = (checked) => {")
    helper_end = selection.index("\n    };", helper_start) + len("\n    };")
    helper = selection[helper_start:helper_end]
    warmup_start = selection.index("warmupCheckbox.click();")
    warmup_end = selection.index("\n    await until(", warmup_start)
    warmup_check = selection[warmup_start:warmup_end]
    probe = tmp_path / "selection-target.mjs"
    probe.write_text(
        """
const targetRow = { node_id: "operation" };
const checkbox = {
  checked: true, disabled: false, indeterminate: false, isConnected: true,
};
const operationRow = {
  dataset: { nodeId: "operation" }, isConnected: true,
  querySelector: () => checkbox,
};
const structuralRow = {
  dataset: { nodeId: "structure" }, isConnected: true,
  querySelector: () => ({ checked: true, disabled: false, indeterminate: false,
    isConnected: true }),
};
let currentReview = { querySelectorAll: () => [structuralRow, operationRow] };
const document = { querySelector: () => currentReview };
""" + helper + """
const results = [];
results.push(operationCheckbox(true) === checkbox);
checkbox.disabled = true;
results.push(operationCheckbox(true) === null);
checkbox.disabled = false;
checkbox.indeterminate = true;
results.push(operationCheckbox(true) === null);
checkbox.indeterminate = false;
checkbox.checked = false;
results.push(operationCheckbox(true) === null);
checkbox.checked = true;
operationRow.isConnected = false;
results.push(operationCheckbox(true) === null);
operationRow.isConnected = true;
checkbox.isConnected = false;
results.push(operationCheckbox(true) === null);
checkbox.isConnected = true;
currentReview = null;
results.push(operationCheckbox(true) === null);
currentReview = {
  dataset: { pending: "" },
  querySelectorAll: () => [structuralRow, operationRow],
};
function warmupAccepted(click) {
  const warmupCheckbox = { click };
  try {
""" + warmup_check + """
    return true;
  } catch (error) {
    return false;
  }
}
results.push(warmupAccepted(() => {}) === false);
results.push(warmupAccepted(() => { currentReview.dataset.pending = "selection"; }) === true);
console.log(JSON.stringify(results));
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ("node", str(probe)), capture_output=True, check=False, text=True, timeout=30
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout) == [True] * 9



def test_start_receipt_observer_registers_filters_and_removes_listener(
    tmp_path: Path,
) -> None:
    script = benchmark._headed_probe_script(
        "ui_confirm_execution_click_feedback"
    )
    start = script.index("  function observeStartReceipt(row) {")
    end = script.index("  async function openExecutionConfirmation(index) {", start)
    helper = script[start:end]
    probe = tmp_path / "start-receipt-observer.mjs"
    probe.write_text(
        """
const channel = new EventTarget();
const active = new Set();
let added = 0;
let removed = 0;
const add = channel.addEventListener.bind(channel);
const remove = channel.removeEventListener.bind(channel);
channel.addEventListener = (kind, listener) => {
  if (kind === "message") { added += 1; active.add(listener); }
  add(kind, listener);
};
channel.removeEventListener = (kind, listener) => {
  if (kind === "message" && active.delete(listener)) removed += 1;
  remove(kind, listener);
};
globalThis.chrome = { webview: channel };
const emit = (taskId) => {
  const event = new Event("message");
  Object.defineProperty(event, "data", { value: {
    completion_token: "3".repeat(32), generation: 0,
    kind: "namisync.command-completion.v1", phase: "completion",
    request_id: "2".repeat(32), response: {
      ok: true, request_id: "2".repeat(32),
      result: { request_id: "4".repeat(32), session_id: "5".repeat(32),
        task_id: taskId }, schema_version: 1,
    },
  }});
  channel.dispatchEvent(event);
};
"""
        + helper
        + """
const taskId = "task-" + "1".repeat(32);
let coexistingCalls = 0;
channel.addEventListener("message", () => { coexistingCalls += 1; });
const observation = observeStartReceipt({ task_id: taskId });
observation.start();
if (added !== 2 || active.size !== 2) throw new Error("listener was not registered");
emit("task-" + "9".repeat(32));
await Promise.resolve();
if (removed !== 0 || active.size !== 2) throw new Error("mismatch was not ignored");
emit(taskId);
const receipt = await observation.promise;
if (receipt.value.task_id !== taskId
    || receipt.value.request_id !== "4".repeat(32)
    || receipt.value.session_id !== "5".repeat(32)) {
  throw new Error("typed TaskStartView changed");
}
if (removed !== 1 || active.size !== 1) throw new Error("listener was not removed");
emit(taskId);
if (removed !== 1 || coexistingCalls !== 3) {
  throw new Error("coexisting listener or settled observer changed");
}
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ("node", str(probe)), capture_output=True, check=False, text=True, timeout=30
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr



@cache
def _frozen_fixture_manifests() -> dict[str, object]:
    return json.loads(AUTHORITY_PATH.read_bytes())["fixture_manifests"]



def _synthetic_fixture_manifests() -> dict[str, object]:
    return deepcopy(_frozen_fixture_manifests())



def _live_fixture_manifests() -> dict[str, object]:
    return {
        "base": build_fixture_manifest(information_heavy=False),
        "information-heavy": build_fixture_manifest(information_heavy=True),
    }


@pytest.mark.parametrize("information_heavy", (False, True))
def test_plan_fixture_recase_operations_have_genuine_prior_case(information_heavy: bool) -> None:
    artifact = build_plan_fixture(information_heavy=information_heavy)
    operations = artifact.plan.operations
    assert operations[3].kind is OperationKind.NOOP
    assert operations[3].target_rel_path == r"witness\0"
    assert operations[6].target_rel_path == r"witness\100"
    assert operations[12].kind is OperationKind.RECASE
    recased = [operation for operation in operations if operation.kind is OperationKind.RECASE]
    assert len(recased) == 16_667
    for operation in recased:
        target_parent, _, target_name = operation.target_rel_path.rpartition("\\")
        prior_parent, _, prior_name = operation.prior_target_rel_path.rpartition("\\")
        assert prior_parent == target_parent
        assert prior_name != target_name and prior_name.casefold() == target_name.casefold()
        assert operation.prior_target_expected == operation.source_expected



def test_plan_review_fixture_realizes_exact_counts_depth_duplicates_and_orders() -> None:
    manifests = _live_fixture_manifests()
    expected = _synthetic_fixture_manifests()
    for case in ("base", "information-heavy"):
        for field in manifests[case].keys() - {"artifact_digest", "plan_fingerprint"}:
            assert manifests[case][field] == expected[case][field]
    base = manifests["base"]
    heavy = manifests["information-heavy"]

    assert base["counts"] == {
        "operations": 100_000,
        "operation_rows": 100_000,
        "prior_rows": 32,
        "structural_group_ghost_rows": 20_000,
        "warnings": 0,
        "unique_warning_occurrences": 0,
        "repeated_warning_occurrences": 0,
        "projection_rows": 120_000,
    }
    assert heavy["counts"]["projection_rows"] == 240_000
    assert heavy["counts"]["unique_warning_occurrences"] == 100_000
    assert heavy["counts"]["repeated_warning_occurrences"] == 20_000
    assert base["depth"] == {"path": 32, "dependency": 32}
    assert heavy["depth"] == {"path": 32, "dependency": 32}
    assert base["selection_facts"] == heavy["selection_facts"] == {
        "destructive": {
            "destructive_operation_count": 49_998,
            "destructive_operation_counts": {
                "delete": 16_666,
                "move_update": 0,
                "trash": 16_665,
                "update": 16_667,
            },
            "irreversible_operation_count": 16_666,
            "irreversible_update_count": 0,
            "required_bytes": "9007200168568816",
            "selected_operations": 100_000,
        },
        "nondestructive": {
            "destructive_operation_count": 0,
            "destructive_operation_counts": {
                "delete": 0,
                "move_update": 0,
                "trash": 0,
                "update": 0,
            },
            "irreversible_operation_count": 0,
            "irreversible_update_count": 0,
            "required_bytes": "456905413",
            "selected_operations": 49_986,
            "user_deselected": 49_998,
        },
    }
    assert base["siblings"]["generated_directory_child_min"] == 5
    assert base["siblings"]["generated_directory_child_max"] == 6
    assert len(base["raw_key_witnesses"]["rows"]) == 15
    assert any(
        row["operation_id"] is None and row["size"] == 71 and row["mtime_ns"] is None
        for row in base["raw_key_witnesses"]["rows"]
    )



def test_plan_review_fixture_expected_orders_match_actual_sibling_sort() -> None:
    artifact = build_plan_fixture(information_heavy=False)
    projection = build_plan_projection(artifact.request.request_id, artifact)
    witnesses = _synthetic_fixture_manifests()["base"]["raw_key_witnesses"]
    assert build_fixture_manifest(information_heavy=False)["raw_key_witnesses"] == witnesses
    witness_ids = set(witnesses["canonical_ids"])

    for column in (PlanSortColumn.FILENAME, PlanSortColumn.SIZE, PlanSortColumn.MTIME):
        for direction in (SortDirection.ASCENDING, SortDirection.DESCENDING):
            ordered = sort_plan_projection(projection, column, direction)
            actual = [
                projection.nodes[source_position].operation_id
                or projection.nodes[source_position].node_id
                for source_position in ordered.ordered_source_positions
                if (
                    projection.nodes[source_position].operation_id
                    or projection.nodes[source_position].node_id
                )
                in witness_ids
            ]
            assert actual == witnesses["expected_orders"][f"{column.value}-{direction.value}"]



def test_plan_review_fixture_folder_sizes_match_independent_path_facts_and_survive_selection() -> None:
    """Finite GUI-M2 witness: one retained 120k fixture, no rescan or timing gate."""
    started = perf_counter()
    artifact = build_plan_fixture(information_heavy=False)
    projection = build_plan_projection(artifact.request.request_id, artifact)

    def stat_for(operation):
        return operation.intended or operation.source_expected or operation.target_expected or operation.prior_target_expected

    facts: dict[str, set[int]] = {}
    for operation in artifact.plan.operations:
        stat = stat_for(operation)
        if stat is None or getattr(stat.kind, "value", stat.kind) != "file":
            continue
        path = operation.target_rel_path.replace("/", "\\").casefold()
        facts.setdefault(path, set()).add(stat.size)

    known_facts = {path: next(iter(sizes)) for path, sizes in facts.items() if len(sizes) == 1}
    totals: dict[str, int] = {"": 0}
    for path, size in known_facts.items():
        parts = path.split("\\")[:-1]
        for index in range(len(parts) + 1):
            parent = "\\".join(parts[:index])
            totals[parent] = totals.get(parent, 0) + size

    folder_nodes = [
        node for node in projection.nodes
        if not node.row_kind.startswith("prior-") and (
            getattr(node, "is_directory", False) or node.row_kind == "folder"
        )
    ]
    assert folder_nodes
    for node in folder_nodes:
        expected = totals.get(node.rel_path_key.casefold().rstrip("\\"), 0)
        if expected > 2**63 - 1:
            assert node.size is None
            assert "overflow" in (node.notice or "")
        else:
            assert node.size == expected
    root = projection.nodes[0]
    assert root.size is None
    assert "overflow" in (root.notice or "")

    state = benchmark.make_plan_review_state(artifact)
    before = {
        node.node_id: node.size for node in state.projection.nodes
        if not node.row_kind.startswith("prior-") and (
            getattr(node, "is_directory", False) or node.row_kind == "folder"
        )
    }
    state.replace_selection(
        selected_operation_ids=frozenset(), exclusion_reasons={},
        selection_revision=1, selection_state="reviewing",
        requires_destructive_confirmation=False, irreversible_update_count=0,
        destructive_operation_count=0, irreversible_operation_count=0,
        destructive_operation_counts={"update": 0, "move_update": 0, "trash": 0, "delete": 0},
        required_bytes="0",
    )
    after = {
        node.node_id: node.size for node in state.projection.nodes
        if getattr(node, "is_directory", False) or node.row_kind == "folder"
    }
    assert after == before
    print(f"folder-size-witness-120k: {len(known_facts)} distinct files, {perf_counter() - started:.3f}s diagnostic")



def test_diagnostic_children_emit_distinct_actual_process_receipts(tmp_path: Path) -> None:
    receipts = []
    for ordinal in range(2):
        output = tmp_path / f"diagnostic-{ordinal}.json"
        launch_token = f"{ordinal + 1:032x}"
        subprocess.run(
            (
                sys.executable,
                str(RUNNER_PATH),
                "--diagnostic-child",
                "--launch-token",
                launch_token,
                "--output",
                str(output),
            ),
            cwd=REPOSITORY_ROOT,
            check=True,
            timeout=30,
        )
        receipt = json.loads(output.read_bytes())
        assert receipt["schema"] == benchmark.CHILD_RECEIPT_SCHEMA
        assert receipt["launch_token"] == launch_token
        assert receipt["process_identity"]["pid"] != os.getpid()
        assert receipt["samples"] == [
            {
                "correctness": {"operations": 12, "projection_rows": 16},
                "elapsed_ns": receipt["samples"][0]["elapsed_ns"],
                "iteration": 1,
                "retained_bytes": None,
            }
        ]
        receipts.append(receipt)

    assert receipts[0]["child_id"] != receipts[1]["child_id"]
    assert receipts[0]["process_identity"] != receipts[1]["process_identity"]


def test_current_rootless_plan_window_and_visible_folder_collapse() -> None:
    artifact = build_plan_fixture(information_heavy=True)
    state = benchmark.make_plan_review_state(artifact)
    assert state.window(expected_revision=0, offset=0, limit=256)["total"] == 239_999

    state.update(
        expected_revision=0, search_query="\u202ehostile", filters=frozenset(),
        sort_column=PlanSortColumn.PATH,
        sort_direction=SortDirection.ASCENDING,
        collapse_node_id=None, collapsed=None,
    )
    assert state.window(expected_revision=1, offset=0, limit=256)["total"] == 2

    state = benchmark.make_plan_review_state(artifact)
    prior = next(
        (index, state.projection.nodes[position])
        for index, position in enumerate(state.current_sequence.visible_positions)
        if state.projection.nodes[position].row_kind == "prior-group"
    )
    offset = prior[0] - 1  # the synthetic Plan root is excluded from public rows
    assert state.window(expected_revision=0, offset=offset, limit=1)["rows"][0]["node_id"] == prior[1].node_id
    changed = state.update(
        expected_revision=0, search_query="", filters=frozenset(),
        sort_column=PlanSortColumn.PATH,
        sort_direction=SortDirection.ASCENDING,
        collapse_node_id=prior[1].node_id, collapsed=True,
    )
    window = state.window(expected_revision=1, offset=offset, limit=256)
    assert changed["collapsed_count"] == 1
    assert len(window["rows"]) == 256
    assert window["rows"][0]["node_id"] == prior[1].node_id


def test_large_plan_task_snapshot_does_not_publish_an_outcome_map() -> None:
    artifact = build_plan_fixture(information_heavy=True)
    assert len(artifact.plan.operations) == 100_000
    session_id = "c2" * 16
    state = TaskPresentationState("task-" + "b1" * 16, session_id)
    observed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def population(value):
        if isinstance(value, dict):
            return 1 + sum(population(child) for child in value.values())
        if isinstance(value, (tuple, list)):
            return 1 + sum(population(child) for child in value)
        return 1

    first_population = None
    for sequence, operation in enumerate(artifact.plan.operations, 1):
        # Real public event projections exercise identity turnover across the
        # existing large corpus; task presentation must not retain its items.
        update = TaskEventUpdateView("event", session_event_view(Envelope(
            SessionId(session_id), sequence, observed_at, CORE_EVENT_SCHEMA_VERSION,
            ItemOutcome(str(operation.op_id), operation.kind,
                        operation.target_rel_path, Outcome.SUCCEEDED),
        )))
        state = state.advance(update, float(sequence))
        if first_population is None:
            first_population = population(asdict(state))
    assert population(asdict(state)) == first_population
    published = snapshot_task_drain_response_prefix(
        state.task_id, session_id, "d3" * 16, (),
        TaskSnapshotStage(state, None),
    )
    assert published.updates == ()
    assert published.snapshot == state.snapshot()
    assert published.snapshot["terminal_result"] is None
    assert not any(str(operation.op_id) in json.dumps(published.snapshot)
                   for operation in (artifact.plan.operations[0], artifact.plan.operations[-1]))


def test_selected_plan_memory_case_rejects_false_timing_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.performance import _child

    case = "projection_incremental_retained_memory_staging_overlap"
    metric = next(row for row in json.loads(CONTRACT_PATH.read_bytes())["metrics"] if row["id"] == case)
    monkeypatch.setattr(benchmark, "uuid4", lambda: SimpleNamespace(hex="a" * 32))
    monkeypatch.setattr(_child, "run_child", lambda *_args, **_kwargs: {
        "metric_id": case,
        "launch_token": "a" * 32,
        "fixture_case": metric["fixture_case"],
        "samples": [{
            "correctness": benchmark._current_correctness(metric),
            "elapsed_ns": 1,
            "retained_bytes": None,
        }],
    })
    with pytest.raises(RuntimeError, match="incomplete or false observation"):
        benchmark.run_case(case, output=tmp_path / "memory.json")
