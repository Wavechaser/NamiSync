"""Installed-wheel child for the M1-4 process-live task shell witness."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
import threading
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from types import MethodType
from typing import Any, Callable
from unittest.mock import patch

from _headed_evidence import EvidencePaths, EvidencePublisher
from _startup_test_support import headed_command_extension


_FAILURE_STAGES = frozenset(
    {
        "page_probe",
        "page_initial",
        "page_initial_ready",
        "page_initial_capacity",
        "page_initial_basic_close",
        "page_initial_retry",
        "page_initial_navigation",
        "page_initial_navigation_cleanup",
        "page_initial_navigation_recorded",
        "page_initial_reinjection_armed",
        "page_initial_reinjection_wait",
        "page_reinjected",
        "page_busy",
        "page_terminal_first",
        "page_terminal_second",
        "child",
    }
)
_FAILURE_TYPES = frozenset(
    {"AssertionError", "AttributeError", "RuntimeError", "TypeError", "ValueError", "Error"}
)
_COMPLETE_TEXT = "Task shell gate complete"


_COMMON_JS = r"""
const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
async function until(predicate, label) {
  for (let attempt = 0; attempt < 300; attempt += 1) {
    const value = predicate();
    if (value) return value;
    await sleep(25);
  }
  throw new Error(`timed out waiting for ${label}`);
}
async function untilAsync(predicate, label) {
  for (let attempt = 0; attempt < 300; attempt += 1) {
    const value = await predicate();
    if (value) return value;
    await sleep(25);
  }
  throw new Error(`timed out waiting for ${label}`);
}
function rows() { return Array.from(document.querySelectorAll(".nami-task-rail__row")); }
function rowByTitle(title) {
  return rows().find((row) => row.querySelector(".nami-task-card__title")?.textContent === title);
}
function selectedTitle() {
  return document.querySelector('.nami-task-card[aria-current="page"] .nami-task-card__title')?.textContent ?? null;
}
function workTitle() { return document.querySelector(".nami-work-panel h2")?.textContent ?? null; }
function statusFor(title) { return rowByTitle(title)?.querySelector(".nami-task-card__status")?.textContent ?? null; }
function clickNew() { document.querySelector(".nami-task-rail__header .nami-button")?.click(); }
function clickSelect(title) { rowByTitle(title)?.querySelector(".nami-task-card")?.click(); }
function clickClose(title) { rowByTitle(title)?.querySelector(".nami-task-rail__close")?.click(); }
function resolvedBackground(variable) {
  const witness = document.createElement("span");
  witness.style.background = `var(${variable})`;
  document.body.append(witness);
  const value = getComputedStyle(witness).backgroundColor;
  witness.remove();
  return value;
}
function selectionAppearance(title) {
  const row = rowByTitle(title);
  const card = row?.querySelector(".nami-task-card");
  const close = row?.querySelector(".nami-task-rail__close");
  if (card === undefined || card === null) return null;
  const style = getComputedStyle(card);
  const marker = getComputedStyle(card, "::before");
  return {
    current: card.ariaCurrent,
    persistentFill: style.backgroundColor === resolvedBackground("--color-selection-highlight"),
    markerWidth: marker.width,
    markerAccent: marker.backgroundColor === resolvedBackground("--color-accent-fill"),
    closeText: close?.textContent ?? null,
    closeEnabled: close?.disabled === false,
  };
}
function selectedAppearanceSettled(title) {
  const appearance = selectionAppearance(title);
  return appearance?.current === "page" &&
    appearance.persistentFill === true &&
    appearance.markerWidth === "3px" &&
    appearance.markerAccent === true;
}
function selectionCleared(title) {
  const card = rowByTitle(title)?.querySelector(".nami-task-card");
  if (card === undefined || card === null) return false;
  const marker = getComputedStyle(card, "::before");
  return card.ariaCurrent === "false" &&
    getComputedStyle(card).backgroundColor === resolvedBackground("--color-neutral-subtle-background") &&
    marker.content === "none";
}
let rawSequence = 0;
async function control(action, value = null) {
  rawSequence += 1;
  const requestId = rawSequence.toString(16).padStart(32, "0");
  const api = window.pywebview?.api;
  if (typeof api?.dispatch !== "function") throw new Error("native bridge is unavailable");
  const native = await api.dispatch(JSON.stringify({
    schema_version: 1,
    request_id: requestId,
    command: "task_shell_test_control",
    payload: { action, value },
  }));
  if (native === null || typeof native !== "object") throw new Error("invalid native response");
  const response = JSON.parse(JSON.stringify(native.response));
  if (native.response_token !== null) await api.dispatch(`ack:${native.response_token}`);
  if (response?.request_id !== requestId || response?.ok !== true) {
    throw new Error(`test control refused ${action}`);
  }
  return response.result;
}
async function ready() {
  await until(() => document.querySelector("#host-status")?.textContent === "Ready", "Ready");
}
"""


_INITIAL_SCRIPT = _COMMON_JS + r"""
(async () => {
  await ready();
  await until(() => rows().length === 46, "46 seeded tasks");
  await control("checkpoint", "ready");
  clickNew();
  await until(() => rows().length === 47, "first new task");
  clickNew();
  await until(() => rows().length === 48, "second new task");
  const newest = rows().slice(0, 3).map((row) => row.querySelector(".nami-task-card__title")?.textContent);
  const blank = document.querySelector(".nami-work-panel__body")?.children.length === 0;
  clickNew();
  await until(() => document.querySelector("#host-status")?.textContent?.includes("could not be created"), "capacity refusal");
  const refusedCount = rows().length;
  await control("checkpoint", "capacity");
  clickSelect("Task 47");
  await until(() => selectedTitle() === "Task 47" && workTitle() === "Task 47", "older task selection");
  await until(() => selectedAppearanceSettled("Task 47"), "older task selected appearance");
  const olderAppearance = selectionAppearance("Task 47");
  clickSelect("Task 48");
  await until(() => selectedTitle() === "Task 48" && workTitle() === "Task 48", "newer task return");
  await until(() => selectedAppearanceSettled("Task 48") && selectionCleared("Task 47"), "transferred task selection appearance");
  const newerAppearance = selectionAppearance("Task 48");
  const olderSelectionCleared = selectionCleared("Task 47");
  clickClose("Task 48");
  await until(() => rows().length === 47 && rowByTitle("Task 48") === undefined, "successful close");
  await control("checkpoint", "basic_close");

  await control("arm_close_failure");
  clickClose("Task 47");
  await until(() => rowByTitle("Task 47")?.querySelector(".nami-task-rail__close")?.textContent === "Retry", "failed close recovery");
  const retainedAfterFailure = rows().length === 47 && statusFor("Task 47") === "Close did not finish. Retry.";
  clickClose("Task 47");
  await until(() => rows().length === 46 && rowByTitle("Task 47") === undefined, "close retry");
  await control("checkpoint", "retry");

  await control("arm_create_delay");
  clickNew();
  await untilAsync(async () => (await control("status")).create_waiting === true, "delayed create");
  clickSelect("Task 46");
  await control("release_create");
  await until(() => rows().length === 47, "delayed create return");
  const navigationStayed = selectedTitle() === "Task 46" && workTitle() === "Task 46";
  await control("checkpoint", "navigation");
  clickClose("Task 49");
  await until(() => rows().length === 46, "delayed create cleanup");
  await control("checkpoint", "navigation_cleanup");

  await control("record", { initial: { newest, blank, refusedCount, retainedAfterFailure, navigationStayed, olderAppearance, newerAppearance, olderSelectionCleared } });
  await control("checkpoint", "navigation_recorded");
  await control("arm_create_delay");
  await control("checkpoint", "reinjection_armed");
  clickNew();
  await untilAsync(async () => (await control("status")).create_waiting === true, "reinjection create");
  await control("checkpoint", "reinjection_wait");
  await control("set_stage", "reinjected");
  location.reload();
})()
"""


_REINJECTED_SCRIPT = _COMMON_JS + r"""
(async () => {
  await ready();
  await until(() => rows().length === 47, "reinjected task list");
  const evidence = {
    count: rows().length,
    newest: rows()[0]?.querySelector(".nami-task-card__title")?.textContent ?? null,
    selected: selectedTitle(),
    work: workTitle(),
  };
  clickClose("Task 47");
  await until(() => rows().length === 46, "reinjected task cleanup");
  await control("record", { reinjected: evidence });
  await control("start_busy");
  await control("set_stage", "busy");
  location.reload();
})()
"""


_BUSY_SCRIPT = _COMMON_JS + r"""
(async () => {
  await ready();
  await until(() => rows().length === 47 && statusFor("Task 47") === "In progress", "busy task");
  clickClose("Task 47");
  await until(() => statusFor("Task 47") === "Canceling and closing…", "pending cancellation");
  const pending = await control("status");
  const retainedPending = rows().length === 47 && rowByTitle("Task 47") !== undefined;
  await control("settle_busy");
  await until(() => rows().length === 46, "settled busy close");
  const settled = await control("status");
  await control("record", { busy: { pending, retainedPending, settled } });
  await control("arm_release_delay");
  await control("start_terminal");
  await control("set_stage", "terminal_first");
  location.reload();
})()
"""


_TERMINAL_FIRST_SCRIPT = _COMMON_JS + r"""
(async () => {
  await ready();
  await until(() => rows().length === 47 && statusFor("Task 47") === "Completed", "terminal presentation");
  await untilAsync(async () => (await control("status")).release_waiting === true, "blocked terminal release");
  const before = await control("status");
  await control("record", { terminal_first: { count: rows().length, status: statusFor("Task 47"), before } });
  await control("set_stage", "terminal_second");
  location.reload();
})()
"""


_TERMINAL_SECOND_SCRIPT = _COMMON_JS + r"""
(async () => {
  await ready();
  await until(() => rows().length === 47 && statusFor("Task 47") === "Completed", "terminal reinjection");
  await untilAsync(async () => (await control("status")).release_calls >= 2, "reconstructed terminal release");
  const retained = await control("status");
  await control("release_cleanup");
  await untilAsync(async () => (await control("status")).session_released === true, "terminal release");
  const released = await control("status");
  clickClose("Task 47");
  await until(() => rows().length === 46, "terminal explicit close");
  const closed = await control("status");
  const report = {
    terminal_second: {
      count_before_close: 47,
      status_before_close: "Completed",
      retained,
      released,
      closed,
    },
  };
  await control("record", report);
  const marker = document.createElement("p");
  marker.textContent = "Task shell gate complete";
  document.body.append(marker);
  await control("complete");
  return { complete: true };
})()
"""


class _Recorder:
    def __init__(self, paths: EvidencePaths) -> None:
        self._publisher = EvidencePublisher(paths)
        self._lock = threading.Lock()
        self._initial: str | None = None
        self._post_ready_failure: dict[str, str] | None = None
        self._data: dict[str, Any] = {
            "schema_version": 1,
            "phase": "starting",
            "startup_errors": [],
            "report": {},
        }

    def set(self, name: str, value: object) -> None:
        with self._lock:
            self._data[name] = value

    def merge_report(self, value: dict[str, object]) -> None:
        with self._lock:
            self._data["report"].update(value)

    def startup_error(self, _message: str) -> None:
        self.set("startup_errors", [{"type": "DesktopStartupError"}])

    def failure(self, stage: str, error: BaseException) -> None:
        if stage not in _FAILURE_STAGES:
            stage = "child"
        failure = {"stage": stage, "type": _error_type(error)}
        with self._lock:
            if self._initial == "failure":
                return
            if self._initial == "ready":
                if self._post_ready_failure is None:
                    self._post_ready_failure = failure
                return
            self._publisher.publish_failure({"failure": failure})
            self._initial = "failure"

    def complete(self) -> None:
        with self._lock:
            if self._initial is not None:
                return
            self._data["phase"] = "complete"
            self._publisher.publish_ready(dict(self._data))
            self._initial = "ready"

    @property
    def settled(self) -> bool:
        with self._lock:
            return self._initial is not None

    def finish(self, exit_code: int, *, host_returned: bool) -> None:
        with self._lock:
            payload: dict[str, object] = {
                "host_returned": host_returned,
                "exit_code": exit_code,
            }
            if self._post_ready_failure is not None:
                payload["post_ready_failure"] = dict(self._post_ready_failure)
            self._publisher.publish_final(payload)


class _Control:
    def __init__(self, recorder: _Recorder, source: Path, target: Path) -> None:
        self.recorder = recorder
        self.source = source
        self.target = target
        self.registry: object | None = None
        self.service: object | None = None
        self.stage = "initial"
        self.checkpoint = "ready"
        self.create_gate = threading.Event()
        self.create_waiting = threading.Event()
        self.delay_create = False
        self.fail_close_remaining = 0
        self.close_failures = 0
        self.busy_gate = threading.Event()
        self.busy_entered = threading.Event()
        self.busy_task_id: str | None = None
        self.busy_session_id: str | None = None
        self.terminal_task_id: str | None = None
        self.terminal_session_id: str | None = None
        self.release_gate = threading.Event()
        self.release_waiting = threading.Event()
        self.delay_release = False
        self.release_calls = 0
        self.observer_release_calls = 0
        self.original_deps: object | None = None

    def bind(self, registry: object) -> None:
        if self.registry is not None:
            return
        self.registry = registry
        self.service = registry._lifecycle
        service = self.service
        original_create = service.create_task_shell
        original_close_shell = service.close_task_shell
        original_release = service.release_task_session
        original_observer_release = service._observer.release

        def create_task_shell(_service: object, command_id: str, delivery_factory: object) -> object:
            result = original_create(command_id, delivery_factory)
            if self.delay_create:
                self.delay_create = False
                self.create_waiting.set()
                if not self.create_gate.wait(10):
                    raise RuntimeError("delayed create was not released")
                self.create_gate.clear()
                self.create_waiting.clear()
            return result

        def close_task_shell(_service: object, task_id: str) -> object:
            if self.fail_close_remaining > 0:
                self.fail_close_remaining -= 1
                self.close_failures += 1
                raise RuntimeError("injected cleanup failure")
            return original_close_shell(task_id)

        def release_task_session(_service: object, *args: object, **kwargs: object) -> object:
            self.release_calls += 1
            if self.delay_release:
                self.release_waiting.set()
                if not self.release_gate.wait(10):
                    raise RuntimeError("terminal cleanup was not released")
            return original_release(*args, **kwargs)

        def observer_release(session_id: str) -> object:
            self.observer_release_calls += 1
            return original_observer_release(session_id)

        service.create_task_shell = MethodType(create_task_shell, service)
        service.close_task_shell = MethodType(close_task_shell, service)
        service.release_task_session = MethodType(release_task_session, service)
        service._observer.release = observer_release

        for index in range(46):
            registry.create_task_shell(f"{1000 + index:032x}")

    def status(self) -> dict[str, object]:
        registry = self._registry()
        tasks = registry.list_tasks().tasks
        terminal = None
        session_released = None
        if self.terminal_task_id is not None:
            match = next((task for task in tasks if task.task_id == self.terminal_task_id), None)
            terminal = match is not None and match.session_state == "completed"
            session_released = None if match is None else match.session_released
        busy_state = None
        if self.busy_session_id is not None:
            try:
                busy_state = self._service().get_session(self.busy_session_id).state
            except self._session_not_found_type():
                busy_state = "retired"
        return {
            "task_count": len(tasks),
            "create_waiting": self.create_waiting.is_set(),
            "close_failures": self.close_failures,
            "busy_entered": self.busy_entered.is_set(),
            "busy_state": busy_state,
            "busy_present": any(task.task_id == self.busy_task_id for task in tasks),
            "terminal": terminal,
            "terminal_present": any(task.task_id == self.terminal_task_id for task in tasks),
            "release_waiting": self.release_waiting.is_set(),
            "session_released": session_released,
            "release_calls": self.release_calls,
            "observer_release_calls": self.observer_release_calls,
        }

    def command(self, payload: object) -> object:
        if type(payload) is not dict or set(payload) != {"action", "value"}:
            raise ValueError("test control payload is invalid")
        action = payload["action"]
        value = payload["value"]
        if action == "status":
            return self.status()
        if action == "record" and type(value) is dict:
            self.recorder.merge_report(value)
            return {"accepted": True}
        if action == "checkpoint" and value in {
            "ready", "capacity", "basic_close", "retry", "navigation",
            "navigation_cleanup", "navigation_recorded", "reinjection_armed",
            "reinjection_wait"
        }:
            self.checkpoint = value
            return {"accepted": True}
        if action == "set_stage" and value in {
            "reinjected", "busy", "terminal_first", "terminal_second"
        }:
            self.stage = value
            return {"accepted": True}
        if action == "arm_close_failure":
            self.fail_close_remaining = 4
            return {"accepted": True}
        if action == "arm_create_delay":
            self.create_gate.clear()
            self.create_waiting.clear()
            self.delay_create = True
            return {"accepted": True}
        if action == "release_create":
            self.create_gate.set()
            return {"accepted": True}
        if action == "start_busy":
            self._start_busy()
            return {"accepted": True}
        if action == "settle_busy":
            self.busy_gate.set()
            self._service()._runtime._deps = self.original_deps
            return {"accepted": True}
        if action == "start_terminal":
            self._start_terminal()
            return {"accepted": True}
        if action == "arm_release_delay":
            self.release_gate.clear()
            self.release_waiting.clear()
            self.delay_release = True
            return {"accepted": True}
        if action == "release_cleanup":
            self.delay_release = False
            self.release_gate.set()
            return {"accepted": True}
        if action == "complete":
            self.recorder.complete()
            return {"accepted": True}
        raise ValueError("unknown test control action")

    def _start_busy(self) -> None:
        service = self._service()
        self.original_deps = service._runtime._deps

        def blocked_scanner(root: object, ignores: object, ctx: object, **kwargs: object) -> object:
            self.busy_entered.set()
            while not self.busy_gate.wait(0.01):
                pass
            ctx.checkpoint()
            return self.original_deps.scanner(root, ignores, ctx, **kwargs)

        service._runtime._deps = replace(self.original_deps, scanner=blocked_scanner)
        started = self._registry().start_plan(
            str(self.source), str(self.target), deletion_policy=None,
            command_id=f"{2001:032x}", wire_intent=None,
        )
        self.busy_task_id = started.task_id
        self.busy_session_id = started.session_id
        if not self.busy_entered.wait(5):
            raise RuntimeError("busy scanner did not enter")

    def _start_terminal(self) -> None:
        started = self._registry().start_plan(
            str(self.source), str(self.target), deletion_policy=None,
            command_id=f"{2002:032x}", wire_intent=None,
        )
        self.terminal_task_id = started.task_id
        self.terminal_session_id = started.session_id

    def _registry(self) -> object:
        if self.registry is None:
            raise RuntimeError("task registry is unavailable")
        return self.registry

    def _service(self) -> object:
        if self.service is None:
            raise RuntimeError("service is unavailable")
        return self.service

    @staticmethod
    def _session_not_found_type() -> type[Exception]:
        from namisync.dispatcher import SessionNotFound

        return SessionNotFound


def _test_spec(handler: Callable[[object], object]) -> object:
    from namisync.interfaces.web.commands import (
        CommandAccess, CommandRetry, CommandSpec, CommandTimeout, FieldRequirement,
    )

    return CommandSpec(
        validate_payload=lambda payload: payload,
        handler=handler,
        access=CommandAccess.READ_ONLY,
        command_id=FieldRequirement.FORBIDDEN,
        revision=FieldRequirement.FORBIDDEN,
        timeout=CommandTimeout.INTERACTIVE,
        retry=CommandRetry.NONE,
    )


def _runtime_value(task: object) -> object:
    if task.IsFaulted or task.IsCanceled:
        raise RuntimeError("native CDP evaluation failed")
    envelope = json.loads(str(task.Result))
    if type(envelope) is not dict or "exceptionDetails" in envelope:
        raise RuntimeError("page task-shell probe failed")
    return envelope.get("result", {}).get("value")


def _begin_probe(window: object, recorder: _Recorder, control: _Control, retained: list[object]) -> None:
    from System import Action

    native = window.native
    if native.InvokeRequired:
        raise RuntimeError("task-shell probe left the UI thread")
    core = native.browser.webview.CoreWebView2
    starting_stage = control.stage
    script = {
        "initial": _INITIAL_SCRIPT,
        "reinjected": _REINJECTED_SCRIPT,
        "busy": _BUSY_SCRIPT,
        "terminal_first": _TERMINAL_FIRST_SCRIPT,
        "terminal_second": _TERMINAL_SECOND_SCRIPT,
    }[starting_stage]
    settings = json.dumps({"expression": script, "awaitPromise": True, "returnByValue": True})

    task = core.CallDevToolsProtocolMethodAsync("Runtime.evaluate", settings)

    def completed() -> None:
        def finish() -> None:
            try:
                value = _runtime_value(task)
                if starting_stage == "terminal_second" and value != {"complete": True}:
                    raise RuntimeError("final page probe returned invalid evidence")
            except BaseException as error:
                if control.stage == starting_stage or starting_stage == "terminal_second":
                    failure_stage = f"page_{starting_stage}"
                    if starting_stage == "initial":
                        failure_stage += f"_{control.checkpoint}"
                    recorder.failure(failure_stage, error)

        finish_action = Action(finish)
        retained.append(finish_action)
        native.BeginInvoke(finish_action)

    completion = Action(completed)
    retained.append(completion)
    task.GetAwaiter().OnCompleted(completion)


def _configure_probe(
    window: object,
    recorder: _Recorder,
    control: _Control,
    retained: list[object],
    original: Callable[..., object],
    *args: object,
    **kwargs: object,
) -> object:
    controller = original(window, *args, **kwargs)

    def loaded() -> None:
        from System import Action

        if control.stage == "reinjected":
            control.create_gate.set()

        def begin() -> None:
            try:
                _begin_probe(window, recorder, control, retained)
            except BaseException as error:
                recorder.failure("page_probe", error)

        action = Action(begin)
        retained.append(action)
        window.native.BeginInvoke(action)

    retained.append(loaded)
    window.events.loaded += loaded
    return controller


def _runtime_identity() -> dict[str, object]:
    import namisync

    return {
        "executable": str(Path(sys.executable).resolve()),
        "namisync_file": str(Path(namisync.__file__).resolve()),
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("namisync", "pywebview", "pythonnet")
        },
    }


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    return parser.parse_args()


def _run(arguments: argparse.Namespace, recorder: _Recorder) -> int:
    from namisync.interfaces.web import host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    control = _Control(recorder, arguments.source, arguments.target)
    retained: list[object] = []
    original = host._configure_window_appearance

    def extension(_document: object, registry: object) -> dict[str, object]:
        control.bind(registry)
        return {"task_shell_test_control": _test_spec(control.command)}

    recorder.set("runtime", _runtime_identity())
    with ExitStack() as stack:
        stack.enter_context(headed_command_extension(host, extension))
        stack.enter_context(
            patch.object(
                host,
                "_configure_window_appearance",
                lambda window, *args, **kwargs: _configure_probe(
                    window, recorder, control, retained, original, *args, **kwargs
                ),
            )
        )
        exit_code = host.run_desktop(
            AppPaths.from_root(arguments.data_dir),
            DesktopInstanceIdentity(arguments.mutex, arguments.title),
            startup_error=recorder.startup_error,
        )
    if not recorder.settled:
        recorder.failure("child", RuntimeError("host returned before task-shell evidence completed"))
    recorder.finish(exit_code, host_returned=True)
    return exit_code


def _error_type(error: BaseException) -> str:
    name = type(error).__name__
    return name if name in _FAILURE_TYPES else "Error"


def main() -> int:
    arguments = _parse_arguments()
    recorder = _Recorder(EvidencePaths(arguments.evidence_dir.resolve()))
    try:
        return _run(arguments, recorder)
    except BaseException as error:
        recorder.failure("child", error)
        recorder.finish(1, host_returned=False)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
