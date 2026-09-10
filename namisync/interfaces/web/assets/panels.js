import { renderText } from "./render.js";

export function createWorkPanel() {
  const panel = document.createElement("section");
  panel.classList.add("nami-card", "nami-work-panel");
  panel.setAttribute("role", "region");
  panel.ariaLabel = "Work area";

  const heading = document.createElement("h2");
  const body = document.createElement("div");
  body.classList.add("nami-work-panel__body");
  panel.append(heading, body);

  function render(task) {
    renderText(heading, task === null ? "Work area" : task.label);
    body.replaceChildren();
    if (task === null) {
      const empty = document.createElement("p");
      empty.classList.add("nami-shell__empty");
      renderText(empty, "No task selected.");
      body.append(empty);
    }
  }

  render(null);
  return Object.freeze({ element: panel, render });
}
