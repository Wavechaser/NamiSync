import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

class Style {
  constructor() { this.values = new Map(); }
  setProperty(key, value) { this.values.set(key, String(value)); }
  set blockSize(value) { this.setProperty("block-size", value); }
  get blockSize() { return this.values.get("block-size"); }
}
class ElementFake {
  constructor(tag, ownerDocument) {
    this.tagName = tag.toUpperCase(); this.ownerDocument = ownerDocument;
    this.children = []; this.parentElement = null; this.listeners = new Map();
    this.dataset = {}; this.attributes = new Map(); this.style = new Style();
    this.className = ""; this.value = ""; this.textContent = "";
    this.hidden = false; this.disabled = false; this.scrollTop = 0; this.clientHeight = 280;
    this.classList = {
      add: (...values) => { this.className = [...new Set([...this.className.split(" "), ...values])].join(" "); },
      contains: (value) => this.className.split(" ").includes(value),
    };
  }
  append(...values) {
    for (const value of values) {
      value.remove(); value.parentElement = this; this.children.push(value);
    }
  }
  replaceChildren(...values) {
    for (const child of this.children) child.parentElement = null;
    this.children = []; this.append(...values);
  }
  remove() {
    if (this.parentElement !== null) this.parentElement.children = this.parentElement.children.filter((value) => value !== this);
    this.parentElement = null;
  }
  addEventListener(key, value) { this.listeners.set(key, [...(this.listeners.get(key) ?? []), value]); }
  removeEventListener(key, value) { this.listeners.set(key, (this.listeners.get(key) ?? []).filter((item) => item !== value)); }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  removeAttribute(key) { this.attributes.delete(key); }
  focus() { document.activeElement = this; this.dispatch("focus"); }
  dispatch(key, fields = {}) {
    const event = { target: this, preventDefault() {}, stopPropagation() { this.stopped = true; }, ...fields };
    for (const callback of this.listeners.get(key) ?? []) callback(event);
    if (!event.stopped && this.parentElement !== null) this.parentElement.dispatch(key, event);
  }
  click() { if (!this.disabled) this.dispatch("click"); }
}
const frames = [];
const observers = [];
globalThis.document = {
  activeElement: null,
  createElement(tag) { return new ElementFake(tag, this); },
  defaultView: {
    requestAnimationFrame(callback) { frames.push(callback); },
    ResizeObserver: class {
      constructor(callback) { this.callback = callback; this.disconnected = false; observers.push(this); }
      observe() {} disconnect() { this.disconnected = true; }
    },
  },
};
globalThis.Element = ElementFake;
globalThis.HTMLElement = ElementFake;
const timers = new Map();
let timerId = 0;
globalThis.setTimeout = (callback, delay) => { timers.set(++timerId, { callback, delay }); return timerId; };
globalThis.clearTimeout = (id) => { timers.delete(id); };
const moduleUrl = (source) => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const assetRoot = process.argv[2];
const renderUrl = moduleUrl(await readFile(join(assetRoot, "render.js"), "utf8"));
const treeUrl = moduleUrl((await readFile(join(assetRoot, "tree.js"), "utf8")).replace("./render.js", renderUrl));
const iconsUrl = moduleUrl(await readFile(join(assetRoot, "icons.js"), "utf8"));
const source = (await readFile(join(assetRoot, "inventory_review.js"), "utf8"))
  .replace("./render.js", renderUrl).replace("./tree.js", treeUrl).replace("./icons.js", iconsUrl);
const { createInventoryReviewPanel } = await import(moduleUrl(source));
const fixture = JSON.parse(await readFile(process.argv[3], "utf8"));
const viewChanges = [], details = [], pages = [], reloads = [], refreshes = [], visibility = [], checks = [];
let pendingPage;
const pane = createInventoryReviewPanel({
  onViewChange: (...args) => viewChanges.push(args),
  onDetail: (...args) => details.push(args),
  onWindow: (...args) => { pages.push(args); return new Promise((resolve) => { pendingPage = resolve; }); },
  onReload: (task) => reloads.push(task),
  onRefresh: (...args) => refreshes.push(args),
  onVisibility: (...args) => visibility.push(args),
  onCheckOutcome: (task) => checks.push(task),
});
const review = { ...fixture.views.default, pending: null, message: null, detail: null, queuedSearchQuery: null, scrollTop: 0 };
const task = { taskId: "inventory", taskKind: "inventory", sessionState: "completed", inventoryReview: review,
  requestId: fixture.views.default.summary.request_id,
  inventoryLoading: false, closePending: false, inventoryError: null, sessionReleased: true,
  inventoryViewUnconfirmed: false, inventoryAction: null };
