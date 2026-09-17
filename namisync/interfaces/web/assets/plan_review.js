import { renderPlanRow } from "./plan.js";
import { createIcon } from "./icons.js";
import { formatByteCount, renderFilesystemText, renderText } from "./render.js";

const FILTERS = Object.freeze([
  "all", "copy", "move", "update", "trash", "mkdir", "recase",
  "move_update", "delete", "noop", "blocked", "notice",
]);
const ALWAYS_VISIBLE_FILTERS = new Set(["all", "copy", "move", "update", "trash"]);
const WINDOW_LIMIT = 256;
const ROW_HEIGHT = 24;

function button(label, className = "nami-button") {
  const element = document.createElement("button");
  element.type = "button";
  element.className = className;
  renderText(element, label);
  return element;
}

function rowView(row, busy, committed) {
  const notes = row.notice ?? row.blocked_reason ?? row.selection_exclusion_reason
    ?? (row.move_peer_id === null ? row.reason ?? "" : `Paired move · ${row.reason ?? ""}`);
  const risk = `Risk: ${row.risk}`;
  const intent = row.operation_kind ?? (row.row_kind === "notice" ? "notice" : "");
  const dependencies = row.dependency_count === 0 ? "" : `${row.dependency_count} deps · `;
  const modified = row.mtime_ns === null ? "" : (() => {
    const date = new Date(Number(BigInt(row.mtime_ns) / 1000000n));
    const pad = (value) => String(value).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  })();
  return {
    checked: row.selection === "selected",
    mixed: row.selection === "mixed",
    selectionDisabled: busy || committed || row.selection === "disabled",
    selectionLabel: `Select ${row.display}`,
    depth: row.depth,
    folder: row.row_kind === "folder" || row.row_kind === "prior-folder",
    expanded: row.expanded ?? false,
    nameText: row.display,
    sizeText: row.size === null ? "" : formatByteCount(row.size),
    intentText: intent.replaceAll("_", " "),
    intentKey: row.blocked_reason !== null
      ? "blocked"
      : row.row_kind === "notice" ? "" : intent,
    checksumText: "",
    modifiedText: modified,
    notesText: `${dependencies}${notes === "" ? risk : `${risk} · ${notes}`}`,
  };
}

function eventInControl(event, row) {
  let target = event.target;
  while (target !== null && target !== row) {
    if (target.classList?.contains("nami-checkbox")
      || target.classList?.contains("nami-file-row__disclosure")) return true;
    target = target.parentElement;
  }
  return false;
}

