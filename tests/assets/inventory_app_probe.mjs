import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { assertSameNode } from "./fake_dom_assertions.mjs";

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
const inventoryOpenRequests = new Map();
let delayedDetail = null, delayedWindow = null, delayedView = null, delayedOpen = null, delayedVisibility = null;
let taskSnapshot = null, observedChecks = 0, refuseRefresh = false, delayedRefresh = null;
let refuseIntegrityStart = false;
let delayedIntegrityStart = null, integrityStartChecks = 0;
let delayedSelection = null, selectionDisposition = "current", selectedFileCount = fixture.views.default.summary.selected_file_count;
let executionStartResult = null;
let planSummaryResponse = null, planWindowResponse = null, delayedPlanOpen = null;
let viewRevision = 0, query = "";
const summary = () => ({ ...fixture.views.default.summary, view_revision: viewRevision, search_query: query,
  selected_file_count:selectedFileCount,
  hidden_selected_file_count:Math.min(fixture.views.default.summary.hidden_selected_file_count, selectedFileCount),
  selection:selectedFileCount === 0 ? "none"
    : selectedFileCount === fixture.views.default.summary.selectable_file_count ? "all" : "partial" });
const windowResponse = (revision, offset) => ({ ...fixture.views.default.window, view_revision: revision, offset });
const defer = () => {
  let resolve, reject;
  const promise = new Promise((accept, refuse) => { resolve = accept; reject = refuse; });
  return { resolve, reject, promise };
};
globalThis.inventoryHarness = {
  openPlanView(taskId) {
    calls.push(["plan-open", taskId]);
    return delayedPlanOpen?.promise ?? Promise.resolve(planSummaryResponse);
  },
  getPlanWindow(taskId, revision, offset, limit) {
    calls.push(["plan-window", taskId, revision, offset, limit]);
    return Promise.resolve(planWindowResponse);
  },
  getExecutionDetail() { throw new Error("unexpected execution detail"); },
  mutateInventoryHighlight() { throw new Error("unexpected inventory highlight"); },
  setInventoryHighlightedSelection() { throw new Error("unexpected highlighted selection"); },
  openInventoryView(taskId) { calls.push(["open", taskId]); return delayedOpen?.promise ?? Promise.resolve({
    ...summary(), task_id:taskId, request_id:inventoryOpenRequests.get(taskId) ?? summary().request_id,
  }); },
  getInventoryWindow(taskId, revision, offset, limit) {
    calls.push(["window", taskId, revision, offset, limit]);
    return delayedWindow?.promise ?? Promise.resolve(windowResponse(revision, offset));
  },
  getInventoryItemAnchor() { throw new Error("unexpected inventory anchor"); },
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
    taskSnapshot = { ...taskSnapshot, task_id: taskId, session_id: "7".repeat(32),
      session_state: "active", session_released: false, request_id: "8".repeat(32),
      session_kind: "inventory" };
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
  setInventorySelection(taskId, requestId, revision, nodeId, selected) {
    calls.push(["select", taskId, requestId, revision, nodeId, selected]);
    if (delayedSelection !== null) return delayedSelection.promise;
    if (selectionDisposition !== "conflict") {
      selectedFileCount = selected ? fixture.views.default.summary.selectable_file_count : 0;
      viewRevision += 1;
    }
    return Promise.resolve({...summary(), task_id:taskId, request_id:requestId,
      disposition:selectionDisposition});
  },
  startInventoryIntegrity(taskId, requestId, commandId, revision, mode, accepted, onDelayed, scope) {
    calls.push(["integrity-start", taskId, requestId, commandId, revision, mode, accepted, scope]);
    if (refuseIntegrityStart) return Promise.reject(new Error("integrity refused"));
    taskSnapshot = {task_id:taskId, session_id:"d".repeat(32), session_state:"active",
      session_released:false, task_kind:taskSnapshot?.task_id === taskId ? taskSnapshot.task_kind : "inventory",
      request_id:"e".repeat(32), plan_request_id:taskSnapshot?.task_id === taskId
        ? taskSnapshot.plan_request_id : null, session_kind:mode};
    const result = {task_id:taskId, session_id:taskSnapshot.session_id,
      request_id:taskSnapshot.request_id};
    if (delayedIntegrityStart !== null) {
      const held = delayedIntegrityStart;
      onDelayed({canCheck:true, checking:false, message:"Check original integrity start",
        check() { integrityStartChecks += 1; held.resolve(result); return held.promise; }});
      return held.promise;
    }
    return Promise.resolve(result);
  },
  controlIntegrity(taskId, sessionId, action) {
    calls.push(["integrity-control", taskId, sessionId, action]);
    return Promise.resolve({session_id:sessionId, action, accepted:true,
      before:action === "resume" ? "paused" : "running",
      after:action === "pause" ? "pausing" : action === "cancel" ? "canceling" : "running",
      detail:null});
  },
  startExecution(taskId, requestId, revision, acknowledged) {
    calls.push(["execution-start", taskId, requestId, revision, acknowledged]);
    if (executionStartResult === null) return Promise.reject(new Error("execution start unavailable"));
    taskSnapshot = {task_id:taskId, session_id:executionStartResult.session_id,
      session_state:"active", session_released:false, task_kind:"sync-plan",
      request_id:executionStartResult.request_id, plan_request_id:requestId,
      session_kind:"sync-execution"};
    return Promise.resolve({...executionStartResult, task_id:taskId});
  },
  controlExecution(taskId, sessionId, action) {
    calls.push(["manual-control", taskId, sessionId, action]);
    return Promise.resolve({session_id:sessionId, action, accepted:true,
      before:action === "resume" ? "paused" : "running",
      after:action === "pause" ? "pausing" : action === "cancel" ? "canceling" : "running",
      detail:null});
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
  "./execution_confirmation.js": url(`export const createExecutionConfirmation = (...factory) => ({
    element: new HTMLElement('dialog'), show(request) { globalThis.inventoryConfirmations.push({factory, request}); }
  });`),
  "./rail.js": url("export const createTaskRail = () => ({ element: new HTMLElement('nav'), render() {} });"),
  "./panels.js": url(`export const createWorkPanel = (setup, plan, settings, inventory) => {
    globalThis.inventoryCallbacks = inventory;
    return { element: new HTMLElement('section'), render(task) { globalThis.inventoryRenders.push(task); }, renderSettings() {} };
  };`),
};
globalThis.inventoryRenders = renders;
globalThis.inventoryConfirmations = [];
for (const [key, value] of Object.entries(replacements)) source = source.replace(key, value);
source += "\nexport { adoptTask, selectTask, acceptTaskUpdate, acceptTaskRelease, loadPlanReview, observeOriginalExecution, loadInventoryReview, changeInventoryView, loadInventoryWindow, readInventoryNavigationWindow, readInventoryDetail, readExecutionDetail, runInventoryAction, changeInventorySelection, startInventoryIntegrityAction, switchTaskPane, controlInventoryIntegrity, checkInventoryOutcome, closeRetainedTask, showSettings, refreshTasks, executeReviewedPlan, tasks, queueRowHighlight, interruptPlanHighlight, refreshInventoryOverlay };";
const app = await import(url(source));
const taskId = fixture.views.default.summary.task_id;
const sessionId = "3".repeat(32);
const task = app.adoptTask({ task_id: taskId, session_id: sessionId, session_state: "active",
  session_released: false, task_kind: "inventory", request_id: fixture.views.default.summary.request_id,
  plan_request_id: null, session_kind: "inventory" });
taskSnapshot = { task_id: taskId, session_id: sessionId, session_state: "active",
  session_released: false, task_kind: "inventory", request_id: task.requestId,
  plan_request_id: null, session_kind: "inventory" };
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
globalThis.inventoryCallbacks.onWindowCancelled(staleReview);
assert.equal(calls.filter(([name]) => name === "window").length, replacementCalls);
priorPublicationRead.resolve(windowResponse(0, 12));
assert.equal(await priorPublicationWindow, null);
assert.equal((await replacementWindow).offset, 48);
assert.equal(calls.filter(([name]) => name === "window").length, replacementCalls + 1);

// Renderer retirement cancels its exact viewport job, not a same-review
// highlight endpoint queued behind the physical read.
delayedWindow = defer();
const viewportRead = delayedWindow;
const retiredViewport = app.loadInventoryWindow(review, 12);
const navigationRevision = review.summary.view_revision;
const endpointRead = app.readInventoryNavigationWindow(review,
  () => task.inventoryReview === review && review.summary.view_revision === navigationRevision,
  taskId, navigationRevision, 48, 256);
const endpointCalls = calls.filter(([name]) => name === "window").length;
globalThis.inventoryCallbacks.onWindowCancelled(review);
delayedWindow = null;
viewportRead.resolve(windowResponse(navigationRevision, 12));
assert.equal(await retiredViewport, null);
assert.equal((await endpointRead).offset, 48, "viewport cancellation retains the newer endpoint demand");
assert.equal(calls.filter(([name]) => name === "window").length, endpointCalls + 1);

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
  session_released: false, task_kind: "inventory", request_id: "5".repeat(32),
  plan_request_id: null, session_kind: "inventory" });
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
    request_id: fixture.views.default.summary.request_id, plan_request_id: null,
    session_kind: "inventory" };
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
  session_released: true, task_kind: "inventory", request_id: fixture.views.default.summary.request_id,
  plan_request_id: null, session_kind: "inventory" });
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
  session_released: true, task_kind: "inventory", request_id: "d".repeat(32),
  plan_request_id: null, session_kind: "inventory" });
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

