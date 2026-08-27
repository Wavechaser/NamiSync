const BRIDGE_SCHEMA_VERSION = 1;
const CORE_EVENT_SCHEMA_VERSION = 5;
const MAX_RELIABLE_EVENT_CANONICAL_BYTES = 1_048_576;
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
    progressState: emptyProgressReducerState(),
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

export async function readCosmeticSection(appliedPresentationRevision = null) {
  if (
    appliedPresentationRevision !== null
    && (
      !Number.isSafeInteger(appliedPresentationRevision)
      || appliedPresentationRevision < 0
    )
  ) {
    throw new TypeError("Applied appearance revision is invalid");
  }
  const payload = Object.freeze({
    section: APPEARANCE_SECTION,
    value_version: APPEARANCE_VALUE_VERSION,
    applied_presentation_revision: appliedPresentationRevision,
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
    schema_version: BRIDGE_SCHEMA_VERSION,
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
    response.schema_version !== BRIDGE_SCHEMA_VERSION ||
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
    (value) => validateTaskDrainResult(value, task, drainId, replayFrom),
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
      task.progressState = reduceProgressState(task.progressState, update);
      presentTerminalUpdate(task, update);
      return;
    }
    const event = update.event;
    if (event.body_type === "Gap") {
      task.progressState = reduceProgressState(task.progressState, update);
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
    task.progressState = reduceProgressState(task.progressState, update);
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
    task.acceptUpdate(
      cloneJsonValue(task.pendingTerminalUpdate),
      progressStateView(task.progressState),
    );
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
    task.acceptUpdate(update, progressStateView(task.progressState));
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

function emptyProgressReducerState() {
  return freezeJsonValue({
    phase: null,
    phaseAuthority: "unknown",
    progress: null,
    activeItem: null,
  });
}

function progressStateView(state) {
  return freezeJsonValue({
    phase: state.phase,
    phaseAuthority: state.phaseAuthority,
    progress: cloneJsonValue(state.progress),
    activeItem: cloneJsonValue(state.activeItem),
  });
}

function progressActiveItem(progress) {
  if (progress.item_id === null) {
    return null;
  }
  return freezeJsonValue({
    item_id: progress.item_id,
    item_type: progress.item_type,
    item_attempt_id: progress.item_attempt_id,
    item_bytes_done: progress.item_bytes_done,
    item_bytes_total: progress.item_bytes_total,
  });
}

function sameActiveIdentity(left, right) {
  return (
    left.item_id === right.item_id &&
    left.item_type === right.item_type
  );
}

function progressAggregateAdvances(previous, current) {
  if (
    current.items_done < previous.items_done ||
    BigInt(current.bytes_done) < BigInt(previous.bytes_done)
  ) {
    return false;
  }
  if (
    previous.items_total !== null &&
    current.items_total !== previous.items_total
  ) {
    return false;
  }
  if (
    previous.bytes_total !== null &&
    current.bytes_total === null
  ) {
    return false;
  }
  if (
    previous.phase === "execute" &&
    previous.bytes_total !== null &&
    current.bytes_total !== previous.bytes_total
  ) {
    return false;
  }
  return !(
    previous.phase !== "execute" &&
    previous.bytes_total !== null &&
    BigInt(current.bytes_total) < BigInt(previous.bytes_total)
  );
}

function sameAttemptAdvances(previous, current) {
  const previousDeterminate = previous.item_bytes_done !== null;
  const currentDeterminate = current.item_bytes_done !== null;
  if (!previousDeterminate) {
    return !currentDeterminate;
  }
  if (!currentDeterminate) {
    return true;
  }
  return (
    BigInt(current.item_bytes_done) >= BigInt(previous.item_bytes_done) &&
    current.item_bytes_total === previous.item_bytes_total
  );
}

function reduceProgressSnapshot(state, progress) {
  let domainState = state;
  if (
    state.phase !== null &&
    progress.phase !== state.phase
  ) {
    if (state.phaseAuthority === "phase_changed") {
      return null;
    }
    domainState = emptyProgressReducerState();
  }
  if (
    domainState.progress !== null &&
    !progressAggregateAdvances(domainState.progress, progress)
  ) {
    return null;
  }
  const nextActive = progressActiveItem(progress);
  if (nextActive !== null) {
    const previousActive = domainState.activeItem;
    if (previousActive !== null) {
      const previousAttempt = previousActive.item_attempt_id;
      const nextAttempt = nextActive.item_attempt_id;
      if (sameActiveIdentity(previousActive, nextActive)) {
        if (previousAttempt !== null && nextAttempt === null) {
          return null;
        }
        if (
          previousAttempt !== null &&
          nextAttempt === previousAttempt &&
          !sameAttemptAdvances(previousActive, nextActive)
        ) {
          return null;
        }
      } else if (
        previousAttempt !== null &&
        nextAttempt === previousAttempt
      ) {
        return null;
      }
    } else if (
      domainState.progress !== null &&
      domainState.progress.item_id !== null
    ) {
      const previousSnapshotActive = progressActiveItem(domainState.progress);
      if (
        sameActiveIdentity(previousSnapshotActive, nextActive) ||
        (
          previousSnapshotActive.item_attempt_id !== null &&
          nextActive.item_attempt_id === previousSnapshotActive.item_attempt_id
        )
      ) {
        return null;
      }
    }
  }

  return freezeJsonValue({
    phase: progress.phase,
    phaseAuthority:
      domainState.phaseAuthority === "phase_changed"
        ? "phase_changed"
        : "progress",
    progress: cloneJsonValue(progress),
    activeItem: nextActive,
  });
}

function reduceItemOutcome(state, event) {
  if (state.phase !== event.body.phase) {
    return state;
  }
  const outcomeIdentity = {
    item_id: event.body.item_id,
    item_type: event.body.item_type,
  };
  const matchesActive =
    state.activeItem !== null &&
    (
      sameActiveIdentity(state.activeItem, outcomeIdentity) ||
      (
        state.phase === "verify" &&
        event.body_type === "IntegrityOutcome" &&
        state.activeItem.item_type === "operation" &&
        state.activeItem.item_id === outcomeIdentity.item_id
      )
    );
  if (!matchesActive) {
    return state;
  }
  return freezeJsonValue({
    phase: state.phase,
    phaseAuthority: state.phaseAuthority,
    progress: state.progress,
    activeItem: null,
  });
}

function reduceProgressState(state, update) {
  if (update.update_type === "record") {
    return emptyProgressReducerState();
  }
  const event = update.event;
  switch (event.body_type) {
    case "PhaseChanged":
      if (state.phase === event.body.phase) {
        return freezeJsonValue({
          phase: state.phase,
          phaseAuthority: "phase_changed",
          progress: state.progress,
          activeItem: state.activeItem,
        });
      }
      return freezeJsonValue({
        phase: event.body.phase,
        phaseAuthority: "phase_changed",
        progress: null,
        activeItem: null,
      });
    case "Progress":
      return reduceProgressSnapshot(state, event.body);
    case "ItemOutcome":
    case "IntegrityOutcome":
      return reduceItemOutcome(state, event);
    case "Gap":
    case "Terminal":
      return emptyProgressReducerState();
    default:
      return state;
  }
}

function preflightProgressUpdates(updates, initialState, replayFrom) {
  let state = freezeJsonValue(cloneJsonValue(initialState));
  for (let index = 0; index < updates.length; index += 1) {
    const update = updates[index];
    const nextState = reduceProgressState(state, update);
    if (nextState === null) {
      return false;
    }
    state = nextState;
    if (
      update.update_type === "event" &&
      update.event.body_type === "Gap" &&
      !(
        index === 0 &&
        replayFrom !== null &&
        update.event.body.first_missed_seq === replayFrom
      )
    ) {
      break;
    }
  }
  return true;
}

function validateTaskDrainResult(value, task, drainId, replayFrom) {
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
    ) &&
    preflightProgressUpdates(
      value.updates,
      task.progressState,
      replayFrom,
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
    return validateLiveSessionEvent(update.event, sessionId);
  }
  if (
    isExactObject(update, ["update_type", "record"]) &&
    update.update_type === "record"
  ) {
    return validateSessionRecord(update.record, sessionId);
  }
  return false;
}

function validateLiveSessionEvent(event, sessionId) {
  return validateSessionEventV5(event, sessionId);
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
    validateOperationResultView(record.result) &&
    record.state ===
      (record.result.canceled ? "canceled" : record.result.filesystem)
  );
}

function validateCancellationTruth(status, disposition, canceled, phases) {
  const execute = phases.find((phase) => phase.phase === "execute");
  const verify = phases.find((phase) => phase.phase === "verify");
  if (status === "canceled" && (!canceled || execute?.status === "completed")) {
    return false;
  }
  if (status === "refused") {
    return !canceled && disposition === "unrun";
  }
  if (canceled && (status === "completed" || status === "failed")) {
    return (
      disposition === "ran" &&
      execute?.status === status &&
      verify?.status === "canceled"
    );
  }
  return true;
}

function validateOperationResultView(value) {
  if (
    !isExactObject(value, [
      "headline",
      "filesystem",
      "integrity",
      "recording",
      "audit",
      "disposition",
      "canceled",
      "phases",
      "bytes_done",
      "bytes_total",
      "error",
      "recording_degraded_items",
      "recording_issues",
      "omitted_detail_count",
      "presentation_omitted_detail_count",
      "review_refusal",
    ]) ||
    !isOneOf(value.headline, RESULT_HEADLINES) ||
    !isOneOf(value.filesystem, TERMINAL_STATES) ||
    !isOneOf(value.integrity, RESULT_INTEGRITY_STATES) ||
    !isOneOf(value.recording, RECORDING_STATES) ||
    !isOneOf(value.audit, RECORDING_STATES) ||
    !isOneOf(value.disposition, DISPOSITIONS) ||
    typeof value.canceled !== "boolean" ||
    !Array.isArray(value.phases) ||
    value.phases.length > 3 ||
    !value.phases.every(validatePhaseResultV5) ||
    new Set(value.phases.map((phase) => phase.phase)).size !==
      value.phases.length ||
    !isScalar64(value.bytes_done) ||
    !isScalar64(value.bytes_total) ||
    BigInt(value.bytes_done) > BigInt(value.bytes_total) ||
    !(value.error === null || isBoundedV5Text(value.error, false)) ||
    !isNonnegativeInteger(value.recording_degraded_items) ||
    !Array.isArray(value.recording_issues) ||
    value.recording_issues.length > 5 ||
    !value.recording_issues.every(validateRecordingIssueV5) ||
    new Set(value.recording_issues.map((issue) => issue.reason)).size !==
      value.recording_issues.length ||
    !isNonnegativeInteger(value.omitted_detail_count) ||
    !isNonnegativeInteger(value.presentation_omitted_detail_count) ||
    !(
      value.review_refusal === null ||
      validateReviewFactV5(value.review_refusal)
    )
  ) {
    return false;
  }
  const expectedRecording =
    value.recording_degraded_items > 0 || value.recording_issues.length > 0
      ? "degraded"
      : "ok";
  if (
    value.recording !== expectedRecording ||
    !validateCancellationTruth(
      value.filesystem, value.disposition, value.canceled, value.phases,
    )
  ) {
    return false;
  }
  return (
    value.review_refusal === null ||
    (value.filesystem === "refused" &&
      value.disposition === "unrun" &&
      !value.canceled &&
      value.bytes_done === "0" &&
      value.bytes_total === "0" &&
      value.phases.length === 0 &&
      value.recording_degraded_items === 0 &&
      value.recording_issues.length === 0 &&
      value.omitted_detail_count === 0 &&
      value.presentation_omitted_detail_count === 0 &&
      value.error === null)
  );
}

export function validateSessionEventV5(event, sessionId) {
  if (
    !isExactObject(event, [
      "session_id",
      "sequence",
      "at",
      "schema_version",
      "body_type",
      "body",
    ]) ||
    event.session_id !== sessionId ||
    !ID_PATTERN.test(event.session_id) ||
    !Number.isSafeInteger(event.sequence) ||
    event.sequence < 1 ||
    !isUtcTimestamp(event.at) ||
    event.schema_version !== CORE_EVENT_SCHEMA_VERSION ||
    !isPlainJsonObject(event.body)
  ) {
    return false;
  }
  let validBody;
  switch (event.body_type) {
    case "StateChanged":
      validBody = (
        isExactObject(event.body, ["state"]) &&
        isOneOf(event.body.state, SESSION_STATES)
      );
      break;
    case "PhaseChanged":
      validBody = (
        isExactObject(event.body, ["phase"]) &&
        isBoundedV5Text(event.body.phase, true)
      );
      break;
    case "Progress":
      return validateProgressV5(event.body);
    case "ItemOutcome":
      validBody = validateOperationItemV5(event.body);
      break;
    case "IntegrityOutcome":
      validBody = validateIntegrityItemV5(event.body);
      break;
    case "Gap":
      validBody = (
        isExactObject(event.body, ["first_missed_seq"]) &&
        Number.isSafeInteger(event.body.first_missed_seq) &&
        event.body.first_missed_seq > 0 &&
        event.body.first_missed_seq <= event.sequence
      );
      break;
    case "Terminal":
      validBody = (
        isExactObject(event.body, ["result"]) &&
        validateTerminalSummaryV5(event.body.result)
      );
      break;
    default:
      return false;
  }
  if (!validBody) {
    return false;
  }
  // Validated v5 primitives have the same compact JSON byte length in Python
  // and JavaScript. Count the persistence envelope ("seq"), not this view.
  const canonical = JSON.stringify({
    session_id: event.session_id,
    seq: event.sequence,
    at: event.at,
    schema_version: event.schema_version,
    body_type: event.body_type,
    body: event.body,
  });
  return new TextEncoder().encode(canonical).length <=
    MAX_RELIABLE_EVENT_CANONICAL_BYTES;
}

function validateProgressV5(value) {
  if (
    !isExactObject(value, [
      "phase",
      "items_done",
      "items_total",
      "bytes_done",
      "bytes_total",
      "current_path",
      "item_id",
      "item_type",
      "item_attempt_id",
      "item_bytes_done",
      "item_bytes_total",
    ]) ||
    !isBoundedV5Text(value.phase, true) ||
    !isNonnegativeInteger(value.items_done) ||
    !isNullableNonnegativeInteger(value.items_total) ||
    !isScalar64(value.bytes_done) ||
    !(value.bytes_total === null || isScalar64(value.bytes_total)) ||
    !(value.current_path === null || isV5Path(value.current_path)) ||
    (value.items_total !== null && value.items_done > value.items_total) ||
    (value.bytes_total !== null &&
      BigInt(value.bytes_done) > BigInt(value.bytes_total))
  ) {
    return false;
  }
  const identityAbsent = value.item_id === null && value.item_type === null;
  const identityPresent =
    isBoundedV5Text(value.item_id, true) &&
    (value.item_type === "operation" || value.item_type === "integrity");
  if (
    (!identityAbsent && !identityPresent) ||
    (identityPresent &&
      value.items_total !== null &&
      value.items_done >= value.items_total)
  ) {
    return false;
  }
  const attemptAbsent = value.item_attempt_id === null;
  const attemptPresent =
    identityPresent &&
    typeof value.item_attempt_id === "string" &&
    ID_PATTERN.test(value.item_attempt_id);
  if (!attemptAbsent && !attemptPresent) {
    return false;
  }
  const itemBytesAbsent =
    value.item_bytes_done === null && value.item_bytes_total === null;
  const itemBytesPresent =
    attemptPresent &&
    isScalar64(value.item_bytes_done) &&
    isScalar64(value.item_bytes_total) &&
    BigInt(value.item_bytes_done) <= BigInt(value.item_bytes_total) &&
    BigInt(value.item_bytes_done) <= BigInt(value.bytes_done) &&
    (value.bytes_total === null ||
      BigInt(value.item_bytes_total) <= BigInt(value.bytes_total));
  return (
    (attemptAbsent && itemBytesAbsent) ||
    (attemptPresent && (itemBytesAbsent || itemBytesPresent))
  );
}

const OPERATION_REASONS_V5 = Object.freeze([
  "noop",
  "already-exists",
  "blocked",
  "dependency-failed",
  "source-drift",
  "target-drift",
  "destination-occupied",
  "wrong-type",
  "source-missing",
  "target-missing",
  "trash-collision",
  "unsafe-path",
  "sharing-violation",
  "acl-copy-failed",
  "cleanup-failed",
  "published-size-mismatch",
  "io-error",
  "policy-stop",
  "canceled",
  "canceled-after-publish",
  "canceled-after-mutation",
  "recorder-failed",
  "unsupported",
  "case_mismatch",
  "case_collision",
  "type_collision",
  "destination_collision",
  "blocked_dependency",
  "blocked-correspondence",
  "blocked-dependency",
  "incomplete-scan",
  "user-deselected",
]);
const OPERATION_KINDS_V5 = Object.freeze([
  "copy",
  "update",
  "move",
  "move_update",
  "recase",
  "mkdir",
  "trash",
  "delete",
  "noop",
]);
const ITEM_RECORDING_REASONS_V5 = Object.freeze([
  "record-write-failed",
  "unrecorded-mutation",
  "recording-prerequisite-failed",
]);
const TASK_RECORDING_REASONS_V5 = Object.freeze([
  "recording-open-failed",
  "final-flush-failed",
  "finish-failed",
  "recording-close-failed",
  "post-settlement-state-diverged",
]);
const DETAIL_TEXT_KEYS_V5 = Object.freeze([
  "backup",
  "backup_metadata",
  "backup_state",
  "backup_state_error",
  "blocked_reason",
  "cleanup_error",
  "destination_state",
  "durable_state",
  "error_type",
  "message",
  "mutation_durable_state",
  "mutation_state",
  "mutation_state_error",
  "old_state_error",
  "publish_state",
  "retry_error",
  "retry_error_type",
  "source_state",
  "state_error",
  "state_error_type",
  "target_state",
  "target_state_error",
  "temp_state",
  "trash_state_error",
]);
const DETAIL_PATH_KEYS_V5 = Object.freeze([
  "backup_path",
  "mutation_destination",
  "prior_path",
  "published_path",
  "trash_path",
]);
const DETAIL_ARRAY_KEYS_V5 = Object.freeze([
  "durability_warnings",
  "incomplete_sides",
  "excluded_dependencies",
]);

function validateOperationItemV5(value) {
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
      "recording",
      "recording_reason",
      "recording_detail",
      "detail_omitted_count",
    ]) &&
    value.item_type === "operation" &&
    value.phase === "execute" &&
    typeof value.item_id === "string" &&
    ID_PATTERN.test(value.item_id) &&
    isOneOf(value.kind, OPERATION_KINDS_V5) &&
    isV5Path(value.path) &&
    isOneOf(value.result, OPERATION_OUTCOMES) &&
    (value.reason === null ||
      isOneOf(value.reason, OPERATION_REASONS_V5)) &&
    validateDetailProjectionV5(value.detail) &&
    validateItemRecordingV5(
      value.recording,
      value.recording_reason,
      value.recording_detail,
      value.result,
    ) &&
    isNonnegativeInteger(value.detail_omitted_count)
  );
}

