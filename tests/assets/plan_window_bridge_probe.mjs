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
  notice: "Partial size: overflow",
  selection_exclusion_reason: null,
};
const baseWindow = (size) => ({
  disposition: "current",
  view_revision: 0,
  highlight_revision: 0,
  offset: 0,
  total: 1,
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
if (requests.length !== 4 || requests.some((request) => request.command !== "get_plan_window")) {
  throw new Error("unexpected bridge command receipt");
}
console.log("ok");
