import { formatByteCount } from "./render.js";

function pathValue(value) {
  return typeof value === "string" && value.trim() !== "" ? value : "-";
}

export function projectActiveOperationProgress(presentation, operationId) {
  const active = presentation?.activeItem;
  if (active === null || active === undefined || active.item_id !== operationId
      || !["operation", "integrity"].includes(active.item_type)) {
    return null;
  }
  if (active.item_type === "integrity" || presentation.phase === "verify") {
    return Object.freeze({
      verification: true,
      verificationProgressPercent: presentation.itemPercent ?? undefined,
    });
  }
  return Object.freeze({
    lifecycleKey: "executing",
    progressPercent: presentation.itemPercent ?? undefined,
  });
}

const CAPACITY_INTEGRITY_RESULTS = new Set(["not-run", "verified", "baselined"]);

export function isCapacityOnlyExecution(execution, activeResult = execution?.result ?? null) {
  return execution != null && activeResult != null
    && execution?.result === activeResult
    && execution.disk_capacity_failure_count > 0
    && execution.failed_operation_count === execution.disk_capacity_failure_count
    && CAPACITY_INTEGRITY_RESULTS.has(activeResult.integrity)
    && activeResult.recording === "ok"
    && activeResult.audit === "ok";
}

function terminalDigest(result, fallbackState, capacityOnly) {
  if (result === null || typeof result !== "object") return null;
  if (result.disposition === "unrun") {
    return { title: "Execution did not start", state: "error", detail: "Execution did not start. Plan again is available." };
  }
  if (capacityOnly) {
    return {
      title: "Needs target space",
      state: "degraded",
      detail: "Execution stopped: more target space is needed.",
      fallbackState,
    };
  }
  const labels = {
    failed: ["Failed", "error"],
    partial: ["Needs review", "error"],
    refused: ["Execution did not start", "error"],
    mismatch: ["Mismatch", "error"],
    canceled: ["Canceled", "canceled"],
    "verification-incomplete": ["Verification incomplete", "degraded"],
    degraded: ["Degraded", "degraded"],
    "all-noop": ["Completed", "completed"],
    success: ["Completed", "completed"],
  };
  const [title, state] = labels[result.headline] ?? ["Needs review", "error"];
  const detail = result.error ?? `${title}.`;
  return { title, state, detail, fallbackState };
}

export function terminalStatusLine(execution, sessionState = null) {
  const result = execution.result;
  if (result === null && !["completed", "failed", "refused", "canceled"].includes(sessionState)) return null;
  const outcome = result === null
    ? ({ completed: "Execution completed", failed: "Execution failed",
      refused: "Execution did not start", canceled: "Execution canceled" })[sessionState]
    : result.headline === "failed" ? "Execution failed"
    : result.headline === "partial" || result.headline === "mismatch" ? "Execution needs review"
      : result.headline === "refused" || result.disposition === "unrun" ? "Execution did not start"
        : result.headline === "canceled" ? "Execution canceled"
          : result.recording === "degraded" ? "Recording degraded"
            : result.headline === "success" || result.headline === "all-noop" ? "Execution OK"
              : "Execution needs review";
  const ended = Date.parse(execution.ended_at);
  const completed = Number.isFinite(ended)
    ? `Completed ${new Date(ended).toLocaleString()}` : null;
  const started = Date.parse(execution.started_at);
  const elapsed = Number.isFinite(started) && Number.isFinite(ended) && ended >= started
    ? Math.floor((ended - started) / 1000) : null;
  const duration = elapsed === null ? null
    : [elapsed >= 3600 ? `${Math.floor(elapsed / 3600)}h` : null,
      elapsed >= 60 ? `${Math.floor(elapsed % 3600 / 60)}m` : null,
      `${elapsed % 60}s`].filter(Boolean).join(" ") + " elapsed";
  return [outcome, completed, duration].filter(Boolean).join(" · ");
}

