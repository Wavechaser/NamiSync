import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { assertSameNode, assertSameNodes } from "./fake_dom_assertions.mjs";
import { fakeRecoveryHandle } from "./fake_recovery_handle.mjs";

class ClassList {
  constructor() { this.values = new Set(); }
  add(...values) { for (const value of values) this.values.add(value); }
}

class ElementFake {
  [Symbol.for("nodejs.util.inspect.custom")]() {
    return `ElementFake<${this.tagName.slice(0, 24)}>`;
  }
  constructor(tagName, textContent = "") {
    this.tagName = tagName.toUpperCase();
    this.textContent = textContent;
    this.children = [];
    this.parentNode = null;
    this.classList = new ClassList();
    this.listeners = new Map();
    this.disabled = false;
  }

  append(...values) {
    for (const value of values) {
      value.remove?.();
      value.parentNode = this;
      this.children.push(value);
    }
  }

  replaceChildren(...values) {
    for (const child of this.children) child.parentNode = null;
    this.children = [];
    this.append(...values);
  }

  remove() {
    if (this.parentNode === null) return;
    this.parentNode.children = this.parentNode.children.filter((item) => item !== this);
    this.parentNode = null;
  }

  addEventListener(name, callback) {
    const callbacks = this.listeners.get(name) ?? [];
    callbacks.push(callback);
    this.listeners.set(name, callbacks);
  }

  click() {
    if (this.disabled) return;
    for (const callback of this.listeners.get("click") ?? []) callback();
  }

  setAttribute(name, value) { this[name] = value; }
}

globalThis.HTMLElement = ElementFake;
globalThis.HTMLSelectElement = ElementFake;
const app = new ElementFake("main");
const status = new ElementFake("p", "Starting...");
const theme = new ElementFake("div");
const settings = new ElementFake("div");
const themeOptions = new ElementFake("div");
const body = new ElementFake("body");
globalThis.document = {
  documentElement: new ElementFake("html"),
  body,
  createElement(tagName) { return new ElementFake(tagName); },
  querySelector(selector) {
    return selector === "#app" ? app
      : selector === "#host-status" ? status
        : selector === "#settings-view" ? settings
          : selector === "#theme-options" ? themeOptions : theme;
  },
};

const windowListeners = new Map();
globalThis.window = {
  chrome: { webview: {} },
  addEventListener(name, callback) {
    const callbacks = windowListeners.get(name) ?? [];
    callbacks.push(callback);
    windowListeners.set(name, callbacks);
  },
};

const TASK_A = `task-${"a".repeat(32)}`;
const TASK_B = `task-${"b".repeat(32)}`;
const TASK_C = `task-${"c".repeat(32)}`;
const TASK_D = `task-${"d".repeat(32)}`;
const TASK_E = `task-${"e".repeat(32)}`;
const TASK_F = `task-${"f".repeat(32)}`;
const SESSION_E = "5".repeat(32);
const SESSION_G = "7".repeat(32);
const TASK_G = `task-${"7".repeat(32)}`;
const snapshotRevisions = new Map();
const pageSnapshot = (taskId, sessionId, facts = {}) => {
  const key = `${taskId}:${sessionId}`;
  const revision = (snapshotRevisions.get(key) ?? 0) + 1;
  snapshotRevisions.set(key, revision);
  return {
    wire_version: 1, task_id: taskId, session_id: sessionId, revision,
    session_state: "active", control_state: "running", phase: null,
    phase_authority: "unknown", progress: null, active_item: null,
    presentation: { aggregate_percent: null, item_percent: null,
      items_done: null, items_total: null, throughput_bytes_per_second: null,
      eta_seconds: null, value: 0, determinate: false, indeterminate: true },
    gap_first_missed_seq: null, terminal_result: null, started_at: null, ended_at: null,
    ...facts,
  };
};
const calls = [];
const creates = [];
const closes = [];
const drains = new Map();
const lists = [];
const planOpens = [];
const planWindows = [];
const planViewUpdates = [];
const planSelections = [];
const planAnchors = [];
const planHighlights = [];
const planExecutions = [];
const executionControls = [];
const planAgainStarts = [];
const setupReads = [];
const executionDetails = [];
const reviewRenders = [];
const confirmationRequests = [];
const executeInvoker = new HTMLElement("button");
let StartPlanUncertainErrorType = null;
let OutcomeUnavailableErrorType = null;
let nextHighlightSummary = null;
let deferAnchor = false;
let deferHighlight = false;

function deferred(collection, onDelayed = null) {
  let resolve;
  let reject;
  const promise = new Promise((acceptResolve, onReject) => {
    resolve = acceptResolve;
    reject = onReject;
  });
  const recovery = onDelayed === null ? null : fakeRecoveryHandle({ state: "submitting", message: null });
  if (recovery !== null) onDelayed(recovery);
  const entry = { promise, resolve, recovery,
    notify(fields) {
      Object.assign(this.recovery, fields);
      onDelayed?.(this.recovery);
    },
    reject,
  };
  collection.push(entry);
  return promise;
}

globalThis.taskHarness = {
  calls,
  createTask(onDelayed) { calls.push(["create"]); return deferred(creates, onDelayed); },
  closeTask(taskId, sessionId, onDelayed) {
    calls.push(["close", taskId, sessionId]);
    const promise = deferred(closes, onDelayed);
    return promise;
  },
  listTasks() { calls.push(["list"]); return deferred(lists); },
  startTaskDrain(taskId, sessionId, acceptUpdate, acceptRefusal, initialState, acceptRelease, acceptRecovered, acceptReleaseDelay) {
    calls.push(["drain", taskId, sessionId, initialState]);
    drains.set(taskId, { acceptUpdate, acceptRefusal, acceptRelease, acceptRecovered, acceptReleaseDelay });
    return () => calls.push(["stop", taskId]);
  },
  openPlanView(...args) { calls.push(["open-plan", ...args]); return deferred(planOpens); },
  getPlanWindow(...args) { calls.push(["plan-window", ...args]); return deferred(planWindows); },
  getPlanAnchor(...args) {
    calls.push(["plan-anchor", ...args]);
    return deferAnchor ? deferred(planAnchors) : Promise.reject(new Error("anchor unavailable"));
  },
  getPlanOperationAnchor(...args) {
    calls.push(["plan-operation-anchor", ...args]);
    return deferAnchor ? deferred(planAnchors) : Promise.reject(new Error("operation anchor unavailable"));
  },
  getExecutionDetail(...args) {
    calls.push(["execution-detail", ...args]);
    return deferred(executionDetails);
  },
  updatePlanView(...args) {
    assert.equal(typeof args.at(-1), "function", "view mutation exposes delay feedback");
    calls.push(["update-plan", ...args.slice(0, -1)]);
    return deferred(planViewUpdates);
  },
  mutatePlanHighlight(...args) {
    assert.equal(typeof args.at(-1), "function", "highlight mutation exposes delay feedback");
    calls.push(["highlight-plan", ...args.slice(0, -1)]);
    if (deferHighlight) return deferred(planHighlights);
    const result = nextHighlightSummary ?? planSummary();
    nextHighlightSummary = null;
    return Promise.resolve(result);
  },
  mutatePlanSelection(...args) {
    assert.equal(typeof args.at(-1), "function", "selection mutation exposes delay feedback");
    calls.push(["select-plan", ...args.slice(0, -1)]);
    return deferred(planSelections, args.at(-1));
  },
  startExecution(...args) {
    assert.equal(typeof args.at(-1), "function", "execution admission exposes delay feedback");
    calls.push(["execute-plan", ...args.slice(0, -1)]);
    const promise = deferred(planExecutions, args.at(-1));
    return promise;
  },
  controlExecution(...args) {
    assert.equal(typeof args.at(-1), "function", "execution control exposes delay feedback");
    calls.push(["control-execution", ...args.slice(0, -1)]);
    const promise = deferred(executionControls, args.at(-1));
    return promise;
  },
  planAgain(...args) {
    assert.equal(typeof args.at(-1), "function", "plan-again exposes delay feedback");
    calls.push(["plan-again", ...args.slice(0, -1)]);
    return deferred(planAgainStarts, args.at(-1));
  },
  readSetup(taskId = null) {
    const plan = taskId === TASK_G;
    const options = {
      filters: [], deletion_policy: "trash", trash_on_update: false,
      preservation: { preserve_ads: false, preserve_created: true, preserve_acl: false },
      propagate_source_casing: false, verify_after_execute: false,
    };
    const result = {
      task_id: taskId,
      snapshot: plan ? {
        setup_state: "frozen", task_kind: "sync-plan",
        source: { location_id: "source-location", display: "C:\\source" },
        target: { location_id: "target-location", display: "D:\\target" },
        root: null, options, plan_again: { available: true },
      } : {
        setup_state: "default", task_kind: null, source: null, target: null, root: null,
        options, plan_again: null,
      },
      recents: taskId === null ? { sources: [], targets: [], pairs: [] } : null,
    };
    if (taskId === TASK_G && globalThis.taskHarness.deferTaskGSetup) {
      const pending = deferred(setupReads);
      setupReads.at(-1).result = result;
      return pending;
    }
    return Promise.resolve(result);
  },
  deferTaskGSetup: false,
};
globalThis.planReviewHarness = { callbacks: null, reviewRenders };
globalThis.executionConfirmationHarness = { confirmationRequests, roots: null };

function moduleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

const renderUrl = moduleUrl(
  'export const renderText = (element, text) => { element.textContent = text; }; export const renderFilesystemText = (element, text) => { element.textContent = text; };',
);
const iconsUrl = moduleUrl(`
  export const createIcon = (document) => document.createElement("svg");
`);
const digestRenderUrl = moduleUrl(await readFile(join(dirname(process.argv[3]), "render.js"), "utf8"));
const taskStatusUrl = moduleUrl((await readFile(join(dirname(process.argv[3]), "task_status.js"), "utf8"))
  .replace("./render.js", digestRenderUrl));
const { taskStatusDigest } = await import(taskStatusUrl);
assert.equal(taskStatusDigest({}).title, "New task");
assert.equal(taskStatusDigest({}).progress.indeterminate, false);
assert.equal(taskStatusDigest({ taskKind: "inventory", sessionState: "active" }).title, "Inventory");
assert.equal(taskStatusDigest({ taskKind: "sync-plan", sessionState: "active", error: "Planning failed." }).progress.indeterminate, false);
assert.equal(taskStatusDigest({ form: { attempt: { kind: "sync-plan", dispatched: true, running: true } } }).detail, "Planning in progress.");
assert.equal(taskStatusDigest({ taskKind: "sync-plan", sessionState: "active" }).progress.indeterminate, true);
assert.equal(taskStatusDigest({ taskKind: "sync-plan", reviewLoading: true,
  review: { summary: { filter_counts: { all: 2 }, required_bytes: "0" } },
}).progress.indeterminate, true);
assert.equal(taskStatusDigest({ taskKind: "sync-plan", form: {
  attempt: { kind: "sync-plan", dispatched: true, running: true },
} }).progress.indeterminate, true);
assert.equal(taskStatusDigest({ taskKind: "sync-plan", form: {
  attempt: { kind: "sync-plan", dispatched: true, running: true },
} }).title, "Planning");
assert.equal(taskStatusDigest({ taskKind: "sync-plan", form: {
  attempt: { kind: "plan-again", dispatched: true, running: true },
} }).progress.indeterminate, true);
assert.equal(taskStatusDigest({ taskKind: "sync-plan", form: {
  attempt: { kind: "sync-plan", dispatched: false, running: true },
} }).progress.indeterminate, false);
assert.equal(taskStatusDigest({ taskKind: "sync-plan", reviewLoading: true,
  error: "Plan unavailable.",
}).progress.indeterminate, false);
assert.equal(taskStatusDigest({ taskKind: "sync-plan", sessionState: "active",
  review: { summary: { filter_counts: { all: 2 }, required_bytes: "0" } },
}).progress.indeterminate, false);
assert.equal(taskStatusDigest({ taskKind: "sync-plan", reviewLoading: false,
  review: { summary: { filter_counts: { all: 2 }, required_bytes: "0" } },
}).progress.indeterminate, false);
assert.equal(taskStatusDigest({ sessionState: "completed", review: { summary: {
  filter_counts: { all: 2 }, required_bytes: "1024", operation_count: 2,
} } }).title, "Plan ready");
assert.equal(taskStatusDigest({ executionStarted: true, sessionState: "active",
  executionControlState: "paused" }).title, "Paused");
assert.equal(taskStatusDigest({ executionStarted: true, sessionState: "active",
  sessionId: "8".repeat(32),
  snapshot: { session_id: "8".repeat(32), session_state: "active", phase: "verify", presentation: {
    value: 50, determinate: true, indeterminate: false,
    items_done: 2, items_total: 4,
    throughput_bytes_per_second: null, eta_seconds: null,
  } } }).progress.value, 50);
assert.equal(taskStatusDigest({ sessionState: "completed", review: { summary: {
  filter_counts: { all: 180 }, required_bytes: "5368709120", selected_operation_count: 0,
  preflight_ready: false,
} } }).detail, "0 items, 5.00 GiB required.");
assert.equal(taskStatusDigest({ sessionState: "completed", review: { summary: {
  filter_counts: { all: 180 }, selected_operation_count: 3, required_bytes: "1024",
} } }).detail, "3 items, 1.00 KiB required.");
assert.equal(taskStatusDigest({ sessionState: "completed", review: { summary: {
  filter_counts: { all: 0 }, required_bytes: "0",
} } }).detail, "Plan is empty.");
assert.equal(taskStatusDigest({ executionStarted: true, sessionState: "active",
  sessionId: "8".repeat(32),
  snapshot: { session_id: "8".repeat(32), session_state: "active", phase: "verify", presentation: {
    value: 0, determinate: false, indeterminate: true,
    items_done: null, items_total: null,
    throughput_bytes_per_second: null, eta_seconds: null,
  } } }).title, "Verifying");
assert.equal(taskStatusDigest({ executionStarted: true, sessionState: "refused" }).title, "Error");
assert.equal(taskStatusDigest({ form: { source: { text: "source" }, target: { text: "" } } }).targetPath, "-");
const capacityRailResult = {
  headline: "failed", filesystem: "failed", integrity: "baselined",
  recording: "ok", audit: "ok", disposition: "ran", error: null,
};
const capacityRailWindow = {
  result: capacityRailResult, failed_operation_count: 1, disk_capacity_failure_count: 1,
};
assert.equal(taskStatusDigest({
  executionStarted: true, sessionState: "failed", executionResult: capacityRailResult,
  review: { window: { execution: capacityRailWindow } },
}).title, "Needs target space");
assert.equal(taskStatusDigest({
  executionStarted: true, sessionState: "failed",
  executionResult: { ...capacityRailResult, integrity: "mismatch" },
  review: { window: { execution: capacityRailWindow } },
}).title, "Failed", "stale retained capacity cannot recolor the rail");
const railSource = (await readFile(process.argv[3], "utf8"))
  .replace("./icons.js", iconsUrl)
  .replace("./render.js", renderUrl)
  .replace("./task_status.js", taskStatusUrl);
