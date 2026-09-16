import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

class ElementFake {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.parentElement = null;
    this.listeners = new Map();
    this.attributes = new Map();
    this.dataset = {};
    this.textContent = "";
    this.disabled = false;
    this.inert = false;
    this.isConnected = true;
    this.open = false;
    this.animations = [];
    this.style = new StyleFake();
  }

  append(...values) {
    for (const value of values) {
      value.parentElement = this;
      this.children.push(value);
    }
  }

  addEventListener(name, callback, options = {}) {
    const listeners = this.listeners.get(name) ?? [];
    listeners.push({ callback, once: options.once === true });
    this.listeners.set(name, listeners);
  }

  removeEventListener(name, callback) {
    this.listeners.set(
      name,
      (this.listeners.get(name) ?? []).filter((entry) => entry.callback !== callback),
    );
  }

  dispatch(name, target = this, propertyName = "") {
    const event = {
      target,
      currentTarget: this,
      defaultPrevented: false,
      propagationStopped: false,
      propertyName,
      preventDefault() { this.defaultPrevented = true; },
      stopPropagation() { this.propagationStopped = true; },
    };
    const retained = [];
    for (const entry of this.listeners.get(name) ?? []) {
      entry.callback(event);
      if (!entry.once) retained.push(entry);
    }
    this.listeners.set(name, retained);
    return event;
  }

  setAttribute(name, value) { this.attributes.set(name, String(value)); }

  showModal() { this.open = true; }
  close() { this.open = false; }
  focus() { this.ownerDocument.activeElement = this; }
  getAnimations() { return this.animations; }
}

class DocumentFake {
  constructor() {
    this.activeElement = null;
    this.documentElement = new ElementFake("html", this);
    this.body = new ElementFake("body", this);
  }
  createElement(tagName) { return new ElementFake(tagName, this); }
}

class StyleFake {
  constructor() { this.values = new Map(); }
  getPropertyValue(name) { return this.values.get(name)?.value ?? ""; }
  getPropertyPriority(name) { return this.values.get(name)?.priority ?? ""; }
  setProperty(name, value, priority = "") {
    this.values.set(name, { value: String(value), priority: String(priority) });
  }
  removeProperty(name) { this.values.delete(name); }
}

globalThis.HTMLElement = ElementFake;
globalThis.document = new DocumentFake();
const animationFrames = [];
globalThis.requestAnimationFrame = (callback) => { animationFrames.push(callback); };

function frame() {
  const callbacks = animationFrames.splice(0);
  for (const callback of callbacks) callback();
}

function moduleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

const renderUrl = moduleUrl(
  "export const renderText = (element, text) => { element.textContent = text; };",
);
const source = (await readFile(process.argv[2], "utf8"))
  .replace("./render.js", renderUrl);
const { createExecutionConfirmation } = await import(moduleUrl(source));

const app = document.createElement("main");
const popup = document.createElement("div");
const trigger = document.createElement("button");
document.activeElement = trigger;
const confirmation = createExecutionConfirmation([app, popup]);
document.body.append(confirmation.element);
const dialog = confirmation.element;
const cancel = findByDataset(dialog, "cancelExecution");
const confirm = findByDataset(dialog, "confirmExecution");

let canceled = 0;
let confirmed = 0;
document.documentElement.style.setProperty("overflow", "clip", "important");
let finishEntrance;
dialog.animations = [{
  effect: { getComputedTiming: () => ({ endTime: 200 }) },
  finished: new Promise((resolve) => { finishEntrance = resolve; }),
}];
confirmation.show({
  destructiveOperationCount: 2,
  returnFocus: trigger,
  onCancel: () => { canceled += 1; },
  onConfirm: () => { confirmed += 1; },
});
assert.equal(dialog.tagName, "DIALOG");
assert.equal(dialog.open, true);
assert.equal(app.inert, true);
assert.equal(popup.inert, true);
assert.equal(document.activeElement, cancel, "Cancel receives initial focus");
assert.equal(document.documentElement.style.getPropertyValue("overflow"), "hidden");
assert.equal(document.documentElement.style.getPropertyPriority("overflow"), "important");
assert.ok(walk(dialog).some((item) => item.textContent === "2 selected destructive operations"));