export function taskStatusDigest(task) {
  const summary = task?.review?.summary ?? null;
  const form = task?.form ?? null;
  const snapshot = task?.snapshot != null && task.snapshot.session_id === task.sessionId
    ? task.snapshot : null;
  const executionState = snapshot?.session_state ?? task?.sessionState ?? null;
  // Planning has no item-level progress, but the shell can still tell us that
  // it is underway. Keep the task rail animated while the start request is
  // being admitted, while a new plan view is loading, or while an active task
  // has not produced a plan yet. Once a plan is available, an existing active
  // session is a ready-to-review plan rather than an indeterminate operation.
  const planning = task?.error == null && task?.taskKind !== "inventory" && !task?.executionStarted && (
    task?.reviewLoading === true
    || (summary === null && executionState === "active")
    || (["sync-plan", "plan-again"].includes(form?.attempt?.kind)
      && form.attempt.dispatched === true && form.attempt.running === true)
  );
  const progress = planning
    ? { value: 0, determinate: false, indeterminate: true, phase: "plan" }
    : (summary !== null || task?.error != null) && !task?.executionStarted
      ? { value: 0, determinate: false, indeterminate: false, phase: null }
      : snapshot === null
        ? { value: 0, determinate: false, indeterminate: executionState === "active", phase: null }
        : {
          value: snapshot.presentation.value,
          determinate: snapshot.presentation.determinate,
          indeterminate: snapshot.presentation.indeterminate,
          done: snapshot.presentation.items_done,
          total: snapshot.presentation.items_total,
          phase: snapshot.phase,
          throughputBytesPerSecond: snapshot.presentation.throughput_bytes_per_second,
          etaSeconds: snapshot.presentation.eta_seconds,
        };
  const retainedExecution = task?.review?.window?.execution ?? null;
  const activeTerminalResult = task?.executionStarted
    ? snapshot?.terminal_result ?? task?.executionResult ?? retainedExecution?.result ?? null : null;
  const matchingRetainedResult = task?.executionStarted && snapshot !== null
    && retainedExecution !== null
    && retainedExecution?.session_id === snapshot.session_id
    && retainedExecution.result !== null
    && JSON.stringify(retainedExecution.result) === JSON.stringify(snapshot.terminal_result);
  const terminal = terminalDigest(
    activeTerminalResult,
    executionState,
    isCapacityOnlyExecution(retainedExecution,
      matchingRetainedResult ? retainedExecution.result : activeTerminalResult),
  );
  const planItemCount = summary?.selected_operation_count ?? 0;
  const planHasItems = (summary?.filter_counts?.all ?? 0) > 0;
  const releaseMessage = task?.releaseRecovery?.message ?? null;
  let title = "New task";
  let state = "new";
  if (releaseMessage !== null || (task?.error !== null && task?.error !== undefined)) {
    [title, state] = ["Error", "error"];
  }
  else if (planning) [title, state] = ["Planning", "planning"];
  else if (summary !== null && !task?.executionStarted) [title, state] = ["Plan ready", "plan"];
  else if (terminal !== null) ({ title, state } = terminal);
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
  if (releaseMessage !== null) detail = releaseMessage;
  else if (typeof task?.error === "string") detail = task.error;
  else if (planning) detail = "Planning in progress.";
  else if (summary !== null && !task?.executionStarted) detail = planItemCount === 0 && !planHasItems ? "Plan is empty."
    : `${planItemCount} items, ${formatByteCount(summary.required_bytes)} required.`;
  else if (terminal !== null) detail = terminal.detail;
  else if (["completed", "failed", "refused", "canceled"].includes(executionState)) detail = `${title}.`;
  else if (summary === null && task?.executionStarted) detail = progress.total == null
    ? "Execution in progress." : `${progress.done} of ${progress.total} items.`;
  else if (summary === null && executionState === "active") detail = task?.taskKind === "inventory"
    ? "Inventory in progress." : "Planning in progress.";
  else if (summary === null) detail = "Choose a source and target.";
  else if (task?.executionStarted) detail = progress.total == null
    ? "Execution in progress." : `${progress.done} of ${progress.total} items.`;
  else detail = "Choose a source and target.";
  return Object.freeze({
    title, state, detail,
    sourcePath: pathValue(summary?.source_path ?? form?.source?.text),
    targetPath: pathValue(summary?.target_path ?? form?.target?.text),
    progress,
  });
}
