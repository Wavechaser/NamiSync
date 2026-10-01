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
  const header = element("div", "nami-card nami-inventory-review__header");
  const title = element("h2", "", "Inventory");
  const rootPath = element("p", "nami-shell__guidance");
  const facts = element("p", "nami-shell__guidance");
  const scanFacts = element("p", "nami-shell__guidance");
  const scanState = element("p", "nami-shell__guidance");
  const message = element("p", "nami-shell__guidance");
  message.setAttribute("role", "status");
  const actionStatus = element("p", "nami-shell__guidance");
  actionStatus.setAttribute("role", "status");
  const refresh = button("Refresh inventory", "inventory-refresh");
  const check = button("Check original outcome", "inventory-check-outcome");
  const reload = button("Reload inventory view", "inventory-reload");
  header.append(title, rootPath, scanState, facts, scanFacts, message, actionStatus, refresh, check, reload);

  const table = element("div", "nami-card nami-inventory-review__table");
  const toolbar = element("div", "nami-inventory-review__toolbar");
  const filters = element("div", "nami-inventory-review__filters");
  filters.ariaLabel = "Inventory filters";
  const all = button("Default", "inventory-all");
  all.ariaPressed = "true";
  filters.append(all);
  const facetButtons = new Map();
  for (const [key, text] of FACETS) {
    const control = button(text, `inventory-filter-${key}`);
    control.dataset.filter = key;
    control.ariaPressed = "false";
    control.addEventListener("click", () => {
      if (current === null || blocked()) return;
      const chosen = new Set(current.summary.filters);
      if (chosen.has(key)) chosen.delete(key);
      else chosen.add(key);
      callbacks.onViewChange(current, { filters: [...chosen] });
    });
    facetButtons.set(key, control);
    filters.append(control);
  }
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

  const sortBar = element("div", "nami-inventory-review__sort");
  const sortLabel = element("label", "", "Sort by ");
  const sort = element("select", "nami-select");
  sort.ariaLabel = "Inventory sort column";
  for (const [key, text] of [["path", "Path"], ["filename", "Name"], ["size", "Size"], ["mtime", "Modified"]]) {
    const option = element("option", "", text);
    option.value = key;
    sort.append(option);
  }
  sortLabel.append(sort);
  const directionLabel = element("label", "", "Direction ");
  const direction = element("select", "nami-select");
  direction.ariaLabel = "Inventory sort direction";
  for (const [key, text] of [["ascending", "Ascending"], ["descending", "Descending"]]) {
    const option = element("option", "", text);
    option.value = key;
    direction.append(option);
  }
  directionLabel.append(direction);
  const reset = button("Reset sort", "inventory-sort-reset");
  sortBar.append(sortLabel, directionLabel, reset);
  const columns = element("div", "nami-inventory-review__columns");
  columns.ariaHidden = "true";
  for (const text of ["Name", "State", "Size", "Modified"]) columns.append(element("span", "", text));
  const rows = element("div", "nami-inventory-review__rows");
  rows.ariaLabel = "Inventory items";
  const empty = element("p", "nami-shell__guidance", "No items match this view.");
  table.append(toolbar, sortBar, columns, rows, empty);

  const detail = element("section", "nami-card nami-inventory-review__detail");
  detail.tabIndex = 0;
  detail.ariaLabel = "Inventory item details";
  const detailTitle = element("h2", "", "Item details");
  const detailStatus = element("p", "nami-shell__guidance");
  detailStatus.setAttribute("role", "status");
  const detailActions = element("div", "nami-inventory-review__actions");
  const refreshSelected = button("Refresh selected", "inventory-refresh-selected");
  const acknowledge = button("Acknowledge missing", "inventory-acknowledge");
  const restore = button("Restore visibility", "inventory-restore");
  detailActions.append(refreshSelected, acknowledge, restore);
  const scopeHint = element("p", "nami-shell__guidance");
  const detailBody = element("dl", "nami-plan-review__detail-body");
  detail.append(detailTitle, detailStatus, detailActions, scopeHint, detailBody);
  const content = element("div", "nami-inventory-review__content");
  content.append(table, detail);
  pane.append(header, content);

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
  all.addEventListener("click", () => {
    if (current !== null && !blocked()) callbacks.onViewChange(current, { filters: [] });
  });
  const changeSort = () => {
    if (current !== null && !blocked()) callbacks.onViewChange(current, {
      sortColumn: sort.value,
      sortDirection: sort.value === "path" ? "ascending" : direction.value,
    });
  };
  sort.addEventListener("change", changeSort);
  direction.addEventListener("change", changeSort);
  reset.addEventListener("click", () => {
    if (current !== null && !blocked()) callbacks.onViewChange(current, {
      sortColumn: "path", sortDirection: "ascending",
    });
  });
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
    const state = element("span", "nami-inventory-row__state", stateText);
    state.dataset.integrity = row.warning !== null ? "" : row.acknowledged ? "missing"
      : row.presence === "present" ? row.verification_state : row.presence;
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
    rowElement.append(state, size, modified);
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
    detail.hidden = selected === null;
    if (selected === null) return;
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
    const review = value.inventoryReview ?? null;
    if (current !== review || task?.taskId !== value.taskId) dispose();
    task = value;
    const first = current !== review;
    current = review;
    const available = review !== null;
    content.hidden = !available;
    reload.hidden = !value.inventoryError && !review?.message;
    reload.disabled = value.inventoryLoading || value.closePending;
    renderText(message, value.inventoryError ?? review?.message ?? (value.inventoryLoading ? "Loading inventory…" : ""));
    message.hidden = message.textContent === "";
    renderText(actionStatus, value.inventoryAction?.message ?? "");
    actionStatus.hidden = actionStatus.textContent === "";
    const actionBlocked = !available || blocked() || !value.sessionReleased || value.sessionState === "active";
    refresh.disabled = actionBlocked;
    refresh.hidden = !available;
    check.hidden = value.inventoryAction?.recovery?.canCheck !== true;
    check.disabled = value.inventoryAction?.recovery?.checking === true;
    renderFilesystemText(rootPath, review?.summary.root_path ?? value.form?.source?.text ?? "");
    renderText(title, value.sessionState === "active" ? "Inventory scan in progress" : "Inventory");
    renderText(scanState, `Current scan: ${value.sessionState === "active" ? "in progress" : value.sessionState}.`);
    renderText(facts, available ? `${rollupText(review.summary.rollup)} · ${review.summary.visible_row_count} visible rows` : "");
    facts.title = available && !review.summary.filters.includes("acknowledged")
      ? `${review.summary.rollup.acknowledged} acknowledged items hidden as matches; folder context may remain. Show them with the Acknowledged filter.` : "";
    renderText(scanFacts, available
      ? `${review.summary.request_id === value.requestId ? "Displayed scan" : "Previous published scan"}: ${review.summary.scan_complete ? "complete" : "incomplete"} · ${review.summary.observed_count} observed · ${review.summary.missing_count} missing · ${review.summary.warning_count} notices` : "");
    if (!available) return;
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
    all.ariaPressed = String(review.summary.filters.length === 0);
    all.disabled = Boolean(blocked());
    for (const [key, control] of facetButtons) {
      const count = key === "notice" ? review.summary.warning_count : review.summary.rollup[key];
      renderText(control, `${label(key)} ${count}`);
      control.ariaPressed = String(review.summary.filters.includes(key));
      control.disabled = Boolean(blocked());
    }
    if (first || (!searchDraft && review.pending !== "view")) search.value = review.summary.search_query;
    if (review.queuedSearchQuery === null && review.pending === null && search.value === review.summary.search_query) searchDraft = false;
    search.disabled = value.closePending || value.inventoryLoading;
    submit.disabled = search.disabled;
    clear.disabled = search.disabled;
    clear.hidden = search.value === "";
    sort.value = review.summary.sort_column;
    direction.value = review.summary.sort_direction;
    sort.disabled = Boolean(blocked());
    direction.disabled = Boolean(blocked()) || sort.value === "path";
    reset.disabled = Boolean(blocked());
    empty.hidden = review.window.total !== 0;
    ensureTree();
    if (committedWindow !== review.window) {
      const generation = tree.beginWindowRequest();
      tree.commitWindow(generation, review.window);
      committedWindow = review.window;
      rows.scrollTop = review.scrollTop ?? 0;
    }
    renderDetails();
  }

  return Object.freeze({ element: pane, render, dispose });
}
