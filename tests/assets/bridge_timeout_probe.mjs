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
  assert.ok([1000, 30000].includes(milliseconds));
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
let uncertainResponses = 0;
let holdNextResponse = false;
let resolveLateResponse = null;
const planning = bridge.startPlan(taskId, sourceId, targetId, options);

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
      if (requestJson.startsWith("ack:")) {
        acknowledgments.push(requestJson);
        return Promise.resolve(true);
      }
      const request = JSON.parse(requestJson);
      requests.push(request);
      if (uncertainResponses > 0) {
        uncertainResponses -= 1;
        return Promise.reject(new Error("simulated uncertain delivery"));
      }
      const nativeResponse = {
        transport_version: 1,
        response_token: holdNextResponse ? "a".repeat(32) : null,
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

assert.deepEqual(await planning, {
  task_id: taskId,
  request_id: "3".repeat(32),
  session_id: "4".repeat(32),
});
assert.equal(requests.length, 1, "only the fresh replay may dispatch");
assert.equal(requests[0].command, "start_plan");
assert.deepEqual(Object.keys(requests[0].payload).sort(), [
  "command_id",
  "options",
  "source_id",
  "target_id",
  "task_id",
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
const uncertainPlanning = bridge.startPlan(taskId, sourceId, targetId, {
  ...options, deletion_policy: "additive",
});
assert.deepEqual(await uncertainPlanning, {
  task_id: taskId,
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
  "options",
  "source_id",
  "target_id",
  "task_id",
]);
assert.equal(uncertainAttempts[0].payload.source_id, sourceId);
assert.equal(uncertainAttempts[0].payload.target_id, targetId);
assert.equal(uncertainAttempts[0].payload.options.deletion_policy, "additive");
assert.match(uncertainAttempts[0].payload.command_id, /^[0-9a-f]{32}$/);
assert.equal("revision" in uncertainAttempts[0].payload, false);
assert.equal(timers.size, 0, "both uncertain attempts clear their deadlines");

// A timed-out native Promise still owns its transport continuation. Its late
// non-null wrapper is detached and acknowledged even though the retry already
// supplied the domain result.
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
assert.equal(acknowledgments.length, 0);
resolveLateResponse();
for (let turn = 0; turn < 8 && acknowledgments.length === 0; turn += 1) {
  await Promise.resolve();
}
assert.deepEqual(acknowledgments, [`ack:${"a".repeat(32)}`]);
for (let turn = 0; turn < 12; turn += 1) await Promise.resolve();
assert.equal(timers.size, 0, "late settlement cannot restore an old deadline");

// Exercise the packaged asynchronous wrappers against a bounded, deterministic
// native/document peer. Host generation deliberately differs from the page's
// reinjection counter, as it does after a real page reload.
const asyncTimers = new Map();
globalThis.setTimeout = (callback, milliseconds) => {
  assert.ok([0, 100, 250, 500, 1000, 5000, 30000].includes(milliseconds));
  const token = nextTimer++;
  asyncTimers.set(token, { callback, milliseconds });
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
  return delivery({ request,
    admission: { transport_version: 1, response_token: nativeToken, completion },
    message: { kind: "namisync.command-completion.v1", ...completion, response: success(request) } });
} } };
page.emit("pywebviewready");
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

// Each command uses its existing recovery identity after a lost completion.
for (const command of ["create_task", "start_plan", "close_task", "release_terminal_session"]) {
  const firstRequest = asyncRequests.length;
  const firstEffect = effects.size;
  let lost;
  delivery = (exchange) => {
    if (lost === undefined) { lost = exchange; return exchange.admission; }
    return immediate(exchange);
  };
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
  await expireAsync(30000);
  if (command === "close_task" || command === "release_terminal_session") await expireAsync(100);
  if (work !== undefined) await work;
  await flush();
  const pair = asyncRequests.slice(firstRequest);
  assert.equal(pair.length, 2, `${command} performs one bounded recovery`);
  assert.notEqual(pair[0].request_id, pair[1].request_id);
  assert.deepEqual(pair[0].payload, pair[1].payload);
  assert.equal(effects.size, firstEffect + 1, `${command} keeps one effect identity`);
  const beforeLate = asyncRequests.length;
  const beforeCleanup = cleanup.length;
  send(lost.message);
  await flush();
  assert.equal(asyncRequests.length, beforeLate, "late completion invokes no new command");
  assert.equal(cleanup.length, beforeCleanup + 1, "late completion is cleanup-only");
  assert.equal(asyncTimers.size, 0, "late cleanup leaves no deadline/history work");
}

// A new document has a fresh local counter but a later persistent host epoch.
let old;
let oldAdmission;
delivery = (exchange) => {
  if (old === undefined) {
    old = exchange;
    return new Promise((resolve) => { oldAdmission = () => resolve(exchange.admission); });
  }
  return immediate(exchange);
};
const reloaded = asyncBridge.createTask();
await flush();
hostGeneration += 1;
page.emit("pywebviewready");
asyncBridge.markBridgeOperational();
await reloaded;
oldAdmission();
send(old.message);
await flush();
assert.equal(asyncTimers.size, 0);
assert.equal(page.listenerCount("pywebviewready"), 1);

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
  let invalid = true;
  const requestCount = asyncRequests.length;
  const effectCount = effects.size;
  delivery = (exchange) => {
    if (invalid) { invalid = false; return malformed(exchange.admission); }
    return immediate(exchange);
  };
  await asyncBridge.createTask();
  assert.equal(asyncRequests.length, requestCount + 2, "invalid admission cannot deliver success");
  assert.equal(effects.size, effectCount + 1, "invalid delivery keeps effect replay identity");
  assert.equal(asyncTimers.size, 0);
}

for (const phase of ["native", "completion"]) {
  delivery = immediate;
  const requestCount = asyncRequests.length;
  let lostAck = false;
  cleanupPolicy = (ack) => {
    if ((phase === "completion") === ack.startsWith("ack:completion:") && !lostAck) {
      lostAck = true;
      acknowledged.add(ack);
      throw new Error("cleanup succeeded but its return was lost");
    }
    if (acknowledged.has(ack)) return false;
    acknowledged.add(ack);
    return true;
  };
  await asyncBridge.createTask();
  assert.equal(lostAck, true);
  assert.equal(asyncRequests.length, requestCount + 1, "cleanup replay does not rerun the command");
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
  assert.equal(refused, 2);
  assert.equal(asyncRequests.length, requestCount + 3, "unconfirmed cleanup requires command recovery");
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
  assert.equal(effects.size, firstEffect + 1, "cleanup timeout replays one effect");
  assert.equal(asyncTimers.size, 0);
  cleanupPolicy = null;
}

// The first excess is refused before native dispatch; deadlines free all slots.
delivery = (exchange) => exchange.admission;
const countBefore = asyncRequests.length;
const batch = Array.from({ length: 64 }, () => asyncBridge.createTask());
await flush();
await assert.rejects(asyncBridge.createTask(), (error) => error.code === "bridge_busy");
assert.equal(asyncRequests.length, countBefore + 64);
delivery = immediate;
const deadlines = [...asyncTimers].filter(([, timer]) => timer.milliseconds === 30000);
assert.equal(deadlines.length, 64);
for (const [token, timer] of deadlines) { asyncTimers.delete(token); timer.callback(); }
await Promise.all(batch);
await asyncBridge.createTask();
assert.equal(asyncTimers.size, 0);
assert.equal(page.listenerCount("pywebviewready"), 1);
