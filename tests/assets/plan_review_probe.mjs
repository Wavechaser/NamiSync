import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { assertSameNode } from "./fake_dom_assertions.mjs";
import { fakeRecoveryHandle } from "./fake_recovery_handle.mjs";

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
  [Symbol.for("nodejs.util.inspect.custom")]() {
    return `ElementFake<${this.tagName.slice(0, 24)}>`;
  }
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
      observers: [],
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
        constructor(callback) {
          this.callback = callback;
          this.observeCount = 0;
          document.defaultView.observers.push(this);
        }
        observe(element) { this.observed = element; this.observeCount += 1; }
        disconnect() { this.observed = null; }
        trigger() { if (this.observed !== null) this.callback(); }
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
const fileRowUrl = moduleUrl((await readFile(join(dirname(process.argv[2]), "file_row.js"), "utf8"))
  .replace("./render.js", renderUrl));
const planUrl = moduleUrl((await readFile(join(dirname(process.argv[2]), "plan.js"), "utf8"))
  .replace("./file_row.js", fileRowUrl).replace("./render.js", renderUrl));
const source = (await readFile(process.argv[2], "utf8"))
  .replace("./plan.js", planUrl)
  .replace("./icons.js", iconsUrl)
  .replace("./task_status.js", taskStatusUrl)
  .replace("./render.js", renderUrl);
const { createPlanReviewPanel } = await import(moduleUrl(source));

const calls = [];
const callbacks = Object.fromEntries([
  "onViewChange", "onWindow", "onSelect", "onScopeSelect", "onExecute", "onControl", "onPlanAgain",
  "onHighlight", "onHighlightedSelect", "onExecutionDetail", "onFollowOverride", "onNavigateCurrent", "onRevealMove",
].map((name) => [name, (...args) => calls.push([name, ...args])]));
const panel = createPlanReviewPanel(callbacks);
const planAgainButton = findAction(panel.element, "plan-again");
const planAgainIcon = planAgainButton.children[0];
assert.ok(planAgainIcon?.classList.contains("nami-icon--arrow-reset"));
for (const action of ["execute", "plan-again", "pause", "resume", "cancel"]) {
  assert.equal(findAction(panel.element, action).disabled, true,
    `fresh panel must not advertise ${action} before a review loads`);
}
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
  move_group: null,
  notice: null,
  selection_exclusion_reason: null,
  execution: null,
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
  window: {
    disposition: "current", view_revision: 0, highlight_revision: 0,
    offset: 10, total: 1000,
    execution: {
      execution_revision: 0, session_id: null, result: null,
      failed_operation_count: null, disk_capacity_failure_count: null,
      gap: null, trash_location: null,
    },
    rows: [row],
  },
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
const planGap = { session_id: "7".repeat(32), session_state: "completed",
  gap_first_missed_seq: 4 };
panel.render({ ...task, sessionId: planGap.session_id, snapshot: planGap });
assert.equal(findByClass(panel.element, "nami-plan-review__execution-alert").hidden, true,
  "a Plan-session Gap cannot be labeled as execution history loss");
assert.equal(findByClass(panel.element, "nami-plan-review__execution").hidden, true);
panel.render({ ...task, review: null, reviewLoading: true });
for (const action of ["execute", "plan-again", "pause", "resume", "cancel"]) {
  const control = findAction(panel.element, action);
  assert.equal(control.disabled, true, `loading review must disable ${action}`);
  const beforeClick = calls.length;
  control.dispatch("click");
  assert.equal(calls.length, beforeClick, `null review must not dispatch ${action}`);
}
assert.equal(findByClass(panel.element, "nami-plan-review__control-group").hidden, true);
panel.render({ ...task, review: null, reviewLoading: false, error: "Plan unavailable" });
assert.equal(executeButton.disabled, true, "failed review cannot leave Execute available");
panel.render(task);
assert.equal(executeButton.disabled, false, "loaded review restores its allowed action");
review.summary = summary;
panel.render(task);
document.defaultView.flushAnimationFrame();
assert.ok(findText(panel.element, hostile));
assert.ok(findText(panel.element, "1 destructive"), "plan diagnostics retain destructive context");
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
assert.ok(statusActions.parentElement === statusCard, "actions live in the status card");
assert.ok(statusMeta.parentElement === statusCard, "facts and feedback live in the status card");
const planDisclosure = findAction(panel.element, "toggle-execution-details");
const planDiagnostics = findByClass(panel.element, "nami-plan-review__diagnostics");
const planItemPane = findByClass(panel.element, "nami-plan-review__detail");
const cardProgress = findByClass(panel.element, "nami-plan-review__progress");
assert.ok(planDisclosure.parentElement === statusMeta, "disclosure shares the detailed status line");
assert.ok(statusCard.children.indexOf(planDiagnostics) < statusCard.children.indexOf(cardProgress),
  "expanded facts precede progress in the same card");
