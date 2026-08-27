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
    stage: 0,
    running: false,
    lostSettled: false,
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

  async function onFirstReady() {
    state.stage = 1;
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

    dispatch("delayed_return")
      .then(
        () => { state.lostSettled = true; },
        () => { state.lostSettled = true; }
      );
    await dispatch("wait_delayed_started");
    window.location.assign(NAVIGATION_TARGET);
  }

  async function onNavigationReinjection() {
    state.stage = 2;
    state.observations.delayedTransport = (
      await dispatch("wait_delayed_transport")
    ).result;
    await delay(0);
    state.observations.afterNavigation = (
      await dispatch("after_navigation", { lost_settled: state.lostSettled })
    ).result;
    state.observations.offOriginRefusal = (
      await dispatch("off_origin_refusal")
    ).result;

    state.stage = 3;
    window.setTimeout(() => {
      const popup = window.open(POPUP_TARGET);
      state.observations.popupReturn = popup === null ? "null" : typeof popup;
    }, 100);
  }

  async function onPopupReinjection() {
    state.stage = 4;
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
      lost_settled: state.lostSettled,
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
      if (state.stage === 0) {
        await onFirstReady();
      } else if (state.stage === 1) {
        await onNavigationReinjection();
      } else if (state.stage === 3) {
        await onPopupReinjection();
      }
    } catch (error) {
      document.getElementById("status").textContent =
        "Native host gates failed: " + String(error);
    } finally {
      state.running = false;
    }
  }

  window.addEventListener("pywebviewready", onReady);
})();
