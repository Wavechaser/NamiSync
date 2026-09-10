import { renderText } from "./render.js";
import { createSetupPanel } from "./setup.js";

export function createWorkPanel(setupCallbacks) {
  const panel = document.createElement("section");
  panel.classList.add("nami-card", "nami-work-panel");
  panel.setAttribute("role", "region");
  panel.ariaLabel = "Work area";

  const heading = document.createElement("h2");
  const body = document.createElement("div");
  body.classList.add("nami-work-panel__body");
  panel.append(heading, body);
  const setup = createSetupPanel(setupCallbacks);
  let content = null;

  function show(value) {
    if (content === value) return;
    content = value;
    body.replaceChildren(value);
  }

  function render(task) {
    renderText(heading, task === null ? "Work area" : task.label);
    if (task === null) {
      const empty = document.createElement("p");
      empty.classList.add("nami-shell__empty");
      renderText(empty, "No task selected.");
      show(empty);
      return;
    }
    if (task.form === null) {
      const loading = document.createElement("p");
      loading.classList.add("nami-shell__guidance");
      renderText(loading, "Loading task setup…");
      show(loading);
      return;
    }
    show(setup.element);
    setup.render(task.form);
  }

  render(null);
  return Object.freeze({ element: panel, render });
}
