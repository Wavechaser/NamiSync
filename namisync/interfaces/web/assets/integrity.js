import { renderFileProgress, renderFileRow } from "./file_row.js";
import { renderText } from "./render.js";

const STRING_FIELDS = Object.freeze([
  "presenceText",
  "presenceStatus",
  "checksumText",
]);
const INTEGRITY_KEYS = Object.freeze(new Set([
  "verified",
  "baselined",
  "unverified",
  "modified",
  "reappeared",
  "unsupported",
  "canceled",
  "missing",
  "mismatched",
  "error",
]));
const ROW_LIFECYCLE_KEYS = Object.freeze(new Set([
  "verifying",
  "completed",
]));

function validProgressPercent(rowView) {
  const verifying = rowView.lifecycleKey === "verifying";
  return verifying
    ? typeof rowView.progressPercent === "number" &&
      Number.isFinite(rowView.progressPercent) &&
      rowView.progressPercent >= 0 &&
      rowView.progressPercent <= 100
    : rowView.progressPercent === undefined;
}

function validRowView(rowView) {
  return rowView !== null &&
    typeof rowView === "object" &&
    !Array.isArray(rowView) &&
    STRING_FIELDS.every((name) => typeof rowView[name] === "string") &&
    validProgressPercent(rowView) &&
    (
      rowView.lifecycleKey === undefined
        ? INTEGRITY_KEYS.has(rowView.presenceStatus)
        : typeof rowView.lifecycleKey === "string" &&
          ROW_LIFECYCLE_KEYS.has(rowView.lifecycleKey) &&
          rowView.presenceStatus === ""
    );
}

function createCell(ownerDocument, className, column, text) {
  const cell = ownerDocument.createElement("div");
  cell.className = `nami-file-row__cell ${className}`;
  cell.dataset.fileColumn = column;
  cell.setAttribute("role", "cell");
  renderText(cell, text);
  return cell;
}

function createIntegrityCell(
  ownerDocument,
  className,
  column,
  integrity,
  lifecycle,
  text,
  progressPercent,
) {
  const cell = createCell(ownerDocument, className, column, "");
  if (lifecycle === "verifying") {
    renderFileProgress(cell, text, progressPercent, lifecycle);
    return cell;
  }
  if (lifecycle !== undefined) {
    cell.dataset.lifecycle = lifecycle;
  } else {
    cell.dataset.integrity = integrity;
  }
  const label = ownerDocument.createElement("span");
  label.className = "nami-file-state-label";
  renderText(label, text);
  cell.append(label);
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
  const presence = createIntegrityCell(
    ownerDocument,
    "nami-integrity-row__presence",
    "primary",
    rowView.presenceStatus,
    rowView.lifecycleKey,
    rowView.presenceText,
    rowView.progressPercent,
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
