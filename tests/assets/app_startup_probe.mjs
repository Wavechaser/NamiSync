import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";


class HTMLElementFake {
  constructor(textContent = "") {
    this.textContent = textContent;
    this.appended = [];
  }

  append(...values) {
    this.appended.push(...values);
  }
}

globalThis.HTMLElement = HTMLElementFake;
const app = new HTMLElementFake();
const status = new HTMLElementFake("Starting...");
globalThis.document = {
  documentElement: new HTMLElementFake(),
  querySelector(selector) {
    return selector === "#app" ? app : selector === "#host-status" ? status : null;
  },
};

const listeners = new Map();
globalThis.window = {
  chrome: { webview: {} },
  addEventListener(name, callback) {
    const callbacks = listeners.get(name) ?? [];
    callbacks.push(callback);
    listeners.set(name, callbacks);
  },
};

const acknowledgements = [];
let operationalMarks = 0;
let appearanceRevision = 0;
let appearanceWaiters = [];
function applyAppearance() {
  appearanceRevision += 1;
  const ready = appearanceWaiters.filter(
    (waiter) => appearanceRevision > waiter.baseline,
  );
  appearanceWaiters = appearanceWaiters.filter(
    (waiter) => appearanceRevision <= waiter.baseline,
  );
  for (const waiter of ready) waiter.resolve();
}
globalThis.startupHarness = {
  acknowledge() {
    let resolve;
    let reject;
    const promise = new Promise((onResolve, onReject) => {
      resolve = onResolve;
      reject = onReject;
    });
    acknowledgements.push({ promise, resolve, reject });
    return promise;
  },
  appearance: Object.freeze({
    revision: () => appearanceRevision,
    whenAppliedAfter(baseline) {
      if (appearanceRevision > baseline) return Promise.resolve();
      return new Promise((resolve) => {
        appearanceWaiters.push({ baseline, resolve });
      });
    },
  }),
};

function moduleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

const bridgeStub = moduleUrl(`
  export class BridgeTransportError extends Error {}
  globalThis.startupHarness.BridgeTransportError = BridgeTransportError;
  export const whenBridgeApiReady = () => Promise.resolve();
  export const acknowledgeShellReady = () => globalThis.startupHarness.acknowledge();
  export const markBridgeOperational = () => { globalThis.startupHarness.markOperational(); };
`);
globalThis.startupHarness.markOperational = () => {
  operationalMarks += 1;
};
const appearanceStub = moduleUrl(`
  export const installAppearanceReceiver = () => globalThis.startupHarness.appearance;
`);
const railStub = moduleUrl("export const createTaskRail = () => ({});");
const panelsStub = moduleUrl("export const createWorkPanel = () => ({});");
const renderStub = moduleUrl(`
  export const renderText = (element, value) => { element.textContent = value; };
`);

let source = await readFile(process.argv[2], "utf8");
source = source.replace(
  /import \{[\s\S]*?\} from "\.\/bridge\.js";/,
  `import { acknowledgeShellReady, BridgeTransportError, markBridgeOperational, whenBridgeApiReady } from "${bridgeStub}";`,
);
source = source
  .replace("./appearance.js", appearanceStub)
  .replace("./panels.js", panelsStub)
  .replace("./rail.js", railStub)
  .replace("./render.js", renderStub);

await import(moduleUrl(source));
for (let turn = 0; turn < 4; turn += 1) await Promise.resolve();
assert.equal(acknowledgements.length, 1);

for (const callback of listeners.get("pywebviewready") ?? []) callback();
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(
  acknowledgements.length,
  2,
  "reinjection while an acknowledgement is pending starts a fresh attempt",
);
assert.equal(status.textContent, "Starting...");
assert.equal(operationalMarks, 0);

acknowledgements[1].resolve({ acknowledged: true });
for (let turn = 0; turn < 4; turn += 1) await Promise.resolve();
assert.equal(
  status.textContent,
  "Starting...",
  "an acknowledgement without appearance convergence cannot report Ready",
);
applyAppearance();
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(status.textContent, "Ready");
assert.equal(operationalMarks, 1);

for (const callback of listeners.get("pywebviewready") ?? []) callback();
for (let turn = 0; turn < 4; turn += 1) await Promise.resolve();
assert.equal(status.textContent, "Starting...");
assert.equal(acknowledgements.length, 3);
acknowledgements[2].reject(
  new globalThis.startupHarness.BridgeTransportError("lost response"),
);
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(
  status.textContent,
  "Starting...",
  "an old appearance cannot settle a new uncertain generation",
);
assert.equal(operationalMarks, 1);
applyAppearance();
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(status.textContent, "Ready");
assert.equal(operationalMarks, 2);

for (const callback of listeners.get("pywebviewready") ?? []) callback();
for (let turn = 0; turn < 4; turn += 1) await Promise.resolve();
assert.equal(status.textContent, "Starting...");
assert.equal(acknowledgements.length, 4);
acknowledgements[3].reject(new Error("definitive refusal"));
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(
  status.textContent,
  "Starting...",
  "a definitive non-transport failure cannot report Ready",
);
assert.equal(operationalMarks, 2);

process.stdout.write("ok");
