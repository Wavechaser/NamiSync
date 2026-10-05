import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fakeRecoveryHandle } from "./fake_recovery_handle.mjs";

const TASK_A = `task-${"a".repeat(32)}`;
const TASK_B = `task-${"b".repeat(32)}`;
const TASK_C = `task-${"c".repeat(32)}`;
const CHOICE = (digit) => `slot-${digit.repeat(32)}`;
const DEFAULT_OPTIONS = Object.freeze({
  filters: [],
  deletion_policy: "trash",
  trash_on_update: false,
  preservation: { preserve_ads: false, preserve_created: true, preserve_acl: false },
  propagate_source_casing: false,
  verify_after_execute: false,
});
const EMPTY_RECENTS = Object.freeze({ sources: [], targets: [], pairs: [] });

class ElementFake {
  constructor(textContent = "") {
    this.textContent = textContent;
    this.children = [];
  }
  append(...values) { this.children.push(...values); }
}

globalThis.HTMLElement = ElementFake;
globalThis.HTMLSelectElement = ElementFake;

function moduleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

function turns(count = 12) {
  return Promise.all(Array.from({ length: count }, async () => Promise.resolve()));
}

async function until(predicate, label) {
  for (let index = 0; index < 200; index += 1) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  throw new Error(`setup app probe timed out: ${label}`);
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((accept, refuse) => { resolve = accept; reject = refuse; });
  return { promise, resolve, reject };
}

// The check resolves the original delivery, never a second adoption promise.
function delayedOriginal(onDelayed, complete) {
  const original = deferred();
  const recovery = fakeRecoveryHandle({ state: "submitting", canCheck: false,
    message: null, check: async () => {
    original.resolve(await complete());
  } });
  onDelayed(recovery);
  recovery.state = "unavailable";
  recovery.canCheck = true;
  recovery.message = "setup-check-sentinel";
  onDelayed(recovery);
  return original.promise;
}

function defaultSnapshot() {
  return {
    setup_state: "default",
    task_kind: null,
    source: null,
    target: null,
    root: null,
    options: structuredClone(DEFAULT_OPTIONS),
    plan_again: null,
  };
}

function summary(taskId = TASK_A) {
  return {
    task_id: taskId,
    session_id: null,
    session_state: null,
    session_released: false,
    task_kind: null,
    request_id: null,
  };
}

function choice(purpose, digit, display = `${purpose}-display`) {
  return {
    purpose,
    state: "resolved",
    choice_id: CHOICE(digit),
    continuation_id: null,
    display,
    location_id: digit,
    candidates: [],
    detail: null,
  };
}

let scenarioId = 0;
async function loadScenario({
  snapshot = defaultSnapshot(), recents = EMPTY_RECENTS, initialSummary = summary(),
} = {}) {
  scenarioId += 1;
  const app = new ElementFake();
  const status = new ElementFake("Starting...");
  const theme = new ElementFake();
  const themeRefresh = new ElementFake();
  themeRefresh.addEventListener = () => {};
  const body = new ElementFake();
  const windowListeners = new Map();
  globalThis.document = {
    documentElement: new ElementFake(),
    body,
    querySelector(selector) {
      return selector === "#app" ? app : selector === "#host-status" ? status
        : selector === "#theme-refresh" ? themeRefresh : theme;
    },
  };
  globalThis.window = {
    chrome: { webview: {} },
    addEventListener(name, callback) {
      const values = windowListeners.get(name) ?? [];
      values.push(callback);
      windowListeners.set(name, values);
    },
  };
  const harness = {
    callbacks: null,
    railCallbacks: null,
    createStates: [],
    model: null,
    task: null,
    drains: [],
    calls: [],
    snapshot,
    recents: structuredClone(recents),
    probeRecentPairs() {
      return Promise.resolve({ pairs: harness.recents.pairs.map((pair) => ({
        mapping_id: pair.mapping_id, source_id: pair.source.location_id,
        target_id: pair.target.location_id, source_state: "resolved", target_state: "resolved",
      })) });
    },
    windowListeners,
    listTasks: () => Promise.resolve({ tasks: [initialSummary] }),
    readSetup(taskId = null) {
      return Promise.resolve({
        task_id: taskId,
        snapshot: taskId === null ? defaultSnapshot() : harness.snapshot,
        recents: taskId === null ? harness.recents : null,
      });
    },
    admitLocation(purpose, candidate) {
      harness.calls.push(["admit", purpose, structuredClone(candidate)]);
      return Promise.resolve(choice(purpose, purpose === "target" ? "2" : "1"));
    },
    pickFolder(purpose) {
      harness.calls.push(["pick", purpose]);
      return Promise.resolve(choice(purpose, "3"));
    },
    prepareSetup(options) {
      harness.calls.push(["prepare", structuredClone(options)]);
      return Promise.resolve(structuredClone(options));
    },
    createTask() {
      harness.calls.push(["create"]);
      return Promise.resolve({ task_id: TASK_B });
    },
    closeTask(...values) {
      harness.calls.push(["close", ...values]);
      return Promise.resolve({ disposition: "closed" });
    },
    startPlan(...values) {
      harness.calls.push(["start-plan", ...values]);
      return Promise.resolve({ task_id: values[0], request_id: "4".repeat(32), session_id: "5".repeat(32) });
    },
    startInventory(...values) {
      harness.calls.push(["start-inventory", ...values]);
      return Promise.resolve({ task_id: values[0], request_id: "6".repeat(32), session_id: "7".repeat(32) });
    },
    planAgain(...values) {
      harness.calls.push(["plan-again", ...values]);
      return Promise.resolve({ task_id: TASK_B, request_id: "8".repeat(32), session_id: "9".repeat(32) });
    },
  };
  globalThis.setupAppHarness = harness;

  const renderUrl = moduleUrl(`
    export const renderText = (element, value) => { element.textContent = value; };
    export const formatByteCount = (value) => String(value);
  `);
  const bridgeUrl = moduleUrl(`
    const harness = globalThis.setupAppHarness;
    export class BridgeTransportError extends Error {}
    export class OutcomeUnavailableError extends BridgeTransportError {}
    export class StartPlanUncertainError extends BridgeTransportError {}
    export class TaskCreateUncertainError extends BridgeTransportError {}
    export class TaskCloseUncertainError extends BridgeTransportError {}
    harness.BridgeTransportError = BridgeTransportError;
    harness.OutcomeUnavailableError = OutcomeUnavailableError;
    harness.StartPlanUncertainError = StartPlanUncertainError;
    harness.TaskCreateUncertainError = TaskCreateUncertainError;
    harness.TaskCloseUncertainError = TaskCloseUncertainError;
    export const acknowledgeShellReady = () => Promise.resolve({ acknowledged: true });
    export const admitLocation = (...args) => harness.admitLocation(...args);
    export const closeTask = (...args) => harness.closeTask(...args);
    export const createTask = (...args) => harness.createTask(...args);
    export const echoReadiness = () => Promise.resolve({ acknowledged: true });
    export const listTasks = () => harness.listTasks();
    export const getExecutionDetail = () => Promise.reject(new Error("unused"));
    export const openInventoryView = () => Promise.reject(new Error("unused inventory read"));
    export const updateInventoryView = () => Promise.reject(new Error("unused inventory read"));
    export const getInventoryWindow = () => Promise.reject(new Error("unused inventory read"));
    export const getInventoryDetail = () => Promise.reject(new Error("unused inventory read"));
    export const refreshInventory = () => Promise.reject(new Error("unused inventory action"));
    export const acknowledgeInventory = () => Promise.reject(new Error("unused inventory action"));
    export const restoreInventory = () => Promise.reject(new Error("unused inventory action"));
    export const markBridgeOperational = () => {};
    export const pickFolder = (...args) => harness.pickFolder(...args);
    export const planAgain = (...args) => harness.planAgain(...args);
    export const prepareSetup = (...args) => harness.prepareSetup(...args);
    export const probeRecentPairs = () => harness.probeRecentPairs();
    export const readSetup = (...args) => harness.readSetup(...args);
    export const startInventory = (...args) => harness.startInventory(...args);
    export const startPlan = (...args) => harness.startPlan(...args);
    export const startTaskDrain = (...args) => {
      const drain = { args, stopped: false };
      harness.drains.push(drain);
      return () => { drain.stopped = true; };
    };
    export const whenBridgeApiReady = () => Promise.resolve();
    // scenario ${scenarioId}
  `);
  const panelUrl = moduleUrl(`
    const harness = globalThis.setupAppHarness;
    export function createWorkPanel(callbacks) {
      harness.callbacks = callbacks;
      return {
        element: {},
        render(task) { harness.task = task; harness.model = task?.form ?? null; harness.settingsVisible = false; },
        renderSettings() { harness.settingsVisible = true; },
      };
    }
    // scenario ${scenarioId}
  `);
  const railUrl = moduleUrl(`
    const harness = globalThis.setupAppHarness;
    export function createTaskRail(callbacks) {
      harness.railCallbacks = callbacks;
      return {
        element: {},
        render(tasks, _selected, creating) {
          harness.createStates.push(creating);
          harness.railTasks = tasks;
          harness.dispatchedPlanningRendered = tasks.some((task) =>
            task.form?.attempt?.kind === "sync-plan" && task.form.attempt.dispatched
            && task.form.attempt.running);
        },
      };
    }
    // scenario ${scenarioId}
  `);
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
  const executionConfirmationUrl = moduleUrl(`
    export const createExecutionConfirmation = () => ({ element: {}, show() {} });
  `);
  let taskStatusSource = await readFile(
    process.argv[2].replace(/app\.js$/, "task_status.js"),
    "utf8",
  );
  const taskStatusRender = moduleUrl(await readFile(process.argv[2].replace(/app\.js$/, "render.js"), "utf8"));
  taskStatusSource = taskStatusSource.replace("./render.js", taskStatusRender);
  const taskStatusUrl = moduleUrl(taskStatusSource);
  let source = await readFile(process.argv[2], "utf8");
  source = source.replace(
    /import \{[\s\S]*?\} from "\.\/bridge\.js";/,
    `import { acknowledgeShellReady, acknowledgeInventory, admitLocation, BridgeTransportError, closeTask, createTask, echoReadiness, getExecutionDetail, getInventoryDetail, getInventoryWindow, openInventoryView, refreshInventory, restoreInventory, updateInventoryView, listTasks, markBridgeOperational, OutcomeUnavailableError, pickFolder, planAgain, prepareSetup, probeRecentPairs, readSetup, StartPlanUncertainError, startInventory, startPlan, startTaskDrain, TaskCloseUncertainError, TaskCreateUncertainError, whenBridgeApiReady } from "${bridgeUrl}";`,
  );
  source = source
    .replace("./readiness.js", readinessUrl)
    .replace("./appearance.js", appearanceUrl)
    .replace("./theme.js", themeUrl)
    .replace("./execution_confirmation.js", executionConfirmationUrl)
    .replace("./panels.js", panelUrl)
    .replace("./rail.js", railUrl)
    .replace("./render.js", renderUrl)
    .replace("./task_status.js", taskStatusUrl);
  source += "\nObject.assign(globalThis.setupAppHarness, { refreshTasks, dispatchFormAttempt, adoptTask, tasks, startPlanAgain, startPairBatch });";
  await import(moduleUrl(`${source}\n// scenario ${scenarioId}`));
  await until(() => harness.model !== null, "initial Setup read");
  return harness;
}

