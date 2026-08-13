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
    randomUUID() {
      const value = (nextId++).toString(16).padStart(32, "0");
      return `${value.slice(0, 8)}-${value.slice(8, 12)}-${value.slice(12, 16)}-${value.slice(16, 20)}-${value.slice(20)}`;
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
const source = await readFile(modulePath, "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const bridge = await import(moduleUrl);

const session = (digit) => digit.repeat(32);
const task = (digit) => `task-${digit.repeat(32)}`;
const at = "2026-08-12T00:00:00Z";
const event = (sessionId, sequence, bodyType = "StateChanged", body = { state: "running" }) => ({
  update_type: "event",
  event: {
    session_id: sessionId,
    sequence,
    at,
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
  items: [],
  phases: [],
  bytes_done: 0,
  bytes_total: 0,
  error: null,
});
const coreOperationResult = Object.freeze({
  status: "completed",
  recording: "ok",
  audit: "ok",
  disposition: "ran",
  canceled: false,
  items: [],
  phases: [],
  bytes_done: 0,
  bytes_total: 0,
  error: null,
});
const terminalRecord = (sessionId, result = operationResult) => ({
  update_type: "record",
  record: {
    session_id: sessionId,
    kind: "plan",
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
  assert.deepEqual(Object.keys(pending.request.payload).sort(), [
    "drain_id",
    "replay_from",
    "session_id",
    "task_id",
  ]);
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
    items_done: 3,
    items_total: 3,
    bytes_done: 0,
    bytes_total: null,
    current_path: null,
  }),
]);
const one1 = await nextRequest(1);
assert.equal(one1.request.payload.replay_from, null);
assert.deepEqual(
  acceptedOne.map((update) => update.event.sequence),
  [1, 3],
);
testWindow.emit("pywebviewready");
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
testWindow.emit("pywebviewready");
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
testWindow.emit("pywebviewready");
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
testWindow.emit("pywebviewready");
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
testWindow.emit("pywebviewready");
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
      testWindow.emit("pywebviewready");
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
const originalRandomUUID = globalThis.crypto.randomUUID;
const mintRefusals = [];
globalThis.crypto.randomUUID = () => "invalid";
const stopSeven = bridge.startTaskDrain(
  task("7"),
  session("7"),
  assert.fail,
  (error) => mintRefusals.push(error),
);
await turns();
assert.equal(mintRefusals.length, 1);
assert.equal(mintRefusals[0].name, "BridgeTransportError");
globalThis.crypto.randomUUID = originalRandomUUID;
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
const terminalCallbackRefusals = [];
const terminalCallbackReleaseStart = releaseRequests.length;
const terminalCallbackCloseStart = closeRequests.length;
const terminalCallbackDrainStart = requests.length;
const stopTerminalCallback = bridge.startTaskDrain(
  task("3"),
  session("c"),
  (update) => {
    terminalCallbackAttempts.push(update);
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
await turns();
assert.equal(testWindow.listenerCount("pywebviewready"), 1);
assert.equal(timers.size, 0);
