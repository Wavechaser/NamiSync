import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const ROW_HEIGHT = 24;

class ClassList {
  constructor(owner) { this.owner = owner; this.values = new Set(); }
  add(...values) { for (const value of values) this.values.add(value); }
  contains(value) {
    return this.values.has(value) || this.owner.className.split(/\s+/).includes(value);
  }
}

class Style {
  constructor() { this.values = new Map(); }
  setProperty(name, value) { this.values.set(name, String(value)); }
  getPropertyValue(name) { return this.values.get(name) ?? ""; }
}

class ElementFake {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.parentElement = null;
    this.className = "";
    this.classList = new ClassList(this);
    this.dataset = {};
    this.style = new Style();
    this.listeners = new Map();
    this.attributes = new Map();
    this.value = "";
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.checked = false;
    this.indeterminate = false;
    this.scrollTop = 0;
    this.clientHeight = 0;
  }

  append(...values) {
    for (const value of values) {
      if (value.tagName === "#FRAGMENT") {
        this.append(...value.children);
        value.children = [];
      } else {
        value.remove?.();
        value.parentElement = this;
        this.children.push(value);
      }
    }
  }

  replaceChildren(...values) {
    for (const child of this.children) child.parentElement = null;
    this.children = [];
    this.append(...values);
  }

  replaceWith(value) {
    if (this.parentElement === null) return;
    const index = this.parentElement.children.indexOf(this);
    this.parentElement.children[index] = value;
    value.parentElement = this.parentElement;
    this.parentElement = null;
  }

  remove() {
    if (this.parentElement === null) return;
    this.parentElement.children = this.parentElement.children.filter((item) => item !== this);
    this.parentElement = null;
  }

  addEventListener(name, callback) {
    const listeners = this.listeners.get(name) ?? [];
    listeners.push(callback);
    this.listeners.set(name, listeners);
  }

  dispatch(name, properties = {}) {
    const event = { target: this, currentTarget: this, preventDefault() {}, ...properties };
    for (const callback of this.listeners.get(name) ?? []) callback(event);
  }

  getBoundingClientRect() {
    const index = this.parentElement?.children.indexOf(this) ?? -1;
    const widths = [32, 300, 100, 130, 112, 112, 300];
    return { width: this.classList.contains("nami-file-list__header-cell")
      ? widths[index] : 100 };
  }

  setAttribute(name, value) { this.attributes.set(name, String(value)); }

  querySelector(selector) {
    const className = selector.startsWith(".") ? selector.slice(1) : null;
    for (const child of this.children) {
      if (className !== null && child.classList.contains(className)) return child;
      const nested = child.querySelector?.(selector);
      if (nested !== null && nested !== undefined) return nested;
    }
    return null;
  }
}

class DocumentFake {
  constructor() {
    this.activeElement = null;
    this.documentElement = new ElementFake("html", this);
    this.defaultView = {
      frames: [],
      listeners: new Map(),
      addEventListener(name, callback) {
        const listeners = this.listeners.get(name) ?? [];
        listeners.push(callback);
        this.listeners.set(name, listeners);
      },
      removeEventListener(name, callback) {
        this.listeners.set(name, (this.listeners.get(name) ?? []).filter((item) => item !== callback));
      },
      dispatch(name, properties = {}) {
        for (const callback of this.listeners.get(name) ?? []) callback(properties);
      },
      ResizeObserver: class {
        constructor(callback) { this.callback = callback; }
        observe() {}
        disconnect() { this.disconnected = true; }
      },
      requestAnimationFrame: (callback) => {
        this.defaultView.frames.push(callback);
        return this.defaultView.frames.length;
      },
      flushAnimationFrame: () => {
        const callbacks = this.defaultView.frames.splice(0);
        for (const callback of callbacks) callback();
      },
    };
  }
  createElement(tagName) { return new ElementFake(tagName, this); }
  createDocumentFragment() { return new ElementFake("#fragment", this); }
}

globalThis.Element = ElementFake;
globalThis.HTMLElement = ElementFake;
globalThis.HTMLInputElement = ElementFake;
globalThis.document = new DocumentFake();
globalThis.window = document.defaultView;
globalThis.getComputedStyle = () => ({ fontSize: "16px" });

function moduleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