function setHighlighted(element, highlighted) {
  element.dataset.highlighted = String(highlighted);
  element.classList.toggle?.("nami-file-row--highlighted", highlighted);
  if (element.classList.toggle === undefined) {
    const classes = new Set(element.className.split(/\s+/).filter(Boolean));
    if (highlighted) classes.add("nami-file-row--highlighted");
    else classes.delete("nami-file-row--highlighted");
    element.className = [...classes].join(" ");
  }
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
    "onViewChange", "onWindow", "onSelect", "onScopeSelect", "onExecute", "onControl", "onPlanAgain",
    "onHighlight", "onHighlightedSelect",
  ];
  if (callbacks === null || typeof callbacks !== "object"
      || !required.every((name) => typeof callbacks[name] === "function")) {
    throw new TypeError("plan review callbacks are incomplete");
  }

  const element = document.createElement("section");
  element.className = "nami-plan-review";
  const header = document.createElement("div");
  header.className = "nami-card nami-plan-review__plan";
  const paths = document.createElement("div");
  paths.className = "nami-plan-review__paths";
  const sourcePath = document.createElement("p");
  sourcePath.className = "nami-plan-review__path nami-plan-review__path--source";
  const targetPath = document.createElement("p");
  targetPath.className = "nami-plan-review__path nami-plan-review__path--target";
  paths.append(sourcePath, targetPath);
  const settings = document.createElement("p");
  settings.className = "nami-shell__guidance";
  const viewSwitcher = document.createElement("div");
  viewSwitcher.className = "nami-segmented nami-plan-review__view-switcher";
  for (const [label, selected] of [["Sync", true], ["Integrity", false]]) {
    const option = button(label, "nami-segmented__item");
    option.ariaChecked = String(selected);
    option.setAttribute("role", "radio");
    option.disabled = !selected;
    viewSwitcher.append(option);
  }
  header.append(viewSwitcher, paths, settings);
  const summary = document.createElement("div");
  summary.className = "nami-card nami-plan-review__summary";
  const statusTitle = document.createElement("p");
  statusTitle.className = "nami-plan-review__status-title";
  statusTitle.setAttribute("role", "status");
  const facts = document.createElement("p");
  facts.className = "nami-shell__guidance nami-plan-review__status-summary";
  const progress = document.createElement("div");
  progress.className = "nami-progress nami-progress--inline nami-plan-review__progress";
  progress.ariaHidden = "true";
  const progressBar = document.createElement("div");
  progressBar.className = "nami-progress__bar";
  progress.append(progressBar);
  summary.append(statusTitle, facts, progress);

  const tableCard = document.createElement("div");
  tableCard.className = "nami-card nami-plan-review__table-card";

  const toolbar = document.createElement("div");
  toolbar.className = "nami-plan-review__toolbar";
  const search = document.createElement("input");
  search.className = "nami-input";
  search.type = "search";
  search.placeholder = "Search this plan";
  search.autocomplete = "off";
  search.ariaLabel = "Search this plan";
  search.dataset.action = "plan-search";
  const filters = document.createElement("div");
  filters.className = "nami-plan-review__filters";
  const filterList = document.createElement("div");
  filterList.className = "nami-plan-review__filter-list";
  const filterButtons = new Map();
  for (const value of FILTERS) {
    const filter = button(value.replaceAll("_", " "), "nami-button nami-plan-review__filter");
    filter.dataset.operation = value;
    filter.ariaPressed = "false";
    filterList.append(filter);
    filterButtons.set(value, filter);
  }
  filters.append(filterList);
  toolbar.append(filters, search);

  const list = document.createElement("div");
  list.className = "nami-file-list nami-table-scroll nami-plan-review__list";
  list.setAttribute("role", "table");
  list.ariaLabel = "Reviewed plan";
  const grid = document.createElement("div");
  grid.className = "nami-file-list__grid nami-file-list__grid--plan nami-table-layout";
  const columnHeader = document.createElement("div");
  columnHeader.className = "nami-file-list__header nami-table__header";
  columnHeader.setAttribute("role", "row");
  const sortHeaders = new Map();
  const columnNames = ["selection", "name", "size", "primary", "secondary", "modified", "notes"];
  for (const [index, [label, column]] of [
    ["Select", null], ["Name", "filename"], ["Size", "size"],
    ["Action", null], ["Checksum", null], ["Modified", "mtime"], ["Notes", null],
  ].entries()) {
    const cell = document.createElement("div");
    cell.className = "nami-file-list__header-cell";
    cell.setAttribute("role", "columnheader");
    if (index === 0) {
      const selectAll = document.createElement("input");
      selectAll.className = "nami-checkbox nami-plan-review__scope-checkbox";
      selectAll.type = "checkbox";
      selectAll.ariaLabel = "Select all operations in the current view";
      cell.append(selectAll);
      selectAll.addEventListener("change", () => {
        if (current !== null) callbacks.onScopeSelect(current, selectAll.checked);
      });
    } else if (column === null) {
      renderText(cell, label);
    } else {
      const sortButton = button("", "nami-plan-review__sort");
      sortButton.dataset.sortColumn = column;
      const text = document.createElement("span");
      renderText(text, label);
      const up = createIcon(document, "chevron-up", "sm");
      const down = createIcon(document, "chevron-down", "sm");
      up.hidden = true;
      down.hidden = true;
      sortButton.append(text, up, down);
      cell.append(sortButton);
      sortHeaders.set(column, { cell, sortButton, up, down });
    }
    if (index < columnNames.length - 1) {
      const resizer = document.createElement("div");
      resizer.className = "nami-file-list__column-resizer";
      resizer.dataset.columnIndex = String(index);
      resizer.dataset.column = columnNames[index];
      resizer.setAttribute("role", "separator");
      resizer.ariaOrientation = "vertical";
      resizer.ariaLabel = `Resize ${label} column`;
      resizer.tabIndex = 0;
      cell.append(resizer);
    }
    columnHeader.append(cell);
  }
  const body = document.createElement("div");
  body.className = "nami-file-list__body nami-table__body nami-plan-review__rows";
  body.setAttribute("role", "rowgroup");
  grid.append(columnHeader, body);
  list.append(grid);

  const footer = document.createElement("div");
  footer.className = "nami-plan-review__actions";
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
  tableCard.append(toolbar, list, footer);
  element.append(header, summary, tableCard);

  let current = null;
  let searchTimer = null;
  let scrollFramePending = false;
  let scrollGeneration = 0;
  let pendingWindowOffset = null;
  let renderedRows = null;
  const renderedText = new WeakMap();
  function updateText(node, value, filesystem = false) {
    if (renderedText.get(node) === value) return;
    renderedText.set(node, value);
    if (filesystem) renderFilesystemText(node, value);
    else renderText(node, value);
  }
  const headerCells = [...columnHeader.children];
  const scopeCheckbox = columnHeader.querySelector(".nami-plan-review__scope-checkbox");
  const resizers = headerCells.slice(0, -1).map(
    (cell) => cell.querySelector(".nami-file-list__column-resizer"),
  );
  const columnMinimums = [2, 12, 5, 8, 7, 7, 14];
  let columnWidths = null;
  let finishResize = null;

  function minimumWidth(index) {
    return columnMinimums[index] * parseFloat(getComputedStyle(document.documentElement).fontSize);
  }

  function applyColumnWidths() {
    if (columnWidths === null) return;
    for (const [index, name] of columnNames.entries()) {
      if (name === "name") continue;
      grid.style.setProperty(`--nami-file-column-${name}`, `${columnWidths[index].toFixed(3)}px`);
    }
    grid.dataset.columnsFrozen = "true";
  }

  function refreshResizers() {
    const notesWidth = columnWidths?.[6] ?? headerCells[6].getBoundingClientRect().width;
    for (const resizer of resizers) {
      const index = Number(resizer.dataset.columnIndex);
      const currentWidth = headerCells[index].getBoundingClientRect().width;
      resizer.ariaValueMin = String(Math.round(minimumWidth(index)));
      resizer.ariaValueMax = String(Math.round(currentWidth + Math.max(0, notesWidth - minimumWidth(6))));
      resizer.ariaValueNow = String(Math.round(currentWidth));
    }
  }

  function freezeColumns() {
    if (columnWidths !== null) return;
    columnWidths = headerCells.map((cell) => cell.getBoundingClientRect().width);
    applyColumnWidths();
  }

  function resizeColumn(index, requestedDelta, startWidths, startNameWidth) {
    const minimumDelta = index === 1
      ? minimumWidth(1) - startNameWidth
      : minimumWidth(index) - startWidths[index];
    const maximumDelta = startWidths[6] - minimumWidth(6);
    const delta = Math.max(minimumDelta, Math.min(maximumDelta, requestedDelta));
    columnWidths = [...startWidths];
    if (index !== 1) columnWidths[index] += delta;
    columnWidths[6] -= delta;
    applyColumnWidths();
    refreshResizers();
  }

  for (const resizer of resizers) {
    const index = Number(resizer.dataset.columnIndex);
    resizer.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      freezeColumns();
      const startX = event.clientX;
      const startWidths = [...columnWidths];
      const startNameWidth = headerCells[1].getBoundingClientRect().width;
      const move = (moveEvent) => resizeColumn(
        index, moveEvent.clientX - startX, startWidths, startNameWidth,
      );
      finishResize?.();
      finishResize = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", finishResize);
        finishResize = null;
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", finishResize);
    });
    resizer.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      freezeColumns();
      resizeColumn(index, event.key === "ArrowRight" ? 8 : -8,
        [...columnWidths], headerCells[1].getBoundingClientRect().width);
    });
  }
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
    [...filterButtons].filter(([value, filter]) => value !== "all" && filter.ariaPressed === "true")
      .map(([value]) => value),
  );
  for (const [value, filter] of filterButtons) {
    filter.addEventListener("click", () => {
      if (value === "all") {
        for (const [key, button] of filterButtons) button.ariaPressed = String(key === "all");
        viewChange({ filters: new Set() });
      } else {
        filter.ariaPressed = String(filter.ariaPressed !== "true");
        const selected = activeFilters();
        filterButtons.get("all").ariaPressed = String(selected.size === 0);
        viewChange({ filters: selected });
      }
    });
  }
  for (const [column, { sortButton }] of sortHeaders) {
    sortButton.addEventListener("click", () => {
      const same = current?.summary.sort_column === column;
      const descending = same && current.summary.sort_direction === "descending";
      viewChange(descending
        ? { sortColumn: "path", sortDirection: "ascending" }
        : { sortColumn: column, sortDirection: same ? "descending" : "ascending" });
    });
  }
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
    const highlightRevision = review.summary.highlight_revision ?? review.window.highlight_revision ?? 0;
    const focusedRow = document.activeElement?.dataset?.nodeId !== undefined;
    const focusNodeId = review.summary.highlight_focus_node_id;
    if (renderedRows?.review === review && renderedRows.window === review.window
    ) {
      if (renderedRows.disabled !== disabled || renderedRows.committed !== committed) {
        for (const [index, checkbox] of renderedRows.checkboxes.entries()) {
          if (checkbox !== null) checkbox.disabled = disabled || committed
            || review.window.rows[index].selection === "disabled";
        }
        renderedRows.disabled = disabled;
        renderedRows.committed = committed;
      }
      if (renderedRows.highlightRevision !== highlightRevision) {
        for (const [index, row] of review.window.rows.entries()) {
          const rendered = renderedRows.rows[index];
          if (rendered === undefined) continue;
          setHighlighted(rendered, row.highlighted === true);
          rendered.ariaSelected = String(row.highlighted === true);
          rendered.tabIndex = row.node_id === (focusNodeId ?? review.window.rows[0]?.node_id) ? 0 : -1;
        }
        if (focusedRow) renderedRows.rows.find((row) => row.dataset.nodeId === focusNodeId)?.focus?.();
        renderedRows.highlightRevision = highlightRevision;
      }
      return;
    }
    const checkboxes = [];
    const rowElements = [];
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
      element.tabIndex = row.node_id === (focusNodeId ?? review.window.rows[0]?.node_id) ? 0 : -1;
      element.ariaSelected = String(row.highlighted === true);
      setHighlighted(element, row.highlighted === true);
      const checkbox = element.querySelector(".nami-checkbox");
      checkboxes.push(checkbox ?? null);
      checkbox?.addEventListener("change", (event) => {
        if (element.dataset.highlighted === "true") {
          callbacks.onHighlightedSelect(review, event.currentTarget.checked);
        } else {
          callbacks.onSelect(review, row, event.currentTarget.checked);
        }
      });
      element.addEventListener("click", (event) => {
        if (eventInControl(event, element)) return;
        const modified = event.ctrlKey || event.metaKey;
        const gesture = event.shiftKey ? (modified ? "add-range" : "extend")
          : modified ? "toggle" : "replace";
        callbacks.onHighlight(review, gesture, row.node_id);
        element.focus?.();
      });
      element.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          callbacks.onHighlight(review, "clear", null);
        } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
          event.preventDefault();
          const direction = event.key === "ArrowUp" ? "move_up" : "move_down";
          const gesture = event.shiftKey ? `${direction}_extend` : direction;
          callbacks.onHighlight(review, gesture, row.node_id);
        }
      });
      element.querySelector(".nami-file-row__disclosure")?.addEventListener("click", () => {
        callbacks.onViewChange(review, {
          collapseNodeId: row.node_id, collapsed: row.expanded === true,
        });
      });
      addGroupDisclosure(element, row, () => callbacks.onViewChange(review, {
        collapseNodeId: row.node_id, collapsed: row.expanded === true,
      }));
      rowElements.push(element);
      fragment.append(element);
    }
    const bottom = document.createElement("div");
    bottom.className = "nami-plan-review__spacer";
    const remaining = Math.max(0, review.window.total - review.window.offset - review.window.rows.length);
    bottom.style.setProperty("block-size", `${remaining * ROW_HEIGHT}px`);
    fragment.append(bottom);
    body.replaceChildren(fragment);
    if (focusedRow) rowElements.find((row) => row.dataset.nodeId === focusNodeId)?.focus?.();
    renderedRows = {
      review, window: review.window, disabled, committed, checkboxes,
      rows: rowElements,
      highlightRevision,
    };
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
      updateText(sourcePath, "Loading reviewed plan…");
      updateText(targetPath, "");
      updateText(settings, "");
      updateText(facts, task.error ?? "Waiting for the completed plan to become available.");
      updateText(statusTitle, task.error ? "Plan unavailable" : "Loading plan");
      summary.dataset.status = task.error ? "attention" : "working";
      progress.classList.remove?.("nami-progress--indeterminate");
      progress.style.setProperty("--nami-progress-value", "0%");
      body.replaceChildren();
      renderedRows = null;
      tableCard.hidden = true;
      return;
    }
    const review = current;
    if (review.window !== previousWindow) pendingWindowOffset = null;
    element.dataset.pending = review.pending ?? "";
    list.ariaRowCount = String(review.window.total + 1);
    tableCard.hidden = false;
    updateText(sourcePath, `Source: ${review.summary.source_path}`, true);
    updateText(targetPath, `Target: ${review.summary.target_path}`, true);
    const options = task.form?.options;
    updateText(settings, options === null || options === undefined
      ? "Reviewed settings unavailable"
      : `Deletion: ${options.deletion_policy === "additive" ? "additive" : "trash"} · Replaced files: ${options.trash_on_update ? "trash" : "replace"} · Preserve: ${[
        options.preservation.preserve_created && "creation time",
        options.preservation.preserve_acl && "ACL",
        options.preservation.preserve_ads && "alternate streams",
      ].filter(Boolean).join(", ") || "none"} · Source casing: ${options.propagate_source_casing ? "on" : "off"} · Verify after execution: ${options.verify_after_execute ? "on" : "off"} · Exclusions: ${options.filters.length === 0 ? "none" : options.filters.join(", ")}`, true);
    const verdict = review.summary.preflight_ready
      ? "Review preflight ready"
      : `${review.summary.preflight_refusal_count} review preflight refusal(s)`;
    updateText(
      facts,
      `${review.summary.selected_operation_count} of ${review.summary.selectable_operation_count} selected · ${review.summary.destructive_operation_count} destructive · ${formatByteCount(review.summary.required_bytes)} required · ${review.summary.visible_row_count} visible · ${verdict} · ${review.summary.warning_count} scan notice(s)`,
    );
    const executionState = task.executionStarted ? task.sessionState : null;
    const canExecuteSelection = review.summary.preflight_ready
      && review.summary.selected_operation_count > 0
      && review.summary.selection_state === "reviewing";
    const statusLabel = executionState === "active" ? "Executing"
      : executionState === "completed" ? "Complete"
        : executionState === "failed" || executionState === "refused" ? "Error"
          : executionState !== null ? executionState.charAt(0).toUpperCase() + executionState.slice(1)
            : !review.summary.preflight_ready ? "Plan needs attention"
              : canExecuteSelection ? "Ready to execute" : "Plan ready";
    updateText(statusTitle, statusLabel);
    summary.dataset.status = executionState ?? (!review.summary.preflight_ready
      ? "attention" : canExecuteSelection ? "ready" : "plan");
    const progressValue = task.executionStarted && Number.isFinite(task.executionProgress)
      ? Math.max(0, Math.min(100, task.executionProgress))
      : 0;
    progress.dataset.lifecycle = executionState ?? "completed";
    if (executionState === "active") {
      progress.classList.add("nami-progress--indeterminate");
    } else {
      progress.classList.remove?.("nami-progress--indeterminate");
    }
    progress.style.setProperty("--nami-progress-value", `${progressValue}%`);
    if (document.activeElement !== search) search.value = review.summary.search_query;
    search.disabled = review.pending !== null && review.pending !== "view";
    for (const [column, { cell, sortButton, up, down }] of sortHeaders) {
      const active = review.summary.sort_column === column;
      const direction = active ? review.summary.sort_direction : null;
      cell.ariaSort = direction ?? "none";
      up.hidden = direction !== "ascending";
      down.hidden = direction !== "descending";
      sortButton.disabled = review.pending !== null;
    }
    for (const [value, filter] of filterButtons) {
      const active = value === "all"
        ? review.summary.filters.length === 0
        : review.summary.filters.includes(value);
      const count = review.summary.filter_counts?.[value] ?? 0;
      filter.ariaPressed = String(active);
      filter.disabled = review.pending !== null;
      filter.hidden = !ALWAYS_VISIBLE_FILTERS.has(value) && count === 0;
      filter.dataset.trashAlert = String(value === "trash" && !active && count > 1);
      updateText(filter, `${value.replaceAll("_", " ")} ${count}`);
    }
    if (scopeCheckbox instanceof HTMLInputElement) {
      const scopeSelectable = review.summary.scope_selectable_operation_count;
      const scopeSelected = review.summary.scope_selected_operation_count;
      const scopeAvailable = Number.isSafeInteger(scopeSelectable)
        && Number.isSafeInteger(scopeSelected)
        && scopeSelectable > 0;
      scopeCheckbox.disabled = review.pending !== null
        || review.summary.selection_state !== "reviewing"
        || !scopeAvailable;
      scopeCheckbox.checked = scopeAvailable && scopeSelected === scopeSelectable;
      scopeCheckbox.indeterminate = scopeAvailable
        && scopeSelected > 0 && scopeSelected < scopeSelectable;
    }
    const activeExecution = task.executionStarted && task.sessionState === "active";
    const retryExecution = task.executionAttempt?.state === "uncertain";
    execute.hidden = review.summary.selection_state !== "reviewing";
    updateText(execute, retryExecution ? "Retry execute" : "Execute");
    execute.disabled = review.pending !== null
      || (task.executionAttempt !== null && !retryExecution)
      || (!retryExecution && !canExecuteSelection);
    planAgain.disabled = review.pending !== null || task.canPlanAgain !== true;
    controls.hidden = !activeExecution;
    pause.hidden = task.executionControlState === "paused";
    resume.hidden = task.executionControlState !== "paused";
    pause.disabled = review.pending !== null || task.executionControlState !== "running";
    resume.disabled = review.pending !== null || task.executionControlState !== "paused";
    cancel.disabled = review.pending !== null || task.executionControlState === "canceling";
    updateText(status, review.message ?? "");
    renderRows(review, task);
    refreshResizers();
    scheduleViewportCheck();
  }

  function dispose() {
    finishResize?.();
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
