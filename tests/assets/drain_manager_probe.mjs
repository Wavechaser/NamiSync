import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { TestEventTarget } from "./_event_target.mjs";


class TestWindow extends TestEventTarget {
  constructor() {
    super();
    this.pywebview = undefined;
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

async function waitUntil(predicate, context) {
  for (let turn = 0; turn < 100; turn += 1) {
    if (predicate()) {
      return;
    }
    await Promise.resolve();
  }
  assert.fail(context);
}


const timers = new Map();
const scheduledDelays = [];
let nextTimer = 1;
globalThis.setTimeout = (callback, milliseconds) => {
  const token = nextTimer;
  nextTimer += 1;
  timers.set(token, callback);
  if (milliseconds !== 30000 && milliseconds !== 5000) {
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
const observedLifecycle = [];
const retainedLifecycleResponses = new Map();
let releaseFailuresRemaining = 0;
let closeFailuresRemaining = 0;
let releaseObservationUnavailable = false;
let closeObservationUnavailable = false;
const releaseRefusalCodes = [];
let inspectReleaseDispatch = null;
testWindow.pywebview = {
  api: {
    dispatch(requestJson) {
      if (requestJson.startsWith("ack:")) {
        return Promise.resolve(true);
      }
      if (requestJson.startsWith("observe:")) {
        const [, requestId, command] = requestJson.split(":");
        observedLifecycle.push({ requestId, command });
        const retained = retainedLifecycleResponses.get(requestId);
        const unavailable = command === "release_terminal_session"
          ? releaseObservationUnavailable : closeObservationUnavailable;
        return Promise.resolve({
          transport_version: 1,
          state: retained !== undefined && retained.command === command && !unavailable
            ? "ready" : "unavailable",
          generation: 0,
          request_id: requestId,
          response_token: retained !== undefined && retained.command === command && !unavailable
            ? requestId : null,
          completion_token: null,
          response: retained !== undefined && retained.command === command && !unavailable
            ? retained.response : null,
        });
      }
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
            retainedLifecycleResponses.set(request.request_id, {
              command: request.command,
              response: {
                schema_version: 1,
                request_id: request.request_id,
                ok: true,
                result: {
                  task_id: request.payload.task_id,
                  session_id: request.payload.session_id,
                  ...(isRelease ? {} : { disposition: "closed" }),
                },
              },
            });
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
              ...(isRelease ? {} : { disposition: "closed" }),
            },
          });
        });
      } else {
        requests.push(invocation);
      }
      return pending.promise.then((response) => ({
        transport_version: 1,
        response_token: request.command === "release_terminal_session"
          || request.command === "close_task" ? request.request_id : null,
        response,
      }));
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

const session = (digit) => digit.repeat(32);
const task = (digit) => `task-${digit.repeat(32)}`;
const at = "2026-08-12T00:00:00+00:00";
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

const snapshotRevisions = new Map();

function snapshotFor(pending, updates, overrides = {}) {
  const taskId = pending.request.payload.task_id;
  const sessionId = pending.request.payload.session_id;
  const revision = (snapshotRevisions.get(taskId) ?? -1) + 1;
  snapshotRevisions.set(taskId, revision);
  const record = updates.findLast((update) => update.update_type === "record")?.record;
  const terminalResult = record?.result ?? null;
  return {
    wire_version: 2,
    task_id: taskId,
    session_id: sessionId,
    revision,
    session_state: record?.state ?? "active",
    control_state: "running",
    phase: null,
    active_item: null,
    progress_inconsistent: false,
    presentation: {
      item_percent: null,
      items_done: null,
      items_total: null,
      throughput_bytes_per_second: null,
      eta_seconds: null,
      value: 0,
      determinate: false,
      indeterminate: true,
    },
    gap_first_missed_seq: null,
    terminal_result: terminalResult,
    started_at: record?.started_at ?? null,
    ended_at: record?.ended_at ?? null,
    ...overrides,
  };
}

function success(pending, updates, snapshotOverrides = {}) {
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
      snapshot: snapshotFor(pending, updates, snapshotOverrides),
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

const operationAnchorIndex = requests.length;
const operationAnchorPromise = bridge.getPlanOperationAnchor(
  task("a"), session("b"), 7, "c".repeat(32),
);
await waitUntil(
  () => requests.length > operationAnchorIndex,
  "operation anchor request was not dispatched",
);
const operationAnchorRequest = requests[operationAnchorIndex];
assert.equal(operationAnchorRequest.request.command, "get_plan_anchor");
assert.deepEqual(operationAnchorRequest.request.payload, {
  task_id: task("a"),
  session_id: session("b"),
  expected_revision: 7,
  operation_id: "c".repeat(32),
});
operationAnchorRequest.resolve({
  schema_version: 1,
  request_id: operationAnchorRequest.request.request_id,
  ok: true,
  result: {
    disposition: "current", view_revision: 7,
    node_id: `node-${"d".repeat(32)}`, index: 41,
  },
});
assert.deepEqual(await operationAnchorPromise, {
  disposition: "current", view_revision: 7,
  node_id: `node-${"d".repeat(32)}`, index: 41,
});
requests.splice(operationAnchorIndex, 1);

// Numeric holes are legal, and a terminal record suppresses rearm.
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
success(one1, [
  event(session("1"), 4),
  event(session("1"), 6),
  event(session("1"), 7, "Terminal", { result: coreOperationResult }),
  terminalRecord(session("1")),
]);
await turns();
assert.deepEqual(
  acceptedOne.map((update) =>
    update.update_type === "event" ? update.event.body_type : "record"),
  [
    "StateChanged",
    "Progress",
    "StateChanged",
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

// A result-free terminal record must not acknowledge a co-batched reliable
// prefix, advance its cursor, or release stream custody.
const nullRecordSession = "87".repeat(16);
const nullRecordTask = `task-${"65".repeat(16)}`;
const acceptedNullRecord = [];
const nullRecordReleases = releaseRequests.length;
const stopNullRecord = bridge.startTaskDrain(
  nullRecordTask, nullRecordSession,
  (update) => acceptedNullRecord.push(update), assert.fail,
);
let nullRecordRecovery = await nextRequest(requests.length);
for (const record of [
  terminalRecord(nullRecordSession, null),
  terminalRecord(nullRecordSession, { ...operationResult, bytes_done: 0 }),
  {
    ...terminalRecord(nullRecordSession),
    record: { ...terminalRecord(nullRecordSession).record, state: "failed" },
  },
]) {
  const recoveryIndex = requests.length;
  success(nullRecordRecovery, [
    event(nullRecordSession, 1),
    event(nullRecordSession, 2, "PhaseChanged", { phase: "execute" }),
    record,
  ]);
  await turns();
  assert.equal(acceptedNullRecord.length, 0);
  assert.equal(releaseRequests.length, nullRecordReleases);
  nullRecordRecovery = await nextRequest(recoveryIndex);
  assert.equal(nullRecordRecovery.request.payload.replay_from, 1);
}
success(nullRecordRecovery, [
  event(nullRecordSession, 1),
  event(nullRecordSession, 2, "PhaseChanged", { phase: "execute" }),
  terminalRecord(nullRecordSession),
]);
await turns();
assert.deepEqual(acceptedNullRecord.map((update) => update.update_type), [
  "event", "event", "record",
]);
assert.equal(releaseRequests.length, nullRecordReleases + 1);
stopNullRecord();

// Live session events retain one browser-owned transport envelope. Event-body
// semantics belong to the trusted Python producer; malformed transport rejects
// the whole batch before callback delivery or replay-cursor movement.
const transportEventSession = "98".repeat(16);
const transportEventTask = `task-${"76".repeat(16)}`;
const acceptedTransportEvents = [];
const refusedTransportEvents = [];
let transportEventRequestIndex = requests.length;
const stopTransportEvents = bridge.startTaskDrain(
  transportEventTask,
  transportEventSession,
  (update) => { if (update !== null) acceptedTransportEvents.push(update); },
  (error) => refusedTransportEvents.push(error),
);
const canonicalTransportUpdate = event(
  transportEventSession,
  1,
  "StateChanged",
  { producer_owned: true },
);
canonicalTransportUpdate.event.at = 42;
const secondTransportEnvelope = {
  ...canonicalTransportUpdate.event,
  sequence: 2,
};
const invalidTransportEnvelopes = [
  ["non-object envelope", null],
  [
    "wrong schema version",
    { ...secondTransportEnvelope, schema_version: 4 },
  ],
  [
    "wrong session",
    { ...secondTransportEnvelope, session_id: "87".repeat(16) },
  ],
  ["zero sequence", { ...secondTransportEnvelope, sequence: 0 }],
  [
    "unsafe sequence",
    {
      ...secondTransportEnvelope,
      sequence: Number.MAX_SAFE_INTEGER + 1,
    },
  ],
  ["non-object body", { ...secondTransportEnvelope, body: [] }],
  [
    "unsafe Gap cursor",
    event(transportEventSession, 2, "Gap", {
      first_missed_seq: Number.MAX_SAFE_INTEGER + 1,
    }).event,
  ],
  ["extra envelope key", { ...secondTransportEnvelope, extra: null }],
];

for (const [label, invalidEnvelope] of invalidTransportEnvelopes) {
  const malformed = await nextRequest(transportEventRequestIndex);
  transportEventRequestIndex += 1;
  assert.equal(malformed.request.payload.replay_from, null, label);
  const invalidUpdate = {
    update_type: "event",
    event: invalidEnvelope,
  };
  success(malformed, [canonicalTransportUpdate, invalidUpdate]);

  const recovery = await nextRequest(transportEventRequestIndex);
  transportEventRequestIndex += 1;
  assert.equal(recovery.request.payload.replay_from, 1, label);
  assert.equal(acceptedTransportEvents.length, 0, label);
  assert.equal(refusedTransportEvents.length, 0, label);
  success(recovery, []);
  await turns();
}

const validTransportRequest = await nextRequest(transportEventRequestIndex);
assert.equal(validTransportRequest.request.payload.replay_from, null);
success(validTransportRequest, [canonicalTransportUpdate]);
await turns();
assert.equal(refusedTransportEvents.length, 0);
assert.equal(acceptedTransportEvents.length, 1);
assert.deepEqual(
  acceptedTransportEvents[0].event.body,
  { producer_owned: true },
);
assert.equal(acceptedTransportEvents[0].event.at, 42);
stopTransportEvents();

// Task snapshots are native presentation facts. The browser accepts their exact
// identity and scalar values without replaying event semantics in this probe.
const snapshotSession = "13".repeat(16);
const snapshotTask = `task-${"24".repeat(16)}`;
const acceptedSnapshots = [];
const refusedSnapshots = [];
const stopSnapshots = bridge.startTaskDrain(
  snapshotTask, snapshotSession,
  (update, snapshot) => acceptedSnapshots.push({ update, snapshot }),
  (error) => refusedSnapshots.push(error),
);
const activeProgress = {
  phase: "execute", items_done: 1, items_total: 3,
  bytes_done: "9007199254740993", bytes_total: "9223372036854775807",
  item_id: "35".repeat(16), item_type: "operation",
  item_attempt_id: "46".repeat(16),
  item_bytes_done: "4", item_bytes_total: "8",
};
const activeItem = Object.fromEntries([
  "item_id", "item_type",
].map((key) => [key, activeProgress[key]]));
const activePresentation = {
  item_percent: 50,
  items_done: 1, items_total: 3,
  throughput_bytes_per_second: 100, eta_seconds: 12,
  value: 12.5, determinate: true, indeterminate: false,
};
const activeFacts = {
  phase: "execute", active_item: activeItem,
  presentation: activePresentation,
};
const snapshot0 = await nextRequest(requests.length);
success(snapshot0, [
  event(snapshotSession, 1, "StateChanged", { state: "running" }),
  event(snapshotSession, 2, "Progress", {
    ...activeProgress, current_path: "observed.bin",
  }),
], activeFacts);
const snapshot1 = await nextRequest(requests.length);
assert.equal(acceptedSnapshots.length, 2);
assert.equal(acceptedSnapshots[0].snapshot, null,
  "only the final callback adopts one response snapshot");
assert.equal(acceptedSnapshots[1].update.event.body.bytes_done,
  "9007199254740993", "Scalar64 stays exact text");
assert.deepEqual(acceptedSnapshots[1].snapshot.active_item, activeItem);
assert.ok(Object.isFrozen(acceptedSnapshots[1].snapshot));
assert.ok(Object.isFrozen(acceptedSnapshots[1].snapshot.active_item));
assert.equal(refusedSnapshots.length, 0);

// Empty catch-up can publish a newer revision without manufacturing an update.
success(snapshot1, [], activeFacts);
const snapshot2 = await nextRequest(requests.length);
assert.equal(acceptedSnapshots.at(-1).update, null);
assert.equal(acceptedSnapshots.at(-1).snapshot.revision, 1);
const acceptedBeforeInvalidSnapshot = acceptedSnapshots.length;
const invalidSnapshots = [
  ["foreign task", { task_id: task("f") }],
  ["foreign session", { session_id: session("f") }],
  ["retired wire version", { wire_version: 1 }],
  ["Boolean revision", { revision: true }],
  ["stale revision", { revision: 0 }],
  ["invalid active identity", {
    ...activeFacts, active_item: { ...activeItem, item_id: 42 },
  }],
  ["unsafe display count", {
    ...activeFacts, presentation: { ...activePresentation,
      items_done: Number.MAX_SAFE_INTEGER + 1 },
  }],
];
let pendingSnapshot = snapshot2;
let nextSnapshotSequence = 3;
for (const [label, invalid] of invalidSnapshots) {
  const updates = [
    event(snapshotSession, nextSnapshotSequence, "StateChanged", { state: "running" }),
    event(snapshotSession, nextSnapshotSequence + 1, "StateChanged", { state: "paused" }),
  ];
  success(pendingSnapshot, updates, { ...activeFacts, ...invalid });
  const retry = await nextRequest(requests.length);
  assert.equal(retry.request.payload.replay_from, nextSnapshotSequence, label);
  assert.equal(acceptedSnapshots.length, acceptedBeforeInvalidSnapshot
    + (nextSnapshotSequence - 3), `${label} cannot deliver the valid sibling`);
  success(retry, updates, activeFacts);
  pendingSnapshot = await nextRequest(requests.length);
  assert.deepEqual(acceptedSnapshots.slice(-2).map(({ update }) =>
    update.event.sequence), [nextSnapshotSequence, nextSnapshotSequence + 1]);
  nextSnapshotSequence += 2;
}
assert.equal(refusedSnapshots.length, 0);
success(pendingSnapshot, [terminalRecord(snapshotSession)]);
await turns();
stopSnapshots();

// The cross-boundary fixture supplies both event envelopes and snapshots from
// the real Python executor and task adapter. No JavaScript producer model is used.
if (crossBoundaryFixture !== null) {
  assert.equal(crossBoundaryFixture.batches.length,
    crossBoundaryFixture.snapshots.length);
  const adopted = [];
  const stopCrossBoundary = bridge.startTaskDrain(
    crossBoundaryFixture.task_id,
    crossBoundaryFixture.session_id,
    (update, snapshot) => {
      if (snapshot !== null) adopted.push({ update, snapshot });
    },
    assert.fail,
  );
  for (let index = 0; index < crossBoundaryFixture.batches.length; index += 1) {
    const pending = await nextRequest(requests.length);
    success(pending, crossBoundaryFixture.batches[index],
      crossBoundaryFixture.snapshots[index]);
  }
  await turns();
  assert.deepEqual(adopted.slice(0, 2).map(({ snapshot }) =>
    snapshot.active_item?.item_id), crossBoundaryFixture.expected_active_ids);
  assert.equal(adopted.at(-1).snapshot.active_item, null);
  stopCrossBoundary();
}
// A second busy result in one uninterrupted generation suspends the exact
// browser entry until explicit replay or stop.
const definitiveBusyRefusals = [];
const definitiveBusyRetries = [];
const definitiveBusyRecovered = [];
const stopDefinitiveBusy = bridge.startTaskDrain(
  task("8"),
  session("8"),
  (update, snapshot) => {
    assert.equal(update, null);
    assert.equal(snapshot.task_id, task("8"));
  },
  (error, retry) => {
    definitiveBusyRefusals.push(error);
    definitiveBusyRetries.push(retry);
  },
  null,
  null,
  () => definitiveBusyRecovered.push(true),
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
assert.equal(typeof definitiveBusyRetries[0], "function");
definitiveBusyRetries[0]();
const busyRecovery = await nextRequest(requests.length);
assert.equal(busyRecovery.request.payload.replay_from, 1);
success(busyRecovery, []);
await turns();
assert.deepEqual(definitiveBusyRecovered, [true]);
stopDefinitiveBusy();
const stopFourReplacement = bridge.startTaskDrain(
  task("8"),
  session("8"),
  assert.fail,
  assert.fail,
);
await nextRequest(requests.length);
stopFourReplacement();
stopDefinitiveBusy();

// A consumer can synchronously stop observation after one accepted event.
// The rest of that response must not escape the retired task epoch.
const acceptedStoppedTail = [];
let stopStoppedTail;
stopStoppedTail = bridge.startTaskDrain(
  task("0"),
  session("0"),
  (update) => {
    acceptedStoppedTail.push(update);
    stopStoppedTail();
  },
  assert.fail,
);
const stoppedTail = await nextRequest(requests.length);
success(stoppedTail, [event(session("0"), 1), event(session("0"), 2)]);
await turns();
assert.deepEqual(acceptedStoppedTail.map((update) => update.event.sequence), [1]);

// Consumer failure suspends before rearm and preserves the failed event for
// exact manual replay. Duplicate task registration is refused synchronously.
const callbackRefusals = [];
const callbackRetries = [];
let callbackAttempts = 0;
const stopSix = bridge.startTaskDrain(
  task("f"),
  session("6"),
  () => {
    callbackAttempts += 1;
    if (callbackAttempts === 1) throw new Error("private consumer detail");
  },
  (error, retry) => {
    callbackRefusals.push(error);
    callbackRetries.push(retry);
  },
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
assert.equal(typeof callbackRetries[0], "function");
callbackRetries[0]();
const sixReplay = await nextRequest(requests.length);
assert.equal(sixReplay.request.payload.replay_from, 1);
success(sixReplay, [event(session("6"), 1)]);
await turns();
assert.equal(callbackAttempts, 2, "failed presentation is replayed once");
stopSix();

// A terminal record consumed by native response admission but lost in the
// browser is recovered through a manual non-null replay of the exact session.
const manualTerminalUpdates = [];
const manualTerminalRetries = [];
const manualTerminalReleaseBase = releaseRequests.length;
const stopManualTerminal = bridge.startTaskDrain(
  task("5"), session("5"),
  (update) => manualTerminalUpdates.push(update),
  (_error, retry) => manualTerminalRetries.push(retry),
);
const manual0 = await nextRequest(requests.length);
success(manual0, [event(session("5"), 1)]);
const manual1 = await nextRequest(requests.length);
refusal(manual1, "drain_busy", "That desktop task already has an event request in progress.");
const manual2 = await nextRequest(requests.length);
refusal(manual2, "drain_busy", "That desktop task already has an event request in progress.");
await turns();
assert.equal(manualTerminalRetries.length, 1);
manualTerminalRetries[0]();
const manualRecovery = await nextRequest(requests.length);
assert.equal(manualRecovery.request.payload.replay_from, 2);
success(manualRecovery, [terminalRecord(session("5"))]);
await turns();
assert.deepEqual(manualTerminalUpdates.map((update) => update.update_type), ["event", "record"]);
assert.equal(releaseRequests.length, manualTerminalReleaseBase + 1);
stopManualTerminal();

// Failure while minting an attempt id is surfaced once from the queued arm,
// does not become an unhandled rejection, and retains exact retry authority.
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
stopSeven();
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
const terminalCallbackSnapshots = [];
const terminalCallbackRefusals = [];
const terminalCallbackReleaseStart = releaseRequests.length;
const terminalCallbackCloseStart = closeRequests.length;
const terminalCallbackDrainStart = requests.length;
const stopTerminalCallback = bridge.startTaskDrain(
  task("3"),
  session("c"),
  (update, snapshot) => {
    terminalCallbackAttempts.push(update);
    terminalCallbackSnapshots.push(snapshot);
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
assert.equal(terminalCallbackSnapshots.length, 2);
for (const snapshot of terminalCallbackSnapshots) {
  assert.ok(Object.isFrozen(snapshot));
  assert.equal(snapshot.session_state, "completed");
  assert.equal(snapshot.terminal_result.headline, "success");
  assert.equal(snapshot.active_item, null);
}
assert.notEqual(terminalCallbackAttempts[0], terminalCallbackAttempts[1]);
assert.equal(terminalCallbackAttempts[0].record.state, "failed");
assert.equal(terminalCallbackAttempts[1].record.state, "completed");
assert.equal(releaseRequests.length, terminalCallbackReleaseStart + 1);
assert.equal(closeRequests.length, terminalCallbackCloseStart);
stopTerminalCallback();
const stopTerminalReplacement = bridge.startTaskDrain(
  task("3"),
  session("c"),
  assert.fail,
  assert.fail,
);
await nextRequest(requests.length);
stopTerminalReplacement();

// A terminal record is presented before session release begins. Lost lifecycle
// returns are recovered by observing their original results without resubmission.
const acceptedRelease = [];
const releaseRefusals = [];
const confirmedReleases = [];
const releaseCountBefore = releaseRequests.length;
const closeCountBeforeRelease = closeRequests.length;
const releaseObserveBefore = observedLifecycle.length;
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
  null,
  (taskId, sessionId) => confirmedReleases.push({ taskId, sessionId }),
);
const release0 = await nextRequest(releaseDrainIndex);
success(release0, [terminalRecord(session("a"))]);
await turns(30);
inspectReleaseDispatch = null;
assert.equal(releaseRequests.length, releaseCountBefore + 1);
assert.deepEqual(
  releaseRequests.slice(releaseCountBefore).map((item) => item.request.payload),
  [{ task_id: task("1"), session_id: session("a") }],
);
const releaseChecks = observedLifecycle.slice(releaseObserveBefore);
assert.ok(releaseChecks.length >= 1 && releaseChecks.length <= 3);
assert.ok(releaseChecks.every((item) => item.command === "release_terminal_session"));
assert.equal(releaseRefusals.length, 0);
assert.deepEqual(confirmedReleases, [
  { taskId: task("1"), sessionId: session("a") },
]);
assert.equal(closeRequests.length, closeCountBeforeRelease);
const closeObserveBefore = observedLifecycle.length;
closeFailuresRemaining = 1;
const closedReleaseTask = await bridge.closeTask(task("1"), session("a"));
assert.deepEqual(closedReleaseTask, {
  task_id: task("1"),
  session_id: session("a"),
  disposition: "closed",
});
assert.equal(closeRequests.length, closeCountBeforeRelease + 1);
const closeChecks = observedLifecycle.slice(closeObserveBefore);
assert.ok(closeChecks.length >= 1 && closeChecks.length <= 3);
assert.ok(closeChecks.every((item) => item.command === "close_task"));
assert.deepEqual(
  closeRequests.slice(closeCountBeforeRelease).map((item) => item.request.payload),
  [{ task_id: task("1"), session_id: session("a") }],
);
assert.equal(confirmedReleases.length, 1, "close cannot repeat release publication");
const stopReleaseReplacement = bridge.startTaskDrain(
  task("1"),
  session("a"),
  assert.fail,
  assert.fail,
);
await nextRequest(requests.length);
stopReleaseReplacement();
assert.throws(
  () => bridge.startTaskDrain(
    task("3"),
    session("d"),
    () => {},
    () => {},
    null,
    {},
  ),
  TypeError,
);

assert.throws(
  () => bridge.startTaskDrain(task("3"), session("d"), () => {}, () => {},
    null, null, null, {}),
  TypeError,
);

// Native admission saturation backs off the read-only drain. Terminal cleanup
// reports its definitive busy refusal for an explicit retry.
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
assert.ok(scheduledDelays.slice(saturationDelayIndex).includes(50));
assert.equal(releaseRequests.length, releaseCountBeforeSaturation + 1);
assert.equal(saturationRefusals.length, 1);
assert.equal(typeof saturationRefusals[0].retry, "function");
saturationRefusals[0].retry();
await turns(20);
assert.equal(releaseRequests.length, releaseCountBeforeSaturation + 2);
stopSaturation();

// Unavailable observation retains the original release and exposes only an
// original-result check as delay status, not a recovery refusal.
const exhaustedReleaseRefusals = [];
const exhaustedReleaseDelays = [];
const exhaustedReleaseStart = releaseRequests.length;
const exhaustedReleaseObserveStart = observedLifecycle.length;
releaseFailuresRemaining = 1;
releaseObservationUnavailable = true;
const exhaustedReleaseDrainStart = requests.length;
const stopExhaustedRelease = bridge.startTaskDrain(
  task("4"),
  session("d"),
  () => {},
  (error) => exhaustedReleaseRefusals.push(error),
  null, null, null,
  (_taskId, _sessionId, status) => exhaustedReleaseDelays.push(status),
);
const exhaustedRelease0 = await nextRequest(exhaustedReleaseDrainStart);
success(exhaustedRelease0, [terminalRecord(session("d"))]);
await waitUntil(
  () => exhaustedReleaseDelays.at(-1)?.state === "unavailable",
  "exhausted release did not expose its qualified observation state",
);
assert.equal(releaseRequests.length, exhaustedReleaseStart + 1);
assert.equal(observedLifecycle.length - exhaustedReleaseObserveStart, 3);
assert.equal(exhaustedReleaseRefusals.length, 0,
  "healthy pending release cannot enter the refusal channel");
assert.equal(typeof exhaustedReleaseDelays.at(-1).check, "function");
releaseObservationUnavailable = false;
await exhaustedReleaseDelays.at(-1).check();
await turns(20);
assert.equal(releaseRequests.length, exhaustedReleaseStart + 1);
assert.ok(observedLifecycle.length - exhaustedReleaseObserveStart >= 4);
assert.ok(observedLifecycle.length - exhaustedReleaseObserveStart <= 6);
stopExhaustedRelease();
const exhaustedCloseStart = closeRequests.length;
const exhaustedCloseObserveStart = observedLifecycle.length;
closeFailuresRemaining = 1;
closeObservationUnavailable = true;
const closeFeedback = [];
let closeSettled = false;
const uncertainClose = bridge.closeTask(task("4"), session("d"),
  (status) => closeFeedback.push(status));
void uncertainClose.then(() => { closeSettled = true; });
await waitUntil(() => closeFeedback.at(-1)?.state === "unavailable",
  "exhausted close must report qualified observation unavailability");
assert.equal(closeSettled, false,
  "observation exhaustion cannot settle the original Close");
assert.equal(typeof closeFeedback.at(-1).check, "function");
assert.equal(closeRequests.length, exhaustedCloseStart + 1);
assert.equal(observedLifecycle.length - exhaustedCloseObserveStart, 3);
assert.throws(
  () => bridge.startTaskDrain(task("4"), session("d"), assert.fail, assert.fail),
  TypeError,
);
closeObservationUnavailable = false;
await closeFeedback.at(-1).check();
await uncertainClose;
assert.equal(closeRequests.length, exhaustedCloseStart + 1);
assert.ok(observedLifecycle.length - exhaustedCloseObserveStart >= 4);
assert.ok(observedLifecycle.length - exhaustedCloseObserveStart <= 6);
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
// refusal suspends the browser entry instead of spinning in microtasks.
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
stopPersistent();
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
stopSix();
stopSeven();
stopRelease();
stopTerminalCallback();
stopExhaustedRelease();
stopPersistent();
await turns();
assert.equal(testWindow.listenerCount("pywebviewready"), 1);
assert.equal(timers.size, 0);
