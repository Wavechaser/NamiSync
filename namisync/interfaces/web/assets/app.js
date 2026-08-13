import { whenBridgeReady } from "./bridge.js";
import { installAppearanceReceiver } from "./appearance.js";
import { createWorkPanel } from "./panels.js";
import { createTaskRail } from "./rail.js";
import { renderText } from "./render.js";

const app = document.querySelector("#app");
const status = document.querySelector("#host-status");
if (!(app instanceof HTMLElement) || !(status instanceof HTMLElement)) {
  throw new TypeError("NamiSync shell elements are unavailable");
}

installAppearanceReceiver(window.chrome.webview, document.documentElement);

app.append(createTaskRail(), createWorkPanel());

whenBridgeReady().then(() => {
  if (status.textContent === "Starting...") {
    renderText(status, "Ready");
  }
});
