import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { TestEventTarget } from "./_event_target.mjs";


class TestWindow extends TestEventTarget {
  constructor() {
    super();
    this.pywebview = undefined;
  }


}


const timers = new Map();
let nextTimer = 1;
globalThis.setTimeout = (callback, milliseconds) => {
  assert.ok([100, 250, 1000, 5000, 30000].includes(milliseconds));
  const token = nextTimer;
  nextTimer += 1;
  timers.set(token, callback);
  if (milliseconds === 100 || milliseconds === 250) {
    queueMicrotask(() => {
      if (timers.delete(token)) callback();
    });
  }
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
const taskId = `task-${"1".repeat(32)}`;
const options = Object.freeze({
  filters: [],
  deletion_policy: "trash",
  trash_on_update: false,
  preservation: Object.freeze({ preserve_ads: false, preserve_created: false, preserve_acl: false }),
  propagate_source_casing: false,
  verify_after_execute: false,
});
const requests = [];
const acknowledgments = [];
const observations = [];
const retained = new Map();
let nextResponseToken = 1;
let loseNextResponse = false;
let holdNextResponse = false;
let resolveLateResponse = null;
const planning = bridge.startPlan(taskId, sourceId, targetId, options);

await Promise.resolve();
assert.equal(timers.size, 1, "pre-ready start owns only its startup deadline");
const [expiredToken, expire] = timers.entries().next().value;
timers.delete(expiredToken);
expire();
await assert.rejects(planning, { name: "BridgeTransportError" });
assert.equal(requests.length, 0, "startup expiry admits no mutation");
assert.equal(observations.length, 0, "startup expiry has no original effect to observe");
assert.equal(timers.size, 0, "startup expiry retires its original continuation");

testWindow.pywebview = {
  api: {
    dispatch(requestJson) {
      if (requestJson.startsWith("ack:")) {
        acknowledgments.push(requestJson);
        return Promise.resolve(true);
      }
      if (requestJson.startsWith("observe:")) {
        const match = /^observe:([0-9a-f]{32}):start_plan$/.exec(requestJson);
        assert.ok(match, "only the original bounded start-plan identity is observed");
        observations.push(requestJson);
        const original = retained.get(match[1]);
        return Promise.resolve({
          transport_version: 1,
          state: original === undefined ? "unavailable" : "ready",
          generation: 1,
          request_id: match[1],
          response_token: original?.response_token ?? null,
          completion_token: null,
          response: original?.response ?? null,
        });
      }
      const request = JSON.parse(requestJson);
      requests.push(request);
      const nativeResponse = {
        transport_version: 1,
        response_token: (nextResponseToken++).toString(16).padStart(32, "0"),
        response: {
          schema_version: 1,
          request_id: request.request_id,
          ok: true,
          result: {
            task_id: taskId,
            request_id: "3".repeat(32),
            session_id: "4".repeat(32),
          },
        },
      };
      retained.set(request.request_id, nativeResponse);
      if (loseNextResponse) {
        loseNextResponse = false;
        return Promise.reject(new Error("simulated lost admission delivery"));
      }
      if (holdNextResponse) {
        holdNextResponse = false;
        return new Promise((resolve) => {
          resolveLateResponse = () => resolve(nativeResponse);
        });
      }
      return Promise.resolve(nativeResponse);
    },
  },
};
testWindow.emit("pywebviewready");
for (let turn = 0; turn < 4; turn += 1) {
  await Promise.resolve();
}
assert.equal(requests.length, 0, "raw injection does not admit normal commands");
bridge.markBridgeOperational();
for (let turn = 0; turn < 8; turn += 1) await Promise.resolve();
assert.equal(requests.length, 0, "late readiness cannot dispatch the retired start");

const freshPlanning = bridge.startPlan(taskId, sourceId, targetId, options);
assert.deepEqual(await freshPlanning, {
  task_id: taskId,
  request_id: "3".repeat(32),
  session_id: "4".repeat(32),
});
assert.equal(requests.length, 1, "a fresh user action dispatches once");
assert.equal(requests[0].command, "start_plan");
assert.deepEqual(Object.keys(requests[0].payload).sort(), [
  "command_id",
  "options",
  "source_id",
  "target_id",
  "task_id",
]);
assert.equal("revision" in requests[0].payload, false);
assert.equal(timers.size, 0, "the completed action clears feedback and cleanup bounds");
assert.equal(
  testWindow.listenerCount("pywebviewready"),
  1,
  "one document-readiness listener remains",
);

// Lost admission delivery recovers the original result without a new command.
loseNextResponse = true;
const uncertainPlanning = bridge.startPlan(taskId, sourceId, targetId, {
  ...options, deletion_policy: "additive",
});
assert.deepEqual(await uncertainPlanning, {
  task_id: taskId,
  request_id: "3".repeat(32),
  session_id: "4".repeat(32),
});
assert.equal(requests.length, 2);
const uncertainRequest = requests[1];
assert.equal(uncertainRequest.command, "start_plan");
assert.deepEqual(observations, [`observe:${uncertainRequest.request_id}:start_plan`]);
assert.deepEqual(Object.keys(uncertainRequest.payload).sort(), [
  "command_id",
  "options",
  "source_id",
  "target_id",
  "task_id",
]);
assert.equal(uncertainRequest.payload.source_id, sourceId);
assert.equal(uncertainRequest.payload.target_id, targetId);
assert.equal(uncertainRequest.payload.options.deletion_policy, "additive");
assert.match(uncertainRequest.payload.command_id, /^[0-9a-f]{32}$/);
assert.equal("revision" in uncertainRequest.payload, false);
assert.equal(timers.size, 0, "recovered action clears its feedback timer");

// Feedback can observe a result while the original native Promise is pending.
holdNextResponse = true;
const latePlanning = bridge.startPlan(taskId, sourceId, targetId, options);
for (let turn = 0; turn < 8 && resolveLateResponse === null; turn += 1) {
  await Promise.resolve();
}
assert.equal(typeof resolveLateResponse, "function");
assert.equal(timers.size, 1);
const [lateTimer, expireLate] = timers.entries().next().value;
timers.delete(lateTimer);
expireLate();
assert.deepEqual(await latePlanning, {
  task_id: taskId,
  request_id: "3".repeat(32),
  session_id: "4".repeat(32),
});
assert.equal(requests.length, 3, "feedback never replays the mutation");
assert.equal(observations.at(-1), `observe:${requests[2].request_id}:start_plan`);
const originalLateAck = `ack:${retained.get(requests[2].request_id).response_token}`;
assert.ok(acknowledgments.includes(originalLateAck),
  "observed result acknowledges its original native response token");
resolveLateResponse();
for (let turn = 0; turn < 8; turn += 1) {
  await Promise.resolve();
}
assert.equal(requests.length, 3, "late admission cannot resubmit the mutation");
for (let turn = 0; turn < 12; turn += 1) await Promise.resolve();
assert.equal(timers.size, 0, "late settlement cannot restore an old feedback timer");

// Exercise the packaged asynchronous wrappers against a bounded, deterministic
// native/document peer. Host generation is independent of the page's local
// readiness count.
const asyncTimers = new Map();
globalThis.setTimeout = (callback, milliseconds) => {
  assert.ok([0, 100, 250, 500, 1000, 5000, 30000].includes(milliseconds));
  const token = nextTimer++;
  asyncTimers.set(token, { callback, milliseconds });
  if (milliseconds === 100 || milliseconds === 250) {
    queueMicrotask(() => {
      if (asyncTimers.delete(token)) callback();
    });
  }
  return token;
};
globalThis.clearTimeout = (token) => asyncTimers.delete(token);
const page = new TestWindow();
const messages = new TestEventTarget();
page.chrome = { webview: messages };
globalThis.window = page;
globalThis.chrome = page.chrome;
const asyncBridge = await import(
  `data:text/javascript;base64,${Buffer.from(`${source}\n// async phase probe`).toString("base64")}`
);
const asyncRequests = [];
const asyncObservations = [];
const retainedExchanges = new Map();
const cleanup = [];
const effects = new Map();
const issued = new Set();
const acknowledged = new Set();
let hostGeneration = 37;
let wireId = 0;
let delivery = (exchange) => {
  send(exchange.message);
  return exchange.admission;
};
let cleanupPolicy = null;
let observationPolicy = (exchange) => exchange === undefined ? "unavailable" : "ready";

function send(message) {
  for (const { handler } of [...(messages.listeners.get("message") ?? [])]) {
    handler({ data: message });
  }
}

async function flush() {
  for (let step = 0; step < 100; step += 1) await Promise.resolve();
}

async function expireAsync(milliseconds) {
  const next = [...asyncTimers].find(([, timer]) => timer.milliseconds === milliseconds);
  assert.ok(next, `expected a ${milliseconds}ms timer`);
  asyncTimers.delete(next[0]);
  next[1].callback();
  await flush();
}

function success(request) {
  if (request.command === "probe_recent_pairs") {
    return { schema_version: 1, request_id: request.request_id, ok: true, result: { pairs: [] } };
  }
  const key = request.payload.command_id ??
    `${request.command}:${request.payload.task_id}:${request.payload.session_id}`;
  if (!effects.has(key)) {
    const identity = (++wireId).toString(16).padStart(32, "0");
    let result;
    if (request.command === "create_task") result = { task_id: `task-${identity}` };
    else if (request.command === "start_plan") {
      result = { task_id: request.payload.task_id, request_id: identity, session_id: identity };
    } else if (request.command === "close_task") {
      result = { ...request.payload, disposition: "closed" };
    } else {
      assert.equal(request.command, "release_terminal_session");
      result = { ...request.payload };
    }
    effects.set(key, result);
  }
  return { schema_version: 1, request_id: request.request_id, ok: true, result: effects.get(key) };
}

page.pywebview = { api: { dispatch(raw) {
  if (raw.startsWith("ack:")) {
    cleanup.push(raw);
    assert.ok(issued.has(raw), "cleanup must name an issued exact phase");
    if (cleanupPolicy !== null) return cleanupPolicy(raw);
    if (acknowledged.has(raw)) return false;
    acknowledged.add(raw);
    return true;
  }
  if (raw.startsWith("observe:")) {
    const match = /^observe:([0-9a-f]{32}):([a-z][a-z0-9]*(?:_[a-z0-9]+)*)$/.exec(raw);
    assert.ok(match, "observation carries a bounded original request and command");
    asyncObservations.push(raw);
    const exchange = retainedExchanges.get(match[1]);
    assert.ok(exchange === undefined || exchange.request.command === match[2]);
    const state = observationPolicy(exchange);
    return {
      transport_version: 1, state, generation: hostGeneration,
      request_id: match[1],
      response_token: state === "unavailable" ? null : exchange?.admission.response_token ?? null,
      completion_token: state === "unavailable" ? null : exchange?.message.completion_token ?? null,
      response: state === "ready" ? exchange.message.response : null,
    };
  }
  const request = JSON.parse(raw);
  asyncRequests.push(request);
  if (request.command === "custom_echo") {
    return { transport_version: 1, response_token: null,
      response: { schema_version: 1, request_id: request.request_id, ok: true, result: request.payload } };
  }
  const nativeToken = (++wireId).toString(16).padStart(32, "0");
  const completionToken = (++wireId).toString(16).padStart(32, "0");
  const completion = { phase: "completion", generation: hostGeneration,
    request_id: request.request_id, completion_token: completionToken };
  issued.add(`ack:${nativeToken}`);
  issued.add(`ack:completion:${hostGeneration}:${request.request_id}:${completionToken}`);
  const exchange = { request,
    admission: { transport_version: 1, response_token: nativeToken, completion },
    message: { kind: "namisync.command-completion.v1", ...completion, response: success(request) } };
  retainedExchanges.set(request.request_id, exchange);
  return delivery(exchange);
} } };
asyncBridge.markBridgeOperational();

let early;
let releaseAdmission;
delivery = (exchange) => {
  early = exchange;
  send(exchange.message);
  return new Promise((resolve) => { releaseAdmission = () => resolve(exchange.admission); });
};
let settled = 0;
const beforeAdmission = asyncBridge.createTask().then((result) => { settled += 1; return result; });
await flush();
assert.equal(settled, 0, "early completion cannot resolve before admission");
assert.equal(cleanup.length, 0, "early completion waits for admission identity");
page.emit("pywebviewready");
page.emit("pywebviewready");
await flush();
assert.equal(settled, 0, "late or duplicate ready cannot abandon admitted work");
assert.equal(asyncRequests.length, 1, "ready events cannot replay an effect");
releaseAdmission();
assert.deepEqual(await beforeAdmission, early.message.response.result);
assert.deepEqual(cleanup.slice(-2), [
  `ack:${early.admission.response_token}`,
  `ack:completion:37:${early.request.request_id}:${early.message.completion_token}`,
]);
assert.equal(settled, 1);
assert.equal(asyncTimers.size, 0);

const immediate = (exchange) => { send(exchange.message); return exchange.admission; };
delivery = immediate;
assert.deepEqual(await asyncBridge.dispatchInteractive("custom_echo", { literal: "unchanged" }, (value) => value),
  { literal: "unchanged" });

// Lost completion delivery recovers each original result without replaying effects.
for (const command of ["create_task", "start_plan", "close_task", "release_terminal_session"]) {
  const firstRequest = asyncRequests.length;
  const firstEffect = effects.size;
  const firstObservation = asyncObservations.length;
  let lost;
  delivery = (exchange) => { lost = exchange; return exchange.admission; };
  const taskId = `task-${(++wireId).toString(16).padStart(32, "0")}`;
  const sessionId = (++wireId).toString(16).padStart(32, "0");
  let work;
  if (command === "create_task") work = asyncBridge.createTask();
  else if (command === "start_plan") work = asyncBridge.startPlan(taskId, sourceId, targetId, options);
  else if (command === "close_task") work = asyncBridge.closeTask(taskId);
  else asyncBridge.startTaskDrain(taskId, sessionId, () => {}, (error) => { throw error; },
    { terminal: true, sessionReleased: false });
  await flush();
  assert.equal(lost.request.command, command);
  await expireAsync(5000);
  if (work !== undefined) await work;
  await flush();
  const [original] = asyncRequests.slice(firstRequest);
  assert.equal(asyncRequests.length, firstRequest + 1,
    `${command} keeps one original mutation request`);
  assert.deepEqual(asyncObservations.slice(firstObservation),
    [`observe:${original.request_id}:${command}`]);
  assert.equal(effects.size, firstEffect + 1, `${command} keeps one effect identity`);
  const beforeLate = asyncRequests.length;
  const completionAck = `ack:completion:${hostGeneration}:${lost.request.request_id}:${lost.message.completion_token}`;
  assert.equal(cleanup.filter((item) => item === completionAck).length, 1,
    "observed result acknowledges its exact original completion once");
  send(lost.message);
  await flush();
  assert.equal(asyncRequests.length, beforeLate, "late completion invokes no new command");
  assert.equal(cleanup.filter((item) => item === completionAck).length, 1,
    "late duplicate completion adds no acknowledgment");
  assert.equal(asyncTimers.size, 0, "late completion leaves no feedback timer");
}

// Wrong phase/token/request envelopes cannot deliver a result or clean custody.
let pending;
delivery = (exchange) => { pending = exchange; return exchange.admission; };
let accepted = false;
const exact = asyncBridge.createTask().then((value) => { accepted = true; return value; });
await flush();
const priorCleanup = cleanup.length;
for (const patch of [
  { phase: "admission" }, { generation: hostGeneration - 1 },
  { request_id: "f".repeat(32) }, { completion_token: "f".repeat(32) },
]) {
  send({ ...pending.message, ...patch });
}
await flush();
assert.equal(accepted, false);
assert.equal(cleanup.length, priorCleanup);
send(pending.message);
await exact;

for (const malformed of [
  (admission) => ({ ...admission, response_token: null }),
  (admission) => ({ ...admission, extra: true }),
  (admission) => ({ ...admission, completion: { ...admission.completion, phase: "admission" } }),
  (admission) => ({ ...admission, completion: { ...admission.completion, generation: "38" } }),
  (admission) => ({ ...admission, completion: { ...admission.completion, request_id: "f".repeat(32) } }),
]) {
  const requestCount = asyncRequests.length;
  const observationCount = asyncObservations.length;
  const effectCount = effects.size;
  delivery = (exchange) => malformed(exchange.admission);
  const work = asyncBridge.createTask();
  await flush();
  if ([...asyncTimers.values()].some((timer) => timer.milliseconds === 5000)) {
    await expireAsync(5000);
  }
  await work;
  assert.equal(asyncRequests.length, requestCount + 1, "invalid admission cannot replay the mutation");
  assert.deepEqual(asyncObservations.slice(observationCount),
    [`observe:${asyncRequests[requestCount].request_id}:create_task`]);
  assert.equal(effects.size, effectCount + 1, "invalid delivery retains one original effect");
  assert.equal(asyncTimers.size, 0);
}

for (const phase of ["native", "completion"]) {
  let captured;
  delivery = (exchange) => { captured = exchange; return immediate(exchange); };
  const requestCount = asyncRequests.length;
  let lostAck = false;
  let originalTaskId;
  cleanupPolicy = (ack) => {
    if ((phase === "completion") === ack.startsWith("ack:completion:") && !lostAck) {
      lostAck = true;
      originalTaskId = captured.message.response.result.task_id;
      captured.message.response.result.task_id = `task-${"f".repeat(32)}`;
      acknowledged.add(ack);
      throw new Error("cleanup succeeded but its return was lost");
    }
    if (acknowledged.has(ack)) return false;
    acknowledged.add(ack);
    return true;
  };
  const adopted = await asyncBridge.createTask();
  assert.equal(lostAck, true);
  assert.equal(adopted.task_id, originalTaskId,
    "validated result capture survives a failed cleanup response");
  assert.equal(asyncRequests.length, requestCount + 1,
    "lost cleanup response cannot rerun the validated command");
  cleanupPolicy = null;

  let refused = 0;
  cleanupPolicy = (ack) => {
    if ((phase === "completion") === ack.startsWith("ack:completion:") && refused < 2) {
      refused += 1;
      return false;
    }
    acknowledged.add(ack);
    return true;
  };
  await asyncBridge.createTask();
  await flush();
  assert.equal(refused, 2);
  assert.equal(asyncRequests.length, requestCount + 2,
    "unconfirmed cleanup cannot replay the second mutation");
  assert.equal(asyncTimers.size, 0);
  cleanupPolicy = null;
}

for (const phase of ["native", "completion"]) {
  delivery = immediate;
  let hung = 0;
  cleanupPolicy = (ack) => {
    if ((phase === "completion") === ack.startsWith("ack:completion:") && hung < 2) {
      hung += 1;
      return new Promise(() => {});
    }
    acknowledged.add(ack);
    return true;
  };
  const firstEffect = effects.size;
  const bounded = asyncBridge.createTask();
  await flush();
  await expireAsync(1000);
  await expireAsync(1000);
  await bounded;
  assert.equal(hung, 2);
  assert.equal(effects.size, firstEffect + 1, "cleanup timeout preserves one effect");
  assert.equal(asyncTimers.size, 0);
  cleanupPolicy = null;
}

// A timed-out read still owns exact cleanup for a later native completion.
// It cannot ACK a completion with no matching async entry.
let lateRead;
delivery = (exchange) => { lateRead = exchange; return exchange.admission; };
const readRequestCount = asyncRequests.length;
const readObservationCount = asyncObservations.length;
const readEffectCount = effects.size;
const readCleanupCount = cleanup.length;
const timedRead = asyncBridge.probeRecentPairs();
await flush();
assert.equal(asyncRequests.length, readRequestCount + 1);
assert.equal(lateRead.request.command, "probe_recent_pairs");
await expireAsync(5000);
await assert.rejects(timedRead, { name: "BridgeTransportError" });
assert.equal(asyncObservations.length, readObservationCount,
  "the read timeout does not start mutation observation");
assert.equal(effects.size, readEffectCount,
  "the timed-out probe has no filesystem effect");
assert.deepEqual(cleanup.slice(readCleanupCount), [`ack:${lateRead.admission.response_token}`],
  "the original read admission is ACKed despite the caller deadline");
const beforeUnmatched = cleanup.length;
send({ ...lateRead.message, request_id: "f".repeat(32) });
await flush();
assert.equal(cleanup.length, beforeUnmatched,
  "a completion without its exact read entry receives no ACK");
send(lateRead.message);
await flush();
assert.deepEqual(cleanup.slice(readCleanupCount), [
  `ack:${lateRead.admission.response_token}`,
  `ack:completion:${hostGeneration}:${lateRead.request.request_id}:${lateRead.message.completion_token}`,
], "late exact completion is ACKed after the read caller has timed out");
assert.equal(asyncRequests.length, readRequestCount + 1,
  "late read cleanup does not issue a second request");
assert.equal(asyncTimers.size, 0);

// Exhausted observation leaves the original effect uncertain; a later retry
// observes that same request and never resubmits the command.
let lateExchange;
delivery = (exchange) => { lateExchange = exchange; return exchange.admission; };
observationPolicy = (exchange) => exchange === lateExchange ? "pending" : "ready";
const unavailableRequestCount = asyncRequests.length;
const unavailableObservationCount = asyncObservations.length;
const unavailableWork = asyncBridge.createTask();
await flush();
await expireAsync(5000);
let unavailableError;
try {
  await unavailableWork;
  assert.fail("three pending observations must report an unavailable outcome");
} catch (error) {
  unavailableError = error;
}
assert.equal(unavailableError.name, "TaskCreateUncertainError");
assert.equal(typeof unavailableError.retry, "function");
assert.equal(asyncRequests.length, unavailableRequestCount + 1);
assert.deepEqual(asyncObservations.slice(unavailableObservationCount),
  Array(3).fill(`observe:${lateExchange.request.request_id}:create_task`));
observationPolicy = () => "ready";
assert.deepEqual(await unavailableError.retry(), lateExchange.message.response.result);
assert.equal(asyncRequests.length, unavailableRequestCount + 1,
  "manual outcome retry only observes the original request");
assert.equal(asyncObservations.length, unavailableObservationCount + 4);

// A captured final error cannot decide whether the effect happened, but its
// exact result is already available and must not retain a pointless retry slot.
for (const code of ["internal_error", "response_too_large"]) {
  let captured;
  delivery = (exchange) => {
    captured = exchange;
    exchange.message.response = {
      schema_version: 1, request_id: exchange.request.request_id, ok: false,
      error: {
        code,
        message: code === "internal_error"
          ? "NamiSync could not complete the desktop action."
          : "The desktop response is too large.",
      },
    };
    return immediate(exchange);
  };
  const requestCount = asyncRequests.length;
  const observationCount = asyncObservations.length;
  let finalError;
  try {
    await asyncBridge.createTask();
    assert.fail(`${code} cannot declare a failed effect`);
  } catch (error) {
    finalError = error;
  }
  assert.equal(finalError.name, "TaskCreateUncertainError");
  assert.equal(finalError.checkable, false);
  assert.equal(finalError.retry, null);
  assert.equal(asyncRequests.length, requestCount + 1,
    "captured error cannot resubmit the original mutation");
  assert.equal(asyncObservations.length, observationCount,
    "captured error has no delivery loss to observe");
  assert.ok(cleanup.includes(`ack:completion:${hostGeneration}:${captured.request.request_id}:${captured.message.completion_token}`),
    "captured final error acknowledges its exact completion");
}

// Only unresolved delivery-loss attempts own observation slots. All 64 slots
// fill before the next mutation or mixed async read is refused.
delivery = (exchange) => exchange.admission;
const countBefore = asyncRequests.length;
const observationsBefore = asyncObservations.length;
const batch = Array.from({ length: 64 }, () => asyncBridge.createTask());
await flush();
await assert.rejects(asyncBridge.createTask(), (error) => error.code === "bridge_busy");
assert.equal(asyncRequests.length, countBefore + 64);
await assert.rejects(asyncBridge.probeRecentPairs(), (error) => error.code === "bridge_busy");
assert.equal(asyncRequests.length, countBefore + 64,
  "the mixed async read cannot exceed the shared native admission ceiling");
const feedback = [...asyncTimers].filter(([, timer]) => timer.milliseconds === 5000);
assert.equal(feedback.length, 64);
observationPolicy = () => "unavailable";
for (const [token, timer] of feedback) { asyncTimers.delete(token); timer.callback(); }
const unavailable = await Promise.allSettled(batch);
assert.ok(unavailable.every((entry) => entry.status === "rejected"
  && entry.reason.name === "TaskCreateUncertainError"));
assert.equal(asyncRequests.length, countBefore + 64,
  "observation exhaustion cannot replay any retained mutation");
assert.equal(asyncObservations.length - observationsBefore, 64 * 3,
  "every retained action used exactly three read-only observations");
for (const request of asyncRequests.slice(countBefore)) {
  assert.equal(asyncObservations.slice(observationsBefore).filter((value) =>
    value === `observe:${request.request_id}:create_task`).length, 3);
}
assert.equal(page.listenerCount("pywebviewready"), 1);
