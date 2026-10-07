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
const calls = [], renders = [], drains = [], stoppedDrains = [];
let delayedDetail = null, delayedWindow = null, delayedView = null, delayedOpen = null, delayedVisibility = null;
let taskSnapshot = null, observedChecks = 0, refuseRefresh = false, delayedRefresh = null;
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
    calls.push(["detail", ...args]); return delayedDetail?.promise ?? Promise.resolve(fixture.snapshots[args[2]] ?? fixture.detail);
  },
  listTasks() { return Promise.resolve({ tasks: taskSnapshot === null ? [] : [taskSnapshot] }); },
  refreshInventory(...args) {
    calls.push(["refresh", ...args.slice(0, 5)]);
    if (refuseRefresh) return Promise.reject(Object.assign(new Error("capacity"), { code: "inventory_capacity" }));
    const [taskId] = args;
    taskSnapshot = { task_id: taskId, session_id: "7".repeat(32), session_state: "active",
      session_released: false, task_kind: "inventory", request_id: "8".repeat(32) };
    return delayedRefresh?.promise ?? Promise.resolve({ task_id: taskId, session_id: taskSnapshot.session_id,
      request_id: taskSnapshot.request_id });
  },
  restoreInventory(...args) {
    calls.push(["restore", ...args.slice(0, 5)]);
    args[5]?.({ canCheck: true, checking: false, message: "Original result pending",
      check() { observedChecks += 1; return Promise.resolve(); } });
    return delayedVisibility?.promise ?? Promise.resolve({ task_id: args[0], request_id: args[1],
      action: "restore", expected_revision: args[3], total: 3, applied: 1, noop: 0,
      stale: 1, conflict: 1, unresolved_count: 0, disposition: "completed" });
  },
  acknowledgeInventory(...args) {
    calls.push(["acknowledge", ...args.slice(0, 5)]);
    return Promise.resolve({ task_id: args[0], request_id: args[1], action: "acknowledge",
      expected_revision: args[3], total: 3, applied: 1, noop: 0, stale: 1,
      conflict: 0, unresolved_count: 1, disposition: "partial" });
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
  startTaskDrain: "(...args) => { globalThis.inventoryDrains.push(args); return () => globalThis.inventoryStoppedDrains.push(args[1]); }",
};
globalThis.inventoryDrains = drains;
globalThis.inventoryStoppedDrains = stoppedDrains;
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
source += "\nexport { adoptTask, selectTask, acceptTaskRelease, loadInventoryReview, changeInventoryView, loadInventoryWindow, readInventoryDetail, runInventoryAction, checkInventoryOutcome, closeRetainedTask, showSettings, refreshTasks, tasks };";
const app = await import(url(source));
const taskId = fixture.views.default.summary.task_id;
const sessionId = "3".repeat(32);
const task = app.adoptTask({ task_id: taskId, session_id: sessionId, session_state: "active",
  session_released: false, task_kind: "inventory", request_id: fixture.views.default.summary.request_id });
taskSnapshot = { task_id: taskId, session_id: sessionId, session_state: "active",
  session_released: false, task_kind: "inventory", request_id: task.requestId };
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
assert.equal(calls.filter(([name]) => name === "detail").length, 1);
assert.deepEqual(review.detail.response, fixture.snapshots[warning.node_id]);
await app.readInventoryDetail(review, folder.node_id);
assert.equal(calls.filter(([name]) => name === "detail").length, 2);
assert.deepEqual(review.detail.response, fixture.snapshots[folder.node_id]);
const beforeContext = calls.filter(([name]) => name === "refresh").length;
refuseRefresh = true;
await app.runInventoryAction(review, "refresh", warning.node_id);
assert.equal(calls.filter(([name]) => name === "refresh").length, beforeContext,
  "informational window rows cannot acquire a command");
await app.runInventoryAction(review, "refresh", real.node_id);
assert.equal(calls.filter(([name]) => name === "refresh").length, beforeContext + 1);
assert.equal(calls.findLast(([name]) => name === "refresh")[5], real.node_id,
  "explicit current row acts on itself while another row owns details");
