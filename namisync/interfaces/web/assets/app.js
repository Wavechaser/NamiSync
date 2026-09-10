import {
  acknowledgeShellReady,
  BridgeTransportError,
  closeTask,
  createTask,
  echoReadiness,
  listTasks,
  markBridgeOperational,
  startTaskDrain,
  whenBridgeApiReady,
} from "./bridge.js";
import { installReadinessReceiver } from "./readiness.js";
import { installAppearanceReceiver } from "./appearance.js";
import { installThemeCombobox, installThemeSelector } from "./theme.js";
import { createWorkPanel } from "./panels.js";
import { createTaskRail } from "./rail.js";
import { renderText } from "./render.js";

const app = document.querySelector("#app");
const status = document.querySelector("#host-status");
const themeSelector = document.querySelector("#theme-mode");
if (
  !(app instanceof HTMLElement)
  || !(status instanceof HTMLElement)
  || !(themeSelector instanceof HTMLElement)
) {
  throw new TypeError("NamiSync shell elements are unavailable");
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
let navigationRevision = 0;
let taskMutationRevision = 0;
let creatingTask = false;
let nextTaskNumber = 1;

const panel = createWorkPanel();
const rail = createTaskRail({
  onCreate: () => { void createBlankTask(); },
  onSelect: selectTask,
  onClose: (taskId) => { void closeRetainedTask(taskId); },
});
app.append(rail.element, panel.element);

function taskArray() {
  return Array.from(tasks.values()).reverse();
}

function renderTasks() {
  rail.render(taskArray(), selectedTaskId, creatingTask);
  panel.render(selectedTaskId === null ? null : tasks.get(selectedTaskId) ?? null);
}

function selectTask(taskId) {
  if (!tasks.has(taskId)) {
    return;
  }
  navigationRevision += 1;
  selectedTaskId = taskId;
  renderTasks();
}

function adoptTask(summary) {
  let task = tasks.get(summary.task_id);
  if (task === undefined) {
    task = {
      taskId: summary.task_id,
      sessionId: summary.session_id,
      sessionState: summary.session_state,
      sessionReleased: summary.session_released,
      closePending: false,
      error: null,
      label: `Task ${nextTaskNumber}`,
      stopDrain: null,
    };
    nextTaskNumber += 1;
    tasks.set(task.taskId, task);
  } else {
    task.sessionId = summary.session_id;
    task.sessionState = summary.session_state;
    task.sessionReleased = summary.session_released;
  }
  if (
    task.sessionId !== null &&
    task.stopDrain === null
  ) {
    task.stopDrain = startTaskDrain(
      task.taskId,
      task.sessionId,
      (update) => acceptTaskUpdate(task, update),
      () => acceptTaskRefusal(task),
      {
        terminal: task.sessionState !== "active",
        sessionReleased: task.sessionReleased,
      },
    );
  }
  return task;
}

function acceptTaskUpdate(task, update) {
  if (tasks.get(task.taskId) !== task) {
    return;
  }
  if (update.update_type === "record") {
    taskMutationRevision += 1;
    task.sessionState = update.record.state;
    if (task.closePending) {
      task.closePending = false;
      void closeRetainedTask(task.taskId);
    }
    renderTasks();
  }
}

function acceptTaskRefusal(task) {
  if (tasks.get(task.taskId) !== task) {
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
}

async function createBlankTask() {
  if (creatingTask) {
    return;
  }
  const epoch = startupEpoch;
  const selectionBaseline = navigationRevision;
  creatingTask = true;
  renderTasks();
  try {
    const result = await createTask();
    taskMutationRevision += 1;
    if (epoch !== startupEpoch) {
      void refreshTasks(startupEpoch);
      return;
    }
    const task = adoptTask({
      task_id: result.task_id,
      session_id: null,
      session_state: null,
      session_released: false,
    });
    if (navigationRevision === selectionBaseline) {
      selectedTaskId = task.taskId;
    }
  } catch (_error) {
    if (epoch === startupEpoch) {
      renderText(
        status,
        "A task could not be created. Close an unused task or wait, then try again.",
      );
    }
  } finally {
    if (epoch === startupEpoch) {
      creatingTask = false;
      renderTasks();
    }
  }
}

async function closeRetainedTask(taskId) {
  const task = tasks.get(taskId);
  if (task === undefined || task.closePending) {
    return;
  }
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
  void theme.open(appliedPresentationRevision);
  if (status.textContent === "Starting...") {
    renderText(status, "Ready");
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
  creatingTask = false;
  for (const task of tasks.values()) {
    task.closePending = false;
  }
  theme.invalidate();
  rejectSupersededStartup?.(new StartupSupersededError());
  if (status.textContent === "Ready") {
    renderText(status, "Starting...");
  }
  void ensureStartup({ rerun: true });
});
void ensureStartup();
