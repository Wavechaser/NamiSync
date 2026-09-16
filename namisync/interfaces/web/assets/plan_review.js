import { renderPlanRow } from "./plan.js";
import { renderFilesystemText, renderText } from "./render.js";

const FILTERS = Object.freeze([
  "copy", "mkdir", "move", "recase", "update", "move_update",
  "trash", "delete", "noop", "blocked", "notice",
]);
const WINDOW_LIMIT = 256;
const ROW_HEIGHT = 24;

function button(label, className = "nami-button") {
  const element = document.createElement("button");
  element.type = "button";
  element.className = className;
  renderText(element, label);
  return element;
}

function fieldLabel(label, control) {
  const field = document.createElement("label");
  field.className = "nami-plan-review__field";
  const text = document.createElement("span");
  text.className = "nami-field__label";
  renderText(text, label);
  field.append(text, control);
  return field;
}

function rowView(row, busy, committed) {
  const notes = row.notice ?? row.blocked_reason ?? row.selection_exclusion_reason
    ?? (row.move_peer_id === null ? row.reason ?? "" : `Paired move · ${row.reason ?? ""}`);
  const risk = `Risk: ${row.risk}`;
  const intent = row.operation_kind ?? (row.row_kind === "notice" ? "notice" : "");
  return {
    checked: row.selection === "selected",
    mixed: row.selection === "mixed",
    selectionDisabled: busy || committed || row.selection === "disabled",
    selectionLabel: `Select ${row.display}`,
    depth: row.depth,
    folder: row.row_kind === "folder" || row.row_kind === "prior-folder",
    expanded: row.expanded ?? false,
    nameText: row.display,
    sizeText: row.size === null ? "" : `${row.size} B`,
    intentText: intent.replaceAll("_", " "),
    intentKey: row.blocked_reason !== null
      ? "blocked"
      : row.row_kind === "notice" ? "" : intent,
    checksumText: row.dependency_count === 0 ? "" : `${row.dependency_count} deps`,
    notesText: notes === "" ? risk : `${risk} · ${notes}`,
  };
}

function addGroupDisclosure(element, row, onCollapse) {
  if (!row.is_container || row.row_kind === "folder" || row.row_kind === "prior-folder") {
    return;
  }
  const name = element.querySelector(".nami-file-row__name");
  const spacer = name?.querySelector(".nami-file-row__disclosure-spacer");
  if (!(name instanceof HTMLElement) || !(spacer instanceof HTMLElement)) return;
  const disclosure = button("", "nami-file-row__disclosure");
  disclosure.ariaExpanded = String(row.expanded);
  disclosure.ariaLabel = `${row.expanded ? "Collapse" : "Expand"} ${row.display}`;
  const chevron = document.createElement("span");
  chevron.className = "nami-file-row__chevron";
  chevron.ariaHidden = "true";
  disclosure.append(chevron);
  disclosure.addEventListener("click", () => onCollapse(row));
  spacer.replaceWith(disclosure);
}