refuseRefresh = false;
await app.readInventoryDetail(review, folder.node_id);
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
const obsoleteQueuedWindow = app.loadInventoryWindow(review, 64);
delayedWindow = null;
await app.changeInventoryView(review, { searchQuery: "evidence" });
assert.equal(await obsoleteQueuedWindow, null, "view action retires queued viewport work before its direct window read");
assert.equal(review.summary.search_query, "evidence");
assert.equal(review.detail, null);
retainedWindow.resolve(windowResponse(0, 0));
assert.equal(await oldWindow, null, "old revision window must not be adopted");
assert.equal(review.window.view_revision, review.summary.view_revision);
assert.equal(staleReview, review);

// A replacement publication may complete its action-owned window while an
// obsolete viewport read drains. Task custody still serializes new viewports.
delayedWindow = defer();
const priorPublicationRead = delayedWindow;
const priorPublicationWindow = app.loadInventoryWindow(review, 12);
const priorQueuedWindow = app.loadInventoryWindow(review, 24);
delayedWindow = null;
await app.loadInventoryReview(task, true);
assert.equal(await priorQueuedWindow, null);
assert.notEqual(task.inventoryReview, review);
review = task.inventoryReview;
const replacementCalls = calls.filter(([name]) => name === "window").length;
const replacementWindow = app.loadInventoryWindow(review, 48);
assert.equal(calls.filter(([name]) => name === "window").length, replacementCalls);
priorPublicationRead.resolve(windowResponse(0, 12));
assert.equal(await priorPublicationWindow, null);
assert.equal((await replacementWindow).offset, 48);
assert.equal(calls.filter(([name]) => name === "window").length, replacementCalls + 1);

// Dispatch rechecks UI eligibility rather than relying on revisions alone.
for (const [block, unblock] of [
  [() => { task.inventoryLoading = true; }, () => { task.inventoryLoading = false; }],
  [() => { task.inventoryAction = { pending: true }; }, () => { task.inventoryAction = null; }],
  [() => { review.pending = "view"; }, () => { review.pending = null; }],
  [() => { task.closeRecovery = { canCheck: true }; }, () => { task.closeRecovery = null; }],
]) {
  delayedWindow = defer();
  const heldRead = delayedWindow;
  const held = app.loadInventoryWindow(review, 12);
  const queued = app.loadInventoryWindow(review, 24);
  const reads = calls.filter(([name]) => name === "window").length;
  block();
  delayedWindow = null;
  heldRead.resolve(Promise.reject(new Error("obsolete window rejection")));
  assert.equal(await held, null);
  assert.equal(await queued, null);
  assert.equal(calls.filter(([name]) => name === "window").length, reads);
  assert.equal(review.message, null);
  unblock();
}
delayedWindow = defer();
const failedWindow = app.loadInventoryWindow(review, 12);
delayedWindow.resolve(Promise.reject(new Error("current window rejection")));
assert.equal(await failedWindow, null);
assert.match(review.message, /Inventory rows unavailable.*Reload/);
delayedWindow = null;
review.message = null;
assert.equal((await app.loadInventoryWindow(review, 24)).offset, 24, "a rejected read releases viewport custody");
delayedWindow = defer();
const conflictedWindow = app.loadInventoryWindow(review, 12);
const retainedWindowAfterConflict = review.window;
delayedWindow.resolve({ ...windowResponse(review.summary.view_revision, 12), disposition: "conflict" });
assert.equal(await conflictedWindow, null);
assert.equal(review.window, retainedWindowAfterConflict);
assert.match(review.message, /Inventory changed.*Reload/);
delayedWindow = null;
review.message = null;
delayedWindow = defer();
const failedSupersededRead = delayedWindow;
const supersededWindow = app.loadInventoryWindow(review, 12);
const latestAfterFailure = app.loadInventoryWindow(review, 24);
delayedWindow = null;
failedSupersededRead.resolve(Promise.reject(new Error("superseded window rejection")));
assert.equal(await supersededWindow, null);
assert.equal((await latestAfterFailure).offset, 24, "obsolete rejection still dispatches the latest eligible intent");
assert.equal(review.message, null);

