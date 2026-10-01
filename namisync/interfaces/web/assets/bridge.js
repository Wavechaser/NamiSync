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
const COMMAND_MAX_ATTEMPTS = 64;
const MUTATION_FEEDBACK_MS = 5000;
const OBSERVATION_TIMEOUT_MS = 1000;
const OBSERVATION_DELAYS_MS = Object.freeze([100, 250]);
const ASYNC_CLEANUP_ACK_TIMEOUT_MS = 1000;
const COMMAND_COMPLETION_KIND = "namisync.command-completion.v1";
const COMMAND_COMPLETION_PHASE = "completion";
const COMMAND_POLICY_JSON = `{
  "shell_ready": {"response_policy": "startup-5-seconds", "retry": "none", "phase": "bootstrap"},
  "readiness_echo": {"response_policy": "startup-5-seconds", "retry": "same-payload-once", "phase": "bootstrap"},
  "pick_folder": {"response_policy": "interactive", "retry": "none", "phase": "open"},
  "create_task": {"response_policy": "mutation-observed", "retry": "none", "phase": "open"},
  "list_tasks": {"response_policy": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "read_setup": {"response_policy": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "probe_recent_pairs": {"response_policy": "local-5-seconds", "retry": "none", "phase": "open"},
  "prepare_setup": {"response_policy": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "admit_location": {"response_policy": "feedback-only", "retry": "none", "phase": "open"},
  "read_cosmetic_section": {"response_policy": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "replace_cosmetic_section": {"response_policy": "feedback-only", "retry": "none", "phase": "open"},
  "start_plan": {"response_policy": "mutation-observed", "retry": "none", "phase": "open"},
  "start_inventory": {"response_policy": "mutation-observed", "retry": "none", "phase": "open"},
  "plan_again": {"response_policy": "mutation-observed", "retry": "none", "phase": "open"},
  "open_plan_view": {"response_policy": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "open_inventory_view": {"response_policy": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "refresh_inventory": {"response_policy": "mutation-observed", "retry": "none", "phase": "open"},
  "acknowledge_inventory": {"response_policy": "mutation-observed", "retry": "none", "phase": "open"},
  "restore_inventory": {"response_policy": "mutation-observed", "retry": "none", "phase": "open"},
  "update_inventory_view": {"response_policy": "feedback-only", "retry": "none", "phase": "open"},
  "get_inventory_window": {"response_policy": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "get_inventory_detail": {"response_policy": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "update_plan_view": {"response_policy": "feedback-only", "retry": "none", "phase": "open"},
  "get_plan_window": {"response_policy": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "get_execution_detail": {"response_policy": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "get_plan_anchor": {"response_policy": "local-5-seconds", "retry": "same-payload-once", "phase": "open"},
  "mutate_plan_selection": {"response_policy": "mutation-observed", "retry": "none", "phase": "open"},
  "mutate_plan_scope": {"response_policy": "mutation-observed", "retry": "none", "phase": "open"},
  "mutate_plan_highlight": {"response_policy": "feedback-only", "retry": "none", "phase": "open"},
  "mutate_plan_highlighted_selection": {"response_policy": "mutation-observed", "retry": "none", "phase": "open"},
  "start_execution": {"response_policy": "mutation-observed", "retry": "none", "phase": "open"},
  "control_execution": {"response_policy": "mutation-observed", "retry": "none", "phase": "open"},
  "next_events": {"response_policy": "drain-30-seconds", "retry": "none", "phase": "open"},
  "release_terminal_session": {"response_policy": "mutation-observed", "retry": "none", "phase": "open"},
  "close_task": {"response_policy": "mutation-observed", "retry": "none", "phase": "open"}
}`;
export const COMMAND_POLICY_CONTRACT = freezeCommandPolicies(
  JSON.parse(COMMAND_POLICY_JSON),
);
const TIMEOUT_MS_BY_POLICY = Object.freeze({
  "startup-5-seconds": 5000,
  "local-5-seconds": 5000,
  "interactive": null,
  "feedback-only": null,
  "mutation-observed": null,
  "drain-30-seconds": 30000,
});
const SHELL_READY_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.shell_ready.response_policy];
const READINESS_ECHO_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.readiness_echo.response_policy];
const COSMETIC_READ_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.read_cosmetic_section.response_policy];
const COSMETIC_REPLACE_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.replace_cosmetic_section.response_policy];
const START_PLAN_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.start_plan.response_policy];
const CREATE_TASK_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.create_task.response_policy];
const LIST_TASKS_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.list_tasks.response_policy];
const SETUP_READ_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.read_setup.response_policy];
const SETUP_PREPARE_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.prepare_setup.response_policy];
const LOCATION_ADMIT_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.admit_location.response_policy];
const INVENTORY_START_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.start_inventory.response_policy];
const PLAN_AGAIN_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.plan_again.response_policy];
const PLAN_VIEW_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.open_plan_view.response_policy];
const EXECUTION_START_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.start_execution.response_policy];
const DRAIN_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.next_events.response_policy];
const SESSION_RELEASE_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.release_terminal_session.response_policy];
const TASK_CLOSE_TIMEOUT_MS =
  TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.close_task.response_policy];
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
const OPERATION_KINDS = Object.freeze([
  "copy", "update", "move", "move_update", "recase", "mkdir", "trash",
  "delete", "noop",
]);
const ITEM_RESULTS = Object.freeze([
  "succeeded", "skipped", "failed", "canceled", "deferred", "blocked",
]);
const OPERATION_REASONS = Object.freeze([
  "noop", "already-exists", "blocked", "dependency-failed", "source-drift",
  "target-drift", "destination-occupied", "wrong-type", "source-missing",
  "target-missing", "trash-collision", "unsafe-path", "sharing-violation",
  "acl-copy-failed", "cleanup-failed", "published-size-mismatch",
  "disk-capacity", "io-error", "policy-stop", "canceled",
  "canceled-after-publish", "canceled-after-mutation", "recorder-failed",
  "unsupported", "case_mismatch", "case_collision", "type_collision",
  "destination_collision", "blocked_dependency", "blocked-correspondence",
  "blocked-dependency", "incomplete-scan", "user-deselected",
]);
const ITEM_RECORDING_REASONS = Object.freeze([
  "record-write-failed", "unrecorded-mutation", "recording-prerequisite-failed",
]);
const INTEGRITY_RESULTS = Object.freeze([
  "verified", "baselined", "mismatched", "modified", "missing",
  "unsupported", "canceled", "error",
]);
const INTEGRITY_REASONS = Object.freeze([
  "path-invalid", "inventory-missing", "inventory-unsupported", "not-found",
  "unsupported-read", "stat-changed", "read-drift", "hash-mismatch",
  "baseline-exists", "read-error", "recording-stale", "recording-conflict",
  "recording-error", "canceled",
]);
const RECORD_DISPOSITIONS = Object.freeze(["applied", "noop", "stale", "conflict"]);
const EXECUTION_EVIDENCE_STATES = Object.freeze([
  "recorded-copy", "already-verified", "unrecorded", "superseded",
  "not-applicable",
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
  inventory_capacity: "Inventory command capacity is full. Close a task before trying again.",
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
let operational = false;
let commandHostGeneration = null;
let bridgeReadyObserved = false;
const taskDrains = new Map();
const taskCloseFences = new Map();
const commandAttempts = new Map();

const documentMessages = globalThis.chrome?.webview;
if (typeof documentMessages?.addEventListener === "function") {
  documentMessages.addEventListener("message", receiveCommandCompletion);
}

window.addEventListener("pywebviewready", () => {
  if (bridgeReadyObserved) return;
  bridgeReadyObserved = true;
  const resolve = resolveRawReadiness;
  rawReadiness = undefined;
  resolveRawReadiness = undefined;
  resolve?.();
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
  constructor() {
    super("The plan-start response could not be confirmed.");
    this.name = "StartPlanUncertainError";
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
  constructor(retry, unavailable = false) {
    super(unavailable
      ? "The completed task release outcome cannot be confirmed. Close and reopen NamiSync to review its current state."
      : "The completed task session could not be released. Retry the release.");
    this.name = "TerminalSessionReleaseError";
    this.retry = retry;
    this.checkable = !unavailable;
  }
}

export class TaskCloseUncertainError extends BridgeTransportError {
  constructor() {
    super("The task-close response could not be confirmed.");
    this.name = "TaskCloseUncertainError";
  }
}

function bridgeApi() {
  return window.pywebview?.api;
}

export function whenBridgeReady() {
  if (
    operational &&
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
  if (operational) {
    return;
  }
  if (typeof bridgeApi()?.dispatch !== "function") {
    throw new BridgeTransportError();
  }
  operational = true;
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
  constructor() {
    super("The task-creation response could not be confirmed.");
    this.name = "TaskCreateUncertainError";
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

export function startPlan(taskId, sourceId, targetId, options, onDelayed = null) {
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
  }), "start_plan", START_PLAN_TIMEOUT_MS, onDelayed);
}

export function startInventory(taskId, rootId, onDelayed = null) {
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
  }), "start_inventory", INVENTORY_START_TIMEOUT_MS, onDelayed);
}

export function planAgain(taskId, sourceMount = null, targetMount = null, onDelayed = null) {
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
  }), "plan_again", PLAN_AGAIN_TIMEOUT_MS, onDelayed);
}