{
  const harness = await loadScenario();
  harness.callbacks.onEdit("source", "C:\\settings-draft");
  const retained = harness.model;
  const admission = deferred();
  harness.admitLocation = () => admission.promise;
  harness.callbacks.onValidate("source");
  harness.railCallbacks.onSettings();
  assert.equal(harness.settingsVisible, true);
  admission.resolve(choice("source", "1", "C:\\settings-draft"));
  await until(() => retained.source.location?.state === "resolved", "background admission while Settings is open");
  assert.equal(harness.settingsVisible, true, "background completion must not replace Settings");
  harness.railCallbacks.onSelect(TASK_A);
  await until(() => harness.settingsVisible === false, "return to retained task");
  assert.equal(harness.model, retained);
  assert.equal(harness.model.source.text, "C:\\settings-draft");

  const stale = deferred();
  harness.callbacks.onEdit("source", "C:\\stale-before-clear");
  harness.admitLocation = () => stale.promise;
  harness.callbacks.onValidate("source");
  const callCount = harness.calls.length;
  harness.callbacks.onEdit("source", "");
  assert.equal(harness.calls.length, callCount, "local clear does not call the bridge");
  stale.resolve(choice("source", "2", "C:\\stale-before-clear"));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(retained.source.text, "");
  assert.equal(retained.source.candidate, null);
  assert.equal(retained.source.location, null, "late admission cannot restore a cleared field");
}

{
  const harness = await loadScenario();
  harness.railCallbacks.onClose(TASK_A);
  await until(() => harness.railTasks.length === 0, "close sole selected task");
  const creation = deferred();
  harness.createTask = () => creation.promise;
  harness.railCallbacks.onCreate();
  harness.railCallbacks.onSettings();
  creation.resolve({ task_id: TASK_B });
  await until(() => harness.railTasks.some((task) => task.taskId === TASK_B), "retain unselected created task");
  assert.equal(harness.settingsVisible, true);
  harness.railCallbacks.onSelect(TASK_B);
  await until(() => harness.settingsVisible === false && harness.task?.taskId === TASK_B,
    "first task selection from a null prior selection");
}

