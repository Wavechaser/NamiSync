import { renderFileProgress, renderFileRow } from "./file_row.js";
import { renderText } from "./render.js";

const STRING_FIELDS = Object.freeze([
  "selectionLabel",
  "nameText",
  "sizeText",
  "intentText",
  "intentKey",
  "checksumText",
  "notesText",
]);
const INTENT_KEYS = Object.freeze(new Set([
  "copy",
  "mkdir",
  "move",
  "recase",
  "update",
  "move_update",
  "trash",
  "delete",
  "noop",
  "error",
  "unsupported",
  "blocked",
]));
const ROW_LIFECYCLE_KEYS = Object.freeze(new Set([
  "executing",
  "completed",
]));

function validProgressPercent(rowView) {
  const executing = rowView.lifecycleKey === "executing";
  return executing
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
    typeof rowView.checked === "boolean" &&
    typeof rowView.mixed === "boolean" &&
    !(rowView.checked && rowView.mixed) &&
    typeof rowView.selectionDisabled === "boolean" &&
    Number.isSafeInteger(rowView.depth) &&
    rowView.depth >= 0 &&
    typeof rowView.folder === "boolean" &&
    typeof rowView.expanded === "boolean" &&
    STRING_FIELDS.every((name) => typeof rowView[name] === "string") &&
    validProgressPercent(rowView) &&
    (
      rowView.lifecycleKey === undefined
        ? rowView.intentKey === "" || INTENT_KEYS.has(rowView.intentKey)
        : typeof rowView.lifecycleKey === "string" &&
          ROW_LIFECYCLE_KEYS.has(rowView.lifecycleKey) &&
          rowView.intentKey === ""
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
  if (rowView.lifecycleKey !== undefined) {
    intent.dataset.lifecycle = rowView.lifecycleKey;
  } else if (rowView.intentKey !== "") {
    intent.dataset.intent = rowView.intentKey;
  }
  if (rowView.lifecycleKey === "executing") {
    renderFileProgress(
      intent,
      rowView.intentText,
      rowView.progressPercent,
      rowView.lifecycleKey,
    );
  } else {
    const intentLabel = ownerDocument.createElement("span");
    intentLabel.className = "nami-file-state-label";
    renderText(intentLabel, rowView.intentText);
    intent.append(intentLabel);
  }

  const checksum = createCell(ownerDocument, "nami-plan-row__checksum", "secondary");
  renderText(checksum, rowView.checksumText);

  renderFileRow(element, rowView, {
    className: "nami-plan-row",
    cells: [intent, checksum],
  });
}
