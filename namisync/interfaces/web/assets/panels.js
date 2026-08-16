import { renderText } from "./render.js";

export function createWorkPanel() {
  const panel = document.createElement("section");
  panel.classList.add("nami-card", "nami-work-panel");
  panel.setAttribute("role", "region");
  panel.ariaLabel = "Work area";

  const heading = document.createElement("h2");
  renderText(heading, "Work area");
  const empty = document.createElement("p");
  empty.classList.add("nami-shell__empty");
  renderText(empty, "No task selected.");
  const guidance = document.createElement("p");
  guidance.classList.add("nami-shell__guidance");
  renderText(
    guidance,
    "Task details will appear here when a task is available.",
  );
  panel.append(heading, empty, guidance);
  return panel;
}