const walk = (root) => [root, ...root.children.flatMap(walk)];
const find = (predicate) => walk(pane.element).find(predicate);
const action = (key) => find((value) => value.dataset.action === key);
const rowElements = () => walk(pane.element).filter((value) => value.getAttribute("role") === "treeitem");
const text = (root) => [root.textContent, ...root.children.map(text)].join(" ");
const tick = async () => { await Promise.resolve(); await Promise.resolve(); };
pane.render(task);
action("inventory-refresh").click();
assert.deepEqual(refreshes.at(-1), [review, null]);
assert.equal(rowElements().length, fixture.views.default.window.rows.length);
assert.equal(find((value) => value.getAttribute("role") === "tree").tabIndex, 0);
assert.equal(find((value) => value.tagName === "INPUT" && value.type === "checkbox"), undefined);
assert.equal(action("inventory-all").textContent, "Default");
assert.match(text(pane.element), /Acknowledged 1/);
assert.match(text(pane.element), /Displayed scan: incomplete/);
assert.ok(!rowElements().some((value) => text(value).includes("missing.txt")));
assert.ok(rowElements().every((value) => value.children.length === 4));
const real = fixture.views.default.window.rows.find((row) => row.row_id === "1");
const realElement = rowElements().find((value) => value.dataset.nodeId === real.node_id);
realElement.click();
assert.equal(details.at(-1)[1], real.node_id);
const root = find((value) => value.getAttribute("role") === "tree");
root.dispatch("keydown", { key: "Enter" });
assert.equal(details.at(-1)[1], real.node_id);
const folder = rowElements().find((value) => value.ariaExpanded === "true");
const disclosure = walk(folder).find((value) => value.classList.contains("nami-tree-row__disclosure"));
disclosure.click();
assert.deepEqual(viewChanges.at(-1)[1], { collapseNodeId: folder.dataset.nodeId, collapsed: true });
assert.equal(details.length, 2, "disclosure must not request detail");
const search = action("inventory-search");
search.value = "  literal.*  "; search.dispatch("input");
assert.equal([...timers.values()][0].delay, 150);
for (const timer of [...timers.values()]) timer.callback();
assert.deepEqual(viewChanges.at(-1)[1], { searchQuery: "  literal.*  " });
action("inventory-search-clear").click();
assert.deepEqual(viewChanges.at(-1)[1], { searchQuery: "" });
assert.equal(document.activeElement, search);
action("inventory-filter-acknowledged").click();
assert.deepEqual(viewChanges.at(-1)[1], { filters: ["acknowledged"] });
for (const column of ["filename", "size", "mtime"]) {
  for (const dir of ["ascending", "descending"]) {
    const sort = find((value) => value.ariaLabel === "Inventory sort column");
    const direction = find((value) => value.ariaLabel === "Inventory sort direction");
    sort.value = column; direction.value = dir; sort.dispatch("change");
    assert.deepEqual(viewChanges.at(-1)[1], { sortColumn: column, sortDirection: dir });
  }
}
action("inventory-sort-reset").click();
assert.deepEqual(viewChanges.at(-1)[1], { sortColumn: "path", sortDirection: "ascending" });
review.detail = { row: real, state: "current", response: fixture.detail };
pane.render(task);
action("inventory-refresh-selected").click();
assert.deepEqual(refreshes.at(-1), [review, real.node_id]);
const detail = find((value) => value.ariaLabel === "Inventory item details");
assert.match(text(detail), new RegExp(fixture.detail.detail.attestation.content.digest));
assert.match(text(detail), new RegExp(`Provenance ${fixture.detail.detail.attestation.content.provenance}`));
assert.match(text(detail), /Observed modified.*9223372036854775807 ns/);
assert.match(text(detail), /Attested modified.*9223372036854775807 ns/);
assert.match(text(detail), /Last verified/);
review.detail.response = fixture.invalidated_detail;
pane.render(task);
assert.match(text(detail), /Verification state Mismatch/);
assert.match(text(detail), /Invalidation reason hash-mismatch/);
assert.match(text(detail), new RegExp(fixture.invalidated_detail.detail.attestation.content.digest));
const notice = fixture.views.default.window.rows.find((row) => row.warning !== null);
review.detail = { row: notice, state: "current", response: null };
pane.render(task);
assert.match(text(detail), /read failed/);
assert.doesNotMatch(text(detail), /Stored digest/);
assert.equal(action("inventory-refresh-selected").disabled, true);
assert.equal(action("inventory-acknowledge").hidden, true);
assert.equal(action("inventory-restore").hidden, true);
Object.assign(review, fixture.views.acknowledged, { detail: null });
pane.render(task);
assert.ok(rowElements().some((value) => text(value).includes("hidden")), "server ancestor context survives");
assert.ok(rowElements().some((value) => text(value).includes("missing.txt")));
assert.match(text(pane.element), /Acknowledged 1/);
Object.assign(review, fixture.views.maximum);
pane.render(task);
assert.equal(rowElements().length, 256, "render complete server window without growing beyond bound");
assert.match(text(pane.element), /Unavailable \(size overflow\)/);
root.scrollTop = 300 * 28; root.dispatch("scroll");
while (frames.length) frames.shift()();
assert.equal(pages.length, 1);
assert.equal(pages[0][0], review);
assert.ok(pages[0][1] > 256);
const oldCount = rowElements().length;
pane.dispose();
pendingPage(fixture.tail);
await tick();
assert.equal(rowElements().length, oldCount, "retired page reply cannot mutate tree");
assert.equal(observers.at(-1).disconnected, true);
task.inventoryReview = { ...fixture.views.empty, pending: null, message: null, detail: null, queuedSearchQuery: null };
pane.render(task);
assert.equal(rowElements().length, 0);
assert.match(text(pane.element), /No items match/);
task.inventoryError = "Inventory unavailable. Reload the inventory view to retry.";
task.requestId = "f".repeat(32); task.sessionState = "refused";
pane.render(task); action("inventory-reload").click();
assert.match(text(pane.element), /Current scan: refused/);
assert.match(text(pane.element), /Previous published scan/);
assert.equal(reloads.at(-1), task);
assert.equal(action("inventory-refresh").disabled, false, "prior publication may refresh current task");
assert.equal(action("inventory-acknowledge").disabled, true, "prior publication cannot mutate visibility");
task.inventoryAction = { pending: true, recovery: { canCheck: true, checking: false }, message: "Original pending" };
pane.render(task);
action("inventory-check-outcome").click();
assert.equal(checks.at(-1), task);
assert.equal(action("inventory-refresh").disabled, true);
pane.dispose();
const setupUrl = moduleUrl("export const createSetupPanel = () => ({ element: document.createElement('div'), render() {} });");
const planUrl = moduleUrl("export const createPlanReviewPanel = () => ({ element: document.createElement('div'), render() {}, dispose() {} });");
const panelSource = (await readFile(join(assetRoot, "panels.js"), "utf8"))
  .replace("./render.js", renderUrl).replace("./inventory_review.js", moduleUrl(source))
  .replace("./setup.js", setupUrl).replace("./plan_review.js", planUrl);
