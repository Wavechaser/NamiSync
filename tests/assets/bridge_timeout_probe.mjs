import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";


class TestWindow {
  constructor() {
    this.pywebview = undefined;
    this.listeners = new Map();
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

  emit(name) {
    for (const listener of [...(this.listeners.get(name) ?? [])]) {
      if (listener.once) {
        this.removeEventListener(name, listener.handler);
      }
      listener.handler();
    }
  }

  listenerCount(name) {
    return (this.listeners.get(name) ?? []).length;
  }
}


const timers = new Map();
let nextTimer = 1;
globalThis.setTimeout = (callback, milliseconds) => {
  assert.equal(milliseconds, 30000);
  const token = nextTimer;
  nextTimer += 1;
  timers.set(token, callback);
  return token;
};
globalThis.clearTimeout = (token) => timers.delete(token);

const testWindow = new TestWindow();
globalThis.window = testWindow;

const modulePath = process.argv[2];
assert.ok(modulePath, "bridge module path is required");
const source = await readFile(modulePath, "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const bridge = await import(moduleUrl);

const sourceId = `slot-${"1".repeat(32)}`;
const targetId = `slot-${"2".repeat(32)}`;
let dispatchCount = 0;
const planning = bridge.startPlan(sourceId, targetId, null);

await Promise.resolve();
assert.equal(timers.size, 1, "the first start-plan attempt owns one deadline");
const [expiredToken, expire] = timers.entries().next().value;
timers.delete(expiredToken);
expire();

for (let turn = 0; turn < 8; turn += 1) {
  await Promise.resolve();
}
assert.equal(dispatchCount, 0, "the pre-ready expired attempt has not dispatched");
assert.equal(timers.size, 1, "the automatic replay owns a fresh deadline");

testWindow.pywebview = {
  api: {
    dispatch(requestJson) {
      dispatchCount += 1;
      const request = JSON.parse(requestJson);
      return Promise.resolve({
        schema_version: 1,
        request_id: request.request_id,
        ok: true,
        result: {
          task_id: `task-${"2".repeat(32)}`,
          request_id: "3".repeat(32),
          session_id: "4".repeat(32),
        },
      });
    },
  },
};
testWindow.emit("pywebviewready");

assert.deepEqual(await planning, {
  task_id: `task-${"2".repeat(32)}`,
  request_id: "3".repeat(32),
  session_id: "4".repeat(32),
});
assert.equal(dispatchCount, 1, "only the fresh replay may dispatch");
assert.equal(timers.size, 0, "the completed replay clears its deadline");
assert.equal(
  testWindow.listenerCount("pywebviewready"),
  1,
  "the attempt-specific reincarnation listener is removed",
);
