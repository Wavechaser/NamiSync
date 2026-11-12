import { renderFileProgress } from "./file_row.js";
import { renderText } from "./render.js";

function createCell(ownerDocument, className, column, text) {
  const cell = ownerDocument.createElement("div");
  cell.className = `nami-file-row__cell ${className}`;
  cell.dataset.fileColumn = column;
  cell.setAttribute("role", "cell");
  renderText(cell, text);
  return cell;
}

export function createIntegrityCell(
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