function validateIntegrityItemV5(value) {
  const rowPair =
    (value?.row_id === null && value?.location_id === null) ||
    (isBoundedV5Text(value?.row_id, true) &&
      isBoundedV5Text(value?.location_id, true));
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
      "detail_omitted_count",
    ]) &&
    value.item_type === "integrity" &&
    isOneOf(value.phase, INTEGRITY_MODES) &&
    isBoundedV5Text(value.item_id, true) &&
    rowPair &&
    value.kind === "integrity" &&
    isV5Path(value.path) &&
    isOneOf(value.result, INTEGRITY_RESULTS) &&
    (value.reason === null || isOneOf(value.reason, INTEGRITY_REASONS)) &&
    (value.detail === null || isBoundedV5Text(value.detail, false)) &&
    (value.read_strategy === null ||
      isOneOf(value.read_strategy, READ_STRATEGIES)) &&
    isOneOf(value.recording, RECORDING_STATES) &&
    (value.record_disposition === null ||
      isOneOf(value.record_disposition, RECORD_DISPOSITIONS)) &&
    isNonnegativeInteger(value.detail_omitted_count)
  );
}

function validateTerminalSummaryV5(value) {
  if (
    !isExactObject(value, [
      "status",
      "recording",
      "audit",
      "disposition",
      "canceled",
      "phases",
      "bytes_done",
      "bytes_total",
      "error",
      "recording_degraded_items",
      "recording_issues",
      "omitted_detail_count",
      "review_fact_limit",
    ]) ||
    !isOneOf(value.status, TERMINAL_STATES) ||
    !isOneOf(value.recording, RECORDING_STATES) ||
    !isOneOf(value.audit, RECORDING_STATES) ||
    !isOneOf(value.disposition, DISPOSITIONS) ||
    typeof value.canceled !== "boolean" ||
    !Array.isArray(value.phases) ||
    value.phases.length > 3 ||
    !value.phases.every(validatePhaseResultV5) ||
    new Set(value.phases.map((phase) => phase.phase)).size !==
      value.phases.length ||
    !isScalar64(value.bytes_done) ||
    !isScalar64(value.bytes_total) ||
    BigInt(value.bytes_done) > BigInt(value.bytes_total) ||
    !(
      value.error === null ||
      (isExactObject(value.error, ["type_name", "message"]) &&
        isBoundedV5Text(value.error.type_name, true) &&
        isBoundedV5Text(value.error.message, false))
    ) ||
    !isNonnegativeInteger(value.recording_degraded_items) ||
    !Array.isArray(value.recording_issues) ||
    value.recording_issues.length > 5 ||
    !value.recording_issues.every(validateRecordingIssueV5) ||
    new Set(value.recording_issues.map((issue) => issue.reason)).size !==
      value.recording_issues.length ||
    !isNonnegativeInteger(value.omitted_detail_count) ||
    !(
      value.review_fact_limit === null ||
      validateReviewFactV5(value.review_fact_limit)
    )
  ) {
    return false;
  }
  const expectedRecording =
    value.recording_degraded_items > 0 || value.recording_issues.length > 0
      ? "degraded"
      : "ok";
  if (
    value.recording !== expectedRecording ||
    !validateCancellationTruth(
      value.status, value.disposition, value.canceled, value.phases,
    )
  ) {
    return false;
  }
  return (
    value.review_fact_limit === null ||
    (value.status === "refused" &&
      value.disposition === "unrun" &&
      !value.canceled &&
      value.bytes_done === "0" &&
      value.bytes_total === "0" &&
      value.phases.length === 0 &&
      value.recording_degraded_items === 0 &&
      value.recording_issues.length === 0 &&
      value.omitted_detail_count === 0 &&
      value.error === null)
  );
}

