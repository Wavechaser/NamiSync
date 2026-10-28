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
for (const counts of [
  {matching_row_count: undefined}, {total_row_count: undefined},
  {matching_row_count: -1}, {total_row_count: -1},
  {matching_row_count: fixture.summary.visible_row_count - 1},
  {total_row_count: fixture.summary.matching_row_count - 1},
]) {
  response = {...fixture.summary, ...counts};
  await assert.rejects(bridge.openInventoryView(task));
}
response = fixture.summary;
for (const recall of [null, {file_count: -1, size: "0", size_overflow: false, size_partial: false},
  {file_count: 1, size: null, size_overflow: false, size_partial: false},
  {file_count: 1, size: "1", size_overflow: false, size_partial: false, extra: true}]) {
  response = {...fixture.summary, recall};
  await assert.rejects(bridge.openInventoryView(task));
}
response = {...fixture.summary, recall: {file_count: 2, size: null, size_overflow: true, size_partial: true}};
assert.deepEqual((await bridge.openInventoryView(task)).recall, response.recall);
const noScan = {...fixture.summary, scan_request_id: null, scan_complete: null,
  scan_scope: null, observed_count: null, missing_count: null, recall: null};
response = noScan;
assert.deepEqual(await bridge.openInventoryView(task), noScan);
for (const patch of [{scan_complete: false}, {scan_scope: {kind: "location", path: null}},
  {observed_count: 0}, {missing_count: 0}, {scan_request_id: "invalid"},
  {scan_request_id: fixture.summary.request_id}]) {
  response = {...noScan, ...patch};
  await assert.rejects(bridge.openInventoryView(task));
}
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
assert.deepEqual(await bridge.setInventorySelection(task, fixture.summary.request_id, 0, null, true), fixture.summary);
assert.deepEqual(requests.at(-1).payload, {task_id: task, request_id: fixture.summary.request_id,
  expected_revision: 0, node_id: null, selected: true});
