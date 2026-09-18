import { formatByteCount } from "./render.js";

function pathValue(value) {
  return typeof value === "string" && value.trim() !== "" ? value : "-";
}

function progressDigest(progressState, active) {
  const progress = progressState?.progress;
  if (progress === null || typeof progress !== "object") return { value: 0, determinate: false, indeterminate: active, phase: progressState?.phase ?? null };
  const total = progress.items_total;
  const done = progress.items_done;
  if (Number.isSafeInteger(total) && total > 0 && Number.isSafeInteger(done)) {
    return { value: Math.max(0, Math.min(100, done / total * 100)), determinate: true, indeterminate: false, done, total, phase: progressState?.phase ?? null };
  }
  return { value: 0, determinate: false, indeterminate: active, phase: progressState?.phase ?? null };
}

export function taskStatusDigest(task) {
  const summary = task?.review?.summary ?? null;
  const form = task?.form ?? null;
  const executionState = task?.sessionState ?? null;
  const active = executionState === "active" && task?.executionControlState !== "paused";
  const progress = summary !== null && !task?.executionStarted
    ? { value: 0, determinate: false, indeterminate: false, phase: null }
    : progressDigest(task?.progressState, active);
  if (task?.executionStarted && executionState === "completed") {
    progress.value = 100;
    progress.determinate = true;
    progress.indeterminate = false;
  }
  const planItemCount = summary?.filter_counts?.all ?? summary?.operation_count ?? 0;
  let title = "New task";
  let state = "new";
  if (task?.error !== null && task?.error !== undefined) [title, state] = ["Error", "error"];
  else if (summary !== null && !task?.executionStarted) [title, state] = ["Plan ready", "plan"];
  else if (executionState === "completed") [title, state] = ["Completed", "completed"];
  else if (executionState === "failed" || executionState === "refused") [title, state] = ["Error", "error"];
  else if (executionState === "canceled") [title, state] = ["Canceled", "canceled"];
  else if (task?.executionStarted) {
    title = task.executionControlState === "paused" ? "Paused" : progress.phase === "verify" ? "Verifying" : "Executing";
    state = title.toLowerCase();
  } else if (executionState === "active") {
    title = task?.taskKind === "inventory" ? "Inventory" : "Planning";
    state = title.toLowerCase();
  }
  let detail;
  if (typeof task?.error === "string") detail = task.error;
  else if (summary !== null && !task?.executionStarted) detail = planItemCount === 0 ? "Plan is empty."
    : `${planItemCount} items, ${formatByteCount(summary.required_bytes)} required.`;
  else if (["completed", "failed", "refused", "canceled"].includes(executionState)) detail = `${title}.`;
  else if (summary === null && task?.executionStarted) detail = progress.total === undefined
    ? "Execution in progress." : `${progress.done} of ${progress.total} items.`;
  else if (summary === null && executionState === "active") detail = task?.taskKind === "inventory"
    ? "Inventory in progress." : "Planning in progress.";
  else if (summary === null) detail = "Choose a source and target.";
  else if (task?.executionStarted) detail = progress.total === undefined
    ? "Execution in progress." : `${progress.done} of ${progress.total} items.`;
  else detail = "Choose a source and target.";
  return Object.freeze({
    title, state, detail,
    sourcePath: pathValue(summary?.source_path ?? form?.source?.text),
    targetPath: pathValue(summary?.target_path ?? form?.target?.text),
    progress,
  });
}
