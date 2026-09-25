import { renderPlanRow } from "./plan.js";
import { createIcon } from "./icons.js";
import { formatByteCount, renderFilesystemText, renderText } from "./render.js";
import {
  isCapacityOnlyExecution,
  projectActiveOperationProgress,
  taskStatusDigest,
  terminalStatusLine,
} from "./task_status.js";

const FILTERS = Object.freeze([
  "all", "copy", "move", "update", "remove", "error", "noop", "notice",
]);
const FILTER_GROUPS = Object.freeze({
  copy: ["copy", "mkdir"], move: ["move", "recase"],
  update: ["update", "move_update"], remove: ["trash", "delete"],
  error: ["error", "unsupported", "blocked"],
});
const ALWAYS_VISIBLE_FILTERS = new Set(["all", "copy", "move", "update", "remove"]);
const WINDOW_LIMIT = 256;
const ROW_HEIGHT = 24;
const DISPLAY_LABELS = Object.freeze({
  all: "All", copy: "Copy", move: "Move", update: "Update", remove: "Remove",
  error: "Error", noop: "No change", notice: "Notice", mkdir: "Create folder",
  recase: "Change name casing", move_update: "Move + update", trash: "Move to trash",
  delete: "Delete permanently", unsupported: "Unsupported", blocked: "Blocked",
});
const REASON_LABELS = Object.freeze({
  source_only: "Only in source", metadata_match: "Metadata matches",
  metadata_changed: "File metadata changed", identity_rename: "Moved file",
  identity_rename_changed: "Moved file with changed metadata",
  required_directory: "Required folder", empty_directory: "Empty folder",
  target_only: "Only in target", directory_cleanup: "Remove unneeded folder",
  unsupported: "Unsupported item", case_mismatch: "Name casing differs",
  unicode_normalization_mismatch: "Unicode name normalization differs",
  case_collision: "Conflicting name casing", type_collision: "File/folder conflict",
  policy_collision: "Naming policy conflict", destination_collision: "Destination conflict",
  blocked_dependency: "Required operation is blocked",
  "blocked-dependency": "Required operation is blocked",
  "blocked-correspondence": "File matching is blocked",
  "incomplete-scan": "Scan incomplete", "user-deselected": "Deselected",
});
// Only redundant low-risk operation reasons are hidden; new values stay visible.
const HIDDEN_REASONS = new Set([
  "source_only", "metadata_match", "identity_rename", "required_directory", "empty_directory",
]);
const displayLabel = (value) => Object.prototype.hasOwnProperty.call(DISPLAY_LABELS, value) ? DISPLAY_LABELS[value] : value;
const reasonLabel = (value) => Object.prototype.hasOwnProperty.call(REASON_LABELS, value) ? REASON_LABELS[value] : value;

const EXECUTION_LABELS = Object.freeze({
  succeeded: "Completed", skipped: "Skipped", failed: "Failed", canceled: "Canceled",
  deferred: "Deferred", blocked: "Blocked", verified: "Verified", baselined: "Baselined",
  mismatched: "Mismatch", modified: "Modified", missing: "Missing", unsupported: "Unsupported",
  error: "Error", "recorded-copy": "Recorded copy", "already-verified": "Already verified",
  unrecorded: "Unrecorded", superseded: "Superseded", "not-applicable": "Not applicable",
  "not-run": "Not run", incomplete: "Incomplete", degraded: "Degraded", ok: "OK",
});
const executionLabel = (value) => Object.prototype.hasOwnProperty.call(EXECUTION_LABELS, value)
  ? EXECUTION_LABELS[value]
  : typeof value === "string"
    ? value.replaceAll("_", " ").replaceAll("-", " ").replace(/^./, (first) => first.toUpperCase())
    : "Unknown";

function operationLifecycle(operation) {
  if (operation === null) return null;
  if (operation.result === "succeeded" || operation.result === "skipped") return "completed";
  if (operation.result === "canceled") return "canceled";
  if (operation.result === "deferred") return "incomplete";
  if (operation.result === "failed" && operation.reason === "disk-capacity") return "capacity";
  if (operation.result === "failed" || operation.result === "blocked") return "failed";
  return null;
}

export function projectExecutionRow(execution) {
  if (execution === null) return { lifecycle: null, intent: null, checksum: "", notes: [] };
  const operation = execution.operation;
  const automatic = execution.automatic_verification;
  const evidence = execution.evidence;
  const notes = [];
  if (operation !== null) {
    notes.push(`Operation: ${executionLabel(operation.result)}${operation.reason === null ? "" : ` (${executionLabel(operation.reason)})`}`);
    if (operation.recording !== "ok") {
      notes.push(`Recording: ${executionLabel(operation.recording)}${operation.recording_reason === null ? "" : ` (${executionLabel(operation.recording_reason)})`}`);
    }
    if (operation.detail_omitted_count > 0) notes.push(`${operation.detail_omitted_count} operation details omitted`);
  }
  if (automatic !== null) {
    notes.push(`Automatic verification: ${executionLabel(automatic.result)}${automatic.reason === null ? "" : ` (${executionLabel(automatic.reason)})`}`);
    if (automatic.recording !== "ok") notes.push(`Verification recording: ${executionLabel(automatic.recording)}`);
    if (automatic.detail_omitted_count > 0) notes.push(`${automatic.detail_omitted_count} verification details omitted`);
  }
  if (evidence !== null) notes.push(`Stored evidence: ${executionLabel(evidence.state)}`);
  return {
    lifecycle: operationLifecycle(operation),
    intent: operation === null ? null : executionLabel(operation.result),
    checksum: evidence?.content?.digest?.slice(0, 8) ?? "",
    notes,
  };
}

