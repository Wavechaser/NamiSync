const SCHEMA_VERSION = 1;
const ID_PATTERN = /^[0-9a-f]{32}$/;
const SLOT_PATTERN = /^slot-[0-9a-f]{32}$/;
const TASK_PATTERN = /^task-[0-9a-f]{32}$/;
const COMMAND_PATTERN = /^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/;
const COMMAND_MAX_LENGTH = 64;
const COMMAND_POLICY_JSON = `{
  "shell_ready": {"timeout": "startup-5-seconds", "retry": "none", "phase": "bootstrap"},
  "readiness_echo": {"timeout": "startup-5-seconds", "retry": "same-payload-once", "phase": "bootstrap"},
  "pick_folder": {"timeout": "interactive", "retry": "none", "phase": "open"},
  "read_cosmetic_section": {"timeout": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "replace_cosmetic_section": {"timeout": "local-5-seconds", "retry": "none", "phase": "open"},
  "start_plan": {"timeout": "mutation-30-seconds", "retry": "same-command-once", "phase": "open"},
  "next_events": {"timeout": "drain-30-seconds", "retry": "none", "phase": "open"},
  "release_terminal_session": {"timeout": "mutation-30-seconds", "retry": "same-payload-bounded", "phase": "open"},
  "close_task": {"timeout": "mutation-30-seconds", "retry": "same-payload-bounded", "phase": "open"}
}`;
export const COMMAND_POLICY_CONTRACT = freezeCommandPolicies(
  JSON.parse(COMMAND_POLICY_JSON),
);
const TIMEOUT_MS_BY_POLICY = Object.freeze({
  "startup-5-seconds": 5000,
  "local-5-seconds": 5000,
  "interactive": null,
  "mutation-30-seconds": 30000,
  "drain-30-seconds": 30000,
});
const SHELL_READY_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.shell_ready.timeout];
const READINESS_ECHO_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.readiness_echo.timeout];
const COSMETIC_READ_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.read_cosmetic_section.timeout];
const COSMETIC_REPLACE_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.replace_cosmetic_section.timeout];
const START_PLAN_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.start_plan.timeout];
const DRAIN_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.next_events.timeout];
const SESSION_RELEASE_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.release_terminal_session.timeout];
const TASK_CLOSE_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.close_task.timeout];
const DRAIN_MAX_UPDATES = 64;
const DRAIN_RECOVERY_DELAYS_MS = Object.freeze([
  50,
  100,
  250,
  500,
  1000,
  2000,
]);
const SESSION_RELEASE_RECOVERY_DELAYS_MS = Object.freeze([100, 250, 500]);
const TASK_CLOSE_RECOVERY_DELAYS_MS = Object.freeze([100, 250, 500]);
const SESSION_STATES = Object.freeze([
  "pending",
  "running",
  "pausing",
  "paused",
  "canceling",
  "completed",
  "failed",
  "canceled",
  "refused",
  "interrupted",
]);
const TERMINAL_STATES = Object.freeze([
  "completed",
  "failed",
  "canceled",
  "refused",
]);
const RECORDING_STATES = Object.freeze(["ok", "degraded"]);
const DISPOSITIONS = Object.freeze(["ran", "unrun"]);
const THEMES = Object.freeze(["system", "light", "dark"]);
const COSMETIC_DISPOSITIONS = Object.freeze(["applied", "noop", "conflict"]);
const APPEARANCE_SECTION = "appearance";
const APPEARANCE_VALUE_VERSION = 1;

function freezeCommandPolicies(policies) {
  for (const policy of Object.values(policies)) {
    Object.freeze(policy);
  }
  return Object.freeze(policies);
}

const PHASE_STATES = Object.freeze([
  "completed",
  "failed",
  "canceled",
  "incomplete",
]);
const OPERATION_OUTCOMES = Object.freeze([
  "succeeded",
  "skipped",
  "failed",
  "canceled",
  "deferred",
  "blocked",
]);
const INTEGRITY_MODES = Object.freeze(["baseline", "verify", "rebaseline"]);
const INTEGRITY_RESULTS = Object.freeze([
  "verified",
  "baselined",
  "mismatched",
  "modified",
  "missing",
  "unsupported",
  "canceled",
  "error",
]);
const INTEGRITY_REASONS = Object.freeze([
  "path-invalid",
  "inventory-missing",
  "inventory-unsupported",
  "not-found",
  "unsupported-read",
  "stat-changed",
  "read-drift",
  "hash-mismatch",
  "baseline-exists",
  "read-error",
  "recording-stale",
  "recording-conflict",
  "recording-error",
  "canceled",
]);
const READ_STRATEGIES = Object.freeze(["windows-unbuffered"]);
const RECORD_DISPOSITIONS = Object.freeze([
  "applied",
  "noop",
  "stale",
  "conflict",
]);
const RESULT_HEADLINES = Object.freeze([
  "failed",
  "partial",
  "refused",
  "mismatch",
  "canceled",
  "verification-incomplete",
  "degraded",
  "all-noop",
  "success",
]);
const RESULT_INTEGRITY_STATES = Object.freeze([
  "mismatch",
  "incomplete",
  "not-run",
  "modified",
  "missing",
  "baselined",
  "verified",
]);
const ERROR_MESSAGES = Object.freeze({
  invalid_request: "The desktop request is invalid.",
  unsupported_version: "Restart NamiSync to load a compatible desktop page.",
  unknown_command: "This desktop action is not available.",
  invalid_payload: "The desktop action contains invalid data.",
  request_too_large: "The desktop request is too large.",
  slot_unavailable:
    "That folder selection is no longer available. Choose both folders again.",
  picker_unavailable: "The folder picker could not open. Try again.",
  command_conflict:
    "This action no longer matches its first attempt. Start the action again.",
  planning_refused:
    "NamiSync could not start a plan for those folders. Review both folders and try again.",
  task_unavailable: "That desktop task is no longer available.",
  drain_busy: "That desktop task already has an event request in progress.",
  observation_conflict:
    "That desktop task is already observing different work.",
  bridge_busy: "NamiSync is busy. Try this action again.",
  bridge_unavailable:
    "NamiSync is closing or this desktop page is no longer trusted.",
  internal_error: "NamiSync could not complete the desktop action.",
});
let rawReadiness;
let resolveRawReadiness;
let operationalReadiness;
let resolveOperationalReadiness;
let bridgeGeneration = 0;
let operationalGeneration = -1;
const taskDrains = new Map();

