import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

class ClassList {
  constructor() { this.values = new Set(); }
  add(...values) { values.forEach((value) => this.values.add(value)); }
}

class ElementFake {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.classList = new ClassList();
    this.listeners = new Map();
    this.dataset = {};
    this.value = "";
    this.textContent = "";
    this.disabled = false;
    this.hidden = false;
    this.attributes = new Map();
  }

  append(...values) {
    for (const value of values) {
      value.parentNode = this;
      this.children.push(value);
    }
  }

  replaceChildren(...values) {
    this.children = [];
    this.append(...values);
  }

  insertBefore(value, reference) {
    value.parentNode = this;
    const previous = this.children.indexOf(value);
    if (previous >= 0) this.children.splice(previous, 1);
    const index = reference === null ? this.children.length : this.children.indexOf(reference);
    this.children.splice(index < 0 ? this.children.length : index, 0, value);
  }

  remove() {
    const index = this.parentNode?.children.indexOf(this) ?? -1;
    if (index >= 0) this.parentNode.children.splice(index, 1);
  }

  addEventListener(name, listener) {
    const values = this.listeners.get(name) ?? [];
    values.push(listener);
    this.listeners.set(name, values);
  }

  dispatch(name, event = {}) {
    for (const listener of this.listeners.get(name) ?? []) listener({ preventDefault() {}, target: this, ...event });
  }

  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  removeAttribute(name) { this.attributes.delete(name); }
  getAttribute(name) {
    const reflected = { "aria-expanded": "ariaExpanded", "aria-disabled": "ariaDisabled", "aria-checked": "ariaChecked" }[name];
    return (reflected === undefined ? undefined : this[reflected]) ?? this.attributes.get(name) ?? null;
  }
  toggleAttribute(name, force) {
    if (force) this.attributes.set(name, "");
    else this.attributes.delete(name);
  }
  focus() { globalThis.document.activeElement = this; }
  contains(value) {
    return value === this || this.children.some((child) => child.contains?.(value));
  }
  querySelectorAll(selector) {
    const matches = [];
    const visit = (element) => {
      for (const child of element.children) {
        if (selector === "[role=option]" && child.getAttribute?.("role") === "option") matches.push(child);
        if (selector === ".nami-setup__pair-placeholder" && child.classList?.values.has("nami-setup__pair-placeholder")) matches.push(child);
        visit(child);
      }
    };
    visit(this);
    return matches;
  }
}

globalThis.HTMLElement = ElementFake;
globalThis.document = {
  activeElement: null,
  createElement(tagName) { return new ElementFake(tagName); },
  addEventListener() {},
};
globalThis.queueMicrotask = (callback) => callback();

function moduleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

const rendererUrl = moduleUrl(`
  export function renderText(element, text) { element.textContent = text; }
  export function renderFilesystemText(element, text) { element.textContent = text; }
`);
const iconsUrl = moduleUrl(`
  export function createIcon(document, name, size) {
    const icon = document.createElement("svg"); icon.dataset.icon = name; icon.dataset.size = size; return icon;
  }
`);
const setupSource = (await readFile(process.argv[2], "utf8"))
  .replace("./icons.js", iconsUrl)
  .replace("./render.js", rendererUrl);
const { createSetupPanel } = await import(moduleUrl(setupSource));

const events = [];
const panel = createSetupPanel({
  onEdit: (...value) => events.push(["edit", ...value]),
  onValidate: (...value) => events.push(["validate", ...value]),
  onPick: (...value) => events.push(["pick", ...value]),
  onRecent: (...value) => events.push(["recent", ...value]),
  onRecentPair: (...value) => events.push(["recent-pair", ...value]),
  onRefreshRecents: () => events.push(["refresh-recents"]),
  onMode: (...value) => events.push(["mode", ...value]),
  onOption: (...value) => events.push(["option", ...value]),
  onAddFilter: (...value) => events.push(["add-filter", ...value]),
  onRemoveFilter: (...value) => events.push(["remove-filter", ...value]),
  onMount: (...value) => events.push(["mount", ...value]),
  onPlanAgainMount: (...value) => events.push(["plan-mount", ...value]),
  onStartPlan: () => events.push(["start-plan"]),
  onStartInventory: () => events.push(["start-inventory"]),
  onAddPair: () => events.push(["add-pair"]),
  onRemoveBatchRow: (row) => events.push(["remove-batch", row]),
  onClearBatchResults: () => events.push(["clear-batch"]),
  onStartBatch: () => events.push(["start-batch"]),
  onPlanAgain: () => events.push(["plan-again"]),
});

