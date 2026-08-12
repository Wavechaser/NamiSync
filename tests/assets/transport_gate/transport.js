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

async function report(payload, validator) {
  return dispatchInteractive(REPORT_COMMAND, Object.freeze(payload), validator);
}

async function run() {
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
  renderText(status, "Transport gate complete");
}

run().catch(() => {
  renderText(status, "Transport gate failed");
});