planDisclosure.dispatch("click");
assert.equal(planDiagnostics.hidden, false, "Plan exposes the shared Details area");
assert.ok(findText(planItemPane, "Highlight an item"), "unfocused Plan has an item placeholder");
review.summary = { ...summary, highlight_focus_node_id: row.node_id, highlight_revision: 1 };
panel.render(task);
assert.ok(findText(planItemPane, "Planned action"), "focused Plan row reveals planned facts");
assert.ok(findText(planItemPane, hostile.replace("\u202e", "⟦U+202E⟧")));
planDisclosure.dispatch("click");
assert.equal(planDiagnostics.hidden, true);
review.summary = summary;
panel.render(task);
assert.equal(planDiagnostics.hidden, true, "highlight updates do not reopen a collapsed card");
assertSameNode(findAction(panel.element, "plan-again"), planAgainButton);
assertSameNode(planAgainButton.children[0], planAgainIcon, "normal Plan again keeps its icon");
assert.equal(planAgainButton.children.length, 1);
assert.equal(planAgainButton.textContent, "");
assert.equal(planAgainButton.ariaLabel, "Plan again");
assert.equal(planAgainButton.title, "Plan again");
review.pending = "plan-again";
task.form = { attempt: { recovery: fakeRecoveryHandle({ canCheck: true }) } };
panel.render(task);
assertSameNode(planAgainButton.children[0], planAgainIcon, "Check outcome keeps the same icon");
assert.equal(planAgainButton.children.length, 1);
assert.equal(planAgainButton.textContent, "");
assert.equal(planAgainButton.ariaLabel, "Check outcome");
assert.equal(planAgainButton.title, "Check outcome");
review.pending = null;
task.form = null;
panel.render(task);
assertSameNode(planAgainButton.children[0], planAgainIcon, "settled Plan again keeps the same icon");
assert.equal(planAgainButton.children.length, 1);
assert.equal(planAgainButton.textContent, "");
assert.equal(planAgainButton.ariaLabel, "Plan again");
assert.equal(planAgainButton.title, "Plan again");
const executionRecovery = { state: "fixed-unknown", canCheck: false, checking: false,
  message: "execution-owner-sentinel", check: () => Promise.resolve(null) };
const recoveryPanel = createPlanReviewPanel(callbacks);
const recoveryFooter = findByClass(recoveryPanel.element, "nami-plan-review__status");
task.executionAttempt = { state: "uncertain", recovery: executionRecovery };
review.pending = "outcome";
review.message = "review-owner-sentinel";
recoveryPanel.render(task);
assert.ok(findText(recoveryFooter, "execution-owner-sentinel"),
  "uncertain Execute shows its own recovery guidance");
assert.equal(findText(recoveryFooter, "review-owner-sentinel"), false);
assert.equal(findAction(recoveryPanel.element, "execute").disabled, true);
const reconstructedReview = { ...review, window: { ...review.window } };
task.review = reconstructedReview;
recoveryPanel.render(task);
assert.ok(findText(recoveryFooter, "execution-owner-sentinel"),
  "review reconstruction retains the execution owner guidance");
assert.equal(findAction(recoveryPanel.element, "execute").disabled, true);
recoveryPanel.dispose();
task.review = review;
task.executionAttempt = null;
review.pending = null;
review.message = null;
panel.render(task);
assert.equal(footerMessage.hidden, true, "idle footer text takes no room");
review.message = "Updating this view…";
panel.render(task);
assert.equal(footerMessage.hidden, false, "in-flight feedback remains visible");
panel.render(task);
assert.ok(findByDataset(panel.element, "nodeId", row.node_id) === renderedRow,
  "unchanged review rendering preserves row controls and focus");
review.pending = "view";
panel.render(task);
assert.ok(findByDataset(panel.element, "nodeId", row.node_id) === renderedRow,
  "pending control disable does not rebuild the row window");
assert.equal(findByClass(renderedRow, "nami-checkbox").disabled, true);
assert.ok(findByClass(panel.element, "nami-plan-review__plan") === planCard,
  "pending rendering preserves the Plan card identity");
assert.ok(findByClass(panel.element, "nami-plan-review__summary") === statusCard,
  "pending rendering preserves the status card identity");
review.pending = null;
panel.render(task);
assert.ok(findByDataset(panel.element, "nodeId", row.node_id) === renderedRow,
  "settled rendering preserves the row identity");
