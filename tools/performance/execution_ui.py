"""Selected installed M1-8 execution UI measurements."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
from typing import Iterator
from unittest.mock import patch
from uuid import uuid4

from . import plan as legacy

from . import execution_receipt as receipt_adapter


_original_headed_probe_script = legacy._headed_probe_script
_FEEDBACK_HELPER = Path(__file__).resolve().parent / "execution_ui_probe.mjs"


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


def _rootless_probe_script(metric_id: str) -> str:
    original = _original_headed_probe_script(metric_id)
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


CONTRACT_PATH = legacy.CONTRACT_PATH
CASES = (
    "ui_update_plan_view_click_feedback",
    "ui_mutate_plan_selection_click_feedback",
    "ui_start_execution_click_feedback",
    "ui_confirm_execution_click_feedback",
    "ui_start_execution_nondestructive_click_feedback",
    "ui_control_pause_click_feedback",
    "ui_control_resume_click_feedback",
    "ui_control_cancel_click_feedback",
    "ui_get_plan_window_one_row_receipt",
    "ui_start_execution_receipt",
    "ui_control_pause_receipt",
    "ui_control_resume_receipt",
    "ui_control_cancel_receipt",
)


def run_headed_child(
    metric_id: str, launch_token: str, *, contract_path: Path,
    benchmark_root: Path, installed_root: Path,
) -> dict[str, object]:
    if metric_id not in CASES:
        raise ValueError("execution UI case is invalid")
    legacy._require_installed_runtime(installed_root)
    if not legacy._is_hex_identifier(launch_token):
        raise ValueError("execution UI launch token is invalid")
    contract = json.loads(contract_path.read_bytes())
    metric = next(item for item in contract["metrics"] if item["id"] == metric_id)
    fixture_spec = contract["headed_fixture"]
    published_plan_count = (
        fixture_spec["fresh_execution_plan_count"][metric["sample_kind"]]
        if metric_id in fixture_spec["fresh_execution_metric_ids"]
        else fixture_spec["default_published_plan_count"]
    )
    with _rootless_fixture_adapter():
        samples, headed_runtime, headed_fixture = legacy._run_headed_page(
            metric, benchmark_root.resolve(), published_plan_count,
        )
    expected_count = 1 if metric["sample_kind"] == "cold" else 6
    if (
        type(samples) is not list or len(samples) != expected_count
        or any(sample["correctness"] != metric["correctness"] for sample in samples)
        or type(headed_fixture) is not dict
        or headed_fixture.get("published_plan_count") != published_plan_count
    ):
        raise RuntimeError("execution UI child did not complete the named action")
    return {
        "child_id": uuid4().hex,
        "headed_fixture": headed_fixture,
        "headed_runtime": headed_runtime,
        "installed_runtime": legacy._installed_runtime_identity(installed_root),
        "launch_token": launch_token,
        "process_identity": legacy._current_process_identity(),
        "fixture_case": metric["fixture_case"],
        "metric_id": metric_id,
        "sample_kind": metric["sample_kind"],
        "samples": samples,
        "schema": legacy.CHILD_RECEIPT_SCHEMA,
    }


def run_case(
    case: str, *, output: Path, installed_root: Path | None = None,
) -> dict[str, object]:
    from ._child import run_child

    if case not in CASES:
        raise ValueError(f"unknown execution UI case: {case}")
    if installed_root is None:
        raise ValueError("execution UI case requires --installed-root")
    token = uuid4().hex
    receipt = run_child(
        "tools.performance.execution_ui",
        [
            "--child", case, "--launch-token", token,
            "--contract", str(CONTRACT_PATH),
            "--benchmark-root", str(output.parent),
            "--installed-root", str(installed_root),
        ], output=output, installed_root=installed_root,
    )
    metric = next(item for item in json.loads(CONTRACT_PATH.read_bytes())["metrics"] if item["id"] == case)
    samples = receipt.get("samples")
    expected_count = 1 if metric["sample_kind"] == "cold" else 6
    fixture = receipt.get("headed_fixture")
    runtime = receipt.get("installed_runtime")
    if (
        receipt.get("metric_id") != case or receipt.get("launch_token") != token
        or type(samples) is not list or len(samples) != expected_count
        or any(type(sample) is not dict or sample.get("correctness") != metric["correctness"]
               or type(sample.get("elapsed_ns")) is not int or sample["elapsed_ns"] < 0
               for sample in samples)
        or type(fixture) is not dict
        or not fixture.get("published_plan_count")
        or type(runtime) is not dict
        or runtime.get("root") != str(installed_root.resolve())
        or runtime.get("namisync_file") != str((installed_root / "namisync" / "__init__.py").resolve())
        or not runtime.get("namisync_version")
    ):
        raise RuntimeError("execution UI child returned an incomplete or false observation")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", choices=CASES, required=True)
    parser.add_argument("--launch-token", required=True)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--installed-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_headed_child(
        args.child, args.launch_token, contract_path=args.contract,
        benchmark_root=args.benchmark_root, installed_root=args.installed_root,
    )
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
