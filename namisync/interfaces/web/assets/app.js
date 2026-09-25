import {
  acknowledgeShellReady,
  admitLocation,
  BridgeTransportError,
  closeTask,
  controlExecution,
  createTask,
  echoReadiness,
  getExecutionDetail,
  getPlanAnchor,
  getPlanOperationAnchor,
  getPlanWindow,
  listTasks,
  markBridgeOperational,
  mutatePlanSelection,
  mutatePlanScope,
  mutatePlanHighlight,
  mutatePlanHighlightedSelection,
  OutcomeUnavailableError,
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
  TaskCloseUncertainError,
  TerminalPresentationError,
  TerminalSessionReleaseError,
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
import { advanceProgressPresentation, rebaseProgressSampling } from "./task_status.js";

const app = document.querySelector("#app");
const status = document.querySelector("#host-status");
const themeSelector = document.querySelector("#theme-mode");
const themeOutcomeStatus = document.querySelector("#theme-outcome-status");
const themeRetryOutcome = document.querySelector("#theme-retry-outcome");
const settingsView = document.querySelector("#settings-view");
const themeOptions = document.querySelector("#theme-options");
const UNKNOWN_OUTCOME_GUIDANCE = "Original outcome cannot be confirmed. Close and reopen NamiSync to review current state.";
if (
  !(app instanceof HTMLElement)
  || !(status instanceof HTMLElement)
  || !(themeSelector instanceof HTMLElement)
  || !(themeOutcomeStatus instanceof HTMLElement)
  || !(themeRetryOutcome instanceof HTMLElement)
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
const theme = installThemeSelector(themeCombobox, {
  onOutcomeStatus(message, retryAvailable) {
    renderText(themeOutcomeStatus, message ?? "");
    themeOutcomeStatus.hidden = message === null;
    themeRetryOutcome.hidden = !retryAvailable;
  },
});
themeRetryOutcome.addEventListener("click", () => { void theme.retryOutcome(); });
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
let planFollowLookupRunning = false;
let pendingPlanFollow = null;
let activePlanFollowKey = null;
let activePlanFollowGeneration = null;

const ACTIVE_EXECUTION_CONTROL_STATES = new Set([
  "pending",
  "running",
  "pausing",
  "paused",
  "canceling",
]);
const STOPPED_TASK_UPDATES_MESSAGE =
  "Task updates stopped. Select Retry updates on this task to restore execution controls.";
const TASK_RECOVERY_MESSAGES = new Set([
  STOPPED_TASK_UPDATES_MESSAGE,
  "Task updates stopped. Close can be retried.",
  "Task recovery paused. Select Retry updates on this task.",
  "Reconnecting task updates…",
  "Task updates are still unavailable. Select Retry updates to try again.",
]);

function clearTaskRecoveryError(task) {
  if (TASK_RECOVERY_MESSAGES.has(task.error)) task.error = null;
}

function setTaskRecoveryError(task, message) {
  if (task.error === null || TASK_RECOVERY_MESSAGES.has(task.error)) {
    task.error = message;
  }
}

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
  onRetryLocationOutcome: retryLocationOutcomes,
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
  onRetryOutcome: (review) => { void retryReviewOutcome(review); },
  onPlanAgain: (review) => { void planAgainFromReview(review); },
  onExecutionDetail: (review, row) => { void readExecutionDetail(review, row); },
  onFollowOverride: disablePlanFollow,
  onNavigateCurrent: (review, enableFollow) => { queuePlanFollow(review, enableFollow, true); },
}, settingsView);
const rail = createTaskRail({
  onCreate: () => { void createBlankTask(); },
  onSelect: selectTask,
  onClose: (taskId) => { void closeRetainedTask(taskId); },
  onRetryUpdates: retryTaskUpdates,
  onSettings: showSettings,
});
app.append(rail.element, panel.element);
const executionConfirmation = createExecutionConfirmation([app, themeOptions]);
document.body.append(executionConfirmation.element);

function taskArray() {
  return Array.from(tasks.values()).reverse();
}

function canCancelAfterFixedReviewOutcome(task, review) {
  const attempt = task.executionControlAttempt;
  return review !== null && review.pending === "outcome"
    && review.outcomeUnknown && review.outcomeRetry === null
    && task.reviewOutcomeUnknown && review.outcomeAction !== "cancel"
    && task.executionStarted && task.sessionState === "active"
    && task.sessionId !== null && task.reviewSessionId === task.sessionId
    && !task.drainUnavailable && !task.closePending && task.closeRetry === null
    && !task.closeOutcomeUnknown && !task.startOutcomeUnknown
    && !task.releaseOutcomeUnknown && task.executionAttempt === null
    && task.executionControlState !== "canceling"
    && (attempt === null || (!attempt.pending && attempt.retry == null
      && !attempt.unknown && !(attempt.independent && attempt.accepted)));
}

function taskCloseBlockReason(task) {
  if (task.closePending && !task.closeManualReady) {
    return task.closeMessage ?? "Wait for this Close request to finish.";
  }
  if (task.closeOutcomeUnknown || task.startOutcomeUnknown || task.reviewOutcomeUnknown
      || task.releaseOutcomeUnknown
      || (task.executionAttempt?.state === "uncertain"
        && task.executionAttempt.retry === null)) return UNKNOWN_OUTCOME_GUIDANCE;
  if (task.form !== null && (
    task.form.source.outcomeRetry !== null || task.form.target.outcomeRetry !== null
    || task.form.source.outcomeUnknown || task.form.target.outcomeUnknown
  )) return "Resolve the folder outcome before closing this task.";
  if (task.executionAttempt !== null) return "Resolve the in-flight execution request before closing.";
  if (task.closeRetry === null && !task.closeManualReady
      && task.review !== null && task.review.pending !== null) {
    return task.review.outcomeRetry !== null
      ? "Check the original review outcome before closing this task."
      : "Wait for the current review action before closing this task.";
  }
  return batchTaskBlockReason(task.taskId);
}

function renderTasks() {
  for (const task of tasks.values()) {
    if (task.reviewOutcomeUnknown && task.review !== null) {
      task.review.message = UNKNOWN_OUTCOME_GUIDANCE;
    }
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
        && ["queued", "submitting", "uncertain", "unknown"].includes(row.state)) ?? false);
      task.form.batchPending ||= batchBlockReason !== null;
      task.form.batchMessage = syncBatchOwner ? batchTaskStartMessage(task.taskId)
        : batchBlockReason === null ? null
          : batchTaskStartMessage(task.taskId)
            ?? "Return to Sync to resolve its in-flight batch request before starting Inventory.";
      task.form.closePending = task.closePending || task.closeRetry !== null
        || task.closeOutcomeUnknown || task.startOutcomeUnknown;
      if (task.startOutcomeUnknown) task.form.actionMessage = UNKNOWN_OUTCOME_GUIDANCE;
    }
    task.canCancelAfterFixedReviewOutcome = canCancelAfterFixedReviewOutcome(task, task.review);
    task.closeBlockReason = taskCloseBlockReason(task);
    task.canPlanAgain = canStartPlanAgain(task);
  }
  rail.render(
    taskArray(),
    selectedTaskId,
    createAttempt?.running === true || createAttempt?.unknown === true,
    settingsVisible,
  );
  if (settingsVisible) panel.renderSettings();
  else panel.render(selectedTaskId === null ? null : tasks.get(selectedTaskId) ?? null);
}

function showSettings() {
  if (settingsVisible) return;
  const task = currentTask();
  if (task?.review != null) retireExecutionDetail(task.review);
  navigationRevision += 1;
  settingsVisible = true;
  renderTasks();
}

function planFollowEligible(review) {
  return review.summary.search_query === ""
    && review.summary.filters.length === 0
    && review.summary.sort_column === "path"
    && review.summary.sort_direction === "ascending";
}

function disablePlanFollow(review) {
  if (review?.follow == null || review.follow.programmatic === true) return;
  review.follow.enabled = false;
  review.follow.generation += 1;
  renderTasks();
}