{
  const pair = {
    mapping_id: "91", source: { location_id: "92", display: "S:\\source", last_used_at: "2026-09-11T00:00:00+00:00" },
    target: { location_id: "93", display: "T:\\target", last_used_at: "2026-09-11T00:00:00+00:00" },
    last_used_at: "2026-09-11T00:00:00+00:00",
  };
  const harness = await loadScenario({ recents: { sources: [], targets: [], pairs: [pair] } });
  await until(() => harness.model.recentPairAvailability["91"]?.source === "online" &&
    harness.model.recentPairAvailability["91"]?.target === "online", "initial online pair");
  const observation = (sourceState, targetState, targetId = "93") => ({ pairs: [{
    mapping_id: "91", source_id: "92", target_id: targetId,
    source_state: sourceState, target_state: targetState,
  }] });
  const old = deferred();
  const fresh = deferred();
  let probes = 0;
  harness.probeRecentPairs = () => (++probes === 1 ? old : fresh).promise;
  harness.callbacks.onRefreshRecents();
  assert.deepEqual(harness.model.recentPairAvailability["91"], { source: "checking", target: "checking" });
  const admissions = () => harness.calls.filter((call) => call[0] === "admit").length;
  const before = admissions();
  await harness.callbacks.onRecentPair(pair);
  assert.equal(admissions(), before, "checking rows cannot acquire choices");
  harness.callbacks.onRefreshRecents();
  harness.callbacks.onRefreshRecents();
  assert.equal(probes, 1, "refreshes coalesce behind the pending request");
  old.resolve(observation("resolved", "resolved"));
  await until(() => probes === 2, "coalesced refresh");
  assert.deepEqual(harness.model.recentPairAvailability["91"], { source: "checking", target: "checking" }, "superseded online reply ignored");
  fresh.resolve(observation("resolved", "offline"));
  await until(() => harness.model.recentPairAvailability["91"]?.source === "online" &&
    harness.model.recentPairAvailability["91"]?.target === "offline", "offline target");
  await harness.callbacks.onRecentPair(pair);
  assert.equal(admissions(), before, "offline rows cannot acquire choices");
  harness.probeRecentPairs = () => Promise.resolve(observation("resolved", "resolved", "94"));
  harness.callbacks.onRefreshRecents();
  await until(() => harness.model.recentPairAvailability["91"]?.source === "unknown" &&
    harness.model.recentPairAvailability["91"]?.target === "unknown", "mismatched pair identity ignored");
  harness.probeRecentPairs = () => Promise.resolve(observation("ambiguous", "resolved"));
  harness.callbacks.onRefreshRecents();
  await until(() => harness.model.recentPairAvailability["91"]?.source === "unavailable" &&
    harness.model.recentPairAvailability["91"]?.target === "online", "ambiguous is not offline");
  harness.probeRecentPairs = () => Promise.reject(new Error("probe failed"));
  harness.callbacks.onRefreshRecents();
  await until(() => harness.model.recentPairAvailability["91"]?.source === "unknown" &&
    harness.model.recentPairAvailability["91"]?.target === "unknown", "failed probe stays unknown");
  assert.equal(admissions(), before, "status probing never admits a UI choice");
}

{
  const harness = await loadScenario();
  let createRetries = 0;
  harness.createTask = (onDelayed) => {
    harness.calls.push(["create"]);
    return delayedOriginal(onDelayed, () => {
      createRetries += 1;
      harness.listTasks = () => Promise.resolve({ tasks: [summary(TASK_A), summary(TASK_B)] });
      return Promise.resolve({ task_id: TASK_B });
    });
  };
  harness.railCallbacks.onCreate();
  await until(
    () => globalThis.document.querySelector("#host-status").textContent.includes("setup-check-sentinel"),
    "new-task uncertainty guidance",
  );
  assert.equal(harness.createStates.at(-1).recovery.canCheck, true, "New task retains one read-only Check");
  assert.equal(harness.createStates.at(-1).running, true);
  assert.match(
    globalThis.document.querySelector("#host-status").textContent,
    /setup-check-sentinel/,
    "the same-document retry retains its pending create guidance",
  );
  harness.railCallbacks.onCreate();
  harness.railCallbacks.onCreate();
  await turns();
  await until(() => createRetries >= 1, "new-task Check reaches the original owner");
  await until(() => harness.task?.taskId === TASK_B, "original create owner adopts the result");
  assert.equal(harness.calls.filter((call) => call[0] === "create").length, 1);
}