const { createWorkPanel } = await import(moduleUrl(panelSource));
const work = createWorkPanel({}, {}, document.createElement("div"), {
  onViewChange() {}, onDetail() {}, onWindow() {}, onReload() {},
});
task.sessionReleased = true; task.review = null;
work.render(task);
assert.ok(walk(work.element).some((value) => value.ariaLabel === "Inventory review"));
work.renderSettings();
assert.ok(!walk(work.element).some((value) => value.ariaLabel === "Inventory review"));

// Exercise the app's fetch and the real pane/tree publication seam together.
const shellNodes = new Map();
document.querySelector = (key) => {
  if (!shellNodes.has(key)) shellNodes.set(key, document.createElement("div"));
  return shellNodes.get(key);
};
document.body = document.createElement("body");
document.documentElement = document.createElement("html");
globalThis.window = { chrome: { webview: {} }, addEventListener() {} };
let viewportReply = null;
const viewportCalls = [];
globalThis.inventoryViewportHarness = {
  openInventoryView: () => Promise.resolve(fixture.views.maximum.summary),
  getInventoryWindow: (...args) => {
    viewportCalls.push(args);
    return viewportReply?.promise ?? Promise.resolve(fixture.views.maximum.window);
  },
};
let appSource = await readFile(join(assetRoot, "app.js"), "utf8");
const bridgeNames = appSource.match(/import \{([\s\S]*?)\} from "\.\/bridge\.js";/)[1]
  .split(",").map((value) => value.trim()).filter(Boolean);
