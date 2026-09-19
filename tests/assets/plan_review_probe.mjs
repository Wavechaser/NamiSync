import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";

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
  get textContent() { return this._textContent ?? ""; }
  set textContent(value) {
    this._textContent = value;
    for (const child of this.children ?? []) child.parentElement = null;
    this.children = [];
  }
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

  insertBefore(value, reference) {
    value.remove();
    const index = this.children.indexOf(reference);
    this.children.splice(index, 0, value);
    value.parentElement = this;
  }

  focus() { this.ownerDocument.activeElement = this; }
  contains(value) { return value === this || this.children.some((child) => child.contains(value)); }

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
    const widths = [32, 300, 130, 112, 100, 112, 300];
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
const taskStatusUrl = moduleUrl((await readFile(join(dirname(process.argv[2]), "task_status.js"), "utf8"))
  .replace("./render.js", renderUrl));
const planUrl = moduleUrl(`
  export function renderPlanRow(element, row) {
    element.className = "nami-file-row nami-plan-row";
    element.dataset.folder = String(row.folder);
    element.textContent = row.nameText;
    const checkbox = document.createElement("input");
    checkbox.className = "nami-checkbox";
    checkbox.checked = row.checked;
    checkbox.disabled = row.selectionDisabled;
    const selection = document.createElement("div");
    selection.dataset.fileColumn = "selection";
    selection.append(checkbox);
    const name = document.createElement("div");
    name.className = "nami-file-row__name";
    name.dataset.fileColumn = "name";
    const disclosure = document.createElement(row.folder ? "button" : "span");
    disclosure.className = row.folder
      ? "nami-file-row__disclosure"
      : "nami-file-row__disclosure-spacer";
    name.append(disclosure);
    const notes = document.createElement("span");
    notes.textContent = row.notesText;
    notes.dataset.fileColumn = "notes";
    const cells = ["size", "primary", "secondary", "modified"].map((column) => {
      const cell = document.createElement("div");
      cell.dataset.fileColumn = column === "modified" ? "secondary" : column;
      cell.className = column === "size" ? "nami-file-row__size" : "nami-plan-row__" + column;
      if (column === "size") cell.textContent = row.sizeText;
      if (column === "primary") cell.textContent = row.intentText;
      return cell;
    });
    element.append(selection, name, ...cells, notes);
  }
`);
const source = (await readFile(process.argv[2], "utf8"))
  .replace("./plan.js", planUrl)
  .replace("./icons.js", iconsUrl)
  .replace("./task_status.js", taskStatusUrl)
  .replace("./render.js", renderUrl);
const { createPlanReviewPanel } = await import(moduleUrl(source));

