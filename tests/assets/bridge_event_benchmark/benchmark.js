import {
  dispatchInteractive,
  startTaskDrain,
} from "./bridge.js";
import {
  bootstrapTestBridge,
  installTestBridgeReadiness,
} from "./bootstrap_test_bridge.js";
import { renderText } from "./render.js";

installTestBridgeReadiness();
await bootstrapTestBridge();


const status = document.querySelector("#status");
const tasks = new Map();
const samples = [];
const gaps = [];
const terminalEventLatencies = [];
const terminalRecordLatencies = [];
const SAMPLE_REPORT_BATCH_SIZE = 100;
const MAX_PENDING_ORDINARY_SAMPLE_REPORTS = 4;
const MAX_PENDING_SAMPLE_REPORTS = 16;
let reporting = Promise.resolve();
let failureReported = false;
let terminalRecords = 0;
let progressMonotonic = true;
let benchmarkStartedAt = null;
let reportQueued = 0;
let reportCompleted = 0;
let activeReport = null;
let pendingSampleReports = 0;
let pendingOrdinarySampleReports = 0;


function isTaskStart(value) {
  return value !== null &&
    typeof value === "object" &&
    Object.keys(value).sort().join(",") ===
      "request_id,session_id,task_id" &&
    /^task-[0-9a-f]{32}$/.test(value.task_id) &&
    /^[0-9a-f]{32}$/.test(value.request_id) &&
    /^[0-9a-f]{32}$/.test(value.session_id);
}


function enqueueReport(kind, value, terminalAdjacent = false) {
  if (kind === "samples") {
    if (
      pendingSampleReports >= MAX_PENDING_SAMPLE_REPORTS ||
      (!terminalAdjacent &&
        pendingOrdinarySampleReports >= MAX_PENDING_ORDINARY_SAMPLE_REPORTS)
    ) {
      const error = new Error("benchmark sample reporting is saturated");
      error.benchmarkStage = "report:samples:capacity";
      throw error;
    }
    pendingSampleReports += 1;
    if (!terminalAdjacent) {
      pendingOrdinarySampleReports += 1;
    }
  }
  reportQueued += 1;
  const reportIndex = reportQueued;
  reporting = reporting.then(async () => {
    activeReport = {
      index: reportIndex,
      kind,
      sample_count: Array.isArray(value) ? value.length : null,
    };
    try {
      const result = await dispatchInteractive(
        "benchmark_report",
        { kind, value },
        (candidate) => candidate !== null && typeof candidate === "object",
      );
      reportCompleted = reportIndex;
      return result;
    } catch (error) {
      error.benchmarkStage = `report:${kind}`;
      throw error;
    } finally {
      activeReport = null;
      if (kind === "samples") {
        pendingSampleReports -= 1;
        if (!terminalAdjacent) {
          pendingOrdinarySampleReports -= 1;
        }
      }
    }
  });
  return reporting;
}


function flushSamples(terminalAdjacent = false) {
  if (samples.length === 0) {
    return;
  }
  enqueueReport(
    "samples",
    samples.splice(0, samples.length),
    terminalAdjacent,
  );
}


function summarizeItems(result) {
  return result.items.map((item) => [item.item_id, item.result]);
}


function summarizeCoreTerminal(result) {
  return {
    status: result.status,
    recording: result.recording,
    audit: result.audit,
    disposition: result.disposition,
    canceled: result.canceled,
    phase_count: result.phases.length,
    bytes_done: result.bytes_done,
    bytes_total: result.bytes_total,
    items: summarizeItems(result),
    error: result.error,
  };
}


function summarizeRecordTerminal(result) {
  return {
    headline: result.headline,
    filesystem: result.filesystem,
    integrity: result.integrity,
    recording: result.recording,
    audit: result.audit,
    disposition: result.disposition,
    canceled: result.canceled,
    phase_count: result.phases.length,
    bytes_done: result.bytes_done,
    bytes_total: result.bytes_total,
    items: summarizeItems(result),
    error: result.error,
  };
}


function summarizeStateChanged(body) {
  return { state: body.state };
}


