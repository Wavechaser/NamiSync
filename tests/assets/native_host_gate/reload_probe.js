import {
  bootstrapTestBridge,
  installTestBridgeReadiness,
} from "./bootstrap_test_bridge.js";
import { installAppearanceReceiver } from "./appearance.js";

installTestBridgeReadiness();
installAppearanceReceiver(window.chrome.webview, document.documentElement);

const REQUEST = (requestId, command) => JSON.stringify({
  schema_version: 1,
  request_id: requestId,
  command,
  payload: {},
});

window.addEventListener("pywebviewready", async () => {
  const result = document.querySelector("#probe-result");
  try {
    if (sessionStorage.getItem("ab6-replaced") === "yes") {
      const refused = await window.pywebview.api.dispatch(
        REQUEST("b".repeat(32), "ab6_hold"),
      );
      if (refused.response_token !== null) {
        await window.pywebview.api.dispatch(`ack:${refused.response_token}`);
      }
      result.textContent = refused.response?.error?.code ?? "missing-refusal";
      return;
    }
    await bootstrapTestBridge({ dispatchCommand: async (command, payload) => {
      const response = await window.pywebview.api.dispatch(JSON.stringify({
        schema_version: 1,
        request_id: (command === "shell_ready" ? "1" : "2").repeat(32),
        command,
        payload,
      }));
      if (response.response_token !== null) {
        await window.pywebview.api.dispatch(`ack:${response.response_token}`);
      }
      return response.response;
    }});
    const admitted = await window.pywebview.api.dispatch(
      REQUEST("a".repeat(32), "ab6_hold"),
    );
    if (admitted.completion?.phase !== "completion") {
      throw new Error("async command was not admitted");
    }
    if (admitted.response_token !== null) {
      await window.pywebview.api.dispatch(`ack:${admitted.response_token}`);
    }
    sessionStorage.setItem("ab6-replaced", "yes");
    location.reload();
  } catch (error) {
    result.textContent = `probe-error:${String(error)}`;
  }
});