const panelSource = (await readFile(process.argv[4], "utf8"))
  .replace("./render.js", renderUrl);
const setupUrl = moduleUrl(`
  export function createSetupPanel() {
    const element = new HTMLElement("div");
    return { element, render() {} };
  }
`);
const planReviewUrl = moduleUrl(`
  export function createPlanReviewPanel(callbacks) {
    globalThis.planReviewHarness.callbacks = callbacks;
    const element = new HTMLElement("div", "Plan review test surface");
    return {
      element,
      render(task) { globalThis.planReviewHarness.reviewRenders.push(task); },
      dispose() {},
    };
  }
`);
const preparedPanelSource = panelSource
  .replace("./setup.js", setupUrl)
  .replace("./plan_review.js", planReviewUrl);
const executionConfirmationUrl = moduleUrl(`
  export function createExecutionConfirmation(roots) {
    globalThis.executionConfirmationHarness.roots = roots;
    return {
      element: new HTMLElement("dialog"),
      show(request) { globalThis.executionConfirmationHarness.confirmationRequests.push(request); },
    };
  }
`);
const bridgeUrl = moduleUrl(`
  export class BridgeTransportError extends Error {}
  export class OutcomeUnavailableError extends BridgeTransportError {
    constructor(retry, checkable = true) { super(); this.retry = retry; this.checkable = checkable; }
  }
  export class StartPlanUncertainError extends BridgeTransportError {
    constructor(retry, checkable = true) { super(); this.retry = retry; this.checkable = checkable; }
  }
  export class TaskCreateUncertainError extends BridgeTransportError {
    constructor(retry, checkable = true) { super(); this.retry = retry; this.checkable = checkable; }
  }
  export class TaskCloseUncertainError extends BridgeTransportError {
    constructor(retry, checkable = true) { super(); this.retry = retry; this.checkable = checkable; }
  }
  export class TerminalPresentationError extends BridgeTransportError {}
  export class TerminalSessionReleaseError extends BridgeTransportError {}
  export const acknowledgeShellReady = () => Promise.resolve({ acknowledged: true });
  export const echoReadiness = () => Promise.resolve({ acknowledged: true });
  export const whenBridgeApiReady = () => Promise.resolve();
  export const markBridgeOperational = () => {};
  export const createTask = (...args) => globalThis.taskHarness.createTask(...args);
  export const closeTask = (...args) => globalThis.taskHarness.closeTask(...args);
  export const listTasks = () => globalThis.taskHarness.listTasks();
  export const controlExecution = (...args) => globalThis.taskHarness.controlExecution(...args);
  export const getPlanAnchor = (...args) => globalThis.taskHarness.getPlanAnchor(...args);
  export const getPlanOperationAnchor = (...args) => globalThis.taskHarness.getPlanOperationAnchor(...args);
  export const getPlanWindow = (...args) => globalThis.taskHarness.getPlanWindow(...args);
  export const getExecutionDetail = (...args) => globalThis.taskHarness.getExecutionDetail(...args);
  export const mutatePlanSelection = (...args) => globalThis.taskHarness.mutatePlanSelection(...args);
  export const openPlanView = (...args) => globalThis.taskHarness.openPlanView(...args);
  export const readSetup = (...args) => globalThis.taskHarness.readSetup(...args);
  export const admitLocation = () => Promise.reject(new BridgeTransportError());
  export const pickFolder = () => Promise.reject(new BridgeTransportError());
  export const prepareSetup = () => Promise.reject(new BridgeTransportError());
  export const startPlan = () => Promise.reject(new BridgeTransportError());
  export const startInventory = () => Promise.reject(new BridgeTransportError());
  export const startExecution = (...args) => globalThis.taskHarness.startExecution(...args);
  export const planAgain = (...args) => globalThis.taskHarness.planAgain(...args);
  export const startTaskDrain = (...args) => globalThis.taskHarness.startTaskDrain(...args);
  export const updatePlanView = (...args) => globalThis.taskHarness.updatePlanView(...args);
  export const mutatePlanHighlight = (...args) => globalThis.taskHarness.mutatePlanHighlight(...args);
`);
StartPlanUncertainErrorType = (await import(bridgeUrl)).StartPlanUncertainError;
OutcomeUnavailableErrorType = (await import(bridgeUrl)).OutcomeUnavailableError;
const readinessUrl = moduleUrl(`
  export const installReadinessReceiver = () => ({
    revision: () => 0,
    whenReceivedAfter: () => Promise.resolve("0".repeat(32)),
  });
`);
const appearanceUrl = moduleUrl("export const installAppearanceReceiver = () => ({});");
const themeUrl = moduleUrl(`
  export const installThemeCombobox = (root) => root;
  export const installThemeSelector = () => ({
    invalidate() {}, refresh() { return Promise.resolve(); }, open() {},
  });
`);
let appSource = await readFile(process.argv[2], "utf8");
appSource = appSource.replace(
  /import \{[\s\S]*?\} from "\.\/bridge\.js";/,
  `import { acknowledgeShellReady, admitLocation, BridgeTransportError, closeTask, controlExecution, createTask, echoReadiness, getExecutionDetail, getPlanAnchor, getPlanOperationAnchor, getPlanWindow, listTasks, markBridgeOperational, mutatePlanHighlight, mutatePlanSelection, openPlanView, OutcomeUnavailableError, pickFolder, planAgain, prepareSetup, readSetup, StartPlanUncertainError, startExecution, startInventory, startPlan, startTaskDrain, TaskCloseUncertainError, TaskCreateUncertainError, TerminalPresentationError, TerminalSessionReleaseError, updatePlanView, whenBridgeApiReady } from "${bridgeUrl}";`,
);
appSource = appSource
  .replace("./readiness.js", readinessUrl)
  .replace("./appearance.js", appearanceUrl)
  .replace("./theme.js", themeUrl)
  .replace("./execution_confirmation.js", executionConfirmationUrl)
  .replace("./task_status.js", taskStatusUrl)
  .replace("./rail.js", moduleUrl(railSource))
  .replace("./panels.js", moduleUrl(preparedPanelSource))
  .replace("./render.js", renderUrl);
appSource += "\nglobalThis.taskHarness.forceReview = loadPlanReview;\n"
  + "globalThis.taskHarness.adoptTask = adoptTask;\n"
  + "globalThis.taskHarness.closeRetainedTask = closeRetainedTask;\n"
  + "globalThis.taskHarness.refreshTasks = refreshTasks;\n";

function walk(root) {
  return [root, ...root.children.flatMap(walk)];
}

function byText(text) {
  if (/^Task \d+$/.test(text)) return taskButton(text);
  return walk(app).find((element) => element.textContent === text);
}

function createButton() {
  return walk(app).find((element) => element.classList.values.has("nami-task-rail__create"));
}

function taskButton(label) {
  return walk(app).find(
    (element) => element.tagName === "BUTTON" && element.dataset?.taskLabel === label,
  );
}

function taskButtons() {
  return walk(app).filter(
    (element) => element.tagName === "BUTTON" &&
      element.classList.values.has("nami-task-card") &&
      element.parentNode.classList.values.has("nami-task-rail__row"),
  );
}

function settingsButton() {
  return walk(app).find(
    (element) => element.classList.values.has("nami-task-rail__settings"),
  );
}

async function turns(count = 12) {
  for (let index = 0; index < count; index += 1) await Promise.resolve();
}

async function until(predicate) {
  for (let index = 0; index < 100; index += 1) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  throw new Error("task-shell probe condition timed out");
}

function planSummary(overrides = {}) {
  return {
    disposition: "opened",
    task_id: TASK_G,
    request_id: "a".repeat(32),
    view_revision: 0,
    selection_revision: 0,
    selection_state: "reviewing",
    highlight_revision: 0,
    highlight_anchor_node_id: null,
    highlight_focus_node_id: null,
    highlight_focus_visible_index: null,
    highlighted_count: 0,
    source_path: "C:\\source",
    target_path: "D:\\target",
    selected_operation_count: 1,
    selectable_operation_count: 1,
    scope_selected_operation_count: 1,
    scope_selectable_operation_count: 1,
    operation_count: 1,
    filter_counts: { all: 1, copy: 1, mkdir: 0, move: 0, recase: 0,
      update: 0, move_update: 0, trash: 0, delete: 0, noop: 0,
      blocked: 0, unsupported: 0, error: 0, notice: 0 },
    preflight_ready: false,
    preflight_refusal_count: 1,
    warning_count: 1,
    requires_destructive_confirmation: false,
    destructive_operation_count: 0,
    destructive_operation_counts: { update: 0, move_update: 0, trash: 0, delete: 0 },
    irreversible_operation_count: 0,
    irreversible_update_count: 0,
    required_bytes: "0",
    visible_row_count: 1,
    search_query: "",
    filters: [],
    sort_column: "path",
    sort_direction: "ascending",
    collapsed_count: 0,
    execution: {
      execution_revision: 0,
      session_id: null,
      result: null,
      failed_operation_count: null,
      disk_capacity_failure_count: null,
      gap: null,
      trash_location: null,
    },
    ...overrides,
  };
}

function planWindow(summary, offset = 0) {
  return {
    disposition: "current",
    view_revision: summary.view_revision,
    highlight_revision: summary.highlight_revision,
    offset,
    total: 1,
    execution: summary.execution,
    rows: [{
      node_id: `node-${"b".repeat(32)}`,
      display: "Source changed after planning",
      depth: 0,
      is_container: false,
      visible_index: 0,
      parent_visible_index: null,
      first_child_visible_index: null,
      position_in_set: 1,
      set_size: 1,
      expanded: null,
      row_kind: "notice",
      operation_id: null,
      operation_kind: null,
      reason: null,
      blocked_reason: null,
      selection: "disabled",
      highlighted: false,
      selectable_operation_count: 0,
      selected_operation_count: 0,
      operation_count: 0,
      size: null,
      mtime_ns: null,
      dependency_count: 0,
      risk: "none",
      move_peer_id: null,
      notice: "The source changed. Create a fresh plan.",
      selection_exclusion_reason: null,
      execution: null,
    }],
  };
}

const imported = import(moduleUrl(appSource));
await until(() => lists.length === 1);
lists[0].resolve({ tasks: [
  { task_id: TASK_A, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_B, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_E, session_id: SESSION_E, session_state: "active", session_released: false },
] });
await imported;
await turns();

assert.equal(taskButton("Task 3")?.ariaCurrent, "page");
assert.deepEqual(
  taskButtons().map((button) => button.dataset.taskLabel),
  ["Task 3", "Task 2", "Task 1"],
  "task rail must be newest-first",
);
const stableTaskBButton = taskButton("Task 2");
taskButton("Task 2").click();
assert.equal(taskButton("Task 2")?.ariaCurrent, "page");
taskButton("Task 1").click();
assert.equal(taskButton("Task 1")?.ariaCurrent, "page");

createButton().click();
await until(() => creates.length === 1);
taskButton("Task 2").click();
creates[0].resolve({ task_id: TASK_C });
await turns();
assert.equal(taskButton("Task 2")?.ariaCurrent, "page", "late create must not steal navigation");
assert.ok(byText("Task 4"));

createButton().click();
await until(() => creates.length === 2);
void globalThis.taskHarness.refreshTasks();
await until(() => lists.length === 2);
creates[1].resolve({ task_id: TASK_D });
await turns();
assert.ok(byText("Task 5"), "an admitted create remains visible in its document");
lists[1].resolve({ tasks: [
  { task_id: TASK_A, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_B, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_C, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_E, session_id: SESSION_E, session_state: "active", session_released: false },
] });
await until(() => lists.length === 3);
await turns();
assert.ok(byText("Task 5"), "a list overtaken by create is stale");
const retainedThroughD = { tasks: [
  { task_id: TASK_A, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_B, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_C, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_D, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_E, session_id: SESSION_E, session_state: "active", session_released: false },
] };
lists[2].resolve(retainedThroughD);
await turns();
assert.ok(byText("Task 5"), "current list retains the admitted task");
assert.ok(taskButton("Task 2") === stableTaskBButton, "refresh preserves existing cards");

void globalThis.taskHarness.refreshTasks();
await until(() => lists.length === 4);
createButton().click();
await until(() => creates.length === 3);
creates[2].resolve({ task_id: TASK_F });
await turns();
assert.ok(byText("Task 6"));
lists[3].resolve({ tasks: [
  { task_id: TASK_A, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_B, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_C, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_D, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_E, session_id: SESSION_E, session_state: "active", session_released: false },
] });
await until(() => lists.length === 5);
lists[4].resolve({ tasks: [
  ...retainedThroughD.tasks,
  { task_id: TASK_F, session_id: null, session_state: null, session_released: false },
] });
await turns();
assert.ok(byText("Task 6"), "a delayed list cannot erase a completed create");

taskButton("Task 1").click();
void globalThis.taskHarness.refreshTasks();
await until(() => lists.length === 6);
const firstClose = walk(app).find((element) => element.ariaLabel === "Close Task 1");
firstClose.click();
await until(() => closes.length === 1);
assert.ok(byText("Task 1"), "card remains until close success");
closes[0].resolve({ task_id: TASK_A, session_id: null, disposition: "closed" });
await turns();
assert.ok(byText("Task 1") === undefined, "closed task is absent");
assert.equal(taskButton("Task 6")?.ariaCurrent, "page", "close selects the newest task");
lists[5].resolve({ tasks: [
  { task_id: TASK_A, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_B, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_C, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_D, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_E, session_id: SESSION_E, session_state: "active", session_released: false },
  { task_id: TASK_F, session_id: null, session_state: null, session_released: false },
] });
await until(() => lists.length === 7);
lists[6].resolve({ tasks: [
  { task_id: TASK_B, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_C, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_D, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_E, session_id: SESSION_E, session_state: "active", session_released: false },
  { task_id: TASK_F, session_id: null, session_state: null, session_released: false },
] });
await turns();
assert.ok(byText("Task 1") === undefined, "a delayed list cannot restore a closed task");

const busyClose = walk(app).find((element) => element.ariaLabel === "Close Task 3");
busyClose.click();
await until(() => closes.length === 2);
closes[1].resolve({ task_id: TASK_E, session_id: SESSION_E, disposition: "pending" });
await turns();
assert.ok(byText("Canceling and closing…"));
drains.get(TASK_E).acceptUpdate({ update_type: "record", record: { state: "canceled" } },
  pageSnapshot(TASK_E, SESSION_E, { session_state: "canceled" }));
await until(() => closes.length === 3);
assert.deepEqual(calls.at(-1), ["close", TASK_E, SESSION_E]);
closes[2].resolve({ task_id: TASK_E, session_id: SESSION_E, disposition: "closed" });
await turns();
assert.ok(byText("Task 3") === undefined, "closed active task is absent");

void globalThis.taskHarness.refreshTasks();
await until(() => lists.length === 8);
lists[7].resolve({ tasks: [
  { task_id: TASK_B, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_C, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_D, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_F, session_id: null, session_state: null, session_released: false },
  {
    task_id: TASK_G, session_id: SESSION_G, session_state: "completed",
    session_released: false, task_kind: "sync-plan", request_id: "a".repeat(32),
  },
] });
await turns();
assert.ok(byText("Completed"));
assert.deepEqual(
  calls.find((call) => call[0] === "drain" && call[1] === TASK_G),
  ["drain", TASK_G, SESSION_G, { terminal: true, sessionReleased: false }],
  "a retained terminal task resumes release without losing terminal truth",
);

