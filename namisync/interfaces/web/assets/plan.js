import { renderFileRow } from "./file_row.js";
import { renderText } from "./render.js";

const STRING_FIELDS = Object.freeze([
  "selectionLabel",
  "nameText",
  "sizeText",
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
    typeof rowView.mixed === "boolean" &&
    !(rowView.checked && rowView.mixed) &&
    typeof rowView.selectionDisabled === "boolean" &&
    Number.isSafeInteger(rowView.depth) &&
    rowView.depth >= 0 &&
    typeof rowView.folder === "boolean" &&
    typeof rowView.expanded === "boolean" &&
    STRING_FIELDS.every((name) => typeof rowView[name] === "string") &&
    ["", "operation", "status"].includes(rowView.intentTone) &&
    (
      rowView.intentTone === ""
        ? rowView.intentKey === ""
        : /^[a-z_]+$/u.test(rowView.intentKey)
    );
}

function createCell(ownerDocument, className, column) {
  const cell = ownerDocument.createElement("div");
  cell.className = `nami-file-row__cell ${className}`;
  cell.dataset.fileColumn = column;
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
  const intent = createCell(ownerDocument, "nami-plan-row__intent", "primary");
  if (rowView.intentTone !== "") {
    intent.dataset[rowView.intentTone] = rowView.intentKey;
  }
  renderText(intent, rowView.intentText);

  const checksum = createCell(ownerDocument, "nami-plan-row__checksum", "secondary");
  renderText(checksum, rowView.checksumText);

  renderFileRow(element, rowView, {
    className: "nami-plan-row",
    cells: [intent, checksum],
  });
}