const syncTaskId = "task-" + "f".repeat(32);
const syncPlanRequestId = "9".repeat(32);
const syncCurrentRequestId = fixture.views.default.summary.request_id;
taskSnapshot = { task_id: syncTaskId, session_id: "6".repeat(32), session_state: "completed",
  session_released: true, task_kind: "sync-plan", request_id: syncCurrentRequestId,
  plan_request_id: syncPlanRequestId, session_kind: "sync-execution" };
const syncTask = app.adoptTask(taskSnapshot);
syncTask.executionStarted = true;
app.selectTask(syncTaskId);
await tick();
const syncReview = { ...review, summary: { ...review.summary, task_id: syncTaskId,
  request_id: syncCurrentRequestId }, pending: null, message: null };
syncTask.inventoryReview = syncReview;
globalThis.inventoryCallbacks.onPaneChange(syncTask, "verify");
await tick();
await app.runInventoryAction(syncReview, "refresh", null, new HTMLElement("button"));
await tick();
assert.equal(syncTask.taskKind, "sync-plan", "ordinary auxiliary Refresh keeps the sync task kind");
assert.equal(syncTask.planRequestId, syncPlanRequestId,
  "ordinary auxiliary Refresh keeps the original Plan request");
assert.equal(syncTask.requestId, "8".repeat(32), "Refresh adopts the new current request");
assert.equal(syncTask.sessionKind, "inventory", "Refresh identifies the current activity");

// Accepted execution adopts its current request before any task-list refresh.
const executionTaskId = "task-" + "4".repeat(32);
const planRequestId = "1".repeat(32);
const planSessionId = "2".repeat(32);
const executionRequestId = "3".repeat(32);
const executionSessionId = "4".repeat(32);
const planSnapshot = {task_id:executionTaskId, session_id:planSessionId,
  session_state:"completed", session_released:true, task_kind:"sync-plan",
  request_id:planRequestId, plan_request_id:planRequestId, session_kind:"sync-plan"};
const executionTask = app.adoptTask(planSnapshot);
const executionReview = {summary:{task_id:executionTaskId, request_id:planRequestId,
  selection_state:"reviewing", selection_revision:5,
  requires_destructive_confirmation:false, destructive_operation_count:0,
  view_revision:0, highlight_revision:0},
  window:{offset:0, rows:[], execution:null},
  actionRevision:0, pending:null, message:null, follow:null};
executionTask.review = executionReview;
executionTask.reviewSessionId = planSessionId;
app.selectTask(executionTaskId);
await tick();
executionStartResult = {task_id:executionTaskId, request_id:executionRequestId,
  session_id:executionSessionId};
const staleExecutionList = defer();
let executionListReads = 0;
globalThis.inventoryHarness.listTasks = () => ++executionListReads === 1
  ? staleExecutionList.promise : Promise.resolve({tasks:[taskSnapshot]});
