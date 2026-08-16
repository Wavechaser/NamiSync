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
  let renderedByIndex = new Map();
  let activeElement = null;
  let activeNodeId = null;
  let activeVisibleIndex = null;
  let pendingVisibleIndex = null;
  let initializedActive = false;

  root.addEventListener("keydown", onKeyDown);
  root.addEventListener("focus", () => {
    if (activeElement === null && !initializedActive) {
      const first = firstRenderedEntry();
      if (first !== null) {
        setActive(first);
      }
    }
  });

  function beginWindowRequest(pendingIndex = null) {
    currentGeneration += 1;
    pendingVisibleIndex = pendingIndex;
    return currentGeneration;
  }

  function commitWindow(generation, window, preferredNodeId = null) {
    if (generation !== currentGeneration) {
      return false;
    }
    const entries = window.rows.map((row) => {
      const element = createRow(document, treeId, row);
      const entry = Object.freeze({element, row});
      element.addEventListener("click", () => {
        setActive(entry);
        root.focus();
        activate(row.node_id);
      });
      return entry;
    });
    const nextByIndex = new Map(
      entries.map((entry) => [entry.row.visible_index, entry]),
    );

    const leadingRows = Math.min(window.offset, window.total);
    const trailingRows = Math.max(
      window.total - leadingRows - entries.length,
      0,
    );
    topSpacer.style.blockSize = `${leadingRows * ROW_H}px`;
    bottomSpacer.style.blockSize = `${trailingRows * ROW_H}px`;
    root.replaceChildren(
      topSpacer,
      ...entries.map((entry) => entry.element),
      bottomSpacer,
    );
    currentTotal = window.total;
    renderedByIndex = nextByIndex;

    let target = null;
    if (preferredNodeId !== null) {
      target = entries.find(
        (entry) => entry.row.node_id === preferredNodeId,
      ) ?? null;
    }
    if (target === null && pendingVisibleIndex !== null) {
      target = renderedByIndex.get(pendingVisibleIndex) ?? null;
    }
    if (target === null && activeNodeId !== null) {
      target = entries.find(
        (entry) => entry.row.node_id === activeNodeId,
      ) ?? null;
    }
    if (target === null && entries.length > 0) {
      target = nearestEntry(entries, activeVisibleIndex);
    }
    if (target === null) {
      clearActive();
    } else {
      setActive(target);
    }
    return true;
  }

  function setActive(entry) {
    if (activeElement !== null) {
      delete activeElement.dataset.active;
    }
    activeElement = entry.element;
    activeElement.dataset.active = "true";
    activeNodeId = entry.row.node_id;
    activeVisibleIndex = entry.row.visible_index;
    pendingVisibleIndex = null;
    initializedActive = true;
    root.setAttribute("aria-activedescendant", activeElement.id);
  }

  function clearActive() {
    if (activeElement !== null) {
      delete activeElement.dataset.active;
    }
    activeElement = null;
    activeNodeId = null;
    activeVisibleIndex = null;
    pendingVisibleIndex = null;
    initializedActive = false;
    root.removeAttribute("aria-activedescendant");
  }

  function navigateTo(visibleIndex) {
    if (visibleIndex < 0 || visibleIndex >= currentTotal) {
      return;
    }
    const rendered = renderedByIndex.get(visibleIndex);
    if (rendered !== undefined) {
      setActive(rendered);
      return;
    }
    requestIndex(visibleIndex);
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

function createRow(document, treeId, row) {
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