const calls = [];
const callbacks = Object.fromEntries([
  "onViewChange", "onWindow", "onSelect", "onScopeSelect", "onExecute", "onControl", "onPlanAgain",
  "onHighlight", "onHighlightedSelect",
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
  dependency_count: 2,
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
  filter_counts: { all: 180, copy: 100, move: 10, update: 5, trash: 2,
    mkdir: 0, recase: 0, move_update: 0, delete: 0, noop: 0, blocked: 0,
    error: 0, unsupported: 0, notice: 1 },
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
  notice: "Partial size: overflow",
  risk: "irreversible",
  blocked_reason: "unsupported",
  selection_exclusion_reason: hostile,
};
review.window.rows.push(notice);

panel.render(task);
assert.equal(panel.element.dataset.pending, "");
const tierStatus = findByClass(panel.element, "nami-plan-review__status-title");
const executeButton = findByClass(panel.element, "nami-button--primary");
assert.equal(tierStatus.textContent, "Plan ready");
assert.equal(executeButton.disabled, true);
review.summary = { ...summary, preflight_ready: true, preflight_refusal_count: 0,
  selected_operation_count: 0 };
panel.render(task);
assert.equal(tierStatus.textContent, "Plan ready");
assert.equal(executeButton.disabled, true);
review.summary = { ...summary, preflight_ready: true, preflight_refusal_count: 0 };
panel.render(task);
assert.equal(tierStatus.textContent, "Plan ready");
assert.equal(executeButton.disabled, false);
review.summary = summary;
panel.render(task);
document.defaultView.flushAnimationFrame();
assert.ok(findText(panel.element, hostile));
assert.equal(findText(panel.element, "1 destructive"), false);
assert.ok(findText(panel.element, "4.00 KiB required"));
assert.ok(findText(panel.element, "planning issues"));
assert.ok(findText(panel.element, "Source:"));
assert.ok(findText(panel.element, "Target:"));
assert.ok(findText(panel.element, "Plan ready"));
assert.ok(findByClass(panel.element, "nami-plan-review__progress"));
assert.ok(findByClass(panel.element, "nami-plan-review__view-switcher"));
assert.equal(findText(panel.element, "Plan review"), false);
assert.equal(findText(panel.element, "Status"), false);
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
const actionResizer = findByDataset(panel.element, "column", "primary");
actionResizer.dispatch("pointerdown", { clientX: 200 });
window.dispatch("pointermove", { clientX: 0 });
assert.equal(grid.style.getPropertyValue("--nami-file-column-primary"), "96.000px",
  "dragging Action respects the same 6rem minimum as its default track");
window.dispatch("pointerup");
const renderedRow = findByDataset(panel.element, "nodeId", row.node_id);
assert.deepEqual(renderedRow.children.map((cell) => cell.dataset.fileColumn),
  ["selection", "name", "primary", "secondary", "size", "secondary", "notes"]);
const planCard = findByClass(panel.element, "nami-plan-review__plan");
const statusCard = findByClass(panel.element, "nami-plan-review__summary");
const footerMessage = findByClass(panel.element, "nami-plan-review__status");
assert.equal(footerMessage.hidden, false, "actionable warnings remain visible");
const statusActions = findByClass(panel.element, "nami-plan-review__actions");
const statusMeta = findByClass(panel.element, "nami-plan-review__status-meta");
assert.equal(statusActions.parentElement, statusCard, "actions live in the status card");
assert.equal(statusMeta.parentElement, statusCard, "facts and feedback live in the status card");
assert.equal(findAction(panel.element, "plan-again").ariaLabel, "Plan again");
assert.equal(findAction(panel.element, "plan-again").title, "Plan again");
review.message = null;
panel.render(task);
assert.equal(footerMessage.hidden, true, "idle footer text takes no room");
review.message = "Updating this view…";
panel.render(task);
assert.equal(footerMessage.hidden, false, "in-flight feedback remains visible");
panel.render(task);
assert.equal(findByDataset(panel.element, "nodeId", row.node_id), renderedRow,
  "unchanged review rendering preserves row controls and focus");
review.pending = "view";
panel.render(task);
assert.equal(findByDataset(panel.element, "nodeId", row.node_id), renderedRow,
  "pending control disable does not rebuild the row window");
assert.equal(findByClass(renderedRow, "nami-checkbox").disabled, true);
assert.equal(findByClass(panel.element, "nami-plan-review__plan"), planCard);
assert.equal(findByClass(panel.element, "nami-plan-review__summary"), statusCard);
review.pending = null;
panel.render(task);
assert.equal(findByDataset(panel.element, "nodeId", row.node_id), renderedRow);
assert.equal(findByClass(renderedRow, "nami-checkbox").disabled, false);
document.defaultView.flushAnimationFrame();
assert.equal(renderedRow.dataset.folder, "false", "operation groups remain non-folder rows");
assert.equal(renderedRow.textContent, hostile);
assert.equal(findText(renderedRow, "Risk: none"), false);
assert.equal(findText(renderedRow, "deps"), false);
const renderedNotice = findByDataset(panel.element, "nodeId", notice.node_id);
assert.equal(renderedNotice.dataset.folder, "false");
assert.ok(findText(renderedNotice, hostile), "notice context renders as inert text");
assert.ok(findText(renderedNotice, "Partial size: overflow"), "overflow note remains visible");
assert.ok(findText(renderedNotice, "Risk: irreversible"));
assert.ok(findText(renderedNotice, "Unsupported item"), "notices do not hide blockers");
assert.equal(findByClass(renderedNotice, "nami-file-row__size").textContent, "",
  "overflow rows do not render a clamped or zero size");
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

renderedRow.dispatch("click", { shiftKey: true });
assert.deepEqual(calls.at(-1), ["onHighlight", review, "extend", row.node_id]);
assert.equal(renderedRow.dataset.namiFocusOrigin, "pointer");
renderedRow.dispatch("focusout");
assert.equal(renderedRow.dataset.namiFocusOrigin, undefined);
renderedRow.dataset.namiFocusOrigin = "pointer";
renderedRow.dispatch("focusin");
assert.equal(renderedRow.dataset.namiFocusOrigin, undefined);
renderedRow.dispatch("click", { ctrlKey: true });
assert.deepEqual(calls.at(-1), ["onHighlight", review, "toggle", row.node_id]);
renderedRow.dispatch("click", { ctrlKey: true, shiftKey: true });
assert.deepEqual(calls.at(-1), ["onHighlight", review, "add-range", row.node_id]);
renderedRow.dispatch("keydown", { key: "ArrowDown", shiftKey: true });
assert.equal(renderedRow.dataset.namiFocusOrigin, undefined);
assert.deepEqual(calls.at(-1), ["onHighlight", review, "move_down_extend", null]);
renderedRow.dispatch("keydown", { key: "Escape" });
assert.deepEqual(calls.at(-1), ["onHighlight", review, "clear", null]);

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
const allFilter = findByDataset(panel.element, "operation", "all");
const copyFilter = findByDataset(panel.element, "operation", "copy");
const mkdirFilter = findByDataset(panel.element, "filterDetail", "mkdir");
const trashFilter = findByDataset(panel.element, "operation", "trash");
assert.equal(allFilter.ariaPressed, "true");
assert.equal(allFilter.ariaLabel, "All 180");
assert.equal(copyFilter.ariaLabel, "Copy 100");
assert.equal(mkdirFilter.ariaLabel, "Create folder 0");
assert.equal(allFilter.children[0].textContent, "All");
assert.equal(allFilter.children[1].textContent, "180");
assert.equal(noticeFilter.hidden, false);
assert.equal(trashFilter.hidden, false);
assert.equal(trashFilter.dataset.trashAlert, "true");
copyFilter.dispatch("click");
assert.deepEqual(calls.at(-1), ["onViewChange", review,
  { filters: new Set(["copy", "mkdir"]) }]);
mkdirFilter.dispatch("click");
assert.deepEqual(calls.at(-1), ["onViewChange", review,
  { filters: new Set(["mkdir"]) }]);
for (const [group, members] of Object.entries({
  update: ["update", "move_update"], move: ["move", "recase"],
  copy: ["copy", "mkdir"], remove: ["trash", "delete"],
  error: ["error", "unsupported", "blocked"],
})) {
  const main = findByDataset(panel.element, "filter", group);
  const split = main.parentElement;
  const arrow = findByClass(split, "nami-plan-filter-split__arrow");
  const menu = findByClass(split, "nami-plan-filter-split__menu");
  const beforeOpen = calls.length;
  arrow.dispatch("click");
  assert.equal(menu.hidden, false);
  assert.equal(calls.length, beforeOpen, "opening a detail menu never filters");
  menu.dispatch("keydown", { key: "End" });
  assert.equal(document.activeElement.dataset.filterDetail, members.at(-1));
  menu.dispatch("keydown", { key: "Escape" });
  assert.equal(menu.hidden, true);
  assert.equal(document.activeElement, arrow);
  review.summary = { ...summary, filters: ["notice", members.at(-1)] };
  panel.render(task);
  main.dispatch("click");
  assert.deepEqual(calls.at(-1)[2].filters, new Set(["notice", ...members]));
  review.summary = { ...summary, filters: ["notice", ...members] };
  panel.render(task);
  main.dispatch("click");
  assert.deepEqual(calls.at(-1)[2].filters, new Set(["notice"]));
  findByDataset(menu, "filterDetail", "all").dispatch("click");
  assert.deepEqual(calls.at(-1)[2].filters, new Set(["notice", ...members]));
}
review.summary = summary;
review.summary = {
  ...review.summary,
  filter_counts: { ...review.summary.filter_counts, trash: 1, notice: 0 },
};
panel.render(task);
assert.equal(trashFilter.dataset.trashAlert, "false");
assert.equal(noticeFilter.hidden, true);
review.summary = summary;
panel.render(task);
noticeFilter.dispatch("click");
assert.deepEqual(calls.at(-1), ["onViewChange", review,
  { filters: new Set(["notice"]) }]);
review.summary = { ...review.summary, filters: ["notice"] };
panel.render(task);
assert.equal(noticeFilter.ariaPressed, "true");
allFilter.dispatch("click");
assert.deepEqual(calls.at(-1), ["onViewChange", review,
  { filters: new Set() }]);
review.summary = { ...review.summary, filters: [] };
panel.render(task);
assert.equal(noticeFilter.ariaPressed, "false");
assert.equal(allFilter.ariaPressed, "true");
assert.equal(
  calls.filter(([name]) => name === "onScopeSelect").length,
  1,
  "filter navigation does not imply scoped selection",
);

const search = findAction(panel.element, "plan-search");
review.pending = "view";
panel.render(task);
assert.equal(search.disabled, false, "a pending view refresh keeps search editable");
review.pending = null;
panel.render(task);
search.value = hostile;
search.dispatch("input");
await new Promise((resolve) => setTimeout(resolve, 175));
assert.deepEqual(calls.at(-1), ["onViewChange", review, { searchQuery: hostile }]);
search.value = "immediate";
search.dispatch("input");
search.dispatch("keydown", { key: "Enter" });
assert.deepEqual(calls.at(-1), ["onViewChange", review, { searchQuery: "immediate" }]);
const immediateCount = calls.length;
findAction(panel.element, "plan-search-submit").dispatch("click");
search.dispatch("keydown", { key: "Enter" });
assert.equal(calls.length, immediateCount, "manual search uses one shared repeat guard");
await new Promise((resolve) => setTimeout(resolve, 175));
assert.equal(calls.length, immediateCount, "manual search cancels the trailing input timer");
const clearSearch = findAction(panel.element, "plan-search-clear");
search.value = "clear this";
search.dispatch("input");
assert.equal(clearSearch.hidden, false);
clearSearch.dispatch("click");
assert.equal(search.value, "");
assert.equal(document.activeElement, search);
assert.equal(clearSearch.hidden, true);
assert.deepEqual(calls.at(-1), ["onViewChange", review, { searchQuery: "" }]);

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
task.review = { ...review, window: { ...review.window, total: 0, rows: [] },
  summary: { ...summary, filter_counts: { ...summary.filter_counts, all: 0 } } };
panel.render(task);
assert.ok(findText(panel.element, "Plan is empty"));
task.review = { ...review, window: { ...review.window, total: 0, rows: [] } };
panel.render(task);
assert.ok(findText(panel.element, "No items match these filters."));
search.value = "stale";
search.dispatch("input");
task.review = null;
panel.render(task);
assert.equal(findByClass(panel.element, "nami-plan-review__table-card").hidden, true);
task.review = review;
panel.render(task);
assert.equal(findByClass(panel.element, "nami-plan-review__settings").children.length, 2,
  "loading must not detach the two semantic-setting rows");
task.review = null;
panel.render(task);
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

const terminologyPanel = createPlanReviewPanel(Object.fromEntries([
  "onViewChange", "onWindow", "onSelect", "onScopeSelect", "onExecute", "onControl",
  "onPlanAgain", "onHighlight", "onHighlightedSelect",
].map((name) => [name, () => {}])));
function terminologyRow(patch) {
  const specimen = { ...row, operation_kind: "noop", reason: null, ...patch };
  terminologyPanel.render({ ...task, review: { ...review,
    window: { ...review.window, rows: [specimen] } } });
  return findByDataset(terminologyPanel.element, "nodeId", specimen.node_id);
}
for (const reason of ["source_only", "metadata_match", "identity_rename", "required_directory", "empty_directory"]) {
  const rendered = terminologyRow({ reason });
  assert.equal(findByDataset(rendered, "fileColumn", "notes").textContent, "", reason);
  assert.ok(findText(rendered, "No change"));
}
for (const [reason, label] of [
  ["metadata_changed", "File metadata changed"], ["target_only", "Only in target"],
  ["directory_cleanup", "Remove unneeded folder"], ["case_collision", "Conflicting name casing"],
  ["future_reason_unclassified", "future_reason_unclassified"],
  ["constructor", "constructor"], ["__proto__", "__proto__"],
]) assert.ok(findText(terminologyRow({ reason }), label), reason);
assert.ok(findText(terminologyRow({ reason: "source_only", blocked_reason: "blocked_dependency" }), "Required operation is blocked"));
assert.ok(findText(terminologyRow({ reason: "source_only", blocked_reason: "blocked_dependency" }), "Only in source"));
assert.ok(findText(terminologyRow({ reason: "metadata_match", risk: "irreversible" }), "Metadata matches"));
assert.ok(findText(terminologyRow({ selection_exclusion_reason: "incomplete-scan" }), "Scan incomplete"));
assert.ok(findText(terminologyRow({ notice: "metadata_match" }), "metadata_match"), "free-form notices are never hidden or rewritten");
assert.ok(findText(terminologyRow({ notice: hostile }), hostile), "unknown notes stay inert and visible");
assert.ok(findText(terminologyRow({ row_kind: "prior-operation", move_peer_id: row.node_id }), "Previous location"));
for (const [operation_kind, label] of [["mkdir", "Create folder"], ["recase", "Change name casing"],
  ["trash", "Move to trash"], ["delete", "Delete permanently"], ["move_update", "Move + update"]]) {
  assert.ok(findText(terminologyRow({ operation_kind }), label));
}
terminologyPanel.dispose();
process.stdout.write("ok");
