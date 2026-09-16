"""Authority, fixture and corruption checks for the M1-7 scale gate."""

from __future__ import annotations

from copy import deepcopy
from functools import cache
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import zipfile

import pytest

import _plan_review_scale as scale
import plan_review_benchmark as benchmark
from plan_review_benchmark import (
    _require_installed_runtime,
    build_fixture_manifest,
    build_plan_fixture,
    canonical_sha256 as runner_canonical_sha256,
    git_blob_oid as runner_git_blob_oid,
)
from namisync.interfaces.web import drain as drain_module
from namisync.workflows.plan_projection import (
    PlanSortColumn,
    SortDirection,
    build_plan_projection,
    sort_plan_projection,
)


CONTRACT_PATH = Path(__file__).with_name("m1_7_plan_compact_contract.json")
LEGACY_CONTRACT_PATH = Path(__file__).with_name("m1_7_plan_contract.json")
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = REPOSITORY_ROOT / "tests" / "plan_review_benchmark.py"
AUTHORITY_PATH = CONTRACT_PATH.with_name("m1_7_plan_compact_authority.json")
MEASUREMENTS_PATH = CONTRACT_PATH.with_name("m1_7_plan_compact_measurements.json")


def _contract() -> dict[str, object]:
    value = json.loads(CONTRACT_PATH.read_bytes())
    assert type(value) is dict
    return value


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
        "ui_mutate_plan_selection_click_feedback", readiness=True
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
    assert "const repetitions = readiness ? 1 : 6;" in script
    assert "return { correctness: samples[0].correctness };" in script

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
        "ui_confirm_execution_click_feedback", readiness=True
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


def test_synthetic_fixture_manifests_are_isolated_from_live_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_generation(**_kwargs: object) -> None:
        raise AssertionError("synthetic authority invoked fixture generation")

    monkeypatch.setattr(benchmark, "build_fixture_manifest", reject_generation)
    monkeypatch.setattr(sys.modules[__name__], "build_fixture_manifest", reject_generation)
    first = _synthetic_fixture_manifests()
    first["base"]["counts"]["operations"] = 0
    second = _synthetic_fixture_manifests()
    assert second["base"]["counts"]["operations"] == 100_000
    assert first["base"] is not second["base"]
    assert _authority_inputs(_contract())["fixture_manifests"] == second


def _authority_inputs(contract: dict[str, object]) -> dict[str, object]:
    source_bytes = {
        path: (
            f"product:{path}\r\n".encode()
            if path in contract["authority"]["installed_paths"]
            else f"source:{path}".encode()
        )
        for path in contract["authority"]["source_paths"]
    }
    installed_bytes = {
        path: source_bytes[path]
        for path in contract["authority"]["installed_paths"]
    }
    source_git_blob_oids = {
        path: scale.git_blob_oid(content.replace(b"\r\n", b"\n"))
        for path, content in source_bytes.items()
    }
    wheel_buffer = io.BytesIO()
    with zipfile.ZipFile(wheel_buffer, "w") as archive:
        for path, content in installed_bytes.items():
            archive.writestr(path, content)
    headed_runtime = {
        "browser": {
            "executable_path": (
                r"C:\Program Files (x86)\Microsoft\EdgeWebView\Application"
                r"\150.0.4078.105\msedgewebview2.exe"
            ),
            "version": "150.0.4078.105",
        },
        "clr": {
            "module_path": (
                r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\clr.dll"
            ),
            "runtime_directory": (
                r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319"
            ),
            "runtime_version": "4.0.30319.42000",
            "system_version": "v4.0.30319",
        },
    }
    runtime_bytes = {
        role: (
            r"C:\runtime\python.exe"
            if role == "python_executable"
            else headed_runtime["browser"]["executable_path"]
            if role == "webview2_browser_executable"
            else headed_runtime["clr"]["module_path"]
            if role == "netfx_clr_module"
            else f"C:\\runtime\\{role}",
            f"runtime:{role}".encode(),
        )
        for role in contract["authority"]["runtime_roles"]
    }
    native_profile_bytes = scale.canonical_json_bytes(
        {
            "schema": "namisync-m1-7-native-profile-v1",
            "declared_reference": contract["profile"],
            "observed": {
                "operating_system": {"product": "Windows 11 Pro", "build": 26200},
                "cpu": {
                    "name": "13th Gen Intel(R) Core(TM) i7-13700K",
                    "physical_cores": 16,
                    "logical_processors": 24,
                },
                "memory": {"total_physical_bytes": 68_397_842_432},
                "disk": {
                    "model": "WD_BLACK SN850X 4000GB",
                    "bus_type": "NVMe",
                    "size_bytes": 4_000_787_030_016,
                },
                "power": {"ac_online": True},
                "python": {
                    "implementation": "CPython",
                    "version": "3.13.14",
                    "executable": r"C:\runtime\python.exe",
                },
                "sqlite": {"version": "3.50.4"},
                "runtime_dependencies": {
                    "bottle": "0.13.4",
                    "pythonnet": "3.1.0",
                    "pywebview": "6.2.1",
                    "xxhash": "3.8.1",
                },
                "workload": {"no_unrelated_sustained_workload": True},
            },
        }
    )
    return {
        "source_bytes": source_bytes,
        "source_git_blob_oids": source_git_blob_oids,
        "installed_bytes": installed_bytes,
        "installed_wheel_name": "namisync-0.1.0-py3-none-any.whl",
        "installed_wheel_bytes": wheel_buffer.getvalue(),
        "runtime_bytes": runtime_bytes,
        "native_profile_bytes": native_profile_bytes,
        "fixture_manifests": _synthetic_fixture_manifests(),
        "headed_runtime": headed_runtime,
    }


