import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { TestEventTarget } from "./_event_target.mjs";


class TestWindow extends TestEventTarget {
  constructor() {
    super();
    this.requests = [];
    this.acknowledgments = [];
    this.acknowledgedTokens = new Set();
    this.nativeResponses = new Map();
    this.nextResponseToken = 1;
    this.loseNextAcknowledgment = false;
    this.queuedResults = new Map();
    this.commandFailures = new Map();
    this.pywebview = {
      api: {
        dispatch: (requestJson) => this.dispatch(requestJson),
      },
    };
  }

  queueResults(command, ...results) {
    this.queuedResults.set(command, results);
  }

  failCommand(command, count) {
    this.commandFailures.set(command, count);
  }

  dispatch(requestJson) {
    if (requestJson.startsWith("ack:")) {
      this.acknowledgments.push(requestJson);
      const duplicate = this.acknowledgedTokens.has(requestJson);
      this.acknowledgedTokens.add(requestJson);
      const acknowledgedResponse = this.nativeResponses.get(requestJson);
      if (acknowledgedResponse !== undefined) {
        acknowledgedResponse.response.result = "mutated after browser detachment";
      }
      if (this.loseNextAcknowledgment) {
        this.loseNextAcknowledgment = false;
        return Promise.reject(new Error("synthetic lost acknowledgment"));
      }
      return Promise.resolve(!duplicate);
    }
    const request = JSON.parse(requestJson);
    this.requests.push(request);
    if (request.command === "reject_once") {
      return Promise.reject(new Error("synthetic transport refusal"));
    }
    const remainingFailures = this.commandFailures.get(request.command) ?? 0;
    if (remainingFailures > 0) {
      this.commandFailures.set(request.command, remainingFailures - 1);
      return Promise.reject(new Error("synthetic command transport refusal"));
    }
    const queued = this.queuedResults.get(request.command);
    const result = queued !== undefined && queued.length > 0
      ? queued.shift()
      : request.command === "pick_folder" || request.command === "admit_location"
        ? {
        purpose: request.payload.purpose,
        state: "resolved",
        choice_id: `slot-${"2".repeat(32)}`,
        continuation_id: null,
        display: "Selected 🌊",
        location_id: "2",
        candidates: [],
        detail: null,
        }
        : request.payload;
    const responseToken = (this.nextResponseToken++).toString(16).padStart(32, "0");
    const response = request.command === "untrusted_refusal"
      ? {
          schema_version: 1,
          request_id: null,
          ok: false,
          error: {
            code: "bridge_unavailable",
            message:
              "NamiSync is closing or this desktop page is no longer trusted.",
          },
        }
      : {
          schema_version: 1,
          request_id: request.request_id,
          ok: true,
          result,
        };
    const nativeResponse = {
      transport_version: 1,
      response_token: responseToken,
      response,
    };
    this.nativeResponses.set(`ack:${responseToken}`, nativeResponse);
    return Promise.resolve(nativeResponse);
  }
}

let timerCalls = 0;
globalThis.setTimeout = () => {
  timerCalls += 1;
  return timerCalls;
};
globalThis.clearTimeout = () => {};

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
  purpose: "source",
  state: "resolved",
  choice_id: `slot-${"2".repeat(32)}`,
  continuation_id: null,
  display: "Selected 🌊",
  location_id: "2",
  candidates: [],
  detail: null,
});
assert.equal(testWindow.requests.at(-1).command, "pick_folder");
assert.equal(testWindow.acknowledgments.length, 2);

testWindow.loseNextAcknowledgment = true;
const retriedAcknowledgment = await bridge.pickFolder("target");
assert.equal(retriedAcknowledgment.choice_id, `slot-${"2".repeat(32)}`);
assert.equal(testWindow.acknowledgments.length, 4);
assert.equal(
  testWindow.acknowledgments[2],
  testWindow.acknowledgments[3],
  "a lost cleanup response retries the exact token",
);

const continuationId = `slot-${"3".repeat(32)}`;
const timersBeforeDirectAdmission = timerCalls;
const continued = await bridge.admitLocation("source", {
  continuation_id: continuationId,
  mount_index: 1,
});
assert.equal(continued.choice_id, `slot-${"2".repeat(32)}`);
assert.deepEqual(testWindow.requests.at(-1).payload, {
  purpose: "source",
  continuation_id: continuationId,
  mount_index: 1,
});
assert.equal(timerCalls, timersBeforeDirectAdmission + 1, "direct continuation admission owns one deadline");
assert.throws(
  () => bridge.admitLocation("source", { continuation_id: continuationId, mount_index: -1 }),
  /candidate or continuation choice/,
);

