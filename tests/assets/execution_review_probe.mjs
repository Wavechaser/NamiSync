import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";

function moduleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

const renderUrl = moduleUrl(`
  export const formatByteCount = (value) => String(value);
  export const renderFilesystemText = (element, value) => { element.textContent = value; };
  export const renderText = (element, value) => { element.textContent = value; };
`);
const planUrl = moduleUrl("export const renderPlanRow = () => {};");
const iconsUrl = moduleUrl("export const createIcon = () => ({});");
const taskStatusSource = (await readFile(process.argv[3], "utf8"))
  .replace("./render.js", renderUrl);
const taskStatusUrl = moduleUrl(taskStatusSource);
const source = (await readFile(process.argv[2], "utf8"))
  .replace("./plan.js", planUrl)
  .replace("./icons.js", iconsUrl)
  .replace("./render.js", renderUrl)
  .replace("./task_status.js", taskStatusUrl);
const { projectExecutionRow, projectExecutionSummary } = await import(moduleUrl(source));
const {
  advanceProgressPresentation,
  projectActiveOperationProgress,
  rebaseProgressSampling,
  taskStatusDigest,
  terminalStatusLine,
} = await import(taskStatusUrl);

const progressUpdate = (at) => ({
  update_type: "event",
  event: { body_type: "Progress", at },
});
const progressState = (at, patch = {}, activePatch = {}) => ({
  phase: patch.phase ?? "execute",
  progressAt: at,
  progress: {
    phase: patch.phase ?? "execute",
    items_done: 1,
    items_total: 4,
    bytes_done: "0",
    bytes_total: "1000",
    ...patch,
  },
  activeItem: {
    item_id: "2".repeat(32),
    item_type: "operation",
    item_attempt_id: "3".repeat(32),
    item_bytes_done: "0",
    item_bytes_total: "100",
    ...activePatch,
  },
});

let presentation = advanceProgressPresentation(
  null,
  progressState("2026-09-22T00:00:00+00:00"),
  progressUpdate("2026-09-22T00:00:00+00:00"),
);
presentation = advanceProgressPresentation(
  presentation,
  progressState("2026-09-22T00:00:05+00:00", { bytes_done: "500" }, {
    item_bytes_done: "50",
  }),
  progressUpdate("2026-09-22T00:00:05+00:00"),
);
assert.equal(presentation.aggregatePercent, 50);
assert.equal(presentation.itemPercent, 50);
assert.equal(presentation.throughputBytesPerSecond, 100);
assert.equal(presentation.etaSeconds, 5);

const changedRate = advanceProgressPresentation(
  presentation,
  progressState("2026-09-22T00:00:10+00:00", { bytes_done: "750" }),
  progressUpdate("2026-09-22T00:00:10+00:00"),
);
const expectedChangedRate = 50 + 50 / Math.E;
assert.ok(Math.abs(changedRate.throughputBytesPerSecond - expectedChangedRate) < 1e-9,
  "a changed rate uses the five-second time-weighted EMA");
assert.ok(Math.abs(changedRate.etaSeconds - 250 / expectedChangedRate) < 1e-9,
  "phase ETA uses that same smoothed rate");

assert.deepEqual(projectActiveOperationProgress(presentation, "2".repeat(32)), {
  lifecycleKey: "executing", progressPercent: 50,
});

presentation = advanceProgressPresentation(
  presentation,
  progressState("2026-09-22T00:00:05+00:00", { bytes_done: "600" }, {
    item_attempt_id: "4".repeat(32), item_bytes_done: "0",
  }),
  progressUpdate("2026-09-22T00:00:05+00:00"),
);
assert.equal(presentation.throughputBytesPerSecond, null, "equal event time rebases");
assert.equal(presentation.itemPercent, 50, "a retry does not move the row backward");

presentation = advanceProgressPresentation(
  presentation,
  progressState("2026-09-22T00:00:10+00:00", {
    phase: "verify", bytes_done: "400", bytes_total: "2000",
  }, { item_type: "integrity", item_bytes_done: "40" }),
  progressUpdate("2026-09-22T00:00:10+00:00"),
);
assert.equal(presentation.aggregatePercent, 20, "a phase starts a new display domain");
assert.deepEqual(projectActiveOperationProgress(presentation, "2".repeat(32)), {
  verification: true, verificationProgressPercent: 40,
});
const rebased = rebaseProgressSampling(presentation);
assert.equal(rebased.aggregatePercent, 20);
assert.equal(rebased.itemPercent, 40);
assert.equal(rebased.sampleAt, null);
assert.equal(rebased.throughputBytesPerSecond, null);
assert.equal(projectActiveOperationProgress(rebased, "9".repeat(32)), null);

