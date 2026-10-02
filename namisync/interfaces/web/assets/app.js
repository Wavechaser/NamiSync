import {
  acknowledgeShellReady,
  acknowledgeInventory,
  admitLocation,
  BridgeTransportError,
  closeTask,
  controlExecution,
  createTask,
  echoReadiness,
  getExecutionDetail,
  getInventoryDetail,
  getInventoryWindow,
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
  openInventoryView,
  pickFolder,
  planAgain,
  prepareSetup,
  probeRecentPairs,
  readSetup,
  refreshInventory,
  restoreInventory,
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
  updateInventoryView,
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
const themeOutcomeStatus = document.querySelector("#theme-outcome-status");
const themeRefresh = document.querySelector("#theme-refresh");
const settingsView = document.querySelector("#settings-view");
const themeOptions = document.querySelector("#theme-options");
const UNKNOWN_OUTCOME_GUIDANCE = "Original outcome cannot be confirmed. Close and reopen NamiSync to review current state.";
if (
  !(app instanceof HTMLElement)
  || !(status instanceof HTMLElement)
  || !(themeSelector instanceof HTMLElement)
  || !(themeOutcomeStatus instanceof HTMLElement)
  || !(themeRefresh instanceof HTMLElement)
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
  onOutcomeStatus(message, refreshAvailable) {
    renderText(themeOutcomeStatus, message ?? "");
    themeOutcomeStatus.hidden = message === null;
    themeRefresh.hidden = !refreshAvailable;
  },
});
themeRefresh.addEventListener("click", () => { void theme.refresh(); });
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
let pickerPending = false;
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
}, settingsView, {
  onViewChange: (review, patch) => { void changeInventoryView(review, patch); },
  onWindow: loadInventoryWindow,
  onDetail: (review, nodeId) => { void readInventoryDetail(review, nodeId); },
  onReload: (task) => { void loadInventoryReview(task, true); },
  onRefresh: (review, nodeId) => { void runInventoryAction(review, "refresh", nodeId); },
  onVisibility: (review, action, nodeId) => { void runInventoryAction(review, action, nodeId); },
  onCheckOutcome: (task) => { void checkInventoryOutcome(task); },
});
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

function fixedOutcome(recovery) {
  return recovery?.state === "fixed-unknown";
}

function checkableOutcome(recovery) {
  return recovery?.canCheck === true;
}

function canCancelAfterFixedReviewOutcome(task, review) {
  const attempt = task.executionControlAttempt;
  return review !== null && review.pending === "outcome"
    && fixedOutcome(review.recovery)
    && review.outcomeAction !== "cancel"
    && task.executionStarted && task.sessionState === "active"
    && task.sessionId !== null && task.reviewSessionId === task.sessionId
    && !task.drainUnavailable && !task.closePending && !checkableOutcome(task.closeRecovery)
    && !fixedOutcome(task.closeRecovery) && !fixedOutcome(task.startRecovery)
    && !fixedOutcome(task.releaseRecovery) && task.executionAttempt === null
    && task.executionControlState !== "canceling"
    && (attempt === null || (!attempt.pending && !checkableOutcome(attempt.recovery)
      && !(attempt.independent && (fixedOutcome(attempt.recovery) || attempt.accepted))));
}

function taskCloseBlockReason(task) {
  if (task.closePending && !task.closeManualReady) {
    return task.closeRecovery?.message ?? task.closeMessage ?? "Wait for this Close request to finish.";
  }
  if (fixedOutcome(task.closeRecovery) || fixedOutcome(task.startRecovery)
      || fixedOutcome(task.releaseRecovery)
      || task.executionAttempt?.state === "uncertain") return UNKNOWN_OUTCOME_GUIDANCE;
  if (task.executionAttempt !== null) return "Resolve the in-flight execution request before closing.";
  if (task.inventoryAction?.pending) return fixedOutcome(task.inventoryAction.recovery)
    ? UNKNOWN_OUTCOME_GUIDANCE
    : checkableOutcome(task.inventoryAction.recovery)
      ? "Check the original inventory outcome before closing this task."
      : "Wait for the current inventory action before closing this task.";
  if (task.executionControlAttempt?.independent) {
    if (fixedOutcome(task.executionControlAttempt.recovery)) return UNKNOWN_OUTCOME_GUIDANCE;
    if (task.executionControlAttempt.pending) return checkableOutcome(task.executionControlAttempt.recovery)
      ? "Check the original Cancel outcome before closing this task."
      : "Wait for the current Cancel request before closing this task.";
  }
  if (!checkableOutcome(task.closeRecovery) && !task.closeManualReady
      && task.review !== null && task.review.pending !== null
      && task.review.pending !== "view"
      && !(fixedOutcome(task.review.recovery) && task.sessionId !== null
        && task.reviewSessionId === task.sessionId)) {
    return checkableOutcome(task.review.recovery)
      || checkableOutcome(task.executionControlAttempt?.recovery)
      ? "Check the original review outcome before closing this task."
      : "Wait for the current review action before closing this task.";
  }
  return batchTaskBlockReason(task.taskId);
}

function renderTasks() {
  for (const task of tasks.values()) {
    if (task.form !== null) {
      task.form.startRecovery = task.startRecovery;
      task.form.recentPairAvailability = recentPairAvailability;
      task.form.batchRunning = pageBatch !== null && pageBatch.running !== null;
      const syncBatchOwner = task.form.editable && task.form.mode === "sync-plan";
      const batchBlockReason = batchTaskBlockReason(task.taskId);
      task.form.batch = syncBatchOwner && pageBatch !== null
        ? pageBatch.rows.filter((row) => row.originTaskId === task.taskId)
        : [];
      task.form.batchCount = syncBatchOwner ? pageBatch?.rows.length ?? 0 : 0;
      task.form.batchPending = syncBatchOwner && (pageBatch?.rows.some((row) => row.originTaskId === task.taskId
        && ["queued", "submitting", "unknown"].includes(row.state)) ?? false);
      task.form.batchPending ||= batchBlockReason !== null;
      task.form.batchMessage = syncBatchOwner ? batchTaskStartMessage(task.taskId)
        : batchBlockReason === null ? null
          : batchTaskStartMessage(task.taskId)
            ?? "Return to Sync to resolve its in-flight batch request before starting Inventory.";
      task.form.closePending = task.closePending || checkableOutcome(task.closeRecovery)
        || fixedOutcome(task.closeRecovery) || fixedOutcome(task.startRecovery);
    }
    task.canCancelAfterFixedReviewOutcome = canCancelAfterFixedReviewOutcome(task, task.review);
    task.closeBlockReason = taskCloseBlockReason(task);
    task.canPlanAgain = canStartPlanAgain(task);
  }
  rail.render(
    taskArray(),
    selectedTaskId,
    createAttempt,
    settingsVisible,
  );
  if (settingsVisible) panel.renderSettings();
  else panel.render(selectedTaskId === null ? null : tasks.get(selectedTaskId) ?? null);
}