const beforeStructuredRefusal = testWindow.acknowledgments.length;
await assert.rejects(
  bridge.dispatchInteractive("untrusted_refusal", {}, () => false),
  {
    name: "BridgeCommandError",
    code: "bridge_unavailable",
    message:
      "NamiSync is closing or this desktop page is no longer trusted.",
  },
);
assert.equal(
  testWindow.acknowledgments.length,
  beforeStructuredRefusal + 1,
  "a recognized refusal acknowledges its exact detached response",
);

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
assert.equal(timerCalls, 1, "interactive transport owns no client deadline");

const setupOptions = {
  filters: [],
  deletion_policy: "trash",
  trash_on_update: true,
  preservation: {
    preserve_ads: false,
    preserve_created: true,
    preserve_acl: false,
  },
  propagate_source_casing: false,
  verify_after_execute: false,
};
const setupLocation = { display: "C:\\Selected", location_id: null };
const defaultSetup = {
  setup_state: "default",
  task_kind: null,
  source: null,
  target: null,
  root: null,
  options: setupOptions,
  plan_again: null,
};
const taskId = `task-${"4".repeat(32)}`;
const otherTaskId = `task-${"5".repeat(32)}`;
const sameTaskStart = {
  task_id: taskId,
  request_id: "6".repeat(32),
  session_id: "7".repeat(32),
};
const freshTaskStart = { ...sameTaskStart, task_id: otherTaskId };

testWindow.queueResults("start_plan", sameTaskStart);
assert.deepEqual(
  await bridge.startPlan(
    taskId,
    `slot-${"8".repeat(32)}`,
    `slot-${"9".repeat(32)}`,
    setupOptions,
  ),
  sameTaskStart,
  "plan start remains bound to its existing task shell",
);
testWindow.queueResults("start_inventory", sameTaskStart);
assert.deepEqual(
  await bridge.startInventory(taskId, `slot-${"a".repeat(32)}`),
  sameTaskStart,
  "inventory start remains bound to its existing task shell",
);
testWindow.queueResults("plan_again", freshTaskStart);
assert.deepEqual(
  await bridge.planAgain(taskId),
  freshTaskStart,
  "Plan again accepts only a fresh task identity",
);

for (const [command, start, mismatch] of [
  [
    "start_plan",
    () => bridge.startPlan(
      taskId,
      `slot-${"8".repeat(32)}`,
      `slot-${"9".repeat(32)}`,
      setupOptions,
    ),
    freshTaskStart,
  ],
  [
    "start_inventory",
    () => bridge.startInventory(taskId, `slot-${"a".repeat(32)}`),
    freshTaskStart,
  ],
  ["plan_again", () => bridge.planAgain(taskId), sameTaskStart],
]) {
  testWindow.queueResults(command, mismatch, mismatch);
  await assert.rejects(
    start(),
    { name: "StartPlanUncertainError" },
    `${command} rejects a response with the wrong task identity`,
  );
}

const typedAmbiguous = {
  purpose: "source",
  state: "ambiguous",
  choice_id: null,
  continuation_id: null,
  display: "C:\\Typed",
  location_id: null,
  candidates: ["C:\\", "D:\\"],
  detail: "Choose a current mount",
};
testWindow.queueResults("admit_location", typedAmbiguous);
assert.deepEqual(
  await bridge.admitLocation("source", {
    kind: "literal_path",
    path: "C:\\Typed",
    selected_mount: null,
  }),
  typedAmbiguous,
  "typed ambiguity needs no picker continuation",
);

const planAgainCandidates = Array.from(
  { length: 53 },
  (_, index) => `C:\\mount-${index}`,
);
const frozenPlanSetup = {
  setup_state: "frozen",
  task_kind: "sync-plan",
  source: setupLocation,
  target: { display: "D:\\Selected", location_id: "2" },
  root: null,
  options: setupOptions,
  plan_again: {
    source_state: "ambiguous",
    source_candidates: planAgainCandidates,
    target_state: "resolved",
    target_candidates: [],
  },
};
const validTaskSetupRead = {
  task_id: taskId,
  snapshot: frozenPlanSetup,
  recents: null,
};
testWindow.queueResults("read_setup", validTaskSetupRead);
assert.deepEqual(
  await bridge.readSetup(taskId),
  validTaskSetupRead,
  "Plan-again readiness admits all 53 resolver candidates",
);