export function projectExecutionSummary(execution) {
  const result = execution.result;
  if (result === null) {
    return execution.session_id === null
      ? { title: null, status: null }
      : { title: "Execution in progress", status: "executing" };
  }
  if (result.disposition === "unrun") return { title: "Execution did not start", status: "error" };
  const capacityOnly = isCapacityOnlyExecution(execution, result);
  if (capacityOnly) return { title: "Execution stopped: more target space is needed", status: "attention" };
  const labels = {
    failed: ["Execution failed", "error"], partial: ["Execution needs review", "error"],
    refused: ["Execution did not start", "error"], mismatch: ["Verification mismatch", "error"],
    canceled: ["Execution canceled", "canceled"],
    "verification-incomplete": ["Verification incomplete", "attention"],
    degraded: ["Execution completed with issues", "attention"],
    "all-noop": ["Execution completed", "completed"], success: ["Execution completed", "completed"],
  };
  const [title, status] = labels[result.headline] ?? ["Execution needs review", "error"];
  return { title, status };
}

function button(label, className = "nami-button") {
  const element = document.createElement("button");
  element.type = "button";
  element.className = className;
  renderText(element, label);
  return element;
}

function countedButton(label, className) {
  const element = button("", className);
  const text = document.createElement("span");
  renderText(text, label);
  const count = document.createElement("span");
  count.className = "nami-filter-count";
  element.append(text, count);
  return element;
}

