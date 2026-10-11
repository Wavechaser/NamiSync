import { renderFilesystemText } from "./render.js";

export const ROW_H = 28;

let nextTreeId = 1;

export function createTree(root, callbacks = {}, rowHeight = ROW_H) {
  if (!(root instanceof Element)) {
    throw new TypeError("tree root must be an Element");
  }
  if (!Number.isSafeInteger(rowHeight) || rowHeight <= 0) {
    throw new TypeError("tree row height must be a positive integer");
  }
  const document = root.ownerDocument;
  if (document === null || typeof document?.createElement !== "function") {
    throw new TypeError("tree root must belong to a document");
  }
  const requestIndex = optionalCallback(callbacks, "requestIndex");
  const requestCancelled = optionalCallback(callbacks, "requestCancelled");
  const toggle = optionalCallback(callbacks, "toggle");
  const activate = optionalCallback(callbacks, "activate");
  const activeChanged = optionalCallback(callbacks, "activeChanged");
  const decorateRow = optionalCallback(callbacks, "decorateRow");
  const context = optionalCallback(callbacks, "context");
  const requestFrame = document.defaultView.requestAnimationFrame.bind(
    document.defaultView,
  );
  const treeId = nextTreeId;
  nextTreeId += 1;

  root.classList.add("nami-tree");
  root.style.setProperty("--row-h", `${rowHeight}px`);
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
  let scrollTopObserved = root.scrollTop;
  let scrollDirection = 0;
  let expectedProgrammaticScroll = null;
  let scrollFramePending = false;
  let initializedActive = false;
  let disposed = false;

  root.addEventListener("keydown", onKeyDown);
  root.addEventListener("scroll", onScroll, {passive: true});
  root.addEventListener("focus", onFocus);
  root.addEventListener("pointerdown", invalidateInternalRequest);
  root.addEventListener("wheel", invalidateInternalRequest, { passive: true });
  root.addEventListener("touchstart", invalidateInternalRequest, { passive: true });
  const resizeObserver = new document.defaultView.ResizeObserver(() => {
    scheduleViewportCheck();
  });
  resizeObserver.observe(root);

  function onFocus() {
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
  }

  function beginWindowRequest(pendingIndex = null) {
    if (disposed) {
      throw new Error("tree controller is disposed");
    }
    scrollDirection = 0;
    scrollTopObserved = root.scrollTop;
    return beginRequest(pendingIndex, "external");
  }

  function beginRequest(pendingIndex, kind) {
    currentGeneration += 1;
    cancelPendingRequest();
    settledScrollViewport = null;
    pendingRequest = Object.freeze({
      clientHeight: kind === "scroll" ? root.clientHeight : null,
      generation: currentGeneration,
      index: pendingIndex,
      kind,
      scrollTop: kind === "scroll" ? root.scrollTop : null,
      direction: kind === "scroll" ? scrollDirection : 0,
    });
    return currentGeneration;
  }

  function finishWindowRequest(generation) {
    if (disposed || generation !== currentGeneration || pendingRequest?.generation !== generation) return false;
    clearPendingRequest();
    settledScrollViewport = Object.freeze({
      clientHeight: root.clientHeight, scrollTop: root.scrollTop,
    });
    return true;
  }

  function commitWindow(generation, window, preferredNodeId = null) {
    if (disposed || generation !== currentGeneration) {
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
    if (requestKind === "scroll" && root.clientHeight > 0 &&
        (offset * rowHeight >= root.scrollTop + root.clientHeight ||
         (offset + sourceRows.length) * rowHeight <= root.scrollTop)) {
      clearPendingRequest();
      if (root.scrollTop === admittedRequest.scrollTop &&
          root.clientHeight === admittedRequest.clientHeight) {
        settledScrollViewport = Object.freeze({
          clientHeight: root.clientHeight, scrollTop: root.scrollTop,
        });
      } else {
        scheduleViewportCheck();
      }
      return false;
    }
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
      decorateRow(element, sourceRow);
      entry = Object.freeze({element, row});
      element.addEventListener("click", () => {
        acceptRenderedIntent(entry);
        root.focus();
        activate(row.node_id);
      });
      element.addEventListener("contextmenu", (event) => {
        acceptRenderedIntent(entry, false);
        context(row.node_id, event, element);
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
    topSpacer.style.blockSize = `${leadingRows * rowHeight}px`;
    bottomSpacer.style.blockSize = `${trailingRows * rowHeight}px`;
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
      target = visibleEntry();
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
    const changed = activeNodeId !== entry.row.node_id;
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
    if (changed) activeChanged(activeNodeId);
  }

  function revealActiveRow() {
    if (activeVisibleIndex === null || root.clientHeight <= 0) {
      return;
    }
    const rowTop = activeVisibleIndex * rowHeight;
    const rowBottom = rowTop + rowHeight;
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
    const changed = activeNodeId !== null;
    if (activeElement !== null) {
      delete activeElement.dataset.active;
    }
    activeElement = null;
    activeNodeId = null;
    activeVisibleIndex = null;
    initializedActive = suppressFocusInitialization;
    root.removeAttribute("aria-activedescendant");
    if (changed) activeChanged(null);
  }

  function navigateTo(visibleIndex) {
    scrollDirection = 0;
    scrollTopObserved = root.scrollTop;
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

  function requestWindow(visibleIndex, kind, offset = Math.max(0, visibleIndex - 32)) {
    if (
      kind === "scroll" && pendingRequest?.kind === "scroll"
      && pendingRequest.direction === scrollDirection
    ) {
      return;
    }
    const generation = beginRequest(visibleIndex, kind);
    try {
      requestIndex(visibleIndex, generation, offset);
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
      scrollTopObserved = root.scrollTop;
      if (!reconcile) {
        return;
      }
    } else {
      expectedProgrammaticScroll = null;
      const direction = Math.sign(root.scrollTop - scrollTopObserved);
      if (direction !== 0) scrollDirection = direction;
      scrollTopObserved = root.scrollTop;
      if (pendingRequest?.kind === "keyboard") {
        invalidatePendingRequest();
      }
    }
    scheduleViewportCheck();
  }

  function scheduleViewportCheck() {
    if (disposed || scrollFramePending) {
      return;
    }
    scrollFramePending = true;
    requestFrame(() => {
      scrollFramePending = false;
      if (!disposed) {
        reconcileViewport();
      }
    });
  }

  function reconcileViewport() {
    if (root.clientHeight <= 0 || currentTotal <= 0) {
      scrollDirection = 0;
      scrollTopObserved = root.scrollTop;
      settledScrollViewport = null;
      if (pendingRequest?.kind === "scroll") invalidatePendingRequest();
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
      Math.floor(viewportTop / rowHeight),
      currentTotal - 1,
    );
    const lastIndex = Math.min(
      Math.max(Math.ceil(viewportBottom / rowHeight) - 1, firstIndex),
      currentTotal - 1,
    );
    const covered = firstIndex >= currentOffset && lastIndex < currentEnd;
    const direction = scrollDirection || (firstIndex < currentOffset ? -1 : 1);
    const offset = Math.min(currentTotal - 1, Math.max(0,
      direction < 0 ? lastIndex + 1 + 32 - 256 : firstIndex - 32));
    const advancing = direction < 0 ? offset < currentOffset : offset > currentOffset;
    const nearEdge = scrollDirection !== 0 && (direction < 0
      ? currentOffset > 0 && firstIndex - currentOffset <= 64
      : currentEnd < currentTotal && currentEnd - lastIndex - 1 <= 64);
    if (covered && (!nearEdge || !advancing)) {
      reconcileVisibleActive();
      if (pendingRequest?.kind === "scroll") {
        invalidatePendingRequest();
      }
      return;
    }

    reconcileVisibleActive();
    const requestTarget = firstIndex < currentOffset ? firstIndex : lastIndex;
    requestWindow(requestTarget, "scroll", offset);
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
    if (root.clientHeight < rowHeight) {
      return null;
    }
    const viewportTop = Math.max(root.scrollTop, 0);
    const viewportBottom = viewportTop + root.clientHeight;
    const firstFullIndex = Math.ceil(viewportTop / rowHeight);
    const lastFullIndex = Math.floor(viewportBottom / rowHeight) - 1;
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
    cancelPendingRequest();
  }

  function acceptRenderedIntent(entry, reveal = true) {
    invalidateInternalRequest();
    setActive(entry, reveal);
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
    if (reconcile) {
      scrollDirection = 0;
      scrollTopObserved = root.scrollTop;
    }
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

  function cancelPendingRequest() {
    const generation = pendingRequest?.generation;
    clearPendingRequest();
    if (generation !== undefined) requestCancelled(generation);
  }

  function onKeyDown(event) {
    if (event.altKey || event.ctrlKey || event.metaKey
        || !["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) invalidateInternalRequest();
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
    if (event.key === "ContextMenu" || (event.key === "F10" && event.shiftKey)) {
      if (active !== undefined) {
        invalidateInternalRequest();
        context(active.row.node_id, event, active.element);
      }
      return;
    }
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        navigateTo(Math.min((pendingRequest?.kind === "keyboard" ? pendingRequest.index : activeVisibleIndex) + 1, currentTotal - 1));
        break;
      case "ArrowUp":
        event.preventDefault();
        navigateTo(Math.max((pendingRequest?.kind === "keyboard" ? pendingRequest.index : activeVisibleIndex) - 1, 0));
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

  function dispose() {
    if (disposed) {
      return;
    }
    disposed = true;
    currentGeneration += 1;
    cancelPendingRequest();
    resizeObserver.disconnect();
    root.removeEventListener("keydown", onKeyDown);
    root.removeEventListener("scroll", onScroll);
    root.removeEventListener("focus", onFocus);
    root.removeEventListener("pointerdown", invalidateInternalRequest);
    root.removeEventListener("wheel", invalidateInternalRequest);
    root.removeEventListener("touchstart", invalidateInternalRequest);
  }

  return Object.freeze({beginWindowRequest, commitWindow, finishWindowRequest, cancelNavigation: invalidateInternalRequest, dispose});
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
  renderFilesystemText(label, row.display);
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
