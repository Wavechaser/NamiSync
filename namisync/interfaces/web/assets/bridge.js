const SCHEMA_VERSION = 1;
const ID_PATTERN = /^[0-9a-f]{32}$/;
const SLOT_PATTERN = /^slot-[0-9a-f]{32}$/;
const START_PLAN_TIMEOUT_MS = 30000;
const ERROR_MESSAGES = Object.freeze({
  invalid_request: "The desktop request is invalid.",
  unsupported_version: "Restart NamiSync to load a compatible desktop page.",
  unknown_command: "This desktop action is not available.",
  invalid_payload: "The desktop action contains invalid data.",
  request_too_large: "The desktop request is too large.",
  slot_unavailable:
    "That folder selection is no longer available. Choose both folders again.",
  picker_unavailable: "The folder picker could not open. Try again.",
  command_conflict:
    "This action no longer matches its first attempt. Start the action again.",
  planning_refused:
    "NamiSync could not start a plan for those folders. Review both folders and try again.",
  bridge_unavailable:
    "NamiSync is closing or this desktop page is no longer trusted.",
  internal_error: "NamiSync could not complete the desktop action.",
});
let readiness;
let resolveReadiness;
let bridgeGeneration = 0;

window.addEventListener("pywebviewready", () => {
  bridgeGeneration += 1;
  const resolve = resolveReadiness;
  readiness = undefined;
  resolveReadiness = undefined;
  resolve?.();
});

export class BridgeCommandError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "BridgeCommandError";
    this.code = code;
  }
}

export class BridgeTransportError extends Error {
  constructor(message = "The desktop response could not be confirmed.") {
    super(message);
    this.name = "BridgeTransportError";
  }
}

export class StartPlanUncertainError extends BridgeTransportError {
  constructor(retry) {
    super("The plan-start response could not be confirmed.");
    this.name = "StartPlanUncertainError";
    this.retry = retry;
  }
}

function bridgeApi() {
  return window.pywebview?.api;
}

export function whenBridgeReady() {
  if (typeof bridgeApi()?.dispatch === "function") {
    return Promise.resolve();
  }
  if (!readiness) {
    readiness = new Promise((resolve) => {
      resolveReadiness = resolve;
    });
  }
  return readiness;
}

export async function pickFolder(purpose) {
  if (purpose !== "source" && purpose !== "target") {
    throw new TypeError("purpose must be source or target");
  }
  return dispatchAttempt(
    "pick_folder",
    Object.freeze({ purpose }),
    validatePickFolderResult,
    null,
  );
}

export async function startPlan(sourceId, targetId, deletionPolicy = null) {
  if (
    typeof sourceId !== "string" ||
    typeof targetId !== "string" ||
    !SLOT_PATTERN.test(sourceId) ||
    !SLOT_PATTERN.test(targetId)
  ) {
    throw new TypeError("startPlan requires source and target slot ids");
  }
  if (
    deletionPolicy !== null &&
    deletionPolicy !== "trash" &&
    deletionPolicy !== "additive"
  ) {
    throw new TypeError("deletionPolicy must be null, trash, or additive");
  }
  const payload = Object.freeze({
    command_id: mintId(),
    source_id: sourceId,
    target_id: targetId,
    deletion_policy: deletionPolicy,
  });
  let automaticReplayUsed = false;
  const submit = async () => {
    try {
      return await startPlanAttempt(payload);
    } catch (error) {
      if (!isUncertainStartPlanFailure(error)) {
        throw error;
      }
      if (!automaticReplayUsed) {
        automaticReplayUsed = true;
        try {
          return await startPlanAttempt(payload);
        } catch (replayError) {
          if (!isUncertainStartPlanFailure(replayError)) {
            throw replayError;
          }
        }
      }
      throw new StartPlanUncertainError(submit);
    }
  };
  return submit();
}

function startPlanAttempt(payload) {
  return dispatchAttempt(
    "start_plan",
    payload,
    validateStartPlanResult,
    START_PLAN_TIMEOUT_MS,
  );
}