function rowView(row, busy, committed, progressPresentation = null) {
  const hideReason = row.risk === "none" && row.blocked_reason === null
    && row.selection_exclusion_reason === null && HIDDEN_REASONS.has(row.reason);
  const reason = hideReason ? null : reasonLabel(row.reason);
  const execution = projectExecutionRow(row.execution);
  const notes = [...new Set([
    row.notice, reasonLabel(row.blocked_reason), reasonLabel(row.selection_exclusion_reason),
    row.move_peer_id === null ? null : row.row_kind.startsWith("prior-") ? "Previous location" : "Paired move",
    reason, ...execution.notes,
  ].filter((value) => typeof value === "string" && value !== ""))].join(" · ");
  const risk = row.risk === "none" ? "" : `Risk: ${row.risk}`;
  const intent = row.operation_kind ?? (row.row_kind === "notice" ? "notice" : "");
  const modified = row.mtime_ns === null ? "" : (() => {
    const date = new Date(Number(BigInt(row.mtime_ns) / 1000000n));
    const pad = (value) => String(value).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  })();
  const activeProgress = projectActiveOperationProgress(progressPresentation, row.operation_id);
  const lifecycle = activeProgress?.lifecycleKey ?? execution.lifecycle;
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
    intentText: execution.intent ?? displayLabel(intent),
    intentKey: lifecycle !== null ? "" : row.blocked_reason !== null
      ? "blocked"
      : row.row_kind === "notice" ? "" : intent,
    ...(lifecycle === null ? {} : { lifecycleKey: lifecycle }),
    ...(activeProgress ?? {}),
    checksumText: execution.checksum,
    modifiedText: modified,
    notesText: notes === "" ? risk : risk === "" ? notes : `${risk} · ${notes}`,
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
    "onHighlight", "onHighlightedSelect", "onExecutionDetail", "onFollowOverride", "onNavigateCurrent",
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
  const sourceValue = document.createElement("span");
  const targetValue = document.createElement("span");
  for (const [row, value, label] of [[sourcePath, sourceValue, "Source:"], [targetPath, targetValue, "Target:"]]) {
    const caption = document.createElement("span");
    renderText(caption, label);
    row.classList.add("nami-labeled-path");
    value.className = "nami-labeled-path__value";
    row.append(caption, value);
  }
  paths.append(sourcePath, targetPath);
  const settings = document.createElement("div");
  settings.className = "nami-shell__guidance nami-plan-review__settings";
  const verifySetting = document.createElement("span");
  const deletionSetting = document.createElement("span");
  const verifyIcon = createIcon(document, "arrow-sync", "sm");
  const deletionIcon = createIcon(document, "delete", "sm");
  const verifyLabel = document.createElement("span");
  const deletionLabel = document.createElement("span");
  verifyIcon.ariaHidden = "true";
  deletionIcon.ariaHidden = "true";
  verifySetting.append(verifyIcon, verifyLabel);
  deletionSetting.append(deletionIcon, deletionLabel);
  settings.append(verifySetting, deletionSetting);
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
  statusTitle.tabIndex = -1;
  const facts = document.createElement("p");
  facts.className = "nami-shell__guidance nami-plan-review__status-summary";
  const executionAlert = document.createElement("p");
  executionAlert.className = "nami-shell__guidance nami-plan-review__execution-alert";
  executionAlert.hidden = true;
  const statusActions = document.createElement("div");
  statusActions.className = "nami-plan-review__actions";
  const statusMeta = document.createElement("div");
  statusMeta.className = "nami-plan-review__status-meta";
  const progress = document.createElement("div");
  progress.className = "nami-progress nami-plan-review__progress";
  progress.ariaHidden = "true";
  const progressBar = document.createElement("div");
  progressBar.className = "nami-progress__bar";
  progress.append(progressBar);
  const executionReview = document.createElement("div");
  executionReview.className = "nami-plan-review__execution";
  const executionAxes = document.createElement("p");
  executionAxes.className = "nami-plan-review__execution-axes";
  const executionIssues = document.createElement("p");
  executionIssues.className = "nami-card nami-plan-review__execution-issues";
  executionIssues.hidden = true;
  executionIssues.tabIndex = 0;
  executionIssues.ariaLabel = "Execution issues";
  const executionTrash = document.createElement("p");
  executionTrash.className = "nami-card nami-plan-review__execution-trash";
  executionTrash.hidden = true;
  executionTrash.tabIndex = 0;
  executionTrash.ariaLabel = "Trash location";
  executionReview.append(executionAxes);
  const detailsToggle = button("Details", "nami-button nami-button--clear nami-plan-review__details-toggle");
  detailsToggle.ariaExpanded = "false";
  detailsToggle.dataset.action = "toggle-execution-details";
  summary.append(statusActions, statusMeta, executionAlert);

  const tableCard = document.createElement("div");
  tableCard.className = "nami-card nami-plan-review__table-card";
  const floatingControls = document.createElement("div");
  floatingControls.className = "nami-plan-review__floating-controls";
  const goCurrent = button("Go to current operation", "nami-button nami-button--secondary");
  goCurrent.dataset.action = "go-current-operation";
  const enableFollow = button("Turn on autoscroll", "nami-button nami-button--primary");
  enableFollow.dataset.action = "enable-operation-follow";
  floatingControls.append(goCurrent, enableFollow);

  const detailCard = document.createElement("section");
  detailCard.className = "nami-card nami-plan-review__detail";
  detailCard.tabIndex = 0;
  detailCard.ariaLabel = "Item details";
  const detailHeader = document.createElement("div");
  detailHeader.className = "nami-plan-review__detail-header";
  const detailTitle = document.createElement("h2");
  renderText(detailTitle, "Item details");
  detailHeader.append(detailTitle);
  const detailStatus = document.createElement("p");
  detailStatus.className = "nami-shell__guidance nami-plan-review__detail-status";
  detailStatus.setAttribute("role", "status");
  const detailBody = document.createElement("dl");
  detailBody.className = "nami-plan-review__detail-body";
  detailCard.append(detailHeader, detailStatus, detailBody);

  const toolbar = document.createElement("div");
  toolbar.className = "nami-plan-review__toolbar";
  const search = document.createElement("input");
  search.className = "nami-input";
  search.type = "search";
  search.placeholder = "Search this plan";
  search.autocomplete = "off";
  search.ariaLabel = "Search this plan";
  search.dataset.action = "plan-search";
  const searchBox = document.createElement("div");
  searchBox.className = "nami-plan-review__search";
  const searchSubmit = button("", "nami-button nami-button--clear nami-button--icon nami-plan-review__search-submit");
  searchSubmit.ariaLabel = "Search now";
  searchSubmit.dataset.action = "plan-search-submit";
  searchSubmit.append(createIcon(document, "search", "sm"));
  const searchClear = button("", "nami-button nami-button--clear nami-button--icon nami-plan-review__search-clear");
  searchClear.ariaLabel = "Clear search";
  searchClear.dataset.action = "plan-search-clear";
  searchClear.append(createIcon(document, "dismiss", "sm"));
  searchClear.hidden = true;
  searchBox.append(search, searchClear, searchSubmit);
  const filters = document.createElement("div");
  filters.className = "nami-plan-review__filters";
  const filterList = document.createElement("div");
  filterList.className = "nami-plan-review__filter-list";
  const filterButtons = new Map();
  const filterMenus = new Map();
  for (const value of FILTERS) {
    const filter = countedButton(displayLabel(value), "nami-button nami-plan-review__filter");
    filter.dataset.operation = value === "remove" ? "trash" : value === "error" ? "blocked" : value;
    filter.dataset.filter = value;
    filter.ariaPressed = "false";
    const members = FILTER_GROUPS[value];
    if (members === undefined) {
      filterList.append(filter);
    } else {
      const split = document.createElement("div");
      split.className = "nami-plan-filter-split";
      const dropdown = button("", "nami-button nami-plan-review__filter nami-plan-filter-split__arrow");
      dropdown.dataset.operation = filter.dataset.operation;
      dropdown.ariaLabel = `${displayLabel(value)} filters`;
      dropdown.ariaHasPopup = "menu";
      dropdown.ariaExpanded = "false";
      dropdown.append(createIcon(document, "chevron-down", "sm"));
      const menu = document.createElement("div");
      menu.className = "nami-menu nami-plan-filter-split__menu";
      menu.setAttribute("role", "menu");
      menu.hidden = true;
      const choices = new Map();
      for (const key of ["all", ...members]) {
        const item = countedButton("", "nami-menu__item");
        item.setAttribute("role", "menuitemradio");
        item.dataset.filterDetail = key;
        menu.append(item);
        choices.set(key, item);
      }
      split.append(filter, dropdown, menu);
      filterList.append(split);
      filterMenus.set(value, { split, dropdown, menu, choices });
    }
    filterButtons.set(value, filter);
  }
  filters.append(filterList);
  toolbar.append(filters, searchBox);

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
  const columnNames = ["selection", "name", "primary", "secondary", "size", "modified", "notes"];
  for (const [index, [label, column]] of [
    ["Select", null], ["Name", "filename"], ["Action", null],
    ["Checksum", null], ["Size", "size"], ["Modified", "mtime"], ["Notes", null],
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

  const execute = button("Execute", "nami-button nami-button--primary");
  execute.dataset.action = "execute";
  const planAgain = button("", "nami-button nami-button--secondary nami-button--icon");
  planAgain.append(createIcon(document, "arrow-reset", "sm"));
  planAgain.ariaLabel = "Plan again";
  planAgain.title = "Plan again";
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
  const retryOutcome = button("Retry outcome", "nami-button nami-button--secondary");
  retryOutcome.dataset.action = "retry-outcome";
  retryOutcome.hidden = true;
  const controls = document.createElement("div");
  controls.className = "nami-plan-review__control-group";
  controls.append(pause, resume, cancel);
  const primary = document.createElement("div");
  primary.className = "nami-plan-review__control-group";
  primary.append(planAgain, execute);
  statusActions.append(statusTitle, controls, primary);
  statusMeta.append(facts, status, retryOutcome, detailsToggle);
  tableCard.append(toolbar, list, floatingControls);
  const content = document.createElement("div");
  content.className = "nami-plan-review__content";
  const diagnostics = document.createElement("div");
  diagnostics.className = "nami-plan-review__diagnostics";
  diagnostics.hidden = true;
  const globalDiagnostics = document.createElement("div");
  globalDiagnostics.className = "nami-plan-review__global-diagnostics";
  const planDiagnostics = document.createElement("p");
  planDiagnostics.className = "nami-plan-review__plan-diagnostics";
  globalDiagnostics.append(planDiagnostics, executionReview, executionIssues, executionTrash);
  diagnostics.append(globalDiagnostics, detailCard);
  summary.append(diagnostics, progress);
  content.append(tableCard);
  element.append(header, summary, content);

  let current = null;
  let detailsExpanded = false;
  let focusedPlanRow = null;
  let focusedPlanRequestId = null;
  let programmaticScroll = false;
  let manualScrollIntent = false;
  let searchTimer = null;
  let lastSearchSubmit = -Infinity;
  let scrollFramePending = false;
  let scrollGeneration = 0;
  let pendingWindowOffset = null;
  let renderedRows = null;
  function disableActions() {
    execute.disabled = true;
    planAgain.disabled = true;
    pause.disabled = true;
    resume.disabled = true;
    cancel.disabled = true;
    controls.hidden = true;
  }
  disableActions();
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
  const columnMinimums = [2, 12, 6, 7, 5, 7, 14];
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
    searchClear.hidden = search.value.length === 0;
    if (searchTimer !== null) clearTimeout(searchTimer);
    const scheduledReview = current;
    searchTimer = setTimeout(() => {
      searchTimer = null;
      if (current === scheduledReview) viewChange({ searchQuery: search.value });
    }, 150);
  });
  function submitSearch() {
    const now = Date.now();
    if (now - lastSearchSubmit < 150) return;
    lastSearchSubmit = now;
    if (searchTimer !== null) clearTimeout(searchTimer);
    searchTimer = null;
    viewChange({ searchQuery: search.value });
  }
  function updateSetting(node, icon, label, glyph, value, tone) {
    node.dataset.tone = tone;
    node.ariaLabel = value;
    icon.className = `nami-icon nami-icon--sm nami-icon--${glyph}`;
    updateText(label, value);
  }
  search.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      submitSearch();
    }
  });
  searchSubmit.addEventListener("click", submitSearch);
  searchClear.addEventListener("pointerdown", (event) => event.preventDefault());
  searchClear.addEventListener("click", () => {
    if (searchTimer !== null) clearTimeout(searchTimer);
    searchTimer = null;
    search.value = "";
    searchClear.hidden = true;
    search.focus();
    viewChange({ searchQuery: "" });
  });
  function closeFilterMenus() {
    for (const { dropdown, menu } of filterMenus.values()) {
      menu.hidden = true;
      dropdown.ariaExpanded = "false";
    }
  }
  function selectFilterGroup(value, detail = null) {
    if (current === null || current.pending !== null) return;
    closeFilterMenus();
    const selected = new Set(current.summary.filters);
    if (value === "all") selected.clear();
    else {
      const members = FILTER_GROUPS[value] ?? [value];
      const active = members.every((member) => selected.has(member));
      for (const member of members) selected.delete(member);
      if (detail !== null || !active) {
        for (const member of detail === null || detail === "all" ? members : [detail]) selected.add(member);
      }
    }
    viewChange({ filters: selected });
  }
  for (const [value, filter] of filterButtons) {
    filter.addEventListener("click", () => selectFilterGroup(value));
  }
  for (const [value, { split, dropdown, menu, choices }] of filterMenus) {
    dropdown.addEventListener("click", () => {
      const open = menu.hidden;
      closeFilterMenus();
      menu.hidden = !open;
      dropdown.ariaExpanded = String(open);
      if (open) choices.get("all").focus();
    });
    for (const [key, item] of choices) item.addEventListener("click", () => {
      selectFilterGroup(value, key);
      dropdown.focus();
    });
    split.addEventListener("focusout", (event) => {
      if (!split.contains(event.relatedTarget)) closeFilterMenus();
    });
    menu.addEventListener("keydown", (event) => {
      const items = [...choices.values()];
      const index = items.indexOf(document.activeElement);
      if (event.key === "Escape") {
        event.preventDefault();
        closeFilterMenus();
        dropdown.focus();
      } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1
          : (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
        items[next].focus();
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
  body.addEventListener("wheel", () => { manualScrollIntent = true; }, { passive: true });
  body.addEventListener("touchstart", () => { manualScrollIntent = true; }, { passive: true });
  body.addEventListener("pointerdown", () => { manualScrollIntent = true; });
  body.addEventListener("keydown", (event) => {
    if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].includes(event.key)) {
      manualScrollIntent = true;
    }
  });
  body.addEventListener("scroll", () => {
    if (current !== null && !programmaticScroll && manualScrollIntent) {
      const target = current.follow?.anchorIndex;
      const first = Math.floor(Math.max(0, body.scrollTop) / ROW_HEIGHT);
      const last = Math.max(first, Math.ceil((body.scrollTop + body.clientHeight) / ROW_HEIGHT) - 1);
      if (!Number.isSafeInteger(target) || target < first || target > last) {
        callbacks.onFollowOverride(current);
      }
    }
    manualScrollIntent = false;
    scheduleViewportCheck();
  });
  const resizeObserver = new window.ResizeObserver(scheduleViewportCheck);
  resizeObserver.observe(body);
  let resizeObserved = true;

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
  retryOutcome.addEventListener("click", () => {
    if (current !== null) callbacks.onRetryOutcome?.(current);
  });
  detailsToggle.addEventListener("click", () => {
    detailsExpanded = !detailsExpanded;
    detailsToggle.ariaExpanded = String(detailsExpanded);
    if (!detailsExpanded && diagnostics.contains(document.activeElement)) detailsToggle.focus?.();
    updateDiagnostics();
  });
  goCurrent.addEventListener("click", () => current !== null && callbacks.onNavigateCurrent(current, false));
  enableFollow.addEventListener("click", () => current !== null && callbacks.onNavigateCurrent(current, true));

  function updateDiagnostics() {
    detailsToggle.hidden = current === null;
    detailsToggle.ariaExpanded = String(detailsExpanded);
    diagnostics.hidden = current === null || !detailsExpanded;
  }

  function renderExecution(execution, terminalState) {
    const presentation = projectExecutionSummary(execution);
    executionReview.hidden = !terminalState && execution.session_id === null && execution.gap === null;
    executionReview.dataset.status = presentation.status ?? "none";
    diagnostics.dataset.status = presentation.status ?? "none";
    const result = execution.result;
    const axes = [];
    const issues = [];
    if (result === null) {
      if (terminalState) axes.push("No retained execution result is available.");
      else if (execution.session_id !== null) axes.push("Live execution facts will appear in this bounded window.");
    } else {
      axes.push(`Filesystem: ${executionLabel(result.filesystem)}`);
      axes.push(`Automatic verification: ${executionLabel(result.integrity)}`);
      axes.push(`Item recording: ${executionLabel(result.recording)}`);
      axes.push(`Audit: ${executionLabel(result.audit)}`);
      axes.push(`Disposition: ${executionLabel(result.disposition)}`);
      for (const phase of result.phases) {
        axes.push(`${executionLabel(phase.phase)} phase: ${executionLabel(phase.status)}`);
        if (phase.error !== null) issues.push(`${executionLabel(phase.phase)}: ${phase.error}`);
      }
      if (result.error !== null) issues.push(result.error);
      for (const issue of result.recording_issues) {
        issues.push(`Recording ${executionLabel(issue.reason)}: ${issue.detail}`);
      }
      if (result.recording_degraded_items > 0) issues.push(`${result.recording_degraded_items} items have degraded recording`);
      if (result.omitted_detail_count > 0) issues.push(`${result.omitted_detail_count} producer details omitted`);
      if (result.presentation_omitted_detail_count > 0) issues.push(`${result.presentation_omitted_detail_count} presentation details omitted`);
      if (execution.failed_operation_count > 0) issues.push(`${execution.failed_operation_count} operations failed`);
      if (execution.disk_capacity_failure_count > 0) issues.push(`${execution.disk_capacity_failure_count} failures need more target space`);
    }
    if (execution.gap !== null) {
      issues.push(execution.gap.minimum_first_missed_seq === execution.gap.maximum_first_missed_seq
        ? `Gap observed at event ${execution.gap.minimum_first_missed_seq}`
        : `Gaps observed from event ${execution.gap.minimum_first_missed_seq} through ${execution.gap.maximum_first_missed_seq}`);
    }
    updateText(executionAlert, "Execution event history has gaps.", execution.gap !== null);
    executionAlert.hidden = execution.gap === null;
    updateText(executionAxes, axes.join(" · "));
    updateText(executionIssues, issues.join(" · "));
    executionIssues.hidden = issues.length === 0;
    const trashText = execution.trash_location === null ? "" : `Trash location: ${execution.trash_location}`;
    updateText(executionTrash, trashText, execution.trash_location !== null);
    executionTrash.hidden = execution.trash_location === null;
    updateDiagnostics();
    return presentation;
  }

  function appendDetailFact(label, value, filesystem = false) {
    const term = document.createElement("dt");
    renderText(term, label);
    const definition = document.createElement("dd");
    if (filesystem) renderFilesystemText(definition, value);
    else renderText(definition, value);
    detailBody.append(term, definition);
  }

  function renderDetail(detail, row) {
    detailBody.replaceChildren();
    updateText(detailTitle, row?.display ?? "Item details", row !== null);
    if (row === null) {
      updateText(detailStatus, "Highlight an item to see its details.");
      detailStatus.hidden = false;
      updateDiagnostics();
      return;
    }
    appendDetailFact("Planned action", displayLabel(row.operation_kind ?? row.row_kind));
    if (row.size !== null) appendDetailFact("Size", formatByteCount(row.size));
    if (row.risk !== "none") appendDetailFact("Risk", executionLabel(row.risk));
    if (row.reason !== null) appendDetailFact("Reason", reasonLabel(row.reason));
    if (row.blocked_reason !== null) appendDetailFact("Blocked", reasonLabel(row.blocked_reason));
    if (row.selection_exclusion_reason !== null) appendDetailFact("Excluded", reasonLabel(row.selection_exclusion_reason));
    if (row.notice !== null) appendDetailFact("Notice", row.notice);
    if (row.operation_id === null || current.window.execution.session_id === null) {
      updateText(detailStatus, "Execution detail is available after this item runs.");
      detailStatus.hidden = false;
      updateDiagnostics();
      return;
    }
    if (detail === null || detail.operationId !== row.operation_id) {
      updateText(detailStatus, "Operation detail is unavailable.");
      detailStatus.hidden = false;
      updateDiagnostics();
      return;
    }
    updateText(detailStatus, detail.state === "loading" ? "Loading operation detail…"
      : detail.state === "not-retained" ? "Detail will be available after terminal release."
        : detail.state === "error" ? detail.message : "");
    detailStatus.hidden = detail.state === "current";
    if (detail.state !== "current") {
      updateDiagnostics();
      return;
    }
    const response = detail.response;
    const operation = response.operation;
    if (operation !== null) {
      appendDetailFact("Operation", `${executionLabel(operation.result)} · ${executionLabel(operation.kind)}${operation.reason === null ? "" : ` · ${executionLabel(operation.reason)}`}`);
      appendDetailFact("Path", operation.path, true);
      appendDetailFact("Operation recording", `${executionLabel(operation.recording)}${operation.recording_reason === null ? "" : ` · ${executionLabel(operation.recording_reason)}`}${operation.recording_detail === null ? "" : ` · ${operation.recording_detail}`}`);
      for (const [key, value] of Object.entries(operation.detail)) {
        const text = Array.isArray(value) ? value.join(", ") : String(value);
        appendDetailFact(executionLabel(key), text, key.endsWith("_path") || key === "mutation_destination");
      }
      if (operation.detail_omitted_count > 0) appendDetailFact("Operation details omitted", String(operation.detail_omitted_count));
    } else appendDetailFact("Operation", "Unknown");
    const automatic = response.automatic_verification;
    if (automatic !== null) {
      appendDetailFact("Automatic verification", `${executionLabel(automatic.result)}${automatic.reason === null ? "" : ` · ${executionLabel(automatic.reason)}`}`);
      appendDetailFact("Verification path", automatic.path, true);
      if (automatic.detail !== null) appendDetailFact("Verification detail", automatic.detail);
      appendDetailFact("Verification recording", executionLabel(automatic.recording));
      if (automatic.detail_omitted_count > 0) appendDetailFact("Verification details omitted", String(automatic.detail_omitted_count));
    } else appendDetailFact("Automatic verification", "Unknown");
    const evidence = response.evidence;
    appendDetailFact("Stored evidence", evidence === null ? "Unknown" : executionLabel(evidence.state));
    if (evidence?.content !== null && evidence?.content !== undefined) {
      appendDetailFact("Evidence digest", evidence.content.digest);
      appendDetailFact("Evidence size", formatByteCount(evidence.content.size));
      appendDetailFact("Evidence provenance", executionLabel(evidence.content.provenance));
    }
    updateDiagnostics();
  }

  function renderRows(review, task) {
    const disabled = review.pending !== null || task.executionAttempt !== null;
    const committed = review.summary.selection_state !== "reviewing";
    const highlightRevision = review.summary.highlight_revision ?? review.window.highlight_revision ?? 0;
    const activeElement = document.activeElement;
    const activeRow = activeElement?.dataset?.nodeId !== undefined
      ? activeElement
      : activeElement?.closest?.("[data-node-id]");
    const focusedRow = activeRow?.dataset?.nodeId !== undefined;
    const focusOrigin = focusedRow ? activeRow.dataset.namiFocusOrigin ?? null : null;
    const focusNodeId = review.summary.highlight_focus_node_id;
    if (renderedRows?.review === review && renderedRows.window === review.window
    ) {
      if (renderedRows.progressPresentation !== task.progressPresentation) {
        const activeOperationId = task.progressPresentation?.activeItem?.item_id ?? null;
        for (const operationId of new Set([renderedRows.activeOperationId, activeOperationId])) {
          if (operationId === null) continue;
          const index = review.window.rows.findIndex((row) => row.operation_id === operationId);
          if (index < 0) continue;
          const rowElement = renderedRows.rows[index];
          const intent = rowElement.querySelector(".nami-plan-row__intent");
          if (intent === null) continue;
          const replacement = document.createElement("div");
          renderPlanRow(replacement, rowView(
            review.window.rows[index], disabled, committed, task.progressPresentation,
          ));
          intent.replaceWith(replacement.querySelector(".nami-plan-row__intent"));
        }
        renderedRows.progressPresentation = task.progressPresentation;
        renderedRows.activeOperationId = activeOperationId;
      }
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
        if (focusedRow) {
          const focused = renderedRows.rows.find((row) => row.dataset.nodeId === focusNodeId);
          if (focused !== undefined) {
            focused.focus?.();
            if (focusOrigin === "pointer") focused.dataset.namiFocusOrigin = "pointer";
          }
        }
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
    if (review.window.total === 0) {
      const empty = document.createElement("p");
      empty.className = "nami-shell__guidance nami-plan-review__empty";
      renderText(empty, review.summary.filter_counts?.all === 0
        ? "Plan is empty" : "No items match these filters.");
      fragment.append(empty);
    }
    for (const row of review.window.rows) {
      const element = document.createElement("div");
      renderPlanRow(element, rowView(
        row,
        disabled,
        committed,
        task.progressPresentation,
      ));
      element.insertBefore(element.querySelector(".nami-file-row__size"),
        element.querySelector(".nami-plan-row__modified"));
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
        element.dataset.namiFocusOrigin = "pointer";
      });
      element.addEventListener("focusin", () => {
        delete element.dataset.namiFocusOrigin;
      });
      element.addEventListener("focusout", () => {
        delete element.dataset.namiFocusOrigin;
      });
      element.addEventListener("keydown", (event) => {
        delete element.dataset.namiFocusOrigin;
        if (event.key === "Escape") {
          event.preventDefault();
          callbacks.onHighlight(review, "clear", null);
        } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
          event.preventDefault();
          element.focus?.();
          delete element.dataset.namiFocusOrigin;
          const direction = event.key === "ArrowUp" ? "move_up" : "move_down";
          const gesture = event.shiftKey ? `${direction}_extend` : direction;
          callbacks.onHighlight(review, gesture, null);
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
    if (focusedRow) {
      const focused = rowElements.find((row) => row.dataset.nodeId === focusNodeId);
      if (focused !== undefined) {
        focused.focus?.();
        if (focusOrigin === "pointer") focused.dataset.namiFocusOrigin = "pointer";
      }
    }
    renderedRows = {
      review, window: review.window, disabled, committed, checkboxes,
      rows: rowElements,
      highlightRevision,
      progressPresentation: task.progressPresentation,
      activeOperationId: task.progressPresentation?.activeItem?.item_id ?? null,
    };
  }

  function render(task) {
    if (!resizeObserved) {
      resizeObserver.observe(body);
      resizeObserved = true;
    }
    const focusInDetails = diagnostics.contains(document.activeElement);
    if (current !== task.review) {
      if (searchTimer !== null) clearTimeout(searchTimer);
      searchTimer = null;
      scrollGeneration += 1;
      scrollFramePending = false;
      pendingWindowOffset = null;
      body.scrollTop = (task.review?.window.offset ?? 0) * ROW_HEIGHT;
      detailsExpanded = false;
      focusedPlanRow = null;
      focusedPlanRequestId = null;
    }
    const previousWindow = renderedRows?.window ?? null;
    current = task.review;
    if (focusInDetails && (current === null || !detailsExpanded)) {
      (current === null ? statusTitle : detailsToggle).focus?.();
    }
    if (current === null) {
      disableActions();
      delete element.dataset.pending;
      updateText(sourceValue, "Loading reviewed plan…");
      updateText(targetValue, "");
      updateSetting(verifySetting, verifyIcon, verifyLabel, "arrow-sync", "", "muted");
      updateSetting(deletionSetting, deletionIcon, deletionLabel, "delete", "", "muted");
      updateText(facts, task.error ?? "Waiting for the completed plan to become available.");
      const digest = taskStatusDigest(task);
      updateText(statusTitle, task.error ? "Plan unavailable" : digest.title);
      summary.dataset.status = task.error ? "attention" : digest.state;
      progress.classList.toggle?.("nami-progress--indeterminate", !task.error && digest.progress.indeterminate);
      progress.style.setProperty("--nami-progress-value", `${digest.progress.value}%`);
      body.replaceChildren();
      renderedRows = null;
      tableCard.hidden = true;
      executionReview.hidden = true;
      executionReview.dataset.status = "none";
      diagnostics.dataset.status = "none";
      updateText(executionAlert, "");
      executionAlert.hidden = true;
      updateText(executionIssues, "");
      executionIssues.hidden = true;
      updateText(executionTrash, "");
      executionTrash.hidden = true;
      planDiagnostics.hidden = true;
      renderDetail(null, null);
      floatingControls.hidden = true;
      return;
    }
    const review = current;
    if (Number.isSafeInteger(review.follow?.scrollOffset)) {
      programmaticScroll = true;
      body.scrollTop = review.follow.scrollOffset * ROW_HEIGHT;
      review.follow.scrollOffset = null;
      window.requestAnimationFrame(() => { programmaticScroll = false; });
    }
    const follow = review.follow ?? null;
    goCurrent.hidden = follow?.hasTarget !== true;
    enableFollow.hidden = follow?.hasTarget !== true
      || follow?.eligible !== true || follow?.enabled === true;
    floatingControls.hidden = goCurrent.hidden && enableFollow.hidden;
    if (review.window !== previousWindow) pendingWindowOffset = null;
    element.dataset.pending = review.pending ?? "";
    list.ariaRowCount = String(review.window.total + 1);
    tableCard.hidden = false;
    updateText(sourceValue, review.summary.source_path, true);
    updateText(targetValue, review.summary.target_path, true);
    sourcePath.title = review.summary.source_path;
    targetPath.title = review.summary.target_path;
    const options = task.form?.options;
    const verifying = options?.verify_after_execute === true;
    updateSetting(
      verifySetting, verifyIcon, verifyLabel,
      verifying ? "arrow-sync-checkmark" : "arrow-sync",
      options == null ? "-" : verifying ? "Verify on" : "Verify off",
      verifying ? "accent" : "muted",
    );
    const additive = options?.deletion_policy === "additive";
    updateSetting(
      deletionSetting, deletionIcon, deletionLabel,
      additive ? "document-add" : "delete",
      options == null ? "-" : additive ? "Additive" : "Trash",
      additive ? "accent" : "muted",
    );
    const planningIssues = review.summary.preflight_refusal_count + review.summary.warning_count;
    const planFacts = `${review.summary.selected_operation_count} of ${review.summary.selectable_operation_count} selected · ${formatByteCount(review.summary.required_bytes)} required · ${planningIssues} planning issues`;
    updateText(planDiagnostics, `Plan: ${review.summary.preflight_refusal_count} refusals · ${review.summary.warning_count} warnings · ${review.summary.destructive_operation_count} destructive operations`);
    planDiagnostics.hidden = task.executionStarted;
    const executionState = task.executionStarted ? task.sessionState : null;
    const canExecuteSelection = review.summary.preflight_ready
      && review.summary.selected_operation_count > 0
      && review.summary.selection_state === "reviewing";
    const digest = taskStatusDigest(task);
    const retainedExecution = review.window.execution;
    const displayExecution = retainedExecution.result === null
      && (task.executionResult != null || task.executionEndedAt != null)
      ? { ...retainedExecution, result: task.executionResult,
        started_at: task.executionStartedAt, ended_at: task.executionEndedAt }
      : retainedExecution;
    const terminalState = task.executionStarted
      && ["completed", "failed", "refused", "canceled"].includes(task.sessionState);
    const executionPresentation = renderExecution(displayExecution, terminalState);
    updateText(statusTitle, terminalState && displayExecution.result === null
      ? digest.title : executionPresentation.title ?? digest.title);
    const progressFacts = task.executionStarted && digest.progress.phase !== null
      ? [
        digest.progress.phase === "verify" ? "Verifying" : "Executing",
        digest.progress.total == null ? null : `${digest.progress.done} of ${digest.progress.total} items`,
        digest.progress.determinate ? `${Math.round(digest.progress.value)}%` : null,
        digest.progress.throughputBytesPerSecond == null ? null
          : `${formatByteCount(BigInt(Math.round(digest.progress.throughputBytesPerSecond)))}/s estimate`,
        digest.progress.etaSeconds == null ? null
          : `${Math.ceil(digest.progress.etaSeconds)}s ETA estimate`,
      ].filter(Boolean).join(" · ")
      : null;
    updateText(facts, terminalState ? terminalStatusLine(displayExecution, task.sessionState)
      : executionPresentation.title === null ? planFacts
        : progressFacts ?? digest.detail);
    summary.dataset.status = terminalState && displayExecution.result === null
      ? digest.state : executionPresentation.status ?? digest.state;
    const progressValue = digest.progress.value;
    progress.dataset.lifecycle = executionState ?? "completed";
    if (digest.progress.indeterminate) {
      progress.classList.add("nami-progress--indeterminate");
    } else {
      progress.classList.remove?.("nami-progress--indeterminate");
    }
    progress.style.setProperty("--nami-progress-value", `${progressValue}%`);
    if (document.activeElement !== search) search.value = review.summary.search_query;
    searchClear.hidden = search.value.length === 0;
    search.disabled = review.pending !== null && review.pending !== "view";
    searchSubmit.disabled = search.disabled;
    searchClear.disabled = search.disabled;
    for (const [column, { cell, sortButton, up, down }] of sortHeaders) {
      const active = review.summary.sort_column === column;
      const direction = active ? review.summary.sort_direction : null;
      cell.ariaSort = direction ?? "none";
      up.hidden = direction !== "ascending";
      down.hidden = direction !== "descending";
      sortButton.disabled = review.pending !== null;
    }
    for (const [value, filter] of filterButtons) {
      const members = FILTER_GROUPS[value] ?? [value];
      const active = value === "all"
        ? review.summary.filters.length === 0
        : members.some((member) => review.summary.filters.includes(member));
      const count = members.reduce((total, member) => total + (review.summary.filter_counts?.[member] ?? 0), 0);
      filter.ariaPressed = String(active);
      filter.disabled = review.pending !== null;
      const hidden = !ALWAYS_VISIBLE_FILTERS.has(value) && count === 0;
      filter.hidden = hidden;
      filter.dataset.trashAlert = String(value === "remove" && !active && count > 1);
      updateText(filter.children[0], displayLabel(value));
      updateText(filter.children[1], String(count));
      filter.ariaLabel = `${displayLabel(value)} ${count}`;
      const grouped = filterMenus.get(value);
      if (grouped !== undefined) {
        grouped.split.hidden = hidden;
        grouped.dropdown.disabled = filter.disabled;
        grouped.dropdown.ariaPressed = String(active);
        for (const [key, item] of grouped.choices) {
          const itemCount = key === "all" ? count : review.summary.filter_counts?.[key] ?? 0;
          const label = key === "all" ? `All ${value === "copy" ? "copies" : value === "remove" ? "removals" : `${value}s`}` : displayLabel(key);
          updateText(item.children[0], label);
          updateText(item.children[1], String(itemCount));
          item.ariaLabel = `${label} ${itemCount}`;
          item.ariaChecked = String(key === "all"
            ? members.every((member) => review.summary.filters.includes(member))
            : review.summary.filters.includes(key) && members.filter((member) => review.summary.filters.includes(member)).length === 1);
        }
      }
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
    const controlUnavailable = task.drainUnavailable
      || task.reviewSessionId !== task.sessionId;
    const retryExecution = task.executionAttempt?.state === "uncertain"
      && typeof task.executionAttempt.retry === "function";
    execute.hidden = review.summary.selection_state !== "reviewing";
    updateText(execute, retryExecution ? "Retry outcome" : "Execute");
    execute.disabled = review.pending !== null
      || (task.executionAttempt !== null && !retryExecution)
      || (!retryExecution && !canExecuteSelection);
    planAgain.disabled = review.pending !== null || task.canPlanAgain !== true;
    controls.hidden = !activeExecution;
    pause.hidden = task.executionControlState === "paused";
    resume.hidden = task.executionControlState !== "paused";
    pause.disabled = review.pending !== null || controlUnavailable
      || task.executionControlState !== "running";
    resume.disabled = review.pending !== null || controlUnavailable
      || task.executionControlState !== "paused";
    cancel.disabled = (review.pending !== null && !task.canCancelAfterFixedReviewOutcome)
      || controlUnavailable
      || task.executionControlState === "canceling";
    const independentCancel = task.executionControlAttempt?.independent
      && task.executionControlAttempt.sessionId === task.sessionId
      ? task.executionControlAttempt : null;
    const actionMessage = [review.message, independentCancel?.message].filter(Boolean).join(" ");
    updateText(status, actionMessage);
    status.title = actionMessage;
    status.hidden = actionMessage.length === 0;
    retryOutcome.hidden = typeof review.outcomeRetry !== "function"
      && typeof independentCancel?.retry !== "function";
    retryOutcome.disabled = review.outcomeRunning === true || independentCancel?.pending === true;
    renderRows(review, task);
    if (focusedPlanRequestId !== review.summary.request_id) focusedPlanRow = null;
    focusedPlanRequestId = review.summary.request_id;
    const focusNodeId = review.summary.highlight_focus_node_id;
    if (focusNodeId === null) focusedPlanRow = null;
    else {
      const visibleFocus = review.window.rows.find((row) => row.node_id === focusNodeId);
      if (visibleFocus !== undefined) focusedPlanRow = visibleFocus;
      else if (focusedPlanRow?.node_id !== focusNodeId) focusedPlanRow = null;
    }
    renderDetail(review.executionDetail ?? null, focusedPlanRow);
    refreshResizers();
    scheduleViewportCheck();
  }

  function dispose() {
    closeFilterMenus();
    finishResize?.();
    resizeObserver.disconnect();
    resizeObserved = false;
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