globalThis.taskHarness.deferTaskGSetup = true;
taskButton("Task 7").click();
drains.get(TASK_G).acceptRelease(TASK_G, SESSION_G);
await until(() => planOpens.length === 1);
assert.deepEqual(calls.at(-1), ["open-plan", TASK_G]);
const firstLoadingSurface = byText("Plan review test surface");
assert.ok(firstLoadingSurface, "selected task shows the retained review while loading");
planOpens[0].reject(new Error("simulated initial plan open failure"));
await until(() => byText("Plan unavailable. Select the task to retry.") !== undefined);
assert.ok(byText("Loading task setup…"), "a failed Plan load leaves the Plan surface");
assert.ok(byText("Plan review test surface") === undefined, "failed Plan surface is absent");
assertSameNode(firstLoadingSurface.parentNode, null, "refused load detaches the loading review");

taskButton("Task 7").click();
await until(() => planOpens.length === 2);
assert.deepEqual(calls.at(-1), ["open-plan", TASK_G]);
planOpens[1].resolve(planSummary());
await until(() => planWindows.length === 1);
planWindows[0].reject(new Error("simulated initial plan window failure"));
await until(() => byText("Plan unavailable. Select the task to retry.") !== undefined);
assert.ok(byText("Loading task setup…"));
assert.ok(byText("Plan review test surface") === undefined, "failed Plan surface is absent");

taskButton("Task 7").click();
taskButton("Task 7").click();
await until(() => planOpens.length === 3);
await turns();
assert.equal(planOpens.length, 3, "rapid reselection keeps one Plan retry in flight");
assert.ok(byText("Plan review test surface"), "Plan retry exposes its loading surface");
assertSameNode(byText("Plan review test surface"), firstLoadingSurface,
  "retry reuses the same review element after refusal");
assert.equal(reviewRenders.at(-1).reviewLoading, true);
const refusedReview = planSummary();
planOpens[2].resolve(refusedReview);
await until(() => planWindows.length === 2);
planWindows[1].resolve(planWindow(refusedReview));
await until(() => reviewRenders.at(-1)?.review?.summary === refusedReview);
assertSameNode(byText("Plan review test surface"), firstLoadingSurface,
  "loaded review remains attached after the delayed window arrives");
const firstReview = reviewRenders.at(-1).review;
assert.match(firstReview.message, /Plan failed review/, "actionable warnings remain");
assert.equal(reviewRenders.at(-1).error, null, "a successful selection retry clears the rail error");
assert.equal(reviewRenders.at(-1).canPlanAgain, false, "Plan again waits for task setup readiness");
globalThis.planReviewHarness.callbacks.onPlanAgain(firstReview);
assert.equal(planAgainStarts.length, 0, "pre-readiness Plan again cannot dispatch");
assert.match(firstReview.message, /current action/);
assert.equal(setupReads.length, 4);
globalThis.taskHarness.deferTaskGSetup = false;
setupReads[0].resolve(setupReads[0].result);
await turns();
assert.equal(reviewRenders.at(-1).canPlanAgain, false, "an older Setup read stays stale");
setupReads[3].resolve(setupReads[3].result);
await until(() => reviewRenders.at(-1).canPlanAgain === true);
const cachedPlanOpenCount = planOpens.length;
taskButton("Task 7").click();
await turns();
assert.equal(planOpens.length, cachedPlanOpenCount, "selecting a current review uses its cache");
assert.equal(firstReview.summary.preflight_ready, false);
assert.equal(firstReview.window.rows[0].row_kind, "notice");

const originalWindow = firstReview.window;
const priorRenderCount = reviewRenders.length;
globalThis.planReviewHarness.callbacks.onWindow(firstReview, 256);
globalThis.planReviewHarness.callbacks.onWindow(firstReview, 512);
assert.equal(planWindows.length, 3, "scroll reads have at most one transport in flight");
assert.equal(firstReview.foregroundWindowReaders, 1, "the whole scroll pump owns one foreground reader");
assert.equal(firstReview.pending, null, "window reads do not disable review actions");
assert.equal(reviewRenders.length, priorRenderCount, "fetch start does not remount the review");
planWindows[2].resolve(planWindow(refusedReview, 256));
await until(() => planWindows.length === 4);
assert.equal(firstReview.window, originalWindow, "superseded offset cannot publish");
assert.deepEqual(calls.at(-1), ["plan-window", TASK_G, 0, 512, 256]);
const latestWindow = planWindow(refusedReview, 512);
planWindows[3].resolve(latestWindow);
await until(() => !firstReview.windowRequestRunning);
assert.equal(firstReview.window, latestWindow);
assert.equal(firstReview.foregroundWindowReaders, 0);
assert.equal(reviewRenders.length, priorRenderCount + 1, "one current receipt renders once");
globalThis.planReviewHarness.callbacks.onWindow(firstReview, 768);
globalThis.planReviewHarness.callbacks.onWindow(firstReview, null);
planWindows[4].resolve(planWindow(refusedReview, 768));
await until(() => !firstReview.windowRequestRunning);
assert.equal(firstReview.window, latestWindow, "return to covered rows invalidates the read");
globalThis.planReviewHarness.callbacks.onWindow(firstReview, 0);
planWindows[5].resolve(originalWindow);
await until(() => !firstReview.windowRequestRunning);
assert.equal(firstReview.window, originalWindow);
planWindows.splice(2); // Keep the following independent gesture receipt ordinals.

globalThis.planReviewHarness.callbacks.onWindow(firstReview, 768);
globalThis.planReviewHarness.callbacks.onViewChange(firstReview, { sortColumn: "size" });
assert.equal(firstReview.pending, "view", "view feedback is published before its receipt");
assert.equal(firstReview.foregroundWindowReaders, 2, "scroll and full view work have distinct reader evidence");
planWindows[2].resolve(planWindow(refusedReview, 768));
await until(() => !firstReview.windowRequestRunning);
assert.equal(firstReview.window, originalWindow, "a newer view action invalidates old window data");
planWindows.pop();
taskButton("Task 6").click();
const sortedReview = planSummary({
  disposition: "updated", view_revision: 1,
  sort_column: "size", sort_direction: "ascending",
});
planViewUpdates[0].resolve(sortedReview);
await until(() => planWindows.length === 3);
planWindows[2].resolve(planWindow(sortedReview));
await until(() => firstReview.pending === null);
assert.equal(firstReview.foregroundWindowReaders, 0);
taskButton("Task 7").click();
assert.equal(firstReview.summary.sort_column, "size");
assert.equal(firstReview.message, null, "successful view refresh adds no footer noise");

const detailRow = { operation_id: "9".repeat(32) };
const hostileDetail = {
  disposition: "current",
  execution_revision: 0,
  operation_id: detailRow.operation_id,
  operation: { display: "<img src=x onerror=alert(1)>" },
};
globalThis.planReviewHarness.callbacks.onExecutionDetail(firstReview, detailRow);
await until(() => executionDetails.length === 1);
settingsButton().click();
assert.equal(firstReview.executionDetail, null, "Settings retires pending execution detail");
executionDetails[0].resolve(hostileDetail);
await turns();
assert.equal(firstReview.executionDetail, null, "a hostile reply cannot publish in Settings");
const detailCallsInSettings = executionDetails.length;
globalThis.planReviewHarness.callbacks.onExecutionDetail(firstReview, detailRow);
await turns();
assert.equal(executionDetails.length, detailCallsInSettings, "Settings admits no detail request");
taskButton("Task 7").click();
assert.equal(firstReview.executionDetail, null, "returning from Settings restores no retired detail");

globalThis.planReviewHarness.callbacks.onExecutionDetail(firstReview, detailRow);
await until(() => executionDetails.length === 2);
settingsButton().click();
taskButton("Task 7").click();
globalThis.planReviewHarness.callbacks.onExecutionDetail(firstReview, detailRow);
await until(() => executionDetails.length === 3);
const currentDetail = { ...hostileDetail, operation: { display: "current detail" } };
executionDetails[2].resolve(currentDetail);
await until(() => firstReview.executionDetail?.state === "current");
executionDetails[1].reject(new Error("retired detail failed late"));
await turns();
assert.equal(firstReview.executionDetail.response, currentDetail, "a late retired error cannot replace current detail");
globalThis.planReviewHarness.callbacks.onExecutionDetail(firstReview, null);
assert.equal(firstReview.executionDetail, null);

const retainedHighlightOffset = firstReview.window.offset;
const offWindowHighlight = planSummary({
  view_revision: firstReview.summary.view_revision,
  highlight_revision: firstReview.summary.highlight_revision,
  highlight_focus_node_id: firstReview.window.rows[0].node_id,
  highlight_focus_visible_index: retainedHighlightOffset + 256,
});
nextHighlightSummary = offWindowHighlight;
globalThis.planReviewHarness.callbacks.onHighlight(
  firstReview,
  "move_down",
  null,
);
await until(() => planWindows.length === 4);
assert.equal(firstReview.foregroundWindowReaders, 1, "highlight mutation and window share one reader span");
assert.equal(
  calls.at(-1)[0],
  "plan-window",
  "an off-window arrow refreshes the visible window",
);
assert.equal(
  calls.at(-1)[3],
  retainedHighlightOffset + 256,
  "an off-window arrow anchors at the authoritative focus index",
);
planWindows[3].resolve(planWindow(offWindowHighlight, retainedHighlightOffset + 256));
await until(() => firstReview.pending === null);
assert.equal(firstReview.window.offset, retainedHighlightOffset + 256);
assert.equal(firstReview.foregroundWindowReaders, 0);
assert.equal(executionDetails.length, 3, "planned-row highlight needs no execution-detail read");

const pointerWindowOffset = firstReview.window.offset;
const retainedPointerHighlight = planSummary({
  view_revision: firstReview.summary.view_revision,
  highlight_revision: firstReview.summary.highlight_revision,
  highlight_focus_node_id: firstReview.window.rows[0].node_id,
  highlight_focus_visible_index: pointerWindowOffset,
});
nextHighlightSummary = retainedPointerHighlight;
globalThis.planReviewHarness.callbacks.onHighlight(
  firstReview,
  "replace",
  firstReview.window.rows[0].node_id,
);
await until(() => planWindows.length === 5);
assert.equal(
  calls.at(-1)[3],
  pointerWindowOffset,
  "a pointer highlight refreshes the retained window offset",
);
planWindows[4].resolve(planWindow(retainedPointerHighlight, pointerWindowOffset));
await until(() => firstReview.pending === null);
assert.equal(firstReview.window.offset, pointerWindowOffset);

globalThis.planReviewHarness.callbacks.onSelect(
  firstReview,
  firstReview.window.rows[0],
  false,
);
await until(() => firstReview.pending === "selection");
assert.equal(firstReview.foregroundWindowReaders, 1, "selection mutation, anchor, and window share one reader span");
const selectedReview = planSummary({
  disposition: "conflict", view_revision: 2, selection_revision: 1,
  selected_operation_count: 1,
});
planSelections[0].resolve(selectedReview);
await until(() => planWindows.length === 6);
planWindows[5].resolve(planWindow(selectedReview));
await until(() => firstReview.pending === null);
assert.equal(firstReview.foregroundWindowReaders, 0);

firstReview.summary = planSummary({
  disposition: "current",
  view_revision: 2,
  selection_revision: 1,
  preflight_ready: true,
  preflight_refusal_count: 0,
  warning_count: 0,
  requires_destructive_confirmation: false,
  destructive_operation_count: 0,
  required_bytes: "7",
});
globalThis.planReviewHarness.callbacks.onExecute(firstReview, executeInvoker);
await until(() => planExecutions.length === 1);
assert.equal(confirmationRequests.length, 0, "non-destructive Execute bypasses confirmation");
assert.deepEqual(
  calls.at(-1),
  ["execute-plan", TASK_G, firstReview.summary.request_id, 1, false],
);
planExecutions[0].reject(new Error("certain refusal before admission"));
await until(() => reviewRenders.at(-1).executionAttempt === null);

firstReview.summary = planSummary({
  disposition: "current",
  view_revision: 2,
  selection_revision: 1,
  preflight_ready: true,
  preflight_refusal_count: 0,
  warning_count: 0,
  requires_destructive_confirmation: true,
  destructive_operation_count: 1,
  destructive_operation_counts: { update: 1, move_update: 0, trash: 0, delete: 0 },
  irreversible_operation_count: 1,
  irreversible_update_count: 1,
  required_bytes: "7",
});
globalThis.planReviewHarness.callbacks.onExecute(firstReview, executeInvoker);
assert.equal(firstReview.pending, "confirmation", "modal feedback precedes confirmation");
assert.equal(planExecutions.length, 1, "destructive Execute does not submit before confirmation");
assert.equal(confirmationRequests.length, 1);
globalThis.planReviewHarness.callbacks.onSelect(
  firstReview,
  firstReview.window.rows[0],
  false,
);
assert.equal(planSelections.length, 1, "selection cannot change while the modal owns the intent");
confirmationRequests[0].onCancel();
await turns();
assert.equal(planExecutions.length, 1, "Cancel submits no command");
assert.equal(firstReview.pending, null);

globalThis.planReviewHarness.callbacks.onExecute(firstReview, executeInvoker);
assert.equal(confirmationRequests.length, 2);
const frozenRequestId = firstReview.summary.request_id;
const frozenSelectionRevision = firstReview.summary.selection_revision;
firstReview.summary = planSummary({
  ...firstReview.summary,
  request_id: "d".repeat(32),
  selection_revision: 9,
});
confirmationRequests[1].onConfirm();
confirmationRequests[1].onConfirm();
await until(() => planExecutions.length === 2);
assert.deepEqual(
  calls.at(-1),
  ["execute-plan", TASK_G, frozenRequestId, frozenSelectionRevision, true],
  "Confirm submits the one exact pre-dialog snapshot",
);
assert.equal(firstReview.pending, "execute", "execute feedback precedes admission");
taskButton("Task 6").click();
const executionSession = "8".repeat(32);
const planDrain = drains.get(TASK_G);
let executionOutcomeChecks = 0;
const checkExecution = () => {
  executionOutcomeChecks += 1;
  return Promise.resolve(null);
};
planExecutions[1].notify({ state: "unavailable", canCheck: true,
  message: "execution-check-sentinel", check: checkExecution });
