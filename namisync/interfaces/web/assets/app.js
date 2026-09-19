import {
  acknowledgeShellReady,
  admitLocation,
  BridgeTransportError,
  closeTask,
  controlExecution,
  createTask,
  echoReadiness,
  getPlanAnchor,
  getPlanWindow,
  listTasks,
  markBridgeOperational,
  mutatePlanSelection,
  mutatePlanScope,
  mutatePlanHighlight,
  mutatePlanHighlightedSelection,
  openPlanView,
  pickFolder,
  planAgain,
  prepareSetup,
  probeRecentPairs,
  readSetup,
  StartPlanUncertainError,
  startInventory,
  startExecution,
  startPlan,
  startTaskDrain,
  TaskCreateUncertainError,
  whenBridgeApiReady,
  updatePlanView,
} from "./bridge.js";
import { installReadinessReceiver } from "./readiness.js";
import { installAppearanceReceiver } from "./appearance.js";
import { installThemeCombobox, installThemeSelector } from "./theme.js";
import { createExecutionConfirmation } from "./execution_confirmation.js";
import { createWorkPanel } from "./panels.js";
import { createTaskRail } from "./rail.js";
import { renderText } from "./render.js";

const app = document.querySelector("#app");
const status = document.querySelector("#host-status");
const themeSelector = document.querySelector("#theme-mode");
const settingsView = document.querySelector("#settings-view");
const themeOptions = document.querySelector("#theme-options");
if (
  !(app instanceof HTMLElement)
  || !(status instanceof HTMLElement)
  || !(themeSelector instanceof HTMLElement)
  || !(settingsView instanceof HTMLElement)
  || !(themeOptions instanceof HTMLElement)
) {
  throw new TypeError("NamiSync shell elements are unavailable");
}

document.addEventListener?.("pointerdown", (event) => {
  if (
    event.target?.matches?.(".nami-input, .nami-select")
    && !event.target.disabled
  ) {
    event.target.dataset.namiFocusOrigin = "pointer";
  }
}, true);
document.addEventListener?.("focusout", (event) => {
  if (event.target?.matches?.(".nami-input, .nami-select")) {
    delete event.target.dataset.namiFocusOrigin;
  }
}, true);

function renderHostStatus(message) {
  renderText(status, message);
  status.hidden = message === "Ready";
}

const readiness = installReadinessReceiver(window.chrome.webview);
const themeCombobox = installThemeCombobox(themeSelector);
const theme = installThemeSelector(themeCombobox);
let appliedPresentationRevision = null;
installAppearanceReceiver(
  window.chrome.webview,
  document.documentElement,
  (revision) => {
    appliedPresentationRevision = revision;
    void theme.refresh(revision);
  },
);

const tasks = new Map();
let selectedTaskId = null;
let settingsVisible = false;
let navigationRevision = 0;
let taskMutationRevision = 0;
let createAttempt = null;
let nextTaskNumber = 1;
let defaultSetup = null;
let defaultSetupRevision = 0;
let recentPairAvailability = Object.create(null);
let recentPairProbeRevision = 0;
let recentPairProbeRunning = false;
let recentPairProbePending = false;
let pageBatch = null;

const ACTIVE_EXECUTION_CONTROL_STATES = new Set([
  "pending",
  "running",
  "pausing",
  "paused",
  "canceling",
]);

function executionControlMessage(state) {
  switch (state) {
    case "pending": return "Execution waiting.";
    case "running": return "Execution running.";
    case "pausing": return "Pausing execution…";
    case "paused": return "Execution paused. Resume available.";
    case "canceling": return "Canceling execution…";
    default: return "Follow live execution status.";
  }
}

const panel = createWorkPanel({
  onEdit: editLocation,
  onValidate: validateLocation,
  onPick: pickLocation,
  onRecent: chooseRecentLocation,
  onRecentPair: chooseRecentPair,
  onRefreshRecents: refreshRecentPairs,
  onMode: editMode,
  onOption: editOption,
  onAddFilter: addFilter,
  onRemoveFilter: removeFilter,
  onMount: chooseMount,
  onPlanAgainMount: choosePlanAgainMount,
  onStartPlan: () => { void startCurrentPlan(); },
  onStartInventory: () => { void startCurrentInventory(); },
  onAddPair: addCurrentPair,
  onRemoveBatchRow: removeBatchRow,
  onClearBatchResults: clearBatchResults,
  onStartBatch: () => { void startPairBatch(); },
  onPlanAgain: () => { void startPlanAgain(); },
}, {
  onViewChange: (review, patch) => { void changePlanView(review, patch); },
  onWindow: (review, offset) => { void loadPlanWindow(review, offset); },
  onSelect: (review, row, selected) => {
    void changePlanSelection(review, row, selected);
  },
  onScopeSelect: (review, selected) => {
    void changePlanSelection(review, null, selected);
  },
  onHighlight: (review, gesture, nodeId) => {
    queuePlanHighlight(review, gesture, nodeId);
  },
  onHighlightedSelect: (review, selected) => {
    void changePlanSelection(review, null, selected, true);
  },
  onExecute: (review, returnFocus) => {
    void executeReviewedPlan(review, returnFocus);
  },
  onControl: (review, action) => {
    void controlReviewedExecution(review, action);
  },
  onPlanAgain: (review) => { void planAgainFromReview(review); },
}, settingsView);
const rail = createTaskRail({
  onCreate: () => { void createBlankTask(); },
  onSelect: selectTask,
  onClose: (taskId) => { void closeRetainedTask(taskId); },
  onSettings: showSettings,
});
app.append(rail.element, panel.element);
const executionConfirmation = createExecutionConfirmation([app, themeOptions]);
document.body.append(executionConfirmation.element);

function taskArray() {
  return Array.from(tasks.values()).reverse();
}

function renderTasks() {
  for (const task of tasks.values()) {
    if (task.form !== null) {
      task.form.recentPairAvailability = recentPairAvailability;
      task.form.batchRunning = pageBatch !== null && pageBatch.running !== null;
      const syncBatchOwner = task.form.editable && task.form.mode === "sync-plan";
      const batchBlockReason = batchTaskBlockReason(task.taskId);
      task.form.batch = syncBatchOwner && pageBatch !== null
        ? pageBatch.rows.filter((row) => row.originTaskId === task.taskId)
        : [];
      task.form.batchCount = syncBatchOwner ? pageBatch?.rows.length ?? 0 : 0;
      task.form.batchPending = syncBatchOwner && (pageBatch?.rows.some((row) => row.originTaskId === task.taskId
        && ["queued", "submitting", "uncertain"].includes(row.state)) ?? false);
      task.form.batchPending ||= batchBlockReason !== null;
      task.form.batchMessage = syncBatchOwner ? batchTaskStartMessage(task.taskId)
        : batchBlockReason === null ? null
          : batchTaskStartMessage(task.taskId)
            ?? "Return to Sync to resolve its in-flight batch request before starting Inventory.";
      task.form.closePending = task.closePending;
    }
    task.batchCloseReason = task.executionAttempt === null
      ? batchTaskBlockReason(task.taskId)
      : "Resolve the in-flight execution request before closing.";
    task.canPlanAgain = canStartPlanAgain(task);
  }
  rail.render(
    taskArray(),
    selectedTaskId,
    createAttempt?.running === true,
    settingsVisible,
  );
  if (settingsVisible) panel.renderSettings();
  else panel.render(selectedTaskId === null ? null : tasks.get(selectedTaskId) ?? null);
}

function showSettings() {
  if (settingsVisible) return;
  navigationRevision += 1;
  settingsVisible = true;
  renderTasks();
}

function selectTask(taskId) {
  const task = tasks.get(taskId);
  if (task === undefined) {
    return;
  }
  navigationRevision += 1;
  selectedTaskId = taskId;
  settingsVisible = false;
  renderTasks();
  void loadTaskSetup(task);
  if (
    task.taskKind === "sync-plan"
    && (task.sessionReleased || task.sessionState === "active")
  ) {
    void loadPlanReview(task);
  }
}