function queuePlanFollow(review, enableFollow = false, explicit = false) {
  const task = currentReviewTask(review);
  if (task === null || task.sessionId === null || review.follow == null) return;
  review.follow.eligible = planFollowEligible(review);
  const operationId = task.progressPresentation?.activeItem?.item_id ?? null;
  review.follow.hasTarget = operationId !== null;
  if (operationId === null) {
    review.follow.message = "No operation is active.";
    review.message = review.follow.message;
    renderTasks();
    return;
  }
  if (enableFollow) review.follow.enabled = review.follow.eligible;
  const anchorKey = `${task.sessionId}:${review.summary.view_revision}:${operationId}`;
  if (review.follow.anchorKey === anchorKey && Number.isSafeInteger(review.follow.anchorIndex)
      && review.follow.anchorIndex >= review.window.offset
      && review.follow.anchorIndex < review.window.offset + review.window.rows.length) {
    if (explicit) {
      review.follow.scrollOffset = review.follow.anchorIndex;
      renderTasks();
    }
    return;
  }
  if (planFollowLookupRunning && activePlanFollowKey === anchorKey
      && activePlanFollowGeneration === review.follow.generation) return;
  const request = Object.freeze({
    task, review, sessionId: task.sessionId, operationId,
    viewRevision: review.summary.view_revision,
    actionRevision: review.actionRevision,
    anchorKey,
    cachedIndex: review.follow.anchorKey === anchorKey ? review.follow.anchorIndex : null,
    followGeneration: review.follow.generation,
    navigation: navigationRevision,
    automatic: enableFollow || review.follow.enabled,
  });
  pendingPlanFollow = request;
  void drainPlanFollow();
}

async function drainPlanFollow() {
  if (planFollowLookupRunning) return;
  planFollowLookupRunning = true;
  try {
    while (pendingPlanFollow !== null) {
      const request = pendingPlanFollow;
      pendingPlanFollow = null;
      const {
        task, review, sessionId, operationId, viewRevision, actionRevision, anchorKey,
        cachedIndex, followGeneration, navigation,
      } = request;
      activePlanFollowKey = anchorKey;
      activePlanFollowGeneration = followGeneration;
      const stillCurrent = () => currentReviewTask(review) === task
        && !settingsVisible && navigationRevision === navigation
        && task.sessionId === sessionId && review.summary.view_revision === viewRevision
        && review.actionRevision === actionRevision
        && review.follow.generation === followGeneration
        && task.progressPresentation?.activeItem?.item_id === operationId;
      try {
        const anchor = Number.isSafeInteger(cachedIndex)
          ? { disposition: "current", index: cachedIndex }
          : await getPlanOperationAnchor(task.taskId, sessionId, viewRevision, operationId);
        if (!stillCurrent()) continue;
        if (anchor.disposition !== "current" || anchor.index === null) {
          review.follow.message = "The current operation is excluded from this view.";
          review.message = review.follow.message;
          renderTasks();
          continue;
        }
        const window = await getPlanWindow(task.taskId, viewRevision, anchor.index, 256);
        if (!stillCurrent() || window.disposition !== "current"
            || window.view_revision !== viewRevision
            || window.highlight_revision !== review.summary.highlight_revision) continue;
        adoptExecutionWindow(review, window);
        review.follow.anchorKey = anchorKey;
        review.follow.anchorIndex = anchor.index;
        review.follow.scrollOffset = anchor.index;
        review.follow.message = null;
        if ([
          "No operation is active.",
          "The current operation is excluded from this view.",
          "Current operation navigation is unavailable. Try again.",
        ].includes(review.message)) review.message = null;
        renderTasks();
      } catch (_error) {
        if (stillCurrent()) {
          review.follow.message = "Current operation navigation is unavailable. Try again.";
          review.message = review.follow.message;
          renderTasks();
        }
      } finally {
        activePlanFollowKey = null;
        activePlanFollowGeneration = null;
      }
    }
  } finally {
    planFollowLookupRunning = false;
    activePlanFollowKey = null;
    activePlanFollowGeneration = null;
    if (pendingPlanFollow !== null) void drainPlanFollow();
  }
}

function selectTask(taskId) {
  const task = tasks.get(taskId);
  if (task === undefined) {
    return;
  }
  navigationRevision += 1;
  const previous = selectedTaskId === null ? null : tasks.get(selectedTaskId) ?? null;
  if (previous?.review != null) retireExecutionDetail(previous.review);
  if (selectedTaskId !== taskId && task.progressPresentation !== null) {
    task.progressPresentation = rebaseProgressSampling(task.progressPresentation);
  }
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
  if (task.executionWindowDirty) void refreshExecutionWindow(task);
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
      closeRetry: null,
      closeAwaitingTerminal: false,
      closeTerminalSeen: false,
      closeAutoConsumed: false,
      closeManualReady: false,
      closeOutcomeUnknown: false,
      startOutcomeUnknown: false,
      reviewOutcomeUnknown: false,
      releaseOutcomeUnknown: false,
      closeFailed: false,
      closeMessage: null,
      recoveryRetry: null,
      recoverySessionId: null,
      recoveryRunning: false,
      error: null,
      label: `Task ${nextTaskNumber}`,
      stopDrain: null,
      drainUnavailable: false,
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
      executionControlAttempt: null,
      executionResult: null,
      executionStartedAt: null,
      executionEndedAt: null,
      executionWindowDirty: false,
      executionWindowDirtyRevision: 0,
      executionWindowRefreshRunning: false,
      progressState: null,
      progressPresentation: null,
    };
    nextTaskNumber += 1;
    tasks.set(task.taskId, task);
  } else {
    if (task.sessionId !== summary.session_id) {
      task.recoveryRetry = null;
      task.recoverySessionId = null;
      task.recoveryRunning = false;
      task.closeFailed = false;
    }
    if (task.sessionId !== summary.session_id || summary.session_state !== "active") {
      const controlAttempt = task.executionControlAttempt;
      task.executionControlAttempt = null;
      if (task.review !== null && controlAttempt !== null
          && task.review.pending === controlAttempt.actionName) task.review.pending = null;
    }
    if (
      task.sessionId !== null
      && summary.session_id !== null
      && task.sessionId !== summary.session_id
      && task.review !== null
    ) {
      task.executionStarted = true;
      task.executionResult = null;
      task.executionStartedAt = null;
      task.executionEndedAt = null;
      task.executionWindowDirty = true;
      task.executionWindowDirtyRevision += 1;
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
    (error, retry) => acceptTaskRefusal(task, sessionId, error, retry),
    {
      terminal: task.sessionState !== "active",
      sessionReleased: task.sessionReleased,
    },
    (_taskId, sessionId) => acceptTaskRelease(task, sessionId),
    (_taskId, sessionId) => acceptTaskRecovery(task, sessionId),
  );
  task.drainUnavailable = false;
}