window.addEventListener("pywebviewready", () => {
  bridgeGeneration += 1;
  operationalGeneration = -1;
  const resolve = resolveRawReadiness;
  rawReadiness = undefined;
  resolveRawReadiness = undefined;
  resolve?.();
  for (const task of taskDrains.values()) {
    if (!task.stopped && !task.terminal && task.pendingTerminalUpdate === null) {
      pauseTaskForBridge(task);
    }
  }
});

export class BridgeCommandError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "BridgeCommandError";
    this.code = code;
  }
}

export class BridgeTransportError extends Error {
  constructor(message = "The desktop response could not be confirmed.") {
    super(message);
    this.name = "BridgeTransportError";
  }
}

export class StartPlanUncertainError extends BridgeTransportError {
  constructor(retry) {
    super("The plan-start response could not be confirmed.");
    this.name = "StartPlanUncertainError";
    this.retry = retry;
  }
}

export class TerminalPresentationError extends BridgeTransportError {
  constructor(retry) {
    super("The completed task could not be displayed. Retry displaying it.");
    this.name = "TerminalPresentationError";
    this.retry = retry;
  }
}

export class TerminalSessionReleaseError extends BridgeTransportError {
  constructor(retry) {
    super("The completed task session could not be released. Retry the release.");
    this.name = "TerminalSessionReleaseError";
    this.retry = retry;
  }
}

export class TaskCloseUncertainError extends BridgeTransportError {
  constructor(retry) {
    super("The task-close response could not be confirmed.");
    this.name = "TaskCloseUncertainError";
    this.retry = retry;
  }
}

function bridgeApi() {
  return window.pywebview?.api;
}

export function whenBridgeReady() {
  if (
    operationalGeneration === bridgeGeneration &&
    typeof bridgeApi()?.dispatch === "function"
  ) {
    return Promise.resolve();
  }
  if (!operationalReadiness) {
    operationalReadiness = new Promise((resolve) => {
      resolveOperationalReadiness = resolve;
    });
  }
  return operationalReadiness;
}

export function whenBridgeApiReady() {
  if (typeof bridgeApi()?.dispatch === "function") {
    return Promise.resolve();
  }
  if (!rawReadiness) {
    rawReadiness = new Promise((resolve) => {
      resolveRawReadiness = resolve;
    });
  }
  return rawReadiness;
}

export function markBridgeOperational() {
  if (operationalGeneration === bridgeGeneration) {
    return;
  }
  if (typeof bridgeApi()?.dispatch !== "function") {
    throw new BridgeTransportError();
  }
  operationalGeneration = bridgeGeneration;
  for (const task of taskDrains.values()) {
    if (!task.stopped && !task.terminal && task.pendingTerminalUpdate === null) {
      task.busyRearmUsed = false;
      task.transportFailures = 0;
      rearmTask(task, task.desiredReplayFrom);
    }
  }
  const resolve = resolveOperationalReadiness;
  operationalReadiness = undefined;
  resolveOperationalReadiness = undefined;
  resolve?.();
}

export async function pickFolder(purpose) {
  if (purpose !== "source" && purpose !== "target") {
    throw new TypeError("purpose must be source or target");
  }
  return dispatchInteractive(
    "pick_folder",
    Object.freeze({ purpose }),
    validatePickFolderResult,
  );
}

export function dispatchInteractive(command, payload, validateResult) {
  if (
    typeof command !== "string" ||
    command.length > COMMAND_MAX_LENGTH ||
    !COMMAND_PATTERN.test(command)
  ) {
    throw new TypeError("command must be a bounded lowercase snake name");
  }
  if (typeof validateResult !== "function") {
    throw new TypeError("validateResult must be callable");
  }
  return dispatchAttempt(command, payload, validateResult, null);
}

export async function startPlan(sourceId, targetId, deletionPolicy = null) {
  if (
    typeof sourceId !== "string" ||
    typeof targetId !== "string" ||
    !SLOT_PATTERN.test(sourceId) ||
    !SLOT_PATTERN.test(targetId)
  ) {
    throw new TypeError("startPlan requires source and target slot ids");
  }
  if (
    deletionPolicy !== null &&
    deletionPolicy !== "trash" &&
    deletionPolicy !== "additive"
  ) {
    throw new TypeError("deletionPolicy must be null, trash, or additive");
  }
  const payload = Object.freeze({
    command_id: mintId(),
    source_id: sourceId,
    target_id: targetId,
    deletion_policy: deletionPolicy,
  });
  let automaticReplayUsed = false;
  const submit = async () => {
    try {
      return await startPlanAttempt(payload);
    } catch (error) {
      if (!isUncertainStartPlanFailure(error)) {
        throw error;
      }
      if (!automaticReplayUsed) {
        automaticReplayUsed = true;
        try {
          return await startPlanAttempt(payload);
        } catch (replayError) {
          if (!isUncertainStartPlanFailure(replayError)) {
            throw replayError;
          }
        }
      }
      throw new StartPlanUncertainError(submit);
    }
  };
  return submit();
}

