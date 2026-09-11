import {
  acknowledgeShellReady,
  admitLocation,
  BridgeTransportError,
  closeTask,
  createTask,
  echoReadiness,
  listTasks,
  markBridgeOperational,
  pickFolder,
  planAgain,
  prepareSetup,
  probeRecentPairs,
  readSetup,
  StartPlanUncertainError,
  startInventory,
  startPlan,
  startTaskDrain,
  TaskCreateUncertainError,
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
let createAttempt = null;
let nextTaskNumber = 1;
let defaultSetup = null;
let defaultSetupRevision = 0;
let recentPairAvailability = Object.create(null);
let recentPairProbeRevision = 0;
let recentPairProbeRunning = false;
let recentPairProbePending = false;
let pageBatch = null;

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
  onStartBatch: () => { void startPairBatch(); },
  onPlanAgain: () => { void startPlanAgain(); },
});
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
  for (const task of tasks.values()) {
    if (task.form !== null) task.form.recentPairAvailability = recentPairAvailability;
  }
  if (pageBatch !== null) {
    for (const task of tasks.values()) {
      if (task.form !== null) {
        task.form.batchRunning = pageBatch.running !== null;
        if (task.form.editable) task.form.batch = pageBatch.rows;
      }
    }
  }
  rail.render(
    taskArray(),
    selectedTaskId,
    createAttempt?.running === true,
  );
  panel.render(selectedTaskId === null ? null : tasks.get(selectedTaskId) ?? null);
}

function selectTask(taskId) {
  if (!tasks.has(taskId)) {
    return;
  }
  navigationRevision += 1;
  selectedTaskId = taskId;
  renderTasks();
  void loadTaskSetup(tasks.get(taskId));
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
    };
    nextTaskNumber += 1;
    tasks.set(task.taskId, task);
  } else {
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
    if (task.form !== null) task.form.sessionState = task.sessionState;
    if (task.closePending) {
      task.closePending = false;
      void closeRetainedTask(task.taskId);
    }
    renderTasks();
    if (["completed", "failed", "canceled", "refused"].includes(task.sessionState)) {
      void loadTaskSetup(task);
    }
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
  if (retry !== null) renderText(status, "Retrying task creation…");
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
    }
    void loadTaskSetup(task);
    if (createAttempt === attempt) createAttempt = null;
  } catch (error) {
    if (createAttempt !== attempt) return;
    if (error instanceof TaskCreateUncertainError) {
      attempt.running = false;
      attempt.retry = error.retry;
      renderText(
        status,
        "Task creation could not be confirmed. Select New task to retry the same request.",
      );
      return;
    }
    createAttempt = null;
    if (epoch === startupEpoch) {
      renderText(
        status,
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
    task === null || form === null || !form.editable || form.mode !== "sync-plan" ||
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
    task === null || form === null || !form.editable || form.mode !== "inventory" ||
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
  const form = currentForm();
  if (
    !formIsEditable(form) || form.mode !== "sync-plan" ||
    (pageBatch !== null && pageBatch.running !== null)
  ) return;
  if (pageBatch === null) pageBatch = { rows: [], generation: 0, running: null };
  if (pageBatch.rows.length >= 48) return;
  pageBatch.rows.push({
    source: snapshotLocationRow(form.source),
    target: snapshotLocationRow(form.target),
    state: "queued",
    stage: null,
    retry: null,
    taskId: null,
    sourceId: null,
    targetId: null,
    options: null,
    snapshot: null,
    recents: null,
    message: "Ready to create.",
  });
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
      row.options = cloneOptions(context.options);
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
      row.message = "That pair could not be created. Review its folders and try again.";
    }
  }
}

async function startPairBatch() {
  const form = currentForm();
  const batch = pageBatch;
  if (
    !formIsEditable(form) || form.mode !== "sync-plan" || form.attempt !== null ||
    batch === null || batch.running !== null
  ) return;
  const rows = batch.rows.filter((row) => ["queued", "uncertain"].includes(row.state));
  if (rows.length === 0) return;
  const queued = rows.filter((row) => row.state === "queued");
  if (queued.length > 0 && form.options === null) return;
  const owner = {};
  const generation = batch.generation;
  const epoch = startupEpoch;
  const optionsInput = queued.length === 0 ? null : cloneOptions(form.options);
  const context = {
    epoch,
    snapshot: form.setup,
    recents: defaultSetup?.recents ?? form.setup.recents,
    options: null,
    canSubmit: () => currentBatchRun(batch, owner, generation) && epoch === startupEpoch,
  };
  batch.running = owner;
  renderTasks();
  try {
    if (optionsInput !== null) context.options = await prepareSetup(optionsInput);
    for (const row of rows) {
      if (!currentBatchRun(batch, owner, generation) || epoch !== startupEpoch) break;
      if (!["queued", "uncertain"].includes(row.state)) continue;
      await startBatchRow(row, context);
      renderTasks();
    }
  } catch (_error) {
    // Preparing one exact option snapshot is read-only; queued rows remain retryable.
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

async function startPlanAgain() {
  const task = currentTask();
  const form = task?.form;
  if (
    task === null || form?.canPlanAgain !== true ||
    (pageBatch !== null && pageBatch.running !== null)
  ) return;
  if (form.attempt !== null) {
    await retryFormAttempt(task, form, "plan-again");
    return;
  }
  const revision = form.revision;
  const sourceMount = form.planAgainMounts.source;
  const targetMount = form.planAgainMounts.target;
  const attempt = beginFormAttempt(task, form, "plan-again");
  if (attempt === null || !freshFormAttempt(task, form, attempt, revision)) return;
  await dispatchFormAttempt(
    task, form, attempt,
    () => planAgain(task.taskId, sourceMount, targetMount),
  );
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
    renderText(status, "Starting...");
  }
  void ensureStartup({ rerun: true });
});
void ensureStartup();