for (const name of ["pointerdown", "pointerup", "click", "dblclick", "contextmenu", "wheel"]) {
  const event = dialog.dispatch(name);
  assert.equal(event.defaultPrevented, true, `${name} is consumed on the smoke`);
  assert.equal(event.propagationStopped, true, `${name} cannot reach the page`);
}
const consequenceContent = walk(dialog).find(
  (item) => item.id === "execution-confirmation-consequence",
);
const contentWheel = dialog.dispatch("wheel", consequenceContent);
assert.equal(contentWheel.defaultPrevented, false, "dialog content keeps native wheel scrolling");
assert.equal(canceled, 0);
assert.equal(confirmed, 0);
assert.equal(dialog.open, true);

const escape = dialog.dispatch("cancel");
assert.equal(escape.defaultPrevented, true);
assert.equal(canceled, 1);
assert.equal(dialog.open, true, "the native modal remains open through its exit state");
assert.equal(app.inert, true, "the page remains inert through dialog closing");
frame();
frame();
assert.equal(dialog.dataset.closing, "true");
dialog.dispatch("transitionend", dialog, "transform");
assert.equal(dialog.open, true, "an unrelated transition cannot release the smoke");
finishEntrance();
await Promise.resolve();
await Promise.resolve();
assert.equal(dialog.open, false);
assert.equal(app.inert, false);
assert.equal(popup.inert, false);
assert.equal(document.activeElement, trigger, "focus returns after native close");
assert.equal(document.documentElement.style.getPropertyValue("overflow"), "clip");
assert.equal(document.documentElement.style.getPropertyPriority("overflow"), "important");

document.activeElement = trigger;
let finishExit;
dialog.animations = [{
  effect: { getComputedTiming: () => ({ endTime: 200 }) },
  finished: new Promise((resolve) => { finishExit = resolve; }),
}];
confirmation.show({
  destructiveOperationCount: 1,
  returnFocus: trigger,
  onCancel: () => { canceled += 1; },
  onConfirm: () => { confirmed += 1; },
});
confirm.dispatch("click");
confirm.dispatch("click");
assert.equal(confirmed, 1, "double activation submits once");
assert.equal(canceled, 1);
assert.equal(dialog.open, true);
assert.equal(dialog.dispatch("pointerdown").defaultPrevented, true);
frame();
frame();
finishExit();
await Promise.resolve();
await Promise.resolve();
assert.equal(dialog.open, false);
assert.equal(document.activeElement, trigger);

dialog.animations = [];
confirmation.show({
  destructiveOperationCount: 1,
  returnFocus: trigger,
  onCancel: () => { throw new Error("test callback failure"); },
  onConfirm: () => { confirmed += 1; },
});
assert.throws(() => cancel.dispatch("click"), /test callback failure/);
frame();
frame();
assert.equal(dialog.open, true, "zero-motion exit still keeps the modal through a frame");
frame();
assert.equal(dialog.open, false, "callback failure cannot strand the inert page");
assert.equal(app.inert, false);

dialog.showModal = () => { throw new Error("native modal unavailable"); };
assert.throws(() => confirmation.show({
  destructiveOperationCount: 1,
  returnFocus: trigger,
  onCancel: () => { canceled += 1; },
  onConfirm: () => { confirmed += 1; },
}), /native modal unavailable/);
assert.equal(app.inert, false, "failed native admission restores the page immediately");
assert.equal(popup.inert, false);
assert.equal(document.documentElement.style.getPropertyValue("overflow"), "clip");
assert.equal(document.documentElement.style.getPropertyPriority("overflow"), "important");

function walk(root) {
  return [root, ...root.children.flatMap(walk)];
}

function findByDataset(root, name) {
  const found = walk(root).find((item) => Object.hasOwn(item.dataset, name));
  assert.ok(found, `missing ${name}`);
  return found;
}

process.stdout.write("ok");