let largeUnknown = advanceProgressPresentation(
  null,
  progressState("2026-09-22T01:00:00+00:00", {
    bytes_done: "90071992547409930", bytes_total: null,
  }),
  progressUpdate("2026-09-22T01:00:00+00:00"),
);
largeUnknown = advanceProgressPresentation(
  largeUnknown,
  progressState("2026-09-22T01:00:05+00:00", {
    bytes_done: "90071992547410430", bytes_total: null,
  }),
  progressUpdate("2026-09-22T01:00:05+00:00"),
);
assert.equal(largeUnknown.throughputBytesPerSecond, 100,
  "Scalar64 subtraction happens before approximate conversion");
assert.equal(largeUnknown.etaSeconds, null, "unknown total suppresses only ETA");
const unknownDigest = taskStatusDigest({
  sessionState: "active", executionStarted: true, executionControlState: "running",
  progressState: progressState("2026-09-22T01:00:05+00:00", {
    bytes_done: "90071992547410430", bytes_total: null,
  }),
  progressPresentation: largeUnknown,
});
assert.equal(unknownDigest.progress.throughputBytesPerSecond, 100);
assert.equal(unknownDigest.progress.etaSeconds, null);
assert.equal(unknownDigest.progress.determinate, false);
largeUnknown = advanceProgressPresentation(
  largeUnknown,
  progressState("2026-09-22T00:59:59+00:00", {
    bytes_done: "90071992547410530", bytes_total: null,
  }),
  progressUpdate("2026-09-22T00:59:59+00:00"),
);
assert.equal(largeUnknown.throughputBytesPerSecond, null,
  "backward event time rebases without rejecting progress");

let growingBudget = advanceProgressPresentation(
  null,
  progressState("2026-09-22T02:00:00+00:00", {
    phase: "verify", bytes_done: "800", bytes_total: "1000",
  }, { item_type: "integrity", item_bytes_done: "80" }),
  progressUpdate("2026-09-22T02:00:00+00:00"),
);
growingBudget = advanceProgressPresentation(
  growingBudget,
  progressState("2026-09-22T02:00:05+00:00", {
    phase: "verify", bytes_done: "900", bytes_total: "2000",
  }, { item_type: "integrity", item_bytes_done: "40" }),
  progressUpdate("2026-09-22T02:00:05+00:00"),
);
assert.equal(growingBudget.aggregatePercent, 80, "budget growth holds aggregate high-water");
assert.equal(growingBudget.itemPercent, 80, "same-item verifier retry holds row high-water");
assert.equal(growingBudget.throughputBytesPerSecond, null, "budget growth restarts sampling");

const terminalPresentation = advanceProgressPresentation(
  rebased,
  { phase: null, progressAt: null, progress: null, activeItem: null },
  { update_type: "record" },
);
assert.equal(terminalPresentation.phase, null);
assert.equal(terminalPresentation.aggregatePercent, null);

const result = (patch = {}) => ({
  headline: "success", filesystem: "completed", integrity: "verified",
  recording: "ok", audit: "ok", disposition: "ran", canceled: false,
  phases: [], bytes_done: "0", bytes_total: "0", error: null,
  recording_degraded_items: 0, recording_issues: [], omitted_detail_count: 0,
  presentation_omitted_detail_count: 0, review_refusal: null, ...patch,
});
const summary = (terminal, patch = {}) => ({
  execution_revision: 7, session_id: "1".repeat(32), result: terminal,
  failed_operation_count: terminal === null ? null : 0,
  disk_capacity_failure_count: terminal === null ? null : 0,
  gap: null, trash_location: terminal === null ? null : "D:\\.synctrash", ...patch,
});

