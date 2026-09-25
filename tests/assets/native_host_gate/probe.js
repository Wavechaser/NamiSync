import {
  bootstrapTestBridge,
  installTestBridgeReadiness,
} from "./bootstrap_test_bridge.js";
import { installAppearanceReceiver } from "./appearance.js";

(function () {
  "use strict";

  const NAVIGATION_TARGET = "https://example.invalid/navigation";
  const FRAME_TARGET = "https://example.invalid/frame";
  const POPUP_TARGET = "https://example.invalid/popup";
  const state = {
    documentToken: "document-" + Math.random().toString(16).slice(2),
    initialUrl: window.location.href,
    readyCount: 0,
    request: 0,
    running: false,
    delayedSettled: false,
    observations: {},
  };
  window.__namiNativeHostGate = state;
  installTestBridgeReadiness();
  const appearance = installAppearanceReceiver(
    window.chrome.webview,
    document.documentElement,
  );
  function delay(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  async function dispatchCommand(command, payload) {
    state.request += 1;
    const nativeResponse = await window.pywebview.api.dispatch(JSON.stringify({
      schema_version: 1,
      request_id: state.request.toString(16).padStart(32, "0"),
      command: command,
      payload: payload,
    }));
    if (
      nativeResponse.response_token !== null &&
      await window.pywebview.api.dispatch(
        `ack:${nativeResponse.response_token}`
      ) !== true
    ) {
      throw new Error("native response acknowledgment failed");
    }
    return nativeResponse.response;
  }

  function dispatch(phase, extra) {
    const payload = Object.assign(
      {
        phase: phase,
        page_url: window.location.href,
        document_token: state.documentToken,
        ready_count: state.readyCount,
      },
      extra || {}
    );
    return dispatchCommand("native_probe", payload);
  }

  async function completeReadinessHandshake() {
    const appearanceBaseline = appearance.revision();
    await bootstrapTestBridge({ dispatchCommand });
    await appearance.whenAppliedAfter(appearanceBaseline);
    const revisions = state.observations.presentationRevisions || [];
    revisions.push(appearance.revision());
    state.observations.presentationRevisions = revisions;
  }

  async function runNativeGate() {
    state.observations.baseline = (await dispatch("baseline")).result;

    window.history.pushState({}, "", "#source-probe");
    await delay(100);
    window.history.replaceState({}, "", state.initialUrl);
    await delay(100);

    const frame = document.createElement("iframe");
    frame.hidden = true;
    frame.src = FRAME_TARGET;
    document.body.appendChild(frame);
    await delay(250);
    state.observations.afterFrame = (await dispatch("after_frame")).result;

    const delayed = dispatch("delayed_return")
      .then(
        (value) => {
          state.delayedSettled = true;
          state.observations.delayedReturn = value.result.token;
        },
        (error) => {
          state.delayedSettled = true;
          state.observations.delayedError = String(error);
        }
      );
    await dispatch("wait_delayed_started");
    window.location.assign(NAVIGATION_TARGET);
    state.observations.delayedTransport = (
      await dispatch("wait_delayed_transport")
    ).result;
    await delayed;
    await delay(0);
    state.observations.afterNavigation = (
      await dispatch("after_navigation", { delayed_settled: state.delayedSettled })
    ).result;
    state.observations.offOriginRefusal = (
      await dispatch("off_origin_refusal")
    ).result;

    const popup = window.open(POPUP_TARGET);
    state.observations.popupReturn = popup === null ? "null" : typeof popup;
    await dispatch("wait_popup_completed");
    state.observations.afterPopup = (
      await dispatch("after_popup", {
        popup_return: state.observations.popupReturn || "not-recorded",
      })
    ).result;
    const finalPayload = {
      initial_url: state.initialUrl,
      final_url: window.location.href,
      document_token: state.documentToken,
      ready_count: state.readyCount,
      delayed_settled: state.delayedSettled,
      observations: state.observations,
    };
    await dispatch("complete", finalPayload);
    document.getElementById("status").textContent = "Native host gates passed";
  }

  async function onReady() {
    state.readyCount += 1;
    if (state.running) {
      return;
    }
    state.running = true;
    try {
      await completeReadinessHandshake();
      await runNativeGate();
    } catch (error) {
      document.getElementById("status").textContent =
        "Native host gates failed: " + String(error);
    } finally {
      state.running = false;
    }
  }

  window.addEventListener("pywebviewready", onReady);
})();