const options = {
  filters: ["  raw\\filter  "], deletion_policy: "trash", trash_on_update: false,
  preservation: { preserve_ads: false, preserve_created: true, preserve_acl: false },
  propagate_source_casing: false, verify_after_execute: false,
};
const model = {
  setup: {
    setup_state: "default",
    task_kind: null,
    recents: {
      sources: [
        { location_id: "7", display: "<recent>", last_used_at: "2026-09-11T00:00:00+00:00" },
        { location_id: "10", display: "second recent", last_used_at: "2026-09-10T00:00:00+00:00" },
      ],
      targets: [],
      pairs: [{
        mapping_id: "9",
        source: { location_id: "7", display: "<pair-source>", last_used_at: "2026-09-11T00:00:00+00:00" },
        target: { location_id: "8", display: "pair-target", last_used_at: "2026-09-11T00:00:00+00:00" },
        last_used_at: "2026-09-11T00:00:00+00:00",
      }],
    },
    plan_again: null,
  },
  recentPairAvailability: { "9": { source: "online", target: "online" } },
  options,
  mode: "sync-plan",
  source: {
    text: "C:\\typed", candidate: null, continuationId: `slot-${"1".repeat(32)}`,
    mountIndex: null, location: { state: "ambiguous", detail: "Choose a mount.", candidates: ["M:\\"] },
  },
  target: { text: "D:\\target", continuationId: null, mountIndex: null, location: null },
  batch: [], batchRunning: false, editable: true, artifactReady: false,
  attempt: null, actionMessage: null,
  canPlanAgain: false, planAgainMounts: { source: null, target: null },
};
function byClass(root, className) {
  if (root.classList?.values.has(className)) return root;
  for (const child of root.children ?? []) {
    const match = byClass(child, className);
    if (match) return match;
  }
  return null;
}
function allByClass(root, className, values = []) {
  if (root.classList?.values.has(className)) values.push(root);
  for (const child of root.children ?? []) allByClass(child, className, values);
  return values;
}

panel.render(model);
const locations = allByClass(panel.element, "nami-setup__location");
const firstSource = byClass(locations[0], "nami-setup__path");
assert.equal(byClass(locations[1], "nami-setup__location-status").textContent, "");
assert.equal(byClass(locations[1], "nami-setup__location-status").hidden, true);
assert.equal(byClass(locations[0], "nami-setup__location-status").textContent, "Choose a mount.");
const mount = byClass(locations[0], "nami-setup__mount");
assert.equal(mount.dataset.mountIndex, "0");
mount.dispatch("click");
const pair = byClass(panel.element, "nami-setup__recent-pair");
const recentPairTable = byClass(panel.element, "nami-setup__recent-pair-table");
assert.equal(recentPairTable.children[1].children.length, 5, "recent table retains five row slots");
assert.ok(allByClass(panel.element, "nami-setup__pair-viewport").length === 2);
assert.deepEqual(
  allByClass(pair, "nami-setup__availability").map((item) => item.dataset.availability),
  ["online", "online"],
);
const pairSelect = byClass(pair, "nami-setup__pair-select");
pairSelect.focus();
pairSelect.dispatch("click");
panel.render(model);
assert.equal(byClass(panel.element, "nami-setup__pair-select"), pairSelect, "recent pair controls retain identity across renders");
assert.equal(globalThis.document.activeElement, pairSelect, "recent pair focus survives a render");
const recentTrigger = byClass(locations[0], "nami-setup__recent-trigger");
const recentPopup = byClass(locations[0], "nami-setup__recent-popup");
assert.deepEqual(allByClass(recentTrigger, "nami-setup__caret").map((item) => item.dataset.icon),
  ["chevron-down", "chevron-up"]);