const renderSource = await readFile(process.argv[3], "utf8");
const renderUrl = moduleUrl(renderSource);
const iconsUrl = moduleUrl(await readFile(process.argv[4], "utf8"));
const planUrl = moduleUrl(`
  export function renderPlanRow(element, row) {
    element.className = "nami-file-row nami-plan-row";
    element.dataset.folder = String(row.folder);
    element.textContent = row.nameText;
    const checkbox = document.createElement("input");
    checkbox.className = "nami-checkbox";
    checkbox.checked = row.checked;
    checkbox.disabled = row.selectionDisabled;
    const name = document.createElement("div");
    name.className = "nami-file-row__name";
    const disclosure = document.createElement(row.folder ? "button" : "span");
    disclosure.className = row.folder
      ? "nami-file-row__disclosure"
      : "nami-file-row__disclosure-spacer";
    name.append(disclosure);
    const notes = document.createElement("span");
    notes.textContent = row.notesText;
    element.append(checkbox, name, notes);
  }
`);
const source = (await readFile(process.argv[2], "utf8"))
  .replace("./plan.js", planUrl)
  .replace("./icons.js", iconsUrl)
  .replace("./render.js", renderUrl);
const { createPlanReviewPanel } = await import(moduleUrl(source));

const calls = [];
const callbacks = Object.fromEntries([
  "onViewChange", "onWindow", "onSelect", "onScopeSelect", "onExecute", "onControl", "onPlanAgain",
].map((name) => [name, (...args) => calls.push([name, ...args])]));
const panel = createPlanReviewPanel(callbacks);
const historicalFooter = document.createElement("div");
const historicalAcknowledgment = document.createElement("input");
historicalAcknowledgment.type = "checkbox";
historicalAcknowledgment.dataset.action = "destructive-confirmation";
historicalAcknowledgment.checked = true;
historicalFooter.append(historicalAcknowledgment);
const hostile = "<img src=x onerror=alert(1)>\u202e海";
const row = {
  node_id: `node-${"1".repeat(32)}`,
  display: hostile,
  depth: 1,
  is_container: true,
  visible_index: 10,
  parent_visible_index: 0,
  first_child_visible_index: 11,
  position_in_set: 1,
  set_size: 1,
  expanded: true,
  row_kind: "operation-group",
  operation_id: null,
  operation_kind: null,
  reason: null,
  blocked_reason: null,
  selection: "mixed",
  selectable_operation_count: 2,
  selected_operation_count: 1,
  operation_count: 2,
  size: null,
  mtime_ns: null,
  dependency_count: 0,
  risk: "none",
  move_peer_id: null,
  notice: null,
  selection_exclusion_reason: null,
};
const summary = {
  disposition: "opened",
  task_id: `task-${"2".repeat(32)}`,
  request_id: "3".repeat(32),
  view_revision: 0,
  selection_revision: 0,
  selection_state: "reviewing",
  source_path: `C:\\${hostile}`,
  target_path: "D:\\target",
  selected_operation_count: 1,
  selectable_operation_count: 2,
  operation_count: 2,
  scope_selected_operation_count: 1,
  scope_selectable_operation_count: 2,
  preflight_ready: false,
  preflight_refusal_count: 1,
  warning_count: 1,
  requires_destructive_confirmation: true,
  destructive_operation_count: 1,
  destructive_operation_counts: { update: 1, move_update: 0, trash: 0, delete: 0 },
  irreversible_operation_count: 1,
  irreversible_update_count: 1,
  required_bytes: "4096",
  visible_row_count: 1000,
  search_query: "",
  filters: [],
  sort_column: "path",
  sort_direction: "ascending",
  collapsed_count: 0,
};
const review = {
  summary,
  window: { disposition: "current", view_revision: 0, offset: 10, total: 1000, rows: [row] },
  pending: null,
  message: "Inspect the refusal.",
};
const task = {
  review,
  error: null,
  canPlanAgain: true,
  executionStarted: false,
  sessionState: "completed",
  executionControlState: "running",
  closePending: false,
  executionAttempt: null,
};

const notice = {
  ...row,
  node_id: `node-${"4".repeat(32)}`,
  display: "Preflight refused",
  is_container: false,
  row_kind: "notice",
  selection: "disabled",
  selectable_operation_count: 0,
  selected_operation_count: 0,
  operation_count: 0,
  notice: hostile,
};
review.window.rows.push(notice);

panel.render(task);
assert.equal(panel.element.dataset.pending, "");
document.defaultView.flushAnimationFrame();
assert.ok(findText(panel.element, hostile));
assert.ok(findText(panel.element, "1 destructive"));
assert.ok(findText(panel.element, "4 KiB required"));
const grid = findByClass(panel.element, "nami-file-list__grid--plan");
const sizeResizer = findByDataset(panel.element, "column", "size");
assert.ok(grid && sizeResizer);
sizeResizer.dispatch("pointerdown", { clientX: 100 });
window.dispatch("pointermove", { clientX: 120 });
assert.equal(grid.style.getPropertyValue("--nami-file-column-size"), "120.000px");
assert.equal(grid.style.getPropertyValue("--nami-file-column-notes"), "280.000px");
window.dispatch("pointerup");
assert.equal(window.listeners.get("pointermove").length, 0);
sizeResizer.dispatch("keydown", { key: "ArrowRight" });
assert.equal(grid.style.getPropertyValue("--nami-file-column-size"), "128.000px");
assert.equal(grid.style.getPropertyValue("--nami-file-column-notes"), "272.000px");
const renderedRow = findByDataset(panel.element, "nodeId", row.node_id);
panel.render(task);
assert.equal(findByDataset(panel.element, "nodeId", row.node_id), renderedRow,
  "unchanged review rendering preserves row controls and focus");
