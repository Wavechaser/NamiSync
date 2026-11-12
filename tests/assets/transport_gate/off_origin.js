import {
  BridgeCommandError,
  dispatchInteractive,
  markBridgeOperational,
  whenBridgeApiReady,
} from "./bridge.js";
import { renderText } from "./render.js";

const REPORT_COMMAND = "test_report";
const REFUSAL_MESSAGE =
  "NamiSync is closing or this desktop page is no longer trusted.";
const status = document.querySelector("#status");

function validNever() {
  return false;
}

async function run() {
  await whenBridgeApiReady();
  markBridgeOperational();
  try {
    await dispatchInteractive(
      REPORT_COMMAND,
      Object.freeze({ phase: "off_origin_attempt" }),
      validNever,
    );
  } catch (error) {
    if (
      error instanceof BridgeCommandError &&
      error.code === "bridge_unavailable" &&
      error.message === REFUSAL_MESSAGE
    ) {
      renderText(status, "Off-origin dispatch refused");
      return;
    }
  }
  renderText(status, "Off-origin dispatch failed");
}

run();