function validatePhaseResultV5(value) {
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
    isBoundedV5Text(value.phase, true) &&
    isOneOf(value.status, PHASE_STATES) &&
    isNonnegativeInteger(value.items_done) &&
    isNullableNonnegativeInteger(value.items_total) &&
    isScalar64(value.bytes_done) &&
    (value.bytes_total === null || isScalar64(value.bytes_total)) &&
    (value.items_total === null || value.items_done <= value.items_total) &&
    (value.bytes_total === null ||
      BigInt(value.bytes_done) <= BigInt(value.bytes_total)) &&
    (value.error === null || isBoundedV5Text(value.error, false))
  );
}

function validateRecordingIssueV5(value) {
  return (
    isExactObject(value, ["reason", "detail"]) &&
    isOneOf(value.reason, TASK_RECORDING_REASONS_V5) &&
    (value.detail === null || isBoundedV5Text(value.detail, false))
  );
}

function validateReviewFactV5(value) {
  if (
    !isExactObject(value, [
      "reason",
      "tree_kind",
      "population",
      "axis",
      "row_limit",
      "byte_limit",
    ]) ||
    value.reason !== "review_fact_limit_exceeded" ||
    !["plan", "inventory"].includes(value.tree_kind) ||
    !["domain", "informational"].includes(value.population) ||
    !["rows", "retained-bytes", "logical-bytes"].includes(value.axis) ||
    !(value.row_limit === null || isNonnegativeInteger(value.row_limit)) ||
    !(value.byte_limit === null || isScalar64(value.byte_limit))
  ) {
    return false;
  }
  if (value.axis === "rows") {
    return value.row_limit === 120000 && value.byte_limit === null;
  }
  if (value.row_limit !== null || value.byte_limit === null) {
    return false;
  }
  if (value.axis === "logical-bytes") {
    return (
      value.tree_kind === "plan" &&
      value.population === "domain" &&
      value.byte_limit === "9223372036854775807"
    );
  }
  const expected =
    value.tree_kind === "plan" && value.population === "domain"
      ? "134217728"
      : "201326592";
  return value.byte_limit === expected;
}

