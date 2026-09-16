import { renderText } from "./render.js";
import { createSetupPanel } from "./setup.js";
import { createPlanReviewPanel } from "./plan_review.js";

export function createWorkPanel(setupCallbacks, planReviewCallbacks, settings) {
  if (!(settings instanceof HTMLElement)) throw new TypeError("settings view must be an element");
  const panel = document.createElement("section");
  panel.classList.add("nami-work-panel");
  panel.setAttribute("role", "region");
  panel.ariaLabel = "Work area";

  const body = document.createElement("div");
  body.classList.add("nami-work-panel__body");
  panel.append(body);
  const setup = createSetupPanel(setupCallbacks);
  const review = createPlanReviewPanel(planReviewCallbacks);
  settings.remove();
  settings.hidden = false;
  let content = null;

  function show(value) {
    if (content === value) return;
    content = value;
    body.replaceChildren(value);
  }

  function render(task) {
    panel.ariaLabel = task === null ? "Work area" : `Work area — ${task.label}`;
    if (task === null) {
      review.dispose();
      const empty = document.createElement("p");
      empty.classList.add("nami-shell__empty");
      renderText(empty, "No task selected.");
      show(empty);
      return;
    }
    if (task.review !== null || task.reviewLoading || task.executionStarted) {
      show(review.element);
      review.render(task);
      return;
    }
    if (task.form === null) {
      review.dispose();
      const loading = document.createElement("p");
      loading.classList.add("nami-shell__guidance");
      renderText(loading, "Loading task setup…");
      show(loading);
      return;
    }
    review.dispose();
    show(setup.element);
    setup.render(task.form);
  }

  function renderSettings() {
    review.dispose();
    panel.ariaLabel = "Settings";
    show(settings);
  }

  render(null);
  return Object.freeze({ element: panel, render, renderSettings });
}
