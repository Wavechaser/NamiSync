import { createIcon } from "./icons.js";
import { renderFilesystemText, renderText } from "./render.js";
import { taskStatusDigest } from "./task_status.js";

export function createTaskRail({ onCreate, onSelect, onClose, onRetryUpdates, onSettings }) {
  if (![onCreate, onSelect, onClose, onRetryUpdates, onSettings].every((callback) => typeof callback === "function")) {
    throw new TypeError("task rail callbacks must be callable");
  }
  const rail = document.createElement("nav");
  rail.classList.add("nami-task-rail");
  rail.ariaLabel = "Task navigation";

  const header = document.createElement("div");
  header.classList.add("nami-task-rail__header");
  const heading = document.createElement("h2");
  renderText(heading, "Tasks");
  const create = document.createElement("button");
  create.classList.add("nami-button", "nami-task-rail__create");
  create.type = "button";
  create.append(createIcon(document, "add-square-multiple", "lg"));
  create.ariaLabel = "New task";
  create.title = "New task";
  create.addEventListener("click", onCreate);
  header.append(heading, create);

  const list = document.createElement("div");
  list.classList.add("nami-task-rail__items");
  const settings = document.createElement("button");
  settings.classList.add("nami-task-card", "nami-task-rail__settings");
  settings.type = "button";
  settings.append(createIcon(document, "settings", "sm"));
  const settingsText = document.createElement("span");
  renderText(settingsText, "Settings");
  settings.append(settingsText);
  settings.addEventListener("click", onSettings);
  rail.append(header, list, settings);
  const entries = new Map();
  const emptySlot = document.createElement("div");
  emptySlot.classList.add("nami-card", "nami-task-rail__empty-slot");
  const empty = document.createElement("p");
  empty.classList.add("nami-shell__empty");
  renderText(empty, "No tasks are available.");
  emptySlot.append(empty);

  function render(tasks, selectedTaskId, createAttempt, settingsVisible = false) {
    const checkCreate = createAttempt?.recovery?.canCheck === true;
    create.disabled = createAttempt?.recovery?.state === "fixed-unknown"
      || (createAttempt?.running === true && (!checkCreate || createAttempt.recovery.checking));
    create.ariaLabel = checkCreate ? "Check new task outcome" : "New task";
    create.title = create.ariaLabel;
    settings.ariaCurrent = settingsVisible ? "page" : "false";
    if (tasks.length === 0) {
      for (const entry of entries.values()) {
        entry.row.remove();
      }
      entries.clear();
      if (emptySlot.parentNode !== list) {
        list.append(emptySlot);
      }
      return;
    }
    emptySlot.remove();
    const retained = new Set(tasks.map((task) => task.taskId));
    for (const [taskId, entry] of entries) {
      if (!retained.has(taskId)) {
        entry.row.remove();
        entries.delete(taskId);
      }
    }
    for (const task of tasks) {
      let entry = entries.get(task.taskId);
      if (entry === undefined) {
        const row = document.createElement("div");
        row.classList.add("nami-task-rail__row");
        const select = document.createElement("button");
        select.classList.add("nami-task-card");
        select.type = "button";
        const title = document.createElement("span");
        title.classList.add("nami-task-card__title");
        const status = document.createElement("span");
        status.classList.add("nami-task-card__status");
        const paths = document.createElement("span");
        paths.classList.add("nami-task-card__paths");
        const source = document.createElement("span");
        const target = document.createElement("span");
        for (const [value, label] of [[source, "Source:"], [target, "Target:"]]) {
          const pathRow = document.createElement("span");
          pathRow.classList.add("nami-labeled-path");
          const caption = document.createElement("span");
          renderText(caption, label);
          value.classList.add("nami-labeled-path__value");
          pathRow.append(caption, value);
          paths.append(pathRow);
        }
        const progress = document.createElement("span");
        progress.classList.add("nami-progress", "nami-progress--inline", "nami-task-card__progress");
        progress.setAttribute("role", "progressbar");
        progress.ariaValueMin = "0";
        progress.ariaValueMax = "100";
        const progressBar = document.createElement("span");
        progressBar.classList.add("nami-progress__bar");
        progress.append(progressBar);
        select.append(title, status, paths, progress);
        select.addEventListener("click", () => onSelect(task.taskId));
        const close = document.createElement("button");
        close.classList.add("nami-icon-button", "nami-task-rail__close");
        close.type = "button";
        close.append(createIcon(document, "dismiss", "sm"));
        close.addEventListener("click", () => onClose(task.taskId));
        const retry = document.createElement("button");
        retry.classList.add("nami-button", "nami-task-rail__retry");
        retry.type = "button";
        renderText(retry, "Retry updates");
        retry.addEventListener("click", () => onRetryUpdates(task.taskId));
        row.append(select, retry, close);
        entry = { row, select, title, status, source, target, progress, retry, close };
        entries.set(task.taskId, entry);
      }
      entry.select.ariaCurrent = !settingsVisible && task.taskId === selectedTaskId ? "page" : "false";
      const digest = taskStatusDigest(task);
      const closeUnavailable = task.closeRecovery?.state === "fixed-unknown";
      renderText(entry.title, closeUnavailable ? "Outcome unavailable" : digest.title);
      const closeReason = typeof task.closeBlockReason === "string" ? task.closeBlockReason : null;
      const closeStatus = task.closePending
        ? task.closeRecovery?.message ?? task.closeMessage
          ?? (task.sessionId === null ? "Closing…" : "Canceling and closing…")
        : closeReason ?? digest.detail;
      renderText(entry.status, closeStatus);
      renderFilesystemText(entry.source, digest.sourcePath);
      renderFilesystemText(entry.target, digest.targetPath);
      entry.source.title = digest.sourcePath;
      entry.target.title = digest.targetPath;
      entry.select.dataset ??= {};
      entry.select.dataset.taskLabel = task.label;
      entry.select.ariaLabel = `${task.label}: ${digest.title}`;
      entry.select.dataset.status = closeUnavailable ? "unavailable" : digest.state;
      if (typeof entry.progress.classList.toggle === "function") {
        entry.progress.classList.toggle("nami-progress--indeterminate", digest.progress.indeterminate);
      }
      if (digest.progress.indeterminate) entry.progress.removeAttribute?.("aria-valuenow");
      else entry.progress.ariaValueNow = String(digest.progress.value);
      entry.progress.style?.setProperty("--nami-progress-value", `${digest.progress.value}%`);
      const checkRelease = task.releaseRecovery?.canCheck === true;
      entry.retry.hidden = (!checkRelease && typeof task.recoveryRetry !== "function")
        || task.closeRecovery?.canCheck === true;
      entry.retry.disabled = task.recoveryRunning || task.releaseRecovery?.checking === true;
      renderText(entry.retry, checkRelease ? task.releaseRecovery.checking ? "Checking outcome…" : "Check outcome"
        : task.recoveryRunning ? "Retrying updates…" : "Retry updates");
      entry.retry.ariaLabel = `${checkRelease ? "Check release outcome for"
        : task.recoveryRunning ? "Retrying updates for" : "Retry updates for"} ${task.label}`;
      const checkClose = task.closePending && task.closeRecovery?.canCheck === true;
      entry.close.disabled = closeReason !== null && (!checkClose || task.closeRecovery.checking);
      entry.close.ariaLabel = checkClose ? `Check Close outcome for ${task.label}` : closeReason ?? `${closeUnavailable ? "Retry close outcome for"
        : task.closeFailed ? "Retry close for" : "Close"} ${task.label}`;
      entry.close.title = entry.close.ariaLabel;
      list.append(entry.row);
    }
  }

  return Object.freeze({ element: rail, render });
}
