const nativeAddEventListener = window.addEventListener.bind(window);
const nativeRemoveEventListener = window.removeEventListener.bind(window);
const readyListeners = new Set();
window.addEventListener = (name, handler, options) => {
  if (name === "pywebviewready") {
    readyListeners.add(handler);
  }
  return nativeAddEventListener(name, handler, options);
};
window.removeEventListener = (name, handler, options) => {
  if (name === "pywebviewready") {
    readyListeners.delete(handler);
  }
  return nativeRemoveEventListener(name, handler, options);
};

const nativeSetTimeout = globalThis.setTimeout.bind(globalThis);
const nativeClearTimeout = globalThis.clearTimeout.bind(globalThis);
const activeTimers = new Set();
globalThis.setTimeout = (callback, milliseconds, ...args) => {
  let token;
  token = nativeSetTimeout(() => {
    activeTimers.delete(token);
    callback(...args);
  }, milliseconds);
  activeTimers.add(token);
  return token;
};
globalThis.clearTimeout = (token) => {
  activeTimers.delete(token);
  return nativeClearTimeout(token);
};

const [bridge, bootstrapModule, renderModule] = await Promise.all([
  import("./bridge.js"),
  import("./bootstrap_test_bridge.js"),
  import("./render.js"),
]);
const {
  closeTask,
  dispatchInteractive,
  markBridgeOperational,
  pickFolder,
  startPlan,
  startTaskDrain,
} = bridge;
const { bootstrapTestBridge, installTestBridgeReadiness } = bootstrapModule;
installTestBridgeReadiness();
await bootstrapTestBridge();
const { renderText } = renderModule;

const REPORT_COMMAND = "test_report";
let browserStage = "bootstrap";
const status = document.querySelector("#status");
const hostileTarget = document.querySelector("#hostile-text");
const nestedTarget = document.querySelector("#nested-text");

function exactObject(value, keys) {
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    Object.getPrototypeOf(value) !== Object.prototype
  ) {
    return false;
  }
  const actual = Object.keys(value);
  return actual.length === keys.length && keys.every((key) => actual.includes(key));
}

function validBootstrap(value) {
  return exactObject(value, ["corpus"]) && typeof value.corpus === "string";
}

function validAccepted(value) {
  return exactObject(value, ["accepted"]) && value.accepted === true;
}

function validDrain(value, plan, drainId) {
  return (
    exactObject(value, ["task_id", "session_id", "drain_id", "updates"]) &&
    value.task_id === plan.task_id &&
    value.session_id === plan.session_id &&
    value.drain_id === drainId &&
    Array.isArray(value.updates)
  );
}

function validDrainProbe(value) {
  return (
    exactObject(value, ["drain_entered", "drain_exited", "drain_settled"]) &&
    typeof value.drain_entered === "boolean" &&
    typeof value.drain_exited === "boolean" &&
    typeof value.drain_settled === "boolean"
  );
}

function validGateStatus(value) {
  return (
    exactObject(value, [
      "release_calls",
      "close_calls",
      "interactive_failures",
      "malformed_attempts",
    ]) &&
    Object.values(value).every(Number.isSafeInteger)
  );
}