const heldExecutionRead = app.refreshTasks();
await app.executeReviewedPlan(executionReview, null);
const pendingExecutionRepair = defer();
globalThis.inventoryHarness.listTasks = () => pendingExecutionRepair.promise;
staleExecutionList.resolve({tasks:[planSnapshot]});
await heldExecutionRead;
await tick();
assert.equal(executionTask.requestId, executionRequestId,
  "accepted execution keeps its current request after an older task-list reply");
assert.equal(executionTask.sessionId, executionSessionId);
assert.equal(executionTask.planRequestId, planRequestId,
  "accepted execution retains the original Plan request independently");
inventoryOpenRequests.set(executionTaskId, executionRequestId);
executionTask.sessionState = "completed";
app.acceptTaskRelease(executionTask, executionSessionId);
await tick();
app.switchTaskPane(executionTask, "verify");
await tick();
globalThis.inventoryHarness.listTasks = () => Promise.reject(new Error("list transport unavailable"));
await app.runInventoryAction(executionTask.inventoryReview, "refresh", null, new HTMLElement("button"));
await tick();
assert.deepEqual(calls.findLast(([name]) => name === "refresh").slice(1, 3),
  [executionTaskId, executionRequestId],
  "immediate Refresh uses the accepted execution request before list recovery");
globalThis.inventoryHarness.listTasks = originalListTasks;
executionStartResult = null;

// Standalone selection, start, control custody, coalesced live results, and stale consent.
const d1TaskId = "task-" + "7".repeat(32);
const d1RequestId = "8".repeat(32);
inventoryOpenRequests.set(d1TaskId, d1RequestId);
const d1Task = app.adoptTask({task_id:d1TaskId, session_id:"9".repeat(32), session_state:"active",
  session_released:false, task_kind:"inventory", request_id:d1RequestId,
  plan_request_id:null, session_kind:"inventory"});
app.selectTask(d1TaskId); await tick();
d1Task.sessionState = "completed";
d1Task.sessionReleased = true;
let d1Review = {...fixture.views.default, summary:{...fixture.views.default.summary,
  task_id:d1TaskId, request_id:d1RequestId}, pending:null, message:null, detail:null,
  queuedSearchQuery:null, actionRevision:0, windowRequestRevision:0, detailRevision:0, scrollTop:19};
d1Task.inventoryReview = d1Review;
const selectionCalls = calls.filter(([name]) => name === "select").length;
delayedSelection = defer();
const unavailableSelection = app.changeInventorySelection(d1Review, null, false);
delayedSelection.resolve(Promise.reject(new Error("selection transport unavailable")));
await unavailableSelection;
delayedSelection = null;
await tick();
assert.equal(calls.filter(([name]) => name === "select").length, selectionCalls + 1,
  "transport recovery never replays a selection gesture");
assert.equal(d1Task.inventoryReview, d1Review,
  "transport uncertainty adopts authoritative state without discarding tree custody");
d1Review = d1Task.inventoryReview;
selectionDisposition = "conflict";
await app.changeInventorySelection(d1Review, null, false);
assert.equal(calls.filter(([name]) => name === "select").length, selectionCalls + 2);
assert.match(d1Review.message, /changed elsewhere/i);
selectionDisposition = "current";
const selectionRevision = d1Review.summary.view_revision;
await app.changeInventorySelection(d1Review, null, true);
assert.equal(calls.filter(([name]) => name === "select").length, selectionCalls + 3);
assert.deepEqual(calls.findLast(([name]) => name === "select").slice(1),
  [d1TaskId, d1RequestId, selectionRevision, null, true]);
assert.equal(d1Review.summary.selected_file_count, d1Review.summary.selectable_file_count);
assert.equal(d1Review.scrollTop, 19, "authoritative selection replacement preserves review scroll custody");
const trigger = new HTMLElement("button");
const startsBefore = calls.filter(([name]) => name === "integrity-start").length;
refuseIntegrityStart = true;
await app.startInventoryIntegrityAction(d1Review, "baseline", trigger);
assert.equal(d1Task.inventoryAction, null, "a settled refusal releases the gesture for a fresh explicit start");
assert.equal(d1Review.message, "Integrity work did not start. Try again when you are ready.");
refuseIntegrityStart = false;
const staleIntegritySnapshot = {task_id:d1TaskId, session_id:d1Task.sessionId,
  session_state:"completed", session_released:true, task_kind:"inventory",
  request_id:d1RequestId, plan_request_id:null, session_kind:"inventory"};
const staleIntegrityList = defer();
let integrityListReads = 0;
globalThis.inventoryHarness.listTasks = () => ++integrityListReads === 1
  ? staleIntegrityList.promise : Promise.resolve({tasks:[taskSnapshot]});
const heldIntegrityRead = app.refreshTasks();
delayedIntegrityStart = defer();
const delayedStart = app.startInventoryIntegrityAction(d1Review, "baseline", trigger);
await tick();
assert.equal(d1Task.inventoryAction.recovery.canCheck, true);
await app.checkInventoryOutcome(d1Task);
await delayedStart;
delayedIntegrityStart = null;
const pendingIntegrityRepair = defer();
globalThis.inventoryHarness.listTasks = () => pendingIntegrityRepair.promise;
staleIntegrityList.resolve({tasks:[staleIntegritySnapshot]});
await heldIntegrityRead;
await tick();
assert.equal(calls.filter(([name]) => name === "integrity-start").length, startsBefore + 2,
  "the owned start attempt does not block its own first submission");
assert.equal(integrityStartChecks, 1);
assert.equal(d1Task.sessionKind, "baseline");
assert.equal(d1Task.sessionState, "active");
assert.equal(d1Task.requestId, "e".repeat(32),
  "accepted ordinary integrity keeps its current request after an older task-list reply");
assert.equal(d1Task.sessionId, "d".repeat(32));
globalThis.inventoryHarness.listTasks = originalListTasks;
const controlsBefore = calls.filter(([name]) => name === "integrity-control").length;
await app.controlInventoryIntegrity(d1Review, "pause");
assert.equal(calls.filter(([name]) => name === "integrity-control").length, controlsBefore + 1);
assert.equal(d1Task.inventoryAction.accepted, true);
await app.controlInventoryIntegrity(d1Review, "pause");
assert.equal(calls.filter(([name]) => name === "integrity-control").length, controlsBefore + 1,
  "an accepted receipt retains custody until an authoritative state update");