await until(() => reviewRenders.at(-1).executionAttempt.recovery?.canCheck === true);
assert.equal(firstReview.pending, "execute");
assert.equal(reviewRenders.at(-1).executionAttempt.state, "submitting");
globalThis.planReviewHarness.callbacks.onSelect(
  firstReview,
  firstReview.window.rows[0],
  false,
);
assert.equal(planSelections.length, 1, "uncertain admission keeps selection frozen");
assert.equal(planExecutions.length, 2, "navigation cannot create an implicit retry");
const uncertainClose = walk(app).find(
  (element) => element.ariaLabel === "Resolve the in-flight execution request before closing.",
);
assert.equal(uncertainClose?.disabled, true, "uncertain admission visibly fences Close");
const closeCallsBeforeUncertainClick = closes.length;
uncertainClose.click();
assert.equal(
  closes.length,
  closeCallsBeforeUncertainClick,
  "uncertain admission cannot issue a Close command",
);
taskButton("Task 7").click();
const replacementReview = {
  ...firstReview,
  summary: planSummary({
    ...firstReview.summary,
    request_id: "e".repeat(32),
    selection_revision: 10,
  }),
  pending: null,
};
reviewRenders.at(-1).review = replacementReview;
globalThis.planReviewHarness.callbacks.onExecute(replacementReview, executeInvoker);
await until(() => executionOutcomeChecks === 1);
assert.equal(planExecutions.length, 2,
  "checking the original confirmed intent after review replacement does not resubmit execution");
const admissionOpenBase = planOpens.length;
const planTerminalSnapshot = pageSnapshot(TASK_G, SESSION_G, {
  revision: 40, session_state: "completed", terminal_result: null,
});
planDrain.acceptUpdate({ update_type: "record", record: { state: "completed" } },
  planTerminalSnapshot);
assert.equal(reviewRenders.at(-1).snapshot, planTerminalSnapshot);
planExecutions[1].resolve({ task_id: TASK_G, session_id: executionSession });
await until(() => calls.some(
  (call) => call[0] === "drain" && call[1] === TASK_G && call[2] === executionSession,
));
const executionDrain = drains.get(TASK_G);
assert.equal(reviewRenders.at(-1).snapshot, null,
  "execution admission retires the Plan session's presentation");
assert.equal(taskStatusDigest(reviewRenders.at(-1)).title, "Executing",
  "the rail cannot report the Plan terminal state for active execution");
assert.notEqual(executionDrain, planDrain, "execution replaces the released plan drain");
assert.equal(planExecutions.length, 2, "navigation cannot duplicate execution admission");
await until(() => planOpens.length === admissionOpenBase + 1);
const admissionReload = planOpens.at(-1);

const stateUpdate = (state) => ({
  update_type: "event",
  event: { body_type: "StateChanged", body: { state } },
});
planDrain.acceptUpdate(stateUpdate("paused"));
assert.equal(
  reviewRenders.at(-1).executionControlState,
  "running",
  "a released plan drain cannot change the execution session",
);
const preRefreshReview = reviewRenders.at(-1).review;
// The synthetic replacement review is not the frozen attempt review; place it at
// the accepted-admission boundary while the forced refresh remains withheld.
preRefreshReview.pending = null;
globalThis.planReviewHarness.callbacks.onControl(preRefreshReview, "pause");
assert.equal(preRefreshReview.pending, "pause", "control feedback precedes its receipt");
assert.deepEqual(calls.at(-1), ["control-execution", TASK_G, executionSession, "pause"]);
executionDrain.acceptUpdate(stateUpdate("running"),
  pageSnapshot(TASK_G, executionSession, { control_state: "running" }));
assert.equal(reviewRenders.at(-1).snapshot?.session_id, executionSession,
  "the execution's lower independent revision is adopted");
executionControls[0].resolve({
  code: "accepted", session_id: executionSession, before: "running",
  after: "pausing", detail: "Pause requested; custody is reaching a checkpoint.", accepted: true,
});
await until(() => preRefreshReview.pending === null);
assert.equal(reviewRenders.at(-1).executionControlState, "running",
  "the accepted control receipt does not replace snapshot state");
assert.equal(preRefreshReview.message, "Pausing execution…");
executionDrain.acceptUpdate(stateUpdate("paused"),
  pageSnapshot(TASK_G, executionSession, { control_state: "paused" }));
assert.equal(reviewRenders.at(-1).executionControlState, "paused");
executionDrain.acceptRefusal(new Error("drain interrupted"), () => true);
assert.match(preRefreshReview.message, /Task updates stopped/);
executionDrain.acceptRecovered(TASK_G, executionSession);
assert.equal(preRefreshReview.message, "Execution paused. Resume available.",
  "recovery uses settled control state rather than an old Pause receipt");

// Execution admission does not replace the old reviewing object until reload
// succeeds. Active execution rejects selection before any backend mutation
// (_require_released_plan_task), even when that stale UI still offers it.
// Plan again is deliberately not used: it creates a different task identity.
const selectionWindowBase = planWindows.length;
admissionReload.reject(new Error("post-admission reload failed"));
await until(() => planWindows.length === selectionWindowBase + 1);
const retainedAdmissionReview = reviewRenders.at(-1).review;
const unchangedSelection = retainedAdmissionReview.summary;
const unchangedAdmissionWindow = retainedAdmissionReview.window;
assert.equal(retainedAdmissionReview.pending, null);
assert.equal(unchangedSelection.selection_state, "reviewing");
assert.equal(reviewRenders.at(-1).executionAttempt, null);
globalThis.planReviewHarness.callbacks.onSelect(
  retainedAdmissionReview, retainedAdmissionReview.window.rows[0], false,
);
await until(() => retainedAdmissionReview.foregroundWindowReaders === 1);
planWindows[selectionWindowBase].resolve(planWindow(unchangedSelection));
await until(() => !reviewRenders.at(-1).executionWindowRefreshRunning);
assert.equal(retainedAdmissionReview.window, unchangedAdmissionWindow, "selection supersedes background publication");
assert.equal(reviewRenders.at(-1).executionWindowDirty, true);
planSelections[1].reject(new Error("task is unavailable: execution custody is unreleased"));
await until(() => planOpens.length === admissionOpenBase + 2);
const selectionRecoveryReload = planOpens.at(-1);
assert.equal(retainedAdmissionReview.foregroundWindowReaders, 0);
assert.equal(retainedAdmissionReview.summary, unchangedSelection, "rejected selection has no mutation effect");

// A second explicit gesture can race the pending reload. Its rejected receipt
// must release ownership; failed reload alone cannot start a competing refresh.
globalThis.planReviewHarness.callbacks.onSelect(
  retainedAdmissionReview, retainedAdmissionReview.window.rows[0], false,
);
await until(() => retainedAdmissionReview.foregroundWindowReaders === 1);
executionDrain.acceptUpdate(stateUpdate("paused"),
  pageSnapshot(TASK_G, executionSession, { control_state: "paused" }));
selectionRecoveryReload.reject(new Error("selection recovery reload failed"));
await until(() => !reviewRenders.at(-1).reviewLoading);
await turns();
assert.equal(planWindows.length, selectionWindowBase + 1, "dirty replay waits for selection cleanup");
planSelections[2].reject(new Error("task is unavailable: execution custody is unreleased"));
await until(() => planOpens.length === admissionOpenBase + 3);
const committedReload = planOpens.at(-1);
assert.equal(retainedAdmissionReview.foregroundWindowReaders, 0);
assert.equal(retainedAdmissionReview.summary, unchangedSelection);
assert.equal(reviewRenders.at(-1).executionWindowDirty, true);

const committedReview = planSummary({
  selection_state: "committed", view_revision: 3, selection_revision: 1,
  preflight_ready: true, preflight_refusal_count: 0, warning_count: 0,
});
committedReload.resolve(committedReview);
const committedWindowBase = planWindows.length;
await until(() => planWindows.length === committedWindowBase + 1);
planWindows.at(-1).resolve(planWindow(committedReview));
await turns();
taskButton("Task 7").click();
const liveTask = reviewRenders.at(-1);
assert.equal(liveTask.sessionId, executionSession);
assert.equal(liveTask.review.summary.selection_state, "committed");
assert.equal(
  liveTask.executionControlState,
  "paused",
  "Plan review refresh preserves the observed live control state",
);

const conflictWindow = (reviewSummary) => ({
  ...planWindow(reviewSummary), disposition: "conflict",
});
const executionDirtyUpdate = { update_type: "event", event: { body_type: "Progress", body: {} } };
const conflictOpenBase = planOpens.length;
const conflictWindowBase = planWindows.length;
executionDrain.acceptUpdate(executionDirtyUpdate);
await until(() => planWindows.length === conflictWindowBase + 1);
planWindows.at(-1).resolve(conflictWindow(committedReview));
await until(() => planOpens.length === conflictOpenBase + 1);
const firstConflictReload = planOpens.at(-1);
firstConflictReload.resolve(committedReview);
await until(() => planWindows.length === conflictWindowBase + 2);
planWindows.at(-1).resolve(conflictWindow(committedReview));
await until(() => reviewRenders.at(-1).executionWindowRefreshRunning === false
  && reviewRenders.at(-1).reviewLoading === false);
await turns();
assert.equal(planWindows.length, conflictWindowBase + 2, "a persistent conflict cannot self-poll");
assert.equal(planOpens.length, conflictOpenBase + 1, "a conflict gets one forced review reopen");
assert.match(liveTask.review.message, /refresh delayed/);

const conflictedReview = liveTask.review;
executionDrain.acceptUpdate(executionDirtyUpdate);
await until(() => planWindows.length === conflictWindowBase + 3);
executionDrain.acceptUpdate(executionDirtyUpdate);
assert.equal(planWindows.length, conflictWindowBase + 3, "a newer live event cannot open a parallel window read");
planWindows.at(-1).resolve(conflictWindow(committedReview));
await until(() => planOpens.length === conflictOpenBase + 2);
const secondConflictReload = planOpens.at(-1);
secondConflictReload.resolve(committedReview);
await until(() => planWindows.length === conflictWindowBase + 4);
planWindows.at(-1).resolve(planWindow(committedReview));
await until(() => liveTask.review !== conflictedReview);
await turns();
assert.equal(planWindows.length, conflictWindowBase + 4, "the one forced reopen captures the newer live event");
let liveReview = liveTask.review;
const executionWindow = (reviewSummary, offset, revision, result = null) => ({
  ...planWindow(reviewSummary, offset),
  total: 2048,
  rows: planWindow(reviewSummary, offset).rows.map((row) => ({
    ...row, visible_index: offset, node_id: `node-${detailRow.operation_id}`,
    row_kind: "operation", operation_id: detailRow.operation_id, operation_kind: "copy",
    display: "example.bin", notice: null, operation_count: 1,
    selectable_operation_count: 1, selected_operation_count: 1, selection: "selected",
    execution: { operation: null, automatic_verification: null, evidence: null },
  })),
  execution: {
    ...planWindow(reviewSummary, offset).execution,
    session_id: executionSession,
    execution_revision: revision,
    result,
    started_at: result === null ? null : "2026-09-23T01:00:00+00:00",
    ended_at: result === null ? null : "2026-09-23T01:01:05+00:00",
    failed_operation_count: result === null ? null : result.filesystem === "failed" ? 1 : 0,
    disk_capacity_failure_count: result === null ? null : 0,
  },
});
const executionResult = (patch = {}) => ({
  headline: "success", filesystem: "completed", integrity: "verified",
  recording: "ok", audit: "ok", disposition: "ran", canceled: false,
  phases: [], bytes_done: "0", bytes_total: "0", error: null,
  recording_degraded_items: 0, recording_issues: [], omitted_detail_count: 0,
  presentation_omitted_detail_count: 0, review_refusal: null, ...patch,
});
const failedResult = executionResult({ headline: "failed", filesystem: "failed" });
const completedResult = executionResult();
const arbitrationWindowBase = planWindows.length;
assert.equal(liveTask.executionWindowRefreshRunning, false);

globalThis.planReviewHarness.callbacks.onWindow(liveReview, 256);
executionDrain.acceptUpdate(executionDirtyUpdate);
assert.equal(planWindows.length, arbitrationWindowBase + 1, "scroll-first dirty refresh waits");
planWindows[arbitrationWindowBase].resolve(executionWindow(committedReview, 256, 2));
await until(() => planWindows.length === arbitrationWindowBase + 2);
planWindows[arbitrationWindowBase + 1].resolve(executionWindow(committedReview, 256, 2));
await until(() => !liveTask.executionWindowRefreshRunning);
assert.equal(liveReview.window.offset, 256);

executionDrain.acceptUpdate(executionDirtyUpdate);
await until(() => planWindows.length === arbitrationWindowBase + 3);
globalThis.planReviewHarness.callbacks.onWindow(liveReview, 512);
planWindows[arbitrationWindowBase + 3].resolve(executionWindow(committedReview, 512, 3));
await until(() => liveReview.window.offset === 512);
liveReview.executionDetail = { retained: true };
planWindows[arbitrationWindowBase + 2].resolve(executionWindow(committedReview, 256, 1, failedResult));
await until(() => planWindows.length === arbitrationWindowBase + 5);
assert.equal(liveReview.window.execution.execution_revision, 3);
assert.deepEqual(liveReview.executionDetail, { retained: true });
assert.notDeepEqual(liveTask.executionResult, failedResult);
planWindows[arbitrationWindowBase + 4].resolve(executionWindow(committedReview, 512, 4, completedResult));
await until(() => !liveTask.executionWindowRefreshRunning);
assert.equal(liveReview.window.execution.execution_revision, 4);
assert.deepEqual(liveTask.executionResult, completedResult);
assert.equal(liveTask.executionStartedAt, "2026-09-23T01:00:00+00:00");
assert.equal(liveTask.executionEndedAt, "2026-09-23T01:01:05+00:00");
assert.equal(liveReview.executionDetail, null);

executionDrain.acceptUpdate(executionDirtyUpdate);
await until(() => planWindows.length === arbitrationWindowBase + 6);
globalThis.planReviewHarness.callbacks.onWindow(liveReview, null);
planWindows[arbitrationWindowBase + 5].resolve(executionWindow(committedReview, 512, 3));
await until(() => planWindows.length === arbitrationWindowBase + 7);
assert.equal(liveReview.window.execution.execution_revision, 4);
planWindows[arbitrationWindowBase + 6].resolve(executionWindow(committedReview, 512, 4));
await until(() => !liveTask.executionWindowRefreshRunning);
assert.equal(liveReview.foregroundWindowReaders, 0);

executionDrain.acceptUpdate(executionDirtyUpdate);
await until(() => planWindows.length === arbitrationWindowBase + 8);
globalThis.planReviewHarness.callbacks.onWindow(liveReview, 768);
planWindows[arbitrationWindowBase + 7].resolve(executionWindow(committedReview, 512, 4));
await turns();
assert.equal(liveReview.window.offset, 512, "refresh completion during foreground work is inert");
planWindows[arbitrationWindowBase + 8].resolve(executionWindow(committedReview, 768, 5));
await until(() => planWindows.length === arbitrationWindowBase + 10);
planWindows[arbitrationWindowBase + 9].resolve(executionWindow(committedReview, 768, 5));
await until(() => !liveTask.executionWindowRefreshRunning);

