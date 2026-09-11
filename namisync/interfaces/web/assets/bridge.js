const BRIDGE_SCHEMA_VERSION = 1;
const NATIVE_TRANSPORT_VERSION = 1;
const CORE_EVENT_SCHEMA_VERSION = 5;
const LIVE_EVENT_BODY_TYPES = Object.freeze([
  "StateChanged",
  "PhaseChanged",
  "Progress",
  "ItemOutcome",
  "IntegrityOutcome",
  "Gap",
  "Terminal",
]);
const ID_PATTERN = /^[0-9a-f]{32}$/;
const SLOT_PATTERN = /^slot-[0-9a-f]{32}$/;
const TASK_PATTERN = /^task-[0-9a-f]{32}$/;
const COMMAND_PATTERN = /^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/;
const COMMAND_MAX_LENGTH = 64;
const ASYNC_COMMAND_MAX_ATTEMPTS = 64;
const ASYNC_CLEANUP_ACK_TIMEOUT_MS = 1000;
const COMMAND_COMPLETION_KIND = "namisync.command-completion.v1";
const COMMAND_COMPLETION_PHASE = "completion";
const COMMAND_POLICY_JSON = `{
  "shell_ready": {"timeout": "startup-5-seconds", "retry": "none", "phase": "bootstrap"},
  "readiness_echo": {"timeout": "startup-5-seconds", "retry": "same-payload-once", "phase": "bootstrap"},
  "pick_folder": {"timeout": "interactive", "retry": "none", "phase": "open"},
  "create_task": {"timeout": "mutation-30-seconds", "retry": "same-command-once", "phase": "open"},
  "list_tasks": {"timeout": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "read_setup": {"timeout": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "probe_recent_pairs": {"timeout": "local-5-seconds", "retry": "none", "phase": "open"},
  "prepare_setup": {"timeout": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "admit_location": {"timeout": "local-5-seconds", "retry": "none", "phase": "open"},
  "read_cosmetic_section": {"timeout": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "replace_cosmetic_section": {"timeout": "local-5-seconds", "retry": "none", "phase": "open"},
  "start_plan": {"timeout": "mutation-30-seconds", "retry": "same-command-once", "phase": "open"},
  "start_inventory": {"timeout": "mutation-30-seconds", "retry": "same-command-once", "phase": "open"},
  "plan_again": {"timeout": "mutation-30-seconds", "retry": "same-command-once", "phase": "open"},
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
const CREATE_TASK_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.create_task.timeout];
const LIST_TASKS_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.list_tasks.timeout];
const SETUP_READ_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.read_setup.timeout];
const SETUP_PREPARE_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.prepare_setup.timeout];
const LOCATION_ADMIT_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.admit_location.timeout];
const INVENTORY_START_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.start_inventory.timeout];
const PLAN_AGAIN_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.plan_again.timeout];
const DRAIN_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.next_events.timeout];
const SESSION_RELEASE_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.release_terminal_session.timeout];
const TASK_CLOSE_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.close_task.timeout];
const DRAIN_MAX_UPDATES = 64;
const LOCATION_MOUNT_CANDIDATE_LIMIT = 27;
const PLAN_AGAIN_MOUNT_CANDIDATE_LIMIT = 53;
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
const TERMINAL_STATES = Object.freeze([
  "completed",
  "failed",
  "canceled",
  "refused",
]);
const RECORDING_STATES = Object.freeze(["ok", "degraded"]);
const TASK_RECORDING_REASONS_V5 = Object.freeze([
  "recording-open-failed",
  "final-flush-failed",
  "finish-failed",
  "recording-close-failed",
  "post-settlement-state-diverged",
]);
const DISPOSITIONS = Object.freeze(["ran", "unrun"]);
const THEMES = Object.freeze(["system", "light", "dark"]);
const LOCATION_PURPOSES = Object.freeze(["source", "target", "inventory"]);
const LOCATION_STATES = Object.freeze([
  "resolved", "invalid_path", "missing", "not_directory", "reparse",
  "placeholder", "remote", "unsupported_volume", "offline", "ambiguous",
  "unavailable", "changed",
]);
const PLAN_AGAIN_STATES = Object.freeze([
  "resolved", "offline", "ambiguous", "missing", "unavailable", "changed",
]);
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
  response_too_large: "The desktop response is too large.",
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
let commandHostGeneration = null;
const taskDrains = new Map();
const asyncCommandAttempts = new Map();

const documentMessages = globalThis.chrome?.webview;
if (typeof documentMessages?.addEventListener === "function") {
  documentMessages.addEventListener("message", receiveCommandCompletion);
}

window.addEventListener("pywebviewready", () => {
  bridgeGeneration += 1;
  operationalGeneration = -1;
  commandHostGeneration = null;
  const resolve = resolveRawReadiness;
  rawReadiness = undefined;
  resolveRawReadiness = undefined;
  resolve?.();
  for (const attempt of asyncCommandAttempts.values()) {
    retireAsyncCommandAttempt(attempt);
  }
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
  if (!isLocationPurpose(purpose)) {
    throw new TypeError("purpose must be source, target, or inventory");
  }
  return dispatchInteractive(
    "pick_folder",
    Object.freeze({ purpose }),
    (value) => value === null || (
      validateLocationChoice(value) && value.purpose === purpose
    ),
  );
}

export class TaskCreateUncertainError extends BridgeTransportError {
  constructor(retry) {
    super("The task-creation response could not be confirmed.");
    this.name = "TaskCreateUncertainError";
    this.retry = retry;
  }
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

export function startPlan(taskId, sourceId, targetId, options) {
  if (
    typeof taskId !== "string" || !TASK_PATTERN.test(taskId) ||
    typeof sourceId !== "string" || !SLOT_PATTERN.test(sourceId) ||
    typeof targetId !== "string" || !SLOT_PATTERN.test(targetId) ||
    !isSetupOptions(options)
  ) {
    throw new TypeError("startPlan requires task, choices, and complete options");
  }
  return submitStart(Object.freeze({
    task_id: taskId,
    command_id: mintId(),
    source_id: sourceId,
    target_id: targetId,
    options: freezeJson(options),
  }), "start_plan", START_PLAN_TIMEOUT_MS);
}

export function startInventory(taskId, rootId) {
  if (
    typeof taskId !== "string" || !TASK_PATTERN.test(taskId) ||
    typeof rootId !== "string" || !SLOT_PATTERN.test(rootId)
  ) {
    throw new TypeError("startInventory requires a task and inventory choice");
  }
  return submitStart(Object.freeze({
    task_id: taskId,
    command_id: mintId(),
    root_id: rootId,
  }), "start_inventory", INVENTORY_START_TIMEOUT_MS);
}

export function planAgain(taskId, sourceMount = null, targetMount = null) {
  if (
    typeof taskId !== "string" || !TASK_PATTERN.test(taskId) ||
    !isOptionalPath(sourceMount) || !isOptionalPath(targetMount)
  ) {
    throw new TypeError("planAgain requires a task and optional current mounts");
  }
  return submitStart(Object.freeze({
    task_id: taskId,
    command_id: mintId(),
    source_mount: sourceMount,
    target_mount: targetMount,
  }), "plan_again", PLAN_AGAIN_TIMEOUT_MS);
}

export async function createTask() {
  const payload = Object.freeze({ command_id: mintId() });
  let automaticReplayUsed = false;
  const submit = async () => {
    try {
      return await dispatchAttempt(
        "create_task",
        payload,
        validateTaskShellResult,
        CREATE_TASK_TIMEOUT_MS,
        true,
      );
    } catch (error) {
      if (!isUncertainStartPlanFailure(error)) throw error;
      if (!automaticReplayUsed) {
        automaticReplayUsed = true;
        try {
          return await dispatchAttempt(
            "create_task",
            payload,
            validateTaskShellResult,
            CREATE_TASK_TIMEOUT_MS,
            true,
          );
        } catch (replayError) {
          if (!isUncertainStartPlanFailure(replayError)) throw replayError;
        }
      }
      throw new TaskCreateUncertainError(submit);
    }
  };
  return submit();
}

export async function listTasks() {
  try {
    return await listTasksAttempt();
  } catch (error) {
    if (!(error instanceof BridgeTransportError)) {
      throw error;
    }
  }
  return listTasksAttempt();
}

function listTasksAttempt() {
  return dispatchAttempt(
    "list_tasks",
    Object.freeze({}),
    validateTaskListResult,
    LIST_TASKS_TIMEOUT_MS,
  );
}

export function startTaskDrain(
  taskId,
  sessionId,
  acceptUpdate,
  acceptRefusal,
  initialState = null,
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
  if (
    initialState !== null &&
    (!isExactObject(initialState, ["terminal", "sessionReleased"]) ||
      typeof initialState.terminal !== "boolean" ||
      typeof initialState.sessionReleased !== "boolean" ||
      (initialState.sessionReleased && !initialState.terminal))
  ) {
    throw new TypeError("startTaskDrain initial state is invalid");
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
    terminal: initialState?.terminal ?? false,
    pendingTerminalUpdate: null,
    terminalPresentationInProgress: false,
    sessionReleased: initialState?.sessionReleased ?? false,
    releaseControl: null,
    releaseTimer: null,
    releaseEpoch: 0,
    releaseFailures: 0,
    stopped: false,
  };
  taskDrains.set(taskId, task);
  if (task.terminal) {
    beginTaskRelease(task);
  } else {
    rearmTask(task, null);
  }

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

export async function closeTask(taskId, sessionId = null) {
  const task = taskDrains.get(taskId);
  if (
    typeof taskId !== "string" ||
    !TASK_PATTERN.test(taskId) ||
    !(sessionId === null || (typeof sessionId === "string" && ID_PATTERN.test(sessionId))) ||
    (sessionId !== null && (task?.sessionId !== sessionId || task.stopped))
  ) {
    throw new TypeError("closeTask requires an exact retained task identity");
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
          (value) => validateTaskCloseResult(value, taskId, sessionId),
          TASK_CLOSE_TIMEOUT_MS,
          true,
        );
        if (result.disposition === "closed" && task !== undefined) {
          stopTask(task);
        }
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

function submitStart(payload, command, timeoutMs) {
  let automaticReplayUsed = false;
  const validateResult = (value) => (
    validateStartPlanResult(value)
    && (command === "plan_again"
      ? value.task_id !== payload.task_id
      : value.task_id === payload.task_id)
  );
  const submit = async () => {
    try {
      return await dispatchAttempt(command, payload, validateResult, timeoutMs, true);
    } catch (error) {
      if (!isUncertainStartPlanFailure(error)) throw error;
      if (!automaticReplayUsed) {
        automaticReplayUsed = true;
        try {
          return await dispatchAttempt(command, payload, validateResult, timeoutMs, true);
        } catch (replayError) {
          if (!isUncertainStartPlanFailure(replayError)) throw replayError;
        }
      }
      throw new StartPlanUncertainError(submit);
    }
  };
  return submit();
}

export function admitLocation(purpose, value) {
  if (!isLocationPurpose(purpose)) {
    throw new TypeError("admitLocation requires a valid purpose");
  }
  let payload;
  if (isLocationCandidate(value)) {
    payload = Object.freeze({ purpose, candidate: freezeJson(value) });
  } else if (isLocationContinuation(value)) {
    payload = Object.freeze({
      purpose,
      continuation_id: value.continuation_id,
      mount_index: value.mount_index,
    });
  } else {
    throw new TypeError("admitLocation requires a candidate or continuation choice");
  }
  return dispatchAttempt(
    "admit_location",
    payload,
    (result) => validateLocationChoice(result) && result.purpose === purpose,
    LOCATION_ADMIT_TIMEOUT_MS,
  );
}

export async function readSetup(taskId = null) {
  if (taskId !== null && (typeof taskId !== "string" || !TASK_PATTERN.test(taskId))) {
    throw new TypeError("readSetup requires a task id or null");
  }
  const payload = Object.freeze({ task_id: taskId });
  const validateResult = (value) => (
    validateSetupReadResult(value) && value.task_id === taskId
  );
  try {
    return await dispatchAttempt("read_setup", payload, validateResult, SETUP_READ_TIMEOUT_MS);
  } catch (error) {
    if (!(error instanceof BridgeTransportError)) throw error;
  }
  return dispatchAttempt("read_setup", payload, validateResult, SETUP_READ_TIMEOUT_MS);
}

export async function prepareSetup(options) {
  if (!isSetupOptions(options)) {
    throw new TypeError("prepareSetup requires complete Setup options");
  }
  const payload = Object.freeze({ options: freezeJson(options) });
  try {
    return await dispatchAttempt("prepare_setup", payload, validateSetupOptions, SETUP_PREPARE_TIMEOUT_MS);
  } catch (error) {
    if (!(error instanceof BridgeTransportError)) throw error;
  }
  return dispatchAttempt("prepare_setup", payload, validateSetupOptions, SETUP_PREPARE_TIMEOUT_MS);
}

export function probeRecentPairs() {
  return dispatchAttempt(
    "probe_recent_pairs", {}, validateRecentPairProbe,
    TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.probe_recent_pairs.timeout], true,
  );
}

function validateRecentPairProbe(value) {
  const states = new Set([
    "resolved", "invalid_path", "missing", "not_directory", "reparse",
    "placeholder", "remote", "unsupported_volume", "offline", "ambiguous",
    "unavailable", "changed",
  ]);
  return isExactObject(value, ["pairs"]) && Array.isArray(value.pairs)
    && value.pairs.length <= 5
    && value.pairs.every((pair) => isExactObject(pair, [
      "mapping_id", "source_id", "target_id", "source_state", "target_state",
    ]) && isLocationId(pair.mapping_id) && isLocationId(pair.source_id)
      && isLocationId(pair.target_id) && pair.source_id !== pair.target_id
      && states.has(pair.source_state) && states.has(pair.target_state))
    && new Set(value.pairs.map((pair) => pair.mapping_id)).size === value.pairs.length;
}

async function dispatchAttempt(
  command,
  payload,
  validateResult,
  timeoutMs,
  asyncSmall = false,
) {
  return dispatchAttemptWithReadiness(
    command,
    payload,
    validateResult,
    timeoutMs,
    whenBridgeReady,
    asyncSmall,
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
  asyncSmall = false,
) {
  return createDispatchAttempt(
    command,
    payload,
    validateResult,
    timeoutMs,
    waitUntilReady,
    asyncSmall,
  ).promise;
}

function createDispatchAttempt(
  command,
  payload,
  validateResult,
  timeoutMs,
  waitUntilReady = whenBridgeReady,
  asyncSmall = false,
) {
  const requestId = mintId();
  const attempt = {
    cancelled: false,
    rejectCancellation: null,
    asyncEntry: null,
  };
  const request = JSON.stringify({
    schema_version: BRIDGE_SCHEMA_VERSION,
    request_id: requestId,
    command,
    payload,
  });
  if (asyncSmall) {
    if (asyncCommandAttempts.size >= ASYNC_COMMAND_MAX_ATTEMPTS) {
      throw new BridgeCommandError("bridge_busy", ERROR_MESSAGES.bridge_busy);
    }
    let resolveCompletion;
    let rejectCompletion;
    const completion = new Promise((resolve, reject) => {
      resolveCompletion = resolve;
      rejectCompletion = reject;
    });
    attempt.asyncEntry = {
      requestId,
      browserGeneration: null,
      hostGeneration: null,
      completionToken: null,
      earlyCompletion: null,
      settling: false,
      completion,
      resolveCompletion,
      rejectCompletion,
    };
    asyncCommandAttempts.set(requestId, attempt.asyncEntry);
  }
  const dispatchPromise = asyncSmall
    ? dispatchSmallReadyAttempt(
      request,
      requestId,
      validateResult,
      attempt,
      waitUntilReady,
    )
    : dispatchReadyAttempt(
      request,
      requestId,
      validateResult,
      attempt,
      waitUntilReady,
    );
  return {
    promise: withDeadline(
      dispatchPromise,
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
    const transport = Promise.resolve(api.dispatch(request)).then(
      (nativeResponse) => detachNativeResponse(
        api,
        nativeResponse,
        generation,
      ),
    );
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

async function dispatchSmallReadyAttempt(
  request,
  requestId,
  validateResult,
  attempt,
  waitUntilReady,
) {
  const entry = attempt.asyncEntry;
  if (entry === null || asyncCommandAttempts.get(requestId) !== entry) {
    throw new BridgeTransportError();
  }
  await waitUntilReady();
  if (attempt.cancelled) {
    throw new BridgeTransportError();
  }
  const generation = bridgeGeneration;
  entry.browserGeneration = generation;
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
  try {
    const api = bridgeApi();
    if (
      attempt.cancelled ||
      generation !== bridgeGeneration ||
      typeof api?.dispatch !== "function"
    ) {
      throw new BridgeTransportError();
    }
    // The pending entry and generation are fixed before native admission.
    const transport = Promise.resolve(api.dispatch(request)).then(
      (nativeResponse) => detachSmallNativeResponse(
        api,
        nativeResponse,
        generation,
        entry,
      ),
    );
    const native = await Promise.race([transport, reincarnated, cancelled]);
    if (native.kind === "direct") {
      retireAsyncCommandAttempt(entry);
      return validateResponse(native.response, requestId, validateResult);
    }
    const response = await Promise.race([
      entry.completion,
      reincarnated,
      cancelled,
    ]);
    if (generation !== bridgeGeneration) {
      throw new BridgeTransportError();
    }
    return validateResponse(response, requestId, validateResult);
  } catch (error) {
    if (error instanceof BridgeCommandError) {
      throw error;
    }
    if (error instanceof BridgeTransportError) {
      throw error;
    }
    throw new BridgeTransportError();
  } finally {
    attempt.rejectCancellation = null;
    window.removeEventListener("pywebviewready", onReincarnation);
    retireAsyncCommandAttempt(entry);
  }
}

async function detachSmallNativeResponse(
  api,
  nativeResponse,
  generation,
  entry,
) {
  const direct = isExactObject(nativeResponse, [
    "transport_version",
    "response_token",
    "response",
  ]);
  const admitted = isExactObject(nativeResponse, [
    "transport_version",
    "response_token",
    "completion",
  ]);
  if (
    (!direct && !admitted) ||
    nativeResponse.transport_version !== NATIVE_TRANSPORT_VERSION ||
    (admitted && nativeResponse.response_token === null) ||
    (
      nativeResponse.response_token !== null &&
      (
        typeof nativeResponse.response_token !== "string" ||
        !ID_PATTERN.test(nativeResponse.response_token)
      )
    )
  ) {
    throw new BridgeTransportError();
  }
  const responseToken = nativeResponse.response_token;
  let value;
  try {
    value = direct
      ? { kind: "direct", response: cloneJsonValue(nativeResponse.response) }
      : { kind: "admitted", completion: cloneJsonValue(nativeResponse.completion) };
    if (admitted) {
      const completion = value.completion;
      if (
        !isExactObject(completion, [
          "phase",
          "generation",
          "request_id",
          "completion_token",
        ]) ||
        completion.phase !== COMMAND_COMPLETION_PHASE ||
        !Number.isSafeInteger(completion.generation) ||
        completion.generation < 0 ||
        completion.request_id !== entry.requestId ||
        typeof completion.completion_token !== "string" ||
        !ID_PATTERN.test(completion.completion_token) ||
        (
          commandHostGeneration !== null &&
          commandHostGeneration !== completion.generation
        )
      ) {
        throw new BridgeTransportError();
      }
      commandHostGeneration = completion.generation;
      entry.hostGeneration = completion.generation;
      entry.completionToken = completion.completion_token;
    }
  } finally {
    nativeResponse = null;
    if (responseToken !== null) {
      await acknowledgeAsyncCleanup(
        api,
        `ack:${responseToken}`,
        generation,
      );
    }
  }
  if (generation !== bridgeGeneration) {
    throw new BridgeTransportError();
  }
  if (direct) {
    return value;
  }
  if (entry.earlyCompletion !== null) {
    void settleCommandCompletion(entry, entry.earlyCompletion);
  }
  return { kind: "admitted" };
}

function receiveCommandCompletion(event) {
  const message = event?.data;
  if (!isCommandCompletionMessage(message)) {
    return;
  }
  const entry = asyncCommandAttempts.get(message.request_id);
  if (entry === undefined) {
    if (
      commandHostGeneration !== null &&
      message.generation === commandHostGeneration
    ) {
      void acknowledgeCommandCompletion(message).catch(() => {});
    }
    return;
  }
  if (
    entry.browserGeneration !== bridgeGeneration ||
    (
      entry.completionToken !== null &&
      (
        entry.hostGeneration !== message.generation ||
        entry.completionToken !== message.completion_token
      )
    )
  ) {
    return;
  }
  let captured;
  try {
    captured = cloneJsonValue(message);
  } catch {
    return;
  }
  if (entry.completionToken === null) {
    if (entry.earlyCompletion === null) {
      entry.earlyCompletion = captured;
    }
    return;
  }
  void settleCommandCompletion(entry, captured);
}

async function settleCommandCompletion(entry, message) {
  if (
    entry.settling ||
    entry.browserGeneration !== bridgeGeneration ||
    entry.hostGeneration !== message.generation ||
    entry.requestId !== message.request_id ||
    entry.completionToken !== message.completion_token
  ) {
    return;
  }
  entry.settling = true;
  try {
    await acknowledgeCommandCompletion(message);
  } catch (_error) {
    if (asyncCommandAttempts.get(entry.requestId) === entry) {
      asyncCommandAttempts.delete(entry.requestId);
      entry.rejectCompletion(new BridgeTransportError());
    }
    return;
  }
  if (asyncCommandAttempts.get(entry.requestId) !== entry) {
    return;
  }
  asyncCommandAttempts.delete(entry.requestId);
  entry.resolveCompletion(message.response);
}

async function acknowledgeCommandCompletion(message) {
  const api = bridgeApi();
  if (
    commandHostGeneration === null ||
    message.generation !== commandHostGeneration ||
    typeof api?.dispatch !== "function"
  ) {
    throw new BridgeTransportError();
  }
  const acknowledgment = [
    "ack",
    COMMAND_COMPLETION_PHASE,
    String(message.generation),
    message.request_id,
    message.completion_token,
  ].join(":");
  return acknowledgeAsyncCleanup(api, acknowledgment, bridgeGeneration);
}

async function acknowledgeAsyncCleanup(api, acknowledgment, generation) {
  let firstDeliveryUncertain = false;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    if (
      generation !== bridgeGeneration ||
      typeof api?.dispatch !== "function"
    ) {
      throw new BridgeTransportError();
    }
    try {
      const acknowledged = await withDeadline(
        Promise.resolve(api.dispatch(acknowledgment)),
        ASYNC_CLEANUP_ACK_TIMEOUT_MS,
        () => {},
      );
      if (
        acknowledged === true ||
        (firstDeliveryUncertain && acknowledged === false)
      ) {
        return;
      }
    } catch (_error) {
      if (attempt === 0) {
        firstDeliveryUncertain = true;
      }
    }
  }
  throw new BridgeTransportError();
}

function retireAsyncCommandAttempt(entry) {
  if (asyncCommandAttempts.get(entry.requestId) === entry) {
    asyncCommandAttempts.delete(entry.requestId);
  }
}

function isCommandCompletionMessage(value) {
  if (
    !isExactObject(value, [
      "kind",
      "phase",
      "generation",
      "request_id",
      "completion_token",
      "response",
    ]) ||
    value.kind !== COMMAND_COMPLETION_KIND ||
    value.phase !== COMMAND_COMPLETION_PHASE ||
    !Number.isSafeInteger(value.generation) ||
    value.generation < 0 ||
    typeof value.request_id !== "string" ||
    !ID_PATTERN.test(value.request_id) ||
    typeof value.completion_token !== "string" ||
    !ID_PATTERN.test(value.completion_token)
  ) {
    return false;
  }
  return isCompletionResponse(value.response, value.request_id);
}

function isCompletionResponse(value, requestId) {
  if (
    value?.schema_version !== BRIDGE_SCHEMA_VERSION ||
    value.request_id !== requestId ||
    typeof value.ok !== "boolean"
  ) {
    return false;
  }
  if (value.ok) {
    return isExactObject(value, ["schema_version", "request_id", "ok", "result"]);
  }
  if (
    !isExactObject(value, ["schema_version", "request_id", "ok", "error"]) ||
    !isExactObject(value.error, ["code", "message"])
  ) {
    return false;
  }
  return ERROR_MESSAGES[value.error.code] === value.error.message;
}

async function detachNativeResponse(api, nativeResponse, generation) {
  if (
    !isExactObject(nativeResponse, [
      "transport_version",
      "response_token",
      "response",
    ]) ||
    nativeResponse.transport_version !== NATIVE_TRANSPORT_VERSION ||
    (
      nativeResponse.response_token !== null &&
      (
        typeof nativeResponse.response_token !== "string" ||
        !ID_PATTERN.test(nativeResponse.response_token)
      )
    )
  ) {
    throw new BridgeTransportError();
  }
  const responseToken = nativeResponse.response_token;
  let response;
  try {
    response = cloneJsonValue(nativeResponse.response);
  } finally {
    nativeResponse = null;
    if (responseToken !== null) {
      await acknowledgeNativeResponse(api, responseToken, generation);
    }
  }
  if (generation !== bridgeGeneration) {
    throw new BridgeTransportError();
  }
  return response;
}

async function acknowledgeNativeResponse(api, responseToken, generation) {
  let firstDeliveryUncertain = false;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    if (
      generation !== bridgeGeneration ||
      typeof api?.dispatch !== "function"
    ) {
      throw new BridgeTransportError();
    }
    try {
      const acknowledged = await api.dispatch(`ack:${responseToken}`);
      if (
        acknowledged === true ||
        (firstDeliveryUncertain && acknowledged === false)
      ) {
        return;
      }
    } catch (_error) {
      if (attempt === 0) {
        firstDeliveryUncertain = true;
      }
    }
  }
  throw new BridgeTransportError();
}

function cancelAttempt(attempt) {
  if (attempt.cancelled) {
    return;
  }
  attempt.cancelled = true;
  if (attempt.asyncEntry !== null) {
    retireAsyncCommandAttempt(attempt.asyncEntry);
  }
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

function validateSetupReadResult(value) {
  if (!isExactObject(value, ["task_id", "snapshot", "recents"])) return false;
  if (value.task_id !== null && (typeof value.task_id !== "string" || !TASK_PATTERN.test(value.task_id))) return false;
  if (!validateSetupSnapshot(value.snapshot)) return false;
  if (value.task_id === null) return validateRecents(value.recents);
  return value.recents === null;
}

function validateRecents(value) {
  return isExactObject(value, ["sources", "targets", "pairs"])
    && Array.isArray(value.sources)
    && Array.isArray(value.targets)
    && Array.isArray(value.pairs)
    && value.sources.length <= 5 && value.targets.length <= 5 && value.pairs.length <= 5
    && value.sources.every(validateRecentLocation)
    && value.targets.every(validateRecentLocation)
    && value.pairs.every((pair) => isExactObject(pair, ["mapping_id", "source", "target", "last_used_at"])
    && isLocationId(pair.mapping_id) && validateRecentLocation(pair.source)
      && validateRecentLocation(pair.target) && isUtcTimestamp(pair.last_used_at));
}

function validateRecentLocation(value) {
  return isExactObject(value, ["location_id", "display", "last_used_at"])
    && isLocationId(value.location_id) && isValidUnicode(value.display)
    && isUtcTimestamp(value.last_used_at);
}

function validateSetupSnapshot(value) {
  if (!isExactObject(value, ["setup_state", "task_kind", "source", "target", "root", "options", "plan_again"])) return false;
  if (!["default", "frozen"].includes(value.setup_state) || ![null, "sync-plan", "inventory"].includes(value.task_kind)) return false;
  if (![value.source, value.target, value.root].every(validateSetupLocation)) return false;
  if (value.options !== null && !validateSetupOptions(value.options)) return false;
  if (value.plan_again !== null && !validatePlanAgainReadiness(value.plan_again)) return false;
  if (value.setup_state === "default") {
    return value.task_kind === null
      && value.source === null && value.target === null && value.root === null
      && value.options !== null && value.plan_again === null;
  }
  if (value.task_kind === "sync-plan") {
    return value.source !== null && value.target !== null && value.root === null
      && value.options !== null;
  }
  if (value.task_kind === "inventory") {
    return value.source === null && value.target === null && value.root !== null
      && value.options === null && value.plan_again === null;
  }
  return false;
}

function validateSetupLocation(value) {
  return value === null || (isExactObject(value, ["display", "location_id"])
    && isValidUnicode(value.display)
    && (value.location_id === null || isLocationId(value.location_id)));
}

function validatePlanAgainReadiness(value) {
  return isExactObject(value, ["source_state", "source_candidates", "target_state", "target_candidates"])
    && PLAN_AGAIN_STATES.includes(value.source_state)
    && PLAN_AGAIN_STATES.includes(value.target_state)
    && validatePathList(value.source_candidates, PLAN_AGAIN_MOUNT_CANDIDATE_LIMIT)
    && validatePathList(value.target_candidates, PLAN_AGAIN_MOUNT_CANDIDATE_LIMIT);
}

function validateLocationChoice(value) {
  if (!isExactObject(value, ["purpose", "state", "choice_id", "continuation_id", "display", "location_id", "candidates", "detail"])) return false;
  if (!isLocationPurpose(value.purpose) || !LOCATION_STATES.includes(value.state)
    || !validatePathList(value.candidates)
    || (value.display !== null && !isValidUnicode(value.display))
    || (value.location_id !== null && !isLocationId(value.location_id))
    || (value.detail !== null && !isValidUnicode(value.detail))) return false;
  if (value.state === "resolved") {
    return typeof value.choice_id === "string" && SLOT_PATTERN.test(value.choice_id)
      && value.continuation_id === null;
  }
  if (value.state === "ambiguous") {
    return value.choice_id === null
      && (value.continuation_id === null
        || (typeof value.continuation_id === "string"
          && SLOT_PATTERN.test(value.continuation_id)));
  }
  return value.choice_id === null && value.continuation_id === null;
}

function validateSetupOptions(value) {
  return isSetupOptions(value);
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

function validateTaskShellResult(value) {
  return (
    isExactObject(value, ["task_id"]) &&
    typeof value.task_id === "string" &&
    TASK_PATTERN.test(value.task_id)
  );
}

function validateTaskSummary(value) {
  return (
    isExactObject(value, [
      "task_id", "session_id", "session_state", "session_released", "task_kind", "request_id",
    ]) &&
    typeof value.task_id === "string" &&
    TASK_PATTERN.test(value.task_id) &&
    (value.session_id === null ||
      (typeof value.session_id === "string" && ID_PATTERN.test(value.session_id))) &&
    [null, "active", "completed", "failed", "canceled", "refused"].includes(
      value.session_state,
    ) &&
    typeof value.session_released === "boolean" &&
    [null, "sync-plan", "inventory"].includes(value.task_kind) &&
    (value.request_id === null || (typeof value.request_id === "string" && ID_PATTERN.test(value.request_id))) &&
    ((value.task_kind === null) === (value.request_id === null)) &&
    ((value.session_state === null) === (value.session_id === null)) &&
    !(value.session_released && [null, "active"].includes(value.session_state))
  );
}

function validateTaskListResult(value) {
  return (
    isExactObject(value, ["tasks"]) &&
    Array.isArray(value.tasks) &&
    value.tasks.length <= 48 &&
    value.tasks.every(validateTaskSummary) &&
    new Set(value.tasks.map((task) => task.task_id)).size === value.tasks.length
  );
}

function validateTaskCloseResult(value, taskId, sessionId) {
  return (
    isExactObject(value, ["task_id", "session_id", "disposition"]) &&
    value.task_id === taskId &&
    value.session_id === sessionId &&
    ["pending", "closed"].includes(value.disposition) &&
    !(sessionId === null && value.disposition !== "closed")
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
      whenBridgeReady,
      true,
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
      (!Number.isSafeInteger(update.event.body.first_missed_seq) ||
        update.event.body.first_missed_seq <= lastSequence ||
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
  return (
    isExactObject(event, [
      "session_id",
      "sequence",
      "at",
      "schema_version",
      "body_type",
      "body",
    ]) &&
    event.session_id === sessionId &&
    Number.isSafeInteger(event.sequence) &&
    event.sequence > 0 &&
    event.schema_version === CORE_EVENT_SCHEMA_VERSION &&
    isOneOf(event.body_type, LIVE_EVENT_BODY_TYPES) &&
    isPlainJsonObject(event.body)
  );
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

function isLocationId(value) {
  return isScalar64(value) && value !== "0";
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    && Object.getPrototypeOf(value) === Object.prototype;
}

function isLocationPurpose(value) {
  return typeof value === "string" && LOCATION_PURPOSES.includes(value);
}

function isOptionalPath(value) {
  return value === null || (typeof value === "string" && value.length > 0 && isValidUnicode(value));
}

function validatePathList(value, maximumCount = LOCATION_MOUNT_CANDIDATE_LIMIT) {
  return Array.isArray(value) && value.length <= maximumCount && value.every((item) => typeof item === "string" && item.length > 0 && isValidUnicode(item));
}

function isLocationCandidate(value) {
  if (!isPlainObject(value)) return false;
  if (isExactObject(value, ["kind", "path", "selected_mount"])) {
    return value.kind === "literal_path" && typeof value.path === "string" && value.path.length > 0
      && isValidUnicode(value.path) && isOptionalPath(value.selected_mount);
  }
  return isExactObject(value, ["kind", "location_id", "selected_mount"])
    && value.kind === "remembered_location" && isLocationId(value.location_id)
    && isOptionalPath(value.selected_mount);
}

function isLocationContinuation(value) {
  return isPlainObject(value)
    && isExactObject(value, ["continuation_id", "mount_index"])
    && typeof value.continuation_id === "string"
    && SLOT_PATTERN.test(value.continuation_id)
    && Number.isSafeInteger(value.mount_index)
    && value.mount_index >= 0;
}

function isSetupOptions(value) {
  return isExactObject(value, ["filters", "deletion_policy", "trash_on_update", "preservation", "propagate_source_casing", "verify_after_execute"])
    && Array.isArray(value.filters) && value.filters.length <= 64
    && value.filters.every((filter) => typeof filter === "string" && filter.length > 0 && isValidUnicode(filter) && new TextEncoder().encode(filter).length <= 1024)
    && new TextEncoder().encode(value.filters.join("")).length <= 16384
    && ["trash", "additive"].includes(value.deletion_policy)
    && typeof value.trash_on_update === "boolean"
    && isExactObject(value.preservation, ["preserve_ads", "preserve_created", "preserve_acl"])
    && value.preservation.preserve_ads === false
    && typeof value.preservation.preserve_created === "boolean"
    && typeof value.preservation.preserve_acl === "boolean"
    && typeof value.propagate_source_casing === "boolean"
    && typeof value.verify_after_execute === "boolean";
}

function freezeJson(value) {
  if (Array.isArray(value)) return Object.freeze(value.map(freezeJson));
  if (isPlainObject(value)) {
    return Object.freeze(Object.fromEntries(Object.entries(value).map(([key, item]) => [key, freezeJson(item)])));
  }
  return value;
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