function adoptTask(summary) {
  let task = tasks.get(summary.task_id);
  if (task === undefined) {
    task = {
      taskId: summary.task_id,
      sessionId: summary.session_id,
      sessionState: summary.session_state,
      sessionReleased: summary.session_released,
      taskKind: summary.task_kind,
      requestId: summary.request_id,
      closePending: false,
      error: null,
      label: `Task ${nextTaskNumber}`,
      stopDrain: null,
      form: null,
      setupRevision: 0,
      review: null,
      reviewLoading: false,
      reviewRevision: 0,
      reviewSessionId: null,
      executionStarted: false,
      executionAttempt: null,
      executionControlState: "running",
      executionControlRevision: 0,
      progressState: null,
    };
    nextTaskNumber += 1;
    tasks.set(task.taskId, task);
  } else {
    if (
      task.sessionId !== null
      && summary.session_id !== null
      && task.sessionId !== summary.session_id
      && task.review !== null
    ) {
      task.executionStarted = true;
    }
    task.sessionId = summary.session_id;
    task.sessionState = summary.session_state;
    task.sessionReleased = summary.session_released;
    task.taskKind = summary.task_kind;
    task.requestId = summary.request_id;
  }
  if (task.form !== null) task.form.sessionState = task.sessionState;
  if (
    task.sessionId !== null &&
    task.stopDrain === null
  ) {
    attachTaskDrain(task);
  }
  if (
    task.taskKind === "sync-plan"
    && (task.sessionReleased || task.sessionState === "active")
  ) {
    void loadPlanReview(task);
  }
  return task;
}

function attachTaskDrain(task) {
  const sessionId = task.sessionId;
  task.stopDrain = startTaskDrain(
    task.taskId,
    sessionId,
    (update, progressState) => acceptTaskUpdate(task, sessionId, update, progressState),
    () => acceptTaskRefusal(task, sessionId),
    {
      terminal: task.sessionState !== "active",
      sessionReleased: task.sessionReleased,
    },
    (_taskId, sessionId) => acceptTaskRelease(task, sessionId),
  );
}

function acceptTaskUpdate(task, sessionId, update, progressState = null) {
  if (tasks.get(task.taskId) !== task || task.sessionId !== sessionId) {
    return;
  }
  if (progressState !== null) task.progressState = progressState;
  if (
    update.update_type === "event"
    && update.event?.body_type === "StateChanged"
    && ACTIVE_EXECUTION_CONTROL_STATES.has(update.event.body?.state)
    && task.sessionState === "active"
  ) {
    task.executionControlRevision += 1;
    task.executionControlState = update.event.body.state;
    if (task.executionStarted && task.review !== null) {
      task.review.message = executionControlMessage(task.executionControlState);
    }
    renderTasks();
    return;
  }
  if (update.update_type === "record") {
    taskMutationRevision += 1;
    task.executionControlRevision += 1;
    task.sessionState = update.record.state;
    if (task.form !== null) task.form.sessionState = task.sessionState;
    if (task.executionStarted && task.review !== null) {
      task.review.message = task.sessionState === "completed" ? null : `Execution ${task.sessionState}.`;
    }
    if (task.closePending) {
      task.closePending = false;
      void closeRetainedTask(task.taskId);
    }
    renderTasks();
    if (["completed", "failed", "canceled", "refused"].includes(task.sessionState)) {
      void loadTaskSetup(task);
    }
  } else {
    renderTasks();
  }
}

function acceptTaskRefusal(task, sessionId) {
  if (tasks.get(task.taskId) !== task || task.sessionId !== sessionId) {
    return;
  }
  task.error = "Task updates stopped. Close can be retried.";
  task.closePending = false;
  renderTasks();
}

async function refreshTasks(epoch) {
  const mutationBaseline = taskMutationRevision;
  const result = await listTasks();
  if (epoch !== startupEpoch) {
    return;
  }
  if (mutationBaseline !== taskMutationRevision) {
    void refreshTasks(epoch);
    return;
  }
  const retainedIds = new Set();
  for (const summary of result.tasks) {
    retainedIds.add(summary.task_id);
    adoptTask(summary);
  }
  for (const [taskId, task] of tasks) {
    if (!retainedIds.has(taskId)) {
      task.stopDrain?.();
      tasks.delete(taskId);
    }
  }
  if (selectedTaskId !== null && !tasks.has(selectedTaskId)) {
    selectedTaskId = null;
  }
  if (selectedTaskId === null && tasks.size > 0) {
    selectedTaskId = taskArray()[0].taskId;
  }
  renderTasks();
  if (selectedTaskId !== null) void loadTaskSetup(tasks.get(selectedTaskId));
}

async function createBlankTask() {
  if (createAttempt?.running) {
    return;
  }
  if (createAttempt !== null && typeof createAttempt.retry !== "function") return;
  const epoch = startupEpoch;
  const selectionBaseline = navigationRevision;
  const retry = createAttempt?.retry ?? null;
  const attempt = createAttempt ?? {
    epoch,
    running: true,
    dispatched: true,
    retry: null,
  };
  createAttempt = attempt;
  attempt.running = true;
  attempt.retry = null;
  if (retry !== null) renderHostStatus("Retrying task creation…");
  renderTasks();
  try {
    const result = await (retry === null ? createTask() : retry());
    taskMutationRevision += 1;
    if (epoch !== startupEpoch) {
      if (createAttempt === attempt) createAttempt = null;
      void refreshTasks(startupEpoch);
      return;
    }
    const task = adoptTask({
      task_id: result.task_id,
      session_id: null,
      session_state: null,
      session_released: false,
      task_kind: null,
      request_id: null,
    });
    if (navigationRevision === selectionBaseline) {
      selectedTaskId = task.taskId;
      settingsVisible = false;
    }
    void loadTaskSetup(task);
    if (createAttempt === attempt) createAttempt = null;
  } catch (error) {
    if (createAttempt !== attempt) return;
    if (error instanceof TaskCreateUncertainError) {
      attempt.running = false;
      attempt.retry = error.retry;
      renderHostStatus(
        "Task creation could not be confirmed. Select New task to retry the same request.",
      );
      return;
    }
    createAttempt = null;
    if (epoch === startupEpoch) {
      renderHostStatus(
        "A task could not be created. Close an unused task or wait, then try again.",
      );
    }
  } finally {
    if (createAttempt === attempt && attempt.retry === null) createAttempt = null;
    renderTasks();
  }
}

async function closeRetainedTask(taskId) {
  const task = tasks.get(taskId);
  if (task === undefined || task.closePending || task.executionAttempt !== null) {
    return;
  }
  if (batchTaskBlockReason(taskId) !== null) return;
  const epoch = startupEpoch;
  task.closePending = true;
  task.error = null;
  renderTasks();
  let remainsPending = false;
  try {
    const result = await closeTask(task.taskId, task.sessionId);
    if (result.disposition === "closed") {
      taskMutationRevision += 1;
    }
    if (epoch !== startupEpoch) {
      void refreshTasks(startupEpoch);
      return;
    }
    if (tasks.get(taskId) !== task) {
      return;
    }
    if (result.disposition === "closed") {
      if (pageBatch !== null) {
        pageBatch.rows = pageBatch.rows.filter((row) => row.originTaskId !== taskId);
      }
      task.stopDrain?.();
      tasks.delete(taskId);
      if (selectedTaskId === taskId) {
        selectedTaskId = tasks.size === 0 ? null : taskArray()[0].taskId;
        navigationRevision += 1;
      }
    } else {
      remainsPending = true;
    }
  } catch (_error) {
    if (epoch === startupEpoch && tasks.get(taskId) === task) {
      task.error = "Close did not finish. Retry.";
    }
  } finally {
    if (
      !remainsPending &&
      epoch === startupEpoch &&
      tasks.get(taskId) === task
    ) {
      task.closePending = false;
    }
    renderTasks();
  }
}

function cloneOptions(options) {
  return {
    filters: [...options.filters],
    deletion_policy: options.deletion_policy,
    trash_on_update: options.trash_on_update,
    preservation: { ...options.preservation },
    propagate_source_casing: options.propagate_source_casing,
    verify_after_execute: options.verify_after_execute,
  };
}

function cloneCandidate(candidate) {
  return candidate === null ? null : { ...candidate };
}

function cloneLocation(location) {
  return location === null ? null : {
    ...location,
    candidates: [...location.candidates],
  };
}

