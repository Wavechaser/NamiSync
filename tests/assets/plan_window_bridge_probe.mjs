import { readFile } from "node:fs/promises";

const listeners = new Map();
globalThis.window = {
  addEventListener(name, callback, options = {}) {
    const entries = listeners.get(name) ?? [];
    entries.push({ callback, once: options.once === true });
    listeners.set(name, entries);
  },
  removeEventListener(name, callback) {
    listeners.set(name, (listeners.get(name) ?? []).filter((entry) => entry.callback !== callback));
  },
  pywebview: { api: null },
};

function dispatch(name) {
  const entries = listeners.get(name) ?? [];
  listeners.set(name, entries.filter((entry) => !entry.once));
  for (const entry of entries) entry.callback();
}

const bridge = await import(`data:text/javascript;base64,${Buffer.from(
  await readFile(process.argv[2], "utf8"),
).toString("base64")}`);

const taskId = `task-${"1".repeat(32)}`;
const baseRow = {
  node_id: `node-${"2".repeat(32)}`,
  display: "overflow.bin",
  depth: 0,
  is_container: false,
  visible_index: 0,
  parent_visible_index: null,
  first_child_visible_index: null,
  position_in_set: 1,
  set_size: 1,
  expanded: null,
  row_kind: "operation",
  operation_id: "3".repeat(32),
  operation_kind: "copy",
  reason: null,
  blocked_reason: null,
  selection: "selected",
  highlighted: false,
  selectable_operation_count: 1,
  selected_operation_count: 1,
  operation_count: 1,
  mtime_ns: null,
  dependency_count: 0,
  risk: "none",
  move_peer_id: null,
  move_group: null,
  notice: "Partial size: overflow",
  selection_exclusion_reason: null,
  execution: {
    operation: null,
    automatic_verification: null,
    evidence: null,
  },
};
const execution = {
  execution_revision: 0,
  session_id: null,
  result: null,
  failed_operation_count: null,
  disk_capacity_failure_count: null,
  gap: null,
  trash_location: null,
  started_at: null,
  ended_at: null,
  refusal: null,
};
const baseWindow = (size) => ({
  disposition: "current",
  view_revision: 0,
  highlight_revision: 0,
  offset: 0,
  total: 1,
  execution,
  rows: [{ ...baseRow, size }],
});

let responseResult = baseWindow(null);
const requests = [];
window.pywebview.api = {
  async dispatch(raw) {
    const request = JSON.parse(raw);
    requests.push(request);
    return {
      transport_version: 1,
      response_token: null,
      response: {
        schema_version: 1,
        request_id: request.request_id,
        ok: true,
        result: responseResult,
      },
    };
  },
};
dispatch("pywebviewready");
bridge.markBridgeOperational();

const read = async (size) => {
  responseResult = baseWindow(size);
  return bridge.getPlanWindow(taskId, 0, 0, 1);
};

const acceptedNull = await read(null);
if (acceptedNull.rows[0].size !== null || acceptedNull.rows[0].notice !== "Partial size: overflow") {
  throw new Error("null size with overflow note was not accepted");
}
const maximum = "9223372036854775807";
const acceptedMaximum = await read(maximum);
if (acceptedMaximum.rows[0].size !== maximum) throw new Error("maximum signed 64-bit size was not preserved");

