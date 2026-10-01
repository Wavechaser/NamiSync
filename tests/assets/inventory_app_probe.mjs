import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

class ElementFake {
  constructor(tag) {
    this.tagName = tag.toUpperCase(); this.children = []; this.textContent = "";
    this.dataset = {}; this.listeners = new Map(); this.classList = { add() {} };
  }
  append(...values) { this.children.push(...values); }
  addEventListener(key, value) { this.listeners.set(key, value); }
}
globalThis.HTMLElement = ElementFake;
globalThis.Element = ElementFake;
const nodes = new Map();
globalThis.document = {
  body: new ElementFake("body"), documentElement: new ElementFake("html"),
  querySelector(key) { if (!nodes.has(key)) nodes.set(key, new ElementFake("div")); return nodes.get(key); },
};
globalThis.window = { chrome: { webview: {} }, addEventListener() {} };
const url = (source) => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const fixture = JSON.parse(await readFile(process.argv[3], "utf8"));
const calls = [], renders = [], drains = [];
let delayedDetail = null, delayedWindow = null, delayedView = null, delayedOpen = null;
let viewRevision = 0, query = "";
const summary = () => ({ ...fixture.views.default.summary, view_revision: viewRevision, search_query: query });
const windowResponse = (revision, offset) => ({ ...fixture.views.default.window, view_revision: revision, offset });
const defer = () => {
  let resolve;
  const promise = new Promise((accept) => { resolve = accept; });
  return { resolve, promise };
};
globalThis.inventoryHarness = {
  openInventoryView(taskId) { calls.push(["open", taskId]); return delayedOpen?.promise ?? Promise.resolve(summary()); },
  getInventoryWindow(taskId, revision, offset, limit) {
    calls.push(["window", taskId, revision, offset, limit]);
    return delayedWindow?.promise ?? Promise.resolve(windowResponse(revision, offset));
  },
  updateInventoryView(taskId, revision, gesture) {
    calls.push(["view", taskId, revision, gesture]);
    if (delayedView !== null) return delayedView.promise;
    viewRevision += 1; query = gesture.searchQuery;
    return Promise.resolve(summary());
  },
  getInventoryDetail(...args) {
    calls.push(["detail", ...args]); return delayedDetail?.promise ?? Promise.resolve(fixture.detail);
  },
};
const appPath = join(process.argv[2], "app.js");
let source = await readFile(appPath, "utf8");
const bridgeNames = source.match(/import \{([\s\S]*?)\} from "\.\/bridge\.js";/)[1]
  .split(",").map((value) => value.trim()).filter(Boolean);
const implementations = {
  whenBridgeApiReady: "() => new Promise(() => {})",
  closeTask: "(taskId, sessionId) => Promise.resolve({ task_id: taskId, session_id: sessionId, disposition: 'closed' })",
  readSetup: "() => new Promise(() => {})",
  startTaskDrain: "(...args) => { globalThis.inventoryDrains.push(args); return () => {}; }",
};
globalThis.inventoryDrains = drains;
const bridgeUrl = url(bridgeNames.map((name) => /^[A-Z]/.test(name)
  ? `export class ${name} extends Error {}`
  : `export const ${name} = ${implementations[name] ?? (name in globalThis.inventoryHarness
    ? `(...args) => globalThis.inventoryHarness.${name}(...args)` : "() => Promise.reject(new Error('unused bridge command'))")};`).join("\n"));
const renderUrl = url(await readFile(join(process.argv[2], "render.js"), "utf8"));
const taskStatusUrl = url((await readFile(join(process.argv[2], "task_status.js"), "utf8")).replace("./render.js", renderUrl));
const replacements = {
  "./bridge.js": bridgeUrl,
  "./render.js": renderUrl,
  "./task_status.js": taskStatusUrl,
  "./readiness.js": url("export const installReadinessReceiver = () => ({ revision: () => 0 });"),
  "./appearance.js": url("export const installAppearanceReceiver = () => {};"),
  "./theme.js": url("export const installThemeCombobox = () => ({}); export const installThemeSelector = () => ({ refresh() {} });"),
  "./execution_confirmation.js": url("export const createExecutionConfirmation = () => ({ element: new HTMLElement('dialog') });"),
  "./rail.js": url("export const createTaskRail = () => ({ element: new HTMLElement('nav'), render() {} });"),
  "./panels.js": url(`export const createWorkPanel = (setup, plan, settings, inventory) => {
    globalThis.inventoryCallbacks = inventory;
    return { element: new HTMLElement('section'), render(task) { globalThis.inventoryRenders.push(task); }, renderSettings() {} };
  };`),
};
globalThis.inventoryRenders = renders;
for (const [key, value] of Object.entries(replacements)) source = source.replace(key, value);
source += "\nexport { adoptTask, selectTask, acceptTaskRelease, loadInventoryReview, changeInventoryView, loadInventoryWindow, readInventoryDetail, closeRetainedTask, showSettings, tasks };";
const app = await import(url(source));
const taskId = fixture.views.default.summary.task_id;
const sessionId = "3".repeat(32);
const task = app.adoptTask({ task_id: taskId, session_id: sessionId, session_state: "active",
  session_released: false, task_kind: "inventory", request_id: fixture.views.default.summary.request_id });
