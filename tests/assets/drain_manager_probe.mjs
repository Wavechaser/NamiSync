import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";


class TestWindow {
  constructor() {
    this.listeners = new Map();
    this.pywebview = undefined;
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


function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((accept, refuse) => {
    resolve = accept;
    reject = refuse;
  });
  return { promise, resolve, reject };
}


async function turns(count = 12) {
  for (let index = 0; index < count; index += 1) {
    await Promise.resolve();
  }
}


const timers = new Map();
const scheduledDelays = [];
let nextTimer = 1;
globalThis.setTimeout = (callback, milliseconds) => {
  const token = nextTimer;
  nextTimer += 1;
  timers.set(token, callback);
  if (milliseconds !== 30000) {
    scheduledDelays.push(milliseconds);
    queueMicrotask(() => {
      if (timers.delete(token)) {
        callback();
      }
    });
  }
  return token;
};
globalThis.clearTimeout = (token) => timers.delete(token);

let nextId = 1;
Object.defineProperty(globalThis, "crypto", {
  configurable: true,
  value: {
    getRandomValues(bytes) {
      assert.ok(bytes instanceof Uint8Array);
      assert.equal(bytes.length, 16);
      bytes.fill(0);
      bytes[15] = nextId;
      nextId += 1;
      return bytes;
    },
  },
});

const testWindow = new TestWindow();
globalThis.window = testWindow;
const requests = [];
const releaseRequests = [];
const closeRequests = [];
let releaseFailuresRemaining = 0;
let closeFailuresRemaining = 0;
const releaseRefusalCodes = [];
let inspectReleaseDispatch = null;
testWindow.pywebview = {
  api: {
    dispatch(requestJson) {
      const pending = deferred();
      const request = JSON.parse(requestJson);
      const invocation = { request, ...pending };
      if (
        request.command === "release_terminal_session" ||
        request.command === "close_task"
      ) {
        assert.deepEqual(Object.keys(request.payload).sort(), [
          "session_id",
          "task_id",
        ]);
        const isRelease = request.command === "release_terminal_session";
        (isRelease ? releaseRequests : closeRequests).push(invocation);
        queueMicrotask(() => {
          if (isRelease) {
            inspectReleaseDispatch?.(request);
          }
          if (
            (isRelease && releaseFailuresRemaining > 0) ||
            (!isRelease && closeFailuresRemaining > 0)
          ) {
            if (isRelease) {
              releaseFailuresRemaining -= 1;
            } else {
              closeFailuresRemaining -= 1;
            }
            pending.reject(new Error("simulated lost lifecycle response"));
            return;
          }
          const refusalCode = isRelease ? releaseRefusalCodes.shift() : undefined;
          if (refusalCode !== undefined) {
            pending.resolve({
              schema_version: 1,
              request_id: request.request_id,
              ok: false,
              error: {
                code: refusalCode,
                message: "NamiSync is busy. Try this action again.",
              },
            });
            return;
          }
          pending.resolve({
            schema_version: 1,
            request_id: request.request_id,
            ok: true,
            result: {
              task_id: request.payload.task_id,
              session_id: request.payload.session_id,
            },
          });
        });
      } else {
        requests.push(invocation);
      }
      return pending.promise;
    },
  },
};

const modulePath = process.argv[2];
assert.ok(modulePath, "bridge module path is required");
const crossBoundaryFixtureArgument = process.argv[3];
const crossBoundaryFixture = crossBoundaryFixtureArgument === undefined
  ? null
  : JSON.parse(
    crossBoundaryFixtureArgument.trimStart().startsWith("{")
      ? crossBoundaryFixtureArgument
      : await readFile(crossBoundaryFixtureArgument, "utf8"),
  );
const source = await readFile(modulePath, "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const bridge = await import(moduleUrl);
bridge.markBridgeOperational();

function reinjectBridge() {
  testWindow.emit("pywebviewready");
  bridge.markBridgeOperational();
}

const session = (digit) => digit.repeat(32);
const task = (digit) => `task-${digit.repeat(32)}`;
const at = "2026-08-12T00:00:00Z";
const event = (sessionId, sequence, bodyType = "StateChanged", body = { state: "running" }) => ({
  update_type: "event",
  event: {
    session_id: sessionId,
    sequence,
    at,
    schema_version: 5,
    body_type: bodyType,
    body,
  },
});
const operationResult = Object.freeze({
  headline: "success",
  filesystem: "completed",
  integrity: "verified",
  recording: "ok",
  audit: "ok",
  disposition: "ran",
  canceled: false,
  phases: [],
  bytes_done: "0",
  bytes_total: "0",
  error: null,
  recording_degraded_items: 0,
  recording_issues: [],
  omitted_detail_count: 0,
  presentation_omitted_detail_count: 0,
  review_refusal: null,
});
const coreOperationResult = Object.freeze({
  status: "completed",
  recording: "ok",
  audit: "ok",
  disposition: "ran",
  canceled: false,
  phases: [],
  bytes_done: "0",
  bytes_total: "0",
  error: null,
  recording_degraded_items: 0,
  recording_issues: [],
  omitted_detail_count: 0,
  review_fact_limit: null,
});
const terminalRecord = (sessionId, result = operationResult) => ({
  update_type: "record",
  record: {
    session_id: sessionId,
    kind: "sync-plan",
    state: "completed",
    supports_pause: false,
    created_at: at,
    started_at: at,
    ended_at: at,
    result,
  },
});

function success(pending, updates) {
  const { request } = pending;
  pending.resolve({
    schema_version: 1,
    request_id: request.request_id,
    ok: true,
    result: {
      task_id: request.payload.task_id,
      session_id: request.payload.session_id,
      drain_id: request.payload.drain_id,
      updates,
    },
  });
}

function refusal(pending, code, message) {
  pending.resolve({
    schema_version: 1,
    request_id: pending.request.request_id,
    ok: false,
    error: { code, message },
  });
}

async function nextRequest(index) {
  for (let turn = 0; turn < 40 && requests.length <= index; turn += 1) {
    await turns(2);
  }
  assert.ok(requests.length > index, `request ${index} was not armed`);
  const pending = requests[index];
  assert.deepEqual(Object.keys(pending.request).sort(), [
    "command",
    "payload",
    "request_id",
    "schema_version",
  ]);
  assert.equal(pending.request.command, "next_events");
  assert.match(pending.request.request_id, /^[0-9a-f]{32}$/);
  assert.deepEqual(Object.keys(pending.request.payload).sort(), [
    "drain_id",
    "replay_from",
    "session_id",
    "task_id",
  ]);
  assert.match(pending.request.payload.drain_id, /^[0-9a-f]{32}$/);
  return pending;
}

// Numeric holes are legal, and bridge reincarnation recovers from the first
// sequence after the last accepted event. A matching leading Gap remains
// visible, permits its retained tail, and a terminal record suppresses rearm.
const acceptedOne = [];
const refusedOne = [];
const stopOne = bridge.startTaskDrain(
  task("a"),
  session("1"),
  (update) => acceptedOne.push(update),
  (error) => refusedOne.push(error),
);
const one0 = await nextRequest(0);
assert.equal(one0.request.payload.replay_from, null);
success(one0, [
  event(session("1"), 1),
  event(session("1"), 3, "Progress", {
    phase: "execute",
    items_done: 3,
    items_total: 3,
    bytes_done: "0",
    bytes_total: null,
    current_path: null,
    item_id: null,
    item_type: null,
    item_attempt_id: null,
    item_bytes_done: null,
    item_bytes_total: null,
  }),
]);
const one1 = await nextRequest(1);
assert.equal(one1.request.payload.replay_from, null);
assert.deepEqual(
  acceptedOne.map((update) => update.event.sequence),
  [1, 3],
);
testWindow.emit("pywebviewready");
await turns();
assert.equal(requests.length, 2);
bridge.markBridgeOperational();
const one2 = await nextRequest(2);
assert.equal(one2.request.payload.replay_from, 4);
success(one1, [event(session("1"), 4)]);
success(one2, [
  event(session("1"), 4, "Gap", { first_missed_seq: 4 }),
  event(session("1"), 6),
  event(session("1"), 7, "Terminal", { result: coreOperationResult }),
  terminalRecord(session("1"), null),
]);
await turns();
assert.deepEqual(
  acceptedOne.map((update) =>
    update.update_type === "event" ? update.event.body_type : "record"),
  [
    "StateChanged",
    "Progress",
    "Gap",
    "StateChanged",
    "Terminal",
    "record",
  ],
);
assert.deepEqual(
  acceptedOne
    .filter((update) => update.update_type === "event")
    .map((update) => update.event.sequence),
  [1, 3, 4, 6, 7],
);
assert.equal(refusedOne.length, 0);
const countAfterTerminal = requests.length;
await turns();
reinjectBridge();
await turns();
assert.equal(requests.length, countAfterTerminal);

// An ordinary Gap stops its batch. The matching leading recovery Gap permits
// only the later recovery tail, without treating sequence holes as loss.
const acceptedTwo = [];
const stopTwo = bridge.startTaskDrain(
  task("b"),
  session("2"),
  (update) => acceptedTwo.push(update),
  assert.fail,
);
const two0 = await nextRequest(countAfterTerminal);
success(two0, [
  event(session("2"), 10, "Gap", { first_missed_seq: 10 }),
  event(session("2"), 11),
]);
const two1 = await nextRequest(countAfterTerminal + 1);
assert.equal(two1.request.payload.replay_from, 10);
assert.deepEqual(
  acceptedTwo.map((update) => update.event.body_type),
  ["Gap"],
);
success(two1, [
  event(session("2"), 10, "Gap", { first_missed_seq: 10 }),
  event(session("2"), 12),
]);
const two2 = await nextRequest(countAfterTerminal + 2);
assert.equal(two2.request.payload.replay_from, null);
assert.deepEqual(
  acceptedTwo.map((update) => update.event.body_type),
  ["Gap", "Gap", "StateChanged"],
);
assert.deepEqual(
  acceptedTwo.map((update) => update.event.sequence),
  [10, 10, 12],
);
success(two2, [terminalRecord(session("2"))]);
await turns();
assert.deepEqual(
  acceptedTwo.map((update) =>
    update.update_type === "event" ? update.event.body_type : "record"),
  ["Gap", "Gap", "StateChanged", "record"],
);
stopTwo();

// Mismatched authority and malformed batches are rejected before any callback.
// Malformed cases include an extra union key, out-of-order event sequences,
// unknown bodies, arbitrary record results, and the exact 64-update cap.
const acceptedThree = [];
const stopThree = bridge.startTaskDrain(
  task("c"),
  session("3"),
  (update) => acceptedThree.push(update),
  assert.fail,
);
const three0 = await nextRequest(countAfterTerminal + 3);
three0.resolve({
  schema_version: 1,
  request_id: three0.request.request_id,
  ok: true,
  result: {
    task_id: task("f"),
    session_id: three0.request.payload.session_id,
    drain_id: three0.request.payload.drain_id,
    updates: [],
  },
});
const threeIdentityRecovery = await nextRequest(countAfterTerminal + 4);
assert.equal(threeIdentityRecovery.request.payload.replay_from, 1);
assert.equal(acceptedThree.length, 0);
success(threeIdentityRecovery, [
  event(session("3"), 1),
  { ...terminalRecord(session("3")), extra: true },
]);
const three1 = await nextRequest(requests.length);
assert.equal(three1.request.payload.replay_from, 1);
assert.equal(acceptedThree.length, 0);
success(three1, [event(session("3"), 10), event(session("3"), 5)]);
const three2 = await nextRequest(requests.length);
assert.equal(three2.request.payload.replay_from, 1);
assert.equal(acceptedThree.length, 0);
success(three2, [event(session("3"), 1, "UnknownBody", {})]);
const three3 = await nextRequest(requests.length);
assert.equal(three3.request.payload.replay_from, 1);
assert.equal(acceptedThree.length, 0);
success(three3, [
  {
    ...terminalRecord(session("3")),
    record: {
      ...terminalRecord(session("3")).record,
      result: { headline: "not an OperationResultView" },
    },
  },
]);
const three4 = await nextRequest(requests.length);
assert.equal(three4.request.payload.replay_from, 1);
assert.equal(acceptedThree.length, 0);
success(
  three4,
  Array.from({ length: 65 }, (_, index) =>
    event(session("3"), index + 1)),
);
const three5 = await nextRequest(requests.length);
assert.equal(three5.request.payload.replay_from, 1);
assert.equal(acceptedThree.length, 0);
stopThree();

// Session events carry the nested core event version independently of the
// bridge command/response version. Exact-shape failures leave the replay
// cursor unchanged, while the current core version is accepted.
const eventVersionSession = "98".repeat(16);
const eventVersionTask = `task-${"76".repeat(16)}`;
const acceptedEventVersions = [];
const refusedEventVersions = [];
let eventVersionRequestIndex = requests.length;
const stopEventVersions = bridge.startTaskDrain(
  eventVersionTask,
  eventVersionSession,
  (update) => acceptedEventVersions.push(update),
  (error) => refusedEventVersions.push(error),
);
const validVersionedEvent = event(eventVersionSession, 1);
const { schema_version: omittedEventVersion, ...eventWithoutVersion } =
  validVersionedEvent.event;
void omittedEventVersion;
const invalidVersionedEvents = [
  [
    "missing nested event version",
    { ...validVersionedEvent, event: eventWithoutVersion },
  ],
  [
    "legacy nested event version",
    {
      ...validVersionedEvent,
      event: { ...validVersionedEvent.event, schema_version: 3 },
    },
  ],
  [
    "extra nested event key",
    {
      ...validVersionedEvent,
      event: { ...validVersionedEvent.event, extra: null },
    },
  ],
  [
    "unsafe integer in a non-Progress live body",
    event(eventVersionSession, 1, "Gap", {
      first_missed_seq: Number.MAX_SAFE_INTEGER + 1,
    }),
  ],
  [
    "unsafe Terminal aggregate integer",
    event(eventVersionSession, 1, "Terminal", {
      result: {
        ...coreOperationResult,
        bytes_done: Number.MAX_SAFE_INTEGER + 1,
        bytes_total: Number.MAX_SAFE_INTEGER + 1,
      },
    }),
  ],
  [
    "unsafe Terminal phase integer",
    event(eventVersionSession, 1, "Terminal", {
      result: {
        ...coreOperationResult,
        phases: [{
          phase: "execute",
          status: "completed",
          items_done: 0,
          items_total: 0,
          bytes_done: Number.MAX_SAFE_INTEGER + 1,
          bytes_total: Number.MAX_SAFE_INTEGER + 1,
          error: null,
        }],
      },
    }),
  ],
];

for (const [label, invalidEvent] of invalidVersionedEvents) {
  const malformed = await nextRequest(eventVersionRequestIndex);
  eventVersionRequestIndex += 1;
  assert.equal(malformed.request.payload.replay_from, null, label);
  success(malformed, [invalidEvent]);

  const recovery = await nextRequest(eventVersionRequestIndex);
  eventVersionRequestIndex += 1;
  assert.equal(recovery.request.payload.replay_from, 1, label);
  assert.equal(acceptedEventVersions.length, 0, label);
  assert.equal(refusedEventVersions.length, 0, label);
  success(recovery, []);
  await turns();
}

const validEventVersionRequest = await nextRequest(eventVersionRequestIndex);
assert.equal(validEventVersionRequest.request.payload.replay_from, null);
success(validEventVersionRequest, [validVersionedEvent]);
await turns();
assert.equal(refusedEventVersions.length, 0);
assert.equal(acceptedEventVersions.length, 1);
assert.equal(acceptedEventVersions[0].event.schema_version, 5);
stopEventVersions();

// Progress is an exact current-source shape. Malformed item identity or byte
// telemetry invalidates the whole batch and recovers from the unchanged
// cursor. A valid populated zero-byte stream remains determinate.
const progressMatrixSession = "ab".repeat(16);
const progressMatrixTask = `task-${"cd".repeat(16)}`;
const acceptedProgressMatrix = [];
const refusedProgressMatrix = [];
let progressMatrixRequestIndex = requests.length;
const stopProgressMatrix = bridge.startTaskDrain(
  progressMatrixTask,
  progressMatrixSession,
  (update) => acceptedProgressMatrix.push(update),
  (error) => refusedProgressMatrix.push(error),
);
const validProgressBody = Object.freeze({
  phase: "execute",
  items_done: 0,
  items_total: 1,
  bytes_done: "1",
  bytes_total: "1",
  current_path: "matrix.bin",
  item_id: "56".repeat(16),
  item_type: "operation",
  item_attempt_id: "12".repeat(16),
  item_bytes_done: "1",
  item_bytes_total: "1",
});
const invalidProgressBodies = [
  [
    "legacy nine-key body",
    {
      items_done: 0,
      items_total: 1,
      bytes_done: 0,
      bytes_total: 1,
      current_path: "matrix.bin",
      item_id: "matrix-operation",
      item_type: "operation",
      item_bytes_done: 0,
      item_bytes_total: 1,
    },
  ],
  ["extra key", { ...validProgressBody, extra: null }],
  ["empty phase", { ...validProgressBody, phase: "" }],
  ["non-text phase", { ...validProgressBody, phase: 7 }],
  ["boolean items done", { ...validProgressBody, items_done: true }],
  ["fractional items done", { ...validProgressBody, items_done: 0.5 }],
  ["negative items done", { ...validProgressBody, items_done: -1 }],
  [
    "unsafe items done",
    { ...validProgressBody, items_done: Number.MAX_SAFE_INTEGER + 1 },
  ],
  ["boolean items total", { ...validProgressBody, items_total: true }],
  ["fractional items total", { ...validProgressBody, items_total: 1.5 }],
  ["negative items total", { ...validProgressBody, items_total: -1 }],
  [
    "unsafe items total",
    { ...validProgressBody, items_total: Number.MAX_SAFE_INTEGER + 1 },
  ],
  ["boolean bytes done", { ...validProgressBody, bytes_done: true }],
  ["fractional bytes done", { ...validProgressBody, bytes_done: 0.5 }],
  ["negative bytes done", { ...validProgressBody, bytes_done: -1 }],
  [
    "unsafe bytes done",
    { ...validProgressBody, bytes_done: Number.MAX_SAFE_INTEGER + 1 },
  ],
  ["boolean bytes total", { ...validProgressBody, bytes_total: true }],
  ["fractional bytes total", { ...validProgressBody, bytes_total: 1.5 }],
  ["negative bytes total", { ...validProgressBody, bytes_total: -1 }],
  [
    "unsafe bytes total",
    { ...validProgressBody, bytes_total: Number.MAX_SAFE_INTEGER + 1 },
  ],
  ["items done exceeds total", { ...validProgressBody, items_done: 2 }],
  ["bytes done exceeds total", { ...validProgressBody, bytes_done: 2 }],
  ["non-text current path", { ...validProgressBody, current_path: 7 }],
  ["item id without type", { ...validProgressBody, item_type: null }],
  ["item type without id", { ...validProgressBody, item_id: null }],
  ["empty item id", { ...validProgressBody, item_id: "" }],
  ["non-text item id", { ...validProgressBody, item_id: 7 }],
  ["unknown item type", { ...validProgressBody, item_type: "scan" }],
  [
    "active item after admission settled",
    {
      ...validProgressBody,
      items_done: 1,
    },
  ],
  [
    "attempt without identity",
    {
      ...validProgressBody,
      item_id: null,
      item_type: null,
      item_bytes_done: null,
      item_bytes_total: null,
    },
  ],
  [
    "bytes without attempt",
    { ...validProgressBody, item_attempt_id: null },
  ],
  [
    "short attempt id",
    { ...validProgressBody, item_attempt_id: "12" },
  ],
  [
    "uppercase attempt id",
    { ...validProgressBody, item_attempt_id: "AB".repeat(16) },
  ],
  [
    "non-text attempt id",
    { ...validProgressBody, item_attempt_id: 7 },
  ],
  [
    "item bytes done without total",
    { ...validProgressBody, item_bytes_total: null },
  ],
  [
    "item bytes total without done",
    { ...validProgressBody, item_bytes_done: null },
  ],
  [
    "item bytes without identity",
    {
      ...validProgressBody,
      item_id: null,
      item_type: null,
      item_attempt_id: null,
    },
  ],
  [
    "boolean item bytes done",
    { ...validProgressBody, item_bytes_done: true },
  ],
  [
    "boolean item bytes total",
    { ...validProgressBody, item_bytes_total: true },
  ],
  [
    "fractional item bytes done",
    { ...validProgressBody, item_bytes_done: 0.5 },
  ],
  [
    "fractional item bytes total",
    { ...validProgressBody, item_bytes_total: 1.5 },
  ],
  [
    "unsafe item byte counters",
    {
      ...validProgressBody,
      item_bytes_done: Number.MAX_SAFE_INTEGER + 1,
      item_bytes_total: Number.MAX_SAFE_INTEGER + 1,
    },
  ],
  [
    "negative item bytes done",
    { ...validProgressBody, item_bytes_done: -1 },
  ],
  [
    "negative item bytes total",
    { ...validProgressBody, item_bytes_total: -1 },
  ],
  [
    "item bytes done exceeds total",
    { ...validProgressBody, item_bytes_done: 2 },
  ],
  [
    "item bytes done exceeds aggregate",
    {
      ...validProgressBody,
      bytes_done: 0,
      item_bytes_done: 1,
    },
  ],
  [
    "item bytes total exceeds aggregate total",
    {
      ...validProgressBody,
      bytes_total: 0,
      item_bytes_total: 1,
    },
  ],
];

for (const [label, body] of invalidProgressBodies) {
  const malformed = await nextRequest(progressMatrixRequestIndex);
  progressMatrixRequestIndex += 1;
  assert.equal(malformed.request.payload.replay_from, null, label);
  success(malformed, [event(progressMatrixSession, 1, "Progress", body)]);

  const recovery = await nextRequest(progressMatrixRequestIndex);
  progressMatrixRequestIndex += 1;
  assert.equal(recovery.request.payload.replay_from, 1, label);
  assert.equal(acceptedProgressMatrix.length, 0, label);
  assert.equal(refusedProgressMatrix.length, 0, label);
  success(recovery, []);
  await turns();
}

const validZeroProgress = {
  ...validProgressBody,
  bytes_done: "0",
  bytes_total: "0",
  item_bytes_done: "0",
  item_bytes_total: "0",
};
const validIndeterminateProgress = {
  ...validProgressBody,
  phase: "verify",
  item_attempt_id: "34".repeat(16),
  item_bytes_done: null,
  item_bytes_total: null,
};
const validPrestreamProgress = {
  ...validProgressBody,
  phase: "baseline",
  item_attempt_id: null,
  item_bytes_done: null,
  item_bytes_total: null,
};
const progressMatrixValid = await nextRequest(progressMatrixRequestIndex);
assert.equal(progressMatrixValid.request.payload.replay_from, null);
success(progressMatrixValid, [
  event(progressMatrixSession, 1, "Progress", validZeroProgress),
  event(progressMatrixSession, 2, "PhaseChanged", { phase: "verify" }),
  event(progressMatrixSession, 3, "Progress", validIndeterminateProgress),
  event(progressMatrixSession, 4, "PhaseChanged", { phase: "baseline" }),
  event(progressMatrixSession, 5, "Progress", validPrestreamProgress),
]);
await turns();
assert.equal(refusedProgressMatrix.length, 0);
assert.equal(acceptedProgressMatrix.length, 5);
assert.deepEqual(acceptedProgressMatrix[0].event.body, validZeroProgress);
assert.deepEqual(
  acceptedProgressMatrix[2].event.body,
  validIndeterminateProgress,
);
assert.deepEqual(
  acceptedProgressMatrix[4].event.body,
  validPrestreamProgress,
);
stopProgressMatrix();

// One malformed lossy Progress invalidates reliable siblings in the same
// response before any callback or cursor movement. Replaying only the reliable
// siblings delivers each once, and bridge recovery resumes after their tail.
const progressBatchSession = "ef".repeat(16);
const progressBatchTask = `task-${"01".repeat(16)}`;
const acceptedProgressBatch = [];
const refusedProgressBatch = [];
const stopProgressBatch = bridge.startTaskDrain(
  progressBatchTask,
  progressBatchSession,
  (update) => acceptedProgressBatch.push(update),
  (error) => refusedProgressBatch.push(error),
);
const operationOutcomeBody = Object.freeze({
  item_type: "operation",
  phase: "execute",
  item_id: "56".repeat(16),
  kind: "copy",
  path: "matrix.bin",
  result: "succeeded",
  reason: null,
  detail: {},
  recording: "ok",
  recording_reason: null,
  recording_detail: null,
  detail_omitted_count: 0,
});
const malformedProgressBatch = await nextRequest(requests.length);
assert.equal(malformedProgressBatch.request.payload.replay_from, null);
success(malformedProgressBatch, [
  event(progressBatchSession, 1, "ItemOutcome", operationOutcomeBody),
  event(progressBatchSession, 2, "Progress", {
    ...validProgressBody,
    extra: null,
  }),
  event(progressBatchSession, 3, "StateChanged", { state: "running" }),
  event(progressBatchSession, 4, "Terminal", { result: coreOperationResult }),
]);

const cleanProgressBatchReplay = await nextRequest(requests.length);
assert.equal(cleanProgressBatchReplay.request.payload.replay_from, 1);
assert.equal(acceptedProgressBatch.length, 0);
assert.equal(refusedProgressBatch.length, 0);
success(cleanProgressBatchReplay, [
  event(progressBatchSession, 1, "ItemOutcome", operationOutcomeBody),
  event(progressBatchSession, 3, "StateChanged", { state: "running" }),
  event(progressBatchSession, 4, "Terminal", { result: coreOperationResult }),
]);

const progressBatchTail = await nextRequest(requests.length);
assert.equal(progressBatchTail.request.payload.replay_from, null);
assert.deepEqual(
  acceptedProgressBatch.map((update) => update.event.body_type),
  ["ItemOutcome", "StateChanged", "Terminal"],
);
assert.deepEqual(
  acceptedProgressBatch.map((update) => update.event.sequence),
  [1, 3, 4],
);
assert.equal(refusedProgressBatch.length, 0);

reinjectBridge();
const progressBatchCursorRecovery = await nextRequest(requests.length);
assert.equal(progressBatchCursorRecovery.request.payload.replay_from, 5);
success(progressBatchTail, []);
success(progressBatchCursorRecovery, [terminalRecord(progressBatchSession)]);
await turns();
assert.deepEqual(
  acceptedProgressBatch
    .filter((update) => update.update_type === "event")
    .map((update) => update.event.sequence),
  [1, 3, 4],
);
assert.equal(acceptedProgressBatch.at(-1).update_type, "record");
assert.equal(refusedProgressBatch.length, 0);
stopProgressBatch();

// The reducer preflights temporal semantics for the whole applicable batch.
// Its immutable callback view follows reliable phase authority, admits numeric
// sequence holes, permits attempt-local reset only under a fresh attempt id,
// and lets reliable outcomes and Terminal override a retained lossy snapshot.
const reducerSession = "13".repeat(16);
const reducerTask = `task-${"24".repeat(16)}`;
const acceptedReducer = [];
const refusedReducer = [];
const stopReducer = bridge.startTaskDrain(
  reducerTask,
  reducerSession,
  (update, progressState) => acceptedReducer.push({ update, progressState }),
  (error) => refusedReducer.push(error),
);
const reducerProgress = (overrides = {}) => ({
  phase: "execute",
  items_done: 1,
  items_total: 2,
  bytes_done: "2",
  bytes_total: "64",
  current_path: "first.bin",
  item_id: "67".repeat(16),
  item_type: "operation",
  item_attempt_id: "45".repeat(16),
  item_bytes_done: "2",
  item_bytes_total: "16",
  ...overrides,
});
const reducer0 = await nextRequest(requests.length);
success(reducer0, [
  event(reducerSession, 1, "PhaseChanged", { phase: "execute" }),
  event(reducerSession, 2, "Progress", reducerProgress({ items_done: 0 })),
  event(reducerSession, 3, "ItemOutcome", {
    ...operationOutcomeBody,
    item_id: "78".repeat(16),
    kind: "mkdir",
    path: "folder",
  }),
  event(reducerSession, 4, "Progress", reducerProgress({
    bytes_done: "4",
    item_bytes_done: "4",
  })),
]);
const reducer1 = await nextRequest(requests.length);
assert.equal(reducer1.request.payload.replay_from, null);
assert.deepEqual(
  acceptedReducer.map(({ update }) => update.event.sequence),
  [1, 2, 3, 4],
);
const executingState = acceptedReducer.at(-1).progressState;
assert.ok(Object.isFrozen(executingState));
assert.ok(Object.isFrozen(executingState.progress));
assert.ok(Object.isFrozen(executingState.activeItem));
assert.deepEqual(Object.keys(executingState).sort(), [
  "activeItem",
  "phase",
  "phaseAuthority",
  "progress",
]);
assert.equal(executingState.phase, "execute");
assert.equal(executingState.phaseAuthority, "phase_changed");
assert.deepEqual(executingState.activeItem, {
  item_id: "67".repeat(16),
  item_type: "operation",
  item_attempt_id: "45".repeat(16),
  item_bytes_done: "4",
  item_bytes_total: "16",
});

const invalidReducerTransitions = [
  [
    "same-attempt item regression",
    reducerProgress({ bytes_done: "4", item_bytes_done: "3" }),
  ],
  [
    "aggregate regression",
    reducerProgress({
      bytes_done: "3",
      item_bytes_done: null,
      item_bytes_total: null,
    }),
  ],
  [
    "settled item regression",
    reducerProgress({
      items_done: 0,
      bytes_done: "4",
      item_bytes_done: "4",
    }),
  ],
  [
    "fixed executor budget change",
    reducerProgress({
      bytes_done: "4",
      bytes_total: "65",
      item_bytes_done: "4",
    }),
  ],
  [
    "selected admission change",
    reducerProgress({
      items_total: 3,
      bytes_done: "4",
      item_bytes_done: "4",
    }),
  ],
  [
    "known admissions become unknown",
    reducerProgress({
      items_total: null,
      bytes_done: "4",
      bytes_total: null,
      item_bytes_done: "4",
    }),
  ],
  [
    "same-attempt item total change",
    reducerProgress({
      bytes_done: "4",
      item_bytes_done: "4",
      item_bytes_total: "17",
    }),
  ],
  [
    "uninterrupted phase disagreement",
    reducerProgress({
      phase: "verify",
      bytes_done: "4",
      item_bytes_done: "4",
    }),
  ],
];
let reducerPending = reducer1;
for (const [label, body] of invalidReducerTransitions) {
  success(reducerPending, [
    event(reducerSession, 5, "Progress", body),
    event(reducerSession, 6, "StateChanged", { state: "paused" }),
  ]);
  const recovery = await nextRequest(requests.length);
  assert.equal(recovery.request.payload.replay_from, 5, label);
  assert.equal(acceptedReducer.length, 4, label);
  assert.equal(refusedReducer.length, 0, label);
  success(recovery, []);
  reducerPending = await nextRequest(requests.length);
  assert.equal(reducerPending.request.payload.replay_from, null, label);
}

success(reducerPending, [
  event(reducerSession, 5, "Progress", reducerProgress({
    bytes_done: "4",
    item_attempt_id: "56".repeat(16),
    item_bytes_done: "0",
    item_bytes_total: "24",
  })),
  event(reducerSession, 6, "StateChanged", { state: "paused" }),
]);
const reducer2 = await nextRequest(requests.length);
assert.equal(reducer2.request.payload.replay_from, null);
const pausedState = acceptedReducer.at(-1).progressState;
assert.equal(pausedState.activeItem.item_attempt_id, "56".repeat(16));
assert.equal(pausedState.activeItem.item_bytes_done, "0");

success(reducer2, [
  event(reducerSession, 7, "Progress", reducerProgress({
    phase: "verify",
    bytes_done: "4",
    item_attempt_id: "56".repeat(16),
    item_bytes_done: "0",
    item_bytes_total: "24",
  })),
  event(reducerSession, 8, "ItemOutcome", operationOutcomeBody),
]);
const reducerPhaseRecovery = await nextRequest(requests.length);
assert.equal(reducerPhaseRecovery.request.payload.replay_from, 7);
assert.equal(acceptedReducer.length, 6);
success(reducerPhaseRecovery, [
  event(reducerSession, 7, "ItemOutcome", {
    ...operationOutcomeBody,
    item_id: "67".repeat(16),
    path: "first.bin",
  }),
]);
const reducer3 = await nextRequest(requests.length);
assert.equal(reducer3.request.payload.replay_from, null);
assert.equal(acceptedReducer.at(-1).progressState.activeItem, null);
assert.notEqual(acceptedReducer.at(-1).progressState.progress, null);

const postCopyOutcomeBody = Object.freeze({
  item_type: "integrity",
  phase: "verify",
  item_id: "89".repeat(16),
  row_id: null,
  location_id: null,
  kind: "integrity",
  path: "second.bin",
  result: "verified",
  reason: null,
  detail: null,
  read_strategy: "windows-unbuffered",
  recording: "ok",
  record_disposition: null,
  detail_omitted_count: 0,
});
success(reducer3, [
  event(reducerSession, 8, "PhaseChanged", { phase: "verify" }),
  event(reducerSession, 9, "Progress", reducerProgress({
    phase: "verify",
    items_done: 0,
    items_total: 1,
    bytes_done: "3",
    bytes_total: "8",
    current_path: "second.bin",
    item_id: "89".repeat(16),
    item_attempt_id: "67".repeat(16),
    item_bytes_done: "3",
    item_bytes_total: "8",
  })),
  event(reducerSession, 10, "Progress", reducerProgress({
    phase: "verify",
    items_done: 0,
    items_total: 1,
    bytes_done: "9",
    bytes_total: "10",
    current_path: "second.bin",
    item_id: "89".repeat(16),
    item_attempt_id: "67".repeat(16),
    item_bytes_done: null,
    item_bytes_total: null,
  })),
]);
const reducer4 = await nextRequest(requests.length);
assert.equal(reducer4.request.payload.replay_from, null);
assert.equal(acceptedReducer.at(-1).progressState.phase, "verify");
assert.equal(
  acceptedReducer.at(-1).progressState.activeItem.item_attempt_id,
  "67".repeat(16),
);
assert.equal(
  acceptedReducer.at(-1).progressState.activeItem.item_bytes_done,
  null,
);

success(reducer4, [
  event(reducerSession, 11, "Progress", reducerProgress({
    phase: "verify",
    items_done: 0,
    items_total: 1,
    bytes_done: "9",
    bytes_total: "10",
    current_path: "second.bin",
    item_id: "89".repeat(16),
    item_attempt_id: "67".repeat(16),
    item_bytes_done: "8",
    item_bytes_total: "8",
  })),
  event(reducerSession, 12, "IntegrityOutcome", postCopyOutcomeBody),
]);
const reducerOvershootRecovery = await nextRequest(requests.length);
assert.equal(reducerOvershootRecovery.request.payload.replay_from, 11);
const countBeforeOvershootRecovery = acceptedReducer.length;
const overshootRecoveryUpdates = [
  event(reducerSession, 11, "IntegrityOutcome", postCopyOutcomeBody),
  event(reducerSession, 12, "Terminal", { result: coreOperationResult }),
  terminalRecord(reducerSession),
];
for (const update of overshootRecoveryUpdates.filter(
  (candidate) => candidate.update_type === "event",
)) {
  assert.equal(
    bridge.validateDormantSessionEventV5(update.event, reducerSession),
    true,
    update.event.body_type,
  );
}
success(reducerOvershootRecovery, overshootRecoveryUpdates);
await turns();
assert.equal(acceptedReducer.length, countBeforeOvershootRecovery + 3);
const postCopyOutcomeState = acceptedReducer.at(-3).progressState;
assert.equal(postCopyOutcomeState.phase, "verify");
assert.equal(postCopyOutcomeState.activeItem, null);
assert.notEqual(postCopyOutcomeState.progress, null);
for (const { progressState } of acceptedReducer.slice(-2)) {
  assert.deepEqual(progressState, {
    phase: null,
    phaseAuthority: "unknown",
    progress: null,
    activeItem: null,
  });
}
assert.equal(refusedReducer.length, 0);
stopReducer();

// Lossy snapshots may skip an inactive handoff. A newer snapshot can therefore
// repoint the current-item spotlight without asserting that the old item
// settled. Attempt tokens remain item-bound, and reliable settlement still
// prevents immediate reactivation of the settled identity.
const handoffSession = "8a".repeat(16);
const handoffTask = `task-${"6b".repeat(16)}`;
const acceptedHandoff = [];
const refusedHandoff = [];
const stopHandoff = bridge.startTaskDrain(
  handoffTask,
  handoffSession,
  (update, progressState) => acceptedHandoff.push({ update, progressState }),
  (error) => refusedHandoff.push(error),
);
const handoffProgress = (itemId, attemptId, overrides = {}) => ({
  phase: "execute",
  items_done: 0,
  items_total: 3,
  bytes_done: "2",
  bytes_total: "24",
  current_path: `${itemId}.bin`,
  item_id: itemId,
  item_type: "operation",
  item_attempt_id: attemptId,
  item_bytes_done: "0",
  item_bytes_total: "8",
  ...overrides,
});
const handoff0 = await nextRequest(requests.length);
success(handoff0, [
  event(handoffSession, 1, "PhaseChanged", { phase: "execute" }),
  event(handoffSession, 2, "Progress", handoffProgress(
    "a1".repeat(16),
    "71".repeat(16),
    { item_bytes_done: "2" },
  )),
  event(handoffSession, 3, "Progress", handoffProgress(
    "a2".repeat(16),
    "72".repeat(16),
  )),
]);
const handoff1 = await nextRequest(requests.length);
assert.equal(handoff1.request.payload.replay_from, null);
assert.deepEqual(
  acceptedHandoff
    .map(({ progressState }) => progressState.activeItem?.item_id ?? null)
    .filter((itemId) => itemId !== null),
  ["a1".repeat(16), "a2".repeat(16)],
);
assert.equal(
  acceptedHandoff.at(-1).progressState.activeItem.item_id,
  "a2".repeat(16),
);

// Reusing B's non-null attempt token for C invalidates the whole batch. A
// replay with C's own token then applies both the lossy and reliable siblings.
success(handoff1, [
  event(handoffSession, 4, "Progress", handoffProgress(
    "a3".repeat(16),
    "72".repeat(16),
  )),
  event(handoffSession, 5, "StateChanged", { state: "paused" }),
]);
const handoffTokenRecovery = await nextRequest(requests.length);
assert.equal(handoffTokenRecovery.request.payload.replay_from, 4);
assert.equal(acceptedHandoff.length, 3);
assert.equal(refusedHandoff.length, 0);
success(handoffTokenRecovery, [
  event(handoffSession, 4, "Progress", handoffProgress(
    "a3".repeat(16),
    "73".repeat(16),
  )),
  event(handoffSession, 5, "StateChanged", { state: "paused" }),
]);
const handoff2 = await nextRequest(requests.length);
assert.equal(handoff2.request.payload.replay_from, null);
assert.equal(
  acceptedHandoff.at(-1).progressState.activeItem.item_id,
  "a3".repeat(16),
);

const operationCOutcome = {
  ...operationOutcomeBody,
  item_id: "a3".repeat(16),
  path: "operation-c.bin",
};
success(handoff2, [
  event(handoffSession, 6, "ItemOutcome", operationCOutcome),
  event(handoffSession, 7, "Progress", handoffProgress(
    "a3".repeat(16),
    "74".repeat(16),
    { items_done: 1 },
  )),
]);
const handoffReactivationRecovery = await nextRequest(requests.length);
assert.equal(handoffReactivationRecovery.request.payload.replay_from, 6);
assert.equal(acceptedHandoff.length, 5);
assert.equal(refusedHandoff.length, 0);
success(handoffReactivationRecovery, [
  event(handoffSession, 6, "ItemOutcome", operationCOutcome),
]);
await turns();
assert.equal(acceptedHandoff.at(-1).update.event.body_type, "ItemOutcome");
assert.equal(acceptedHandoff.at(-1).progressState.activeItem, null);
assert.equal(refusedHandoff.length, 0);
stopHandoff();

// The optional fixture carries real Python producer output through this same
// packaged reducer. It is omitted for the standalone JavaScript matrix.
if (crossBoundaryFixture !== null) {
  assert.equal(typeof crossBoundaryFixture, "object");
  assert.equal(typeof crossBoundaryFixture.task_id, "string");
  assert.equal(typeof crossBoundaryFixture.session_id, "string");
  assert.ok(Array.isArray(crossBoundaryFixture.batches));
  assert.ok(Array.isArray(crossBoundaryFixture.expected_active_ids));
  const acceptedCrossBoundary = [];
  const refusedCrossBoundary = [];
  const crossBoundaryRequestStart = requests.length;
  const stopCrossBoundary = bridge.startTaskDrain(
    crossBoundaryFixture.task_id,
    crossBoundaryFixture.session_id,
    (update, progressState) => {
      acceptedCrossBoundary.push({ update, progressState });
    },
    (error) => refusedCrossBoundary.push(error),
  );
  for (let index = 0; index < crossBoundaryFixture.batches.length; index += 1) {
    const pending = await nextRequest(crossBoundaryRequestStart + index);
    assert.equal(
      pending.request.payload.task_id,
      crossBoundaryFixture.task_id,
    );
    assert.equal(
      pending.request.payload.session_id,
      crossBoundaryFixture.session_id,
    );
    assert.equal(pending.request.payload.replay_from, null);
    assert.match(pending.request.payload.drain_id, /^[0-9a-f]{32}$/);
    success(pending, crossBoundaryFixture.batches[index]);
    await turns();
    assert.equal(refusedCrossBoundary.length, 0);
  }
  const acceptedSequences = acceptedCrossBoundary
    .filter(({ update }) => update.update_type === "event")
    .map(({ update }) => update.event.sequence);
  for (let index = 1; index < acceptedSequences.length; index += 1) {
    assert.ok(acceptedSequences[index] > acceptedSequences[index - 1]);
  }
  const distinctActiveIds = [];
  for (const { progressState } of acceptedCrossBoundary) {
    const itemId = progressState.activeItem?.item_id ?? null;
    if (
      itemId !== null &&
      distinctActiveIds.at(-1) !== itemId
    ) {
      distinctActiveIds.push(itemId);
    }
  }
  assert.deepEqual(
    distinctActiveIds,
    crossBoundaryFixture.expected_active_ids,
  );
  if (crossBoundaryFixture.expected_outcome_ids !== undefined) {
    assert.deepEqual(
      acceptedCrossBoundary
        .filter(({ update }) => (
          update.update_type === "event" &&
          update.event.body_type.endsWith("Outcome")
        ))
        .map(({ update }) => update.event.body.item_id),
      crossBoundaryFixture.expected_outcome_ids,
    );
  }
  if (crossBoundaryFixture.expect_final_inactive === true) {
    assert.equal(acceptedCrossBoundary.at(-1).progressState.activeItem, null);
  }
  stopCrossBoundary();
}

// Gap discards the pre-gap reducer domain. A matching recovery Gap can then
// deliver self-described Progress even when the reliable PhaseChanged was
// lost; current_path remains informational and cannot synthesize activity.
const gapProgressSession = "35".repeat(16);
const gapProgressTask = `task-${"46".repeat(16)}`;
const acceptedGapProgress = [];
const stopGapProgress = bridge.startTaskDrain(
  gapProgressTask,
  gapProgressSession,
  (update, progressState) => acceptedGapProgress.push({ update, progressState }),
  assert.fail,
);
const gapProgress0 = await nextRequest(requests.length);
success(gapProgress0, [
  event(gapProgressSession, 1, "PhaseChanged", { phase: "baseline" }),
  event(gapProgressSession, 2, "Progress", {
    ...validProgressBody,
    phase: "baseline",
    item_id: "integrity-one",
    item_type: "integrity",
  }),
]);
const gapProgress1 = await nextRequest(requests.length);
success(gapProgress1, [
  event(gapProgressSession, 3, "Gap", { first_missed_seq: 3 }),
  event(gapProgressSession, 4, "StateChanged", { state: "running" }),
]);
const gapProgressRecovery = await nextRequest(requests.length);
assert.equal(gapProgressRecovery.request.payload.replay_from, 3);
assert.equal(acceptedGapProgress.at(-1).update.event.body_type, "Gap");
assert.deepEqual(acceptedGapProgress.at(-1).progressState, {
  phase: null,
  phaseAuthority: "unknown",
  progress: null,
  activeItem: null,
});
success(gapProgressRecovery, [
  event(gapProgressSession, 3, "Gap", { first_missed_seq: 3 }),
  event(gapProgressSession, 5, "Progress", {
    ...validProgressBody,
    phase: "baseline",
    bytes_done: "3",
    bytes_total: "3",
    current_path: "recovered.bin",
    item_id: null,
    item_type: null,
    item_attempt_id: null,
    item_bytes_done: null,
    item_bytes_total: null,
  }),
  event(gapProgressSession, 6, "Progress", {
    ...validProgressBody,
    phase: "verify",
    bytes_done: "2",
    bytes_total: "4",
    current_path: "newer-phase.bin",
    item_id: null,
    item_type: null,
    item_attempt_id: null,
    item_bytes_done: null,
    item_bytes_total: null,
  }),
]);
const gapProgress2 = await nextRequest(requests.length);
const recoveredBaselineState = acceptedGapProgress.at(-2).progressState;
assert.equal(recoveredBaselineState.phase, "baseline");
assert.equal(recoveredBaselineState.phaseAuthority, "progress");
assert.equal(recoveredBaselineState.progress.current_path, "recovered.bin");
const recoveredProgressState = acceptedGapProgress.at(-1).progressState;
assert.equal(acceptedGapProgress.at(-1).update.event.body.phase, "verify");
assert.equal(recoveredProgressState.phase, "verify");
assert.equal(recoveredProgressState.phaseAuthority, "progress");
assert.equal(recoveredProgressState.progress.bytes_done, "2");
assert.equal(recoveredProgressState.progress.bytes_total, "4");
assert.equal(recoveredProgressState.progress.current_path, "newer-phase.bin");
assert.equal(recoveredProgressState.activeItem, null);
const acceptedBeforeGapRegression = acceptedGapProgress.length;
success(gapProgress2, [
  event(gapProgressSession, 7, "StateChanged", { state: "paused" }),
  event(gapProgressSession, 8, "Progress", {
    ...validProgressBody,
    phase: "verify",
    bytes_done: "1",
    bytes_total: "4",
    item_id: null,
    item_type: null,
    item_attempt_id: null,
    item_bytes_done: null,
    item_bytes_total: null,
  }),
]);
const gapProgressRegressionRecovery = await nextRequest(requests.length);
assert.equal(gapProgressRegressionRecovery.request.payload.replay_from, 7);
assert.equal(acceptedGapProgress.length, acceptedBeforeGapRegression);
success(gapProgressRegressionRecovery, [
  event(gapProgressSession, 7, "StateChanged", { state: "paused" }),
  event(gapProgressSession, 8, "Progress", {
    ...validProgressBody,
    phase: "verify",
    bytes_done: "3",
    bytes_total: "4",
    item_id: null,
    item_type: null,
    item_attempt_id: null,
    item_bytes_done: null,
    item_bytes_total: null,
  }),
]);
const gapProgress3 = await nextRequest(requests.length);
assert.equal(gapProgress3.request.payload.replay_from, null);
assert.deepEqual(
  acceptedGapProgress
    .slice(acceptedBeforeGapRegression)
    .map(({ update }) => update.event.sequence),
  [7, 8],
);
assert.equal(acceptedGapProgress.at(-1).progressState.progress.bytes_done, "3");
success(gapProgress3, [terminalRecord(gapProgressSession)]);
await turns();
assert.equal(acceptedGapProgress.at(-1).update.update_type, "record");
assert.equal(acceptedGapProgress.at(-1).progressState.phase, null);
stopGapProgress();

// Unknown aggregate admissions may become known once and an authoritative
// inactive snapshot may clear activity without an ItemOutcome at an exceptional
// reporter boundary. Later known admissions remain subject to temporal guards.
const inactiveSession = "79".repeat(16);
const inactiveTask = `task-${"8a".repeat(16)}`;
const acceptedInactive = [];
const stopInactive = bridge.startTaskDrain(
  inactiveTask,
  inactiveSession,
  (update, progressState) => acceptedInactive.push({ update, progressState }),
  assert.fail,
);
const inactive0 = await nextRequest(requests.length);
success(inactive0, [
  event(inactiveSession, 1, "PhaseChanged", { phase: "verify" }),
  event(inactiveSession, 2, "Progress", {
    ...validProgressBody,
    phase: "verify",
    items_total: null,
    bytes_done: "2",
    bytes_total: null,
    item_id: "b1".repeat(16),
    item_type: "integrity",
    item_bytes_done: "2",
    item_bytes_total: "8",
  }),
  event(inactiveSession, 3, "Progress", {
    ...validProgressBody,
    phase: "verify",
    items_total: 1,
    bytes_done: "2",
    bytes_total: "8",
    current_path: null,
    item_id: null,
    item_type: null,
    item_attempt_id: null,
    item_bytes_done: null,
    item_bytes_total: null,
  }),
]);
const inactive1 = await nextRequest(requests.length);
assert.equal(acceptedInactive.length, 3);
assert.equal(acceptedInactive.at(-1).progressState.progress.items_total, 1);
assert.equal(acceptedInactive.at(-1).progressState.progress.bytes_total, "8");
assert.equal(acceptedInactive.at(-1).progressState.activeItem, null);
success(inactive1, [terminalRecord(inactiveSession)]);
await turns();
stopInactive();

// Repeating reliable authority for the same phase does not reset its temporal
// domain. The whole batch is refused when a following snapshot tries to use
// that repeated PhaseChanged as permission to regress aggregate work.
const samePhaseSession = "57".repeat(16);
const samePhaseTask = `task-${"68".repeat(16)}`;
const acceptedSamePhase = [];
const stopSamePhase = bridge.startTaskDrain(
  samePhaseTask,
  samePhaseSession,
  (update, progressState) => acceptedSamePhase.push({ update, progressState }),
  assert.fail,
);
const samePhase0 = await nextRequest(requests.length);
success(samePhase0, [
  event(samePhaseSession, 1, "PhaseChanged", { phase: "execute" }),
  event(samePhaseSession, 2, "Progress", reducerProgress({
    items_done: 0,
    bytes_done: "4",
    item_bytes_done: "4",
  })),
]);
const samePhase1 = await nextRequest(requests.length);
success(samePhase1, [
  event(samePhaseSession, 3, "PhaseChanged", { phase: "execute" }),
  event(samePhaseSession, 4, "Progress", reducerProgress({
    items_done: 0,
    bytes_done: "3",
    item_bytes_done: "3",
  })),
]);
const samePhaseRecovery = await nextRequest(requests.length);
assert.equal(samePhaseRecovery.request.payload.replay_from, 3);
assert.equal(acceptedSamePhase.length, 2);
success(samePhaseRecovery, [
  event(samePhaseSession, 3, "PhaseChanged", { phase: "execute" }),
  event(samePhaseSession, 4, "Progress", reducerProgress({
    items_done: 0,
    bytes_done: "5",
    item_bytes_done: "5",
  })),
]);
const samePhase2 = await nextRequest(requests.length);
assert.equal(acceptedSamePhase.length, 4);
assert.equal(acceptedSamePhase.at(-1).progressState.progress.bytes_done, "5");
assert.equal(acceptedSamePhase.at(-1).progressState.phaseAuthority, "phase_changed");
success(samePhase2, [terminalRecord(samePhaseSession)]);
await turns();
stopSamePhase();

// Bridge reincarnation changes transport custody but does not reset reducer
// comparisons. The stale response is ignored, and the same regression from the
// current recovery attempt is refused without moving its replay cursor.
const reducerReincarnationSession = "9b".repeat(16);
const reducerReincarnationTask = `task-${"ac".repeat(16)}`;
const acceptedReducerReincarnation = [];
const stopReducerReincarnation = bridge.startTaskDrain(
  reducerReincarnationTask,
  reducerReincarnationSession,
  (update, progressState) => {
    acceptedReducerReincarnation.push({ update, progressState });
  },
  assert.fail,
);
const reducerReincarnation0 = await nextRequest(requests.length);
success(reducerReincarnation0, [
  event(reducerReincarnationSession, 1, "PhaseChanged", { phase: "execute" }),
  event(reducerReincarnationSession, 2, "Progress", reducerProgress({
    items_done: 0,
    bytes_done: "4",
    item_bytes_done: "4",
  })),
]);
const staleReducerReincarnation = await nextRequest(requests.length);
reinjectBridge();
const currentReducerReincarnation = await nextRequest(requests.length);
assert.equal(currentReducerReincarnation.request.payload.replay_from, 3);
const regressingReincarnationProgress = event(
  reducerReincarnationSession,
  3,
  "Progress",
  reducerProgress({
    items_done: 0,
    bytes_done: "3",
    item_bytes_done: null,
    item_bytes_total: null,
  }),
);
success(staleReducerReincarnation, [regressingReincarnationProgress]);
success(currentReducerReincarnation, [regressingReincarnationProgress]);
const reducerReincarnationRecovery = await nextRequest(requests.length);
assert.equal(reducerReincarnationRecovery.request.payload.replay_from, 3);
assert.equal(acceptedReducerReincarnation.length, 2);
assert.equal(
  acceptedReducerReincarnation.at(-1).progressState.progress.bytes_done,
  "4",
);
success(reducerReincarnationRecovery, [
  event(reducerReincarnationSession, 3, "Progress", reducerProgress({
    items_done: 0,
    bytes_done: "5",
    item_bytes_done: "5",
  })),
]);
const reducerReincarnationTail = await nextRequest(requests.length);
assert.equal(
  acceptedReducerReincarnation.at(-1).progressState.progress.bytes_done,
  "5",
);
success(reducerReincarnationTail, [
  terminalRecord(reducerReincarnationSession),
]);
await turns();
stopReducerReincarnation();

// Bridge reincarnation resets the one drain-busy convergence allowance. A busy
// reply from the freshly abandoned call therefore cannot prematurely stop the
// current generation.
const busyRefusals = [];
const stopFour = bridge.startTaskDrain(
  task("d"),
  session("4"),
  () => {},
  (error) => busyRefusals.push(error),
);
const four0 = await nextRequest(requests.length);
refusal(
  four0,
  "drain_busy",
  "That desktop task already has an event request in progress.",
);
const four1 = await nextRequest(requests.length);
reinjectBridge();
const four2 = await nextRequest(requests.length);
refusal(
  four1,
  "drain_busy",
  "That desktop task already has an event request in progress.",
);
refusal(
  four2,
  "drain_busy",
  "That desktop task already has an event request in progress.",
);
const four3 = await nextRequest(requests.length);
success(four3, [terminalRecord(session("4"))]);
await turns();
assert.deepEqual(
  busyRefusals.map((error) => [error.name, error.code, error.message]),
  [],
);

// A second busy result in one uninterrupted generation is definitive and the
// stopped entry is removed so an explicit later observation can be created.
const definitiveBusyRefusals = [];
const stopDefinitiveBusy = bridge.startTaskDrain(
  task("8"),
  session("8"),
  assert.fail,
  (error) => definitiveBusyRefusals.push(error),
);
const busy0 = await nextRequest(requests.length);
refusal(
  busy0,
  "drain_busy",
  "That desktop task already has an event request in progress.",
);
const busy1 = await nextRequest(requests.length);
refusal(
  busy1,
  "drain_busy",
  "That desktop task already has an event request in progress.",
);
await turns();
assert.equal(definitiveBusyRefusals.length, 1);
assert.equal(definitiveBusyRefusals[0].code, "drain_busy");
const stopFourReplacement = bridge.startTaskDrain(
  task("8"),
  session("8"),
  assert.fail,
  assert.fail,
);
await nextRequest(requests.length);
stopFourReplacement();
stopDefinitiveBusy();

// Repeated readiness while one call is outstanding invalidates it but coalesces
// into one current recovery arm. A terminal record lost with the stale response
// is reconciled by the current recovery response and then suppresses rearm.
const acceptedFive = [];
const stopFive = bridge.startTaskDrain(
  task("e"),
  session("5"),
  (update) => acceptedFive.push(update),
  assert.fail,
);
const fiveIndex = requests.length;
const five0 = await nextRequest(fiveIndex);
testWindow.emit("pywebviewready");
testWindow.emit("pywebviewready");
await turns();
assert.equal(requests.length, fiveIndex + 1);
bridge.markBridgeOperational();
const five1 = await nextRequest(fiveIndex + 1);
await turns();
assert.equal(requests.length, fiveIndex + 2);
assert.equal(five1.request.payload.replay_from, 1);
success(five0, [terminalRecord(session("5"))]);
await turns();
assert.equal(acceptedFive.length, 0);
success(five1, [terminalRecord(session("5"), null)]);
await turns();
assert.equal(acceptedFive.length, 1);
assert.equal(acceptedFive[0].update_type, "record");
const countAfterRecoveredTerminal = requests.length;
reinjectBridge();
await turns();
assert.equal(requests.length, countAfterRecoveredTerminal);

// A stale nonterminal reliable response is not applied. Recovery may return
// that retained event without a Gap, and it is then delivered exactly once.
const acceptedReliable = [];
const stopReliable = bridge.startTaskDrain(
  task("9"),
  session("9"),
  (update) => acceptedReliable.push(update),
  assert.fail,
);
const reliable0 = await nextRequest(requests.length);
reinjectBridge();
const reliable1 = await nextRequest(requests.length);
success(reliable0, [event(session("9"), 1, "PhaseChanged", { phase: "scan" })]);
await turns();
assert.equal(acceptedReliable.length, 0);
success(reliable1, [
  event(session("9"), 1, "PhaseChanged", { phase: "scan" }),
  terminalRecord(session("9")),
]);
await turns();
assert.deepEqual(
  acceptedReliable.map((update) =>
    update.update_type === "event" ? update.event.body_type : "record"),
  ["PhaseChanged", "record"],
);

// Cursor acceptance precedes presentation. If a callback synchronously
// observes bridge reincarnation, recovery starts at sequence+1 and the stale
// tail from that just-invalidated batch cannot render.
const acceptedCursor = [];
const stopCursor = bridge.startTaskDrain(
  task("0"),
  session("0"),
  (update) => {
    acceptedCursor.push(update);
    if (acceptedCursor.length === 1) {
      reinjectBridge();
    }
  },
  assert.fail,
);
const cursor0 = await nextRequest(requests.length);
success(cursor0, [event(session("0"), 1), event(session("0"), 2)]);
const cursor1 = await nextRequest(requests.length);
assert.equal(cursor1.request.payload.replay_from, 2);
assert.deepEqual(
  acceptedCursor.map((update) => update.event.sequence),
  [1],
);
success(cursor1, [terminalRecord(session("0"))]);
await turns();
assert.equal(acceptedCursor.length, 2);

// Consumer failure stops before it can rearm and reports one bounded local
// transport refusal. Duplicate task registration is refused synchronously.
const callbackRefusals = [];
const stopSix = bridge.startTaskDrain(
  task("f"),
  session("6"),
  () => {
    throw new Error("private consumer detail");
  },
  (error) => callbackRefusals.push(error),
);
assert.throws(
  () => bridge.startTaskDrain(task("f"), session("6"), () => {}, () => {}),
  TypeError,
);
const six0 = await nextRequest(requests.length);
success(six0, [event(session("6"), 1)]);
await turns();
assert.equal(callbackRefusals.length, 1);
assert.equal(callbackRefusals[0].name, "BridgeTransportError");
assert.ok(!callbackRefusals[0].message.includes("private"));

// Failure while minting an attempt id is surfaced once from the queued arm,
// does not become an unhandled rejection, and releases the task-map entry.
const originalGetRandomValues = globalThis.crypto.getRandomValues;
const mintRefusals = [];
globalThis.crypto.getRandomValues = () => {
  throw new Error("simulated unavailable cryptography");
};
const stopSeven = bridge.startTaskDrain(
  task("7"),
  session("7"),
  assert.fail,
  (error) => mintRefusals.push(error),
);
await turns();
assert.equal(mintRefusals.length, 1);
assert.equal(mintRefusals[0].name, "BridgeTransportError");
assert.equal(
  mintRefusals[0].message,
  "The desktop request id could not be created.",
);
globalThis.crypto.getRandomValues = originalGetRandomValues;
const stopSevenReplacement = bridge.startTaskDrain(
  task("7"),
  session("7"),
  assert.fail,
  assert.fail,
);
await nextRequest(requests.length);
stopSevenReplacement();

// A terminal callback failure retains the validated record and task authority,
// mutates no native lifetime, and its retry presents the same record before one
// terminal-session release. Automatic terminal cleanup never closes the task.
const terminalCallbackAttempts = [];
const terminalCallbackProgressStates = [];
const terminalCallbackRefusals = [];
const terminalCallbackReleaseStart = releaseRequests.length;
const terminalCallbackCloseStart = closeRequests.length;
const terminalCallbackDrainStart = requests.length;
const stopTerminalCallback = bridge.startTaskDrain(
  task("3"),
  session("c"),
  (update, progressState) => {
    terminalCallbackAttempts.push(update);
    terminalCallbackProgressStates.push(progressState);
    if (terminalCallbackAttempts.length === 1) {
      update.record.state = "failed";
      throw new Error("private terminal renderer detail");
    }
  },
  (error) => terminalCallbackRefusals.push(error),
);
const terminalCallback0 = await nextRequest(terminalCallbackDrainStart);
success(terminalCallback0, [terminalRecord(session("c"))]);
await turns();
assert.equal(terminalCallbackAttempts.length, 1);
assert.equal(terminalCallbackRefusals.length, 1);
assert.equal(terminalCallbackRefusals[0].name, "TerminalPresentationError");
assert.equal(typeof terminalCallbackRefusals[0].retry, "function");
assert.ok(!terminalCallbackRefusals[0].message.includes("private"));
assert.equal(releaseRequests.length, terminalCallbackReleaseStart);
assert.equal(closeRequests.length, terminalCallbackCloseStart);
terminalCallbackRefusals[0].retry();
await turns(20);
assert.equal(terminalCallbackAttempts.length, 2);
assert.equal(terminalCallbackProgressStates.length, 2);
for (const progressState of terminalCallbackProgressStates) {
  assert.ok(Object.isFrozen(progressState));
  assert.deepEqual(progressState, {
    phase: null,
    phaseAuthority: "unknown",
    progress: null,
    activeItem: null,
  });
}
assert.notEqual(terminalCallbackAttempts[0], terminalCallbackAttempts[1]);
assert.equal(terminalCallbackAttempts[0].record.state, "failed");
assert.equal(terminalCallbackAttempts[1].record.state, "completed");
assert.equal(releaseRequests.length, terminalCallbackReleaseStart + 1);
assert.equal(closeRequests.length, terminalCallbackCloseStart);
stopTerminalCallback();
assert.throws(
  () => bridge.startTaskDrain(task("3"), session("c"), assert.fail, assert.fail),
  TypeError,
);

// A terminal record is presented before session release begins. A lost release
// response retries the same task/session authority; confirmed release retains
// the browser entry, and only explicit close removes it.
const acceptedRelease = [];
const releaseRefusals = [];
const releaseCountBefore = releaseRequests.length;
const closeCountBeforeRelease = closeRequests.length;
const releaseDelayIndex = scheduledDelays.length;
releaseFailuresRemaining = 1;
inspectReleaseDispatch = (request) => {
  assert.equal(acceptedRelease.at(-1)?.update_type, "record");
  assert.equal(request.payload.task_id, task("1"));
  assert.equal(request.payload.session_id, session("a"));
};
const releaseDrainIndex = requests.length;
const stopRelease = bridge.startTaskDrain(
  task("1"),
  session("a"),
  (update) => acceptedRelease.push(update),
  (error) => releaseRefusals.push(error),
);
const release0 = await nextRequest(releaseDrainIndex);
success(release0, [terminalRecord(session("a"))]);
await turns(30);
inspectReleaseDispatch = null;
assert.equal(releaseRequests.length, releaseCountBefore + 2);
assert.deepEqual(
  releaseRequests.slice(releaseCountBefore).map((item) => item.request.payload),
  [
    { task_id: task("1"), session_id: session("a") },
    { task_id: task("1"), session_id: session("a") },
  ],
);
assert.deepEqual(scheduledDelays.slice(releaseDelayIndex), [100]);
assert.equal(releaseRefusals.length, 0);
assert.equal(closeRequests.length, closeCountBeforeRelease);
const closeDelayIndex = scheduledDelays.length;
closeFailuresRemaining = 1;
const closedReleaseTask = await bridge.closeTask(task("1"), session("a"));
assert.deepEqual(closedReleaseTask, {
  task_id: task("1"),
  session_id: session("a"),
});
assert.equal(closeRequests.length, closeCountBeforeRelease + 2);
assert.deepEqual(scheduledDelays.slice(closeDelayIndex), [100]);
assert.deepEqual(
  closeRequests.slice(closeCountBeforeRelease).map((item) => item.request.payload),
  [
    { task_id: task("1"), session_id: session("a") },
    { task_id: task("1"), session_id: session("a") },
  ],
);
const stopReleaseReplacement = bridge.startTaskDrain(
  task("1"),
  session("a"),
  assert.fail,
  assert.fail,
);
await nextRequest(requests.length);
stopReleaseReplacement();

// Native admission saturation is uncertain for both drain consumption and
// terminal cleanup. Both paths back off and preserve their exact authority.
const saturationRefusals = [];
const saturationDelayIndex = scheduledDelays.length;
const saturationRequestIndex = requests.length;
const releaseCountBeforeSaturation = releaseRequests.length;
releaseRefusalCodes.push("bridge_busy");
const stopSaturation = bridge.startTaskDrain(
  task("6"),
  session("6"),
  () => {},
  (error) => saturationRefusals.push(error),
);
const saturation0 = await nextRequest(saturationRequestIndex);
refusal(
  saturation0,
  "bridge_busy",
  "NamiSync is busy. Try this action again.",
);
const saturation1 = await nextRequest(saturationRequestIndex + 1);
assert.equal(saturation1.request.payload.replay_from, 1);
success(saturation1, [terminalRecord(session("6"))]);
await turns(30);
assert.deepEqual(scheduledDelays.slice(saturationDelayIndex), [50, 100]);
assert.equal(releaseRequests.length, releaseCountBeforeSaturation + 2);
assert.equal(saturationRefusals.length, 0);
stopSaturation();

// Exhausted release uncertainty retains the task and exposes an exact retry.
const exhaustedReleaseRefusals = [];
const exhaustedReleaseStart = releaseRequests.length;
releaseFailuresRemaining = 4;
const exhaustedReleaseDrainStart = requests.length;
const stopExhaustedRelease = bridge.startTaskDrain(
  task("4"),
  session("d"),
  () => {},
  (error) => exhaustedReleaseRefusals.push(error),
);
const exhaustedRelease0 = await nextRequest(exhaustedReleaseDrainStart);
success(exhaustedRelease0, [terminalRecord(session("d"))]);
await turns(40);
assert.equal(releaseRequests.length, exhaustedReleaseStart + 4);
assert.equal(exhaustedReleaseRefusals.length, 1);
assert.equal(
  exhaustedReleaseRefusals[0].name,
  "TerminalSessionReleaseError",
);
assert.equal(typeof exhaustedReleaseRefusals[0].retry, "function");
releaseFailuresRemaining = 0;
exhaustedReleaseRefusals[0].retry();
await turns(20);
assert.equal(releaseRequests.length, exhaustedReleaseStart + 5);
stopExhaustedRelease();
const exhaustedCloseStart = closeRequests.length;
closeFailuresRemaining = 4;
let uncertainClose;
try {
  await bridge.closeTask(task("4"), session("d"));
  assert.fail("exhausted close uncertainty must be visible");
} catch (error) {
  uncertainClose = error;
}
assert.equal(uncertainClose.name, "TaskCloseUncertainError");
assert.equal(typeof uncertainClose.retry, "function");
assert.equal(closeRequests.length, exhaustedCloseStart + 4);
assert.throws(
  () => bridge.startTaskDrain(task("4"), session("d"), assert.fail, assert.fail),
  TypeError,
);
closeFailuresRemaining = 0;
await uncertainClose.retry();
assert.equal(closeRequests.length, exhaustedCloseStart + 5);
const stopClosedReplacement = bridge.startTaskDrain(
  task("4"),
  session("d"),
  assert.fail,
  assert.fail,
);
await nextRequest(requests.length);
stopClosedReplacement();

// Persistent malformed transport responses consume a finite exponential
// recovery budget. Every retry keeps the exact recovery cursor, then one fixed
// refusal releases the browser entry instead of spinning in microtasks.
const persistentRefusals = [];
const persistentDelayIndex = scheduledDelays.length;
const persistentRequestIndex = requests.length;
const stopPersistent = bridge.startTaskDrain(
  task("2"),
  session("b"),
  assert.fail,
  (error) => persistentRefusals.push(error),
);
for (let attempt = 0; attempt < 7; attempt += 1) {
  const pending = await nextRequest(persistentRequestIndex + attempt);
  if (attempt > 0) {
    assert.equal(pending.request.payload.replay_from, 1);
  }
  pending.resolve(null);
  await turns(12);
}
assert.deepEqual(scheduledDelays.slice(persistentDelayIndex), [
  50,
  100,
  250,
  500,
  1000,
  2000,
]);
assert.equal(persistentRefusals.length, 1);
assert.equal(persistentRefusals[0].name, "BridgeTransportError");
const stopPersistentReplacement = bridge.startTaskDrain(
  task("2"),
  session("b"),
  assert.fail,
  assert.fail,
);
await nextRequest(requests.length);
stopPersistentReplacement();

stopOne();
stopOne();
stopTwo();
stopThree();
stopFour();
stopFive();
stopSix();
stopSeven();
stopReliable();
stopCursor();
stopRelease();
stopTerminalCallback();
stopExhaustedRelease();
stopPersistent();
stopProgressMatrix();
stopProgressBatch();
await turns();
assert.equal(testWindow.listenerCount("pywebviewready"), 1);
assert.equal(timers.size, 0);
