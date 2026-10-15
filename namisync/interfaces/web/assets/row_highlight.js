// Compact gestures only: Python owns membership, anchors, and range resolution.
export function pointerHighlightGesture(event) {
  const modified = event.ctrlKey || event.metaKey;
  return event.shiftKey ? (modified ? "add-range" : "extend")
    : modified ? "toggle" : "replace";
}

export function keyboardHighlightGesture(event) {
  if (event.key === "Escape") return "clear";
  if (event.altKey || event.ctrlKey || event.metaKey) return null;
  if (event.key === "Home") return "first";
  if (event.key === "End") return "last";
  if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return null;
  const direction = event.key === "ArrowUp" ? "move_up" : "move_down";
  return event.shiftKey ? `${direction}_extend` : direction;
}