function requireGate(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function waitFor(predicate, message, timeoutMs = 12000) {
  const deadline = performance.now() + timeoutMs;
  while (!predicate()) {
    if (performance.now() >= deadline) {
      throw new Error(message);
    }
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
}

function injectRendererOnlyReturnTableLoss() {
  window.dispatchEvent(new Event("pywebviewready"));
  markBridgeOperational();
}

async function probeRawPrivateReceiverNames() {
  const attempts = [
    ["_document._record", ["https://attacker.invalid/"]],
    ["_commands.clear", []],
    ["dispatch.__self__._document._record", ["https://attacker.invalid/"]],
  ];
  for (let index = 0; index < attempts.length; index += 1) {
    const [name, params] = attempts[index];
    window.chrome.webview.postMessage([
      name,
      JSON.stringify(params),
      `raw-private-${index}`,
    ]);
  }
  await new Promise((resolve) => setTimeout(resolve, 200));
}

async function report(payload, validator) {
  return dispatchInteractive(REPORT_COMMAND, Object.freeze(payload), validator);
}

async function proveConcurrentDrain(sourceId, targetId) {
  const plan = await startPlan(sourceId, targetId, "additive");
  const drainId = globalThis.crypto.randomUUID().replaceAll("-", "").toLowerCase();
  let drainSettled = false;
  void dispatchInteractive(
    "next_events",
    Object.freeze({
      task_id: plan.task_id,
      session_id: plan.session_id,
      drain_id: drainId,
      replay_from: null,
    }),
    (value) => validDrain(value, plan, drainId),
  ).then(
    () => {
      drainSettled = true;
    },
    () => {
      drainSettled = true;
    },
  );
  for (let attempt = 0; attempt < 50; attempt += 1) {
    const probe = await report(
      { phase: "drain_probe", drain_settled: drainSettled },
      validDrainProbe,
    );
    if (probe.drain_entered || probe.drain_exited || drainSettled) {
      if (probe.drain_exited || probe.drain_settled || !probe.drain_entered) {
        throw new Error("next_events was not concurrent with the report RPC");
      }
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  throw new Error("next_events did not enter its long poll");
}

async function proveBrowserGate(sourceId, targetId) {
  browserStage = "interactive-single-attempt";
  let interactiveRefusal;
  try {
    await report({ phase: "interactive_failure" }, () => true);
  } catch (error) {
    interactiveRefusal = { name: error.name, code: error.code };
  }
  requireGate(
    interactiveRefusal?.name === "BridgeCommandError" &&
      interactiveRefusal.code === "internal_error",
    "interactive command did not fail exactly once",
  );

  await report({ phase: "arm_start_uncertainty" }, validAccepted);
  browserStage = "start-plan-uncertainty";
  setTimeout(injectRendererOnlyReturnTableLoss, 50);
  const mainPlan = await startPlan(sourceId, targetId, "trash");

  const mainAccepted = [];
  const mainRefusals = [];
  const callbackReleaseOrder = [];
  const nestedItems = [];
  let nestedRecord;
  const stopMain = startTaskDrain(
    mainPlan.task_id,
    mainPlan.session_id,
    (update) => {
      mainAccepted.push(update);
      if (
        update.update_type === "event" &&
        ["ItemOutcome", "IntegrityOutcome"].includes(update.event.body_type)
      ) {
        nestedItems.push(update.event.body);
        if (update.event.body_type === "ItemOutcome") {
          renderText(nestedTarget, update.event.body.path);
        }
      }
      if (update.update_type === "record") {
        callbackReleaseOrder.push("record");
        nestedRecord = update.record;
      }
    },
    (error) => mainRefusals.push(error),
  );
  browserStage = "stale-drain-reincarnation";
  setTimeout(injectRendererOnlyReturnTableLoss, 50);
  await waitFor(
    () => mainAccepted.length >= 2,
    "reincarnated drain did not recover its retained prefix",
  );
  requireGate(
    mainAccepted[0].event.sequence === 1 &&
      mainAccepted[1].event.sequence === 3,
    "numeric hole was not accepted exactly",
  );
  await report({ phase: "emit_gap" }, validAccepted);
  browserStage = "explicit-gap-recovery";
  await waitFor(
    () => nestedRecord !== undefined,
    "explicit Gap recovery did not reach terminal truth",
  );
  requireGate(mainRefusals.length === 0, "main drain was unexpectedly refused");

  let lifecycle = await report({ phase: "status" }, validGateStatus);
  browserStage = "terminal-session-release";
  for (let attempt = 0; lifecycle.release_calls < 1 && attempt < 100; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 10));
    lifecycle = await report({ phase: "status" }, validGateStatus);
  }
  requireGate(lifecycle.release_calls >= 1, "terminal session was not released");
  requireGate(lifecycle.close_calls === 0, "automatic release closed the task");
  callbackReleaseOrder.push("release");
  const automaticCloseCalls = lifecycle.close_calls;
  await closeTask(mainPlan.task_id, mainPlan.session_id);

  let replacementRegistration = false;
  const stopReplacement = startTaskDrain(
    mainPlan.task_id,
    mainPlan.session_id,
    () => {},
    () => {},
  );
  replacementRegistration = true;
  stopReplacement();

  const busyAccepted = [];
  const busyRefusals = [];
  const busyPlan = await startPlan(sourceId, targetId, "trash");
  browserStage = "finite-busy-recovery";
  const stopBusy = startTaskDrain(
    busyPlan.task_id,
    busyPlan.session_id,
    (update) => busyAccepted.push(update),
    (error) => busyRefusals.push({ name: error.name, code: error.code ?? null }),
  );
  await waitFor(
    () => busyAccepted.some((update) => update.update_type === "record"),
    "finite drain/bridge busy recovery did not converge",
  );
  requireGate(busyRefusals.length === 0, "busy recovery became terminal");
  lifecycle = await report({ phase: "status" }, validGateStatus);
  for (let attempt = 0; lifecycle.release_calls < 2 && attempt < 100; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 10));
    lifecycle = await report({ phase: "status" }, validGateStatus);
  }
  requireGate(lifecycle.release_calls >= 2, "busy task session was not released");
  await closeTask(busyPlan.task_id, busyPlan.session_id);

  const malformedAccepted = [];
  const malformedRefusals = [];
  const malformedPlan = await startPlan(sourceId, targetId, "trash");
  browserStage = "finite-malformed-recovery";
  const stopMalformed = startTaskDrain(
    malformedPlan.task_id,
    malformedPlan.session_id,
    (update) => malformedAccepted.push(update),
    (error) => malformedRefusals.push(error),
  );
  await waitFor(
    () => malformedRefusals.length === 1,
    "malformed response budget did not terminate",
  );
  requireGate(
    malformedAccepted.length === 0 &&
      malformedRefusals[0].name === "BridgeTransportError",
    "malformed response escaped its fixed refusal",
  );
  const malformedRefusal = { name: malformedRefusals[0].name };
  const stopMalformedReplacement = startTaskDrain(
    malformedPlan.task_id,
    malformedPlan.session_id,
    () => {},
    () => {},
  );
  stopMalformedReplacement();

  stopMain();
  stopBusy();
  stopMalformed();
  browserStage = "task-listener-timer-cleanup";
  await waitFor(
    () => readyListeners.size === 1 && activeTimers.size === 0,
    "bridge tasks left listeners or timers behind",
  );

  const acceptedTypes = mainAccepted.map((update) =>
    update.update_type === "event" ? update.event.body_type : "record");
  const acceptedSequences = mainAccepted
    .filter((update) => update.update_type === "event")
    .map((update) => update.event.sequence);
  return {
    accepted_types: acceptedTypes,
    accepted_sequences: acceptedSequences,
    callback_release_order: callbackReleaseOrder,
    automatic_close_calls: automaticCloseCalls,
    busy_refusals: busyRefusals,
    cleanup: {
      active_timers: activeTimers.size,
      ready_listeners: readyListeners.size,
    },
    interactive_refusal: interactiveRefusal,
    malformed_refusal: malformedRefusal,
    nested_dom: {
      observed: nestedTarget.textContent,
      element_children: nestedTarget.children.length,
      image_count: nestedTarget.querySelectorAll("img").length,
      hostile_marker_defined: globalThis.__namiHostileMarker !== undefined,
    },
    nested_items: nestedItems,
    nested_record: nestedRecord,
    replacement_registration: replacementRegistration,
  };
}