export function startTaskDrain(
  taskId,
  sessionId,
  acceptUpdate,
  acceptRefusal,
) {
  if (
    typeof taskId !== "string" ||
    typeof sessionId !== "string" ||
    !TASK_PATTERN.test(taskId) ||
    !ID_PATTERN.test(sessionId)
  ) {
    throw new TypeError("startTaskDrain requires task and session ids");
  }
  if (typeof acceptUpdate !== "function" || typeof acceptRefusal !== "function") {
    throw new TypeError("startTaskDrain requires update and refusal callbacks");
  }
  if (taskDrains.has(taskId)) {
    throw new TypeError("that task already has a browser drain");
  }
  const task = {
    taskId,
    sessionId,
    acceptUpdate,
    acceptRefusal,
    epoch: 0,
    active: null,
    armScheduled: false,
    armTimer: null,
    scheduledEpoch: null,
    desiredReplayFrom: null,
    lastAcceptedSequence: 0,
    busyRearmUsed: false,
    transportFailures: 0,
    terminal: false,
    pendingTerminalUpdate: null,
    terminalPresentationInProgress: false,
    sessionReleased: false,
    releaseControl: null,
    releaseTimer: null,
    releaseEpoch: 0,
    releaseFailures: 0,
    stopped: false,
  };
  taskDrains.set(taskId, task);
  rearmTask(task, null);

  return () => {
    if (
      !task.stopped &&
      (task.terminal || task.pendingTerminalUpdate !== null)
    ) {
      return;
    }
    if (!task.stopped) {
      stopTask(task);
    }
    if (taskDrains.get(taskId) === task) {
      taskDrains.delete(taskId);
    }
  };
}

export async function readCosmeticSection() {
  const payload = Object.freeze({
    section: APPEARANCE_SECTION,
    value_version: APPEARANCE_VALUE_VERSION,
  });
  try {
    return await readCosmeticSectionAttempt(payload);
  } catch (error) {
    if (!(error instanceof BridgeTransportError)) {
      throw error;
    }
  }
  return readCosmeticSectionAttempt(payload);
}

export function replaceCosmeticSection(expectedRevision, theme) {
  if (!isNonnegativeInteger(expectedRevision)) {
    throw new TypeError("expectedRevision must be a nonnegative safe integer");
  }
  if (!isOneOf(theme, THEMES)) {
    throw new TypeError("theme must be system, light, or dark");
  }
  return dispatchAttempt(
    "replace_cosmetic_section",
    Object.freeze({
      section: APPEARANCE_SECTION,
      value_version: APPEARANCE_VALUE_VERSION,
      expected_revision: expectedRevision,
      value: Object.freeze({ theme }),
    }),
    validateCosmeticReplacementResult,
    COSMETIC_REPLACE_TIMEOUT_MS,
  );
}

export function acknowledgeShellReady() {
  return dispatchAttemptWithReadiness(
    "shell_ready",
    Object.freeze({}),
    validateShellReadyResult,
    SHELL_READY_TIMEOUT_MS,
    whenBridgeApiReady,
  );
}

export function echoReadiness(challenge) {
  if (typeof challenge !== "string" || !ID_PATTERN.test(challenge)) {
    throw new TypeError(
      "readiness challenge must be 32 lowercase hex characters",
    );
  }
  return dispatchAttemptWithReadiness(
    "readiness_echo",
    Object.freeze({ challenge }),
    validateReadinessEchoResult,
    READINESS_ECHO_TIMEOUT_MS,
    whenBridgeApiReady,
  );
}

export async function closeTask(taskId, sessionId) {
  const task = taskDrains.get(taskId);
  if (
    typeof taskId !== "string" ||
    typeof sessionId !== "string" ||
    !TASK_PATTERN.test(taskId) ||
    !ID_PATTERN.test(sessionId) ||
    task?.sessionId !== sessionId ||
    task.stopped
  ) {
    throw new TypeError("closeTask requires a retained task and session");
  }

  const submit = async () => {
    for (
      let attempt = 0;
      attempt <= TASK_CLOSE_RECOVERY_DELAYS_MS.length;
      attempt += 1
    ) {
      try {
        const result = await dispatchAttempt(
          "close_task",
          Object.freeze({ task_id: taskId, session_id: sessionId }),
          (value) => validateTaskIdentityResult(value, task),
          TASK_CLOSE_TIMEOUT_MS,
        );
        stopTask(task);
        return result;
      } catch (error) {
        if (
          !(error instanceof BridgeTransportError) &&
          !isUncertainTaskCommandFailure(error)
        ) {
          throw error;
        }
        if (attempt >= TASK_CLOSE_RECOVERY_DELAYS_MS.length) {
          throw new TaskCloseUncertainError(submit);
        }
        await delay(TASK_CLOSE_RECOVERY_DELAYS_MS[attempt]);
      }
    }
    throw new TaskCloseUncertainError(submit);
  };

  return submit();
}

function startPlanAttempt(payload) {
  return dispatchAttempt(
    "start_plan",
    payload,
    validateStartPlanResult,
    START_PLAN_TIMEOUT_MS,
  );
}

async function dispatchAttempt(command, payload, validateResult, timeoutMs) {
  return dispatchAttemptWithReadiness(
    command,
    payload,
    validateResult,
    timeoutMs,
    whenBridgeReady,
  );
}

function readCosmeticSectionAttempt(payload) {
  return dispatchAttempt(
    "read_cosmetic_section",
    payload,
    validateCosmeticSectionResult,
    COSMETIC_READ_TIMEOUT_MS,
  );
}

async function dispatchAttemptWithReadiness(
  command,
  payload,
  validateResult,
  timeoutMs,
  waitUntilReady,
) {
  return createDispatchAttempt(
    command,
    payload,
    validateResult,
    timeoutMs,
    waitUntilReady,
  ).promise;
}