const overflow = await read("9223372036854775808").then(
  () => null,
  (error) => error,
);
if (overflow === null) throw new Error("signed 64-bit overflow was accepted");
const terminalResult = {
  headline: "success", filesystem: "completed", integrity: "not-run",
  recording: "ok", audit: "ok", disposition: "ran", canceled: false,
  phases: [], bytes_done: "0", bytes_total: "0", error: null,
  recording_degraded_items: 0, recording_issues: [], omitted_detail_count: 0,
  presentation_omitted_detail_count: 0, review_refusal: null,
};
const terminalExecution = {
  ...execution, session_id: "1".repeat(32), result: terminalResult,
  failed_operation_count: 0, disk_capacity_failure_count: 0,
  trash_location: "D:\\.synctrash",
  started_at: "2026-08-12T10:00:00+00:00",
  ended_at: "2026-08-12T10:00:03+00:00",
};
responseResult = { ...baseWindow(null), execution: terminalExecution };
const acceptedTerminal = await bridge.getPlanWindow(taskId, 0, 0, 1);
if (acceptedTerminal.execution.ended_at !== terminalExecution.ended_at) {
  throw new Error("terminal record time was not preserved");
}
for (const invalid of [
  { ...terminalExecution, ended_at: null },
  { ...terminalExecution, started_at: "2026-08-12T10:00:00+05:30" },
  { ...terminalExecution, started_at: undefined },
  { ...execution, ended_at: terminalExecution.ended_at },
]) {
  responseResult = { ...baseWindow(null), execution: invalid };
  const rejected = await bridge.getPlanWindow(taskId, 0, 0, 1).then(
    () => null,
    (error) => error,
  );
  if (rejected === null) throw new Error("invalid execution timestamp was accepted");
}
if (requests.length !== 13 || requests.some((request) => request.command !== "get_plan_window")) {
  throw new Error(`unexpected bridge command receipt: ${requests.length}`);
}
const refusedExecution = {
  ...terminalExecution,
  result: { ...terminalResult, headline: "failed", filesystem: "refused", disposition: "unrun" },
  refusal: { origin: "preflight", codes: ["insufficient_space", "root_unavailable"] },
};
for (const refusal of [refusedExecution.refusal,
  { origin: "commitment", codes: [] }, { origin: "other", codes: [] }]) {
  responseResult = { ...baseWindow(null), execution: { ...refusedExecution, refusal } };
  const accepted = await bridge.getPlanWindow(taskId, 0, 0, 1);
  if (JSON.stringify(accepted.execution.refusal) !== JSON.stringify(refusal)) {
    throw new Error("bounded refusal disclosure was not preserved");
  }
}
for (const refusal of [null, { origin: "preflight", codes: [] },
  { origin: "preflight", codes: ["unknown"] },
  { origin: "preflight", codes: ["source_drift", "source_drift"] },
  { origin: "commitment", codes: ["source_drift"] },
  { origin: "other", codes: [], detail: "private" }]) {
  responseResult = { ...baseWindow(null), execution: { ...refusedExecution, refusal } };
  const rejected = await bridge.getPlanWindow(taskId, 0, 0, 1).then(() => null, (error) => error);
  if (rejected === null) throw new Error("invalid refusal disclosure was accepted");
}
responseResult = { ...baseWindow(null), execution: {
  ...terminalExecution, refusal: refusedExecution.refusal,
} };
if (await bridge.getPlanWindow(taskId, 0, 0, 1).then(() => null, (error) => error) === null) {
  throw new Error("completed execution accepted a refusal disclosure");
}
const groupRow = { ...baseRow, row_kind: "prior-group", operation_id: null,
  operation_kind: null, execution: null, size: null, is_container: true,
  selection: "disabled", selectable_operation_count: 0, selected_operation_count: 0,
  operation_count: 0, move_peer_id: `node-${"9".repeat(32)}`,
  move_group: { count: 1, destination: "" } };
responseResult = { ...baseWindow(null), rows: [groupRow] };
await bridge.getPlanWindow(taskId, 0, 0, 1);
for (const move_group of [null, { count: 0, destination: "" }, { count: 1, destination: "relative", absolute: "private" }]) {
  responseResult = { ...baseWindow(null), rows: [{ ...groupRow, move_group }] };
  if (await bridge.getPlanWindow(taskId, 0, 0, 1).then(() => null, (error) => error) === null) {
    throw new Error("invalid informational move group was accepted");
  }
}
const revealSummary = {
  disposition: "applied", task_id: taskId, request_id: "6".repeat(32), view_revision: 1,
  selection_revision: 0, selection_state: "reviewing", highlight_revision: 0,
  highlight_anchor_node_id: null, highlight_focus_node_id: null, highlight_focus_visible_index: null,
  highlighted_count: 0, source_path: "C:\\source", target_path: "D:\\target",
  selected_operation_count: 1, selectable_operation_count: 1, operation_count: 1,
  scope_selected_operation_count: 1, scope_selectable_operation_count: 1,
  filter_counts: Object.fromEntries(["all", "copy", "mkdir", "move", "recase", "update", "move_update",
    "trash", "delete", "noop", "blocked", "unsupported", "error", "notice"].map((key) => [key, key === "all" || key === "copy" ? 1 : 0])),
  preflight_ready: true, preflight_refusal_count: 0, warning_count: 0,
  requires_destructive_confirmation: false, destructive_operation_count: 0,
  destructive_operation_counts: { update: 0, move_update: 0, trash: 0, delete: 0 },
  irreversible_operation_count: 0, irreversible_update_count: 0, required_bytes: "0",
  visible_row_count: 600, search_query: "", filters: [], sort_column: "path", sort_direction: "ascending",
  collapsed_count: 0, execution,
};
responseResult = { summary: revealSummary, node_id: groupRow.move_peer_id, index: 400 };
const revealStart = requests.length;
const revealed = await bridge.revealPlanMove(taskId, 0, groupRow.node_id);
if (revealed.index !== 400 || requests.length !== revealStart + 1
    || requests.at(-1).command !== "reveal_plan_move") throw new Error("move reveal did not use one compact command");
for (const value of [{ ...responseResult, index: 600 }, { ...responseResult, node_id: null },
  { ...responseResult, summary: { ...revealSummary, task_id: `task-${"9".repeat(32)}` } }]) {
  responseResult = value;
  if (await bridge.revealPlanMove(taskId, 0, groupRow.node_id).then(() => null, (error) => error) === null) {
    throw new Error("invalid move destination reply was accepted");
  }
}
console.log("ok");
