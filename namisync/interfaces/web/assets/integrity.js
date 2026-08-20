import { renderFileRow } from "./file_row.js";
import { renderText } from "./render.js";

const STRING_FIELDS = Object.freeze([
  "presenceText",
  "presenceStatus",
  "checksumText",
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
    STATUS_KEYS.has(rowView.presenceStatus);
}

function createCell(ownerDocument, className, column, text) {
  const cell = ownerDocument.createElement("div");
  cell.className = `nami-file-row__cell ${className}`;
  cell.dataset.fileColumn = column;
  cell.setAttribute("role", "cell");
  renderText(cell, text);
  return cell;
}

function createStatusCell(ownerDocument, className, column, status, text) {
  const cell = createCell(ownerDocument, className, column, text);
  cell.dataset.status = status;
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
  const checksum = createCell(
    ownerDocument,
    "nami-integrity-row__checksum",
    "secondary",
    rowView.checksumText,
  );
  renderFileRow(element, rowView, {
    className: "nami-integrity-row",
    cells: [presence, checksum],
  });
}
