import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const TASK_A = `task-${"a".repeat(32)}`;
const TASK_B = `task-${"b".repeat(32)}`;
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
  const windowListeners = new Map();
  globalThis.document = {
    documentElement: new ElementFake(),
    querySelector(selector) {
      return selector === "#app" ? app : selector === "#host-status" ? status : theme;
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

  const renderUrl = moduleUrl("export const renderText = (element, value) => { element.textContent = value; };");
  const bridgeUrl = moduleUrl(`
    const harness = globalThis.setupAppHarness;
    export class BridgeTransportError extends Error {}
    export class StartPlanUncertainError extends BridgeTransportError {
      constructor(retry) { super(); this.retry = retry; }
    }
    export class TaskCreateUncertainError extends BridgeTransportError {
      constructor(retry) { super(); this.retry = retry; }
    }
    harness.StartPlanUncertainError = StartPlanUncertainError;
    harness.TaskCreateUncertainError = TaskCreateUncertainError;
    export const acknowledgeShellReady = () => Promise.resolve({ acknowledged: true });
    export const admitLocation = (...args) => harness.admitLocation(...args);
    export const closeTask = () => Promise.reject(new Error("unused"));
    export const createTask = () => harness.createTask();
    export const echoReadiness = () => Promise.resolve({ acknowledged: true });
    export const listTasks = () => harness.listTasks();
    export const markBridgeOperational = () => {};
    export const pickFolder = (...args) => harness.pickFolder(...args);
    export const planAgain = (...args) => harness.planAgain(...args);
    export const prepareSetup = (...args) => harness.prepareSetup(...args);
    export const probeRecentPairs = () => harness.probeRecentPairs();
    export const readSetup = (...args) => harness.readSetup(...args);
    export const startInventory = (...args) => harness.startInventory(...args);
    export const startPlan = (...args) => harness.startPlan(...args);
    export const startTaskDrain = () => () => {};
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
        render(_tasks, _selected, creating) { harness.createStates.push(creating); },
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
  let source = await readFile(process.argv[2], "utf8");
  source = source.replace(
    /import \{[\s\S]*?\} from "\.\/bridge\.js";/,
    `import { acknowledgeShellReady, admitLocation, BridgeTransportError, closeTask, createTask, echoReadiness, listTasks, markBridgeOperational, pickFolder, planAgain, prepareSetup, probeRecentPairs, readSetup, StartPlanUncertainError, startInventory, startPlan, startTaskDrain, TaskCreateUncertainError, whenBridgeApiReady } from "${bridgeUrl}";`,
  );
  source = source
    .replace("./readiness.js", readinessUrl)
    .replace("./appearance.js", appearanceUrl)
    .replace("./theme.js", themeUrl)
    .replace("./panels.js", panelUrl)
    .replace("./rail.js", railUrl)
    .replace("./render.js", renderUrl);
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
  harness.createTask = () => {
    harness.calls.push(["create"]);
    return Promise.reject(new harness.TaskCreateUncertainError(() => {
      createRetries += 1;
      return Promise.resolve({ task_id: TASK_B });
    }));
  };
  harness.railCallbacks.onCreate();
  await until(
    () => globalThis.document.querySelector("#host-status").textContent.includes("Select New task"),
    "new-task uncertainty guidance",
  );
  assert.equal(harness.createStates.at(-1), false, "New task is enabled only for the retained retry");
  for (const callback of harness.windowListeners.get("pywebviewready") ?? []) callback();
  await turns();
  assert.match(
    globalThis.document.querySelector("#host-status").textContent,
    /Select New task to retry the same request/,
    "reinjection retains the pending create guidance",
  );
  harness.railCallbacks.onCreate();
  harness.railCallbacks.onCreate();
  await until(() => createRetries === 1, "same new-task retry closure");
  assert.ok(harness.createStates.includes(true), "New task is disabled while its request runs");
  assert.equal(harness.calls.filter((call) => call[0] === "create").length, 1);
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
  let planRetries = 0;
  harness.startPlan = (...values) => {
    harness.calls.push(["start-plan", ...values]);
    return Promise.reject(new harness.StartPlanUncertainError(() => {
      planRetries += 1;
      return Promise.resolve({ task_id: TASK_A, request_id: "4".repeat(32), session_id: "5".repeat(32) });
    }));
  };
  callbacks.onStartPlan();
  await until(() => typeof firstModel.attempt?.retry === "function", "plan uncertainty retained");
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
    return Promise.reject(new harness.StartPlanUncertainError(() => {
      inventoryRetries += 1;
      return Promise.resolve({ task_id: TASK_A, request_id: "6".repeat(32), session_id: "7".repeat(32) });
    }));
  };
  callbacks.onStartInventory();
  await until(() => typeof harness.model.attempt?.retry === "function", "inventory uncertainty retained");
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
    return Promise.reject(new harness.StartPlanUncertainError(() => {
      retries += 1;
      return Promise.resolve({ task_id: TASK_B, request_id: "8".repeat(32), session_id: "9".repeat(32) });
    }));
  };
  harness.callbacks.onPlanAgain();
  await until(() => typeof harness.model.attempt?.retry === "function", "Plan-again uncertainty retained");
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
  harness.createTask = () => {
    harness.calls.push(["create"]);
    return Promise.reject(new harness.TaskCreateUncertainError(() => {
      createRetries += 1;
      return Promise.resolve({ task_id: TASK_B });
    }));
  };
  let startRetries = 0;
  harness.startPlan = (...values) => {
    harness.calls.push(["start-plan", ...values]);
    return Promise.reject(new harness.StartPlanUncertainError(() => {
      startRetries += 1;
      return Promise.resolve({ task_id: TASK_B, request_id: "4".repeat(32), session_id: "5".repeat(32) });
    }));
  };
  callbacks.onStartBatch();
  callbacks.onStartBatch();
  callbacks.onAddPair();
  assert.equal(harness.model.batch.length, 1, "running batch rejects add and reentrant Start");
  prepare.resolve(structuredClone(DEFAULT_OPTIONS));
  await until(() => harness.model.batch[0].state === "uncertain", "create uncertainty retained");
  assert.equal(harness.model.batch[0].stage, "creating");
  callbacks.onStartBatch();
  await until(() => harness.model.batch[0].stage === "starting", "start uncertainty retained");
  assert.equal(createRetries, 1);
  assert.equal(harness.calls.filter((call) => call[0] === "create").length, 1);
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
  await until(() => prepareCalls === 1, "active form owner");
  callbacks.onStartBatch();
  await turns();
  assert.equal(harness.calls.filter((call) => call[0] === "create").length, 0,
    "active form attempt blocks batch submission");
  formPrepare.resolve(structuredClone(DEFAULT_OPTIONS));
  await until(() => harness.model.attempt === null, "form owner released");
  callbacks.onStartBatch();
  await until(() => harness.calls.some((call) => call[0] === "create"), "batch resumes after form owner");
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
  batchPrepare.resolve(structuredClone(DEFAULT_OPTIONS));
  await until(() => !harness.model.batchRunning, "batch owner released");
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
  harness.createTask = () => {
    harness.calls.push(["create"]);
    return firstCreate.promise;
  };
  callbacks.onStartBatch();
  await until(() => harness.calls.filter((call) => call[0] === "create").length === 1, "first serial create");
  assert.equal(harness.calls.some((call) => call[0] === "start-plan"), false);
  for (const callback of harness.windowListeners.get("pywebviewready") ?? []) callback();
  firstCreate.resolve({ task_id: TASK_B });
  await until(() => harness.model.batch.every((row) => row.state === "stopped"), "replacement stops unsent work");
  assert.equal(harness.calls.some((call) => call[0] === "start-plan"), false);
  assert.equal(harness.calls.filter((call) => call[0] === "create").length, 1);
}

await turns();
console.log("ok");