{
  const harness = await loadScenario();
  harness.createTask = (onDelayed) => {
    harness.calls.push(["create"]);
    onDelayed(fakeRecoveryHandle({ state: "fixed-unknown", message: "create-fixed-sentinel" }));
    return Promise.reject(new harness.TaskCreateUncertainError());
  };
  harness.railCallbacks.onCreate();
  await until(() => globalThis.document.querySelector("#host-status").textContent.includes(
    "create-fixed-sentinel"), "fixed-unknown create guidance");
  assert.equal(harness.createStates.at(-1).recovery.state, "fixed-unknown",
    "a fixed unknown create keeps New task fenced without an observation retry");
  harness.railCallbacks.onCreate();
  await turns();
  assert.equal(harness.calls.filter((call) => call[0] === "create").length, 1,
    "repeated New task gestures cannot create another task after a fixed unknown");
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  callbacks.onEdit("source", "C:\\first-source");
  callbacks.onEdit("target", "D:\\first-target");
  callbacks.onAddPair();
  const firstOriginResult = harness.model.batch[0];
  firstOriginResult.state = "created";
  harness.railCallbacks.onCreate();
  await until(() => harness.task?.taskId === TASK_B && harness.model !== null, "clear-results second origin");
  callbacks.onEdit("source", "E:\\second-source");
  callbacks.onEdit("target", "F:\\second-target");
  callbacks.onAddPair();
  harness.model.batch[0].state = "refused";
  callbacks.onClearBatchResults();
  assert.deepEqual(harness.model.batch, [], "Clear results removes this origin's terminal rows");
  harness.railCallbacks.onSelect(TASK_A);
  assert.equal(harness.model.batch[0], firstOriginResult, "Clear results retains terminal rows from other origins");
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  callbacks.onEdit("source", "C:\\closing-source");
  callbacks.onEdit("target", "D:\\closing-target");
  callbacks.onAddPair();
  const closing = deferred();
  harness.closeTask = (...values) => {
    harness.calls.push(["close", ...values]);
    return closing.promise;
  };
  harness.railCallbacks.onClose(TASK_A);
  await until(() => harness.model.closePending, "origin close pending");
  callbacks.onStartBatch();
  await turns();
  assert.equal(harness.calls.some((call) => call[0] === "prepare" || call[0] === "admit"), false);
  assert.equal(harness.model.batch[0].state, "queued", "a pending close cannot launch queued batch work");
  closing.resolve({ task_id: TASK_A, session_id: null, disposition: "closed" });
  await until(() => !harness.railTasks.some((task) => task.taskId === TASK_A), "origin close completion");
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  callbacks.onEdit("source", "C:\\closing-source");
  callbacks.onEdit("target", "D:\\closing-target");
  callbacks.onAddPair();
  harness.closeTask = (...values) => {
    harness.calls.push(["close", ...values.slice(0, 2)]);
    values.at(-1)(fakeRecoveryHandle({ state: "fixed-unknown", message: "close-fixed-sentinel" }));
    return Promise.reject(new harness.TaskCloseUncertainError());
  };
  harness.railCallbacks.onClose(TASK_A);
  await until(() => harness.model.closePending && harness.railTasks.find(
    (task) => task.taskId === TASK_A)?.closeRecovery?.message === "close-fixed-sentinel",
  "fixed-unknown Close keeps its form fence");
  callbacks.onStartPlan();
  callbacks.onStartInventory();
  callbacks.onStartBatch();
  callbacks.onAddPair();
  harness.railCallbacks.onClose(TASK_A);
  await turns();
  assert.equal(harness.calls.filter((call) => call[0] === "close").length, 1,
    "fixed-unknown Close offers no replay");
  assert.equal(harness.calls.some((call) => ["prepare", "admit", "start-plan", "start-inventory"].includes(call[0])),
    false, "unresolved Close fences every start and batch replacement");
  assert.equal(harness.model.batch.length, 1);
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  callbacks.onEdit("source", "C:\\capacity-source");
  callbacks.onEdit("target", "D:\\capacity-target");
  for (let index = 0; index < 48; index += 1) callbacks.onAddPair();
  assert.equal(harness.model.batchCount, 48);
  harness.railCallbacks.onCreate();
  await until(() => harness.task?.taskId === TASK_B && harness.model !== null, "capacity second origin");
  callbacks.onEdit("source", "E:\\other-source");
  callbacks.onEdit("target", "F:\\other-target");
  callbacks.onAddPair();
  assert.equal(harness.model.batchCount, 48, "the 48-pair cap is page-wide across origins");
  assert.deepEqual(harness.model.batch, []);
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  callbacks.onEdit("source", "C:\\origin-source");
  callbacks.onEdit("target", "D:\\origin-target");
  callbacks.onAddPair();
  const originRow = harness.model.batch[0];
  harness.railCallbacks.onCreate();
  await until(() => harness.task?.taskId === TASK_B && harness.model !== null, "fresh second task");
  assert.deepEqual(harness.model.batch, [], "a fresh task does not inherit another Setup's batch");
  callbacks.onRemoveBatchRow(originRow);
  harness.railCallbacks.onSelect(TASK_A);
  assert.equal(harness.model.batch[0], originRow, "cross-origin removal is refused and navigation restores the origin batch");
  callbacks.onRemoveBatchRow(originRow);
  assert.deepEqual(harness.model.batch, [], "queued origin row is removable");
  callbacks.onAddPair();
  harness.railCallbacks.onClose(TASK_A);
  await until(() => harness.calls.some((call) => call[0] === "close"), "origin close");
  await until(() => harness.task?.taskId === TASK_B && harness.model !== null, "closed origin selection");
  assert.deepEqual(harness.model.batch, [], "confirmed origin close discards its queued rows");
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  callbacks.onEdit("source", "C:\\sync-source");
  callbacks.onEdit("target", "D:\\sync-target");
  callbacks.onAddPair();
  assert.equal(harness.model.batch.length, 1, "sync Setup owns its queued row");
  callbacks.onMode("inventory");
  assert.deepEqual(harness.model.batch, [], "Inventory hides the sync batch rows");
  assert.equal(harness.model.batchCount, 0, "Inventory has no batch count");
  assert.equal(harness.model.batchPending, false, "Inventory is not batch-pending");
  callbacks.onEdit("source", "I:\\inventory");
  callbacks.onStartInventory();
  await until(() => harness.calls.some((call) => call[0] === "start-inventory"), "inventory start with queued sync row");
  callbacks.onMode("sync-plan");
  assert.equal(harness.model.batch.length, 1, "returning to Sync restores the retained row");
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  callbacks.onEdit("source", "C:\\source");
  callbacks.onEdit("target", "D:\\target");
  const pendingAdmission = deferred();
  harness.admitLocation = (purpose, candidate) => {
    harness.calls.push(["admit", purpose, structuredClone(candidate)]);
    return pendingAdmission.promise;
  };
  callbacks.onStartPlan();
  await until(() => harness.calls.some((call) => call[0] === "admit"), "delayed Start admission");
  const firstModel = harness.model;
  firstModel.options.deletion_policy = "additive";
  firstModel.revision += 1;
  pendingAdmission.resolve(choice("source", "1"));
  await until(() => firstModel.attempt === null, "stale form attempt abandoned");
  assert.equal(harness.calls.some((call) => call[0] === "prepare"), false);
  assert.equal(harness.calls.some((call) => call[0] === "start-plan"), false);

  callbacks.onOption("deletion_policy", "trash");
  harness.admitLocation = (purpose, candidate) => {
    harness.calls.push(["admit", purpose, structuredClone(candidate)]);
    return Promise.resolve(choice(purpose, purpose === "target" ? "2" : "1"));
  };
  const pendingPlan = deferred();
  harness.startPlan = (...values) => {
    values.at(-1)(fakeRecoveryHandle({ state: "pending", canCheck: true,
      check: async () => assert.fail("late delivery needs no Check") }));
    return pendingPlan.promise;
  };
  callbacks.onStartPlan();
  await until(() => firstModel.attempt?.dispatched === true, "planning dispatched");
  assert.equal(harness.dispatchedPlanningRendered, true,
    "planning state must repaint before the start response arrives");
  pendingPlan.resolve({ task_id: TASK_A, request_id: "4".repeat(32), session_id: "5".repeat(32) });
  await until(() => firstModel.attempt === null, "planning response settled");
  let planRetries = 0;
  harness.startPlan = (...values) => {
    harness.calls.push(["start-plan", ...values]);
    return delayedOriginal(values.at(-1), () => {
      planRetries += 1;
      return Promise.resolve({ task_id: TASK_A, request_id: "4".repeat(32), session_id: "5".repeat(32) });
    });
  };
  callbacks.onStartPlan();
  await until(() => firstModel.attempt?.recovery?.canCheck === true, "plan uncertainty retained");
  callbacks.onStartPlan();
  await until(() => planRetries === 1 && firstModel.attempt === null, "same plan retry closure");
  assert.equal(harness.calls.filter((call) => call[0] === "start-plan").length, 1);

  callbacks.onMode("inventory");
  assert.equal(firstModel.source.location, null, "mode change drops source-purpose authority");
  harness.pickFolder = (purpose) => {
    harness.calls.push(["pick", purpose]);
    return Promise.resolve(choice(purpose, "3", "I:\\inventory"));
  };
  callbacks.onPick("source");
  await until(() => firstModel.source.location?.purpose === "inventory", "inventory picker result");
  assert.deepEqual(harness.calls.findLast((call) => call[0] === "pick"), ["pick", "inventory"]);
  assert.equal(harness.model, firstModel, "editable Setup identity survives task refresh");
  assert.equal(firstModel.mode, "inventory");
  let inventoryRetries = 0;
  harness.startInventory = (...values) => {
    harness.calls.push(["start-inventory", ...values]);
    return delayedOriginal(values.at(-1), () => {
      inventoryRetries += 1;
      return Promise.resolve({ task_id: TASK_A, request_id: "6".repeat(32), session_id: "7".repeat(32) });
    });
  };
  callbacks.onStartInventory();
  await until(() => harness.model.attempt?.recovery?.canCheck === true, "inventory uncertainty retained");
  callbacks.onStartInventory();
  await until(() => inventoryRetries === 1 && firstModel.attempt === null, "same inventory retry closure");
  assert.equal(harness.calls.filter((call) => call[0] === "start-inventory").length, 1);

  callbacks.onMode("sync-plan");
  callbacks.onEdit("source", "C:\\clone");
  harness.admitLocation = (purpose, candidate) => {
    harness.calls.push(["admit", purpose, structuredClone(candidate)]);
    if (candidate.selected_mount === null) {
      return Promise.resolve({
        purpose, state: "ambiguous", choice_id: null, continuation_id: null,
        display: "C:\\clone", location_id: "11", candidates: ["C:\\", "E:\\"], detail: "Choose a mount.",
      });
    }
    return Promise.resolve(choice(purpose, "4", candidate.selected_mount));
  };
  callbacks.onValidate("source");
  await until(() => firstModel.source.location?.state === "ambiguous", "typed ambiguity");
  callbacks.onMount("source", 1);
  await until(() => firstModel.source.location?.state === "resolved", "typed ambiguity mount");
  assert.deepEqual(harness.calls.findLast((call) => call[0] === "admit").slice(1), [
    "source", { kind: "literal_path", path: "C:\\clone", selected_mount: "E:\\" },
  ]);

  const continuationId = CHOICE("c");
  harness.pickFolder = (purpose) => Promise.resolve({
    purpose, state: "ambiguous", choice_id: null, continuation_id: continuationId,
    display: "picker clone", location_id: "12", candidates: ["M:\\", "N:\\"], detail: "Choose a mount.",
  });
  harness.admitLocation = (purpose, candidate) => {
    harness.calls.push(["admit", purpose, structuredClone(candidate)]);
    return Promise.resolve(choice(purpose, "5", "N:\\"));
  };
  callbacks.onPick("source");
  await until(() => firstModel.source.continuationId === continuationId, "picker continuation");
  callbacks.onMount("source", 1);
  await until(() => firstModel.source.location?.state === "resolved", "picker continuation choice");
  assert.deepEqual(harness.calls.findLast((call) => call[0] === "admit").slice(1), [
    "source", { continuation_id: continuationId, mount_index: 1 },
  ]);

  const pair = {
    mapping_id: "21",
    source: { location_id: "22", display: "S:\\recent", last_used_at: "2026-09-11T00:00:00+00:00" },
    target: { location_id: "23", display: "T:\\recent", last_used_at: "2026-09-11T00:00:00+00:00" },
    last_used_at: "2026-09-11T00:00:00+00:00",
  };
  harness.recents.pairs.push(pair);
  callbacks.onRefreshRecents();
  await until(() => harness.model.recentPairAvailability["21"]?.source === "online" &&
    harness.model.recentPairAvailability["21"]?.target === "online", "recent pair probe");
  callbacks.onRecentPair(pair);
  await until(() => firstModel.target.location?.state === "resolved", "recent pair admission");
  const recentAdmissions = harness.calls.filter((call) => call[0] === "admit").slice(-2);
  assert.deepEqual(recentAdmissions.map((call) => call.slice(1)), [
    ["source", { kind: "remembered_location", location_id: "22", selected_mount: null }],
    ["target", { kind: "remembered_location", location_id: "23", selected_mount: null }],
  ]);
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  callbacks.onEdit("source", "C:\\source");
  await callbacks.onValidate("source");
  await until(() => harness.model.source.location?.state === "resolved", "picker-cancel baseline");
  const baseline = {
    location: harness.model.source.location,
    candidate: structuredClone(harness.model.source.candidate),
    text: harness.model.source.text,
    revision: harness.model.source.revision,
    admissionRevision: harness.model.source.admissionRevision,
  };
  const cancel = deferred();
  harness.pickFolder = () => cancel.promise;
  callbacks.onPick("source");
  await until(() => harness.model.source.location === null, "picker pending state");
  cancel.resolve(null);
  await until(() => harness.model.source.location === baseline.location, "picker cancel restores authority");
  assert.deepEqual(harness.model.source.candidate, baseline.candidate);
  assert.equal(harness.model.source.text, baseline.text);
  assert.ok(harness.model.source.revision > baseline.revision);
  assert.ok(harness.model.source.admissionRevision > baseline.admissionRevision);

  const failed = deferred();
  harness.pickFolder = () => failed.promise;
  callbacks.onPick("source");
  failed.reject(new Error("picker failed"));
  await until(() => harness.model.source.location === baseline.location, "picker error restores authority");

  const staleCancel = deferred();
  harness.pickFolder = () => staleCancel.promise;
  callbacks.onPick("source");
  callbacks.onEdit("source", "C:\\replacement");
  staleCancel.resolve(null);
  await turns();
  assert.equal(harness.model.source.location, null, "stale picker cancel cannot restore old authority");
  assert.deepEqual(harness.model.source.candidate, {
    kind: "literal_path", path: "C:\\replacement", selected_mount: null,
  });
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  callbacks.onEdit("source", "C:\\source");
  callbacks.onEdit("target", "D:\\target");
  harness.startPlan = (...values) => {
    harness.calls.push(["start-plan", ...values.slice(0, 4)]);
    values.at(-1)(fakeRecoveryHandle({ state: "fixed-unknown", message: "plan-fixed-sentinel" }));
    return Promise.reject(new harness.StartPlanUncertainError());
  };
  callbacks.onStartPlan();
  await until(() => harness.model.attempt?.recovery?.state === "fixed-unknown", "fixed-unknown plan retained");
  assert.equal(harness.model.attempt.recovery.message, "plan-fixed-sentinel");
  const form = harness.model;
  callbacks.onStartPlan();
  callbacks.onStartInventory();
  callbacks.onMode("inventory");
  callbacks.onAddPair();
  await turns();
  assert.equal(harness.model, form, "the same form retains the unknown intent");
  assert.equal(form.mode, "sync-plan", "mode replacement stays fenced");
  assert.equal(form.batch.length, 0, "unknown plan cannot seed a batch");
  assert.equal(harness.calls.filter((call) => call[0] === "start-plan").length, 1,
    "unknown plan cannot submit another effect");
  assert.equal(harness.calls.some((call) => call[0] === "start-inventory"), false);
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  callbacks.onEdit("source", "C:\\original");
  callbacks.onEdit("target", "D:\\target");
  const original = deferred();
  harness.admitLocation = (purpose, candidate) => {
    harness.calls.push(["admit", purpose, structuredClone(candidate)]);
    if (candidate.path === "C:\\original") return original.promise;
    return Promise.resolve(choice(purpose, purpose === "source" ? "4" : "2", candidate.path));
  };
  callbacks.onValidate("source");
  await until(() => harness.model.source.pending, "original admission pending");
  assert.equal(harness.task.closeBlockReason, null, "folder admission alone does not fence Close");
  callbacks.onEdit("source", "C:\\replacement");
  callbacks.onValidate("source");
  await until(() => harness.model.source.location?.choice_id === CHOICE("4"), "fresh choice admitted");
  original.resolve(choice("source", "1", "C:\\original"));
  await turns();
  assert.equal(harness.model.source.text, "C:\\replacement");
  assert.equal(harness.model.source.location.choice_id, CHOICE("4"), "late old admission cannot restore old authority");
  callbacks.onStartPlan();
  await until(() => harness.calls.some((call) => call[0] === "start-plan"), "latest choice feeds Start");
  assert.equal(harness.calls.find((call) => call[0] === "start-plan")[2], CHOICE("4"));
}

