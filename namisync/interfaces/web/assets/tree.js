import { renderText } from "./render.js";

export const ROW_H = 28;

export function createTree(root) {
  if (!(root instanceof Element)) {
    throw new TypeError("tree root must be an Element");
  }
  const document = root.ownerDocument;
  if (document === null || typeof document?.createElement !== "function") {
    throw new TypeError("tree root must belong to a document");
  }

  root.classList.add("nami-tree");
  root.role = "tree";

  const topSpacer = createSpacer(document);
  const bottomSpacer = createSpacer(document);
  root.replaceChildren(topSpacer, bottomSpacer);

  let currentGeneration = 0;

  function beginWindowRequest() {
    currentGeneration += 1;
    return currentGeneration;
  }

  function commitWindow(generation, window) {
    if (generation !== currentGeneration) {
      return false;
    }

    const rows = window.rows.map((row) => createRow(document, row));
    const leadingRows = Math.min(window.offset, window.total);
    const trailingRows = Math.max(
      window.total - leadingRows - rows.length,
      0,
    );
    topSpacer.style.blockSize = `${leadingRows * ROW_H}px`;
    bottomSpacer.style.blockSize = `${trailingRows * ROW_H}px`;
    root.replaceChildren(topSpacer, ...rows, bottomSpacer);
    return true;
  }

  return Object.freeze({beginWindowRequest, commitWindow});
}

function createSpacer(document) {
  const spacer = document.createElement("div");
  spacer.classList.add("nami-tree__spacer");
  spacer.ariaHidden = "true";
  return spacer;
}

function createRow(document, row) {
  const element = document.createElement("div");
  element.classList.add("nami-tree-row");
  element.dataset.nodeId = row.node_id;
  element.role = "treeitem";
  element.ariaLevel = String(row.depth + 1);
  element.style.setProperty("--nami-tree-depth", String(row.depth));
  if (row.is_container) {
    element.ariaExpanded = String(row.expanded);
  }

  const label = document.createElement("span");
  label.classList.add("nami-tree-row__label");
  renderText(label, row.display);
  element.append(label);
  return element;
}