function snapshotLocationRow(row) {
  return {
    text: row.text,
    location: cloneLocation(row.location),
    candidate: cloneCandidate(row.candidate),
    continuationId: row.continuationId,
    mountIndex: row.mountIndex,
    revision: row.revision,
    admissionRevision: row.admissionRevision,
  };
}

function createForm(snapshot, recents) {
  const root = (value) => ({
    text: value?.display ?? "",
    location: value === null ? null : {
      purpose: null,
      state: "resolved",
      choice_id: null,
      continuation_id: null,
      detail: null,
    },
    candidate: value?.location_id === null || value === null ? null : {
      kind: "remembered_location", location_id: value.location_id, selected_mount: null,
    },
    continuationId: null,
    mountIndex: null,
    revision: 0,
    admissionRevision: 0,
  });
  const inventory = snapshot.task_kind === "inventory";
  return {
    setup: { ...snapshot, recents },
    options: snapshot.options === null ? null : cloneOptions(snapshot.options),
    source: root(inventory ? snapshot.root : snapshot.source),
    target: root(snapshot.target),
    batch: [],
    batchCount: 0,
    batchPending: false,
    batchMessage: null,
    closePending: false,
    batchRunning: false,
    editable: snapshot.setup_state === "default" && snapshot.task_kind === null,
    mode: inventory ? "inventory" : "sync-plan",
    revision: 0,
    attempt: null,
    actionMessage: null,
    artifactReady: snapshot.setup_state === "frozen" && snapshot.task_kind === "sync-plan"
      && snapshot.plan_again !== null,
    canPlanAgain: snapshot.plan_again !== null,
    planAgainMounts: { source: null, target: null },
    sessionState: null,
  };
}

async function loadTaskSetup(task) {
  if (task === undefined || tasks.get(task.taskId) !== task) return;
  const revision = ++task.setupRevision;
  try {
    const result = await readSetup(task.taskId);
    if (tasks.get(task.taskId) !== task || task.setupRevision !== revision) return;
    const retained = task.form;
    if (
      retained !== null && retained.editable &&
      result.snapshot.setup_state === "default" && result.snapshot.task_kind === null
    ) {
      retained.setup = { ...result.snapshot, recents: retained.setup.recents };
      retained.canPlanAgain = result.snapshot.plan_again !== null;
      task.form = retained;
    } else {
      task.form = createForm(
        result.snapshot,
        defaultSetup?.recents ?? { sources: [], targets: [], pairs: [] },
      );
    }
    task.form.sessionState = task.sessionState;
    renderTasks();
  } catch (_error) {
    if (tasks.get(task.taskId) === task && task.setupRevision === revision) {
      task.error = "Task setup could not be read. Select the task to retry.";
      renderTasks();
    }
  }
}

async function loadDefaultSetup() {
  const revision = ++defaultSetupRevision;
  const epoch = startupEpoch;
  try {
    const result = await readSetup();
    if (revision !== defaultSetupRevision || epoch !== startupEpoch) return;
    defaultSetup = result;
    for (const task of tasks.values()) {
      if (task.form === null && task.taskKind === null) {
        void loadTaskSetup(task);
      } else if (task.form?.editable) {
        task.form.setup = { ...task.form.setup, recents: defaultSetup.recents };
      }
    }
    refreshRecentPairs();
  } catch (_error) {
    // Task-specific reads retain the existing action-guiding error path.
  }
}

function refreshRecentPairs() {
  recentPairProbeRevision += 1;
  recentPairAvailability = Object.create(null);
  for (const pair of defaultSetup?.recents.pairs ?? []) {
    recentPairAvailability[pair.mapping_id] = { source: "checking", target: "checking" };
  }
  renderTasks();
  recentPairProbePending = true;
  void runRecentPairProbe();
}

async function runRecentPairProbe() {
  if (recentPairProbeRunning || !recentPairProbePending) return;
  recentPairProbePending = false;
  const recents = defaultSetup?.recents;
  if (recents === undefined || recents.pairs.length === 0) return;
  recentPairProbeRunning = true;
  const revision = recentPairProbeRevision;
  const epoch = startupEpoch;
  const current = () => revision === recentPairProbeRevision
    && epoch === startupEpoch && defaultSetup?.recents === recents;
  try {
    const result = await probeRecentPairs();
    if (!current()) return;
    for (const pair of recents.pairs) {
      const observed = result.pairs.find((item) => item.mapping_id === pair.mapping_id
        && item.source_id === pair.source.location_id && item.target_id === pair.target.location_id);
      const endpointState = (state) => state === "resolved" ? "online"
        : state === "offline" || state === "missing" ? "offline"
          : state === undefined ? "unknown" : "unavailable";
      recentPairAvailability[pair.mapping_id] = {
        source: endpointState(observed?.source_state),
        target: endpointState(observed?.target_state),
      };
    }
  } catch (_error) {
    if (current()) {
      for (const pair of recents.pairs) {
        recentPairAvailability[pair.mapping_id] = { source: "unknown", target: "unknown" };
      }
    }
  } finally {
    recentPairProbeRunning = false;
    if (current()) renderTasks();
    if (recentPairProbePending) void runRecentPairProbe();
  }
}

function currentTask() {
  return selectedTaskId === null ? null : tasks.get(selectedTaskId) ?? null;
}

function currentForm() {
  return currentTask()?.form ?? null;
}

function formIsEditable(form) {
  return form !== null && form.editable && form.attempt === null;
}

function originHasPendingBatch(taskId) {
  return pageBatch?.rows.some((row) => row.originTaskId === taskId
    && ["queued", "submitting", "uncertain"].includes(row.state)) ?? false;
}

function batchTaskBlockReason(taskId) {
  if (pageBatch?.running?.originTaskId === taskId) {
    return "Wait for this task's active batch submission before closing.";
  }
  const retained = pageBatch?.rows.find((row) => ["submitting", "uncertain"].includes(row.state)
    && (row.originTaskId === taskId || row.taskId === taskId));
  return retained === undefined
    ? null
    : "Resolve this task's submitting or uncertain batch pair before closing.";
}

function batchTaskStartMessage(taskId) {
  const row = pageBatch?.rows.find((value) => ["submitting", "uncertain"].includes(value.state)
    && value.taskId === taskId && value.originTaskId !== taskId);
  if (row !== undefined) {
    const origin = tasks.get(row.originTaskId);
    return `Resolve the batch request in ${origin?.label ?? "its originating task"} before starting this task separately.`;
  }
  return null;
}

function locationPurpose(form, rowName) {
  return rowName === "source" && form.mode === "inventory" ? "inventory" : rowName;
}

function clearLocationChoice(row) {
  row.location = null;
  row.continuationId = null;
  row.mountIndex = null;
  row.admissionRevision += 1;
}

function editMode(mode) {
  const form = currentForm();
  if (!formIsEditable(form) || !["sync-plan", "inventory"].includes(mode) || form.mode === mode) return;
  form.mode = mode;
  form.revision += 1;
  form.source.revision += 1;
  clearLocationChoice(form.source);
  form.actionMessage = null;
  renderTasks();
}

function acceptTaskRelease(task, sessionId) {
  if (tasks.get(task.taskId) !== task || task.sessionId !== sessionId) return;
  task.sessionReleased = true;
  renderTasks();
  if (task.taskKind === "sync-plan") void loadPlanReview(task);
}

function currentReviewTask(review) {
  const task = currentTask();
  return task !== null && task.review === review ? task : null;
}

function retainedReviewTask(review) {
  const taskId = review?.summary?.task_id;
  const task = typeof taskId === "string" ? tasks.get(taskId) ?? null : null;
  return task !== null && task.review === review ? task : null;
}