{
  const inventorySnapshot = {
    setup_state: "frozen", task_kind: "inventory", source: null, target: null,
    root: { display: "R:\\library", location_id: "31" }, options: null, plan_again: null,
  };
  const harness = await loadScenario({ snapshot: inventorySnapshot });
  assert.equal(harness.model.mode, "inventory");
  assert.equal(harness.model.source.text, "R:\\library");
  assert.equal(harness.model.source.candidate.location_id, "31");
  assert.equal(harness.model.target.text, "");
}

{
  const planSnapshot = {
    setup_state: "frozen", task_kind: "sync-plan",
    source: { display: "C:\\source", location_id: "41" },
    target: { display: "D:\\target", location_id: "42" }, root: null,
    options: structuredClone(DEFAULT_OPTIONS),
    plan_again: { source_state: "resolved", source_candidates: [], target_state: "resolved", target_candidates: [] },
  };
  const harness = await loadScenario({ snapshot: planSnapshot });
  let retries = 0;
  harness.planAgain = (...values) => {
    harness.calls.push(["plan-again", ...values]);
    return delayedOriginal(values.at(-1), () => {
      retries += 1;
      return Promise.resolve({ task_id: TASK_B, request_id: "8".repeat(32), session_id: "9".repeat(32) });
    });
  };
  harness.callbacks.onPlanAgain();
  await until(() => harness.model.attempt?.recovery?.canCheck === true, "Plan-again uncertainty retained");
  harness.callbacks.onPlanAgain();
  await until(() => retries === 1, "same Plan-again retry closure");
  assert.equal(harness.calls.filter((call) => call[0] === "plan-again").length, 1);
  assert.equal(harness.model.artifactReady, true);
}

