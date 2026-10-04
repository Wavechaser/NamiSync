"""Functional controls for selected M1-8 UI measurements."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import subprocess

import pytest

from tools.performance import execution_ui as adapter
from tools.performance import _child as performance_child
from _frontend_test_support import _node_executable

REPOSITORY_ROOT = Path(__file__).parents[3]


@pytest.mark.parametrize("metric_id", tuple(adapter._FEEDBACK_MARKERS))
@pytest.mark.parametrize("outcome", ("pending", "accepted"))
def test_ui_adapted_feedback_keeps_exact_action_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, metric_id: str, outcome: str,
) -> None:
    contract = json.loads(adapter.CONTRACT_PATH.read_bytes())
    metric = next(row for row in contract["metrics"] if row["id"] == metric_id)
    correctness = deepcopy(metric["correctness"])
    assert correctness.pop(adapter._FEEDBACK_MARKERS[metric_id]) is True
    correctness.update(feedback_frame=True, frame_outcome=outcome)
    sample_count = 1 if metric["sample_kind"] == "cold" else 6

    def page(_metric: dict, _root: Path, count: int) -> tuple[list, dict, dict]:
        return ([{"correctness": deepcopy(correctness), "elapsed_ns": 1}
                 for _ in range(sample_count)], {}, {"published_plan_count": count})

    monkeypatch.setattr(adapter.legacy, "_run_headed_page", page)
    monkeypatch.setattr(adapter.legacy, "_require_installed_runtime", lambda _root: None)
    receipt = adapter.run_headed_child(
        metric_id, "a" * 32, contract_path=adapter.CONTRACT_PATH,
        benchmark_root=tmp_path, installed_root=tmp_path,
    )
    assert receipt["samples"][0]["correctness"] == correctness

    for invalid in (
        {**correctness, "feedback_frame": False},
        {**correctness, "frame_outcome": "missing"},
        {**correctness, "action": "wrong"},
        {**correctness, "extra": True},
    ):
        assert not adapter._correctness_matches(metric, invalid)


@pytest.mark.parametrize("corruption", (None, "marker", "outcome", "action"))
def test_ui_parent_checks_adapted_feedback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str | None,
) -> None:
    metric_id = "ui_start_execution_nondestructive_click_feedback"
    contract = json.loads(adapter.CONTRACT_PATH.read_bytes())
    metric = next(row for row in contract["metrics"] if row["id"] == metric_id)
    correctness = deepcopy(metric["correctness"])
    assert correctness.pop("busy_frame") is True
    correctness.update(feedback_frame=True, frame_outcome="pending")
    if corruption == "marker":
        correctness["feedback_frame"] = False
    elif corruption == "outcome":
        correctness["frame_outcome"] = "missing"
    elif corruption == "action":
        correctness["action"] = "wrong"
    installed_root = tmp_path / "installed"

    def child(_module: str, args: list[str], **_kwargs: object) -> dict:
        token = args[args.index("--launch-token") + 1]
        return {
            "metric_id": metric_id,
            "launch_token": token,
            "samples": [{"correctness": correctness, "elapsed_ns": 1}],
            "headed_fixture": {"published_plan_count": 2},
            "installed_runtime": {
                "root": str(installed_root.resolve()),
                "namisync_file": str((installed_root / "namisync" / "__init__.py").resolve()),
                "namisync_version": "test",
            },
        }

    monkeypatch.setattr(performance_child, "run_child", child)
    if corruption is None:
        receipt = adapter.run_case(metric_id, output=tmp_path / "report.json", installed_root=installed_root)
        assert receipt["samples"][0]["correctness"] == correctness
    else:
        with pytest.raises(RuntimeError, match="incomplete or false observation"):
            adapter.run_case(metric_id, output=tmp_path / "report.json", installed_root=installed_root)


@pytest.mark.parametrize("corruption", (None, "refused", "wrong_action"))
def test_ui_child_checks_control_action_and_restores_adapters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str | None,
) -> None:
    metric_id = "ui_control_pause_receipt"
    contract = json.loads(adapter.CONTRACT_PATH.read_bytes())
    metric = next(row for row in contract["metrics"] if row["id"] == metric_id)
    original_script = adapter.legacy._headed_probe_script
    original_settle = adapter.legacy._HeadedFixtureController._settle_initial_view
    calls: list[tuple[str, int]] = []

    def page(metric_contract: dict, root: Path, count: int) -> tuple[list, dict, dict]:
        assert root == tmp_path.resolve()
        assert adapter.legacy._headed_probe_script is adapter._rootless_probe_script
        assert (
            adapter.legacy._HeadedFixtureController._settle_initial_view
            is adapter.receipt_adapter._rootless_settlement
        )
        calls.append((metric_contract["id"], count))
        samples = [
            {"correctness": deepcopy(metric["correctness"]), "elapsed_ns": 1}
            for _ in range(6)
        ]
        if corruption == "refused":
            samples[0]["correctness"]["accepted"] = False
        elif corruption == "wrong_action":
            samples[0]["correctness"]["action"] = "resume"
        return samples, {}, {"published_plan_count": count}

    monkeypatch.setattr(adapter.legacy, "_run_headed_page", page)
    monkeypatch.setattr(adapter.legacy, "_require_installed_runtime", lambda _root: None)
    if corruption is None:
        receipt = adapter.run_headed_child(
            metric_id, "a" * 32, contract_path=adapter.CONTRACT_PATH,
            benchmark_root=tmp_path, installed_root=tmp_path,
        )
        assert receipt["samples"][0]["correctness"] == metric["correctness"]
        assert receipt["headed_fixture"]["published_plan_count"] == calls[0][1]
    else:
        with pytest.raises(RuntimeError, match="did not complete the named action"):
            adapter.run_headed_child(
                metric_id, "a" * 32, contract_path=adapter.CONTRACT_PATH,
                benchmark_root=tmp_path, installed_root=tmp_path,
            )
    expected_count = contract["headed_fixture"]["fresh_execution_plan_count"][metric["sample_kind"]]
    assert calls == [(metric_id, expected_count)]
    assert adapter.legacy._headed_probe_script is original_script
    assert adapter.legacy._HeadedFixtureController._settle_initial_view is original_settle

@pytest.mark.parametrize("metric_id", adapter.CASES)
def test_ui_script_adapter_changes_scoped_feedback_and_retains_other_endpoints(
    metric_id: str,
) -> None:
    original = adapter.legacy._headed_probe_script(metric_id)
    adapted = adapter._rootless_probe_script(metric_id)
    assert original.count("initialWindow.total !== 120000") == 1
    assert adapted != original
    assert adapted.count("initialWindow.total !== 119999") == 1
    assert adapted.count("const uFeedback =") == 1
    assert adapted.count("feedback_frame: true") == 5
    assert adapted.count("uFeedback.controlCorrectness") == 2

    def branch(script: str, start: str, end: str) -> str:
        return script.split(start, 1)[1].split(end, 1)[0]

    assert branch(
        adapted, '  } else if (metric === "ui_start_execution_click_feedback") {',
        '  } else if (metric === "ui_confirm_execution_click_feedback") {',
    ) == branch(
        original, '  } else if (metric === "ui_start_execution_click_feedback") {',
        '  } else if (metric === "ui_confirm_execution_click_feedback") {',
    )
    assert branch(
        adapted, '  } else if (metric === "ui_get_plan_window_one_row_receipt") {',
        '  } else if (metric === "ui_start_execution_receipt") {',
    ) == branch(
        original, '  } else if (metric === "ui_get_plan_window_one_row_receipt") {',
        '  } else if (metric === "ui_start_execution_receipt") {',
    )



def test_ui_generated_script_parses_and_selection_warmup_uses_typed_observer(tmp_path: Path) -> None:
    node = _node_executable()
    assert node is not None, "Node.js is required for the U script seam control"
    script = adapter._rootless_probe_script(adapter.CASES[1])
    assert "const warmupObservation = uFeedback.observeDispatch" in script
    assert "await warmupObservation.finish();" in script
    assert "selection_revision === initialSummary.selection_revision + 1" in script
    path = tmp_path / "u-probe.js"
    path.write_text(script, encoding="utf-8")
    completed = subprocess.run(
        (str(node), "--max-old-space-size=128", "--check", str(path)),
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize("adapted", [False, True])
def test_cancel_click_measurement_arms_before_timing_submission(adapted: bool) -> None:
    node = _node_executable()
    assert node is not None, "Node.js is required for the Cancel timing seam"
    factory = adapter._rootless_probe_script if adapted else adapter.legacy._headed_probe_script
    script = factory("ui_control_cancel_click_feedback")
    branch = script.split('  } else if (metric.endsWith("_click_feedback")) {', 1)[1].split(
        '  } else if (metric === "ui_get_plan_window_one_row_receipt") {', 1,
    )[0]
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const [branch, adapted] = JSON.parse(fs.readFileSync(0, 'utf8'));
const events = [];
let timed = false;
async function prepareExecutionControl(index) {
  let armed = false;
  const review = {dataset: {pending: ''}};
  const cancel = {disabled: false, click() {
    if (!armed) {armed = true; events.push('arm'); return;}
    events.push(timed ? 'timed-submit' : 'warmup-submit');
    cancel.disabled = true;
    armed = false;
  }};
  review.querySelector = () => cancel;
  return {review, row: {index}};
}
async function timedClick(element) {
  timed = true;
  element.click();
  timed = false;
  return adapted ? {elapsedNs: 1, outcome: 'pending'} : 1;
}
const until = async (predicate) => assert.equal(predicate(), true);
const samples = [];
const sample = (...args) => args;
const uFeedback = {
  observeControl: () => ({finish: async () => {}, dispose() {}}),
  controlSuccessor: () => true,
};
const AsyncFunction = Object.getPrototypeOf(async function() {}).constructor;
new AsyncFunction('metric', 'prepareExecutionControl', 'timedClick', 'until',
  'samples', 'sample', 'uFeedback', branch)('ui_control_cancel_click_feedback',
  prepareExecutionControl, timedClick, until, samples, sample, uFeedback).then(() => {
    assert.deepEqual(events, ['arm', adapted ? 'timed-submit' : 'warmup-submit', 'arm', 'timed-submit']);
    assert.equal(samples.length, 1);
  }).catch((error) => {console.error(error); process.exitCode = 1;});
"""
    completed = subprocess.run(
        (str(node), "--max-old-space-size=128", "-e", harness),
        input=json.dumps([branch, adapted]), capture_output=True, text=True,
        timeout=20, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr



def test_ui_generated_timed_observer_accepts_both_orders_and_rejects_false_actions() -> None:
    node = _node_executable()
    assert node is not None, "Node.js is required for the U observer control"
    script = adapter._rootless_probe_script(adapter.CASES[5])
    start = script.index("  async function timedClick(element, review, pending, observer, settledUI")
    end = script.index("  async function timedReceipt(", start)
    timed_click = script[start:end]
    helper = (REPOSITORY_ROOT / "tools/performance/execution_ui_probe.mjs").read_text(encoding="utf-8")
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const [helper, timedClick] = JSON.parse(fs.readFileSync(0, 'utf8'));
const window = {pywebview: {api: null}};
let document;
const nextFrame = () => new Promise((resolve) => setImmediate(resolve));
const until = async (predicate) => {
  for (let i = 0; i < 4; i += 1) {
    if (predicate()) return true;
    await nextFrame();
  }
  throw Error('typed reply missing');
};
const {uFeedback, click} = new Function('window', 'document', 'nextFrame', 'until', 'performance',
  `${helper}\n${timedClick}\nreturn {uFeedback, click: timedClick};`)(
    window, {querySelector: (...args) => document.querySelector(...args)}, nextFrame, until, performance);
const TASK = `task-${'a'.repeat(32)}`;
const SESSION = 'b'.repeat(32);
const REQUEST = 'c'.repeat(32);
const before = {pause: 'running', resume: 'paused', cancel: 'running'};
const after = {pause: 'pausing', resume: 'pending', cancel: 'canceling'};

async function run(kind, order, fault = null) {
  const action = kind.startsWith('control-') ? kind.slice(8) : kind;
  const confirmed = kind === 'confirm';
  const start = kind === 'confirm' || kind === 'execute';
  const pending = start ? 'execute' : kind === 'sort' ? 'view' : kind === 'selection' ? 'selection' : action;
  const row = {task_id: TASK, session_id: SESSION, request_id: REQUEST,
    source_path: 'C:/source', target_path: 'D:/target'};
  const controls = {
    toggle: {dataset: {action: action === 'resume' ? 'resume' : 'pause'}, disabled: false},
    cancel: {hidden: false, disabled: false},
  };
  const sortHeader = {ariaSort: 'none', isConnected: true};
  const selection = {checked: false};
  const source = {textContent: row.source_path};
  const target = {textContent: row.target_path};
  let status = '';
  const review = {
    isConnected: true, dataset: {pending: confirmed ? 'confirmation' : ''},
    querySelector: (selector) => {
      if (selector === '.nami-plan-review__status') return {textContent: status};
      if (selector === '.nami-plan-review__path--source .nami-labeled-path__value') return source;
      if (selector === '.nami-plan-review__path--target .nami-labeled-path__value') return target;
      if (selector === '[data-control="pause-resume"]') return controls.toggle;
      const control = selector.match(/data-action="([a-z]+)"/);
      return control ? controls[control[1]] : null;
    },
    contains: (element) => element?.parentElement === sortHeader,
  };
  const dialog = {open: confirmed};
  document = {querySelector: (selector) => ({
    '.nami-plan-review': review,
    '#execution-confirmation': dialog,
    '#app': {inert: confirmed},
    '#theme-options': {inert: confirmed},
  })[selector] ?? null};
  let release;
  const native = new Promise((resolve) => {release = resolve;});
  const api = {dispatch: () => native};
  window.pywebview.api = api;
  const request = {
    request_id: 'd'.repeat(32), command: kind === 'sort' ? 'update_plan_view'
      : kind === 'selection' ? 'mutate_plan_selection' : 'control_execution',
    payload: {task_id: TASK, session_id: SESSION, action,
      expected_revision: 1, expected_view_revision: 1,
      expected_selection_revision: 1, sort_column: 'size', sort_direction: 'ascending',
      node_id: 'node', selected: true},
  };
  const result = kind === 'sort'
    ? {disposition: 'applied', task_id: TASK, request_id: REQUEST,
      view_revision: 2, sort_column: 'size', sort_direction: 'ascending'}
    : kind === 'selection'
      ? {disposition: 'applied', task_id: TASK, request_id: REQUEST,
        view_revision: 2, selection_revision: 2}
      : {accepted: true, code: 'accepted', session_id: SESSION,
        before: before[action], after: after[action], detail: 'accepted'};
  const nativeReply = {transport_version: 1, response_token: null,
    response: {schema_version: 1, request_id: request.request_id, ok: true, result}};
  const succeedUI = () => {
    review.dataset.pending = '';
    if (kind === 'sort') {
      sortHeader.ariaSort = 'ascending';
      if (fault === 'detached-header') sortHeader.isConnected = false;
    }
    else if (kind === 'selection') selection.checked = true;
    else if (start) status = 'Execution running.';
    else if (action === 'pause') {
      status = fault === 'advanced-progress' ? 'Execution paused. Resume available.' : 'Pausing execution…';
      controls.toggle.disabled = true;
      if (fault === 'advanced-progress') {controls.toggle.dataset.action = 'resume'; controls.toggle.disabled = false;}
    } else if (action === 'resume') {
      status = fault === 'advanced-progress' ? 'Execution running.' : 'Execution waiting.';
      controls.toggle.dataset.action = 'pause';
      controls.toggle.disabled = fault !== 'advanced-progress';
    } else {
      status = fault === 'advanced-progress' ? 'Execution canceled.' : 'Canceling execution…';
      controls.cancel.disabled = true;
    }
  };
  let observer;
  if (start) {
    let accepted = false;
    observer = {peek: () => accepted, facts: () => ({accepted}),
      finish: async () => {if (!accepted) throw Error('missing start receipt');}};
    release = () => {accepted = fault !== 'refused' && fault !== 'wrong-identity';
      if (fault !== 'wrong-ui') succeedUI();};
  } else {
    observer = kind.startsWith('control-')
      ? uFeedback.observeControl(row, action)
      : uFeedback.observeDispatch(request.command, {
        task_id: TASK,
        matches: (payload) => kind === 'sort'
          ? payload.sort_column === 'size' && payload.expected_revision === 1
          : payload.node_id === 'node' && payload.expected_view_revision === 1
            && payload.expected_selection_revision === 1,
      }, (value) => kind === 'sort'
        ? value?.disposition === 'applied' && value.view_revision === 2
          && value.task_id === TASK && value.request_id === REQUEST
        : value?.disposition === 'applied' && value.selection_revision === 2
          && value.task_id === TASK && value.request_id === REQUEST);
    const nativeRelease = release;
    release = () => {
      if (fault === 'refused') nativeReply.response.result = {...result, accepted: false,
        disposition: 'conflict', code: 'illegal-state'};
      if (fault === 'wrong-identity') nativeReply.response.request_id = 'e'.repeat(32);
      if (fault === 'malformed-envelope') nativeReply.response.schema_version = 9;
      if (fault !== 'wrong-ui') native.then(succeedUI);
      nativeRelease(nativeReply);
    };
  }
  const element = {
    isConnected: fault !== 'detached', disabled: fault === 'disabled', hidden: false,
    closest: () => fault === 'hidden' ? {} : null,
    parentElement: sortHeader,
    click: () => {
      review.dataset.pending = pending;
      if (fault === 'wrong-current-review') source.textContent = 'C:/other';
      status = `${action[0].toUpperCase()}${action.slice(1)} requested…`;
      if (!start && !fault?.startsWith('no-dispatch')) {
        if (fault === 'stale-revision') {
          request.payload.expected_revision = 9;
          request.payload.expected_view_revision = 9;
        }
        if (fault === 'wrong-session') request.payload.session_id = 'e'.repeat(32);
        api.dispatch(JSON.stringify(request));
      }
      if (order === 'before' && fault !== 'no-dispatch') queueMicrotask(release);
    },
  };
  const settled = (frame) => kind === 'sort'
    ? uFeedback.sortSuccessor(row, review, element, frame)
    : kind === 'selection' ? frame.pending === '' && selection.checked === true
        && uFeedback.currentReview(row, review) !== null
      : start ? uFeedback.startedSuccessor(row, frame, confirmed)
        : uFeedback.controlSuccessor(review, row, action, frame);
  const invoke = () => click(element, review, pending, observer, settled,
    confirmed ? 'confirmation' : '', row);
  if (fault === 'wrong-ui' || fault === 'no-dispatch') {
    const feedback = await invoke();
    assert.equal(feedback.outcome, 'pending');
    if (fault === 'no-dispatch') await assert.rejects(observer.finish());
    else {
      await observer.finish();
      assert.equal(settled({pending: review.dataset.pending, connected: true}), false);
    }
    observer.dispose?.();
    return;
  }
  if (fault && fault !== 'no-dispatch-pending' && fault !== 'advanced-progress') {
    await assert.rejects(invoke());
    observer.dispose?.();
    return;
  }
  const feedback = await invoke();
  assert.equal(feedback.outcome, order === 'before' ? 'accepted' : 'pending');
  if (order === 'after') release();
  if (fault === 'no-dispatch-pending') await assert.rejects(observer.finish());
  else await observer.finish();
  observer.dispose?.();
}

(async () => {
  const kinds = ['sort', 'selection', 'confirm', 'execute',
    'control-pause', 'control-resume', 'control-cancel'];
  for (const kind of kinds) {
    await run(kind, 'before');
    await run(kind, 'after');
    for (const fault of ['refused', 'wrong-identity', 'wrong-ui',
      'disabled', 'detached', 'hidden', 'no-dispatch', 'wrong-current-review']) {
      await run(kind, 'before', fault);
    }
    if (kind !== 'confirm' && kind !== 'execute') {
      await run(kind, 'before', 'malformed-envelope');
      if (kind === 'sort' || kind === 'selection') await run(kind, 'before', 'stale-revision');
      if (kind === 'sort') await run(kind, 'before', 'detached-header');
      if (kind.startsWith('control-')) await run(kind, 'before', 'wrong-session');
    }
    if (kind.startsWith('control-')) await run(kind, 'before', 'advanced-progress');
  }
  await run('control-pause', 'after', 'no-dispatch-pending');
})().catch((error) => {console.error(error); process.exitCode = 1;});
"""
    completed = subprocess.run(
        (str(node), "--max-old-space-size=128", "-e", harness),
        input=json.dumps([helper, timed_click]), capture_output=True, text=True,
        timeout=20, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr



def test_ui_start_receipt_observer_binds_exact_plan_request_and_removes_listener() -> None:
    node = _node_executable()
    assert node is not None, "Node.js is required for the U start observer control"
    script = adapter._rootless_probe_script(adapter.CASES[3])
    start = script.index("  function observeStartReceipt(row) {")
    end = script.index("  async function openExecutionConfirmation(", start)
    observer_source = script[start:end]
    helper = (REPOSITORY_ROOT / "tools/performance/execution_ui_probe.mjs").read_text(encoding="utf-8")
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const [helper, source] = JSON.parse(fs.readFileSync(0, 'utf8'));
const listeners = new Set();
globalThis.chrome = {webview: {
  addEventListener: (_kind, callback) => listeners.add(callback),
  removeEventListener: (_kind, callback) => listeners.delete(callback),
}};
const nativeDispatch = (_wire) => Promise.resolve({});
const window = {pywebview: {api: {dispatch: nativeDispatch}}};
const observe = new Function('window', 'performance',
  `${helper}\n${source}; return observeStartReceipt;`)(window, performance);
const row = {task_id: `task-${'a'.repeat(32)}`, request_id: 'b'.repeat(32),
  selection_revision: 1, destructive_operation_count: 1};
const transport = 'c'.repeat(32);
const dispatch = (planId = row.request_id, requestId = transport,
  commandId = 'f'.repeat(32)) => window.pywebview.api.dispatch(JSON.stringify({
  schema_version: 1, request_id: requestId, command: 'start_execution',
  payload: {task_id: row.task_id, request_id: planId, expected_revision: 1,
    destructive_acknowledged: true, command_id: commandId},
}));
const send = (runId, ok = true, requestId = transport) => {
  const event = {data: {
    kind: 'namisync.command-completion.v1', generation: 1,
    phase: 'completion', request_id: requestId, completion_token: 'd'.repeat(32),
    response: {schema_version: 1, request_id: requestId, ok,
      result: {task_id: row.task_id, request_id: runId, session_id: 'e'.repeat(32)}},
  }};
  for (const callback of [...listeners]) callback(event);
};
(async () => {
  const wrong = observe(row);
  wrong.start();
  await dispatch('9'.repeat(32));
  send('1'.repeat(32));
  await assert.rejects(wrong.promise, /typed execution receipt is invalid/);
  assert.equal(listeners.size, 0);
  assert.equal(window.pywebview.api.dispatch, nativeDispatch);
  const refused = observe(row);
  refused.start();
  await dispatch();
  send('1'.repeat(32), false);
  await assert.rejects(refused.promise, /typed execution receipt is invalid/);
  assert.equal(window.pywebview.api.dispatch, nativeDispatch);
  const receipt = observe(row);
  receipt.start();
  await dispatch();
  send('1'.repeat(32), true, '2'.repeat(32));
  assert.equal(receipt.peek(), false);
  assert.equal(listeners.size, 1);
  send('1'.repeat(32));
  const value = await receipt.promise;
  assert.equal(value.value.request_id, '1'.repeat(32));
  assert.notEqual(value.value.request_id, row.request_id);
  assert.equal(receipt.peek(), true);
  assert.deepEqual(receipt.facts().exact, true);
  assert.equal(listeners.size, 0);
  assert.equal(window.pywebview.api.dispatch, nativeDispatch);
  const replay = observe(row);
  replay.start();
  await dispatch();
  await dispatch(row.request_id, '6'.repeat(32));
  send('1'.repeat(32), true, '6'.repeat(32));
  await replay.promise;
  assert.equal(replay.facts().exact, true);
  const independent = observe(row);
  independent.start();
  await dispatch();
  await dispatch(row.request_id, '6'.repeat(32), '7'.repeat(32));
  send('1'.repeat(32), true, '6'.repeat(32));
  await assert.rejects(independent.promise, /typed execution receipt is invalid/);
  assert.equal(window.pywebview.api.dispatch, nativeDispatch);
})().catch((error) => {console.error(error); process.exitCode = 1;});
"""
    completed = subprocess.run(
        (str(node), "--max-old-space-size=128", "-e", harness),
        input=json.dumps([helper, observer_source]), capture_output=True, text=True,
        timeout=20, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr



def test_ui_start_settlement_binds_public_plan_and_returned_session() -> None:
    node = _node_executable()
    assert node is not None, "Node.js is required for the U start settlement control"
    script = adapter._rootless_probe_script(adapter.CASES[3])
    start = script.index("  async function settleStartedExecution(prepared, observation) {")
    end = script.index("  async function prepareExecutionControl(", start)
    source = script[start:end]
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = JSON.parse(fs.readFileSync(0, 'utf8'));
const TASK = `task-${'a'.repeat(32)}`;
const PLAN = 'b'.repeat(32);
const RUN = 'c'.repeat(32);
const SESSION = 'd'.repeat(32);
const summary = {task_id: TASK, task_kind: 'sync-plan',
  request_id: PLAN, session_id: SESSION};
const bridge = {listTasks: async () => ({tasks: [summary]})};
const until = async (predicate) => {
  if (!predicate()) throw Error('execution admission did not settle');
};
const document = {querySelector: () => ({open: false})};
const settle = new Function('bridge', 'until', 'document',
  `${source}; return settleStartedExecution;`)(bridge, until, document);
const prepared = {row: {task_id: TASK, request_id: PLAN},
  review: {dataset: {pending: ''}, querySelector: () => ({disabled: false})}};
const receipt = {value: {task_id: TASK, request_id: RUN, session_id: SESSION}};
(async () => {
  assert.equal((await settle(prepared, {promise: Promise.resolve(receipt)})).value.request_id, RUN);
  summary.request_id = 'e'.repeat(32);
  await assert.rejects(settle(prepared, {promise: Promise.resolve(receipt)}), /current task run/);
  summary.request_id = PLAN;
  summary.session_id = 'e'.repeat(32);
  await assert.rejects(settle(prepared, {promise: Promise.resolve(receipt)}), /current task run/);
})().catch((error) => {console.error(error); process.exitCode = 1;});
"""
    completed = subprocess.run(
        (str(node), "--max-old-space-size=128", "-e", harness),
        input=json.dumps(source), capture_output=True, text=True,
        timeout=20, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr



@pytest.mark.parametrize("site", ("total", "warmup"))
def test_ui_script_adapter_refuses_changed_site(monkeypatch: pytest.MonkeyPatch, site: str) -> None:
    original = adapter.legacy._headed_probe_script(adapter.CASES[1])
    if site == "total":
        changed = original.replace("initialWindow.total !== 120000", "initialWindow.total !== 119999")
    else:
        changed = original.replace("warmupCheckbox.click();", "warmupCheckbox.dispatch();")
    monkeypatch.setattr(adapter, "_original_headed_probe_script", lambda *_args, **_kwargs: changed)
    with pytest.raises(ValueError, match="adaptation site changed"):
        adapter._rootless_probe_script(adapter.CASES[1])