delayedWindow = defer();
const navigationRead = delayedWindow;
const navigationWindow = app.loadInventoryWindow(review, 12);
const navigationQueued = app.loadInventoryWindow(review, 24);
const navigationReads = calls.filter(([name]) => name === "window").length;
app.showSettings();
assert.equal(await navigationQueued, null);
delayedWindow = null;
navigationRead.resolve(windowResponse(review.summary.view_revision, 12));
assert.equal(await navigationWindow, null);
assert.equal(calls.filter(([name]) => name === "window").length, navigationReads);
app.selectTask(taskId); await tick();
review = task.inventoryReview;
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
delayedWindow = defer();
const sessionWindowRead = delayedWindow;
const sessionWindow = app.loadInventoryWindow(review, 12);
const sessionQueued = app.loadInventoryWindow(review, 24);
app.adoptTask({ task_id: taskId, session_id: "4".repeat(32), session_state: "active",
  session_released: false, task_kind: "inventory", request_id: "5".repeat(32) });
assert.equal(task.inventoryReview, review, "new scan preserves old publication");
assert.equal(task.executionStarted, false);
assert.equal(await sessionQueued, null, "session replacement retires its queued viewport callback");
const sessionWindowCount = calls.filter(([name]) => name === "window").length;
delayedWindow = null;
sessionWindowRead.resolve(Promise.reject(new Error("retired session read")));
assert.equal(await sessionWindow, null);
assert.equal(calls.filter(([name]) => name === "window").length, sessionWindowCount);
assert.equal(review.message, null);
retainedDetail.resolve({ ...fixture.detail, view_revision: review.summary.view_revision });
await sessionDetail;
assert.equal(review.detail, null, "changed session invalidates old details");
task.sessionState = "completed";
task.sessionReleased = true;
task.requestId = review.summary.request_id;
const acknowledgedRow = fixture.views.acknowledged.window.rows.find((row) => row.row_id === "2");
review.detail = { row: acknowledgedRow, state: "current", response: null };
delayedVisibility = defer();
const restoreOriginal = app.runInventoryAction(review, "restore", acknowledgedRow.node_id);
const restoreCall = calls.findLast(([name]) => name === "restore");
assert.deepEqual(restoreCall.slice(1, 3), [taskId, task.requestId]);
assert.equal(restoreCall[4], review.summary.view_revision);
assert.equal(restoreCall[5], acknowledgedRow.node_id);
assert.equal(task.inventoryAction.pending, true);
await app.checkInventoryOutcome(task);
assert.equal(observedChecks, 1);
assert.equal(calls.filter(([name]) => name === "restore").length, 1, "Check cannot submit again");
app.showSettings();
const restoreResult = { task_id: taskId, request_id: task.requestId, action: "restore",
  expected_revision: review.summary.view_revision, total: 3, applied: 1, noop: 0,
  stale: 1, conflict: 1, unresolved_count: 0, disposition: "completed" };
delayedVisibility.resolve(restoreResult);
await restoreOriginal;
delayedVisibility = null;
assert.equal(task.inventoryAction.pending, false);
assert.match(task.inventoryAction.message, /1 stale, 1 conflicted, 0 unresolved/);
assert.equal(task.inventoryViewUnconfirmed, true, "navigation retains result before view recovery");
delayedOpen = defer();
const failedVisibilityReload = delayedOpen;
app.selectTask(taskId); await tick();
failedVisibilityReload.resolve(Promise.reject(new Error("projection unavailable")));
await tick();
assert.equal(task.inventoryReview, review, "failed post-effect rebuild keeps prior publication");
assert.equal(task.inventoryViewUnconfirmed, true);
delayedOpen = null;
await app.loadInventoryReview(task, true);
review = task.inventoryReview;
assert.equal(task.inventoryViewUnconfirmed, false);
review.detail = { row: acknowledgedRow, state: "current", response: null };
await app.runInventoryAction(review, "acknowledge", acknowledgedRow.node_id);
assert.match(task.inventoryAction.message, /1 applied, 0 already set, 1 stale, 0 conflicted, 1 unresolved/);
review = task.inventoryReview;
task.requestId = "5".repeat(32);
task.inventoryViewUnconfirmed = true;
review.detail = { row: acknowledgedRow, state: "current", response: null };
const priorRestoreCount = calls.filter(([name]) => name === "restore").length;
await app.runInventoryAction(review, "restore", acknowledgedRow.node_id);
assert.equal(calls.filter(([name]) => name === "restore").length, priorRestoreCount,
  "dirty prior publication cannot admit fresh visibility");