document.defaultView.flushAnimationFrame();
assert.equal(renderedRow.dataset.folder, "false", "operation groups remain non-folder rows");
assert.equal(renderedRow.textContent, hostile);
assert.ok(findText(renderedRow, "Risk: none"));
const renderedNotice = findByDataset(panel.element, "nodeId", notice.node_id);
assert.equal(renderedNotice.dataset.folder, "false");
assert.ok(findText(renderedNotice, hostile), "notice context renders as inert text");
assert.equal(
  findByClass(renderedRow, "nami-plan-review__spacer"),
  null,
);
const groupDisclosure = findByClass(renderedRow, "nami-file-row__disclosure");
groupDisclosure.dispatch("click");
assert.deepEqual(calls.at(-1).slice(0, 2), ["onViewChange", review]);
assert.deepEqual(calls.at(-1)[2], {
  collapseNodeId: row.node_id,
  collapsed: true,
});

const checkbox = findByClass(renderedRow, "nami-checkbox");
checkbox.checked = false;
checkbox.dispatch("change");
assert.deepEqual(calls.at(-1), ["onSelect", review, row, false]);

const scopeCheckbox = findByClass(panel.element, "nami-plan-review__scope-checkbox");
assert.ok(scopeCheckbox);
assert.equal(scopeCheckbox.indeterminate, true);
scopeCheckbox.checked = true;
scopeCheckbox.dispatch("change");
assert.deepEqual(calls.at(-1), ["onScopeSelect", review, true]);

const sizeSort = findByDataset(panel.element, "sortColumn", "size");
const nameSort = findByDataset(panel.element, "sortColumn", "filename");
assert.ok(sizeSort && nameSort);
sizeSort.dispatch("click");
assert.deepEqual(calls.at(-1), ["onViewChange", review,
  { sortColumn: "size", sortDirection: "ascending" }]);
review.summary = { ...review.summary, sort_column: "size", sort_direction: "ascending" };
panel.render(task);
sizeSort.dispatch("click");
assert.deepEqual(calls.at(-1), ["onViewChange", review,
  { sortColumn: "size", sortDirection: "descending" }]);
review.summary = { ...review.summary, sort_direction: "descending" };
panel.render(task);
nameSort.dispatch("click");
assert.deepEqual(calls.at(-1), ["onViewChange", review,
  { sortColumn: "filename", sortDirection: "ascending" }]);
review.summary = { ...review.summary, sort_column: "filename", sort_direction: "ascending" };
panel.render(task);
nameSort.dispatch("click");
review.summary = { ...review.summary, sort_direction: "descending" };
panel.render(task);
nameSort.dispatch("click");
assert.deepEqual(calls.at(-1), ["onViewChange", review,
  { sortColumn: "path", sortDirection: "ascending" }]);

const noticeFilter = findByDataset(panel.element, "operation", "notice");
noticeFilter.dispatch("click");
assert.deepEqual(calls.at(-1), ["onViewChange", review,
  { filters: new Set(["notice"]) }]);
assert.equal(noticeFilter.ariaPressed, "true");
assert.equal(
  calls.filter(([name]) => name === "onScopeSelect").length,
  1,
  "filter navigation does not imply scoped selection",
);

const search = findAction(panel.element, "plan-search");
search.value = hostile;
search.dispatch("input");
await new Promise((resolve) => setTimeout(resolve, 175));
assert.deepEqual(calls.at(-1), ["onViewChange", review, { searchQuery: hostile }]);

assert.equal(
  findByDataset(panel.element, "action", "destructive-confirmation"),
  null,
  "the stale persistent acknowledgment control is absent",
);
findAction(panel.element, "execute").dispatch("click");
assert.deepEqual(calls.at(-1), ["onExecute", review, findAction(panel.element, "execute")]);

task.canPlanAgain = false;
panel.render(task);
assert.equal(findAction(panel.element, "plan-again").disabled, true);
task.canPlanAgain = true;

review.summary = {
  ...summary,
  request_id: "5".repeat(32),
  selection_revision: 1,
  destructive_operation_count: 2,
  destructive_operation_counts: { update: 1, move_update: 0, trash: 0, delete: 1 },
  irreversible_operation_count: 2,
};
panel.render(task);
assert.equal(
  historicalAcknowledgment.checked,
  true,
  "the historical persistent checkbox reproduces an acknowledgment detached from revision state",
);
findAction(panel.element, "execute").dispatch("click");
assert.deepEqual(calls.at(-1), ["onExecute", review, findAction(panel.element, "execute")]);
assert.equal(findByDataset(panel.element, "action", "destructive-confirmation"), null);

