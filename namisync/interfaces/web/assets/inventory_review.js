import { createTableColumns } from "./table_columns.js";
import { taskStatusDigest } from "./task_status.js";
import { createFilterMenu } from "./filter_menu.js";
import { createRowMenu } from "./row_menu.js";
import { createIcon } from "./icons.js";
import { createTree } from "./tree.js";
import { pointerHighlightGesture } from "./row_highlight.js";
import { createIntegrityCell } from "./integrity.js";
import { formatByteCount, formatFilesystemPath, formatLocalDateTime, renderFilesystemText, renderText } from "./render.js";

const FACETS = Object.freeze([
  ["present", "Present"], ["unverified", "Unverified"], ["verified", "Verified"],
  ["modified", "Modified"], ["reappeared", "Reappeared"], ["unsupported", "Unsupported"],
  ["missing", "Missing"], ["mismatched", "Mismatch"], ["acknowledged", "Acknowledged"],
  ["notice", "Notice"], ["recall", "Not fully local"],
]);
const label = (value) => FACETS.find(([key]) => key === value)?.[1] ?? value;
const integrityLabel = (value) => ({baselined: "Baselined", canceled: "Canceled",
  error: "Error"})[value] ?? label(value);
const bytes = (value) => value === null ? "Unavailable" : formatByteCount(value);

function modifiedTime(value) {
  if (value === null) return "Unavailable";
  return formatLocalDateTime(Number(BigInt(value) / 1000000n)) ?? "Unavailable";
}

function element(tag, className = "", text = "") {
  const value = document.createElement(tag);
  value.className = className;
  renderText(value, text);
  return value;
}

function button(text, action) {
  const value = element("button", "nami-button", text);
  value.type = "button";
  value.dataset.action = action;
  return value;
}

function rollupText(rollup) {
  return `${rollup.domain_count} items · ${rollup.file_count} files · ${bytes(rollup.size)}`
    + (rollup.size_overflow ? " (size overflow)" : rollup.size_partial ? " (partial size)" : "");
}

