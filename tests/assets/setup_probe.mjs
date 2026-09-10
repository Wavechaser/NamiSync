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

  addEventListener(name, listener) {
    const values = this.listeners.get(name) ?? [];
    values.push(listener);
    this.listeners.set(name, values);
  }

  dispatch(name, event = {}) {
    for (const listener of this.listeners.get(name) ?? []) listener({ preventDefault() {}, ...event });
  }

  setAttribute(name, value) { this[name] = value; }
}

globalThis.HTMLElement = ElementFake;
globalThis.document = {
  activeElement: null,
  createElement(tagName) { return new ElementFake(tagName); },
};
globalThis.queueMicrotask = (callback) => callback();

function moduleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

const rendererUrl = moduleUrl(`
  export function renderText(element, text) { element.textContent = text; }
  export function renderFilesystemText(element, text) { element.textContent = text; }
`);
const setupSource = (await readFile(process.argv[2], "utf8")).replace("./render.js", rendererUrl);
const { createSetupPanel } = await import(moduleUrl(setupSource));

const events = [];
const panel = createSetupPanel({
  onEdit: (...value) => events.push(["edit", ...value]),
  onValidate: (...value) => events.push(["validate", ...value]),
  onPick: (...value) => events.push(["pick", ...value]),
  onRecent: (...value) => events.push(["recent", ...value]),
  onRecentPair: (...value) => events.push(["recent-pair", ...value]),
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
panel.render(model);
const firstSource = panel.element.children[5].children[1];
assert.equal(panel.element.children[5].children[3].textContent, "Choose a mount.");
const mount = panel.element.children[5].children.at(-1).children[0];
assert.equal(mount.dataset.mountIndex, "0");
mount.dispatch("click");
const pair = panel.element.children[7].children[1].children[0];
pair.dispatch("click");
const startPlan = panel.element.children[9].children[0];
const startBatch = panel.element.children[9].children[3];
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
const filterInput = panel.element.children[8].children[3].children[1];
filterInput.value = "  no-normalize\\  ";
filterInput.dispatch("keydown", { key: "Enter" });
const mode = panel.element.children[4];
mode.value = "inventory";
mode.dispatch("change");
panel.render({
  ...model, options: null, editable: false, mode: "inventory",
  setup: { ...model.setup, setup_state: "frozen", task_kind: "inventory" },
});
assert.equal(panel.element.children[5].children[1], firstSource, "renders retain the active source input");
assert.equal(firstSource.disabled, true);
assert.equal(panel.element.children[5].children[0].textContent, "Inventory root");
assert.deepEqual(events, [
  ["mount", "source", 0],
  ["recent-pair", model.setup.recents.pairs[0]],
  ["edit", "source", "C:\\edited"],
  ["validate", "source"],
  ["add-filter", "  no-normalize\\  "],
  ["mode", "inventory"],
]);
console.log("ok");