delayedWindow = defer();
const overlayReads = calls.filter(([name]) => name === "window").length;
const activeSnapshot = {session_id:d1Task.sessionId, session_state:"active", phase:"baseline",
  active_item:null, control_state:"pausing", presentation:{value:20, determinate:true,
    indeterminate:false, items_done:1, items_total:3, item_percent:null,
    throughput_bytes_per_second:null, eta_seconds:null}, terminal_result:null,
  progress_inconsistent:false};
app.acceptTaskUpdate(d1Task, d1Task.sessionId, {update_type:"state"}, activeSnapshot);
assert.equal(d1Task.inventoryAction, null,
  "the authoritative pausing snapshot releases accepted receipt custody");
assert.equal(d1Task.executionControlState, "pausing");
app.acceptTaskUpdate(d1Task, d1Task.sessionId, {update_type:"progress"},
  {...activeSnapshot, control_state:"paused",
    presentation:{...activeSnapshot.presentation, value:40, items_done:2}});
assert.equal(d1Task.executionControlState, "paused",
  "only the later checkpoint snapshot makes Resume available");
assert.equal(calls.filter(([name]) => name === "window").length, overlayReads + 1,
  "one live overlay read runs while a latest update queues");
const liveOverlay = {request_id:d1Task.requestId, session_id:d1Task.sessionId, mode:"baseline",
  location_id:d1Review.summary.location_id, revision:1, complete:false, gap:true, items:[]};
delayedWindow.resolve({...windowResponse(d1Review.summary.view_revision, d1Review.window.offset),
  integrity:liveOverlay});
delayedWindow = null;
await tick();
assert.equal(calls.filter(([name]) => name === "window").length, overlayReads + 2,
  "the coalesced reader performs only the latest pending overlay read");

d1Task.sessionState = "completed";
d1Task.sessionReleased = true;
d1Task.requestId = "a".repeat(32);
d1Task.inventoryReview = {...d1Review, summary:{...d1Review.summary, request_id:d1Task.requestId,
  view_revision:d1Review.summary.view_revision + 1, selected_file_count:3,
  selectable_file_count:3, hidden_selected_file_count:2, selection:"all"}, pending:null,
  message:null, actionRevision:0};
const currentD1Review = d1Task.inventoryReview;
await app.startInventoryIntegrityAction(currentD1Review, "rebaseline", trigger);
const confirmation = globalThis.inventoryConfirmations.at(-1).request;
assert.equal(confirmation.destructiveOperationCount, 3);
assert.match(confirmation.countDetail, /2 hidden/);
currentD1Review.summary = {...currentD1Review.summary,
  view_revision:currentD1Review.summary.view_revision + 1};
confirmation.onConfirm();
await tick();
assert.equal(calls.filter(([name]) => name === "integrity-start").length, startsBefore + 2,
  "changed revision invalidates Rebaseline consent without submitting or replaying");

function attachReleasedExecutionTask(taskId, originalSessionId, currentSessionId, requestId, headline = "success") {
  let owner = app.adoptTask({task_id:taskId, session_id:originalSessionId,
    session_state:"completed", session_released:true, task_kind:"sync-plan",
    request_id:requestId, plan_request_id:requestId, session_kind:"sync-execution"});
  owner.executionStarted = true;
  owner.executionSessionState = "completed";
  owner.reviewSessionId = originalSessionId;
  owner.review = {summary:{task_id:taskId, request_id:requestId, highlight_focus_node_id:null},
    window:{execution:{session_id:originalSessionId, execution_revision:7,
      has_successful_copied_files:true,
      result:{headline, disposition:"ran", recording:headline === "degraded" ? "degraded" : "ok"}}}};
  app.observeOriginalExecution(owner, requestId, owner.review.window.execution);
  owner.inventoryReview = {...currentD1Review,
    summary:{...currentD1Review.summary, task_id:taskId, request_id:requestId,
      selected_file_count:1, selectable_file_count:3, hidden_selected_file_count:0,
      selection:"partial"}, pending:null, message:null, actionRevision:0};
  owner = app.adoptTask({task_id:taskId, session_id:currentSessionId,
    session_state:"completed", session_released:true, task_kind:"sync-plan",
    request_id:requestId, plan_request_id:requestId, session_kind:"inventory"});
  taskSnapshot = {task_id:taskId, session_id:currentSessionId, session_state:"completed",
    session_released:true, task_kind:"sync-plan", request_id:requestId,
    plan_request_id:requestId, session_kind:"inventory"};
  return owner;
}

const copiedTask = attachReleasedExecutionTask("task-" + "1".repeat(32),
  "2".repeat(32), "3".repeat(32), "4".repeat(32));
app.selectTask(copiedTask.taskId);
app.switchTaskPane(copiedTask, "verify"); await tick();
const copiedReview = copiedTask.inventoryReview;
const copiedFact = copiedTask.originalExecutionFact;
app.observeOriginalExecution(copiedTask, copiedTask.planRequestId,
  {...copiedFact.execution, execution_revision:8, has_successful_copied_files:false});
const knownEmptyBase = calls.filter(([name]) => name === "integrity-start").length;
await app.startInventoryIntegrityAction(copiedReview, "verify", trigger, "copied");
assert.equal(calls.filter(([name]) => name === "integrity-start").length, knownEmptyBase,
  "a known-empty original execution does not allocate a new start command");
app.observeOriginalExecution(copiedTask, copiedTask.planRequestId, copiedFact.execution);
app.observeOriginalExecution(copiedTask, "foreign-plan",
  {...copiedFact.execution, execution_revision:9});
app.observeOriginalExecution(copiedTask, copiedTask.planRequestId,
  {...copiedFact.execution, session_id:"foreign-execution", execution_revision:9});
assert.equal(copiedTask.originalExecutionFact.execution.has_successful_copied_files, false,
  "older or foreign facts cannot re-enable a known-empty action");
app.observeOriginalExecution(copiedTask, copiedTask.planRequestId,
  {...copiedFact.execution, execution_revision:9, has_successful_copied_files:null});
