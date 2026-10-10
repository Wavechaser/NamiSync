// Installed-asset timing hooks. The driver below is evaluated through native CDP.
globalThis.__tableLoading = (() => {
  const requests = [], reads = [], windows = new WeakMap(), intents = new Map();
  let pending = 0, fatal = null, gesture = null, initial = null, failure = null;
  const now = () => performance.now();
  const ns = (value) => Math.round(value * 1000000);
  const byId = (id) => requests.find((row) => row.request_id === id);
  function coverage(component, fixture) {
    const task = globalThis.__tableLoadingApp?.currentTask();
    if (task?.taskId !== fixture.task_id || task.sessionId !== fixture.session_id) return null;
    const current = component === "plan" ? task.review : task.inventoryReview;
    const panel = document.querySelector(component === "plan" ? ".nami-plan-review" : ".nami-inventory-review");
    const root = panel?.querySelector(component === "plan" ? ".nami-plan-review__rows" : ".nami-inventory-review__rows");
    if (!current || !root || root.clientHeight <= 0) return null;
    const first = Math.floor(root.scrollTop / 24);
    const last = Math.min(current.window.total - 1, Math.ceil((root.scrollTop + root.clientHeight) / 24) - 1);
    const rows = [...root.querySelectorAll("[data-node-id]")];
    const rowIds = rows.map((row) => row.dataset.nodeId);
    const truthful = rows.length === current.window.rows.length && rows.length <= 256
      && current.window.rows.every((row, index) => row.node_id === rowIds[index]);
    const activeNode = component === "plan" ? current.summary.highlight_focus_node_id
      : document.getElementById(root.getAttribute("aria-activedescendant"))?.dataset.nodeId;
    return {covered: truthful && first >= current.window.offset
      && last < current.window.offset + current.window.rows.length,
      first, last, offset: current.window.offset, row_count: rows.length, total: current.window.total,
      active_index: current.window.rows.find((row) => row.node_id === activeNode)?.visible_index ?? null,
      first_node_id: current.window.rows.find((row) => row.visible_index === first)?.node_id ?? null,
      active_node_id: activeNode ?? null,
      ownership: globalThis.__tableLoadingApp.snapshot(task.taskId, component),
      pending, visibility_state: document.visibilityState, document_has_focus: document.hasFocus()};
  }
  const parse = JSON.parse;
  JSON.parse = function (...args) {
    const started = now();
    const value = parse.apply(this, args);
    const ended = now();
    const row = byId(value?.response?.request_id);
    if (row) row.decode_ns = ns(ended - started);
    return value;
  };
  return {
    requests, ns, coverage,
    get pending() { return pending; },
    get fatal() { return fatal; },
    get failure() { return failure; },
    get initial() { return initial; },
    begin(value) { gesture = value; },
    end() { gesture = null; },
    restore() { JSON.parse = parse; },
    initialRead(component, task) {
      if (initial === null && task?.taskKind === (component === "plan" ? "sync-plan" : "inventory")
          && task.sessionReleased && !(task.reviewLoading || task.inventoryLoading)) {
        initial = {kind: "initial", iteration: 1, started: now(), component, frames: [], finished: false};
        gesture = initial;
        const fixture = {task_id: task.taskId, session_id: task.sessionId};
        const observeFrame = () => {
          if (initial.finished) return;
          if (initial.frames.length >= 1800) { fatal = "initial frame observation incomplete"; return; }
          initial.frames.push({timestamp: now(), value: coverage(component, fixture)});
          requestAnimationFrame(observeFrame);
        };
        requestAnimationFrame(observeFrame);
      }
    },
    intent(component, offset) { intents.set(component, {offset, started: now()}); },
    read(component, offset) {
      const intent = intents.get(component);
      reads.push({component, offset, readStarted: now(),
        intentStarted: intent?.offset === offset ? intent.started : now(),
        intentSource: intent?.offset === offset ? "viewport-callback" : "window-call"});
    },
    submit(attempt, request) {
      if (!["get_plan_window", "get_inventory_window"].includes(attempt.command)) return;
      if (requests.length >= 1024) { fatal = "browser request recorder overflow"; return; }
      const value = parse(request);
      const component = attempt.command === "get_plan_window" ? "plan" : "inventory";
      const index = reads.findIndex((row) => row.component === component && row.offset === value.payload.offset);
      const read = index < 0 ? null : reads.splice(index, 1)[0];
      const submitted = now();
      pending += 1;
      requests.push({request_id: attempt.requestId, command: attempt.command,
        payload: value.payload, submitted, gesture: gesture ? `${gesture.kind}-${gesture.iteration}` : null,
        ownership: globalThis.__tableLoadingApp.snapshot(value.payload.task_id, component),
        intent_source: read?.intentSource ?? "unobserved", adopted: false,
        intent_wait_ns: read ? ns(submitted - read.intentStarted) : null,
        readiness_wait_ns: read ? ns(submitted - read.readStarted) : null});
    },
    native(id) {
      const row = byId(id);
      if (row) { row.native_at = now(); row.round_trip_ns = ns(row.native_at - row.submitted); }
    },
    validated(attempt, response) {
      const row = byId(attempt.requestId);
      if (!row) return;
      pending -= 1;
      row.validated_at = now();
      row.validation_ns = ns(row.validated_at - row.native_at);
      row.disposition = response.result?.disposition ?? "error";
      row.returned_offset = response.result?.offset;
      row.row_count = response.result?.rows?.length;
      row.returned_view_revision = response.result?.view_revision;
      row.returned_first_node_id = response.result?.rows?.[0]?.node_id ?? null;
      row.settlement_error = attempt.result?.error ? String(attempt.result.error).slice(0, 512) : null;
      if (row.settlement_error === null && response.ok && row.disposition === "current" && attempt.result?.value) windows.set(attempt.result.value, row);
      else {
        fatal = row.settlement_error ?? "window returned an error/conflict";
        failure ??= {request_id: row.request_id, error: fatal, response};
      }
    },
    dom(window, started, treeGeneration = null) {
      const row = windows.get(window);
      if (row) {
        row.dom_ns = ns(now() - started);
        row.adopted = true;
        row.tree_generation = treeGeneration;
        row.adoption_ownership = globalThis.__tableLoadingApp.snapshot(row.payload.task_id,
          row.command === "get_plan_window" ? "plan" : "inventory");
      }
    },
  };
})();

