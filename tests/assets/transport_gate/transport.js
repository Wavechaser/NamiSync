import {
  dispatchInteractive,
  pickFolder,
  startPlan,
} from "./bridge.js";
import { renderText } from "./render.js";

const REPORT_COMMAND = "test_report";
const status = document.querySelector("#status");
const hostileTarget = document.querySelector("#hostile-text");

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

async function run() {
  await probeRawPrivateReceiverNames();
  const bootstrap = await report({ phase: "hostile" }, validBootstrap);
  const initialScriptCount = document.scripts.length;
  renderText(hostileTarget, bootstrap.corpus);

  const source = await pickFolder("source");
  const target = await pickFolder("target");
  if (source === null || target === null) {
    throw new Error("native folder selection was cancelled");
  }
  const plan = await startPlan(source.id, target.id, null);
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
  await proveConcurrentDrain(source.id, target.id);
  renderText(status, "Transport gate complete");
}

run().catch(() => {
  renderText(status, "Transport gate failed");
});