recentTrigger.dispatch("keydown", { key: "ArrowDown" });
assert.equal(recentTrigger.getAttribute("aria-expanded"), "true");
recentPopup.dispatch("keydown", { key: "Enter" });
assert.equal(recentTrigger.getAttribute("aria-expanded"), "false");
recentTrigger.dispatch("keydown", { key: "ArrowDown" });
const previousSources = model.setup.recents.sources;
model.setup.recents.sources = [{ ...previousSources[0], display: "Updated recent" }];
panel.render(model);
assert.equal(recentPopup.hidden, true, "same-form recent reload closes the old popup");
assert.equal(recentTrigger.getAttribute("aria-expanded"), "false");
assert.equal(globalThis.document.activeElement, recentTrigger, "recent reload restores focus before replacing options");
recentTrigger.dispatch("keydown", { key: "ArrowDown" });
model.setup.recents.sources = [];
panel.render(model);
assert.equal(recentPopup.hidden, true);
assert.equal(recentTrigger.disabled, true);
assert.equal(globalThis.document.activeElement, firstSource, "empty recents restore focus to the editable path");
model.setup.recents.sources = previousSources;
panel.render(model);
recentTrigger.dispatch("click");
const pointerOptions = recentPopup.querySelectorAll("[role=option]");
assert.ok(pointerOptions.every((option) => option.getAttribute("data-active") === null),
  "pointer-open recents have no default active treatment");
recentTrigger.dispatch("keydown", { key: "ArrowUp" });
assert.equal(globalThis.document.activeElement, pointerOptions[1], "ArrowUp from neutral opens at the last recent");
assert.equal(pointerOptions[1].getAttribute("data-active"), "");
pointerOptions[0].dispatch("pointerenter");
assert.ok(pointerOptions.every((option) => option.getAttribute("data-active") === null),
  "pointer handoff clears keyboard active treatment");
recentPopup.dispatch("keydown", { key: "Enter" });
assert.equal(events.at(-1)[2], previousSources[1], "Enter chooses the still-focused option after pointer handoff");
assert.equal(recentPopup.hidden, true);
assert.ok(pointerOptions.every((option) => option.getAttribute("data-active") === null),
  "choosing a recent resets active treatment before the next open");
const moreOptions = byClass(panel.element, "nami-setup__more-summary");
const advancedOptions = byClass(panel.element, "nami-setup__advanced-options");
assert.equal(moreOptions.tagName, "BUTTON");
assert.equal(moreOptions.getAttribute("aria-controls"), "setup-advanced-options");
assert.equal(moreOptions.getAttribute("aria-expanded"), "false");
assert.deepEqual(allByClass(moreOptions, "nami-setup__more-caret").map((item) => item.dataset.icon),
  ["chevron-down", "chevron-up"]);
assert.equal(advancedOptions.hidden, true);
moreOptions.dispatch("click");
assert.equal(moreOptions.getAttribute("aria-expanded"), "true");
assert.equal(advancedOptions.hidden, false);
assert.ok(allByClass(advancedOptions, "nami-setup__option").every((label) =>
  label.children.length === 2 && label.children[0].getAttribute("role") === "switch" && label.children[1].tagName === "SPAN"));