executionDrain.acceptUpdate(executionDirtyUpdate);
await until(() => planWindows.length === arbitrationWindowBase + 11);
globalThis.planReviewHarness.callbacks.onWindow(liveReview, 1024);
planWindows[arbitrationWindowBase + 11].resolve(executionWindow(committedReview, 1024, 5));
await until(() => liveReview.window.offset === 1024);
planWindows[arbitrationWindowBase + 10].resolve(executionWindow(committedReview, 768, 5));
await until(() => planWindows.length === arbitrationWindowBase + 13);
assert.equal(liveReview.window.offset, 1024, "late equal-revision refresh cannot replace foreground offset");
planWindows[arbitrationWindowBase + 12].resolve(executionWindow(committedReview, 1024, 5));
await until(() => !liveTask.executionWindowRefreshRunning);

executionDrain.acceptUpdate(executionDirtyUpdate);
await until(() => planWindows.length === arbitrationWindowBase + 14);
globalThis.planReviewHarness.callbacks.onWindow(liveReview, 1280);
assert.equal(liveReview.foregroundWindowReaders, 1);
planWindows[arbitrationWindowBase + 13].reject(new Error("superseded refresh failed"));
planWindows[arbitrationWindowBase + 14].resolve(executionWindow(committedReview, 1280, 6));
await until(() => planWindows.length === arbitrationWindowBase + 16);
assert.doesNotMatch(liveReview.message ?? "", /refresh delayed/, "a stale rejection publishes no error");
planWindows[arbitrationWindowBase + 15].resolve(executionWindow(committedReview, 1280, 6));
await until(() => !liveTask.executionWindowRefreshRunning);
assert.equal(liveReview.window.offset, 1280);
assert.equal(liveReview.foregroundWindowReaders, 0);
planWindows.splice(arbitrationWindowBase);

const foregroundViewWindowBase = planWindows.length;
const foregroundViewUpdate = planViewUpdates.length;
const viewWindowBefore = liveReview.window;
deferAnchor = true;
globalThis.planReviewHarness.callbacks.onViewChange(liveReview, { sortColumn: "size" });
executionDrain.acceptUpdate(executionDirtyUpdate);
await until(() => liveTask.executionWindowDirty === true);
assert.equal(planWindows.length, foregroundViewWindowBase, "dirty refresh defers through view mutation");
const liveViewSummary = planSummary({
  ...committedReview, disposition: "applied", view_revision: 4,
  sort_column: "size", sort_direction: "ascending",
});
planViewUpdates[foregroundViewUpdate].resolve(liveViewSummary);
await until(() => planAnchors.length === 1);
assert.equal(planWindows.length, foregroundViewWindowBase, "anchor acquisition still owns the foreground span");
assert.equal(liveReview.window, viewWindowBefore);
planAnchors[0].resolve({ disposition: "current", index: 1280 });
deferAnchor = false;
await until(() => planWindows.length === foregroundViewWindowBase + 1);
assert.deepEqual(calls.at(-1), ["plan-window", TASK_G, 4, 1280, 256]);
planWindows[foregroundViewWindowBase].resolve(executionWindow(liveViewSummary, 1280, 6));
await until(() => planWindows.length === foregroundViewWindowBase + 2);
assert.deepEqual(calls.at(-1), ["plan-window", TASK_G, 4, 1280, 256]);
planWindows[foregroundViewWindowBase + 1].resolve(executionWindow(liveViewSummary, 1280, 6));
await until(() => !liveTask.executionWindowRefreshRunning);
assert.equal(liveReview.foregroundWindowReaders, 0);
assert.equal(liveTask.executionWindowDirty, false);
planWindows.splice(foregroundViewWindowBase);

const foregroundHighlightWindowBase = planWindows.length;
const liveHighlightSummary = planSummary({
  ...liveViewSummary, highlight_revision: 1,
  highlight_focus_node_id: liveReview.window.rows[0].node_id,
  highlight_focus_visible_index: 1280,
});
const autoDetailsBefore = executionDetails.length;
deferHighlight = true;
globalThis.planReviewHarness.callbacks.onHighlight(liveReview, "replace", liveReview.window.rows[0].node_id);
await until(() => planHighlights.length === 1);
executionDrain.acceptUpdate(executionDirtyUpdate);
await turns();
assert.equal(planWindows.length, foregroundHighlightWindowBase, "highlight mutation itself holds dirty replay");
planHighlights[0].resolve(liveHighlightSummary);
deferHighlight = false;
await until(() => planWindows.length === foregroundHighlightWindowBase + 1);
executionDrain.acceptUpdate(executionDirtyUpdate);
assert.equal(planWindows.length, foregroundHighlightWindowBase + 1, "dirty refresh defers through highlight window");
planWindows[foregroundHighlightWindowBase].resolve(executionWindow(liveHighlightSummary, 1280, 6));
await until(() => planWindows.length === foregroundHighlightWindowBase + 2);
assert.equal(executionDetails.length, autoDetailsBefore + 1,
  "authoritative focused operation requests one bounded detail");
planWindows[foregroundHighlightWindowBase + 1].resolve(executionWindow(liveReview.summary, 1280, 6));
await until(() => !liveTask.executionWindowRefreshRunning);
assert.equal(executionDetails.length, autoDetailsBefore + 1,
  "unchanged execution revision and focus do not duplicate detail reads");
assert.equal(liveReview.foregroundWindowReaders, 0);
assert.equal(liveTask.executionWindowDirty, false);
planWindows.splice(foregroundHighlightWindowBase);

const failedForegroundBase = planWindows.length;
const windowBeforeErrors = liveReview.window;
deferHighlight = true;
globalThis.planReviewHarness.callbacks.onHighlight(liveReview, "replace", liveReview.window.rows[0].node_id);
await until(() => planHighlights.length === 2);
const rejectedHighlight = liveReview.highlightQueue.catch(() => {});
executionDrain.acceptUpdate(executionDirtyUpdate);
planHighlights[1].reject(new Error("highlight request failed"));
await rejectedHighlight;
deferHighlight = false;
await until(() => planWindows.length === failedForegroundBase + 1);
assert.equal(liveReview.foregroundWindowReaders, 0, "rejected highlight releases its entire span");
assert.equal(liveReview.window, windowBeforeErrors);
planWindows[failedForegroundBase].resolve(executionWindow(liveReview.summary, 1280, 6));
await until(() => !liveTask.executionWindowRefreshRunning);
const windowBeforeScrollError = liveReview.window;
globalThis.planReviewHarness.callbacks.onWindow(liveReview, 1536);
executionDrain.acceptUpdate(executionDirtyUpdate);
planWindows[failedForegroundBase + 1].reject(new Error("scroll request failed"));
await until(() => planWindows.length === failedForegroundBase + 3);
assert.equal(liveReview.foregroundWindowReaders, 0, "rejected scroll cannot strand dirty refresh");
assert.equal(liveReview.window, windowBeforeScrollError);
assert.deepEqual(calls.at(-1), ["plan-window", TASK_G, liveReview.summary.view_revision, 1280, 256]);
planWindows[failedForegroundBase + 2].resolve(executionWindow(liveReview.summary, 1280, 6));
await until(() => !liveTask.executionWindowRefreshRunning);
planWindows.splice(failedForegroundBase);

// Hidden views retain dirtiness, but a response cannot publish across navigation.
for (const destination of ["settings", "task"]) {
  const navigationBase = planWindows.length;
  const retainedWindow = liveReview.window;
  const retainedResult = liveTask.executionResult;
  executionDrain.acceptUpdate(executionDirtyUpdate);
  await until(() => planWindows.length === navigationBase + 1);
  if (destination === "settings") settingsButton().click();
  else taskButton("Task 6").click();
  planWindows[navigationBase].resolve(executionWindow(liveReview.summary, 0, 1, failedResult));
  await until(() => !liveTask.executionWindowRefreshRunning);
  assert.equal(liveReview.window, retainedWindow);
  assert.equal(liveTask.executionResult, retainedResult);
  assert.equal(liveTask.executionWindowDirty, true);
  await turns();
  assert.equal(planWindows.length, navigationBase + 1, "hidden dirty review does not self-poll");
  taskButton("Task 7").click();
  await until(() => planWindows.length === navigationBase + 2);
  assert.deepEqual(calls.at(-1), ["plan-window", TASK_G, liveReview.summary.view_revision, 1280, 256]);
  planWindows[navigationBase + 1].resolve(executionWindow(liveReview.summary, 1280, 6));
  await until(() => !liveTask.executionWindowRefreshRunning);
  assert.equal(liveTask.executionWindowDirty, false);
  planWindows.splice(navigationBase);
}

const followAnchorBase = planAnchors.length;
const followWindowBase = planWindows.length;
const followSummaryBefore = liveReview.summary;
liveReview.summary = {
  ...liveReview.summary,
  search_query: "",
  filters: [],
  sort_column: "path",
  sort_direction: "ascending",
};
const activeOperationId = "f".repeat(32);
liveTask.progressPresentation = Object.freeze({
  activeItem: Object.freeze({ item_id: activeOperationId, item_type: "operation" }),
});
liveReview.follow.enabled = true;
liveReview.follow.eligible = true;
liveReview.follow.hasTarget = true;
deferAnchor = true;
globalThis.planReviewHarness.callbacks.onNavigateCurrent(liveReview, false);
await until(() => planAnchors.length === followAnchorBase + 1);
globalThis.planReviewHarness.callbacks.onNavigateCurrent(liveReview, false);
await turns();
assert.equal(
  planAnchors.length,
  followAnchorBase + 1,
  "the same target and follow generation coalesce behind one anchor lookup",
);
globalThis.planReviewHarness.callbacks.onFollowOverride(liveReview);
assert.equal(liveReview.follow.enabled, false, "manual override disables automatic follow");
globalThis.planReviewHarness.callbacks.onNavigateCurrent(liveReview, true);
assert.equal(liveReview.follow.enabled, true, "Enable restores follow for an active target");
planAnchors[followAnchorBase].resolve({ disposition: "current", index: 1280 });
await until(() => planAnchors.length === followAnchorBase + 2);
assert.equal(
  planWindows.length,
  followWindowBase,
  "the stale anchor reply cannot navigate after a newer follow generation",
);
planAnchors[followAnchorBase + 1].resolve({ disposition: "current", index: 1280 });
await until(() => planWindows.length === followWindowBase + 1);
planWindows[followWindowBase].resolve(executionWindow(liveReview.summary, 1280, 6));
await until(() => liveReview.follow.scrollOffset === 1280);
deferAnchor = false;
planAnchors.splice(followAnchorBase);
planWindows.splice(followWindowBase);

liveReview.follow.scrollOffset = null; // the renderer consumed the first jump; the user scrolled within this window
const sameTargetWindowBase = planWindows.length;
const sameTargetAnchorBase = planAnchors.length;
executionDrain.acceptUpdate(executionDirtyUpdate);
assert.equal(liveReview.follow.scrollOffset, null,
  "an automatic byte tick does not snap the same visible target back into place");
assert.equal(planAnchors.length, sameTargetAnchorBase,
  "the cached visible target needs no new anchor lookup");
await until(() => planWindows.length === sameTargetWindowBase + 1);
planWindows[sameTargetWindowBase].resolve(executionWindow(liveReview.summary, 1280, 6));
await until(() => !liveTask.executionWindowRefreshRunning);
assert.equal(liveReview.follow.scrollOffset, null,
  "ordinary window refresh still preserves the user's within-window scroll");
globalThis.planReviewHarness.callbacks.onNavigateCurrent(liveReview, false);
assert.equal(liveReview.follow.scrollOffset, 1280,
  "explicit Go to current jumps to the cached target");
assert.equal(planAnchors.length, sameTargetAnchorBase,
  "explicit cached Go does not launch an anchor lookup");
planWindows.splice(sameTargetWindowBase);

globalThis.planReviewHarness.callbacks.onFollowOverride(liveReview);
liveTask.progressPresentation = Object.freeze({ activeItem: null });
liveReview.follow.hasTarget = false;
const noActiveAnchorCount = planAnchors.length;
globalThis.planReviewHarness.callbacks.onNavigateCurrent(liveReview, true);
await turns();
assert.equal(liveReview.follow.enabled, false, "Enable cannot turn on follow without an active operation");
assert.equal(planAnchors.length, noActiveAnchorCount, "no active operation launches no anchor lookup");
assert.equal(liveReview.follow.message, "No operation is active.");
liveReview.summary = followSummaryBefore;

const replacedControlBase = executionControls.length;
globalThis.planReviewHarness.callbacks.onControl(liveReview, "resume");
const replacedControlOpenBase = planOpens.length;
const replacedControlWindowBase = planWindows.length;
void globalThis.taskHarness.forceReview(liveTask, true);
await until(() => planOpens.length === replacedControlOpenBase + 1);
planOpens.at(-1).resolve(liveReview.summary);
await until(() => planWindows.length === replacedControlWindowBase + 1);
planWindows.at(-1).resolve(executionWindow(liveReview.summary, 0, 6));
await until(() => liveTask.review !== liveReview);
const replacedReview = liveTask.review;
assert.equal(replacedReview.pending, "resume", "review replacement retains an in-flight control");
const duplicateControlCount = executionControls.length;
globalThis.planReviewHarness.callbacks.onControl(replacedReview, "resume");
assert.equal(executionControls.length, duplicateControlCount, "replacement cannot dispatch a duplicate control");
executionControls[replacedControlBase].resolve({
  code: "not-found", session_id: executionSession, before: "paused",
  after: "paused", detail: "Resume was refused after review replacement.", accepted: false,
});
await until(() => replacedReview.pending === null);
assert.equal(replacedReview.message, "Resume was refused after review replacement.");
executionControls.splice(replacedControlBase, 1);
liveReview = replacedReview;

const erroredControlIndex = executionControls.length;
globalThis.planReviewHarness.callbacks.onControl(liveReview, "resume");
const erroredOpenBase = planOpens.length;
const erroredWindowBase = planWindows.length;
void globalThis.taskHarness.forceReview(liveTask, true);
await until(() => planOpens.length === erroredOpenBase + 1);
planOpens.at(-1).resolve(liveReview.summary);
await until(() => planWindows.length === erroredWindowBase + 1);
planWindows.at(-1).resolve(executionWindow(liveReview.summary, 0, 6));
const priorErrorReview = liveReview;
await until(() => liveTask.review !== priorErrorReview);
liveReview = liveTask.review;
assert.equal(liveReview.pending, "resume");
executionControls[erroredControlIndex].reject(new Error("simulated lost control reply"));
await until(() => liveReview.pending === null);
assert.equal(liveReview.message, "Resume refused. Follow live status.",
  "a task error remains a refusal after review replacement");
executionControls.splice(erroredControlIndex, 1);

globalThis.planReviewHarness.callbacks.onControl(liveReview, "resume");
assert.equal(liveReview.pending, "resume", "resume feedback precedes its receipt");
assert.deepEqual(calls.at(-1), ["control-execution", TASK_G, executionSession, "resume"]);
const controlWindowBase = planWindows.length;
executionDrain.acceptUpdate(stateUpdate("pending"));
executionDrain.acceptUpdate(stateUpdate("running"),
  pageSnapshot(TASK_G, executionSession, { control_state: "running" }));
await until(() => planWindows.length === controlWindowBase + 1);
const pendingControlWindow = planWindows[controlWindowBase];
executionControls[1].resolve({
  code: "accepted", session_id: executionSession, before: "paused",
  after: "pending", detail: "Resume requested; resource admission is pending.", accepted: true,
});
await until(() => liveReview.pending === null);
assert.equal(
  reviewRenders.at(-1).executionControlState,
  "running",
  "a late resume receipt cannot regress the observed running state",
);

