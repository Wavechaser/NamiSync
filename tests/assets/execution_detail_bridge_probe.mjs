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
const operationId = "2".repeat(32);
const fullDetail = {
  disposition: "current",
  execution_revision: 7,
  operation_id: operationId,
  operation: {
    item_type: "operation",
    phase: "execute",
    item_id: operationId,
    kind: "copy",
    path: "copy.txt",
    result: "succeeded",
    reason: null,
    detail: { message: "copied </script> \u2028 hostile" },
    recording: "ok",
    recording_reason: null,
    recording_detail: null,
    detail_omitted_count: 0,
  },
  automatic_verification: {
    item_type: "integrity",
    phase: "verify",
    item_id: operationId,
    row_id: null,
    location_id: null,
    kind: "integrity",
    path: "copy.txt",
    result: "verified",
    reason: null,
    detail: null,
    read_strategy: null,
    recording: "ok",
    record_disposition: "noop",
    detail_omitted_count: 0,
  },
  evidence: {
    state: "recorded-copy",
    content: {
      algorithm: "xxh3_128",
      digest: "01".repeat(16),
      size: "4",
      provenance: "copy",
      observed_at: "2026-01-01T00:00:00+00:00",
    },
  },
};
let responseResult = fullDetail;
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

const accepted = await bridge.getExecutionDetail(taskId, operationId, 7);
if (accepted.operation.detail.message !== "copied </script> \u2028 hostile") {
  throw new Error("full execution detail was not accepted");
}
const foreignId = "3".repeat(32);
responseResult = {
  ...fullDetail,
  operation_id: foreignId,
  operation: { ...fullDetail.operation, item_id: foreignId },
  automatic_verification: {
    ...fullDetail.automatic_verification,
    item_id: foreignId,
  },
};
const foreign = await bridge.getExecutionDetail(taskId, operationId, 7).then(
  () => null,
  (error) => error,
);
if (!(foreign instanceof bridge.BridgeTransportError)) {
  throw new Error("foreign operation detail was not rejected");
}
if (requests.length !== 3) {
  throw new Error("foreign operation correlation was not enforced on retry");
}
responseResult = {
  ...fullDetail,
  operation: {
    ...fullDetail.operation,
    result: "failed",
    recording: "degraded",
    recording_reason: "record-write-failed",
  },
};
const contradictory = await bridge.getExecutionDetail(taskId, operationId, 7).then(
  () => null,
  (error) => error,
);
if (!(contradictory instanceof bridge.BridgeTransportError)) {
  throw new Error("contradictory operation recording fact was not rejected");
}
if (requests.length !== 5 || requests.some((request) => (
  request.command !== "get_execution_detail"
  || request.payload.task_id !== taskId
  || request.payload.operation_id !== operationId
  || request.payload.expected_execution_revision !== 7
))) {
  throw new Error("execution detail request correlation changed");
}
console.log("ok");
