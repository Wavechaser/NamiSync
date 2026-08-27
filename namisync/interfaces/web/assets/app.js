import {
  acknowledgeShellReady,
  BridgeTransportError,
  echoReadiness,
  markBridgeOperational,
  whenBridgeApiReady,
} from "./bridge.js";
import { installReadinessReceiver } from "./readiness.js";
import { installAppearanceReceiver } from "./appearance.js";
import { installThemeCombobox, installThemeSelector } from "./theme.js";
import { createWorkPanel } from "./panels.js";
import { createTaskRail } from "./rail.js";
import { renderText } from "./render.js";

const app = document.querySelector("#app");
const status = document.querySelector("#host-status");
const themeSelector = document.querySelector("#theme-mode");
if (
  !(app instanceof HTMLElement)
  || !(status instanceof HTMLElement)
  || !(themeSelector instanceof HTMLElement)
) {
  throw new TypeError("NamiSync shell elements are unavailable");
}

const readiness = installReadinessReceiver(window.chrome.webview);
const themeCombobox = installThemeCombobox(themeSelector);
const theme = installThemeSelector(themeCombobox);
let appliedPresentationRevision = null;
installAppearanceReceiver(
  window.chrome.webview,
  document.documentElement,
  (revision) => {
    appliedPresentationRevision = revision;
    void theme.refresh(revision);
  },
);

app.append(createTaskRail(), createWorkPanel());

class StartupSupersededError extends Error {}

let startupEpoch = 0;
let rejectSupersededStartup = null;

async function finishStartup(epoch, readinessBaseline) {
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
  const challenge = await awaitCurrent(
    readiness.whenReceivedAfter(readinessBaseline),
  );
  let acknowledged = false;
  for (let attempt = 0; attempt < 2 && !acknowledged; attempt += 1) {
    try {
      const result = await awaitCurrent(echoReadiness(challenge));
      acknowledged = result.acknowledged;
    } catch (error) {
      if (!(error instanceof BridgeTransportError) || attempt > 0) {
        throw error;
      }
    }
  }
  if (!acknowledged) {
    throw new BridgeTransportError(
      "The desktop readiness echo could not be confirmed.",
    );
  }
  markBridgeOperational();
  void theme.open(appliedPresentationRevision);
  if (status.textContent === "Starting...") {
    renderText(status, "Ready");
  }
}

let startupAttempt = null;
let startupRerunRequested = false;
let startupRerunReadinessBaseline = null;

function ensureStartup({
  rerun = false,
  readinessBaseline = readiness.revision(),
} = {}) {
  if (startupAttempt !== null) {
    if (rerun) {
      startupRerunRequested = true;
      startupRerunReadinessBaseline = readinessBaseline;
    }
    return startupAttempt;
  }
  const attempt = finishStartup(startupEpoch, readinessBaseline);
  startupAttempt = attempt;
  void attempt.finally(() => {
    if (startupAttempt === attempt) {
      startupAttempt = null;
      rejectSupersededStartup = null;
      if (startupRerunRequested) {
        const rerunReadinessBaseline = startupRerunReadinessBaseline;
        startupRerunRequested = false;
        startupRerunReadinessBaseline = null;
        void ensureStartup({
          readinessBaseline: rerunReadinessBaseline,
        });
      }
    }
  }).catch(() => {
    // Native startup refusal owns the action-guiding terminal diagnostic.
  });
  return attempt;
}

window.addEventListener("pywebviewready", () => {
  startupEpoch += 1;
  theme.invalidate();
  rejectSupersededStartup?.(new StartupSupersededError());
  if (status.textContent === "Ready") {
    renderText(status, "Starting...");
  }
  void ensureStartup({ rerun: true });
});
void ensureStartup();
