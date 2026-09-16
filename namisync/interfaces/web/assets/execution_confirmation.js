import { renderText } from "./render.js";

const DISMISS_EVENTS = Object.freeze([
  "pointerdown", "pointerup", "click", "dblclick", "contextmenu", "wheel",
]);

function button(label, className) {
  const element = document.createElement("button");
  element.type = "button";
  element.className = className;
  renderText(element, label);
  return element;
}

export function createExecutionConfirmation(backgroundRoots) {
  if (!Array.isArray(backgroundRoots)
      || backgroundRoots.length === 0
      || !backgroundRoots.every((root) => root instanceof HTMLElement)) {
    throw new TypeError("execution confirmation requires page background roots");
  }

  const dialog = document.createElement("dialog");
  dialog.id = "execution-confirmation";
  dialog.className = "nami-dialog nami-execution-confirmation";
  dialog.setAttribute("aria-labelledby", "execution-confirmation-title");
  dialog.setAttribute(
    "aria-describedby",
    "execution-confirmation-consequence execution-confirmation-count",
  );

  const heading = document.createElement("h2");
  heading.id = "execution-confirmation-title";
  renderText(heading, "Confirm destructive changes");
  const consequence = document.createElement("p");
  consequence.id = "execution-confirmation-consequence";
  renderText(
    consequence,
    "These selected operations can replace or remove files. Review the count before continuing.",
  );
  const count = document.createElement("p");
  count.id = "execution-confirmation-count";
  count.className = "nami-execution-confirmation__count";
  const actions = document.createElement("div");
  actions.className = "nami-execution-confirmation__actions";
  const cancel = button("Cancel", "nami-button nami-button--secondary");
  cancel.dataset.cancelExecution = "";
  const confirm = button("Confirm and execute", "nami-button nami-button--primary");
  confirm.dataset.confirmExecution = "";
  actions.append(cancel, confirm);
  dialog.append(heading, consequence, count, actions);

  let current = null;
  let inertSnapshot = null;
  let overflowSnapshot = null;

  function restoreBackground() {
    if (inertSnapshot === null) return;
    for (const [root, inert] of inertSnapshot) root.inert = inert;
    inertSnapshot = null;
  }

  function restorePageScroll() {
    if (overflowSnapshot === null) return;
    const [value, priority] = overflowSnapshot;
    if (value === "") document.documentElement.style.removeProperty("overflow");
    else document.documentElement.style.setProperty("overflow", value, priority);
    overflowSnapshot = null;
  }

  function finishClose(state) {
    if (current !== state) return;
    dialog.close();
    delete dialog.dataset.closing;
    current = null;
    restoreBackground();
    restorePageScroll();
    if (
      state.returnFocus instanceof HTMLElement
      && state.returnFocus.isConnected
      && !state.returnFocus.disabled
    ) {
      state.returnFocus.focus();
    }
  }

  function closeAfterExit(state) {
    cancel.disabled = true;
    confirm.disabled = true;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (current !== state) return;
      dialog.dataset.closing = "true";
      const finiteAnimations = dialog.getAnimations().filter((animation) => {
        const endTime = animation.effect?.getComputedTiming().endTime;
        return Number.isFinite(endTime);
      });
      if (finiteAnimations.length === 0) {
        requestAnimationFrame(() => finishClose(state));
        return;
      }
      void Promise.allSettled(finiteAnimations.map((animation) => animation.finished))
        .then(() => finishClose(state));
    }));
  }

  function settle(kind) {
    const state = current;
    if (state === null || state.settled) return;
    state.settled = true;
    try {
      if (kind === "confirm") state.onConfirm();
      else state.onCancel();
    } finally {
      closeAfterExit(state);
    }
  }

  cancel.addEventListener("click", () => settle("cancel"));
  confirm.addEventListener("click", () => settle("confirm"));
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    settle("cancel");
  });
  for (const name of DISMISS_EVENTS) {
    dialog.addEventListener(name, (event) => {
      if (event.target !== dialog) return;
      event.preventDefault();
      event.stopPropagation();
    });
  }
  function show({ destructiveOperationCount, returnFocus, onCancel, onConfirm }) {
    if (
      current !== null
      || !Number.isSafeInteger(destructiveOperationCount)
      || destructiveOperationCount <= 0
      || !(returnFocus instanceof HTMLElement)
      || typeof onCancel !== "function"
      || typeof onConfirm !== "function"
    ) {
      throw new TypeError("execution confirmation request is invalid");
    }
    current = { onCancel, onConfirm, returnFocus, settled: false };
    inertSnapshot = backgroundRoots.map((root) => [root, root.inert]);
    overflowSnapshot = [
      document.documentElement.style.getPropertyValue("overflow"),
      document.documentElement.style.getPropertyPriority("overflow"),
    ];
    document.documentElement.style.setProperty("overflow", "hidden", "important");
    for (const root of backgroundRoots) root.inert = true;
    renderText(
      count,
      `${destructiveOperationCount} selected destructive operation${destructiveOperationCount === 1 ? "" : "s"}`,
    );
    cancel.disabled = false;
    confirm.disabled = false;
    delete dialog.dataset.closing;
    try {
      dialog.showModal();
    } catch (error) {
      current = null;
      restoreBackground();
      restorePageScroll();
      throw error;
    }
    cancel.focus();
  }

  return Object.freeze({ element: dialog, show });
}