const completedAt = "2026-09-22T02:01:05+00:00";
const startedAt = "2026-09-22T02:00:00+00:00";
assert.equal(terminalStatusLine(summary(result(), {
  started_at: startedAt, ended_at: completedAt,
})), `Execution OK · Completed ${new Date(completedAt).toLocaleString()} · 1m 5s elapsed`);
assert.equal(terminalStatusLine(summary(result({ recording: "degraded" }), {
  started_at: null, ended_at: completedAt,
})), `Recording degraded · Completed ${new Date(completedAt).toLocaleString()}`,
"unrun/null-start completion omits elapsed");
assert.equal(terminalStatusLine(summary(result({ headline: "failed" }), {
  started_at: completedAt, ended_at: startedAt,
})), `Execution failed · Completed ${new Date(startedAt).toLocaleString()}`,
"negative elapsed is unavailable");
assert.equal(terminalStatusLine(summary(result({ headline: "failed" }), {
  started_at: null, ended_at: null,
})), "Execution failed", "missing timestamps do not fabricate completion");
assert.equal(terminalStatusLine(summary(null, {
  started_at: startedAt, ended_at: completedAt,
}), "failed"), `Execution failed · Completed ${new Date(completedAt).toLocaleString()} · 1m 5s elapsed`,
"terminal state and matching record time remain truthful without an execution result");
assert.equal(terminalStatusLine(summary(null), null), null,
"a live result-free session does not acquire a terminal outcome");

assert.deepEqual(projectExecutionSummary(summary(null)), {
  title: "Execution in progress", status: "executing",
});
assert.deepEqual(projectExecutionSummary(summary(result())), {
  title: "Execution completed", status: "completed",
}, "a successful zero-byte run is completed, not unrun");
assert.equal(projectExecutionSummary(summary(result({ headline: "partial", filesystem: "failed" }))).status, "error");
assert.equal(projectExecutionSummary(summary(result({ headline: "canceled", filesystem: "canceled", canceled: true }))).title, "Execution canceled");
assert.equal(projectExecutionSummary(summary(result({
  headline: "refused", filesystem: "refused", integrity: "not-run", disposition: "unrun",
}))).title, "Execution did not start");
for (const integrity of ["not-run", "verified", "baselined"]) {
  assert.deepEqual(projectExecutionSummary(summary(result({
    headline: "failed", filesystem: "failed", integrity,
  }), { failed_operation_count: 1, disk_capacity_failure_count: 1 })), {
    title: "Execution stopped: more target space is needed", status: "attention",
  });
}
assert.equal(projectExecutionSummary(summary(result({
  headline: "failed", filesystem: "failed", integrity: "not-run",
}), { failed_operation_count: 2, disk_capacity_failure_count: 1 })).title,
"Execution failed", "capacity cannot mask an independent operation failure");
for (const patch of [
  { integrity: "mismatch" },
  { integrity: "unknown" },
  { integrity: "verified", recording: "degraded" },
  { integrity: "baselined", audit: "degraded" },
]) {
  assert.equal(projectExecutionSummary(summary(result({
    headline: "failed", filesystem: "failed", ...patch,
  }), { failed_operation_count: 1, disk_capacity_failure_count: 1 })).title,
  "Execution failed", "capacity guidance requires every independent axis to be safe");
}
assert.equal(projectExecutionSummary(summary(result({
  headline: "failed", filesystem: "failed", integrity: "verified",
}), { failed_operation_count: 1, disk_capacity_failure_count: 0 })).title,
"Execution failed", "capacity guidance requires a positive known capacity count");
assert.equal(projectExecutionSummary(summary(result({
  headline: "mismatch", integrity: "mismatch",
}))).title, "Verification mismatch");
assert.equal(projectExecutionSummary(summary(result({
  headline: "degraded", recording: "degraded", audit: "degraded",
  recording_degraded_items: 1,
}))).status, "attention");

