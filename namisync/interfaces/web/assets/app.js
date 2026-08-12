import { whenBridgeReady } from "./bridge.js";

const status = document.querySelector("#host-status");

whenBridgeReady().then(() => {
  if (status.textContent === "Starting...") {
    status.textContent = "Ready";
  }
});
