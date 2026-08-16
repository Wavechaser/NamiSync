import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";


class TestWindow {
  constructor() {
    this.listeners = new Map();
    this.requests = [];
    this.pywebview = {
      api: {
        dispatch: (requestJson) => this.dispatch(requestJson),
      },
    };
  }

  addEventListener(name, handler, options = {}) {
    const listeners = this.listeners.get(name) ?? [];
    listeners.push({ handler, once: options.once === true });
    this.listeners.set(name, listeners);
  }

  removeEventListener(name, handler) {
    const listeners = this.listeners.get(name) ?? [];
    this.listeners.set(
      name,
      listeners.filter((listener) => listener.handler !== handler),
    );
  }

  dispatch(requestJson) {
    const request = JSON.parse(requestJson);
    this.requests.push(request);
    if (request.command === "reject_once") {
      return Promise.reject(new Error("synthetic transport refusal"));
    }
    const result = request.command === "pick_folder"
      ? { id: `slot-${"2".repeat(32)}`, display: "Selected 🌊" }
      : request.payload;
    return Promise.resolve({
      schema_version: 1,
      request_id: request.request_id,
      ok: true,
      result,
    });
  }
}

let timerCalls = 0;
globalThis.setTimeout = () => {
  timerCalls += 1;
  throw new Error("interactive transport must not create a deadline");
};

const testWindow = new TestWindow();
globalThis.window = testWindow;

const modulePath = process.argv[2];
assert.ok(modulePath, "bridge module path is required");
const source = await readFile(modulePath, "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const bridge = await import(moduleUrl);
bridge.markBridgeOperational();

const invalidCommands = [
  null,
  "",
  "A_command",
  "_private",
  "trailing_",
  "double__word",
  "hyphen-name",
  "a".repeat(65),
];
for (const command of invalidCommands) {
  assert.throws(
    () => bridge.dispatchInteractive(command, {}, () => true),
    /command must be a bounded lowercase snake name/,
  );
}
assert.throws(
  () => bridge.dispatchInteractive("valid_command", {}, null),
  /validateResult must be callable/,
);
assert.equal(testWindow.requests.length, 0, "invalid arguments dispatch nothing");

const unvalidatedPayload = ["payload", "belongs", "to", "the", "command"];
assert.deepEqual(
  await bridge.dispatchInteractive(
    "a".repeat(64),
    unvalidatedPayload,
    (value) => Array.isArray(value),
  ),
  unvalidatedPayload,
);

const selected = await bridge.pickFolder("source");
assert.deepEqual(selected, {
  id: `slot-${"2".repeat(32)}`,
  display: "Selected 🌊",
});
assert.equal(testWindow.requests.at(-1).command, "pick_folder");

const beforeRefusal = testWindow.requests.length;
await assert.rejects(
  bridge.dispatchInteractive("reject_once", {}, () => true),
  { name: "BridgeTransportError" },
);
assert.equal(
  testWindow.requests.length,
  beforeRefusal + 1,
  "interactive transport never automatically retries",
);
assert.equal(timerCalls, 0, "interactive transport owns no client deadline");
