import { renderFileRow } from "./file_row.js";
import { renderText } from "./render.js";

const STRING_FIELDS = Object.freeze([
  "presenceText",
  "presenceStatus",
  "integrityText",
  "integrityStatus",
]);
const STATUS_KEYS = Object.freeze(new Set([
  "complete",
  "success",
  "failure",
  "error",
  "warning",
  "degraded",
  "incomplete",
  "active",
  "paused",
  "canceled",
  "mismatch",
  "blocked",
  "deferred",
  "neutral",
  "noop",
]));

function validRowView(rowView) {
  return rowView !== null &&
    typeof rowView === "object" &&
    !Array.isArray(rowView) &&
    STRING_FIELDS.every((name) => typeof rowView[name] === "string") &&
    STATUS_KEYS.has(rowView.presenceStatus) &&
    STATUS_KEYS.has(rowView.integrityStatus);
}

function createStatusCell(ownerDocument, className, column, status, text) {
  const cell = ownerDocument.createElement("div");
  cell.className = `nami-file-row__cell ${className}`;
  cell.dataset.fileColumn = column;
  cell.dataset.status = status;
  cell.setAttribute("role", "cell");
  renderText(cell, text);
  return cell;
}

export function renderIntegrityRow(element, rowView) {
  if (!(element instanceof HTMLElement)) {
    throw new TypeError("renderIntegrityRow target must be an HTMLElement");
  }
  if (!validRowView(rowView)) {
    throw new TypeError("renderIntegrityRow view is invalid");
  }
  const ownerDocument = element.ownerDocument;
  const presence = createStatusCell(
    ownerDocument,
    "nami-integrity-row__presence",
    "primary",
    rowView.presenceStatus,
    rowView.presenceText,
  );
  const integrity = createStatusCell(
    ownerDocument,
    "nami-integrity-row__integrity",
    "secondary",
    rowView.integrityStatus,
    rowView.integrityText,
  );
  renderFileRow(element, rowView, {
    className: "nami-integrity-row",
    cells: [presence, integrity],
  });
}