async function loadPlanReview(task, force = false) {
  if (
    task === undefined || tasks.get(task.taskId) !== task
    || task.taskKind !== "sync-plan" || task.sessionId === null
    || task.reviewLoading
    || (!force && task.review !== null && task.reviewSessionId === task.sessionId)
  ) return;
  const request = ++task.reviewRevision;
  const sessionId = task.sessionId;
  task.reviewLoading = true;
  renderTasks();
  try {
    const summary = await openPlanView(task.taskId);
    const window = await getPlanWindow(task.taskId, summary.view_revision, 0, 256);
    if (
      tasks.get(task.taskId) !== task || task.reviewRevision !== request
      || task.sessionId !== sessionId || window.disposition !== "current"
      || window.view_revision !== summary.view_revision
      || window.highlight_revision !== summary.highlight_revision
    ) return;
    task.executionStarted ||= summary.selection_state === "committed";
    const message = task.executionStarted
      ? task.sessionState === "active"
        ? executionControlMessage(task.executionControlState)
        : task.sessionState === "completed" ? null : `Execution ${task.sessionState}.`
      : summary.preflight_ready
        ? null
        : "Plan failed review. Inspect notices and create a fresh plan.";
    task.review = {
      summary,
      window,
      pending: null,
      queuedSearchQuery: null,
      highlightQueue: Promise.resolve(),
      message,
      actionRevision: 0,
      windowRequestRevision: 0,
      windowRequestOffset: null,
      windowRequestRunning: false,
    };
    task.reviewSessionId = sessionId;
    task.error = null;
  } catch (_error) {
    if (
      tasks.get(task.taskId) === task && task.reviewRevision === request
      && task.sessionId === sessionId
      && task.sessionState !== "active"
    ) {
      task.error = "Plan unavailable. Select the task to retry.";
    }
  } finally {
    if (tasks.get(task.taskId) === task && task.reviewRevision === request) {
      task.reviewLoading = false;
      renderTasks();
    }
  }
}

async function readPlanWindowAtAnchor(task, review, summary, anchorNodeId, fallbackOffset) {
  let offset = fallbackOffset;
  if (anchorNodeId !== null) {
    try {
      const anchor = await getPlanAnchor(
        task.taskId,
        summary.view_revision,
        anchorNodeId,
      );
      if (anchor.disposition === "current" && anchor.index !== null) {
        offset = anchor.index;
      }
    } catch (_error) {
      offset = 0;
    }
  }
  return getPlanWindow(task.taskId, summary.view_revision, offset, 256);
}

async function changePlanView(review, patch, queued = false) {
  const task = queued ? retainedReviewTask(review) : currentReviewTask(review);
  if (task === null) return;
  if (review.pending !== null) {
    if (review.pending === "view" && Object.keys(patch).length === 1
        && typeof patch.searchQuery === "string") {
      review.queuedSearchQuery = patch.searchQuery;
    }
    return;
  }
  const action = ++review.actionRevision;
  const anchorNodeId = review.window.rows[0]?.node_id ?? null;
  const sortColumn = patch.sortColumn ?? review.summary.sort_column;
  const gesture = {
    searchQuery: patch.searchQuery ?? review.summary.search_query,
    filters: [...(patch.filters ?? review.summary.filters)],
    sortColumn,
    sortDirection: sortColumn === "path"
      ? "ascending"
      : patch.sortDirection ?? review.summary.sort_direction,
    collapseNodeId: patch.collapseNodeId ?? null,
    collapsed: patch.collapseNodeId === undefined ? null : patch.collapsed,
  };
  review.pending = "view";
  review.message = "Updating view…";
  renderTasks();
  try {
    const summary = await updatePlanView(
      task.taskId,
      review.summary.view_revision,
      gesture,
    );
    if (retainedReviewTask(review) !== task || review.actionRevision !== action) return;
    const window = await readPlanWindowAtAnchor(
      task,
      review,
      summary,
      anchorNodeId,
      0,
    );
    if (
      retainedReviewTask(review) !== task || review.actionRevision !== action
      || window.disposition !== "current"
      || window.view_revision !== summary.view_revision
      || window.highlight_revision !== summary.highlight_revision
    ) return;
    review.summary = summary;
    review.window = window;
    review.message = summary.disposition === "conflict"
      ? "View changed. Current view restored."
      : null;
  } catch (_error) {
    if (retainedReviewTask(review) === task && review.actionRevision === action) {
      review.message = "View update failed. Try again.";
    }
  } finally {
    if (retainedReviewTask(review) === task && review.actionRevision === action) {
      review.pending = null;
      renderTasks();
      const queuedSearchQuery = review.queuedSearchQuery;
      review.queuedSearchQuery = null;
      if (queuedSearchQuery !== null
          && queuedSearchQuery !== review.summary.search_query) {
        void changePlanView(review, { searchQuery: queuedSearchQuery }, true);
      }
    }
  }
}

async function loadPlanWindow(review, offset) {
  const task = currentReviewTask(review);
  if (task === null) return;
  if (offset !== null && review.pending !== null) return;
  review.windowRequestRevision += 1;
  review.windowRequestOffset = offset;
  if (offset === null || review.windowRequestRunning) return;

  review.windowRequestRunning = true;
  try {
    while (review.windowRequestOffset !== null) {
      const requestedOffset = review.windowRequestOffset;
      const request = review.windowRequestRevision;
      const action = review.actionRevision;
      const viewRevision = review.summary.view_revision;
      try {
        const window = await getPlanWindow(
          task.taskId,
          viewRevision,
          requestedOffset,
          256,
        );
        if (retainedReviewTask(review) !== task) return;
        if (
          review.actionRevision !== action
          || review.summary.view_revision !== viewRevision
        ) {
          review.windowRequestOffset = null;
          return;
        }
        if (
          review.windowRequestRevision !== request
          || review.windowRequestOffset !== requestedOffset
        ) continue;
        review.windowRequestOffset = null;
        if (
          window.disposition !== "current"
          || window.view_revision !== viewRevision
          || window.highlight_revision !== review.summary.highlight_revision
        ) return;
        review.window = window;
        review.message = "";
        renderTasks();
      } catch (_error) {
        if (
          retainedReviewTask(review) === task
          && review.windowRequestRevision === request
          && review.windowRequestOffset === requestedOffset
        ) {
          review.windowRequestOffset = null;
          review.message = "More rows unavailable. Scroll to retry.";
          renderTasks();
        }
      }
    }
  } finally {
    review.windowRequestRunning = false;
  }
}

function queuePlanHighlight(review, gesture, nodeId) {
  const queuedViewRevision = review.summary.view_revision;
  const queuedActionRevision = review.actionRevision;
  review.highlightQueue = review.highlightQueue.catch(() => {}).then(async () => {
    const task = currentReviewTask(review);
    if (task === null || review.pending !== null || task.executionAttempt !== null
        || review.summary.view_revision !== queuedViewRevision
        || review.actionRevision !== queuedActionRevision) return;
    const action = review.actionRevision;
    const viewRevision = review.summary.view_revision;
    const summary = await mutatePlanHighlight(
      task.taskId, viewRevision, review.summary.highlight_revision, gesture, nodeId,
    );
    if (retainedReviewTask(review) !== task || review.actionRevision !== action) return;
    const moving = gesture === "move_up" || gesture === "move_down"
      || gesture === "move_up_extend" || gesture === "move_down_extend";
    const focusIndex = summary.highlight_focus_visible_index;
    const currentEnd = review.window.offset + review.window.rows.length;
    const targetOutsideWindow = moving
      && Number.isSafeInteger(focusIndex)
      && (focusIndex < review.window.offset || focusIndex >= currentEnd);
    const window = await getPlanWindow(
      task.taskId,
      summary.view_revision,
      targetOutsideWindow ? focusIndex : review.window.offset,
      256,
    );
    if (retainedReviewTask(review) !== task || review.actionRevision !== action
        || window.disposition !== "current"
        || window.view_revision !== summary.view_revision
        || window.highlight_revision !== summary.highlight_revision) return;
    review.summary = summary;
    review.window = window;
    renderTasks();
  });
  return review.highlightQueue;
}