assert.equal(findByClass(renderedRow, "nami-checkbox").disabled, false);
document.defaultView.flushAnimationFrame();
assert.equal(renderedRow.dataset.folder, "false", "operation groups remain non-folder rows");
assert.ok(findText(renderedRow, hostile.replace("\u202e", "⟦U+202E⟧")));
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
assertSameNode(
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
  assert.ok(document.activeElement === arrow, "Escape returns focus to the filter arrow");
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
assert.ok(document.activeElement === search, "clearing search returns focus to its input");
assert.equal(clearSearch.hidden, true);
assert.deepEqual(calls.at(-1), ["onViewChange", review, { searchQuery: "" }]);

assert.ok(
  findByDataset(panel.element, "action", "destructive-confirmation") === null,
  "the stale persistent acknowledgment control is absent",
);
const firstExecuteButton = findAction(panel.element, "execute");
firstExecuteButton.dispatch("click");
assert.ok(calls.at(-1)[0] === "onExecute" && calls.at(-1)[1] === review
  && calls.at(-1)[2] === firstExecuteButton, "Execute preserves review and invoker identity");

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
const secondExecuteButton = findAction(panel.element, "execute");
secondExecuteButton.dispatch("click");
assert.ok(calls.at(-1)[0] === "onExecute" && calls.at(-1)[1] === review
  && calls.at(-1)[2] === secondExecuteButton,
"later Execute preserves review and invoker identity");
assert.ok(findByDataset(panel.element, "action", "destructive-confirmation") === null, "the destructive acknowledgment control remains absent");

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
task.drainUnavailable = true;
panel.render(task);
for (const action of ["pause", "resume", "cancel"]) {
  assert.equal(findAction(panel.element, action).disabled, true,
    "a stopped task drain offers no execution controls");
}
task.drainUnavailable = false;

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

review.follow = { anchorIndex: 10, hasTarget: true, eligible: true, enabled: true };
panel.render(task);
const overrideCount = calls.filter(([name]) => name === "onFollowOverride").length;
viewport.dispatch("wheel");
viewport.scrollTop = ROW_HEIGHT * 10 + 1;
viewport.dispatch("scroll");
document.defaultView.flushAnimationFrame();
assert.equal(
  calls.filter(([name]) => name === "onFollowOverride").length,
  overrideCount,
  "a small manual scroll retains follow while the current operation stays visible",
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

task.sessionId = "a".repeat(32);
task.executionControlAttempt = { sessionId: task.sessionId,
  recovery: fakeRecoveryHandle({ canCheck: true }) };
review.pending = "pause";
panel.render(task);
const controlCheck = findAction(panel.element, "retry-outcome");
assert.equal(controlCheck.hidden, false);
assert.equal(controlCheck.disabled, false, "ordinary control Check is available while idle");
task.executionControlAttempt.recovery.checking = true;
panel.render(task);
assert.equal(controlCheck.disabled, true, "ordinary control Check is disabled while running");
task.executionControlAttempt.recovery.checking = false;
panel.render(task);
assert.equal(controlCheck.disabled, false, "ordinary control Check returns after observation");
task.executionControlAttempt = null;
task.sessionId = null;
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
  "onPlanAgain", "onHighlight", "onHighlightedSelect", "onExecutionDetail", "onFollowOverride", "onNavigateCurrent", "onRevealMove",
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

const moveCalls = [];
const movePanel = createPlanReviewPanel(Object.fromEntries([
  "onViewChange", "onWindow", "onSelect", "onScopeSelect", "onExecute", "onControl",
  "onPlanAgain", "onHighlight", "onHighlightedSelect", "onExecutionDetail", "onFollowOverride", "onNavigateCurrent", "onRevealMove",
].map((name) => [name, (...args) => moveCalls.push([name, ...args])])));
const moveRow = { ...row, row_kind: "prior-group", operation_kind: null,
  selection: "disabled", selectable_operation_count: 0, selected_operation_count: 0,
  operation_count: 0, display: "2 items moved to destination\\nested",
  move_peer_id: `node-${"9".repeat(32)}`,
  move_group: { count: 2, destination: "destination\\nested" } };
const moveReview = { ...review, window: { ...review.window, rows: [moveRow] } };
movePanel.render({ ...task, review: moveReview });
const moveElement = findByDataset(movePanel.element, "nodeId", moveRow.node_id);
const movePill = findByClass(moveElement, "nami-plan-move-pill");
assert.ok(movePill);
assert.equal(movePill.ariaLabel, moveRow.display);
assert.equal(movePill.title, moveRow.display);
assert.equal(findByClass(moveElement, "nami-badge").textContent, "2 items moved to");
assert.equal(findByClass(moveElement, "nami-plan-move-pill__destination").textContent, "destination\\nested");
assert.equal(findByClass(moveElement, "nami-checkbox"), null);
movePill.dispatch("click");
moveElement.dispatch("click", { target: movePill });
assert.deepEqual(moveCalls.map(([name]) => name), ["onRevealMove"]);
assert.equal(moveCalls[0][2], moveRow.node_id);
findByClass(moveElement, "nami-file-row__disclosure").dispatch("click");
assert.equal(moveCalls.at(-1)[0], "onViewChange");
assert.equal(moveCalls.at(-1)[2].collapseNodeId, moveRow.node_id);
moveReview.pending = "view";
movePanel.render({ ...task, review: moveReview });
assert.equal(movePill.disabled, true);
movePanel.dispose();

const detailCalls = [];
const executionPanel = createPlanReviewPanel(Object.fromEntries([
  "onViewChange", "onWindow", "onSelect", "onScopeSelect", "onExecute", "onControl",
  "onPlanAgain", "onHighlight", "onHighlightedSelect", "onExecutionDetail", "onFollowOverride", "onNavigateCurrent", "onRevealMove",
].map((name) => [name, (...args) => {
  if (name === "onExecutionDetail") detailCalls.push(args);
}])));
const operationId = "5".repeat(32);
const terminalResult = {
  headline: "partial", filesystem: "failed", integrity: "mismatch",
  recording: "degraded", audit: "degraded", disposition: "ran", canceled: false,
  phases: [{ phase: "execute", status: "failed", error: hostile }],
  bytes_done: "0", bytes_total: "0", error: "mixed I/O failure",
  recording_degraded_items: 1,
  recording_issues: [{ reason: "final-flush-failed", detail: hostile }],
  omitted_detail_count: 2, presentation_omitted_detail_count: 3, review_refusal: null,
};
const executionSummary = {
  execution_revision: 9, session_id: "6".repeat(32), result: terminalResult,
  failed_operation_count: 2, disk_capacity_failure_count: 1,
  gap: { minimum_first_missed_seq: 4, maximum_first_missed_seq: 8 },
  trash_location: `D:\\${hostile}`,
};
const executionRow = {
  ...row, node_id: `node-${"7".repeat(32)}`, display: "zero-byte.bin",
  is_container: true, row_kind: "operation-group", operation_id: operationId,
  operation_kind: "copy", selection: "selected", selectable_operation_count: 1,
  selected_operation_count: 1, operation_count: 1, size: "0",
  execution: {
    operation: { result: "succeeded", reason: null, recording: "degraded",
      recording_reason: "record-write-failed", detail_omitted_count: 2 },
    automatic_verification: { result: "mismatched", reason: "hash-mismatch",
      recording: "ok", record_disposition: "noop", detail_omitted_count: 3 },
    evidence: { state: "superseded", content: null },
  },
};
const executionReviewState = {
  ...review, summary: { ...summary, selection_state: "committed",
    highlight_focus_node_id: executionRow.node_id, highlight_revision: 1 },
  window: { ...review.window, execution: executionSummary, rows: [executionRow], total: 1 },
  executionDetail: null,
};
const executionTask = { ...task, review: executionReviewState, executionStarted: true,
  sessionState: "failed" };
const liveTerminalReview = { ...executionReviewState, window: {
  ...executionReviewState.window, execution: { ...executionSummary, result: null,
    started_at: null, ended_at: null },
} };
const terminalPageSnapshot = (result, patch = {}) => ({
  wire_version: 2, session_id: executionSummary.session_id, session_state: "failed",
  terminal_result: result, started_at: "2026-09-23T01:00:00+00:00",
  ended_at: "2026-09-23T01:01:05+00:00",
  progress_inconsistent: false, phase: null, gap_first_missed_seq: null,
  presentation: { value: 0, determinate: false, indeterminate: false,
    items_done: null, items_total: null, throughput_bytes_per_second: null,
    eta_seconds: null },
  ...patch,
});
executionPanel.render({ ...executionTask, review: liveTerminalReview,
  sessionId: executionSummary.session_id,
  snapshot: terminalPageSnapshot(terminalResult, { progress_inconsistent: true }) });
assert.equal(findByClass(executionPanel.element, "nami-plan-review__status-summary").textContent,
  `Execution needs review · Completed ${new Date("2026-09-23T01:01:05+00:00").toLocaleString()} · 1m 5s elapsed · Some progress updates were inconsistent.`,
  "terminal snapshot updates the card before retained-window capture");
assert.ok(findText(executionPanel.element, "Some progress updates were inconsistent."));
executionPanel.render({ ...executionTask, review: liveTerminalReview,
  sessionId: executionSummary.session_id, snapshot: null });
assert.equal(findByClass(executionPanel.element, "nami-plan-review__status-summary").textContent,
  "Execution failed",
  "terminal state remains visible when no result was retained");
assert.ok(findText(executionPanel.element, "No retained execution result is available."));
executionPanel.render({ ...executionTask, review: null, error: null });
const initialDiagnostics = findByClass(executionPanel.element, "nami-plan-review__diagnostics");
assert.equal(initialDiagnostics.hidden, true, "an initial null review has no diagnostics row");
assert.equal(findByClass(executionPanel.element, "nami-plan-review__execution-issues").hidden, true);
assert.equal(findByClass(executionPanel.element, "nami-plan-review__execution-trash").hidden, true);
executionPanel.render(executionTask);
const executionContent = findByClass(executionPanel.element, "nami-plan-review__content");
const executionDiagnostics = findByClass(executionPanel.element, "nami-plan-review__diagnostics");
const executionIssues = findByClass(executionPanel.element, "nami-plan-review__execution-issues");
const executionTrash = findByClass(executionPanel.element, "nami-plan-review__execution-trash");
const globalDiagnostics = findByClass(executionPanel.element, "nami-plan-review__global-diagnostics");
const executionDetailCard = findByClass(executionPanel.element, "nami-plan-review__detail");
const executionStatusCard = findByClass(executionPanel.element, "nami-plan-review__summary");
const detailsToggle = findAction(executionPanel.element, "toggle-execution-details");
const executionAlert = findByClass(executionPanel.element, "nami-plan-review__execution-alert");
assert.ok(executionContent, "table and diagnostics share one bounded content region");
assert.ok(executionDiagnostics, "variable diagnostics share one explicit grid row");
assert.ok(findByClass(executionPanel.element, "nami-plan-review__table-card").parentElement === executionContent,
  "the table remains in the bounded content region");
assert.ok(executionDiagnostics.parentElement === executionStatusCard,
  "the inline Details pane expands the existing status card");
assert.ok(globalDiagnostics.parentElement === executionDiagnostics,
  "global execution facts occupy one Details column");
assert.ok(executionIssues.parentElement === globalDiagnostics,
  "global issues remain in the global Details column");
assert.ok(executionTrash.parentElement === globalDiagnostics,
  "trash location remains in the global Details column");
assert.ok(executionDetailCard.parentElement === executionDiagnostics,
  "operation detail remains in the Details pane");
assert.equal(detailsToggle.ariaExpanded, "false");
assert.equal(executionDiagnostics.hidden, true, "Details is folded by default");
assert.equal(executionAlert.hidden, false, "a compact gap warning remains visible while Details is folded");
assert.ok(executionAlert.parentElement === executionStatusCard,
  "the compact gap warning belongs to the folded status card");
detailsToggle.dispatch("click");
assert.equal(detailsToggle.ariaExpanded, "true");
assert.equal(executionDiagnostics.hidden, false);
assert.equal(executionDetailCard.hidden, false, "expanded Details always includes an item pane");
assert.equal(executionIssues.tabIndex, 0, "terminal diagnostics remain keyboard-scrollable");
assert.equal(executionIssues.ariaLabel, "Execution issues");
assert.equal(executionTrash.tabIndex, 0, "the literal trash location remains keyboard-scrollable");
assert.equal(executionTrash.ariaLabel, "Trash location");
assert.equal(executionDetailCard.tabIndex, 0, "operation detail remains keyboard-scrollable");
assert.equal(executionDetailCard.ariaLabel, "Item details");
assert.ok(findText(executionPanel.element, "Execution needs review"));
assert.ok(findText(executionPanel.element, "Filesystem: Failed"));
assert.ok(findText(executionPanel.element, "Automatic verification: Mismatch"));
assert.ok(findText(executionPanel.element, "producer details omitted"));
assert.ok(findText(executionPanel.element, "presentation details omitted"));
assert.ok(findText(executionPanel.element, "Gaps observed from event 4 through 8"));
assert.ok(findText(executionPanel.element, "Trash location:"));
assert.ok(findText(executionPanel.element, "Operation: Completed"));
assert.ok(findText(executionPanel.element, "Automatic verification: Mismatch"));
assert.ok(findText(executionPanel.element, "Stored evidence: Superseded"));
assertSameNode(findByClass(executionPanel.element, "nami-plan-review__detail-button"), null,
  "rows use authoritative highlight instead of a separate detail button");
assert.ok(findText(executionDetailCard, "Planned action"));
assert.ok(findText(executionDetailCard, "zero-byte.bin"));
assert.equal(detailCalls.length, 0, "rendering a focused row does not bypass the highlight controller");
executionReviewState.executionDetail = {
  operationId, executionRevision: 9,
  state: "current",
  response: {
    disposition: "current", execution_revision: 9, operation_id: operationId,
    operation: {
      item_type: "operation", phase: "execute", item_id: operationId, kind: "copy",
      path: `C:\\${hostile}`, result: "succeeded", reason: null,
      detail: { message: hostile, continued: false }, recording: "degraded",
      recording_reason: "record-write-failed", recording_detail: hostile,
      detail_omitted_count: 1,
    },
    automatic_verification: {
      item_type: "integrity", phase: "verify", item_id: operationId,
      row_id: null, location_id: null, kind: "integrity", path: `D:\\${hostile}`,
      result: "mismatched", reason: "hash-mismatch", detail: hostile,
      read_strategy: "windows-unbuffered", recording: "ok",
      record_disposition: "noop", detail_omitted_count: 1,
    },
    evidence: { state: "unrecorded", content: null },
  },
};
executionPanel.render(executionTask);
const detailBody = findByClass(executionPanel.element, "nami-plan-review__detail-body");
assert.ok(findText(detailBody, hostile), "hostile detail remains literal text");
assert.equal(walk(detailBody).some((item) => item.tagName === "IMG"), false);
detailsToggle.dispatch("click");
assert.equal(executionDiagnostics.hidden, true, "user collapse folds retained detail");
executionPanel.render(executionTask);
assert.equal(executionDiagnostics.hidden, true, "routine render preserves collapse");
executionReviewState.window = { ...executionReviewState.window };
executionPanel.render(executionTask);
assert.equal(executionDiagnostics.hidden, true, "window adoption preserves collapse");
assert.ok(findText(detailBody, hostile), "collapsed detail still refreshes its content");
detailsToggle.dispatch("click");
assert.equal(executionDiagnostics.hidden, false);
const retainedResponse = executionReviewState.executionDetail.response;
executionReviewState.executionDetail = null;
executionPanel.render(executionTask);
assert.equal(executionDetailCard.hidden, false, "item pane remains with planned facts after detail retirement");
assert.ok(findText(executionDetailCard, "Planned action"));

executionReviewState.executionDetail = {
  operationId, executionRevision: 9, state: "loading", response: null, message: null,
};
executionPanel.render(executionTask);
assert.equal(executionDiagnostics.hidden, false, "new row Details request opens the pane");
assert.ok(findText(executionDetailCard, "Loading operation detail"));
executionReviewState.executionDetail.state = "current";
executionReviewState.executionDetail.response = retainedResponse;
executionPanel.render(executionTask);
assert.ok(findText(detailBody, hostile), "loading-to-result refreshes the same detail");
detailsToggle.focus();
detailsToggle.dispatch("click");
assert.equal(executionDiagnostics.hidden, true);
executionReviewState.executionDetail = { ...executionReviewState.executionDetail,
  response: { ...retainedResponse, operation: { ...retainedResponse.operation, result: "failed" } } };
executionPanel.render(executionTask);
assert.equal(executionDiagnostics.hidden, true, "a changed focused detail never reopens deliberate collapse");
detailsToggle.dispatch("click");

const quietResult = {
  ...terminalResult,
  headline: "success", filesystem: "completed", integrity: "verified",
  recording: "ok", audit: "ok",
  phases: [{ phase: "execute", status: "completed", error: null }],
  error: null, recording_degraded_items: 0, recording_issues: [],
  omitted_detail_count: 0, presentation_omitted_detail_count: 0,
};
for (const issuesVisible of [false, true]) {
  for (const trashVisible of [false, true]) {
      const visibilityReview = {
        ...executionReviewState,
        window: {
          ...executionReviewState.window,
          execution: {
            ...executionSummary,
            result: { ...quietResult, error: issuesVisible ? hostile : null },
            failed_operation_count: 0,
            disk_capacity_failure_count: 0,
            gap: null,
            trash_location: trashVisible ? `D:\\${hostile}` : null,
          },
        },
        executionDetail: null,
      };
      executionPanel.render({
        ...executionTask, review: visibilityReview,
      });
      assert.equal(executionIssues.hidden, !issuesVisible);
      assert.equal(executionTrash.hidden, !trashVisible);
      assert.equal(executionDetailCard.hidden, false, "item pane is present with or without execution facts");
      assert.equal(globalDiagnostics.hidden, false, "secondary execution facts keep the global column available");
      if (executionDiagnostics.hidden) detailsToggle.dispatch("click");
      assert.equal(executionDiagnostics.hidden, false);
      assert.ok(findText(executionDetailCard, "Planned action"));
  }
}

function assertNullReviewDiagnostics(error) {
  executionPanel.render({
    ...executionTask,
    review: null,
    error,
    sessionState: error === null ? "planning" : "failed",
  });
  assert.equal(executionDiagnostics.hidden, true);
  assert.equal(executionDiagnostics.dataset.status, "none");
  assert.equal(executionIssues.hidden, true);
  assert.equal(executionIssues.textContent, "");
  assert.equal(executionTrash.hidden, true);
  assert.equal(executionTrash.textContent, "");
  assert.equal(executionDetailCard.parentElement.hidden, true);
}

executionPanel.render(executionTask);
if (executionDiagnostics.hidden) detailsToggle.dispatch("click");
assert.equal(executionDiagnostics.hidden, false);
assert.ok(executionIssues.textContent.includes(hostile));
assert.ok(findText(executionTrash, "Trash location:"));
assertNullReviewDiagnostics(null);
executionPanel.render(executionTask);
if (executionDiagnostics.hidden) detailsToggle.dispatch("click");
assert.equal(executionDiagnostics.hidden, false);
assert.ok(executionIssues.textContent.includes(hostile));
assert.ok(findText(executionTrash, "Trash location:"));
assertNullReviewDiagnostics("Different task plan unavailable.");
executionPanel.render(executionTask);
if (executionDiagnostics.hidden) detailsToggle.dispatch("click");
assert.equal(executionDiagnostics.hidden, false);
assert.ok(executionIssues.textContent.includes(hostile));
assert.ok(findText(executionTrash, "Trash location:"));

const capacityResult = {
  ...terminalResult,
  headline: "failed", filesystem: "failed", integrity: "verified",
  recording: "ok", audit: "ok",
  phases: [{ phase: "execute", status: "failed", error: "disk capacity" }],
  error: null, recording_degraded_items: 0, recording_issues: [],
  omitted_detail_count: 0, presentation_omitted_detail_count: 0,
};
const capacityRow = {
  ...executionRow,
  display: "capacity.bin",
  execution: {
    operation: {
      result: "failed", reason: "disk-capacity", recording: "ok",
      recording_reason: null, detail_omitted_count: 0,
    },
    automatic_verification: {
      result: "verified", reason: null, recording: "ok",
      record_disposition: "noop", detail_omitted_count: 0,
    },
    evidence: {
      state: "recorded-copy",
      content: { digest: "abcdef0123456789abcdef0123456789" },
    },
  },
};
const capacityReview = {
  ...executionReviewState,
  window: {
    ...executionReviewState.window,
    rows: [capacityRow],
    execution: {
      ...executionSummary,
      result: capacityResult,
      failed_operation_count: 1,
      disk_capacity_failure_count: 1,
    },
  },
  executionDetail: null,
};
executionPanel.render({
  ...executionTask, review: capacityReview, sessionId: executionSummary.session_id,
  snapshot: terminalPageSnapshot(capacityResult),
});
assert.ok(findText(executionPanel.element, "Execution stopped: more target space is needed"));
executionPanel.render({
  ...executionTask, review: capacityReview, sessionId: "9".repeat(32),
  snapshot: terminalPageSnapshot(terminalResult, {
    session_id: "9".repeat(32),
  }),
});
assert.equal(findByClass(executionPanel.element, "nami-plan-review__status-title").textContent,
  "Execution needs review",
  "a different session's capacity counts cannot replace snapshot result");
assert.equal(findByClass(executionPanel.element, "nami-plan-review__execution-trash").hidden, true,
  "a different session's trash location is not current guidance");
executionPanel.render({
  ...executionTask, review: capacityReview, sessionId: executionSummary.session_id,
  sessionState: "active",
  snapshot: terminalPageSnapshot(null, { session_state: "active", started_at: null,
    ended_at: null }),
});
assert.equal(findByClass(executionPanel.element, "nami-plan-review__status-title").textContent,
  "Execution in progress",
  "active snapshot does not inherit the retained terminal window result");
executionPanel.render({
  ...executionTask, review: capacityReview, sessionId: executionSummary.session_id,
  snapshot: terminalPageSnapshot(capacityResult),
});
const capacityIntent = walk(executionPanel.element).find(
  (item) => item.dataset?.lifecycle === "capacity",
);
assert.ok(capacityIntent, "the exact disk-capacity failure has its closed lifecycle key");
assert.ok(findText(capacityIntent, "Failed"), "capacity row retains the literal failed result");
assert.ok(findText(executionPanel.element, "Operation: Failed (Disk capacity)"));
assert.ok(findText(executionPanel.element, "Automatic verification: Verified"));
assert.ok(findText(executionPanel.element, "Stored evidence: Recorded copy"),
  "capacity presentation preserves every independent row axis");
assert.ok(findText(executionPanel.element, "abcdef01"), "only stored evidence supplies the checksum");

const quietDetailReview = {
  ...capacityReview,
  window: {
    ...capacityReview.window,
    execution: { ...executionSummary, session_id: null, result: null, gap: null, trash_location: null },
  },
  executionDetail: { operationId, state: "loading", response: null, message: null },
};
const quietDetailTask = { ...executionTask, review: quietDetailReview };
executionPanel.render(quietDetailTask);
if (executionDiagnostics.hidden) detailsToggle.dispatch("click");
executionDetailCard.focus();
detailsToggle.dispatch("click");
assert.ok(document.activeElement === detailsToggle,
  "whole-pane collapse returns hidden-content focus to its disclosure");
detailsToggle.dispatch("click");
executionDetailCard.focus();
executionPanel.render({ ...quietDetailTask, review: null });
assert.ok(document.activeElement === findByClass(executionPanel.element, "nami-plan-review__status-title"),
  "null review returns hidden-detail focus to visible status");
executionPanel.dispose();

const livePanel = createPlanReviewPanel(callbacks);
const liveRow = {
  ...executionRow, execution: null, is_container: false, row_kind: "operation",
};
const liveReview = {
  ...executionReviewState,
  window: {
    ...executionReviewState.window,
    rows: [liveRow], total: 1,
    execution: { ...executionSummary, result: null, gap: null, trash_location: null },
  },
  executionDetail: null,
};
const liveTask = {
  ...executionTask, review: liveReview, sessionState: "active",
  sessionId: "8".repeat(32),
  executionControlState: "running",
  progressPresentation: {
    phase: "execute", activeItem: { item_id: operationId, item_type: "operation" },
    itemPercent: 10,
  },
};
livePanel.render(liveTask);
const liveElement = findByDataset(livePanel.element, "nodeId", liveRow.node_id);
let liveIntent = findByClass(liveElement, "nami-plan-row__intent");
assert.equal(liveIntent.dataset.lifecycle, "executing",
  "unsettled operation composes through the real row validator");
assert.equal(findByClass(liveIntent, "nami-progress").ariaValueNow, "10");
liveElement.focus();
liveTask.progressPresentation = { ...liveTask.progressPresentation, itemPercent: 80 };
livePanel.render(liveTask);
liveIntent = findByClass(liveElement, "nami-plan-row__intent");
assert.equal(findByClass(liveIntent, "nami-progress").ariaValueNow, "80",
  "same-window progress updates the visible active row");
assert.ok(findByDataset(livePanel.element, "nodeId", liveRow.node_id) === liveElement,
  "progress keeps row identity");
assert.ok(document.activeElement === liveElement, "progress keeps row focus");
liveRow.execution = {
  operation: executionRow.execution.operation,
  automatic_verification: null, evidence: null,
};
liveTask.progressPresentation = {
  phase: "verify", activeItem: { item_id: operationId, item_type: "operation" },
  itemPercent: 40,
};
livePanel.render(liveTask);
liveIntent = findByClass(liveElement, "nami-plan-row__intent");
assert.equal(liveIntent.dataset.lifecycle, "completed", "copy outcome survives verification");
assert.ok(findText(liveIntent, "Completed"));
assert.equal(findByClass(liveIntent, "nami-plan-row__verification")
  .querySelector(".nami-progress").ariaValueNow, "40");
liveTask.progressPresentation = { phase: "verify", activeItem: null, itemPercent: null };
livePanel.render(liveTask);
liveIntent = findByClass(liveElement, "nami-plan-row__intent");
assert.equal(liveIntent.dataset.lifecycle, "completed", "retirement keeps copy outcome");
assertSameNode(findByClass(liveIntent, "nami-plan-row__verification"), null);
assert.ok(document.activeElement === liveElement, "retirement keeps row focus");
liveTask.snapshot = {
  session_id: liveTask.sessionId, session_state: "active", phase: "execute", terminal_result: null,
  presentation: {
    value: 0, determinate: false, indeterminate: true,
    items_done: 0, items_total: 1,
    throughput_bytes_per_second: 18014398509481984, eta_seconds: null,
  },
};
livePanel.render(liveTask);
assert.ok(findText(findByClass(livePanel.element, "nami-plan-review__status-summary"),
  "16.00 PiB/s estimate"), "the approximate large rate renders without violating the exact byte formatter");
findAction(livePanel.element, "pause").dispatch("click");
assert.deepEqual(calls.at(-1), ["onControl", liveReview, "pause"],
  "real composed row leaves controls dispatchable");
livePanel.dispose();

const resizeCalls = [];
const resizePanel = createPlanReviewPanel({
  ...callbacks, onWindow: (_review, offset) => resizeCalls.push(offset),
});
const resizeBody = findByClass(resizePanel.element, "nami-plan-review__rows");
const resizeObserver = document.defaultView.observers.at(-1);
const resizeTask = { ...task, review };
resizePanel.render(resizeTask);
document.defaultView.flushAnimationFrame();
resizePanel.dispose();
resizePanel.render(resizeTask);
document.defaultView.flushAnimationFrame();
resizeBody.clientHeight = 700;
resizeObserver.trigger();
document.defaultView.flushAnimationFrame();
assert.deepEqual(resizeCalls, [0], "reused review observes newly visible rows after resize");
assertSameNode(resizeObserver.observed, resizeBody, "reused review observes its current body");
const observedAfterReuse = resizeObserver.observeCount;
resizePanel.render(resizeTask);
assert.equal(resizeObserver.observeCount, observedAfterReuse,
  "re-rendering one active review does not add another observation");
resizeBody.clientHeight = 0;
resizePanel.dispose();
resizePanel.render(resizeTask);
document.defaultView.flushAnimationFrame();
resizeBody.clientHeight = 700;
resizeObserver.trigger();
document.defaultView.flushAnimationFrame();
assert.deepEqual(resizeCalls, [0, 0], "another reuse responds to the next viewport resize");
resizeObserver.trigger();
document.defaultView.flushAnimationFrame();
assert.deepEqual(resizeCalls, [0, 0], "one settled resize does not duplicate the window read");
resizePanel.dispose();
process.stdout.write("ok");