refuseRefresh = true;
await app.runInventoryAction(review, "refresh", null);
assert.match(task.inventoryAction.message, /Close a task before trying again/);
refuseRefresh = false;
const previousDrainCount = drains.length;
await app.runInventoryAction(task.inventoryReview, "refresh", null);
const refreshCall = calls.findLast(([name]) => name === "refresh");
assert.equal(refreshCall[2], "5".repeat(32), "Refresh uses current request with prior publication");
assert.equal(task.requestId, "8".repeat(32));
assert.equal(drains.length, previousDrainCount + 1, "new same-task session attaches its own drain");
assert.equal(task.inventoryReview.summary.request_id, review.summary.request_id,
  "Refresh retains prior complete publication while scanning");
const originalListTasks = globalThis.inventoryHarness.listTasks;
for (const observation of ["failed", "stale"]) {
  const oldSnapshot = { task_id: taskId, session_id: (observation === "failed" ? "9" : "a").repeat(32),
    session_state: "completed", session_released: true, task_kind: "inventory",
    request_id: fixture.views.default.summary.request_id };
  app.adoptTask(oldSnapshot);
  taskSnapshot = oldSnapshot;
  await tick();
  const retainedPublication = task.inventoryReview;
  const oldList = defer();
  let olderRead;
  if (observation === "failed") {
    globalThis.inventoryHarness.listTasks = () => Promise.reject(new Error("list transport unavailable"));
  } else {
    let reads = 0;
    globalThis.inventoryHarness.listTasks = () => ++reads === 1 ? oldList.promise : originalListTasks();
    olderRead = app.refreshTasks();
  }
  const beforeDrains = drains.length;
  const beforeStarts = calls.filter(([name]) => name === "refresh").length;
  await app.runInventoryAction(retainedPublication, "refresh", null);
  if (olderRead !== undefined) {
    oldList.resolve({ tasks: [oldSnapshot] });
    await olderRead;
    await tick();
  }
  assert.equal(task.sessionId, "7".repeat(32), `Refresh retains admitted identity after ${observation} task-list observation`);
  assert.equal(task.requestId, "8".repeat(32));
  assert.equal(task.sessionState, "active");
  assert.equal(task.sessionReleased, false);
  assert.equal(drains.length, beforeDrains + 1, "Refresh attaches only its admitted drain");
  assert.equal(drains.at(-1)[1], task.sessionId);
  assert.ok(stoppedDrains.includes(oldSnapshot.session_id), "the prior session drain is retired");
  assert.equal(task.inventoryReview, retainedPublication, "observation failure retains the prior complete publication");
  assert.equal(task.inventoryAction.pending, false);
  assert.equal(task.inventoryAction.message, null, "admitted Refresh leaves progress feedback to current scan status");
  assert.equal(calls.filter(([name]) => name === "refresh").length, beforeStarts + 1, "task-list recovery cannot repeat Refresh");
  globalThis.inventoryHarness.listTasks = originalListTasks;
}

// A task-list observation and terminal drain can beat the original start reply.
app.adoptTask({ task_id: taskId, session_id: "b".repeat(32), session_state: "completed",
  session_released: true, task_kind: "inventory", request_id: fixture.views.default.summary.request_id });
