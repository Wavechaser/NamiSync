import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";

function moduleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

process.env.TZ = "UTC";
const renderUrl = moduleUrl(await readFile(join(dirname(process.argv[2]), "render.js"), "utf8"));
const planUrl = moduleUrl("export const renderPlanRow = () => {};");
const iconsUrl = moduleUrl("export const createIcon = () => ({});");
const taskStatusSource = (await readFile(process.argv[3], "utf8"))
  .replace("./render.js", renderUrl);
const taskStatusUrl = moduleUrl(taskStatusSource);
const filterUrl = moduleUrl((await readFile(join(dirname(process.argv[2]), "filter_menu.js"), "utf8"))
  .replace("./icons.js", iconsUrl).replace("./render.js", renderUrl));
const tableColumnsUrl = moduleUrl(await readFile(join(dirname(process.argv[2]), "table_columns.js"), "utf8"));
const source = (await readFile(process.argv[2], "utf8"))
  .replace("./table_columns.js", tableColumnsUrl)
  .replace("./filter_menu.js", filterUrl)
  .replace("./plan.js", planUrl)
  .replace("./icons.js", iconsUrl)
  .replace("./render.js", renderUrl)
  .replace("./task_status.js", taskStatusUrl);
const { projectExecutionRow, projectExecutionSummary } = await import(moduleUrl(source));
const {
  projectActiveOperationProgress,
  taskStatusDigest,
  terminalStatusLine,
} = await import(taskStatusUrl);

const digestSession = "8".repeat(32);
const activeSnapshot = {
  wire_version: 2,
  session_id: digestSession,
  session_state: "active",
  progress_inconsistent: false,
  phase: "execute",
  presentation: {
    value: 50, determinate: true, indeterminate: false,
    items_done: 1, items_total: 4,
    throughput_bytes_per_second: 100, eta_seconds: 5,
  },
  terminal_result: null,
};
const activeDigest = taskStatusDigest({
  sessionId: digestSession, sessionState: "active", executionStarted: true,
  executionControlState: "running", snapshot: activeSnapshot,
});
assert.equal(activeDigest.progress.value, 50);
assert.equal(activeDigest.progress.done, 1);
assert.equal(activeDigest.progress.total, 4);
assert.equal(activeDigest.progress.throughputBytesPerSecond, 100);
assert.equal(activeDigest.progress.etaSeconds, 5);
assert.deepEqual(projectActiveOperationProgress({
  phase: "execute",
  activeItem: { item_id: "2".repeat(32), item_type: "operation" },
  itemPercent: 50,
}, "2".repeat(32)), {
  lifecycleKey: "executing", progressPercent: 50,
});
assert.deepEqual(projectActiveOperationProgress({
  phase: "verify",
  activeItem: { item_id: "2".repeat(32), item_type: "integrity" },
  itemPercent: 40,
}, "2".repeat(32)), {
  verification: true, verificationProgressPercent: 40,
});
assert.equal(projectActiveOperationProgress({
  phase: "verify", activeItem: null, itemPercent: null,
}, "2".repeat(32)), null);

const unknownSnapshot = {
  ...activeSnapshot,
  presentation: {
    ...activeSnapshot.presentation,
    value: 0, determinate: false, indeterminate: true,
    throughput_bytes_per_second: 100, eta_seconds: null,
  },
};
const unknownDigest = taskStatusDigest({
  sessionId: digestSession, sessionState: "active", executionStarted: true,
  executionControlState: "running", snapshot: unknownSnapshot,
});
assert.equal(unknownDigest.progress.determinate, false);
assert.equal(unknownDigest.progress.throughputBytesPerSecond, 100);
assert.equal(unknownDigest.progress.etaSeconds, null);