function validateItemRecordingV5(status, reason, detail, outcome) {
  if (!isOneOf(status, RECORDING_STATES)) {
    return false;
  }
  if (status === "ok") {
    return reason === null && detail === null;
  }
  return (
    isOneOf(reason, ITEM_RECORDING_REASONS_V5) &&
    (detail === null || isBoundedV5Text(detail, false)) &&
    (reason === "record-write-failed"
      ? outcome === "succeeded" || outcome === "skipped"
      : outcome === "failed")
  );
}

function validateDetailProjectionV5(value) {
  if (!isPlainJsonObject(value)) {
    return false;
  }
  let leaves = 0;
  let pathLeaves = 0;
  for (const [key, item] of Object.entries(value)) {
    if (!/^[\x20-\x7e]{1,64}$/.test(key)) {
      return false;
    }
    if (DETAIL_TEXT_KEYS_V5.includes(key)) {
      if (!isBoundedV5Text(item, false)) {
        return false;
      }
      leaves += 1;
    } else if (DETAIL_PATH_KEYS_V5.includes(key)) {
      if (!isV5Path(item)) {
        return false;
      }
      leaves += 1;
      pathLeaves += 1;
    } else if (key === "continued") {
      if (typeof item !== "boolean") {
        return false;
      }
      leaves += 1;
    } else if (DETAIL_ARRAY_KEYS_V5.includes(key)) {
      if (!Array.isArray(item) || item.length > 32) {
        return false;
      }
      if (
        key === "incomplete_sides" &&
        !item.every((member) => ["source", "target"].includes(member))
      ) {
        return false;
      }
      if (
        key === "excluded_dependencies" &&
        !item.every(
          (member) => typeof member === "string" && ID_PATTERN.test(member),
        )
      ) {
        return false;
      }
      if (
        key === "durability_warnings" &&
        !item.every((member) => isBoundedV5Text(member, false))
      ) {
        return false;
      }
      leaves += item.length;
    } else {
      return false;
    }
    if (leaves > 32 || pathLeaves > 8) {
      return false;
    }
  }
  return true;
}

