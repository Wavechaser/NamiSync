import { formatByteCount } from "./render.js";

function pathValue(value) {
  return typeof value === "string" && value.trim() !== "" ? value : "-";
}

const RATE_HORIZON_SECONDS = 5;

function percent(done, total) {
  if (done === null || total === null) return null;
  const doneValue = BigInt(done);
  const totalValue = BigInt(total);
  if (totalValue <= 0n) return null;
  const scaled = Number((doneValue * 1000000n) / totalValue) / 10000;
  return Math.max(0, Math.min(100, scaled));
}

function emptyPresentation(phase = null) {
  return Object.freeze({
    phase,
    aggregatePercent: null,
    aggregateHighWater: null,
    itemPercent: null,
    itemHighWater: null,
    itemsDone: null,
    itemsTotal: null,
    throughputBytesPerSecond: null,
    etaSeconds: null,
    activeItem: null,
    sampleAt: null,
    sampleBytesDone: null,
    smoothedRate: null,
    bytesTotal: null,
  });
}

export function rebaseProgressSampling(previous) {
  if (previous === null || typeof previous !== "object") return previous;
  return Object.freeze({
    ...previous,
    throughputBytesPerSecond: null,
    etaSeconds: null,
    sampleAt: null,
    sampleBytesDone: null,
    smoothedRate: null,
  });
}