async function changePlanSelection(review, row, selected, highlightedScope = false) {
  if (currentReviewTask(review) === null || review.pending !== null) return;
  const clickedViewRevision = review.summary.view_revision;
  await review.highlightQueue.catch(() => {});
  const task = currentReviewTask(review);
  if (
    task === null || review.pending !== null
    || review.summary.view_revision !== clickedViewRevision
    || review.summary.selection_state !== "reviewing"
    || task.executionAttempt !== null
  ) return;
  if (!highlightedScope && row !== null
      && review.summary.highlight_anchor_node_id !== null) {
    await queuePlanHighlight(review, "clear", null).catch(() => {});
    if (currentReviewTask(review) !== task) return;
  }
  const action = ++review.actionRevision;
  const anchorNodeId = review.window.rows[0]?.node_id ?? null;
  review.pending = "selection";
  review.message = "Updating selection…";
  renderTasks();
  try {
    const summary = highlightedScope
      ? await mutatePlanHighlightedSelection(
        task.taskId, review.summary.view_revision,
        review.summary.highlight_revision, review.summary.selection_revision, selected,
      )
      : row === null
      ? await mutatePlanScope(
        task.taskId, review.summary.view_revision,
        review.summary.selection_revision, selected,
      )
      : await mutatePlanSelection(
        task.taskId, review.summary.view_revision,
        review.summary.selection_revision, row.node_id, selected,
      );
    if (retainedReviewTask(review) !== task || review.actionRevision !== action) return;
    const window = await readPlanWindowAtAnchor(
      task,
      review,
      summary,
      anchorNodeId,
      review.window.offset,
    );
    if (
      retainedReviewTask(review) !== task || review.actionRevision !== action
      || window.disposition !== "current"
    ) return;
    review.summary = summary;
    review.window = window;
    review.message = summary.disposition === "applied"
      ? null
      : summary.disposition === "conflict"
        ? "Selection changed elsewhere. Current selection shown."
        : summary.disposition === "frozen" || summary.disposition === "in-flight"
          ? "Selection is already committed to execution."
          : null;
  } catch (_error) {
    if (retainedReviewTask(review) === task && review.actionRevision === action) {
      review.message = "Selection uncertain. Reloading review…";
      review.pending = null;
      void loadPlanReview(task, true);
      return;
    }
  } finally {
    if (
      retainedReviewTask(review) === task && review.actionRevision === action
      && review.pending !== null
    ) {
      review.pending = null;
      renderTasks();
    }
  }
}

async function executeReviewedPlan(review, returnFocus) {
  const task = currentReviewTask(review);
  if (
    task !== null
    && task.executionAttempt?.state === "uncertain"
  ) {
    await submitReviewedExecution(task, task.executionAttempt);
    return;
  }
  if (
    task === null || review.pending !== null
    || review.summary.selection_state !== "reviewing"
    || task.executionAttempt !== null
  ) return;
  const attempt = {
    review,
    taskId: task.taskId,
    requestId: review.summary.request_id,
    selectionRevision: review.summary.selection_revision,
    destructiveAcknowledged: review.summary.requires_destructive_confirmation,
    destructiveOperationCount: review.summary.destructive_operation_count,
    retry: null,
    submissionStarted: false,
    state: review.summary.requires_destructive_confirmation ? "confirming" : "submitting",
  };
  task.executionAttempt = attempt;
  review.pending = attempt.state === "confirming" ? "confirmation" : "execute";
  review.message = attempt.state === "confirming"
    ? "Confirm destructive changes in the dialog."
    : "Starting execution…";
  renderTasks();
  if (attempt.state === "confirming") {
    try {
      executionConfirmation.show({
        destructiveOperationCount: attempt.destructiveOperationCount,
        returnFocus,
        onCancel: () => cancelReviewedExecution(task, attempt),
        onConfirm: () => { void submitReviewedExecution(task, attempt); },
      });
    } catch (_error) {
      task.executionAttempt = null;
      review.pending = null;
      review.message = "Confirmation unavailable. Selection remains editable.";
      renderTasks();
    }
    return;
  }
  await submitReviewedExecution(task, attempt);
}

function cancelReviewedExecution(task, attempt) {
  if (task.executionAttempt !== attempt || attempt.state !== "confirming") return;
  task.executionAttempt = null;
  if (task.review === attempt.review) {
    attempt.review.pending = null;
    attempt.review.message = null;
  }
  renderTasks();
}

async function submitReviewedExecution(task, attempt) {
  if (
    task.executionAttempt !== attempt
    || !["confirming", "submitting", "uncertain"].includes(attempt.state)
  ) return;
  if (attempt.submissionStarted) return;
  const submit = attempt.retry ?? (() => startExecution(
    attempt.taskId,
    attempt.requestId,
    attempt.selectionRevision,
    attempt.destructiveAcknowledged,
  ));
  attempt.retry = null;
  attempt.submissionStarted = true;
  attempt.state = "submitting";
  if (task.review !== null) {
    task.review.pending = "execute";
    task.review.message = attempt.destructiveAcknowledged
      ? "Starting confirmed execution…"
      : "Starting execution…";
  }
  renderTasks();
  try {
    const result = await submit();
    if (tasks.get(task.taskId) !== task || task.executionAttempt !== attempt) return;
    task.executionAttempt = null;
    if (typeof result.task_id === "string") {
      task.sessionId = result.session_id;
      task.sessionState = "active";
      task.sessionReleased = false;
      task.executionStarted = true;
      task.executionControlRevision += 1;
      task.executionControlState = "running";
      task.reviewSessionId = result.session_id;
      attachTaskDrain(task);
      if (task.review === attempt.review) {
        attempt.review.message = executionControlMessage(task.executionControlState);
        attempt.review.pending = null;
      }
      renderTasks();
      await loadPlanReview(task, true);
      return;
    }
    const currentReview = task.review;
    if (currentReview === null) return;
    currentReview.message = result.disposition === "confirmation-required"
      ? "Confirmation no longer matches. Review selection again."
      : result.disposition === "conflict"
        ? "Selection changed. Review it before executing."
        : "Execution admission is already in progress.";
    currentReview.pending = null;
    renderTasks();
    await loadPlanReview(task, true);
  } catch (error) {
    if (tasks.get(task.taskId) !== task || task.executionAttempt !== attempt) return;
    const currentReview = task.review;
    if (error instanceof StartPlanUncertainError) {
      attempt.state = "uncertain";
      attempt.retry = error.retry;
      attempt.submissionStarted = false;
      if (currentReview !== null) {
        currentReview.pending = null;
        currentReview.message = "Execution uncertain. Retry the same request.";
      }
    } else {
      task.executionAttempt = null;
      if (currentReview !== null) {
        currentReview.pending = null;
        currentReview.message = currentReview.summary.preflight_ready
          ? "Execution did not start. Selection remains editable."
          : "Plan refused. Create a fresh plan.";
      }
    }
    renderTasks();
  } finally {
    if (
      tasks.get(task.taskId) === task && task.executionAttempt === attempt
      && attempt.state !== "uncertain"
    ) {
      task.executionAttempt = null;
      if (task.review === attempt.review) attempt.review.pending = null;
      renderTasks();
    }
  }
}

async function controlReviewedExecution(review, actionName) {
  const task = currentReviewTask(review);
  if (
    task === null || review.pending !== null || !task.executionStarted
    || task.sessionState !== "active" || task.sessionId === null
  ) return;
  const action = ++review.actionRevision;
  const sessionId = task.sessionId;
  const controlRevision = task.executionControlRevision;
  const controlState = task.executionControlState;
  review.pending = actionName;
  review.message = `${actionName[0].toUpperCase()}${actionName.slice(1)} requested…`;
  renderTasks();
  try {
    const result = await controlExecution(task.taskId, sessionId, actionName);
    if (
      retainedReviewTask(review) !== task || review.actionRevision !== action
      || task.sessionId !== sessionId || task.sessionState !== "active"
    ) return;
    if (
      task.executionControlRevision === controlRevision
      || task.executionControlState === controlState
    ) {
      if (result.accepted && ACTIVE_EXECUTION_CONTROL_STATES.has(result.after)) {
        task.executionControlRevision += 1;
        task.executionControlState = result.after;
        review.message = executionControlMessage(result.after);
      } else {
        review.message = result.detail || `The ${actionName} request was not accepted.`;
      }
    }
  } catch (_error) {
    if (
      retainedReviewTask(review) === task && review.actionRevision === action
      && task.sessionId === sessionId && task.sessionState === "active"
      && (
        task.executionControlRevision === controlRevision
        || task.executionControlState === controlState
      )
    ) {
      review.message = `${actionName[0].toUpperCase()}${actionName.slice(1)} uncertain. Follow live status.`;
    }
  } finally {
    if (
      retainedReviewTask(review) === task && review.actionRevision === action
      && task.sessionId === sessionId
    ) {
      review.pending = null;
      renderTasks();
    }
  }
}