function acceptTaskUpdate(task, sessionId, update, progressState = null) {
  if (tasks.get(task.taskId) !== task || task.sessionId !== sessionId) {
    return;
  }
  if (progressState !== null) {
    task.progressState = progressState;
    task.progressPresentation = advanceProgressPresentation(
      task.progressPresentation, progressState, update,
    );
    if (task.review?.follow != null) {
      task.review.follow.hasTarget = task.progressPresentation?.activeItem?.item_id != null;
    }
  }
  if (task.executionStarted) markExecutionWindowDirty(task);
  if (
    update.update_type === "event"
    && update.event?.body_type === "StateChanged"
    && ACTIVE_EXECUTION_CONTROL_STATES.has(update.event.body?.state)
    && task.sessionState === "active"
  ) {
    task.executionControlRevision += 1;
    task.executionControlState = update.event.body.state;
    if (task.executionControlAttempt?.sessionId === sessionId) {
      if (task.executionControlAttempt.pending) {
        task.executionControlAttempt.message = executionControlMessage(task.executionControlState);
      } else if (task.executionControlAttempt.retry == null
          && !task.executionControlAttempt.unknown
          && !(task.executionControlAttempt.independent
            && task.executionControlAttempt.accepted)) {
        task.executionControlAttempt = null;
      }
    }
    if (task.executionStarted && task.review !== null && !task.reviewOutcomeUnknown) {
      task.review.message = executionControlMessage(task.executionControlState);
    }
    renderTasks();
    return;
  }
  if (update.update_type === "record") {
    task.recoveryRetry = null;
    task.recoverySessionId = null;
    task.recoveryRunning = false;
    task.drainUnavailable = false;
    clearTaskRecoveryError(task);
    taskMutationRevision += 1;
    task.executionControlRevision += 1;
    const controlAttempt = task.executionControlAttempt;
    task.executionControlAttempt = null;
    if (task.review !== null && controlAttempt !== null
        && task.review.pending === controlAttempt.actionName) task.review.pending = null;
    task.sessionState = update.record.state;
    if (update.record.kind === "sync-execution") {
      task.executionResult = update.record.result;
      task.executionStartedAt = update.record.started_at ?? null;
      task.executionEndedAt = update.record.ended_at ?? null;
    }
    if (task.form !== null) task.form.sessionState = task.sessionState;
    if (task.executionStarted && task.review !== null) {
      task.review.message = task.sessionState === "completed" ? null : `Execution ${task.sessionState}.`;
    }
    if (task.closePending && ["completed", "failed", "canceled", "refused"].includes(task.sessionState)) {
      task.closeTerminalSeen = true;
      continuePendingClose(task);
    }
    renderTasks();
    if (["completed", "failed", "canceled", "refused"].includes(task.sessionState)) {
      void loadTaskSetup(task);
    }
  } else {
    renderTasks();
  }
  if (task.review !== null && task.executionStarted && task.sessionState === "active") {
    task.review.follow.hasTarget = task.progressPresentation?.activeItem?.item_id != null;
    if (task.review.follow.enabled && task.review.follow.eligible) queuePlanFollow(task.review);
  }
}

function acceptTaskRefusal(task, sessionId, error, retry = null) {
  if (tasks.get(task.taskId) !== task || task.sessionId !== sessionId) {
    return;
  }
  const drainStopped = task.sessionState === "active"
    && !(error instanceof TerminalPresentationError)
    && !(error instanceof TerminalSessionReleaseError);
  if (drainStopped) task.drainUnavailable = true;
  task.recoveryRetry = retry ?? (typeof error?.retry === "function" ? error.retry : null);
  task.recoverySessionId = sessionId;
  task.recoveryRunning = false;
  if (error instanceof TerminalSessionReleaseError && !error.checkable) {
    task.releaseOutcomeUnknown = true;
    setTaskRecoveryError(task, UNKNOWN_OUTCOME_GUIDANCE);
    renderTasks();
    return;
  }
  if (drainStopped && task.executionStarted) {
    setTaskRecoveryError(task, STOPPED_TASK_UPDATES_MESSAGE);
    if (task.review !== null) task.review.message = STOPPED_TASK_UPDATES_MESSAGE;
  } else {
    setTaskRecoveryError(task, task.recoveryRetry === null
      ? "Task updates stopped. Close can be retried."
      : "Task recovery paused. Select Retry updates on this task.");
  }
  renderTasks();
}

function acceptTaskRecovery(task, sessionId) {
  if (tasks.get(task.taskId) !== task || task.sessionId !== sessionId) return;
  task.recoveryRetry = null;
  task.recoverySessionId = null;
  task.recoveryRunning = false;
  task.drainUnavailable = false;
  clearTaskRecoveryError(task);
  if (task.review?.message === STOPPED_TASK_UPDATES_MESSAGE) {
    task.review.message = task.executionControlAttempt?.sessionId === sessionId
      ? task.executionControlAttempt.message : executionControlMessage(task.executionControlState);
  }
  renderTasks();
}

function retryTaskUpdates(taskId) {
  const task = tasks.get(taskId);
  if (
    task === undefined || task.recoveryRunning || task.closeRetry !== null ||
    task.recoverySessionId !== task.sessionId ||
    typeof task.recoveryRetry !== "function"
  ) return;
  task.recoveryRunning = true;
  setTaskRecoveryError(task, "Reconnecting task updates…");
  renderTasks();
  try {
    if (task.recoveryRetry() === false) {
      task.recoveryRunning = false;
      setTaskRecoveryError(task, "Task updates are still unavailable. Select Retry updates to try again.");
      renderTasks();
    }
  } catch (_error) {
    task.recoveryRunning = false;
    setTaskRecoveryError(task, "Task updates are still unavailable. Select Retry updates to try again.");
    renderTasks();
  }
}

async function refreshTasks() {
  const mutationBaseline = taskMutationRevision;
  const result = await listTasks();
  if (mutationBaseline !== taskMutationRevision) {
    void refreshTasks();
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
  if (createAttempt?.running || createAttempt?.unknown) {
    return;
  }
  if (createAttempt !== null && typeof createAttempt.retry !== "function") return;
  const selectionBaseline = navigationRevision;
  const retry = createAttempt?.retry ?? null;
  const attempt = createAttempt ?? {
    running: true,
    dispatched: true,
    retry: null,
    unknown: false,
  };
  createAttempt = attempt;
  attempt.running = true;
  attempt.retry = null;
  if (retry !== null) renderHostStatus("Checking the original task outcome…");
  renderTasks();
  try {
    const result = await (retry === null
      ? createTask(() => renderHostStatus("Task response delayed. Checking the original outcome…"))
      : retry());
    taskMutationRevision += 1;
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
      attempt.unknown = !error.checkable;
      renderHostStatus(
        error.checkable
          ? "Task outcome unavailable. Select New task to check the original request."
          : UNKNOWN_OUTCOME_GUIDANCE,
      );
      return;
    }
    createAttempt = null;
    renderHostStatus(
      "A task could not be created. Close an unused task or wait, then try again.",
    );
  } finally {
    if (createAttempt === attempt && attempt.retry === null && !attempt.unknown) createAttempt = null;
    renderTasks();
  }
}

function continuePendingClose(task) {
  if (!task.closePending || !task.closeAwaitingTerminal
      || !task.closeTerminalSeen || task.closeAutoConsumed) return;
  task.closeAutoConsumed = true;
  task.closePending = false;
  if (task.review?.pending === "close") task.review.pending = null;
  void closeRetainedTask(task.taskId);
}

