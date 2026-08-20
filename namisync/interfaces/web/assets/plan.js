import { renderFilesystemText, renderText } from "./render.js";

const STRING_FIELDS = Object.freeze([
  "selectionLabel",
  "pathText",
  "intentText",
  "intentTone",
  "intentKey",
  "checksumText",
  "notesText",
]);

function validRowView(rowView) {
  return rowView !== null &&
    typeof rowView === "object" &&
    !Array.isArray(rowView) &&
    typeof rowView.checked === "boolean" &&
    typeof rowView.selectionDisabled === "boolean" &&
    Number.isSafeInteger(rowView.depth) &&
    rowView.depth >= 0 &&
    typeof rowView.folder === "boolean" &&
    STRING_FIELDS.every((name) => typeof rowView[name] === "string") &&
    ["", "operation", "status"].includes(rowView.intentTone) &&
    (
      rowView.intentTone === ""
        ? rowView.intentKey === ""
        : /^[a-z_]+$/u.test(rowView.intentKey)
    );
}

function createCell(ownerDocument, className) {
  const cell = ownerDocument.createElement("div");
  cell.className = `nami-plan-row__cell ${className}`;
  cell.setAttribute("role", "cell");
  return cell;
}

export function renderPlanRow(element, rowView) {
  if (!(element instanceof HTMLElement)) {
    throw new TypeError("renderPlanRow target must be an HTMLElement");
  }
  if (!validRowView(rowView)) {
    throw new TypeError("renderPlanRow view is invalid");
  }

  const ownerDocument = element.ownerDocument;
  const selection = createCell(ownerDocument, "nami-plan-row__selection");
  const checkbox = ownerDocument.createElement("input");
  checkbox.className = "nami-checkbox";
  checkbox.type = "checkbox";
  checkbox.checked = rowView.checked;
  checkbox.disabled = rowView.selectionDisabled;
  checkbox.ariaLabel = rowView.selectionLabel;
  selection.append(checkbox);

  const path = createCell(ownerDocument, "nami-plan-row__path");
  renderFilesystemText(path, rowView.pathText);

  const intent = createCell(ownerDocument, "nami-plan-row__intent");
  if (rowView.intentTone !== "") {
    intent.dataset[rowView.intentTone] = rowView.intentKey;
  }
  renderText(intent, rowView.intentText);

  const checksum = createCell(ownerDocument, "nami-plan-row__checksum");
  renderText(checksum, rowView.checksumText);

  const notes = createCell(ownerDocument, "nami-plan-row__notes");
  renderText(notes, rowView.notesText);

  element.className = "nami-plan-row";
  element.dataset.folder = String(rowView.folder);
  element.setAttribute("role", "row");
  element.style.setProperty("--nami-plan-depth", String(rowView.depth));
  element.replaceChildren(selection, path, intent, checksum, notes);
}
