import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

class ElementFake {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.listeners = new Map();
    this.dataset = {};
    this.value = "";
    this.disabled = false;
    this.textContent = "";
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, listener) { this.listeners.set(name, listener); }
  click() { if (!this.disabled) this.listeners.get("click")?.({}); }
  change(checked) {
    this.checked = checked;
    this.listeners.get("change")?.({});
  }
}
globalThis.HTMLElement = ElementFake;
globalThis.document = { createElement: (name) => new ElementFake(name) };
const moduleUrl = (source) => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const reads = [], saves = [];
class BridgeTransportError extends Error {}
globalThis.settingsProbe = {
  BridgeTransportError,
  read() { const value = deferred(); reads.push(value); return value.promise; },
  commit(patch, onDelayed) {
    const value = { ...deferred(), patch, onDelayed };
    saves.push(value);
    return value.promise;
  },
};
const source = (await readFile(process.argv[2], "utf8"))
  .replace("./bridge.js", moduleUrl(`
    export const BridgeTransportError = globalThis.settingsProbe.BridgeTransportError;
    export const readSetupDefaults = () => globalThis.settingsProbe.read();
    export const commitSetupDefaults = (...args) => globalThis.settingsProbe.commit(...args);`))
  .replace("./render.js", moduleUrl(`
    export const renderText = (element, value) => { element.textContent = value; };
    export const renderFilesystemText = renderText;`));
const { installSetupDefaults } = await import(moduleUrl(source));
const flush = async () => { for (let count = 0; count < 5; count += 1) await Promise.resolve(); };
const options = (patch = {}) => ({ filters: [], deletion_policy: "trash", trash_on_update: true,
  preservation: { preserve_ads: false, preserve_created: true, preserve_acl: false },
  propagate_source_casing: false, verify_after_execute: false, ...patch });
const elements = Object.fromEntries(["controls", "status", "save", "refresh"].map((name) =>
  [`#setup-defaults-${name}`, new ElementFake(name === "save" || name === "refresh" ? "button" : "div")]));
const root = { querySelector: (selector) => elements[selector] };
const panel = installSetupDefaults(root);
const walk = (element) => [element, ...element.children.flatMap(walk)];
const controls = elements["#setup-defaults-controls"];
const find = (predicate) => walk(controls).find(predicate);
const verify = find((value) => value.dataset.defaultOption === "verify_after_execute");
const ads = find((value) => value.dataset.defaultOption === "preserve_ads");
const save = elements["#setup-defaults-save"];
const refresh = elements["#setup-defaults-refresh"];
const status = elements["#setup-defaults-status"];
const filter = find((value) => value.id === "defaults-filter");
const add = find((value) => value.textContent === "Add filter");
assert.ok(save.disabled && verify.disabled && ads.disabled);
const initial = panel.open();
void panel.open();
assert.equal(reads.length, 1, "concurrent navigation shares the active read");
reads[0].resolve(options({ filters: ["line\nbreak", "literal\\*.txt"] }));
await initial;
assert.ok(!verify.disabled && ads.disabled && save.disabled);
assert.deepEqual(find((value) => value.className === "nami-settings__filter-list").children
  .map((value) => value.children[0].textContent), ["line\nbreak", "literal\\*.txt"]);

verify.change(true);
assert.equal(status.textContent, "Unsaved changes.");
const reopen = panel.open();
verify.change(false); // A stale event cannot edit while the read owns the controls.
reads[1].resolve(options({ filters: ["server-only"] }));
await reopen;
assert.ok(verify.checked, "navigation retains unsaved fields");
save.click();
save.click();
void panel.open();
assert.equal(reads.length, 2);
assert.equal(saves.length, 1);
assert.deepEqual(saves[0].patch, { verify_after_execute: true }, "clean canonical fields are not committed");
assert.ok(verify.disabled && save.disabled);
saves[0].onDelayed({ state: "pending", check: null });
assert.match(status.textContent, /Waiting for confirmation/);
verify.change(false);
saves[0].resolve(options({ filters: ["server-only"], verify_after_execute: true }));
await flush();
assert.ok(verify.checked && !verify.disabled && save.disabled && ads.disabled);
saves[0].onDelayed({ state: "pending", check: null });
assert.match(status.textContent, /^Defaults saved/, "retired delayed feedback cannot overwrite confirmation");

filter.value = "raw\\pattern\tvalue";
add.click();
save.click();
assert.deepEqual(saves[1].patch, { filters: ["server-only", "raw\\pattern\tvalue"] });
saves[1].reject(new BridgeTransportError("lost completion"));
await flush();
assert.ok(refresh.hidden === false && verify.disabled && save.disabled);
assert.equal(saves.length, 2, "unknown completion is never replayed");
refresh.click();
assert.equal(reads.length, 3);
reads[2].resolve(options({ filters: ["server-only"], verify_after_execute: true }));
await flush();
assert.ok(!verify.disabled && !save.disabled);
assert.match(status.textContent, /earlier save outcome could not be confirmed/);
save.click();
assert.deepEqual(saves[2].patch, { filters: ["server-only", "raw\\pattern\tvalue"] });
saves[2].reject(new TypeError("invalid filter"));
await flush();
assert.ok(!verify.disabled && !save.disabled && refresh.hidden);
assert.match(status.textContent, /not saved/);

const failedRead = panel.open();
reads[3].reject(new BridgeTransportError("read failed"));
await failedRead;
assert.ok(verify.disabled && !refresh.hidden);
refresh.click();
reads[4].resolve(options({ filters: ["server-only"], verify_after_execute: true }));
await flush();
assert.ok(!verify.disabled && !save.disabled);
assert.equal(status.textContent, "Unsaved changes.");
assert.equal(saves.length, 3);
console.log("ok");