const bridgeFunctions = {
  whenBridgeApiReady: "() => new Promise(() => {})",
  readSetup: "() => new Promise(() => {})",
  startTaskDrain: "() => () => {}",
};
const viewportBridge = moduleUrl(bridgeNames.map((name) => /^[A-Z]/.test(name)
  ? `export class ${name} extends Error {}`
  : `export const ${name} = ${bridgeFunctions[name] ?? (name in globalThis.inventoryViewportHarness
    ? `(...args) => globalThis.inventoryViewportHarness.${name}(...args)` : "() => Promise.reject(new Error('unused bridge command'))")};`).join("\n"));
const taskStatusUrl = moduleUrl((await readFile(join(assetRoot, "task_status.js"), "utf8")).replace("./render.js", renderUrl));
for (const [key, value] of Object.entries({
  "./bridge.js": viewportBridge, "./render.js": renderUrl, "./task_status.js": taskStatusUrl,
  "./panels.js": moduleUrl(panelSource),
  "./readiness.js": moduleUrl("export const installReadinessReceiver = () => ({ revision: () => 0 });"),
  "./appearance.js": moduleUrl("export const installAppearanceReceiver = () => {};"),
  "./theme.js": moduleUrl("export const installThemeCombobox = () => ({}); export const installThemeSelector = () => ({ refresh() {} });"),
  "./execution_confirmation.js": moduleUrl("export const createExecutionConfirmation = () => ({ element: document.createElement('dialog') });"),
  "./rail.js": moduleUrl("export const createTaskRail = () => ({ element: document.createElement('nav'), render() {} });"),
})) appSource = appSource.replace(key, value);
appSource += "\nexport { adoptTask, selectTask, panel };";
const app = await import(moduleUrl(appSource));
const liveTask = app.adoptTask({ task_id: fixture.views.maximum.summary.task_id,
  session_id: "3".repeat(32), session_state: "completed", session_released: true,
  task_kind: "inventory", request_id: fixture.views.maximum.summary.request_id });
const settle = async () => { for (let count = 0; count < 8; count += 1) await Promise.resolve(); };
app.selectTask(liveTask.taskId); await settle();
const liveReview = liveTask.inventoryReview;
const treeRoot = walk(app.panel.element).find((value) => value.getAttribute("role") === "tree");
const firstLiveRow = () => treeRoot.children.find((value) => value.getAttribute("role") === "treeitem");
const initialWindow = liveReview.window;
const initialNode = firstLiveRow().dataset.nodeId;
const delayedViewport = () => {
  let resolve;
  const promise = new Promise((accept) => { resolve = accept; });
  return { resolve, promise };
};
viewportReply = delayedViewport();
treeRoot.scrollTop = 300 * 28; treeRoot.dispatch("scroll");
while (frames.length) frames.shift()();
assert.equal(viewportCalls.at(-1)[2], 268);
treeRoot.scrollTop = 0; treeRoot.dispatch("scroll");
while (frames.length) frames.shift()();
viewportReply.resolve(fixture.tail); await settle();
assert.equal(liveReview.window === initialWindow, true, "retired viewport reply must not enter cached app state");
app.panel.render(liveTask);
assert.equal(firstLiveRow().dataset.nodeId, initialNode, "later render cannot adopt a rejected window");
viewportReply = delayedViewport();
treeRoot.scrollTop = 300 * 28; treeRoot.dispatch("scroll");
while (frames.length) frames.shift()();
viewportReply.resolve(fixture.tail); await settle();
assert.equal(liveReview.window === fixture.tail, true, "accepted viewport reply becomes the retained window");
assert.equal(firstLiveRow().dataset.nodeId, fixture.tail.rows[0].node_id);
const acceptedScroll = treeRoot.scrollTop;
app.panel.render(liveTask);
assert.equal(treeRoot.scrollTop, acceptedScroll, "rendering the accepted window preserves scrolling");
assert.equal(firstLiveRow().dataset.nodeId, fixture.tail.rows[0].node_id);
app.panel.renderSettings();
process.stdout.write("ok\n");