copiedReview.summary = {...copiedReview.summary, selected_file_count:0, hidden_selected_file_count:0};
const retainedOriginal = copiedTask.originalExecutionFact;
const copiedStartBase = calls.filter(([name]) => name === "integrity-start").length;
delayedIntegrityStart = defer();
const copiedStart = app.startInventoryIntegrityAction(copiedReview, "verify", trigger, "copied");
await tick();
await app.startInventoryIntegrityAction(copiedReview, "verify", trigger, "copied");
app.switchTaskPane(copiedTask, "plan");
delayedIntegrityStart.resolve({task_id:copiedTask.taskId, session_id:"d".repeat(32), request_id:"e".repeat(32)});
await copiedStart; delayedIntegrityStart = null;
assert.equal(calls.filter(([name]) => name === "integrity-start").length, copiedStartBase + 1,
  "unknown copied truth preserves server admission and a double gesture starts one command");
assert.deepEqual(calls.findLast(([name]) => name === "integrity-start").slice(5), ["verify", false, "copied"]);
assert.equal(copiedTask.sessionKind, "verify");
assert.equal(copiedTask.originalExecutionFact, retainedOriginal);
assert.equal(drains.at(-1)[1], copiedTask.sessionId,
  "ordinary copied session is adopted after returning to Plan");
app.switchTaskPane(copiedTask, "verify");
const controlsBase = calls.filter(([name]) => name === "integrity-control").length;
await app.controlInventoryIntegrity(copiedTask.inventoryReview, "pause");
assert.equal(calls.filter(([name]) => name === "integrity-control").length, controlsBase + 1);
copiedTask.sessionState = "completed"; copiedTask.sessionReleased = true;
copiedTask.inventoryAction = null;
copiedTask.inventoryReview.summary = {...copiedTask.inventoryReview.summary, request_id:copiedTask.requestId};
const selectedStartBase = calls.filter(([name]) => name === "integrity-start").length;
await app.startInventoryIntegrityAction(copiedTask.inventoryReview, "verify", trigger);
assert.equal(calls.filter(([name]) => name === "integrity-start").length, selectedStartBase,
  "ordinary selected scope still requires selected files");
copiedTask.inventoryReview.summary = {...copiedTask.inventoryReview.summary, selected_file_count:1};
await app.startInventoryIntegrityAction(copiedTask.inventoryReview, "verify", trigger);
assert.equal(calls.findLast(([name]) => name === "integrity-start").at(-1), "selected");

// Auxiliary scans supersede current evidence without changing execution truth.
const cacheOwner = attachReleasedExecutionTask("task-" + "5".repeat(32),
  "6".repeat(32), "7".repeat(32), "8".repeat(32));
const cacheReview = cacheOwner.review;
const cacheRow = {node_id:"cached-node", operation_id:"9".repeat(32)};
Object.assign(cacheReview, {actionRevision:0, detailRevision:0, scrollTop:512 * 24, follow:{enabled:false, sentinel:true},
  planDetail:{nodeId:cacheRow.node_id, actionRevision:0, viewRevision:0}, executionDetail:null});
Object.assign(cacheReview.summary, {view_revision:0, highlight_revision:0,
  highlight_focus_node_id:cacheRow.node_id, selection_revision:7});
Object.assign(cacheReview.window, {offset:512, rows:[cacheRow], disposition:"current",
  view_revision:0, highlight_revision:0});
const cacheSummary = cacheReview.summary, cacheFollow = cacheReview.follow;
const cacheFact = cacheOwner.originalExecutionFact;
const priorPlanWindow = globalThis.inventoryHarness.getPlanWindow;
const staleDetail = defer(), freshWindow = defer();
let evidenceReads = 0;
globalThis.inventoryHarness.getExecutionDetail = () => ++evidenceReads === 1
  ? staleDetail.promise : Promise.resolve({disposition:"current", evidence:{state:"superseded", content:null}});
globalThis.inventoryHarness.getPlanWindow = (...args) => {
  calls.push(["plan-window", ...args]); return freshWindow.promise;
};
app.selectTask(cacheOwner.taskId); await tick();
const staleDetailWork = app.readExecutionDetail(cacheReview, cacheRow);
cacheOwner.sessionState = "completed";
app.acceptTaskRelease(cacheOwner, cacheOwner.sessionId);
assert.equal(cacheReview.executionDetail, null, "scan release retires pending evidence detail");
staleDetail.resolve({disposition:"current", evidence:{state:"recorded-copy", content:{digest:"old"}}});
await staleDetailWork;
assert.equal(cacheReview.executionDetail, null, "a retired response cannot reinstall the old digest");
freshWindow.resolve({...cacheReview.window}); await tick();
assert.equal(cacheReview.executionDetail.response.evidence.state, "superseded");
assert.equal(calls.findLast(([name]) => name === "plan-window")[3], 512);
assert.equal(cacheReview.summary, cacheSummary);
assert.equal(cacheReview.follow, cacheFollow);
assert.equal(cacheReview.scrollTop, 512 * 24);
assert.equal(cacheOwner.originalExecutionFact, cacheFact);
globalThis.inventoryHarness.getPlanWindow = priorPlanWindow;
planWindowResponse = {...cacheReview.window};
for (const kind of ["inventory", "verify"]) {
  app.switchTaskPane(cacheOwner, "verify"); await tick();
  cacheOwner.sessionKind = kind;
  const beforeReturnReads = calls.filter(([name]) => name === "plan-window").length;
  app.acceptTaskRelease(cacheOwner, cacheOwner.sessionId);
  assert.equal(cacheOwner.executionWindowDirty, true);
  assert.equal(cacheReview.executionDetail, null);
  await tick();
  assert.equal(calls.filter(([name]) => name === "plan-window").length, beforeReturnReads,
    "hidden Plan records dirty demand without background reads");
  app.switchTaskPane(cacheOwner, "plan"); await tick();
  assert.equal(cacheOwner.executionWindowDirty, false);
  assert.equal(cacheReview.executionDetail.response.evidence.state, "superseded");
  assert.equal(cacheReview.window.offset, 512);
  assert.equal(cacheReview.summary, cacheSummary);
  assert.equal(cacheReview.follow, cacheFollow);
  assert.equal(cacheOwner.originalExecutionFact, cacheFact);
}

// The real Inventory app queue shares mutation custody and read admission with scrolling.
const alignedId = "task-0123456789abcdef0123456789abcdef";
const alignedTask = app.adoptTask({task_id:alignedId, session_id:"0".repeat(32),
  session_state:"completed", session_released:true, task_kind:"inventory",
  request_id:fixture.views.maximum.summary.request_id, plan_request_id:null, session_kind:"inventory"});