// DRIVER
(async () => {
  const trace = globalThis.__tableLoading;
  let observed = null;
  const frame = () => new Promise((resolve) => requestAnimationFrame(() => {
    if (observed) observed.frames.push({timestamp: performance.now(), value: coverage()});
    resolve();
  }));
  const gestures = [];
  async function until(predicate, label) {
    for (let index = 0; index < 1800; index += 1) {
      if (trace.fatal) throw new Error(trace.fatal);
      const value = predicate();
      if (value) return value;
      await frame();
    }
    throw new Error(`table-loading ${label} incomplete`);
  }
  await until(() => typeof window.pywebview?.api?.dispatch === "function"
    && globalThis.__tableLoadingApp && document.querySelector("#host-status")?.textContent === "Ready", "startup readiness");
  const api = globalThis.__tableLoadingApp;
  const id = crypto.randomUUID().replaceAll("-", "");
  const native = await window.pywebview.api.dispatch(JSON.stringify({
    schema_version: 1, request_id: id, command: "plan_scale_fixture", payload: {},
  }));
  const response = JSON.parse(JSON.stringify(native.response));
  const fixture = response?.result;
  if (native.response_token !== null) await window.pywebview.api.dispatch(`ack:${native.response_token}`);
  if (response?.request_id !== id || response?.ok !== true || !fixture?.task_id) throw new Error("fixture metadata refused");
  if (api.currentTask()?.taskId !== fixture.task_id) api.selectTask(fixture.task_id);
  const component = fixture.case === "plan-base" ? "plan" : "inventory";
  const panel = () => document.querySelector(component === "plan" ? ".nami-plan-review" : ".nami-inventory-review");
  const body = () => panel()?.querySelector(component === "plan" ? ".nami-plan-review__rows" : ".nami-inventory-review__rows");
  const owner = () => {
    const task = api.currentTask();
    if (task?.taskId !== fixture.task_id || task.sessionId !== fixture.session_id) return null;
    return component === "plan" ? task.review : task.inventoryReview;
  };
  function coverage() {
    const value = trace.coverage(component, fixture);
    return value?.total === fixture.visible_rows ? value : null;
  }
  async function observe(gesture, target) {
    let gap = null, uncovered = 0, frames = 0;
    const gaps = [];
    let coveredAt = null, paintAt = null, stable = 0, result;
    const landed = (value) => value?.covered && value.total === fixture.visible_rows
      && value.visibility_state === "visible" && value.document_has_focus
      && (gesture.kind === "keyboard"
        ? value.active_index === target && value.first <= target && target <= value.last
        : value.first === target);
    let inspected = 0;
    for (let index = 0; index < 1800 && paintAt === null; index += 1) {
      if (trace.fatal) throw new Error(trace.fatal);
      while (inspected < gesture.frames.length) {
        const entry = gesture.frames[inspected++];
        stable = landed(entry.value) ? stable + 1 : 0;
        if (stable === 1) coveredAt = entry.timestamp;
        if (stable === 2) { paintAt = entry.timestamp; result = entry.value; break; }
      }
      if (paintAt === null) await frame();
    }
    frames = inspected;
    if (paintAt === null) throw new Error("gesture frame interval was not observed");
    gesture.finished = true;
    observed = null;
    await until(() => trace.pending === 0 && landed(coverage()), "gesture settlement");
    await frame();
    await until(() => trace.pending === 0 && landed(coverage()), "gesture final accounting");
    const settledAt = performance.now();
    for (const {timestamp, value} of gesture.frames ?? []) {
      if (timestamp > paintAt) break;
      if (!value?.covered) gap ??= timestamp;
      else if (gap !== null) { gaps.push([gap - gesture.started, timestamp - gesture.started]); uncovered += timestamp - gap; gap = null; }
    }
    if (gap !== null) { gaps.push([gap - gesture.started, paintAt - gesture.started]); uncovered += paintAt - gap; }
    const requests = trace.requests.filter((row) => row.gesture === `${gesture.kind}-${gesture.iteration}`);
    const changes = requests.flatMap((row) => [[row.submitted, 1], [row.validated_at, -1]])
      .sort((left, right) => left[0] - right[0]);
    let outstanding = 0, maximum = 0;
    for (const [, delta] of changes) { outstanding += delta; maximum = Math.max(maximum, outstanding); }
    const inputs = gesture.inputs ?? [];
    const lastInput = inputs.at(-1) ?? gesture.started;
    gestures.push({kind: gesture.kind, iteration: gesture.iteration, target,
      input_timestamps_ms: inputs.map(value => value - gesture.started),
      input_cadence_ms: inputs.slice(1).map((value, index) => value - inputs[index]),
      input_span_ns: trace.ns(lastInput - gesture.started),
      covered_after_last_input_ns: trace.ns(coveredAt - lastInput),
      paint_opportunity_after_last_input_ns: trace.ns(paintAt - lastInput),
      settlement_after_last_input_ns: trace.ns(settledAt - lastInput),
      setup_offset: gesture.setupOffset ?? null,
      setup_request_id: gesture.setupRequestId ?? null,
      setup_first: gesture.setupFirst ?? null, setup_last: gesture.setupLast ?? null,
      landed: true, ...result, covered_ns: trace.ns(coveredAt - gesture.started),
      paint_opportunity_ns: trace.ns(paintAt - gesture.started), uncovered_ns: trace.ns(uncovered),
      settlement_ns: trace.ns(settledAt - gesture.started), settlement_pending: trace.pending,
      frame_count: frames, uncovered_intervals_ms: gaps, request_count: requests.length,
      maximum_outstanding: maximum, discarded_responses: requests.filter((row) => !row.adopted).length});
    trace.end();
    gesture.finished = true;
    observed = null;
  }
  function scroll(index) {
    body().scrollTop = index * 24;
    body().dispatchEvent(new Event("scroll"));
  }
  async function reset(index = 0) {
    trace.end();
    scroll(index);
    await until(() => coverage()?.covered && trace.pending === 0, "reset coverage");
    await frame();
    await until(() => coverage()?.covered && trace.pending === 0, "reset settlement");
  }
  try {
    const initial = await until(() => trace.initial, "initial read start");
    if (!initial || initial.component !== component) throw new Error("initial table-load start not observed");
    await observe(initial, 0);
    const root = body();
    const profile = {inner_width: innerWidth, inner_height: innerHeight,
      device_pixel_ratio: devicePixelRatio, viewport_width: root.clientWidth,
      viewport_height: root.clientHeight, theme: document.documentElement.dataset.theme,
      visibility_state: document.visibilityState, document_has_focus: document.hasFocus(),
      reduced_motion: matchMedia("(prefers-reduced-motion: reduce)").matches,
      forced_colors: matchMedia("(forced-colors: active)").matches,
      details_expanded: panel().querySelector('[data-action="toggle-execution-details"], [data-action="inventory-details"]')?.ariaExpanded,
      row_height: root.querySelector("[data-node-id]").getBoundingClientRect().height};
    if (profile.theme !== "light" || profile.reduced_motion || profile.forced_colors
        || profile.details_expanded !== "false" || Math.abs(profile.row_height - 24) > 0.1) {
      throw new Error("table-loading declared profile not reached");
    }
    for (const kind of ["sequential", "jump", "covered-return", "burst", "keyboard"]) {
      for (let iteration = 1; iteration <= 3; iteration += 1) {
        await reset();
        let keyboardSetup = null;
        if (kind === "keyboard") {
          await reset(20032);
          keyboardSetup = coverage();
          const last = Math.ceil((20032 * 24 + root.clientHeight) / 24) - 1;
          const setupRead = trace.requests.findLast(row => row.adopted
            && row.returned_offset === keyboardSetup.offset && row.row_count === 256);
          if (keyboardSetup.first !== 20032 || keyboardSetup.last !== last
              || !keyboardSetup.covered || !setupRead) throw new Error("keyboard setup window not observed");
          keyboardSetup.requestId = setupRead.request_id;
        }
        let target = kind === "jump" ? 60000 : kind === "burst" ? 40000 : 256;
        if (kind === "keyboard") {
          const first = root.querySelector("[data-node-id]");
          target = owner().window.offset - 1;
          first.click();
          // Row activation can focus/reveal synchronously; restore setup before yielding.
          root.scrollTop = keyboardSetup.first * 24;
          first.focus({preventScroll: true});
          await until(() => trace.pending === 0 && coverage()?.covered
            && (component === "plan" ? owner().summary.highlight_focus_node_id === first.dataset.nodeId
              : root.getAttribute("aria-activedescendant") === first.id), "keyboard setup focus");
          await frame();
          const selectedSetup = coverage();
          if (selectedSetup.offset !== keyboardSetup.offset || selectedSetup.first !== keyboardSetup.first
              || selectedSetup.last !== keyboardSetup.last || selectedSetup.active_index !== keyboardSetup.offset) {
            throw new Error("keyboard setup geometry or active row changed");
          }
          const live = root.querySelector("[data-node-id]");
          live.focus({preventScroll: true});
          if (component === "plan" && document.activeElement !== live) throw new Error("Plan keyboard target lost focus");
          if (component === "inventory") root.focus();
        }
        const gesture = {kind, iteration, started: performance.now(), frames: [], inputs: []};
        if (kind === "keyboard") {
          gesture.setupOffset = keyboardSetup.offset;
          gesture.setupRequestId = keyboardSetup.requestId;
          gesture.setupFirst = keyboardSetup.first;
          gesture.setupLast = keyboardSetup.last;
        }
        if (document.visibilityState !== "visible" || !document.hasFocus()) throw new Error("measurement document is not visible/focused");
        observed = gesture;
        trace.begin(gesture);
        if (kind === "burst") {
          for (const index of [5000, 10000, 15000, 20000, 25000, 30000, 35000, 40000]) {
            gesture.inputs.push(performance.now()); scroll(index); await frame();
          }
        } else if (kind === "covered-return") {
          gesture.inputs.push(performance.now()); scroll(10000); await frame();
          gesture.inputs.push(performance.now()); scroll(0); target = 0;
        } else if (kind === "keyboard") {
          const focused = component === "plan" ? document.activeElement : root;
          gesture.inputs.push(performance.now());
          focused.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowUp", bubbles: true, cancelable: true}));
        } else { gesture.inputs.push(performance.now()); scroll(target); }
        await observe(gesture, target);
      }
    }
    return {samples: {complete: true, fixture, profile, gestures, requests: trace.requests,
      input_method: "synthetic DOM scroll/click/keydown through production handlers; not native input evidence"}};
  } catch (error) {
    return {samples: {complete: false, fixture, error: String(error).slice(0, 512), failure: trace.failure, gestures, requests: trace.requests}};
  } finally {
    trace.restore();
  }
})()