for (const sessionState of ["active", "failed"]) {
  const planSnapshot = {
    setup_state: "frozen", task_kind: "sync-plan",
    source: { display: "C:\\source", location_id: "51" },
    target: { display: "D:\\target", location_id: "52" }, root: null,
    options: structuredClone(DEFAULT_OPTIONS), plan_again: null,
  };
  const harness = await loadScenario({
    snapshot: planSnapshot,
    initialSummary: {
      ...summary(),
      session_id: "5".repeat(32),
      session_state: sessionState,
      task_kind: "sync-plan",
      request_id: "6".repeat(32),
    },
  });
  assert.equal(harness.model.sessionState, sessionState);
  assert.equal(harness.model.artifactReady, false, `${sessionState} start snapshot has no plan artifact`);
  assert.equal(harness.model.canPlanAgain, false);
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  harness.pickFolder = (purpose) => Promise.resolve(choice(purpose, purpose === "source" ? "6" : "7"));
  callbacks.onPick("source");
  await until(() => harness.model.source.location?.state === "resolved", "resolved source picker");
  callbacks.onPick("target");
  await until(() => harness.model.target.location?.state === "resolved", "resolved picker pair");
  assert.equal(harness.model.source.candidate, null);
  callbacks.onAddPair();
  const prepare = deferred();
  harness.prepareSetup = (options) => {
    harness.calls.push(["prepare", structuredClone(options)]);
    return prepare.promise;
  };
  let createRetries = 0;
  harness.createTask = (onDelayed) => {
    harness.calls.push(["create"]);
    return delayedOriginal(onDelayed, () => {
      createRetries += 1;
      harness.listTasks = () => Promise.resolve({ tasks: [summary(TASK_A), summary(TASK_B)] });
      return Promise.resolve({ task_id: TASK_B });
    });
  };
  let startRetries = 0;
  harness.startPlan = (...values) => {
    harness.calls.push(["start-plan", ...values]);
    return delayedOriginal(values.at(-1), () => {
      startRetries += 1;
      return Promise.resolve({ task_id: TASK_B, request_id: "4".repeat(32), session_id: "5".repeat(32) });
    });
  };
  callbacks.onStartBatch();
  callbacks.onStartBatch();
  callbacks.onAddPair();
  assert.equal(harness.model.batch.length, 1, "running batch rejects add and reentrant Start");
  prepare.resolve(structuredClone(DEFAULT_OPTIONS));
  await until(() => harness.model.batch[0].stage === "creating"
    && harness.model.batch[0].recovery?.canCheck === true, "create uncertainty retained");
  assert.equal(harness.model.batch[0].stage, "creating");
  assert.ok(harness.railTasks.find((task) => task.taskId === TASK_A).closeBlockReason);
  harness.railCallbacks.onClose(TASK_A);
  await turns();
  assert.equal(harness.calls.some((call) => call[0] === "close"), false, "uncertain origin cannot be closed");
  callbacks.onStartBatch();
  await until(() => harness.model.batch[0].stage === "starting" &&
    harness.model.batch[0].state === "submitting" && harness.model.batchRunning &&
    harness.railTasks.some((task) => task.taskId === TASK_B), "start uncertainty and child retained");
  assert.equal(createRetries, 1);
  assert.equal(harness.calls.filter((call) => call[0] === "create").length, 1);
  harness.railCallbacks.onSelect(TASK_B);
  assert.match(harness.model.batchMessage, /Task 1/, "the child points back to its batch origin");
  const startsBeforeBlockedChild = harness.calls.filter((call) => call[0] === "start-plan").length;
  callbacks.onStartPlan();
  callbacks.onMode("inventory");
  callbacks.onEdit("source", "I:\\blocked-inventory");
  const inventoryStartsBeforeBlockedChild = harness.calls.filter((call) => call[0] === "start-inventory").length;
  callbacks.onStartInventory();
  await turns();
  assert.deepEqual(harness.model.batch, [], "Inventory does not expose the uncertain sync row");
  assert.equal(harness.model.batchPending, true, "uncertain child ownership still guards Inventory");
  assert.match(harness.model.batchMessage, /Task 1/, "Inventory directs the child back to its batch origin");
  assert.equal(harness.calls.filter((call) => call[0] === "start-inventory").length,
    inventoryStartsBeforeBlockedChild, "uncertain batch child cannot start Inventory");
  harness.railCallbacks.onClose(TASK_B);
  await turns();
  assert.equal(harness.calls.filter((call) => call[0] === "start-plan").length, startsBeforeBlockedChild,
    "the uncertain batch child cannot start a separate plan");
  assert.equal(harness.calls.some((call) => call[0] === "close"), false,
    "the uncertain batch child cannot close before exact retry settles");
  harness.railCallbacks.onSelect(TASK_A);
  callbacks.onStartBatch();
  await until(() => startRetries === 1 && harness.model.batch[0].state === "created", "batch start retry");
  assert.equal(harness.calls.filter((call) => call[0] === "start-plan").length, 1);
  assert.equal(harness.calls.filter((call) => call[0] === "admit").length, 0, "resolved picker rows need no candidate");
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  harness.pickFolder = (purpose) => Promise.resolve(choice(purpose, purpose === "source" ? "6" : "7"));
  callbacks.onPick("source");
  await until(() => harness.model.source.location?.state === "resolved", "form-owner source");
  callbacks.onPick("target");
  await until(() => harness.model.target.location?.state === "resolved", "form-owner locations");
  callbacks.onAddPair();
  const formPrepare = deferred();
  let prepareCalls = 0;
  harness.prepareSetup = (options) => {
    harness.calls.push(["prepare", structuredClone(options)]);
    prepareCalls += 1;
    return prepareCalls === 1 ? formPrepare.promise : Promise.resolve(structuredClone(options));
  };
  callbacks.onStartPlan();
  await turns();
  assert.equal(prepareCalls, 0, "a pending origin batch blocks a separate form start");
  assert.equal(harness.model.batchPending, true);
  assert.equal(harness.model.batchMessage, null, "ordinary origin batch state needs no generic instruction");
  callbacks.onRemoveBatchRow(harness.model.batch[0]);
  callbacks.onStartPlan();
  await until(() => prepareCalls === 1, "form starts after queued batch removal");
  formPrepare.resolve(structuredClone(DEFAULT_OPTIONS));
  await until(() => harness.model.attempt === null, "form owner released");
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  harness.pickFolder = (purpose) => Promise.resolve(choice(purpose, purpose === "source" ? "8" : "9"));
  callbacks.onPick("source");
  await until(() => harness.model.source.location?.state === "resolved", "batch-owner source");
  callbacks.onPick("target");
  await until(() => harness.model.target.location?.state === "resolved", "batch-owner locations");
  callbacks.onAddPair();
  const batchPrepare = deferred();
  harness.prepareSetup = (options) => {
    harness.calls.push(["prepare", structuredClone(options)]);
    return batchPrepare.promise;
  };
  callbacks.onStartBatch();
  await until(() => harness.model.batchRunning, "active batch owner");
  callbacks.onStartPlan();
  await turns();
  assert.equal(harness.calls.filter((call) => call[0] === "start-plan").length, 0,
    "active batch blocks form submission");
  harness.model.options.deletion_policy = "additive";
  batchPrepare.resolve(structuredClone(DEFAULT_OPTIONS));
  await until(() => !harness.model.batchRunning, "batch owner released");
  assert.equal(harness.model.batch[0].options.deletion_policy, "trash",
    "the row retains the exact options frozen when it was added");
  callbacks.onStartPlan();
  await until(() => harness.calls.some((call) => call[0] === "start-plan" && call[1] === TASK_A),
    "form start resumes after batch owner");
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  harness.pickFolder = (purpose) => Promise.resolve(choice(purpose, purpose === "source" ? "8" : "9"));
  callbacks.onPick("source");
  await until(() => harness.model.source.location?.state === "resolved", "replacement source picker");
  callbacks.onPick("target");
  await until(() => harness.model.target.location?.state === "resolved", "replacement pair");
  callbacks.onAddPair();
  callbacks.onAddPair();
  const firstCreate = deferred();
  harness.createTask = (onDelayed) => {
    harness.calls.push(["create"]);
    return firstCreate.promise;
  };
  callbacks.onStartBatch();
  await until(() => harness.calls.filter((call) => call[0] === "create").length === 1, "first serial create");
  assert.equal(harness.calls.some((call) => call[0] === "start-plan"), false);
  callbacks.onRemoveBatchRow(harness.model.batch[1]);
  assert.equal(harness.model.batch.length, 1, "a later queued row is removable during the serial run");
  firstCreate.resolve({ task_id: TASK_B });
  await until(() => harness.model.batch.every((row) => row.state === "created"), "retained row completes after create");
  assert.equal(harness.calls.filter((call) => call[0] === "start-plan").length, 1);
  assert.equal(harness.calls.filter((call) => call[0] === "create").length, 1);
}