function showSettings() {
  if (settingsVisible) return;
  const task = currentTask();
  if (task?.review != null) retireExecutionDetail(task.review);
  if (task?.inventoryReview != null) retireInventoryDetail(task.inventoryReview);
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
  if (previous?.inventoryReview != null) retireInventoryDetail(previous.inventoryReview);
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
  if (task.taskKind === "inventory" && task.sessionReleased) void loadInventoryReview(task, true);
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
      closeRecovery: null,
      closeAwaitingTerminal: false,
      closeTerminalSeen: false,
      closeAutoConsumed: false,
      closeManualReady: false,
      startRecovery: null,
      releaseRecovery: null,
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
      inventoryReview: null,
      inventoryLoading: false,
      inventoryRevision: 0,
      inventoryError: null,
      inventoryAction: null,
      inventoryViewUnconfirmed: false,
      executionStarted: false,
      executionAttempt: null,
      executionControlState: "running",
      executionControlRevision: 0,
      executionControlAttempt: null,
      executionWindowDirty: false,
      executionWindowDirtyRevision: 0,
      executionWindowRefreshRunning: false,
      progressPresentation: null,
      snapshot: null,
    };
    nextTaskNumber += 1;
    tasks.set(task.taskId, task);
  } else {
    if (task.sessionId !== summary.session_id) {
      task.stopDrain?.();
      task.stopDrain = null;
      if (task.inventoryReview !== null) retireInventoryDetail(task.inventoryReview);
      task.inventoryRevision += 1;
      task.inventoryLoading = false;
      task.recoveryRetry = null;
      task.recoverySessionId = null;
      task.recoveryRunning = false;
      task.releaseRecovery = null;
      task.closeFailed = false;
      task.snapshot = null;
      task.progressPresentation = null;
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
      && summary.task_kind === "sync-plan"
      && task.requestId === summary.request_id
      && task.review !== null
    ) {
      task.executionStarted = true;
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
  if (task.taskKind === "inventory" && task.sessionReleased) void loadInventoryReview(task);
  return task;
}

function adoptTaskStart(result, taskKind) {
  taskMutationRevision += 1;
  const observed = tasks.get(result.task_id);
  if (observed?.sessionId === result.session_id) return observed;
  return adoptTask({
    task_id: result.task_id,
    request_id: result.request_id,
    session_id: result.session_id,
    session_state: "active",
    session_released: false,
    task_kind: taskKind,
  });
}

function attachTaskDrain(task) {
  const sessionId = task.sessionId;
  task.stopDrain = startTaskDrain(
    task.taskId,
    sessionId,
    (update, snapshot) => acceptTaskUpdate(task, sessionId, update, snapshot),
    (error, retry) => acceptTaskRefusal(task, sessionId, error, retry),
    {
      terminal: task.sessionState !== "active",
      sessionReleased: task.sessionReleased,
    },
    (_taskId, sessionId) => acceptTaskRelease(task, sessionId),
    (_taskId, sessionId) => acceptTaskRecovery(task, sessionId),
    (_taskId, sessionId, feedback) => acceptTaskReleaseDelay(task, sessionId, feedback),
  );
  task.drainUnavailable = false;
}

function acceptTaskUpdate(task, sessionId, update, snapshot = null) {
  if (tasks.get(task.taskId) !== task || task.sessionId !== sessionId) {
    return;
  }
  if (snapshot !== null) {
    task.snapshot = snapshot;
    task.progressPresentation = {
      phase: snapshot.phase,
      activeItem: snapshot.active_item,
      itemPercent: snapshot.presentation.item_percent,
    };
    if (task.executionControlState !== snapshot.control_state) {
      task.executionControlRevision += 1;
      task.executionControlState = snapshot.control_state;
      if (task.executionControlAttempt?.sessionId === sessionId) {
        if (task.executionControlAttempt.pending) {
          task.executionControlAttempt.message = executionControlMessage(snapshot.control_state);
        } else if (!checkableOutcome(task.executionControlAttempt.recovery)
            && !fixedOutcome(task.executionControlAttempt.recovery)
            && !(task.executionControlAttempt.independent
              && task.executionControlAttempt.accepted)) {
          task.executionControlAttempt = null;
        }
      }
      if (task.executionStarted && task.review !== null && !fixedOutcome(task.review.recovery)) {
        task.review.message = executionControlMessage(snapshot.control_state);
      }
    }
    if (task.review?.follow != null) {
      task.review.follow.hasTarget = task.progressPresentation?.activeItem?.item_id != null;
    }
  }
  if (task.executionStarted) markExecutionWindowDirty(task);
  if (update?.update_type === "record") {
    task.recoveryRetry = null;
    task.recoverySessionId = null;
    task.recoveryRunning = false;
    task.drainUnavailable = false;
    clearTaskRecoveryError(task);
    taskMutationRevision += 1;
    const controlAttempt = task.executionControlAttempt;
    task.executionControlAttempt = null;
    if (task.review !== null && controlAttempt !== null
        && task.review.pending === controlAttempt.actionName) task.review.pending = null;
    task.sessionState = snapshot.session_state;
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
  if (error instanceof TerminalSessionReleaseError && error.checkable) {
    task.releaseRecovery = null;
  }
  task.recoveryRetry = retry ?? (typeof error?.retry === "function" ? error.retry : null);
  task.recoverySessionId = sessionId;
  task.recoveryRunning = false;
  if (error instanceof TerminalSessionReleaseError && !error.checkable) {
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
  if (!checkableOutcome(task.releaseRecovery)) clearTaskRecoveryError(task);
  if (task.review?.message === STOPPED_TASK_UPDATES_MESSAGE) {
    task.review.message = task.executionControlAttempt?.sessionId === sessionId
      ? task.executionControlAttempt.message : executionControlMessage(task.executionControlState);
  }
  renderTasks();
}

function retryTaskUpdates(taskId) {
  const task = tasks.get(taskId);
  if (task !== undefined && checkableOutcome(task.releaseRecovery)
      && !task.releaseRecovery.checking) {
    void task.releaseRecovery.check();
    return;
  }
  if (
    task === undefined || task.recoveryRunning || checkableOutcome(task.closeRecovery) ||
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
  if (selectedTaskId !== null) void loadInventoryReview(tasks.get(selectedTaskId));
}

async function createBlankTask() {
  if (createAttempt?.running) {
    if (checkableOutcome(createAttempt.recovery)) await createAttempt.recovery.check();
    return;
  }
  if (fixedOutcome(createAttempt?.recovery)) return;
  const selectionBaseline = navigationRevision;
  const attempt = {
    running: true,
    recovery: null,
  };
  createAttempt = attempt;
  renderTasks();
  try {
    const result = await createTask((recovery) => {
      if (createAttempt === attempt) {
        attempt.recovery = recovery;
        if (recovery.message !== null) renderHostStatus(recovery.message);
        renderTasks();
      }
    });
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
      renderHostStatus(attempt.recovery?.message ?? UNKNOWN_OUTCOME_GUIDANCE);
      return;
    }
    createAttempt = null;
    renderHostStatus(
      "A task could not be created. Close an unused task or wait, then try again.",
    );
  } finally {
    if (createAttempt === attempt && !fixedOutcome(attempt.recovery)) createAttempt = null;
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
  if (task?.closePending && checkableOutcome(task.closeRecovery)) {
    await task.closeRecovery.check();
    return;
  }
  if (task === undefined || taskCloseBlockReason(task) !== null) return;
  const pendingFolderRow = pageBatch?.running?.originTaskId === taskId
    && pageBatch.running.row?.stage?.startsWith("admitting-")
    ? pageBatch.running.row : null;
  if (pendingFolderRow !== null) {
    pageBatch.rows = pageBatch.rows.filter((row) => row !== pendingFolderRow);
    pageBatch.generation += 1;
    pendingFolderRow.abandonAdmission?.();
  }
  if (!task.closeAwaitingTerminal) {
    task.closeTerminalSeen = task.sessionState !== null && task.sessionState !== "active";
    task.closeAutoConsumed = false;
  }
  task.closeAwaitingTerminal = false;
  task.closeManualReady = false;
  task.closePending = true;
  task.closeRecovery = null;
  task.closeFailed = false;
  task.closeMessage = null;
  task.error = null;
  task.inventoryRevision += 1;
  task.inventoryLoading = false;
  if (task.inventoryReview !== null) {
    task.inventoryReview.actionRevision += 1;
    task.inventoryReview.pending = "close";
    retireInventoryDetail(task.inventoryReview);
  }
  if (task.review !== null) {
    task.review.actionRevision += 1;
    task.review.pending = "close";
  }
  renderTasks();
  let remainsPending = false;
  try {
    const result = await closeTask(task.taskId, task.sessionId, (recovery) => {
        if (tasks.get(taskId) === task) {
          task.closeRecovery = recovery;
          renderTasks();
        }
      });
    task.closeRecovery = null;
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
      if (!(error instanceof TaskCloseUncertainError)) task.closeRecovery = null;
      task.closeFailed = true;
      task.closeMessage = null;
      task.error = error instanceof TaskCloseUncertainError
        ? null : "Close was refused. Retry close.";
      if (!checkableOutcome(task.closeRecovery) && !fixedOutcome(task.closeRecovery)
          && task.review?.pending === "close") task.review.pending = null;
      if (!checkableOutcome(task.closeRecovery) && !fixedOutcome(task.closeRecovery)
          && task.inventoryReview?.pending === "close") task.inventoryReview.pending = null;
    }
  } finally {
    if (
      !remainsPending &&
      tasks.get(taskId) === task
    ) {
      task.closePending = false;
      if (!checkableOutcome(task.closeRecovery) && !fixedOutcome(task.closeRecovery)
          && task.review?.pending === "close") task.review.pending = null;
      if (!checkableOutcome(task.closeRecovery) && !fixedOutcome(task.closeRecovery)
          && task.inventoryReview?.pending === "close") task.inventoryReview.pending = null;
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
    pending: false,
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
    pending: false,
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
    && ["queued", "submitting", "unknown"].includes(row.state)) ?? false;
}

function batchTaskBlockReason(taskId) {
  const pendingFolderRow = pageBatch?.running?.originTaskId === taskId
    && pageBatch.running.row?.stage?.startsWith("admitting-")
    ? pageBatch.running.row : null;
  if (pageBatch?.running?.originTaskId === taskId && pendingFolderRow === null) {
    return "Wait for this task's active batch submission before closing.";
  }
  const retained = pageBatch?.rows.find((row) => ["submitting", "unknown"].includes(row.state)
    && row !== pendingFolderRow && (row.originTaskId === taskId || row.taskId === taskId));
  return retained === undefined
    ? null
    : "Resolve this task's submitting or unknown batch pair before closing.";
}

function batchTaskStartMessage(taskId) {
  const row = pageBatch?.rows.find((value) => ["submitting", "unknown"].includes(value.state)
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
  row.pending = false;
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
  task.releaseRecovery = null;
  task.recoveryRetry = null;
  task.recoverySessionId = null;
  task.recoveryRunning = false;
  clearTaskRecoveryError(task);
  task.sessionReleased = true;
  task.executionWindowDirty = true;
  task.executionWindowDirtyRevision += 1;
  renderTasks();
  if (task.taskKind === "sync-plan") void loadPlanReview(task, true);
  if (task.taskKind === "inventory") void loadInventoryReview(task, true);
}

function acceptTaskReleaseDelay(task, sessionId, recovery) {
  if (tasks.get(task.taskId) !== task || task.sessionId !== sessionId) return;
  task.releaseRecovery = recovery;
  task.recoverySessionId = sessionId;
  renderTasks();
}

function retireExecutionDetail(review) {
  if (review === null || review === undefined) return;
  review.detailRevision = (review.detailRevision ?? 0) + 1;
  review.executionDetail = null;
}

function retireInventoryDetail(review) {
  review.detailRevision += 1;
  review.detail = null;
}

function inventoryCommandId() {
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
}

function inventoryResultMessage(result) {
  const label = result.action === "acknowledge" ? "Acknowledge missing" : "Restore visibility";
  return `${label}: ${result.applied} applied, ${result.noop} already set, `
    + `${result.stale} stale, ${result.conflict} conflicted, `
    + `${result.unresolved_count} unresolved of ${result.total} missing items.`;
}

async function checkInventoryOutcome(task) {
  const attempt = task.inventoryAction;
  if (tasks.get(task.taskId) !== task || !attempt?.pending
      || !checkableOutcome(attempt.recovery) || attempt.recovery.checking) return;
  attempt.message = "Checking the original inventory outcome…";
  renderTasks();
  try {
    await attempt.recovery.check();
  } catch (_error) {
    if (task.inventoryAction === attempt) attempt.message = attempt.recovery.message;
  } finally {
    if (task.inventoryAction === attempt) renderTasks();
  }
}

async function runInventoryAction(review, kind, nodeId) {
  const task = currentInventoryTask(review);
  if (task === null || task.inventoryLoading || task.inventoryAction?.pending
      || (kind !== "refresh" && task.inventoryViewUnconfirmed) || review.pending !== null
      || !task.sessionReleased || task.sessionState === "active"
      || checkableOutcome(task.closeRecovery) || fixedOutcome(task.closeRecovery)) return;
  if (nodeId !== null && (review.detail?.row?.node_id !== nodeId
      || review.detail.row.warning !== null)) return;
  if (kind !== "refresh" && review.summary.request_id !== task.requestId) return;
  const requestId = task.requestId;
  const revision = review.summary.view_revision;
  const attempt = {
    kind, requestId, revision, nodeId, commandId: inventoryCommandId(),
    pending: true, recovery: null,
    message: kind === "refresh" ? "Starting inventory scan…" : "Updating missing-item visibility…",
  };
  task.inventoryAction = attempt;
  review.windowRequestRevision += 1;
  retireInventoryDetail(review);
  renderTasks();
  const stillOwned = () => tasks.get(task.taskId) === task && task.inventoryAction === attempt;
  const onDelayed = (recovery) => {
    if (!stillOwned()) return;
    if (typeof recovery?.check === "function") attempt.recovery = recovery;
    attempt.message = attempt.recovery?.message ?? "Waiting for the original inventory outcome…";
    renderTasks();
  };
  try {
    const result = kind === "refresh"
      ? await refreshInventory(task.taskId, requestId, attempt.commandId, revision, nodeId, onDelayed)
      : await (kind === "acknowledge" ? acknowledgeInventory : restoreInventory)(
        task.taskId, requestId, attempt.commandId, revision, nodeId, onDelayed);
    if (!stillOwned()) return;
    attempt.pending = false;
    attempt.recovery = null;
    if (kind === "refresh") {
      adoptTaskStart(result, "inventory");
      attempt.message = null;
      renderTasks();
      try { await refreshTasks(); } catch (_error) {
        // The admitted identity and its live drain already own current task status.
      }
    } else {
      attempt.message = inventoryResultMessage(result);
      task.inventoryViewUnconfirmed = true;
      if (selectedTaskId === task.taskId && !settingsVisible && task.requestId === requestId) {
        await loadInventoryReview(task, true);
        if (stillOwned() && task.inventoryViewUnconfirmed) {
          attempt.message += " Reload inventory view to confirm current visibility before another action.";
        }
      }
    }
  } catch (error) {
    if (!stillOwned()) return;
    if (error instanceof StartPlanUncertainError || error instanceof OutcomeUnavailableError) {
      attempt.pending = true;
      attempt.message = attempt.recovery?.message ?? UNKNOWN_OUTCOME_GUIDANCE;
    } else {
      attempt.pending = false;
      attempt.recovery = null;
      attempt.message = error?.code === "inventory_capacity"
        ? "Inventory command capacity is full. Close a task before trying again."
        : kind === "refresh"
          ? "Inventory refresh was refused. Review this task and try again."
          : "Visibility change was refused. Reload inventory view before trying again.";
    }
  } finally {
    if (stillOwned()) renderTasks();
  }
}

function currentInventoryTask(review) {
  const task = currentTask();
  return task !== null && !settingsVisible && !task.closePending
    && task.inventoryReview === review ? task : null;
}

async function loadInventoryReview(task, force = false) {
  if (task === undefined || tasks.get(task.taskId) !== task || selectedTaskId !== task.taskId
      || settingsVisible || task.closePending || task.taskKind !== "inventory"
      || !task.sessionReleased || task.sessionId === null
      || (!force && (task.inventoryLoading || task.inventoryReview !== null))) return;
  const request = ++task.inventoryRevision;
  const sessionId = task.sessionId;
  const navigation = navigationRevision;
  if (task.inventoryReview !== null) {
    task.inventoryReview.actionRevision += 1;
    task.inventoryReview.pending = null;
    task.inventoryReview.queuedSearchQuery = null;
    retireInventoryDetail(task.inventoryReview);
  }
  task.inventoryLoading = true;
  task.inventoryError = null;
  renderTasks();
  const stillCurrent = () => tasks.get(task.taskId) === task && task.inventoryRevision === request
    && task.sessionId === sessionId && selectedTaskId === task.taskId
    && navigationRevision === navigation && !settingsVisible && !task.closePending;
  try {
    const summary = await openInventoryView(task.taskId);
    if (!stillCurrent()) return;
    const window = await getInventoryWindow(task.taskId, summary.view_revision, 0, 256);
    if (!stillCurrent()) return;
    if (window.disposition !== "current" || window.view_revision !== summary.view_revision) {
      task.inventoryError = "Inventory changed. Reload the inventory view to continue.";
      return;
    }
    task.inventoryReview = {
      summary, window, pending: null, message: null, queuedSearchQuery: null,
      actionRevision: 0, windowRequestRevision: 0, detailRevision: 0, detail: null, scrollTop: 0,
    };
    task.inventoryViewUnconfirmed = false;
  } catch (error) {
    if (stillCurrent()) task.inventoryError = error?.code === "task_unavailable"
      && task.sessionState === "refused" && task.inventoryReview !== null
      && task.inventoryReview.summary.request_id !== task.requestId
      ? "Inventory unavailable for the refused scan. Check the location, reconnect its drive if needed, then click Refresh."
      : "Inventory unavailable. Reload the inventory view to retry.";
  } finally {
    if (tasks.get(task.taskId) === task && task.inventoryRevision === request) {
      task.inventoryLoading = false;
      renderTasks();
    }
  }
}

async function changeInventoryView(review, patch) {
  const task = currentInventoryTask(review);
  if (task === null || task.inventoryLoading) return;
  if (review.pending !== null) {
    if (review.pending === "view" && Object.keys(patch).length === 1
        && typeof patch.searchQuery === "string") review.queuedSearchQuery = patch.searchQuery;
    return;
  }
  const action = ++review.actionRevision;
  const sessionId = task.sessionId;
  const publication = review.summary.request_id;
  const navigation = navigationRevision;
  const gesture = {
    searchQuery: patch.searchQuery ?? review.summary.search_query,
    filters: [...(patch.filters ?? review.summary.filters)],
    sortColumn: patch.sortColumn ?? review.summary.sort_column,
    sortDirection: (patch.sortColumn ?? review.summary.sort_column) === "path"
      ? "ascending" : patch.sortDirection ?? review.summary.sort_direction,
    collapseNodeId: patch.collapseNodeId ?? null,
    collapsed: patch.collapseNodeId === undefined ? null : patch.collapsed,
  };
  review.windowRequestRevision += 1;
  retireInventoryDetail(review);
  review.pending = "view";
  review.message = "Updating inventory view…";
  renderTasks();
  const stillCurrent = () => currentInventoryTask(review) === task && review.actionRevision === action
    && task.sessionId === sessionId && review.summary.request_id === publication
    && navigationRevision === navigation;
  try {
    const summary = await updateInventoryView(task.taskId, review.summary.view_revision, gesture, () => {
      if (stillCurrent()) {
        review.message = "View response delayed. Reload the inventory view to read its current state.";
        renderTasks();
      }
    });
    if (!stillCurrent()) return;
    const window = await getInventoryWindow(task.taskId, summary.view_revision, 0, 256);
    if (!stillCurrent()) return;
    if (window.disposition !== "current" || window.view_revision !== summary.view_revision) {
      review.message = "Inventory changed. Reload the inventory view to continue.";
      return;
    }
    review.summary = summary;
    review.window = window;
    review.scrollTop = 0;
    review.message = summary.disposition === "conflict" ? "View changed. Current inventory view shown." : null;
  } catch (_error) {
    if (stillCurrent()) review.message = "View response unavailable. Reload the inventory view to retry.";
  } finally {
    if (tasks.get(task.taskId) === task && task.inventoryReview === review && review.actionRevision === action) {
      review.pending = null;
      renderTasks();
      const queued = review.queuedSearchQuery;
      review.queuedSearchQuery = null;
      if (currentInventoryTask(review) === task && queued !== null
          && queued !== review.summary.search_query) void changeInventoryView(review, { searchQuery: queued });
    }
  }
}

async function loadInventoryWindow(review, offset) {
  const task = currentInventoryTask(review);
  if (task === null || task.inventoryLoading || review.pending !== null) return null;
  const request = ++review.windowRequestRevision;
  const action = review.actionRevision;
  const sessionId = task.sessionId;
  const publication = review.summary.request_id;
  const revision = review.summary.view_revision;
  const navigation = navigationRevision;
  const stillCurrent = () => currentInventoryTask(review) === task
    && review.windowRequestRevision === request && review.actionRevision === action
    && task.sessionId === sessionId && review.summary.request_id === publication
    && review.summary.view_revision === revision && navigationRevision === navigation;
  try {
    const window = await getInventoryWindow(task.taskId, revision, offset, 256);
    if (!stillCurrent()) return null;
    if (window.disposition !== "current") {
      review.message = "Inventory changed. Reload the inventory view to continue.";
      renderTasks();
      return null;
    }
    return window;
  } catch (_error) {
    if (stillCurrent()) {
      review.message = "Inventory rows unavailable. Reload the inventory view to retry.";
      renderTasks();
    }
    return null;
  }
}

async function readInventoryDetail(review, nodeId) {
  const task = currentInventoryTask(review);
  if (task === null || task.inventoryLoading || review.pending !== null) return;
  const row = review.window.rows.find((value) => value.node_id === nodeId);
  if (row === undefined) return;
  const request = ++review.detailRevision;
  const action = review.actionRevision;
  const sessionId = task.sessionId;
  const publication = review.summary.request_id;
  const revision = review.summary.view_revision;
  const navigation = navigationRevision;
  const detail = { row, state: row.row_id === null ? "current" : "loading", response: null };
  review.detail = detail;
  renderTasks();
  if (row.row_id === null) return;
  const stillCurrent = () => currentInventoryTask(review) === task && review.detailRevision === request
    && review.detail === detail && review.actionRevision === action && task.sessionId === sessionId
    && review.summary.request_id === publication && review.summary.view_revision === revision
    && navigationRevision === navigation;
  try {
    const response = await getInventoryDetail(task.taskId, revision, nodeId);
    if (!stillCurrent()) return;
    if (response.disposition === "conflict") {
      retireInventoryDetail(review);
      review.message = "Inventory changed. Reload the inventory view to read current details.";
    } else {
      detail.state = response.disposition;
      detail.response = response;
    }
  } catch (_error) {
    if (stillCurrent()) detail.state = "error";
  } finally {
    if (currentInventoryTask(review) === task && review.detailRevision === request
        && navigationRevision === navigation) renderTasks();
  }
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
    || task.review?.pending === "selection"
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
    const message = task.executionStarted
      ? task.sessionState === "active"
        ? executionControlMessage(task.executionControlState)
        : task.sessionState === "completed" ? null : `Execution ${task.sessionState}.`
      : summary.preflight_ready
        ? null
        : "Plan failed review. Inspect notices and create a fresh plan.";
    const controlAttempt = task.executionControlAttempt?.sessionId === sessionId
      ? task.executionControlAttempt : null;
    const retainedRecovery = task.reviewSessionId === sessionId
      ? task.review?.recovery ?? null : null;
    const retainedOutcomeAction = task.reviewSessionId === sessionId
      ? task.review?.outcomeAction ?? null : null;
    const retainedFollow = task.reviewSessionId === sessionId ? task.review?.follow ?? null : null;
    const eligibleFollow = summary.search_query === "" && summary.filters.length === 0
      && summary.sort_column === "path" && summary.sort_direction === "ascending";
    task.review = {
      summary,
      window,
      pending: task.closePending || checkableOutcome(task.closeRecovery) || fixedOutcome(task.closeRecovery)
        ? "close"
        : checkableOutcome(retainedRecovery) || fixedOutcome(retainedRecovery) ? "outcome"
        : controlAttempt?.pending ? controlAttempt.actionName : null,
      recovery: retainedRecovery,
      outcomeAction: retainedOutcomeAction,
      refreshAvailable: false,
      queuedSearchQuery: null,
      highlightQueue: Promise.resolve(),
      message: task.drainUnavailable && task.sessionState === "active" && task.executionStarted
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
      (_feedback) => {
        if (retainedReviewTask(review) === task && review.actionRevision === action) {
          review.refreshAvailable = true;
          review.message = "View update is still pending. Refresh to read the current review.";
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
    review.refreshAvailable = false;
    review.message = summary.disposition === "conflict"
      ? "View changed. Current view restored."
      : null;
  } catch (_error) {
    if (retainedReviewTask(review) === task && review.actionRevision === action) {
      review.queuedSearchQuery = null;
      review.refreshAvailable = true;
      review.message = "View response unavailable. Refresh to read the current review.";
      void loadPlanReview(task, true);
    }
  } finally {
    if (retainedReviewTask(review) === task && review.actionRevision === action) {
      if (review.pending === "view") review.pending = null;
      renderTasks();
      const queuedSearchQuery = review.queuedSearchQuery;
      review.queuedSearchQuery = null;
      if (review.pending === null && queuedSearchQuery !== null
          && queuedSearchQuery !== review.summary.search_query) {
        void changePlanView(review, { searchQuery: queuedSearchQuery }, true);
      }
    }
    endForegroundWindowRead(review);
  }
}

function retainReviewOutcome(review, error, actionName = review.outcomeAction ?? null) {
  if (!(error instanceof OutcomeUnavailableError)) return false;
  review.outcomeAction = actionName;
  review.pending = "outcome";
  renderTasks();
  return true;
}

async function retryReviewOutcome(review) {
  const task = retainedReviewTask(review);
  const cancelAttempt = task?.executionControlAttempt;
  if (task !== null && fixedOutcome(review.recovery)
      && cancelAttempt?.independent && checkableOutcome(cancelAttempt.recovery)) {
    await retryIndependentCancelOutcome(task, cancelAttempt);
    return;
  }
  if (task !== null && cancelAttempt !== null && !cancelAttempt.independent
      && cancelAttempt.sessionId === task.sessionId
      && checkableOutcome(cancelAttempt.recovery)) {
    await cancelAttempt.recovery.check();
    return;
  }
  if (task === null || review.recovery?.checking) return;
  if (review.refreshAvailable) {
    review.refreshAvailable = false;
    review.actionRevision += 1;
    await loadPlanReview(task, true);
    if (task.review === review) {
      review.refreshAvailable = true;
      review.message = "Current review unavailable. Select Refresh review to try again.";
      renderTasks();
    }
    return;
  }
  if (checkableOutcome(review.recovery)) await review.recovery.check();
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
            review.refreshAvailable = true;
            review.message = "Highlight is still pending. Select Refresh review to read the current highlight.";
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
      review.refreshAvailable = false;
      const focusedRow = window.rows.find((row) => row.node_id === summary.highlight_focus_node_id);
      if (focusedRow?.operation_id === review.executionDetail?.operationId
          && review.executionDetail?.state === "error") {
        void readExecutionDetail(review, focusedRow);
      }
      renderTasks();
    } catch (_error) {
      if (retainedReviewTask(review) === task && review.actionRevision === action) {
        review.refreshAvailable = true;
        review.message = "Highlight response unavailable. Select Refresh review to read the current highlight.";
        renderTasks();
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
  const onDelayed = (recovery) => {
    if (retainedReviewTask(review) === task && review.actionRevision === action) {
      review.recovery = recovery;
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
    review.recovery = null;
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
      && review.pending === "selection" && !fixedOutcome(review.recovery)
    ) {
      review.recovery = null;
      review.pending = null;
      renderTasks();
    }
    endForegroundWindowRead(review);
  }
}

async function executeReviewedPlan(review, returnFocus) {
  const task = currentReviewTask(review);
  if (task !== null && task.executionAttempt?.state === "submitting") {
    const attempt = task.executionAttempt;
    if (checkableOutcome(attempt.recovery)) await attempt.recovery.check();
    return;
  }
  if (
    task === null || task.closePending || checkableOutcome(task.closeRecovery)
    || fixedOutcome(task.closeRecovery) || review.pending !== null
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
    recovery: null,
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
    || !["confirming", "submitting"].includes(attempt.state)
  ) return;
  if (attempt.submissionStarted) return;
  const submit = () => startExecution(
    attempt.taskId,
    attempt.requestId,
    attempt.selectionRevision,
    attempt.destructiveAcknowledged,
    (recovery) => {
      if (tasks.get(task.taskId) === task && task.executionAttempt === attempt
          && task.review !== null) {
        attempt.recovery = recovery;
        renderTasks();
      }
    },
  );
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
      task.snapshot = null;
      task.progressPresentation = null;
      task.executionStarted = true;
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
      if (currentReview !== null) {
        currentReview.pending = "outcome";
        currentReview.message = null;
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
    attempt.message = executionControlMessage(result.after);
  } else {
    attempt.message = result.detail || `The ${attempt.actionName} request was not accepted.`;
  }
  if (!attempt.independent && task.review !== null) task.review.message = attempt.message;
}

async function retryIndependentCancelOutcome(task, attempt) {
  if (task.executionControlAttempt !== attempt || fixedOutcome(attempt.recovery)
      || task.sessionId !== attempt.sessionId || task.sessionState !== "active") return;
  if (checkableOutcome(attempt.recovery)) await attempt.recovery.check();
}

async function controlReviewedExecution(review, actionName) {
  const task = currentReviewTask(review);
  const independentCancel = task !== null && actionName === "cancel"
    && canCancelAfterFixedReviewOutcome(task, review);
  if (
    task === null || task.closePending || checkableOutcome(task.closeRecovery)
    || fixedOutcome(task.closeRecovery) || (review.pending !== null && !independentCancel)
    || !task.executionStarted
    || task.sessionState !== "active" || task.sessionId === null
    || task.reviewSessionId !== task.sessionId
    || task.drainUnavailable || task.executionControlAttempt?.pending
    || (fixedOutcome(task.executionControlAttempt?.recovery) && !independentCancel)
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
    recovery: null,
    independent: independentCancel,
    accepted: false,
    controlRevision,
    controlState,
  };
  task.executionControlAttempt = attempt;
  if (!independentCancel) {
    review.pending = actionName;
    review.message = attempt.message;
  }
  renderTasks();
  const stillOwned = () => tasks.get(task.taskId) === task
    && task.sessionId === sessionId && task.executionControlAttempt === attempt;
  try {
    const result = await controlExecution(task.taskId, sessionId, actionName, (recovery) => {
      if (stillOwned() && task.review !== null) {
        attempt.recovery = recovery;
        if (!independentCancel) task.review.recovery = recovery;
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
        attempt.message = null;
      } else if (!independentCancel && task.review !== null
          && retainReviewOutcome(task.review, error, actionName)) {
        attempt.message = null;
      } else {
        attempt.message = `${actionName[0].toUpperCase()}${actionName.slice(1)} refused. Follow live status.`;
      }
      if (!independentCancel && task.review !== null) task.review.message = attempt.message;
    }
  } finally {
    if (stillOwned()) {
      if (independentCancel) {
        attempt.pending = false;
      } else {
        attempt.pending = false;
        if (task.review?.pending === actionName) task.review.pending = null;
      }
      renderTasks();
    }
  }
}

async function planAgainFromReview(review) {
  const task = currentReviewTask(review);
  if (task !== null && review.pending === "plan-again"
      && checkableOutcome(task.form?.attempt?.recovery)) {
    await retryFormAttempt(task, task.form, "plan-again");
    return;
  }
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
  if (!row.text || row.candidate === null || row.pending) return null;
  const revision = row.revision;
  const admissionRevision = ++row.admissionRevision;
  row.pending = true;
  renderTasks();
  let result;
  try {
    result = await admitLocation(purpose, row.candidate, () => {
      if (tasks.get(task.taskId) === task && task.form === form
          && row.revision === revision) {
        form.actionMessage = "Folder choice is still pending. Wait, or edit this folder to choose again.";
        renderTasks();
      }
    });
  } catch (error) {
    if (tasks.get(task.taskId) === task && task.form === form
        && row.revision === revision && row.admissionRevision === admissionRevision) {
      form.actionMessage = "Folder choice could not be confirmed. Review or choose this folder again.";
      renderTasks();
    }
    throw error;
  } finally {
    if (tasks.get(task.taskId) === task && task.form === form
        && row.revision === revision && row.admissionRevision === admissionRevision) {
      row.pending = false;
      renderTasks();
    }
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
  if (task === null || !formIsEditable(form) || pickerPending) return;
  pickerPending = true;
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
  const admissionRevision = ++row.admissionRevision;
  row.pending = true;
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
    if (tasks.get(task.taskId) === task && task.form === form
        && row.revision === revision) {
      form.actionMessage = "Folder choice could not be confirmed. Choose it again.";
      renderTasks();
    }
  } finally {
    pickerPending = false;
    if (tasks.get(task.taskId) === task && task.form === form
        && form[purpose] === row && row.revision === revision
        && row.admissionRevision === admissionRevision) {
      row.pending = false;
      renderTasks();
    }
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
  row.pending = true;
  renderTasks();
  try {
    const result = await admitLocation(purpose, selection, () => {
      if (tasks.get(task.taskId) === task && task.form === form
          && row.revision === revision) {
        form.actionMessage = "Mount choice is still pending. Wait, or choose another mount.";
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
  } catch (_error) {
    if (
      tasks.get(task.taskId) === task &&
      task.form === form &&
      row.revision === revision &&
      row.admissionRevision === admissionRevision
    ) {
      row.mountIndex = null;
      row.pending = false;
      form.actionMessage = "Folder choice could not be confirmed. Choose a mount again.";
      renderTasks();
    }
  } finally {
    if (tasks.get(task.taskId) === task && task.form === form
        && row.revision === revision && row.admissionRevision === admissionRevision) {
      row.pending = false;
      renderTasks();
    }
  }
}

function beginFormAttempt(task, form, kind) {
  if (
    tasks.get(task.taskId) !== task || task.form !== form || form.attempt !== null ||
    fixedOutcome(task.closeRecovery) || fixedOutcome(task.startRecovery) ||
    (pageBatch !== null && pageBatch.running !== null)
  ) return null;
  const attempt = {
    kind,
    running: true,
    dispatched: false,
    recovery: null,
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
    const result = await submit();
    adoptTaskStart(result, attempt.kind === "inventory" ? "inventory" : "sync-plan");
  } catch (error) {
    if (!currentFormAttempt(task, form, attempt)) return;
    if (error instanceof StartPlanUncertainError) {
      attempt.running = false;
      renderTasks();
      return;
    }
    form.attempt = null;
    task.startRecovery = null;
    form.actionMessage = "That task could not be started. Review the setup and try again.";
    renderTasks();
    void loadTaskSetup(task);
    return;
  }
  if (currentFormAttempt(task, form, attempt)) {
    form.attempt = null;
    task.startRecovery = null;
  }
  renderTasks();
  try { await refreshTasks(); } catch (_error) {
    // The admitted identity and its live drain already own current task status.
  }
}

async function retryFormAttempt(task, form, kind) {
  const attempt = form.attempt;
  if (
    attempt === null || attempt.kind !== kind || !attempt.running ||
    !checkableOutcome(attempt.recovery) || attempt.recovery.checking
  ) return false;
  await attempt.recovery.check();
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
    task === null || task.closePending || checkableOutcome(task.closeRecovery) || fixedOutcome(task.closeRecovery)
    || fixedOutcome(task.startRecovery) || form === null || !form.editable || form.mode !== "sync-plan" ||
    (originHasPendingBatch(task.taskId) || batchTaskBlockReason(task.taskId) !== null) ||
    (pageBatch !== null && pageBatch.running !== null)
  ) return;
  if (form.attempt !== null) {
    await retryFormAttempt(task, form, "sync-plan");
    return;
  }
  if (!form.source.text || !form.target.text || form.options === null
      || form.source.pending || form.target.pending) return;
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
      () => startPlan(task.taskId, ready.sourceId, ready.targetId, ready.options, (recovery) => {
        if (currentFormAttempt(task, form, attempt)) {
          attempt.recovery = recovery;
          task.startRecovery = recovery;
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
    task === null || task.closePending || checkableOutcome(task.closeRecovery) || fixedOutcome(task.closeRecovery)
    || fixedOutcome(task.startRecovery) || form === null || !form.editable || form.mode !== "inventory" ||
    batchTaskBlockReason(task.taskId) !== null ||
    (pageBatch !== null && pageBatch.running !== null)
  ) return;
  if (form.attempt !== null) {
    await retryFormAttempt(task, form, "inventory");
    return;
  }
  if (!form.source.text || form.source.pending) return;
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
      task.taskId, root.choice_id, (recovery) => {
        if (currentFormAttempt(task, form, attempt)) {
          attempt.recovery = recovery;
          task.startRecovery = recovery;
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
    task === null || task.closePending || checkableOutcome(task.closeRecovery) || fixedOutcome(task.closeRecovery)
    || fixedOutcome(task.startRecovery) || !formIsEditable(form) || form.mode !== "sync-plan" ||
    form.source.pending || form.target.pending ||
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
    recovery: null,
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
  if (pageBatch === null || (row?.state !== "queued"
      && !(row?.state === "submitting" && row.stage?.startsWith("admitting-")))) return;
  const index = pageBatch.rows.indexOf(row);
  if (index < 0 || row.originTaskId !== selectedTaskId) return;
  pageBatch.rows.splice(index, 1);
  row.abandonAdmission?.();
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

function retainBatchUnknown(row, stage) {
  row.state = "unknown";
  row.stage = stage;
  row.message = null;
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
      const options = await prepareSetup(cloneOptions(row.options));
      if (!context.contains(row) || row.state !== "queued" || !context.canSubmit()) return;
      row.options = cloneOptions(options);
      row.state = "submitting";
      row.message = "Checking folders…";
      renderTasks();
      row.stage = "admitting-source";
      const source = await admitBatchRow(row.source, "source", row);
      if (!context.contains(row) || !context.canSubmit()) return;
      row.stage = "admitting-target";
      const target = await admitBatchRow(row.target, "target", row);
      if (!context.contains(row) || !context.canSubmit()) return;
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
      const shell = await createTask((recovery) => {
        if (row.state === "submitting") {
          row.recovery = recovery;
          renderTasks();
        }
      });
      row.recovery = null;
      task = adoptBatchShell(shell, row);
    if (!context.canSubmit()) {
      row.state = "stopped";
      row.message = "The blank task was retained; its plan was not submitted because the batch changed.";
      void refreshTasks();
      return;
    }
    row.stage = "starting";
    row.message = "Creating plan…";
    renderTasks();
    const result = await startPlan(task.taskId, row.sourceId, row.targetId, row.options, (recovery) => {
      if (row.state === "submitting") {
        row.recovery = recovery;
        renderTasks();
      }
    });
    adoptTaskStart(result, "sync-plan");
    row.recovery = null;
    row.state = "created";
    row.message = "Plan task created.";
  } catch (error) {
    if (error instanceof TaskCreateUncertainError) {
      retainBatchUnknown(row, "creating");
    } else if (error instanceof StartPlanUncertainError) {
      retainBatchUnknown(row, "starting");
    } else {
      row.state = "refused";
      row.recovery = null;
      row.message = "That pair could not be created. Review its folders and settings, then try again.";
    }
  }
}

async function startPairBatch() {
  const task = currentTask();
  const form = currentForm();
  const batch = pageBatch;
  if (batch?.running?.originTaskId === task?.taskId) {
    const row = batch.running.row;
    if (checkableOutcome(row?.recovery) && !row.recovery.checking) {
      await row.recovery.check();
    }
    return;
  }
  if (
    task === null || task.closePending || checkableOutcome(task.closeRecovery) || fixedOutcome(task.closeRecovery)
    || fixedOutcome(task.startRecovery) || !formIsEditable(form) || form.mode !== "sync-plan" || form.attempt !== null
    || form.source.pending || form.target.pending ||
    batch === null || batch.running !== null
  ) return;
  if (batch.rows.some((row) => row.originTaskId === task.taskId
      && row.state === "unknown")) return;
  const rows = batch.rows.filter((row) => row.originTaskId === task.taskId
    && row.state === "queued");
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
      && tasks.get(task.taskId) === task && !task.closePending && !checkableOutcome(task.closeRecovery)
      && !fixedOutcome(task.closeRecovery) && !fixedOutcome(task.startRecovery),
  };
  batch.running = owner;
  renderTasks();
  try {
    for (const row of rows) {
      if (!currentBatchRun(batch, owner, generation)) break;
      if (!batch.rows.includes(row)) continue;
      if (row.state !== "queued") continue;
      owner.row = row;
      await startBatchRow(row, context);
      renderTasks();
    }
  } finally {
    if (batch.running === owner) batch.running = null;
    renderTasks();
  }
  try { await refreshTasks(); } catch (_error) {
    // Each admitted child already retains its identity and current task drain.
  }
}

async function admitBatchRow(row, purpose, batchRow) {
  const accepted = resolvedChoice(row, purpose);
  if (accepted !== null) return accepted;
  if (!row.text || row.candidate === null) return null;
  const revision = row.revision;
  const abandoned = new Promise((resolve) => {
    batchRow.abandonAdmission = () => resolve(null);
  });
  const admission = admitLocation(purpose, row.candidate, () => {
    if (batchRow.state === "submitting") {
      batchRow.message = "Folder response delayed. Wait, or remove this pair and add it again after reviewing the folders.";
      renderTasks();
    }
  });
  let result;
  try { result = await Promise.race([admission, abandoned]); }
  finally { batchRow.abandonAdmission = null; }
  if (result === null) return null;
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
    task === null || currentTask() !== task || task.closePending || checkableOutcome(task.closeRecovery)
    || fixedOutcome(task.closeRecovery) || fixedOutcome(task.startRecovery) ||
    form?.canPlanAgain !== true ||
    originHasPendingBatch(task.taskId) || batchTaskBlockReason(task.taskId) !== null ||
    (pageBatch !== null && pageBatch.running !== null)
  ) return false;
  return form.attempt === null || (
    form.attempt.kind === "plan-again" && form.attempt.running &&
    checkableOutcome(form.attempt.recovery) && !form.attempt.recovery.checking
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
    () => planAgain(task.taskId, sourceMount, targetMount, (recovery) => {
      if (currentFormAttempt(task, form, attempt)) {
        attempt.recovery = recovery;
        task.startRecovery = recovery;
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
