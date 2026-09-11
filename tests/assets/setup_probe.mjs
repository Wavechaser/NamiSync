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
      sources: [{ location_id: "7", display: "<recent>", last_used_at: "2026-09-11T00:00:00+00:00" }],
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
  recentPairAvailability: { "9": "online" },
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
assert.equal(byClass(locations[0], "nami-setup__location-status").textContent, "Choose a mount.");
const mount = byClass(locations[0], "nami-setup__mount");
assert.equal(mount.dataset.mountIndex, "0");
mount.dispatch("click");
const pair = byClass(panel.element, "nami-setup__recent-pair");
assert.equal(pair.dataset.availability, "online");
const pairSelect = byClass(pair, "nami-setup__pair-select");
pairSelect.focus();
pairSelect.dispatch("click");
panel.render(model);
assert.equal(byClass(panel.element, "nami-setup__pair-select"), pairSelect, "recent pair controls retain identity across renders");
assert.equal(globalThis.document.activeElement, pairSelect, "recent pair focus survives a render");
const recentTrigger = byClass(locations[0], "nami-setup__recent-trigger");
const recentPopup = byClass(locations[0], "nami-setup__recent-popup");
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
const moreOptions = byClass(panel.element, "nami-setup__more-options");
assert.equal(moreOptions.tagName, "DETAILS");
assert.equal(byClass(panel.element, "nami-setup__primary-options").children[2].children[0].getAttribute("role"), "switch");
model.recentPairAvailability = { "9": "offline" };
panel.render(model);
const offlinePair = byClass(panel.element, "nami-setup__recent-pair");
assert.equal(offlinePair.getAttribute("aria-disabled"), "true");
assert.equal(byClass(offlinePair, "nami-setup__pair-select").disabled, true);
assert.equal(byClass(offlinePair, "nami-setup__availability").children[1].textContent, "Offline");
assert.deepEqual(allByClass(offlinePair, "nami-setup__pair-path").map((item) => item.textContent), ["<pair-source>", "pair-target"]);
const actions = byClass(panel.element, "nami-setup__actions").children;
const startPlan = actions[0];
const startBatch = actions[3];
assert.equal(startPlan.disabled, true, "an ambiguous row requires an explicit mount choice");
model.source.location = null;
model.source.candidate = { kind: "literal_path", path: "C:\\typed", selected_mount: null };
panel.render(model);
assert.equal(startPlan.disabled, false, "nonempty unadmitted rows stay startable for admission on Start");
model.source.location = { state: "missing", choice_id: null, detail: "Reconnect this folder.", candidates: [] };
panel.render(model);
assert.equal(startPlan.disabled, false, "a missing row stays startable for a fresh retry");
model.batch = [{ state: "queued", message: "Ready to create." }];
model.batchRunning = true;
panel.render(model);
assert.equal(startPlan.disabled, true, "active batch disables form start");
assert.equal(startBatch.disabled, true, "active batch disables reentrant batch start");
model.batchRunning = false;
model.attempt = { kind: "sync-plan", running: true, retry: null };
panel.render(model);
assert.equal(startBatch.disabled, true, "active form attempt disables batch start");
model.attempt = null;
model.batch = [];
panel.render(model);
firstSource.value = "C:\\edited";
firstSource.dispatch("input");
firstSource.dispatch("keydown", { key: "Enter" });
const filterInput = byClass(panel.element, "nami-setup__filters").children[1];
filterInput.value = "  no-normalize\\  ";
filterInput.dispatch("keydown", { key: "Enter" });
const mode = byClass(panel.element, "nami-setup__mode");
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
  ["edit", "source", "C:\\edited"],
  ["validate", "source"],
  ["add-filter", "  no-normalize\\  "],
  ["mode", "inventory"],
]);
console.log("ok");
