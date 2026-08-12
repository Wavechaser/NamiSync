import { whenBridgeReady } from "./bridge.js";

const status = document.querySelector("#host-status");

whenBridgeReady().then(() => {
  status.textContent = "Ready";
});
