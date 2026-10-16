import { renderFilesystemText } from "./render.js";
import { keyboardHighlightGesture } from "./row_highlight.js";
import { createTableController } from "./table_controller.js";

export const ROW_H = 28;

let nextTreeId = 1;

export function createTree(root, callbacks = {}, rowHeight = ROW_H, viewport = root, topInset = 0) {
  if (!(root instanceof Element)) {
    throw new TypeError("tree root must be an Element");
  }
  if (!Number.isSafeInteger(rowHeight) || rowHeight <= 0) {
    throw new TypeError("tree row height must be a positive integer");
  }
  if (!(viewport instanceof Element) || !Number.isSafeInteger(topInset) || topInset < 0) {
    throw new TypeError("tree viewport and top inset must be valid");
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
  const highlight = optionalCallback(callbacks, "highlight");
  const treeId = nextTreeId;
  nextTreeId += 1;

  root.classList.add("nami-tree");
  root.style.setProperty("--row-h", `${rowHeight}px`);
  root.setAttribute("role", "tree");
  if (callbacks.highlight !== undefined) root.ariaMultiSelectable = "true";
  root.tabIndex = 0;

  const topSpacer = createSpacer(document);
  const bottomSpacer = createSpacer(document);
  root.replaceChildren(topSpacer, bottomSpacer);

  let renderedByIndex = new Map();
  let activeElement = null;
  let activeNodeId = null;
  let activeVisibleIndex = null;
  let initializedActive = false;
  let disposed = false;

  const table = createTableController(viewport, rowHeight, topInset, {
    requestIndex, requestCancelled, viewportChanged: reconcileVisibleActive,
  });
  root.addEventListener("keydown", onKeyDown);
  root.addEventListener("focus", onFocus);

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

  function commitWindow(generation, window, preferredNodeId = null, reveal = true) {
    return table.commitWindow(generation, window, (admittedRequest, restoreScroll) => {
      const offset = window.offset;
      const total = window.total;
      const sourceRows = window.rows;
      const requestKind = admittedRequest?.kind ?? null;
      const requestedIndex = admittedRequest?.index ?? null;
      const entries = sourceRows.map((sourceRow) => {
        const row = snapshotRow(sourceRow);
        let entry;
        const element = createRow(document, treeId, row, (event) => {
          event.stopPropagation();
          if (row.expanded === null) {
            return;
          }
          acceptRenderedIntent(entry);
          root.focus({preventScroll: true});
          toggle(row.node_id, !row.expanded);
        });
        decorateRow(element, sourceRow);
        entry = Object.freeze({element, row});
        element.addEventListener("click", (event) => {
          acceptRenderedIntent(entry, callbacks.highlight === undefined);
          root.focus({preventScroll: true});
          activate(row.node_id, event);
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
      renderedByIndex = nextByIndex;
      restoreScroll();

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
        setActive(target, reveal && requestKind !== "scroll");
        if (requestKind === "keyboard" && callbacks.highlight !== undefined) highlight("replace", target.row.node_id);
      }
    }, reveal);
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
    if (activeVisibleIndex !== null) table.revealRow(activeVisibleIndex);
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
    table.resetTravel();
    if (visibleIndex < 0 || visibleIndex >= table.total) {
      return;
    }
    const rendered = renderedByIndex.get(visibleIndex);
    if (rendered !== undefined) {
      acceptRenderedIntent(rendered);
      if (callbacks.highlight !== undefined) highlight("replace", rendered.row.node_id);
      return;
    }
    table.requestKeyboard(visibleIndex);
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
    const [firstFullIndex, lastFullIndex] = table.bounds(true);
    if (lastFullIndex < firstFullIndex) return null;
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

  function acceptRenderedIntent(entry, reveal = true) {
    table.invalidateInternalRequest();
    setActive(entry, reveal);
  }

  function onKeyDown(event) {
    const gesture = keyboardHighlightGesture(event);
    if (!event.defaultPrevented && callbacks.highlight !== undefined && gesture !== null) {
      event.preventDefault();
      table.invalidateInternalRequest();
      highlight(gesture, null);
      return;
    }
    if (event.altKey || event.ctrlKey || event.metaKey
        || !["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) table.invalidateInternalRequest();
    if (
      event.defaultPrevented || event.altKey || event.ctrlKey ||
      event.metaKey
    ) {
      return;
    }
    if (activeVisibleIndex === null) {
      if (event.key === "Home" && table.total > 0) {
        event.preventDefault();
        navigateTo(0);
      } else if (event.key === "End" && table.total > 0) {
        event.preventDefault();
        navigateTo(table.total - 1);
      }
      return;
    }
    const active = renderedByIndex.get(activeVisibleIndex);
    if (event.key === "ContextMenu" || (event.key === "F10" && event.shiftKey)) {
      if (active !== undefined) {
        table.invalidateInternalRequest();
        context(active.row.node_id, event, active.element);
      }
      return;
    }
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        navigateTo(Math.min((table.keyboardIndex ?? activeVisibleIndex) + 1, table.total - 1));
        break;
      case "ArrowUp":
        event.preventDefault();
        navigateTo(Math.max((table.keyboardIndex ?? activeVisibleIndex) - 1, 0));
        break;
      case "Home":
        event.preventDefault();
        navigateTo(0);
        break;
      case "End":
        event.preventDefault();
        navigateTo(table.total - 1);
        break;
      case "ArrowRight":
        event.preventDefault();
        if (active !== undefined && active.row.expanded === false) {
          table.invalidateInternalRequest();
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
          table.invalidateInternalRequest();
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
          table.invalidateInternalRequest();
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
    table.dispose();
    root.removeEventListener("keydown", onKeyDown);
    root.removeEventListener("focus", onFocus);
  }

  return Object.freeze({beginWindowRequest: table.beginWindowRequest, commitWindow,
    finishWindowRequest: table.finishWindowRequest, cancelNavigation: table.cancelNavigation, dispose});
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