{
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  harness.pickFolder = (purpose) => Promise.resolve(choice(purpose, purpose === "source" ? "4" : "5"));
  callbacks.onPick("source");
  await until(() => harness.model.source.location?.state === "resolved", "snapshot source");
  callbacks.onPick("target");
  await until(() => harness.model.target.location?.state === "resolved", "snapshot pair");

  harness.model.options.filters.push("remove-while-preparing/**");
  callbacks.onAddPair();
  harness.model.options.filters[0] = "reject/**";
  callbacks.onAddPair();
  harness.model.options.filters[0] = "first/**";
  callbacks.onAddPair();
  harness.model.options.filters[0] = "second/**";
  harness.model.options.deletion_policy = "additive";
  harness.model.options.verify_after_execute = true;
  callbacks.onAddPair();
  harness.model.options.filters[0] = "draft-after-add/**";

  assert.deepEqual(harness.model.batch.map((row) => [
    row.options.filters[0], row.options.deletion_policy, row.options.verify_after_execute,
  ]), [
    ["remove-while-preparing/**", "trash", false],
    ["reject/**", "trash", false],
    ["first/**", "trash", false],
    ["second/**", "additive", true],
  ], "each Add pair clones the then-current filters and switches");

  const firstPrepare = deferred();
  harness.prepareSetup = (options) => {
    harness.calls.push(["prepare", structuredClone(options)]);
    if (options.filters[0] === "remove-while-preparing/**") return firstPrepare.promise;
    if (options.filters[0] === "reject/**") return Promise.reject(new harness.BridgeTransportError());
    return Promise.resolve({ ...structuredClone(options), filters: [...options.filters, "canonical/**"] });
  };
  let createIndex = 0;
  harness.createTask = (onDelayed) => {
    harness.calls.push(["create"]);
    createIndex += 1;
    return Promise.resolve({ task_id: createIndex === 1 ? TASK_B : TASK_C });
  };
  let exactRetries = 0;
  harness.startPlan = (...values) => {
    harness.calls.push(["start-plan", ...structuredClone(values.slice(0, 4))]);
    if (values[0] !== TASK_C) return Promise.resolve({ task_id: values[0], request_id: "4".repeat(32), session_id: "5".repeat(32) });
    return delayedOriginal(values.at(-1), () => {
      exactRetries += 1;
      return Promise.resolve({ task_id: TASK_C, request_id: "6".repeat(32), session_id: "7".repeat(32) });
    });
  };

  callbacks.onStartBatch();
  await until(() => harness.calls.some((call) => call[0] === "prepare"), "first row preparation");
  callbacks.onRemoveBatchRow(harness.model.batch[0]);
  assert.equal(harness.model.batch.length, 3, "the queued row being prepared remains removable");
  harness.model.options.filters[0] = "draft-while-preparing/**";
  firstPrepare.resolve({ ...structuredClone(harness.calls.find((call) => call[0] === "prepare")[1]), filters: ["remove-while-preparing/**", "canonical/**"] });
  await until(() => harness.model.batch.at(-1).recovery?.canCheck === true, "pair-owned batch waits for original outcome");

  assert.deepEqual(harness.calls.filter((call) => call[0] === "prepare").map((call) => call[1].filters),
    [["remove-while-preparing/**"], ["reject/**"], ["first/**"], ["second/**"]],
    "each retained queued row is prepared from its own Add-pair snapshot");
  const submitted = harness.calls.filter((call) => call[0] === "start-plan");
  assert.deepEqual(submitted.map((call) => [call[4].filters, call[4].deletion_policy, call[4].verify_after_execute]), [
    [["first/**", "canonical/**"], "trash", false],
    [["second/**", "canonical/**"], "additive", true],
  ], "submission uses each row's canonical prepared options");
  assert.equal(harness.model.batch.find((row) => row.options.filters[0] === "reject/**").state, "refused",
    "one preparation refusal does not stop later serial settlement");
  const preparesBeforeRetry = harness.calls.filter((call) => call[0] === "prepare").length;
  callbacks.onStartBatch();
  await until(() => exactRetries === 1, "uncertain row exact retry");
  assert.equal(harness.calls.filter((call) => call[0] === "prepare").length, preparesBeforeRetry,
    "an uncertain request retries without canonicalizing its options again");
}

// Pending folder admission is local, removable work, not a reason to retain a
// batch effect fence. Neither deliberate removal nor origin Close can permit a
// late folder reply to continue into task creation.
for (const action of ["remove", "close"]) {
  const harness = await loadScenario();
  const callbacks = harness.callbacks;
  callbacks.onEdit("source", "C:\\pending-batch-source");
  callbacks.onEdit("target", "D:\\pending-batch-target");
  callbacks.onAddPair();
  const form = harness.model;
  const row = form.batch[0];
  const admission = deferred();
  harness.admitLocation = (purpose, candidate, onDelayed) => {
    harness.calls.push(["admit", purpose, structuredClone(candidate)]);
    onDelayed({ state: "pending", check: null });
    return admission.promise;
  };
  callbacks.onStartBatch();
  await until(() => typeof row.abandonAdmission === "function", "batch folder admission pending");
  assert.equal(harness.calls.some((call) => call[0] === "create"), false);
  if (action === "remove") {
    callbacks.onRemoveBatchRow(row);
    await until(() => !form.batchRunning && form.batch.length === 0, "explicit row removal releases coordinator");
  } else {
    harness.closeTask = (...values) => {
      harness.calls.push(["close", ...values.slice(0, 2)]);
      harness.listTasks = () => Promise.resolve({ tasks: [] });
      return Promise.resolve({ task_id: TASK_A, session_id: null, disposition: "closed" });
    };
    harness.railCallbacks.onClose(TASK_A);
    await until(() => !harness.railTasks.some((task) => task.taskId === TASK_A), "origin Close during folder admission");
  }
  admission.resolve(choice("source", "1"));
  await turns();
  assert.equal(harness.calls.some((call) => ["create", "start-plan"].includes(call[0])), false,
    "the late folder reply cannot continue a discarded batch row");
}

