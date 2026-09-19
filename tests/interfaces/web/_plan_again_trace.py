"""Bounded, test-only tracing for the installed Plan-again route."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import re
from threading import Lock
from types import MappingProxyType, MethodType


PHASES = frozenset({"setup", "task-47-48", "task-48-49"})
TRACE_LIMIT = 48
TRACE_VALUES = {
    "button-event": frozenset(
        f"{trusted}-{enabled}-{current}"
        for trusted in ("trusted", "untrusted")
        for enabled in ("enabled", "disabled")
        for current in ("current", "missing")
    ),
    "button-projection": frozenset({"pending", "enabled", "ineligible"}),
    "callback-identity": frozenset({"current", "retained-not-current", "replaced"}),
    "callback-pending": frozenset({"clear", "pending"}),
    "eligibility": frozenset({
        "close", "form-not-ready", "origin-batch", "task-batch",
        "global-batch", "idle", "retry-idle", "other-attempt",
    }),
    "attempt-route": frozenset({"blocked", "retry", "fresh"}),
    "attempt-created": frozenset({"none", "fresh", "stale"}),
    "dispatch": frozenset({"submitted"}),
    "dispatch-settle": frozenset({"success", "uncertain", "error"}),
    "task-refresh": frozenset({"added", "unchanged"}),
    "bridge-call": frozenset({"entered"}),
    "response-validation": frozenset({"accepted", "same-task-rejected", "shape-rejected"}),
    "bridge-attempt": frozenset({"created"}),
    "async-capacity": frozenset({"full", "available"}),
    "async-entry": frozenset({"registered"}),
    "bridge-readiness": frozenset({"waiting", "ready"}),
    "native-response": frozenset({"direct", "admitted"}),
    "command-completion": frozenset({"matched"}),
    "host-validation": frozenset({"entered", "accepted", "rejected"}),
    "host-handler": frozenset({"entered", "returned", "error"}),
    "replay": frozenset({"miss", "hit", "error"}),
    "registry": frozenset({"entered", "returned", "error"}),
}


_BRIDGE_PREFIX = """const BRIDGE_SCHEMA_VERSION = 1;\n"""
_BRIDGE_TRACE = r'''const NAMI_PLAN_AGAIN_TRACE_LIMIT = 48;
globalThis.__namiPlanAgainTrace = (() => {
  const cases = Object.create(null);
  let phase = null;
  const allowed = new Set(["setup", "task-47-48", "task-48-49"]);
  const begin = (value) => {
    if (!allowed.has(value)) return false;
    phase = value;
    cases[value] ??= {entries: [], overflow: false};
    return true;
  };
  const record = (stage, value) => {
    try {
      if (phase === null || typeof stage !== "string" || typeof value !== "string") return;
      const item = cases[phase];
      if (item.entries.length >= NAMI_PLAN_AGAIN_TRACE_LIMIT) {
        item.overflow = true;
        return;
      }
      item.entries.push({sequence: item.entries.length + 1, stage, value});
    } catch (_error) {
      // Diagnostic observation cannot alter the product route.
    }
  };
  const end = (value) => {
    if (phase !== value) return false;
    phase = null;
    return true;
  };
  const snapshot = () => JSON.parse(JSON.stringify({cases}));
  return Object.freeze({begin, record, end, snapshot});
})();
const namiPlanAgainTrace = (stage, value) =>
  globalThis.__namiPlanAgainTrace.record(stage, value);

const BRIDGE_SCHEMA_VERSION = 1;
'''

_BRIDGE_PLAN_AGAIN = r'''export function planAgain(taskId, sourceMount = null, targetMount = null) {
  namiPlanAgainTrace("bridge-call", "entered");
'''
_BRIDGE_PLAN_AGAIN_ORIGINAL = r'''export function planAgain(taskId, sourceMount = null, targetMount = null) {
'''

_BRIDGE_VALIDATE = r'''  const validateResult = (value) => (
    validateStartPlanResult(value)
    && (command === "plan_again"
      ? value.task_id !== payload.task_id
      : value.task_id === payload.task_id)
  );
'''
_BRIDGE_VALIDATE_TRACE = r'''  const validateResult = (value) => {
    const shapeValid = validateStartPlanResult(value);
    const identityValid = shapeValid && (command === "plan_again"
      ? value.task_id !== payload.task_id
      : value.task_id === payload.task_id);
    if (command === "plan_again") {
      namiPlanAgainTrace("response-validation", identityValid ? "accepted" :
        shapeValid ? "same-task-rejected" : "shape-rejected");
    }
    return identityValid;
  };
'''

_BRIDGE_ATTEMPT = r'''  const requestId = mintId();
  const attempt = {
'''
_BRIDGE_ATTEMPT_TRACE = r'''  const requestId = mintId();
  if (command === "plan_again") namiPlanAgainTrace("bridge-attempt", "created");
  const attempt = {
'''

_BRIDGE_CAPACITY = r'''    if (asyncCommandAttempts.size >= ASYNC_COMMAND_MAX_ATTEMPTS) {
      throw new BridgeCommandError("bridge_busy", ERROR_MESSAGES.bridge_busy);
    }
'''
_BRIDGE_CAPACITY_TRACE = r'''    if (asyncCommandAttempts.size >= ASYNC_COMMAND_MAX_ATTEMPTS) {
      if (command === "plan_again") namiPlanAgainTrace("async-capacity", "full");
      throw new BridgeCommandError("bridge_busy", ERROR_MESSAGES.bridge_busy);
    }
    if (command === "plan_again") namiPlanAgainTrace("async-capacity", "available");
'''

_BRIDGE_ENTRY = r'''    asyncCommandAttempts.set(requestId, attempt.asyncEntry);
  }
'''
_BRIDGE_ENTRY_TRACE = r'''    if (command === "plan_again") attempt.asyncEntry.planAgainTrace = true;
    asyncCommandAttempts.set(requestId, attempt.asyncEntry);
    if (command === "plan_again") namiPlanAgainTrace("async-entry", "registered");
  }
'''

_BRIDGE_READY = r'''  if (entry === null || asyncCommandAttempts.get(requestId) !== entry) {
    throw new BridgeTransportError();
  }
  await waitUntilReady();
  if (attempt.cancelled) {
'''
_BRIDGE_READY_TRACE = r'''  if (entry === null || asyncCommandAttempts.get(requestId) !== entry) {
    throw new BridgeTransportError();
  }
  if (entry.planAgainTrace) namiPlanAgainTrace("bridge-readiness", "waiting");
  await waitUntilReady();
  if (entry.planAgainTrace) namiPlanAgainTrace("bridge-readiness", "ready");
  if (attempt.cancelled) {
'''

_BRIDGE_NATIVE = r'''    const native = await Promise.race([transport, reincarnated, cancelled]);
    if (native.kind === "direct") {
'''
_BRIDGE_NATIVE_TRACE = r'''    const native = await Promise.race([transport, reincarnated, cancelled]);
    if (entry.planAgainTrace) namiPlanAgainTrace("native-response", native.kind);
    if (native.kind === "direct") {
'''

_BRIDGE_COMPLETION = r'''  const entry = asyncCommandAttempts.get(message.request_id);
  if (entry === undefined) {
'''
_BRIDGE_COMPLETION_TRACE = r'''  const entry = asyncCommandAttempts.get(message.request_id);
  if (entry?.planAgainTrace === true) namiPlanAgainTrace("command-completion", "matched");
  if (entry === undefined) {
'''

_PLAN_CLICK = r'''  planAgain.addEventListener("click", () => {
    if (current !== null) callbacks.onPlanAgain(current);
  });
'''
_PLAN_CLICK_TRACE = r'''  planAgain.addEventListener("click", (event) => {
    globalThis.__namiPlanAgainTrace?.record("button-event", `${event.isTrusted ? "trusted" : "untrusted"}-${planAgain.disabled ? "disabled" : "enabled"}-${current === null ? "missing" : "current"}`);
    if (current !== null) callbacks.onPlanAgain(current);
  });
'''

_PLAN_RENDER = r'''    planAgain.disabled = review.pending !== null || task.canPlanAgain !== true;
'''
_PLAN_RENDER_TRACE = r'''    planAgain.disabled = review.pending !== null || task.canPlanAgain !== true;
    globalThis.__namiPlanAgainTrace?.record("button-projection", review.pending !== null ? "pending" : task.canPlanAgain === true ? "enabled" : "ineligible");
'''

_APP_CALLBACK = r'''async function planAgainFromReview(review) {
  const task = currentReviewTask(review);
  if (task === null || review.pending !== null) return;
'''
_APP_CALLBACK_TRACE = r'''async function planAgainFromReview(review) {
  const task = currentReviewTask(review);
  const retained = retainedReviewTask(review);
  globalThis.__namiPlanAgainTrace?.record("callback-identity", task !== null ? "current" : retained !== null ? "retained-not-current" : "replaced");
  globalThis.__namiPlanAgainTrace?.record("callback-pending", review.pending === null ? "clear" : "pending");
  if (task === null || review.pending !== null) return;
'''

_APP_ELIGIBILITY = r'''function canStartPlanAgain(task) {
  const form = task?.form;
  if (
    task === null || currentTask() !== task || task.closePending ||
    form?.canPlanAgain !== true ||
    originHasPendingBatch(task.taskId) || batchTaskBlockReason(task.taskId) !== null ||
    (pageBatch !== null && pageBatch.running !== null)
  ) return false;
  return form.attempt === null || (
    form.attempt.kind === "plan-again" && !form.attempt.running &&
    typeof form.attempt.retry === "function"
  );
}
'''
_APP_ELIGIBILITY_TRACE = r'''function canStartPlanAgain(task) {
  const form = task?.form;
  if (task === null || currentTask() !== task) {
    return false;
  }
  if (task.closePending) {
    globalThis.__namiPlanAgainTrace?.record("eligibility", "close");
    return false;
  }
  if (form?.canPlanAgain !== true) {
    globalThis.__namiPlanAgainTrace?.record("eligibility", "form-not-ready");
    return false;
  }
  if (originHasPendingBatch(task.taskId)) {
    globalThis.__namiPlanAgainTrace?.record("eligibility", "origin-batch");
    return false;
  }
  if (batchTaskBlockReason(task.taskId) !== null) {
    globalThis.__namiPlanAgainTrace?.record("eligibility", "task-batch");
    return false;
  }
  if (pageBatch !== null && pageBatch.running !== null) {
    globalThis.__namiPlanAgainTrace?.record("eligibility", "global-batch");
    return false;
  }
  const attempt = form.attempt;
  if (attempt === null) {
    globalThis.__namiPlanAgainTrace?.record("eligibility", "idle");
    return true;
  }
  const retryIdle = attempt.kind === "plan-again" && !attempt.running &&
    typeof attempt.retry === "function";
  globalThis.__namiPlanAgainTrace?.record("eligibility", retryIdle ? "retry-idle" : "other-attempt");
  return retryIdle;
}
'''

_APP_START = r'''  if (!canStartPlanAgain(task)) return false;
  if (form.attempt !== null) {
    return retryFormAttempt(task, form, "plan-again");
  }
'''
_APP_START_TRACE = r'''  if (!canStartPlanAgain(task)) {
    globalThis.__namiPlanAgainTrace?.record("attempt-route", "blocked");
    return false;
  }
  if (form.attempt !== null) {
    globalThis.__namiPlanAgainTrace?.record("attempt-route", "retry");
    return retryFormAttempt(task, form, "plan-again");
  }
  globalThis.__namiPlanAgainTrace?.record("attempt-route", "fresh");
'''

_APP_BEGIN = r'''  const attempt = beginFormAttempt(task, form, "plan-again");
  if (attempt === null || !freshFormAttempt(task, form, attempt, revision)) return false;
'''
_APP_BEGIN_TRACE = r'''  const attempt = beginFormAttempt(task, form, "plan-again");
  const fresh = attempt !== null && freshFormAttempt(task, form, attempt, revision);
  globalThis.__namiPlanAgainTrace?.record("attempt-created", attempt === null ? "none" : fresh ? "fresh" : "stale");
  if (!fresh) return false;
'''

_APP_DISPATCH_START = r'''async function dispatchFormAttempt(task, form, attempt, submit) {
  attempt.dispatched = true;
  renderTasks();
  try {
    await submit();
'''
_APP_DISPATCH_START_TRACE = r'''async function dispatchFormAttempt(task, form, attempt, submit) {
  attempt.dispatched = true;
  renderTasks();
  if (attempt.kind === "plan-again") globalThis.__namiPlanAgainTrace?.record("dispatch", "submitted");
  try {
    await submit();
    if (attempt.kind === "plan-again") globalThis.__namiPlanAgainTrace?.record("dispatch-settle", "success");
'''

_APP_DISPATCH_CATCH = r'''  } catch (error) {
    if (!currentFormAttempt(task, form, attempt)) return;
    if (error instanceof StartPlanUncertainError) {
'''
_APP_DISPATCH_CATCH_TRACE = r'''  } catch (error) {
    if (attempt.kind === "plan-again") globalThis.__namiPlanAgainTrace?.record("dispatch-settle", error instanceof StartPlanUncertainError ? "uncertain" : "error");
    if (!currentFormAttempt(task, form, attempt)) return;
    if (error instanceof StartPlanUncertainError) {
'''

_APP_REFRESH = r'''  if (currentFormAttempt(task, form, attempt)) form.attempt = null;
  await refreshTasks(startupEpoch);
}
'''
_APP_REFRESH_TRACE = r'''  if (currentFormAttempt(task, form, attempt)) form.attempt = null;
  const countBeforeRefresh = attempt.kind === "plan-again" ? tasks.size : null;
  await refreshTasks(startupEpoch);
  if (attempt.kind === "plan-again") globalThis.__namiPlanAgainTrace?.record("task-refresh", tasks.size > countBeforeRefresh ? "added" : "unchanged");
}
'''


_ASSET_PATCHES = {
    "bridge.js": (
        (_BRIDGE_PREFIX, _BRIDGE_TRACE),
        (_BRIDGE_PLAN_AGAIN_ORIGINAL, _BRIDGE_PLAN_AGAIN),
        (_BRIDGE_VALIDATE, _BRIDGE_VALIDATE_TRACE),
        (_BRIDGE_ATTEMPT, _BRIDGE_ATTEMPT_TRACE),
        (_BRIDGE_CAPACITY, _BRIDGE_CAPACITY_TRACE),
        (_BRIDGE_ENTRY, _BRIDGE_ENTRY_TRACE),
        (_BRIDGE_READY, _BRIDGE_READY_TRACE),
        (_BRIDGE_NATIVE, _BRIDGE_NATIVE_TRACE),
        (_BRIDGE_COMPLETION, _BRIDGE_COMPLETION_TRACE),
    ),
    "plan_review.js": ((_PLAN_CLICK, _PLAN_CLICK_TRACE), (_PLAN_RENDER, _PLAN_RENDER_TRACE)),
    "app.js": (
        (_APP_CALLBACK, _APP_CALLBACK_TRACE),
        (_APP_ELIGIBILITY, _APP_ELIGIBILITY_TRACE),
        (_APP_START, _APP_START_TRACE),
        (_APP_BEGIN, _APP_BEGIN_TRACE),
        (_APP_DISPATCH_START, _APP_DISPATCH_START_TRACE),
        (_APP_DISPATCH_CATCH, _APP_DISPATCH_CATCH_TRACE),
        (_APP_REFRESH, _APP_REFRESH_TRACE),
    ),
}


def _asset_root(installed_root: Path) -> Path:
    return installed_root / "Lib" / "site-packages" / "namisync" / "interfaces" / "web" / "assets"


@contextmanager
def installed_plan_again_trace(installed_root: Path) -> Iterator[dict[str, dict[str, object]]]:
    """Instrument three exact installed assets and restore their original bytes."""

    originals: dict[Path, bytes] = {}
    hashes: dict[str, dict[str, object]] = {}
    transformed: dict[Path, bytes] = {}
    try:
        for name, replacements in _ASSET_PATCHES.items():
            path = _asset_root(installed_root) / name
            original = path.read_bytes()
            text = original.decode("utf-8")
            for old, new in replacements:
                pattern_text = re.escape(old).replace(re.escape("\n"), r"\r?\n")
                matches = list(re.finditer(pattern_text, text))
                if len(matches) != 1:
                    raise AssertionError(f"Plan-again trace anchor drifted in {name}")
                match = matches[0]
                matched = match.group(0)
                preceding = text[max(0, match.start() - 256):match.start()]
                newline = "\r\n" if "\r\n" in matched or "\r\n" in preceding else "\n"
                installed_new = new.replace("\n", newline)
                text = text[:match.start()] + installed_new + text[match.end():]
            instrumented = text.encode("utf-8")
            originals[path] = original
            transformed[path] = instrumented
            hashes[name] = {
                "original": sha256(original).hexdigest(),
                "instrumented": sha256(instrumented).hexdigest(),
                "anchors": len(replacements),
            }
        for path, instrumented in transformed.items():
            path.write_bytes(instrumented)
        yield hashes
    finally:
        failure: OSError | None = None
        for path, original in originals.items():
            try:
                path.write_bytes(original)
            except OSError as error:
                if failure is None:
                    failure = error
        if failure is not None:
            raise failure


def verify_restored_assets(
    installed_root: Path, hashes: Mapping[str, Mapping[str, object]],
) -> None:
    for name, evidence in hashes.items():
        actual = sha256((_asset_root(installed_root) / name).read_bytes()).hexdigest()
        if actual != evidence.get("original"):
            raise AssertionError(f"Plan-again trace did not restore {name}")


class PlanAgainHostTrace:
    """One bounded host-local sequence for the three declared cases."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._phase: str | None = None
        self._cases: dict[str, dict[str, object]] = {}

    def begin(self, phase: str) -> None:
        if phase not in PHASES:
            raise ValueError("unknown Plan-again trace phase")
        with self._lock:
            self._phase = phase
            self._cases.setdefault(phase, {"entries": [], "overflow": False})

    def record(self, stage: str, value: str) -> None:
        with self._lock:
            if self._phase is None:
                return
            case = self._cases[self._phase]
            entries = case["entries"]
            assert type(entries) is list
            if len(entries) >= TRACE_LIMIT:
                case["overflow"] = True
                return
            entries.append({"sequence": len(entries) + 1, "stage": stage, "value": value})

    def end(self, phase: str) -> None:
        with self._lock:
            if self._phase != phase:
                raise ValueError("Plan-again trace phase does not match")
            self._phase = None

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {"cases": {phase: {
                "entries": [dict(entry) for entry in value["entries"]],
                "overflow": value["overflow"],
            } for phase, value in self._cases.items()}}