const pausedDigest = taskStatusDigest({
  sessionId: digestSession, sessionState: "active", executionStarted: true,
  executionControlState: "paused",
  snapshot: { ...unknownSnapshot, presentation: {
    ...unknownSnapshot.presentation, indeterminate: false,
  } },
});
assert.equal(pausedDigest.title, "Paused");
assert.equal(pausedDigest.progress.indeterminate, false);
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
})), "Execution OK · Completed 2026-09-22 02:01 · 1m 5s elapsed");
assert.equal(terminalStatusLine(summary(result({ recording: "degraded" }), {
  started_at: null, ended_at: completedAt,
})), "Recording degraded · Completed 2026-09-22 02:01",
"unrun/null-start completion omits elapsed");
assert.equal(terminalStatusLine(summary(result({ headline: "failed" }), {
  started_at: completedAt, ended_at: startedAt,
})), "Execution failed · Completed 2026-09-22 02:00",
"negative elapsed is unavailable");
assert.equal(terminalStatusLine(summary(result({ headline: "failed" }), {
  started_at: null, ended_at: null,
})), "Execution failed", "missing timestamps do not fabricate completion");
assert.equal(terminalStatusLine(summary(null, {
  started_at: startedAt, ended_at: completedAt,
}), "failed"), "Execution failed · Completed 2026-09-22 02:01 · 1m 5s elapsed",
"terminal state and matching record time remain truthful without an execution result");
assert.equal(terminalStatusLine(summary(null), null), null,
"a live result-free session does not acquire a terminal outcome");
assert.equal(terminalStatusLine(summary(result(), {
  started_at: "invalid", ended_at: "invalid",
})), "Execution OK", "invalid dates do not fabricate completion or elapsed time");
process.env.TZ = "Asia/Shanghai";
assert.equal(terminalStatusLine(summary(result(), {
  started_at: "2026-12-31T23:59:30+00:00", ended_at: "2027-01-01T00:00:35+00:00",
})), "Execution OK · Completed 2027-01-01 08:00 · 1m 5s elapsed");
process.env.TZ = "UTC";

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
  review: { window: { execution: railCapacityExecution } },
});
assert.deepEqual(
  { title: capacityTask.title, state: capacityTask.state, detail: capacityTask.detail },
  {
    title: "Needs target space", state: "degraded",
    detail: "Execution stopped: more target space is needed.",
  },
);
const terminalSnapshot = (terminalResult, sessionId = railCapacityExecution.session_id) => ({
  wire_version: 2, session_id: sessionId, session_state: "failed",
  terminal_result: terminalResult,
  progress_inconsistent: false, phase: null, started_at: null, ended_at: null,
  presentation: { value: 0, determinate: false, indeterminate: false,
    items_done: null, items_total: null, throughput_bytes_per_second: null,
    eta_seconds: null },
});
for (const staleResult of [
  result({ headline: "failed", filesystem: "failed", integrity: "mismatch" }),
  result({ headline: "failed", filesystem: "failed", integrity: "verified", recording: "degraded" }),
]) {
  const staleTask = taskStatusDigest({
    sessionId: railCapacityExecution.session_id, sessionState: "failed",
    executionStarted: true, executionControlState: "running",
    snapshot: terminalSnapshot(staleResult),
    review: { window: { execution: railCapacityExecution } },
  });
  assert.equal(staleTask.title, "Failed", "stale capacity counts cannot recolor a newer failure");
  assert.equal(staleTask.state, "error");
}
const mismatchedCapacityTask = taskStatusDigest({
  sessionId: "9".repeat(32), sessionState: "failed",
  executionStarted: true, executionControlState: "running",
  snapshot: terminalSnapshot({ ...railCapacityResult }, "9".repeat(32)),
  review: { window: { execution: railCapacityExecution } },
});
assert.equal(mismatchedCapacityTask.title, "Failed", "a prior session's capacity counts have no rail authority");
const matchingCapacityTask = taskStatusDigest({
  sessionId: railCapacityExecution.session_id, sessionState: "active",
  executionStarted: true, snapshot: terminalSnapshot({ ...railCapacityResult }),
  review: { window: { execution: railCapacityExecution } },
});
assert.equal(matchingCapacityTask.title, "Needs target space",
  "same-session terminal window counts preserve capacity guidance");
const activeAgainstTerminalWindow = taskStatusDigest({
  sessionId: railCapacityExecution.session_id, sessionState: "active",
  executionStarted: true,
  snapshot: { ...activeSnapshot, session_id: railCapacityExecution.session_id },
  review: { window: { execution: railCapacityExecution } },
});
assert.equal(activeAgainstTerminalWindow.title, "Executing",
  "an active snapshot does not inherit a retained terminal result");
const inconsistentTask = taskStatusDigest({
  sessionId: railCapacityExecution.session_id, sessionState: "active",
  executionStarted: true,
  snapshot: { ...terminalSnapshot(railCapacityResult), progress_inconsistent: true },
  review: { window: { execution: railCapacityExecution } },
});
assert.equal(inconsistentTask.title, "Needs target space");
assert.ok(inconsistentTask.detail.includes("Some progress updates were inconsistent."));

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
  sessionId: digestSession,
  snapshot: { ...terminalSnapshot(result({ headline: "degraded", recording: "degraded",
    recording_degraded_items: 1 }), digestSession), session_state: "completed" },
  review: null, form: null,
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
globalThis.Element = RowElement;
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