const filterControls = byClass(advancedOptions, "nami-setup__filter-controls");
assert.deepEqual(filterControls.children.map((item) => item.tagName), ["INPUT", "BUTTON"]);
panel.render(model);
assert.equal(moreOptions.getAttribute("aria-expanded"), "true", "advanced disclosure survives a render");
assert.equal(advancedOptions.hidden, false);
const primaryOptions = byClass(panel.element, "nami-setup__primary-options");
const verifyToggle = byClass(panel.element, "nami-setup__verify-row").children[0];
const additiveToggle = byClass(panel.element, "nami-setup__additive-row").children[0];
assert.equal(verifyToggle.getAttribute("role"), "switch");
assert.equal(additiveToggle.getAttribute("role"), "switch");
assert.deepEqual(primaryOptions.children.slice(0, 2).map((item) => item.children[1].textContent), ["Verify execution", "Additive sync"]);
assert.equal(additiveToggle.checked, false);
additiveToggle.checked = true;
additiveToggle.dispatch("change");
model.recentPairAvailability = { "9": { source: "online", target: "offline" } };
panel.render(model);
const offlinePair = byClass(panel.element, "nami-setup__recent-pair");
assert.equal(offlinePair.getAttribute("aria-disabled"), "true");
assert.equal(byClass(offlinePair, "nami-setup__pair-select").disabled, true);
assert.deepEqual(
  allByClass(offlinePair, "nami-setup__availability").map((item) => item.children[1].textContent),
  ["Online", "Offline"],
  "a mixed pair retains both endpoint truths while selection is disabled",
);
assert.deepEqual(allByClass(offlinePair, "nami-setup__pair-path-value").map((item) => item.textContent), ["<pair-source>", "pair-target"]);
const actions = byClass(panel.element, "nami-setup__actions").children;
const startPlan = actions[0];
const addPair = actions[2];
const startBatch = byClass(panel.element, "nami-setup__batch-actions").children[1];
assert.equal(startBatch.textContent, "Create batch");
assert.equal(startPlan.disabled, true, "an ambiguous row requires an explicit mount choice");
model.source.location = null;
model.source.candidate = { kind: "literal_path", path: "C:\\typed", selected_mount: null };
panel.render(model);
assert.equal(startPlan.disabled, false, "nonempty unadmitted rows stay startable for admission on Start");
model.source.location = { state: "missing", choice_id: null, detail: "Reconnect this folder.", candidates: [] };
panel.render(model);
assert.equal(startPlan.disabled, false, "a missing row stays startable for a fresh retry");
const queuedBatchRow = {
  source: { text: "C:\\batch-source" }, target: { text: "D:\\batch-target" },
  state: "queued", options: structuredClone(options), message: "Ready to create.",
};
model.batch = [queuedBatchRow];
model.batchRunning = true;
panel.render(model);
const renderedBatch = byClass(panel.element, "nami-setup__batch-row");
const batchTable = byClass(panel.element, "nami-setup__batch-table");
assert.deepEqual(batchTable.children[0].children[0].children.map((item) => item.children[0]?.textContent ?? item.ariaLabel),
  ["Folders", "Settings", "Status", "Actions"]);
assert.equal(batchTable.children[1].children.length, 5, "batch table retains five row slots");
assert.deepEqual(byClass(renderedBatch, "nami-setup__batch-settings").children.map((item) => item.textContent),
  ["Verify: Off", "Deletion: Trash"]);
assert.deepEqual(allByClass(renderedBatch, "nami-setup__batch-path").map((item) =>
  [item.children[0].textContent, item.children[1].textContent, item.title]), [
  ["Source: ", "C:\\batch-source", "C:\\batch-source"], ["Target: ", "D:\\batch-target", "D:\\batch-target"],
]);
assert.equal(byClass(renderedBatch, "nami-setup__batch-status").textContent, "Ready");
assert.equal(byClass(renderedBatch, "nami-setup__batch-status").title, "Ready to create.");
assert.equal(startPlan.hidden, false);
assert.equal(startPlan.disabled, true, "a queued batch keeps single Create visible but unavailable");
assert.equal(startBatch.hidden, false);
assert.equal(byClass(panel.element, "nami-setup__clear-batch").hidden, false);
assert.equal(byClass(panel.element, "nami-setup__clear-batch").disabled, true,
  "Clear results stays visible but disabled for queued-only rows");
byClass(renderedBatch, "nami-setup__batch-remove").dispatch("click");
model.batch = [{ ...queuedBatchRow, state: "created", options: { ...options, deletion_policy: "additive", verify_after_execute: true }, message: "Plan task created." }];
panel.render(model);
assert.deepEqual(byClass(byClass(panel.element, "nami-setup__batch-row"), "nami-setup__batch-settings").children.map((item) => item.textContent),
  ["Verify: On", "Deletion: Additive"], "terminal rows retain their attempted settings");
assert.equal(startPlan.hidden, false, "single Create stays visible after the batch settles");
assert.equal(startBatch.hidden, false);
assert.equal(startBatch.disabled, true, "Create batch stays visible but disabled for settled-only rows");
assert.equal(byClass(panel.element, "nami-setup__clear-batch").hidden, false);
assert.equal(byClass(panel.element, "nami-setup__clear-batch").disabled, false);
byClass(panel.element, "nami-setup__clear-batch").dispatch("click");
model.batch = [queuedBatchRow];
panel.render(model);
assert.equal(startPlan.disabled, true, "active batch disables form start");
assert.equal(startBatch.disabled, true, "active batch disables reentrant batch start");
model.batchRunning = false;
model.batch = [{ ...queuedBatchRow, state: "unknown", message: "Unknown state." }];
panel.render(model);
assert.equal(startBatch.hidden, false);
assert.equal(startBatch.disabled, true, "unknown rows cannot start a batch");
assert.equal(byClass(panel.element, "nami-setup__clear-batch").disabled, true,
  "unknown rows cannot be cleared as terminal results");