const operation = (patch = {}) => ({
  result: "succeeded", reason: null, recording: "ok", recording_reason: null,
  detail_omitted_count: 0, ...patch,
});
const verification = (patch = {}) => ({
  result: "verified", reason: null, recording: "ok", record_disposition: "noop",
  detail_omitted_count: 0, ...patch,
});
const evidence = (state, content = null) => ({ state, content });
const row = projectExecutionRow({
  operation: operation({ detail_omitted_count: 2 }),
  automatic_verification: verification({ detail_omitted_count: 3 }),
  evidence: evidence("recorded-copy", {
    algorithm: "xxh3_128", digest: "abcdef0123456789abcdef0123456789", size: "0",
    provenance: "copy", observed_at: "2026-09-20T00:00:00+00:00",
  }),
});
assert.equal(row.lifecycle, "completed");
assert.equal(row.checksum, "abcdef01");
assert.ok(row.notes.includes("Operation: Completed"));
assert.ok(row.notes.includes("Automatic verification: Verified"));
assert.ok(row.notes.includes("2 operation details omitted"));
assert.ok(row.notes.includes("3 verification details omitted"));
assert.ok(row.notes.includes("Stored evidence: Recorded copy"));

for (const state of ["unrecorded", "superseded", "not-applicable"]) {
  const projected = projectExecutionRow({
    operation: operation(), automatic_verification: null, evidence: evidence(state),
  });
  assert.equal(projected.checksum, "");
  assert.ok(projected.notes.includes(`Stored evidence: ${state === "not-applicable" ? "Not applicable" : state[0].toUpperCase() + state.slice(1)}`));
}
assert.deepEqual(projectExecutionRow({
  operation: null, automatic_verification: null, evidence: null,
}), { lifecycle: null, intent: null, checksum: "", notes: [] }, "missing axes remain unknown");
const capacityRow = projectExecutionRow({
  operation: operation({ result: "failed", reason: "disk-capacity" }),
  automatic_verification: null,
  evidence: evidence("unrecorded"),
});
assert.equal(capacityRow.lifecycle, "capacity");
assert.equal(capacityRow.intent, "Failed");
assert.ok(capacityRow.notes.includes("Operation: Failed (Disk capacity)"));
assert.ok(capacityRow.notes.includes("Stored evidence: Unrecorded"));

const railCapacityResult = result({
  headline: "failed", filesystem: "failed", integrity: "verified",
});
const railCapacityExecution = summary(railCapacityResult, {
  failed_operation_count: 1, disk_capacity_failure_count: 1,
});
const capacityTask = taskStatusDigest({
  sessionState: "failed", executionStarted: true, executionControlState: "running",
  executionResult: railCapacityResult,
  review: { window: { execution: railCapacityExecution } },
});
assert.deepEqual(
  { title: capacityTask.title, state: capacityTask.state, detail: capacityTask.detail },
  {
    title: "Needs target space", state: "degraded",
    detail: "Execution stopped: more target space is needed.",
  },
);
for (const staleResult of [
  result({ headline: "failed", filesystem: "failed", integrity: "mismatch" }),
  result({ headline: "failed", filesystem: "failed", integrity: "verified", recording: "degraded" }),
]) {
  const staleTask = taskStatusDigest({
    sessionState: "failed", executionStarted: true, executionControlState: "running",
    executionResult: staleResult,
    review: { window: { execution: railCapacityExecution } },
  });
  assert.equal(staleTask.title, "Failed", "stale capacity counts cannot recolor a newer failure");
  assert.equal(staleTask.state, "error");
}
const mismatchedCapacityTask = taskStatusDigest({
  sessionState: "failed", executionStarted: true, executionControlState: "running",
  executionResult: { ...railCapacityResult },
  review: { window: { execution: railCapacityExecution } },
});
assert.equal(mismatchedCapacityTask.title, "Failed", "structurally equal stale results have no rail authority");