export async function createTask(onDelayed = null) {
  const payload = Object.freeze({ command_id: mintId() });
  try {
    return await dispatchAttempt(
      "create_task", payload, validateTaskShellResult,
      CREATE_TASK_TIMEOUT_MS, true, onDelayed,
    );
  } catch (error) {
    if (error instanceof OutcomeUnavailableError) throw new TaskCreateUncertainError();
    throw error;
  }
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
  acceptRelease = null,
  acceptRecovered = null,
  acceptReleaseDelay = null,
) {
  if (
    typeof taskId !== "string" ||
    typeof sessionId !== "string" ||
    !TASK_PATTERN.test(taskId) ||
    !ID_PATTERN.test(sessionId)
  ) {
    throw new TypeError("startTaskDrain requires task and session ids");
  }
  if (taskCloseFences.has(taskId)) {
    throw new TypeError("that task is retiring");
  }
  if (typeof acceptUpdate !== "function" || typeof acceptRefusal !== "function") {
    throw new TypeError("startTaskDrain requires update and refusal callbacks");
  }
  if (acceptRelease !== null && typeof acceptRelease !== "function") {
    throw new TypeError("startTaskDrain release callback must be a function");
  }
  if (acceptRecovered !== null && typeof acceptRecovered !== "function") {
    throw new TypeError("startTaskDrain recovery callback must be a function");
  }
  if (acceptReleaseDelay !== null && typeof acceptReleaseDelay !== "function") {
    throw new TypeError("startTaskDrain release delay callback must be a function");
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
  const existing = taskDrains.get(taskId);
  if (existing !== undefined) {
    if (!existing.terminal || !existing.sessionReleased) {
      throw new TypeError("that task already has a browser drain");
    }
    stopTask(existing);
    taskDrains.delete(taskId);
  }
  const task = {
    taskId,
    sessionId,
    acceptUpdate,
    acceptRefusal,
    acceptRelease,
    acceptRecovered,
    acceptReleaseDelay,
    epoch: 0,
    active: null,
    armScheduled: false,
    armTimer: null,
    scheduledEpoch: null,
    desiredReplayFrom: null,
    lastAcceptedSequence: 0,
    snapshotRevision: null,
    busyRearmUsed: false,
    transportFailures: 0,
    terminal: initialState?.terminal ?? false,
    pendingTerminalUpdate: null,
    terminalPresentationInProgress: false,
    sessionReleased: initialState?.sessionReleased ?? false,
    releaseControl: null,
    releaseEpoch: 0,
    suspended: false,
    recoveryPending: false,
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

export function replaceCosmeticSection(expectedRevision, theme, onDelayed = null) {
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
    COSMETIC_REPLACE_TIMEOUT_MS, false, onDelayed,
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

export async function closeTask(taskId, sessionId = null, onDelayed = null) {
  const task = taskDrains.get(taskId);
  const retainedFence = taskCloseFences.get(taskId);
  if (
    typeof taskId !== "string" ||
    !TASK_PATTERN.test(taskId) ||
    !(sessionId === null || (typeof sessionId === "string" && ID_PATTERN.test(sessionId))) ||
    (sessionId !== null && (task?.sessionId !== sessionId || task.stopped)) ||
    (retainedFence !== undefined && retainedFence !== sessionId)
  ) {
    throw new TypeError("closeTask requires an exact retained task identity");
  }
  taskCloseFences.set(taskId, sessionId);

  const settle = async (resultPromise) => {
    try {
      const result = await resultPromise;
      if (result.disposition === "closed" && task !== undefined) stopTask(task);
      if (taskCloseFences.get(taskId) === sessionId) taskCloseFences.delete(taskId);
      return result;
    } catch (error) {
      if (error instanceof OutcomeUnavailableError) {
        throw new TaskCloseUncertainError();
      }
      if (taskCloseFences.get(taskId) === sessionId) taskCloseFences.delete(taskId);
      throw error;
    }
  };
  return settle(dispatchAttempt(
    "close_task", Object.freeze({ task_id: taskId, session_id: sessionId }),
    (value) => validateTaskCloseResult(value, taskId, sessionId),
    TASK_CLOSE_TIMEOUT_MS, true, onDelayed,
  ));
}

function submitStart(payload, command, timeoutMs, onDelayed = null) {
  const validateResult = (value) => (
    validateStartPlanResult(value)
    && (command !== "refresh_inventory" || value.request_id !== payload.request_id)
    && (command === "plan_again"
      ? value.task_id !== payload.task_id
      : value.task_id === payload.task_id)
  );
  return dispatchAttempt(
    command, payload, validateResult, timeoutMs, true, onDelayed,
  ).catch((error) => {
    if (error instanceof OutcomeUnavailableError) throw new StartPlanUncertainError();
    throw error;
  });
}

async function inventoryRead(command, payload, validate) {
  const submit = () => dispatchAttempt(command, Object.freeze(payload), validate, PLAN_VIEW_TIMEOUT_MS);
  try { return await submit(); } catch (error) {
    if (!(error instanceof BridgeTransportError)) throw error;
  }
  return submit();
}

export function openInventoryView(taskId) {
  requireTaskId(taskId, "openInventoryView");
  return inventoryRead("open_inventory_view", {task_id: taskId},
    (value) => validateInventorySummary(value) && value.task_id === taskId);
}

export function refreshInventory(taskId, requestId, commandId, expectedRevision, nodeId = null, onDelayed = null) {
  requireTaskId(taskId, "refreshInventory");
  if (typeof requestId !== "string" || !ID_PATTERN.test(requestId)
      || typeof commandId !== "string" || !ID_PATTERN.test(commandId)
      || !isNonnegativeInteger(expectedRevision) || !(nodeId === null || isNodeId(nodeId))) {
    throw new TypeError("refreshInventory requires an exact current inventory gesture");
  }
  return submitStart(Object.freeze({task_id: taskId, request_id: requestId,
    command_id: commandId, expected_revision: expectedRevision, node_id: nodeId}),
  "refresh_inventory", INVENTORY_START_TIMEOUT_MS, onDelayed);
}

function changeInventoryVisibility(action, taskId, requestId, commandId, expectedRevision, nodeId, onDelayed) {
  requireTaskId(taskId, "inventory visibility");
  if (typeof requestId !== "string" || !ID_PATTERN.test(requestId)
      || typeof commandId !== "string" || !ID_PATTERN.test(commandId)
      || !isNonnegativeInteger(expectedRevision) || !(nodeId === null || isNodeId(nodeId))) {
    throw new TypeError("inventory visibility requires an exact current inventory gesture");
  }
  const validate = (value) => {
    if (!isExactObject(value, ["task_id", "request_id", "action", "expected_revision", "total",
      "applied", "noop", "stale", "conflict", "unresolved_count", "disposition"])
        || value.task_id !== taskId || value.request_id !== requestId
        || value.action !== action || value.expected_revision !== expectedRevision
        || ![value.total, value.applied, value.noop, value.stale, value.conflict,
          value.unresolved_count].every(isNonnegativeInteger)) return false;
    return value.applied + value.noop + value.stale + value.conflict + value.unresolved_count === value.total
      && value.disposition === (value.unresolved_count > 0 ? "partial" : "completed");
  };
  return dispatchAttempt(`${action === "acknowledge" ? "acknowledge" : "restore"}_inventory`,
    Object.freeze({task_id: taskId, request_id: requestId, command_id: commandId,
      expected_revision: expectedRevision, node_id: nodeId}), validate,
    INVENTORY_START_TIMEOUT_MS, true, onDelayed);
}

export function acknowledgeInventory(taskId, requestId, commandId, expectedRevision, nodeId = null, onDelayed = null) {
  return changeInventoryVisibility("acknowledge", taskId, requestId, commandId, expectedRevision, nodeId, onDelayed);
}

export function restoreInventory(taskId, requestId, commandId, expectedRevision, nodeId = null, onDelayed = null) {
  return changeInventoryVisibility("restore", taskId, requestId, commandId, expectedRevision, nodeId, onDelayed);
}

export function updateInventoryView(taskId, expectedRevision, view, onDelayed = null) {
  requireTaskId(taskId, "updateInventoryView");
  if (!isNonnegativeInteger(expectedRevision) || !isTreeViewGesture(view, INVENTORY_FILTERS)) {
    throw new TypeError("updateInventoryView requires an exact revision and gesture");
  }
  return dispatchAttempt("update_inventory_view", Object.freeze({
    task_id: taskId, expected_revision: expectedRevision, search_query: view.searchQuery,
    filters: Object.freeze([...view.filters]), sort_column: view.sortColumn,
    sort_direction: view.sortDirection, collapse_node_id: view.collapseNodeId, collapsed: view.collapsed,
  }), (value) => validateInventorySummary(value) && value.task_id === taskId,
  PLAN_VIEW_TIMEOUT_MS, false, onDelayed);
}

export function getInventoryWindow(taskId, expectedRevision, offset, limit) {
  requireTaskId(taskId, "getInventoryWindow");
  if (!isNonnegativeInteger(expectedRevision) || !isNonnegativeInteger(offset)
      || !Number.isInteger(limit) || limit < 1 || limit > 256) {
    throw new TypeError("getInventoryWindow requires a bounded exact window");
  }
  return inventoryRead("get_inventory_window", {task_id: taskId, expected_revision: expectedRevision, offset, limit},
    (value) => validateInventoryWindow(value) && value.offset === offset
      && value.rows.length <= limit && (value.disposition === "conflict" || value.view_revision === expectedRevision));
}

export function getInventoryDetail(taskId, expectedRevision, nodeId) {
  requireTaskId(taskId, "getInventoryDetail");
  if (!isNonnegativeInteger(expectedRevision) || !isNodeId(nodeId)) {
    throw new TypeError("getInventoryDetail requires an exact revision and node");
  }
  return inventoryRead("get_inventory_detail", {task_id: taskId, expected_revision: expectedRevision, node_id: nodeId},
    (value) => validateInventoryDetail(value) && value.node_id === nodeId
      && (value.disposition === "conflict" || value.view_revision === expectedRevision));
}

export async function openPlanView(taskId) {
  requireTaskId(taskId, "openPlanView");
  const payload = Object.freeze({ task_id: taskId });
  const submit = () => dispatchAttempt(
    "open_plan_view", payload, validatePlanViewSummary, PLAN_VIEW_TIMEOUT_MS,
  );
  try {
    return await submit();
  } catch (error) {
    if (!(error instanceof BridgeTransportError)) throw error;
  }
  return submit();
}

export function updatePlanView(taskId, expectedRevision, view, onDelayed = null) {
  requireTaskId(taskId, "updatePlanView");
  if (!isNonnegativeInteger(expectedRevision) || !isPlanViewGesture(view)) {
    throw new TypeError("updatePlanView requires an exact revision and gesture");
  }
  return dispatchAttempt(
    "update_plan_view",
    Object.freeze({
      task_id: taskId,
      expected_revision: expectedRevision,
      search_query: view.searchQuery,
      filters: Object.freeze([...view.filters]),
      sort_column: view.sortColumn,
      sort_direction: view.sortDirection,
      collapse_node_id: view.collapseNodeId,
      collapsed: view.collapsed,
    }),
    validatePlanViewSummary,
    PLAN_VIEW_TIMEOUT_MS, false, onDelayed,
  );
}

export async function getPlanWindow(taskId, expectedRevision, offset, limit) {
  requireTaskId(taskId, "getPlanWindow");
  if (!isNonnegativeInteger(expectedRevision) || !isNonnegativeInteger(offset)
      || !Number.isInteger(limit) || limit < 1 || limit > 256) {
    throw new TypeError("getPlanWindow requires a bounded exact window");
  }
  const payload = Object.freeze({
    task_id: taskId, expected_revision: expectedRevision, offset, limit,
  });
  const submit = () => dispatchAttempt(
    "get_plan_window", payload, validatePlanWindow, PLAN_VIEW_TIMEOUT_MS,
  );
  try {
    return await submit();
  } catch (error) {
    if (!(error instanceof BridgeTransportError)) throw error;
  }
  return submit();
}

export async function getExecutionDetail(
  taskId, operationId, expectedExecutionRevision,
) {
  requireTaskId(taskId, "getExecutionDetail");
  if (typeof operationId !== "string" || !ID_PATTERN.test(operationId)
      || !isNonnegativeInteger(expectedExecutionRevision)) {
    throw new TypeError("getExecutionDetail requires an operation and execution revision");
  }
  const payload = Object.freeze({
    task_id: taskId,
    operation_id: operationId,
    expected_execution_revision: expectedExecutionRevision,
  });
  const validateResult = (value) => (
    validateExecutionDetail(value) && value.operation_id === operationId
  );
  const submit = () => dispatchAttempt(
    "get_execution_detail", payload, validateResult, PLAN_VIEW_TIMEOUT_MS,
  );
  try {
    return await submit();
  } catch (error) {
    if (!(error instanceof BridgeTransportError)) throw error;
  }
  return submit();
}

export async function getPlanAnchor(taskId, expectedRevision, nodeId) {
  requireTaskId(taskId, "getPlanAnchor");
  if (!isNonnegativeInteger(expectedRevision) || !isNodeId(nodeId)) {
    throw new TypeError("getPlanAnchor requires an exact revision and node");
  }
  const payload = Object.freeze({
    task_id: taskId, expected_revision: expectedRevision, node_id: nodeId,
  });
  const submit = () => dispatchAttempt(
    "get_plan_anchor", payload, validatePlanAnchor, PLAN_VIEW_TIMEOUT_MS,
  );
  try {
    return await submit();
  } catch (error) {
    if (!(error instanceof BridgeTransportError)) throw error;
  }
  return submit();
}

export class OutcomeUnavailableError extends BridgeTransportError {
  constructor() {
    super("The original action outcome cannot be confirmed. Close and reopen NamiSync to review its current state.");
    this.name = "OutcomeUnavailableError";
  }
}

export async function getPlanOperationAnchor(
  taskId, sessionId, expectedRevision, operationId,
) {
  requireTaskId(taskId, "getPlanOperationAnchor");
  if (typeof sessionId !== "string" || !ID_PATTERN.test(sessionId)
      || !isNonnegativeInteger(expectedRevision)
      || typeof operationId !== "string" || !ID_PATTERN.test(operationId)) {
    throw new TypeError(
      "getPlanOperationAnchor requires exact session, revision, and operation identities",
    );
  }
  const payload = Object.freeze({
    task_id: taskId,
    session_id: sessionId,
    expected_revision: expectedRevision,
    operation_id: operationId,
  });
  const submit = () => dispatchAttempt(
    "get_plan_anchor", payload, validatePlanAnchor, PLAN_VIEW_TIMEOUT_MS,
  );
  try {
    return await submit();
  } catch (error) {
    if (!(error instanceof BridgeTransportError)) throw error;
  }
  return submit();
}

export function mutatePlanSelection(
  taskId, expectedViewRevision, expectedSelectionRevision, nodeId, selected,
  onDelayed = null,
) {
  requireTaskId(taskId, "mutatePlanSelection");
  if (!isNonnegativeInteger(expectedViewRevision)
      || !isNonnegativeInteger(expectedSelectionRevision) || !isNodeId(nodeId)
      || typeof selected !== "boolean") {
    throw new TypeError("mutatePlanSelection requires exact view and selection revisions");
  }
  const payload = Object.freeze({
    task_id: taskId,
    command_id: mintId(),
    expected_view_revision: expectedViewRevision,
    expected_selection_revision: expectedSelectionRevision,
    node_id: nodeId,
    selected,
  });
  return dispatchAttempt(
    "mutate_plan_selection", payload, validatePlanViewSummary,
    PLAN_VIEW_TIMEOUT_MS, false, onDelayed,
  );
}

export function mutatePlanScope(
  taskId, expectedViewRevision, expectedSelectionRevision, selected,
  onDelayed = null,
) {
  requireTaskId(taskId, "mutatePlanScope");
  if (!isNonnegativeInteger(expectedViewRevision)
      || !isNonnegativeInteger(expectedSelectionRevision)
      || typeof selected !== "boolean") {
    throw new TypeError("mutatePlanScope requires exact view and selection revisions");
  }
  const payload = Object.freeze({
    task_id: taskId,
    command_id: mintId(),
    expected_view_revision: expectedViewRevision,
    expected_selection_revision: expectedSelectionRevision,
    selected,
  });
  return dispatchAttempt(
    "mutate_plan_scope", payload, validatePlanViewSummary,
    PLAN_VIEW_TIMEOUT_MS, false, onDelayed,
  );
}

export function mutatePlanHighlight(
  taskId, expectedViewRevision, expectedHighlightRevision, gesture, nodeId = null,
  onDelayed = null,
) {
  requireTaskId(taskId, "mutatePlanHighlight");
  const endpoints = new Set(["replace", "toggle", "extend", "add-range"]);
  const implicit = new Set([
    "clear", "move_up", "move_down", "move_up_extend", "move_down_extend",
  ]);
  if (!isNonnegativeInteger(expectedViewRevision)
      || !isNonnegativeInteger(expectedHighlightRevision)
      || !(endpoints.has(gesture) || implicit.has(gesture))
      || (endpoints.has(gesture) ? !isNodeId(nodeId) : nodeId !== null)) {
    throw new TypeError("mutatePlanHighlight requires exact revisions and gesture");
  }
  return dispatchAttempt(
    "mutate_plan_highlight",
    Object.freeze({
      task_id: taskId,
      expected_view_revision: expectedViewRevision,
      expected_highlight_revision: expectedHighlightRevision,
      gesture,
      node_id: nodeId,
    }),
    validatePlanViewSummary,
    PLAN_VIEW_TIMEOUT_MS, false, onDelayed,
  );
}

export function mutatePlanHighlightedSelection(
  taskId, expectedViewRevision, expectedHighlightRevision,
  expectedSelectionRevision, selected, onDelayed = null,
) {
  requireTaskId(taskId, "mutatePlanHighlightedSelection");
  if (!isNonnegativeInteger(expectedViewRevision)
      || !isNonnegativeInteger(expectedHighlightRevision)
      || !isNonnegativeInteger(expectedSelectionRevision)
      || typeof selected !== "boolean") {
    throw new TypeError(
      "mutatePlanHighlightedSelection requires exact revisions and selection",
    );
  }
  const payload = Object.freeze({
    task_id: taskId,
    command_id: mintId(),
    expected_view_revision: expectedViewRevision,
    expected_highlight_revision: expectedHighlightRevision,
    expected_selection_revision: expectedSelectionRevision,
    selected,
  });
  return dispatchAttempt(
    "mutate_plan_highlighted_selection", payload, validatePlanViewSummary,
    PLAN_VIEW_TIMEOUT_MS, false, onDelayed,
  );
}

export function startExecution(taskId, requestId, expectedRevision, destructiveAcknowledged = false, onDelayed = null) {
  requireTaskId(taskId, "startExecution");
  if (typeof requestId !== "string" || !ID_PATTERN.test(requestId)
      || !isNonnegativeInteger(expectedRevision)
      || typeof destructiveAcknowledged !== "boolean") {
    throw new TypeError("startExecution requires exact review commitment");
  }
  const payload = Object.freeze({
    task_id: taskId,
    request_id: requestId,
    command_id: mintId(),
    expected_revision: expectedRevision,
    destructive_acknowledged: destructiveAcknowledged,
  });
  return dispatchAttempt(
    "start_execution", payload, validateExecutionAdmission,
    EXECUTION_START_TIMEOUT_MS, true, onDelayed,
  ).catch((error) => {
    if (error instanceof OutcomeUnavailableError) throw new StartPlanUncertainError();
    throw error;
  });
}

export function controlExecution(taskId, sessionId, action, onDelayed = null) {
  requireTaskId(taskId, "controlExecution");
  const task = taskDrains.get(taskId);
  if (typeof sessionId !== "string" || !ID_PATTERN.test(sessionId)
      || !["pause", "resume", "cancel"].includes(action)
      || task === undefined || task.sessionId !== sessionId
      || task.stopped || task.terminal) {
    throw new TypeError("controlExecution requires the current live execution");
  }
  return dispatchAttempt(
    "control_execution",
    Object.freeze({ task_id: taskId, session_id: sessionId, action }),
    (value) => validateControlReceipt(value, sessionId),
    PLAN_VIEW_TIMEOUT_MS, false, onDelayed,
  );
}

export function admitLocation(purpose, value, onDelayed = null) {
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
    LOCATION_ADMIT_TIMEOUT_MS, false, onDelayed,
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
    TIMEOUT_MS_BY_POLICY[COMMAND_POLICY_CONTRACT.probe_recent_pairs.response_policy], true,
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
  onDelayed = null,
) {
  return dispatchAttemptWithReadiness(
    command,
    payload,
    validateResult,
    timeoutMs,
    whenBridgeReady,
    asyncSmall,
    onDelayed,
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
  onDelayed = null,
) {
  return createDispatchAttempt(
    command,
    payload,
    validateResult,
    timeoutMs,
    waitUntilReady,
    asyncSmall,
    onDelayed,
  ).promise;
}

function createDispatchAttempt(
  command, payload, validateResult, timeoutMs,
  waitUntilReady = whenBridgeReady, asyncSmall = false, onDelayed = null,
) {
  const requestId = mintId();
  const observed = COMMAND_POLICY_CONTRACT[command]?.response_policy === "mutation-observed";
  const feedbackOnly = COMMAND_POLICY_CONTRACT[command]?.response_policy === "feedback-only";
  if ((observed || asyncSmall) && commandAttempts.size >= COMMAND_MAX_ATTEMPTS) {
    throw new BridgeCommandError("bridge_busy", ERROR_MESSAGES.bridge_busy);
  }
  const attempt = {
    command, requestId, validateResult, observed, asyncSmall, feedbackOnly,
    onDelayed, generation: null, responseToken: null, completionToken: null,
    earlyCompletion: null, result: null, settling: false, cleanupOnly: false,
    nativeAckStarted: false,
    dispatched: false, cancelled: false, delayedTimer: null,
    observationRunning: null, rejectCancellation: null,
    recoveryState: "submitting", directDeliveryAlive: true,
    resolve: null, reject: null,
  };
  if (observed) {
    attempt.recovery = Object.freeze({
      get state() { return attempt.recoveryState; },
      get checking() { return attempt.result === null && attempt.observationRunning !== null; },
      get canCheck() {
        return attempt.result === null && attempt.dispatched
          && ["pending", "unavailable"].includes(attempt.recoveryState);
      },
      get message() {
        if (attempt.recoveryState === "fixed-unknown") {
          if (attempt.result?.error?.code === "invalid_result") {
            return "Original desktop result failed validation (invalid_result). Close and reopen NamiSync to review current state.";
          }
          return "Original outcome cannot be confirmed. Close and reopen NamiSync to review current state.";
        }
        if (attempt.recoveryState === "settled") return null;
        if (attempt.observationRunning !== null) return "Checking the original outcome…";
        if (attempt.recoveryState === "unavailable") {
          return "Outcome unavailable. Select Check outcome to observe the original request, or close and reopen NamiSync to review current state.";
        }
        if (attempt.recoveryState === "pending") {
          const liveDelivery = attempt.directDeliveryAlive
            || (attempt.asyncSmall && attempt.completionToken !== null
              && attempt.generation !== null);
          return liveDelivery
            ? "Response delayed. Waiting for the original outcome; Check outcome is available."
            : "Original result is still pending. Select Check outcome to observe the original request.";
        }
        return null;
      },
      check() {
        return attempt.recovery.canCheck ? recoverObservedResult(attempt) : Promise.resolve(null);
      },
    });
    notifyAttemptDelay(attempt);
  }
  const outcome = observed || asyncSmall ? new Promise((resolve, reject) => {
    attempt.resolve = resolve;
    attempt.reject = reject;
  }) : null;
  attempt.outcome = outcome;
  // An ordinary direct request has no late completion or observation to own.
  if (observed || asyncSmall) commandAttempts.set(requestId, attempt);
  const request = JSON.stringify({
    schema_version: BRIDGE_SCHEMA_VERSION, request_id: requestId,
    command, payload,
  });
  const dispatch = runAttempt(attempt, request, waitUntilReady);
  if (observed) {
    void dispatch.catch((error) => {
      if (!attempt.dispatched) {
        retireAttempt(attempt);
        attempt.reject(error instanceof BridgeTransportError ? error : new BridgeTransportError());
      } else {
        attempt.directDeliveryAlive = false;
        void recoverObservedResult(attempt);
      }
    });
    return { promise: outcome, cancel: () => {} };
  }
  // The completion promise is consumed only after a successful async admission.
  void outcome?.catch(() => {});
  const promise = withDeadline(dispatch, timeoutMs, () => cancelAttempt(attempt));
  return { promise, cancel: () => cancelAttempt(attempt) };
}

async function runAttempt(attempt, request, waitUntilReady) {
  try {
    if (attempt.observed || attempt.feedbackOnly) {
      await withDeadline(waitUntilReady(), SHELL_READY_TIMEOUT_MS, () => {});
    } else {
      await waitUntilReady();
    }
    if (attempt.cancelled) throw new BridgeTransportError();
    const api = bridgeApi();
    if (typeof api?.dispatch !== "function") throw new BridgeTransportError();
    const cancelled = new Promise((_resolve, reject) => {
      attempt.rejectCancellation = reject;
    });
    if (attempt.observed || attempt.feedbackOnly) {
      attempt.delayedTimer = setTimeout(() => {
        if (attempt.result !== null) return;
        if (attempt.observed) attempt.recoveryState = "pending";
        notifyAttemptDelay(attempt, "pending");
        if (attempt.observed) void recoverObservedResult(attempt);
      }, MUTATION_FEEDBACK_MS);
    }
    // No await occurs between the last cancellation check and native admission.
    attempt.dispatched = true;
    const transport = Promise.resolve(api.dispatch(request)).then(
      (native) => acceptNativeResponse(attempt, api, native),
    );
    const kind = attempt.observed
      ? await transport : await Promise.race([transport, cancelled]);
    if (kind === "admitted") {
      return attempt.observed ? undefined
        : await Promise.race([attempt.outcome, cancelled]);
    }
    return attempt.observed ? undefined : resultFor(attempt);
  } catch (error) {
    if (!attempt.observed) {
      if (attempt.dispatched && attempt.asyncSmall) attempt.cleanupOnly = true;
      else retireAttempt(attempt);
    }
    if (error instanceof BridgeCommandError || error instanceof BridgeTransportError) throw error;
    throw new BridgeTransportError();
  } finally {
    attempt.rejectCancellation = null;
    if (!attempt.observed) clearTimeout(attempt.delayedTimer);
  }
}

function resultFor(attempt) {
  if (attempt.result.error !== null) throw attempt.result.error;
  return attempt.result.value;
}

async function acceptNativeResponse(attempt, api, native) {
  const direct = isExactObject(native, ["transport_version", "response_token", "response"]);
  const admitted = isExactObject(native, ["transport_version", "response_token", "completion"]);
  if ((!direct && !admitted) || native.transport_version !== NATIVE_TRANSPORT_VERSION
      || (admitted && native.response_token === null)
      || (native.response_token !== null
        && (typeof native.response_token !== "string"
          || !ID_PATTERN.test(native.response_token)))
      || (attempt.responseToken !== null && native.response_token !== null
        && attempt.responseToken !== native.response_token)) {
    throw new BridgeTransportError();
  }
  if (native.response_token !== null) attempt.responseToken = native.response_token;
  if (direct) {
    const response = cloneJsonValue(native.response);
    settleAttemptResponse(attempt, response);
    if (!attempt.observed) acknowledgeNativeAdmission(attempt, api);
    return "direct";
  }
  const completion = cloneJsonValue(native.completion);
  if (!attempt.asyncSmall || !isExactObject(completion, [
    "phase", "generation", "request_id", "completion_token",
  ]) || completion.phase !== COMMAND_COMPLETION_PHASE
      || !Number.isSafeInteger(completion.generation) || completion.generation < 0
      || completion.request_id !== attempt.requestId
      || typeof completion.completion_token !== "string"
      || !ID_PATTERN.test(completion.completion_token)
      || (attempt.generation !== null && attempt.generation !== completion.generation)
      || (commandHostGeneration !== null && commandHostGeneration !== completion.generation)
      || (attempt.completionToken !== null
        && attempt.completionToken !== completion.completion_token)) {
    throw new BridgeTransportError();
  }
  attempt.generation = completion.generation;
  attempt.completionToken = completion.completion_token;
  commandHostGeneration = completion.generation;
  acknowledgeNativeAdmission(attempt, api);
  if (attempt.earlyCompletion !== null) {
    const early = attempt.earlyCompletion;
    attempt.earlyCompletion = null;
    void acceptCompletion(attempt, early);
  }
  return "admitted";
}

function acknowledgeNativeAdmission(attempt, api) {
  if (attempt.responseToken === null || attempt.nativeAckStarted) return;
  attempt.nativeAckStarted = true;
  void acknowledgeCleanup(api, `ack:${attempt.responseToken}`).catch(() => {});
}

function captureAttemptResponse(attempt, response) {
  let value;
  let error = null;
  try {
    value = validateResponse(response, attempt.requestId, attempt.validateResult);
  } catch (failure) {
    error = failure;
  }
  if (attempt.observed && error !== null && !(error instanceof BridgeCommandError)
      && response !== null && typeof response === "object"
      && response.request_id === attempt.requestId) {
    error = new OutcomeUnavailableError();
    error.code = "invalid_result";
  }
  if (attempt.observed && error !== null && !(error instanceof BridgeCommandError)
      && !(error instanceof OutcomeUnavailableError)) {
    throw error;
  }
  if (attempt.observed && ["internal_error", "response_too_large"].includes(error?.code)) {
    error = new OutcomeUnavailableError();
  }
  return { value, error };
}

function settleAttemptResponse(attempt, response) {
  if (attempt.result !== null) return;
  const { value, error } = captureAttemptResponse(attempt, response);
  attempt.result = { value, error };
  clearTimeout(attempt.delayedTimer);
  if (attempt.observed) {
    attempt.recoveryState = error instanceof OutcomeUnavailableError ? "fixed-unknown" : "settled";
    notifyAttemptDelay(attempt);
  }
  if (attempt.observed) acknowledgeNativeAdmission(attempt, bridgeApi());
  if (attempt.completionToken !== null && attempt.observed) {
    void acknowledgeCommandCompletion({
      generation: attempt.generation, request_id: attempt.requestId,
      completion_token: attempt.completionToken,
    }).catch(() => {});
  }
  if (attempt.observed || attempt.asyncSmall) {
    retireAttempt(attempt);
    if (error === null) attempt.resolve(value);
    else attempt.reject(error);
  }
}

function notifyAttemptDelay(attempt, status) {
  try {
    attempt.onDelayed?.(attempt.observed ? attempt.recovery : { state: status, check: null });
  } catch (_error) { /* Presentation cannot change custody. */ }
}

function retireAttempt(attempt) {
  if (commandAttempts.get(attempt.requestId) === attempt) {
    commandAttempts.delete(attempt.requestId);
  }
  clearTimeout(attempt.delayedTimer);
}

async function recoverObservedResult(attempt) {
  if (attempt.result !== null) return attempt.result;
  if (attempt.observationRunning !== null) return attempt.observationRunning;
  const run = (async () => {
    let latestStatus = "unavailable";
    for (let index = 0; index < 3; index += 1) {
      if (attempt.result !== null) break;
      if (index > 0) await delay(OBSERVATION_DELAYS_MS[index - 1]);
      try {
        const api = bridgeApi();
        if (typeof api?.dispatch !== "function") throw new BridgeTransportError();
        const observed = await withDeadline(
          Promise.resolve(api.dispatch(`observe:${attempt.requestId}:${attempt.command}`)),
          OBSERVATION_TIMEOUT_MS, () => {},
        );
        const status = acceptObservedObservation(attempt, observed);
        latestStatus = status;
      } catch (_error) {
        latestStatus = "unavailable";
      }
    }
    if (attempt.result === null) {
      clearTimeout(attempt.delayedTimer);
      attempt.recoveryState = latestStatus;
      notifyAttemptDelay(attempt);
    }
    return attempt.result;
  })();
  attempt.observationRunning = run;
  if (attempt.result === null) notifyAttemptDelay(attempt);
  try {
    return await run;
  } finally {
    if (attempt.observationRunning === run) {
      attempt.observationRunning = null;
      if (attempt.result === null) notifyAttemptDelay(attempt);
    }
  }
}

function acceptObservedObservation(attempt, observed) {
  if (!isExactObject(observed, [
    "transport_version", "state", "generation", "request_id",
    "response_token", "completion_token", "response",
  ]) || observed.transport_version !== NATIVE_TRANSPORT_VERSION
      || !["pending", "ready", "unavailable"].includes(observed.state)
      || !Number.isSafeInteger(observed.generation) || observed.generation < 0
      || observed.request_id !== attempt.requestId
      || (attempt.generation !== null && attempt.generation !== observed.generation)
      || (commandHostGeneration !== null && commandHostGeneration !== observed.generation)
      || (observed.response_token !== null
        && (typeof observed.response_token !== "string"
          || !ID_PATTERN.test(observed.response_token)))
      || (observed.completion_token !== null
        && (typeof observed.completion_token !== "string"
          || !ID_PATTERN.test(observed.completion_token)))
      || (attempt.responseToken !== null && observed.response_token !== null
        && attempt.responseToken !== observed.response_token)
      || (attempt.completionToken !== null && observed.completion_token !== null
        && attempt.completionToken !== observed.completion_token)
      || (!attempt.asyncSmall && observed.completion_token !== null)) {
    throw new BridgeTransportError();
  }
  if (observed.state === "unavailable") {
    if (observed.response_token !== null || observed.completion_token !== null
        || observed.response !== null) throw new BridgeTransportError();
    return "unavailable";
  }
  if (observed.state === "pending" && observed.response !== null) {
    throw new BridgeTransportError();
  }
  if (observed.state === "ready"
      && (observed.response_token === null || observed.response === null)) {
    throw new BridgeTransportError();
  }
  attempt.generation = observed.generation;
  commandHostGeneration = observed.generation;
  if (observed.response_token !== null) attempt.responseToken = observed.response_token;
  if (observed.completion_token !== null) {
    attempt.completionToken = observed.completion_token;
    if (attempt.earlyCompletion !== null) {
      const early = attempt.earlyCompletion;
      attempt.earlyCompletion = null;
      void acceptCompletion(attempt, early);
    }
  }
  if (observed.state === "ready" && attempt.result === null) {
    settleAttemptResponse(attempt, cloneJsonValue(observed.response));
  }
  return observed.state;
}

function receiveCommandCompletion(event) {
  const message = event?.data;
  if (!isCommandCompletionMessage(message)) return;
  const attempt = commandAttempts.get(message.request_id);
  if (attempt === undefined || !attempt.asyncSmall || attempt.result !== null
      || (attempt.generation !== null && attempt.generation !== message.generation)
      || (attempt.completionToken !== null
        && attempt.completionToken !== message.completion_token)) return;
  let captured;
  try { captured = cloneJsonValue(message); } catch { return; }
  if (attempt.completionToken === null) {
    if (attempt.earlyCompletion === null) attempt.earlyCompletion = captured;
    return;
  }
  void acceptCompletion(attempt, captured);
}

async function acceptCompletion(attempt, message) {
  if (attempt.settling || attempt.result !== null
      || attempt.generation !== message.generation
      || attempt.requestId !== message.request_id
      || attempt.completionToken !== message.completion_token) return;
  attempt.settling = true;
  try {
    if (attempt.cleanupOnly) {
      captureAttemptResponse(attempt, message.response);
      retireAttempt(attempt);
    } else {
      settleAttemptResponse(attempt, message.response);
    }
  } catch (_error) {
    attempt.settling = false;
    if (!attempt.observed && !attempt.cleanupOnly) {
      retireAttempt(attempt);
      attempt.reject(new BridgeTransportError());
    }
    return;
  }
  if (!attempt.observed) void acknowledgeCommandCompletion(message).catch(() => {});
}

async function acknowledgeCommandCompletion(message) {
  const api = bridgeApi();
  if (commandHostGeneration === null
      || message.generation !== commandHostGeneration
      || typeof api?.dispatch !== "function") throw new BridgeTransportError();
  return acknowledgeCleanup(api, [
    "ack", COMMAND_COMPLETION_PHASE, String(message.generation),
    message.request_id, message.completion_token,
  ].join(":"));
}

async function acknowledgeCleanup(api, acknowledgment) {
  let firstDeliveryUncertain = false;
  for (let index = 0; index < 2; index += 1) {
    if (typeof api?.dispatch !== "function") throw new BridgeTransportError();
    try {
      const acknowledged = await withDeadline(
        Promise.resolve(api.dispatch(acknowledgment)),
        ASYNC_CLEANUP_ACK_TIMEOUT_MS, () => {},
      );
      if (acknowledged === true || (firstDeliveryUncertain && acknowledged === false)) {
        return;
      }
    } catch (_error) {
      if (index === 0) firstDeliveryUncertain = true;
    }
  }
  throw new BridgeTransportError();
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

function cancelAttempt(attempt) {
  if (attempt.cancelled) return;
  attempt.cancelled = true;
  if (attempt.dispatched && attempt.asyncSmall) attempt.cleanupOnly = true;
  else retireAttempt(attempt);
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
    if (response.request_id !== requestId || !("result" in response)) {
      throw new BridgeTransportError();
    }
    if (!validateResult(response.result)) throw new BridgeTransportError();
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
  if (task.stopped || task.suspended || task.terminal || task.pendingTerminalUpdate !== null) {
    return;
  }
  task.epoch += 1;
  task.desiredReplayFrom = replayFrom;
  task.active?.control.cancel();
  task.active = null;
  cancelTaskArm(task);
  if (!operational) {
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
      task.suspended ||
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
    !task.suspended &&
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
  let snapshotDelivered = false;
  for (let index = 0; index < result.updates.length; index += 1) {
    if (task.stopped || task.terminal || task.epoch !== active.epoch) {
      return;
    }
    const update = result.updates[index];
    const snapshot = index === result.updates.length - 1 ? result.snapshot : null;
    if (update.update_type === "record") {
      presentTerminalUpdate(task, update, result.snapshot);
      if (task.terminal && isCurrentTaskEpoch(task, active)) {
        task.recoveryPending = false;
      }
      return;
    }
    const event = update.event;
    if (event.body_type === "Gap") {
      if (!deliverTaskUpdate(task, update, task.lastAcceptedSequence, snapshot)) {
        return;
      }
      snapshotDelivered = snapshot !== null;
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
    const previousSequence = task.lastAcceptedSequence;
    task.lastAcceptedSequence = event.sequence;
    if (!deliverTaskUpdate(task, update, previousSequence, snapshot)) {
      return;
    }
    snapshotDelivered = snapshot !== null;
  }
  if (!snapshotDelivered && !deliverTaskUpdate(task, null, task.lastAcceptedSequence, result.snapshot)) return;
  if (!notifyTaskRecovered(task, active)) return;
  rearmTask(task, null);
}

function isCurrentTaskEpoch(task, active) {
  return !task.stopped && !task.suspended &&
    taskDrains.get(task.taskId) === task && task.epoch === active.epoch;
}

function notifyTaskRecovered(task, active) {
  if (!isCurrentTaskEpoch(task, active)) return false;
  if (!task.recoveryPending) return true;
  try {
    task.acceptRecovered?.(task.taskId, task.sessionId);
  } catch (_error) {
    stopTaskWithRefusal(task, new BridgeTransportError("The desktop update could not be applied."));
    return false;
  }
  if (!isCurrentTaskEpoch(task, active)) return false;
  task.recoveryPending = false;
  return true;
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

function validateShellReadyResult(value) {
  return isExactObject(value, ["acknowledged"]) && value.acknowledged === true;
}

function validateReadinessEchoResult(value) {
  return isExactObject(value, ["acknowledged"])
    && typeof value.acknowledged === "boolean";
}

function presentTerminalUpdate(task, update, snapshot) {
  if (task.stopped || task.terminal || taskDrains.get(task.taskId) !== task) {
    return;
  }
  if (task.pendingTerminalUpdate === null) {
    task.pendingTerminalUpdate = freezeJsonValue({
      update: cloneJsonValue(update), snapshot: cloneJsonValue(snapshot),
    });
  }
  if (task.terminalPresentationInProgress) {
    return;
  }
  task.terminalPresentationInProgress = true;
  try {
    task.acceptUpdate(
      cloneJsonValue(task.pendingTerminalUpdate.update),
      freezeJsonValue(cloneJsonValue(task.pendingTerminalUpdate.snapshot)),
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
  task.snapshotRevision = task.pendingTerminalUpdate.snapshot.revision;
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
  presentTerminalUpdate(task, task.pendingTerminalUpdate.update, task.pendingTerminalUpdate.snapshot);
}

function deliverTaskUpdate(task, update, previousSequence, snapshot) {
  try {
    task.acceptUpdate(update, snapshot === null ? null : freezeJsonValue(cloneJsonValue(snapshot)));
    if (snapshot !== null) task.snapshotRevision = snapshot.revision;
    return true;
  } catch (_error) {
    task.lastAcceptedSequence = previousSequence;
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
  task.suspended = true;
  task.epoch += 1;
  task.active?.control.cancel();
  task.active = null;
  cancelTaskArm(task);
  reportTaskRefusal(task, error, () => retryTaskDrain(task));
}

function retryTaskDrain(task) {
  if (
    task.stopped || !task.suspended || task.terminal ||
    taskDrains.get(task.taskId) !== task || taskCloseFences.has(task.taskId)
  ) return false;
  task.suspended = false;
  task.recoveryPending = true;
  task.busyRearmUsed = false;
  task.transportFailures = 0;
  rearmTask(task, task.lastAcceptedSequence + 1);
  return true;
}

function reportTaskRefusal(task, error, retry = null) {
  try {
    task.acceptRefusal(error, retry);
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
  if (taskDrains.get(task.taskId) === task) {
    taskDrains.delete(task.taskId);
  }
}

function beginTaskRelease(task) {
  if (task.releaseControl !== null) {
    return;
  }
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
      (status) => {
        if (!isCurrentTaskRelease(task, epoch)) return;
        try {
          task.acceptReleaseDelay?.(task.taskId, task.sessionId, status);
        } catch (_error) { /* Presentation cannot change release custody. */ }
      },
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
  if (task.acceptRelease !== null) {
    try {
      task.acceptRelease(task.taskId, task.sessionId);
    } catch (_error) {
      reportTaskRefusal(
        task,
        new BridgeTransportError("The completed task could not be presented."),
      );
    }
  }
}

function refuseTaskRelease(task, epoch, error) {
  if (!isCurrentTaskRelease(task, epoch)) {
    return;
  }
  task.releaseControl = null;
  if (error instanceof OutcomeUnavailableError) {
    reportTaskRefusal(task, new TerminalSessionReleaseError(null, true));
    return;
  }
  reportTaskRefusal(task, new TerminalSessionReleaseError(() => beginTaskRelease(task)));
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

function validateTaskDrainResult(value, task, drainId, replayFrom) {
  return (
    isExactObject(value, ["task_id", "session_id", "drain_id", "updates", "snapshot"]) &&
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
    validateTaskSnapshot(value.snapshot, task, value.updates)
  );
}

function validPercentage(value) {
  return value === null || (typeof value === "number" && Number.isFinite(value)
    && value >= 0 && value <= 100);
}

function validEstimate(value) {
  return value === null || (typeof value === "number" && Number.isFinite(value)
    && value >= 0);
}

function validateTaskSnapshot(snapshot, task, updates) {
  if (!isExactObject(snapshot, [
    "wire_version", "task_id", "session_id", "revision", "session_state",
    "control_state", "phase", "active_item", "progress_inconsistent",
    "presentation", "gap_first_missed_seq", "terminal_result", "started_at", "ended_at",
  ]) || snapshot.wire_version !== 2 || snapshot.task_id !== task.taskId
    || snapshot.session_id !== task.sessionId || !isNonnegativeInteger(snapshot.revision)
    || (task.snapshotRevision !== null && snapshot.revision < task.snapshotRevision)
    || !isOneOf(snapshot.session_state, ["active", ...TERMINAL_STATES])
    || !isOneOf(snapshot.control_state, ["running", "pausing", "paused", "canceling"])
    || !(snapshot.phase === null || (typeof snapshot.phase === "string"
      && snapshot.phase.length > 0 && isValidUnicode(snapshot.phase)))
    || typeof snapshot.progress_inconsistent !== "boolean"
    || !isNullableNonnegativeInteger(snapshot.gap_first_missed_seq)
    || snapshot.gap_first_missed_seq === 0
    || !(snapshot.started_at === null || isUtcTimestamp(snapshot.started_at))
    || !(snapshot.ended_at === null || isUtcTimestamp(snapshot.ended_at))) return false;
  if (snapshot.session_state === "active" && snapshot.ended_at !== null) return false;
  if (snapshot.session_state !== "active" && (snapshot.ended_at === null
    || snapshot.phase !== null || snapshot.active_item !== null)) return false;
  const active = snapshot.active_item;
  if (active !== null && (!isExactObject(active, ["item_id", "item_type"])
    || typeof active.item_id !== "string" || active.item_id.length === 0
    || !isValidUnicode(active.item_id)
    || !isOneOf(active.item_type, ["operation", "integrity"]))) return false;
  const display = snapshot.presentation;
  if (!isExactObject(display, [
    "item_percent", "items_done", "items_total",
    "value", "determinate", "indeterminate",
    "throughput_bytes_per_second", "eta_seconds",
  ]) || !validPercentage(display.item_percent)
    || !isNullableNonnegativeInteger(display.items_done)
    || !isNullableNonnegativeInteger(display.items_total)
    || !validPercentage(display.value) || display.value === null
    || typeof display.determinate !== "boolean"
    || typeof display.indeterminate !== "boolean"
    || !validEstimate(display.throughput_bytes_per_second)
    || !validEstimate(display.eta_seconds)) return false;
  const result = snapshot.terminal_result;
  if (result !== null && !validateOperationResultView(result)) return false;
  if (snapshot.session_state === "active" && result !== null) return false;
  if (snapshot.session_state !== "active" && result === null) return false;
  if (result !== null && snapshot.session_state !== (result.canceled ? "canceled" : result.filesystem)) return false;
  const record = updates.at(-1)?.update_type === "record" ? updates.at(-1).record : null;
  if (record !== null) {
    if (snapshot.session_state !== record.state || snapshot.started_at !== record.started_at
      || snapshot.ended_at !== record.ended_at || result === null
      || Object.keys(result).some((key) => JSON.stringify(result[key]) !== JSON.stringify(record.result[key]))) return false;
  }
  return true;
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
    isOneOf(record.kind, ["sync-plan", "inventory", "sync-execution"]) &&
    isOneOf(record.state, TERMINAL_STATES) &&
    record.supports_pause === (record.kind === "sync-execution") &&
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

function isBoundedPath(value) {
  return typeof value === "string" && value.length > 0
    && value.length <= 32767 && isValidUnicode(value);
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

function requireTaskId(taskId, operation) {
  if (typeof taskId !== "string" || !TASK_PATTERN.test(taskId)) {
    throw new TypeError(`${operation} requires a task id`);
  }
}

function isNodeId(value) {
  return typeof value === "string" && /^node-[0-9a-f]{32}$/.test(value);
}

const INVENTORY_FILTERS = new Set([
  "present", "unverified", "verified", "modified", "reappeared", "unsupported",
  "missing", "mismatched", "acknowledged", "notice",
]);

function isPlanViewGesture(value) {
  const filters = new Set([
    "copy", "mkdir", "move", "recase", "update", "move_update",
    "trash", "delete", "noop", "blocked", "error", "unsupported", "notice",
  ]);
  return isTreeViewGesture(value, filters);
}

function isTreeViewGesture(value, filters) {
  return isExactObject(value, [
    "searchQuery", "filters", "sortColumn", "sortDirection",
    "collapseNodeId", "collapsed",
  ]) && isValidUnicode(value.searchQuery)
    && new TextEncoder().encode(value.searchQuery).length <= 65536
    && Array.isArray(value.filters) && value.filters.length <= filters.size
    && value.filters.every((item) => filters.has(item))
    && new Set(value.filters).size === value.filters.length
    && ["path", "filename", "size", "mtime"].includes(value.sortColumn)
    && ["ascending", "descending"].includes(value.sortDirection)
    && !(value.sortColumn === "path" && value.sortDirection !== "ascending")
    && (value.collapseNodeId === null || isNodeId(value.collapseNodeId))
    && (value.collapsed === null || typeof value.collapsed === "boolean")
    && ((value.collapseNodeId === null) === (value.collapsed === null));
}

function validateInventoryRollup(value) {
  const counts = ["domain_count", "file_count", "present", "unverified", "verified", "modified",
    "reappeared", "unsupported", "missing", "mismatched", "acknowledged"];
  return isExactObject(value, [...counts, "size", "size_overflow", "size_partial"])
    && counts.every((key) => isNonnegativeInteger(value[key]))
    && (value.size === null || isScalar64(value.size))
    && typeof value.size_overflow === "boolean" && typeof value.size_partial === "boolean"
    && (value.size_overflow === (value.size === null));
}

function validateInventorySummary(value) {
  return isExactObject(value, ["disposition", "task_id", "request_id", "location_id", "view_revision",
    "root_path", "scan_complete", "observed_count", "missing_count", "warning_count", "rollup",
    "visible_row_count", "search_query", "filters", "sort_column", "sort_direction", "collapsed_count"])
    && ["opened", "current", "conflict", "noop"].includes(value.disposition)
    && typeof value.task_id === "string" && TASK_PATTERN.test(value.task_id)
    && typeof value.request_id === "string" && ID_PATTERN.test(value.request_id)
    && isScalar64(value.location_id) && value.location_id !== "0"
    && ["view_revision", "observed_count", "missing_count", "warning_count", "visible_row_count", "collapsed_count"]
      .every((key) => isNonnegativeInteger(value[key]))
    && (value.root_path === null || isBoundedPath(value.root_path))
    && typeof value.scan_complete === "boolean" && validateInventoryRollup(value.rollup)
    && isTreeViewGesture({searchQuery: value.search_query, filters: value.filters,
      sortColumn: value.sort_column, sortDirection: value.sort_direction,
      collapseNodeId: null, collapsed: null}, INVENTORY_FILTERS);
}

function validateInventoryWindow(value) {
  return isExactObject(value, ["disposition", "view_revision", "offset", "total", "rows"])
    && ["current", "conflict"].includes(value.disposition)
    && [value.view_revision, value.offset, value.total].every(isNonnegativeInteger)
    && Array.isArray(value.rows) && value.rows.length <= 256
    && (value.disposition !== "conflict" || (value.rows.length === 0 && value.total === 0))
    && value.rows.every((row, index) => validateInventoryRow(row)
      && row.visible_index === value.offset + index && row.visible_index < value.total)
    && new Set(value.rows.map((row) => row.node_id)).size === value.rows.length;
}

function validateInventoryRow(value) {
  return isExactObject(value, ["node_id", "display", "depth", "is_container", "visible_index",
    "parent_visible_index", "first_child_visible_index", "position_in_set", "set_size", "expanded",
    "row_kind", "row_id", "presence", "verification_state", "has_baseline", "acknowledged",
    "reappeared", "size", "mtime_ns", "rollup", "warning"])
    && isNodeId(value.node_id) && isValidUnicode(value.display)
    && [value.depth, value.visible_index, value.position_in_set, value.set_size].every(isNonnegativeInteger)
    && value.position_in_set > 0 && value.position_in_set <= value.set_size
    && [value.parent_visible_index, value.first_child_visible_index].every(isNullableNonnegativeInteger)
    && (value.parent_visible_index === null || value.parent_visible_index < value.visible_index)
    && (value.first_child_visible_index === null || value.first_child_visible_index > value.visible_index)
    && typeof value.is_container === "boolean" && (value.expanded === null || typeof value.expanded === "boolean")
    && ["folder", "subject", "notice"].includes(value.row_kind)
    && (value.row_id === null || (isScalar64(value.row_id) && value.row_id !== "0"))
    && (value.presence === null || ["present", "missing", "unsupported"].includes(value.presence))
    && (value.verification_state === null || ["unverified", "verified", "modified", "mismatched"].includes(value.verification_state))
    && ((value.row_id === null) === (value.presence === null))
    && ((value.row_id === null) === (value.verification_state === null))
    && [value.has_baseline, value.acknowledged, value.reappeared].every((item) => typeof item === "boolean")
    && [value.size, value.mtime_ns].every((item) => item === null || isScalar64(item))
    && validateInventoryRollup(value.rollup)
    && (value.warning === null || (isExactObject(value.warning, ["code", "path", "detail"])
      && isBoundedV5Text(value.warning.code, true)
      && (value.warning.path === null || value.warning.path === "" || isBoundedPath(value.warning.path)) && isValidUnicode(value.warning.detail)))
    && ((value.row_kind === "notice") === (value.warning !== null))
    && (value.warning === null || (value.row_id === null && !value.is_container));
}

function validateInventorySubject(value) {
  return isExactObject(value, ["kind", "size", "mtime_ns", "file_identity"])
    && ["file", "directory"].includes(value.kind) && isScalar64(value.size) && isScalar64(value.mtime_ns)
    && (value.file_identity === null || (isExactObject(value.file_identity, ["volume_serial", "file_index"])
      && isValidUnicode(value.file_identity.volume_serial) && value.file_identity.volume_serial.length > 0
      && typeof value.file_identity.file_index === "string" && /^(?:0|[1-9][0-9]*)$/.test(value.file_identity.file_index)
      && BigInt(value.file_identity.file_index) <= 340282366920938463463374607431768211455n));
}

function validateInventoryDetail(value) {
  if (!isExactObject(value, ["disposition", "view_revision", "node_id", "detail"])
      || !["current", "conflict", "unavailable"].includes(value.disposition)
      || !isNonnegativeInteger(value.view_revision) || !isNodeId(value.node_id)) return false;
  if (value.disposition !== "current") return value.detail === null;
  const detail = value.detail;
  if (!isExactObject(detail, ["row", "observed", "attestation"])) return false;
  const row = detail.row;
  const times = ["last_observed_at", "last_verified_at", "missing_since", "acknowledged_at", "reappeared_at", "verification_invalidated_at"];
  if (!isExactObject(row, ["row_id", "location_id", "path", "path_key", "entry_kind", "presence",
    "size", "mtime_ns", "has_baseline", ...times, "unsupported_reason", "verification_state", "verification_invalidated_reason"])
    || !isScalar64(row.row_id) || row.row_id === "0" || !isScalar64(row.location_id) || row.location_id === "0"
    || !isBoundedPath(row.path) || !isValidUnicode(row.path_key)
    || ![null, "file", "directory"].includes(row.entry_kind) || !["present", "missing", "unsupported"].includes(row.presence)
    || !["unverified", "verified", "modified", "mismatched"].includes(row.verification_state)
    || ![row.size, row.mtime_ns].every((item) => item === null || isScalar64(item))
    || typeof row.has_baseline !== "boolean" || !times.every((key) => row[key] === null || isUtcTimestamp(row[key]))
    || ![row.unsupported_reason, row.verification_invalidated_reason].every((item) => item === null || isValidUnicode(item))
    || (detail.observed !== null && !validateInventorySubject(detail.observed))
    || row.has_baseline !== (detail.attestation !== null)) return false;
  if (detail.attestation === null) return true;
  if (!isExactObject(detail.attestation, ["content", "subject"]) || !validateInventorySubject(detail.attestation.subject)) return false;
  const content = detail.attestation.content;
  return isExactObject(content, ["algorithm", "digest", "size", "provenance", "observed_at"])
    && content.algorithm === "xxh3_128" && typeof content.digest === "string" && /^[0-9a-f]{32}$/.test(content.digest)
    && isScalar64(content.size) && content.size === detail.attestation.subject.size
    && ["copy", "readback", "verify"].includes(content.provenance) && isUtcTimestamp(content.observed_at);
}

function validatePlanViewSummary(value) {
  return isExactObject(value, [
    "disposition", "task_id", "request_id", "view_revision",
    "selection_revision", "selection_state", "highlight_revision",
    "highlight_anchor_node_id", "highlight_focus_node_id",
    "highlight_focus_visible_index", "highlighted_count",
    "source_path", "target_path",
    "selected_operation_count", "selectable_operation_count", "operation_count",
    "filter_counts",
    "scope_selected_operation_count", "scope_selectable_operation_count",
    "preflight_ready", "preflight_refusal_count", "warning_count",
    "requires_destructive_confirmation", "destructive_operation_count",
    "destructive_operation_counts", "irreversible_operation_count",
    "irreversible_update_count", "required_bytes",
    "visible_row_count", "search_query", "filters", "sort_column",
    "sort_direction", "collapsed_count", "execution",
  ])
    && ["opened", "current", "applied", "noop", "conflict", "in-flight", "frozen"]
      .includes(value.disposition)
    && typeof value.task_id === "string" && TASK_PATTERN.test(value.task_id)
    && typeof value.request_id === "string" && ID_PATTERN.test(value.request_id)
    && [value.view_revision, value.selection_revision,
      value.highlight_revision, value.highlighted_count,
      value.selected_operation_count, value.selectable_operation_count,
      value.operation_count, value.scope_selected_operation_count,
      value.scope_selectable_operation_count, value.visible_row_count,
      value.collapsed_count]
      .every(isNonnegativeInteger)
    && (value.highlight_anchor_node_id === null || isNodeId(value.highlight_anchor_node_id))
    && (value.highlight_focus_node_id === null || isNodeId(value.highlight_focus_node_id))
    && (value.highlight_focus_visible_index === null
      || isNonnegativeInteger(value.highlight_focus_visible_index))
    && (value.highlight_focus_node_id !== null
      || value.highlight_focus_visible_index === null)
    && value.scope_selected_operation_count <= value.selected_operation_count
    && isExactObject(value.filter_counts, [
      "all", "copy", "mkdir", "move", "recase", "update", "move_update",
      "trash", "delete", "noop", "blocked", "error", "unsupported", "notice",
    ])
    && Object.values(value.filter_counts).every(isNonnegativeInteger)
    && value.filter_counts.all === Object.entries(value.filter_counts)
      .filter(([category]) => category !== "all")
      .reduce((total, [, count]) => total + count, 0)
    && value.operation_count <= value.filter_counts.all
    && typeof value.preflight_ready === "boolean"
    && isNonnegativeInteger(value.preflight_refusal_count)
    && isNonnegativeInteger(value.warning_count)
    && typeof value.requires_destructive_confirmation === "boolean"
    && isNonnegativeInteger(value.destructive_operation_count)
    && isExactObject(value.destructive_operation_counts, [
      "update", "move_update", "trash", "delete",
    ])
    && Object.values(value.destructive_operation_counts).every(isNonnegativeInteger)
    && isNonnegativeInteger(value.irreversible_operation_count)
    && isNonnegativeInteger(value.irreversible_update_count)
    && isScalar64(value.required_bytes)
    && ["reviewing", "committing", "committed"].includes(value.selection_state)
    && isValidUnicode(value.source_path) && isValidUnicode(value.target_path)
    && isValidUnicode(value.search_query)
    && Array.isArray(value.filters)
    && value.filters.every((item) => typeof item === "string")
    && ["path", "filename", "size", "mtime"].includes(value.sort_column)
    && ["ascending", "descending"].includes(value.sort_direction)
    && value.selected_operation_count <= value.selectable_operation_count
    && value.scope_selected_operation_count <= value.scope_selectable_operation_count
    && value.scope_selectable_operation_count <= value.selectable_operation_count
    && value.selectable_operation_count <= value.operation_count
    && value.destructive_operation_count <= value.selected_operation_count
    && Object.values(value.destructive_operation_counts)
      .reduce((total, count) => total + count, 0) === value.destructive_operation_count
    && value.irreversible_update_count <= value.destructive_operation_counts.update
    && value.irreversible_operation_count
      === value.destructive_operation_counts.delete + value.irreversible_update_count
    && value.requires_destructive_confirmation
      === (value.destructive_operation_count > 0)
    && validateExecutionSummary(value.execution);
}

function validateExecutionSummary(value) {
  if (!isExactObject(value, [
    "execution_revision", "session_id", "result", "failed_operation_count",
    "disk_capacity_failure_count", "gap", "trash_location", "started_at", "ended_at",
  ]) || !isNonnegativeInteger(value.execution_revision)
      || !(value.session_id === null
        || (typeof value.session_id === "string" && ID_PATTERN.test(value.session_id)))) {
    return false;
  }
  const terminalAbsent = value.result === null
    && value.failed_operation_count === null
    && value.disk_capacity_failure_count === null
    && value.trash_location === null
    && value.started_at === null
    && value.ended_at === null;
  const terminalPresent = validateOperationResultView(value.result)
    && isNonnegativeInteger(value.failed_operation_count)
    && isNonnegativeInteger(value.disk_capacity_failure_count)
    && value.disk_capacity_failure_count <= value.failed_operation_count
    && isBoundedPath(value.trash_location)
    && (value.started_at === null || isUtcTimestamp(value.started_at))
    && isUtcTimestamp(value.ended_at);
  return (terminalAbsent || terminalPresent)
    && (value.session_id !== null || terminalAbsent)
    && (value.gap === null || (
      isExactObject(value.gap, [
        "minimum_first_missed_seq", "maximum_first_missed_seq",
      ])
      && isNonnegativeInteger(value.gap.minimum_first_missed_seq)
      && value.gap.minimum_first_missed_seq > 0
      && isNonnegativeInteger(value.gap.maximum_first_missed_seq)
      && value.gap.maximum_first_missed_seq >= value.gap.minimum_first_missed_seq
    ));
}

function validateItemRecording(result, recording, reason, detail) {
  if (!RECORDING_STATES.includes(recording)) return false;
  if (recording === "ok") {
    return reason === null && (detail === undefined || detail === null);
  }
  if (!ITEM_RECORDING_REASONS.includes(reason)
      || !(detail === undefined || detail === null || isBoundedV5Text(detail, false))) {
    return false;
  }
  return reason === "record-write-failed"
    ? ["succeeded", "skipped"].includes(result)
    : result === "failed";
}

function validateOperationCompact(value) {
  return isExactObject(value, [
    "result", "reason", "recording", "recording_reason", "detail_omitted_count",
  ]) && ITEM_RESULTS.includes(value.result)
    && (value.reason === null || OPERATION_REASONS.includes(value.reason))
    && validateItemRecording(
      value.result, value.recording, value.recording_reason, undefined,
    )
    && isNonnegativeInteger(value.detail_omitted_count);
}

function validateIntegrityCompact(value) {
  return isExactObject(value, [
    "result", "reason", "recording", "record_disposition", "detail_omitted_count",
  ]) && INTEGRITY_RESULTS.includes(value.result)
    && (value.reason === null || INTEGRITY_REASONS.includes(value.reason))
    && RECORDING_STATES.includes(value.recording)
    && (value.record_disposition === null
      || RECORD_DISPOSITIONS.includes(value.record_disposition))
    && isNonnegativeInteger(value.detail_omitted_count);
}

function validateExecutionEvidence(value) {
  if (!isExactObject(value, ["state", "content"])
      || !EXECUTION_EVIDENCE_STATES.includes(value.state)) return false;
  const exposesContent = ["recorded-copy", "already-verified"].includes(value.state);
  if ((value.content !== null) !== exposesContent) return false;
  if (value.content === null) return true;
  return isExactObject(value.content, [
    "algorithm", "digest", "size", "provenance", "observed_at",
  ]) && value.content.algorithm === "xxh3_128"
    && typeof value.content.digest === "string"
    && /^[0-9a-f]{32}$/.test(value.content.digest)
    && isScalar64(value.content.size)
    && ["copy", "readback", "verify"].includes(value.content.provenance)
    && isUtcTimestamp(value.content.observed_at)
    && (value.state !== "recorded-copy" || value.content.provenance === "copy")
    && (value.state !== "already-verified"
      || ["readback", "verify"].includes(value.content.provenance));
}

function validateExecutionRow(value) {
  return isExactObject(value, [
    "operation", "automatic_verification", "evidence",
  ]) && (value.operation === null || validateOperationCompact(value.operation))
    && (value.automatic_verification === null
      || validateIntegrityCompact(value.automatic_verification))
    && (value.evidence === null || validateExecutionEvidence(value.evidence));
}

function validatePlanWindowRow(value) {
  return isExactObject(value, [
    "node_id", "display", "depth", "is_container", "visible_index",
    "parent_visible_index", "first_child_visible_index", "position_in_set",
    "set_size", "expanded", "row_kind", "operation_id", "operation_kind",
    "reason", "blocked_reason", "selection", "highlighted", "selectable_operation_count",
    "selected_operation_count", "operation_count", "size", "mtime_ns",
    "dependency_count", "risk", "move_peer_id", "notice",
    "selection_exclusion_reason", "execution",
  ]) && isNodeId(value.node_id) && isValidUnicode(value.display)
    && isNonnegativeInteger(value.depth) && typeof value.is_container === "boolean"
    && isNonnegativeInteger(value.visible_index)
    && (value.parent_visible_index === null || isNonnegativeInteger(value.parent_visible_index))
    && (value.first_child_visible_index === null || isNonnegativeInteger(value.first_child_visible_index))
    && isNonnegativeInteger(value.position_in_set) && value.position_in_set >= 1
    && isNonnegativeInteger(value.set_size) && value.position_in_set <= value.set_size
    && (value.expanded === null || typeof value.expanded === "boolean")
    && typeof value.row_kind === "string"
    && (value.operation_id === null || (typeof value.operation_id === "string" && ID_PATTERN.test(value.operation_id)))
    && (value.operation_kind === null || typeof value.operation_kind === "string")
    && (value.reason === null || typeof value.reason === "string")
    && (value.blocked_reason === null || typeof value.blocked_reason === "string")
    && ["selected", "unselected", "mixed", "disabled"].includes(value.selection)
    && typeof value.highlighted === "boolean"
    && [value.selectable_operation_count, value.selected_operation_count,
      value.operation_count, value.dependency_count].every(isNonnegativeInteger)
    && value.selected_operation_count <= value.selectable_operation_count
    && value.selectable_operation_count <= value.operation_count
    && (value.size === null || isScalar64(value.size))
    && (value.mtime_ns === null || isScalar64(value.mtime_ns))
    && ["none", "reversible", "irreversible"].includes(value.risk)
    && (value.move_peer_id === null || isNodeId(value.move_peer_id))
    && (value.notice === null || isValidUnicode(value.notice))
    && (value.selection_exclusion_reason === null
      || isValidUnicode(value.selection_exclusion_reason))
    && (value.execution === null || validateExecutionRow(value.execution))
    && ((value.operation_id === null) === (value.execution === null));
}

function validatePlanWindow(value) {
  return isExactObject(value, [
    "disposition", "view_revision", "highlight_revision", "offset", "total",
    "execution", "rows",
  ]) && ["current", "conflict"].includes(value.disposition)
    && [value.view_revision, value.highlight_revision, value.offset, value.total].every(isNonnegativeInteger)
    && validateExecutionSummary(value.execution)
    && Array.isArray(value.rows) && value.rows.length <= 256
    && value.rows.every(validatePlanWindowRow);
}

function validateOperationDetail(value) {
  if (!isPlainJsonObject(value)) return false;
  const textKeys = new Set([
    "backup", "backup_metadata", "backup_state", "backup_state_error",
    "blocked_reason", "cleanup_error", "destination_state", "durable_state",
    "error_type", "message", "mutation_durable_state", "mutation_state",
    "mutation_state_error", "old_state_error", "publish_state", "retry_error",
    "retry_error_type", "source_state", "state_error", "state_error_type",
    "target_state", "target_state_error", "temp_state", "trash_state_error",
  ]);
  const pathKeys = new Set([
    "backup_path", "mutation_destination", "prior_path", "published_path", "trash_path",
  ]);
  let leaves = 0;
  let pathLeaves = 0;
  for (const [key, item] of Object.entries(value)) {
    if (!/^[\x00-\x7f]{1,64}$/.test(key)) return false;
    if (textKeys.has(key)) {
      if (!isBoundedV5Text(item, false)) return false;
      leaves += 1;
    } else if (pathKeys.has(key)) {
      if (!isBoundedPath(item)) return false;
      leaves += 1;
      pathLeaves += 1;
    } else if (key === "continued") {
      if (typeof item !== "boolean") return false;
      leaves += 1;
    } else if ([
      "durability_warnings", "incomplete_sides", "excluded_dependencies",
    ].includes(key)) {
      if (!Array.isArray(item) || item.length > 32) return false;
      if (key === "incomplete_sides"
          && !item.every((member) => ["source", "target"].includes(member))) return false;
      if (key === "excluded_dependencies"
          && !item.every((member) => typeof member === "string" && ID_PATTERN.test(member))) return false;
      if (key === "durability_warnings"
          && !item.every((member) => isBoundedV5Text(member, false))) return false;
      leaves += item.length;
    } else {
      return false;
    }
    if (leaves > 32 || pathLeaves > 8) return false;
  }
  return true;
}

function validateOperationItemView(value) {
  return isExactObject(value, [
    "item_type", "phase", "item_id", "kind", "path", "result", "reason",
    "detail", "recording", "recording_reason", "recording_detail",
    "detail_omitted_count",
  ]) && value.item_type === "operation" && value.phase === "execute"
    && typeof value.item_id === "string" && ID_PATTERN.test(value.item_id)
    && OPERATION_KINDS.includes(value.kind) && isBoundedPath(value.path)
    && ITEM_RESULTS.includes(value.result)
    && (value.reason === null || OPERATION_REASONS.includes(value.reason))
    && validateOperationDetail(value.detail)
    && validateItemRecording(
      value.result, value.recording, value.recording_reason, value.recording_detail,
    )
    && isNonnegativeInteger(value.detail_omitted_count);
}

function validateIntegrityOutcomeView(value) {
  return isExactObject(value, [
    "item_type", "phase", "item_id", "row_id", "location_id", "kind", "path",
    "result", "reason", "detail", "read_strategy", "recording",
    "record_disposition", "detail_omitted_count",
  ]) && value.item_type === "integrity" && value.phase === "verify"
    && typeof value.item_id === "string" && ID_PATTERN.test(value.item_id)
    && ((value.row_id === null && value.location_id === null)
      || (isBoundedV5Text(value.row_id, true) && isBoundedV5Text(value.location_id, true)))
    && value.kind === "integrity" && isBoundedPath(value.path)
    && INTEGRITY_RESULTS.includes(value.result)
    && (value.reason === null || INTEGRITY_REASONS.includes(value.reason))
    && (value.detail === null || isBoundedV5Text(value.detail, false))
    && (value.read_strategy === null || value.read_strategy === "windows-unbuffered")
    && RECORDING_STATES.includes(value.recording)
    && (value.record_disposition === null
      || RECORD_DISPOSITIONS.includes(value.record_disposition))
    && isNonnegativeInteger(value.detail_omitted_count);
}

function validateExecutionDetail(value) {
  if (!isExactObject(value, [
    "disposition", "execution_revision", "operation_id", "operation",
    "automatic_verification", "evidence",
  ]) || !["current", "conflict", "not-retained"].includes(value.disposition)
      || !isNonnegativeInteger(value.execution_revision)
      || typeof value.operation_id !== "string" || !ID_PATTERN.test(value.operation_id)
      || !(value.operation === null || validateOperationItemView(value.operation))
      || !(value.automatic_verification === null
        || validateIntegrityOutcomeView(value.automatic_verification))
      || !(value.evidence === null || validateExecutionEvidence(value.evidence))) {
    return false;
  }
  if (value.operation !== null && value.operation.item_id !== value.operation_id) return false;
  if (value.automatic_verification !== null
      && value.automatic_verification.item_id !== value.operation_id) return false;
  return value.disposition === "current"
    || (value.operation === null
      && value.automatic_verification === null
      && value.evidence === null);
}

function validatePlanAnchor(value) {
  return isExactObject(value, ["disposition", "view_revision", "node_id", "index"])
    && ["current", "conflict"].includes(value.disposition)
    && isNonnegativeInteger(value.view_revision)
    && (value.node_id === null || isNodeId(value.node_id))
    && (value.index === null || isNonnegativeInteger(value.index))
    && ((value.node_id === null) === (value.index === null));
}

function validateExecutionAdmission(value) {
  if (validateStartPlanResult(value)) return true;
  return isExactObject(value, ["disposition", "revision", "state", "session"])
    && ["in-flight", "frozen", "conflict", "confirmation-required"].includes(value.disposition)
    && isNonnegativeInteger(value.revision)
    && ["reviewing", "committing", "committed"].includes(value.state)
    && (value.session === null || (isExactObject(value.session, ["request_id", "session_id"])
      && typeof value.session.request_id === "string" && ID_PATTERN.test(value.session.request_id)
      && typeof value.session.session_id === "string" && ID_PATTERN.test(value.session.session_id)));
}

function validateControlReceipt(value, sessionId) {
  return isExactObject(value, [
    "code", "session_id", "before", "after", "detail", "accepted",
  ]) && typeof value.code === "string" && value.session_id === sessionId
    && (value.before === null || typeof value.before === "string")
    && (value.after === null || typeof value.after === "string")
    && isValidUnicode(value.detail) && typeof value.accepted === "boolean";
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
