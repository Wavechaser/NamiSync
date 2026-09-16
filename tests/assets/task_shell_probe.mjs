import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

class ClassList {
  constructor() { this.values = new Set(); }
  add(...values) { for (const value of values) this.values.add(value); }
}

class ElementFake {
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
const calls = [];
const creates = [];
const closes = [];
const drains = new Map();
const lists = [];
const planOpens = [];
const planWindows = [];
const planViewUpdates = [];
const planSelections = [];
const planExecutions = [];
const executionControls = [];
const planAgainStarts = [];
const setupReads = [];
const reviewRenders = [];
const confirmationRequests = [];
const executeInvoker = new HTMLElement("button");
let StartPlanUncertainErrorType = null;

function deferred(collection) {
  let resolve;
  let reject;
  const promise = new Promise((acceptResolve, onReject) => {
    resolve = acceptResolve;
    reject = onReject;
  });
  const entry = { promise, resolve, reject };
  collection.push(entry);
  return promise;
}

globalThis.taskHarness = {
  calls,
  createTask() { calls.push(["create"]); return deferred(creates); },
  closeTask(taskId, sessionId) {
    calls.push(["close", taskId, sessionId]);
    return deferred(closes);
  },
  listTasks() { calls.push(["list"]); return deferred(lists); },
  startTaskDrain(taskId, sessionId, acceptUpdate, acceptRefusal, initialState, acceptRelease) {
    calls.push(["drain", taskId, sessionId, initialState]);
    drains.set(taskId, { acceptUpdate, acceptRefusal, acceptRelease });
    return () => calls.push(["stop", taskId]);
  },
  openPlanView(...args) { calls.push(["open-plan", ...args]); return deferred(planOpens); },
  getPlanWindow(...args) { calls.push(["plan-window", ...args]); return deferred(planWindows); },
  updatePlanView(...args) { calls.push(["update-plan", ...args]); return deferred(planViewUpdates); },
  mutatePlanSelection(...args) { calls.push(["select-plan", ...args]); return deferred(planSelections); },
  startExecution(...args) { calls.push(["execute-plan", ...args]); return deferred(planExecutions); },
  controlExecution(...args) { calls.push(["control-execution", ...args]); return deferred(executionControls); },
  planAgain(...args) { calls.push(["plan-again", ...args]); return deferred(planAgainStarts); },
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
  'export const renderText = (element, text) => { element.textContent = text; };',
);
const iconsUrl = moduleUrl(`
  export const createIcon = (document) => document.createElement("svg");
`);
const railSource = (await readFile(process.argv[3], "utf8"))
  .replace("./icons.js", iconsUrl)
  .replace("./render.js", renderUrl);
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
  export class StartPlanUncertainError extends BridgeTransportError {
    constructor(retry) { super(); this.retry = retry; }
  }
  export class TaskCreateUncertainError extends BridgeTransportError {
    constructor(retry) { super(); this.retry = retry; }
  }
  export const acknowledgeShellReady = () => Promise.resolve({ acknowledged: true });
  export const echoReadiness = () => Promise.resolve({ acknowledged: true });
  export const whenBridgeApiReady = () => Promise.resolve();
  export const markBridgeOperational = () => {};
  export const createTask = () => globalThis.taskHarness.createTask();
  export const closeTask = (...args) => globalThis.taskHarness.closeTask(...args);
  export const listTasks = () => globalThis.taskHarness.listTasks();
  export const controlExecution = (...args) => globalThis.taskHarness.controlExecution(...args);
  export const getPlanAnchor = () => Promise.reject(new BridgeTransportError());
  export const getPlanWindow = (...args) => globalThis.taskHarness.getPlanWindow(...args);
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
`);
StartPlanUncertainErrorType = (await import(bridgeUrl)).StartPlanUncertainError;
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
  `import { acknowledgeShellReady, admitLocation, BridgeTransportError, closeTask, controlExecution, createTask, echoReadiness, getPlanAnchor, getPlanWindow, listTasks, markBridgeOperational, mutatePlanSelection, openPlanView, pickFolder, planAgain, prepareSetup, readSetup, StartPlanUncertainError, startExecution, startInventory, startPlan, startTaskDrain, TaskCreateUncertainError, updatePlanView, whenBridgeApiReady } from "${bridgeUrl}";`,
);
appSource = appSource
  .replace("./readiness.js", readinessUrl)
  .replace("./appearance.js", appearanceUrl)
  .replace("./theme.js", themeUrl)
  .replace("./execution_confirmation.js", executionConfirmationUrl)
  .replace("./rail.js", moduleUrl(railSource))
  .replace("./panels.js", moduleUrl(preparedPanelSource))
  .replace("./render.js", renderUrl);

function walk(root) {
  return [root, ...root.children.flatMap(walk)];
}

function byText(text) {
  return walk(app).find((element) => element.textContent === text);
}

function createButton() {
  return walk(app).find((element) => element.classList.values.has("nami-task-rail__create"));
}

function taskButton(label) {
  return walk(app).find(
    (element) => element.tagName === "BUTTON" &&
      element.children.some((child) => child.textContent === label),
  );
}

function taskButtons() {
  return walk(app).filter(
    (element) => element.tagName === "BUTTON" &&
      element.classList.values.has("nami-task-card") &&
      element.parentNode.classList.values.has("nami-task-rail__row"),
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
    source_path: "C:\\source",
    target_path: "D:\\target",
    selected_operation_count: 1,
    selectable_operation_count: 1,
    operation_count: 1,
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
    ...overrides,
  };
}

function planWindow(summary, offset = 0) {
  return {
    disposition: "current",
    view_revision: summary.view_revision,
    offset,
    total: 1,
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
  taskButtons().map((button) => button.children[0].textContent),
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
for (const callback of windowListeners.get("pywebviewready") ?? []) callback();
await until(() => lists.length === 2);
creates[1].resolve({ task_id: TASK_D });
await turns();
assert.equal(byText("Task 5"), undefined, "pre-reinjection create response is stale");
lists[1].resolve({ tasks: [
  { task_id: TASK_A, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_B, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_C, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_E, session_id: SESSION_E, session_state: "active", session_released: false },
] });
await until(() => lists.length === 4);
await turns();
assert.equal(byText("Task 5"), undefined, "a list overtaken by create is stale");
const retainedThroughD = { tasks: [
  { task_id: TASK_A, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_B, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_C, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_D, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_E, session_id: SESSION_E, session_state: "active", session_released: false },
] };
lists[2].resolve(retainedThroughD);
lists[3].resolve(retainedThroughD);
await turns();
assert.ok(byText("Task 5"), "current rehydration adopts the retained task");
assert.equal(taskButton("Task 2"), stableTaskBButton, "reinjection preserves existing cards");

for (const callback of windowListeners.get("pywebviewready") ?? []) callback();
await until(() => lists.length === 5);
createButton().click();
await until(() => creates.length === 3);
creates[2].resolve({ task_id: TASK_F });
await turns();
assert.ok(byText("Task 6"));
lists[4].resolve({ tasks: [
  { task_id: TASK_A, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_B, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_C, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_D, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_E, session_id: SESSION_E, session_state: "active", session_released: false },
] });
await until(() => lists.length === 6);
lists[5].resolve({ tasks: [
  ...retainedThroughD.tasks,
  { task_id: TASK_F, session_id: null, session_state: null, session_released: false },
] });
await turns();
assert.ok(byText("Task 6"), "a delayed list cannot erase a completed create");

taskButton("Task 1").click();
for (const callback of windowListeners.get("pywebviewready") ?? []) callback();
await until(() => lists.length === 7);
const firstClose = walk(app).find((element) => element.ariaLabel === "Close Task 1");
firstClose.click();
await until(() => closes.length === 1);
assert.ok(byText("Task 1"), "card remains until close success");
closes[0].resolve({ task_id: TASK_A, session_id: null, disposition: "closed" });
await turns();
assert.equal(byText("Task 1"), undefined);
assert.equal(taskButton("Task 6")?.ariaCurrent, "page", "close selects the newest task");
lists[6].resolve({ tasks: [
  { task_id: TASK_A, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_B, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_C, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_D, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_E, session_id: SESSION_E, session_state: "active", session_released: false },
  { task_id: TASK_F, session_id: null, session_state: null, session_released: false },
] });
await until(() => lists.length === 8);
lists[7].resolve({ tasks: [
  { task_id: TASK_B, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_C, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_D, session_id: null, session_state: null, session_released: false },
  { task_id: TASK_E, session_id: SESSION_E, session_state: "active", session_released: false },
  { task_id: TASK_F, session_id: null, session_state: null, session_released: false },
] });
await turns();
assert.equal(byText("Task 1"), undefined, "a delayed list cannot restore a closed task");

const busyClose = walk(app).find((element) => element.ariaLabel === "Close Task 3");
busyClose.click();
await until(() => closes.length === 2);
closes[1].resolve({ task_id: TASK_E, session_id: SESSION_E, disposition: "pending" });
await turns();
assert.ok(byText("Canceling and closing…"));
drains.get(TASK_E).acceptUpdate({ update_type: "record", record: { state: "canceled" } });
await until(() => closes.length === 3);
assert.deepEqual(calls.at(-1), ["close", TASK_E, SESSION_E]);
closes[2].resolve({ task_id: TASK_E, session_id: SESSION_E, disposition: "closed" });
await turns();
assert.equal(byText("Task 3"), undefined);

for (const callback of windowListeners.get("pywebviewready") ?? []) callback();
await until(() => lists.length === 9);
lists[8].resolve({ tasks: [
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
  "reinjection resumes terminal-session release without losing terminal truth",
);

globalThis.taskHarness.deferTaskGSetup = true;
taskButton("Task 7").click();
drains.get(TASK_G).acceptRelease(TASK_G, SESSION_G);
await until(() => planOpens.length === 1);
assert.deepEqual(calls.at(-1), ["open-plan", TASK_G]);
planOpens[0].reject(new Error("simulated initial plan open failure"));
await until(() => byText("Plan review could not be loaded. Select the task to retry.") !== undefined);
assert.ok(byText("Loading task setup…"), "a failed Plan load leaves the Plan surface");
assert.equal(byText("Plan review test surface"), undefined);

taskButton("Task 7").click();
await until(() => planOpens.length === 2);
assert.deepEqual(calls.at(-1), ["open-plan", TASK_G]);
planOpens[1].resolve(planSummary());
await until(() => planWindows.length === 1);
planWindows[0].reject(new Error("simulated initial plan window failure"));
await until(() => byText("Plan review could not be loaded. Select the task to retry.") !== undefined);
assert.ok(byText("Loading task setup…"));
assert.equal(byText("Plan review test surface"), undefined);

taskButton("Task 7").click();
taskButton("Task 7").click();
await until(() => planOpens.length === 3);
await turns();
assert.equal(planOpens.length, 3, "rapid reselection keeps one Plan retry in flight");
assert.ok(byText("Plan review test surface"), "Plan retry exposes its loading surface");
assert.equal(reviewRenders.at(-1).reviewLoading, true);
const refusedReview = planSummary();
planOpens[2].resolve(refusedReview);
await until(() => planWindows.length === 2);
planWindows[1].resolve(planWindow(refusedReview));
await until(() => reviewRenders.at(-1)?.review?.summary === refusedReview);
const firstReview = reviewRenders.at(-1).review;
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
taskButton("Task 7").click();
assert.equal(firstReview.summary.sort_column, "size");

globalThis.planReviewHarness.callbacks.onSelect(
  firstReview,
  firstReview.window.rows[0],
  false,
);
assert.equal(firstReview.pending, "selection");
const selectedReview = planSummary({
  disposition: "conflict", view_revision: 2, selection_revision: 1,
  selected_operation_count: 1,
});
planSelections[0].resolve(selectedReview);
await until(() => planWindows.length === 4);
planWindows[3].resolve(planWindow(selectedReview));
await until(() => firstReview.pending === null);

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
const retry = () => globalThis.taskHarness.startExecution(
  TASK_G,
  frozenRequestId,
  frozenSelectionRevision,
  true,
);
planExecutions[1].reject(new StartPlanUncertainErrorType(retry));
await until(() => firstReview.pending === null);
assert.equal(reviewRenders.at(-1).executionAttempt.state, "uncertain");
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
await until(() => planExecutions.length === 3);
assert.deepEqual(
  calls.at(-1),
  ["execute-plan", TASK_G, frozenRequestId, frozenSelectionRevision, true],
  "uncertain retry retains the exact confirmed intent after review replacement",
);
planExecutions[2].resolve({ task_id: TASK_G, session_id: executionSession });
await until(() => calls.some(
  (call) => call[0] === "drain" && call[1] === TASK_G && call[2] === executionSession,
));
const executionDrain = drains.get(TASK_G);
assert.notEqual(executionDrain, planDrain, "execution replaces the released plan drain");
assert.equal(planExecutions.length, 3, "navigation cannot duplicate execution admission");
await until(() => planOpens.length === 4);

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
executionDrain.acceptUpdate(stateUpdate("running"));
executionControls[0].resolve({
  code: "accepted", session_id: executionSession, before: "running",
  after: "pausing", detail: "Pause requested; custody is reaching a checkpoint.", accepted: true,
});
await until(() => preRefreshReview.pending === null);
assert.equal(reviewRenders.at(-1).executionControlState, "pausing");
assert.equal(preRefreshReview.message, "Pausing execution…");
executionDrain.acceptUpdate(stateUpdate("paused"));
assert.equal(reviewRenders.at(-1).executionControlState, "paused");

const committedReview = planSummary({
  selection_state: "committed", view_revision: 3, selection_revision: 1,
  preflight_ready: true, preflight_refusal_count: 0, warning_count: 0,
});
planOpens[3].resolve(committedReview);
await until(() => planWindows.length === 5);
planWindows[4].resolve(planWindow(committedReview));
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

const liveReview = liveTask.review;
globalThis.planReviewHarness.callbacks.onControl(liveReview, "resume");
assert.equal(liveReview.pending, "resume", "resume feedback precedes its receipt");
assert.deepEqual(calls.at(-1), ["control-execution", TASK_G, executionSession, "resume"]);
executionDrain.acceptUpdate(stateUpdate("pending"));
executionDrain.acceptUpdate(stateUpdate("running"));
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
executionDrain.acceptUpdate(stateUpdate("running"));
executionControls[2].resolve({
  code: "not-found", session_id: executionSession, before: null,
  after: null, detail: "Pause was not accepted.", accepted: false,
});
await until(() => liveReview.pending === null);
assert.equal(reviewRenders.at(-1).executionControlState, "running");
assert.equal(liveReview.message, "Pause was not accepted.");

globalThis.planReviewHarness.callbacks.onControl(liveReview, "pause");
executionDrain.acceptUpdate(stateUpdate("running"));
executionControls[3].reject(new Error("simulated uncertain control receipt"));
await until(() => liveReview.pending === null);
assert.equal(reviewRenders.at(-1).executionControlState, "running");
assert.equal(liveReview.message, "The pause response was uncertain. Follow the live task status.");

globalThis.planReviewHarness.callbacks.onControl(liveReview, "pause");
executionDrain.acceptUpdate(stateUpdate("pausing"));
executionControls[4].reject(new Error("simulated late uncertain control receipt"));
await until(() => liveReview.pending === null);
assert.equal(reviewRenders.at(-1).executionControlState, "pausing");
assert.equal(liveReview.message, "Pausing execution…");

globalThis.planReviewHarness.callbacks.onControl(liveReview, "cancel");
assert.equal(liveReview.pending, "cancel", "cancel feedback precedes its receipt");
assert.deepEqual(calls.at(-1), ["control-execution", TASK_G, executionSession, "cancel"]);
executionDrain.acceptUpdate({ update_type: "record", record: { state: "refused" } });
await turns();
assert.equal(reviewRenders.at(-1).sessionState, "refused");
const terminalMessage = liveReview.message;
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
liveTask.reviewSessionId = null;
executionDrain.acceptRelease(TASK_G, executionSession);
await until(() => planOpens.length === 5);
planOpens[4].resolve(committedReview);
await until(() => planWindows.length === 6);
planWindows[5].resolve(planWindow(committedReview));
await until(() => reviewRenders.at(-1).review !== liveReview);
const postTerminalReview = reviewRenders.at(-1).review;
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

const retainedBeforeCapacityRefusal = taskButtons();
createButton().click();
await until(() => creates.length === 4);
creates[3].reject(new Error("simulated task capacity refusal"));
await turns();
assert.equal(
  status.textContent,
  "A task could not be created. Close an unused task or wait, then try again.",
);
assert.deepEqual(
  taskButtons(),
  retainedBeforeCapacityRefusal,
  "task creation refusal must retain every existing task card",
);
process.stdout.write("ok");
