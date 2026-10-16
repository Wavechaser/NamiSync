import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { assertSameNode } from "./fake_dom_assertions.mjs";

process.env.TZ = "UTC";

class Style {
  constructor() { this.values = new Map(); }
  setProperty(key, value) { this.values.set(key, String(value)); }
  set blockSize(value) { this.setProperty("block-size", value); }
  get blockSize() { return this.values.get("block-size"); }
}
class ElementFake {
  constructor(tag, ownerDocument) {
    this.tagName = tag.toUpperCase(); this.ownerDocument = ownerDocument;
    this.children = []; this.parentElement = null; this.listeners = new Map(); this.captureListeners = new Map();
    this.dataset = {}; this.attributes = new Map(); this.style = new Style();
    this.className = ""; this.value = ""; this.textContent = "";
    this.hidden = false; this.disabled = false; this.scrollTop = 0; this.clientHeight = 280;
    this.classList = {
      add: (...values) => { this.className = [...new Set([...this.className.split(" "), ...values])].join(" "); },
      contains: (value) => this.className.split(" ").includes(value),
      toggle: (value, enabled) => {
        const values = new Set(this.className.split(" "));
        if (enabled) values.add(value); else values.delete(value);
        this.className = [...values].join(" ");
      },
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
  closest(selector) {
    for (let value = this; value !== null; value = value.parentElement) {
      if (value.classList.contains(selector.slice(1))) return value;
    }
    return null;
  }
  contains(value) { return value === this || this.children.some((child) => child.contains(value)); }
  getBoundingClientRect() { return { left: 16, right: 176, height: 32, top: 200, bottom: 232, width: 160 }; }
  querySelector(selector) {
    return this.children.find((value) => value.classList.contains(selector.slice(1)))
      ?? this.children.map((value) => value.querySelector(selector)).find(Boolean) ?? null;
  }
  remove() {
    if (this.parentElement !== null) this.parentElement.children = this.parentElement.children.filter((value) => value !== this);
    this.parentElement = null;
  }
  addEventListener(key, value, options) {
    const listeners = options === true || options?.capture ? this.captureListeners : this.listeners;
    listeners.set(key, [...(listeners.get(key) ?? []), value]);
  }
  removeEventListener(key, value, options) {
    const listeners = options === true || options?.capture ? this.captureListeners : this.listeners;
    listeners.set(key, (listeners.get(key) ?? []).filter(item => item !== value));
  }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  removeAttribute(key) { this.attributes.delete(key); }
  focus() {
    document.activeElement = this; this.dispatch("focus");
    for (const callback of documentListeners.get("focusin") ?? []) callback({target:this});
  }
  dispatch(key, fields = {}) {
    const event = { type: key, target: this, preventDefault() {}, stopPropagation() { this.stopped = true; }, ...fields };
    const path = [];
    for (let node=this; node !== null; node=node.parentElement) path.push(node);
    for (const node of [...path].reverse()) {
      for (const callback of node.captureListeners.get(key) ?? []) callback(event);
      if (event.stopped) return;
    }
    for (const node of path) {
      for (const callback of node.listeners.get(key) ?? []) callback(event);
      if (event.stopped) return;
    }
  }
  click() { if (!this.disabled) this.dispatch("click"); }
}
const frames = [];
const observers = [];
const documentListeners = new Map();
const viewListeners = new Map();
globalThis.document = {
  addEventListener(key, callback) { documentListeners.set(key, [...(documentListeners.get(key) ?? []), callback]); },
  removeEventListener(key, callback) { documentListeners.set(key, (documentListeners.get(key) ?? []).filter((value) => value !== callback)); },
  activeElement: null,
  createElement(tag) { return new ElementFake(tag, this); },
  defaultView: {
    innerHeight: 800,
    innerWidth: 1280,
    addEventListener(key, callback) { viewListeners.set(key, [...(viewListeners.get(key) ?? []), callback]); },
    removeEventListener(key, callback) { viewListeners.set(key, (viewListeners.get(key) ?? []).filter((value) => value !== callback)); },
    requestAnimationFrame(callback) { frames.push(callback); },
    ResizeObserver: class {
      constructor(callback) { this.callback = callback; this.disconnected = false; observers.push(this); }
      observe() {} disconnect() { this.disconnected = true; }
    },
  },
};
globalThis.window = document.defaultView;
document.body = new ElementFake("body", document);
globalThis.getComputedStyle = () => ({fontSize: "16px"});
globalThis.Element = ElementFake;
globalThis.HTMLElement = ElementFake;
const timers = new Map();
let timerId = 0;
globalThis.setTimeout = (callback, delay) => { timers.set(++timerId, { callback, delay }); return timerId; };
globalThis.clearTimeout = (id) => { timers.delete(id); };
const moduleUrl = (source) => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const assetRoot = process.argv[2];
const renderUrl = moduleUrl(await readFile(join(assetRoot, "render.js"), "utf8"));
const highlightUrl = moduleUrl(await readFile(join(assetRoot, "row_highlight.js"), "utf8"));
const tableControllerUrl = moduleUrl(await readFile(join(assetRoot, "table_controller.js"), "utf8"));
const treeUrl = moduleUrl((await readFile(join(assetRoot, "tree.js"), "utf8")).replace("./render.js", renderUrl).replace("./row_highlight.js", highlightUrl).replace("./table_controller.js", tableControllerUrl));
const fileRowUrl = moduleUrl((await readFile(join(assetRoot, "file_row.js"), "utf8")).replace("./render.js", renderUrl));
const integrityUrl = moduleUrl((await readFile(join(assetRoot, "integrity.js"), "utf8"))
  .replace("./file_row.js", fileRowUrl).replace("./render.js", renderUrl));
const iconsUrl = moduleUrl(await readFile(join(assetRoot, "icons.js"), "utf8"));
const filterUrl = moduleUrl((await readFile(join(assetRoot, "filter_menu.js"), "utf8"))
  .replace("./render.js", renderUrl).replace("./icons.js", iconsUrl));
const rowMenuUrl = moduleUrl((await readFile(join(assetRoot, "row_menu.js"), "utf8"))
  .replace("./render.js", renderUrl));
const tableColumnsUrl = moduleUrl(await readFile(join(assetRoot, "table_columns.js"), "utf8"));
const inventoryTaskStatusUrl = moduleUrl((await readFile(join(assetRoot, "task_status.js"), "utf8")).replace("./render.js", renderUrl));
const source = (await readFile(join(assetRoot, "inventory_review.js"), "utf8"))
  .replace("./row_highlight.js", highlightUrl)
  .replace("./task_status.js", inventoryTaskStatusUrl)
  .replace("./table_columns.js", tableColumnsUrl)
  .replace("./filter_menu.js", filterUrl)
  .replace("./row_menu.js", rowMenuUrl)
  .replace("./integrity.js", integrityUrl)
  .replace("./render.js", renderUrl).replace("./tree.js", treeUrl).replace("./icons.js", iconsUrl);
const { createInventoryReviewPanel } = await import(moduleUrl(source));
const fixture = JSON.parse(await readFile(process.argv[3], "utf8"));
const viewChanges = [], details = [], pages = [], reloads = [], refreshes = [], visibility = [], checks = [];
const selections = [], starts = [], controls = [];
let pendingPage;
const pane = createInventoryReviewPanel({
  onViewChange: (...args) => viewChanges.push(args),
  onDetail: (...args) => details.push(args),
  onWindow: (...args) => { pages.push(args); return new Promise((resolve) => { pendingPage = resolve; }); },
  onReload: (task) => reloads.push(task),
  onRefresh: (...args) => refreshes.push(args),
  onVisibility: (...args) => visibility.push(args),
  onSelect: (...args) => selections.push(args),
  onStart: (...args) => starts.push(args),
  onControl: (...args) => controls.push(args),
  onCheckOutcome: (task) => checks.push(task),
});
const review = { ...fixture.views.default, pending: null, message: null, detail: null, queuedSearchQuery: null, scrollTop: 0 };
const permanentPointerListeners = documentListeners.get("pointerdown").length;
const task = { taskId: "inventory", taskKind: "inventory", sessionState: "completed", inventoryReview: review,
  requestId: fixture.views.default.summary.request_id,
  inventoryLoading: false, closePending: false, inventoryError: null, sessionReleased: true,
  inventoryViewUnconfirmed: false, inventoryAction: null };
const walk = (root) => [root, ...root.children.flatMap(walk)];
const find = (predicate) => walk(pane.element).find(predicate);
const action = (key) => find((value) => value.dataset.action === key);
const rowElements = () => walk(pane.element).filter((value) => value.getAttribute("role") === "treeitem");
const rowElement = (nodeId) => rowElements().find((value) => value.dataset.nodeId === nodeId);
const rowSelection = (nodeId) => walk(rowElement(nodeId))
  .find((value) => value.dataset.action === "inventory-select-row");
const text = (root) => [root.textContent, ...root.children.map(text)].join(" ");
const tick = async () => { await Promise.resolve(); await Promise.resolve(); };
pane.render(task);
const statusLine = find((value) => value.classList.contains("nami-inventory-review__status-line"));
const statusSummary = find((value) => value.classList.contains("nami-plan-review__status-summary"));
const progressTrack = find((value) => value.classList.contains("nami-plan-review__progress"));
assert.doesNotMatch(statusSummary.textContent, /visible rows/);
assert.doesNotMatch(statusLine.textContent, /Current scan:|completed/);
assert.equal(progressTrack.hidden, false, "terminal track remains visible without inventing a percentage");
assert.equal(progressTrack.classList.contains("nami-progress--indeterminate"), false);
task.inventoryLoading = true;
pane.render(task);
assert.equal(find((value) => value.classList.contains("nami-inventory-review__status-line")), statusLine);
assert.match(statusLine.textContent, /Loading inventory view…/);
task.inventoryLoading = false;
task.sessionState = "active";
pane.render(task);
assert.equal(progressTrack.classList.contains("nami-progress--indeterminate"), true,
  "a scan without totals uses the shared indeterminate class");
task.sessionId = "a".repeat(32);
task.snapshot = { session_id: task.sessionId, session_state: "active", phase: "inventory",
  presentation: { value: 37, determinate: true, indeterminate: false,
    items_done: 37, items_total: 100 }, terminal_result: null };
pane.render(task);
assert.equal(progressTrack.classList.contains("nami-progress--indeterminate"), false);
assert.equal(progressTrack.children[0].style.values.get("--nami-progress-value"), "37%");
task.snapshot = { ...task.snapshot, session_state: "completed" };
task.sessionState = "completed";
pane.render(task);
assert.equal(progressTrack.hidden, false);
assert.equal(progressTrack.children[0].style.values.get("--nami-progress-value"), "37%",
  "terminal presentation retains the supplied value instead of fabricating 100%");
task.snapshot = null;
pane.render(task);
action("inventory-refresh").click();
assert.deepEqual(refreshes.at(-1), [review, null, action("inventory-refresh")]);
assert.equal(rowElements().length, fixture.views.default.window.rows.length);
assert.deepEqual(walk(pane.element).filter((value) => value.dataset.nodeId !== undefined), rowElements(),
  "data-node-id uniquely identifies Inventory rows");
assert.equal(find((value) => value.getAttribute("role") === "tree").tabIndex, 0);
const selectionVisuals = walk(pane.element).filter((value) => value.tagName === "INPUT" && value.type === "checkbox");
assert.equal(selectionVisuals.length, rowElements().length + 1);
const locationSelection = action("inventory-select-location");
assert.equal(locationSelection.checked, review.summary.selection === "all");
assert.equal(locationSelection.indeterminate, review.summary.selection === "partial");
assert.equal(locationSelection.disabled, review.summary.selectable_file_count === 0);
for (const row of review.window.rows) {
  const checkbox = rowSelection(row.node_id);
  assert.equal(checkbox.checked, row.selection === "all");
  assert.equal(checkbox.indeterminate, row.selection === "partial");
  assert.equal(checkbox.disabled, !row.selectable);
}
const beforeSelectionClick = [viewChanges.length, details.length, refreshes.length, visibility.length];
locationSelection.checked = false;
locationSelection.dispatch("change");
assert.deepEqual(selections.at(-1), [review, null, false]);
const selectableRow = review.window.rows.find((row) => row.selectable);
const selectableCheckbox = rowSelection(selectableRow.node_id);
const detailCount = details.length;
selectableCheckbox.checked = false;
selectableCheckbox.dispatch("change");
assert.deepEqual(selections.at(-1), [review, selectableRow.node_id, false]);
assert.equal(details.length, detailCount, "checkbox change cannot activate the tree row");
assert.deepEqual([viewChanges.length, details.length, refreshes.length, visibility.length], beforeSelectionClick);
assert.match(action("inventory-select-location").ariaLabel, /matching files.*collapsed and off-window/i);
assert.match(selectableCheckbox.ariaLabel, /matching files.*collapsed and off-window|Select file/);
assert.match(find((value) => Object.hasOwn(value.dataset, "inventorySelectionSummary")).textContent,
  new RegExp(`^${review.summary.selected_file_count} of ${review.summary.selectable_file_count} files selected`));
assert.equal(action("inventory-baseline").disabled, review.summary.selected_file_count === 0);
const originalSummary = review.summary;
const originalWindow = review.window;
review.summary = {...review.summary, selected_file_count:review.summary.selectable_file_count,
  hidden_selected_file_count:0, selection:"all"};
review.window = {...review.window, rows:review.window.rows.map(row => row.selectable
  ? {...row, selection:"all"} : row)};
pane.render(task);
assert.equal(action("inventory-baseline").disabled, false);
action("inventory-baseline").click();
assert.deepEqual(starts.at(-1).slice(0, 2), [review, "baseline"]);
task.sessionId = "b".repeat(32);
task.sessionKind = "verify";
task.sessionState = "active";
task.sessionReleased = false;
task.executionControlState = "running";
review.summary = originalSummary;
review.window = originalWindow;
pane.render(task);
assert.equal(action("inventory-pause").hidden, false);
assert.equal(action("inventory-resume").hidden, true);
action("inventory-pause").click();
assert.deepEqual(controls.at(-1), [review, "pause"]);
task.inventoryAction = {pending:false, accepted:true};
pane.render(task);
assert.equal(action("inventory-pause").disabled, true,
  "an accepted control remains visibly owned until live state changes");
assert.equal(action("inventory-cancel").disabled, true);
task.inventoryAction = null;
task.executionControlState = "pausing";
pane.render(task);
assert.equal(action("inventory-pause").disabled, true);
assert.equal(action("inventory-resume").hidden, true,
  "pausing keeps both Pause and Resume unavailable until the checkpoint settles");
task.executionControlState = "paused";
pane.render(task);
assert.equal(action("inventory-resume").hidden, false);
action("inventory-resume").click();
assert.deepEqual(controls.at(-1), [review, "resume"]);
action("inventory-cancel").click();
assert.deepEqual(controls.at(-1), [review, "cancel"]);
task.sessionId = null;
task.sessionKind = "inventory";
task.sessionState = "completed";
task.sessionReleased = true;
task.executionControlState = "running";
pane.render(task);
assert.equal(find((value) => value.getAttribute("role") === "tree").style.values.get("--row-h"), "24px");
const filterTrigger = action("filter-menu");
const filterPopup = find((value) => value.classList.contains("nami-filter-menu__popup"));
const filterItem = (key) => find((value) => value.dataset.filter === key);
assert.equal(filterTrigger.children[2].textContent, "0");
assert.equal(filterPopup.children.length, 11);
assert.equal(filterItem("all").children[2].hidden, true, "reset does not invent a count");
assert.equal(filterItem("acknowledged").ariaLabel, "Acknowledged 1");
assert.match(text(pane.element), /Displayed scan: Entire location · incomplete/);
assert.match(text(pane.element), /1 notices from this scan/);
assert.doesNotMatch(text(pane.element), /Other inventory items were not rescanned/);
for (const [scope, expected] of [
  [{kind: "item", path: "folder\\one.txt"}, "Item: folder\\one.txt"],
  [{kind: "folder", path: "folder"}, "Folder: folder (including subfolders)"],
  [{kind: "selection", path: null}, "Selected items"],
]) {
  review.summary = {...review.summary, scan_scope: scope};
  pane.render(task);
  assert.ok(text(pane.element).includes(`Displayed scan: ${expected} · incomplete`));
  assert.ok(statusLine.textContent.includes(`Displayed scan: ${expected}`), "status keeps its compact scope");
  const globalDetails = find((value) => value.classList.contains("nami-plan-review__global-diagnostics"));
  const fullScope = scope.path === null ? expected : expected.replace(scope.path, `${review.summary.root_path}\\${scope.path}`);
  assert.ok(text(globalDetails).includes(`Displayed scan: ${fullScope}`), "global details join the published root");
  assert.match(text(pane.element), /Other inventory items were not rescanned/);
  task.requestId = "f".repeat(32);
  task.sessionState = "refused";
  pane.render(task);
  assert.ok(text(pane.element).includes(`Previous published scan: ${expected}`));
  assert.ok(text(globalDetails).includes(`Previous published scan: ${fullScope}`));
  assert.match(text(pane.element), /Current activity: refused/);
  task.requestId = fixture.views.default.summary.request_id;
  task.sessionState = "completed";
}
review.summary = {...fixture.views.default.summary, scan_request_id: null,
  scan_scope: null, scan_complete: null, observed_count: null, missing_count: null};
pane.render(task);
assert.match(text(pane.element), /Current ledger · No inventory scan/);
assert.doesNotMatch(text(pane.element), /incomplete|observed|notices from this scan/);
review.summary = fixture.views.default.summary;
pane.render(task);
assert.ok(!rowElements().some((value) => text(value).includes("missing.txt")));
assert.ok(rowElements().every((value) => value.children.length === 7));
const real = fixture.views.default.window.rows.find((row) => row.row_id === "1");
const realElement = rowElements().find((value) => value.dataset.nodeId === real.node_id);
assert.equal(realElement.children[5].textContent, "2262-04-11 23:47");
assert.equal(realElement.children[5].title, "Own modified time: 9223372036854775807 ns");
assert.equal(realElement.querySelector(".nami-file-state-label").textContent, "Verified");
assert.equal(rowElements().find((value) => value.dataset.nodeId === fixture.views.default.window.rows.find((row) => row.warning !== null).node_id)
  .querySelector(".nami-file-row__notes").textContent, "read failed");
realElement.click();
assert.equal(details.at(-1)[1], real.node_id);
const root = find((value) => value.getAttribute("role") === "tree");
const viewport = find((value) => value.classList.contains("nami-inventory-review__list"));
viewport.clientHeight += 24;
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
filterTrigger.click();
filterItem("acknowledged").focus();
filterItem("acknowledged").click();
assert.deepEqual(viewChanges.at(-1)[1], { filters: ["acknowledged"] });
review.pending = "view";
pane.render(task);
assert.equal(filterPopup.hidden, false);
assert.equal(document.activeElement, filterItem("acknowledged"));
const pendingChanges = viewChanges.length;
filterItem("present").click();
assert.equal(viewChanges.length, pendingChanges);
review.pending = null;
review.summary = { ...review.summary, filters: ["acknowledged"] };
pane.render(task);
assert.equal(filterTrigger.children[2].textContent, "1");
assert.equal(filterPopup.hidden, false);
filterItem("present").click();
assert.deepEqual(viewChanges.at(-1)[1], { filters: ["acknowledged", "present"] });
filterItem("all").click();
assert.deepEqual(viewChanges.at(-1)[1], { filters: [] });
review.summary = fixture.views.default.summary;
pane.render(task);
assert.equal(filterTrigger.children[2].textContent, "0");
assert.ok(!rowElements().some((value) => text(value).includes("missing.txt")), "All preserves default acknowledged hiding");
pane.dispose();
assert.equal(filterPopup.hidden, true);
assert.equal(documentListeners.get("pointerdown").length, permanentPointerListeners);
assert.equal(viewListeners.get("blur").length, 0);
pane.render(task);
for (const column of ["filename", "size", "mtime"]) {
  for (const [currentColumn, currentDirection, expectedColumn, expectedDirection] of [
    ["path", "ascending", column, "ascending"],
    [column, "ascending", column, "descending"],
    [column, "descending", "path", "ascending"],
  ]) {
    review.summary = {...review.summary, sort_column: currentColumn, sort_direction: currentDirection};
    pane.render(task);
    action(`inventory-sort-${column}`).click();
    assert.deepEqual(viewChanges.at(-1)[1], {sortColumn: expectedColumn, sortDirection: expectedDirection});
  }
}
review.summary = fixture.views.default.summary;
review.detail = { row: real, state: "current", response: fixture.detail };
pane.render(task);
rowElements().find((value) => value.dataset.nodeId === real.node_id).click();
action("inventory-refresh-selected").click();
assert.deepEqual(refreshes.at(-1), [review, real.node_id, action("inventory-refresh-selected")]);
const detail = find((value) => value.ariaLabel === "Inventory item details");
const pathFact = () => {
  const body = detail.children.find((value) => value.tagName === "DL");
  const index = body.children.findIndex((value) => value.tagName === "DT" && ["Path", "Path at scan time"].includes(value.textContent));
  return index === -1 ? null : body.children[index + 1].textContent;
};
assert.equal(pathFact(), `${review.summary.root_path}\\${fixture.detail.detail.row.path}`);
const establishedRoot = review.summary.root_path;
review.summary = { ...review.summary, root_path: null };
pane.render(task);
assert.equal(pathFact(), fixture.detail.detail.row.path, "an absent established root retains relative evidence");
review.summary = { ...review.summary, root_path: establishedRoot };
review.detail = { row: { ...real, row_id: null, is_container: true, display: "Child" },
  state: "current", response: { snapshot: { path: "Parent\\Child", warning: null }, detail: null } };
pane.render(task);
assert.equal(pathFact(), `${establishedRoot}\\Parent\\Child`, "synthetic folder details use the snapshot path rather than the basename");
review.detail = { row: real, state: "current", response: fixture.detail };
pane.render(task);
const diagnostics = find((value) => value.classList.contains("nami-inventory-review__diagnostics"));
assert.equal(diagnostics.hidden, true, "details start hidden without dropping selected evidence");
action("inventory-details").click();
assert.equal(diagnostics.hidden, false);
detail.focus();
action("inventory-details").click();
assert.equal(document.activeElement, action("inventory-details"));
assert.equal(diagnostics.hidden, true);
action("inventory-details").click();
assert.equal(action("inventory-refresh-selected").parentElement.parentElement.parentElement.classList.contains("nami-plan-review__summary"), true);
const modes = walk(pane.element).filter((value) => value.getAttribute("role") === "radio");
assert.deepEqual(modes.map((value) => [value.textContent, value.ariaChecked, value.disabled]), [["Sync", "false", true], ["Integrity", "true", false]]);
const checksumCell = realElement.querySelector(".nami-inventory-row__checksum");
assert.equal(checksumCell.textContent, real.recorded_checksum.slice(0, 8));
assert.ok(checksumCell.title.includes(real.recorded_checksum));
assert.match(text(detail), new RegExp(fixture.detail.detail.attestation.content.digest));
assert.match(text(detail), new RegExp(`Provenance ${fixture.detail.detail.attestation.content.provenance}`));
assert.match(text(detail), /Observed modified 2262-04-11 23:47 \(9223372036854775807 ns\)/);
assert.match(text(detail), /Attested modified 2262-04-11 23:47 \(9223372036854775807 ns\)/);
for (const key of ["Last observed", "Last verified", "Evidence observed"]) {
  assert.ok(text(detail).includes(`${key} 2026-01-02 03:04`));
}
for (const key of ["Missing since", "Acknowledged", "Reappeared", "Verification invalidated"]) {
  assert.ok(text(detail).includes(`${key} Unavailable`));
}
const dateKeys = ["last_observed_at", "last_verified_at", "missing_since", "acknowledged_at",
  "reappeared_at", "verification_invalidated_at"];
review.detail.response = { ...fixture.detail, detail: { ...fixture.detail.detail,
  row: { ...fixture.detail.detail.row, ...Object.fromEntries(dateKeys.map((key) => [key, "2026-12-31T23:04:59.999999+00:00"])) },
} };
process.env.TZ = "Asia/Shanghai";
pane.render(task);
for (const key of ["Last observed", "Last verified", "Missing since", "Acknowledged", "Reappeared", "Verification invalidated"]) {
  assert.ok(text(detail).includes(`${key} 2027-01-01 07:04`));
}
assert.match(text(detail), /Observed modified 2262-04-12 07:47/);
process.env.TZ = "UTC";
review.detail.response = fixture.invalidated_detail;
pane.render(task);
assert.match(text(detail), /Verification state Mismatch/);
assert.match(text(detail), /Invalidation reason hash-mismatch/);
assert.match(text(detail), new RegExp(fixture.invalidated_detail.detail.attestation.content.digest));
const notice = fixture.views.default.window.rows.find((row) => row.warning !== null);
review.detail = { row: notice, state: "current", response: fixture.snapshots[notice.node_id] };
pane.render(task);
assert.equal(pathFact(), `${establishedRoot}\\${fixture.snapshots[notice.node_id].snapshot.path}`);
review.detail = { row: notice, state: "current", response: { ...fixture.snapshots[notice.node_id],
  snapshot: { ...fixture.snapshots[notice.node_id].snapshot, path: null } } };
pane.render(task);
assert.equal(pathFact(), "Unavailable", "a nullable warning path never becomes a path from its label");
review.detail = { row: notice, state: "current", response: fixture.snapshots[notice.node_id] };
pane.render(task);
assert.match(text(detail), /read failed/);
assert.doesNotMatch(text(detail), /Stored digest/);
rowElements().find((value) => value.dataset.nodeId === notice.node_id).click();
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
viewport.scrollTop = 300 * 24; viewport.dispatch("scroll");
while (frames.length) frames.shift()();
assert.equal(pages.length, 1);
assert.equal(pages[0][0], review);
assert.equal(pages[0][1], 268, "downward placement retains 32 rows behind");
const oldCount = rowElements().length;
pane.dispose();
pendingPage(fixture.tail);
await tick();
assert.equal(rowElements().length, oldCount, "retired page reply cannot mutate tree");
assert.equal(observers.at(-1).disconnected, true);
task.inventoryReview = { ...fixture.views.empty, pending: null, message: null, detail: null, queuedSearchQuery: null };
pane.render(task);
assert.equal(rowElements().length, 0);
assert.equal(action("inventory-refresh-selected").disabled, true, "empty windows have no current action target");
assert.match(text(pane.element), /No items match/);
task.inventoryError = "Inventory unavailable. Reload the inventory view to retry.";
task.requestId = "f".repeat(32); task.sessionState = "refused";
pane.render(task); action("inventory-reload").click();
assert.match(text(pane.element), /Current activity: refused/);
assert.match(text(pane.element), /Previous published scan/);
assert.equal(reloads.at(-1), task);
assert.equal(action("inventory-refresh").disabled, false, "prior publication may refresh current task");
assert.equal(action("inventory-acknowledge").disabled, true, "prior publication cannot mutate visibility");
task.inventoryAction = { pending: true, recovery: { canCheck: true, checking: false }, message: "Original pending" };
pane.render(task);
assert.match(statusLine.textContent, /Original pending/);
assert.match(statusLine.textContent, /Inventory unavailable/);
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
let startChecks = 0;
const work = createWorkPanel({onStartInventory: () => { startChecks += 1; }}, {}, document.createElement("div"), {
  onViewChange() {}, onDetail() {}, onWindow() {}, onReload() {},
});
task.sessionReleased = true; task.review = null;
work.render(task);
assert.ok(walk(work.element).some((value) => value.ariaLabel === "Inventory review"));
work.renderSettings();
assert.ok(!walk(work.element).some((value) => value.ariaLabel === "Inventory review"));
const pendingInventory = { taskId: "pending-inventory", label: "Pending", taskKind: null,
  sessionState: null, sessionReleased: false, inventoryReview: null, review: null,
  form: { source: {text: "C:\\pending"}, attempt: { kind: "inventory", running: true, dispatched: false } } };
work.render(pendingInventory);
const pendingPane = () => walk(work.element).find((value) => value.ariaLabel === "Inventory review");
const pendingTitle = () => walk(pendingPane()).find((value) => value.classList.contains("nami-plan-review__status-title"));
assert.equal(pendingTitle().textContent, "Checking folders");
assert.equal(walk(pendingPane()).find((value) => value.classList.contains("nami-inventory-review__content")).hidden, false);
assert.equal(walk(pendingPane()).some((value) => value.getAttribute("role") === "treeitem"), false);
pendingInventory.form.attempt.dispatched = true;
work.render(pendingInventory);
assert.equal(pendingTitle().textContent, "Scanning");
pendingInventory.form.attempt.recovery = {canCheck: true, checking: false, message: "Check original start"};
work.render(pendingInventory);
walk(pendingPane()).find((value) => value.dataset.action === "inventory-check-outcome").click();
assert.equal(startChecks, 1, "start recovery reuses the original setup action");
pendingInventory.form.attempt.running = false;
work.render(pendingInventory);
assert.equal(pendingTitle().textContent, "Outcome unknown");
assert.equal(walk(pendingPane()).find((value) => value.classList.contains("nami-plan-review__progress")).classList.contains("nami-progress--indeterminate"), false);
pendingInventory.form.attempt = null;
work.render(pendingInventory);
assert.equal(walk(work.element).some((value) => value.ariaLabel === "Inventory review"), false,
  "refused admission returns to Setup");
pendingInventory.taskKind = "inventory"; pendingInventory.sessionState = "active";
work.render(pendingInventory);
assert.equal(pendingTitle().textContent, "Scanning", "native active start renders before session release");
pendingInventory.sessionId = "a".repeat(32);
pendingInventory.sessionState = "failed";
pendingInventory.inventoryError = "Scan failed; reload the inventory view.";
work.render(pendingInventory);
assert.equal(pendingTitle().textContent, "Inventory scan failed", "terminal failure keeps its admitted shell before release");
assert.equal(walk(pendingPane()).find((value) => value.classList.contains("nami-plan-review__progress")).classList.contains("nami-progress--indeterminate"), false);

// Exercise the app's fetch and the real pane/tree publication seam together.
const shellNodes = new Map();
document.querySelector = (key) => {
  if (!shellNodes.has(key)) shellNodes.set(key, document.createElement("div"));
  return shellNodes.get(key);
};
document.body = document.createElement("body");
document.documentElement = document.createElement("html");
globalThis.window = { ...document.defaultView, chrome: { webview: {} }, addEventListener() {} };
let viewportReply = null;
let liveReview = null;
const viewportCalls = [];
const viewportPromises = [];
const assertProjectedWindow = (actual, expected, message) => {
  assert.equal(actual.offset, expected.offset, message);
  assert.equal(actual.total, expected.total, message);
  assert.deepEqual(actual.rows, expected.rows, message);
};
globalThis.inventoryViewportPromises = viewportPromises;
const liveDetails = [], liveRefreshes = [];
let admitInitial, startInitial, initialStarts = 0;
globalThis.inventoryViewportHarness = {
  admitLocation: () => new Promise((resolve) => { admitInitial = resolve; }),
  startInventory: () => { initialStarts += 1; return new Promise((resolve) => { startInitial = resolve; }); },
  openInventoryView: () => Promise.resolve(fixture.views.maximum.summary),
  getInventoryWindow: (...args) => {
    viewportCalls.push(args);
    const capturedHighlight = liveReview?.highlightReceipt?.highlight_revision
      ?? liveReview?.summary.highlight_revision ?? 0;
    return (viewportReply?.promise ?? Promise.resolve(args[2] >= 240 ? fixture.tail : liveReview?.window ?? fixture.views.maximum.window))
      .then(window => {
        return {...window, highlight_revision:capturedHighlight};
      });
  },
  mutateInventoryHighlight: (taskId, view, revision, gesture, nodeId) => {
    const rows = [...fixture.views.maximum.window.rows, ...fixture.views.middle.window.rows,
      ...fixture.views.default.window.rows];
    const focus = liveReview.summary.highlight_focus_visible_index;
    const index = gesture.startsWith("move_")
      ? focus === null ? gesture.startsWith("move_down") ? 0 : liveReview.window.total-1
        : Math.max(0, Math.min(liveReview.window.total-1, focus+(gesture.startsWith("move_down") ? 1 : -1)))
      : rows.find(row => row.node_id === nodeId).visible_index;
    const row = rows.find(row => row.visible_index === index && (liveReview.window.total > 100
      ? fixture.views.maximum.window.rows.includes(row) || fixture.views.middle.window.rows.includes(row)
      : fixture.views.default.window.rows.includes(row)));
    return Promise.resolve({...liveReview.summary, highlight_revision:revision+1,
      highlight_anchor_node_id:row.node_id, highlight_focus_node_id:row.node_id,
      highlight_focus_visible_index:index, highlighted_count:1});
  },
  getInventoryDetail: (...args) => {
    liveDetails.push(args);
    return Promise.resolve(fixture.snapshots[args[2]] ?? fixture.detail);
  },
  refreshInventory: (...args) => {
    liveRefreshes.push(args.slice(0, 5));
    return Promise.reject(Object.assign(new Error("capacity"), { code: "inventory_capacity" }));
  },
};
let appSource = await readFile(join(assetRoot, "app.js"), "utf8");
appSource = appSource.replace("onWindow: loadInventoryWindow,", `onWindow: (review, offset) => {
  const promise = loadInventoryWindow(review, offset);
  globalThis.inventoryViewportPromises.push(promise);
  return promise;
},`);
appSource = appSource.replace("const window = await loadInventoryWindow(review, offset);", `const promise = loadInventoryWindow(review, offset);
  globalThis.inventoryViewportPromises.push(promise);
  const window = await promise;`);
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
appSource += "\nexport { adoptTask, selectTask, panel, startCurrentInventory };";
const app = await import(moduleUrl(appSource));
const initialTask = app.adoptTask({task_id: "task-" + "9".repeat(32), session_id: null,
  session_state: null, session_released: false, task_kind: null, request_id: null,
  plan_request_id: null, session_kind: null});
initialTask.form = { editable: true, mode: "inventory", revision: 0, attempt: null,
  source: {text: "C:\\initial", pending: false, candidate: {}, revision: 0, admissionRevision: 0} };
app.selectTask(initialTask.taskId);
const initialStart = app.startCurrentInventory();
const initialPane = () => walk(app.panel.element).find((value) => value.ariaLabel === "Inventory review");
const initialTitle = () => walk(initialPane()).find((value) => value.classList.contains("nami-plan-review__status-title"));
assert.equal(initialTitle().textContent, "Checking folders");
assert.equal(walk(initialPane()).some((value) => value.getAttribute("role") === "treeitem"), false);
admitInitial({purpose: "inventory", choice_id: "initial", display: "C:\\initial", continuation_id: null});
for (let count = 0; count < 12; count += 1) await Promise.resolve();
assert.equal(initialTitle().textContent, "Scanning");
let initialChecks = 0;
initialTask.form.attempt.recovery = {canCheck: true, checking: false, message: "Original scan delayed", check: async () => {
  initialChecks += 1;
  startInitial({task_id: initialTask.taskId, request_id: fixture.views.default.summary.request_id,
    session_id: "9".repeat(32)});
}};
app.panel.render(initialTask);
walk(initialPane()).find((value) => value.dataset.action === "inventory-check-outcome").click();
await initialStart;
assert.equal(initialStarts, 1); assert.equal(initialChecks, 1);
assert.equal(initialTitle().textContent, "Scanning", "adopted active scan retains its loading shell");
assert.equal(walk(initialPane()).some((value) => value.getAttribute("role") === "treeitem"), false,
  "Inventory cannot publish rows before session release");
const liveTask = app.adoptTask({ task_id: fixture.views.maximum.summary.task_id,
  session_id: "3".repeat(32), session_state: "completed", session_released: true,
  task_kind: "inventory", request_id: fixture.views.maximum.summary.request_id,
  plan_request_id: null, session_kind: "inventory" });
const settle = async () => { for (let count = 0; count < 24; count += 1) await Promise.resolve(); };
app.selectTask(liveTask.taskId); await settle();
liveReview = liveTask.inventoryReview;
const treeRoot = walk(app.panel.element).find((value) => value.getAttribute("role") === "tree");
const treeViewport = walk(app.panel.element).find((value) => value.classList.contains("nami-inventory-review__list"));
treeViewport.clientHeight += 24;
const firstLiveRow = () => treeRoot.children.find((value) => value.getAttribute("role") === "treeitem");
const initialWindow = liveReview.window;
const initialNode = firstLiveRow().dataset.nodeId;
const delayedViewport = () => {
  let resolve;
  const promise = new Promise((accept) => { resolve = accept; });
  return { resolve, promise };
};
viewportReply = delayedViewport();
treeViewport.scrollTop = 300 * 24; treeViewport.dispatch("scroll");
while (frames.length) frames.shift()();
assert.equal(viewportCalls.at(-1)[2], 268);
assert.equal(walk(app.panel.element).find((value) => value.dataset.action === "inventory-refresh-selected").disabled,
  true, "a viewport gap clears the current toolbar target");
treeViewport.scrollTop = 280 * 24; treeViewport.dispatch("scroll");
while (frames.length) frames.shift()();
assert.equal(viewportCalls.length, 2, "the second viewport intent waits behind the initial read");
treeViewport.scrollTop = 0; treeViewport.dispatch("scroll");
while (frames.length) frames.shift()();
assert.equal(viewportPromises.length, 2, "reversal replaces intent behind the same physical read");
viewportReply.resolve(fixture.tail); await settle();
assert.equal(await viewportPromises[0], null);
assert.equal(viewportCalls.length, 2, "covered return prevents queued follow-up work");
assert.equal(liveReview.window === initialWindow, true, "retired viewport reply must not enter cached app state");
app.panel.render(liveTask);
assert.equal(firstLiveRow().dataset.nodeId, initialNode, "later render cannot adopt a rejected window");

// Multiple changing positions share one read. Its overlapping response enters
// both the tree and the app cache immediately, before scrolling has stopped.
for (const input of ["wheel", "pointerdown", "touchstart"]) {
viewportReply = delayedViewport();
const burstRead = viewportReply;
const burstCalls = viewportCalls.length;
const burstPromises = viewportPromises.length;
for (const index of [256, 260, 264, 268, 272, 276, 280, 288]) {
  treeRoot.dispatch(input);
  treeViewport.scrollTop = index * 24; treeViewport.dispatch("scroll");
  while (frames.length) frames.shift()();
}
assert.equal(viewportCalls.length, burstCalls + 1);
assert.equal(viewportPromises.length, burstPromises + 1);
assert.equal(liveReview.pending, null, "viewport reads do not enter action-pending state");
assert.equal(liveTask.inventoryAction, null);
burstRead.resolve(fixture.tail); await settle();
assertProjectedWindow(await viewportPromises[burstPromises], fixture.tail);
assertProjectedWindow(liveReview.window, fixture.tail);
assert.equal(treeViewport.scrollTop, 288 * 24);
assert.equal(viewportCalls.length, burstCalls + 1, "the first covering reply needs no replacement RPC");
assert.equal(treeRoot.children.filter((value) => value.getAttribute("role") === "treeitem").length,
  fixture.tail.rows.length);
assert.ok(fixture.tail.rows.length <= 256);
Object.assign(liveReview, fixture.views.maximum, { scrollTop: 0 });
app.panel.render(liveTask);
while (frames.length) frames.shift()();
}

// Failed or refused reads settle only their generation. No automatic retry
// occurs at rest, but a changed user viewport can fetch again.
for (const failure of ["error", "conflict"]) {
  const callsBefore = viewportCalls.length;
  viewportReply = delayedViewport();
  treeViewport.scrollTop = 270 * 24; treeViewport.dispatch("scroll");
  while (frames.length) frames.shift()();
  assert.equal(viewportCalls.length, callsBefore + 1);
  viewportReply.resolve(failure === "error"
    ? Promise.reject(new Error("temporary read failure"))
    : { disposition: "conflict" });
  await settle();
  while (frames.length) frames.shift()();
  assert.equal(viewportCalls.length, callsBefore + 1, "failure does not busy-retry");
  viewportReply = delayedViewport();
  treeViewport.scrollTop = 280 * 24; treeViewport.dispatch("scroll");
  while (frames.length) frames.shift()();
  assert.equal(viewportCalls.length, callsBefore + 2, "changed scrolling retries the failed read");
  viewportReply.resolve(fixture.tail); await settle();
  assertProjectedWindow(liveReview.window, fixture.tail);
  Object.assign(liveReview, fixture.views.maximum, { scrollTop: 0, message: null });
  app.panel.render(liveTask);
  while (frames.length) frames.shift()();
}

// Keyboard replacement shares the app read pump: an old scroll cannot receive
// its result, and only the authoritative endpoint may reveal keyboard focus.
viewportReply = delayedViewport();
const beforeKeyboard = viewportReply;
const keyboardCalls = viewportCalls.length;
treeViewport.scrollTop = 256 * 24; treeViewport.dispatch("scroll");
while (frames.length) frames.shift()();
treeViewport.scrollTop = 280 * 24; treeViewport.dispatch("scroll");
while (frames.length) frames.shift()();
const queuedScroll = viewportPromises.at(-1);
treeRoot.dispatch("keydown", {key:"End"}); await settle();
assert.equal(viewportCalls.length, keyboardCalls+1);
viewportReply = delayedViewport();
beforeKeyboard.resolve(fixture.tail); await settle();
assert.equal(await queuedScroll, null, "keyboard intent retires the held scroll response");
assert.equal(viewportCalls.length, keyboardCalls+2, "only the latest keyboard lookup follows the retired scroll");
const keyboardLookup = viewportReply;
viewportReply = null;
keyboardLookup.resolve(fixture.tail);
await liveReview.highlightQueue;
assert.equal(treeRoot.getAttribute("aria-activedescendant"), treeRoot.children.at(-2).id);
assert.equal(treeViewport.scrollTop, 301*24-(treeViewport.clientHeight-24));

const resetNavigation = () => {
  Object.assign(liveReview, fixture.views.maximum, {scrollTop:0, message:null, highlightReceipt:null});
  app.panel.render(liveTask);
  while (frames.length) frames.shift()();
};
resetNavigation();
// Outside input retires the held absolute endpoint. Reentry follows the server's
// retained focus, even when the tree's viewport-active row differs after scrolling.
for (const [input, fail] of [["pointerdown",false], ["wheel",false], ["touchstart",false], ["keydown",true]]) {
  const row = liveReview.window.rows[10];
  liveReview.summary = {...liveReview.summary, highlight_focus_node_id:row.node_id,
    highlight_anchor_node_id:row.node_id, highlight_focus_visible_index:10, highlighted_count:1};
  viewportReply = delayedViewport();
  const interrupted = viewportReply;
  treeRoot.dispatch("keydown", {key:"End"}); await settle();
  for (const callback of documentListeners.get(input) ?? []) {
    callback({target:document.createElement("button"), key:"ArrowDown"});
  }
  treeRoot.dispatch("keydown", {key:"ArrowDown"});
  assert.notEqual(treeRoot.getAttribute("aria-activedescendant"), firstLiveRow().id.replace(/row-\d+$/, "row-300"));
  viewportReply = null;
  interrupted.resolve(fail ? Promise.reject(new Error("retired outside-input failure")) : fixture.tail);
  await liveReview.highlightQueue;
  assert.equal(liveReview.summary.highlight_focus_visible_index, 11,
    "outside input clears the held endpoint before authoritative keyboard reentry");
  assert.equal(treeRoot.getAttribute("aria-activedescendant"), firstLiveRow().id.replace(/row-\d+$/, "row-11"));
  resetNavigation();
}

viewportReply = delayedViewport();
const heldNavigation = viewportReply;
const heldNavigationCalls = viewportCalls.length;
treeRoot.dispatch("keydown", {key:"End"}); await settle();
for (let index=0; index<25; index+=1) treeRoot.dispatch("keydown", {key:"ArrowDown"});
for (let index=0; index<5; index+=1) treeRoot.dispatch("keydown", {key:"ArrowUp"});
assert.equal(viewportCalls.length, heldNavigationCalls+1, "held keys share one admitted endpoint lookup");
viewportReply = delayedViewport();
heldNavigation.resolve(fixture.tail); await settle();
assert.equal(viewportCalls.length, heldNavigationCalls+2, "only the latest pending endpoint survives");
const finalLookup = viewportReply;
viewportReply = null;
finalLookup.resolve(fixture.tail);
await liveReview.highlightQueue;
assert.equal(liveReview.summary.highlight_focus_visible_index, fixture.tail.total-6,
  "edge repeats clamp each event before reversing five rows");
assert.equal(treeRoot.getAttribute("aria-activedescendant"), firstLiveRow().id.replace(/row-\d+$/, `row-${fixture.tail.total-6}`));
resetNavigation();

for (const cancel of [() => firstLiveRow().click(),
  ...["wheel","pointerdown","touchstart"].map(input => () => treeRoot.dispatch(input)),
  ...["ctrlKey","altKey","metaKey"].map(modifier =>
    () => treeRoot.dispatch("keydown", {key:"ArrowDown", [modifier]:true})),
  () => app.panel.renderSettings()]) {
  viewportReply = delayedViewport();
  const held = viewportReply;
  const retainedWindow = liveReview.window;
  const callsBefore = viewportCalls.length;
  treeRoot.dispatch("keydown", {key:"End"}); await settle();
  treeRoot.dispatch("keydown", {key:"End"});
  cancel();
  assert.equal(viewportCalls.length, callsBefore+1, "replacement and cancellation cannot overlap reads");
  viewportReply = null;
  held.resolve(Promise.reject(new Error("retired viewport failure")));
  await liveReview.highlightQueue;
  assertProjectedWindow(liveReview.window, retainedWindow, "a canceled endpoint cannot replace the retained row scope");
  assert.equal(liveReview.message, null, "retired lookup errors are silent");
  resetNavigation();
}
app.panel.render(liveTask);
const restoredTree = walk(app.panel.element).find((value) => value.getAttribute("role") === "tree");
// Continue the existing witnesses using the recreated controller/root.
assert.equal(restoredTree, treeRoot);
viewportReply = delayedViewport();
treeViewport.scrollTop = 300 * 24; treeViewport.dispatch("scroll");
while (frames.length) frames.shift()();
viewportReply.resolve(fixture.tail); await settle();
assertProjectedWindow(liveReview.window, fixture.tail, "accepted viewport reply becomes the retained window");
assert.equal(firstLiveRow().dataset.nodeId, fixture.tail.rows[0].node_id);
assert.equal(walk(app.panel.element).find((value) => value.dataset.action === "inventory-refresh-selected").disabled,
  false, "accepted viewport adopts eligibility after its window enters the page owner");
const acceptedScroll = treeViewport.scrollTop;
app.panel.render(liveTask);
assert.equal(treeViewport.scrollTop, acceptedScroll, "rendering the accepted window preserves scrolling");
assert.equal(firstLiveRow().dataset.nodeId, fixture.tail.rows[0].node_id);
viewportReply = null;
Object.assign(liveReview, fixture.views.default, { scrollTop: 0 });
app.panel.render(liveTask);
const liveFolder = fixture.views.default.window.rows.find((row) => row.row_kind === "folder");
const liveFile = fixture.views.default.window.rows.find((row) => row.row_id === "1");
const liveRow = (nodeId) => treeRoot.children.find((value) => value.dataset.nodeId === nodeId);
liveRow(liveFolder.node_id).click();
await settle();
const cardSelection = liveReview.detail;
assert.equal(cardSelection.row.node_id, liveFolder.node_id);
assert.deepEqual(cardSelection.response, fixture.snapshots[liveFolder.node_id]);
const liveDiagnostics = walk(app.panel.element).find((value) => value.classList.contains("nami-plan-review__diagnostics"));
assert.equal(liveDiagnostics.hidden, true);
const beforeArrowDetails = liveDetails.length;
treeRoot.dispatch("keydown", {key: "ArrowDown"});
await liveReview.highlightQueue;
assert.equal(treeRoot.getAttribute("aria-activedescendant"), liveRow(liveFile.node_id).id);
assert.equal(liveReview.detail === cardSelection, true, "arrows preserve the card's displayed item");
assert.equal(liveDetails.length, beforeArrowDetails, "highlight navigation does not read details");
assert.equal(liveDiagnostics.hidden, true);
const liveRefreshSelected = walk(app.panel.element).find((value) => value.dataset.action === "inventory-refresh-selected");
assert.equal(liveRefreshSelected.disabled, false);
liveRefreshSelected.click();
liveRefreshSelected.click();
await settle();
assert.equal(liveRefreshes.length, 1, "the page submits one original Refresh despite a pending repeated click");
assert.equal(liveRefreshes[0][0], liveTask.taskId);
assert.equal(liveRefreshes[0][1], liveTask.requestId);
assert.equal(liveRefreshes[0][3], liveReview.summary.view_revision);
assert.equal(liveRefreshes[0][4], liveFile.node_id, "Refresh selected follows the current active row, not the card");
app.panel.renderSettings();
const menuCalls = [];
const menuPane = createInventoryReviewPanel({
  onViewChange: (...args) => menuCalls.push(["view", ...args]),
  onDetail: (...args) => menuCalls.push(["detail", ...args]),
  onWindow: async () => null, onReload: () => {}, onCheckOutcome: () => {},
  onRefresh: (...args) => menuCalls.push(["refresh", ...args]),
  onVisibility: (...args) => menuCalls.push(["visibility", ...args]),
});
const menuRows = fixture.views.default.window.rows.map((row) => row.row_id === "1"
  ? { ...row, presence: "missing", acknowledged: false } : row);
const menuReview = { ...fixture.views.default, pending: null, detail: null,
  window: { ...fixture.views.default.window, rows: menuRows } };
const menuTask = { ...task, inventoryReview: menuReview, inventoryLoading: false,
  closePending: false, closeRecovery: null, inventoryAction: null,
  sessionState: "completed", sessionReleased: true,
  requestId: menuReview.summary.request_id, inventoryViewUnconfirmed: false };
menuPane.render(menuTask);
const menuWalk = () => walk(menuPane.element);
const menuTree = menuWalk().find((value) => value.getAttribute("role") === "tree");
const menuPopup = menuWalk().find((value) => value.classList.contains("nami-row-menu"));
const menuRow = (row) => menuWalk().find((value) => value.dataset.nodeId === row.node_id);
const missingRow = menuRows.find((row) => row.row_id === "1");
const menuFolder = menuRows.find((row) => row.row_kind === "folder");
const menuNotice = menuRows.find((row) => row.warning !== null);
menuReview.detail = { row: menuFolder, state: "current", response: { snapshot: { path: "folder", warning: null }, detail: null } };
menuPane.render(menuTask);
function ownedContext(target, type, fields = {}) {
  let prevented = false, stopped = false;
  target.dispatch(type, {...fields, preventDefault() { prevented = true; },
    stopPropagation() { stopped = true; this.stopped = true; }});
  assert.equal(prevented, true, "owned context gestures suppress browser fallback");
  assert.equal(stopped, true, "owned context gestures do not reach another owner");
}
const menuPointer = (row) => ownedContext(menuRow(row), "contextmenu", {clientX: 1279, clientY: 799});
menuPointer(missingRow);
assert.equal(menuCalls.length, 0, "right-click has no read or mutation effect");
assert.equal(menuReview.detail.row, menuFolder, "opening context preserves unrelated details");
assert.deepEqual(menuPopup.children.map((item) => item.textContent), ["Show details", "Refresh selected", "Acknowledge missing"]);
assert.equal(menuTree.getAttribute("aria-activedescendant"), menuRow(missingRow).id);
menuPopup.children[2].click();
assert.deepEqual(menuCalls.at(-1), ["visibility", menuReview, "acknowledge", missingRow.node_id]);
assert.equal(menuPopup.hidden, true);
assert.equal(document.activeElement, menuTree);
menuTree.dispatch("keydown", {key: "F10", shiftKey: true});
assert.equal(menuPopup.hidden, false, "keyboard context uses the tree active row");
menuPopup.children[0].click();
assert.deepEqual(menuCalls.at(-1), ["detail", menuReview, missingRow.node_id]);
assert.equal(menuWalk().find((value) => value.classList.contains("nami-plan-review__diagnostics")).hidden, false);
menuPointer(missingRow);
menuPopup.children[1].click();
assert.deepEqual(menuCalls.at(-1), ["refresh", menuReview, missingRow.node_id, menuRow(missingRow)]);
menuPointer(menuFolder);
assert.equal(menuPopup.children.some((value) => value.dataset.action === "row-acknowledge"), false,
  "missing descendant counts do not authorize context acknowledgement of a present folder");
assert.ok(menuPopup.children.some((value) => value.dataset.action === "row-refresh"));
menuPointer(menuNotice);
assert.deepEqual(menuPopup.children.map((item) => item.textContent), ["Show details"]);
menuReview.detail = { row: missingRow, state: "current", response: fixture.detail };
menuPane.render(menuTask);
assert.equal(menuWalk().find((value) => value.dataset.action === "inventory-refresh-selected").disabled,
  true, "an active notice disables Refresh even when an eligible card is retained");
menuPointer(menuFolder);
menuWalk().find((value) => value.dataset.action === "inventory-acknowledge").click();
assert.deepEqual(menuCalls.at(-1), ["visibility", menuReview, "acknowledge", missingRow.node_id],
  "acknowledgement retains the card item while a different row is active");
menuReview.detail = { ...menuReview.detail, row: { ...missingRow, acknowledged: true } };
menuPane.render(menuTask);
menuWalk().find((value) => value.dataset.action === "inventory-restore").click();
assert.deepEqual(menuCalls.at(-1), ["visibility", menuReview, "restore", missingRow.node_id],
  "Restore retains the card item while a different row is active");
assert.equal(menuWalk().find((value) => value.dataset.action === "inventory-refresh-selected").disabled, false);
menuPointer(missingRow);
const staleAcknowledge = menuPopup.children[2];
menuReview.pending = "view";
menuPane.render(menuTask);
const menuBeforeStale = menuCalls.length;
menuPointer(missingRow);
ownedContext(menuTree, "keydown", {key: "F10", shiftKey: true});
assert.equal(menuPopup.hidden, true);
staleAcknowledge.click();
assert.equal(menuCalls.length, menuBeforeStale);
assert.equal(menuPopup.hidden, true);
menuReview.pending = null;
menuTask.inventoryViewUnconfirmed = true;
menuPane.render(menuTask);
menuPointer(missingRow);
assert.deepEqual(menuPopup.children.map((item) => item.textContent), ["Show details", "Refresh selected"]);
menuTask.closePending = true;
menuPane.render(menuTask);
assert.equal(menuPopup.hidden, true);
menuTask.closePending = false;
menuTask.inventoryViewUnconfirmed = false;
menuPane.render(menuTask);
menuPointer(missingRow);
menuPopup.dispatch("keydown", {key: "Escape"});
assert.equal(document.activeElement, menuTree);
assert.equal(menuTree.getAttribute("aria-activedescendant"), menuRow(missingRow).id);
menuTree.dispatch("keydown", {key: "ContextMenu"});
assert.equal(menuPopup.hidden, false);
const missingInvoker = menuRow(missingRow);
menuReview.window = {...menuReview.window, rows:menuRows.filter(row => row !== missingRow)};
const beforeMissingOwner = menuCalls.length;
ownedContext(missingInvoker, "contextmenu", {clientX: 200, clientY: 200});
assert.equal(menuCalls.length, beforeMissingOwner, "a missing current-window node cannot dispatch");
menuPane.render(menuTask);
assert.equal(menuPopup.hidden, true);
ownedContext(missingInvoker, "contextmenu", {clientX: 200, clientY: 200});
assert.equal(menuPopup.hidden, true);
assert.equal(menuCalls.length, beforeMissingOwner);
menuPane.dispose();
staleAcknowledge.click();
assert.equal(menuCalls.length, menuBeforeStale);
const folderCalls = [];
const folderPane = createInventoryReviewPanel({
  onViewChange: () => {}, onDetail: () => {}, onWindow: async () => null,
  onReload: () => {}, onCheckOutcome: () => {}, onRefresh: () => {},
  onVisibility: (...args) => folderCalls.push(args),
});
const folderReview = {...fixture.missing_folder, pending:null, detail:null};
const folderTask = {...menuTask, inventoryReview:folderReview,
  requestId:folderReview.summary.request_id};
folderPane.render(folderTask);
const folderDomain = folderReview.window.rows.find(row => row.row_id === "3");
assert.equal(folderDomain.is_container, true);
assert.equal(folderDomain.presence, "missing");
const folderElement = walk(folderPane.element).find(value => value.dataset.nodeId === folderDomain.node_id);
ownedContext(folderElement, "contextmenu", {clientX: 200, clientY: 200});
const folderPopup = walk(folderPane.element).find(value => value.classList.contains("nami-row-menu"));
assert.ok(folderPopup.children.some(value => value.dataset.action === "row-acknowledge"));
assert.equal(folderPopup.children.some(value => /restore/i.test(value.textContent)), false);
folderPopup.children.find(value => value.dataset.action === "row-acknowledge").click();
assert.deepEqual(folderCalls, [[folderReview, "acknowledge", folderDomain.node_id]]);
folderPane.dispose();
const presentationRows = [
  {...real, node_id:"presence-return", reappeared:true, verification_state:"unverified"},
  {...real, node_id:"presence-mismatch", reappeared:true, verification_state:"mismatched"},
  {...real, node_id:"presence-missing", presence:"missing", acknowledged:true},
  {...real, node_id:"partial-folder", row_id:null, presence:null, verification_state:null,
    is_container:true, expanded:false, rollup:{...real.rollup, size_partial:true, size_overflow:false}},
  {...real, node_id:"overflow-folder", row_id:null, presence:null, verification_state:null,
    is_container:true, expanded:false, rollup:{...real.rollup, size_partial:false, size_overflow:true}},
].map((row, index) => ({...row, visible_index:index}));
const presentationReview = {...fixture.views.default, pending:null, detail:null,
  window:{...fixture.views.default.window, offset:0, total:presentationRows.length, rows:presentationRows}};
const presentationTask = {...menuTask, inventoryReview:presentationReview};
const paneChanges = [], copiedStarts = [];
const presentationPane = createInventoryReviewPanel({onViewChange:()=>{}, onDetail:()=>{},
  onWindow:async()=>null, onReload:()=>{}, onCheckOutcome:()=>{}, onRefresh:()=>{}, onVisibility:()=>{},
  onPaneChange:(...args)=>paneChanges.push(args), onCopiedStart:(...args)=>copiedStarts.push(args)});
presentationPane.render(presentationTask);
const presented = walk(presentationPane.element).filter(value => value.getAttribute("role") === "treeitem");
assert.deepEqual(presented.map(value => value.querySelector(".nami-file-state-label").textContent),
  ["Reappeared", "Mismatch", "Missing", "Folder", "Folder"]);
assert.deepEqual(presented.map(value => value.querySelector(".nami-file-row__notes").textContent),
  ["", "", "Acknowledged", "Partial size", "Size overflow"]);
assert.equal(presented[0].querySelector(".nami-inventory-row__checksum").textContent, real.recorded_checksum.slice(0, 8));
assert.equal(presented[1].querySelector(".nami-integrity-row__presence").dataset.integrity, "mismatched");
for (const [phase, label] of [["baseline", "Baseline"], ["verify", "Verification"], ["rebaseline", "Rebaseline"]]) {
  presentationTask.sessionState = "completed";
  presentationTask.snapshot = {terminal_result: {phases: [{phase}]}};
  presentationPane.render(presentationTask);
  assert.equal(presentationPane.element.querySelector(".nami-plan-review__status-title").textContent, `${label} completed`);
}
const overlayItem = {row_id:real.row_id, result:"verified", reason:null, recording:"ok",
  record_disposition:null, detail_omitted_count:0};
const overlay = {request_id:"c".repeat(32), session_id:"d".repeat(32), mode:"verify",
  location_id:presentationReview.summary.location_id, revision:1, complete:false, gap:true,
  items:[overlayItem]};
presentationTask.requestId = overlay.request_id;
presentationTask.sessionId = overlay.session_id;
presentationTask.sessionKind = "verify";
presentationTask.sessionState = "active";
presentationTask.sessionReleased = false;
presentationTask.snapshot = null;
presentationReview.window = {...presentationReview.window, integrity:overlay};
presentationReview.detail = {row:presentationRows[0], state:"current", response:{...fixture.detail,
  detail:{...fixture.detail.detail, attestation:null}, integrity:overlay}};
presentationPane.render(presentationTask);
assert.match(walk(presentationPane.element).find(value => Object.hasOwn(value.dataset, "integrityResult")).textContent,
  /Live verification results may be incomplete · 1 window result/);
assert.equal(walk(presentationPane.element).find(value => Object.hasOwn(value.dataset, "integrityState")).dataset.integrityState,
  "verified");
assert.ok(walk(presentationPane.element).some(value => value.classList.contains("nami-file-state-label")
  && value.textContent === "Verification: Verified"));
for (const [mode, owner, result] of [["baseline", "Baseline", "baselined"],
  ["rebaseline", "Rebaseline", "baselined"]]) {
  presentationReview.window = {...presentationReview.window,
    integrity:{...overlay, mode, items:[{...overlayItem, result}]}};
  presentationPane.render(presentationTask);
  assert.ok(walk(presentationPane.element).some(value => value.classList.contains("nami-file-state-label")
    && value.textContent === `${owner}: Baselined`), `${owner} owns its row result label`);
}
presentationReview.window = {...presentationReview.window, integrity:overlay};
presentationPane.render(presentationTask);
assert.match(text(walk(presentationPane.element).find(value => value.ariaLabel === "Inventory item details")),
  /Verification result Verified.*Stored digest No baseline evidence/,
  "ordinary detail remains visible when ledger attestation is absent");
presentationReview.window = {...presentationReview.window,
  integrity:{...overlay, revision:2, complete:true, gap:false, items:[]}};
presentationTask.sessionState = "completed";
presentationTask.sessionReleased = true;
presentationTask.snapshot = {session_id:overlay.session_id, session_state:"completed", phase:"verify",
  presentation:{value:100, determinate:true, indeterminate:false, items_done:0, items_total:0},
  terminal_result:{headline:"partial", disposition:"completed", error:"One result needs review",
    phases:[{phase:"verify"}]}};
presentationPane.render(presentationTask);
assert.match(walk(presentationPane.element).find(value => Object.hasOwn(value.dataset, "integrityResult")).textContent,
  /Verification retained results · 0 window results/);
assert.equal(walk(presentationPane.element).some(value => Object.hasOwn(value.dataset, "integrityState")), false,
  "terminal zero-result replacement removes the live subset");
assert.equal(presentationPane.element.querySelector(".nami-plan-review__status-title").textContent,
  "Verification needs review", "terminal reconciliation is not presented as successful completion");
presentationReview.window = {...presentationReview.window,
  integrity:{...overlay, revision:3, complete:true, gap:false}};
presentationTask.requestId = "e".repeat(32);
presentationTask.sessionId = "f".repeat(32);
presentationTask.sessionKind = "inventory";
presentationTask.sessionState = "active";
presentationTask.sessionReleased = false;
presentationTask.snapshot = null;
presentationPane.render(presentationTask);
assert.equal(walk(presentationPane.element).find(value => Object.hasOwn(value.dataset, "integrityState")).dataset.integrityState,
  "verified", "a later Refresh retains the latest ordinary result generation");

Object.assign(presentationTask, {taskKind:"sync-plan", executionStarted:true, workPane:"verify",
  sessionKind:"inventory", sessionState:"completed", sessionReleased:true, snapshot:null,
  requestId:presentationReview.summary.request_id, planRequestId:"original-plan", executionSessionId:"original-execution",
  originalExecutionFact:{planRequestId:"original-plan", execution:{session_id:"original-execution",
    execution_revision:7, has_successful_copied_files:true}}});
presentationPane.render(presentationTask);
const presentationAction = key => walk(presentationPane.element).find(value => value.dataset.action === key);
assert.equal(presentationAction("inventory-baseline").hidden, true);
assert.equal(presentationAction("inventory-rebaseline").hidden, true);
assert.equal(presentationAction("inventory-verify").hidden, false);
assert.equal(presentationAction("inventory-verify").textContent, "Verify current state");
assert.equal(presentationAction("verify-copied-files").hidden, false);
presentationAction("verify-copied-files").click();
assert.deepEqual(copiedStarts, [[presentationReview]]);
const retainedCopiedFact = presentationTask.originalExecutionFact;
presentationReview.summary = {...presentationReview.summary, selected_file_count:1};
presentationTask.originalExecutionFact = {...retainedCopiedFact,
  execution:{...retainedCopiedFact.execution, has_successful_copied_files:false}};
presentationPane.render(presentationTask);
assert.equal(presentationAction("verify-copied-files").disabled, true);
presentationAction("verify-copied-files").click();
assert.equal(copiedStarts.length, 1, "a known-empty copied scope cannot start");
assert.match(text(presentationPane.element), /Execution copied no files successfully\. Select files and use Verify current state\./);
assert.equal(presentationAction("inventory-verify").disabled, false, "selected Verify stays independent");
for (const unknown of [null,
  {...retainedCopiedFact, execution:{...retainedCopiedFact.execution, has_successful_copied_files:null}},
  {...presentationTask.originalExecutionFact, planRequestId:"foreign-plan"},
  {...presentationTask.originalExecutionFact, execution:{...presentationTask.originalExecutionFact.execution, session_id:"foreign-execution"}},
]) {
  presentationTask.originalExecutionFact = unknown;
  presentationPane.render(presentationTask);
  assert.equal(presentationAction("verify-copied-files").disabled, false, "unavailable/foreign truth is not empty");
  assert.doesNotMatch(text(presentationPane.element), /Execution copied no files successfully/);
}
presentationTask.originalExecutionFact = retainedCopiedFact;
presentationPane.render(presentationTask);
presentationAction("pane-plan").click();
assert.deepEqual(paneChanges.at(-1), [presentationTask, "plan"]);
presentationPane.dispose();

// A passive selection receipt keeps the live outer viewport and focused checkbox.
const highlightCalls = [], highlightedSelections = [];
const alignedReview = {...fixture.views.maximum, pending:null, message:null, detail:null,
  queuedSearchQuery:null, scrollTop:0};
const alignedTask = {...task, taskKind:"inventory", requestId:alignedReview.summary.request_id,
  sessionState:"completed", sessionReleased:true, inventoryReview:alignedReview,
  closePending:false, inventoryLoading:false, inventoryAction:null};
const alignedPane = createInventoryReviewPanel({
  onHighlight:(...args) => highlightCalls.push(args),
  onHighlightedSelect:(...args) => highlightedSelections.push(args),
  onDetail() {}, onWindow:async () => fixture.tail,
});
alignedPane.render(alignedTask);
const alignedTree = alignedPane.element.querySelector(".nami-inventory-review__rows");
const alignedViewport = alignedPane.element.querySelector(".nami-inventory-review__list");
const alignedRows = () => alignedTree.children.filter(value => value.dataset.nodeId !== undefined);
for (const [properties, gesture] of [[{}, "replace"], [{ctrlKey:true}, "toggle"],
  [{shiftKey:true}, "extend"], [{ctrlKey:true, shiftKey:true}, "add-range"]]) {
  alignedRows()[1].dispatch("click", properties);
  assert.deepEqual(highlightCalls.at(-1), [alignedReview, gesture, alignedReview.window.rows[1].node_id]);
}
alignedTree.dispatch("keydown", {key:"ArrowDown", shiftKey:true});
assert.deepEqual(highlightCalls.at(-1), [alignedReview, "move_down_extend", null]);
alignedTree.dispatch("keydown", {key:"Escape"});
assert.deepEqual(highlightCalls.at(-1), [alignedReview, "clear", null]);
alignedViewport.scrollTop = 280 * 24;
alignedViewport.dispatch("scroll");
alignedReview.window = {...fixture.tail, rows:fixture.tail.rows.map(row => ({...row, highlighted:true}))};
alignedPane.render(alignedTask);
const alignedCheckbox = alignedRows()[5].querySelector(".nami-checkbox");
alignedCheckbox.focus();
alignedCheckbox.checked = true;
alignedCheckbox.dispatch("change");
assert.deepEqual(highlightedSelections.at(-1), [alignedReview, true]);
const retainedTop = alignedViewport.scrollTop;
alignedViewport.dispatch("scroll");
alignedReview.pending = "selection";
alignedPane.render(alignedTask);
assert.equal(Boolean(alignedCheckbox.disabled), true);
// Chromium blurs a focused checkbox when the pending render disables it.
document.activeElement = document.body;
alignedReview.window = {...alignedReview.window, rows:alignedReview.window.rows.map(row => ({...row, selection:"all"}))};
alignedPane.render(alignedTask);
alignedReview.pending = null;
alignedPane.render(alignedTask);
assert.equal(alignedViewport.scrollTop, retainedTop, "selection replacement preserves nonzero outer viewport");
assertSameNode(document.activeElement, alignedRows()[5].querySelector(".nami-checkbox"),
  "selection replacement restores the checked row's checkbox focus");

for (const interruption of ["focus", "input", "outside", "dispose"]) {
  alignedRows()[5].querySelector(".nami-checkbox").focus();
  alignedReview.pending = "selection";
  alignedPane.render(alignedTask);
  document.activeElement = document.body;
  if (interruption === "focus") {
    walk(alignedPane.element).find(value => value.dataset.action === "inventory-search").focus();
    document.activeElement = document.body;
  } else if (interruption === "input") alignedViewport.dispatch("pointerdown");
  else if (interruption === "outside") {
    for (const callback of documentListeners.get("keydown") ?? []) callback({target:document.body, key:"Tab"});
  } else alignedPane.dispose();
  alignedReview.window = {...alignedReview.window, rows:[...alignedReview.window.rows]};
  alignedPane.render(alignedTask);
  alignedReview.pending = null;
  alignedPane.render(alignedTask);
  assertSameNode(document.activeElement, document.body,
    `settled selection cannot restore checkbox focus after newer ${interruption}`);
}
const alignedHeader = walk(alignedPane.element).find(value => value.dataset.action === "inventory-select-location");
alignedHeader.focus();
alignedReview.pending = "selection";
alignedPane.render(alignedTask);
assert.equal(Boolean(alignedHeader.disabled), true);
document.activeElement = document.body;
alignedReview.pending = null;
alignedPane.render(alignedTask);
assertSameNode(document.activeElement, alignedHeader, "settled selection restores the matching-scope header checkbox");

// Copied-file verification renders the same bounded ordinary result generation.
const maximumRows = fixture.views.maximum.window.rows;
const costItems = maximumRows.filter(row => row.row_id !== null).map(row => ({...overlayItem, row_id:row.row_id}));
alignedTask.taskKind = "sync-plan";
alignedTask.executionStarted = true;
alignedTask.workPane = "verify";
alignedReview.window = {...fixture.views.maximum.window,
  integrity:{...overlay, location_id:alignedReview.summary.location_id, items:costItems}};
alignedPane.render(alignedTask);
assert.equal(walk(alignedPane.element).filter(value => Object.hasOwn(value.dataset, "integrityState")).length,
  costItems.length);
const alignedAction = name => walk(alignedPane.element).find(value => value.dataset.action === name);
assert.equal(alignedAction("inventory-refresh").classList.contains("nami-button--primary"), false);
assert.equal(alignedAction("verify-copied-files").classList.contains("nami-button--primary"), true);
alignedTask.taskKind = "inventory"; alignedPane.render(alignedTask);
assert.equal(alignedAction("inventory-refresh").classList.contains("nami-button--primary"), true);
alignedPane.dispose();
process.stdout.write("ok\n");
