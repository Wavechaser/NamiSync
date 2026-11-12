import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

globalThis.window = {addEventListener() {}, removeEventListener() {}, pywebview: {api: null}};
const bridge = await import(`data:text/javascript;base64,${Buffer.from(await readFile(process.argv[2], "utf8")).toString("base64")}`);
const taskId = `task-${"1".repeat(32)}`;
const requestId = "2".repeat(32);
const nodeId = `node-${"3".repeat(32)}`;
const requests = [];
const observations = [];
let result;
let lost = true;
let original;
window.pywebview.api = {async dispatch(raw) {
  if (raw.startsWith("ack:")) return true;
  if (raw.startsWith("observe:")) {
    observations.push(raw);
    assert.equal(raw, `observe:${original.request_id}:${original.command}`);
    return {transport_version: 1, state: "ready", generation: 1,
      request_id: original.request_id, response_token: "a".repeat(32), completion_token: null,
      response: {schema_version: 1, request_id: original.request_id, ok: true, result}};
  }
  original = JSON.parse(raw);
  requests.push(original);
  if (lost) { lost = false; throw new Error("original delivery lost after write"); }
  return {transport_version: 1, response_token: null, response: {
    schema_version: 1, request_id: original.request_id, ok: true, result}};
}};
bridge.markBridgeOperational();
const complete = {task_id: taskId, request_id: requestId, action: "acknowledge",
  expected_revision: 7, total: 120000, applied: 119997, noop: 1, stale: 1,
  conflict: 1, unresolved_count: 0, disposition: "completed"};
result = complete;
assert.deepEqual(await bridge.acknowledgeInventory(taskId, requestId, "4".repeat(32), 7, nodeId), complete);
assert.equal(requests.length, 1);
assert.equal(observations.length, 1, "lost delivery observes the original without another effect");
assert.deepEqual(requests[0].payload, {task_id: taskId, request_id: requestId,
  command_id: "4".repeat(32), expected_revision: 7, node_id: nodeId});
result = {...complete, action: "restore", applied: 5, noop: 0, stale: 0, conflict: 0,
  unresolved_count: 119995, disposition: "partial"};
assert.deepEqual(await bridge.restoreInventory(taskId, requestId, "5".repeat(32), 7), result);
assert.equal(requests[1].command, "restore_inventory");
for (const patch of [{total: 119999}, {applied: true}, {unresolved_count: -1},
  {disposition: "completed"}, {expected_revision: 8}, {request_id: "9".repeat(32)},
  {row_ids: ["1"]}]) {
  result = {...complete, action: "restore", applied: 5, noop: 0, stale: 0, conflict: 0,
    unresolved_count: 119995, disposition: "partial", ...patch};
  let error;
  try { await bridge.restoreInventory(taskId, requestId, "6".repeat(32), 7); }
  catch (caught) { error = caught; }
  assert.equal(error?.code, "invalid_result", "malformed matching result cannot claim an outcome");
}
const before = requests.length;
assert.throws(() => bridge.acknowledgeInventory(taskId, requestId, "foreign", 7));
assert.throws(() => bridge.restoreInventory(taskId, requestId, "7".repeat(32), true));
assert.throws(() => bridge.restoreInventory(taskId, requestId, "7".repeat(32), 7, "warning-" + "8".repeat(32)));
assert.equal(requests.length, before);
console.log("ok");