async function run() {
  browserStage = "private-receiver-probe";
  await probeRawPrivateReceiverNames();
  browserStage = "hostile-bootstrap";
  const bootstrap = await report({ phase: "hostile" }, validBootstrap);
  const initialScriptCount = document.scripts.length;
  renderText(hostileTarget, bootstrap.corpus);

  const source = await pickFolder("source");
  const target = await pickFolder("target");
  if (source === null || target === null) {
    throw new Error("native folder selection was cancelled");
  }
  const plan = await startPlan(source.id, target.id, null);
  browserStage = "browser-gate";
  const browserGate = await proveBrowserGate(source.id, target.id);
  await proveConcurrentDrain(source.id, target.id);
  browserStage = "final-report";
  await report(
    {
      phase: "complete",
      observed: hostileTarget.textContent,
      source_id: source.id,
      target_id: target.id,
      source_keys: Object.keys(source).sort(),
      target_keys: Object.keys(target).sort(),
      source_display: source.display,
      target_display: target.display,
      plan,
      browser_gate: browserGate,
      dom: {
        element_children: hostileTarget.children.length,
        script_count_before: initialScriptCount,
        script_count_after: document.scripts.length,
        image_count: hostileTarget.querySelectorAll("img").length,
        hostile_marker_defined: globalThis.__namiHostileMarker !== undefined,
      },
    },
    validAccepted,
  );
  renderText(status, "Transport gate complete");
}

run().catch(async (error) => {
  try {
    await report(
      {
        phase: "browser_failure",
        stage: browserStage,
        type: typeof error?.name === "string" ? error.name : "Error",
      },
      validAccepted,
    );
  } catch (_reportError) {
    // The native hard deadline remains the final containment boundary.
  }
  renderText(status, "Transport gate failed");
});
