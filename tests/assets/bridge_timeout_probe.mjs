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
const requests = [];
let uncertainResponses = 0;
const planning = bridge.startPlan(sourceId, targetId, null);

await Promise.resolve();
assert.equal(timers.size, 1, "the first start-plan attempt owns one deadline");
const [expiredToken, expire] = timers.entries().next().value;
timers.delete(expiredToken);
expire();

for (let turn = 0; turn < 8; turn += 1) {
  await Promise.resolve();
}
assert.equal(requests.length, 0, "the pre-ready expired attempt has not dispatched");
assert.equal(timers.size, 1, "the automatic replay owns a fresh deadline");

testWindow.pywebview = {
  api: {
    dispatch(requestJson) {
      const request = JSON.parse(requestJson);
      requests.push(request);
      if (uncertainResponses > 0) {
        uncertainResponses -= 1;
        return Promise.reject(new Error("simulated uncertain delivery"));
      }
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
for (let turn = 0; turn < 4; turn += 1) {
  await Promise.resolve();
}
assert.equal(requests.length, 0, "raw injection does not admit normal commands");
bridge.markBridgeOperational();

assert.deepEqual(await planning, {
  task_id: `task-${"2".repeat(32)}`,
  request_id: "3".repeat(32),
  session_id: "4".repeat(32),
});
assert.equal(requests.length, 1, "only the fresh replay may dispatch");
assert.equal(requests[0].command, "start_plan");
assert.deepEqual(Object.keys(requests[0].payload).sort(), [
  "command_id",
  "deletion_policy",
  "source_id",
  "target_id",
]);
assert.equal("revision" in requests[0].payload, false);
assert.equal(timers.size, 0, "the completed replay clears its deadline");
assert.equal(
  testWindow.listenerCount("pywebviewready"),
  1,
  "the attempt-specific reincarnation listener is removed",
);

// A dispatched but uncertain attempt retries with a fresh transport request id
// and the identical command id and original wire intent. No revision is
// invented for this session-creating command.
uncertainResponses = 1;
const uncertainPlanning = bridge.startPlan(sourceId, targetId, "additive");
assert.deepEqual(await uncertainPlanning, {
  task_id: `task-${"2".repeat(32)}`,
  request_id: "3".repeat(32),
  session_id: "4".repeat(32),
});
assert.equal(requests.length, 3);
const uncertainAttempts = requests.slice(1);
assert.notEqual(uncertainAttempts[0].request_id, uncertainAttempts[1].request_id);
assert.equal(uncertainAttempts[0].command, "start_plan");
assert.equal(uncertainAttempts[1].command, "start_plan");
assert.deepEqual(uncertainAttempts[0].payload, uncertainAttempts[1].payload);
assert.deepEqual(Object.keys(uncertainAttempts[0].payload).sort(), [
  "command_id",
  "deletion_policy",
  "source_id",
  "target_id",
]);
assert.equal(uncertainAttempts[0].payload.source_id, sourceId);
assert.equal(uncertainAttempts[0].payload.target_id, targetId);
assert.equal(uncertainAttempts[0].payload.deletion_policy, "additive");
assert.match(uncertainAttempts[0].payload.command_id, /^[0-9a-f]{32}$/);
assert.equal("revision" in uncertainAttempts[0].payload, false);
assert.equal(timers.size, 0, "both uncertain attempts clear their deadlines");
