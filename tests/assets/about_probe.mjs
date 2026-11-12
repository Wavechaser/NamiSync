import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

class Style {
  constructor() { this.values = new Map(); }
  getPropertyValue(name) { return this.values.get(name)?.[0] ?? ""; }
  getPropertyPriority(name) { return this.values.get(name)?.[1] ?? ""; }
  setProperty(name, value, priority = "") { this.values.set(name, [value, priority]); }
  removeProperty(name) { this.values.delete(name); }
}
class Element {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase(); this.children = []; this.listeners = new Map();
    this.dataset = {}; this.style = new Style(); this.isConnected = true; this.inert = false;
    this.disabled = false; this.open = false; this.animations = []; this.textContent = "";
  }
  append(...values) { this.children.push(...values); }
  replaceChildren(...values) { this.children = values; }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, callback) { this.listeners.set(name, callback); }
  dispatch(name, target = this) {
    const event = { target, defaultPrevented: false, stopped: false,
      preventDefault() { this.defaultPrevented = true; }, stopPropagation() { this.stopped = true; } };
    this.listeners.get(name)?.(event); return event;
  }
  focus() { document.activeElement = this; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  getAnimations() { return this.animations; }
}
globalThis.HTMLElement = Element;
globalThis.document = { documentElement: new Element("html"), createElement: (name) => new Element(name) };
const frames = [];
globalThis.requestAnimationFrame = (callback) => frames.push(callback);
const frame = () => { for (const callback of frames.splice(0)) callback(); };
const moduleUrl = (source) => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const legalUrl = pathToFileURL(process.argv[3]).href;
const { NAMI_LICENSE, OPEN_SOURCE_ACKNOWLEDGEMENTS } = await import(legalUrl);
const source = (await readFile(process.argv[2], "utf8"))
  .replace("./legal_content.js", legalUrl)
  .replace("./render.js", moduleUrl("export const renderText = (element, text) => { element.textContent = text; };"));
const { createAboutNotices } = await import(moduleUrl(source));
const app = new Element("main"), popup = new Element("div"), invoker = new Element("button");
popup.inert = true;
const notices = createAboutNotices([app, popup]);
const dialog = notices.element;
const [heading, body, actions] = dialog.children;
const close = actions.children[0];
document.documentElement.style.setProperty("overflow", "clip", "important");
notices.showLicense(invoker);
assert.ok(dialog.open && app.inert && popup.inert);
assert.equal(document.activeElement, close);
assert.equal(heading.textContent, NAMI_LICENSE.title);
assert.equal(body.children[0].children.at(-1).textContent, NAMI_LICENSE.text);
for (const name of ["pointerdown", "pointerup", "click", "dblclick", "contextmenu", "wheel"]) {
  const event = dialog.dispatch(name);
  assert.ok(event.defaultPrevented && event.stopped);
}
assert.equal(dialog.dispatch("wheel", body).defaultPrevented, false);
let finish;
dialog.animations = [{ effect: {getComputedTiming: () => ({endTime: 200})},
  finished: new Promise((resolve) => { finish = resolve; }) }];
dialog.dispatch("cancel");
frame(); frame();
assert.ok(dialog.open && app.inert && dialog.dataset.closing === "true");
notices.showAcknowledgements(invoker);
assert.equal(heading.textContent, NAMI_LICENSE.title, "closing modal cannot be replaced");
finish(); await Promise.resolve(); await Promise.resolve();
assert.ok(!dialog.open && !app.inert && popup.inert);
assert.equal(document.activeElement, invoker);
assert.equal(document.documentElement.style.getPropertyValue("overflow"), "clip");
assert.equal(document.documentElement.style.getPropertyPriority("overflow"), "important");
dialog.animations = [];
notices.showAcknowledgements(invoker);
assert.equal(heading.textContent, OPEN_SOURCE_ACKNOWLEDGEMENTS.title);
assert.deepEqual(body.children.slice(1).map((value) => value.children.at(-1).textContent),
  OPEN_SOURCE_ACKNOWLEDGEMENTS.notices.map((value) => value.text));
close.dispatch("click"); frame(); frame(); frame();
assert.ok(!dialog.open && !app.inert && popup.inert);
dialog.showModal = () => { throw new Error("native modal unavailable"); };
assert.throws(() => notices.showLicense(invoker), /native modal unavailable/);
assert.ok(!app.inert && popup.inert);
assert.equal(document.documentElement.style.getPropertyValue("overflow"), "clip");
console.log(JSON.stringify({license: NAMI_LICENSE, acknowledgements: OPEN_SOURCE_ACKNOWLEDGEMENTS}));