async function dispatchAttempt(command, payload, validateResult, timeoutMs) {
  const requestId = mintId();
  const request = JSON.stringify({
    schema_version: SCHEMA_VERSION,
    request_id: requestId,
    command,
    payload,
  });
  await whenBridgeReady();
  const generation = bridgeGeneration;
  let onReincarnation;
  const reincarnated = new Promise((resolve, reject) => {
    void resolve;
    onReincarnation = () => reject(new BridgeTransportError());
    window.addEventListener("pywebviewready", onReincarnation, { once: true });
  });
  const api = bridgeApi();
  if (
    generation !== bridgeGeneration ||
    typeof api?.dispatch !== "function"
  ) {
    window.removeEventListener("pywebviewready", onReincarnation);
    throw new BridgeTransportError();
  }

  let response;
  try {
    response = await withDeadline(
      Promise.race([api.dispatch(request), reincarnated]),
      timeoutMs,
    );
  } catch (error) {
    if (error instanceof BridgeTransportError) {
      throw error;
    }
    throw new BridgeTransportError();
  } finally {
    window.removeEventListener("pywebviewready", onReincarnation);
  }
  if (generation !== bridgeGeneration) {
    throw new BridgeTransportError();
  }
  return validateResponse(response, requestId, validateResult);
}

async function withDeadline(value, timeoutMs) {
  if (timeoutMs === null) {
    return value;
  }
  let timer;
  try {
    return await Promise.race([
      value,
      new Promise((resolve, reject) => {
        void resolve;
        timer = setTimeout(() => reject(new BridgeTransportError()), timeoutMs);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

function validateResponse(response, requestId, validateResult) {
  if (
    !isExactObject(response, ["schema_version", "request_id", "ok", "result"]) &&
    !isExactObject(response, ["schema_version", "request_id", "ok", "error"])
  ) {
    throw new BridgeTransportError();
  }
  if (
    response.schema_version !== SCHEMA_VERSION ||
    response.request_id !== requestId ||
    typeof response.ok !== "boolean"
  ) {
    throw new BridgeTransportError();
  }
  if (response.ok) {
    if (!("result" in response) || !validateResult(response.result)) {
      throw new BridgeTransportError();
    }
    return response.result;
  }
  if (!("error" in response) || !isExactObject(response.error, ["code", "message"])) {
    throw new BridgeTransportError();
  }
  const expectedMessage = ERROR_MESSAGES[response.error.code];
  if (expectedMessage === undefined || response.error.message !== expectedMessage) {
    throw new BridgeTransportError();
  }
  throw new BridgeCommandError(response.error.code, expectedMessage);
}

function validatePickFolderResult(value) {
  return (
    value === null ||
    (isExactObject(value, ["id", "display"]) &&
      typeof value.id === "string" &&
      SLOT_PATTERN.test(value.id) &&
      isValidUnicode(value.display))
  );
}

function validateStartPlanResult(value) {
  return (
    isExactObject(value, ["request_id", "session_id"]) &&
    typeof value.request_id === "string" &&
    typeof value.session_id === "string" &&
    ID_PATTERN.test(value.request_id) &&
    ID_PATTERN.test(value.session_id)
  );
}

function isExactObject(value, keys) {
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    Object.getPrototypeOf(value) !== Object.prototype
  ) {
    return false;
  }
  const actual = Object.keys(value);
  return actual.length === keys.length && keys.every((key) => actual.includes(key));
}

function isValidUnicode(value) {
  if (typeof value !== "string") {
    return false;
  }
  for (let index = 0; index < value.length; index += 1) {
    const unit = value.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (next < 0xdc00 || next > 0xdfff) {
        return false;
      }
      index += 1;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      return false;
    }
  }
  return true;
}

function isUncertainStartPlanFailure(error) {
  return (
    error instanceof BridgeTransportError ||
    (error instanceof BridgeCommandError && error.code === "internal_error")
  );
}

function mintId() {
  const value = globalThis.crypto?.randomUUID?.().replaceAll("-", "").toLowerCase();
  if (!ID_PATTERN.test(value)) {
    throw new BridgeTransportError("The desktop request id could not be created.");
  }
  return value;
}