app.selectTask(alignedId); await tick();
const completeRows = [...new Map([...fixture.views.maximum.window.rows, ...fixture.views.middle.window.rows]
  .map(row => [row.visible_index, row])).values()];
const endpoint = index => completeRows.find(row => row.visible_index === index).node_id;
let authoritativeHighlight = {...fixture.views.maximum.summary, task_id:alignedId,
  highlight_anchor_node_id:endpoint(250), highlight_focus_node_id:endpoint(250),
  highlight_focus_visible_index:250, highlighted_count:1};
const alignedWindow = (offset, summary = authoritativeHighlight) => ({...fixture.views.maximum.window,
  highlight_revision:summary.highlight_revision, offset,
  rows:completeRows.filter(row => row.visible_index >= offset && row.visible_index < offset + 256)
    .map(row => ({...row, highlighted:row.node_id === summary.highlight_focus_node_id}))});
const alignedReview = {summary:authoritativeHighlight, window:alignedWindow(0), pending:null, message:null,
  queuedSearchQuery:null, actionRevision:0, windowRequestRevision:0, detailRevision:0, detail:null,
  scrollTop:250*24, highlightQueue:Promise.resolve()};
alignedTask.inventoryReview = alignedReview;
assert.equal(alignedTask.inventoryLoading, false, "the highlight fixture starts with a released published view");
const rowMutations = [], rowReads = [], rangeSelections = [];
let heldHighlight = null, heldOverlay = null;
globalThis.inventoryHarness.openInventoryView = () => Promise.resolve(authoritativeHighlight);
globalThis.inventoryHarness.getInventoryWindow = (taskId, revision, offset, limit) => {
  rowReads.push({taskId, revision, offset, limit});
  if (heldOverlay !== null) {
    const held = heldOverlay;
    heldOverlay = null;
    return held.promise;
  }
  return Promise.resolve(alignedWindow(offset));
};
globalThis.inventoryHarness.mutateInventoryHighlight = (taskId, view, highlight, gesture, nodeId, delayed) => {
  rowMutations.push({taskId, view, highlight, gesture, nodeId, delayed});
  const index = gesture.startsWith("move_")
    ? authoritativeHighlight.highlight_focus_visible_index + (gesture.startsWith("move_down") ? 1 : -1)
    : completeRows.find(row => row.node_id === nodeId).visible_index;
  authoritativeHighlight = {...authoritativeHighlight, highlight_revision:highlight+1,
    highlight_focus_node_id:endpoint(index), highlight_focus_visible_index:index,
    highlight_anchor_node_id:gesture === "replace" ? endpoint(index) : authoritativeHighlight.highlight_anchor_node_id};
  if (heldHighlight !== null) {
    heldHighlight.receipt = authoritativeHighlight;
    return heldHighlight.promise;
  }
  return Promise.resolve(authoritativeHighlight);
};
globalThis.inventoryHarness.setInventoryHighlightedSelection = (taskId, requestId, revision, highlight, selected) => {
  rangeSelections.push({taskId, requestId, revision, highlight, selected});
  return Promise.resolve({...authoritativeHighlight, disposition:highlight === authoritativeHighlight.highlight_revision
    ? "current" : "conflict"});
};
heldHighlight = defer();
let highlightWork = app.queueRowHighlight(alignedReview, "move_down", null, true);
await tick();
assert.equal(rowMutations.length, 1);
for (let i=0; i<20; i+=1) app.queueRowHighlight(alignedReview, "move_down", null, true);
const firstReceipt = heldHighlight.receipt;
heldHighlight.resolve(firstReceipt); heldHighlight = null;
await highlightWork;
assert.equal(rowMutations.length, 2, "held repeated arrows submit only the final endpoint after the admitted step");
assert.equal(rowMutations[1].gesture, "replace");
assert.equal(rowMutations[1].nodeId, endpoint(271));
assert.equal(alignedReview.summary.highlight_focus_visible_index, 271);
assert.equal(alignedReview.window.offset, 239, "off-window highlight retains 32 leading rows");
assert.ok(rowReads.every(read => read.limit === 256));

heldHighlight = defer();
highlightWork = app.queueRowHighlight(alignedReview, "move_down", null, true);
await tick();
globalThis.inventoryCallbacks.onInterrupt(alignedReview); // The renderer's Tab boundary.
const interruptedReceipt = heldHighlight.receipt;
heldHighlight.resolve(interruptedReceipt); heldHighlight = null;
await highlightWork;
assert.equal(alignedReview.summary.highlight_revision, 2, "retired keyboard receipt cannot paint");
assert.equal(alignedReview.highlightReceipt.highlight_revision, 3, "admitted mutation retains custody");
assert.equal(alignedReview.keyboardRevealWindow, null);
const reconciled = await app.loadInventoryWindow(alignedReview, 239);
alignedReview.window = reconciled;
assert.equal(alignedReview.summary.highlight_revision, 3, "fresh scroll reconciles the retained receipt");
assert.equal(alignedReview.keyboardRevealWindow, null, "receipt reconciliation cannot reclaim keyboard focus");

heldHighlight = defer();
highlightWork = app.queueRowHighlight(alignedReview, "move_down", null, true);
await tick();
const selectedAt = alignedReview.summary.highlight_revision;
const rangeWork = app.changeInventorySelection(alignedReview, null, true, true);
heldHighlight.resolve(heldHighlight.receipt); heldHighlight = null;
await highlightWork; await rangeWork;
assert.equal(rangeSelections.at(-1).highlight, selectedAt, "range checkbox retains its displayed highlight revision");
assert.equal(alignedReview.summary.selected_file_count, 0);
assert.match(alignedReview.message, /Review the current highlight, then select again/);

alignedTask.sessionKind = "verify";
alignedTask.sessionState = "active";
alignedTask.sessionReleased = false;
const staleOverlay = alignedWindow(239);
heldOverlay = defer();
const overlayReceipt = heldOverlay;
const overlayWork = app.refreshInventoryOverlay(alignedTask);
await tick();
await app.queueRowHighlight(alignedReview, "replace", endpoint(279), true);
overlayReceipt.resolve(staleOverlay);
await overlayWork;
assert.equal(alignedReview.window.highlight_revision, authoritativeHighlight.highlight_revision,
  "a held live-overlay response cannot overwrite newer highlight flags");