async function planAgainFromReview(review) {
  const task = currentReviewTask(review);
  if (task === null || review.pending !== null) return;
  if (!canStartPlanAgain(task)) {
    review.message = "Wait for the current action, then try Plan again.";
    renderTasks();
    return;
  }
  const action = ++review.actionRevision;
  review.pending = "plan-again";
  review.message = "Creating plan…";
  renderTasks();
  const dispatched = await startPlanAgain(task);
  if (retainedReviewTask(review) === task && review.actionRevision === action) {
    review.pending = null;
    review.message = dispatched
      ? task.form?.actionMessage ?? null
      : "Wait for the current action, then try Plan again.";
    renderTasks();
  }
}

function editLocation(purpose, text) {
  const form = currentForm();
  if (!formIsEditable(form)) return;
  const row = form[purpose];
  row.text = text;
  clearLocationChoice(row);
  row.candidate = text ? { kind: "literal_path", path: text, selected_mount: null } : null;
  row.revision += 1;
  form.revision += 1;
  form.actionMessage = null;
  renderTasks();
}

function acceptLocation(row, result) {
  row.location = result;
  row.continuationId = result.continuation_id;
  row.mountIndex = null;
  if (result.display !== null) row.text = result.display;
}

function resolvedChoice(row, purpose) {
  return row.location?.purpose === purpose && typeof row.location.choice_id === "string"
    ? row.location
    : null;
}

async function admitRow(task, form, rowName, purpose = rowName) {
  const row = form[rowName];
  if (!row.text || row.candidate === null) return null;
  const revision = row.revision;
  const admissionRevision = ++row.admissionRevision;
  const result = await admitLocation(purpose, row.candidate);
  if (tasks.get(task.taskId) !== task || task.form !== form || row.revision !== revision || row.admissionRevision !== admissionRevision) return null;
  acceptLocation(row, result);
  renderTasks();
  return result;
}

async function validateLocation(purpose) {
  const task = currentTask();
  const form = task?.form;
  if (task === null || !formIsEditable(form)) return;
  try {
    await admitRow(task, form, purpose, locationPurpose(form, purpose));
  } catch (_error) {
    if (tasks.get(task.taskId) === task && task.form === form) renderTasks();
  }
}

async function pickLocation(purpose) {
  const task = currentTask();
  const form = task?.form;
  if (task === null || !formIsEditable(form)) return;
  const row = form[purpose];
  const admissionPurpose = locationPurpose(form, purpose);
  const prior = {
    location: row.location,
    candidate: row.candidate,
    continuationId: row.continuationId,
    mountIndex: row.mountIndex,
  };
  const revision = ++row.revision;
  const formRevision = ++form.revision;
  row.admissionRevision += 1;
  row.location = null;
  row.candidate = null;
  row.continuationId = null;
  row.mountIndex = null;
  renderTasks();
  const restore = () => {
    if (
      tasks.get(task.taskId) !== task || task.form !== form ||
      form.revision !== formRevision || row.revision !== revision
    ) return;
    row.location = prior.location;
    row.candidate = prior.candidate;
    row.continuationId = prior.continuationId;
    row.mountIndex = prior.mountIndex;
    renderTasks();
  };
  try {
    const result = await pickFolder(admissionPurpose);
    if (result === null) {
      restore();
      return;
    }
    if (
      tasks.get(task.taskId) !== task || task.form !== form ||
      form.revision !== formRevision || row.revision !== revision
    ) return;
    row.candidate = null;
    acceptLocation(row, result);
    row.text = result.display ?? "";
    renderTasks();
  } catch (_error) {
    restore();
  }
}

async function chooseRecentLocation(purpose, recent) {
  const task = currentTask();
  const form = task?.form;
  if (task === null || !formIsEditable(form)) return;
  const row = form[purpose];
  row.text = recent.display;
  clearLocationChoice(row);
  row.candidate = { kind: "remembered_location", location_id: recent.location_id, selected_mount: null };
  row.revision += 1;
  form.revision += 1;
  renderTasks();
  try {
    await admitRow(task, form, purpose, locationPurpose(form, purpose));
  } catch (_error) {
    if (tasks.get(task.taskId) === task && task.form === form) renderTasks();
  }
}

async function chooseRecentPair(pair) {
  const task = currentTask();
  const form = task?.form;
  if (task === null || !formIsEditable(form) || form.mode !== "sync-plan") return;
  const availability = recentPairAvailability[pair.mapping_id];
  if (form.batchRunning || availability?.source !== "online" || availability?.target !== "online"
    || !form.setup.recents.pairs.some((item) => item.mapping_id === pair.mapping_id
      && item.source.location_id === pair.source.location_id
      && item.target.location_id === pair.target.location_id)) return;
  for (const [rowName, recent] of [["source", pair.source], ["target", pair.target]]) {
    const row = form[rowName];
    row.text = recent.display;
    clearLocationChoice(row);
    row.candidate = { kind: "remembered_location", location_id: recent.location_id, selected_mount: null };
    row.revision += 1;
  }
  form.revision += 1;
  renderTasks();
  await Promise.allSettled([
    admitRow(task, form, "source", "source"),
    admitRow(task, form, "target", "target"),
  ]);
}

function editOption(key, value) {
  const form = currentForm();
  if (!formIsEditable(form) || form.options === null) return;
  if (key in form.options) form.options[key] = value;
  else if (key in form.options.preservation) form.options.preservation[key] = value;
  form.revision += 1;
  renderTasks();
}

function addFilter(value) {
  const form = currentForm();
  if (!formIsEditable(form) || form.options === null || value.length === 0) return;
  form.options.filters.push(value);
  form.revision += 1;
  renderTasks();
}

function removeFilter(index) {
  const form = currentForm();
  if (!formIsEditable(form) || form.options === null) return;
  form.options.filters.splice(index, 1);
  form.revision += 1;
  renderTasks();
}

async function chooseMount(rowName, mountIndex) {
  const task = currentTask();
  const form = task?.form;
  if (task === null || !formIsEditable(form)) return;
  const row = form[rowName];
  const purpose = locationPurpose(form, rowName);
  if (
    row.location?.state !== "ambiguous" ||
    !Number.isSafeInteger(mountIndex) ||
    mountIndex < 0 ||
    mountIndex >= row.location.candidates.length
  ) return;
  const continuationId = row.continuationId;
  const candidate = row.candidate;
  if (typeof continuationId !== "string" && candidate === null) return;
  const selection = typeof continuationId === "string"
    ? { continuation_id: continuationId, mount_index: mountIndex }
    : { ...candidate, selected_mount: row.location.candidates[mountIndex] };
  const revision = ++row.revision;
  const formRevision = ++form.revision;
  const admissionRevision = ++row.admissionRevision;
  row.mountIndex = mountIndex;
  renderTasks();
  try {
    const result = await admitLocation(purpose, selection);
    if (
      tasks.get(task.taskId) !== task ||
      task.form !== form ||
      form.revision !== formRevision ||
      row.revision !== revision ||
      row.admissionRevision !== admissionRevision ||
      row.continuationId !== continuationId ||
      row.mountIndex !== mountIndex
    ) return;
    acceptLocation(row, result);
    renderTasks();
  } catch (_error) {
    if (
      tasks.get(task.taskId) === task &&
      task.form === form &&
      row.revision === revision &&
      row.admissionRevision === admissionRevision
    ) {
      clearLocationChoice(row);
      renderTasks();
    }
  }
}

function beginFormAttempt(task, form, kind) {
  if (
    tasks.get(task.taskId) !== task || task.form !== form || form.attempt !== null ||
    (pageBatch !== null && pageBatch.running !== null)
  ) return null;
  const attempt = {
    kind,
    epoch: startupEpoch,
    running: true,
    dispatched: false,
    retry: null,
  };
  form.attempt = attempt;
  form.actionMessage = null;
  renderTasks();
  return attempt;
}

function currentFormAttempt(task, form, attempt) {
  return tasks.get(task.taskId) === task && task.form === form && form.attempt === attempt;
}

