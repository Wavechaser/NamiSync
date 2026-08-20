import { renderText } from "./render.js";

export function createTaskRail() {
  const rail = document.createElement("nav");
  rail.classList.add("nami-task-rail");
  rail.ariaLabel = "Task navigation";

  const heading = document.createElement("h2");
  renderText(heading, "Tasks");
  const emptySlot = document.createElement("div");
  emptySlot.classList.add("nami-card", "nami-task-rail__empty-slot");
  const empty = document.createElement("p");
  empty.classList.add("nami-shell__empty");
  renderText(empty, "No tasks are available.");
  emptySlot.append(empty);
  rail.append(heading, emptySlot);
  return rail;
}
