import {
  acknowledgeShellReady,
  BridgeTransportError,
  echoReadiness,
  markBridgeOperational,
  whenBridgeApiReady,
} from "./bridge.js";
import { installReadinessReceiver } from "./readiness.js";


let readinessReceiver;


export function installTestBridgeReadiness() {
  if (readinessReceiver === undefined) {
    readinessReceiver = installReadinessReceiver(window.chrome.webview);
  }
  return readinessReceiver;
}


function acceptedRawResponse(response) {
  return response !== null &&
    typeof response === "object" &&
    response.ok === true;
}


export async function bootstrapTestBridge(options = undefined) {
  const readiness = installTestBridgeReadiness();
  const readinessBaseline = readiness.revision();
  const rawDispatch = options?.dispatchCommand;
  if (rawDispatch !== undefined && typeof rawDispatch !== "function") {
    throw new TypeError("dispatchCommand must be a function");
  }
  await whenBridgeApiReady();
  if (rawDispatch === undefined) {
    try {
      await acknowledgeShellReady();
    } catch (error) {
      if (!(error instanceof BridgeTransportError)) {
        throw error;
      }
    }
  } else {
    const response = await rawDispatch("shell_ready", {});
    if (!acceptedRawResponse(response)) {
      throw new Error("Test bridge shell acknowledgement was refused");
    }
  }
  const challenge = await readiness.whenReceivedAfter(readinessBaseline);
  let acknowledged = false;
  for (let attempt = 0; attempt < 2 && !acknowledged; attempt += 1) {
    try {
      if (rawDispatch === undefined) {
        acknowledged = (await echoReadiness(challenge)).acknowledged;
      } else {
        const response = await rawDispatch("readiness_echo", { challenge });
        acknowledged = acceptedRawResponse(response) &&
          response.result?.acknowledged === true;
      }
    } catch (error) {
      if (
        (rawDispatch === undefined && !(error instanceof BridgeTransportError)) ||
        attempt > 0
      ) {
        throw error;
      }
    }
  }
  if (!acknowledged) {
    throw new BridgeTransportError();
  }
  markBridgeOperational();
}