export function createInventoryReviewPanel(callbacks) {
  const pane = element("section", "nami-inventory-review");
  pane.ariaLabel = "Inventory review";
  for (const name of ["pointerdown", "wheel", "touchstart", "input", "contextmenu"]) {
    pane.addEventListener(name, () => {
      selectionFocus = null;
      tree?.cancelNavigation();
      if (current !== null) callbacks.onInterrupt?.(current);
    }, { capture: true, passive: true });
  }
  for (const name of ["pointerdown", "wheel", "touchstart", "input", "contextmenu", "keydown"]) {
    document.addEventListener(name, (event) => {
      if (!pane.contains(event.target)) {
        selectionFocus = null;
        tree?.cancelNavigation();
        if (current !== null) callbacks.onInterrupt?.(current);
      }
    }, { capture: true, passive: true });
  }
  pane.addEventListener("keydown", (event) => {
    selectionFocus = null;
    if (event.altKey || event.ctrlKey || event.metaKey
        || !["ArrowUp", "ArrowDown"].includes(event.key)
        || event.target !== rows) {
      tree?.cancelNavigation();
      if (current !== null) callbacks.onInterrupt?.(current);
    }
  }, true);
  document.addEventListener("focusin", (event) => {
    if (selectionFocus !== null && event.target !== selectionFocus.control) selectionFocus = null;
  }, true);
  const header = element("div", "nami-card nami-plan-review__plan nami-inventory-review__header");
  const switcher = element("div", "nami-segmented nami-plan-review__view-switcher");
  switcher.setAttribute("role", "radiogroup");
  switcher.ariaLabel = "Task type";
  const planPane = button("Sync", "pane-plan");
  planPane.className = "nami-segmented__item";
  planPane.setAttribute("role", "radio");
  const verifyPane = button("Integrity", "pane-verify");
  verifyPane.className = "nami-segmented__item";
  verifyPane.setAttribute("role", "radio");
  planPane.addEventListener("click", () => {
    if (task !== null && !planPane.disabled) callbacks.onPaneChange?.(task, "plan");
  });
  verifyPane.addEventListener("click", () => {
    if (task !== null && !verifyPane.disabled) callbacks.onPaneChange?.(task, "verify");
  });
  switcher.append(planPane, verifyPane);
  const paths = element("div", "nami-plan-review__paths");
  const rootLine = element("p", "nami-plan-review__path nami-labeled-path");
  const rootPath = element("span", "nami-labeled-path__value");
  rootLine.append(element("span", "", "Root:"), rootPath);
  paths.append(rootLine);
  header.append(switcher, paths);
  const summary = element("div", "nami-card nami-plan-review__summary");
  const title = element("p", "nami-plan-review__status-title", "Inventory");
  title.setAttribute("role", "status");
  title.tabIndex = -1;
  const facts = element("p", "nami-shell__guidance nami-plan-review__status-summary");
  const selectionSummary = element("p", "nami-shell__guidance nami-inventory-review__selection-summary");
  selectionSummary.dataset.inventorySelectionSummary = "";
  const statusLine = element("p", "nami-shell__guidance nami-inventory-review__status-line");
  statusLine.setAttribute("role", "status");
  const integrityResult = element("div", "nami-shell__guidance nami-inventory-review__integrity-result");
  integrityResult.dataset.integrityResult = "";
  const refresh = button("Refresh inventory", "inventory-refresh");
  const refreshSelected = button("Refresh selected", "inventory-refresh-selected");
  refresh.classList.add("nami-button--primary");
  const baseline = button("Baseline", "inventory-baseline");
  const verify = button("Verify", "inventory-verify");
  const copiedVerify = button("Verify copied files", "verify-copied-files");
  copiedVerify.classList.add("nami-button--primary");
  const rebaseline = button("Rebaseline", "inventory-rebaseline");
  verify.classList.add("nami-button--primary");
  const pause = button("Pause", "inventory-pause");
  const resume = button("Resume", "inventory-resume");
  const cancel = button("Cancel", "inventory-cancel");
  const check = button("Check original outcome", "inventory-check-outcome");
  const reload = button("Reload inventory view", "inventory-reload");
  const statusActions = element("div", "nami-plan-review__actions");
  const actions = element("div", "nami-inventory-review__actions");
  actions.append(baseline, verify, rebaseline, copiedVerify, pause, resume, cancel, refreshSelected, refresh, reload);
  statusActions.append(title, actions);
  const statusMeta = element("div", "nami-plan-review__status-meta");
  const detailsToggle = button("Details", "inventory-details");
  detailsToggle.classList.add("nami-button--clear", "nami-plan-review__details-toggle");
  detailsToggle.ariaExpanded = "false";
  statusMeta.append(facts, detailsToggle);
  const progress = element("div", "nami-progress nami-plan-review__progress");
  progress.ariaHidden = "true";
  const progressBar = element("div", "nami-progress__bar");
  progress.append(progressBar);
  const recoveryActions = element("div", "nami-inventory-review__actions");
  recoveryActions.append(check);
  summary.append(statusActions, statusMeta, selectionSummary, statusLine, integrityResult, recoveryActions, progress);

  const table = element("div", "nami-card nami-plan-review__table-card nami-inventory-review__table");
  const floatingControls = element("div", "nami-plan-review__floating-controls");
  const goCurrent = button("Go to current item", "go-current-item");
  const enableFollow = button("Turn on autoscroll", "enable-item-follow");
  enableFollow.classList.add("nami-button--primary");
  floatingControls.append(goCurrent, enableFollow);
  goCurrent.addEventListener("click", () => {
    if (current !== null && !goCurrent.disabled) callbacks.onNavigateCurrent?.(current, false);
  });
  enableFollow.addEventListener("click", () => {
    if (current !== null && !enableFollow.disabled) callbacks.onNavigateCurrent?.(current, true);
  });
  const toolbar = element("div", "nami-plan-review__toolbar");
  const filters = element("div", "nami-plan-review__filters");
  filters.ariaLabel = "Inventory filters";
  const filterMenu = createFilterMenu(FACETS, (selected) => {
    if (current !== null && !blocked()) callbacks.onViewChange(current, { filters: [...selected] });
  });
  filters.append(filterMenu.element);
  const searchBox = element("div", "nami-plan-review__search");
  const search = element("input", "nami-input");
  search.type = "search";
  search.placeholder = "Search inventory";
  search.autocomplete = "off";
  search.ariaLabel = "Search inventory";
  search.dataset.action = "inventory-search";
  const submit = button("", "inventory-search-submit");
  submit.className = "nami-button nami-button--clear nami-button--icon nami-plan-review__search-submit";
  submit.ariaLabel = "Search now";
  submit.append(createIcon(document, "search", "sm"));
  const clear = button("", "inventory-search-clear");
  clear.className = "nami-button nami-button--clear nami-button--icon nami-plan-review__search-clear";
  clear.ariaLabel = "Clear search";
  clear.append(createIcon(document, "dismiss", "sm"));
  searchBox.append(search, clear, submit);
  toolbar.append(filters, searchBox);

  const list = element("div", "nami-file-list nami-table-scroll nami-table-scroll--single nami-inventory-review__list");
  const grid = element("div", "nami-file-list__grid nami-table-layout nami-inventory-review__grid");
  const columnHeader = element("div", "nami-file-list__header nami-table__header nami-inventory-review__columns");
  const columnNames = ["selection", "name", "primary", "secondary", "size", "modified", "notes"];
  const sortHeaders = new Map();
  let headerSelection = null;
  for (const [index, [text, column]] of [
    ["Selection", null], ["Filename", "filename"], ["Presence", null], ["Checksum", null],
    ["Size", "size"], ["Modified", "mtime"], ["Notes", null],
  ].entries()) {
    const cell = element("div", "nami-file-list__header-cell");
    if (index === 0) {
      cell.ariaLabel = text;
      const checkbox = element("input", "nami-checkbox");
      checkbox.type = "checkbox";
      checkbox.checked = false;
      checkbox.indeterminate = false;
      checkbox.dataset.action = "inventory-select-location";
      checkbox.ariaLabel = "Select all matching files in this location, including collapsed and off-window files";
      for (const eventName of ["pointerdown", "click", "change"]) {
        checkbox.addEventListener(eventName, (event) => event.stopPropagation());
      }
      checkbox.addEventListener("change", () => {
        if (current !== null && !checkbox.disabled) callbacks.onSelect?.(current, null, checkbox.checked);
      });
      headerSelection = checkbox;
      cell.append(checkbox);
    } else if (column === null) renderText(cell, text);
    else {
      const sortButton = button("", `inventory-sort-${column}`);
      sortButton.className = "nami-plan-review__sort";
      sortButton.dataset.sortColumn = column;
      const up = createIcon(document, "chevron-up", "sm");
      const down = createIcon(document, "chevron-down", "sm");
      up.hidden = true;
      down.hidden = true;
      sortButton.append(element("span", "", text), up, down);
      cell.append(sortButton);
      sortHeaders.set(column, { cell, sortButton, up, down });
    }
    if (index < columnNames.length - 1) {
      const resizer = element("div", "nami-file-list__column-resizer");
      resizer.dataset.columnIndex = String(index);
      resizer.dataset.column = columnNames[index];
      resizer.setAttribute("role", "separator");
      resizer.ariaOrientation = "vertical";
      resizer.ariaLabel = `Resize ${text} column`;
      resizer.tabIndex = 0;
      cell.append(resizer);
    }
    columnHeader.append(cell);
  }
  const rows = element("div", "nami-table__body nami-inventory-review__rows");
  rows.ariaLabel = "Inventory items";
  grid.append(columnHeader, rows);
  list.append(grid);
  const columns = createTableColumns(grid, [...columnHeader.children], columnNames, [2, 12, 8, 7, 5, 7, 14], 1, 6);
  const empty = element("p", "nami-shell__guidance", "No items match this view.");
  table.append(toolbar, list, empty, floatingControls);

  const detail = element("section", "nami-card nami-plan-review__detail nami-inventory-review__detail");
  detail.tabIndex = 0;
  detail.ariaLabel = "Inventory item details";
  const detailTitle = element("h2", "", "Item details");
  const detailHeader = element("div", "nami-plan-review__detail-header");
  detailHeader.append(detailTitle);
  const detailStatus = element("p", "nami-shell__guidance");
  detailStatus.setAttribute("role", "status");
  const detailActions = element("div", "nami-inventory-review__actions");
  const acknowledge = button("Acknowledge missing", "inventory-acknowledge");
  const restore = button("Restore visibility", "inventory-restore");
  detailActions.append(acknowledge, restore);
  const scopeHint = element("p", "nami-shell__guidance");
  const detailBody = element("dl", "nami-plan-review__detail-body");
  detail.append(detailHeader, detailStatus, detailActions, scopeHint, detailBody);
  const content = element("div", "nami-inventory-review__content");
  content.append(table);
  const diagnostics = element("div", "nami-plan-review__diagnostics nami-inventory-review__diagnostics");
  diagnostics.hidden = true;
  const globalDetails = element("section", "nami-card nami-plan-review__global-diagnostics");
  globalDetails.tabIndex = 0;
  globalDetails.ariaLabel = "Inventory task details";
  const globalFacts = element("p", "nami-shell__guidance");
  const globalScanFacts = element("p", "nami-shell__guidance");
  const globalScanState = element("p", "nami-shell__guidance");
  globalDetails.append(element("h2", "", "Task details"), globalScanState, globalScanFacts, globalFacts);
  diagnostics.append(globalDetails, detail);
  pane.append(header, summary, content, diagnostics);

  let detailsExpanded = false;
  let current = null;
  let task = null;
  let tree = null;
  let committedWindow = null;
  let activeNodeId = null;
  let activeRefreshTarget = null;
  let rowOrdinaryItems = new Map();
  let rowOrdinaryMode = null;
  let rowOrdinarySessionId = null;
  let renderedProgress = null;
  const selectionControls = new Map();
  let selectionFocus = null;
  let searchTimer = null;
  let searchDraft = false;
  const rowMenu = createRowMenu(pane);
  list.addEventListener("scroll", () => {
    if (current !== null) current.scrollTop = list.scrollTop;
  }, {passive: true});

  function blocked() { return task?.closePending || task?.inventoryLoading || current?.pending
    || task?.inventoryAction?.pending || task?.inventoryAction?.accepted; }
  function matchingIntegrity(candidate) {
    const result = candidate ?? null;
    return result !== null && current !== null
      && result.location_id === current.summary.location_id
      ? result : null;
  }
  function currentIntegrity() { return matchingIntegrity(current?.window?.integrity); }
  function selectionBlocked() {
    return blocked() || !task?.sessionReleased || task.sessionState === "active"
      || current?.summary.request_id !== task?.requestId || task?.inventoryViewUnconfirmed;
  }
  function activeRow() {
    return current?.window.rows.find((row) => row.node_id === activeNodeId) ?? activeRefreshTarget;
  }
  function refreshTarget(row) {
    return {node_id:row.node_id, warning:row.warning === null ? null : true,
      viewRevision:current.summary.view_revision, publication:current.summary.request_id};
  }
  function updateRefreshSelected() {
    const row = activeRow();
    refreshSelected.disabled = row === null || row.warning !== null || Boolean(blocked())
      || !task?.sessionReleased || task.sessionState === "active";
  }
  function updateSelectionControls() {
    if (headerSelection !== null) {
      headerSelection.checked = current?.summary.selection === "all";
      headerSelection.indeterminate = current?.summary.selection === "partial";
      headerSelection.disabled = current === null || current.summary.scope_selectable_file_count === 0
        || selectionBlocked();
    }
    for (const row of current?.window.rows ?? []) {
      const checkbox = selectionControls.get(row.node_id);
      if (checkbox === undefined) continue;
      checkbox.checked = row.selection === "all";
      checkbox.indeterminate = row.selection === "partial";
      checkbox.disabled = !row.selectable || selectionBlocked();
    }
  }
  function submitSearch() {
    clearTimeout(searchTimer);
    searchTimer = null;
    if (current === null || task?.closePending) return;
    callbacks.onViewChange(current, { searchQuery: search.value });
  }
  search.addEventListener("input", () => {
    searchDraft = true;
    clear.hidden = search.value === "";
    clearTimeout(searchTimer);
    searchTimer = setTimeout(submitSearch, 150);
  });
  search.addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); submitSearch(); }
  });
  submit.addEventListener("click", submitSearch);
  clear.addEventListener("click", () => {
    search.value = "";
    searchDraft = true;
    clear.hidden = true;
    search.focus();
    submitSearch();
  });
  for (const [column, { sortButton }] of sortHeaders) {
    sortButton.addEventListener("click", () => {
      if (current === null || blocked()) return;
      const same = current.summary.sort_column === column;
      callbacks.onViewChange(current, same && current.summary.sort_direction === "descending"
        ? { sortColumn: "path", sortDirection: "ascending" }
        : { sortColumn: column, sortDirection: same ? "descending" : "ascending" });
    });
  }
  detailsToggle.addEventListener("click", () => {
    detailsExpanded = !detailsExpanded;
    detailsToggle.ariaExpanded = String(detailsExpanded);
    if (!detailsExpanded && diagnostics.contains(document.activeElement)) detailsToggle.focus();
    diagnostics.hidden = !detailsExpanded;
  });
  const resizeObserver = new window.ResizeObserver(() => {
    if (current !== null) { columns.freeze(); columns.refresh(); }
  });
  resizeObserver.observe(list);
  reload.addEventListener("click", () => { if (task !== null) callbacks.onReload(task); });
  refresh.addEventListener("click", () => {
    if (task !== null && current !== null && !blocked()) callbacks.onRefresh(current, null, refresh);
  });
  check.addEventListener("click", () => {
    if (task === null || check.disabled) return;
    if (task.form?.attempt?.kind === "inventory") callbacks.onCheckStart?.();
    else callbacks.onCheckOutcome(task);
  });
  refreshSelected.addEventListener("click", () => {
    updateRefreshSelected();
    const row = activeRow();
    if (!refreshSelected.disabled) callbacks.onRefresh(current, row.node_id, refreshSelected);
  });
  for (const [control, mode] of [[baseline, "baseline"], [verify, "verify"], [rebaseline, "rebaseline"]]) {
    control.addEventListener("click", () => {
      if (current !== null && !control.disabled) callbacks.onStart?.(current, mode, control);
    });
  }
  copiedVerify.addEventListener("click", () => {
    if (current !== null && !copiedVerify.disabled) callbacks.onCopiedStart?.(current);
  });
  for (const [control, action] of [[pause, "pause"], [resume, "resume"], [cancel, "cancel"]]) {
    control.addEventListener("click", () => {
      if (current !== null && !control.disabled) callbacks.onControl?.(current, action);
    });
  }
  acknowledge.addEventListener("click", () => {
    const row = current?.detail?.row;
    if (row !== undefined && row.warning === null && !blocked()) callbacks.onVisibility(current, "acknowledge", row.node_id);
  });
  restore.addEventListener("click", () => {
    const row = current?.detail?.row;
    if (row !== undefined && row.warning === null && !blocked()) callbacks.onVisibility(current, "restore", row.node_id);
  });

  function renderPresence(state, row) {
    const ordinaryItem = row.is_container ? null : rowOrdinaryItems.get(row.row_id) ?? null;
    const presentation = task?.progressPresentation;
    const active = presentation?.activeItem;
    const live = !row.is_container && row.warning === null && row.row_id !== null
      && task.sessionState === "active" && task.snapshot?.session_id === task.sessionId
      && task.snapshot.session_state === "active"
      && ["baseline", "verify", "rebaseline"].includes(task.sessionKind)
      && active?.item_type === "integrity"
      && active.item_id === `${current.summary.location_id}:${row.row_id}`
      && !(rowOrdinarySessionId === task.sessionId && ordinaryItem !== null);
    const stateKey = row.warning !== null || row.row_id === null ? ""
      : row.presence !== "present" ? row.presence
      : row.is_container ? row.reappeared ? "reappeared"
        : ["error", "unsupported"].includes(row.verification_state) ? row.verification_state : ""
      : row.verification_state === "mismatched" ? "mismatched"
      : row.reappeared ? "reappeared" : row.verification_state;
    const owner = ({baseline: "Baseline", verify: "Verification", rebaseline: "Rebaseline"})[rowOrdinaryMode] ?? "Integrity";
    const liveLabel = ({baseline: "Baselining", verify: "Verifying", rebaseline: "Rebaselining"})[task?.sessionKind];
    const percent = live && Number.isFinite(presentation.itemPercent) ? presentation.itemPercent : undefined;
    const stateText = live ? liveLabel : ordinaryItem !== null ? integrityLabel(ordinaryItem.result)
      : row.warning !== null ? "Notice" : integrityLabel(stateKey);
    const content = createIntegrityCell(document, "", "primary",
      live ? "" : ordinaryItem?.result ?? stateKey, live && percent !== undefined ? "verifying" : undefined,
      stateText, percent);
    state.replaceChildren(...Array.from(content.children));
    delete state.dataset.integrity;
    delete state.dataset.lifecycle;
    delete state.dataset.integrityState;
    Object.assign(state.dataset, content.dataset);
    if (!live && ordinaryItem !== null) state.dataset.integrityState = ordinaryItem.result;
    state.title = live ? stateText : ordinaryItem !== null
      ? [owner, integrityLabel(ordinaryItem.result), ordinaryItem.reason, ordinaryItem.recording,
        ordinaryItem.record_disposition, ordinaryItem.detail_omitted_count > 0
          ? `${ordinaryItem.detail_omitted_count} details omitted` : null].filter(Boolean).join(" · ")
      : row.is_container || row.row_id === null ? stateText
        : `${label(row.presence)} · ${label(row.verification_state)}${row.reappeared ? " · Reappeared" : ""}`;
  }

  function decorateRow(rowElement, row) {
    rowElement.classList.add("nami-file-row", "nami-inventory-row");
    rowElement.dataset.folder = String(row.is_container);
    rowElement.style.setProperty("--nami-file-depth", String(row.depth));
    const name = element("div", "nami-file-row__cell nami-file-row__name nami-inventory-row__name");
    const disclosure = rowElement.children[0];
    disclosure.classList.add("nami-file-row__disclosure");
    const chevron = element("span", "nami-file-row__chevron");
    chevron.ariaHidden = "true";
    disclosure.append(chevron);
    rowElement.children[1].classList.add("nami-file-row__name-text");
    name.append(...Array.from(rowElement.children));
    if (row.recall) {
      const availability = element("span", "nami-file-row__availability");
      availability.setAttribute("role", "img");
      availability.ariaLabel = "Not fully available locally. Access may retrieve content through your provider.";
      availability.title = availability.ariaLabel;
      availability.append(createIcon(document, "cloud-arrow-down", "sm"));
      name.append(availability);
    }
    const selection = element("div", "nami-file-row__cell nami-file-row__selection");
    const checkbox = element("input", "nami-checkbox");
    checkbox.type = "checkbox";
    checkbox.dataset.action = "inventory-select-row";
    checkbox.checked = row.selection === "all";
    checkbox.indeterminate = row.selection === "partial";
    checkbox.disabled = !row.selectable || selectionBlocked();
    checkbox.ariaLabel = row.is_container
      ? `Select matching files in folder ${row.display}, including collapsed and off-window files`
      : `Select file ${row.display}`;
    for (const eventName of ["pointerdown", "click", "change"]) {
      checkbox.addEventListener(eventName, (event) => event.stopPropagation());
    }
    checkbox.addEventListener("change", () => {
      if (current !== null && !checkbox.disabled) {
        if (row.highlighted && callbacks.onHighlightedSelect !== undefined) callbacks.onHighlightedSelect(current, checkbox.checked);
        else callbacks.onSelect?.(current, row.node_id, checkbox.checked);
      }
    });
    selectionControls.set(row.node_id, checkbox);
    selection.append(checkbox);
    rowElement.replaceChildren(selection, name);
    const state = element("div", "nami-file-row__cell nami-inventory-row__state nami-integrity-row__presence");
    renderPresence(state, row);
    const checksum = element("div", "nami-file-row__cell nami-inventory-row__checksum nami-integrity-row__checksum", row.recorded_checksum?.slice(0, 8) ?? "—");
    checksum.title = row.recorded_checksum === null ? "No stored baseline evidence" : `Stored baseline checksum: ${row.recorded_checksum}`;
    const sizeText = row.warning !== null ? "" : row.is_container
      ? bytes(row.rollup.size)
      : bytes(row.size);
    const size = element("div", "nami-file-row__cell nami-file-row__size nami-inventory-row__size", sizeText);
    size.title = row.warning !== null ? "" : row.is_container
      ? `Complete folder files: ${sizeText}${row.rollup.size_overflow ? " (overflow)" : row.rollup.size_partial ? " (partial)" : ""}. Own object size: ${bytes(row.size)}.`
      : `Own file size: ${sizeText}.`;
    const modified = element("div", "nami-file-row__cell nami-plan-row__modified nami-inventory-row__modified", row.warning === null ? modifiedTime(row.mtime_ns) : "");
    modified.title = row.mtime_ns === null ? "" : `Own modified time: ${row.mtime_ns} ns`;
    const notesText = [row.warning?.detail, row.acknowledged ? "Acknowledged" : null,
      row.warning === null && row.is_container && row.rollup.size_overflow ? "Size overflow" : null,
      row.warning === null && row.is_container && row.rollup.size_partial ? "Partial size" : null]
      .filter(Boolean).join(" · ");
    const notes = element("div", "nami-file-row__cell nami-file-row__notes", notesText);
    notes.title = notesText;
    rowElement.dataset.highlighted = String(row.highlighted === true);
    rowElement.ariaSelected = String(row.highlighted === true);
    rowElement.append(state, checksum, size, modified, notes);
  }

  function ensureTree() {
    if (tree !== null) return;
    tree = createTree(rows, {
      initialActive: activeNodeId === null ? null : {
        nodeId:activeNodeId, visibleIndex:current.window.anchor_visible_index,
      },
      interactionAllowed: () => !blocked(),
      manualScroll: (first, last) => {
        if (current !== null) callbacks.onFollowOverride?.(current, first, last);
      },
      decorateRow,
      requestCancelled: (generation) => {
        if (current !== null) callbacks.onWindowCancelled?.(current, generation);
      },
      activeChanged: (nodeId) => {
        activeNodeId = nodeId;
        const row = current?.window.rows.find(value => value.node_id === nodeId);
        activeRefreshTarget = row === undefined ? null : refreshTarget(row);
        if (current !== null) {
          current.activeNodeId = nodeId;
          current.activeRefreshTarget = activeRefreshTarget;
        }
        updateRefreshSelected();
      },
      context: (nodeId, event, rowElement) => {
        event.preventDefault();
        event.stopPropagation();
        const review = current;
        const owner = task;
        const window = review?.window;
        const row = window?.rows.find((value) => value.node_id === nodeId);
        if (row === undefined) return;
        const actionRevision = review.actionRevision;
        const viewRevision = review.summary.view_revision;
        const publication = review.summary.request_id;
        const sessionId = owner.sessionId;
        const isCurrent = () => current === review && task === owner
          && review.activeNodeId === nodeId && review.actionRevision === actionRevision
          && review.summary.view_revision === viewRevision && review.summary.request_id === publication
          && owner.sessionId === sessionId
          && !blocked() && owner.closeRecovery == null;
        const actionBlocked = !owner.sessionReleased || owner.sessionState === "active";
        const actions = [{ id: "row-details", label: "Show details", run: () => {
          detailsExpanded = true;
          detailsToggle.ariaExpanded = "true";
          diagnostics.hidden = false;
          callbacks.onDetail(review, nodeId);
        } }];
        if (row.is_container && row.expanded !== null) {
          actions.push({ id: "row-collapse", label: row.expanded ? "Collapse" : "Expand",
            run: () => callbacks.onViewChange(review, { collapseNodeId: nodeId, collapsed: row.expanded }) });
        }
        if (row.warning === null && !actionBlocked) {
          actions.push({ id: "row-refresh", label: "Refresh selected",
            run: () => callbacks.onRefresh(review, nodeId,
              [...rows.children].find(value => value.dataset.nodeId === nodeId) ?? refreshSelected) });
          if (row.presence === "missing" && !row.acknowledged
              && review.summary.request_id === owner.requestId && !owner.inventoryViewUnconfirmed) {
            actions.push({ id: "row-acknowledge", label: "Acknowledge missing",
              run: () => callbacks.onVisibility(review, "acknowledge", nodeId) });
          }
        }
        filterMenu.close();
        rowMenu.open(event, rowElement, rows, actions, isCurrent);
      },
      toggle: (nodeId, expanded) => {
        if (current !== null && !blocked()) callbacks.onViewChange(current, {
          collapseNodeId: nodeId, collapsed: !expanded,
        });
      },
      highlight: typeof callbacks.onHighlight !== "function" ? undefined : (gesture, nodeId) => {
        if (current !== null && !blocked()) callbacks.onHighlight(current, gesture, nodeId);
      },
      activate: (nodeId, event) => {
        if (current === null || blocked()) return;
        if (event !== undefined) callbacks.onHighlight?.(current, pointerHighlightGesture(event), nodeId);
        callbacks.onDetail(current, nodeId);
      },
      requestIndex: async (index, generation, offset) => {
        const owner = current;
        const controller = tree;
        if (owner === null || blocked()) {
          controller.finishWindowRequest(generation);
          return;
        }
        const window = await callbacks.onWindow(owner, offset);
        if (current !== owner || tree !== controller) return;
        if (window === null) {
          controller.finishWindowRequest(generation);
          return;
        }
        if (commitTreeWindow(controller, generation, window)) {
          owner.window = window;
          committedWindow = window;
          updateRefreshSelected();
        }
      },
    }, 24, list, 24);
  }

  function commitTreeWindow(controller, generation, window, preferredNodeId = null, reveal = true, passive = false) {
    const ordinary = matchingIntegrity(window.integrity);
    rowOrdinaryItems = new Map((ordinary?.items ?? []).map((item) => [item.row_id, item]));
    rowOrdinaryMode = ordinary?.mode ?? null;
    rowOrdinarySessionId = ordinary?.session_id ?? null;
    const accepted = passive ? controller.commitPassiveWindow(generation, window)
      : controller.commitWindow(generation, window, preferredNodeId, reveal);
    if (accepted) {
      const row = window.rows.find(value => value.node_id === activeNodeId);
      if (row !== undefined) activeRefreshTarget = refreshTarget(row);
      else if (activeRefreshTarget !== null && window.anchor_node_id === activeNodeId
          && window.anchor_visible_index !== null) {
        activeRefreshTarget = {...activeRefreshTarget,
          viewRevision:current.summary.view_revision, publication:current.summary.request_id};
      }
      if (current !== null) current.activeRefreshTarget = activeRefreshTarget;
    }
    return accepted;
  }

  function appendDetail(key, value, filesystem = false) {
    const term = element("dt", "", key);
    const description = element("dd");
    (filesystem ? renderFilesystemText : renderText)(description, value ?? "Unavailable");
    detailBody.append(term, description);
  }
  function subjectDetails(prefix, subject) {
    appendDetail(`${prefix} kind`, subject?.kind ?? null);
    appendDetail(`${prefix} size`, subject === null ? null : `${bytes(subject.size)} (${subject.size} bytes)`);
    appendDetail(`${prefix} modified`, subject === null ? null : `${modifiedTime(subject.mtime_ns)} (${subject.mtime_ns} ns)`);
    appendDetail(`${prefix} identity`, subject?.file_identity === null || subject === null ? null
      : `${subject.file_identity.volume_serial}:${subject.file_identity.file_index}`);
  }
  function renderDetails() {
    detailBody.replaceChildren();
    const selected = current?.detail ?? null;
    if (selected === null) {
      renderText(detailTitle, "Item details");
      renderText(detailStatus, "Select an item to see its details.");
      return;
    }
    renderFilesystemText(detailTitle, selected.row.display);
    renderText(detailStatus, selected.state === "loading" ? "Loading current evidence…"
      : selected.state === "unavailable" ? "This item has no current ledger row. Select another item."
      : selected.state === "error" ? "Details unavailable. Select the item again to retry."
      : selected.row.warning !== null ? "Scan notice" : selected.row.row_id === null ? "Folder summary" : "Current ledger evidence");
    const row = selected.row;
    if (row.warning !== null) {
      appendDetail("Notice", row.warning.code);
      if (selected.state === "current") {
        appendDetail("Path at scan time", formatFilesystemPath(current.summary.root_path, selected.response.snapshot.path), true);
        appendDetail("Details", selected.response.snapshot.warning.detail);
      }
      return;
    }
    if (row.is_container) {
      appendDetail("Complete folder scope", rollupText(row.rollup));
      for (const [key, text] of FACETS) {
        if (key !== "notice" && key !== "recall") appendDetail(`Folder ${text.toLowerCase()}`, String(row.rollup[key]));
      }
    }
    if (row.row_id === null) {
      if (row.is_container && selected.state === "current") {
        appendDetail("Path at scan time", formatFilesystemPath(current.summary.root_path, selected.response.snapshot.path), true);
      }
      return;
    }
    if (selected.state !== "current") return;
    const value = selected.response.detail;
    appendDetail("Path", formatFilesystemPath(current.summary.root_path, value.row.path), true);
    appendDetail("Presence", label(value.row.presence));
    appendDetail("Verification state", label(value.row.verification_state));
    subjectDetails("Observed", value.observed);
    appendDetail("Last observed", formatLocalDateTime(value.row.last_observed_at));
    appendDetail("Last verified", formatLocalDateTime(value.row.last_verified_at));
    appendDetail("Missing since", formatLocalDateTime(value.row.missing_since));
    appendDetail("Acknowledged", formatLocalDateTime(value.row.acknowledged_at));
    appendDetail("Reappeared", formatLocalDateTime(value.row.reappeared_at));
    appendDetail("Verification invalidated", formatLocalDateTime(value.row.verification_invalidated_at));
    appendDetail("Invalidation reason", value.row.verification_invalidated_reason);
    appendDetail("Unsupported reason", value.row.unsupported_reason);

    const ordinary = matchingIntegrity(selected.response.integrity) ?? currentIntegrity();
    const ordinaryItem = ordinary?.items.find((item) => item.row_id === row.row_id) ?? null;
    if (ordinaryItem !== null) {
      appendDetail(`${({baseline: "Baseline", verify: "Verification", rebaseline: "Rebaseline"})[ordinary.mode]} result`, integrityLabel(ordinaryItem.result));
      appendDetail("Result reason", ordinaryItem.reason);
      appendDetail("Recording", ordinaryItem.recording);
      appendDetail("Record disposition", ordinaryItem.record_disposition);
      appendDetail("Omitted result details", String(ordinaryItem.detail_omitted_count));
    }
    if (value.attestation === null) {
      appendDetail("Stored digest", "No baseline evidence");
      return;
    }
    appendDetail("Stored digest", value.attestation.content.digest);
    appendDetail("Algorithm", value.attestation.content.algorithm);
    appendDetail("Provenance", value.attestation.content.provenance);
    appendDetail("Evidence observed", formatLocalDateTime(value.attestation.content.observed_at));
    subjectDetails("Attested", value.attestation.subject);
  }

  function dispose() {
    selectionFocus = null;
    if (current !== null) callbacks.onInterrupt?.(current);
    rowMenu.dispose();
    filterMenu.dispose();
    columns.dispose();
    resizeObserver.disconnect();
    detailsExpanded = false;
    diagnostics.hidden = true;
    detailsToggle.ariaExpanded = "false";
    clearTimeout(searchTimer);
    searchTimer = null;
    if (current !== null) current.scrollTop = list.scrollTop;
    tree?.dispose();
    tree = null;
    committedWindow = null;
    activeNodeId = null;
    activeRefreshTarget = null;
    rowOrdinaryItems.clear();
    rowOrdinaryMode = null;
    rowOrdinarySessionId = null;
    renderedProgress = null;
    selectionControls.clear();
    current = null;
    task = null;
    searchDraft = false;
  }

  function render(value) {
    const focusInDetails = diagnostics.contains(document.activeElement);
    const review = value.inventoryReview ?? null;
    if (current !== review || task?.taskId !== value.taskId) dispose();
    task = value;
    const first = current !== review;
    current = review;
    if (tree === null && review?.activeNodeId === review?.window.anchor_node_id
        && Number.isSafeInteger(review?.window.anchor_visible_index)) {
      activeNodeId = review.activeNodeId;
      activeRefreshTarget = review.activeRefreshTarget;
    }
    resizeObserver.observe(list);
    if (focusInDetails && !detailsExpanded) title.focus();
    detailsToggle.hidden = review === null;
    diagnostics.hidden = review === null || !detailsExpanded;
    const available = review !== null;
    const follow = review?.follow;
    goCurrent.hidden = !available || follow?.hasTarget !== true;
    enableFollow.hidden = goCurrent.hidden || follow?.eligible !== true || follow?.enabled === true;
    goCurrent.disabled = Boolean(blocked());
    enableFollow.disabled = goCurrent.disabled;
    floatingControls.hidden = goCurrent.hidden && enableFollow.hidden;
    const syncTask = value.taskKind === "sync-plan" && value.executionStarted;
    const executionFact = value.originalExecutionFact;
    const copiedScopeEmpty = executionFact?.planRequestId === value.planRequestId
      && value.executionSessionId != null
      && executionFact?.execution?.session_id === value.executionSessionId
      && executionFact.execution.has_successful_copied_files === false;
    refresh.classList.toggle("nami-button--primary", !syncTask);
    switcher.ariaLabel = syncTask ? "Task view" : "Task type";
    renderText(planPane, syncTask ? "Plan" : "Sync");
    renderText(verifyPane, syncTask ? "Verify" : "Integrity");
    planPane.ariaChecked = String(!syncTask ? false : value.workPane === "plan");
    verifyPane.ariaChecked = String(!syncTask || value.workPane === "verify");
    planPane.disabled = !syncTask || value.workPane === "plan";
    verifyPane.disabled = syncTask ? value.workPane === "verify" : false;
    content.hidden = false;
    reload.hidden = value.inventoryError ? value.inventoryReloadAvailable !== true : review?.refreshAvailable !== true;
    reload.disabled = value.inventoryLoading || value.closePending;
    const actionBlocked = !available || blocked() || !value.sessionReleased || value.sessionState === "active";
    refresh.disabled = actionBlocked;
    refresh.hidden = !available;
    const startAttempt = value.form?.attempt?.kind === "inventory" ? value.form.attempt : null;
    const recovery = startAttempt?.recovery ?? value.inventoryAction?.recovery;
    check.hidden = recovery?.canCheck !== true;
    check.disabled = recovery?.checking === true || (startAttempt !== null && !startAttempt.running);
    recoveryActions.hidden = check.hidden;
    renderFilesystemText(rootPath, review?.summary.root_path ?? value.form?.source?.text ?? "");
    rootLine.title = review?.summary.root_path ?? value.form?.source?.text ?? "";
    const ordinary = currentIntegrity();
    const activityKind = (ordinary != null && ordinary.session_id === value.sessionId ? ordinary.mode : null)
      ?? value.snapshot?.terminal_result?.phases?.find(phase => ["baseline", "verify", "rebaseline"].includes(phase.phase))?.phase
      ?? value.snapshot?.phase;
    const activity = ({baseline: "Baseline", verify: "Verification", rebaseline: "Rebaseline"})[activityKind] ?? "Inventory scan";
    const digest = taskStatusDigest(value);
    const auxiliarySession = ["baseline", "verify", "rebaseline"].includes(value.sessionKind);
    summary.dataset.status = value.inventoryError ? "attention" : digest.state;
    renderText(title, auxiliarySession ? digest.title
      : startAttempt !== null || value.sessionState === "active" || value.inventoryLoading ? digest.title
      : value.sessionState === "refused" ? `${activity} did not start`
        : value.sessionState === "failed" ? `${activity} failed`
          : value.sessionState === "canceled" ? `${activity} canceled` : `${activity} completed`);
    progress.className = "nami-progress nami-plan-review__progress"
      + (digest.progress.indeterminate ? " nami-progress--indeterminate" : "");
    progress.dataset.status = digest.state;
    progress.dataset.indeterminate = String(digest.progress.indeterminate);
    progressBar.style.setProperty("--nami-progress-value", `${digest.progress.value}%`);
    renderText(facts, available ? rollupText(review.summary.rollup) : "");
    facts.hidden = !available;
    facts.title = available && !review.summary.filters.includes("acknowledged")
      ? `${review.summary.rollup.acknowledged} acknowledged items hidden as matches; folder context may remain. Show them with the Acknowledged filter.` : "";
    renderText(selectionSummary, available
      ? `${review.summary.selected_file_count} of ${review.summary.selectable_file_count} files selected`
        + (review.summary.hidden_selected_file_count > 0
          ? ` · ${review.summary.hidden_selected_file_count} hidden by filters or search` : "")
      : "");
    selectionSummary.hidden = !available;
    const resultMode = ({baseline: "Baseline", verify: "Verification", rebaseline: "Rebaseline"})[ordinary?.mode];
    renderText(integrityResult, ordinary === null ? ""
      : `${ordinary.complete ? `${resultMode} retained results`
        : ordinary.gap ? `Live ${resultMode.toLowerCase()} results may be incomplete`
          : `Live ${resultMode.toLowerCase()} results`}`
        + ` · ${ordinary.items.length} window result${ordinary.items.length === 1 ? "" : "s"}`);
    integrityResult.hidden = ordinary === null;
    const scanScope = review?.summary.scan_scope;
    const hasScan = available && review.summary.scan_request_id !== null;
    const scopeLabel = scanScope?.kind === "location" ? "Entire location"
      : scanScope?.kind === "item" ? `Item: ${scanScope.path}`
      : scanScope?.kind === "folder" ? `Folder: ${scanScope.path} (including subfolders)` : "Selected items";
    const publication = available
      ? hasScan ? `${review.summary.scan_request_id === value.requestId ? "Displayed scan" : "Previous published scan"}: ${scopeLabel}` : "Current ledger · No inventory scan" : "";
    const detailScopeLabel = scanScope?.kind === "item" ? `Item: ${formatFilesystemPath(review.summary.root_path, scanScope.path)}`
      : scanScope?.kind === "folder" ? `Folder: ${formatFilesystemPath(review.summary.root_path, scanScope.path)} (including subfolders)` : scopeLabel;
    const detailPublication = available
      ? hasScan ? `${review.summary.scan_request_id === value.requestId ? "Displayed scan" : "Previous published scan"}: ${detailScopeLabel}` : "Current ledger · No inventory scan" : "";
    const scanCounts = hasScan
      ? `${review.summary.observed_count} observed · ${review.summary.missing_count} missing · ${review.summary.warning_count} notices from this scan.${scanScope.kind === "location" ? "" : " Other inventory items were not rescanned."}` : "";
    const guidance = value.inventoryError ?? startAttempt?.recovery?.message ?? review?.message
      ?? (value.inventoryLoading ? "Loading inventory view…" : "");
    renderFilesystemText(statusLine, [...new Set([
      available ? `${publication}${hasScan ? ` · ${review.summary.scan_complete ? "" : "incomplete · "}${scanCounts}` : ""}` : "",
      guidance, value.inventoryAction?.message,
      available && syncTask && copiedScopeEmpty && value.sessionReleased
        ? "Execution copied no files successfully. Select files and use Verify current state." : "",
    ].filter(Boolean))].join(" · "));
    renderText(globalScanState, `Current activity: ${value.sessionState === "active" ? "in progress" : value.sessionState}.`);
    renderFilesystemText(globalScanFacts, available
      ? `${detailPublication}${hasScan ? ` · ${review.summary.scan_complete ? "complete" : "incomplete"} · ${scanCounts}` : ""}` : "");
    if (!available) {
      toolbar.hidden = true;
      empty.hidden = true;
      rows.replaceChildren();
      list.ariaRowCount = "1";
      search.disabled = true;
      submit.disabled = true;
      clear.disabled = true;
      for (const { sortButton } of sortHeaders.values()) sortButton.disabled = true;
      rowMenu.close();
      filterMenu.render([], {}, true);
      refreshSelected.disabled = true;
      for (const control of [baseline, verify, rebaseline, copiedVerify, pause, resume, cancel]) control.hidden = true;
      updateSelectionControls();
      detailActions.hidden = true;
      return;
    }
    toolbar.hidden = false;
    renderText(globalFacts, `${rollupText(review.summary.rollup)}. ${review.summary.rollup.acknowledged} acknowledged items. Stored checksums are baseline evidence; a scan does not verify current bytes.`);
    const selected = review.detail?.row ?? null;
    const domain = selected !== null && selected.warning === null;
    const currentPublication = review.summary.request_id === value.requestId && !value.inventoryViewUnconfirmed;
    const currentOrdinary = value.sessionState === "active"
      && ["baseline", "verify", "rebaseline"].includes(value.sessionKind);
    const canStart = value.taskKind === "inventory" && value.sessionReleased && currentPublication
      && review.summary.selected_file_count > 0 && !blocked();
    for (const control of [baseline, rebaseline]) {
      control.hidden = syncTask || currentOrdinary;
      control.disabled = !canStart;
    }
    const currentAuxiliary = currentOrdinary;
    verify.hidden = currentOrdinary;
    verify.disabled = !value.sessionReleased || !currentPublication
      || review.summary.selected_file_count === 0 || Boolean(blocked());
    renderText(verify, syncTask ? "Verify current state" : "Verify");
    copiedVerify.hidden = !syncTask || currentAuxiliary;
    copiedVerify.disabled = copiedScopeEmpty || !value.sessionReleased || !currentPublication || Boolean(blocked());
    pause.hidden = !currentAuxiliary || value.executionControlState === "paused";
    pause.disabled = !currentAuxiliary || value.executionControlState !== "running" || Boolean(blocked());
    resume.hidden = !currentAuxiliary || value.executionControlState !== "paused";
    resume.disabled = !currentAuxiliary || Boolean(blocked());
    cancel.hidden = !currentAuxiliary;
    cancel.disabled = !currentAuxiliary || value.executionControlState === "canceling" || Boolean(blocked());
    const missingCount = selected?.is_container ? selected.rollup.missing
      : selected?.presence === "missing" && !selected.acknowledged ? 1 : 0;
    const acknowledgedCount = selected?.is_container ? selected.rollup.acknowledged
      : selected?.presence === "missing" && selected.acknowledged ? 1 : 0;
    detailActions.hidden = !domain;
    acknowledge.hidden = !domain || missingCount === 0;
    acknowledge.disabled = actionBlocked || !currentPublication;
    restore.hidden = !domain || acknowledgedCount === 0;
    restore.disabled = actionBlocked || !currentPublication;
    renderText(scopeHint, domain && selected.is_container
      ? "Folder actions include all missing items below it, including hidden and off-window items. Restore visibility does not restore files."
      : domain && acknowledgedCount > 0 ? "Restore visibility does not restore the missing file." : "");
    scopeHint.hidden = scopeHint.textContent === "";
    const counts = Object.fromEntries(FACETS.map(([key]) => [key,
      key === "notice" ? review.summary.warning_count
        : key === "recall" ? review.summary.recall_item_count : review.summary.rollup[key]]));
    filterMenu.render(review.summary.filters, counts, Boolean(blocked()));
    if (first || (!searchDraft && review.pending !== "view")) search.value = review.summary.search_query;
    if (review.queuedSearchQuery === null && review.pending === null && search.value === review.summary.search_query) searchDraft = false;
    search.disabled = value.closePending || value.inventoryLoading;
    submit.disabled = search.disabled;
    clear.disabled = search.disabled;
    clear.hidden = search.value === "";
    for (const [column, { cell, sortButton, up, down }] of sortHeaders) {
      const direction = review.summary.sort_column === column ? review.summary.sort_direction : null;
      cell.ariaSort = direction ?? "none";
      up.hidden = direction !== "ascending";
      down.hidden = direction !== "descending";
      sortButton.disabled = Boolean(blocked());
    }
    empty.hidden = review.window.total !== 0;
    ensureTree();
    if (review.pending === "selection" && selectionFocus === null) {
      if (document.activeElement === headerSelection) selectionFocus = {nodeId:null, control:headerSelection};
      else {
        const focused = [...selectionControls].find(([, control]) => control === document.activeElement);
        if (focused !== undefined) selectionFocus = {nodeId:focused[0], control:focused[1]};
      }
    }
    const replacingRows = committedWindow !== review.window || review.keyboardRevealWindow === review.window;
    if (replacingRows) {
      const focusedCheckbox = [...selectionControls].find(([, control]) => control === document.activeElement)?.[0];
      const scrollTop = review.scrollTop ?? list.scrollTop;
      const keyboard = review.keyboardRevealWindow === review.window;
      selectionControls.clear();
      list.scrollTop = scrollTop;
      const generation = tree.beginWindowRequest();
      commitTreeWindow(tree, generation, review.window,
        keyboard ? review.summary.highlight_focus_node_id : null, keyboard,
        review.passiveRevealWindow === review.window);
      review.passiveRevealWindow = null;
      committedWindow = review.window;
      if (!keyboard) list.scrollTop = scrollTop;
      if (focusedCheckbox !== undefined && review.pending !== "selection") {
        selectionControls.get(focusedCheckbox)?.focus?.({preventScroll: true});
      }
      review.keyboardRevealWindow = null;
    }
    const active = value.progressPresentation?.activeItem;
    const progressKey = JSON.stringify([value.sessionId, value.sessionKind, value.sessionState,
      value.snapshot?.session_id, value.snapshot?.session_state, active?.item_type,
      active?.item_id, value.progressPresentation?.itemPercent]);
    if (!replacingRows && renderedProgress?.key !== progressKey) {
      for (const row of review.window.rows) {
        const itemId = `${review.summary.location_id}:${row.row_id}`;
        if (itemId !== active?.item_id && itemId !== renderedProgress?.itemId) continue;
        const rowElement = selectionControls.get(row.node_id)?.parentElement?.parentElement;
        if (rowElement !== undefined && rowElement !== null) renderPresence(rowElement.children[2], row);
      }
    }
    renderedProgress = {key:progressKey, itemId:active?.item_id};
    if (Number.isSafeInteger(follow?.scrollOffset)) {
      tree.revealPassiveRow(follow.scrollOffset);
      follow.scrollOffset = null;
    }
    updateRefreshSelected();
    updateSelectionControls();
    if (selectionFocus !== null && review.pending !== "selection") {
      const retained = selectionFocus;
      selectionFocus = null;
      const control = retained.nodeId === null ? headerSelection : selectionControls.get(retained.nodeId);
      if (!selectionBlocked() && control !== undefined && !control.disabled
          && (document.activeElement === document.body || document.activeElement === retained.control)) {
        control.focus({preventScroll:true});
      }
    }
    columns.freeze();
    columns.refresh();
    renderDetails();
    rowMenu.reconcile();
  }

  return Object.freeze({ element: pane, render, dispose });
}