function createDispatchAttempt(
  command,
  payload,
  validateResult,
  timeoutMs,
  waitUntilReady = whenBridgeReady,
) {
  const requestId = mintId();
  const attempt = {
    cancelled: false,
    rejectCancellation: null,
  };
  const request = JSON.stringify({
    schema_version: SCHEMA_VERSION,
    request_id: requestId,
    command,
    payload,
  });
  return {
    promise: withDeadline(
      dispatchReadyAttempt(
        request,
        requestId,
        validateResult,
        attempt,
        waitUntilReady,
      ),
      timeoutMs,
      () => cancelAttempt(attempt),
    ),
    cancel: () => cancelAttempt(attempt),
  };
}

async function dispatchReadyAttempt(
  request,
  requestId,
  validateResult,
  attempt,
  waitUntilReady,
) {
  await waitUntilReady();
  if (attempt.cancelled) {
    throw new BridgeTransportError();
  }
  const generation = bridgeGeneration;
  let onReincarnation;
  const reincarnated = new Promise((resolve, reject) => {
    void resolve;
    onReincarnation = () => reject(new BridgeTransportError());
    window.addEventListener("pywebviewready", onReincarnation, { once: true });
  });
  const cancelled = new Promise((resolve, reject) => {
    void resolve;
    attempt.rejectCancellation = reject;
  });
  let response;
  try {
    const api = bridgeApi();
    if (
      attempt.cancelled ||
      generation !== bridgeGeneration ||
      typeof api?.dispatch !== "function"
    ) {
      throw new BridgeTransportError();
    }
    // No await occurs between this final cancellation check and dispatch.
    const transport = api.dispatch(request);
    response = await Promise.race([transport, reincarnated, cancelled]);
  } catch (error) {
    if (error instanceof BridgeTransportError) {
      throw error;
    }
    throw new BridgeTransportError();
  } finally {
    attempt.rejectCancellation = null;
    window.removeEventListener("pywebviewready", onReincarnation);
  }
  if (generation !== bridgeGeneration) {
    throw new BridgeTransportError();
  }
  return validateResponse(response, requestId, validateResult);
}

function cancelAttempt(attempt) {
  if (attempt.cancelled) {
    return;
  }
  attempt.cancelled = true;
  attempt.rejectCancellation?.(new BridgeTransportError());
}

