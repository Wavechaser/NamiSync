import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

globalThis.window = {addEventListener() {}, removeEventListener() {}, pywebview: {api: null}};
const fixture = JSON.parse(await readFile(process.argv[3], "utf8"));
const bridge = await import(`data:text/javascript;base64,${Buffer.from(await readFile(process.argv[2], "utf8")).toString("base64")}`);
let response;
const requests = [];
window.pywebview.api = {async dispatch(raw) {
  const request = JSON.parse(raw);
  requests.push(request);
  return {transport_version: 1, response_token: null, response: {
    schema_version: 1, request_id: request.request_id, ok: true, result: response,
  }};
}};
bridge.markBridgeOperational();
const task = fixture.summary.task_id;
response = fixture.summary;
assert.deepEqual(await bridge.openInventoryView(task), fixture.summary);
for (const scan_scope of [
  {kind: "item", path: "one.txt"}, {kind: "folder", path: "folder"},
  {kind: "selection", path: null},
]) {
  response = {...fixture.summary, scan_scope};
  assert.deepEqual((await bridge.openInventoryView(task)).scan_scope, scan_scope);
}
for (const scan_scope of [
  null, {kind: "unknown", path: null}, {kind: "location", path: "folder"},
  {kind: "selection", path: "one.txt"}, {kind: "folder", path: null},
  {kind: "item", path: "x".repeat(32768)}, {kind: "item", path: ""},
  {kind: "folder", path: "folder", extra: true},
]) {
  response = {...fixture.summary, scan_scope};
  await assert.rejects(bridge.openInventoryView(task));
}
response = fixture.summary;
const gesture = {searchQuery: "", filters: [], sortColumn: "path", sortDirection: "ascending", collapseNodeId: null, collapsed: null};
assert.deepEqual(await bridge.updateInventoryView(task, 0, gesture), fixture.summary);
response = fixture.window;
assert.deepEqual(await bridge.getInventoryWindow(task, 0, 0, 256), fixture.window);
response = fixture.detail;
const node = fixture.detail.node_id;
assert.deepEqual(await bridge.getInventoryDetail(task, 0, node), fixture.detail);
assert.equal(fixture.detail.detail.attestation.content.digest.length, 32);
assert.equal(fixture.detail.detail.observed.file_identity.file_index, "1267650600228229401496703205377");
for (const patch of [
  {rows: [...fixture.window.rows, fixture.window.rows[0]]},
  {view_revision: 1},
  {rows: [{...fixture.window.rows[0], size: "9223372036854775808"}]},
  {rows: [{...fixture.window.rows[0], row_id: 1}]},
  {rows: [{...fixture.window.rows[0], node_id: "foreign"}]},
]) {
  response = {...fixture.window, ...patch};
  await assert.rejects(bridge.getInventoryWindow(task, 0, 0, 256));
}
response = {...fixture.summary, task_id: `task-${"f".repeat(32)}`};
await assert.rejects(bridge.openInventoryView(task));
response = {...fixture.detail, node_id: `node-${"f".repeat(32)}`};
await assert.rejects(bridge.getInventoryDetail(task, 0, node));
response = structuredClone(fixture.detail);
response.detail.attestation.content.provenance = "manual-post-copy";
await assert.rejects(bridge.getInventoryDetail(task, 0, node));
response = {...fixture.detail, disposition: "unavailable", detail: null};
assert.equal((await bridge.getInventoryDetail(task, 0, node)).detail, null);
const before = requests.length;
assert.throws(() => bridge.getInventoryWindow(task, 0, 0, 257));
assert.throws(() => bridge.updateInventoryView(task, 0, {...gesture, filters: ["copy"]}));
assert.throws(() => bridge.updateInventoryView(task, 0, {...gesture, sortDirection: "descending"}));
assert.equal(requests.length, before);
assert.ok(requests.every((item) => !Object.hasOwn(item.payload, "command_id")));
console.log("ok");