// An unrelated option edit can make the picker result stale, but cannot keep
// its row pending after the native picker itself has settled.
{
  const harness = await loadScenario();
  const picker = deferred();
  harness.pickFolder = () => picker.promise;
  harness.callbacks.onPick("source");
  await until(() => harness.model.source.pending, "picker holds its row");
  harness.callbacks.onOption("deletion_policy", "additive");
  picker.resolve(choice("source", "3"));
  await until(() => !harness.model.source.pending, "picker releases row after unrelated option edit");
  assert.equal(harness.model.source.location, null, "the stale result remains unadopted");
  assert.equal(harness.model.options.deletion_policy, "additive");
}

// An admitted start is authoritative even when the subsequent task-list read
// fails or a read launched before admission finishes afterward.
const lifecycleScenario = process.argv[3] ?? "all";
for (const kind of ["inventory", "sync-plan"]) {
  for (const observation of ["failed", "stale"]) {
    if (lifecycleScenario !== "all" && lifecycleScenario !== `${kind}-${observation}`) continue;
    const harness = await loadScenario();
    const task = harness.task;
    const form = task.form;
    const attempt = { kind, running: true, dispatched: false };
    form.attempt = attempt;
    const start = { task_id: TASK_A, request_id: (kind === "inventory" ? "6" : "4").repeat(32),
      session_id: (kind === "inventory" ? "7" : "5").repeat(32) };
    const active = { ...start, task_kind: kind, session_state: "active", session_released: false };
    const oldList = deferred();
    let olderRead;
    if (observation === "failed") {
      harness.listTasks = () => Promise.reject(new Error("list transport unavailable"));
    } else {
      let reads = 0;
      harness.listTasks = () => ++reads === 1 ? oldList.promise : Promise.resolve({ tasks: [active] });
      olderRead = harness.refreshTasks();
    }
    const submit = kind === "inventory" ? () => harness.startInventory(TASK_A) : () => harness.startPlan(TASK_A);
    const dispatched = harness.dispatchFormAttempt(task, form, attempt, submit);
    let dispatchError;
    try { await dispatched; } catch (error) { dispatchError = error; }
    assert.equal(task.sessionId, start.session_id, `${kind}: admitted session survives ${observation} list`);
    assert.equal(task.requestId, start.request_id);
    assert.equal(task.sessionState, "active");
    assert.equal(task.sessionReleased, false);
    assert.equal(harness.drains.at(-1).args[1], start.session_id);
    assert.equal(dispatchError, undefined, "task-list observation failure cannot reject an admitted start");
    if (olderRead !== undefined) {
      oldList.resolve({ tasks: [summary()] });
      await olderRead;
      await turns();
      assert.equal(task.sessionId, start.session_id, "an older task list cannot restore the pre-start shell");
      assert.equal(harness.drains.at(-1).args[1], start.session_id);
    }
  }
}

// Plan again adopts its newly admitted task without modifying the original
// review. A fresh request must never be inferred to be execution.
if (lifecycleScenario === "all" || lifecycleScenario === "plan-again") {
  const snapshot = {
    setup_state: "frozen", task_kind: "sync-plan",
    source: { display: "C:\\source", location_id: "41" },
    target: { display: "D:\\target", location_id: "42" }, root: null,
    options: structuredClone(DEFAULT_OPTIONS),
    plan_again: { source_state: "resolved", source_candidates: [], target_state: "resolved", target_candidates: [] },
  };
  const originalSummary = { ...summary(), session_id: "1".repeat(32), request_id: "2".repeat(32),
    task_kind: "sync-plan", session_state: "completed", session_released: true };
  const harness = await loadScenario({ snapshot, initialSummary: originalSummary });
  const original = harness.task;
  original.review = { pending: null };
  const originalReview = original.review;
  const shell = harness.adoptTask({ ...summary(TASK_B), session_id: "6".repeat(32),
    request_id: "7".repeat(32), task_kind: "sync-plan", session_state: "completed", session_released: true });
  shell.review = { pending: null };
  const previousDrain = harness.drains.at(-1);
  harness.listTasks = () => Promise.reject(new Error("list transport unavailable"));
  let dispatchError;
  try { await harness.startPlanAgain(original); } catch (error) { dispatchError = error; }
  assert.equal(harness.calls.filter((call) => call[0] === "plan-again").length, 1);
  assert.equal(original.review, originalReview);
  assert.equal(original.sessionId, originalSummary.session_id);
  assert.equal(shell.sessionId, "9".repeat(32));
  assert.equal(shell.requestId, "8".repeat(32));
  assert.equal(shell.executionStarted, false, "fresh Plan-again admission cannot imply execution");
  assert.equal(shell.executionWindowDirty, false);
  assert.equal(previousDrain.stopped, true, "session replacement stops its old drain");
  assert.equal(harness.drains.at(-1).args[1], shell.sessionId);
  assert.equal(dispatchError, undefined, "Plan-again admission also survives observation failure");
  previousDrain.args[5](TASK_B, "6".repeat(32));
  assert.equal(shell.sessionReleased, false, "the superseded drain cannot release the new session");
  assert.equal(shell.sessionState, "active");
  harness.adoptTask({ ...summary(TASK_B), session_id: "a".repeat(32),
    request_id: shell.requestId, task_kind: "sync-plan", session_state: "active", session_released: false });
  assert.equal(shell.executionStarted, true, "execution's same-request transition remains intact");
  assert.equal(shell.executionWindowDirty, true);
}

for (const observation of ["failed", "stale"]) {
  if (lifecycleScenario !== "all" && lifecycleScenario !== `batch-${observation}`) continue;
  const harness = await loadScenario();
  harness.pickFolder = (purpose) => Promise.resolve(choice(purpose, purpose === "source" ? "6" : "7"));
  harness.callbacks.onPick("source");
  await until(() => harness.model.source.location?.state === "resolved", "batch resolved source");
  harness.callbacks.onPick("target");
  await until(() => harness.model.target.location?.state === "resolved", "batch resolved target");
  harness.callbacks.onAddPair();
  const start = { task_id: TASK_B, request_id: "4".repeat(32), session_id: "5".repeat(32) };
  const active = { ...start, task_kind: "sync-plan", session_state: "active", session_released: false };
  const startReply = deferred();
  harness.startPlan = (...values) => {
    harness.calls.push(["start-plan", ...values]);
    return startReply.promise;
  };
  const dispatched = harness.startPairBatch();
  await until(() => harness.calls.some((call) => call[0] === "start-plan"), "batch dispatched original start");
  const oldList = deferred();
  let olderRead;
  if (observation === "failed") {
    harness.listTasks = () => Promise.reject(new Error("list transport unavailable"));
  } else {
    let reads = 0;
    harness.listTasks = () => ++reads === 1 ? oldList.promise
      : Promise.resolve({ tasks: [summary(TASK_A), active] });
    olderRead = harness.refreshTasks();
  }
  startReply.resolve(start);
  let dispatchError;
  try { await dispatched; } catch (error) { dispatchError = error; }
  if (olderRead !== undefined) {
    oldList.resolve({ tasks: [summary(TASK_A), summary(TASK_B)] });
    await olderRead;
    await turns();
  }
  const child = harness.tasks.get(TASK_B);
  assert.equal(child?.sessionId, start.session_id, `batch: admitted session survives ${observation} list`);
  assert.equal(child?.requestId, start.request_id);
  assert.equal(child?.sessionState, "active");
  assert.equal(child?.sessionReleased, false);
  assert.equal(harness.drains.at(-1).args[1], start.session_id);
  assert.equal(harness.model.batch[0].state, "created");
  assert.equal(harness.calls.filter((call) => call[0] === "start-plan").length, 1);
  assert.equal(dispatchError, undefined, "batch observation failure cannot reject an admitted start");
}

await turns();
console.log("ok");
