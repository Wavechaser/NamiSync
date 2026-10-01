import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

globalThis.window = {addEventListener() {}, removeEventListener() {}, pywebview: {api: null}};
const bridge = await import(`data:text/javascript;base64,${Buffer.from(await readFile(process.argv[2], "utf8")).toString("base64")}`);
const taskId = `task-${"1".repeat(32)}`;
const priorRequest = "2".repeat(32);
const commandId = "3".repeat(32);
const result = {task_id: taskId, request_id: "4".repeat(32), session_id: "5".repeat(32)};
const requests = [];
const observations = [];
let original;
let mode = "lost";
window.pywebview.api = {async dispatch(raw) {
  if (raw.startsWith("ack:")) return true;
  if (raw.startsWith("observe:")) {
    observations.push(raw);
    assert.equal(raw, `observe:${original.request_id}:refresh_inventory`);
    return {transport_version: 1, state: "ready", generation: 1,
      request_id: original.request_id, response_token: "a".repeat(32), completion_token: null,
      response: {schema_version: 1, request_id: original.request_id, ok: true, result}};
  }
  original = JSON.parse(raw);
  requests.push(original);
  if (mode === "lost") throw new Error("post-effect direct delivery lost");
  if (mode === "capacity") return {transport_version: 1, response_token: null,
    response: {schema_version: 1, request_id: original.request_id, ok: false,
      error: {code: "inventory_capacity", message: "Inventory command capacity is full. Close a task before refreshing."}}};
  return {transport_version: 1, response_token: null, response: {
    schema_version: 1, request_id: original.request_id, ok: true,
    result: {...result, request_id: priorRequest},
  }};
}};
bridge.markBridgeOperational();
assert.deepEqual(await bridge.refreshInventory(taskId, priorRequest, commandId, 7), result);
assert.equal(requests.length, 1, "recovery observes the original without another scan submission");
assert.equal(observations.length, 1);
assert.equal(requests[0].command, "refresh_inventory");
assert.deepEqual(requests[0].payload, {task_id: taskId, request_id: priorRequest,
  command_id: commandId, expected_revision: 7, node_id: null});
for (const args of [
  [taskId, "foreign", commandId, 7],
  [taskId, priorRequest, "foreign", 7],
  [taskId, priorRequest, commandId, true],
  [taskId, priorRequest, commandId, 2 ** 53],
  [taskId, priorRequest, commandId, 7, `warning-${"6".repeat(32)}`],
]) assert.throws(() => bridge.refreshInventory(...args));
assert.equal(requests.length, 1, "invalid gestures refuse before transport");
mode = "invalid";
await assert.rejects(bridge.refreshInventory(taskId, priorRequest, "6".repeat(32), 7));
assert.equal(requests.length, 2);
assert.equal(observations.length, 1, "an invalid matching result does not replay a mutation");
mode = "capacity";
await assert.rejects(bridge.refreshInventory(taskId, priorRequest, "7".repeat(32), 7),
  (error) => error.code === "inventory_capacity" && /Close a task/.test(error.message));
assert.equal(requests.length, 3);
console.log("ok");
