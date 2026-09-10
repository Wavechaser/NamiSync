import { renderText } from "./render.js";

function taskStatus(task) {
  if (task.closePending) {
    return task.sessionId === null ? "Closing…" : "Canceling and closing…";
  }
  if (task.error !== null) {
    return task.error;
  }
  if (task.sessionState === null) {
    return "Not started";
  }
  const labels = {
    active: "In progress",
    completed: "Completed",
    failed: "Failed",
    canceled: "Canceled",
    refused: "Refused",
  };
  return labels[task.sessionState];
}

export function createTaskRail({ onCreate, onSelect, onClose }) {
  if (![onCreate, onSelect, onClose].every((callback) => typeof callback === "function")) {
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
  create.classList.add("nami-button");
  create.type = "button";
  renderText(create, "New task");
  create.addEventListener("click", onCreate);
  header.append(heading, create);

  const list = document.createElement("div");
  list.classList.add("nami-task-rail__items");
  rail.append(header, list);
  const entries = new Map();
  const emptySlot = document.createElement("div");
  emptySlot.classList.add("nami-card", "nami-task-rail__empty-slot");
  const empty = document.createElement("p");
  empty.classList.add("nami-shell__empty");
  renderText(empty, "No tasks are available.");
  emptySlot.append(empty);

  function render(tasks, selectedTaskId, creating) {
    create.disabled = creating;
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
        select.append(title, status);
        select.addEventListener("click", () => onSelect(task.taskId));
        const close = document.createElement("button");
        close.classList.add("nami-button", "nami-task-rail__close");
        close.type = "button";
        close.addEventListener("click", () => onClose(task.taskId));
        row.append(select, close);
        entry = { row, select, title, status, close };
        entries.set(task.taskId, entry);
      }
      entry.select.ariaCurrent = task.taskId === selectedTaskId ? "page" : "false";
      renderText(entry.title, task.label);
      renderText(entry.status, taskStatus(task));
      entry.close.disabled = task.closePending;
      entry.close.ariaLabel = `${task.error === null ? "Close" : "Retry close for"} ${task.label}`;
      renderText(entry.close, task.error === null ? "Close" : "Retry");
      list.append(entry.row);
    }
  }

  return Object.freeze({ element: rail, render });
}