export function createPlanReviewPanel(callbacks) {
  const required = [
    "onViewChange", "onWindow", "onSelect", "onExecute", "onControl", "onPlanAgain",
  ];
  if (callbacks === null || typeof callbacks !== "object"
      || !required.every((name) => typeof callbacks[name] === "function")) {
    throw new TypeError("plan review callbacks are incomplete");
  }

  const element = document.createElement("section");
  element.className = "nami-plan-review";
  const header = document.createElement("div");
  header.className = "nami-card nami-plan-review__summary";
  const heading = document.createElement("h2");
  renderText(heading, "Plan review");
  const paths = document.createElement("p");
  paths.className = "nami-plan-review__paths";
  const facts = document.createElement("p");
  facts.className = "nami-shell__guidance";
  header.append(heading, paths, facts);

  const toolbar = document.createElement("div");
  toolbar.className = "nami-card nami-plan-review__toolbar";
  const search = document.createElement("input");
  search.className = "nami-input";
  search.type = "search";
  search.placeholder = "Search this plan";
  search.autocomplete = "off";
  search.dataset.action = "plan-search";
  const sort = document.createElement("select");
  sort.className = "nami-select";
  sort.dataset.action = "plan-sort";
  for (const [value, label] of [
    ["path", "Path"], ["filename", "Filename"], ["size", "Size"], ["mtime", "Modified"],
  ]) {
    const option = document.createElement("option");
    option.value = value;
    renderText(option, label);
    sort.append(option);
  }
  const direction = document.createElement("select");
  direction.className = "nami-select";
  direction.dataset.action = "plan-sort-direction";
  for (const [value, label] of [["ascending", "Ascending"], ["descending", "Descending"]]) {
    const option = document.createElement("option");
    option.value = value;
    renderText(option, label);
    direction.append(option);
  }
  const reset = button("Reset view", "nami-button nami-button--secondary");
  reset.dataset.action = "plan-reset";
  const filters = document.createElement("details");
  filters.className = "nami-plan-review__filters";
  const filterSummary = document.createElement("summary");
  renderText(filterSummary, "Filter operations");
  const filterList = document.createElement("div");
  filterList.className = "nami-plan-review__filter-list";
  const filterInputs = new Map();
  for (const value of FILTERS) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = value;
    const text = document.createElement("span");
    renderText(text, value.replaceAll("_", " "));
    label.append(input, text);
    filterList.append(label);
    filterInputs.set(value, input);
  }
  filters.append(filterSummary, filterList);
  toolbar.append(
    fieldLabel("Search", search), fieldLabel("Sort by", sort),
    fieldLabel("Direction", direction), reset, filters,
  );

  const list = document.createElement("div");
  list.className = "nami-file-list nami-file-list__grid nami-plan-review__list";
  list.setAttribute("role", "grid");
  const columnHeader = document.createElement("div");
  columnHeader.className = "nami-file-list__header";
  columnHeader.setAttribute("role", "row");
  for (const label of ["Select", "Name", "Size", "Action", "Dependencies", "Notes"]) {
    const cell = document.createElement("div");
    cell.className = "nami-file-row__cell";
    cell.setAttribute("role", "columnheader");
    renderText(cell, label);
    columnHeader.append(cell);
  }
  const body = document.createElement("div");
  body.className = "nami-file-list__body nami-plan-review__rows";
  body.setAttribute("role", "rowgroup");
  list.append(columnHeader, body);

  const footer = document.createElement("div");
  footer.className = "nami-card nami-plan-review__actions";
  const execute = button("Execute", "nami-button nami-button--primary");
  execute.dataset.action = "execute";
  const planAgain = button("Plan again", "nami-button nami-button--secondary");
  planAgain.dataset.action = "plan-again";
  const pause = button("Pause", "nami-button nami-button--secondary");
  pause.dataset.action = "pause";
  const resume = button("Resume", "nami-button nami-button--secondary");
  resume.dataset.action = "resume";
  const cancel = button("Cancel", "nami-button nami-button--secondary");
  cancel.dataset.action = "cancel";
  const status = document.createElement("p");
  status.className = "nami-shell__guidance nami-plan-review__status";
  status.setAttribute("role", "status");
  status.ariaLive = "polite";
  const controls = document.createElement("div");
  controls.className = "nami-plan-review__control-group";
  controls.append(pause, resume, cancel);
  const primary = document.createElement("div");
  primary.className = "nami-plan-review__control-group";
  primary.append(planAgain, execute);
  footer.append(controls, primary, status);
  element.append(header, toolbar, list, footer);

  let current = null;
  let searchTimer = null;
  let scrollFramePending = false;
  let scrollGeneration = 0;
  let pendingWindowOffset = null;
  let renderedRows = null;
  const viewChange = (patch) => {
    if (current !== null) callbacks.onViewChange(current, patch);
  };
  search.addEventListener("input", () => {
    if (searchTimer !== null) clearTimeout(searchTimer);
    const scheduledReview = current;
    searchTimer = setTimeout(() => {
      searchTimer = null;
      if (current === scheduledReview) viewChange({ searchQuery: search.value });
    }, 150);
  });
  const activeFilters = () => new Set(
    [...filterInputs].filter(([, input]) => input.checked).map(([value]) => value),
  );
  for (const input of filterInputs.values()) {
    input.addEventListener("change", () => viewChange({ filters: activeFilters() }));
  }
  sort.addEventListener("change", () => viewChange({ sortColumn: sort.value }));
  direction.addEventListener("change", () => viewChange({ sortDirection: direction.value }));
  reset.addEventListener("click", () => viewChange({
    searchQuery: "", filters: new Set(), sortColumn: "path", sortDirection: "ascending",
  }));
  body.addEventListener("scroll", () => {
    scheduleViewportCheck();
  });
  const resizeObserver = new window.ResizeObserver(scheduleViewportCheck);
  resizeObserver.observe(body);

  function scheduleViewportCheck() {
    if (current === null || scrollFramePending) return;
    const generation = scrollGeneration;
    scrollFramePending = true;
    window.requestAnimationFrame(() => {
      scrollFramePending = false;
      if (current !== null && generation === scrollGeneration) reconcileViewport();
    });
  }

  function reconcileViewport() {
    if (body.clientHeight <= 0 || current.window.total <= 0) return;
    const viewportTop = Math.max(body.scrollTop, 0);
    const firstIndex = Math.min(
      Math.floor(viewportTop / ROW_HEIGHT),
      current.window.total - 1,
    );
    const lastIndex = Math.min(
      Math.max(
        Math.ceil((viewportTop + body.clientHeight) / ROW_HEIGHT) - 1,
        firstIndex,
      ),
      current.window.total - 1,
    );
    const windowEnd = current.window.offset + current.window.rows.length;
    if (firstIndex >= current.window.offset && lastIndex < windowEnd) {
      if (pendingWindowOffset !== null) {
        pendingWindowOffset = null;
        callbacks.onWindow(current, null);
      }
      return;
    }
    const offset = Math.max(0, firstIndex - 32);
    if (offset === current.window.offset) return;
    if (offset !== pendingWindowOffset) {
      pendingWindowOffset = offset;
      callbacks.onWindow(current, offset);
    }
  }
  execute.addEventListener("click", () => {
    if (current !== null) callbacks.onExecute(current, execute);
  });
  planAgain.addEventListener("click", () => {
    if (current !== null) callbacks.onPlanAgain(current);
  });
  pause.addEventListener("click", () => current !== null && callbacks.onControl(current, "pause"));
  resume.addEventListener("click", () => current !== null && callbacks.onControl(current, "resume"));
  cancel.addEventListener("click", () => current !== null && callbacks.onControl(current, "cancel"));

  function renderRows(review, task) {
    const disabled = review.pending !== null || task.executionAttempt !== null;
    const committed = review.summary.selection_state !== "reviewing";
    if (renderedRows?.review === review && renderedRows.window === review.window
        && renderedRows.disabled === disabled && renderedRows.committed === committed) return;
    renderedRows = { review, window: review.window, disabled, committed };
    const fragment = document.createDocumentFragment();
    const top = document.createElement("div");
    top.className = "nami-plan-review__spacer";
    top.style.setProperty("block-size", `${review.window.offset * ROW_HEIGHT}px`);
    fragment.append(top);
    for (const row of review.window.rows) {
      const element = document.createElement("div");
      renderPlanRow(element, rowView(
        row,
        disabled,
        committed,
      ));
      element.dataset.nodeId = row.node_id;
      element.ariaRowIndex = String(row.visible_index + 2);
      element.querySelector(".nami-checkbox")?.addEventListener("change", (event) => {
        callbacks.onSelect(review, row, event.currentTarget.checked);
      });
      element.querySelector(".nami-file-row__disclosure")?.addEventListener("click", () => {
        callbacks.onViewChange(review, {
          collapseNodeId: row.node_id, collapsed: row.expanded === true,
        });
      });
      addGroupDisclosure(element, row, () => callbacks.onViewChange(review, {
        collapseNodeId: row.node_id, collapsed: row.expanded === true,
      }));
      fragment.append(element);
    }
    const bottom = document.createElement("div");
    bottom.className = "nami-plan-review__spacer";
    const remaining = Math.max(0, review.window.total - review.window.offset - review.window.rows.length);
    bottom.style.setProperty("block-size", `${remaining * ROW_HEIGHT}px`);
    fragment.append(bottom);
    body.replaceChildren(fragment);
  }

  function render(task) {
    if (current !== task.review) {
      if (searchTimer !== null) clearTimeout(searchTimer);
      searchTimer = null;
      scrollGeneration += 1;
      scrollFramePending = false;
      pendingWindowOffset = null;
      body.scrollTop = (task.review?.window.offset ?? 0) * ROW_HEIGHT;
    }
    const previousWindow = renderedRows?.window ?? null;
    current = task.review;
    if (current === null) {
      delete element.dataset.pending;
      renderText(paths, "Loading reviewed plan…");
      renderText(facts, task.error ?? "Waiting for the completed plan to become available.");
      body.replaceChildren();
      renderedRows = null;
      toolbar.hidden = true;
      footer.hidden = true;
      return;
    }
    const review = current;
    if (review.window !== previousWindow) pendingWindowOffset = null;
    element.dataset.pending = review.pending ?? "";
    list.ariaRowCount = String(review.window.total + 1);
    toolbar.hidden = false;
    footer.hidden = false;
    renderFilesystemText(paths, `${review.summary.source_path} → ${review.summary.target_path}`);
    const verdict = review.summary.preflight_ready
      ? "Review preflight ready"
      : `${review.summary.preflight_refusal_count} review preflight refusal(s)`;
    renderText(
      facts,
      `${review.summary.selected_operation_count} of ${review.summary.selectable_operation_count} selected · ${review.summary.destructive_operation_count} destructive · ${review.summary.required_bytes} B required · ${review.summary.visible_row_count} visible · ${verdict} · ${review.summary.warning_count} scan notice(s)`,
    );
    if (document.activeElement !== search) search.value = review.summary.search_query;
    sort.value = review.summary.sort_column;
    direction.value = review.summary.sort_direction;
    direction.disabled = review.pending !== null || sort.value === "path";
    reset.disabled = review.pending !== null;
    search.disabled = review.pending !== null;
    sort.disabled = review.pending !== null;
    for (const [value, input] of filterInputs) {
      input.checked = review.summary.filters.includes(value);
      input.disabled = review.pending !== null;
    }
    const activeExecution = task.executionStarted && task.sessionState === "active";
    const retryExecution = task.executionAttempt?.state === "uncertain";
    execute.hidden = review.summary.selection_state !== "reviewing";
    renderText(execute, retryExecution ? "Retry execute" : "Execute");
    execute.disabled = review.pending !== null
      || (task.executionAttempt !== null && !retryExecution)
      || (!retryExecution && review.summary.selected_operation_count === 0);
    planAgain.disabled = review.pending !== null || task.canPlanAgain !== true;
    controls.hidden = !activeExecution;
    pause.hidden = task.executionControlState === "paused";
    resume.hidden = task.executionControlState !== "paused";
    pause.disabled = review.pending !== null || task.executionControlState !== "running";
    resume.disabled = review.pending !== null || task.executionControlState !== "paused";
    cancel.disabled = review.pending !== null || task.executionControlState === "canceling";
    renderText(status, review.message ?? "");
    renderRows(review, task);
    scheduleViewportCheck();
  }

  function dispose() {
    resizeObserver.disconnect();
    if (searchTimer !== null) clearTimeout(searchTimer);
    searchTimer = null;
    scrollGeneration += 1;
    scrollFramePending = false;
    pendingWindowOffset = null;
    current = null;
    renderedRows = null;
  }

  return Object.freeze({ element, render, dispose });
}
