import { whenBridgeReady } from "./bridge.js";
import { renderText } from "./render.js";

const status = document.querySelector("#host-status");

whenBridgeReady().then(() => {
  if (status.textContent === "Starting...") {
    renderText(status, "Ready");
  }
});