def traced_plan_again_commands(
    commands: Mapping[str, object], trace: PlanAgainHostTrace,
) -> Mapping[str, object]:
    """Replace the actual CommandSpec-held validator and handler."""

    spec = commands["plan_again"]
    validator = spec.validate_payload
    handler = spec.handler

    def validate(payload: object) -> object:
        trace.record("host-validation", "entered")
        try:
            result = validator(payload)
        except BaseException:
            trace.record("host-validation", "rejected")
            raise
        trace.record("host-validation", "accepted")
        return result

    def handle(payload: object) -> object:
        trace.record("host-handler", "entered")
        try:
            result = handler(payload)
        except BaseException:
            trace.record("host-handler", "error")
            raise
        trace.record("host-handler", "returned")
        return result

    return MappingProxyType({**commands, "plan_again": replace(
        spec, validate_payload=validate, handler=handle,
    )})


def trace_registry_plan_again(registry: object, trace: PlanAgainHostTrace) -> None:
    """Wrap one concrete test-owned registry instance exactly once."""

    original = registry.start_plan_again
    original_replay = registry.replay_start

    def replay_start(_registry: object, *args: object, **kwargs: object) -> object:
        try:
            result = original_replay(*args, **kwargs)
        except BaseException:
            trace.record("replay", "error")
            raise
        trace.record("replay", "miss" if result is None else "hit")
        return result

    def start_plan_again(_registry: object, *args: object, **kwargs: object) -> object:
        trace.record("registry", "entered")
        try:
            result = original(*args, **kwargs)
        except BaseException:
            trace.record("registry", "error")
            raise
        trace.record("registry", "returned")
        return result

    registry.replay_start = MethodType(replay_start, registry)
    registry.start_plan_again = MethodType(start_plan_again, registry)


