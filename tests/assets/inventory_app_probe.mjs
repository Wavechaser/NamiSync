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
const inventoryOpenRequests = new Map();
let delayedDetail = null, delayedWindow = null, delayedView = null, delayedOpen = null, delayedVisibility = null;
let taskSnapshot = null, observedChecks = 0, refuseRefresh = false, delayedRefresh = null;
let refuseIntegrityStart = false;
let delayedIntegrityStart = null, integrityStartChecks = 0;
let delayedSelection = null, selectionDisposition = "current", selectedFileCount = fixture.views.default.summary.selected_file_count;
let manualReadinessResponse = null, delayedManualReadiness = null, delayedManualStart = null;
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
  openInventoryView(taskId) { calls.push(["open", taskId]); return delayedOpen?.promise ?? Promise.resolve({
    ...summary(), task_id:taskId, request_id:inventoryOpenRequests.get(taskId) ?? summary().request_id,
  }); },
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
  startInventoryIntegrity(taskId, requestId, commandId, revision, mode, accepted, onDelayed) {
    calls.push(["integrity-start", taskId, requestId, commandId, revision, mode, accepted]);
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
  getManualVerificationReadiness(taskId, sessionId, revision) {
    calls.push(["manual-readiness", taskId, sessionId, revision]);
    return delayedManualReadiness?.promise ?? Promise.resolve({...manualReadinessResponse,
      task_id:taskId, session_id:sessionId, execution_revision:revision});
  },
  startManualVerification(taskId, sessionId, commandId, revision) {
    calls.push(["manual-start", taskId, sessionId, commandId, revision]);
    taskSnapshot = {task_id:taskId, session_id:"b".repeat(32), session_state:"active",
      session_released:false, task_kind:"sync-plan", request_id:"c".repeat(32),
      plan_request_id:taskSnapshot.plan_request_id, session_kind:"manual-verify"};
    const result = {task_id:taskId, session_id:taskSnapshot.session_id,
      request_id:taskSnapshot.request_id};
    return delayedManualStart?.promise ?? Promise.resolve(result);
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
source += "\nexport { adoptTask, selectTask, acceptTaskUpdate, acceptTaskRelease, loadPlanReview, observeOriginalExecution, loadInventoryReview, changeInventoryView, loadInventoryWindow, readInventoryDetail, runInventoryAction, changeInventorySelection, startInventoryIntegrityAction, startManualVerificationAction, loadManualReadiness, switchTaskPane, controlInventoryIntegrity, checkInventoryOutcome, closeRetainedTask, showSettings, refreshTasks, executeReviewedPlan, tasks };";
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
await app.runInventoryAction(syncReview, "refresh", null);
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
  window:{offset:0, rows:[], execution:null}, foregroundWindowEpoch:0,
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
await app.runInventoryAction(executionTask.inventoryReview, "refresh", null);
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

const exactTaskId = "task-" + "1".repeat(32);
const exactOriginal = "2".repeat(32);
const exactAuxiliary = "3".repeat(32);
const exactRequest = "4".repeat(32);
const exactTask = attachReleasedExecutionTask(exactTaskId, exactOriginal, exactAuxiliary, exactRequest);
app.selectTask(exactTaskId);
manualReadinessResponse = {reason:"ready", applicable_count:1, ready_count:1,
  already_verified_count:0, attempted:false};
delayedManualReadiness = defer();
const readinessBefore = calls.filter(([name]) => name === "manual-readiness").length;
app.switchTaskPane(exactTask, "verify");
await tick();
app.switchTaskPane(exactTask, "plan");
app.switchTaskPane(exactTask, "verify");
delayedManualReadiness.resolve({...manualReadinessResponse, task_id:exactTaskId,
  session_id:exactOriginal, execution_revision:7});
await tick();
delayedManualReadiness = null;
assert.equal(calls.filter(([name]) => name === "manual-readiness").length, readinessBefore + 2,
  "rapid Verify reentry replaces the pane-retired readiness read");
assert.equal(exactTask.manualExactEligible, true,
  "ready exact verification remains available through a released auxiliary association");
const manualStarts = calls.filter(([name]) => name === "manual-start").length;
const staleManualSnapshot = {...taskSnapshot};
const staleManualList = defer();
let manualListReads = 0;
globalThis.inventoryHarness.listTasks = () => ++manualListReads === 1
  ? staleManualList.promise : Promise.resolve({tasks:[taskSnapshot]});
const heldManualRead = app.refreshTasks();
delayedManualStart = defer();
const manualStart = app.startManualVerificationAction(exactTask.inventoryReview);
await tick();
app.switchTaskPane(exactTask, "plan");
delayedManualStart.resolve({task_id:exactTaskId, session_id:"b".repeat(32),
  request_id:"c".repeat(32)});
await manualStart;
delayedManualStart = null;
const pendingManualRepair = defer();
globalThis.inventoryHarness.listTasks = () => pendingManualRepair.promise;
staleManualList.resolve({tasks:[staleManualSnapshot]});
await heldManualRead;
await tick();
assert.equal(calls.filter(([name]) => name === "manual-start").length, manualStarts + 1);
assert.deepEqual(calls.findLast(([name]) => name === "manual-start").slice(1, 3),
  [exactTaskId, exactOriginal], "manual start remains bound to the original execution");
assert.equal(exactTask.sessionKind, "manual-verify");
assert.equal(exactTask.sessionId, "b".repeat(32),
  "an accepted manual session remains adopted after switching back to Plan");
assert.equal(exactTask.requestId, "c".repeat(32),
  "accepted manual verification keeps its current request after an older task-list reply");
assert.equal(exactTask.planRequestId, exactRequest);
assert.equal(drains.at(-1)[1], exactTask.sessionId,
  "the accepted manual session attaches its drain independently of pane visibility");
globalThis.inventoryHarness.listTasks = originalListTasks;
app.switchTaskPane(exactTask, "verify");
const manualControls = calls.filter(([name]) => name === "manual-control").length;
await app.controlInventoryIntegrity(exactTask.inventoryReview, "pause");
assert.equal(calls.filter(([name]) => name === "manual-control").length, manualControls + 1,
  "manual controls use execution control for the current manual session");

const fallbackTaskId = "task-" + "5".repeat(32);
const fallbackOriginal = "6".repeat(32);
const fallbackTask = attachReleasedExecutionTask(fallbackTaskId, fallbackOriginal,
  "7".repeat(32), "8".repeat(32), "degraded");
app.selectTask(fallbackTaskId);
manualReadinessResponse = {reason:"unrecorded", applicable_count:1, ready_count:0,
  already_verified_count:0, attempted:false};
app.switchTaskPane(fallbackTask, "verify");
await tick();
assert.equal(fallbackTask.manualExactEligible, false);
assert.equal(fallbackTask.manualFallbackEligible, true,
  "normally completed recording degradation keeps the explicit current-state fallback");
const fallbackStarts = calls.filter(([name]) => name === "integrity-start").length;
await app.startInventoryIntegrityAction(fallbackTask.inventoryReview, "verify", trigger);
assert.equal(calls.filter(([name]) => name === "integrity-start").length, fallbackStarts + 1);
assert.equal(calls.findLast(([name]) => name === "integrity-start")[5], "verify");

// Release launches a production Plan reload. Entering Verify retires its paint
// authority, but the original execution facts must still reconcile readiness.
const releaseTaskId = "task-" + "9".repeat(32);
const releaseOriginal = "a".repeat(32);
const releaseRequest = "f".repeat(32);
const releaseTask = attachReleasedExecutionTask(releaseTaskId, releaseOriginal,
  releaseOriginal, releaseRequest);
releaseTask.sessionKind = "sync-execution";
releaseTask.sessionReleased = false;
const retainedPlan = releaseTask.review;
retainedPlan.window = {...retainedPlan.window, offset:512, rows:[]};
retainedPlan.summary = {...retainedPlan.summary, view_revision:0, highlight_revision:0,
  selection_revision:0, selection_state:"committed", search_query:"", filters:[],
  sort_column:"path", sort_direction:"ascending", execution:retainedPlan.window.execution};
retainedPlan.executionDetail = {sentinel:"retained-detail"};
retainedPlan.planDetail = {sentinel:"retained-plan-detail"};
retainedPlan.foregroundWindowReaders = 0;
retainedPlan.foregroundWindowEpoch = 0;
retainedPlan.actionRevision = 0;
app.selectTask(releaseTaskId);
await tick();
planSummaryResponse = {...retainedPlan.summary,
  execution:{...retainedPlan.window.execution, execution_revision:8}};
planWindowResponse = {disposition:"current", view_revision:0, highlight_revision:0,
  offset:0, rows:[], execution:planSummaryResponse.execution};
delayedPlanOpen = defer();
delayedManualReadiness = defer();
const releasedSummary = delayedPlanOpen;
app.acceptTaskRelease(releaseTask, releaseOriginal);
app.switchTaskPane(releaseTask, "verify");
await tick();
delayedPlanOpen = null;
releasedSummary.resolve(planSummaryResponse);
await tick();
delayedManualReadiness.resolve({task_id:releaseTaskId, session_id:releaseOriginal,
  execution_revision:8, reason:"conflict", applicable_count:1, ready_count:0,
  already_verified_count:0, attempted:false});
delayedManualReadiness = null;
manualReadinessResponse = {reason:"ready", applicable_count:1, ready_count:1,
  already_verified_count:0, attempted:false};
await tick();
assert.equal(releaseTask.manualExactEligible, true,
  "release/Verify ordering reconciles original execution readiness without Reload");
assert.equal(releaseTask.review, retainedPlan, "Verify retains the Plan review owner");
assert.equal(retainedPlan.window.offset, 512, "execution fact adoption cannot paint Plan rows");
assert.equal(retainedPlan.executionDetail.sentinel, "retained-detail");
assert.equal(retainedPlan.planDetail.sentinel, "retained-plan-detail");

const readinessRead = globalThis.inventoryHarness.getManualVerificationReadiness;
const planOpenRead = globalThis.inventoryHarness.openPlanView;
const readyResult = (owner, revision, reason = "ready") => ({task_id:owner.taskId,
  session_id:owner.executionSessionId, execution_revision:revision, reason,
  applicable_count:1, ready_count:reason === "ready" ? 1 : 0,
  already_verified_count:0, attempted:false});
const readinessCalls = (owner) => calls.filter(([name, id]) => name === "manual-readiness" && id === owner.taskId);
const planOpenCalls = (owner) => calls.filter(([name, id]) => name === "plan-open" && id === owner.taskId);
async function readinessOwner(index) {
  planSummaryResponse = null;
  const id = index.toString(16).padStart(32, "0");
  const owner = attachReleasedExecutionTask("task-" + id, "ac" + id.slice(2),
    "ac" + id.slice(2), "bc" + id.slice(2));
  await tick();
  owner.sessionKind = "sync-execution";
  owner.review.summary = {...retainedPlan.summary, task_id:owner.taskId,
    request_id:owner.planRequestId, execution:owner.review.window.execution};
  owner.review.window = {...owner.review.window, offset:768, rows:[]};
  owner.review.foregroundWindowReaders = 0;
  owner.review.foregroundWindowEpoch = 0;
  owner.review.actionRevision = 0;
  owner.review.pending = null;
  owner.review.executionDetail = {sentinel:index};
  owner.review.planDetail = {sentinel:index};
  inventoryOpenRequests.set(owner.taskId, owner.requestId);
  app.selectTask(owner.taskId);
  await tick();
  planSummaryResponse = owner.review.summary;
  planWindowResponse = {disposition:"current", view_revision:0, highlight_revision:0,
    offset:0, rows:[], execution:owner.review.window.execution};
  return owner;
}

// Conflict is a hint: the existing summary read, rather than the hint itself,
// supplies revision 8, then one bounded read establishes eligibility.
const conflictOwner = await readinessOwner(101);
const conflictPlan = conflictOwner.review;
const conflictSummary = defer();
let conflictReads = 0;
globalThis.inventoryHarness.getManualVerificationReadiness = (id, session, revision) => {
  calls.push(["manual-readiness", id, session, revision]);
  return Promise.resolve(readyResult(conflictOwner, ++conflictReads === 1 ? 8 : revision,
    conflictReads === 1 ? "conflict" : "ready"));
};
globalThis.inventoryHarness.openPlanView = (id) => {
  calls.push(["plan-open", id]); return conflictSummary.promise;
};
const conflictWindows = calls.filter(([name]) => name === "plan-window").length;
app.switchTaskPane(conflictOwner, "verify");
await tick();
assert.equal(conflictOwner.manualExactEligible, false, "a conflict revision alone grants no eligibility");
assert.equal(conflictOwner.originalExecutionFact.execution.execution_revision, 7);
conflictSummary.resolve({...conflictPlan.summary,
  execution:{...conflictPlan.window.execution, execution_revision:8}});
await tick();
assert.deepEqual(readinessCalls(conflictOwner).map((call) => call[3]), [7, 8]);
assert.equal(planOpenCalls(conflictOwner).length, 2, "one initial fixture read plus one conflict summary read");
assert.equal(calls.filter(([name]) => name === "plan-window").length, conflictWindows,
  "readiness reconciliation never fetches or paints Plan rows");
assert.equal(conflictOwner.manualExactEligible, true);
assert.equal(conflictOwner.review, conflictPlan);
assert.equal(conflictPlan.window.offset, 768);
assert.equal(conflictPlan.executionDetail.sentinel, 101);
assert.equal(conflictPlan.planDetail.sentinel, 101);
globalThis.inventoryHarness.getManualVerificationReadiness = readinessRead;
globalThis.inventoryHarness.openPlanView = planOpenRead;

taskSnapshot = {task_id:conflictOwner.taskId, session_id:conflictOwner.sessionId,
  session_state:"completed", session_released:true, task_kind:"sync-plan",
  request_id:conflictOwner.requestId, plan_request_id:conflictOwner.planRequestId,
  session_kind:"sync-execution"};
const latestStartBase = calls.filter(([name]) => name === "manual-start").length;
const acceptedOriginalFact = conflictOwner.originalExecutionFact;
delayedManualStart = defer();
const latestStart = app.startManualVerificationAction(conflictOwner.inventoryReview);
await tick();
await app.startManualVerificationAction(conflictOwner.inventoryReview);
// A late lower Plan read cannot revoke the admitted command's result custody.
app.observeOriginalExecution(conflictOwner, conflictOwner.planRequestId,
  {...conflictPlan.window.execution, execution_revision:7});
delayedManualStart.resolve({task_id:conflictOwner.taskId, session_id:"b".repeat(32),
  request_id:"c".repeat(32)});
await latestStart;
delayedManualStart = null;
assert.equal(calls.filter(([name]) => name === "manual-start").length, latestStartBase + 1,
  "double gesture never replays the one manual Start");
assert.equal(calls.findLast(([name]) => name === "manual-start")[4], 8,
  "the first manual Start captures the reconciled execution revision");
assert.equal(conflictOwner.sessionKind, "manual-verify");
assert.equal(conflictOwner.originalExecutionFact, acceptedOriginalFact,
  "accepted auxiliary work preserves original execution fact custody");

// The real release summary can advance first while an older readiness reply is
// running. A burst keeps exactly one latest demand and never rolls facts back.
const burstOwner = await readinessOwner(102);
burstOwner.sessionReleased = false;
delayedPlanOpen = defer();
const burstSummary = delayedPlanOpen;
delayedManualReadiness = defer();
const burstRead = delayedManualReadiness;
app.acceptTaskRelease(burstOwner, burstOwner.sessionId);
app.switchTaskPane(burstOwner, "verify");
await tick();
const burstBase = readinessCalls(burstOwner).length;
for (let index = 0; index < 20; index += 1) void app.loadManualReadiness(burstOwner);
planSummaryResponse = {...burstOwner.review.summary,
  execution:{...burstOwner.review.window.execution, execution_revision:8}};
planWindowResponse = {...planWindowResponse, execution:planSummaryResponse.execution};
delayedPlanOpen = null;
burstSummary.resolve(planSummaryResponse);
await tick();
assert.equal(burstOwner.originalExecutionFact.execution.execution_revision, 8);
assert.equal(readinessCalls(burstOwner).length, burstBase, "only one readiness read runs through a burst");
delayedManualReadiness = null;
burstRead.resolve(readyResult(burstOwner, 7));
await tick();
assert.deepEqual(readinessCalls(burstOwner).map((call) => call[3]), [7, 8]);
assert.equal(burstOwner.manualExactEligible, true, "a crossed read retains the latest demand");
app.observeOriginalExecution(burstOwner, burstOwner.planRequestId,
  {...planSummaryResponse.execution, execution_revision:6});
assert.equal(burstOwner.originalExecutionFact.execution.execution_revision, 8,
  "a late lower revision cannot roll the same execution back");
app.observeOriginalExecution(burstOwner, "wrong-plan", {...planSummaryResponse.execution, execution_revision:9});
app.observeOriginalExecution(burstOwner, burstOwner.planRequestId,
  {...planSummaryResponse.execution, session_id:"ff".repeat(16), execution_revision:9});
assert.equal(burstOwner.originalExecutionFact.execution.execution_revision, 8,
  "unrelated Plan and original-session facts have no adoption authority");

// Repeated conflict and transport failure terminate with actionable Reload.
const failedOwner = await readinessOwner(103);
let failedReads = 0;
globalThis.inventoryHarness.getManualVerificationReadiness = (id, session, revision) => {
  calls.push(["manual-readiness", id, session, revision]); failedReads += 1;
  return Promise.resolve(readyResult(failedOwner, revision, "conflict"));
};
app.switchTaskPane(failedOwner, "verify");
await tick();
assert.equal(failedReads, 2, "unchanged conflict gets one reconciliation round and stops");
assert.equal(failedOwner.manualReadinessLoading, false);
assert.equal(failedOwner.manualExactEligible, false);
assert.match(failedOwner.manualReadinessError, /Reload/);
await tick();
assert.equal(failedReads, 2, "conflict does not poll on later turns");
globalThis.inventoryHarness.getManualVerificationReadiness = (id, session, revision) => {
  calls.push(["manual-readiness", id, session, revision]); failedReads += 1;
  return Promise.reject(new Error("transport unavailable"));
};
await app.loadManualReadiness(failedOwner);
assert.equal(failedReads, 3, "an explicit Reload admits one fresh attempt");
assert.equal(failedOwner.manualReadinessLoading, false);
assert.match(failedOwner.manualReadinessError, /Reload/);
globalThis.inventoryHarness.getManualVerificationReadiness = readinessRead;

// Harmless variation: delayed Inventory completion with no execution crossing
// retains the same ready facts and produces no conflict-summary read.
const harmlessOwner = await readinessOwner(104);
delayedOpen = defer();
const harmlessInventory = delayedOpen;
const harmlessOpenBase = planOpenCalls(harmlessOwner).length;
app.switchTaskPane(harmlessOwner, "verify");
await tick();
assert.equal(harmlessOwner.manualExactEligible, true);
delayedOpen = null;
harmlessInventory.resolve({...summary(), task_id:harmlessOwner.taskId,
  request_id:harmlessOwner.requestId});
await tick();
assert.equal(harmlessOwner.manualExactEligible, true);
assert.ok(readinessCalls(harmlessOwner).every((call) => call[3] === 7));
assert.equal(planOpenCalls(harmlessOwner).length, harmlessOpenBase);

// Pane, task, Settings, Close and original-session replacement retire the old
// demand. Reentry gets a fresh read; an auxiliary session keeps original facts.
for (const [index, retire] of [
  [105, (owner) => app.switchTaskPane(owner, "plan")],
  [106, () => app.selectTask(harmlessOwner.taskId)],
  [107, () => app.showSettings()],
  [108, (owner) => app.closeRetainedTask(owner.taskId)],
  [109, (owner) => app.adoptTask({task_id:owner.taskId, session_id:"dd".repeat(16),
    session_state:"active", session_released:false, task_kind:"sync-plan",
    request_id:owner.requestId, plan_request_id:owner.planRequestId, session_kind:"sync-execution"})],
]) {
  const owner = await readinessOwner(index);
  const originalFact = owner.originalExecutionFact;
  delayedManualReadiness = defer();
  const retiredRead = delayedManualReadiness;
  app.switchTaskPane(owner, "verify");
  await tick();
  const retiredReply = readyResult(owner, 7);
  await retire(owner);
  delayedManualReadiness = null;
  retiredRead.resolve(retiredReply);
  await tick();
  assert.equal(owner.manualReadiness, null, `${index}: retired reply cannot restore eligibility`);
  assert.equal(readinessCalls(owner).length, 1, `${index}: retirement cannot revive old demand`);
  assert.equal(owner.manualReadinessLoading, false);
  if (index === 109) {
    assert.equal(owner.originalExecutionFact, null, "a new original execution resets its fact");
    app.observeOriginalExecution(owner, owner.planRequestId,
      {...originalFact.execution, session_id:owner.executionSessionId, execution_revision:1});
    assert.equal(owner.originalExecutionFact.execution.execution_revision, 1,
      "a replacement execution may begin at a lower revision");
  } else if (index !== 108) {
    app.selectTask(owner.taskId);
    if (owner.workPane === "plan") app.switchTaskPane(owner, "verify");
    await tick();
    assert.equal(owner.manualExactEligible, true, `${index}: reentry demands current readiness`);
    const fact = owner.originalExecutionFact;
    app.adoptTask({task_id:owner.taskId, session_id:"ee".repeat(16),
      session_state:"completed", session_released:true, task_kind:"sync-plan",
      request_id:owner.requestId, plan_request_id:owner.planRequestId, session_kind:"inventory"});
    assert.equal(owner.originalExecutionFact, fact, "auxiliary association preserves original execution facts");
  }
}
process.stdout.write("ok\n");