function freshFormAttempt(task, form, attempt, revision) {
  return currentFormAttempt(task, form, attempt)
    && !attempt.dispatched
    && attempt.epoch === startupEpoch
    && form.revision === revision;
}

async function dispatchFormAttempt(task, form, attempt, submit) {
  attempt.dispatched = true;
  try {
    await submit();
  } catch (error) {
    if (!currentFormAttempt(task, form, attempt)) return;
    if (error instanceof StartPlanUncertainError) {
      attempt.running = false;
      attempt.retry = error.retry;
      form.actionMessage = "The start response could not be confirmed. Retry the same request.";
      renderTasks();
      return;
    }
    form.attempt = null;
    form.actionMessage = "That task could not be started. Review the setup and try again.";
    renderTasks();
    void loadTaskSetup(task);
    return;
  }
  if (currentFormAttempt(task, form, attempt)) form.attempt = null;
  await refreshTasks(startupEpoch);
}

async function retryFormAttempt(task, form, kind) {
  const attempt = form.attempt;
  if (
    attempt === null || attempt.kind !== kind || attempt.running ||
    typeof attempt.retry !== "function"
  ) return false;
  const retry = attempt.retry;
  attempt.running = true;
  attempt.retry = null;
  form.actionMessage = "Retrying the same start request…";
  renderTasks();
  await dispatchFormAttempt(task, form, attempt, retry);
  return true;
}

async function choicesForStart(task, form, attempt, revision, optionsInput) {
  const source = resolvedChoice(form.source, "source") ?? await admitRow(task, form, "source", "source");
  if (!freshFormAttempt(task, form, attempt, revision)) return null;
  const target = resolvedChoice(form.target, "target") ?? await admitRow(task, form, "target", "target");
  if (!freshFormAttempt(task, form, attempt, revision)) return null;
  if (typeof source?.choice_id !== "string" || typeof target?.choice_id !== "string") return null;
  const options = await prepareSetup(optionsInput);
  if (!freshFormAttempt(task, form, attempt, revision)) return null;
  return { sourceId: source.choice_id, targetId: target.choice_id, options };
}

function abandonFreshAttempt(task, form, attempt) {
  if (currentFormAttempt(task, form, attempt) && !attempt.dispatched) {
    form.attempt = null;
    renderTasks();
  }
}

function refuseFreshAttempt(task, form, attempt) {
  if (!currentFormAttempt(task, form, attempt) || attempt.dispatched) return;
  form.attempt = null;
  form.actionMessage = "That task could not be started. Review the setup and try again.";
  renderTasks();
  void loadTaskSetup(task);
}

async function startCurrentPlan() {
  const task = currentTask();
  const form = task?.form;
  if (
    task === null || task.closePending || form === null || !form.editable || form.mode !== "sync-plan" ||
    (originHasPendingBatch(task.taskId) || batchTaskBlockReason(task.taskId) !== null) ||
    (pageBatch !== null && pageBatch.running !== null)
  ) return;
  if (form.attempt !== null) {
    await retryFormAttempt(task, form, "sync-plan");
    return;
  }
  if (!form.source.text || !form.target.text || form.options === null) return;
  const revision = form.revision;
  const optionsInput = cloneOptions(form.options);
  const attempt = beginFormAttempt(task, form, "sync-plan");
  if (attempt === null) return;
  try {
    const ready = await choicesForStart(task, form, attempt, revision, optionsInput);
    if (ready === null) {
      abandonFreshAttempt(task, form, attempt);
      return;
    }
    form.options = cloneOptions(ready.options);
    await dispatchFormAttempt(
      task, form, attempt,
      () => startPlan(task.taskId, ready.sourceId, ready.targetId, ready.options),
    );
  } catch (_error) {
    refuseFreshAttempt(task, form, attempt);
  }
}

async function startCurrentInventory() {
  const task = currentTask();
  const form = task?.form;
  if (
    task === null || task.closePending || form === null || !form.editable || form.mode !== "inventory" ||
    batchTaskBlockReason(task.taskId) !== null ||
    (pageBatch !== null && pageBatch.running !== null)
  ) return;
  if (form.attempt !== null) {
    await retryFormAttempt(task, form, "inventory");
    return;
  }
  if (!form.source.text) return;
  const revision = form.revision;
  const attempt = beginFormAttempt(task, form, "inventory");
  if (attempt === null) return;
  try {
    const root = resolvedChoice(form.source, "inventory")
      ?? await admitRow(task, form, "source", "inventory");
    if (!freshFormAttempt(task, form, attempt, revision) || typeof root?.choice_id !== "string") {
      abandonFreshAttempt(task, form, attempt);
      return;
    }
    await dispatchFormAttempt(task, form, attempt, () => startInventory(task.taskId, root.choice_id));
  } catch (_error) {
    refuseFreshAttempt(task, form, attempt);
  }
}

function addCurrentPair() {
  const task = currentTask();
  const form = currentForm();
  if (
    task === null || task.closePending || !formIsEditable(form) || form.mode !== "sync-plan" ||
    (pageBatch !== null && pageBatch.running !== null)
  ) return;
  if (form.options === null) return;
  if (pageBatch === null) pageBatch = { rows: [], generation: 0, running: null };
  if (pageBatch.rows.length >= 48) return;
  pageBatch.rows.push({
    originTaskId: task.taskId,
    source: snapshotLocationRow(form.source),
    target: snapshotLocationRow(form.target),
    state: "queued",
    stage: null,
    retry: null,
    taskId: null,
    sourceId: null,
    targetId: null,
    options: cloneOptions(form.options),
    snapshot: null,
    recents: null,
    message: "Ready to create.",
  });
  renderTasks();
}

function removeBatchRow(row) {
  if (pageBatch === null || row?.state !== "queued") return;
  const index = pageBatch.rows.indexOf(row);
  if (index < 0 || row.originTaskId !== selectedTaskId) return;
  pageBatch.rows.splice(index, 1);
  renderTasks();
}

function clearBatchResults() {
  if (pageBatch === null || selectedTaskId === null) return;
  pageBatch.rows = pageBatch.rows.filter((row) => row.originTaskId !== selectedTaskId
    || !["created", "refused", "stopped"].includes(row.state));
  renderTasks();
}

function currentBatchRun(batch, owner, generation) {
  return pageBatch === batch && batch.running === owner && batch.generation === generation;
}

function batchRowUncertain(row, stage, error) {
  row.state = "uncertain";
  row.stage = stage;
  row.retry = error.retry;
  row.message = stage === "creating"
    ? "Task creation could not be confirmed. Retry this same batch request."
    : "Plan start could not be confirmed. Retry this same batch request.";
}

function adoptBatchShell(shell, row) {
  const task = adoptTask({
    task_id: shell.task_id,
    session_id: null,
    session_state: null,
    session_released: false,
    task_kind: null,
    request_id: null,
  });
  row.taskId = task.taskId;
  task.form = createForm(row.snapshot, row.recents);
  task.form.source = snapshotLocationRow(row.source);
  task.form.target = snapshotLocationRow(row.target);
  task.form.options = cloneOptions(row.options);
  return task;
}

