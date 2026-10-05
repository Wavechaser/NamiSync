import { createTableColumns } from "./table_columns.js";
import { taskStatusDigest } from "./task_status.js";
import { createFilterMenu } from "./filter_menu.js";
import { createIcon } from "./icons.js";
import { createTree } from "./tree.js";
import { formatByteCount, renderFilesystemText, renderText } from "./render.js";

const FACETS = Object.freeze([
  ["present", "Present"], ["unverified", "Unverified"], ["verified", "Verified"],
  ["modified", "Modified"], ["reappeared", "Reappeared"], ["unsupported", "Unsupported"],
  ["missing", "Missing"], ["mismatched", "Mismatch"], ["acknowledged", "Acknowledged"],
  ["notice", "Notice"],
]);
const label = (value) => FACETS.find(([key]) => key === value)?.[1] ?? value;
const bytes = (value) => value === null ? "Unavailable" : formatByteCount(value);

function modifiedTime(value) {
  if (value === null) return "Unavailable";
  const date = new Date(Number(BigInt(value) / 1000000n));
  return Number.isNaN(date.getTime()) ? "Unavailable" : date.toLocaleString();
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
  const header = element("div", "nami-card nami-plan-review__plan nami-inventory-review__header");
  const switcher = element("div", "nami-segmented nami-plan-review__view-switcher");
  switcher.setAttribute("role", "radiogroup");
  switcher.ariaLabel = "Task type";
  for (const [text, selected] of [["Sync", false], ["Integrity", true]]) {
    const option = button(text, "inventory-mode");
    option.className = "nami-segmented__item";
    option.setAttribute("role", "radio");
    option.ariaChecked = String(selected);
    option.disabled = !selected;
    switcher.append(option);
  }
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
  const statusLine = element("p", "nami-shell__guidance nami-inventory-review__status-line");
  statusLine.setAttribute("role", "status");
  const refresh = button("Refresh inventory", "inventory-refresh");
  const refreshSelected = button("Refresh selected", "inventory-refresh-selected");
  refresh.classList.add("nami-button--primary");
  const check = button("Check original outcome", "inventory-check-outcome");
  const reload = button("Reload inventory view", "inventory-reload");
  const statusActions = element("div", "nami-plan-review__actions");
  const actions = element("div", "nami-inventory-review__actions");
  actions.append(refreshSelected, refresh);
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
  recoveryActions.append(check, reload);
  summary.append(statusActions, statusMeta, statusLine, recoveryActions, progress);

  const table = element("div", "nami-card nami-plan-review__table-card nami-inventory-review__table");
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

  const list = element("div", "nami-file-list nami-table-scroll nami-inventory-review__list");
  const grid = element("div", "nami-file-list__grid nami-table-layout nami-inventory-review__grid");
  const columnHeader = element("div", "nami-file-list__header nami-table__header nami-inventory-review__columns");
  const columnNames = ["name", "primary", "secondary", "size", "modified"];
  const sortHeaders = new Map();
  for (const [index, [text, column]] of [
    ["Filename", "filename"], ["State", null], ["Checksum", null], ["Size", "size"], ["Modified", "mtime"],
  ].entries()) {
    const cell = element("div", "nami-file-list__header-cell");
    if (column === null) renderText(cell, text);
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
  const columns = createTableColumns(grid, [...columnHeader.children], columnNames, [12, 8, 7, 5, 7], 0, 4);
  const empty = element("p", "nami-shell__guidance", "No items match this view.");
  table.append(toolbar, list, empty);

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
  let searchTimer = null;
  let searchDraft = false;

  function blocked() { return task?.closePending || task?.inventoryLoading || current?.pending
    || task?.inventoryAction?.pending; }
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
  resizeObserver.observe(rows);
  reload.addEventListener("click", () => { if (task !== null) callbacks.onReload(task); });
  refresh.addEventListener("click", () => {
    if (task !== null && current !== null && !blocked()) callbacks.onRefresh(current, null);
  });
  check.addEventListener("click", () => {
    if (task !== null) callbacks.onCheckOutcome(task);
  });
  refreshSelected.addEventListener("click", () => {
    const row = current?.detail?.row;
    if (row !== undefined && row.warning === null && !blocked()) callbacks.onRefresh(current, row.node_id);
  });
  acknowledge.addEventListener("click", () => {
    const row = current?.detail?.row;
    if (row !== undefined && row.warning === null && !blocked()) callbacks.onVisibility(current, "acknowledge", row.node_id);
  });
  restore.addEventListener("click", () => {
    const row = current?.detail?.row;
    if (row !== undefined && row.warning === null && !blocked()) callbacks.onVisibility(current, "restore", row.node_id);
  });

  function decorateRow(rowElement, row) {
    rowElement.classList.add("nami-inventory-row");
    const name = element("span", "nami-inventory-row__name");
    name.append(...Array.from(rowElement.children));
    rowElement.replaceChildren(name);
    const stateText = row.warning !== null ? "Notice" : row.row_id === null ? "Folder"
      : [row.acknowledged ? "Acknowledged" : label(row.presence), label(row.verification_state),
        row.reappeared ? "Reappeared" : null].filter(Boolean).join(" · ");
    const state = element("span", "nami-inventory-row__state nami-integrity-row__presence");
    state.append(element("span", "nami-file-state-label", stateText));
    state.dataset.integrity = row.warning !== null || row.row_id === null ? ""
      : row.presence !== "present" ? row.presence
      : row.reappeared && ["unverified", "modified"].includes(row.verification_state)
        ? "reappeared" : row.verification_state;
    const checksum = element("span", "nami-inventory-row__checksum nami-integrity-row__checksum", row.recorded_checksum?.slice(0, 8) ?? "—");
    checksum.title = row.recorded_checksum === null ? "No stored baseline evidence" : `Stored baseline checksum: ${row.recorded_checksum}`;
    state.title = stateText;
    const sizeText = row.warning !== null ? "" : row.is_container
      ? bytes(row.rollup.size) + (row.rollup.size_overflow ? " (overflow)" : row.rollup.size_partial ? " (partial)" : "")
      : bytes(row.size);
    const size = element("span", "nami-inventory-row__size", sizeText);
    size.title = row.warning !== null ? "" : row.is_container
      ? `Complete folder files: ${sizeText}. Own object size: ${bytes(row.size)}.`
      : `Own file size: ${sizeText}.`;
    const modified = element("span", "nami-inventory-row__modified", row.warning === null ? modifiedTime(row.mtime_ns) : "");
    modified.title = row.mtime_ns === null ? "" : `Own modified time: ${row.mtime_ns} ns`;
    rowElement.append(state, checksum, size, modified);
  }

  function ensureTree() {
    if (tree !== null) return;
    tree = createTree(rows, {
      decorateRow,
      toggle: (nodeId, expanded) => {
        if (current !== null && !blocked()) callbacks.onViewChange(current, {
          collapseNodeId: nodeId, collapsed: !expanded,
        });
      },
      activate: (nodeId) => { if (current !== null && !blocked()) callbacks.onDetail(current, nodeId); },
      requestIndex: async (index, generation) => {
        const owner = current;
        const controller = tree;
        if (owner === null || blocked()) return;
        const window = await callbacks.onWindow(owner, Math.max(0, index - 32));
        if (current !== owner || tree !== controller || window === null) return;
        if (controller.commitWindow(generation, window)) {
          owner.window = window;
          committedWindow = window;
        }
      },
    });
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
      appendDetail("Path", row.warning.path, true);
      appendDetail("Details", row.warning.detail);
      return;
    }
    if (row.is_container) {
      appendDetail("Complete folder scope", rollupText(row.rollup));
      for (const [key, text] of FACETS) {
        if (key !== "notice") appendDetail(`Folder ${text.toLowerCase()}`, String(row.rollup[key]));
      }
    }
    if (row.row_id === null) return;
    if (selected.state !== "current") return;
    const value = selected.response.detail;
    appendDetail("Path", value.row.path, true);
    appendDetail("Presence", label(value.row.presence));
    appendDetail("Verification state", label(value.row.verification_state));
    subjectDetails("Observed", value.observed);
    appendDetail("Last observed", value.row.last_observed_at);
    appendDetail("Last verified", value.row.last_verified_at);
    appendDetail("Missing since", value.row.missing_since);
    appendDetail("Acknowledged", value.row.acknowledged_at);
    appendDetail("Reappeared", value.row.reappeared_at);
    appendDetail("Verification invalidated", value.row.verification_invalidated_at);
    appendDetail("Invalidation reason", value.row.verification_invalidated_reason);
    appendDetail("Unsupported reason", value.row.unsupported_reason);
    if (value.attestation === null) {
      appendDetail("Stored digest", "No baseline evidence");
      return;
    }
    appendDetail("Stored digest", value.attestation.content.digest);
    appendDetail("Algorithm", value.attestation.content.algorithm);
    appendDetail("Provenance", value.attestation.content.provenance);
    appendDetail("Evidence observed", value.attestation.content.observed_at);
    subjectDetails("Attested", value.attestation.subject);
  }

  function dispose() {
    filterMenu.dispose();
    columns.dispose();
    resizeObserver.disconnect();
    detailsExpanded = false;
    diagnostics.hidden = true;
    detailsToggle.ariaExpanded = "false";
    clearTimeout(searchTimer);
    searchTimer = null;
    if (current !== null) current.scrollTop = rows.scrollTop;
    tree?.dispose();
    tree = null;
    committedWindow = null;
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
    resizeObserver.observe(rows);
    if (focusInDetails && !detailsExpanded) title.focus();
    detailsToggle.hidden = review === null;
    diagnostics.hidden = review === null || !detailsExpanded;
    const available = review !== null;
    content.hidden = !available;
    reload.hidden = !value.inventoryError && !review?.message;
    reload.disabled = value.inventoryLoading || value.closePending;
    const actionBlocked = !available || blocked() || !value.sessionReleased || value.sessionState === "active";
    refresh.disabled = actionBlocked;
    refresh.hidden = !available;
    check.hidden = value.inventoryAction?.recovery?.canCheck !== true;
    check.disabled = value.inventoryAction?.recovery?.checking === true;
    recoveryActions.hidden = check.hidden && reload.hidden;
    renderFilesystemText(rootPath, review?.summary.root_path ?? value.form?.source?.text ?? "");
    rootLine.title = review?.summary.root_path ?? value.form?.source?.text ?? "";
    const digest = taskStatusDigest(value);
    summary.dataset.status = value.inventoryError ? "attention" : digest.state;
    renderText(title, value.sessionState === "active" ? "Inventory scan in progress"
      : value.sessionState === "refused" ? "Inventory scan did not start"
        : value.sessionState === "failed" ? "Inventory scan failed"
          : value.sessionState === "canceled" ? "Inventory scan canceled" : "Inventory scan completed");
    progress.className = "nami-progress nami-plan-review__progress"
      + (digest.progress.indeterminate ? " nami-progress--indeterminate" : "");
    progress.dataset.status = digest.state;
    progress.dataset.indeterminate = String(digest.progress.indeterminate);
    progressBar.style.setProperty("--nami-progress-value", `${digest.progress.value}%`);
    renderText(facts, available ? rollupText(review.summary.rollup) : "");
    facts.hidden = !available;
    facts.title = available && !review.summary.filters.includes("acknowledged")
      ? `${review.summary.rollup.acknowledged} acknowledged items hidden as matches; folder context may remain. Show them with the Acknowledged filter.` : "";
    const scanScope = review?.summary.scan_scope;
    const scopeLabel = scanScope?.kind === "location" ? "Entire location"
      : scanScope?.kind === "item" ? `Item: ${scanScope.path}`
      : scanScope?.kind === "folder" ? `Folder: ${scanScope.path} (including subfolders)` : "Selected items";
    const publication = available
      ? `${review.summary.request_id === value.requestId ? "Displayed scan" : "Previous published scan"}: ${scopeLabel}` : "";
    const scanCounts = available
      ? `${review.summary.observed_count} observed · ${review.summary.missing_count} missing · ${review.summary.warning_count} notices from this scan.${scanScope.kind === "location" ? "" : " Other inventory items were not rescanned."}` : "";
    const guidance = value.inventoryError ?? review?.message
      ?? (value.inventoryLoading ? "Loading inventory view…" : "");
    renderFilesystemText(statusLine, [...new Set([
      available ? `${publication} · ${review.summary.scan_complete ? "" : "incomplete · "}${scanCounts}` : "",
      guidance, value.inventoryAction?.message,
    ].filter(Boolean))].join(" · "));
    renderText(globalScanState, `Current scan: ${value.sessionState === "active" ? "in progress" : value.sessionState}.`);
    renderFilesystemText(globalScanFacts, available
      ? `${publication} · ${review.summary.scan_complete ? "complete" : "incomplete"} · ${scanCounts}` : "");
    if (!available) {
      filterMenu.render([], {}, true);
      refreshSelected.disabled = true;
      detailActions.hidden = true;
      return;
    }
    renderText(globalFacts, `${rollupText(review.summary.rollup)}. ${review.summary.rollup.acknowledged} acknowledged items. Stored checksums are baseline evidence; a scan does not verify current bytes.`);
    const selected = review.detail?.row ?? null;
    const domain = selected !== null && selected.warning === null;
    const currentPublication = review.summary.request_id === value.requestId && !value.inventoryViewUnconfirmed;
    const missingCount = selected?.is_container ? selected.rollup.missing
      : selected?.presence === "missing" && !selected.acknowledged ? 1 : 0;
    const acknowledgedCount = selected?.is_container ? selected.rollup.acknowledged
      : selected?.presence === "missing" && selected.acknowledged ? 1 : 0;
    detailActions.hidden = !domain;
    refreshSelected.disabled = actionBlocked || !domain;
    acknowledge.hidden = !domain || missingCount === 0;
    acknowledge.disabled = actionBlocked || !currentPublication;
    restore.hidden = !domain || acknowledgedCount === 0;
    restore.disabled = actionBlocked || !currentPublication;
    renderText(scopeHint, domain && selected.is_container
      ? "Folder actions include all missing items below it, including hidden and off-window items. Restore visibility does not restore files."
      : domain && acknowledgedCount > 0 ? "Restore visibility does not restore the missing file." : "");
    scopeHint.hidden = scopeHint.textContent === "";
    const counts = Object.fromEntries(FACETS.map(([key]) => [key,
      key === "notice" ? review.summary.warning_count : review.summary.rollup[key]]));
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
    if (committedWindow !== review.window) {
      const generation = tree.beginWindowRequest();
      tree.commitWindow(generation, review.window);
      committedWindow = review.window;
      rows.scrollTop = review.scrollTop ?? 0;
    }
    columns.freeze();
    columns.refresh();
    renderDetails();
  }

  return Object.freeze({ element: pane, render, dispose });
}