model.batch = [{ ...queuedBatchRow, state: "uncertain", message: "Retry this request." }];
panel.render(model);
assert.equal(startBatch.textContent, "Retry batch");
assert.equal(startBatch.disabled, false, "an uncertain row exposes the same-command retry");
model.mode = "inventory";
panel.render(model);
assert.equal(startBatch.hidden, false);
assert.equal(startBatch.disabled, true, "inventory mode retains but disables the batch retry");
model.mode = "sync-plan";
model.editable = false;
panel.render(model);
assert.equal(startBatch.hidden, false);
assert.equal(startBatch.disabled, true, "a noneditable form retains but disables the batch retry");
model.editable = true;
model.batch = [queuedBatchRow];
model.batchCount = 48;
panel.render(model);
assert.equal(addPair.disabled, true, "the page-wide batch cap disables Add pair");
model.batchCount = 1;
model.closePending = true;
panel.render(model);
assert.equal(startBatch.disabled, true, "pending origin close disables batch start");
model.attempt = { kind: "sync-plan", running: false, retry() {} };
panel.render(model);
assert.equal(startPlan.disabled, true, "pending origin close disables exact form retry");
model.closePending = false;
model.attempt = { kind: "sync-plan", running: true, retry: null };
panel.render(model);
assert.equal(startBatch.disabled, true, "active form attempt disables batch start");
model.attempt = null;
model.batch = [];
panel.render(model);
firstSource.value = "C:\\edited";
firstSource.dispatch("input");
const clearSource = byClass(locations[0], "nami-setup__clear");
assert.equal(clearSource.hidden, false);
let preventedClearFocus = false;
clearSource.dispatch("pointerdown", { preventDefault() { preventedClearFocus = true; } });
assert.equal(preventedClearFocus, true);
firstSource.dispatch("blur", { relatedTarget: clearSource });
clearSource.dispatch("click");
assert.equal(firstSource.value, "");
assert.equal(clearSource.hidden, true);
assert.equal(globalThis.document.activeElement, firstSource);
firstSource.value = "C:\\edited";
firstSource.dispatch("input");
firstSource.dispatch("keydown", { key: "Enter" });
const filterInput = filterControls.children[0];
filterInput.value = "  no-normalize\\  ";
filterInput.dispatch("keydown", { key: "Enter" });
const mode = byClass(panel.element, "nami-setup__mode");
assert.equal(mode.ariaLabel, "Task type");
assert.equal(byClass(panel.element, "nami-setup__action-status").hidden, true);
mode.children[0].dispatch("keydown", { key: "ArrowRight" });
panel.render({
  ...model, options: null, editable: false, mode: "inventory",
  setup: { ...model.setup, setup_state: "frozen", task_kind: "inventory" },
});
assert.equal(byClass(allByClass(panel.element, "nami-setup__location")[0], "nami-setup__path"), firstSource, "renders retain the active source input");
assert.equal(firstSource.disabled, true);
assert.equal(allByClass(panel.element, "nami-setup__location")[0].children[0].children[0].textContent, "Root");
assert.deepEqual(events, [
  ["mount", "source", 0],
  ["recent-pair", model.setup.recents.pairs[0]],
  ["recent", "source", model.setup.recents.sources[0]],
  ["recent", "source", model.setup.recents.sources[1]],
  ["option", "deletion_policy", "additive"],
  ["remove-batch", queuedBatchRow],
  ["clear-batch"],
  ["edit", "source", "C:\\edited"],
  ["edit", "source", ""],
  ["edit", "source", "C:\\edited"],
  ["validate", "source"],
  ["add-filter", "  no-normalize\\  "],
  ["mode", "inventory"],
]);
console.log("ok");
