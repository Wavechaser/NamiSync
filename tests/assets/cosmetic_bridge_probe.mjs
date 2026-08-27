import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";


const INVALID_PAYLOAD_MESSAGE = "The desktop action contains invalid data.";
const MAX_SAFE_REVISION = Number.MAX_SAFE_INTEGER;


class TestWindow {
  constructor() {
    this.handlers = [];
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

  enqueue(handler) {
    this.handlers.push(handler);
  }

  dispatch(requestJson) {
    if (requestJson.startsWith("ack:")) {
      return Promise.resolve(true);
    }
    const request = JSON.parse(requestJson);
    this.requests.push(request);
    const handler = this.handlers.shift();
    assert.equal(typeof handler, "function", "every cosmetic request is expected");
    return Promise.resolve(handler(request)).then((response) => ({
      transport_version: 1,
      response_token: null,
      response,
    }));
  }
}


const timers = new Map();
let nextTimer = 1;
globalThis.setTimeout = (callback, milliseconds) => {
  assert.equal(milliseconds, 5000, "cosmetic commands use the local deadline");
  const token = nextTimer;
  nextTimer += 1;
  timers.set(token, callback);
  return token;
};
globalThis.clearTimeout = (token) => timers.delete(token);

let randomSeed = 0;
Object.defineProperty(globalThis, "crypto", {
  configurable: true,
  value: {
    getRandomValues(bytes) {
      randomSeed += 1;
      bytes.fill(randomSeed);
      return bytes;
    },
  },
});

const testWindow = new TestWindow();
globalThis.window = testWindow;

const modulePath = process.argv[2];
assert.ok(modulePath, "bridge module path is required");
const source = await readFile(modulePath, "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const bridge = await import(moduleUrl);

function readResult(overrides = {}) {
  return {
    section: "appearance",
    value_version: 1,
    revision: 0,
    dirty: false,
    value: { theme: "system" },
    ...overrides,
  };
}

function replaceResult(overrides = {}) {
  return {
    ...readResult(),
    disposition: "applied",
    ...overrides,
  };
}

function success(request, result) {
  return Promise.resolve({
    schema_version: 1,
    request_id: request.request_id,
    ok: true,
    result,
  });
}

function invalidPayload(request) {
  return Promise.resolve({
    schema_version: 1,
    request_id: request.request_id,
    ok: false,
    error: { code: "invalid_payload", message: INVALID_PAYLOAD_MESSAGE },
  });
}

async function flushUntil(predicate) {
  for (let turn = 0; turn < 24; turn += 1) {
    if (predicate()) {
      return;
    }
    await Promise.resolve();
  }
  assert.fail("cosmetic bridge probe did not reach the expected state");
}

function expireOnlyDeadline() {
  assert.equal(timers.size, 1, "one cosmetic attempt owns one deadline");
  const [token, expire] = timers.entries().next().value;
  timers.delete(token);
  expire();
}

// API injection alone is not operational readiness. Both cosmetic wrappers
// remain queued until the current document completes the bilateral handshake.
const preOperationalHandler = (request) => success(
  request,
  request.command === "read_cosmetic_section" ? readResult() : replaceResult(),
);
testWindow.enqueue(preOperationalHandler);
testWindow.enqueue(preOperationalHandler);
const preOperationalRead = bridge.readCosmeticSection();
const preOperationalReplace = bridge.replaceCosmeticSection(0, "system");
await flushUntil(() => timers.size === 2);
assert.equal(testWindow.requests.length, 0);
bridge.markBridgeOperational();
await flushUntil(() => testWindow.requests.length === 2);
assert.deepEqual(await preOperationalRead, readResult());
assert.deepEqual(await preOperationalReplace, replaceResult());
assert.equal(timers.size, 0);

// Reads retry exactly once after transport uncertainty with the identical wire
// intent and a fresh request identity.
testWindow.enqueue(() => Promise.reject(new Error("uncertain read delivery")));
testWindow.enqueue((request) => success(request, readResult({ revision: 2 })));
const readStart = testWindow.requests.length;
assert.deepEqual(await bridge.readCosmeticSection(17), readResult({ revision: 2 }));
const readAttempts = testWindow.requests.slice(readStart);
assert.equal(readAttempts.length, 2);
assert.notEqual(readAttempts[0].request_id, readAttempts[1].request_id);
for (const request of readAttempts) {
  assert.equal(request.command, "read_cosmetic_section");
  assert.deepEqual(request.payload, {
    section: "appearance",
    value_version: 1,
    applied_presentation_revision: 17,
  });
}
assert.deepEqual(readAttempts[0].payload, readAttempts[1].payload);
assert.equal(timers.size, 0);

// A structured command refusal is authoritative and must not replay.
testWindow.enqueue(invalidPayload);
const refusedReadStart = testWindow.requests.length;
await assert.rejects(bridge.readCosmeticSection(), {
  name: "BridgeCommandError",
  code: "invalid_payload",
});
assert.equal(testWindow.requests.length, refusedReadStart + 1);
assert.equal(timers.size, 0);

// Deadline uncertainty follows the same single-replay rule.
testWindow.enqueue(() => new Promise(() => {}));
testWindow.enqueue((request) => success(request, readResult({ dirty: true })));
const timedReadStart = testWindow.requests.length;
const timedRead = bridge.readCosmeticSection();
await flushUntil(() => testWindow.requests.length === timedReadStart + 1);
expireOnlyDeadline();
await flushUntil(() => testWindow.requests.length === timedReadStart + 2);
assert.deepEqual(await timedRead, readResult({ dirty: true }));
assert.equal(timers.size, 0);

const invalidReadResults = [
  { ...readResult(), extra: null },
  { section: "appearance", value_version: 1, revision: 0, value: { theme: "system" } },
  readResult({ section: "future" }),
  readResult({ value_version: true }),
  readResult({ value_version: 2 }),
  readResult({ revision: -1 }),
  readResult({ revision: 0.5 }),
  readResult({ revision: true }),
  readResult({ revision: MAX_SAFE_REVISION + 1 }),
  readResult({ dirty: 0 }),
  readResult({ value: null }),
  readResult({ value: {} }),
  readResult({ value: { theme: "system", extra: null } }),
  readResult({ value: { theme: "sepia" } }),
];
for (const invalidResult of invalidReadResults) {
  testWindow.enqueue((request) => success(request, invalidResult));
  testWindow.enqueue((request) => success(request, invalidResult));
  const before = testWindow.requests.length;
  await assert.rejects(bridge.readCosmeticSection(), {
    name: "BridgeTransportError",
  });
  assert.equal(testWindow.requests.length, before + 2);
  assert.equal(timers.size, 0);
}

for (const theme of ["system", "light", "dark"]) {
  const result = readResult({
    revision: MAX_SAFE_REVISION,
    dirty: true,
    value: { theme },
  });
  testWindow.enqueue((request) => success(request, result));
  assert.deepEqual(await bridge.readCosmeticSection(), result);
}

const invalidRevisions = [-1, 0.5, true, false, MAX_SAFE_REVISION + 1];
for (const revision of invalidRevisions) {
  assert.throws(
    () => bridge.replaceCosmeticSection(revision, "light"),
    /expectedRevision must be a nonnegative safe integer/,
  );
}
for (const theme of [null, "", "Light", "sepia", 1]) {
  assert.throws(
    () => bridge.replaceCosmeticSection(0, theme),
    /theme must be system, light, or dark/,
  );
}

for (const disposition of ["applied", "noop", "conflict"]) {
  const result = replaceResult({
    disposition,
    revision: MAX_SAFE_REVISION,
    dirty: true,
    value: { theme: "dark" },
  });
  testWindow.enqueue((request) => success(request, result));
  const before = testWindow.requests.length;
  assert.deepEqual(
    await bridge.replaceCosmeticSection(MAX_SAFE_REVISION, "dark"),
    result,
  );
  const [request] = testWindow.requests.slice(before);
  assert.equal(request.command, "replace_cosmetic_section");
  assert.deepEqual(request.payload, {
    section: "appearance",
    value_version: 1,
    expected_revision: MAX_SAFE_REVISION,
    value: { theme: "dark" },
  });
  assert.equal("command_id" in request.payload, false);
  assert.equal("revision" in request.payload, false);
}

const invalidReplaceResults = [
  { ...replaceResult(), extra: null },
  readResult(),
  replaceResult({ disposition: "stale" }),
  replaceResult({ revision: true }),
  replaceResult({ dirty: null }),
  replaceResult({ value: { theme: "sepia" } }),
];
for (const invalidResult of invalidReplaceResults) {
  testWindow.enqueue((request) => success(request, invalidResult));
  const before = testWindow.requests.length;
  await assert.rejects(bridge.replaceCosmeticSection(0, "system"), {
    name: "BridgeTransportError",
  });
  assert.equal(
    testWindow.requests.length,
    before + 1,
    "replacement never automatically replays an invalid response",
  );
  assert.equal(timers.size, 0);
}

testWindow.enqueue(() => Promise.reject(new Error("uncertain replacement")));
const uncertainReplaceStart = testWindow.requests.length;
await assert.rejects(bridge.replaceCosmeticSection(0, "light"), {
  name: "BridgeTransportError",
});
assert.equal(testWindow.requests.length, uncertainReplaceStart + 1);

testWindow.enqueue(() => new Promise(() => {}));
const timedReplaceStart = testWindow.requests.length;
const timedReplace = bridge.replaceCosmeticSection(0, "light");
await flushUntil(() => testWindow.requests.length === timedReplaceStart + 1);
expireOnlyDeadline();
await assert.rejects(timedReplace, { name: "BridgeTransportError" });
assert.equal(testWindow.requests.length, timedReplaceStart + 1);
assert.equal(timers.size, 0);
assert.equal(testWindow.handlers.length, 0);