function isScalar64(value) {
  return (
    typeof value === "string" &&
    /^(?:0|[1-9][0-9]*)$/.test(value) &&
    BigInt(value) <= 9223372036854775807n
  );
}

function isBoundedV5Text(value, nonempty) {
  return (
    typeof value === "string" &&
    isValidUnicode(value) &&
    (!nonempty || value.length > 0) &&
    new TextEncoder().encode(value).length <= 1024
  );
}

function isV5Path(value) {
  return (
    typeof value === "string" &&
    isValidUnicode(value) &&
    !value.includes("\u0000") &&
    value.length <= 32767
  );
}

function isNonnegativeInteger(value) {
  return Number.isSafeInteger(value) && value >= 0;
}

function isNullableNonnegativeInteger(value) {
  return value === null || isNonnegativeInteger(value);
}

function isOneOf(value, choices) {
  return typeof value === "string" && choices.includes(value);
}

function isUtcTimestamp(value) {
  if (typeof value !== "string") {
    return false;
  }
  const match = /^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]{6})?\+00:00$/.exec(value);
  // Without multiline mode, $ matches only the end of the input.
  if (match === null || match[0] !== value) {
    return false;
  }
  const [year, month, day, hour, minute, second] = match.slice(1).map(Number);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return (
    year >= 1 &&
    month >= 1 && month <= 12 &&
    day >= 1 && day <= days[month - 1] &&
    hour < 24 && minute < 60 && second < 60
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
      // At end of string next is NaN, which must also refuse the pair.
      if (!(next >= 0xdc00 && next <= 0xdfff)) {
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
