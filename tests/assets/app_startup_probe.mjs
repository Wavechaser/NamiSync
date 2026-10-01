import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";


class HTMLElementFake {
  constructor(textContent = "") {
    this.textContent = textContent;
    this.appended = [];
  }

  append(...values) {
    this.appended.push(...values);
  }
}

class HTMLSelectElementFake extends HTMLElementFake {}

globalThis.HTMLElement = HTMLElementFake;
globalThis.HTMLSelectElement = HTMLSelectElementFake;
const app = new HTMLElementFake();
const status = new HTMLElementFake("Starting...");
const theme = new HTMLSelectElementFake();
const settings = new HTMLElementFake();
const themeOptions = new HTMLElementFake();
const themeOutcomeStatus = new HTMLElementFake();
const themeRefresh = new HTMLElementFake();
themeRefresh.addEventListener = () => {};
const body = new HTMLElementFake();
globalThis.document = {
  documentElement: new HTMLElementFake(),
  body,
  querySelector(selector) {
    return selector === "#app"
      ? app
      : selector === "#host-status"
        ? status
        : selector === "#theme-mode"
          ? theme
          : selector === "#settings-view"
            ? settings
            : selector === "#theme-options" ? themeOptions
              : selector === "#theme-outcome-status" ? themeOutcomeStatus
                : selector === "#theme-refresh" ? themeRefresh : null;
  },
};

const listeners = new Map();
globalThis.window = {
  chrome: { webview: {} },
  addEventListener(name, callback) {
    const callbacks = listeners.get(name) ?? [];
    callbacks.push(callback);
    listeners.set(name, callbacks);
  },
};

const shellAcknowledgements = [];
const echoAttempts = [];
let operationalMarks = 0;
let themeOpens = 0;
let themeRefreshes = 0;
let rawApiReady = false;
let resolveRawApiReadiness;
const rawApiReadiness = new Promise((resolve) => {
  resolveRawApiReadiness = resolve;
});
let readinessRevision = 0;
let latestChallenge = null;
let readinessWaiters = [];

