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
globalThis.document = {
  documentElement: new ElementFake("html"),
  createElement(tagName) { return new ElementFake(tagName); },
  querySelector(selector) {
    return selector === "#app" ? app : selector === "#host-status" ? status : theme;
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
  startTaskDrain(taskId, sessionId, acceptUpdate, acceptRefusal, initialState) {
    calls.push(["drain", taskId, sessionId, initialState]);
    drains.set(taskId, { acceptUpdate, acceptRefusal });
    return () => calls.push(["stop", taskId]);
  },
};

function moduleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

const renderUrl = moduleUrl(
  'export const renderText = (element, text) => { element.textContent = text; };',
);
const railSource = (await readFile(process.argv[3], "utf8"))
  .replace("./render.js", renderUrl);
const panelSource = (await readFile(process.argv[4], "utf8"))
  .replace("./render.js", renderUrl);
const bridgeUrl = moduleUrl(`
  export class BridgeTransportError extends Error {}
  export const acknowledgeShellReady = () => Promise.resolve({ acknowledged: true });
  export const echoReadiness = () => Promise.resolve({ acknowledged: true });
  export const whenBridgeApiReady = () => Promise.resolve();
  export const markBridgeOperational = () => {};
  export const createTask = () => globalThis.taskHarness.createTask();
  export const closeTask = (...args) => globalThis.taskHarness.closeTask(...args);
  export const listTasks = () => globalThis.taskHarness.listTasks();
  export const startTaskDrain = (...args) => globalThis.taskHarness.startTaskDrain(...args);
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
let appSource = await readFile(process.argv[2], "utf8");
appSource = appSource.replace(
  /import \{[\s\S]*?\} from "\.\/bridge\.js";/,
  `import { acknowledgeShellReady, BridgeTransportError, closeTask, createTask, echoReadiness, listTasks, markBridgeOperational, startTaskDrain, whenBridgeApiReady } from "${bridgeUrl}";`,
);
appSource = appSource
  .replace("./readiness.js", readinessUrl)
  .replace("./appearance.js", appearanceUrl)
  .replace("./theme.js", themeUrl)
  .replace("./rail.js", moduleUrl(railSource))
  .replace("./panels.js", moduleUrl(panelSource))
  .replace("./render.js", renderUrl);

function walk(root) {
  return [root, ...root.children.flatMap(walk)];
}

function byText(text) {
  return walk(app).find((element) => element.textContent === text);
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
      element.classList.values.has("nami-task-card"),
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

byText("New task").click();
await until(() => creates.length === 1);
taskButton("Task 2").click();
creates[0].resolve({ task_id: TASK_C });
await turns();
assert.equal(taskButton("Task 2")?.ariaCurrent, "page", "late create must not steal navigation");
assert.ok(byText("Task 4"));

byText("New task").click();
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
byText("New task").click();
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
  { task_id: TASK_G, session_id: SESSION_G, session_state: "completed", session_released: false },
] });
await turns();
assert.ok(byText("Completed"));
assert.deepEqual(
  calls.find((call) => call[0] === "drain" && call[1] === TASK_G),
  ["drain", TASK_G, SESSION_G, { terminal: true, sessionReleased: false }],
  "reinjection resumes terminal-session release without losing terminal truth",
);

const retainedBeforeCapacityRefusal = taskButtons();
byText("New task").click();
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
