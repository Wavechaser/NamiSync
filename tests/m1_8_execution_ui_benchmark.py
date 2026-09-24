"""Separate M1-8 U-v2 UI gate for thirteen installed-headed cases.

Reuse the protected workload with rootless settlement, guarded U first-frame
feedback observers, exact Start binding, and typed control acceptance. Keep the
historical probe, timing budgets, sample counts, and native profile unchanged.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterator, Mapping
from unittest.mock import patch
from uuid import uuid4

import plan_review_benchmark as legacy

sys.path.insert(0, str(Path(__file__).resolve().parent / "interfaces" / "web"))
import _m1_8_execution_ui_scale as scoped
import m1_8_execution_receipt_benchmark as receipt_adapter
import _plan_review_scale as plan_scale


_original_headed_probe_script = legacy._headed_probe_script
_FEEDBACK_HELPER = Path(__file__).resolve().parent / "assets" / "m1_8_execution_ui_probe.mjs"


def _replace_once(script: str, before: str, after: str, label: str) -> str:
    if script.count(before) != 1 or after in script:
        raise ValueError(f"U observer adaptation site changed: {label}")
    return script.replace(before, after, 1)


def _replace_section(script: str, start: str, end: str, after: str, label: str) -> str:
    if script.count(start) != 1 or script.count(end) != 1:
        raise ValueError(f"U observer adaptation site changed: {label}")
    first = script.index(start)
    last = script.index(end, first)
    return script[:first] + after + script[last:]


def _rootless_probe_script(metric_id: str, *, readiness: bool = False) -> str:
    original = _original_headed_probe_script(metric_id, readiness=readiness)
    script = _replace_once(
        original, "initialWindow.total !== 120000", "initialWindow.total !== 119999",
        "rootless selection fixture",
    )
    helper = _FEEDBACK_HELPER.read_text(encoding="utf-8")
    script = _replace_once(script, "  const nextFrame =", helper + "\n  const nextFrame =", "feedback helper")
    script = _replace_section(
        script, "  async function timedClick(element, pending) {", "  async function timedReceipt(",
        "  async function timedClick(element, review, pending, observer, settledUI, initialPending = '', row = null) {\n"
        "    return uFeedback.timedFeedback(element, review, pending, observer, settledUI, initialPending, row);\n"
        "  }\n", "shared timed feedback",
    )
    script = _replace_section(
        script, "  function observeStartReceipt(row) {",
        "  async function openExecutionConfirmation(",
        "  function observeStartReceipt(row) {\n"
        "    return uFeedback.observeTypedStart(row);\n"
        "  }\n", "exact start request/receipt observer",
    )
    script = _replace_once(
        script,
        '''    const current = await rawFixture();
    const row = current.rows.find((value) => value.task_id === prepared.row.task_id);
    if (row?.session_id !== receipt.value.session_id) {
      throw new Error("execution receipt did not become the current session");
    }
    return receipt;''',
        '''    const current = await bridge.listTasks();
    const task = current.tasks.find((value) => value.task_id === prepared.row.task_id);
    if (task?.task_kind !== "sync-plan"
        || task.request_id !== prepared.row.request_id
        || task.session_id !== receipt.value.session_id) {
      throw new Error("execution receipt did not become the current task run");
    }
    return receipt;''',
        "typed start result current task identity",
    )
    return _adapt_feedback_cases(script)


def _adapt_feedback_cases(script: str) -> str:
    script = _replace_once(
        script,
        '''    filenameSort.click();
    await until(() => review.dataset.pending === "", "sort warmup settlement");''',
        '''    const warmupBase = await bridge.openPlanView(rows[0].task_id);
    if (warmupBase.task_id !== rows[0].task_id
        || warmupBase.request_id !== rows[0].request_id
        || warmupBase.sort_column !== "path") throw new Error("sort warmup base changed");
    const sortWarmup = uFeedback.observeDispatch("update_plan_view", {
      task_id: rows[0].task_id,
      matches: (payload) => payload.sort_column === "filename"
        && payload.sort_direction === "ascending"
        && payload.expected_revision === warmupBase.view_revision,
    }, (value) => value?.disposition === "applied"
      && value.task_id === rows[0].task_id
      && value.request_id === rows[0].request_id
      && value.view_revision === warmupBase.view_revision + 1
      && value.sort_column === "filename" && value.sort_direction === "ascending");
    await timedClick(filenameSort, review, "view", sortWarmup,
      (frame) => uFeedback.sortSuccessor(rows[0], review, filenameSort, frame), "", rows[0]);
    await sortWarmup.finish();
    sortWarmup.dispose();
    await until(() => review.dataset.pending === ""
      && filenameSort.parentElement?.ariaSort === "ascending", "sort warmup settlement");
    const measuredBase = await bridge.openPlanView(rows[0].task_id);
    if (measuredBase.task_id !== rows[0].task_id
        || measuredBase.request_id !== rows[0].request_id
        || measuredBase.view_revision !== warmupBase.view_revision + 1
        || measuredBase.sort_column !== "filename") {
      throw new Error("sort measured base changed");
    }''',
        "sort warmup acceptance",
    )
    script = _replace_section(
        script,
        "    const started = performance.now();\n    sort.click();",
        '  } else if (metric === "ui_mutate_plan_selection_click_feedback") {',
        '''    const observation = uFeedback.observeDispatch("update_plan_view", {
      task_id: rows[0].task_id,
      matches: (payload) => payload.sort_column === "size"
        && payload.sort_direction === "ascending"
        && payload.expected_revision === measuredBase.view_revision,
    }, (value) => value?.disposition === "applied"
      && value.task_id === rows[0].task_id
      && value.request_id === rows[0].request_id
      && value.view_revision === measuredBase.view_revision + 1
      && value.sort_column === "size" && value.sort_direction === "ascending");
    const feedback = await timedClick(sort, review, "view", observation,
      (frame) => uFeedback.sortSuccessor(rows[0], review, sort, frame), "", rows[0]);
    await observation.finish();
    observation.dispose();
    await until(
      () => review.dataset.pending === "" && sort.parentElement?.ariaSort === "ascending",
      "sort command settlement",
    );
    samples.push(sample(1, feedback.elapsedNs, {
      feedback_frame: true, frame_outcome: feedback.outcome, action: "sort",
    }));
''', "sort feedback",
    )
    script = _replace_section(
        script,
        "    warmupCheckbox.click();\n",
        "    const warmupSummary = await bridge.openPlanView(fixtureRow.task_id);",
        '''    const warmupObservation = uFeedback.observeDispatch("mutate_plan_selection", {
      task_id: fixtureRow.task_id,
      matches: (payload) => payload.node_id === targetRow.node_id
        && payload.selected === false
        && payload.expected_view_revision === initialSummary.view_revision
        && payload.expected_selection_revision === initialSummary.selection_revision,
    }, (value) => value?.disposition === "applied"
      && value.task_id === fixtureRow.task_id
      && value.request_id === fixtureRow.request_id
      && value.view_revision === initialSummary.view_revision + 1
      && value.selection_revision === initialSummary.selection_revision + 1);
    await timedClick(warmupCheckbox, review, "selection", warmupObservation,
      (frame) => frame.pending === ""
        && uFeedback.currentReview(fixtureRow, review) !== null
        && operationCheckbox(false) !== null, "", fixtureRow);
    await warmupObservation.finish();
    warmupObservation.dispose();
    await until(
      () => document.querySelector(".nami-plan-review")?.dataset.pending === "",
      "selection warmup settlement",
    );
''', "selection warmup feedback",
    )
    script = _replace_once(
        script,
        '    const elapsed = await timedClick(measuredCheckbox, "selection");',
        '''    const selectionObservation = uFeedback.observeDispatch("mutate_plan_selection", {
      task_id: fixtureRow.task_id,
      matches: (payload) => payload.node_id === targetRow.node_id
        && payload.selected === true
        && payload.expected_view_revision === warmupSummary.view_revision
        && payload.expected_selection_revision === warmupSummary.selection_revision,
    }, (value) => value?.disposition === "applied"
      && value.task_id === fixtureRow.task_id
      && value.request_id === fixtureRow.request_id
      && value.view_revision === warmupSummary.view_revision + 1
      && value.selection_revision === warmupSummary.selection_revision + 1);
    const feedback = await timedClick(measuredCheckbox, review, "selection",
      selectionObservation, (frame) => frame.pending === ""
        && uFeedback.currentReview(fixtureRow, review) !== null
        && operationCheckbox(true) !== null, "", fixtureRow);
    await selectionObservation.finish();
    selectionObservation.dispose();''',
        "selection measured feedback",
    )
    script = _replace_once(
        script,
        '    samples.push(sample(1, elapsed, { pending_frame: true, action: "selection" }));',
        '''    samples.push(sample(1, feedback.elapsedNs, {
      feedback_frame: true, frame_outcome: feedback.outcome, action: "selection",
    }));''',
        "selection measured sample",
    )
    return _adapt_execution_feedback(script)


def _adapt_execution_feedback(script: str) -> str:
    script = _replace_section(
        script,
        "    const elapsed = await timedClick(\n      prepared.dialog.querySelector",
        '  } else if (metric === "ui_start_execution_nondestructive_click_feedback") {',
        '''    const feedback = await timedClick(
      prepared.dialog.querySelector("[data-confirm-execution]"), prepared.review,
      "execute", observation,
      (frame) => uFeedback.startedSuccessor(prepared.row, frame, true), "confirmation",
      prepared.row,
    );
    if (feedback.outcome === "pending" && (prepared.dialog.open !== true
        || document.querySelector("#app")?.inert !== true
        || document.querySelector("#theme-options")?.inert !== true)) {
      throw new Error("confirmed execution lost its modal pending frame");
    }
    await settleStartedExecution(prepared, observation);
    samples.push(sample(1, feedback.elapsedNs, {
      feedback_frame: true, frame_outcome: feedback.outcome, action: "confirm",
      snapshot_exact: true, fresh_eligible_plan: true,
    }));
''', "confirm feedback",
    )
    script = _replace_section(
        script,
        "    const elapsed = await timedClick(\n      review.querySelector('[data-action=\"execute\"]')",
        '  } else if (metric.endsWith("_click_feedback")) {',
        '''    const feedback = await timedClick(
      review.querySelector('[data-action="execute"]'), review, "execute", observation,
      (frame) => uFeedback.startedSuccessor(row, frame, false), "", row,
    );
    if (document.querySelector("#execution-confirmation")?.open === true) {
      throw new Error("nondestructive Execute opened confirmation");
    }
    await settleStartedExecution(prepared, observation);
    samples.push(sample(1, feedback.elapsedNs, {
      feedback_frame: true, frame_outcome: feedback.outcome, action: "execute",
      destructive_selection: false, modal_bypassed: true, fresh_eligible_plan: true,
    }));
''', "nondestructive start feedback",
    )
    script = _replace_section(
        script,
        '    let review = (await prepareExecutionControl(0, action)).review;',
        '  } else if (metric === "ui_get_plan_window_one_row_receipt") {',
        '''    let prepared = await prepareExecutionControl(0, action);
    let review = prepared.review;
    let observation = uFeedback.observeControl(prepared.row, action);
    await timedClick(review.querySelector(`[data-action="${action}"]`), review,
      action, observation,
      (frame) => uFeedback.controlSuccessor(review, prepared.row, action, frame),
      "", prepared.row);
    await observation.finish();
    observation.dispose();
    await until(() => review.dataset.pending === ""
      && (action === "pause"
        ? review.querySelector('[data-action="resume"]')?.hidden === false
        : action === "resume"
          ? review.querySelector('[data-action="pause"]')?.hidden === false
          : review.querySelector('[data-action="cancel"]')?.disabled === true),
      `${action} warmup settlement`);
    prepared = await prepareExecutionControl(1, action);
    review = prepared.review;
    observation = uFeedback.observeControl(prepared.row, action);
    const feedback = await timedClick(
      review.querySelector(`[data-action="${action}"]`), review, action,
      observation, (frame) => uFeedback.controlSuccessor(review, prepared.row, action, frame),
      "", prepared.row,
    );
    await observation.finish();
    observation.dispose();
    await until(
      () => {
        if (review.dataset.pending !== "") return false;
        if (action === "pause") {
          return review.querySelector('[data-action="resume"]')?.hidden === false;
        }
        if (action === "resume") {
          return review.querySelector('[data-action="pause"]')?.hidden === false;
        }
        return review.querySelector('[data-action="cancel"]')?.disabled === true;
      },
      `${action} command settlement`,
    );
    samples.push(sample(1, feedback.elapsedNs, {
      feedback_frame: true, frame_outcome: feedback.outcome, action,
    }));
''', "control feedback and warmup",
    )
    return _adapt_warm_controls(script)


def _adapt_warm_controls(script: str) -> str:
    script = _replace_once(
        script,
        '''    if (action === "resume") {
      review.querySelector('[data-action="pause"]').click();
      await until(
        () => review.querySelector('[data-action="resume"]')?.disabled === false,
        "paused execution control",
      );
    }
    const current = await rawFixture();''',
        '''    if (action === "resume") {
      const beforePause = (await rawFixture()).rows[index];
      const pauseObservation = uFeedback.observeControl(beforePause, "pause");
      await timedClick(review.querySelector('[data-action="pause"]'), review,
        "pause", pauseObservation,
        (frame) => uFeedback.controlSuccessor(review, beforePause, "pause", frame),
        "", beforePause);
      await pauseObservation.finish();
      pauseObservation.dispose();
      await until(
        () => review.querySelector('[data-action="resume"]')?.disabled === false,
        "paused execution control",
      );
    }
    const current = await rawFixture();''',
        "resume setup pause acceptance",
    )
    script = _replace_once(
        script,
        '''    await bridge.controlExecution(
      prepared.row.task_id, prepared.row.session_id, action,
    );''',
        '''    const warmupControl = await bridge.controlExecution(
      prepared.row.task_id, prepared.row.session_id, action,
    );
    uFeedback.controlCorrectness(warmupControl, prepared.row, action);''',
        "warm control acceptance",
    )
    script = _replace_once(
        script,
        '''      samples.push(sample(iteration, receipt.elapsedNs, {
        accepted: receipt.value.session_id === controlRow.session_id,
        action,
      }));''',
        '''      samples.push(sample(iteration, receipt.elapsedNs,
        uFeedback.controlCorrectness(receipt.value, controlRow, action)));''',
        "measured warm control acceptance",
    )
    return script


@contextmanager
def _rootless_fixture_adapter() -> Iterator[None]:
    with receipt_adapter._rootless_fixture_adapter(), patch.object(
        legacy, "_headed_probe_script", _rootless_probe_script,
    ):
        yield


CONTRACT_PATH = Path(__file__).resolve().parent / "interfaces" / "web" / "m1_7_plan_compact_contract.json"
METRIC_IDS = scoped.METRIC_IDS


def run_headed_child(metric_id: str, launch_token: str, *, contract_path: Path,
                     benchmark_root: Path, installed_root: Path) -> dict[str, object]:
    return _run_scoped_headed_child(
        metric_id, launch_token, contract_path=contract_path,
        benchmark_root=benchmark_root, installed_root=installed_root, readiness=False,
    )


def run_headed_readiness(metric_id: str, launch_token: str, *, contract_path: Path,
                         benchmark_root: Path, installed_root: Path) -> dict[str, object]:
    return _run_scoped_headed_child(
        metric_id, launch_token, contract_path=contract_path,
        benchmark_root=benchmark_root, installed_root=installed_root, readiness=True,
    )


def _run_scoped_headed_child(
    metric_id: str, launch_token: str, *, contract_path: Path,
    benchmark_root: Path, installed_root: Path, readiness: bool,
) -> dict[str, object]:
    if metric_id not in METRIC_IDS:
        raise ValueError("scoped adapter metric is invalid")
    if benchmark_root is None or installed_root is None:
        raise ValueError("scoped headed child requires installed benchmark roots")
    benchmark_root = benchmark_root.resolve()
    legacy._require_installed_runtime(installed_root)
    if not legacy._is_hex_identifier(launch_token):
        raise ValueError("scoped launch token is invalid")
    contract = json.loads(contract_path.read_bytes())
    metric = scoped._metrics(contract)[metric_id]
    if readiness and metric_id not in contract["readiness"]["headed_metric_ids"]:
        raise ValueError("scoped readiness metric is not declared")
    fixture_spec = contract["headed_fixture"]
    published_plan_count = (
        fixture_spec["fresh_execution_plan_count"][metric["sample_kind"]]
        if metric_id in fixture_spec["fresh_execution_metric_ids"]
        else fixture_spec["default_published_plan_count"]
    )
    with _rootless_fixture_adapter():
        observed, headed_runtime, headed_fixture = legacy._run_headed_page(
            metric, benchmark_root, published_plan_count, readiness=readiness,
        )
    identity = {
        "child_id": uuid4().hex,
        "headed_fixture": headed_fixture,
        "headed_runtime": headed_runtime,
        "launch_token": launch_token,
        "process_identity": legacy._current_process_identity(),
    }
    if readiness:
        receipt = {
            **identity, "correctness": {metric_id: observed},
            "metric_ids": [metric_id], "schema": plan_scale.READINESS_CHILD_SCHEMA,
            "surface": "installed-headed",
        }
    else:
        receipt = {
            **identity, "fixture_case": metric["fixture_case"],
            "metric_id": metric_id, "sample_kind": metric["sample_kind"],
            "samples": observed, "schema": plan_scale.CHILD_RECEIPT_SCHEMA,
        }
    _validate_child_receipt(
        receipt, {"stage": "readiness" if readiness else "measurement",
                  "metric_id": metric_id, "launch_token": launch_token},
        metric, headed_runtime, set(), set(), set(), set(),
    )
    return receipt


def build_authority(*, contract_path: Path, source_root: Path, installed_root: Path,
                    installed_wheel: Path, benchmark_root: Path,
                    no_unrelated_sustained_workload: bool) -> dict[str, object]:
    compact = legacy.build_authority(
        contract_path=contract_path, source_root=source_root, installed_root=installed_root,
        installed_wheel=installed_wheel, benchmark_root=benchmark_root,
        no_unrelated_sustained_workload=no_unrelated_sustained_workload,
    )
    compact_bytes = plan_scale.canonical_json_bytes(compact)
    source_files: dict[str, dict[str, str]] = {}
    for relative in (*scoped.SOURCE_ONLY_PATHS, *scoped.PRODUCT_PATHS):
        content = (source_root / relative).read_bytes()
        source_files[relative] = {
            "git_blob_oid": plan_scale._git_filtered_blob_oid(source_root, relative, content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    product_files: dict[str, dict[str, str]] = {}
    import io
    import zipfile
    with zipfile.ZipFile(io.BytesIO(installed_wheel.read_bytes())) as wheel:
        for relative in scoped.PRODUCT_PATHS:
            source = (source_root / relative).read_bytes()
            installed = (installed_root / relative).read_bytes()
            member = wheel.read(relative)
            product_files[relative] = {
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "wheel_member_sha256": hashlib.sha256(member).hexdigest(),
                "installed_sha256": hashlib.sha256(installed).hexdigest(),
            }
    contract = json.loads(contract_path.read_bytes())
    return {
        "compact_authority": compact,
        "compact_authority_receipt": {
            "byte_length": len(compact_bytes),
            "git_blob_oid": plan_scale.git_blob_oid(compact_bytes),
            "sha256": hashlib.sha256(compact_bytes).hexdigest(),
        },
        "contract_sha256": plan_scale.canonical_sha256(contract),
        "product_files": product_files,
        "schema": scoped.AUTHORITY_SCHEMA,
        "source_files": source_files,
    }


def _write_once(path: Path, value: object) -> bytes:
    if path.exists() or not path.parent.is_dir():
        raise FileExistsError("scoped evidence output already exists or parent is unavailable")
    content = plan_scale.canonical_json_bytes(value)
    path.write_bytes(content)
    return content


def _write_index(path: Path, value: object) -> None:
    content = plan_scale.canonical_json_bytes(value)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _output_bytes(value: object) -> bytes:
    if value is None:
        return b""
    if type(value) is bytes:
        return value
    return str(value).encode("utf-8", errors="replace")


def _validate_child_receipt(
    receipt: object, planned: Mapping[str, object], metric: Mapping[str, object],
    headed_runtime: object, child_ids: set[str], tokens: set[str], processes: set[tuple[int, int]],
    fixture_ids: set[tuple[str, str]],
) -> None:
    expected_schema = plan_scale.READINESS_CHILD_SCHEMA if planned["stage"] == "readiness" else plan_scale.CHILD_RECEIPT_SCHEMA
    if type(receipt) is not dict or receipt.get("schema") != expected_schema:
        raise ValueError("scoped child receipt schema is invalid")
    if planned["stage"] == "readiness":
        if (
            not plan_scale._is_readiness_receipt(receipt)
            or receipt["metric_ids"] != [planned["metric_id"]]
            or receipt["surface"] != "installed-headed"
        ):
            raise ValueError("scoped readiness receipt is invalid")
    else:
        if (
            not plan_scale._is_measurement_receipt(receipt)
            or receipt["metric_id"] != planned["metric_id"]
            or receipt["fixture_case"] != metric["fixture_case"]
            or receipt["sample_kind"] != metric["sample_kind"]
            or type(receipt["samples"]) is not list or len(receipt["samples"]) != (1 if metric["sample_kind"] == "cold" else 6)
        ):
            raise ValueError("scoped measurement receipt is invalid")
    if receipt["launch_token"] != planned["launch_token"] or receipt["headed_runtime"] != headed_runtime:
        raise ValueError("scoped child receipt provenance is invalid")
    scoped._validate_identity(receipt, child_ids, tokens, processes)
    scoped._validate_rootless_headed_fixture(metric, receipt["headed_fixture"], fixture_ids)
    if planned["stage"] == "readiness":
        correctness = receipt["correctness"]
        if type(correctness) is not dict or set(correctness) != {planned["metric_id"]}:
            raise ValueError("scoped readiness correctness is invalid")
        scoped._u_correctness(
            metric, receipt["headed_fixture"], 1, correctness[planned["metric_id"]],
        )
    else:
        for iteration, sample in enumerate(receipt["samples"], start=1):
            if type(sample) is not dict:
                raise ValueError("scoped measurement sample is invalid")
            expected = scoped._u_correctness(
                metric, receipt["headed_fixture"], iteration, sample.get("correctness"),
            )
            if plan_scale._measurement_sample_issue(
                sample, iteration, expected, "elapsed_ns", "retained_bytes",
            ):
                raise ValueError("scoped measurement sample is invalid")


def _planned_attempts() -> list[dict[str, object]]:
    rows = [("readiness", metric) for metric in METRIC_IDS]
    rows.extend(("measurement", metric) for metric in METRIC_IDS for _ in range(5))
    return [
        {"attempt": ordinal, "launch_token": uuid4().hex, "metric_id": metric, "stage": stage}
        for ordinal, (stage, metric) in enumerate(rows, start=1)
    ]


def collect(*, python: Path, authority_path: Path, output: Path, collection_root: Path,
            contract_path: Path, benchmark_root: Path, installed_root: Path) -> None:
    """Run the fixed thirteen-readiness/sixty-five-child sequence with retained prelaunch state."""

    index_path = collection_root / "collection.json"
    child_root = collection_root / "children"
    log_root = collection_root / "logs"
    failed_raw_path = collection_root / "failed-receipts.json"
    if (
        output.exists() or index_path.exists() or child_root.exists() or log_root.exists()
        or failed_raw_path.exists() or not collection_root.is_dir()
    ):
        raise FileExistsError("scoped collection already exists or root is unavailable")
    authority_bytes = authority_path.read_bytes()
    authority = json.loads(authority_bytes)
    compact = authority["compact_authority"]
    compact_bytes = plan_scale.canonical_json_bytes(compact)
    scoped.validate_authority(
        json.loads(contract_path.read_bytes()), compact, compact_bytes,
        authority["compact_authority_receipt"]["git_blob_oid"], authority,
    )
    planned = _planned_attempts()
    child_root.mkdir()
    log_root.mkdir()
    index: dict[str, object] = {"accepted": [], "planned": planned, "state": {**planned[0], "status": "next"}}
    _write_index(index_path, index)
    wrappers: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    child_ids: set[str] = set()
    tokens: set[str] = set()
    processes: set[tuple[int, int]] = set()
    fixture_ids: set[tuple[str, str]] = set()
    metrics = {metric["id"]: metric for metric in json.loads(contract_path.read_bytes())["metrics"]}
    for planned_item in planned:
        index["state"] = {**planned_item, "status": "launching"}
        _write_index(index_path, index)
        attempt = planned_item["attempt"]
        receipt_path = child_root / f"{attempt:02d}.json"
        log_path = log_root / f"{attempt:02d}.log"
        mode = "--readiness" if planned_item["stage"] == "readiness" else "--child"
        command = [str(python), str(Path(__file__).resolve()), mode, planned_item["metric_id"], "--launch-token", planned_item["launch_token"], "--contract", str(contract_path), "--benchmark-root", str(benchmark_root), "--installed-root", str(installed_root), "--output", str(receipt_path)]
        completed: subprocess.CompletedProcess[str] | None = None
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
            log = (completed.stdout + completed.stderr).encode("utf-8", errors="replace")
            log_path.write_bytes(log)
            if completed.returncode:
                raise RuntimeError(f"child exited {completed.returncode}")
            receipt = json.loads(receipt_path.read_bytes())
            _validate_child_receipt(
                receipt, planned_item, metrics[planned_item["metric_id"]], compact["headed_runtime"],
                child_ids, tokens, processes, fixture_ids,
            )
        except BaseException as error:
            if not log_path.exists():
                if isinstance(error, subprocess.TimeoutExpired):
                    log_path.write_bytes(_output_bytes(error.stdout) + _output_bytes(error.stderr))
                else:
                    log_path.write_text(str(error), encoding="utf-8")
            log = log_path.read_bytes()
            failure = {
                "error": str(error)[:4096], "error_class": type(error).__name__, "error_truncated": len(str(error)) > 4096,
                "exit_code": None if isinstance(error, subprocess.TimeoutExpired) else (None if completed is None else completed.returncode), "launch_token": planned_item["launch_token"],
                "metric_id": planned_item["metric_id"], "raw_log": {"byte_length": len(log), "sha256": hashlib.sha256(log).hexdigest()},
                "stage": planned_item["stage"], "timed_out": isinstance(error, subprocess.TimeoutExpired),
            }
            failures.append(failure)
            index["state"] = {**planned_item, "failure": failure, "status": "failed"}
            _write_once(failed_raw_path, {"failures": failures, "receipts": wrappers})
            _write_index(index_path, index)
            raise RuntimeError("scoped collection stopped after its first failure") from error
        wrappers.append({"receipt": receipt, "receipt_sha256": plan_scale.canonical_sha256(receipt)})
        index["accepted"].append({
            "attempt": attempt, "child_id": receipt["child_id"], "launch_token": planned_item["launch_token"],
            "metric_id": planned_item["metric_id"], "process_identity": receipt["process_identity"],
            "receipt_path": f"children/{attempt:02d}.json", "receipt_sha256": hashlib.sha256(plan_scale.canonical_json_bytes(receipt)).hexdigest(), "stage": planned_item["stage"],
        })
        index["state"] = ({"status": "complete"} if attempt == len(planned) else {**planned[attempt], "status": "next"})
        _write_index(index_path, index)
    raw = {
        "authority_receipt": {"byte_length": len(authority_bytes), "git_blob_oid": plan_scale.git_blob_oid(authority_bytes), "sha256": hashlib.sha256(authority_bytes).hexdigest()},
        "children": wrappers[len(METRIC_IDS):], "collection": index, "failures": failures, "readiness": wrappers[:len(METRIC_IDS)], "schema": scoped.RECEIPTS_SCHEMA,
    }
    _write_once(output, raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze-authority", action="store_true")
    mode.add_argument("--child", choices=METRIC_IDS)
    mode.add_argument("--readiness", choices=METRIC_IDS)
    mode.add_argument("--collect", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authority", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--installed-root", type=Path, required=True)
    parser.add_argument("--installed-wheel", type=Path)
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--collection-root", type=Path)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--launch-token")
    parser.add_argument("--confirm-no-unrelated-sustained-workload", action="store_true")
    arguments = parser.parse_args()
    if arguments.freeze_authority:
        if (
            arguments.source_root is None or arguments.installed_wheel is None
            or not arguments.confirm_no_unrelated_sustained_workload
        ):
            raise ValueError("authority freeze requires source root and wheel")
        _write_once(arguments.output, build_authority(
            contract_path=arguments.contract, source_root=arguments.source_root,
            installed_root=arguments.installed_root, installed_wheel=arguments.installed_wheel,
            benchmark_root=arguments.benchmark_root,
            no_unrelated_sustained_workload=arguments.confirm_no_unrelated_sustained_workload,
        ))
        return 0
    if arguments.collect:
        if arguments.authority is None or arguments.collection_root is None:
            raise ValueError("collection requires authority and collection root")
        collect(python=Path(sys.executable), authority_path=arguments.authority, output=arguments.output,
                collection_root=arguments.collection_root, contract_path=arguments.contract,
                benchmark_root=arguments.benchmark_root, installed_root=arguments.installed_root)
        return 0
    if arguments.launch_token is None:
        raise ValueError("child mode requires a launch token")
    receipt = (
        run_headed_child(arguments.child, arguments.launch_token, contract_path=arguments.contract,
                         benchmark_root=arguments.benchmark_root, installed_root=arguments.installed_root)
        if arguments.child else run_headed_readiness(arguments.readiness, arguments.launch_token,
                         contract_path=arguments.contract, benchmark_root=arguments.benchmark_root,
                         installed_root=arguments.installed_root)
    )
    _write_once(arguments.output, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