assert.equal(alignedReview.window.rows.find(row => row.node_id === endpoint(279)).highlighted, true);
assert.equal(alignedReview.keyboardRevealWindow, null);
alignedReview.window = alignedWindow(0);
heldOverlay = defer();
const oldOffsetReceipt = heldOverlay;
const oldOffsetWork = app.refreshInventoryOverlay(alignedTask);
await tick();
alignedReview.window = await app.loadInventoryWindow(alignedReview, 239);
oldOffsetReceipt.resolve(alignedWindow(0));
await oldOffsetWork;
assert.equal(alignedReview.window.offset, 239, "a held overlay cannot roll the foreground viewport back");
assert.equal(rowReads.at(-1).offset, 239, "the only dirty update is reread at the current foreground offset");

heldOverlay = defer();
const finalOverlayReceipt = heldOverlay;
const finalOverlaySnapshot = alignedWindow(239);
const finalOverlayWork = app.refreshInventoryOverlay(alignedTask);
await tick();
heldHighlight = defer();
highlightWork = app.queueRowHighlight(alignedReview, "move_down", null, true);
await tick();
globalThis.inventoryCallbacks.onInterrupt(alignedReview);
finalOverlayReceipt.resolve(finalOverlaySnapshot);
await finalOverlayWork;
const readsWhileHeld = rowReads.length;
heldHighlight.resolve(heldHighlight.receipt); heldHighlight = null;
await highlightWork; await tick();
assert.ok(rowReads.length > readsWhileHeld, "a final dirty overlay waits for admitted foreground mutation settlement");
assert.equal(alignedReview.window.highlight_revision, authoritativeHighlight.highlight_revision);
assert.equal(alignedReview.keyboardRevealWindow, null, "deferred live refresh cannot revive interrupted keyboard reveal");

// An independently invalidated result read remains needed even when its window
// or detail rejects after the foreground reader has already settled.
let overlayFactRevision = 0;
const overlayFacts = () => ({request_id:alignedTask.requestId, session_id:alignedTask.sessionId,
  mode:"verify", location_id:alignedReview.summary.location_id, revision:overlayFactRevision,
  complete:true, gap:false, items:[]});
const resultWindow = offset => ({...alignedWindow(offset), integrity:overlayFacts()});
let rejectedWindow = null, rejectedDetail = null, failNextWindow = false;
globalThis.inventoryHarness.getInventoryWindow = (taskId, revision, offset, limit) => {
  rowReads.push({taskId, revision, offset, limit});
  if (rejectedWindow !== null) {
    const held = rejectedWindow; rejectedWindow = null; return held.promise;
  }
  if (failNextWindow) {
    failNextWindow = false; return Promise.reject(new Error("result read unavailable"));
  }
  return Promise.resolve(resultWindow(offset));
};
globalThis.inventoryHarness.getInventoryDetail = (taskId, revision, nodeId) => {
  if (rejectedDetail !== null) {
    const held = rejectedDetail; rejectedDetail = null; return held.promise;
  }
  return Promise.resolve({...fixture.detail, node_id:nodeId, view_revision:revision, integrity:overlayFacts()});
};
for (const [kind, failReread] of [["window", false], ["detail", false], ["window", true]]) {
  const failedRead = defer();
  if (kind === "window") rejectedWindow = failedRead;
  else {
    rejectedDetail = failedRead;
    alignedReview.detail = {row:alignedReview.window.rows.find(row => row.row_id !== null),
      state:"current", response:fixture.detail};
  }
  const rejectedWork = app.refreshInventoryOverlay(alignedTask);
  await tick();
  alignedReview.window = await app.loadInventoryWindow(alignedReview, 239);
  const settledReads = rowReads.length;
  overlayFactRevision += 1;
  failNextWindow = failReread;
  failedRead.reject(new Error(`${kind} overlay unavailable`));
  await rejectedWork; await tick();
  assert.equal(rowReads.length, settledReads + 1,
    `${kind}: rejected overlay retains exactly one independently invalidated result demand`);
  assert.equal(alignedReview.window.offset, 239);
  if (!failReread) {
    assert.equal(alignedReview.window.integrity.revision, overlayFactRevision,
      `${kind}: the final result is reread without another drain update`);
    if (kind === "detail") assert.equal(alignedReview.detail.response.integrity.revision, overlayFactRevision);
  }
  assert.equal(alignedTask.inventoryOverlayRunning, false);
  assert.equal(alignedReview.keyboardRevealWindow, null);
  await tick();
  assert.equal(rowReads.length, settledReads + 1, "failure of the fresh reread cannot start error polling");
  alignedReview.detail = null;
}

rejectedWindow = defer();
const uninvalidatedRead = rejectedWindow;
const uninvalidatedWork = app.refreshInventoryOverlay(alignedTask);
await tick();
const uninvalidatedReads = rowReads.length;
uninvalidatedRead.reject(new Error("uninvalidated overlay unavailable"));
await uninvalidatedWork; await tick();
assert.equal(rowReads.length, uninvalidatedReads, "transport failure alone admits no automatic reread");

rejectedWindow = defer();
const retiredOverlayRead = rejectedWindow;
const retiredOverlayWork = app.refreshInventoryOverlay(alignedTask);
await tick();
alignedReview.window = await app.loadInventoryWindow(alignedReview, 239);
const retiredOverlayReads = rowReads.length;
const retiredOverlayRevision = alignedReview.window.integrity.revision;
app.showSettings();
retiredOverlayRead.reject(new Error("retired overlay unavailable"));
await retiredOverlayWork; await tick();
assert.equal(rowReads.length, retiredOverlayReads, "retired navigation cannot resurrect invalidated overlay demand");
assert.equal(alignedReview.window.integrity.revision, retiredOverlayRevision);

// Refresh starts directly; it no longer forfeits a copied-file opportunity.
const refreshOwner = attachReleasedExecutionTask("task-" + "9".repeat(32),
  "a".repeat(32), "b".repeat(32), "c".repeat(32));
app.selectTask(refreshOwner.taskId); app.switchTaskPane(refreshOwner, "verify"); await tick();
const refreshCount = calls.filter(([name]) => name === "refresh").length;
const confirmationCount = globalThis.inventoryConfirmations.length;
refuseRefresh = true;
await app.runInventoryAction(refreshOwner.inventoryReview, "refresh", null, trigger);
assert.equal(calls.filter(([name]) => name === "refresh").length, refreshCount + 1);
assert.equal(globalThis.inventoryConfirmations.length, confirmationCount);
refuseRefresh = false;

