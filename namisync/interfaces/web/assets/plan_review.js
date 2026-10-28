import { createTableController } from "./table_controller.js";
import { pointerHighlightGesture, keyboardHighlightGesture } from "./row_highlight.js";
import { createTableColumns } from "./table_columns.js";
import { renderPlanRow } from "./plan.js";
import { createFilterMenu } from "./filter_menu.js";
import { createRowMenu } from "./row_menu.js";
import { createIcon } from "./icons.js";
import { formatByteCount, formatFilesystemPath, formatLocalDateTime, renderFilesystemText, renderText } from "./render.js";
import {
  executionHeadline,
  isCapacityOnlyExecution,
  projectActiveOperationProgress,
  selectTaskExecution,
  taskStatusDigest,
  terminalStatusLine,
} from "./task_status.js";

const FILTERS = Object.freeze([
  "copy", "mkdir", "move", "rename", "update", "move_update", "trash", "delete",
  "error", "unsupported", "blocked", "noop", "notice", "recall",
]);
const WINDOW_LIMIT = 256;
const ROW_HEIGHT = 24;
const DISPLAY_LABELS = Object.freeze({
  all: "All", copy: "Copy", move: "Move", update: "Update", remove: "Remove",
  error: "Error", noop: "No change", notice: "Notice", mkdir: "Create folder",
  recase: "Recase", rename: "Rename", move_update: "Move + update", trash: "Move to trash",
  delete: "Delete", unsupported: "Unsupported", blocked: "Blocked",
  recall: "Remote files",
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

function modifiedText(mtime) {
  if (mtime === null) return "";
  return formatLocalDateTime(Number(BigInt(mtime) / 1000000n)) ?? "";
}

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
const isNoChange = (operation) => operation?.result === "skipped" && operation.reason === "noop";

function operationLifecycle(operation) {
  if (operation === null) return null;
  if (operation.result === "succeeded"
    || (operation.result === "skipped" && operation.reason === "noop")) return "completed";
  if (operation.result === "skipped") return "skipped";
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
  const lifecycle = operationLifecycle(operation);
  const notes = [];
  if (operation !== null) {
    notes.push(isNoChange(operation) ? "Operation: No change"
      : `Operation: ${executionLabel(operation.result)}${operation.reason === null ? "" : ` (${executionLabel(operation.reason)})`}`);
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
    lifecycle,
    intent: operation === null ? null : isNoChange(operation) ? "No change"
      : lifecycle === "completed" ? "Completed" : executionLabel(operation.result),
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
  if (result.disposition === "unrun") return { title: executionHeadline(result), status: "error" };
  const capacityOnly = isCapacityOnlyExecution(execution);
  if (capacityOnly) return { title: executionHeadline(result, capacityOnly), status: "attention" };
  const labels = {
    failed: "error", partial: "error", refused: "error", mismatch: "error",
    canceled: "canceled", "verification-incomplete": "attention", degraded: "attention",
    "all-noop": "completed", success: "completed",
  };
  return { title: executionHeadline(result), status: labels[result.headline] ?? "error" };
}

function button(label, className = "nami-button") {
  const element = document.createElement("button");
  element.type = "button";
  element.className = className;
  renderText(element, label);
  return element;
}

function rowView(row, busy, committed, progressPresentation = null) {
  const hideReason = row.risk === "none" && row.blocked_reason === null
    && row.selection_exclusion_reason === null && HIDDEN_REASONS.has(row.reason);
  const reason = hideReason ? null : reasonLabel(row.reason);
  const execution = projectExecutionRow(row.execution);
  const notes = [...new Set([
    row.notice, reasonLabel(row.blocked_reason), reasonLabel(row.selection_exclusion_reason),
    row.move_peer_id === null || row.row_kind === "prior-group" ? null : row.row_kind.startsWith("prior-") ? "Previous location" : "Paired move",
    reason, ...execution.notes,
  ].filter((value) => typeof value === "string" && value !== ""))].join(" · ");
  const risk = row.risk === "none" ? "" : `Risk: ${row.risk}`;
  const intent = row.presentation_kind ?? (row.row_kind === "notice" ? "notice" : "");
  const modified = modifiedText(row.mtime_ns);
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
      || target.classList?.contains("nami-plan-move-pill")
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

export function createPlanReviewPanel(callbacks, detailsState = { expanded: false }) {
  const required = [
    "onViewChange", "onWindow", "onSelect", "onScopeSelect", "onExecute", "onControl", "onPlanAgain",
    "onHighlight", "onHighlightedSelect", "onExecutionDetail", "onFollowOverride", "onNavigateCurrent", "onRevealMove",
    "onPaneChange",
  ];
  if (callbacks === null || typeof callbacks !== "object"
      || !required.every((name) => typeof callbacks[name] === "function")) {
    throw new TypeError("plan review callbacks are incomplete");
  }

  const element = document.createElement("section");
  element.className = "nami-plan-review";
  const interruptNavigation = () => {
    if (current !== null) callbacks.onNavigationInterrupt?.(current);
  };
  for (const name of ["pointerdown", "wheel", "touchstart", "input", "contextmenu"]) {
    element.addEventListener(name, interruptNavigation, { capture: true, passive: true });
  }
  for (const name of ["pointerdown", "wheel", "touchstart", "input", "contextmenu", "keydown"]) {
    document.addEventListener(name, (event) => {
      if (!element.contains(event.target)) interruptNavigation();
    }, { capture: true, passive: true });
  }
  element.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey
        || !["ArrowUp", "ArrowDown"].includes(event.key)
        || !event.target?.closest?.("[data-node-id]")) interruptNavigation();
  }, true);
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
  viewSwitcher.setAttribute("role", "radiogroup");
  viewSwitcher.ariaLabel = "Task view";
  const planPane = button("Plan", "nami-segmented__item");
  planPane.dataset.action = "pane-plan";
  planPane.setAttribute("role", "radio");
  const verifyPane = button("Verify", "nami-segmented__item");
  verifyPane.dataset.action = "pane-verify";
  verifyPane.setAttribute("role", "radio");
  planPane.addEventListener("click", () => {
    if (currentTask !== null && !planPane.disabled) callbacks.onPaneChange(currentTask, "plan");
  });
  verifyPane.addEventListener("click", () => {
    if (currentTask !== null && !verifyPane.disabled) callbacks.onPaneChange(currentTask, "verify");
  });
  viewSwitcher.append(planPane, verifyPane);
  header.append(viewSwitcher, paths, settings);
  const summary = document.createElement("div");
  summary.className = "nami-card nami-plan-review__summary";
  const statusTitle = document.createElement("p");
  statusTitle.className = "nami-plan-review__status-title";
  statusTitle.setAttribute("role", "status");
  statusTitle.tabIndex = -1;
  const facts = document.createElement("p");
  facts.className = "nami-shell__guidance nami-plan-review__status-summary";
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
  executionIssues.className = "nami-plan-review__execution-issues";
  executionIssues.hidden = true;
  executionIssues.tabIndex = 0;
  executionIssues.ariaLabel = "Execution issues";
  const executionTrash = document.createElement("p");
  executionTrash.className = "nami-plan-review__execution-trash";
  executionTrash.hidden = true;
  executionTrash.tabIndex = 0;
  executionTrash.ariaLabel = "Trash location";
  executionReview.append(executionAxes);
  const detailsToggle = button("Details", "nami-button nami-button--clear nami-plan-review__details-toggle");
  detailsToggle.ariaExpanded = "false";
  detailsToggle.dataset.action = "toggle-execution-details";
  summary.append(statusActions, statusMeta);

  const tableCard = document.createElement("div");
  tableCard.className = "nami-card nami-plan-review__table-card";
  const floatingControls = document.createElement("div");
  floatingControls.className = "nami-plan-review__floating-controls";
  const goCurrent = button("", "nami-button nami-button--secondary nami-button--icon");
  goCurrent.ariaLabel = goCurrent.title = "Go to current operation";
  goCurrent.append(createIcon(document, "eye", "sm"));
  goCurrent.dataset.action = "go-current-operation";
  const enableFollow = button("", "nami-button nami-button--primary nami-button--icon");
  enableFollow.ariaLabel = enableFollow.title = "Turn on autoscroll";
  enableFollow.append(createIcon(document, "location-ripple", "sm"));
  enableFollow.dataset.action = "enable-operation-follow";
  const goCurrentSurface = document.createElement("div");
  goCurrentSurface.className = "nami-plan-review__floating-control";
  goCurrentSurface.append(goCurrent);
  const enableFollowSurface = document.createElement("div");
  enableFollowSurface.className = "nami-plan-review__floating-control";
  enableFollowSurface.append(enableFollow);
  floatingControls.append(goCurrentSurface, enableFollowSurface);

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
  const filterMenu = createFilterMenu(FILTERS.map((key) => [key, displayLabel(key)]), (selected) => {
    if (current !== null && current.pending === null) viewChange({ filters: selected });
  });
  filters.append(filterMenu.element);
  toolbar.append(filters, searchBox);

  const list = document.createElement("div");
  list.className = "nami-file-list nami-table-scroll nami-table-scroll--single nami-plan-review__list";
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
  const pause = button("", "nami-button nami-button--secondary nami-button--icon");
  pause.dataset.action = "pause";
  pause.dataset.control = "pause-resume";
  const pauseIcon = createIcon(document, "pause", "sm");
  const playIcon = createIcon(document, "play-filled", "sm");
  playIcon.hidden = true;
  pause.append(pauseIcon, playIcon);
  const cancel = button("", "nami-button nami-button--secondary nami-button--icon");
  cancel.dataset.action = "cancel";
  const stopIcon = createIcon(document, "stop", "sm");
  const filledStopIcon = createIcon(document, "stop-filled", "sm");
  cancel.append(stopIcon, filledStopIcon);
  const status = document.createElement("p");
  status.className = "nami-shell__guidance nami-plan-review__status";
  status.setAttribute("role", "status");
  status.ariaLive = "polite";
  const retryOutcome = button("Check outcome", "nami-button nami-button--secondary");
  retryOutcome.dataset.action = "retry-outcome";
  retryOutcome.hidden = true;
  const controls = document.createElement("div");
  controls.className = "nami-plan-review__control-group";
  controls.append(pause, cancel);
  const primary = document.createElement("div");
  primary.className = "nami-plan-review__control-group";
  primary.append(planAgain, execute, retryOutcome);
  const actionButtons = document.createElement("div");
  actionButtons.className = "nami-plan-review__action-buttons";
  actionButtons.append(controls, primary);
  statusActions.append(statusTitle, actionButtons);
  statusMeta.append(facts, status, detailsToggle);
  tableCard.append(toolbar, list, floatingControls);
  const content = document.createElement("div");
  content.className = "nami-plan-review__content";
  const diagnostics = document.createElement("div");
  diagnostics.className = "nami-plan-review__diagnostics";
  diagnostics.hidden = true;
  const globalDiagnostics = document.createElement("div");
  globalDiagnostics.className = "nami-card nami-plan-review__global-diagnostics";
  globalDiagnostics.tabIndex = 0;
  globalDiagnostics.ariaLabel = "Task details";
  const globalTitle = document.createElement("h2");
  renderText(globalTitle, "Task details");
  const planDiagnostics = document.createElement("p");
  planDiagnostics.className = "nami-plan-review__plan-diagnostics";
  const planBreakdown = document.createElement("p");
  planBreakdown.className = "nami-plan-review__plan-breakdown";
  const globalStatus = document.createElement("p");
  globalStatus.className = "nami-plan-review__global-status";
  globalDiagnostics.append(globalTitle, globalStatus, planDiagnostics, planBreakdown,
    executionReview, executionIssues, executionTrash);
  diagnostics.append(globalDiagnostics, detailCard);
  summary.append(progress);
  content.append(tableCard);
  element.append(header, summary, content, diagnostics);

  let current = null;
  let currentTask = null;
  const rowMenu = createRowMenu(element);
  let focusedPlanRow = null;
  let focusedPlanRequestId = null;
  let searchTimer = null;
  let lastSearchSubmit = -Infinity;
  let renderedRows = null;
  let controlTaskId = null;
  let controlSessionId = null;
  let cancelDeadline = null;
  let cancelTimer = null;
  function paintCancel() {
    const armed = cancelDeadline !== null;
    cancel.className = `nami-button nami-button--${armed ? "primary" : "secondary"} nami-button--icon`;
    stopIcon.hidden = armed;
    filledStopIcon.hidden = !armed;
    cancel.ariaPressed = String(armed);
    cancel.ariaLabel = armed ? "Confirm cancellation" : "Cancel execution";
    cancel.title = armed ? "Click Cancel again within 5 seconds to stop execution." : "Cancel execution";
  }
  function disarmCancel() {
    if (cancelTimer !== null) clearTimeout(cancelTimer);
    cancelTimer = null;
    cancelDeadline = null;
    paintCancel();
  }
  paintCancel();
  function disableActions() {
    execute.disabled = true;
    planAgain.disabled = true;
    pause.disabled = true;
    cancel.disabled = true;
    controls.hidden = true;
    disarmCancel();
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
  const columns = createTableColumns(grid, headerCells, columnNames, [2, 12, 6, 7, 5, 7, 14], 1, 6);
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
  for (const [column, { sortButton }] of sortHeaders) {
    sortButton.addEventListener("click", () => {
      const same = current?.summary.sort_column === column;
      const descending = same && current.summary.sort_direction === "descending";
      viewChange(descending
        ? { sortColumn: "path", sortDirection: "ascending" }
        : { sortColumn: column, sortDirection: same ? "descending" : "ascending" });
    });
  }
  let table = null;
  function ensureTable() {
    if (table !== null) return;
    table = createTableController(list, ROW_HEIGHT, ROW_HEIGHT, {
      requestIndex: (_index, generation, offset) => {
        const owner = table;
        callbacks.onWindow(current, offset,
          (window) => owner.acceptsWindow(generation, window),
          (outcome) => owner.finishWindowRequest(generation, outcome));
      },
      requestCancelled: () => { if (current !== null) callbacks.onWindow(current, null); },
      manualScroll: (first, last) => {
        if (current !== null) callbacks.onFollowOverride(current, first, last);
      },
    });
  }
  const resizeObserver = new window.ResizeObserver(() => {
    if (current !== null) {
      columns.freeze();
      columns.refresh();
    }
  });
  resizeObserver.observe(list);
  let resizeObserved = true;

  function revealRow(index) { table.revealRow(index); }
  execute.addEventListener("click", () => {
    if (current !== null) callbacks.onExecute(current, execute);
  });
  planAgain.addEventListener("click", () => {
    if (current !== null && !planAgain.hidden && !planAgain.disabled) callbacks.onPlanAgain(current);
  });
  pause.addEventListener("click", () => {
    if (current !== null && !pause.disabled) callbacks.onControl(current, pause.dataset.action);
  });
  cancel.addEventListener("click", () => {
    if (current === null || cancel.disabled || controls.hidden) return;
    if (cancelDeadline !== null && performance.now() < cancelDeadline) {
      disarmCancel();
      callbacks.onControl(current, "cancel");
      return;
    }
    disarmCancel();
    cancelDeadline = performance.now() + 5000;
    cancelTimer = setTimeout(disarmCancel, 5000);
    paintCancel();
  });
  retryOutcome.addEventListener("click", () => {
    if (current !== null) callbacks.onRetryOutcome?.(current);
    else if (!retryOutcome.disabled) callbacks.onCheckStart?.();
  });
  detailsToggle.addEventListener("click", () => {
    detailsState.expanded = !detailsState.expanded;
    detailsToggle.ariaExpanded = String(detailsState.expanded);
    if (!detailsState.expanded && diagnostics.contains(document.activeElement)) detailsToggle.focus?.();
    updateDiagnostics();
  });
  goCurrent.addEventListener("click", () => current !== null && callbacks.onNavigateCurrent(current, false));
  enableFollow.addEventListener("click", () => current !== null && callbacks.onNavigateCurrent(current, true));

  function updateDiagnostics() {
    detailsToggle.hidden = current === null;
    detailsToggle.ariaExpanded = String(detailsState.expanded);
    diagnostics.hidden = current === null || !detailsState.expanded;
  }

  function openRowMenu(event, rowElement, review, row) {
    const window = review.window;
    const owner = currentTask;
    const actionRevision = review.actionRevision;
    const viewRevision = review.summary.view_revision;
    const selectionState = review.summary.selection_state;
    const sessionId = owner?.sessionId;
    const isCurrent = () => current === review && currentTask === owner
      && review.window === window && review.actionRevision === actionRevision
      && review.summary.view_revision === viewRevision && review.summary.selection_state === selectionState
      && owner?.sessionId === sessionId
      && review.pending === null && owner?.executionAttempt == null
      && !owner?.closePending && owner?.closeRecovery == null
      && element.contains(rowElement);
    const actions = [{ id: "row-details", label: "Show details", run: () => {
      detailsState.expanded = true;
      updateDiagnostics();
      callbacks.onHighlight(review, "replace", row.node_id);
    } }];
    if (row.selection !== "disabled" && review.summary.selection_state === "reviewing"
        && !row.row_kind.startsWith("prior-")) {
      const selected = row.selection !== "selected";
      actions.push({ id: "row-selection", label: selected ? "Select" : "Deselect",
        run: () => callbacks.onSelect(review, row, selected) });
    }
    if (row.is_container && row.expanded !== null) {
      actions.push({ id: "row-collapse", label: row.expanded ? "Collapse" : "Expand",
        run: () => callbacks.onViewChange(review, {
          collapseNodeId: row.node_id, collapsed: row.expanded,
        }) });
    }
    filterMenu.close();
    rowMenu.open(event, rowElement, rowElement, actions, isCurrent);
  }

  function renderExecution(execution, terminalState, snapshot = null) {
    const presentation = projectExecutionSummary(execution);
    const gap = execution.gap ?? (snapshot?.gap_first_missed_seq == null ? null : {
      minimum_first_missed_seq: snapshot.gap_first_missed_seq,
      maximum_first_missed_seq: snapshot.gap_first_missed_seq,
    });
    executionReview.hidden = !terminalState && execution.session_id === null && gap === null;
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
    if (gap !== null) {
      issues.push(gap.minimum_first_missed_seq === gap.maximum_first_missed_seq
        ? `Gap observed at event ${gap.minimum_first_missed_seq}`
        : `Gaps observed from event ${gap.minimum_first_missed_seq} through ${gap.maximum_first_missed_seq}`);
    }
    updateText(executionAxes, axes.join(" · "));
    updateText(executionIssues, issues.join(" · "));
    executionIssues.hidden = issues.length === 0;
    const trashText = execution.trash_location === null ? "" : `Trash location: ${execution.trash_location}`;
    updateText(executionTrash, trashText, execution.trash_location !== null);
    executionTrash.hidden = execution.trash_location === null;
    updateDiagnostics();
    return { ...presentation, advisory: gap === null ? "" : "Execution event history has gaps." };
  }

  function appendDetailFact(label, value, { filesystem = false, fullWidth = filesystem, block = false } = {}) {
    const term = document.createElement("dt");
    renderText(term, label);
    const definition = document.createElement("dd");
    if (fullWidth) {
      term.className = definition.className = "nami-detail-full";
    }
    if (block) {
      term.classList.add("nami-detail-block");
      if (!fullWidth) definition.classList.add("nami-detail-block");
    }
    if (filesystem) renderFilesystemText(definition, value);
    else renderText(definition, value);
    detailBody.append(term, definition);
    return definition;
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
    const response = detail?.operationId === row.operation_id && detail.state === "current" ? detail.response : null;
    const operation = response?.operation ?? row.execution?.operation ?? null;
    const action = rowView({ ...row, execution: response ?? row.execution }, false, false, currentTask?.executionPresentation);
    const actionFact = appendDetailFact(operation === null ? "Planned action" : "Operation", "");
    actionFact.classList.add("nami-plan-row__intent");
    if (action.lifecycleKey !== undefined) actionFact.dataset.lifecycle = action.lifecycleKey;
    else if (action.intentKey !== "") actionFact.dataset.intent = action.intentKey;
    const actionLabel = document.createElement("span");
    actionLabel.className = "nami-file-state-label";
    renderText(actionLabel, operation === null ? action.intentText
      : isNoChange(operation) ? "No change"
        : `${executionLabel(operation.result)} · ${displayLabel(operation.kind ?? row.operation_kind)}`);
    actionFact.append(actionLabel);
    if (row.reason !== null) appendDetailFact("Reason", reasonLabel(row.reason));
    if (row.blocked_reason !== null) appendDetailFact("Blocked", reasonLabel(row.blocked_reason));
    if (row.selection_exclusion_reason !== null) appendDetailFact("Excluded", reasonLabel(row.selection_exclusion_reason));
    if (operation?.reason != null && !isNoChange(operation)) appendDetailFact("Result reason", executionLabel(operation.reason));
    if (operation !== null) appendDetailFact("Operation recording", `${executionLabel(operation.recording)}${operation.recording_reason == null ? "" : ` · ${executionLabel(operation.recording_reason)}`}${operation.recording_detail == null ? "" : ` · ${operation.recording_detail}`}`);
    const planned = current.planDetail;
    let plannedStatus = "Planned details are unavailable.";
    if (planned?.nodeId === row.node_id) {
      plannedStatus = planned.state === "loading" ? "Loading planned details…"
        : planned.state === "error" ? planned.message : "";
      if (planned.state === "current") {
        const paths = planned.response.detail;
        const root = paths.path_origin === "source" ? current.summary.source_path : current.summary.target_path;
        if (paths.source_path !== null) appendDetailFact("Source path", formatFilesystemPath(current.summary.source_path, paths.source_path), { filesystem: true, block: true });
        if (paths.path !== null) appendDetailFact(paths.path_origin === "source" ? "Source path" : "Target path", formatFilesystemPath(root, paths.path), { filesystem: true, block: paths.source_path === null });
        if (paths.prior_path !== null) appendDetailFact("Previous path", formatFilesystemPath(current.summary.target_path, paths.prior_path), { filesystem: true });
        if (paths.move_destination_path !== null) appendDetailFact("Move destination", formatFilesystemPath(current.summary.target_path, paths.move_destination_path), { filesystem: true });
        if (paths.notice !== null) appendDetailFact("Notice", paths.notice);
      }
    }
    if (row.notice !== null && !(planned?.nodeId === row.node_id && planned.state === "current")) {
      appendDetailFact("Notice", row.notice);
    }
    if (row.size !== null) appendDetailFact("Size", formatByteCount(row.size), { block: true });
    if (row.mtime_ns !== null) appendDetailFact("Modified", modifiedText(row.mtime_ns));
    if (row.dependency_count > 0) appendDetailFact("Dependencies", String(row.dependency_count));
    if (row.is_container) {
      appendDetailFact("Operations", String(row.operation_count));
      appendDetailFact("Selection", `${row.selected_operation_count} of ${row.selectable_operation_count} selected`);
    } else if (row.selection === "selected" || row.selection === "unselected") {
      appendDetailFact("Selection", row.selection === "selected" ? "Selected" : "Not selected");
    }
    if (row.risk !== "none") appendDetailFact("Risk", executionLabel(row.risk));
    if (row.operation_id === null || current.window.execution.session_id === null) {
      updateText(detailStatus, plannedStatus);
      detailStatus.hidden = plannedStatus === "";
      updateDiagnostics();
      return;
    }
    if (detail === null || detail.operationId !== row.operation_id) {
      updateText(detailStatus, [plannedStatus, "Operation detail is unavailable."].filter(Boolean).join(" "));
      detailStatus.hidden = false;
      updateDiagnostics();
      return;
    }
    const executionStatus = detail.state === "loading" ? "Loading operation detail…"
      : detail.state === "not-retained" ? "Detail will be available after terminal release."
        : detail.state === "error" ? detail.message : "";
    updateText(detailStatus, [plannedStatus, executionStatus].filter(Boolean).join(" "));
    detailStatus.hidden = plannedStatus === "" && executionStatus === "";
    if (detail.state !== "current") {
      updateDiagnostics();
      return;
    }
    if (operation !== null) {
      for (const [key, value] of Object.entries(operation.detail)) {
        const text = Array.isArray(value) ? value.join(", ") : String(value);
        const filesystem = key.endsWith("_path") || key === "mutation_destination";
        const targetPath = ["backup_path", "mutation_destination", "prior_path", "published_path", "trash_path"].includes(key);
        appendDetailFact(executionLabel(key), targetPath ? formatFilesystemPath(current.summary.target_path, text) : text, { filesystem });
      }
      if (operation.detail_omitted_count > 0) appendDetailFact("Operation details omitted", String(operation.detail_omitted_count));
    }
    const automatic = response.automatic_verification;
    if (automatic !== null) {
      appendDetailFact("Automatic verification", `${executionLabel(automatic.result)}${automatic.reason === null ? "" : ` · ${executionLabel(automatic.reason)}`}`, { block: true });
      appendDetailFact("Verification path", formatFilesystemPath(current.summary.target_path, automatic.path), { filesystem: true });
      if (automatic.detail !== null) appendDetailFact("Verification detail", automatic.detail);
      appendDetailFact("Verification recording", executionLabel(automatic.recording));
      if (automatic.detail_omitted_count > 0) appendDetailFact("Verification details omitted", String(automatic.detail_omitted_count));
    } else appendDetailFact("Automatic verification", "Unknown");
    const evidence = response.evidence;
    appendDetailFact("Stored evidence", evidence === null ? "Unknown" : executionLabel(evidence.state), { block: true });
    if (evidence?.content !== null && evidence?.content !== undefined) {
      appendDetailFact("Evidence digest", evidence.content.digest, { fullWidth: true });
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
    const restoreFocusNodeId = review.keyboardRevealWindow === review.window
      ? focusNodeId : activeRow?.dataset?.nodeId;
    if (renderedRows?.review === review && renderedRows.window === review.window
    ) {
      if (renderedRows.progressPresentation !== task.executionPresentation) {
        const activeOperationId = task.executionPresentation?.activeItem?.item_id ?? null;
        for (const operationId of new Set([renderedRows.activeOperationId, activeOperationId])) {
          if (operationId === null) continue;
          const index = review.window.rows.findIndex((row) => row.operation_id === operationId);
          if (index < 0) continue;
          const rowElement = renderedRows.rows[index];
          const intent = rowElement.querySelector(".nami-plan-row__intent");
          if (intent === null) continue;
          const replacement = document.createElement("div");
          renderPlanRow(replacement, rowView(
            review.window.rows[index], disabled, committed, task.executionPresentation,
          ));
          intent.replaceWith(replacement.querySelector(".nami-plan-row__intent"));
        }
        renderedRows.progressPresentation = task.executionPresentation;
        renderedRows.activeOperationId = activeOperationId;
      }
      if (renderedRows.disabled !== disabled || renderedRows.committed !== committed) {
        for (const [index, checkbox] of renderedRows.checkboxes.entries()) {
          if (checkbox !== null) checkbox.disabled = disabled || committed
            || review.window.rows[index].selection === "disabled";
          const pill = renderedRows.rows[index].querySelector(".nami-plan-move-pill");
          if (pill !== null) pill.disabled = disabled;
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
          const checkbox = renderedRows.checkboxes[index];
          if (checkbox !== null && checkbox !== undefined) checkbox.ariaLabel = row.highlighted && review.summary.highlighted_count > 1
            ? "Select highlighted operations only" : `Select ${row.display}`;
          rendered.tabIndex = row.node_id === (focusNodeId ?? review.window.rows[0]?.node_id) ? 0 : -1;
        }
        if (focusedRow) {
          const focused = renderedRows.rows.find((row) => row.dataset.nodeId === restoreFocusNodeId);
          if (focused !== undefined) {
            focused.focus?.({ preventScroll: true });
            if (review.keyboardRevealWindow === review.window) {
              revealRow(Number(focused.ariaRowIndex) - 2);
              table.resetTravel();
            }
            if (focusOrigin === "pointer") focused.dataset.namiFocusOrigin = "pointer";
          }
        }
        renderedRows.highlightRevision = highlightRevision;
      }
      review.keyboardRevealWindow = null;
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
        task.executionPresentation,
      ));
      if (row.recall) {
        const availability = document.createElement("span");
        availability.className = "nami-file-row__availability";
        availability.setAttribute("role", "img");
        availability.ariaLabel = "Not fully available locally. Access may retrieve content through your provider.";
        availability.title = availability.ariaLabel;
        availability.append(createIcon(document, "cloud", "sm"));
        element.querySelector(".nami-file-row__name").append(availability);
      }
      element.insertBefore(element.querySelector(".nami-file-row__size"),
        element.querySelector(".nami-plan-row__modified"));
      element.dataset.nodeId = row.node_id;
      element.ariaRowIndex = String(row.visible_index + 2);
      element.tabIndex = row.node_id === (focusNodeId ?? review.window.rows[0]?.node_id) ? 0 : -1;
      element.ariaSelected = String(row.highlighted === true);
      setHighlighted(element, row.highlighted === true);
      const checkbox = element.querySelector(".nami-checkbox");
      if (checkbox !== null && row.highlighted && review.summary.highlighted_count > 1) {
        checkbox.ariaLabel = "Select highlighted operations only";
      }
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
        const gesture = pointerHighlightGesture(event);
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
        if (event.key === "ContextMenu" || (event.key === "F10" && event.shiftKey)) {
          openRowMenu(event, element, review, row);
        } else if (event.key === "Escape") {
          event.preventDefault();
          callbacks.onHighlight(review, "clear", null);
        } else if ((event.key === "ArrowUp" || event.key === "ArrowDown")
            && !event.altKey && !event.ctrlKey && !event.metaKey) {
          event.preventDefault();
          element.focus?.();
          delete element.dataset.namiFocusOrigin;
          const gesture = keyboardHighlightGesture(event);
          callbacks.onHighlight(review, gesture, null);
        }
      });
      element.addEventListener("contextmenu", (event) => openRowMenu(event, element, review, row));
      element.querySelector(".nami-file-row__disclosure")?.addEventListener("click", () => {
        callbacks.onViewChange(review, {
          collapseNodeId: row.node_id, collapsed: row.expanded === true,
        });
      });
      addGroupDisclosure(element, row, () => callbacks.onViewChange(review, {
        collapseNodeId: row.node_id, collapsed: row.expanded === true,
      }));
      if (row.prior_name !== null || (row.operation_id !== null
          && ["move", "move_update"].includes(row.presentation_kind))) {
        const previous = document.createElement("span");
        previous.className = "nami-plan-row__previous";
        const renamed = row.presentation_kind === "rename";
        renderFilesystemText(previous, renamed ? `renamed from ${row.prior_name}`
          : row.presentation_kind === "move" ? "moved from another folder"
            : "previous location available in details");
        previous.title = previous.textContent;
        element.querySelector(".nami-file-row__name").append(previous);
      }
      if (row.row_kind === "prior-group" && row.move_peer_id !== null) {
        const pill = button("", "nami-plan-move-pill");
        const badge = document.createElement("span");
        badge.className = "nami-badge";
        badge.dataset.form = "fill";
        const count = document.createElement("span");
        count.className = "nami-plan-move-pill__count";
        renderText(count, `${row.move_group.count} ${row.move_group.count === 1 ? "item" : "items"} moved to`);
        const destination = document.createElement("span");
        destination.className = "nami-plan-move-pill__destination";
        renderFilesystemText(destination, row.move_group.destination_display || "root");
        badge.append(count, destination);
        pill.append(badge);
        pill.title = row.display;
        pill.ariaLabel = row.display;
        pill.disabled = disabled;
        pill.addEventListener("click", () => callbacks.onRevealMove(review, row.node_id));
        element.querySelector(".nami-file-row__name-text").replaceWith(pill);
        element.querySelector(".nami-file-row__selection").replaceChildren();
        checkboxes[checkboxes.length - 1] = null;
      }
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
      const focused = rowElements.find((row) => row.dataset.nodeId === restoreFocusNodeId);
      if (focused !== undefined) {
        focused.focus?.({ preventScroll: true });
        if (review.keyboardRevealWindow === review.window) {
          revealRow(Number(focused.ariaRowIndex) - 2);
          table.resetTravel();
        }
        if (focusOrigin === "pointer") focused.dataset.namiFocusOrigin = "pointer";
      }
    }
    review.keyboardRevealWindow = null;
    renderedRows = {
      review, window: review.window, disabled, committed, checkboxes,
      rows: rowElements,
      highlightRevision,
      progressPresentation: task.executionPresentation,
      activeOperationId: task.executionPresentation?.activeItem?.item_id ?? null,
    };
  }

  function render(task) {
    ensureTable();
    currentTask = task;
    planAgain.hidden = (task.sessionState === "active" && (task.executionStarted || task.review === null))
      || task.executionAttempt != null;
    const verifyAvailable = task.taskKind === "sync-plan" && task.executionStarted
      && task.executionSessionId !== null
      && (task.sessionKind !== "sync-execution" || task.sessionReleased);
    planPane.ariaChecked = "true";
    planPane.disabled = false;
    verifyPane.ariaChecked = "false";
    verifyPane.disabled = !verifyAvailable;
    if (controlTaskId !== task.taskId || controlSessionId !== task.sessionId) {
      filterMenu.close();
      disarmCancel();
      controlTaskId = task.taskId;
      controlSessionId = task.sessionId;
    }
    if (!resizeObserved) {
      resizeObserver.observe(list);
      resizeObserved = true;
    }
    const focusInDetails = diagnostics.contains(document.activeElement);
    if (current !== task.review) {
      filterMenu.close();
      if (searchTimer !== null) clearTimeout(searchTimer);
      searchTimer = null;
      table.reset();
      table.setScrollTop((task.review?.window.offset ?? 0) * ROW_HEIGHT);
      focusedPlanRow = null;
      focusedPlanRequestId = null;
    }
    const previousWindow = renderedRows?.window ?? null;
    current = task.review;
    rowMenu.reconcile();
    if (focusInDetails && (current === null || !detailsState.expanded)) {
      (current === null ? statusTitle : detailsToggle).focus?.();
    }
    if (current === null) {
      filterMenu.render([], {}, true);
      disableActions();
      delete element.dataset.pending;
      updateText(sourceValue, task.form?.source?.text ?? "Loading reviewed plan…", true);
      updateText(targetValue, task.form?.target?.text ?? "", true);
      sourcePath.title = task.form?.source?.text ?? "";
      targetPath.title = task.form?.target?.text ?? "";
      updateSetting(verifySetting, verifyIcon, verifyLabel, "arrow-sync", "", "muted");
      updateSetting(deletionSetting, deletionIcon, deletionLabel, "delete", "", "muted");
      const digest = taskStatusDigest(task);
      updateText(facts, task.error ?? (task.form?.attempt?.recovery?.message
        ? "Waiting for the original start outcome." : digest.detail));
      const recovery = task.form?.attempt?.recovery;
      updateText(status, recovery?.message ?? (task.error ? "Check the task settings and try again."
        : "Wait for the plan before reviewing changes."));
      status.hidden = false;
      retryOutcome.hidden = recovery?.canCheck !== true;
      retryOutcome.disabled = recovery?.checking === true || task.form?.attempt?.running !== true;
      updateText(retryOutcome, "Check outcome");
      updateText(statusTitle, task.error ? "Plan unavailable" : digest.title);
      summary.dataset.status = task.error ? "attention" : digest.state;
      progress.classList.toggle?.("nami-progress--indeterminate", !task.error && digest.progress.indeterminate);
      progress.style.setProperty("--nami-progress-value", `${digest.progress.value}%`);
      body.replaceChildren();
      renderedRows = null;
      list.ariaRowCount = "1";
      tableCard.hidden = false;
      toolbar.hidden = true;
      if (scopeCheckbox instanceof HTMLInputElement) {
        scopeCheckbox.disabled = true;
        scopeCheckbox.checked = false;
        scopeCheckbox.indeterminate = false;
      }
      for (const { sortButton } of sortHeaders.values()) sortButton.disabled = true;
      executionReview.hidden = true;
      executionReview.dataset.status = "none";
      diagnostics.dataset.status = "none";
      updateText(executionIssues, "");
      executionIssues.hidden = true;
      updateText(executionTrash, "");
      executionTrash.hidden = true;
      planDiagnostics.hidden = true;
      planBreakdown.hidden = true;
      updateText(globalStatus, "");
      renderDetail(null, null);
      floatingControls.hidden = true;
      return;
    }
    const review = current;
    toolbar.hidden = false;
    if (previousWindow !== null && previousWindow.view_revision !== review.window.view_revision) {
      table.resetTravel();
    }
    if (Number.isSafeInteger(review.follow?.scrollOffset)) {
      table.setScrollTop(review.follow.scrollOffset * ROW_HEIGHT);
      review.follow.scrollOffset = null;
    }
    const follow = review.follow ?? null;
    goCurrent.hidden = follow?.hasTarget !== true;
    enableFollow.hidden = follow?.hasTarget !== true
      || follow?.eligible !== true || follow?.enabled === true;
    goCurrentSurface.hidden = goCurrent.hidden;
    enableFollowSurface.hidden = enableFollow.hidden;
    floatingControls.hidden = goCurrent.hidden && enableFollow.hidden;
    if (review.window !== previousWindow) table.setWindow(review.window);
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
    const breakdown = FILTERS.filter((key) => key !== "recall" && review.summary.filter_counts?.[key] > 0)
      .map((key) => `${displayLabel(key)} ${review.summary.filter_counts[key]}`);
    updateText(planBreakdown, `Plan actions: ${breakdown.join(" · ")}`);
    planBreakdown.hidden = breakdown.length === 0;
    const { snapshot, sessionState, execution } = selectTaskExecution(task);
    const executionState = task.executionStarted ? sessionState : null;
    const canExecuteSelection = review.summary.preflight_ready
      && review.summary.selected_operation_count > 0
      && review.summary.selection_state === "reviewing";
    const digest = taskStatusDigest(task);
    const displayExecution = execution;
    const terminalState = task.executionStarted
      && ["completed", "failed", "refused", "canceled"].includes(executionState);
    const executionPresentation = renderExecution(displayExecution, terminalState,
      task.executionStarted ? snapshot : null);
    const controlTitle = task.executionStarted && !terminalState
      ? ({paused: "Execution paused", pausing: "Pausing execution", canceling: "Canceling execution"})[task.executionControlState]
      : null;
    updateText(statusTitle, controlTitle ?? (terminalState && displayExecution.result === null
      ? digest.title : executionPresentation.title ?? (task.executionStarted ? "Execution" : digest.title)));
    const executionProgress = snapshot?.presentation ?? null;
    const progressFacts = task.executionStarted && snapshot?.phase != null
      ? [
        snapshot.phase === "verify" ? "Verifying" : "Executing",
        executionProgress.items_total == null ? null : `${executionProgress.items_done} of ${executionProgress.items_total} items`,
        executionProgress.determinate ? `${Math.round(executionProgress.value)}%` : null,
        executionProgress.throughput_bytes_per_second == null ? null
          : `${formatByteCount(BigInt(Math.round(executionProgress.throughput_bytes_per_second)))}/s estimate`,
        executionProgress.eta_seconds == null ? null
          : `${Math.ceil(executionProgress.eta_seconds)}s ETA estimate`,
      ].filter(Boolean).join(" · ")
      : null;
    const statusFacts = terminalState ? terminalStatusLine(displayExecution, executionState)
      : executionPresentation.title === null ? planFacts
        : progressFacts ?? digest.detail;
    updateText(facts, snapshot?.progress_inconsistent === true
      ? [statusFacts, "Some progress updates were inconsistent."].filter(Boolean).join(" · ")
      : statusFacts);
    summary.dataset.status = terminalState && displayExecution.result === null
      ? "error" : task.executionStarted && !terminalState && task.executionControlState === "paused"
        ? "paused" : executionPresentation.status ?? (task.executionStarted ? "executing" : digest.state);
    const progressValue = executionProgress?.value ?? 0;
    progress.dataset.lifecycle = executionState ?? "completed";
    if (executionProgress?.indeterminate) {
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
    filterMenu.render(review.summary.filters, review.summary.filter_counts, review.pending !== null);
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
    const activeExecution = task.executionStarted && task.sessionKind === "sync-execution" && task.sessionState === "active";
    const controlUnavailable = task.drainUnavailable
      || task.reviewSessionId !== task.executionSessionId;
    const checkExecution = task.executionAttempt?.state === "submitting"
      && task.executionAttempt.recovery?.canCheck
      && !task.executionAttempt.recovery.checking;
    execute.hidden = review.summary.selection_state !== "reviewing";
    updateText(execute, checkExecution ? "Check outcome" : "Execute");
    execute.disabled = (review.pending !== null && !checkExecution)
      || (task.executionAttempt !== null && !checkExecution)
      || (!checkExecution && !canExecuteSelection);
    const checkPlanAgain = review.pending === "plan-again"
      && task.form?.attempt?.recovery?.canCheck && !task.form.attempt.recovery.checking;
    const planAgainLabel = checkPlanAgain ? "Check outcome" : "Plan again";
    planAgain.ariaLabel = planAgainLabel;
    planAgain.title = planAgainLabel;
    planAgain.disabled = (review.pending !== null && !checkPlanAgain) || task.canPlanAgain !== true;
    controls.hidden = !activeExecution;
    const paused = task.executionControlState === "paused";
    pause.dataset.action = paused ? "resume" : "pause";
    pause.ariaLabel = paused ? "Resume execution" : "Pause execution";
    pause.title = pause.ariaLabel;
    pause.className = `nami-button nami-button--${paused ? "primary" : "secondary"} nami-button--icon`;
    pause.ariaPressed = String(paused);
    pauseIcon.hidden = paused;
    playIcon.hidden = !paused;
    pause.disabled = review.pending !== null || controlUnavailable
      || !["running", "paused"].includes(task.executionControlState);
    cancel.disabled = (review.pending !== null && !task.canCancelAfterFixedReviewOutcome)
      || controlUnavailable
      || task.executionControlState === "canceling";
    if (controls.hidden || cancel.disabled
        || (cancelDeadline !== null && performance.now() >= cancelDeadline)) disarmCancel();
    const controlAttempt = task.executionControlAttempt?.sessionId === task.sessionId
      ? task.executionControlAttempt : null;
    const independentCancel = controlAttempt?.independent ? controlAttempt : null;
    const primaryRecovery = review.pending === "execute" || task.executionAttempt?.state === "uncertain"
      ? task.executionAttempt?.recovery
      : review.pending === "plan-again" ? task.form?.attempt?.recovery : review.recovery;
    const controlGuidance = task.executionControlState === "paused" ? "Execution is paused. Resume when ready."
      : task.executionControlState === "pausing" ? "Pausing at the next safe checkpoint."
        : task.executionControlState === "canceling" ? "Canceling at the next safe checkpoint." : "Execution is in progress.";
    const actionMessage = [...new Set([primaryRecovery?.message ?? review.message,
      independentCancel?.recovery?.message ?? independentCancel?.message,
      executionPresentation.advisory,
      controlTitle ? controlGuidance : "",
      isCapacityOnlyExecution(displayExecution) ? "Free target space, then restart task with Plan Again." : ""].filter(Boolean))].join(" ")
      || (task.executionStarted ? terminalState ? "Review item results in Details." : controlGuidance
          : "Review the selected changes before executing.");
    updateText(globalStatus, [facts.textContent, actionMessage].filter(Boolean).join(" · "));
    updateText(status, actionMessage);
    status.title = actionMessage;
    status.hidden = false;
    const checkOutcome = review.recovery?.canCheck || controlAttempt?.recovery?.canCheck;
    retryOutcome.hidden = !checkOutcome && !review.refreshAvailable;
    updateText(retryOutcome, checkOutcome ? "Check outcome" : "Refresh review");
    retryOutcome.disabled = review.recovery?.checking === true || controlAttempt?.recovery?.checking === true;
    renderRows(review, task);
    if (Number.isSafeInteger(review.moveScrollOffset)) {
      // Query removal can grow the spacers; scroll only after their new height exists.
      table.setScrollTop(review.moveScrollOffset * ROW_HEIGHT);
      review.moveScrollOffset = null;
    }
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
    rowMenu.reconcile();
    columns.freeze();
    columns.refresh();
    table?.schedule();
  }

  function dispose() {
    rowMenu.dispose();
    currentTask = null;
    disarmCancel();
    controlTaskId = null;
    controlSessionId = null;
    filterMenu.dispose();
    columns.dispose();
    resizeObserver.disconnect();
    resizeObserved = false;
    if (searchTimer !== null) clearTimeout(searchTimer);
    searchTimer = null;
    // The app keeps read custody across reuse; teardown silently retires panel demand.
    table?.reset();
    table?.dispose();
    table = null;
    current = null;
    renderedRows = null;
  }

  return Object.freeze({ element, render, dispose });
}
