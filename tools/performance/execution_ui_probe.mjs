// Injected only by the scoped U installed-headed probe. Keep one scalar result.
const uFeedback = (() => {
  function observeDispatch(command, expectedPayload, acceptedResult) {
    const api = window.pywebview?.api;
    const original = api?.dispatch;
    if (typeof original !== "function") throw new Error("native dispatch observer unavailable");
    let count = 0;
    let finished = false;
    let accepted = false;
    let requestId = null;
    let failure = null;
    api.dispatch = function (wire) {
      let request = null;
      if (typeof wire === "string" && wire.startsWith("{")) {
        try { request = JSON.parse(wire); } catch (_error) { /* Native owns invalid input. */ }
      }
      if (request?.command !== command) return original.call(this, wire);
      count += 1;
      if (count !== 1 || request?.payload?.task_id !== expectedPayload.task_id
          || !expectedPayload.matches(request.payload)) {
        failure = "wrong or repeated action request";
      }
      requestId = typeof request?.request_id === "string"
        ? request.request_id.slice(0, 64) : null;
      let native;
      try {
        native = original.call(this, wire);
      } catch (error) {
        finished = true;
        failure = failure ?? `native dispatch threw ${String(error?.name ?? "Error").slice(0, 80)}`;
        throw error;
      }
      // Observe the original return value; never insert an await into the app's path.
      Promise.resolve(native).then((reply) => {
        try {
          const response = reply?.response;
          accepted = failure === null && reply?.transport_version === 1
            && Object.keys(reply).sort().join(",") === "response,response_token,transport_version"
            && (reply.response_token === null
              || (typeof reply.response_token === "string"
                && /^[0-9a-f]{32}$/.test(reply.response_token)))
            && response?.schema_version === 1
            && Object.keys(response).sort().join(",") === "ok,request_id,result,schema_version"
            && response.request_id === requestId
            && response.ok === true && acceptedResult(response.result, request.payload);
          if (!accepted) failure = failure ?? "typed action reply refused or mismatched";
        } catch (_error) {
          failure = failure ?? "typed action reply could not be inspected";
        }
        finished = true;
      }, (error) => {
        failure = failure ?? `native dispatch rejected ${String(error?.name ?? "Error").slice(0, 80)}`;
        finished = true;
      });
      return native;
    };
    return {
      peek: () => count === 1 && finished && accepted,
      finish: async () => {
        await until(() => finished || count > 1, `${command} typed reply`);
        if (count !== 1 || !accepted) throw new Error(
          `${command} action failed: ${JSON.stringify({ count, finished, requestId, failure })}`,
        );
      },
      dispose: () => { api.dispatch = original; },
      facts: () => ({ count, finished, accepted, requestId, failure }),
    };
  }

  function assertEligible(element, review, initialPending = "") {
    if (element?.isConnected !== true || element.disabled !== false
        || element.hidden === true || element.closest?.("[hidden]") != null
        || review?.isConnected !== true || review.dataset.pending !== initialPending) {
      throw new Error("action control is not eligible and connected");
    }
  }

  function currentReview(row, captured = null) {
    const review = document.querySelector(".nami-plan-review");
    if (review?.isConnected !== true || (captured !== null && review !== captured)) return null;
    const source = review.querySelector(
      ".nami-plan-review__path--source .nami-labeled-path__value",
    )?.textContent;
    const target = review.querySelector(
      ".nami-plan-review__path--target .nami-labeled-path__value",
    )?.textContent;
    return source === row.source_path && target === row.target_path ? review : null;
  }

  const controlStates = {
    pause: ["running", "pausing"],
    resume: ["paused", "pending"],
    cancel: ["running", "canceling"],
  };

  function exactControl(value, row, action) {
    const [before, after] = controlStates[action] ?? [];
    return value?.code === "accepted" && value.accepted === true
      && value.session_id === row.session_id
      && value.before === before && value.after === after;
  }

  function observeControl(row, action) {
    return observeDispatch("control_execution", {
      task_id: row.task_id,
      matches: (payload) => payload.session_id === row.session_id
        && payload.action === action,
    }, (value) => exactControl(value, row, action));
  }

  function observeStartRequest(row) {
    const api = window.pywebview?.api;
    const original = api?.dispatch;
    if (typeof original !== "function") throw new Error("start request observer unavailable");
    const requests = new Map();
    let count = 0;
    let commandId = null;
    api.dispatch = function (wire) {
      let request = null;
      if (typeof wire === "string" && wire.startsWith("{")) {
        try { request = JSON.parse(wire); } catch (_error) { /* Native owns invalid input. */ }
      }
      if (request?.command === "start_execution") {
        count += 1;
        const valid = count <= 2 && /^[0-9a-f]{32}$/.test(request.request_id)
          && request.schema_version === 1
          && Object.keys(request.payload ?? {}).sort().join(",")
            === "command_id,destructive_acknowledged,expected_revision,request_id,task_id"
          && request.payload?.task_id === row.task_id
          && request.payload?.request_id === row.request_id
          && request.payload?.expected_revision === row.selection_revision
          && /^[0-9a-f]{32}$/.test(request.payload?.command_id)
          && (count === 1 || request.payload.command_id === commandId)
          && request.payload?.destructive_acknowledged
            === (row.destructive_operation_count > 0);
        if (count === 1) commandId = request.payload?.command_id ?? null;
        if (count <= 2) requests.set(request.request_id, valid);
      }
      return original.call(this, wire);
    };
    return {
      status: (requestId) => requests.get(requestId) ?? null,
      facts: () => ({count, exact: count > 0 && count <= 2
        && [...requests.values()].every(Boolean)}),
      dispose: () => {api.dispatch = original;},
    };
  }

  function observeTypedStart(row) {
    const channel = globalThis.chrome?.webview;
    if (typeof channel?.addEventListener !== "function"
        || typeof channel.removeEventListener !== "function") {
      throw new Error("production document message channel is unavailable");
    }
    const outbound = observeStartRequest(row);
    let started = null;
    let acceptedReceipt = null;
    let timeout = null;
    let receive = null;
    const promise = new Promise((resolve, reject) => {
      const finish = (callback, value) => {
        channel.removeEventListener("message", receive);
        outbound.dispose();
        if (timeout !== null) clearTimeout(timeout);
        callback(value);
      };
      receive = (event) => {
        const message = event?.data;
        const requestId = message?.request_id;
        if (typeof requestId !== "string" || outbound.status(requestId) === null) return;
        const response = message.response;
        const value = response?.result;
        if (outbound.status(requestId) !== true || !outbound.facts().exact
            || message.kind !== "namisync.command-completion.v1"
            || Object.keys(message).sort().join(",")
              !== "completion_token,generation,kind,phase,request_id,response"
            || message.phase !== "completion"
            || !Number.isSafeInteger(message.generation) || message.generation < 0
            || !/^[0-9a-f]{32}$/.test(requestId)
            || !/^[0-9a-f]{32}$/.test(message.completion_token)
            || Object.keys(response ?? {}).sort().join(",")
              !== "ok,request_id,result,schema_version"
            || response.schema_version !== 1 || response.request_id !== requestId
            || response.ok !== true
            || Object.keys(value ?? {}).sort().join(",") !== "request_id,session_id,task_id"
            || value.task_id !== row.task_id
            || !/^[0-9a-f]{32}$/.test(value.request_id)
            || !/^[0-9a-f]{32}$/.test(value.session_id)
            || started === null) {
          finish(reject, new Error(`typed execution receipt is invalid: ${JSON.stringify(
            outbound.facts(),
          )}`));
          return;
        }
        acceptedReceipt = value;
        finish(resolve, {
          elapsedNs: Math.round((performance.now() - started) * 1000000),
          value,
        });
      };
      channel.addEventListener("message", receive);
      timeout = setTimeout(
        () => finish(reject, new Error(`timed out waiting for typed execution receipt: ${JSON.stringify(
          outbound.facts(),
        )}`)),
        30000,
      );
    });
    return {
      promise,
      peek: () => acceptedReceipt !== null,
      facts: () => ({
        ...outbound.facts(), task_id: acceptedReceipt?.task_id ?? null,
        execution_request_id: acceptedReceipt?.request_id ?? null,
        session_id: acceptedReceipt?.session_id ?? null,
      }),
      start: () => {
        if (started !== null) throw new Error("execution receipt timer repeated");
        started = performance.now();
      },
    };
  }

  function controlSuccessor(review, row, action, frame) {
    if (frame.pending !== "" || !frame.connected || currentReview(row, review) === null) return false;
    const pause = review.querySelector('[data-action="pause"]');
    const resume = review.querySelector('[data-action="resume"]');
    const cancel = review.querySelector('[data-action="cancel"]');
    if (action === "pause") {
      return (frame.status === "Pausing execution…" && pause?.disabled === true)
        || (frame.status === "Execution paused. Resume available."
          && resume?.hidden === false && resume.disabled === false);
    }
    if (action === "resume") {
      return (frame.status === "Execution waiting." && pause?.disabled === true)
        || (frame.status === "Execution running."
          && pause?.hidden === false && pause.disabled === false);
    }
    return (frame.status === "Canceling execution…" && cancel?.disabled === true)
      || (frame.status === "Execution canceled." && cancel?.disabled === true);
  }

  function controlCorrectness(value, row, action) {
    if (!exactControl(value, row, action)) throw new Error(`${action} typed receipt was not accepted`);
    return {
      accepted: true, action, task_id: row.task_id,
      expected_session_id: row.session_id, session_id: value.session_id,
      code: value.code, before: value.before, after: value.after,
    };
  }

  function startedSuccessor(row, frame, confirmed) {
    const review = currentReview(row);
    const status = review?.querySelector(".nami-plan-review__status")?.textContent ?? "";
    const pause = review?.querySelector('[data-action="pause"]');
    const dialog = document.querySelector("#execution-confirmation");
    const modalMatches = confirmed
      ? dialog?.open === true && document.querySelector("#app")?.inert === true
        && document.querySelector("#theme-options")?.inert === true
      : dialog?.open !== true;
    return frame.pending === "" && review?.isConnected === true
      && (status === "Execution running." || status === "Execution waiting.")
      && pause?.hidden === false
      && pause.disabled === (status === "Execution waiting.")
      && modalMatches;
  }

  function sortSuccessor(row, review, sort, frame) {
    return frame.pending === "" && currentReview(row, review) !== null
      && sort?.isConnected === true && sort.parentElement?.isConnected === true
      && review.contains(sort) && sort.parentElement.ariaSort === "ascending";
  }

  async function timedFeedback(
    element, review, pending, observer, settledUI, initialPending = "", row = null,
  ) {
    assertEligible(element, review, initialPending);
    if (row !== null && currentReview(row, review) === null) {
      throw new Error("action review identity changed before click");
    }
    const started = performance.now();
    element.click();
    await nextFrame();
    const elapsedNs = Math.round((performance.now() - started) * 1000000);
    const frame = {
      pending: review.dataset.pending ?? null,
      connected: review.isConnected === true,
      actionConnected: element.isConnected === true,
      current: row === null || currentReview(row, review) !== null,
      status: (review.querySelector(".nami-plan-review__status")?.textContent ?? "").slice(0, 160),
    };
    let outcome = null;
    if (frame.connected && frame.current && frame.pending === pending) {
      outcome = "pending";
    } else if (observer.peek() && settledUI(frame)) {
      outcome = "accepted";
    }
    if (outcome === null) throw new Error(
      `${pending} first-frame feedback invalid: ${JSON.stringify({
        ...frame, receipt: observer.facts(),
      })}`,
    );
    return { elapsedNs, outcome };
  }

  return {
    assertEligible, controlCorrectness, controlSuccessor, currentReview,
    exactControl, observeControl, observeDispatch, observeTypedStart,
    observeStartRequest,
    sortSuccessor, startedSuccessor, timedFeedback,
  };
})();
