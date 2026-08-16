import { renderText } from "./render.js";

export const ROW_H = 28;

let nextTreeId = 1;

export function createTree(root, callbacks = {}) {
  if (!(root instanceof Element)) {
    throw new TypeError("tree root must be an Element");
  }
  const document = root.ownerDocument;
  if (document === null || typeof document?.createElement !== "function") {
    throw new TypeError("tree root must belong to a document");
  }
  const requestIndex = optionalCallback(callbacks, "requestIndex");
  const toggle = optionalCallback(callbacks, "toggle");
  const activate = optionalCallback(callbacks, "activate");
  const requestFrame = document.defaultView.requestAnimationFrame.bind(
    document.defaultView,
  );
  const treeId = nextTreeId;
  nextTreeId += 1;

  root.classList.add("nami-tree");
  root.setAttribute("role", "tree");
  root.tabIndex = 0;

  const topSpacer = createSpacer(document);
  const bottomSpacer = createSpacer(document);
  root.replaceChildren(topSpacer, bottomSpacer);

  let currentGeneration = 0;
  let currentTotal = 0;
  let currentOffset = 0;
  let currentEnd = 0;
  let renderedByIndex = new Map();
  let activeElement = null;
  let activeNodeId = null;
  let activeVisibleIndex = null;
  let pendingRequest = null;
  let settledScrollViewport = null;
  let expectedProgrammaticScroll = null;
  let scrollFramePending = false;
  let initializedActive = false;

  root.addEventListener("keydown", onKeyDown);
  root.addEventListener("scroll", onScroll, {passive: true});
  root.addEventListener("focus", () => {
    if (activeElement !== null) {
      revealActiveRow();
      return;
    }
    if (!initializedActive) {
      const first = firstRenderedEntry();
      if (first !== null) {
        acceptRenderedIntent(first);
      }
    }
  });

  function beginWindowRequest(pendingIndex = null) {
    return beginRequest(pendingIndex, "external");
  }

  function beginRequest(pendingIndex, kind) {
    currentGeneration += 1;
    settledScrollViewport = null;
    pendingRequest = Object.freeze({
      clientHeight: kind === "scroll" ? root.clientHeight : null,
      generation: currentGeneration,
      index: pendingIndex,
      kind,
      scrollTop: kind === "scroll" ? root.scrollTop : null,
    });
    return currentGeneration;
  }

  function commitWindow(generation, window, preferredNodeId = null) {
    if (generation !== currentGeneration) {
      return false;
    }
    const offset = window.offset;
    const total = window.total;
    const sourceRows = window.rows;
    const admittedRequest = pendingRequest?.generation === generation
      ? pendingRequest
      : null;
    const requestKind = admittedRequest?.kind ?? null;
    const requestedIndex = admittedRequest?.index ?? null;
    const preservedScrollTop = root.scrollTop;
    const entries = sourceRows.map((sourceRow) => {
      const row = snapshotRow(sourceRow);
      let entry;
      const element = createRow(document, treeId, row, (event) => {
        event.stopPropagation();
        if (row.expanded === null) {
          return;
        }
        acceptRenderedIntent(entry);
        root.focus();
        toggle(row.node_id, !row.expanded);
      });
      entry = Object.freeze({element, row});
      element.addEventListener("click", () => {
        acceptRenderedIntent(entry);
        root.focus();
        activate(row.node_id);
      });
      return entry;
    });
    const nextByIndex = new Map(
      entries.map((entry) => [entry.row.visible_index, entry]),
    );

    const leadingRows = Math.min(offset, total);
    const trailingRows = Math.max(
      total - leadingRows - entries.length,
      0,
    );
    topSpacer.style.blockSize = `${leadingRows * ROW_H}px`;
    bottomSpacer.style.blockSize = `${trailingRows * ROW_H}px`;
    root.replaceChildren(
      topSpacer,
      ...entries.map((entry) => entry.element),
      bottomSpacer,
    );
    currentTotal = total;
    currentOffset = leadingRows;
    currentEnd = leadingRows + entries.length;
    renderedByIndex = nextByIndex;
    if (requestKind === "scroll") {
      setProgrammaticScrollTop(preservedScrollTop, false);
    }
    if (pendingRequest?.generation === generation) {
      clearPendingRequest();
    }

    let target = null;
    if (requestKind === "scroll") {
      target = visibleEntry(requestedIndex);
    } else if (preferredNodeId !== null) {
      target = entries.find(
        (entry) => entry.row.node_id === preferredNodeId,
      ) ?? null;
    }
    if (
      target === null && requestKind !== "scroll" &&
      requestedIndex !== null
    ) {
      target = renderedByIndex.get(requestedIndex) ?? null;
    }
    if (
      target === null && requestKind !== "scroll" && activeNodeId !== null
    ) {
      target = entries.find(
        (entry) => entry.row.node_id === activeNodeId,
      ) ?? null;
    }
    if (
      target === null && requestKind !== "scroll" && entries.length > 0
    ) {
      target = nearestEntry(entries, activeVisibleIndex);
    }
    if (target === null) {
      clearActive(requestKind === "scroll");
    } else {
      setActive(target, requestKind !== "scroll");
    }
    const scrollViewportUnchanged = requestKind === "scroll" &&
      root.scrollTop === admittedRequest.scrollTop &&
      root.clientHeight === admittedRequest.clientHeight;
    if (scrollViewportUnchanged) {
      settledScrollViewport = Object.freeze({
        clientHeight: root.clientHeight,
        scrollTop: root.scrollTop,
      });
    } else {
      scheduleViewportCheck();
    }
    return true;
  }

  function setActive(entry, reveal = true) {
    if (activeElement !== null) {
      delete activeElement.dataset.active;
    }
    activeElement = entry.element;
    activeElement.dataset.active = "true";
    activeNodeId = entry.row.node_id;
    activeVisibleIndex = entry.row.visible_index;
    initializedActive = true;
    root.setAttribute("aria-activedescendant", activeElement.id);
    if (reveal) {
      revealActiveRow();
    }
  }

  function revealActiveRow() {
    if (activeVisibleIndex === null || root.clientHeight <= 0) {
      return;
    }
    const rowTop = activeVisibleIndex * ROW_H;
    const rowBottom = rowTop + ROW_H;
    const viewportTop = root.scrollTop;
    const viewportBottom = viewportTop + root.clientHeight;
    if (rowTop < viewportTop) {
      setProgrammaticScrollTop(rowTop);
    } else if (rowBottom > viewportBottom) {
      setProgrammaticScrollTop(
        Math.max(rowBottom - root.clientHeight, 0),
      );
    }
  }

  function clearActive(suppressFocusInitialization = false) {
    if (activeElement !== null) {
      delete activeElement.dataset.active;
    }
    activeElement = null;
    activeNodeId = null;
    activeVisibleIndex = null;
    initializedActive = suppressFocusInitialization;
    root.removeAttribute("aria-activedescendant");
  }

  function navigateTo(visibleIndex) {
    if (visibleIndex < 0 || visibleIndex >= currentTotal) {
      return;
    }
    const rendered = renderedByIndex.get(visibleIndex);
    if (rendered !== undefined) {
      acceptRenderedIntent(rendered);
      return;
    }
    requestWindow(visibleIndex, "keyboard");
  }

  function requestWindow(visibleIndex, kind) {
    if (
      kind === "scroll" && pendingRequest?.kind === "scroll" &&
      pendingRequest.index === visibleIndex
    ) {
      return;
    }
    const generation = beginRequest(visibleIndex, kind);
    try {
      requestIndex(visibleIndex, generation);
    } catch (error) {
      if (pendingRequest?.generation === generation) {
        clearPendingRequest();
      }
      throw error;
    }
  }

  function onScroll() {
    if (
      expectedProgrammaticScroll !== null &&
      root.scrollTop === expectedProgrammaticScroll.scrollTop
    ) {
      const reconcile = expectedProgrammaticScroll.reconcile;
      expectedProgrammaticScroll = null;
      if (!reconcile) {
        return;
      }
    } else {
      expectedProgrammaticScroll = null;
      if (pendingRequest?.kind === "keyboard") {
        invalidatePendingRequest();
      }
    }
    scheduleViewportCheck();
  }

  function scheduleViewportCheck() {
    if (scrollFramePending) {
      return;
    }
    scrollFramePending = true;
    requestFrame(() => {
      scrollFramePending = false;
      reconcileViewport();
    });
  }

  function reconcileViewport() {
    if (root.clientHeight <= 0 || currentTotal <= 0) {
      return;
    }
    if (
      settledScrollViewport !== null &&
      root.scrollTop === settledScrollViewport.scrollTop &&
      root.clientHeight === settledScrollViewport.clientHeight
    ) {
      return;
    }
    settledScrollViewport = null;
    if (pendingRequest?.kind === "external") {
      reconcileVisibleActive();
      return;
    }
    if (pendingRequest?.kind === "keyboard") {
      return;
    }

    const viewportTop = Math.max(root.scrollTop, 0);
    const viewportBottom = viewportTop + root.clientHeight;
    const firstIndex = Math.min(
      Math.floor(viewportTop / ROW_H),
      currentTotal - 1,
    );
    const lastIndex = Math.min(
      Math.max(Math.ceil(viewportBottom / ROW_H) - 1, firstIndex),
      currentTotal - 1,
    );
    const covered = firstIndex >= currentOffset && lastIndex < currentEnd;
    if (covered) {
      reconcileVisibleActive();
      if (pendingRequest?.kind === "scroll") {
        invalidatePendingRequest();
      }
      return;
    }

    reconcileVisibleActive();
    const requestTarget = firstIndex < currentOffset ? firstIndex : lastIndex;
    requestWindow(requestTarget, "scroll");
  }

  function reconcileVisibleActive(preferredIndex = null) {
    const target = visibleEntry(preferredIndex);
    if (target !== null) {
      if (target.element !== activeElement) {
        setActive(target, false);
      }
    } else {
      clearActive(true);
    }
  }

  function visibleEntry(preferredIndex = null) {
    if (root.clientHeight < ROW_H) {
      return null;
    }
    const viewportTop = Math.max(root.scrollTop, 0);
    const viewportBottom = viewportTop + root.clientHeight;
    const firstFullIndex = Math.ceil(viewportTop / ROW_H);
    const lastFullIndex = Math.floor(viewportBottom / ROW_H) - 1;
    const nearestIndex = preferredIndex ?? activeVisibleIndex ?? firstFullIndex;
    let active = null;
    let nearest = null;
    for (const entry of renderedByIndex.values()) {
      const index = entry.row.visible_index;
      if (index < firstFullIndex || index > lastFullIndex) {
        continue;
      }
      if (index === preferredIndex) {
        return entry;
      }
      if (entry.row.node_id === activeNodeId) {
        active = entry;
      }
      if (
        nearest === null ||
        Math.abs(index - nearestIndex) <
          Math.abs(nearest.row.visible_index - nearestIndex)
      ) {
        nearest = entry;
      }
    }
    return active ?? nearest;
  }

  function invalidatePendingRequest() {
    currentGeneration += 1;
    clearPendingRequest();
  }

  function acceptRenderedIntent(entry) {
    invalidateInternalRequest();
    setActive(entry);
  }

  function invalidateInternalRequest() {
    if (
      pendingRequest?.kind === "keyboard" ||
      pendingRequest?.kind === "scroll"
    ) {
      invalidatePendingRequest();
    }
  }

  function setProgrammaticScrollTop(value, reconcile = true) {
    const previous = root.scrollTop;
    root.scrollTop = value;
    if (root.scrollTop !== previous) {
      expectedProgrammaticScroll = Object.freeze({
        reconcile,
        scrollTop: root.scrollTop,
      });
    }
  }

  function clearPendingRequest() {
    pendingRequest = null;
  }

  function onKeyDown(event) {
    if (
      event.defaultPrevented || event.altKey || event.ctrlKey ||
      event.metaKey
    ) {
      return;
    }
    if (activeVisibleIndex === null) {
      if (event.key === "Home" && currentTotal > 0) {
        event.preventDefault();
        navigateTo(0);
      } else if (event.key === "End" && currentTotal > 0) {
        event.preventDefault();
        navigateTo(currentTotal - 1);
      }
      return;
    }
    const active = renderedByIndex.get(activeVisibleIndex);
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        navigateTo(Math.min(activeVisibleIndex + 1, currentTotal - 1));
        break;
      case "ArrowUp":
        event.preventDefault();
        navigateTo(Math.max(activeVisibleIndex - 1, 0));
        break;
      case "Home":
        event.preventDefault();
        navigateTo(0);
        break;
      case "End":
        event.preventDefault();
        navigateTo(currentTotal - 1);
        break;
      case "ArrowRight":
        event.preventDefault();
        if (active !== undefined && active.row.expanded === false) {
          invalidateInternalRequest();
          toggle(active.row.node_id, true);
        } else if (
          active !== undefined && active.row.expanded === true &&
          active.row.first_child_visible_index !== null
        ) {
          navigateTo(active.row.first_child_visible_index);
        }
        break;
      case "ArrowLeft":
        event.preventDefault();
        if (active !== undefined && active.row.expanded === true) {
          invalidateInternalRequest();
          toggle(active.row.node_id, false);
        } else if (
          active !== undefined && active.row.parent_visible_index !== null
        ) {
          navigateTo(active.row.parent_visible_index);
        }
        break;
      case "Enter":
        event.preventDefault();
        if (active !== undefined) {
          invalidateInternalRequest();
          activate(active.row.node_id);
        }
        break;
    }
  }

  function firstRenderedEntry() {
    for (const entry of renderedByIndex.values()) {
      return entry;
    }
    return null;
  }

  return Object.freeze({beginWindowRequest, commitWindow});
}