globalThis.planReviewHarness.callbacks.onControl(liveReview, "pause");
executionDrain.acceptUpdate(stateUpdate("running"),
  pageSnapshot(TASK_G, executionSession, { control_state: "running" }));
executionControls[2].resolve({
  code: "not-found", session_id: executionSession, before: null,
  after: null, detail: "Pause was not accepted.", accepted: false,
});
await until(() => liveReview.pending === null);
assert.equal(reviewRenders.at(-1).executionControlState, "running");
assert.equal(liveReview.message, "Pause was not accepted.");

globalThis.planReviewHarness.callbacks.onControl(liveReview, "pause");
executionDrain.acceptUpdate(stateUpdate("running"),
  pageSnapshot(TASK_G, executionSession, { control_state: "running" }));
executionControls[3].reject(new Error("simulated uncertain control receipt"));
await until(() => liveReview.pending === null);
assert.equal(reviewRenders.at(-1).executionControlState, "running");
assert.equal(liveReview.message, "Pause refused. Follow live status.");

globalThis.planReviewHarness.callbacks.onControl(liveReview, "pause");
executionDrain.acceptUpdate(stateUpdate("pausing"),
  pageSnapshot(TASK_G, executionSession, { control_state: "pausing" }));
executionControls[4].reject(new Error("simulated late uncertain control receipt"));
await until(() => liveReview.pending === null);
assert.equal(reviewRenders.at(-1).executionControlState, "pausing");
assert.equal(liveReview.message, "Pausing execution…");

globalThis.planReviewHarness.callbacks.onControl(liveReview, "cancel");
assert.equal(liveReview.pending, "cancel", "cancel feedback precedes its receipt");
assert.deepEqual(calls.at(-1), ["control-execution", TASK_G, executionSession, "cancel"]);
const refusedResult = executionResult({ headline: "refused", filesystem: "refused",
  integrity: "not-run", disposition: "unrun" });
assert.equal(planWindows.length, controlWindowBase + 1, "control updates share one in-flight window read");
executionDrain.acceptUpdate({ update_type: "record", record: {
  kind: "sync-execution", state: "refused", result: refusedResult,
  started_at: null, ended_at: "2026-09-23T02:00:00+00:00",
} }, pageSnapshot(TASK_G, executionSession, {
  session_state: "refused", terminal_result: refusedResult,
  started_at: null, ended_at: "2026-09-23T02:00:00+00:00",
}));
await turns();
assert.equal(reviewRenders.at(-1).sessionState, "refused");
assert.equal(liveTask.executionResult, refusedResult, "live terminal record precedes retained window capture");
assert.equal(liveTask.executionStartedAt, null);
assert.equal(liveTask.executionEndedAt, "2026-09-23T02:00:00+00:00");
const terminalMessage = liveReview.message;
assert.equal(terminalMessage, "Execution refused.", "terminal errors remain actionable feedback");
executionControls[5].resolve({
  code: "accepted", session_id: executionSession, before: "pausing",
  after: "pausing", detail: "Cancel will settle after the pause drain.", accepted: true,
});
await until(() => liveReview.pending === null);
assert.equal(liveReview.message, terminalMessage, "a late control receipt cannot replace terminal status");
assert.equal(
  reviewRenders.at(-1).review.summary.selection_state,
  "committed",
  "post-admission refusal retains committed selection and unrun review truth",
);
const releaseWindowBefore = liveReview.window;
const releaseResultBefore = liveTask.executionResult;
const retainedSummary = liveReview.summary;
const retiredViewUpdate = planViewUpdates.length;
globalThis.planReviewHarness.callbacks.onViewChange(liveReview, { sortColumn: "path" });
assert.equal(liveReview.foregroundWindowReaders, 1);
liveTask.reviewSessionId = null;
const releaseOpenBase = planOpens.length;
executionDrain.acceptRelease(TASK_G, executionSession);
await until(() => planOpens.length === releaseOpenBase + 1);
const retainedReload = planOpens.at(-1);
assert.equal(planWindows.length, controlWindowBase + 1, "live execution updates coalesce behind one bounded window read");
assert.equal(planWindows.at(-1), pendingControlWindow, "release retains the in-flight control window");
pendingControlWindow.resolve(executionWindow(retainedSummary, 1280, 7, failedResult));
await until(() => !liveTask.executionWindowRefreshRunning);
assert.equal(liveReview.window, releaseWindowBefore, "reload admission invalidates old refresh before review replacement");
assert.equal(liveTask.executionResult, releaseResultBefore);
assert.equal(liveTask.reviewLoading, true);

// A user detail read can observe the newly retained revision during reload.
// Its real conflict disposition adds dirty intent after reload admission.
const releaseDetailIndex = executionDetails.length;
globalThis.planReviewHarness.callbacks.onExecutionDetail(liveReview, liveReview.window.rows[0]);
await until(() => executionDetails.length === releaseDetailIndex + 1);
executionDetails[releaseDetailIndex].resolve({
  disposition: "conflict", execution_revision: 7, operation_id: detailRow.operation_id,
  operation: null, automatic_verification: null, evidence: null,
});
await until(() => liveReview.executionDetail === null);
assert.equal(planWindows.length, controlWindowBase + 1, "dirty detail reconciliation cannot compete with reload");
retainedReload.resolve(retainedSummary);
await until(() => planWindows.length === controlWindowBase + 2);
planWindows.at(-1).resolve(executionWindow(retainedSummary, 0, 7));
await until(() => reviewRenders.at(-1).review !== liveReview);
const postTerminalReview = reviewRenders.at(-1).review;
await until(() => planWindows.length === controlWindowBase + 3);
assert.deepEqual(calls.at(-1), ["plan-window", TASK_G, retainedSummary.view_revision, 0, 256]);
planWindows.at(-1).resolve(executionWindow(retainedSummary, 0, 7));
await until(() => !liveTask.executionWindowRefreshRunning);
assert.equal(liveTask.executionWindowDirty, false);
assert.equal(postTerminalReview.foregroundWindowReaders, 0);
assert.equal(postTerminalReview.window.execution.execution_revision, 7);
assert.equal(liveReview.window, releaseWindowBefore, "retired review never adopts replacement receipts");
const replacementWindow = postTerminalReview.window;
planViewUpdates[retiredViewUpdate].reject(new Error("old view request failed after replacement"));
await until(() => liveReview.foregroundWindowReaders === 0);
assert.equal(postTerminalReview.window, replacementWindow);
assert.equal(postTerminalReview.message, terminalMessage, "stale foreground rejection cannot overwrite replacement feedback");
assert.equal(planWindows.length, controlWindowBase + 3, "retired foreground cleanup cannot launch another refresh");
assert.equal(
  postTerminalReview.message,
  terminalMessage,
  "a forced review refresh cannot replace terminal execution truth",
);
globalThis.planReviewHarness.callbacks.onPlanAgain(postTerminalReview);
await until(() => planAgainStarts.length === 1);
assert.deepEqual(calls.at(-1), ["plan-again", TASK_G, null, null]);
planAgainStarts[0].reject(new Error("simulated Plan-again refusal"));
await until(() => postTerminalReview.pending === null);

const searchUpdateBase = planViewUpdates.length;
const searchWindowBase = planWindows.length;
globalThis.planReviewHarness.callbacks.onViewChange(postTerminalReview, { searchQuery: "a" });
assert.equal(postTerminalReview.pending, "view");
globalThis.planReviewHarness.callbacks.onViewChange(postTerminalReview, { searchQuery: "ab" });
globalThis.planReviewHarness.callbacks.onViewChange(postTerminalReview, { searchQuery: "abc" });
assert.equal(planViewUpdates.length, searchUpdateBase + 1, "typing during a slow refresh does not overlap requests");
const firstSearch = planSummary({
  ...retainedSummary, disposition: "applied", view_revision: 5, search_query: "a",
});
planViewUpdates[searchUpdateBase].resolve(firstSearch);
await until(() => planWindows.length === searchWindowBase + 1);
planWindows.at(-1).resolve(planWindow(firstSearch));
await until(() => planViewUpdates.length === searchUpdateBase + 2);
assert.deepEqual(calls.at(-1), ["update-plan", TASK_G, 5, {
  searchQuery: "abc", filters: [], sortColumn: "size", sortDirection: "ascending",
  collapseNodeId: null, collapsed: null,
}], "only the latest queued query follows the completed refresh");
const finalSearch = planSummary({
  ...retainedSummary, disposition: "applied", view_revision: 6, search_query: "abc",
});
planViewUpdates[searchUpdateBase + 1].resolve(finalSearch);
await until(() => planWindows.length === searchWindowBase + 2);
planWindows.at(-1).resolve(planWindow(finalSearch));
await until(() => postTerminalReview.pending === null);
assert.equal(postTerminalReview.summary.search_query, "abc");

const retainedBeforeCapacityRefusal = taskButtons();
createButton().click();
await until(() => creates.length === 4);
creates[3].reject(new Error("simulated task capacity refusal"));
await turns();
assert.equal(
  status.textContent,
  "A task could not be created. Close an unused task or wait, then try again.",
);
assertSameNodes(
  taskButtons(),
  retainedBeforeCapacityRefusal,
  "task creation refusal must retain every existing task card",
);

const stoppedTaskId = `task-${"8".repeat(32)}`;
const stoppedSessionId = "8".repeat(32);
const stoppedOpenBase = planOpens.length;
const stoppedWindowBase = planWindows.length;
const stoppedTask = globalThis.taskHarness.adoptTask({
  task_id: stoppedTaskId, session_id: stoppedSessionId,
  session_state: "active", session_released: false,
  task_kind: "sync-plan", request_id: "a".repeat(32),
});
await until(() => planOpens.length === stoppedOpenBase + 1);
const stoppedSummary = planSummary({
  task_id: stoppedTaskId, selection_state: "committed",
  execution: { ...committedReview.execution, session_id: stoppedSessionId },
});
planOpens.at(-1).resolve(stoppedSummary);
await until(() => planWindows.length === stoppedWindowBase + 1);
planWindows.at(-1).resolve(planWindow(stoppedSummary));
await until(() => stoppedTask.review !== null);
taskButton(stoppedTask.label).click();
const oldStoppedReview = stoppedTask.review;
const priorSessionId = stoppedTask.sessionId;
const beforeStaleReviewControl = executionControls.length;
stoppedTask.sessionId = "9".repeat(32);
globalThis.planReviewHarness.callbacks.onControl(oldStoppedReview, "pause");
assert.equal(executionControls.length, beforeStaleReviewControl,
  "an old review cannot control a replacement session while it loads");
stoppedTask.sessionId = priorSessionId;
const acceptedControlIndex = executionControls.length;
globalThis.planReviewHarness.callbacks.onControl(oldStoppedReview, "pause");
const acceptedOpenBase = planOpens.length;
const acceptedWindowBase = planWindows.length;
void globalThis.taskHarness.forceReview(stoppedTask, true);
await until(() => planOpens.length === acceptedOpenBase + 1);
planOpens.at(-1).resolve(oldStoppedReview.summary);
await until(() => planWindows.length === acceptedWindowBase + 1);
planWindows.at(-1).resolve(planWindow(oldStoppedReview.summary));
await until(() => stoppedTask.review !== oldStoppedReview);
const stoppedReview = stoppedTask.review;
assert.equal(stoppedReview.pending, "pause");
executionControls[acceptedControlIndex].resolve({
  code: "accepted", session_id: stoppedSessionId, before: "running",
  after: "pausing", detail: "Pause requested.", accepted: true,
});
await until(() => stoppedReview.pending === null);
assert.equal(stoppedReview.message, "Pausing execution…",
  "accepted control feedback survives review replacement");
assert.equal(stoppedTask.executionControlState, "running",
  "the receipt leaves control state with the last snapshot");
const stoppedDrain = drains.get(stoppedTaskId);
assert.ok(stoppedDrain);
stoppedDrain.acceptRefusal(new (await import(bridgeUrl)).TerminalPresentationError());
assert.equal(stoppedTask.drainUnavailable, false,
  "terminal presentation retry does not stop the live drain");
const controlCallsBeforeStop = calls.filter(([name]) => name === "control-execution").length;
let stoppedRecoveryCalls = 0;
stoppedDrain.acceptRefusal(new Error("lost updates"), () => {
  stoppedRecoveryCalls += 1;
  return true;
});
assert.equal(stoppedTask.drainUnavailable, true);
assert.match(stoppedReview.message, /Retry updates/);
globalThis.planReviewHarness.callbacks.onControl(stoppedReview, "pause");
assert.equal(calls.filter(([name]) => name === "control-execution").length,
  controlCallsBeforeStop, "stopped drain never dispatches a control");
assert.doesNotMatch(stoppedReview.message, /uncertain/);
const stoppedRefreshOpenBase = planOpens.length;
const stoppedRefreshWindowBase = planWindows.length;
void globalThis.taskHarness.forceReview(stoppedTask, true);
await until(() => planOpens.length === stoppedRefreshOpenBase + 1);
planOpens.at(-1).resolve(stoppedReview.summary);
await until(() => planWindows.length === stoppedRefreshWindowBase + 1);
planWindows.at(-1).resolve(planWindow(stoppedReview.summary));
await until(() => stoppedTask.review !== stoppedReview);
assert.equal(stoppedTask.error, stoppedReview.message,
  "review refresh retains stopped-update guidance on the task card");
assert.equal(stoppedTask.review.message, stoppedReview.message);
globalThis.planReviewHarness.callbacks.onControl(stoppedTask.review, "cancel");
assert.equal(calls.filter(([name]) => name === "control-execution").length,
  controlCallsBeforeStop, "refreshed stopped review cannot dispatch a control");
const stoppedRetryButton = walk(app).find((element) =>
  element.ariaLabel === `Retry updates for ${stoppedTask.label}`);
assert.ok(stoppedRetryButton);
assert.equal(typeof stoppedTask.recoveryRetry, "function");
assert.equal(stoppedTask.recoverySessionId, stoppedTask.sessionId);
assert.equal(stoppedTask.closeRecovery, null);
assert.equal(stoppedRetryButton.disabled, false);
stoppedRetryButton.click();
assert.equal(stoppedRecoveryCalls, 1);
assert.equal(stoppedTask.drainUnavailable, true,
  "retry intent alone cannot restore control authority");
stoppedDrain.acceptRecovered(stoppedTaskId, stoppedSessionId);
assert.equal(stoppedTask.drainUnavailable, false);
assert.equal(stoppedTask.recoveryRetry, null);
assert.equal(stoppedTask.review.message, "Pausing execution…",
  "recovery restores accepted control feedback beneath the stopped-update guidance");
