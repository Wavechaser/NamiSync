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
globalThis.document = {
  documentElement: new HTMLElementFake(),
  querySelector(selector) {
    return selector === "#app"
      ? app
      : selector === "#host-status"
        ? status
        : selector === "#theme-mode"
          ? theme
          : null;
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
let themeInvalidations = 0;
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
  export class StartPlanUncertainError extends BridgeTransportError {
    constructor(retry) { super(); this.retry = retry; }
  }
  export class TaskCreateUncertainError extends BridgeTransportError {
    constructor(retry) { super(); this.retry = retry; }
  }
  globalThis.startupHarness.BridgeTransportError = BridgeTransportError;
  export const whenBridgeApiReady = () => globalThis.startupHarness.whenBridgeApiReady();
  export const acknowledgeShellReady = () => globalThis.startupHarness.acknowledgeShell();
  export const echoReadiness = (challenge) => globalThis.startupHarness.echo(challenge);
  export const markBridgeOperational = () => { globalThis.startupHarness.markOperational(); };
  export const createTask = () => Promise.reject(new Error("unused"));
  export const closeTask = () => Promise.reject(new Error("unused"));
  export const listTasks = () => Promise.resolve({ tasks: [] });
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
`);

let source = await readFile(process.argv[2], "utf8");
source = source.replace(
  /import \{[\s\S]*?\} from "\.\/bridge\.js";/,
  `import { acknowledgeShellReady, admitLocation, BridgeTransportError, closeTask, createTask, echoReadiness, listTasks, markBridgeOperational, pickFolder, planAgain, prepareSetup, readSetup, StartPlanUncertainError, startInventory, startPlan, startTaskDrain, TaskCreateUncertainError, whenBridgeApiReady } from "${bridgeStub}";`,
);
source = source
  .replace("./readiness.js", readinessStub)
  .replace("./appearance.js", appearanceStub)
  .replace("./theme.js", themeStub)
  .replace("./panels.js", panelsStub)
  .replace("./rail.js", railStub)
  .replace("./render.js", renderStub);

window.addEventListener("pywebviewready", () => {
  globalThis.startupHarness.signalBridgeApiReady();
});
globalThis.startupHarness.invalidateTheme = () => {
  themeInvalidations += 1;
};
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

const challengeBeforeDeferredRerun = "0".repeat(32);
for (const callback of listeners.get("pywebviewready") ?? []) callback();
emitChallenge(challengeBeforeDeferredRerun);
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(
  shellAcknowledgements.length,
  1,
  "raw readiness resolving before the app listener cannot acknowledge the superseded attempt",
);
shellAcknowledgements[0].resolve({ acknowledged: true });
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.deepEqual(
  echoAttempts.map((attempt) => attempt.value),
  [challengeBeforeDeferredRerun],
  "a challenge delivered before the deferred rerun must remain visible to it",
);
echoAttempts[0].resolve({ acknowledged: true });
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(status.textContent, "Ready");
assert.equal(operationalMarks, 1);
assert.equal(themeOpens, 1, "post-OPEN cosmetic initialization is fire-and-forget");

shellAcknowledgements.length = 0;
echoAttempts.length = 0;
operationalMarks = 0;

for (const callback of listeners.get("pywebviewready") ?? []) callback();
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(shellAcknowledgements.length, 1);

for (const callback of listeners.get("pywebviewready") ?? []) callback();
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(
  shellAcknowledgements.length,
  2,
  "reinjection while a shell acknowledgement is pending starts a fresh attempt",
);
assert.equal(status.textContent, "Starting...");
assert.equal(operationalMarks, 0);

shellAcknowledgements[1].resolve({ acknowledged: true });
for (let turn = 0; turn < 4; turn += 1) await Promise.resolve();
assert.equal(echoAttempts.length, 0);
assert.equal(
  status.textContent,
  "Starting...",
  "a shell acknowledgement without a native challenge cannot report Ready",
);

const firstChallenge = "a".repeat(32);
emitChallenge(firstChallenge);
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.deepEqual(echoAttempts.map((attempt) => attempt.value), [firstChallenge]);
echoAttempts[0].resolve({ acknowledged: false });
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.deepEqual(
  echoAttempts.map((attempt) => attempt.value),
  [firstChallenge, firstChallenge],
  "a false result retries the identical challenge exactly once",
);
echoAttempts[1].resolve({ acknowledged: true });
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(status.textContent, "Ready");
assert.equal(operationalMarks, 1);
assert.equal(themeOpens, 2);

for (const callback of listeners.get("pywebviewready") ?? []) callback();
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(status.textContent, "Starting...");
assert.equal(shellAcknowledgements.length, 3);
shellAcknowledgements[2].reject(
  new globalThis.startupHarness.BridgeTransportError("lost response"),
);
const secondChallenge = "b".repeat(32);
emitChallenge(secondChallenge);
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(echoAttempts.length, 3);
echoAttempts[2].reject(
  new globalThis.startupHarness.BridgeTransportError("lost response"),
);
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.deepEqual(
  echoAttempts.slice(2).map((attempt) => attempt.value),
  [secondChallenge, secondChallenge],
  "transport uncertainty retries the identical challenge exactly once",
);
echoAttempts[3].resolve({ acknowledged: true });
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(status.textContent, "Ready");
assert.equal(operationalMarks, 2);
assert.equal(themeOpens, 3);

for (const callback of listeners.get("pywebviewready") ?? []) callback();
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(status.textContent, "Starting...");
assert.equal(shellAcknowledgements.length, 4);
shellAcknowledgements[3].reject(new Error("definitive refusal"));
emitChallenge("c".repeat(32));
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(
  status.textContent,
  "Starting...",
  "a definitive non-transport failure cannot report Ready",
);
assert.equal(operationalMarks, 2);
assert.equal(echoAttempts.length, 4);
assert.ok(
  themeInvalidations >= 4,
  "every bridge reincarnation invalidates the older cosmetic attempt",
);

process.stdout.write("ok");