function optionalCallback(callbacks, name) {
  if (callbacks === null || typeof callbacks !== "object") {
    throw new TypeError("tree callbacks must be an object");
  }
  const callback = callbacks[name];
  if (callback === undefined) {
    return () => {};
  }
  if (typeof callback !== "function") {
    throw new TypeError(`tree ${name} callback must be a function`);
  }
  return callback;
}

function createSpacer(document) {
  const spacer = document.createElement("div");
  spacer.classList.add("nami-tree__spacer");
  spacer.ariaHidden = "true";
  return spacer;
}

function snapshotRow(row) {
  return Object.freeze({
    node_id: row.node_id,
    display: row.display,
    depth: row.depth,
    visible_index: row.visible_index,
    parent_visible_index: row.parent_visible_index,
    first_child_visible_index: row.first_child_visible_index,
    position_in_set: row.position_in_set,
    set_size: row.set_size,
    expanded: row.expanded,
  });
}

function createRow(document, treeId, row, onDisclosureClick) {
  const element = document.createElement("div");
  element.classList.add("nami-tree-row");
  element.id = `nami-tree-${treeId}-row-${row.visible_index}`;
  element.dataset.nodeId = row.node_id;
  element.setAttribute("role", "treeitem");
  element.ariaLevel = String(row.depth + 1);
  element.ariaPosInSet = String(row.position_in_set);
  element.ariaSetSize = String(row.set_size);
  element.style.setProperty("--nami-tree-depth", String(row.depth));
  if (row.expanded !== null) {
    element.ariaExpanded = String(row.expanded);
  }

  const disclosure = document.createElement("span");
  disclosure.classList.add("nami-tree-row__disclosure");
  disclosure.ariaHidden = "true";
  if (row.expanded === null) {
    disclosure.classList.add("nami-tree-row__disclosure--leaf");
  }
  disclosure.addEventListener("click", onDisclosureClick);
  const label = document.createElement("span");
  label.classList.add("nami-tree-row__label");
  renderText(label, row.display);
  element.append(disclosure, label);
  return element;
}

function nearestEntry(entries, visibleIndex) {
  if (visibleIndex === null) {
    return entries[0];
  }
  return entries.reduce((nearest, entry) =>
    Math.abs(entry.row.visible_index - visibleIndex) <
      Math.abs(nearest.row.visible_index - visibleIndex)
      ? entry
      : nearest);
}