const recoveredOpenBase = planOpens.length;
const recoveredWindowBase = planWindows.length;
void globalThis.taskHarness.forceReview(stoppedTask, true);
await until(() => planOpens.length === recoveredOpenBase + 1);
planOpens.at(-1).resolve(stoppedTask.review.summary);
await until(() => planWindows.length === recoveredWindowBase + 1);
planWindows.at(-1).resolve(planWindow(stoppedTask.review.summary));
await until(() => stoppedTask.review.message === "Pausing execution…" && !stoppedTask.reviewLoading);
const uncertainCloseIndex = closes.length;
walk(app).find((element) => element.ariaLabel === `Close ${stoppedTask.label}`).click();
await until(() => closes.length === uncertainCloseIndex + 1);
let closeOutcomeChecks = 0;
const checkExactClose = () => {
  closeOutcomeChecks += 1;
  return Promise.resolve(null);
};
closes.at(-1).notify({ state: "unavailable", canCheck: true,
  message: "execution-check-sentinel", check: checkExactClose });
await until(() => stoppedTask.closeRecovery?.canCheck === true);
assert.equal(walk(app).find((element) =>
  element.ariaLabel === `Retry updates for ${stoppedTask.label}`).hidden, true,
  "uncertain Close fences observation retry");
walk(app).find((element) => element.ariaLabel === `Check Close outcome for ${stoppedTask.label}`).click();
await until(() => closeOutcomeChecks === 1);
assert.equal(closes.length, uncertainCloseIndex + 1, "Check does not resubmit Close");
closes.at(-1).resolve({ task_id: stoppedTaskId, session_id: stoppedSessionId, disposition: "closed" });
await turns();
assert.ok(taskButton(stoppedTask.label) === undefined);

const earlyStoppedTaskId = `task-${"9".repeat(32)}`;
const earlyStoppedSessionId = "9".repeat(32);
const earlyStoppedOpenBase = planOpens.length;
const earlyStoppedWindowBase = planWindows.length;
const earlyStoppedTask = globalThis.taskHarness.adoptTask({
  task_id: earlyStoppedTaskId, session_id: earlyStoppedSessionId,
  session_state: "active", session_released: false,
  task_kind: "sync-plan", request_id: "a".repeat(32),
});
await until(() => planOpens.length === earlyStoppedOpenBase + 1);
assert.equal(earlyStoppedTask.executionStarted, false,
  "rehydration has not loaded the committed review yet");
const earlyStoppedDrain = drains.get(earlyStoppedTaskId);
earlyStoppedDrain.acceptRefusal(new Error("lost updates"), () => true);
assert.equal(earlyStoppedTask.drainUnavailable, true,
  "an active drain refusal is retained before execution review loads");
assert.match(earlyStoppedTask.error, /Retry updates/);
const earlyStoppedSummary = planSummary({
  task_id: earlyStoppedTaskId, selection_state: "committed",
  execution: { ...committedReview.execution, session_id: earlyStoppedSessionId },
});
planOpens.at(-1).resolve(earlyStoppedSummary);
await until(() => planWindows.length === earlyStoppedWindowBase + 1);
planWindows.at(-1).resolve(planWindow(earlyStoppedSummary));
await until(() => earlyStoppedTask.review !== null);
taskButton(earlyStoppedTask.label).click();
assert.equal(earlyStoppedTask.executionStarted, true);
assert.match(earlyStoppedTask.error, /Retry updates/);
assert.equal(earlyStoppedTask.review.message, earlyStoppedTask.error);
const controlCallsBeforeEarlyStop = calls.filter(([name]) => name === "control-execution").length;
globalThis.planReviewHarness.callbacks.onControl(earlyStoppedTask.review, "pause");
assert.equal(calls.filter(([name]) => name === "control-execution").length,
  controlCallsBeforeEarlyStop,
  "early drain refusal prevents control dispatch after committed review loads");
const failedCloseIndex = closes.length;
walk(app).find((element) => element.ariaLabel === `Close ${earlyStoppedTask.label}`).click();
await until(() => closes.length === failedCloseIndex + 1);
closes.at(-1).reject(new Error("temporary close failure"));
await until(() => earlyStoppedTask.closeFailed);
const independentCloseError = earlyStoppedTask.error;
assert.equal(independentCloseError, "Close was refused. Retry close.");
walk(app).find((element) =>
  element.ariaLabel === `Retry updates for ${earlyStoppedTask.label}`).click();
earlyStoppedDrain.acceptRecovered(earlyStoppedTaskId, earlyStoppedSessionId);
assert.equal(earlyStoppedTask.error, independentCloseError,
  "observation recovery cannot erase a later Close failure");
earlyStoppedDrain.acceptRefusal(new Error("updates stopped again"), () => true);
assert.equal(earlyStoppedTask.error, independentCloseError,
  "another drain refusal cannot replace Close feedback");
const pendingCloseIndex = closes.length;
walk(app).find((element) =>
  element.ariaLabel === `Retry close for ${earlyStoppedTask.label}`).click();
await until(() => closes.length === pendingCloseIndex + 1);
closes.at(-1).resolve({
  task_id: earlyStoppedTaskId, session_id: earlyStoppedSessionId, disposition: "pending",
});
await turns();
assert.equal(earlyStoppedTask.closePending, true);
const pendingRetry = walk(app).find((element) =>
  element.ariaLabel === `Retry updates for ${earlyStoppedTask.label}`);
assert.ok(pendingRetry && !pendingRetry.disabled && !pendingRetry.hidden,
  "pending Close leaves the task-level recovery action available");
pendingRetry.click();
earlyStoppedDrain.acceptRecovered(earlyStoppedTaskId, earlyStoppedSessionId);
assert.equal(earlyStoppedTask.closePending, true,
  "empty recovery alone cannot claim terminal Close");
earlyStoppedDrain.acceptUpdate({ update_type: "record", record: { state: "canceled" } },
  pageSnapshot(earlyStoppedTaskId, earlyStoppedSessionId, { session_state: "canceled" }));
await until(() => closes.length === pendingCloseIndex + 2);
closes.at(-1).resolve({
  task_id: earlyStoppedTaskId, session_id: earlyStoppedSessionId, disposition: "closed",
});
await turns();
assert.ok(taskButton(earlyStoppedTask.label) === undefined);

const replacedSessionTaskId = `task-${"6".repeat(32)}`;
const replacedSessionId = "6".repeat(32);
const replacementSessionId = "4".repeat(32);
const replacedSessionOpenBase = planOpens.length;
const replacedSessionWindowBase = planWindows.length;
const replacedSessionTask = globalThis.taskHarness.adoptTask({
  task_id: replacedSessionTaskId, session_id: replacedSessionId,
  session_state: "active", session_released: false,
  task_kind: "sync-plan", request_id: "a".repeat(32),
});
await until(() => planOpens.length === replacedSessionOpenBase + 1);
const replacedSessionSummary = planSummary({
  task_id: replacedSessionTaskId, selection_state: "committed",
  execution: { ...committedReview.execution, session_id: replacedSessionId },
});
planOpens.at(-1).resolve(replacedSessionSummary);
await until(() => planWindows.length === replacedSessionWindowBase + 1);
planWindows.at(-1).resolve(planWindow(replacedSessionSummary));
await until(() => replacedSessionTask.review !== null);
taskButton(replacedSessionTask.label).click();
const oldSessionReview = replacedSessionTask.review;
const staleControlIndex = executionControls.length;
globalThis.planReviewHarness.callbacks.onControl(oldSessionReview, "cancel");
assert.equal(oldSessionReview.pending, "cancel");
const replacementOpenBase = planOpens.length;
const replacementWindowBase = planWindows.length;
globalThis.taskHarness.adoptTask({
  task_id: replacedSessionTaskId, session_id: replacementSessionId,
  session_state: "active", session_released: false,
  task_kind: "sync-plan", request_id: "a".repeat(32),
});
await until(() => planOpens.length === replacementOpenBase + 1);
const replacementSummary = planSummary({
  task_id: replacedSessionTaskId, selection_state: "committed",
  execution: { ...committedReview.execution, session_id: replacementSessionId },
});
planOpens.at(-1).resolve(replacementSummary);
await until(() => planWindows.length === replacementWindowBase + 1);
planWindows.at(-1).resolve(planWindow(replacementSummary));
await until(() => replacedSessionTask.review !== oldSessionReview);
const newSessionReview = replacedSessionTask.review;
assert.equal(newSessionReview.pending, null);
const newSessionMessage = newSessionReview.message;
executionControls[staleControlIndex].resolve({
  code: "not-found", session_id: replacedSessionId,
  before: "running", after: "running", detail: "Stale control refusal.", accepted: false,
});
await turns();
assert.equal(newSessionReview.message, newSessionMessage,
  "a prior session's control reply cannot overwrite replacement review feedback");
assert.equal(replacedSessionTask.executionControlState, "running");

const unknownReviewTaskId = `task-${"3".repeat(32)}`;
const unknownReviewSessionId = "3".repeat(32);
const unknownOpenBase = planOpens.length;
const unknownWindowBase = planWindows.length;
const unknownReviewTask = globalThis.taskHarness.adoptTask({
  task_id: unknownReviewTaskId, session_id: unknownReviewSessionId,
  session_state: "active", session_released: false,
  task_kind: "sync-plan", request_id: "a".repeat(32),
});
await until(() => planOpens.length === unknownOpenBase + 1);
const unknownSummary = planSummary({ task_id: unknownReviewTaskId });
planOpens.at(-1).resolve(unknownSummary);
await until(() => planWindows.length === unknownWindowBase + 1);
planWindows.at(-1).resolve(planWindow(unknownSummary));
await until(() => unknownReviewTask.review !== null);
taskButton(unknownReviewTask.label).click();
const unknownReview = unknownReviewTask.review;
const unknownSelectionBase = planSelections.length;
globalThis.planReviewHarness.callbacks.onSelect(unknownReview, unknownReview.window.rows[0], true);
await until(() => planSelections.length === unknownSelectionBase + 1);
const pendingReviewClose = walk(app).find((element) =>
  element.ariaLabel === "Wait for the current review action before closing this task.");
assert.equal(pendingReviewClose?.disabled, true,
  "in-flight review and Close use the same visible block reason");
const pendingReviewCloseBase = closes.length;
globalThis.taskHarness.closeRetainedTask(unknownReviewTaskId);
await turns();
assert.equal(closes.length, pendingReviewCloseBase,
  "in-flight review cannot silently submit Close");
planSelections.at(-1).notify({ state: "fixed-unknown", canCheck: false,
  message: "execution-fixed-outcome-sentinel" });
planSelections.at(-1).reject(new OutcomeUnavailableErrorType(null, false));
await until(() => unknownReview.recovery?.state === "fixed-unknown");
assert.equal(unknownReview.pending, "outcome");
assert.equal(unknownReview.recovery.canCheck, false);
assert.equal(unknownReview.recovery.message, "execution-fixed-outcome-sentinel");
const unknownSelectionCount = planSelections.length;
globalThis.planReviewHarness.callbacks.onSelect(unknownReview, unknownReview.window.rows[0], false);
globalThis.planReviewHarness.callbacks.onHighlight(unknownReview, "replace", unknownReview.window.rows[0].node_id);
await turns();
assert.equal(planSelections.length, unknownSelectionCount,
  "fixed-unknown review intent blocks a second selection effect");
const unknownClose = walk(app).find((element) =>
  element.ariaLabel === `Close ${unknownReviewTask.label}`);
assert.equal(unknownClose?.disabled, false,
  "exact task/session Close remains available after a fixed review error");
const unknownReloadBase = planOpens.length;
const unknownReloadWindowBase = planWindows.length;
void globalThis.taskHarness.forceReview(unknownReviewTask, true);
await until(() => planOpens.length === unknownReloadBase + 1);
planOpens.at(-1).resolve(unknownSummary);
await until(() => planWindows.length === unknownReloadWindowBase + 1);
planWindows.at(-1).resolve(planWindow(unknownSummary));
await until(() => unknownReviewTask.review !== unknownReview);
assert.equal(unknownReviewTask.review.pending, "outcome",
  "a read-only review replacement retains the fixed-unknown intent fence");
assert.equal(unknownReviewTask.review.recovery.canCheck, false);
const unknownCloseBase = closes.length;
unknownClose.click();
await until(() => closes.length === unknownCloseBase + 1);
assert.deepEqual(calls.at(-1), ["close", unknownReviewTaskId, unknownReviewSessionId],
  "fixed review failure closes only its exact task/session");
closes.at(-1).resolve({ task_id: unknownReviewTaskId,
  session_id: unknownReviewSessionId, disposition: "closed" });
await until(() => taskButton(unknownReviewTask.label) === undefined);

async function openActiveUnknownOutcomeTask(hex) {
  const taskId = `task-${hex.repeat(32)}`;
  const sessionId = hex.repeat(32);
  const openBase = planOpens.length;
  const windowBase = planWindows.length;
  const task = globalThis.taskHarness.adoptTask({
    task_id: taskId, session_id: sessionId, session_state: "active",
    session_released: false, task_kind: "sync-plan", request_id: "a".repeat(32),
  });
  task.executionStarted = true;
  await until(() => planOpens.length === openBase + 1);
  const summary = planSummary({
    task_id: taskId, selection_state: "committed",
    execution: { ...planSummary().execution, session_id: sessionId },
  });
  planOpens.at(-1).resolve(summary);
  await until(() => planWindows.length === windowBase + 1);
  planWindows.at(-1).resolve(planWindow(summary));
  await until(() => task.review !== null);
  taskButton(task.label).click();
  return task;
}

const highlightTask = await openActiveUnknownOutcomeTask("0");
const highlightReview = highlightTask.review;
const highlightBase = planHighlights.length;
deferHighlight = true;
globalThis.planReviewHarness.callbacks.onHighlight(
  highlightReview, "replace", highlightReview.window.rows[0].node_id,
);
await until(() => planHighlights.length === highlightBase + 1);
planHighlights.at(-1).reject(new Error("highlight transport failed"));
await until(() => highlightReview.refreshAvailable === true);
deferHighlight = false;
assert.equal(highlightReview.recovery?.state === "fixed-unknown", false);
assert.equal(highlightReview.pending, null);
assert.match(highlightReview.message, /Refresh review/);
const highlightClose = walk(app).find((element) =>
  element.ariaLabel === `Close ${highlightTask.label}`);
assert.equal(highlightClose?.disabled, false, "presentation failure does not fence Close");
const highlightReloadBase = planOpens.length;
const highlightReloadWindowBase = planWindows.length;
globalThis.planReviewHarness.callbacks.onRetryOutcome(highlightReview);
await until(() => planOpens.length === highlightReloadBase + 1);
planOpens.at(-1).resolve(highlightReview.summary);
await until(() => planWindows.length === highlightReloadWindowBase + 1);
planWindows.at(-1).resolve(planWindow(highlightReview.summary));
await until(() => highlightTask.review !== highlightReview);
assert.equal(highlightTask.review.recovery?.state === "fixed-unknown", false);

const unknownPauseTask = await openActiveUnknownOutcomeTask("1");
const pauseReview = unknownPauseTask.review;
const pauseBase = executionControls.length;
globalThis.planReviewHarness.callbacks.onControl(pauseReview, "pause");
await until(() => executionControls.length === pauseBase + 1);
executionControls.at(-1).notify({ state: "fixed-unknown", canCheck: false,
  message: "execution-fixed-outcome-sentinel" });