export function advanceProgressPresentation(previous, progressState, update) {
  if (update?.update_type === "record"
      || ["Gap", "Terminal"].includes(update?.event?.body_type)) {
    return emptyPresentation();
  }
  const raw = progressState?.progress;
  const phase = progressState?.phase ?? null;
  if (raw === null || typeof raw !== "object") {
    return previous?.phase === phase ? previous : emptyPresentation(phase);
  }
  const samePhase = previous?.phase === phase;
  const activeItem = progressState?.activeItem ?? null;
  const sameItem = samePhase
    && previous?.activeItem !== null
    && activeItem !== null
    && previous.activeItem.item_id === activeItem.item_id
    && previous.activeItem.item_type === activeItem.item_type;
  const computedAggregatePercent = percent(raw.bytes_done, raw.bytes_total);
  const aggregateHighWater = computedAggregatePercent === null
    ? (samePhase ? previous.aggregateHighWater : null)
    : Math.max(samePhase ? previous.aggregateHighWater ?? 0 : 0, computedAggregatePercent);
  const computedItemPercent = activeItem === null
    ? null
    : percent(activeItem.item_bytes_done, activeItem.item_bytes_total);
  const itemHighWater = computedItemPercent === null
    ? (sameItem ? previous.itemHighWater : null)
    : Math.max(sameItem ? previous.itemHighWater ?? 0 : 0, computedItemPercent);
  let sampleAt = samePhase ? previous.sampleAt : null;
  let sampleBytesDone = samePhase ? previous.sampleBytesDone : null;
  let smoothedRate = samePhase ? previous.smoothedRate : null;
  let throughputBytesPerSecond = samePhase ? previous.throughputBytesPerSecond : null;
  let etaSeconds = null;
  const acceptedProgress = update?.update_type === "event"
    && update.event?.body_type === "Progress";
  const totalChanged = samePhase && previous.bytesTotal !== raw.bytes_total;
  if (acceptedProgress) {
    const acceptedAt = Date.parse(progressState.progressAt);
    if (totalChanged || sampleAt === null || sampleBytesDone === null) {
      sampleAt = acceptedAt;
      sampleBytesDone = raw.bytes_done;
      smoothedRate = null;
      throughputBytesPerSecond = null;
    } else {
      const elapsedSeconds = (acceptedAt - sampleAt) / 1000;
      if (!(elapsedSeconds > 0)) {
        sampleAt = acceptedAt;
        sampleBytesDone = raw.bytes_done;
        smoothedRate = null;
        throughputBytesPerSecond = null;
      } else {
        const exactDelta = BigInt(raw.bytes_done) - BigInt(sampleBytesDone);
        const observedRate = Number(exactDelta) / elapsedSeconds;
        const alpha = 1 - Math.exp(-elapsedSeconds / RATE_HORIZON_SECONDS);
        smoothedRate = smoothedRate === null
          ? observedRate
          : alpha * observedRate + (1 - alpha) * smoothedRate;
        throughputBytesPerSecond = Number.isFinite(smoothedRate) && smoothedRate >= 0
          ? smoothedRate
          : null;
        sampleAt = acceptedAt;
        sampleBytesDone = raw.bytes_done;
      }
    }
  }
  if (throughputBytesPerSecond !== null && throughputBytesPerSecond > 0
      && raw.bytes_total !== null) {
    const remaining = BigInt(raw.bytes_total) - BigInt(raw.bytes_done);
    const estimate = Number(remaining) / throughputBytesPerSecond;
    etaSeconds = Number.isFinite(estimate) && estimate >= 0 ? estimate : null;
  }
  return Object.freeze({
    phase,
    aggregatePercent: computedAggregatePercent === null ? null : aggregateHighWater,
    aggregateHighWater,
    itemPercent: computedItemPercent === null ? null : itemHighWater,
    itemHighWater,
    itemsDone: raw.items_done,
    itemsTotal: raw.items_total,
    throughputBytesPerSecond,
    etaSeconds,
    activeItem,
    sampleAt,
    sampleBytesDone,
    smoothedRate,
    bytesTotal: raw.bytes_total,
  });
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

function progressDigest(progressState, presentation, active) {
  const progress = progressState?.progress;
  if (progress === null || typeof progress !== "object") return { value: 0, determinate: false, indeterminate: active, phase: progressState?.phase ?? null };
  if (presentation?.aggregatePercent != null) {
    return {
      value: presentation.aggregatePercent,
      determinate: true,
      indeterminate: false,
      done: progress.items_done,
      total: progress.items_total,
      phase: progressState?.phase ?? null,
      throughputBytesPerSecond: presentation.throughputBytesPerSecond,
      etaSeconds: presentation.etaSeconds,
    };
  }
  const itemTotal = progress.items_total;
  const itemsDone = progress.items_done;
  if (progress.bytes_total === "0"
      && Number.isSafeInteger(itemTotal) && itemTotal > 0
      && Number.isSafeInteger(itemsDone)) {
    return {
      value: Math.max(0, Math.min(100, itemsDone / itemTotal * 100)),
      determinate: true,
      indeterminate: false,
      done: itemsDone,
      total: itemTotal,
      phase: progressState?.phase ?? null,
    };
  }
  return {
    value: 0, determinate: false, indeterminate: active,
    done: progress.items_done, total: progress.items_total,
    phase: progressState?.phase ?? null,
    throughputBytesPerSecond: presentation?.throughputBytesPerSecond ?? null,
    etaSeconds: null,
  };
}

const CAPACITY_INTEGRITY_RESULTS = new Set(["not-run", "verified", "baselined"]);

export function isCapacityOnlyExecution(execution, activeResult = execution?.result ?? null) {
  return activeResult !== null
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
  const executionState = task?.sessionState ?? null;
  const active = executionState === "active" && task?.executionControlState !== "paused";
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
      : progressDigest(task?.progressState, task?.progressPresentation, active);
  const retainedExecution = task?.review?.window?.execution ?? null;
  const activeTerminalResult = task?.executionResult ?? retainedExecution?.result ?? null;
  const terminal = terminalDigest(
    activeTerminalResult,
    executionState,
    isCapacityOnlyExecution(retainedExecution, activeTerminalResult),
  );
  const planItemCount = summary?.selected_operation_count ?? 0;
  const planHasItems = (summary?.filter_counts?.all ?? 0) > 0;
  let title = "New task";
  let state = "new";
  if (task?.error !== null && task?.error !== undefined) [title, state] = ["Error", "error"];
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
  if (typeof task?.error === "string") detail = task.error;
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