def validate_trace_snapshot(
    value: object, phases: set[str], *, allow_empty: bool = False,
    allow_overflow: bool = False,
) -> None:
    if type(value) is not dict or set(value) != {"cases"} or type(value["cases"]) is not dict:
        raise AssertionError("Plan-again trace snapshot shape is invalid")
    if set(value["cases"]) != phases:
        raise AssertionError("Plan-again trace phase membership is invalid")
    for phase, case in value["cases"].items():
        if phase not in PHASES or type(case) is not dict or set(case) != {"entries", "overflow"}:
            raise AssertionError("Plan-again trace case shape is invalid")
        entries = case["entries"]
        if (
            type(entries) is not list or (not allow_empty and not entries)
            or len(entries) > TRACE_LIMIT
            or (case["overflow"] is not False and not (
                allow_overflow and case["overflow"] is True
            ))
        ):
            raise AssertionError("Plan-again trace case bounds are invalid")
        for sequence, entry in enumerate(entries, 1):
            if (
                type(entry) is not dict or set(entry) != {"sequence", "stage", "value"}
                or entry["sequence"] != sequence
                or entry["stage"] not in TRACE_VALUES
                or entry["value"] not in TRACE_VALUES[entry["stage"]]
            ):
                raise AssertionError("Plan-again trace entry shape is invalid")
