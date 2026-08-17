import {
  acknowledgeShellReady,
  BridgeTransportError,
  dispatchInteractive,
  echoReadiness,
  markBridgeOperational,
  whenBridgeApiReady,
} from "./bridge.js";
import { installReadinessReceiver } from "./readiness.js";
import { installAppearanceReceiver } from "./appearance.js";
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
  const readiness = installReadinessReceiver(window.chrome.webview);
  installAppearanceReceiver(
    window.chrome.webview,
    document.documentElement,
  );
  const readinessBaseline = readiness.revision();
  await whenBridgeApiReady();
  try {
    await acknowledgeShellReady();
  } catch (error) {
    if (!(error instanceof BridgeTransportError)) {
      throw error;
    }
  }
  const challenge = await readiness.whenReceivedAfter(readinessBaseline);
  let readinessAcknowledged = false;
  for (let attempt = 0; attempt < 2 && !readinessAcknowledged; attempt += 1) {
    try {
      readinessAcknowledged = (await echoReadiness(challenge)).acknowledged;
    } catch (error) {
      if (!(error instanceof BridgeTransportError) || attempt > 0) throw error;
    }
  }
  if (!readinessAcknowledged) throw new BridgeTransportError();
  markBridgeOperational();
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