delayedRefresh = defer();
const lateStart = app.runInventoryAction(task.inventoryReview, "refresh", null);
await app.refreshTasks();
const observedDrain = drains.at(-1);
observedDrain[2]({ update_type: "record" }, {
  session_state: "completed", phase: "inventory", active_item: null,
  presentation: { item_percent: null }, control_state: "running",
});
observedDrain[5](taskId, task.sessionId);
await tick();
assert.equal(task.sessionState, "completed");
assert.equal(task.sessionReleased, true);
const beforeLateReplyDrains = drains.length;
const staleObservation = defer();
globalThis.inventoryHarness.listTasks = () => staleObservation.promise;
const beforeLateReplyRead = app.refreshTasks();
globalThis.inventoryHarness.listTasks = () => Promise.reject(new Error("list transport unavailable"));
delayedRefresh.resolve({ task_id: taskId, session_id: task.sessionId, request_id: task.requestId });
await lateStart;
// Keep the replacement observation pending so it cannot repair a regressed state.
globalThis.inventoryHarness.listTasks = () => defer().promise;
staleObservation.resolve({ tasks: [taskSnapshot] });
await beforeLateReplyRead;
assert.equal(task.sessionState, "completed", "late same-session admission cannot regress observed completion");
assert.equal(task.sessionReleased, true, "late same-session admission preserves observed release");
assert.equal(drains.length, beforeLateReplyDrains, "late same-session admission keeps its observed drain");
assert.equal(task.inventoryAction.message, null, "late admission cannot promise a result after completion");
delayedRefresh = null;
globalThis.inventoryHarness.listTasks = originalListTasks;

// A refused scan with no fresh location details cannot be repaired by a view reload.
app.adoptTask({ task_id: taskId, session_id: "c".repeat(32), session_state: "refused",
  session_released: true, task_kind: "inventory", request_id: "d".repeat(32) });
const retainedBeforeRefusal = task.inventoryReview;
delayedOpen = defer();
const refusedOpen = app.loadInventoryReview(task, true);
delayedOpen.resolve(Promise.reject(Object.assign(new Error("details unavailable"), { code: "task_unavailable" })));
await refusedOpen;
assert.equal(task.inventoryReview, retainedBeforeRefusal);
assert.match(task.inventoryError, /[Cc]heck.*location.*[Rr]econnect.*Refresh/);
assert.doesNotMatch(task.inventoryError, /Reload/);
assert.equal(task.inventoryAction.message, null, "refused scan retains no pending-result promise");
delayedOpen = defer();
const transportFailedOpen = app.loadInventoryReview(task, true);
delayedOpen.resolve(Promise.reject(new Error("transport unavailable")));
await transportFailedOpen;
assert.match(task.inventoryError, /Reload/, "transport failure alone retains view retry guidance");
delayedOpen = null;

review = task.inventoryReview;
delayedDetail = defer();
const closeDetail = app.readInventoryDetail(review, real.node_id);
const retainedCloseDetail = delayedDetail;
delayedWindow = defer();
const closeWindowRead = delayedWindow;
const beforeCloseReads = calls.filter(([name]) => name === "window").length;
const closeWindow = app.loadInventoryWindow(review, 12);
const closeQueued = app.loadInventoryWindow(review, 24);
const closeReads = calls.filter(([name]) => name === "window").length;
assert.equal(closeReads, beforeCloseReads + 1, "close witness holds a current viewport bridge read");
await app.closeRetainedTask(taskId);
assert.equal(app.tasks.has(taskId), false);
assert.equal(await closeQueued, null);
delayedWindow = null;
closeWindowRead.resolve(Promise.reject(new Error("retired closed-task window")));
assert.equal(await closeWindow, null);
assert.equal(calls.filter(([name]) => name === "window").length, closeReads);
retainedCloseDetail.resolve({ ...fixture.detail, view_revision: review.summary.view_revision });
await closeDetail;
assert.equal(review.detail, null, "Close invalidates outstanding details");
assert.ok(renders.some((value) => value === task));
assert.equal(typeof globalThis.inventoryCallbacks.onReload, "function");
process.stdout.write("ok\n");