async function closeRetainedTask(taskId) {
  const task = tasks.get(taskId);
  if (task === undefined || taskCloseBlockReason(task) !== null) return;
  if (!task.closeAwaitingTerminal) {
    task.closeTerminalSeen = task.sessionState !== null && task.sessionState !== "active";
    task.closeAutoConsumed = false;
  }
  task.closeAwaitingTerminal = false;
  task.closeManualReady = false;
  task.closePending = true;
  task.closeFailed = false;
  task.closeMessage = null;
  task.error = null;
  if (task.review !== null) task.review.pending = "close";
  renderTasks();
  let remainsPending = false;
  try {
    const result = await (task.closeRetry === null
      ? closeTask(task.taskId, task.sessionId, () => {
        if (tasks.get(taskId) === task) {
          task.closeMessage = "Close response delayed. Checking its original outcome…";
          renderTasks();
        }
      }) : task.closeRetry());
    task.closeRetry = null;
    task.closeOutcomeUnknown = false;
    task.closeFailed = false;
    task.closeMessage = null;
    if (result.disposition === "closed") {
      taskMutationRevision += 1;
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
      task.closeAwaitingTerminal = true;
      if (task.closeTerminalSeen && !task.closeAutoConsumed) {
        continuePendingClose(task);
      } else if (task.closeAutoConsumed) {
        task.closeManualReady = true;
        task.closeFailed = true;
        task.closeMessage = "Close is still pending. Select Retry close to check whether cleanup finished.";
      }
    }
  } catch (error) {
    if (tasks.get(taskId) === task) {
      task.closeRetry = error instanceof TaskCloseUncertainError ? error.retry : null;
      task.closeOutcomeUnknown = error instanceof TaskCloseUncertainError && !error.checkable;
      task.closeFailed = true;
      task.closeMessage = null;
      task.error = task.closeOutcomeUnknown
        ? UNKNOWN_OUTCOME_GUIDANCE
        : task.closeRetry === null
        ? "Close was refused. Retry close."
        : "Close outcome unavailable. Select Retry close to check the original request.";
      if (task.closeRetry === null && !task.closeOutcomeUnknown
          && task.review?.pending === "close") task.review.pending = null;
    }
  } finally {
    if (
      !remainsPending &&
      tasks.get(taskId) === task
    ) {
      task.closePending = false;
      if (task.closeRetry === null && !task.closeOutcomeUnknown
          && task.review?.pending === "close") task.review.pending = null;
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
    outcomeRetry: null,
    outcomeUnknown: false,
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
    outcomeRetry: null,
    outcomeUnknown: false,
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
  try {
    const result = await readSetup();
    if (revision !== defaultSetupRevision) return;
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
  const current = () => revision === recentPairProbeRevision
    && defaultSetup?.recents === recents;
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
    && ["queued", "submitting", "uncertain", "unknown"].includes(row.state)) ?? false;
}

function batchTaskBlockReason(taskId) {
  if (pageBatch?.running?.originTaskId === taskId) {
    return "Wait for this task's active batch submission before closing.";
  }
  const retained = pageBatch?.rows.find((row) => ["submitting", "uncertain", "unknown"].includes(row.state)
    && (row.originTaskId === taskId || row.taskId === taskId));
  return retained === undefined
    ? null
    : "Resolve this task's submitting or uncertain batch pair before closing.";
}

function batchTaskStartMessage(taskId) {
  const row = pageBatch?.rows.find((value) => ["submitting", "uncertain", "unknown"].includes(value.state)
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
  row.outcomeRetry = null;
  row.outcomeUnknown = false;
}

function editMode(mode) {
  const form = currentForm();
  if (!formIsEditable(form) || !["sync-plan", "inventory"].includes(mode) || form.mode === mode) return;
  if (form.source.outcomeRetry !== null || form.target.outcomeRetry !== null
      || form.source.outcomeUnknown || form.target.outcomeUnknown) return;
  form.mode = mode;
  form.revision += 1;
  form.source.revision += 1;
  clearLocationChoice(form.source);
  form.actionMessage = null;
  renderTasks();
}

function acceptTaskRelease(task, sessionId) {
  if (tasks.get(task.taskId) !== task || task.sessionId !== sessionId) return;
  task.recoveryRetry = null;
  task.recoverySessionId = null;
  task.recoveryRunning = false;
  task.releaseOutcomeUnknown = false;
  clearTaskRecoveryError(task);
  task.sessionReleased = true;
  task.executionWindowDirty = true;
  task.executionWindowDirtyRevision += 1;
  renderTasks();
  if (task.taskKind === "sync-plan") void loadPlanReview(task, true);
}

function retireExecutionDetail(review) {
  if (review === null || review === undefined) return;
  review.detailRevision = (review.detailRevision ?? 0) + 1;
  review.executionDetail = null;
}

function adoptExecutionWindow(review, window) {
  if (review.window?.execution?.execution_revision
      !== window.execution.execution_revision) retireExecutionDetail(review);
  review.window = window;
  const focusNodeId = review.summary.highlight_focus_node_id;
  const focusedRow = window.rows.find((row) => row.node_id === focusNodeId) ?? null;
  if (focusNodeId === null || (review.executionDetail !== null
      && review.executionDetail.focusNodeId !== focusNodeId)) {
    retireExecutionDetail(review);
  }
  if (focusedRow?.operation_id != null && window.execution.session_id !== null
      && (review.executionDetail?.operationId !== focusedRow.operation_id
        || review.executionDetail?.executionRevision !== window.execution.execution_revision)) {
    void readExecutionDetail(review, focusedRow);
  }
}

function beginForegroundWindowRead(review) {
  review.foregroundWindowEpoch += 1;
  review.foregroundWindowReaders += 1;
}

function endForegroundWindowRead(review) {
  review.foregroundWindowReaders -= 1;
  const task = retainedReviewTask(review);
  if (
    task !== null && task.executionWindowDirty && review.foregroundWindowReaders === 0
    && !task.reviewLoading
    && selectedTaskId === task.taskId && !settingsVisible
  ) void refreshExecutionWindow(task);
}

function markExecutionWindowDirty(task) {
  task.executionWindowDirty = true;
  task.executionWindowDirtyRevision += 1;
  if (selectedTaskId === task.taskId && !settingsVisible && task.review !== null
      && !task.reviewLoading) {
    void refreshExecutionWindow(task);
  }
}

async function refreshExecutionWindow(task) {
  if (
    tasks.get(task.taskId) !== task || selectedTaskId !== task.taskId || settingsVisible
    || task.review === null || task.reviewLoading || task.executionWindowRefreshRunning
    || task.review.foregroundWindowReaders > 0
  ) return;
  task.executionWindowRefreshRunning = true;
  try {
    while (task.executionWindowDirty) {
      task.executionWindowDirty = false;
      const review = task.review;
      const foregroundWindowEpoch = review.foregroundWindowEpoch;
      const reviewRevision = task.reviewRevision;
      const sessionId = task.sessionId;
      const requestId = review.summary.request_id;
      const action = review.actionRevision;
      const viewRevision = review.summary.view_revision;
      const offset = review.window.offset;
      const refreshStillCurrent = () => (
        tasks.get(task.taskId) === task && selectedTaskId === task.taskId && !settingsVisible
        && task.review === review && !task.reviewLoading && task.reviewRevision === reviewRevision
        && task.sessionId === sessionId && review.foregroundWindowReaders === 0
        && review.foregroundWindowEpoch === foregroundWindowEpoch
        && review.summary.request_id === requestId && review.actionRevision === action
        && review.summary.view_revision === viewRevision && review.window.offset === offset
      );
      try {
        const window = await getPlanWindow(task.taskId, viewRevision, offset, 256);
        if (!refreshStillCurrent()) {
          task.executionWindowDirty = true;
          return;
        }
        if (
          window.disposition !== "current" || window.view_revision !== viewRevision
          || window.highlight_revision !== review.summary.highlight_revision
        ) {
          task.executionWindowDirty = false;
          void loadPlanReview(task, true);
          return;
        }
        adoptExecutionWindow(review, window);
        if (window.execution.result !== null) {
          task.executionResult = window.execution.result;
          task.executionStartedAt = window.execution.started_at ?? null;
          task.executionEndedAt = window.execution.ended_at ?? null;
        }
        renderTasks();
      } catch (_error) {
        if (!refreshStillCurrent()) {
          if (tasks.get(task.taskId) === task) task.executionWindowDirty = true;
          return;
        }
        if (
          tasks.get(task.taskId) === task && selectedTaskId === task.taskId
          && task.review === review && task.sessionId === sessionId
        ) {
          review.message ||= "Execution status refresh delayed.";
          renderTasks();
        }
        return;
      }
    }
  } finally {
    task.executionWindowRefreshRunning = false;
    if (task.executionWindowDirty && selectedTaskId === task.taskId && !settingsVisible) {
      void refreshExecutionWindow(task);
    }
  }
}

async function readExecutionDetail(review, row) {
  if (settingsVisible) return;
  const task = currentReviewTask(review);
  if (task === null) return;
  const request = ++review.detailRevision;
  if (row === null) {
    review.executionDetail = null;
    renderTasks();
    return;
  }
  const operationId = row.operation_id;
  const executionRevision = review.window.execution.execution_revision;
  const sessionId = task.sessionId;
  const requestId = review.summary.request_id;
  const action = review.actionRevision;
  const navigation = navigationRevision;
  const detail = { operationId, executionRevision, focusNodeId: row.node_id ?? null,
    state: "loading", response: null, message: null };
  review.executionDetail = detail;
  renderTasks();
  try {
    const response = await getExecutionDetail(task.taskId, operationId, executionRevision);
    if (
      currentReviewTask(review) !== task || review.detailRevision !== request
      || review.executionDetail !== detail || task.sessionId !== sessionId
      || review.summary.request_id !== requestId || review.actionRevision !== action
      || review.window.execution.execution_revision !== executionRevision
      || navigationRevision !== navigation || settingsVisible
    ) return;
    if (response.disposition === "current") {
      detail.state = "current";
      detail.response = response;
    } else if (response.disposition === "not-retained") {
      detail.state = "not-retained";
    } else {
      retireExecutionDetail(review);
      markExecutionWindowDirty(task);
    }
  } catch (_error) {
    if (currentReviewTask(review) === task && review.detailRevision === request
        && review.executionDetail === detail && navigationRevision === navigation
        && !settingsVisible) {
      detail.state = "error";
      detail.message = "Highlight the item again to retry operation detail.";
    }
  } finally {
    if (currentReviewTask(review) === task && review.detailRevision === request
        && navigationRevision === navigation && !settingsVisible) renderTasks();
  }
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
  const dirtyRevision = task.executionWindowDirtyRevision;
  const sessionId = task.sessionId;
  task.reviewLoading = true;
  renderTasks();
  try {
    const summary = await openPlanView(task.taskId);
    const window = await getPlanWindow(task.taskId, summary.view_revision, 0, 256);
    if (
      tasks.get(task.taskId) !== task || task.reviewRevision !== request
      || task.sessionId !== sessionId
    ) return;
    if (
      window.disposition !== "current" || window.view_revision !== summary.view_revision
      || window.highlight_revision !== summary.highlight_revision
    ) {
      task.executionWindowDirty = task.executionWindowDirtyRevision !== dirtyRevision;
      if (task.review !== null) task.review.message = "Execution status refresh delayed. Select the task to retry.";
      else if (task.sessionState !== "active") task.error = "Plan unavailable. Select the task to retry.";
      return;
    }
    task.executionStarted ||= summary.selection_state === "committed";
    if (window.execution.result !== null) {
      task.executionResult = window.execution.result;
      task.executionStartedAt = window.execution.started_at ?? null;
      task.executionEndedAt = window.execution.ended_at ?? null;
    }
    const message = task.executionStarted
      ? task.sessionState === "active"
        ? executionControlMessage(task.executionControlState)
        : task.sessionState === "completed" ? null : `Execution ${task.sessionState}.`
      : summary.preflight_ready
        ? null
        : "Plan failed review. Inspect notices and create a fresh plan.";
    const controlAttempt = task.executionControlAttempt?.sessionId === sessionId
      ? task.executionControlAttempt : null;
    const retainedOutcomeRetry = task.reviewSessionId === sessionId
      ? task.review?.outcomeRetry ?? null : null;
    const retainedOutcomeUnknown = task.reviewOutcomeUnknown;
    const retainedOutcomeAction = task.reviewSessionId === sessionId
      ? task.review?.outcomeAction ?? null : null;
    const retainedFollow = task.reviewSessionId === sessionId ? task.review?.follow ?? null : null;
    const eligibleFollow = summary.search_query === "" && summary.filters.length === 0
      && summary.sort_column === "path" && summary.sort_direction === "ascending";
    task.review = {
      summary,
      window,
      pending: task.closePending || task.closeRetry !== null || task.closeOutcomeUnknown
        ? "close"
        : retainedOutcomeRetry !== null || retainedOutcomeUnknown ? "outcome"
        : controlAttempt?.pending ? controlAttempt.actionName : null,
      outcomeRetry: retainedOutcomeRetry,
      outcomeUnknown: retainedOutcomeUnknown,
      outcomeAction: retainedOutcomeAction,
      outcomeRunning: false,
      queuedSearchQuery: null,
      highlightQueue: Promise.resolve(),
      message: retainedOutcomeUnknown
        || (task.executionAttempt?.state === "uncertain"
          && task.executionAttempt.retry === null) ? UNKNOWN_OUTCOME_GUIDANCE
        : retainedOutcomeRetry !== null
        ? "Outcome unavailable. Retry outcome to check the original action."
        : task.drainUnavailable && task.sessionState === "active" && task.executionStarted
        ? STOPPED_TASK_UPDATES_MESSAGE
        : controlAttempt?.message ?? message,
      actionRevision: 0,
      windowRequestRevision: 0,
      windowRequestOffset: null,
      windowRequestRunning: false,
      foregroundWindowReaders: 0,
      foregroundWindowEpoch: 0,
      executionDetail: null,
      detailRevision: 0,
      follow: {
        enabled: retainedFollow === null ? task.executionStarted && eligibleFollow : retainedFollow.enabled,
        eligible: eligibleFollow,
        hasTarget: task.progressPresentation?.activeItem?.item_id != null,
        message: null,
        anchorKey: retainedFollow?.anchorKey ?? null,
        anchorIndex: retainedFollow?.anchorIndex ?? null,
        scrollOffset: null,
        generation: retainedFollow?.generation ?? 0,
      },
    };
    task.reviewSessionId = sessionId;
    task.executionWindowDirty = task.executionWindowDirtyRevision !== dirtyRevision;
    task.error = task.drainUnavailable
      ? task.sessionState === "active" && task.executionStarted
        ? STOPPED_TASK_UPDATES_MESSAGE : "Task updates stopped. Close can be retried."
      : null;
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
      if (task.executionWindowDirty) void refreshExecutionWindow(task);
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
  if (review.follow !== null && ["searchQuery", "filters", "sortColumn", "sortDirection"]
      .some((key) => Object.prototype.hasOwnProperty.call(patch, key))) {
    review.follow.enabled = false;
    review.follow.generation += 1;
  }
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
  beginForegroundWindowRead(review);
  renderTasks();
  try {
    const summary = await updatePlanView(
      task.taskId,
      review.summary.view_revision,
      gesture,
      () => {
        if (retainedReviewTask(review) === task && review.actionRevision === action) {
          review.message = "View response delayed. Checking the original outcome…";
          renderTasks();
        }
      },
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
    adoptExecutionWindow(review, window);
    review.message = summary.disposition === "conflict"
      ? "View changed. Current view restored."
      : null;
  } catch (error) {
    if (retainedReviewTask(review) === task && review.actionRevision === action) {
      if (!retainReviewOutcome(review, error)) {
        review.message = "View update was refused. Reload the review before trying again.";
      }
    }
  } finally {
    if (retainedReviewTask(review) === task && review.actionRevision === action) {
      if (review.outcomeRetry === null && !review.outcomeUnknown) review.pending = null;
      renderTasks();
      const queuedSearchQuery = review.queuedSearchQuery;
      review.queuedSearchQuery = null;
      if (review.outcomeRetry === null && !review.outcomeUnknown && queuedSearchQuery !== null
          && queuedSearchQuery !== review.summary.search_query) {
        void changePlanView(review, { searchQuery: queuedSearchQuery }, true);
      }
    }
    endForegroundWindowRead(review);
  }
}

function retainReviewOutcome(review, error, actionName = review.outcomeAction ?? null) {
  if (!(error instanceof OutcomeUnavailableError)) return false;
  const task = retainedReviewTask(review);
  review.outcomeRetry = error.retry;
  review.outcomeUnknown = !error.checkable;
  review.outcomeAction = actionName;
  if (task !== null && review.outcomeUnknown) task.reviewOutcomeUnknown = true;
  review.outcomeRunning = false;
  review.pending = "outcome";
  review.message = error.checkable
    ? "Outcome unavailable. Retry outcome to check the original action."
    : UNKNOWN_OUTCOME_GUIDANCE;
  renderTasks();
  return true;
}

async function retryReviewOutcome(review) {
  const task = retainedReviewTask(review);
  const cancelAttempt = task?.executionControlAttempt;
  if (task !== null && review.outcomeUnknown && review.outcomeRetry === null
      && cancelAttempt?.independent && typeof cancelAttempt.retry === "function") {
    await retryIndependentCancelOutcome(task, cancelAttempt);
    return;
  }
  if (task === null || review.outcomeRunning
      || typeof review.outcomeRetry !== "function") return;
  const retry = review.outcomeRetry;
  review.outcomeRunning = true;
  review.message = "Checking the original action outcome…";
  renderTasks();
  try {
    await retry();
    review.outcomeRetry = null;
    review.outcomeUnknown = false;
    review.outcomeAction = null;
    review.pending = null;
    task.executionControlAttempt = null;
    await loadPlanReview(task, true);
  } catch (error) {
    if (!retainReviewOutcome(review, error)) {
      review.outcomeRetry = null;
      review.outcomeUnknown = false;
      review.outcomeAction = null;
      review.pending = null;
      review.message = "The action was refused. Reloading the current review…";
      task.executionControlAttempt = null;
      await loadPlanReview(task, true);
    }
  } finally {
    review.outcomeRunning = false;
    renderTasks();
  }
}

async function loadPlanWindow(review, offset) {
  const task = currentReviewTask(review);
  if (task === null) return;
  if (offset !== null && review.pending !== null) return;
  review.windowRequestRevision += 1;
  review.windowRequestOffset = offset;
  if (offset === null) {
    review.foregroundWindowEpoch += 1;
    return;
  }
  if (review.windowRequestRunning) {
    review.foregroundWindowEpoch += 1;
    return;
  }

  review.windowRequestRunning = true;
  beginForegroundWindowRead(review);
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
        adoptExecutionWindow(review, window);
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
    endForegroundWindowRead(review);
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
    beginForegroundWindowRead(review);
    const action = review.actionRevision;
    const viewRevision = review.summary.view_revision;
    try {
      const summary = await mutatePlanHighlight(
        task.taskId, viewRevision, review.summary.highlight_revision, gesture, nodeId,
        () => {
          if (retainedReviewTask(review) === task && review.actionRevision === action) {
            review.message = "Highlight response delayed. Checking the original outcome…";
            renderTasks();
          }
        },
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
      adoptExecutionWindow(review, window);
      const focusedRow = window.rows.find((row) => row.node_id === summary.highlight_focus_node_id);
      if (focusedRow?.operation_id === review.executionDetail?.operationId
          && review.executionDetail?.state === "error") {
        void readExecutionDetail(review, focusedRow);
      }
      renderTasks();
    } catch (error) {
      if (retainedReviewTask(review) === task && review.actionRevision === action) {
        if (!retainReviewOutcome(review, error)) {
          review.message = "Highlight was refused. Highlight the item again to retry.";
          renderTasks();
        }
      }
    } finally {
      endForegroundWindowRead(review);
    }
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
  beginForegroundWindowRead(review);
  renderTasks();
  const onDelayed = () => {
    if (retainedReviewTask(review) === task && review.actionRevision === action) {
      review.message = "Selection response delayed. Checking the original outcome…";
      renderTasks();
    }
  };
  try {
    const summary = highlightedScope
      ? await mutatePlanHighlightedSelection(
        task.taskId, review.summary.view_revision,
        review.summary.highlight_revision, review.summary.selection_revision, selected,
        onDelayed,
      )
      : row === null
      ? await mutatePlanScope(
        task.taskId, review.summary.view_revision,
        review.summary.selection_revision, selected, onDelayed,
      )
      : await mutatePlanSelection(
        task.taskId, review.summary.view_revision,
        review.summary.selection_revision, row.node_id, selected, onDelayed,
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
    adoptExecutionWindow(review, window);
    review.message = summary.disposition === "applied"
      ? null
      : summary.disposition === "conflict"
        ? "Selection changed elsewhere. Current selection shown."
        : summary.disposition === "frozen" || summary.disposition === "in-flight"
          ? "Selection is already committed to execution."
          : null;
  } catch (error) {
    if (retainedReviewTask(review) === task && review.actionRevision === action) {
      if (!retainReviewOutcome(review, error)) {
        review.message = "Selection response was refused. Reloading review…";
        review.pending = null;
        void loadPlanReview(task, true);
      }
      return;
    }
  } finally {
    if (
      retainedReviewTask(review) === task && review.actionRevision === action
      && review.pending !== null && review.outcomeRetry === null && !review.outcomeUnknown
    ) {
      review.pending = null;
      renderTasks();
    }
    endForegroundWindowRead(review);
  }
}

async function executeReviewedPlan(review, returnFocus) {
  const task = currentReviewTask(review);
  if (
    task !== null
    && task.executionAttempt?.state === "uncertain"
  ) {
    if (typeof task.executionAttempt.retry === "function") {
      await submitReviewedExecution(task, task.executionAttempt);
    }
    return;
  }
  if (
    task === null || task.closePending || task.closeRetry !== null
    || task.closeOutcomeUnknown || review.pending !== null
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
  if (attempt.state === "uncertain" && typeof attempt.retry !== "function") return;
  if (attempt.submissionStarted) return;
  const submit = attempt.retry ?? (() => startExecution(
    attempt.taskId,
    attempt.requestId,
    attempt.selectionRevision,
    attempt.destructiveAcknowledged,
    () => {
      if (tasks.get(task.taskId) === task && task.executionAttempt === attempt
          && task.review !== null) {
        task.review.message = "Execution response delayed. Checking the original admission…";
        renderTasks();
      }
    },
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
      task.executionResult = null;
      task.executionStartedAt = null;
      task.executionEndedAt = null;
      task.executionWindowDirty = true;
      task.executionWindowDirtyRevision += 1;
      task.executionControlRevision += 1;
      task.executionControlState = "running";
      task.reviewSessionId = result.session_id;
      if (attempt.review.follow !== null) {
        attempt.review.follow.eligible = planFollowEligible(attempt.review);
        attempt.review.follow.enabled = attempt.review.follow.eligible;
        attempt.review.follow.generation += 1;
        attempt.review.follow.anchorKey = null;
        attempt.review.follow.anchorIndex = null;
      }
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
        currentReview.message = error.checkable
          ? "Execution outcome unavailable. Retry outcome to check the original request."
          : UNKNOWN_OUTCOME_GUIDANCE;
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

function recordExecutionControlResult(task, attempt, result) {
  if (result.accepted) attempt.accepted = true;
  if (task.executionControlRevision !== attempt.controlRevision
      && task.executionControlState !== attempt.controlState) return;
  if (result.accepted && ACTIVE_EXECUTION_CONTROL_STATES.has(result.after)) {
    task.executionControlRevision += 1;
    task.executionControlState = result.after;
    attempt.message = executionControlMessage(result.after);
  } else {
    attempt.message = result.detail || `The ${attempt.actionName} request was not accepted.`;
  }
  if (!attempt.independent && task.review !== null) task.review.message = attempt.message;
}

async function retryIndependentCancelOutcome(task, attempt) {
  if (task.executionControlAttempt !== attempt || attempt.pending
      || typeof attempt.retry !== "function" || attempt.unknown
      || task.sessionId !== attempt.sessionId || task.sessionState !== "active") return;
  const retry = attempt.retry;
  attempt.retry = null;
  attempt.pending = true;
  attempt.message = "Checking the original Cancel outcome…";
  renderTasks();
  const stillOwned = () => tasks.get(task.taskId) === task
    && task.sessionId === attempt.sessionId && task.executionControlAttempt === attempt;
  try {
    const result = await retry();
    if (stillOwned() && task.sessionState === "active") {
      recordExecutionControlResult(task, attempt, result);
    }
  } catch (error) {
    if (stillOwned() && task.sessionState === "active") {
      if (error instanceof OutcomeUnavailableError) {
        attempt.retry = error.retry;
        attempt.unknown = !error.checkable;
        attempt.message = error.checkable
          ? "Cancel outcome unavailable. Retry outcome to check the original Cancel request."
          : "Cancel outcome cannot be confirmed. Close and reopen NamiSync before trying another Cancel.";
      } else {
        attempt.message = "Cancel refused. Follow live status.";
      }
    }
  } finally {
    if (stillOwned()) {
      attempt.pending = false;
      renderTasks();
    }
  }
}

async function controlReviewedExecution(review, actionName) {
  const task = currentReviewTask(review);
  const independentCancel = task !== null && actionName === "cancel"
    && canCancelAfterFixedReviewOutcome(task, review);
  if (
    task === null || task.closePending || task.closeRetry !== null
    || task.closeOutcomeUnknown || (review.pending !== null && !independentCancel)
    || !task.executionStarted
    || task.sessionState !== "active" || task.sessionId === null
    || task.reviewSessionId !== task.sessionId
    || task.drainUnavailable || task.executionControlAttempt?.pending
  ) return;
  review.actionRevision += 1;
  const sessionId = task.sessionId;
  const controlRevision = task.executionControlRevision;
  const controlState = task.executionControlState;
  const attempt = {
    sessionId,
    actionName,
    pending: true,
    message: `${actionName[0].toUpperCase()}${actionName.slice(1)} requested…`,
    retry: null,
    unknown: false,
    independent: independentCancel,
    accepted: false,
    controlRevision,
    controlState,
  };
  task.executionControlAttempt = attempt;
  if (actionName === "pause" || actionName === "resume") {
    task.progressPresentation = rebaseProgressSampling(task.progressPresentation);
  }
  if (!independentCancel) {
    review.pending = actionName;
    review.message = attempt.message;
  }
  renderTasks();
  const stillOwned = () => tasks.get(task.taskId) === task
    && task.sessionId === sessionId && task.executionControlAttempt === attempt;
  try {
    const result = await controlExecution(task.taskId, sessionId, actionName, () => {
      if (stillOwned() && task.review !== null) {
        attempt.message = `${actionName[0].toUpperCase()}${actionName.slice(1)} response delayed. Checking its original outcome…`;
        if (!independentCancel) task.review.message = attempt.message;
        renderTasks();
      }
    });
    if (!stillOwned() || task.sessionState !== "active" || task.drainUnavailable) return;
    recordExecutionControlResult(task, attempt, result);
  } catch (error) {
    if (
      stillOwned() && task.sessionState === "active" && !task.drainUnavailable
      && (independentCancel || error instanceof OutcomeUnavailableError || (
        task.executionControlRevision === controlRevision
        || task.executionControlState === controlState
      ))
    ) {
      if (independentCancel && error instanceof OutcomeUnavailableError) {
        attempt.retry = error.retry;
        attempt.unknown = !error.checkable;
        attempt.message = error.checkable
          ? "Cancel outcome unavailable. Retry outcome to check the original Cancel request."
          : "Cancel outcome cannot be confirmed. Close and reopen NamiSync before trying another Cancel.";
      } else if (!independentCancel && task.review !== null
          && retainReviewOutcome(task.review, error, actionName)) {
        attempt.message = task.review.message;
      } else {
        attempt.message = `${actionName[0].toUpperCase()}${actionName.slice(1)} refused. Follow live status.`;
      }
      if (!independentCancel && task.review !== null) task.review.message = attempt.message;
    }
  } finally {
    if (stillOwned()) {
      if (independentCancel) {
        attempt.pending = false;
      } else if (task.review?.outcomeRetry === null) {
        attempt.pending = false;
        if (task.review?.pending === actionName) task.review.pending = null;
      }
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
  if (row.outcomeRetry !== null || row.outcomeUnknown) return;
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

function retainLocationOutcome(task, form, row, error, accept) {
  if (!(error instanceof OutcomeUnavailableError)) return false;
  if (!error.checkable) {
    row.outcomeRetry = null;
    row.outcomeUnknown = true;
    form.actionMessage = UNKNOWN_OUTCOME_GUIDANCE;
    renderTasks();
    return true;
  }
  const revision = row.revision;
  row.outcomeRetry = async () => {
    if (tasks.get(task.taskId) !== task || task.form !== form
        || row.revision !== revision) return;
    form.actionMessage = "Checking the original folder outcome…";
    renderTasks();
    try {
      const result = await error.retry();
      if (tasks.get(task.taskId) !== task || task.form !== form
          || row.revision !== revision) return;
      row.outcomeRetry = null;
      row.outcomeUnknown = false;
      accept(result);
      form.actionMessage = null;
      renderTasks();
    } catch (failure) {
      if (tasks.get(task.taskId) !== task || task.form !== form
          || row.revision !== revision) return;
      if (!retainLocationOutcome(task, form, row, failure, accept)) {
        row.outcomeRetry = null;
        form.actionMessage = "Folder choice was refused. Check the path and try again.";
        renderTasks();
      }
    }
  };
  form.actionMessage = "Folder outcome unavailable. Retry outcome to check the original choice.";
  renderTasks();
  return true;
}

async function retryLocationOutcomes() {
  const task = currentTask();
  const form = task?.form;
  if (task === null || form === null) return;
  for (const row of [form.source, form.target]) {
    if (typeof row.outcomeRetry === "function") await row.outcomeRetry();
  }
}

function resolvedChoice(row, purpose) {
  return row.location?.purpose === purpose && typeof row.location.choice_id === "string"
    ? row.location
    : null;
}

async function admitRow(task, form, rowName, purpose = rowName) {
  const row = form[rowName];
  if (!row.text || row.candidate === null || row.outcomeRetry !== null
      || row.outcomeUnknown) return null;
  const revision = row.revision;
  const admissionRevision = ++row.admissionRevision;
  let result;
  try {
    result = await admitLocation(purpose, row.candidate, () => {
      if (tasks.get(task.taskId) === task && task.form === form
          && row.revision === revision) {
        form.actionMessage = "Folder response delayed. Checking its original outcome…";
        renderTasks();
      }
    });
  } catch (error) {
    if (tasks.get(task.taskId) === task && task.form === form
        && row.revision === revision && row.admissionRevision === admissionRevision) {
      retainLocationOutcome(task, form, row, error, (value) => acceptLocation(row, value));
    }
    throw error;
  }
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
  if (row.outcomeRetry !== null || row.outcomeUnknown) return;
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
  } catch (error) {
    if (!retainLocationOutcome(task, form, row, error, (result) => {
      if (result === null) restore();
      else {
        acceptLocation(row, result);
        row.text = result.display ?? "";
      }
    })) restore();
  }
}

async function chooseRecentLocation(purpose, recent) {
  const task = currentTask();
  const form = task?.form;
  if (task === null || !formIsEditable(form)) return;
  const row = form[purpose];
  if (row.outcomeRetry !== null || row.outcomeUnknown) return;
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
  if (form.source.outcomeRetry !== null || form.target.outcomeRetry !== null
      || form.source.outcomeUnknown || form.target.outcomeUnknown) return;
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
  if (row.outcomeRetry !== null || row.outcomeUnknown) return;
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
    const result = await admitLocation(purpose, selection, () => {
      if (tasks.get(task.taskId) === task && task.form === form
          && row.revision === revision) {
        form.actionMessage = "Folder choice response delayed. Checking its original outcome…";
        renderTasks();
      }
    });
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
  } catch (error) {
    if (
      tasks.get(task.taskId) === task &&
      task.form === form &&
      row.revision === revision &&
      row.admissionRevision === admissionRevision
    ) {
      if (!retainLocationOutcome(task, form, row, error, (result) => acceptLocation(row, result))) {
        clearLocationChoice(row);
        renderTasks();
      }
    }
  }
}

function beginFormAttempt(task, form, kind) {
  if (
    tasks.get(task.taskId) !== task || task.form !== form || form.attempt !== null ||
    task.closeOutcomeUnknown || task.startOutcomeUnknown ||
    (pageBatch !== null && pageBatch.running !== null)
  ) return null;
  const attempt = {
    kind,
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
    && form.revision === revision;
}

async function dispatchFormAttempt(task, form, attempt, submit) {
  attempt.dispatched = true;
  renderTasks();
  try {
    await submit();
  } catch (error) {
    if (!currentFormAttempt(task, form, attempt)) return;
    if (error instanceof StartPlanUncertainError) {
      attempt.running = false;
      attempt.retry = error.retry;
      attempt.unknown = !error.checkable;
      if (attempt.unknown) task.startOutcomeUnknown = true;
      form.actionMessage = error.checkable
        ? "Outcome unavailable. Retry outcome to check the original request."
        : UNKNOWN_OUTCOME_GUIDANCE;
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
  await refreshTasks();
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
  form.actionMessage = "Checking the original start outcome…";
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
  form.actionMessage = form.source.outcomeUnknown || form.target.outcomeUnknown
    ? UNKNOWN_OUTCOME_GUIDANCE
    : form.source.outcomeRetry !== null || form.target.outcomeRetry !== null
    ? "Folder outcome unavailable. Retry outcome to check the original choice."
    : "That task could not be started. Review the setup and try again.";
  renderTasks();
  void loadTaskSetup(task);
}

async function startCurrentPlan() {
  const task = currentTask();
  const form = task?.form;
  if (
    task === null || task.closePending || task.closeRetry !== null || task.closeOutcomeUnknown
    || task.startOutcomeUnknown || form === null || !form.editable || form.mode !== "sync-plan" ||
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
      () => startPlan(task.taskId, ready.sourceId, ready.targetId, ready.options, () => {
        if (currentFormAttempt(task, form, attempt)) {
          form.actionMessage = "Plan response delayed. Checking its original outcome…";
          renderTasks();
        }
      }),
    );
  } catch (_error) {
    refuseFreshAttempt(task, form, attempt);
  }
}

async function startCurrentInventory() {
  const task = currentTask();
  const form = task?.form;
  if (
    task === null || task.closePending || task.closeRetry !== null || task.closeOutcomeUnknown
    || task.startOutcomeUnknown || form === null || !form.editable || form.mode !== "inventory" ||
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
    await dispatchFormAttempt(task, form, attempt, () => startInventory(
      task.taskId, root.choice_id, () => {
        if (currentFormAttempt(task, form, attempt)) {
          form.actionMessage = "Inventory response delayed. Checking its original outcome…";
          renderTasks();
        }
      },
    ));
  } catch (_error) {
    refuseFreshAttempt(task, form, attempt);
  }
}

function addCurrentPair() {
  const task = currentTask();
  const form = currentForm();
  if (
    task === null || task.closePending || task.closeRetry !== null || task.closeOutcomeUnknown
    || task.startOutcomeUnknown || !formIsEditable(form) || form.mode !== "sync-plan" ||
    form.source.outcomeRetry !== null || form.target.outcomeRetry !== null
    || form.source.outcomeUnknown || form.target.outcomeUnknown ||
    (pageBatch !== null && pageBatch.running !== null)
  ) return;
  if (pageBatch?.rows.some((row) => row.originTaskId === task.taskId
      && row.state === "unknown")) return;
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
  row.state = error.checkable ? "uncertain" : "unknown";
  row.stage = stage;
  row.retry = error.retry;
  row.message = !error.checkable ? UNKNOWN_OUTCOME_GUIDANCE : stage.startsWith("admitting-")
    ? "Folder outcome unavailable. Retry outcome for this batch row."
    : stage === "creating" ? "Task outcome unavailable. Retry outcome for this batch row."
      : "Plan outcome unavailable. Retry outcome for this batch row.";
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
      row.message = stage.startsWith("admitting-") ? "Checking folder outcome…"
        : stage === "creating" ? "Checking task outcome…" : "Checking plan outcome…";
      renderTasks();
      const result = await retry();
      if (stage === "admitting-source" || stage === "admitting-target") {
        const purpose = stage === "admitting-source" ? "source" : "target";
        acceptLocation(row[purpose], result);
        row.state = "queued";
        row.retry = null;
        return startBatchRow(row, context);
      }
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
      row.stage = "admitting-source";
      const source = await admitBatchRow(row.source, "source", row);
      row.stage = "admitting-target";
      const target = await admitBatchRow(row.target, "target", row);
      if (typeof source?.choice_id !== "string" || typeof target?.choice_id !== "string") {
        throw new BridgeTransportError();
      }
      row.sourceId = source.choice_id;
      row.targetId = target.choice_id;
      row.snapshot = context.snapshot;
      row.recents = context.recents;
      if (!context.canSubmit()) {
        row.state = "stopped";
        row.message = "Not submitted because the batch changed.";
        return;
      }
      row.stage = "creating";
      row.message = "Creating task…";
      renderTasks();
      const shell = await createTask(() => {
        if (row.state === "submitting") {
          row.message = "Task response delayed. Checking its original outcome…";
          renderTasks();
        }
      });
      task = adoptBatchShell(shell, row);
    }
    if (!context.canSubmit()) {
      row.state = "stopped";
      row.message = "The blank task was retained; its plan was not submitted because the batch changed.";
      void refreshTasks();
      return;
    }
    row.stage = "starting";
    row.message = "Creating plan…";
    renderTasks();
    await startPlan(task.taskId, row.sourceId, row.targetId, row.options, () => {
      if (row.state === "submitting") {
        row.message = "Plan response delayed. Checking its original outcome…";
        renderTasks();
      }
    });
    row.state = "created";
    row.message = "Plan task created.";
  } catch (error) {
    if (error instanceof OutcomeUnavailableError
        && ["admitting-source", "admitting-target"].includes(row.stage)) {
      batchRowUncertain(row, row.stage, error);
    } else if (error instanceof TaskCreateUncertainError) {
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
    task === null || task.closePending || task.closeRetry !== null || task.closeOutcomeUnknown
    || task.startOutcomeUnknown || !formIsEditable(form) || form.mode !== "sync-plan" || form.attempt !== null
    || form.source.outcomeRetry !== null || form.target.outcomeRetry !== null
    || form.source.outcomeUnknown || form.target.outcomeUnknown ||
    batch === null || batch.running !== null
  ) return;
  if (batch.rows.some((row) => row.originTaskId === task.taskId
      && row.state === "unknown")) return;
  const rows = batch.rows.filter((row) => row.originTaskId === task.taskId
    && ["queued", "uncertain"].includes(row.state));
  if (rows.length === 0) return;
  const queued = rows.filter((row) => row.state === "queued");
  if (queued.some((row) => row.options === null)) return;
  const owner = { originTaskId: task.taskId };
  const generation = batch.generation;
  const context = {
    snapshot: form.setup,
    recents: defaultSetup?.recents ?? form.setup.recents,
    contains: (row) => batch.rows.includes(row),
    canSubmit: () => currentBatchRun(batch, owner, generation)
      && tasks.get(task.taskId) === task && !task.closePending && task.closeRetry === null
      && !task.closeOutcomeUnknown && !task.startOutcomeUnknown,
  };
  batch.running = owner;
  renderTasks();
  try {
    for (const row of rows) {
      if (!currentBatchRun(batch, owner, generation)) break;
      if (!batch.rows.includes(row)) continue;
      if (!["queued", "uncertain"].includes(row.state)) continue;
      await startBatchRow(row, context);
      renderTasks();
    }
  } finally {
    if (batch.running === owner) batch.running = null;
    renderTasks();
  }
  await refreshTasks();
}

async function admitBatchRow(row, purpose, batchRow) {
  const accepted = resolvedChoice(row, purpose);
  if (accepted !== null) return accepted;
  if (!row.text || row.candidate === null) return null;
  const revision = row.revision;
  const result = await admitLocation(purpose, row.candidate, () => {
    if (batchRow.state === "submitting") {
      batchRow.message = "Folder response delayed. Checking its original outcome…";
      renderTasks();
    }
  });
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
    task === null || currentTask() !== task || task.closePending || task.closeRetry !== null
    || task.closeOutcomeUnknown || task.startOutcomeUnknown ||
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
    () => planAgain(task.taskId, sourceMount, targetMount, () => {
      if (currentFormAttempt(task, form, attempt)) {
        form.actionMessage = "Plan-again response delayed. Checking its original outcome…";
        renderTasks();
      }
    }),
  );
  return true;
}

async function finishStartup() {
  const readinessBaseline = readiness.revision();
  await whenBridgeApiReady();
  try {
    await acknowledgeShellReady();
  } catch (error) {
    if (!(error instanceof BridgeTransportError)) {
      throw error;
    }
  }
  const challenge = await readiness.whenReceivedAfter(readinessBaseline);
  let acknowledged = false;
  for (let attempt = 0; attempt < 2 && !acknowledged; attempt += 1) {
    try {
      const result = await echoReadiness(challenge);
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
  await refreshTasks();
  void loadDefaultSetup();
  void theme.open(appliedPresentationRevision);
  if (status.textContent === "Starting...") {
    renderHostStatus("Ready");
  }
}

void finishStartup().catch(() => {
  // Native startup refusal owns the action-guiding terminal diagnostic.
});
