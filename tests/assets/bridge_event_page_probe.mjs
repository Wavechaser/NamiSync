import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const path = process.argv[2];
let source = readFileSync(path, "utf8").replace(/\r\n/g, "\n");
const imports = source.match(/^import \{[\s\S]*?\} from "\.\/[^\"]+";\r?\n/gm);
assert.equal(imports?.length, 3);
source = source.replace(/^import \{[\s\S]*?\} from "\.\/[^\"]+";\r?\n/gm, "");
source = source.replace(
  "installTestBridgeReadiness();\nawait bootstrapTestBridge();",
  "",
);
source = source.replace(
  'void start().catch((error) => fail(error, "start"));',
  "",
);
source += `\nglobalThis.probe = {
  fixtureBytes, summarizeCoreTerminal, summarizeRecordTerminal,
  acceptUpdate, enqueueReport,
  state: () => ({
    failureReported, pendingSampleReports, pendingOrdinarySampleReports,
    reportQueued, reportCompleted, progressMonotonic, samples: [...samples],
  }),
};`;

const calls = [];
let sampleCalls = 0;
const context = {
  document: { querySelector: () => ({}) },
  performance: { now: () => 10 },
  renderText: () => {},
  dispatchInteractive: async (command, payload) => {
    calls.push({ command, payload });
    if (payload.kind === "samples" && sampleCalls++ === 0) {
      const error = new Error("The desktop action contains invalid data");
      error.name = "BridgeCommandError";
      throw error;
    }
    return { accepted: true };
  },
};
vm.runInNewContext(source, context, { filename: path });
const probe = context.probe;

for (const coordinate of ["1", "10", "1500"]) {
  assert.equal(probe.fixtureBytes(coordinate), Number(coordinate));
}
for (const invalid of ["0", "01", "1501", "1.0", 1, null]) {
  assert.throws(() => probe.fixtureBytes(invalid));
}

const core = {
  status: "completed", recording: "ok", audit: "ok", disposition: "ran",
  canceled: false, phases: [], bytes_done: "1500", bytes_total: "1500",
  error: null,
};
assert.equal(probe.summarizeCoreTerminal(core).bytes_done, 1500);
assert.equal("items" in probe.summarizeCoreTerminal(core), false);
const record = {
  headline: "success", filesystem: "completed", integrity: "not-run",
  ...core,
};
assert.equal(probe.summarizeRecordTerminal(record).bytes_total, 1500);
assert.equal("items" in probe.summarizeRecordTerminal(record), false);

const task = { lastProgress: 0 };
for (const [index, coordinate] of ["9", "10", "99", "100"].entries()) {
  probe.acceptUpdate(task, {
    update_type: "event",
    event: {
      body_type: "Progress", body: { bytes_done: coordinate },
      at: new Date().toISOString(), session_id: "f".repeat(32),
      sequence: index + 1,
    },
  });
}
assert.equal(task.lastProgress, 100);
assert.equal(probe.state().progressMonotonic, true);
assert.deepEqual(Array.from(probe.state().samples, (sample) => sample.position),
  [9, 10, 99, 100]);

const first = probe.enqueueReport("samples", [{}]);
const queued = probe.enqueueReport("samples", [{}]);
await Promise.allSettled([first, queued]);
await Promise.resolve();
const state = probe.state();
assert.equal(state.failureReported, true);
assert.equal(state.pendingSampleReports, 0);
assert.equal(state.pendingOrdinarySampleReports, 0);
assert.equal(state.reportQueued, 2);
assert.equal(state.reportCompleted, 0);
assert.deepEqual(calls.map((call) => call.payload.kind), ["samples", "complete"]);
assert.equal(calls[1].payload.value.failure, "BridgeCommandError");
assert.equal(calls[1].payload.value.failure_source, "report:samples");
assert.equal(calls[1].payload.value.failure_message,
  "The desktop action contains invalid data");
assert.equal(calls[1].payload.value.active_report.index, 1);
assert.equal(calls[1].payload.value.active_report.kind, "samples");
assert.equal(calls[1].payload.value.active_report.sample_count, 1);
const before = probe.state().samples.length;
probe.acceptUpdate(task, {
  update_type: "event",
  event: { body_type: "Progress", body: { bytes_done: "11" } },
});
assert.equal(probe.state().samples.length, before);
console.log(JSON.stringify({ first_failure: calls[1].payload.value.failure_source }));