// Ordinary Inventory Follow uses the current session and C's one read job, including pane/loading reentry.
const followTask = attachReleasedExecutionTask("task-" + "d".repeat(32),
  "e".repeat(32), "f".repeat(32), "a".repeat(32));
app.selectTask(followTask.taskId); await tick();
app.adoptTask({task_id:followTask.taskId, session_id:"b".repeat(32), request_id:"c".repeat(32),
  plan_request_id:followTask.planRequestId, task_kind:"sync-plan", session_kind:"verify",
  session_state:"active", session_released:false});
followTask.inventoryReview = {...currentD1Review, detail:null, pending:null, actionRevision:0,
  summary:{...fixture.views.maximum.summary, task_id:followTask.taskId, request_id:followTask.requestId},
  window:fixture.views.maximum.window, follow:null};
const followAnchors = [], followWindows = [];
let heldFollowAnchor = defer();
globalThis.inventoryHarness.getInventoryItemAnchor = (taskId, sessionId, revision, itemId) => {
  followAnchors.push({taskId, sessionId, revision, itemId});
  return heldFollowAnchor?.promise ?? Promise.resolve({disposition:"current", view_revision:revision,
    node_id:real.node_id, index:itemId.endsWith(":1") ? 40 : 300});
};
const followWindow = (revision, offset) => ({...fixture.views.maximum.window,
  view_revision:revision, highlight_revision:followTask.inventoryReview.summary.highlight_revision,
  offset, rows:fixture.views.maximum.window.rows.slice(0, Math.min(256, fixture.views.maximum.window.total - offset))
    .map((row, index) => ({...row, visible_index:offset + index}))});
globalThis.inventoryHarness.getInventoryWindow = (taskId, revision, offset) => {
  followWindows.push(offset); return Promise.resolve(followWindow(revision, offset));
};
const followSnapshot = (itemId, itemType = "integrity") => ({session_id:followTask.sessionId,
  session_state:"active", control_state:"running", phase:"verify",
  active_item:itemId === null ? null : {item_id:itemId, item_type:itemType}, presentation:{item_percent:10}});
app.acceptTaskUpdate(followTask, followTask.sessionId, null, followSnapshot("1:1"));
assert.equal(followAnchors.length, 0, "a hidden Inventory pane launches no Follow read");
app.switchTaskPane(followTask, "verify");
assert.equal(followAnchors.length, 1, "pane return resolves the last current active item without another event");
const oldFollow = heldFollowAnchor;
app.acceptTaskUpdate(followTask, followTask.sessionId, null, followSnapshot("1:2"));
heldFollowAnchor = null;
oldFollow.resolve({disposition:"current", view_revision:followTask.inventoryReview.summary.view_revision,
  node_id:real.node_id, index:40});
await tick();
assert.equal(followAnchors.length, 2);
assert.deepEqual(followAnchors.map(value => value.itemId), ["1:1", "1:2"]);
assert.ok(followWindows.includes(300));
assert.equal(followWindows.includes(40), false, "a retired item anchor cannot dispatch its window");
let followReview = followTask.inventoryReview;
followReview.follow.scrollOffset = null;
app.acceptTaskUpdate(followTask, followTask.sessionId, null, followSnapshot("1:2"));
await tick();
assert.equal(followAnchors.length, 2, "same loaded target progress does not resolve again");
assert.equal(followReview.follow.scrollOffset, null, "same target progress does not reposition");
globalThis.inventoryCallbacks.onFollowOverride(followReview, 300, 310);
assert.equal(followReview.follow.enabled, true);
globalThis.inventoryCallbacks.onFollowOverride(followReview, 0, 10);
assert.equal(followReview.follow.enabled, false);
followReview.summary = {...followReview.summary, sort_column:"filename", view_revision:1};
const beforeGo = followAnchors.length;
globalThis.inventoryCallbacks.onNavigateCurrent(followReview, false); await tick();
assert.equal(followAnchors.length, beforeGo + 1);
assert.equal(followReview.summary.sort_column, "filename");
assert.equal(followReview.follow.enabled, false, "Go in another view does not enable Follow or change sorting");
followReview.summary = {...followReview.summary, sort_column:"path"};
app.switchTaskPane(followTask, "plan");
app.acceptTaskUpdate(followTask, followTask.sessionId, null, followSnapshot("1:1"));
app.switchTaskPane(followTask, "verify"); await tick();
assert.equal(followAnchors.length, beforeGo + 1, "same-session pane return preserves disabled choice");
globalThis.inventoryCallbacks.onNavigateCurrent(followReview, true); await tick();
assert.equal(followReview.follow.enabled, true);
delayedOpen = defer();
const followReload = app.loadInventoryReview(followTask, true);
const duringLoad = followAnchors.length;
app.acceptTaskUpdate(followTask, followTask.sessionId, null, followSnapshot("1:2"));
assert.equal(followAnchors.length, duringLoad, "loading retains current target without reading through the old owner");
delayedOpen.resolve({...followReview.summary, task_id:followTask.taskId, request_id:followTask.requestId});
await followReload; delayedOpen = null; await tick();
followReview = followTask.inventoryReview;
assert.equal(followAnchors.length, duringLoad + 1, "load completion resolves the latest active item without another event");
assert.equal(followReview.follow.enabled, true);
app.acceptTaskUpdate(followTask, followTask.sessionId, null, followSnapshot("unmapped-scan", "operation"));
assert.equal(followReview.follow.hasTarget, false, "non-integrity progress cannot invent an Inventory row");
heldFollowAnchor = defer();
app.acceptTaskUpdate(followTask, followTask.sessionId, null, followSnapshot("1:1"));
const closingAnchor = heldFollowAnchor;
const windowsBeforeRetirement = followWindows.length;
app.showSettings();
heldFollowAnchor = null;
closingAnchor.resolve({disposition:"current", view_revision:followReview.summary.view_revision,
  node_id:real.node_id, index:40});
await tick();
assert.equal(followWindows.length, windowsBeforeRetirement, "retired settings navigation dispatches no Follow window");
process.stdout.write("ok\n");