for (const mismatched of [
  { ...validTaskSetupRead, task_id: null, snapshot: defaultSetup, recents: {
    sources: [], targets: [], pairs: [],
  } },
  { ...validTaskSetupRead, task_id: otherTaskId },
]) {
  testWindow.queueResults("read_setup", mismatched, mismatched);
  await assert.rejects(
    bridge.readSetup(taskId),
    { name: "BridgeTransportError" },
    "task Setup reads reject default or other-task responses",
  );
}

const taskResponseForDefaultRead = { ...validTaskSetupRead };
testWindow.queueResults(
  "read_setup",
  taskResponseForDefaultRead,
  taskResponseForDefaultRead,
);
await assert.rejects(
  bridge.readSetup(),
  { name: "BridgeTransportError" },
  "default Setup reads reject task-bound responses",
);

const oversizedLocationChoice = {
  ...typedAmbiguous,
  candidates: planAgainCandidates.slice(0, 28),
};
testWindow.queueResults("admit_location", oversizedLocationChoice);
await assert.rejects(
  bridge.admitLocation("source", {
    kind: "literal_path",
    path: "C:\\Typed",
    selected_mount: null,
  }),
  { name: "BridgeTransportError" },
  "location admission remains limited to 27 mount candidates",
);

const invalidRecents = {
  task_id: null,
  snapshot: defaultSetup,
  recents: { sources: { length: 0 }, targets: [], pairs: [] },
};
testWindow.queueResults("read_setup", invalidRecents, invalidRecents);
await assert.rejects(
  bridge.readSetup(),
  { name: "BridgeTransportError" },
  "non-array recents fail as transport data instead of throwing TypeError",
);

const inconsistentSetups = [
  { ...defaultSetup, task_kind: "sync-plan" },
  { ...frozenPlanSetup, task_kind: null },
  { ...frozenPlanSetup, source: null },
  {
    setup_state: "frozen",
    task_kind: "inventory",
    source: null,
    target: null,
    root: setupLocation,
    options: setupOptions,
    plan_again: null,
  },
];
for (const snapshot of inconsistentSetups) {
  const invalid = { task_id: taskId, snapshot, recents: null };
  testWindow.queueResults("read_setup", invalid, invalid);
  await assert.rejects(
    bridge.readSetup(taskId),
    { name: "BridgeTransportError" },
    "inconsistent Setup state and task kind must be rejected",
  );
}

const inconsistentTaskList = {
  tasks: [{
    task_id: taskId,
    session_id: null,
    session_state: null,
    session_released: false,
    task_kind: "sync-plan",
    request_id: null,
  }],
};
testWindow.queueResults("list_tasks", inconsistentTaskList, inconsistentTaskList);
await assert.rejects(
  bridge.listTasks(),
  { name: "BridgeTransportError" },
  "task kind and request identity must be coupled",
);

testWindow.failCommand("create_task", 2);
testWindow.queueResults("create_task", { task_id: taskId });
let createUncertain;
try {
  await bridge.createTask();
  assert.fail("uncertain task creation must expose its retained retry");
} catch (error) {
  createUncertain = error;
}
assert.equal(createUncertain.name, "TaskCreateUncertainError");
assert.ok(createUncertain instanceof bridge.BridgeTransportError);
assert.equal(typeof createUncertain.retry, "function");
const createAttempts = testWindow.requests.filter(
  (request) => request.command === "create_task",
);
assert.equal(createAttempts.length, 2, "createTask performs one automatic replay");
assert.deepEqual(createAttempts[0].payload, createAttempts[1].payload);
const created = await createUncertain.retry();
assert.deepEqual(created, { task_id: taskId });
const recoveredCreateAttempts = testWindow.requests.filter(
  (request) => request.command === "create_task",
);
assert.equal(recoveredCreateAttempts.length, 3);
assert.deepEqual(
  recoveredCreateAttempts.map((request) => request.payload.command_id),
  Array(3).fill(createAttempts[0].payload.command_id),
  "manual task-create recovery reuses the exact command intent",
);
