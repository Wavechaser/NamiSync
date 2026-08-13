import { renderText } from "./render.js";

export function createTaskRail() {
  const rail = document.createElement("nav");
  rail.classList.add("nami-task-rail");
  rail.ariaLabel = "Task navigation";

  const heading = document.createElement("h2");
  renderText(heading, "Tasks");
  const empty = document.createElement("p");
  empty.classList.add("nami-shell__empty");
  renderText(empty, "No tasks are available.");
  rail.append(heading, empty);
  return rail;
}