function pendingAttempt(entries, value = undefined) {
  let resolve;
  let reject;
  const promise = new Promise((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  entries.push({ promise, resolve, reject, value });
  return promise;
}

function emitChallenge(challenge) {
  readinessRevision += 1;
  latestChallenge = challenge;
  const ready = readinessWaiters.filter(
    (waiter) => readinessRevision > waiter.baseline,
  );
  readinessWaiters = readinessWaiters.filter(
    (waiter) => readinessRevision <= waiter.baseline,
  );
  for (const waiter of ready) waiter.resolve(challenge);
}

globalThis.startupHarness = {
  whenBridgeApiReady() {
    return rawApiReady ? Promise.resolve() : rawApiReadiness;
  },
  signalBridgeApiReady() {
    rawApiReady = true;
    resolveRawApiReadiness();
  },
  acknowledgeShell() {
    return pendingAttempt(shellAcknowledgements);
  },
  echo(challenge) {
    return pendingAttempt(echoAttempts, challenge);
  },
  readiness: Object.freeze({
    revision: () => readinessRevision,
    whenReceivedAfter(baseline) {
      if (readinessRevision > baseline) return Promise.resolve(latestChallenge);
      return new Promise((resolve) => {
        readinessWaiters.push({ baseline, resolve });
      });
    },
  }),
};

function moduleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

const bridgeStub = moduleUrl(`
  export class BridgeTransportError extends Error {}
  export class OutcomeUnavailableError extends BridgeTransportError {}
  export class StartPlanUncertainError extends BridgeTransportError {}
  export class TaskCreateUncertainError extends BridgeTransportError {}
  export class TaskCloseUncertainError extends BridgeTransportError {}
  globalThis.startupHarness.BridgeTransportError = BridgeTransportError;
  export const whenBridgeApiReady = () => globalThis.startupHarness.whenBridgeApiReady();
  export const acknowledgeShellReady = () => globalThis.startupHarness.acknowledgeShell();
  export const echoReadiness = (challenge) => globalThis.startupHarness.echo(challenge);
  export const markBridgeOperational = () => { globalThis.startupHarness.markOperational(); };
  export const createTask = () => Promise.reject(new Error("unused"));
  export const closeTask = () => Promise.reject(new Error("unused"));
  export const listTasks = () => Promise.resolve({ tasks: [] });
  export const getExecutionDetail = () => Promise.reject(new Error("unused"));
  export const openInventoryView = () => Promise.reject(new Error("unused inventory read"));
  export const updateInventoryView = () => Promise.reject(new Error("unused inventory read"));
  export const getInventoryWindow = () => Promise.reject(new Error("unused inventory read"));
  export const getInventoryDetail = () => Promise.reject(new Error("unused inventory read"));
  export const readSetup = () => Promise.resolve({
    task_id: null,
    snapshot: {
      setup_state: "default", task_kind: null, source: null, target: null, root: null,
      options: { filters: [], deletion_policy: "trash", trash_on_update: false,
        preservation: { preserve_ads: false, preserve_created: true, preserve_acl: false },
        propagate_source_casing: false, verify_after_execute: false },
      plan_again: null,
    },
    recents: { sources: [], targets: [], pairs: [] },
  });
  export const admitLocation = () => Promise.reject(new Error("unused"));
  export const probeRecentPairs = () => Promise.resolve({ pairs: [] });
  export const pickFolder = () => Promise.reject(new Error("unused"));
  export const planAgain = () => Promise.reject(new Error("unused"));
  export const prepareSetup = () => Promise.reject(new Error("unused"));
  export const startInventory = () => Promise.reject(new Error("unused"));
  export const startPlan = () => Promise.reject(new Error("unused"));
  export const startTaskDrain = () => () => {};
`);
globalThis.startupHarness.markOperational = () => {
  operationalMarks += 1;
};
const readinessStub = moduleUrl(`
  export const installReadinessReceiver = () => globalThis.startupHarness.readiness;
`);
const appearanceStub = moduleUrl(`
  export const installAppearanceReceiver = (_webview, _root, onApplied) => {
    onApplied();
    return Object.freeze({});
  };
`);
const themeStub = moduleUrl(`
  export const installThemeCombobox = (root) => root;
  export const installThemeSelector = () => Object.freeze({
    invalidate() { globalThis.startupHarness.invalidateTheme(); },
    open() { return globalThis.startupHarness.openTheme(); },
    refresh() { return globalThis.startupHarness.refreshTheme(); },
  });
`);
const railStub = moduleUrl(`
  export const createTaskRail = () => ({ element: {}, render() {} });
`);
const panelsStub = moduleUrl(`
  export const createWorkPanel = () => ({ element: {}, render() {} });
`);
const renderStub = moduleUrl(`
  export const renderText = (element, value) => { element.textContent = value; };
  export const formatByteCount = (value) => String(value);
`);
const executionConfirmationStub = moduleUrl(`
  export const createExecutionConfirmation = () => ({ element: {}, show() {} });
`);

let source = await readFile(process.argv[2], "utf8");
let taskStatusSource = await readFile(
  process.argv[2].replace(/app\.js$/, "task_status.js"),
  "utf8",
);
taskStatusSource = taskStatusSource.replace("./render.js", renderStub);
const taskStatusStub = moduleUrl(taskStatusSource);
source = source.replace(
  /import \{[\s\S]*?\} from "\.\/bridge\.js";/,
  `import { acknowledgeShellReady, admitLocation, BridgeTransportError, closeTask, createTask, echoReadiness, getExecutionDetail, getInventoryDetail, getInventoryWindow, openInventoryView, updateInventoryView, listTasks, markBridgeOperational, OutcomeUnavailableError, pickFolder, planAgain, prepareSetup, probeRecentPairs, readSetup, StartPlanUncertainError, startInventory, startPlan, startTaskDrain, TaskCloseUncertainError, TaskCreateUncertainError, whenBridgeApiReady } from "${bridgeStub}";`,
);
source = source
  .replace("./readiness.js", readinessStub)
  .replace("./appearance.js", appearanceStub)
  .replace("./theme.js", themeStub)
  .replace("./execution_confirmation.js", executionConfirmationStub)
  .replace("./panels.js", panelsStub)
  .replace("./rail.js", railStub)
  .replace("./render.js", renderStub)
  .replace("./task_status.js", taskStatusStub);

window.addEventListener("pywebviewready", () => {
  globalThis.startupHarness.signalBridgeApiReady();
});
globalThis.startupHarness.openTheme = () => {
  themeOpens += 1;
  return new Promise(() => {});
};
globalThis.startupHarness.refreshTheme = () => {
  themeRefreshes += 1;
  return Promise.resolve(false);
};
await import(moduleUrl(source));
for (let turn = 0; turn < 4; turn += 1) await Promise.resolve();
assert.equal(themeRefreshes, 1, "early appearance refresh is readiness-neutral");
assert.equal(
  shellAcknowledgements.length,
  0,
  "startup waits while the raw bridge API is absent",
);

const challenge = "a".repeat(32);
for (const callback of listeners.get("pywebviewready") ?? []) callback();
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(
  shellAcknowledgements.length,
  1,
  "initial bridge readiness starts one shell acknowledgement",
);
assert.equal(echoAttempts.length, 0);
shellAcknowledgements[0].reject(
  new globalThis.startupHarness.BridgeTransportError("lost shell response"),
);
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(status.textContent, "Starting...");
assert.equal(operationalMarks, 0);
assert.equal(echoAttempts.length, 0);
emitChallenge(challenge);
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.deepEqual(echoAttempts.map((attempt) => attempt.value), [challenge]);
echoAttempts[0].resolve({ acknowledged: false });
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.deepEqual(
  echoAttempts.map((attempt) => attempt.value),
  [challenge, challenge],
  "a false result retries the identical challenge exactly once",
);
echoAttempts[1].resolve({ acknowledged: true });
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(status.textContent, "Ready");
assert.equal(operationalMarks, 1);
assert.equal(themeOpens, 1, "post-OPEN cosmetic initialization is fire-and-forget");

for (const callback of listeners.get("pywebviewready") ?? []) callback();
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(status.textContent, "Ready");
assert.equal(shellAcknowledgements.length, 1, "a second ready event cannot restart startup");
assert.equal(echoAttempts.length, 2);
assert.equal(operationalMarks, 1);
assert.equal(themeOpens, 1);

process.stdout.write("ok");
