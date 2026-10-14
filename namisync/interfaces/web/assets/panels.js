import { renderText } from "./render.js";
import { createSetupPanel } from "./setup.js";
import { createPlanReviewPanel } from "./plan_review.js";
import { createInventoryReviewPanel } from "./inventory_review.js";

export function createWorkPanel(setupCallbacks, planReviewCallbacks, settings, inventoryCallbacks) {
  if (!(settings instanceof HTMLElement)) throw new TypeError("settings view must be an element");
  const panel = document.createElement("section");
  panel.classList.add("nami-work-panel");
  panel.setAttribute("role", "region");
  panel.ariaLabel = "Work area";

  const body = document.createElement("div");
  body.classList.add("nami-work-panel__body");
  panel.append(body);
  const setup = createSetupPanel(setupCallbacks);
  const review = createPlanReviewPanel({ ...planReviewCallbacks, onCheckStart: setupCallbacks.onStartPlan });
  const inventory = createInventoryReviewPanel({ ...inventoryCallbacks, onCheckStart: setupCallbacks.onStartInventory });
  settings.remove();
  settings.hidden = false;
  let content = null;
  let renderedTaskId = null;

  function show(value) {
    if (content === value) return;
    value.hidden = false;
    content = value;
    body.replaceChildren(value);
  }

  function showTaskPane(value, peer) {
    if (content === value) return;
    value.hidden = false;
    if (content === peer && peer.parentNode === body) {
      peer.hidden = true;
      if (value.parentNode !== body) body.append(value);
      content = value;
      return;
    }
    show(value);
  }

  function render(task) {
    panel.ariaLabel = task === null ? "Work area" : `Work area — ${task.label}`;
    if (task === null) {
      review.dispose();
      inventory.dispose();
      renderedTaskId = null;
      const empty = document.createElement("p");
      empty.classList.add("nami-shell__empty");
      renderText(empty, "No task selected.");
      show(empty);
      return;
    }
    if (renderedTaskId !== null && renderedTaskId !== task.taskId) {
      review.dispose();
      inventory.dispose();
    }
    renderedTaskId = task.taskId;
    const starting = task.form?.attempt?.kind;
    if (task.taskKind === "sync-plan" && task.executionStarted && task.workPane === "verify") {
      showTaskPane(inventory.element, review.element);
      inventory.render(task);
      return;
    }
    if (task.taskKind === "sync-plan" && (starting === "sync-plan" || task.review !== null
        || task.reviewLoading || task.executionStarted || task.sessionId != null)) {
      showTaskPane(review.element, inventory.element);
      review.render(task);
      return;
    }
    if (starting === "inventory" || (task.taskKind === "inventory" && (task.inventoryReview != null
        || task.inventoryLoading || task.sessionReleased || task.sessionId != null || task.sessionState === "active"))) {
      review.dispose();
      show(inventory.element);
      inventory.render(task);
      return;
    }
    inventory.dispose();
    if (starting === "sync-plan" || task.review !== null || task.reviewLoading || task.executionStarted) {
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
    inventory.dispose();
    renderedTaskId = null;
    panel.ariaLabel = "Settings";
    show(settings);
  }

  render(null);
  return Object.freeze({ element: panel, render, renderSettings });
}