async function withDeadline(value, timeoutMs, onDeadline) {
  if (timeoutMs === null) {
    return value;
  }
  let timer;
  try {
    return await Promise.race([
      value,
      new Promise((resolve, reject) => {
        void resolve;
        timer = setTimeout(() => {
          onDeadline();
          reject(new BridgeTransportError());
        }, timeoutMs);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

function validateResponse(response, requestId, validateResult) {
  if (
    !isExactObject(response, ["schema_version", "request_id", "ok", "result"]) &&
    !isExactObject(response, ["schema_version", "request_id", "ok", "error"])
  ) {
    throw new BridgeTransportError();
  }
  if (
    response.schema_version !== SCHEMA_VERSION ||
    typeof response.ok !== "boolean"
  ) {
    throw new BridgeTransportError();
  }
  if (response.ok) {
    if (
      response.request_id !== requestId ||
      !("result" in response) ||
      !validateResult(response.result)
    ) {
      throw new BridgeTransportError();
    }
    return response.result;
  }
  if (
    (response.request_id !== requestId && response.request_id !== null) ||
    !("error" in response) ||
    !isExactObject(response.error, ["code", "message"])
  ) {
    throw new BridgeTransportError();
  }
  const expectedMessage = ERROR_MESSAGES[response.error.code];
  if (expectedMessage === undefined || response.error.message !== expectedMessage) {
    throw new BridgeTransportError();
  }
  throw new BridgeCommandError(response.error.code, expectedMessage);
}

function validatePickFolderResult(value) {
  return (
    value === null ||
    (isExactObject(value, ["id", "display"]) &&
      typeof value.id === "string" &&
      SLOT_PATTERN.test(value.id) &&
      isValidUnicode(value.display))
  );
}

function validateStartPlanResult(value) {
  return (
    isExactObject(value, ["task_id", "request_id", "session_id"]) &&
    typeof value.task_id === "string" &&
    typeof value.request_id === "string" &&
    typeof value.session_id === "string" &&
    TASK_PATTERN.test(value.task_id) &&
    ID_PATTERN.test(value.request_id) &&
    ID_PATTERN.test(value.session_id)
  );
}

function rearmTask(task, replayFrom, delayMs = 0) {
  if (task.stopped || task.terminal || task.pendingTerminalUpdate !== null) {
    return;
  }
  task.epoch += 1;
  task.desiredReplayFrom = replayFrom;
  task.active?.control.cancel();
  task.active = null;
  cancelTaskArm(task);
  if (operationalGeneration !== bridgeGeneration) {
    if (task.desiredReplayFrom === null) {
      task.desiredReplayFrom = task.lastAcceptedSequence + 1;
    }
    return;
  }
  const epoch = task.epoch;
  task.armScheduled = true;
  task.scheduledEpoch = epoch;
  const arm = () => {
    if (task.scheduledEpoch !== epoch) {
      return;
    }
    task.armScheduled = false;
    task.armTimer = null;
    task.scheduledEpoch = null;
    if (
      task.stopped ||
      task.terminal ||
      task.pendingTerminalUpdate !== null ||
      taskDrains.get(task.taskId) !== task
    ) {
      return;
    }
    try {
      runTaskDrain(task, epoch, task.desiredReplayFrom);
    } catch (error) {
      stopTaskWithRefusal(
        task,
        error instanceof BridgeTransportError ? error : new BridgeTransportError(),
      );
    }
  };
  if (delayMs > 0) {
    task.armTimer = setTimeout(arm, delayMs);
  } else {
    queueMicrotask(arm);
  }
}

function cancelTaskArm(task) {
  if (task.armTimer !== null) {
    clearTimeout(task.armTimer);
  }
  task.armTimer = null;
  task.armScheduled = false;
  task.scheduledEpoch = null;
}

function runTaskDrain(task, epoch, replayFrom) {
  const drainId = mintId();
  const control = createDispatchAttempt(
    "next_events",
    Object.freeze({
      task_id: task.taskId,
      session_id: task.sessionId,
      drain_id: drainId,
      replay_from: replayFrom,
    }),
    (value) => validateTaskDrainResult(value, task, drainId),
    DRAIN_TIMEOUT_MS,
  );
  const active = { epoch, replayFrom, drainId, control };
  task.active = active;
  void control.promise.then(
    (result) => settleTaskDrain(task, active, result),
    (error) => refuseTaskDrain(task, active, error),
  );
}

function isCurrentTaskDrain(task, active) {
  return (
    !task.stopped &&
    !task.terminal &&
    taskDrains.get(task.taskId) === task &&
    task.epoch === active.epoch &&
    task.active === active
  );
}

function settleTaskDrain(task, active, result) {
  if (!isCurrentTaskDrain(task, active)) {
    return;
  }
  task.active = null;
  task.busyRearmUsed = false;
  task.transportFailures = 0;
  for (let index = 0; index < result.updates.length; index += 1) {
    if (task.stopped || task.terminal || task.epoch !== active.epoch) {
      return;
    }
    const update = result.updates[index];
    if (update.update_type === "record") {
      presentTerminalUpdate(task, update);
      return;
    }
    const event = update.event;
    if (event.body_type === "Gap") {
      if (!deliverTaskUpdate(task, update)) {
        return;
      }
      const missed = event.body.first_missed_seq;
      const matchingLeadingRecoveryGap =
        index === 0 &&
        active.replayFrom !== null &&
        missed === active.replayFrom;
      if (matchingLeadingRecoveryGap) {
        continue;
      }
      rearmTask(task, missed);
      return;
    }
    if (event.sequence <= task.lastAcceptedSequence) {
      continue;
    }
    task.lastAcceptedSequence = event.sequence;
    if (!deliverTaskUpdate(task, update)) {
      return;
    }
  }
  rearmTask(task, null);
}

function validateCosmeticSectionResult(value) {
  return (
    isExactObject(value, [
      "section",
      "value_version",
      "revision",
      "dirty",
      "value",
    ]) && validateCosmeticSectionFields(value)
  );
}

function validateCosmeticReplacementResult(value) {
  return (
    isExactObject(value, [
      "section",
      "value_version",
      "revision",
      "dirty",
      "value",
      "disposition",
    ]) &&
    validateCosmeticSectionFields(value) &&
    isOneOf(value.disposition, COSMETIC_DISPOSITIONS)
  );
}

function validateCosmeticSectionFields(value) {
  return (
    value.section === APPEARANCE_SECTION &&
    value.value_version === APPEARANCE_VALUE_VERSION &&
    isNonnegativeInteger(value.revision) &&
    typeof value.dirty === "boolean" &&
    isExactObject(value.value, ["theme"]) &&
    isOneOf(value.value.theme, THEMES)
  );
}

function pauseTaskForBridge(task) {
  task.epoch += 1;
  task.desiredReplayFrom = task.lastAcceptedSequence + 1;
  task.active?.control.cancel();
  task.active = null;
  cancelTaskArm(task);
}

function validateShellReadyResult(value) {
  return isExactObject(value, ["acknowledged"]) && value.acknowledged === true;
}

function validateReadinessEchoResult(value) {
  return isExactObject(value, ["acknowledged"])
    && typeof value.acknowledged === "boolean";
}

function presentTerminalUpdate(task, update) {
  if (task.stopped || task.terminal || taskDrains.get(task.taskId) !== task) {
    return;
  }
  if (task.pendingTerminalUpdate === null) {
    task.pendingTerminalUpdate = freezeJsonValue(cloneJsonValue(update));
  }
  if (task.terminalPresentationInProgress) {
    return;
  }
  task.terminalPresentationInProgress = true;
  try {
    task.acceptUpdate(cloneJsonValue(task.pendingTerminalUpdate));
  } catch (_error) {
    task.terminalPresentationInProgress = false;
    reportTaskRefusal(
      task,
      new TerminalPresentationError(() => retryTerminalPresentation(task)),
    );
    return;
  }
  task.terminalPresentationInProgress = false;
  task.pendingTerminalUpdate = null;
  task.terminal = true;
  beginTaskRelease(task);
}

function retryTerminalPresentation(task) {
  if (
    task.stopped ||
    task.terminal ||
    task.pendingTerminalUpdate === null ||
    taskDrains.get(task.taskId) !== task
  ) {
    return;
  }
  presentTerminalUpdate(task, task.pendingTerminalUpdate);
}

function deliverTaskUpdate(task, update) {
  try {
    task.acceptUpdate(update);
    return true;
  } catch (_error) {
    stopTaskWithRefusal(
      task,
      new BridgeTransportError("The desktop update could not be applied."),
    );
    return false;
  }
}

function refuseTaskDrain(task, active, error) {
  if (!isCurrentTaskDrain(task, active)) {
    return;
  }
  task.active = null;
  if (error instanceof BridgeCommandError) {
    if (error.code === "drain_busy" && !task.busyRearmUsed) {
      task.busyRearmUsed = true;
      rearmTask(task, active.replayFrom);
      return;
    }
    if (!isUncertainTaskCommandFailure(error)) {
      stopTaskWithRefusal(task, error);
      return;
    }
  }
  task.busyRearmUsed = false;
  const failureIndex = task.transportFailures;
  if (failureIndex >= DRAIN_RECOVERY_DELAYS_MS.length) {
    stopTaskWithRefusal(task, new BridgeTransportError());
    return;
  }
  task.transportFailures += 1;
  rearmTask(
    task,
    task.lastAcceptedSequence + 1,
    DRAIN_RECOVERY_DELAYS_MS[failureIndex],
  );
}

function stopTaskWithRefusal(task, error) {
  stopTask(task);
  reportTaskRefusal(task, error);
}

function reportTaskRefusal(task, error) {
  try {
    task.acceptRefusal(error);
  } catch (_callbackError) {
    // Presentation failure cannot mutate retained native authority.
  }
}

function cloneJsonValue(value) {
  if (Array.isArray(value)) {
    return value.map((item) => cloneJsonValue(item));
  }
  if (value !== null && typeof value === "object") {
    const clone = {};
    for (const [key, item] of Object.entries(value)) {
      clone[key] = cloneJsonValue(item);
    }
    return clone;
  }
  return value;
}

function freezeJsonValue(value) {
  if (value !== null && typeof value === "object") {
    for (const item of Object.values(value)) {
      freezeJsonValue(item);
    }
    Object.freeze(value);
  }
  return value;
}

function stopTask(task) {
  task.stopped = true;
  task.epoch += 1;
  task.active?.control.cancel();
  task.active = null;
  cancelTaskArm(task);
  task.releaseEpoch += 1;
  task.releaseControl?.cancel();
  task.releaseControl = null;
  if (task.releaseTimer !== null) {
    clearTimeout(task.releaseTimer);
  }
  task.releaseTimer = null;
  if (taskDrains.get(task.taskId) === task) {
    taskDrains.delete(task.taskId);
  }
}

function beginTaskRelease(task) {
  if (task.releaseControl !== null || task.releaseTimer !== null) {
    return;
  }
  task.releaseFailures = 0;
  runTaskRelease(task);
}

function runTaskRelease(task) {
  if (
    task.stopped ||
    !task.terminal ||
    task.sessionReleased ||
    taskDrains.get(task.taskId) !== task
  ) {
    return;
  }
  const epoch = task.releaseEpoch + 1;
  task.releaseEpoch = epoch;
  let control;
  try {
    control = createDispatchAttempt(
      "release_terminal_session",
      Object.freeze({ task_id: task.taskId, session_id: task.sessionId }),
      (value) => validateTaskIdentityResult(value, task),
      SESSION_RELEASE_TIMEOUT_MS,
    );
  } catch (_error) {
    refuseTaskRelease(task, epoch, new BridgeTransportError());
    return;
  }
  task.releaseControl = control;
  void control.promise.then(
    () => settleTaskRelease(task, epoch),
    (error) => refuseTaskRelease(task, epoch, error),
  );
}

function isCurrentTaskRelease(task, epoch) {
  return (
    !task.stopped &&
    task.terminal &&
    !task.sessionReleased &&
    taskDrains.get(task.taskId) === task &&
    task.releaseEpoch === epoch
  );
}

function settleTaskRelease(task, epoch) {
  if (!isCurrentTaskRelease(task, epoch)) {
    return;
  }
  task.releaseControl = null;
  task.sessionReleased = true;
}

function refuseTaskRelease(task, epoch, error) {
  if (!isCurrentTaskRelease(task, epoch)) {
    return;
  }
  task.releaseControl = null;
  const uncertain =
    error instanceof BridgeTransportError ||
    isUncertainTaskCommandFailure(error);
  if (!uncertain) {
    reportTaskRefusal(
      task,
      new TerminalSessionReleaseError(() => beginTaskRelease(task)),
    );
    return;
  }
  const failureIndex = task.releaseFailures;
  if (failureIndex >= SESSION_RELEASE_RECOVERY_DELAYS_MS.length) {
    reportTaskRefusal(
      task,
      new TerminalSessionReleaseError(() => beginTaskRelease(task)),
    );
    return;
  }
  task.releaseFailures += 1;
  const expectedEpoch = task.releaseEpoch;
  task.releaseTimer = setTimeout(() => {
    task.releaseTimer = null;
    if (isCurrentTaskRelease(task, expectedEpoch)) {
      runTaskRelease(task);
    }
  }, SESSION_RELEASE_RECOVERY_DELAYS_MS[failureIndex]);
}

function isUncertainTaskCommandFailure(error) {
  return (
    error instanceof BridgeCommandError &&
    (error.code === "bridge_busy" || error.code === "internal_error")
  );
}

function validateTaskIdentityResult(value, task) {
  return (
    isExactObject(value, ["task_id", "session_id"]) &&
    value.task_id === task.taskId &&
    value.session_id === task.sessionId
  );
}

function delay(milliseconds) {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}

function validateTaskDrainResult(value, task, drainId) {
  return (
    isExactObject(value, ["task_id", "session_id", "drain_id", "updates"]) &&
    value.task_id === task.taskId &&
    value.session_id === task.sessionId &&
    value.drain_id === drainId &&
    Array.isArray(value.updates) &&
    value.updates.length <= DRAIN_MAX_UPDATES &&
    validateTaskUpdates(
      value.updates,
      task.sessionId,
      task.lastAcceptedSequence,
    )
  );
}

function validateTaskUpdates(updates, sessionId, lastAcceptedSequence) {
  let lastSequence = lastAcceptedSequence;
  let sawTerminalEvent = false;
  let sawRecord = false;
  for (let index = 0; index < updates.length; index += 1) {
    const update = updates[index];
    if (!validateTaskUpdate(update, sessionId)) {
      return false;
    }
    if (update.update_type === "record") {
      if (sawRecord || index !== updates.length - 1) {
        return false;
      }
      sawRecord = true;
      continue;
    }
    if (
      sawRecord ||
      sawTerminalEvent ||
      update.event.sequence <= lastSequence
    ) {
      return false;
    }
    if (
      update.event.body_type === "Gap" &&
      (update.event.body.first_missed_seq <= lastSequence ||
        update.event.body.first_missed_seq > update.event.sequence)
    ) {
      return false;
    }
    lastSequence = update.event.sequence;
    if (update.event.body_type === "Terminal") {
      sawTerminalEvent = true;
    }
  }
  return true;
}

function validateTaskUpdate(update, sessionId) {
  if (
    isExactObject(update, ["update_type", "event"]) &&
    update.update_type === "event"
  ) {
    return validateSessionEvent(update.event, sessionId);
  }
  if (
    isExactObject(update, ["update_type", "record"]) &&
    update.update_type === "record"
  ) {
    return validateSessionRecord(update.record, sessionId);
  }
  return false;
}

function validateSessionEvent(event, sessionId) {
  if (
    !isExactObject(event, ["session_id", "sequence", "at", "body_type", "body"]) ||
    event.session_id !== sessionId ||
    !Number.isSafeInteger(event.sequence) ||
    event.sequence < 1 ||
    !isUtcTimestamp(event.at) ||
    !isPlainJsonObject(event.body)
  ) {
    return false;
  }
  switch (event.body_type) {
    case "StateChanged":
      return (
        isExactObject(event.body, ["state"]) &&
        isOneOf(event.body.state, SESSION_STATES)
      );
    case "PhaseChanged":
      return (
        isExactObject(event.body, ["phase"]) &&
        isValidNonemptyText(event.body.phase)
      );
    case "Progress":
      return validateProgress(event.body);
    case "ItemOutcome":
      return validateOperationItem(event.body);
    case "IntegrityOutcome":
      return validateIntegrityItem(event.body);
    case "Gap":
      return (
        isExactObject(event.body, ["first_missed_seq"]) &&
        Number.isSafeInteger(event.body.first_missed_seq) &&
        event.body.first_missed_seq > 0
      );
    case "Terminal":
      return (
        isExactObject(event.body, ["result"]) &&
        validateCoreOperationResult(event.body.result)
      );
    default:
      return false;
  }
}

function validateSessionRecord(record, sessionId) {
  return (
    isExactObject(record, [
      "session_id",
      "kind",
      "state",
      "supports_pause",
      "created_at",
      "started_at",
      "ended_at",
      "result",
    ]) &&
    record.session_id === sessionId &&
    record.kind === "sync-plan" &&
    isOneOf(record.state, TERMINAL_STATES) &&
    record.supports_pause === false &&
    isUtcTimestamp(record.created_at) &&
    (record.started_at === null || isUtcTimestamp(record.started_at)) &&
    isUtcTimestamp(record.ended_at) &&
    (record.result === null ||
      (validateOperationResultView(record.result) &&
        record.state ===
          (record.result.canceled ? "canceled" : record.result.filesystem)))
  );
}

function validateProgress(value) {
  if (
    !(
      isExactObject(value, [
        "items_done",
        "items_total",
        "bytes_done",
        "bytes_total",
        "current_path",
        "item_id",
        "item_type",
        "item_bytes_done",
        "item_bytes_total",
      ]) &&
      isNonnegativeInteger(value.items_done) &&
      isNullableNonnegativeInteger(value.items_total) &&
      isNonnegativeInteger(value.bytes_done) &&
      isNullableNonnegativeInteger(value.bytes_total) &&
      (value.items_total === null || value.items_done <= value.items_total) &&
      (value.bytes_total === null || value.bytes_done <= value.bytes_total) &&
      isNullableText(value.current_path)
    )
  ) {
    return false;
  }
  const identityAbsent = value.item_id === null && value.item_type === null;
  const identityPresent =
    isValidNonemptyText(value.item_id) &&
    (value.item_type === "operation" || value.item_type === "integrity");
  if (!identityAbsent && !identityPresent) {
    return false;
  }
  const itemBytesAbsent =
    value.item_bytes_done === null && value.item_bytes_total === null;
  const itemBytesPresent =
    identityPresent &&
    isNonnegativeInteger(value.item_bytes_done) &&
    isNonnegativeInteger(value.item_bytes_total) &&
    value.item_bytes_done <= value.item_bytes_total;
  return itemBytesAbsent || itemBytesPresent;
}

function validateOperationItem(value) {
  return (
    isExactObject(value, [
      "item_type",
      "phase",
      "item_id",
      "kind",
      "path",
      "result",
      "reason",
      "detail",
    ]) &&
    value.item_type === "operation" &&
    value.phase === "execute" &&
    isValidNonemptyText(value.item_id) &&
    isValidNonemptyText(value.kind) &&
    isValidText(value.path) &&
    isOneOf(value.result, OPERATION_OUTCOMES) &&
    isNullableText(value.reason) &&
    isPlainJsonObject(value.detail) &&
    isJsonValue(value.detail)
  );
}

function validateIntegrityItem(value) {
  return (
    isExactObject(value, [
      "item_type",
      "phase",
      "item_id",
      "row_id",
      "location_id",
      "kind",
      "path",
      "result",
      "reason",
      "detail",
      "read_strategy",
      "recording",
      "record_disposition",
    ]) &&
    value.item_type === "integrity" &&
    isOneOf(value.phase, INTEGRITY_MODES) &&
    isValidNonemptyText(value.item_id) &&
    ((value.row_id === null && value.location_id === null) ||
      (isValidNonemptyText(value.row_id) &&
        isValidNonemptyText(value.location_id))) &&
    value.kind === "integrity" &&
    isValidNonemptyText(value.path) &&
    isOneOf(value.result, INTEGRITY_RESULTS) &&
    (value.reason === null || isOneOf(value.reason, INTEGRITY_REASONS)) &&
    isNullableText(value.detail) &&
    (value.read_strategy === null ||
      isOneOf(value.read_strategy, READ_STRATEGIES)) &&
    isOneOf(value.recording, RECORDING_STATES) &&
    (value.record_disposition === null ||
      isOneOf(value.record_disposition, RECORD_DISPOSITIONS))
  );
}

function validatePhaseResult(value) {
  return (
    isExactObject(value, [
      "phase",
      "status",
      "items_done",
      "items_total",
      "bytes_done",
      "bytes_total",
      "error",
    ]) &&
    isValidNonemptyText(value.phase) &&
    isOneOf(value.status, PHASE_STATES) &&
    isNonnegativeInteger(value.items_done) &&
    isNullableNonnegativeInteger(value.items_total) &&
    isNonnegativeInteger(value.bytes_done) &&
    isNullableNonnegativeInteger(value.bytes_total) &&
    (value.items_total === null || value.items_done <= value.items_total) &&
    (value.bytes_total === null || value.bytes_done <= value.bytes_total) &&
    isNullableText(value.error)
  );
}

function validateCoreOperationResult(value) {
  return (
    isExactObject(value, [
      "status",
      "recording",
      "audit",
      "disposition",
      "canceled",
      "items",
      "phases",
      "bytes_done",
      "bytes_total",
      "error",
    ]) &&
    isOneOf(value.status, TERMINAL_STATES) &&
    isOneOf(value.recording, RECORDING_STATES) &&
    isOneOf(value.audit, RECORDING_STATES) &&
    isOneOf(value.disposition, DISPOSITIONS) &&
    typeof value.canceled === "boolean" &&
    Array.isArray(value.items) &&
    value.items.every(validateResultItem) &&
    Array.isArray(value.phases) &&
    value.phases.every(validatePhaseResult) &&
    isNonnegativeInteger(value.bytes_done) &&
    isNonnegativeInteger(value.bytes_total) &&
    value.bytes_done <= value.bytes_total &&
    (value.status !== "canceled" || value.canceled) &&
    !(value.status === "refused" && value.canceled) &&
    (value.status !== "refused" || value.disposition === "unrun") &&
    (value.error === null ||
      (isExactObject(value.error, ["type_name", "message"]) &&
        isValidText(value.error.type_name) &&
        isValidText(value.error.message)))
  );
}

function validateOperationResultView(value) {
  return (
    isExactObject(value, [
      "headline",
      "filesystem",
      "integrity",
      "recording",
      "audit",
      "disposition",
      "canceled",
      "items",
      "phases",
      "bytes_done",
      "bytes_total",
      "error",
    ]) &&
    isOneOf(value.headline, RESULT_HEADLINES) &&
    isOneOf(value.filesystem, TERMINAL_STATES) &&
    isOneOf(value.integrity, RESULT_INTEGRITY_STATES) &&
    isOneOf(value.recording, RECORDING_STATES) &&
    isOneOf(value.audit, RECORDING_STATES) &&
    isOneOf(value.disposition, DISPOSITIONS) &&
    typeof value.canceled === "boolean" &&
    Array.isArray(value.items) &&
    value.items.every(validateResultItem) &&
    Array.isArray(value.phases) &&
    value.phases.every(validatePhaseResult) &&
    isNonnegativeInteger(value.bytes_done) &&
    isNonnegativeInteger(value.bytes_total) &&
    value.bytes_done <= value.bytes_total &&
    (value.filesystem !== "canceled" || value.canceled) &&
    !(value.filesystem === "refused" && value.canceled) &&
    (value.filesystem !== "refused" || value.disposition === "unrun") &&
    isNullableText(value.error)
  );
}

function validateResultItem(value) {
  if (!isPlainJsonObject(value)) {
    return false;
  }
  return value.item_type === "operation"
    ? validateOperationItem(value)
    : value.item_type === "integrity" && validateIntegrityItem(value);
}

function isNonnegativeInteger(value) {
  return Number.isSafeInteger(value) && value >= 0;
}

function isNullableNonnegativeInteger(value) {
  return value === null || isNonnegativeInteger(value);
}

function isValidText(value) {
  return typeof value === "string" && isValidUnicode(value);
}

function isNullableText(value) {
  return value === null || isValidText(value);
}

function isValidNonemptyText(value) {
  return isValidText(value) && value.length > 0;
}

function isOneOf(value, choices) {
  return typeof value === "string" && choices.includes(value);
}

function isUtcTimestamp(value) {
  return (
    typeof value === "string" &&
    isValidUnicode(value) &&
    (value.endsWith("Z") || value.endsWith("+00:00")) &&
    Number.isFinite(Date.parse(value))
  );
}

function isPlainJsonObject(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.getPrototypeOf(value) === Object.prototype
  );
}

function isJsonValue(value) {
  if (value === null || typeof value === "boolean") {
    return true;
  }
  if (typeof value === "string") {
    return isValidUnicode(value);
  }
  if (typeof value === "number") {
    return Number.isFinite(value);
  }
  if (Array.isArray(value)) {
    return value.every(isJsonValue);
  }
  if (!isPlainJsonObject(value)) {
    return false;
  }
  return Object.entries(value).every(
    ([key, item]) => isValidUnicode(key) && isJsonValue(item),
  );
}

function isExactObject(value, keys) {
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    Object.getPrototypeOf(value) !== Object.prototype
  ) {
    return false;
  }
  const actual = Object.keys(value);
  return actual.length === keys.length && keys.every((key) => actual.includes(key));
}

function isValidUnicode(value) {
  if (typeof value !== "string") {
    return false;
  }
  for (let index = 0; index < value.length; index += 1) {
    const unit = value.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (next < 0xdc00 || next > 0xdfff) {
        return false;
      }
      index += 1;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      return false;
    }
  }
  return true;
}

function isUncertainStartPlanFailure(error) {
  return (
    error instanceof BridgeTransportError ||
    (error instanceof BridgeCommandError && error.code === "internal_error")
  );
}

function mintId() {
  let value = "";
  try {
    const cryptography = globalThis.crypto;
    if (typeof cryptography?.getRandomValues !== "function") {
      throw new TypeError("secure random values are unavailable");
    }
    const bytes = new Uint8Array(16);
    cryptography.getRandomValues(bytes);
    for (const byte of bytes) {
      value += byte.toString(16).padStart(2, "0");
    }
  } catch {
    throw new BridgeTransportError("The desktop request id could not be created.");
  }
  if (!ID_PATTERN.test(value)) {
    throw new BridgeTransportError("The desktop request id could not be created.");
  }
  return value;
}