function recordSample(sampleClass, update) {
  const event = update.update_type === "event" ? update.event : null;
  const record = update.update_type === "record" ? update.record : null;
  const at = event?.at ?? record?.ended_at;
  const observedAt = Date.now();
  const emittedAt = Date.parse(at);
  const latency = observedAt - emittedAt;
  if (!Number.isFinite(latency)) {
    throw new TypeError("benchmark event timestamp is invalid");
  }
  const sample = {
    class: sampleClass,
    event_id: event?.body_type === "ItemOutcome"
      ? event.body.item_id
      : event?.body_type ?? (record === null ? null : "record"),
    event_result: event?.body_type === "ItemOutcome"
      ? event.body.result
      : event?.body_type === "Terminal"
        ? summarizeCoreTerminal(event.body.result)
        : event?.body_type === "StateChanged"
          ? summarizeStateChanged(event.body)
        : record?.result === null || record === null
          ? null
          : summarizeRecordTerminal(record.result),
    latency_ms: latency,
    observed_offset_ms: benchmarkStartedAt === null
      ? null
      : performance.now() - benchmarkStartedAt,
    position: event?.body_type === "Progress"
      ? event.body.bytes_done
      : null,
    record_state: record?.state ?? null,
    session_id: event?.session_id ?? record.session_id,
    sequence: event?.sequence ?? null,
  };
  if (sampleClass === "terminal_event" || sampleClass === "terminal_record") {
    flushSamples(true);
  }
  samples.push(sample);
  if (sampleClass === "terminal_event") {
    terminalEventLatencies.push(sample.latency_ms);
  }
  if (sampleClass === "terminal_record") {
    terminalRecordLatencies.push(sample.latency_ms);
  }
  if (
    samples.length >= SAMPLE_REPORT_BATCH_SIZE ||
    sampleClass === "terminal_event" ||
    sampleClass === "terminal_record"
  ) {
    flushSamples(
      sampleClass === "terminal_event" || sampleClass === "terminal_record",
    );
  }
}


async function finish() {
  flushSamples();
  await reporting;
  await enqueueReport("complete", {
    gap_events: gaps,
    progress_monotonic: progressMonotonic,
    session_ids: [...tasks.values()].map((task) => task.identity.session_id),
    task_count: tasks.size,
    terminal_event_latencies_ms: terminalEventLatencies,
    terminal_record_latencies_ms: terminalRecordLatencies,
    terminal_record_count: terminalRecords,
  });
  renderText(status, "Benchmark complete. The parent harness will close this window.");
  // This final request is a one-way close handshake. Its native admission
  // proves the preceding DOM mutation; the parent intentionally closes before
  // Chromium is guaranteed to receive the response.
  void enqueueReport("presented", null).catch(() => undefined);
}


function acceptUpdate(task, update) {
  if (update.update_type === "record") {
    recordSample("terminal_record", update);
    terminalRecords += 1;
    if (terminalRecords === 4) {
      void finish().catch((error) => fail(error, "finish"));
    }
    return;
  }
  const event = update.event;
  if (event.body_type === "Progress") {
    const completed = event.body.bytes_done;
    if (completed < task.lastProgress) {
      progressMonotonic = false;
    }
    task.lastProgress = completed;
    recordSample("progress", update);
    return;
  }
  if (event.body_type === "ItemOutcome") {
    recordSample("reliable", update);
    return;
  }
  if (event.body_type === "StateChanged") {
    recordSample("reliable", update);
    return;
  }
  if (event.body_type === "Terminal") {
    recordSample("terminal_event", update);
    return;
  }
  if (event.body_type === "Gap") {
    gaps.push({
      session_id: event.session_id,
      sequence: event.sequence,
      first_missed_seq: event.body.first_missed_seq,
    });
  }
}


function fail(error, source = "task") {
  if (failureReported) {
    return;
  }
  failureReported = true;
  const name = typeof error?.name === "string" ? error.name : "Error";
  renderText(status, `Benchmark failed (${name}).`);
  reporting = reporting
    .catch(() => undefined)
    .then(() => dispatchInteractive(
      "benchmark_report",
      {
        kind: "complete",
        value: {
          failure: name,
          failure_source: typeof error?.benchmarkStage === "string"
            ? error.benchmarkStage
            : source,
          active_report: activeReport,
          report_queued: reportQueued,
          report_completed: reportCompleted,
          buffered_sample_count: samples.length,
          gap_events: gaps,
          progress_monotonic: progressMonotonic,
          session_ids: [...tasks.values()]
            .map((task) => task.identity.session_id),
          task_count: tasks.size,
          terminal_event_latencies_ms: terminalEventLatencies,
          terminal_record_latencies_ms: terminalRecordLatencies,
          terminal_record_count: terminalRecords,
        },
      },
      (result) => result?.accepted === true,
    ));
  void reporting.catch(() => {});
}


async function start() {
  renderText(status, "Waiting for the benchmark start handshake…");
  await dispatchInteractive(
    "benchmark_report",
    { kind: "ready", value: null },
    (value) => value?.accepted === true,
  );
  renderText(status, "Running the 60-second event fixture…");
  benchmarkStartedAt = performance.now();
  const starts = await dispatchInteractive(
    "benchmark_start",
    {},
    (value) => Array.isArray(value) && value.length === 4 && value.every(isTaskStart),
  );
  for (const identity of starts) {
    const task = { identity, lastProgress: 0 };
    tasks.set(identity.task_id, task);
    startTaskDrain(
      identity.task_id,
      identity.session_id,
      (update) => acceptUpdate(task, update),
      (error) => fail(error, `task:${identity.task_id}`),
    );
  }
}


void start().catch((error) => fail(error, "start"));