const mixedResult = result({
  headline: "mismatch", filesystem: "failed", integrity: "mismatch",
  recording: "degraded", recording_degraded_items: 1,
});
const mixedWindow = {
  execution: summary(mixedResult, {
    failed_operation_count: 1, disk_capacity_failure_count: 1,
  }),
  rows: [
    {
      operation: operation(),
      automatic_verification: verification({ result: "mismatched", reason: "hash-mismatch" }),
      evidence: evidence("superseded"),
    },
    {
      operation: operation({
        result: "failed", reason: "disk-capacity", recording: "degraded",
        recording_reason: "record-write-failed",
      }),
      automatic_verification: null,
      evidence: evidence("unrecorded"),
    },
  ],
};
assert.deepEqual(projectExecutionSummary(mixedWindow.execution), {
  title: "Verification mismatch", status: "error",
}, "a mixed window keeps its known aggregate integrity failure red");
const mixedRail = taskStatusDigest({
  sessionState: "failed", executionStarted: true, executionControlState: "running",
  executionResult: mixedResult,
  review: { window: mixedWindow },
});
assert.deepEqual({ title: mixedRail.title, state: mixedRail.state }, {
  title: "Mismatch", state: "error",
}, "the rail uses the same active mixed terminal result");
const [mismatchedRow, mixedCapacityRow] = mixedWindow.rows.map(projectExecutionRow);
assert.equal(mismatchedRow.lifecycle, "completed");
assert.ok(mismatchedRow.notes.includes("Automatic verification: Mismatch (Hash mismatch)"));
assert.ok(mismatchedRow.notes.includes("Stored evidence: Superseded"));
assert.equal(mixedCapacityRow.lifecycle, "capacity");
assert.equal(mixedCapacityRow.intent, "Failed");
assert.ok(mixedCapacityRow.notes.includes("Operation: Failed (Disk capacity)"));
assert.ok(mixedCapacityRow.notes.includes("Recording: Degraded (Record write failed)"));
assert.ok(mixedCapacityRow.notes.includes("Stored evidence: Unrecorded"));

const terminalTask = taskStatusDigest({
  sessionState: "completed", executionStarted: true, executionControlState: "running",
  executionResult: result({ headline: "degraded", recording: "degraded",
    recording_degraded_items: 1 }), progressState: null, review: null, form: null,
});
assert.equal(terminalTask.title, "Degraded", "known terminal degradation cannot stay green");
assert.equal(terminalTask.state, "degraded");

// Exercise the production row renderer rather than only its projected values.
class RowElement {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName; this.ownerDocument = ownerDocument;
    this.children = []; this.dataset = {}; this.attributes = {};
    this.style = { setProperty() {} };
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this.attributes[name] = value; }
}
const rowDocument = { createElement: (tag) => new RowElement(tag, rowDocument) };
globalThis.HTMLElement = RowElement;
const rowAssets = dirname(process.argv[2]);
const fileRowUrl = moduleUrl((await readFile(join(rowAssets, "file_row.js"), "utf8"))
  .replace("./render.js", renderUrl));
const realPlanUrl = moduleUrl((await readFile(join(rowAssets, "plan.js"), "utf8"))
  .replace("./file_row.js", fileRowUrl).replace("./render.js", renderUrl));
const { renderPlanRow } = await import(realPlanUrl);
const baseRenderedRow = {
  checked: true, mixed: false, selectionDisabled: true, depth: 0,
  folder: false, expanded: false, selectionLabel: "Select copy", nameText: "copy.bin",
  sizeText: "100 B", intentText: "Completed", intentKey: "", checksumText: "",
  modifiedText: "", notesText: "", lifecycleKey: "completed",
};
const descendants = (element) => [element, ...element.children.flatMap(descendants)];
for (const [itemType, phase] of [["operation", "execute"], ["operation", "verify"], ["integrity", "verify"]]) {
  for (const itemPercent of [40, null]) {
    const rendered = rowDocument.createElement("div");
    const overlay = projectActiveOperationProgress({
      phase, activeItem: { item_id: "2".repeat(32), item_type: itemType }, itemPercent,
    }, "2".repeat(32));
    renderPlanRow(rendered, { ...baseRenderedRow, ...overlay });
    const intent = rendered.children.find((child) => child.dataset.fileColumn === "primary");
    const verifying = phase === "verify";
    assert.equal(intent.dataset.lifecycle, verifying ? "completed" : "executing");
    const verification = intent.children.find((child) => child.className === "nami-plan-row__verification");
    if (verifying) {
      assert.equal(intent.children[0].textContent, "Completed");
      assert.ok(verification, "verification has its own nested presentation");
      if (itemPercent === null) assert.equal(verification.textContent, "Verifying");
    } else {
      assert.equal(verification, undefined);
    }
    const bars = descendants(intent).filter((child) => child.attributes.role === "progressbar");
    assert.equal(bars.length, itemPercent === null ? 0 : 1);
    if (itemPercent !== null) assert.equal(bars[0].ariaValueNow, "40");
  }
}
process.stdout.write("ok");