task.executionStarted = true;
task.sessionState = "active";
panel.render(task);
findAction(panel.element, "pause").dispatch("click");
assert.deepEqual(calls.at(-1), ["onControl", review, "pause"]);
task.executionControlState = "pausing";
panel.render(task);
assert.equal(findAction(panel.element, "pause").disabled, true);
assert.equal(findAction(panel.element, "resume").hidden, true);
assert.equal(findAction(panel.element, "cancel").disabled, false);
task.executionControlState = "paused";
panel.render(task);
findAction(panel.element, "resume").dispatch("click");
assert.deepEqual(calls.at(-1), ["onControl", review, "resume"]);
task.executionControlState = "pending";
panel.render(task);
assert.equal(findAction(panel.element, "pause").disabled, true);
assert.equal(findAction(panel.element, "resume").hidden, true);
assert.equal(findAction(panel.element, "cancel").disabled, false);
task.executionControlState = "running";
panel.render(task);
findAction(panel.element, "cancel").dispatch("click");
assert.deepEqual(calls.at(-1), ["onControl", review, "cancel"]);

const viewport = findByClass(panel.element, "nami-plan-review__rows");
viewport.clientHeight = ROW_HEIGHT - 1;
viewport.scrollTop = ROW_HEIGHT * 10;
const coveredWindowCallCount = calls.filter(([name]) => name === "onWindow").length;
viewport.dispatch("scroll");
viewport.scrollTop = ROW_HEIGHT * 10 + 1;
viewport.dispatch("scroll");
assert.equal(document.defaultView.frames.length, 1, "rapid scrolls share one frame");
document.defaultView.flushAnimationFrame();
assert.equal(
  calls.filter(([name]) => name === "onWindow").length,
  coveredWindowCallCount,
  "a covered viewport does not refetch",
);

viewport.scrollTop = ROW_HEIGHT * 300;
viewport.dispatch("scroll");
viewport.scrollTop = ROW_HEIGHT * 400;
viewport.dispatch("scroll");
document.defaultView.flushAnimationFrame();
assert.deepEqual(calls.at(-1), ["onWindow", review, 368]);
const windowCallCount = calls.filter(([name]) => name === "onWindow").length;
viewport.dispatch("scroll");
document.defaultView.flushAnimationFrame();
assert.equal(
  calls.filter(([name]) => name === "onWindow").length,
  windowCallCount,
  "the same uncovered range is requested once",
);
viewport.scrollTop = ROW_HEIGHT * 10;
viewport.dispatch("scroll");
document.defaultView.flushAnimationFrame();
assert.deepEqual(calls.at(-1), ["onWindow", review, null]);

review.pending = "selection";
panel.render(task);
assert.equal(panel.element.dataset.pending, "selection");
assert.equal(findAction(panel.element, "pause").disabled, true);

review.pending = null;
panel.render(task);
const beforeDispose = calls.length;
viewport.scrollTop = ROW_HEIGHT * 400;
const nextReview = { ...review, window: { ...review.window, offset: 0 } };
task.review = nextReview;
panel.render(task);
assert.equal(viewport.scrollTop, 0, "switching reviews starts within retained rows");
document.defaultView.flushAnimationFrame();
assert.equal(calls.length, beforeDispose, "task switch does not fetch the old viewport");
viewport.clientHeight = ROW_HEIGHT * 400;
panel.render(task);
document.defaultView.flushAnimationFrame();
panel.render(task);
document.defaultView.flushAnimationFrame();
assert.equal(calls.length, beforeDispose, "tall viewport does not refetch the same bounded window");
search.value = "stale";
search.dispatch("input");
task.review = null;
panel.render(task);
assert.equal(findByClass(panel.element, "nami-plan-review__table-card").hidden, true);
findAction(panel.element, "plan-again").dispatch("click");
assert.equal(calls.length, beforeDispose, "loading review actions cannot reuse stale review identity");
panel.dispose();
await new Promise((resolve) => setTimeout(resolve, 175));
assert.equal(calls.length, beforeDispose, "disposed debounce cannot target a later task");

function walk(root) {
  return [root, ...root.children.flatMap(walk)];
}

function findByClass(root, className) {
  return walk(root).find((item) => item.classList.contains(className)) ?? null;
}

function findByDataset(root, name, value) {
  return walk(root).find((item) => item.dataset[name] === value) ?? null;
}

function findAction(root, action) {
  const found = findByDataset(root, "action", action);
  assert.ok(found, `missing ${action} control`);
  return found;
}

function findText(root, text) {
  return walk(root).some((item) => item.textContent.includes(text));
}

process.stdout.write("ok");