for (const patch of [{selected_file_count: true}, {selected_file_count: 999},
  {hidden_selected_file_count: 1}, {selection: "all"}]) {
  response = {...fixture.summary, ...patch};
  await assert.rejects(bridge.openInventoryView(task));
}
response = fixture.window;
assert.deepEqual(await bridge.getInventoryWindow(task, 0, 0, 256), fixture.window);
const nominatedNode = fixture.window.rows[0].node_id;
response = {...fixture.window, anchor_node_id:nominatedNode, anchor_visible_index:0};
assert.equal((await bridge.getInventoryWindow(task, 0, 0, 256, nominatedNode)).anchor_visible_index, 0);
assert.equal(requests.at(-1).payload.anchor_node_id, nominatedNode);
for (const patch of [{anchor_node_id:"node-" + "f".repeat(32)}, {anchor_visible_index:true},
  {anchor_visible_index:fixture.window.total}, {anchor_visible_index:null}, {anchor_visible_index:1}]) {
  response = {...fixture.window, anchor_node_id:nominatedNode, anchor_visible_index:0, ...patch};
  await assert.rejects(bridge.getInventoryWindow(task, 0, 0, 256, nominatedNode));
}
response = fixture.window;
await assert.rejects(bridge.getInventoryWindow(task, 0, 0, 256, nominatedNode));
response = {...fixture.window, anchor_node_id:"node-" + "f".repeat(32), anchor_visible_index:null};
assert.equal((await bridge.getInventoryWindow(task, 0, 0, 256, response.anchor_node_id)).anchor_visible_index, null);
await assert.rejects(bridge.getInventoryWindow(task, 0, 0, 256));
assert.throws(() => bridge.getInventoryWindow(task, 0, 0, 256, "foreign"));
response = fixture.zero_scope.summary;
assert.equal((await bridge.openInventoryView(task)).scope_selectable_file_count, 0);
response = fixture.zero_scope.window;
const zeroScopeWindow = await bridge.getInventoryWindow(task, 0, 0, 256);
assert.equal(zeroScopeWindow.rows.length, 1, "an unverified directory remains visible above verified files");
assert.equal(zeroScopeWindow.rows[0].rollup.file_count, 1);
assert.equal(zeroScopeWindow.rows[0].selectable, false, "a visible folder with no matching files has an inert checkbox");
assert.equal(fixture.window.rows.find(row => row.row_id === "1").recorded_checksum, fixture.detail.detail.attestation.content.digest);
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
  ...["f".repeat(31), "f".repeat(33), "F".repeat(32), 1, "z".repeat(32)].map(recorded_checksum => ({rows: [{...fixture.window.rows[0], recorded_checksum}]})),
  {rows: [{...fixture.window.rows[0], has_baseline: false}]},
  {rows: [{...fixture.window.rows[0], recorded_checksum: null}]},
  {rows: [{...fixture.window.rows[0], display: "x".repeat(301)}]},
  {rows: [{...fixture.window.rows[0], display: "\ud800"}]},
  {rows: [{...fixture.window.rows[0], selectable: false, selection: "all"}]},
  {rows: [{...fixture.window.rows[0], selection: "unknown"}]},
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
response = {...fixture.detail, disposition: "unavailable", snapshot: null, detail: null};
assert.equal((await bridge.getInventoryDetail(task, 0, node)).detail, null);
const noticeRow = fixture.window.rows.find(row => row.warning !== null);
for (const warning of [{...noticeRow.warning, path: "repeat"}, {...noticeRow.warning, code: "future"},
  {...noticeRow.warning, detail: "x".repeat(301)}, {...noticeRow.warning, detail: "\ud800"}]) {
  response = {...fixture.window, rows: fixture.window.rows.map(row => row === noticeRow ? {...row, warning} : row)};
  await assert.rejects(bridge.getInventoryWindow(task, 0, 0, 256));
}
const snapshotDetail = {...fixture.detail, detail: null, snapshot: {path: "Folder\\Nested", warning: null}};
response = snapshotDetail;
assert.deepEqual(await bridge.getInventoryDetail(task, 0, node), snapshotDetail);
response = {...snapshotDetail, snapshot: {path: null, warning: {code: "access_denied", detail: "full diagnostic"}}};
assert.deepEqual((await bridge.getInventoryDetail(task, 0, node)).snapshot, response.snapshot);
for (const patch of [{snapshot: null}, {snapshot: {path: null, warning: null}},
  {snapshot: {path: "x".repeat(32768), warning: null}}, {snapshot: {path: "\ud800", warning: null}},
  {snapshot: {path: "", warning: {code: "future", detail: ""}}},
  {snapshot: {path: "", warning: {code: "access_denied", detail: "x".repeat(1025)}}},
  {disposition: "conflict"}, {disposition: "unavailable"}]) {
  response = {...snapshotDetail, ...patch};
  await assert.rejects(bridge.getInventoryDetail(task, 0, node));
}
const before = requests.length;
assert.throws(() => bridge.setInventorySelection(task, fixture.summary.request_id, 0, null, 1));
assert.throws(() => bridge.setInventorySelection(task, "foreign", 0, null, true));
assert.throws(() => bridge.getInventoryWindow(task, 0, 0, 257));
assert.throws(() => bridge.updateInventoryView(task, 0, {...gesture, filters: ["copy"]}));
assert.throws(() => bridge.updateInventoryView(task, 0, {...gesture, sortDirection: "descending"}));
assert.equal(requests.length, before);
assert.ok(requests.every((item) => !Object.hasOwn(item.payload, "command_id")));
const integrity = {request_id: "a".repeat(32), session_id: "b".repeat(32), mode: "verify",
  location_id: fixture.summary.location_id, revision: 2, complete: true, gap: false,
  items: [{row_id: "1", result: "verified", reason: null, recording: "ok", record_disposition: "applied", detail_omitted_count: 0}]};
response = {...fixture.window, integrity};
assert.deepEqual((await bridge.getInventoryWindow(task, 0, 0, 256)).integrity, integrity);
response = {...fixture.detail, integrity};
assert.deepEqual((await bridge.getInventoryDetail(task, 0, node)).integrity, integrity);
for (const patch of [{session_id: "foreign"}, {request_id: null}, {mode: "manual-verify"},
  {revision: true}, {complete: true, gap: true}, {items: [...integrity.items, ...integrity.items]},
  {items: [{...integrity.items[0], row_id: "999999"}]}, {items: [{...integrity.items[0], result: "future"}]}]) {
  response = {...fixture.window, integrity: {...integrity, ...patch}};
  await assert.rejects(bridge.getInventoryWindow(task, 0, 0, 256));
}
response = {...fixture.detail, integrity: {...integrity, location_id: "999999"}};
await assert.rejects(bridge.getInventoryDetail(task, 0, node));
console.log("ok");
