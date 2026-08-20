import { renderFilesystemText, renderText } from "./render.js";

const BASE_STRING_FIELDS = Object.freeze([
  "selectionLabel",
  "nameText",
  "sizeText",
  "notesText",
]);

function validBaseView(rowView) {
  return rowView !== null &&
    typeof rowView === "object" &&
    !Array.isArray(rowView) &&
    typeof rowView.checked === "boolean" &&
    typeof rowView.mixed === "boolean" &&
    !(rowView.checked && rowView.mixed) &&
    typeof rowView.selectionDisabled === "boolean" &&
    Number.isSafeInteger(rowView.depth) &&
    rowView.depth >= 0 &&
    typeof rowView.folder === "boolean" &&
    typeof rowView.expanded === "boolean" &&
    BASE_STRING_FIELDS.every((name) => typeof rowView[name] === "string");
}

function createCell(ownerDocument, name) {
  const cell = ownerDocument.createElement("div");
  cell.className = `nami-file-row__cell nami-file-row__${name}`;
  cell.dataset.fileColumn = name;
  cell.setAttribute("role", "cell");
  return cell;
}

function renderName(cell, rowView) {
  const ownerDocument = cell.ownerDocument;
  if (rowView.folder) {
    const disclosure = ownerDocument.createElement("button");
    disclosure.className = "nami-file-row__disclosure";
    disclosure.type = "button";
    disclosure.ariaExpanded = String(rowView.expanded);
    disclosure.ariaLabel = `${rowView.expanded ? "Collapse" : "Expand"} ${rowView.nameText}`;
    const chevron = ownerDocument.createElement("span");
    chevron.className = "nami-file-row__chevron";
    chevron.ariaHidden = "true";
    disclosure.append(chevron);
    cell.append(disclosure);
  } else {
    const spacer = ownerDocument.createElement("span");
    spacer.className = "nami-file-row__disclosure-spacer";
    spacer.ariaHidden = "true";
    cell.append(spacer);
  }
  const label = ownerDocument.createElement("span");
  label.className = "nami-file-row__name-text";
  renderFilesystemText(label, rowView.nameText);
  cell.append(label);
}

export function renderFileRow(element, rowView, details) {
  if (!(element instanceof HTMLElement)) {
    throw new TypeError("file row target must be an HTMLElement");
  }
  if (
    !validBaseView(rowView) ||
    details === null ||
    typeof details !== "object" ||
    !Array.isArray(details.cells) ||
    details.cells.length !== 2 ||
    !details.cells.every((cell) => cell instanceof HTMLElement) ||
    typeof details.className !== "string" ||
    !details.className
  ) {
    throw new TypeError("file row view is invalid");
  }

  const ownerDocument = element.ownerDocument;
  const selection = createCell(ownerDocument, "selection");
  const checkbox = ownerDocument.createElement("input");
  checkbox.className = "nami-checkbox";
  checkbox.type = "checkbox";
  checkbox.checked = rowView.checked;
  checkbox.indeterminate = rowView.mixed;
  checkbox.disabled = rowView.selectionDisabled;
  checkbox.ariaLabel = rowView.selectionLabel;
  if (rowView.mixed) {
    checkbox.ariaChecked = "mixed";
  }
  selection.append(checkbox);

  const name = createCell(ownerDocument, "name");
  renderName(name, rowView);
  const size = createCell(ownerDocument, "size");
  renderText(size, rowView.sizeText);
  const notes = createCell(ownerDocument, "notes");
  renderText(notes, rowView.notesText);

  element.className = `nami-file-row ${details.className}`;
  element.dataset.folder = String(rowView.folder);
  element.setAttribute("role", "row");
  element.style.setProperty("--nami-file-depth", String(rowView.depth));
  element.replaceChildren(selection, name, size, ...details.cells, notes);
}
