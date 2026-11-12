import {
  dispatchInteractive,
} from "./bridge.js";
import {
  bootstrapTestBridge,
  installTestBridgeReadiness,
} from "./bootstrap_test_bridge.js";
import { renderText } from "./render.js";

const REPORT_COMMAND = "test_report";
const status = document.querySelector("#status");

function validTarget(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.getPrototypeOf(value) === Object.prototype &&
    Object.keys(value).length === 1 &&
    typeof value.url === "string" &&
    value.url.startsWith("http://127.0.0.1:")
  );
}

async function run() {
  installTestBridgeReadiness();
  await bootstrapTestBridge();
  const target = await dispatchInteractive(
    REPORT_COMMAND,
    Object.freeze({ phase: "off_origin_target" }),
    validTarget,
  );
  window.location.assign(target.url);
}

run().catch(() => {
  renderText(status, "Off-origin setup failed");
});