async function startBatchRow(row, context) {
  try {
    let task = row.taskId === null ? null : tasks.get(row.taskId) ?? null;
    if (row.state === "uncertain") {
      const stage = row.stage;
      const retry = row.retry;
      if (typeof retry !== "function") throw new BridgeTransportError();
      row.state = "submitting";
      row.retry = null;
      row.message = stage === "creating" ? "Retrying task creation…" : "Retrying plan start…";
      renderTasks();
      const result = await retry();
      if (stage === "starting") {
        row.state = "created";
        row.message = "Plan task created.";
        return;
      }
      task = adoptBatchShell(result, row);
    } else {
      const options = await prepareSetup(cloneOptions(row.options));
      if (!context.contains(row) || row.state !== "queued" || !context.canSubmit()) return;
      row.options = cloneOptions(options);
      row.state = "submitting";
      row.message = "Checking folders…";
      renderTasks();
      const source = await admitBatchRow(row.source, "source");
      const target = await admitBatchRow(row.target, "target");
      if (typeof source?.choice_id !== "string" || typeof target?.choice_id !== "string") {
        throw new BridgeTransportError();
      }
      row.sourceId = source.choice_id;
      row.targetId = target.choice_id;
      row.snapshot = context.snapshot;
      row.recents = context.recents;
      if (!context.canSubmit()) {
        row.state = "stopped";
        row.message = "Not submitted after the page was replaced.";
        return;
      }
      row.stage = "creating";
      row.message = "Creating task…";
      renderTasks();
      const shell = await createTask();
      task = adoptBatchShell(shell, row);
    }
    if (!context.canSubmit()) {
      row.state = "stopped";
      row.message = "The blank task was retained; its plan was not submitted after the page was replaced.";
      void refreshTasks(startupEpoch);
      return;
    }
    row.stage = "starting";
    row.message = "Creating plan…";
    renderTasks();
    await startPlan(task.taskId, row.sourceId, row.targetId, row.options);
    row.state = "created";
    row.message = "Plan task created.";
  } catch (error) {
    if (error instanceof TaskCreateUncertainError) {
      batchRowUncertain(row, "creating", error);
    } else if (error instanceof StartPlanUncertainError) {
      batchRowUncertain(row, "starting", error);
    } else {
      row.state = "refused";
      row.retry = null;
      row.message = "That pair could not be created. Review its folders and settings, then try again.";
    }
  }
}

async function startPairBatch() {
  const task = currentTask();
  const form = currentForm();
  const batch = pageBatch;
  if (
    task === null || task.closePending || !formIsEditable(form) || form.mode !== "sync-plan" || form.attempt !== null ||
    batch === null || batch.running !== null
  ) return;
  const rows = batch.rows.filter((row) => row.originTaskId === task.taskId
    && ["queued", "uncertain"].includes(row.state));
  if (rows.length === 0) return;
  const queued = rows.filter((row) => row.state === "queued");
  if (queued.some((row) => row.options === null)) return;
  const owner = { originTaskId: task.taskId };
  const generation = batch.generation;
  const epoch = startupEpoch;
  const context = {
    epoch,
    snapshot: form.setup,
    recents: defaultSetup?.recents ?? form.setup.recents,
    contains: (row) => batch.rows.includes(row),
    canSubmit: () => currentBatchRun(batch, owner, generation) && epoch === startupEpoch
      && tasks.get(task.taskId) === task && !task.closePending,
  };
  batch.running = owner;
  renderTasks();
  try {
    for (const row of rows) {
      if (!currentBatchRun(batch, owner, generation) || epoch !== startupEpoch) break;
      if (!batch.rows.includes(row)) continue;
      if (!["queued", "uncertain"].includes(row.state)) continue;
      await startBatchRow(row, context);
      renderTasks();
    }
  } finally {
    if (batch.running === owner) batch.running = null;
    renderTasks();
  }
  if (epoch === startupEpoch) await refreshTasks(epoch);
}

async function admitBatchRow(row, purpose) {
  const accepted = resolvedChoice(row, purpose);
  if (accepted !== null) return accepted;
  if (!row.text || row.candidate === null) return null;
  const revision = row.revision;
  const result = await admitLocation(purpose, row.candidate);
  if (row.revision !== revision) return null;
  acceptLocation(row, result);
  return result;
}

function choosePlanAgainMount(purpose, mount) {
  const form = currentForm();
  if (form === null || !form.canPlanAgain || form.attempt !== null) return;
  form.planAgainMounts[purpose] = mount;
  form.revision += 1;
  renderTasks();
}

function canStartPlanAgain(task) {
  const form = task?.form;
  if (
    task === null || currentTask() !== task || task.closePending ||
    form?.canPlanAgain !== true ||
    originHasPendingBatch(task.taskId) || batchTaskBlockReason(task.taskId) !== null ||
    (pageBatch !== null && pageBatch.running !== null)
  ) return false;
  return form.attempt === null || (
    form.attempt.kind === "plan-again" && !form.attempt.running &&
    typeof form.attempt.retry === "function"
  );
}

async function startPlanAgain(task = currentTask()) {
  const form = task?.form;
  if (!canStartPlanAgain(task)) return false;
  if (form.attempt !== null) {
    return retryFormAttempt(task, form, "plan-again");
  }
  const revision = form.revision;
  const sourceMount = form.planAgainMounts.source;
  const targetMount = form.planAgainMounts.target;
  const attempt = beginFormAttempt(task, form, "plan-again");
  if (attempt === null || !freshFormAttempt(task, form, attempt, revision)) return false;
  await dispatchFormAttempt(
    task, form, attempt,
    () => planAgain(task.taskId, sourceMount, targetMount),
  );
  return true;
}

class StartupSupersededError extends Error {}

let startupEpoch = 0;
let rejectSupersededStartup = null;

async function finishStartup(epoch, readinessBaseline) {
  const superseded = new Promise((resolve, reject) => {
    void resolve;
    if (epoch !== startupEpoch) {
      reject(new StartupSupersededError());
      return;
    }
    rejectSupersededStartup = reject;
  });
  const awaitCurrent = async (value) => {
    const result = await Promise.race([value, superseded]);
    if (epoch !== startupEpoch) {
      throw new StartupSupersededError();
    }
    return result;
  };
  await awaitCurrent(whenBridgeApiReady());
  try {
    await awaitCurrent(acknowledgeShellReady());
  } catch (error) {
    if (!(error instanceof BridgeTransportError)) {
      throw error;
    }
  }
  const challenge = await awaitCurrent(
    readiness.whenReceivedAfter(readinessBaseline),
  );
  let acknowledged = false;
  for (let attempt = 0; attempt < 2 && !acknowledged; attempt += 1) {
    try {
      const result = await awaitCurrent(echoReadiness(challenge));
      acknowledged = result.acknowledged;
    } catch (error) {
      if (!(error instanceof BridgeTransportError) || attempt > 0) {
        throw error;
      }
    }
  }
  if (!acknowledged) {
    throw new BridgeTransportError(
      "The desktop readiness echo could not be confirmed.",
    );
  }
  markBridgeOperational();
  await awaitCurrent(refreshTasks(epoch));
  void loadDefaultSetup();
  void theme.open(appliedPresentationRevision);
  if (status.textContent === "Starting...") {
    renderHostStatus("Ready");
  }
}

let startupAttempt = null;
let startupRerunRequested = false;
let startupRerunReadinessBaseline = null;

function ensureStartup({
  rerun = false,
  readinessBaseline = readiness.revision(),
} = {}) {
  if (startupAttempt !== null) {
    if (rerun) {
      startupRerunRequested = true;
      startupRerunReadinessBaseline = readinessBaseline;
    }
    return startupAttempt;
  }
  const attempt = finishStartup(startupEpoch, readinessBaseline);
  startupAttempt = attempt;
  void attempt.finally(() => {
    if (startupAttempt === attempt) {
      startupAttempt = null;
      rejectSupersededStartup = null;
      if (startupRerunRequested) {
        const rerunReadinessBaseline = startupRerunReadinessBaseline;
        startupRerunRequested = false;
        startupRerunReadinessBaseline = null;
        void ensureStartup({
          readinessBaseline: rerunReadinessBaseline,
        });
      }
    }
  }).catch(() => {
    // Native startup refusal owns the action-guiding terminal diagnostic.
  });
  return attempt;
}

window.addEventListener("pywebviewready", () => {
  startupEpoch += 1;
  recentPairProbeRevision += 1;
  recentPairProbePending = false;
  recentPairAvailability = Object.create(null);
  renderTasks();
  if (pageBatch !== null) {
    pageBatch.generation += 1;
    for (const row of pageBatch.rows) {
      if (row.state === "queued") {
        row.state = "stopped";
        row.message = "Not submitted after the page was replaced.";
      }
    }
  }
  for (const task of tasks.values()) {
    task.closePending = false;
    if (task.form !== null && task.form.attempt !== null && !task.form.attempt.dispatched) {
      task.form.attempt = null;
      task.form.actionMessage = "The start was stopped before submission when the page was replaced.";
    }
  }
  theme.invalidate();
  rejectSupersededStartup?.(new StartupSupersededError());
  if (status.textContent === "Ready") {
    renderHostStatus("Starting...");
  }
  void ensureStartup({ rerun: true });
});
void ensureStartup();
