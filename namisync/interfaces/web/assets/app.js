import {
  acknowledgeShellReady,
  BridgeTransportError,
  markBridgeOperational,
  whenBridgeApiReady,
} from "./bridge.js";
import { installAppearanceReceiver } from "./appearance.js";
import { createWorkPanel } from "./panels.js";
import { createTaskRail } from "./rail.js";
import { renderText } from "./render.js";

const app = document.querySelector("#app");
const status = document.querySelector("#host-status");
if (!(app instanceof HTMLElement) || !(status instanceof HTMLElement)) {
  throw new TypeError("NamiSync shell elements are unavailable");
}

const appearance = installAppearanceReceiver(
  window.chrome.webview,
  document.documentElement,
);

app.append(createTaskRail(), createWorkPanel());

class StartupSupersededError extends Error {}

let startupEpoch = 0;
let rejectSupersededStartup = null;

async function finishStartup(epoch, appearanceBaseline) {
  const superseded = new Promise((resolve, reject) => {
    void resolve;
    if (epoch !== startupEpoch) {
      reject(new StartupSupersededError());
      return;
    }
    rejectSupersededStartup = reject;
  });
  const awaitCurrent = async (value) => {
    const result = await Promise.race([value, superseded]);
    if (epoch !== startupEpoch) {
      throw new StartupSupersededError();
    }
    return result;
  };
  await awaitCurrent(whenBridgeApiReady());
  try {
    await awaitCurrent(acknowledgeShellReady());
  } catch (error) {
    if (!(error instanceof BridgeTransportError)) {
      throw error;
    }
  }
  await awaitCurrent(appearance.whenAppliedAfter(appearanceBaseline));
  markBridgeOperational();
  if (status.textContent === "Starting...") {
    renderText(status, "Ready");
  }
}

let startupAttempt = null;
let startupRerunRequested = false;

function ensureStartup({ rerun = false } = {}) {
  if (startupAttempt !== null) {
    startupRerunRequested ||= rerun;
    return startupAttempt;
  }
  const attempt = finishStartup(startupEpoch, appearance.revision());
  startupAttempt = attempt;
  void attempt.finally(() => {
    if (startupAttempt === attempt) {
      startupAttempt = null;
      rejectSupersededStartup = null;
      if (startupRerunRequested) {
        startupRerunRequested = false;
        void ensureStartup();
      }
    }
  }).catch(() => {
    // Native startup refusal owns the action-guiding terminal diagnostic.
  });
  return attempt;
}

window.addEventListener("pywebviewready", () => {
  startupEpoch += 1;
  rejectSupersededStartup?.(new StartupSupersededError());
  if (status.textContent === "Ready") {
    renderText(status, "Starting...");
  }
  void ensureStartup({ rerun: true });
});
void ensureStartup();