const tick = async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); };
app.selectTask(taskId); await tick();
assert.equal(calls.length, 0, "active inventory must not open terminal review");
task.sessionState = "completed";
app.acceptTaskRelease(task, sessionId); await tick();
assert.equal(task.review, null, "inventory cannot acquire Plan/execution state");
assert.equal(task.executionStarted, false);
assert.ok(task.inventoryReview);
assert.deepEqual(calls[1], ["window", taskId, 0, 0, 256]);
let review = task.inventoryReview;
delayedOpen = defer();
const retainedOpen = delayedOpen;
const oldOpen = app.loadInventoryReview(task, true);
app.showSettings();
retainedOpen.resolve(summary()); await oldOpen;
assert.equal(task.inventoryReview, review, "navigation rejects a stale publication read");
delayedOpen = null;
app.selectTask(taskId); await tick();
review = task.inventoryReview;
delayedOpen = defer();
const failedOpen = app.loadInventoryReview(task, true);
const failedRead = delayedOpen;
delayedOpen = null;
failedRead.resolve(Promise.reject(new Error("ledger unavailable")));
await failedOpen;
assert.equal(task.inventoryReview, review, "failed reload retains prior complete publication");
assert.equal(review.pending, null);
assert.match(task.inventoryError, /Reload/);
await app.loadInventoryReview(task, true);
review = task.inventoryReview;
assert.equal(task.inventoryError, null);
const real = review.window.rows.find((row) => row.row_id === "1");
const warning = review.window.rows.find((row) => row.warning !== null);
const folder = review.window.rows.find((row) => row.row_kind === "folder");
await app.readInventoryDetail(review, warning.node_id);
assert.equal(review.detail.row, warning);
assert.equal(calls.filter(([name]) => name === "detail").length, 0);
await app.readInventoryDetail(review, folder.node_id);
assert.equal(calls.filter(([name]) => name === "detail").length, 0);
delayedDetail = defer();
const oldDetail = app.readInventoryDetail(review, real.node_id);
assert.equal(review.detail.state, "loading");
app.showSettings();
delayedDetail.resolve(fixture.detail); await oldDetail;
assert.equal(review.detail, null, "navigation must retire detail before reply");
delayedDetail = null;
app.selectTask(taskId); await tick();
review = task.inventoryReview;
const staleReview = review;
delayedWindow = defer();
const retainedWindow = delayedWindow;
const oldWindow = app.loadInventoryWindow(review, 0);
delayedWindow = null;
await app.changeInventoryView(review, { searchQuery: "evidence" });
assert.equal(review.summary.search_query, "evidence");
assert.equal(review.detail, null);
retainedWindow.resolve(windowResponse(0, 0));
assert.equal(await oldWindow, null, "old revision window must not be adopted");
assert.equal(review.window.view_revision, review.summary.view_revision);
assert.equal(staleReview, review);
delayedView = defer();
const retainedView = delayedView;
const firstQuery = app.changeInventoryView(review, { searchQuery: "one" });
await tick();
await app.changeInventoryView(review, { searchQuery: "two" });
assert.equal(review.queuedSearchQuery, "two");
delayedView = null; viewRevision += 1; query = "one";
retainedView.resolve(summary()); await firstQuery; await tick();
assert.equal(review.summary.search_query, "two");
assert.equal(review.pending, null);
assert.equal(review.queuedSearchQuery, null);
delayedDetail = defer();
const sessionDetail = app.readInventoryDetail(review, real.node_id);
const retainedDetail = delayedDetail;
app.adoptTask({ task_id: taskId, session_id: "4".repeat(32), session_state: "active",
  session_released: false, task_kind: "inventory", request_id: "5".repeat(32) });
assert.equal(task.inventoryReview, review, "new scan preserves old publication");
assert.equal(task.executionStarted, false);
retainedDetail.resolve({ ...fixture.detail, view_revision: review.summary.view_revision });
await sessionDetail;
assert.equal(review.detail, null, "changed session invalidates old details");
delayedDetail = defer();
const closeDetail = app.readInventoryDetail(review, real.node_id);
const retainedCloseDetail = delayedDetail;
await app.closeRetainedTask(taskId);
assert.equal(app.tasks.has(taskId), false);
retainedCloseDetail.resolve({ ...fixture.detail, view_revision: review.summary.view_revision });
await closeDetail;
assert.equal(review.detail, null, "Close invalidates outstanding details");
assert.ok(renders.some((value) => value === task));
assert.equal(typeof globalThis.inventoryCallbacks.onReload, "function");
process.stdout.write("ok\n");