executionControls.at(-1).reject(new OutcomeUnavailableErrorType(null, false));
await until(() => pauseReview.recovery?.state === "fixed-unknown");
assert.equal(pauseReview.outcomeAction, "pause");
assert.equal(unknownPauseTask.canCancelAfterFixedReviewOutcome, true);
globalThis.planReviewHarness.callbacks.onControl(pauseReview, "cancel");
await until(() => executionControls.length === pauseBase + 2);
assert.equal(pauseReview.pending, "outcome");
assert.equal(unknownPauseTask.executionControlAttempt.independent, true);
let cancelObservationCalls = 0;
executionControls.at(-1).notify({ state: "unavailable", canCheck: true,
  message: "execution-check-sentinel", check: () => {
  cancelObservationCalls += 1;
  return Promise.resolve(null);
} });
await until(() => unknownPauseTask.executionControlAttempt.recovery?.canCheck === true);
assert.equal(pauseReview.recovery.canCheck, false, "independent Cancel cannot replace the original warning");
assert.equal(walk(app).find((element) => element.ariaLabel ===
  "Check the original Cancel outcome before closing this task.")?.disabled, true,
  "pending independent Cancel still fences task Close");
globalThis.planReviewHarness.callbacks.onControl(pauseReview, "cancel");
assert.equal(executionControls.length, pauseBase + 2, "pending Cancel cannot be resubmitted");
const cancelReloadBase = planOpens.length;
const cancelReloadWindowBase = planWindows.length;
void globalThis.taskHarness.forceReview(unknownPauseTask, true);
await until(() => planOpens.length === cancelReloadBase + 1);
planOpens.at(-1).resolve(pauseReview.summary);
await until(() => planWindows.length === cancelReloadWindowBase + 1);
planWindows.at(-1).resolve(planWindow(pauseReview.summary));
await until(() => unknownPauseTask.review !== pauseReview);
const reloadedPauseReview = unknownPauseTask.review;
assert.equal(reloadedPauseReview.pending, "outcome");
assert.equal(reloadedPauseReview.recovery.message, "execution-fixed-outcome-sentinel");
globalThis.planReviewHarness.callbacks.onRetryOutcome(reloadedPauseReview);
await until(() => cancelObservationCalls === 1);
assert.equal(executionControls.length, pauseBase + 2, "Check observes without resubmitting Cancel");
executionControls.at(-1).resolve({
  code: "accepted", session_id: unknownPauseTask.sessionId,
  before: "running", after: "canceling", detail: "Cancel requested.", accepted: true,
});
await until(() => unknownPauseTask.executionControlAttempt.pending === false);
assert.equal(unknownPauseTask.executionControlAttempt.accepted, true);
assert.equal(unknownPauseTask.canCancelAfterFixedReviewOutcome, false);
assert.equal(reloadedPauseReview.recovery.message, "execution-fixed-outcome-sentinel");

const unknownCancelTask = await openActiveUnknownOutcomeTask("4");
const cancelReview = unknownCancelTask.review;
const originalCancelBase = executionControls.length;
globalThis.planReviewHarness.callbacks.onControl(cancelReview, "cancel");
await until(() => executionControls.length === originalCancelBase + 1);
executionControls.at(-1).notify({ state: "fixed-unknown", canCheck: false,
  message: "execution-fixed-outcome-sentinel" });
executionControls.at(-1).reject(new OutcomeUnavailableErrorType(null, false));
await until(() => cancelReview.recovery?.state === "fixed-unknown");
assert.equal(cancelReview.outcomeAction, "cancel");
assert.equal(unknownCancelTask.canCancelAfterFixedReviewOutcome, false);
globalThis.planReviewHarness.callbacks.onControl(cancelReview, "cancel");
await turns();
assert.equal(executionControls.length, originalCancelBase + 1,
  "unknown original Cancel cannot be treated as an independent Cancel");

const pendingViewTask = await openActiveUnknownOutcomeTask("6");
const pendingViewReview = pendingViewTask.review;
const pendingViewBase = planViewUpdates.length;
globalThis.planReviewHarness.callbacks.onViewChange(pendingViewReview, { sortColumn: "size" });
await until(() => planViewUpdates.length === pendingViewBase + 1);
assert.equal(pendingViewReview.pending, "view");
const viewCloseBase = closes.length;
walk(app).find((element) => element.ariaLabel === `Close ${pendingViewTask.label}`).click();
await until(() => closes.length === viewCloseBase + 1);
assert.equal(pendingViewTask.closePending, true, "presentation work does not fence Close");
planViewUpdates.at(-1).resolve(planSummary({ ...pendingViewReview.summary,
  view_revision: pendingViewReview.summary.view_revision + 1 }));
await turns();
assert.equal(pendingViewTask.closePending, true, "late view result cannot clear Close ownership");
assert.equal(pendingViewReview.pending, "close");
closes.at(-1).resolve({ task_id: pendingViewTask.taskId,
  session_id: pendingViewTask.sessionId, disposition: "closed" });
await until(() => taskButton(pendingViewTask.label) === undefined);

const pendingReleaseTask = await openActiveUnknownOutcomeTask("5");
const pendingReleaseDrain = drains.get(pendingReleaseTask.taskId);
let releaseChecks = 0;
pendingReleaseDrain.acceptReleaseDelay(pendingReleaseTask.taskId,
  pendingReleaseTask.sessionId, fakeRecoveryHandle({ canCheck: true,
    message: "release-check-sentinel", check: () => {
    releaseChecks += 1;
    return Promise.resolve(null);
  } }));
assert.equal(pendingReleaseTask.drainUnavailable, false,
  "healthy delayed release is not a drain refusal");
pendingReleaseDrain.acceptRecovered(pendingReleaseTask.taskId, pendingReleaseTask.sessionId);
assert.equal(pendingReleaseTask.releaseRecovery.message, "release-check-sentinel",
  "unrelated recovery cannot clear pending release feedback");
const releaseCheckButton = walk(app).find((element) =>
  element.ariaLabel === `Check release outcome for ${pendingReleaseTask.label}`);
assert.ok(releaseCheckButton && !releaseCheckButton.hidden);
releaseCheckButton.click();
await until(() => releaseChecks === 1);
assert.equal(pendingReleaseTask.sessionReleased, false,
  "observation alone does not claim a release receipt");
pendingReleaseDrain.acceptRelease(pendingReleaseTask.taskId, pendingReleaseTask.sessionId);
assert.equal(pendingReleaseTask.releaseRecovery, null);
assert.equal(pendingReleaseTask.sessionReleased, true);

const closeRaceTaskId = `task-${"2".repeat(32)}`;
const closeRaceSessionId = "2".repeat(32);
const closeRaceTask = globalThis.taskHarness.adoptTask({
  task_id: closeRaceTaskId, session_id: closeRaceSessionId,
  session_state: "active", session_released: false,
  task_kind: "inventory", request_id: "a".repeat(32),
});
await until(() => drains.has(closeRaceTaskId));
const closeRaceBase = closes.length;
void globalThis.taskHarness.closeRetainedTask(closeRaceTaskId);
await until(() => closes.length === closeRaceBase + 1);
drains.get(closeRaceTaskId).acceptUpdate({ update_type: "record", record: { state: "canceled" } },
  pageSnapshot(closeRaceTaskId, closeRaceSessionId, { session_state: "canceled" }));
await turns();
assert.equal(closes.length, closeRaceBase + 1,
  "terminal state before the first Close receipt does not submit a second Close");
closes[closeRaceBase].resolve({
  task_id: closeRaceTaskId, session_id: closeRaceSessionId, disposition: "pending",
});
await until(() => closes.length === closeRaceBase + 2);
assert.equal(closeRaceTask.closePending, true,
  "the known pending receipt and terminal state admit one Close continuation");
closes[closeRaceBase + 1].resolve({
  task_id: closeRaceTaskId, session_id: closeRaceSessionId, disposition: "pending",
});
await turns();
drains.get(closeRaceTaskId).acceptUpdate({ update_type: "record", record: { state: "canceled" } },
  pageSnapshot(closeRaceTaskId, closeRaceSessionId, { session_state: "canceled" }));
await turns();
assert.equal(closes.length, closeRaceBase + 2,
  "a pending continuation cannot create an automatic Close loop");
assert.equal(closeRaceTask.closePending, true,
  "continued pending Close remains visible for explicit resolution");
assert.equal(closeRaceTask.closeManualReady, true);
assert.match(closeRaceTask.closeMessage, /Select Retry close/);
void globalThis.taskHarness.closeRetainedTask(closeRaceTaskId);
await until(() => closes.length === closeRaceBase + 3);
closes[closeRaceBase + 2].resolve({
  task_id: closeRaceTaskId, session_id: closeRaceSessionId, disposition: "closed",
});
await turns();
void globalThis.taskHarness.closeRetainedTask(closeRaceTaskId);
await turns();
assert.equal(closes.length, closeRaceBase + 3,
  "a settled task cannot receive another Close effect");

// The execution promise rejects after its recovery handle has been retained.
// A fresh review must leave that handle, its guidance, and the effect fences intact.
const uncertainExecutionTaskId = `task-${"9".repeat(32)}`;
const uncertainExecutionSessionId = "9".repeat(32);
const uncertainOpenBase = planOpens.length;
const uncertainWindowBase = planWindows.length;
const uncertainExecutionTask = globalThis.taskHarness.adoptTask({
  task_id: uncertainExecutionTaskId, session_id: uncertainExecutionSessionId,
  session_state: "completed", session_released: true,
  task_kind: "sync-plan", request_id: "9".repeat(32),
});
await until(() => planOpens.length === uncertainOpenBase + 1);
const uncertainSummary = planSummary({
  task_id: uncertainExecutionTaskId, request_id: "9".repeat(32),
  preflight_ready: true, preflight_refusal_count: 0, warning_count: 0,
});
planOpens.at(-1).resolve(uncertainSummary);
await until(() => planWindows.length === uncertainWindowBase + 1);
planWindows.at(-1).resolve(planWindow(uncertainSummary));
await until(() => uncertainExecutionTask.review?.summary === uncertainSummary);
taskButton(uncertainExecutionTask.label).click();
const uncertainExecutionReview = uncertainExecutionTask.review;
const uncertainExecutionBase = planExecutions.length;
globalThis.planReviewHarness.callbacks.onExecute(uncertainExecutionReview, executeInvoker);
await until(() => planExecutions.length === uncertainExecutionBase + 1);
const uncertainExecution = planExecutions.at(-1);
const originalRecovery = uncertainExecution.recovery;
uncertainExecution.notify({ state: "unavailable", canCheck: true,
  message: "execution-check-sentinel", check: () => Promise.resolve(null) });
assert.equal(uncertainExecutionTask.executionAttempt.recovery, originalRecovery);
originalRecovery.state = "fixed-unknown";
originalRecovery.canCheck = false;
originalRecovery.message = "execution-admission-owner-sentinel";
uncertainExecution.reject(new StartPlanUncertainErrorType());
await until(() => uncertainExecutionTask.executionAttempt?.state === "uncertain");
assert.equal(uncertainExecutionTask.executionAttempt.recovery, originalRecovery);
assert.equal(uncertainExecutionReview.pending, "outcome");
const fencedSelectionBase = planSelections.length;
globalThis.planReviewHarness.callbacks.onSelect(
  uncertainExecutionReview, uncertainExecutionReview.window.rows[0], false,
);
assert.equal(planSelections.length, fencedSelectionBase);
globalThis.planReviewHarness.callbacks.onExecute(uncertainExecutionReview, executeInvoker);
assert.equal(planExecutions.length, uncertainExecutionBase + 1);
const fencedClose = taskButton(uncertainExecutionTask.label).parentNode.children.find(
  (element) => element.classList.values.has("nami-task-rail__close"));
assert.equal(fencedClose?.disabled, true);
assert.equal(fencedClose.ariaLabel, uncertainExecutionTask.closeBlockReason);
const closeBase = closes.length;
fencedClose.click();
assert.equal(closes.length, closeBase);
void globalThis.taskHarness.forceReview(uncertainExecutionTask, true);
await until(() => planOpens.length === uncertainOpenBase + 2);
planOpens.at(-1).resolve(uncertainSummary);
await until(() => planWindows.length === uncertainWindowBase + 2);
planWindows.at(-1).resolve(planWindow(uncertainSummary));
await until(() => uncertainExecutionTask.review !== uncertainExecutionReview);
assert.equal(uncertainExecutionTask.executionAttempt.recovery, originalRecovery);
assert.equal(originalRecovery.message, "execution-admission-owner-sentinel");
globalThis.planReviewHarness.callbacks.onExecute(uncertainExecutionTask.review, executeInvoker);
assert.equal(planExecutions.length, uncertainExecutionBase + 1);
assert.equal(fencedClose.disabled, true);

const failedTaskId = `task-${"3".repeat(32)}`;
const failedPlanSession = "3".repeat(32);
const failedExecutionSession = "c".repeat(32);
const failedOpenBase = planOpens.length;
const failedWindowBase = planWindows.length;
const failedTask = globalThis.taskHarness.adoptTask({
  task_id: failedTaskId, session_id: failedPlanSession,
  session_state: "completed", session_released: true,
  task_kind: "sync-plan", request_id: "3".repeat(32),
});
await until(() => planOpens.length === failedOpenBase + 1);
const failedPlanSummary = planSummary({ task_id: failedTaskId,
  request_id: "3".repeat(32), preflight_ready: true,
  preflight_refusal_count: 0, warning_count: 0 });
planOpens.at(-1).resolve(failedPlanSummary);
await until(() => planWindows.length === failedWindowBase + 1);
planWindows.at(-1).resolve(planWindow(failedPlanSummary));
await until(() => failedTask.review !== null);
taskButton(failedTask.label).click();
const failedPlanDrain = drains.get(failedTaskId);
failedPlanDrain.acceptUpdate({ update_type: "record", record: { state: "completed" } },
  pageSnapshot(failedTaskId, failedPlanSession, {
    revision: 40, session_state: "completed",
  }));
const failedExecuteBase = planExecutions.length;
globalThis.planReviewHarness.callbacks.onExecute(failedTask.review, executeInvoker);
await until(() => planExecutions.length === failedExecuteBase + 1);
planExecutions.at(-1).resolve({ task_id: failedTaskId, session_id: failedExecutionSession });
await until(() => failedTask.sessionId === failedExecutionSession);
const failedExecutionDrain = drains.get(failedTaskId);
const terminalFailureResult = executionResult({ headline: "failed", filesystem: "failed" });
failedExecutionDrain.acceptUpdate({ update_type: "record", record: {
  kind: "sync-execution", state: "failed", result: terminalFailureResult,
} }, pageSnapshot(failedTaskId, failedExecutionSession, {
  session_state: "failed", terminal_result: terminalFailureResult,
}));
assert.equal(failedTask.sessionState, "failed",
  "the new execution's lower revision cannot suppress its failed terminal record");
assert.equal(failedTask.executionResult, terminalFailureResult);
assert.equal(taskStatusDigest(failedTask).title, "Failed");

process.stdout.write("ok");