def _authority(contract: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    inputs = _authority_inputs(contract)
    authority = {
        "contract_sha256": scale.CONTRACT_SHA256,
        "fixture_manifests": deepcopy(inputs["fixture_manifests"]),
        "headed_runtime": deepcopy(inputs["headed_runtime"]),
        "installed_files": {
            path: {
                "installed_sha256": hashlib.sha256(content).hexdigest(),
                "source_sha256": hashlib.sha256(
                    inputs["source_bytes"][path]
                ).hexdigest(),
                "wheel_member_sha256": hashlib.sha256(content).hexdigest(),
            }
            for path, content in inputs["installed_bytes"].items()
        },
        "installed_wheel": {
            "byte_length": len(inputs["installed_wheel_bytes"]),
            "name": inputs["installed_wheel_name"],
            "sha256": hashlib.sha256(inputs["installed_wheel_bytes"]).hexdigest(),
        },
        "native_profile": {
            "byte_length": len(inputs["native_profile_bytes"]),
            "sha256": hashlib.sha256(inputs["native_profile_bytes"]).hexdigest(),
            "utf8_hex": inputs["native_profile_bytes"].hex(),
        },
        "runtime_files": {
            role: {"path": path, "sha256": hashlib.sha256(content).hexdigest()}
            for role, (path, content) in inputs["runtime_bytes"].items()
        },
        "schema": scale.AUTHORITY_SCHEMA,
        "source_files": {
            path: {
                "git_blob_oid": inputs["source_git_blob_oids"][path],
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for path, content in inputs["source_bytes"].items()
        },
    }
    return authority, inputs


def _artifact(
    contract: dict[str, object], authority: dict[str, object]
) -> tuple[dict[str, object], bytes]:
    children = []
    process_seed = 10_000
    identity_seed = 1
    for metric in contract["metrics"]:
        sampling = contract["sampling"][metric["sample_kind"]]
        for child_ordinal in range(sampling["fresh_children"]):
            samples = []
            for iteration in range(1, sampling["samples_per_child"] + 1):
                value = 10_000 + child_ordinal * 100 + iteration
                samples.append(
                    {
                        "correctness": deepcopy(metric["correctness"]),
                        "elapsed_ns": value if "budget_ns" in metric else None,
                        "iteration": iteration,
                        "retained_bytes": value if "budget_bytes" in metric else None,
                    }
                )
            receipt = {
                "child_id": f"{identity_seed:032x}",
                "fixture_case": metric["fixture_case"],
                "headed_fixture": (
                    _synthetic_headed_fixture(contract, metric, identity_seed)
                    if metric["surface"] == "installed-headed"
                    else None
                ),
                "headed_runtime": (
                    deepcopy(authority["headed_runtime"])
                    if metric["surface"] == "installed-headed"
                    else None
                ),
                "launch_token": f"{identity_seed + 1_000_000:032x}",
                "metric_id": metric["id"],
                "process_identity": {
                    "creation_filetime_100ns": 20_000_000 + identity_seed,
                    "pid": process_seed + identity_seed,
                },
                "sample_kind": metric["sample_kind"],
                "samples": samples,
                "schema": scale.CHILD_RECEIPT_SCHEMA,
            }
            children.append(
                {"receipt": receipt, "receipt_sha256": scale.canonical_sha256(receipt)}
            )
            identity_seed += 1
    authority_bytes = scale.canonical_json_bytes(authority)
    return (
        {
            "authority_receipt": {
                "byte_length": len(authority_bytes),
                "git_blob_oid": scale.git_blob_oid(authority_bytes),
                "sha256": hashlib.sha256(authority_bytes).hexdigest(),
            },
            "children": children,
            "contract_sha256": scale.CONTRACT_SHA256,
            "fixture_manifest_sha256": {
                name: scale.canonical_sha256(manifest)
                for name, manifest in authority["fixture_manifests"].items()
            },
            "native_profile_sha256": authority["native_profile"]["sha256"],
            "schema": scale.RAW_ARTIFACT_SCHEMA,
        },
        authority_bytes,
    )


def _synthetic_headed_fixture(
    contract: dict[str, object],
    metric: dict[str, object],
    identity_seed: int,
) -> dict[str, object]:
    specification = contract["headed_fixture"]
    count = (
        specification["fresh_execution_plan_count"][metric["sample_kind"]]
        if metric["id"] in specification["fresh_execution_metric_ids"]
        else specification["default_published_plan_count"]
    )
    rows = []
    for ordinal in range(count):
        row_seed = identity_seed * 10 + ordinal
        request_id = f"{row_seed + 1_000_000:032x}"
        task_id = f"task-{row_seed:032x}"
        plan_session_id = f"{row_seed + 2_000_000:032x}"
        source_path = rf"C:\m1-7\{identity_seed}\{ordinal}\source"
        target_path = rf"D:\m1-7\{identity_seed}\{ordinal}\target"
        rows.append({
            "execution_unused": True,
            "initial_view_settlement": {
                "first_row": {
                    "node_id": _synthetic_plan_root_node_id(request_id),
                    "operation_id": None,
                    "visible_index": 0,
                },
                "open_disposition": "opened",
                "plan_session_id": plan_session_id,
                "request_id": request_id,
                "source_path": source_path,
                "target_path": target_path,
                "task_id": task_id,
                "view_revision": 0,
                "window_disposition": "current",
                "window_limit": 256,
                "window_offset": 0,
                "window_row_count": 256,
                "window_total": 120_000,
                "window_view_revision": 0,
            },
            "plan_session_id": plan_session_id,
            "request_id": request_id,
            "session_released": True,
            "session_state": "completed",
            "source_path": source_path,
            "target_path": target_path,
            "task_id": task_id,
            "task_kind": "sync-plan",
        })
    return {"published_plan_count": count, "rows": rows}


def _synthetic_plan_root_node_id(request_id: str) -> str:
    digest = hashlib.blake2b(digest_size=16, person=b"NamiSyncNodeV1")
    for value in ("plan", request_id, ""):
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return f"node-{digest.hexdigest()}"


def _readiness(
    contract: dict[str, object], authority: dict[str, object]
) -> tuple[dict[str, object], bytes]:
    plan = [
        ("installed-headed", [contract["readiness"]["headed_metric_ids"][0]]),
        ("component", list(contract["readiness"]["component_metric_ids"])),
        ("component", [contract["readiness"]["memory_metric_id"]]),
        *(
            ("installed-headed", [metric_id])
            for metric_id in contract["readiness"]["headed_metric_ids"][1:]
        ),
    ]
    metrics = {metric["id"]: metric for metric in contract["metrics"]}
    children = []
    coverage = []
    for ordinal, (surface, metric_ids) in enumerate(plan, start=1):
        metric = metrics[metric_ids[0]]
        receipt = {
            "child_id": f"{ordinal:032x}",
            "correctness": {
                metric_id: deepcopy(metrics[metric_id]["correctness"])
                for metric_id in metric_ids
            },
            "headed_fixture": (
                _synthetic_headed_fixture(contract, metric, ordinal)
                if surface == "installed-headed"
                else None
            ),
            "headed_runtime": (
                deepcopy(authority["headed_runtime"])
                if surface == "installed-headed"
                else None
            ),
            "launch_token": f"{ordinal + 1_000_000:032x}",
            "metric_ids": metric_ids,
            "process_identity": {
                "creation_filetime_100ns": 30_000_000 + ordinal,
                "pid": 20_000 + ordinal,
            },
            "schema": scale.READINESS_CHILD_SCHEMA,
            "surface": surface,
        }
        children.append({
            "receipt": receipt,
            "receipt_sha256": scale.canonical_sha256(receipt),
        })
        coverage.extend(metric_ids)
    authority_bytes = scale.canonical_json_bytes(authority)
    return ({
        "authority_sha256": hashlib.sha256(authority_bytes).hexdigest(),
        "children": children,
        "contract_sha256": scale.CONTRACT_SHA256,
        "coverage": coverage,
        "schema": scale.READINESS_SCHEMA,
    }, authority_bytes)


def _rehash_child(wrapper: dict[str, object]) -> None:
    wrapper["receipt_sha256"] = scale.canonical_sha256(wrapper["receipt"])


def _validate_artifact(
    contract: dict[str, object],
    authority: dict[str, object],
    authority_bytes: bytes,
    raw: dict[str, object],
):
    return scale.validate_artifact(
        contract,
        authority,
        authority_bytes,
        raw["authority_receipt"]["git_blob_oid"],
        raw,
    )


def test_plan_review_scale_contract_has_independent_complete_fixed_table() -> None:
    contract = _contract()

    scale._validate_contract(contract)
    assert contract["schema"] == scale.CONTRACT_SCHEMA
    assert scale.canonical_sha256(contract) == scale.CONTRACT_SHA256
    assert len(contract["metrics"]) == 35
    assert contract["sampling"]["warm"] == {
        "fresh_children": 5,
        "samples_per_child": 6,
    }
    metric_ids = {metric["id"] for metric in contract["metrics"]}
    assert {
        "ui_get_plan_window_one_row_receipt",
        "ui_confirm_execution_click_feedback",
        "ui_start_execution_nondestructive_click_feedback",
        "ui_control_pause_receipt",
        "ui_control_resume_receipt",
        "ui_control_cancel_receipt",
        "selection_freeze_normalize_100000",
    } <= metric_ids
    assert all(metric["tier"] == 2 for metric in contract["metrics"])
    readiness = contract["readiness"]
    assert readiness["child_count"] == 15
    assert readiness["headed_metric_ids"][0] == (
        "ui_mutate_plan_selection_click_feedback"
    )
    assert set(readiness["component_metric_ids"]) | {
        readiness["memory_metric_id"], *readiness["headed_metric_ids"]
    } == metric_ids


def test_readiness_validates_exact_15_child_35_case_untimed_coverage() -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    readiness, authority_bytes = _readiness(contract, authority)

    scale.validate_readiness(contract, authority, authority_bytes, readiness)

    assert len(readiness["children"]) == 15
    assert len(readiness["coverage"]) == 35
    assert readiness["coverage"][0] == "ui_mutate_plan_selection_click_feedback"
    encoded = scale.canonical_json_bytes(readiness)
    assert b'"samples"' not in encoded
    assert b'"elapsed_ns"' not in encoded
    assert b'"retained_bytes"' not in encoded


def test_readiness_uses_longer_watchdog_only_for_component_aggregate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    readiness, authority_bytes = _readiness(contract, authority)
    authority_path = tmp_path / "authority.json"
    authority_path.write_bytes(authority_bytes)
    receipts = iter(readiness["children"])
    timeouts: list[int] = []

    monkeypatch.setattr(benchmark, "_require_installed_runtime", lambda _root: None)
    monkeypatch.setattr(benchmark, "build_authority", lambda **_kwargs: authority)

    def child(
        command: list[str],
        *,
        benchmark_root: Path,
        label: str,
        timeout_seconds: int = 300,
    ) -> None:
        del benchmark_root, label
        timeouts.append(timeout_seconds)
        receipt = deepcopy(next(receipts)["receipt"])
        receipt["launch_token"] = command[command.index("--launch-token") + 1]
        benchmark._write_canonical_json(
            Path(command[command.index("--output") + 1]), receipt
        )

    monkeypatch.setattr(benchmark, "_run_child_command", child)
    benchmark.run_readiness(
        contract_path=CONTRACT_PATH,
        authority_path=authority_path,
        source_root=tmp_path,
        installed_root=tmp_path,
        installed_wheel=tmp_path / "candidate.whl",
        benchmark_root=tmp_path / "run",
        output=tmp_path / "readiness.json",
        no_unrelated_sustained_workload=True,
    )

    assert timeouts == [300, 600, *([300] * 13)]


def test_child_process_watchdog_defaults_to_measurement_boundary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    timeouts = []

    def run(*_args: object, **kwargs: object) -> object:
        timeouts.append(kwargs["timeout"])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    benchmark._run_child_command(
        ["measurement-child"], benchmark_root=tmp_path, label="measurement"
    )
    benchmark._run_child_command(
        ["readiness-component"],
        benchmark_root=tmp_path,
        label="component",
        timeout_seconds=600,
    )

    assert timeouts == [300, 600]


@pytest.mark.parametrize("corruption", ["missing", "duplicate", "tampered"])
def test_readiness_refuses_incomplete_duplicate_and_tampered_children(
    corruption: str,
) -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    readiness, authority_bytes = _readiness(contract, authority)
    changed = deepcopy(readiness)
    if corruption == "missing":
        changed["children"].pop()
    elif corruption == "duplicate":
        changed["children"][1] = deepcopy(changed["children"][0])
    else:
        changed["children"][0]["receipt"]["correctness"] = {}
        changed["children"][0]["receipt_sha256"] = scale.canonical_sha256(
            changed["children"][0]["receipt"]
        )

    with pytest.raises(ValueError, match="readiness"):
        scale.validate_readiness(contract, authority, authority_bytes, changed)


def test_failed_readiness_preserves_first_accepted_child(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    readiness, authority_bytes = _readiness(contract, authority)
    authority_path = tmp_path / "authority.json"
    authority_path.write_bytes(authority_bytes)
    benchmark_root = tmp_path / "run"
    output = tmp_path / "readiness.json"
    calls = 0
    timeouts: list[int] = []

    monkeypatch.setattr(benchmark, "_require_installed_runtime", lambda _root: None)
    monkeypatch.setattr(benchmark, "build_authority", lambda **_kwargs: authority)

    def child(
        command: list[str],
        *,
        benchmark_root: Path,
        label: str,
        timeout_seconds: int = 300,
    ) -> None:
        nonlocal calls
        calls += 1
        timeouts.append(timeout_seconds)
        if calls == 2:
            raise subprocess.TimeoutExpired(command, timeout_seconds)
        receipt = deepcopy(readiness["children"][0]["receipt"])
        receipt["launch_token"] = command[command.index("--launch-token") + 1]
        child_output = Path(command[command.index("--output") + 1])
        benchmark._write_canonical_json(child_output, receipt)

    monkeypatch.setattr(benchmark, "_run_child_command", child)

    with pytest.raises(subprocess.TimeoutExpired):
        benchmark.run_readiness(
            contract_path=CONTRACT_PATH,
            authority_path=authority_path,
            source_root=tmp_path,
            installed_root=tmp_path,
            installed_wheel=tmp_path / "candidate.whl",
            benchmark_root=benchmark_root,
            output=output,
            no_unrelated_sustained_workload=True,
        )

    collection_path = benchmark_root / "readiness.collection.json"
    collection = json.loads(collection_path.read_bytes())
    assert not output.exists()
    assert len(collection["accepted"]) == 1
    assert collection["next_or_failed"]["status"] == "failed"
    assert collection["next_or_failed"]["child_ordinal"] == 1
    assert collection["next_or_failed"]["error_class"] == "TimeoutExpired"
    assert timeouts == [300, 600]
    scale.validate_collection_index(
        contract, authority_bytes, b"", collection, benchmark_root
    )


def test_interruption_after_readiness_receipt_uses_first_unaccepted_attempt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    readiness, authority_bytes = _readiness(contract, authority)
    authority_path = tmp_path / "authority.json"
    authority_path.write_bytes(authority_bytes)
    benchmark_root = tmp_path / "run"
    original_publish = benchmark._publish_collection_index
    publications = 0

    monkeypatch.setattr(benchmark, "_require_installed_runtime", lambda _root: None)
    monkeypatch.setattr(benchmark, "build_authority", lambda **_kwargs: authority)

    def child(
        command: list[str],
        *,
        benchmark_root: Path,
        label: str,
        timeout_seconds: int = 300,
    ) -> None:
        del timeout_seconds
        receipt = deepcopy(readiness["children"][0]["receipt"])
        receipt["launch_token"] = command[command.index("--launch-token") + 1]
        benchmark._write_canonical_json(
            Path(command[command.index("--output") + 1]), receipt
        )

    def publish(path: Path, **kwargs: object) -> None:
        nonlocal publications
        publications += 1
        if publications == 2:
            raise KeyboardInterrupt
        original_publish(path, **kwargs)

    monkeypatch.setattr(benchmark, "_run_child_command", child)
    monkeypatch.setattr(benchmark, "_publish_collection_index", publish)

    with pytest.raises(KeyboardInterrupt):
        benchmark.run_readiness(
            contract_path=CONTRACT_PATH,
            authority_path=authority_path,
            source_root=tmp_path,
            installed_root=tmp_path,
            installed_wheel=tmp_path / "candidate.whl",
            benchmark_root=benchmark_root,
            output=tmp_path / "readiness.json",
            no_unrelated_sustained_workload=True,
        )

    collection = json.loads(
        (benchmark_root / "readiness.collection.json").read_bytes()
    )
    assert len(collection["accepted"]) == 1
    assert collection["next_or_failed"] == {
        "case_id": "component",
        "child_ordinal": 1,
        "error": "KeyboardInterrupt",
        "error_class": "KeyboardInterrupt",
        "error_truncated": False,
        "launch_token": collection["next_or_failed"]["launch_token"],
        "status": "failed",
    }
    scale.validate_collection_index(
        contract, authority_bytes, b"", collection, benchmark_root
    )


def test_gate_refuses_invalid_readiness_before_child_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    readiness, authority_bytes = _readiness(contract, authority)
    readiness["coverage"] = readiness["coverage"][:-1]
    authority_path = tmp_path / "authority.json"
    readiness_path = tmp_path / "readiness.json"
    authority_path.write_bytes(authority_bytes)
    readiness_path.write_bytes(scale.canonical_json_bytes(readiness))
    monkeypatch.setattr(benchmark, "_require_installed_runtime", lambda _root: None)
    monkeypatch.setattr(benchmark, "build_authority", lambda **_kwargs: authority)
    monkeypatch.setattr(
        benchmark,
        "_run_child_command",
        lambda *_args, **_kwargs: pytest.fail("measurement child launched"),
    )

    with pytest.raises(RuntimeError, match="readiness coverage"):
        benchmark.run_gate(
            contract_path=CONTRACT_PATH,
            authority_path=authority_path,
            readiness_path=readiness_path,
            source_root=tmp_path,
            installed_root=tmp_path,
            installed_wheel=tmp_path / "candidate.whl",
            benchmark_root=tmp_path / "run",
            output=tmp_path / "measurements.json",
            no_unrelated_sustained_workload=True,
        )


def test_failed_measurement_preserves_validated_child_and_rejects_corruption(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    raw, authority_bytes = _artifact(contract, authority)
    readiness, _ = _readiness(contract, authority)
    readiness_bytes = scale.canonical_json_bytes(readiness)
    authority_path = tmp_path / "authority.json"
    readiness_path = tmp_path / "readiness.json"
    authority_path.write_bytes(authority_bytes)
    readiness_path.write_bytes(readiness_bytes)
    benchmark_root = tmp_path / "run"
    calls = 0

    monkeypatch.setattr(benchmark, "_require_installed_runtime", lambda _root: None)
    monkeypatch.setattr(benchmark, "build_authority", lambda **_kwargs: authority)

    def child(command: list[str], *, benchmark_root: Path, label: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("second measurement child failed")
        receipt = deepcopy(raw["children"][0]["receipt"])
        receipt["launch_token"] = command[command.index("--launch-token") + 1]
        benchmark._write_canonical_json(
            Path(command[command.index("--output") + 1]), receipt
        )

    monkeypatch.setattr(benchmark, "_run_child_command", child)

    with pytest.raises(RuntimeError, match="second measurement child failed"):
        benchmark.run_gate(
            contract_path=CONTRACT_PATH,
            authority_path=authority_path,
            readiness_path=readiness_path,
            source_root=tmp_path,
            installed_root=tmp_path,
            installed_wheel=tmp_path / "candidate.whl",
            benchmark_root=benchmark_root,
            output=tmp_path / "measurements.json",
            no_unrelated_sustained_workload=True,
        )

    collection = json.loads(
        (benchmark_root / "measurement.collection.json").read_bytes()
    )
    assert len(collection["accepted"]) == 1
    scale.validate_collection_index(
        contract, authority_bytes, readiness_bytes, collection, benchmark_root
    )
    reused_attempt = deepcopy(collection)
    reused_attempt["next_or_failed"]["launch_token"] = (
        reused_attempt["accepted"][0]["launch_token"]
    )
    with pytest.raises(ValueError, match="attempt launch is reused"):
        scale.validate_collection_index(
            contract,
            authority_bytes,
            readiness_bytes,
            reused_attempt,
            benchmark_root,
        )
    receipt_path = benchmark_root / collection["accepted"][0]["receipt_path"]
    receipt_bytes = receipt_path.read_bytes()
    receipt_path.unlink()
    with pytest.raises(ValueError, match="receipt is unavailable"):
        scale.validate_collection_index(
            contract, authority_bytes, readiness_bytes, collection, benchmark_root
        )
    receipt_path.write_bytes(receipt_bytes)
    duplicate = deepcopy(collection)
    duplicate_item = deepcopy(duplicate["accepted"][0])
    duplicate_item["child_ordinal"] = 1
    duplicate["accepted"].append(duplicate_item)
    with pytest.raises(ValueError, match="collection member identity"):
        scale.validate_collection_index(
            contract, authority_bytes, readiness_bytes, duplicate, benchmark_root
        )
    receipt_path.write_bytes(receipt_path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="receipt hash"):
        scale.validate_collection_index(
            contract, authority_bytes, readiness_bytes, collection, benchmark_root
        )
    with pytest.raises(ValueError, match="artifact shape"):
        scale.validate_artifact(
            contract, authority, authority_bytes, "0" * 40, collection
        )


def test_plan_review_fixture_realizes_exact_counts_depth_duplicates_and_orders() -> None:
    manifests = _live_fixture_manifests()
    expected = _synthetic_fixture_manifests()
    for case in ("base", "information-heavy"):
        for field in ("counts", "raw_key_witnesses", "retained_representation"):
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
        row["operation_id"] is None and row["size"] is None and row["mtime_ns"] is None
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


def test_validator_hash_and_p95_oracles_are_independent_of_runner() -> None:
    value = {"unicode": "Straße\u202e", "values": [3, 1, 2]}
    samples = list(range(30))

    assert scale.canonical_sha256(value) == runner_canonical_sha256(value)
    assert scale.git_blob_oid(b"source bytes") == runner_git_blob_oid(b"source bytes")
    assert scale.nearest_rank_p95(samples) == 28


def test_validator_keeps_protected_legacy_contract_and_authority_valid() -> None:
    contract = json.loads(LEGACY_CONTRACT_PATH.read_bytes())
    authority_path = LEGACY_CONTRACT_PATH.with_name("m1_7_plan_authority.json")
    authority = json.loads(authority_path.read_bytes())

    scale._validate_contract(contract)
    scale._validate_authority(contract, authority)

    raw = json.loads(
        LEGACY_CONTRACT_PATH.with_name("m1_7_plan_measurements.json").read_bytes()
    )
    with pytest.raises(ValueError, match="exceeds its fixed budget"):
        scale.validate_artifact(
            contract,
            authority,
            authority_path.read_bytes(),
            raw["authority_receipt"]["git_blob_oid"],
            raw,
        )


def test_validator_refuses_cross_family_authority() -> None:
    compact_contract = _contract()
    legacy_authority = json.loads(
        LEGACY_CONTRACT_PATH.with_name("m1_7_plan_authority.json").read_bytes()
    )

    with pytest.raises(ValueError, match="authority contract"):
        scale._validate_authority(compact_contract, legacy_authority)


def test_validator_refuses_cross_family_raw_artifact() -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    raw, authority_bytes = _artifact(contract, authority)
    raw["schema"] = scale.LEGACY_RAW_ARTIFACT_SCHEMA

    with pytest.raises(ValueError, match="artifact schema"):
        _validate_artifact(contract, authority, authority_bytes, raw)


def test_current_runner_refuses_to_freeze_legacy_representation(
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="cannot freeze legacy"):
        benchmark.build_authority(
            contract_path=LEGACY_CONTRACT_PATH,
            source_root=REPOSITORY_ROOT,
            installed_root=tmp_path,
            installed_wheel=tmp_path / "missing.whl",
            benchmark_root=tmp_path,
            no_unrelated_sustained_workload=True,
        )


def test_source_authority_keeps_raw_bytes_distinct_from_git_filtered_identity() -> None:
    content = b"first\r\nsecond\r\n"

    filtered = scale._git_filtered_blob_oid(
        REPOSITORY_ROOT,
        "tests/plan_review_benchmark.py",
        content,
    )

    assert filtered == scale.git_blob_oid(b"first\nsecond\n")
    assert filtered != scale.git_blob_oid(content)


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
        assert receipt["schema"] == scale.CHILD_RECEIPT_SCHEMA
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


def test_gate_refuses_a_hashed_install_that_is_not_the_loaded_package(
    tmp_path: Path,
) -> None:
    installed_root = tmp_path / "Lib" / "site-packages"
    package = installed_root / "namisync"
    package.mkdir(parents=True)
    (package / "__init__.py").write_bytes(b'__version__ = "0.test"\n')
    metadata = installed_root / "namisync-0.test.dist-info"
    metadata.mkdir()
    (metadata / "RECORD").write_bytes(b"namisync/__init__.py,,\n")

    with pytest.raises(RuntimeError, match="did not import NamiSync"):
        _require_installed_runtime(installed_root)


def test_committed_source_verifier_accepts_exact_clean_head(
    tmp_path: Path,
) -> None:
    contract = _contract()
    authority, inputs = _authority(contract)
    raw, authority_bytes = _artifact(contract, authority)
    source_root = tmp_path / "repository"
    source_root.mkdir()
    (source_root / ".gitattributes").write_text("* text eol=lf\n", encoding="utf-8")
    for relative, content in inputs["source_bytes"].items():
        path = source_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    contract_path = source_root / "tests" / "interfaces" / "web" / CONTRACT_PATH.name
    authority_path = source_root / contract["artifacts"]["authority"]
    raw_path = source_root / contract["artifacts"]["measurements"]
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    authority_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_bytes(CONTRACT_PATH.read_bytes())
    authority_path.write_bytes(authority_bytes)
    raw_path.write_bytes(scale.canonical_json_bytes(raw))
    commands = (
        ("git", "init", "--quiet"),
        ("git", "add", "."),
        (
            "git", "-c", "user.name=M1-7 Validator", "-c",
            "user.email=m1-7@example.invalid", "commit", "--quiet", "-m", "fixture",
        ),
    )
    for command in commands:
        subprocess.run(command, cwd=source_root, check=True, timeout=30)

    scale.validate_committed_source_workspace(
        contract,
        authority,
        source_root,
        contract_path=contract_path,
        authority_path=authority_path,
        raw_path=raw_path,
        raw=raw,
    )
    changed_path = source_root / contract["authority"]["source_paths"][0]
    changed_path.write_bytes(changed_path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="physical bytes changed"):
        scale.validate_committed_source_workspace(
            contract,
            authority,
            source_root,
            contract_path=contract_path,
            authority_path=authority_path,
            raw_path=raw_path,
            raw=raw,
        )


def test_real_plan_review_artifacts_use_terminal_validator_when_present() -> None:
    if not (AUTHORITY_PATH.exists() and MEASUREMENTS_PATH.exists()):
        pytest.skip("M1-7 authority and measurement artifacts are not frozen yet")
    readiness_value = os.environ.get("NAMISYNC_M1_7_READINESS_PATH")
    if readiness_value is None:
        pytest.skip("M1-7 readiness artifact path is not configured")
    readiness_path = Path(readiness_value)
    assert readiness_path.is_file()
    authority = json.loads(AUTHORITY_PATH.read_bytes())
    python_executable = Path(
        authority["runtime_files"]["python_executable"]["path"]
    )
    installed_root = python_executable.parent.parent / "Lib" / "site-packages"
    installed_wheel = (
        REPOSITORY_ROOT / "build" / "m1-7" / "inputs"
        / authority["installed_wheel"]["name"]
    )
    assert installed_root.is_dir() and installed_wheel.is_file()

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        (
            str(python_executable), str(Path(scale.__file__).resolve()),
            "--contract", str(CONTRACT_PATH),
            "--authority", str(AUTHORITY_PATH),
            "--readiness", str(readiness_path),
            "--measurements", str(MEASUREMENTS_PATH),
            "--source-root", str(REPOSITORY_ROOT),
            "--installed-root", str(installed_root),
            "--installed-wheel", str(installed_wheel),
        ),
        cwd=REPOSITORY_ROOT / "build" / "m1-7" / "evidence",
        capture_output=True,
        check=False,
        env=environment,
        text=True,
        timeout=300,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_plan_review_scale_validates_actual_authority_bytes() -> None:
    contract = _contract()
    authority, inputs = _authority(contract)

    scale.validate_authority_bytes(contract, authority, **inputs)


@pytest.mark.parametrize(
    ("population", "message"),
    [
        ("source_bytes", "source population"),
        ("installed_bytes", "installed population"),
        ("runtime_bytes", "runtime population"),
    ],
)
def test_plan_review_scale_refuses_unlisted_actual_paths(population: str, message: str) -> None:
    contract = _contract()
    authority, inputs = _authority(contract)
    inputs = deepcopy(inputs)
    if population == "runtime_bytes":
        inputs[population]["unlisted"] = (r"C:\runtime\unlisted", b"unlisted")
    else:
        inputs[population]["unlisted.py"] = b"unlisted"

    with pytest.raises(ValueError, match=message):
        scale.validate_authority_bytes(contract, authority, **inputs)


def test_plan_review_scale_refuses_well_formed_wrong_hashes_and_runtime() -> None:
    contract = _contract()
    authority, inputs = _authority(contract)
    wrong = deepcopy(authority)
    source_path = next(iter(wrong["source_files"]))
    wrong["source_files"][source_path]["sha256"] = "a" * 64
    with pytest.raises(ValueError, match="source bytes"):
        scale.validate_authority_bytes(contract, wrong, **inputs)

    wrong = deepcopy(inputs)
    role = next(iter(wrong["runtime_bytes"]))
    path, _content = wrong["runtime_bytes"][role]
    wrong["runtime_bytes"][role] = (path, b"changed runtime")
    with pytest.raises(ValueError, match="runtime bytes"):
        scale.validate_authority_bytes(contract, authority, **wrong)


def test_plan_review_scale_refuses_self_consistent_but_mismatched_install() -> None:
    contract = _contract()
    authority, inputs = _authority(contract)
    wrong_inputs = deepcopy(inputs)
    wrong_authority = deepcopy(authority)
    path = next(iter(wrong_inputs["installed_bytes"]))
    changed = b"different installed product bytes\n"
    wrong_inputs["installed_bytes"][path] = changed
    wrong_authority["installed_files"][path]["installed_sha256"] = (
        hashlib.sha256(changed).hexdigest()
    )

    with pytest.raises(ValueError, match="source, wheel and installed"):
        scale.validate_authority_bytes(
            contract, wrong_authority, **wrong_inputs
        )


def test_plan_review_scale_refuses_false_headed_runtime_identity() -> None:
    contract = _contract()
    authority, inputs = _authority(contract)
    authority["headed_runtime"]["browser"]["version"] = "149.0.0.0"
    inputs["headed_runtime"]["browser"]["version"] = "149.0.0.0"

    with pytest.raises(ValueError, match="WebView2 runtime identity"):
        scale.validate_authority_bytes(contract, authority, **inputs)


def test_plan_review_scale_refuses_profile_bound_to_another_python_runtime() -> None:
    contract = _contract()
    authority, inputs = _authority(contract)
    profile = json.loads(inputs["native_profile_bytes"])
    profile["observed"]["python"]["executable"] = r"C:\runtime\other-python.exe"
    profile_bytes = scale.canonical_json_bytes(profile)
    authority["native_profile"] = {
        "byte_length": len(profile_bytes),
        "sha256": hashlib.sha256(profile_bytes).hexdigest(),
        "utf8_hex": profile_bytes.hex(),
    }
    inputs["native_profile_bytes"] = profile_bytes

    with pytest.raises(ValueError, match="profile runtime"):
        scale.validate_authority_bytes(contract, authority, **inputs)


@pytest.mark.parametrize(
    ("path", "wrong_value"),
    [
        (("operating_system", "build"), 26_201),
        (("cpu", "logical_processors"), 23),
        (("memory", "total_physical_bytes"), 64 * 1024**3),
        (("disk", "model"), "another disk"),
        (("power", "ac_online"), False),
        (("python", "version"), "3.13.13"),
        (("sqlite", "version"), "3.49.0"),
        (("workload", "no_unrelated_sustained_workload"), False),
    ],
)
def test_plan_review_scale_refuses_canonical_but_false_native_profile(
    path: tuple[str, str], wrong_value: object
) -> None:
    contract = _contract()
    authority, inputs = _authority(contract)
    profile = json.loads(inputs["native_profile_bytes"])
    profile["observed"][path[0]][path[1]] = wrong_value
    profile_bytes = scale.canonical_json_bytes(profile)
    authority["native_profile"] = {
        "byte_length": len(profile_bytes),
        "sha256": hashlib.sha256(profile_bytes).hexdigest(),
        "utf8_hex": profile_bytes.hex(),
    }
    inputs["native_profile_bytes"] = profile_bytes

    with pytest.raises(ValueError, match="does not match the reference"):
        scale.validate_authority_bytes(contract, authority, **inputs)


def test_plan_review_scale_refuses_wrong_realized_fixture_count() -> None:
    contract = _contract()
    authority, inputs = _authority(contract)
    wrong = deepcopy(inputs)
    wrong["fixture_manifests"]["base"]["counts"]["projection_rows"] = 119_999

    with pytest.raises(ValueError, match="realized fixtures"):
        scale.validate_authority_bytes(contract, authority, **wrong)


def test_plan_review_scale_refuses_incomplete_retained_representation() -> None:
    contract = _contract()
    authority, inputs = _authority(contract)
    authority["fixture_manifests"]["base"]["retained_representation"][
        "visible_sequence"
    ]["sibling_ordinals"]["count"] = 0
    inputs["fixture_manifests"] = deepcopy(authority["fixture_manifests"])

    with pytest.raises(ValueError, match="compact buffer population"):
        scale.validate_authority_bytes(contract, authority, **inputs)


def test_plan_review_scale_refuses_false_compact_permutation_population() -> None:
    contract = _contract()
    authority, inputs = _authority(contract)
    descriptor = authority["fixture_manifests"]["base"]["retained_representation"][
        "plan_review_state"
    ]["current_order"]["ordered_source_positions"]
    descriptor["unique_count"] -= 1
    inputs["fixture_manifests"] = deepcopy(authority["fixture_manifests"])

    with pytest.raises(ValueError, match="not a permutation"):
        scale.validate_authority_bytes(contract, authority, **inputs)


def test_plan_review_scale_refuses_visible_buffer_not_matching_current_order() -> None:
    contract = _contract()
    authority, inputs = _authority(contract)
    descriptor = authority["fixture_manifests"]["base"]["retained_representation"][
        "visible_sequence"
    ]["visible_source_positions"]
    descriptor["values_sha256"] = "0" * 64
    inputs["fixture_manifests"] = deepcopy(authority["fixture_manifests"])

    with pytest.raises(ValueError, match="visible order is not current"):
        scale.validate_authority_bytes(contract, authority, **inputs)


def test_plan_review_scale_validates_one_terminal_verdict_free_artifact() -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    raw, authority_bytes = _artifact(contract, authority)

    observations = _validate_artifact(contract, authority, authority_bytes, raw)

    assert len(observations) == len(contract["metrics"])
    assert all(item.headroom > 0 for item in observations)
    assert all(len(item.within_child_ranges) == 5 for item in observations)
    assert all(item.across_child_range >= 0 for item in observations)
    assert "passed" not in raw and "observations" not in raw


def test_plan_review_scale_refuses_well_formed_wrong_authority_receipt() -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    raw, authority_bytes = _artifact(contract, authority)
    raw["authority_receipt"]["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="authority receipt"):
        _validate_artifact(contract, authority, authority_bytes, raw)


def test_plan_review_scale_refuses_missing_and_extra_metric_cases() -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    raw, authority_bytes = _artifact(contract, authority)
    missing = deepcopy(raw)
    metric_id = contract["metrics"][0]["id"]
    missing["children"] = [
        child for child in missing["children"]
        if child["receipt"]["metric_id"] != metric_id
    ]
    with pytest.raises(ValueError, match="membership is incomplete"):
        _validate_artifact(contract, authority, authority_bytes, missing)

    extra = deepcopy(raw)
    extra_child = deepcopy(extra["children"][0])
    extra_child["receipt"]["metric_id"] = "extra-case"
    extra_child["receipt"]["child_id"] = "f" * 32
    extra_child["receipt"]["launch_token"] = "e" * 32
    extra_child["receipt"]["process_identity"] = {
        "pid": 999_999,
        "creation_filetime_100ns": 999_999,
    }
    _rehash_child(extra_child)
    extra["children"].append(extra_child)
    with pytest.raises(ValueError, match="child metric"):
        _validate_artifact(contract, authority, authority_bytes, extra)


def test_plan_review_scale_refuses_child_and_process_reuse() -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    raw, authority_bytes = _artifact(contract, authority)

    for field, message in (("child_id", "child identity"), ("launch_token", "child launch")):
        changed = deepcopy(raw)
        changed["children"][1]["receipt"][field] = changed["children"][0]["receipt"][field]
        _rehash_child(changed["children"][1])
        with pytest.raises(ValueError, match=message):
            _validate_artifact(contract, authority, authority_bytes, changed)

    changed = deepcopy(raw)
    changed["children"][1]["receipt"]["process_identity"] = deepcopy(
        changed["children"][0]["receipt"]["process_identity"]
    )
    _rehash_child(changed["children"][1])
    with pytest.raises(ValueError, match="child process"):
        _validate_artifact(contract, authority, authority_bytes, changed)


def test_plan_review_scale_refuses_wrong_child_count_and_correctness() -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    raw, authority_bytes = _artifact(contract, authority)
    changed = deepcopy(raw)
    changed["children"][0]["receipt"]["samples"].pop()
    _rehash_child(changed["children"][0])
    with pytest.raises(ValueError, match="sample count"):
        _validate_artifact(contract, authority, authority_bytes, changed)

    changed = deepcopy(raw)
    changed["children"][0]["receipt"]["samples"][0]["correctness"] = {}
    _rehash_child(changed["children"][0])
    with pytest.raises(ValueError, match="correctness receipt"):
        _validate_artifact(contract, authority, authority_bytes, changed)


def test_plan_review_scale_refuses_wrong_headed_fixture_population_and_freshness() -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    raw, authority_bytes = _artifact(contract, authority)
    wrapper = next(
        child for child in raw["children"]
        if child["receipt"]["metric_id"] == "ui_start_execution_receipt"
    )

    wrong_count = deepcopy(raw)
    changed = next(
        child for child in wrong_count["children"]
        if child["receipt"]["metric_id"] == "ui_start_execution_receipt"
    )
    changed["receipt"]["headed_fixture"]["rows"].pop()
    changed["receipt"]["headed_fixture"]["published_plan_count"] -= 1
    _rehash_child(changed)
    with pytest.raises(ValueError, match="fixture population"):
        _validate_artifact(contract, authority, authority_bytes, wrong_count)

    reused = deepcopy(raw)
    changed = next(
        child for child in reused["children"]
        if child["receipt"]["metric_id"] == "ui_start_execution_receipt"
    )
    changed["receipt"]["headed_fixture"]["rows"][1]["request_id"] = (
        changed["receipt"]["headed_fixture"]["rows"][0]["request_id"]
    )
    _rehash_child(changed)
    with pytest.raises(ValueError, match="identity is invalid or reused"):
        _validate_artifact(contract, authority, authority_bytes, reused)

    stale = deepcopy(raw)
    changed = next(
        child for child in stale["children"]
        if child["receipt"]["metric_id"] == "ui_start_execution_receipt"
    )
    changed["receipt"]["headed_fixture"]["rows"][0]["execution_unused"] = False
    _rehash_child(changed)
    with pytest.raises(ValueError, match="fixture publication"):
        _validate_artifact(contract, authority, authority_bytes, stale)

    wrong_settlement = deepcopy(raw)
    changed = next(
        child for child in wrong_settlement["children"]
        if child["receipt"]["metric_id"] == "ui_start_execution_receipt"
    )
    changed["receipt"]["headed_fixture"]["rows"][0][
        "initial_view_settlement"
    ]["first_row"]["node_id"] = "node-" + "0" * 32
    _rehash_child(changed)
    with pytest.raises(ValueError, match="initial view settlement"):
        _validate_artifact(
            contract,
            authority,
            authority_bytes,
            wrong_settlement,
        )

    assert wrapper["receipt"]["headed_fixture"]["published_plan_count"] == 7


def test_plan_review_scale_refuses_p95_pass_with_maximum_failure() -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    raw, authority_bytes = _artifact(contract, authority)
    metric = next(
        item for item in contract["metrics"]
        if item["id"] == "projection_unchanged_window"
    )
    wrapper = next(
        child for child in raw["children"]
        if child["receipt"]["metric_id"] == metric["id"]
    )
    wrapper["receipt"]["samples"][0]["elapsed_ns"] = metric["maximum_budget_ns"] + 1
    _rehash_child(wrapper)

    with pytest.raises(ValueError, match="maximum exceeds"):
        _validate_artifact(contract, authority, authority_bytes, raw)


def test_plan_review_scale_refuses_fixed_statistic_failure() -> None:
    contract = _contract()
    authority, _inputs = _authority(contract)
    raw, authority_bytes = _artifact(contract, authority)
    metric = next(item for item in contract["metrics"] if item["id"] == "projection_cold_base")
    wrapper = next(
        child for child in raw["children"]
        if child["receipt"]["metric_id"] == metric["id"]
    )
    wrapper["receipt"]["samples"][0]["elapsed_ns"] = metric["budget_ns"] + 1
    _rehash_child(wrapper)

    with pytest.raises(ValueError, match="statistic exceeds"):
        _validate_artifact(contract, authority, authority_bytes, raw)
