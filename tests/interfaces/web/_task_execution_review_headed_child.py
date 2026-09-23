"""Installed-wheel child for the short execution-review witness."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import sys
import threading
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Callable
from unittest.mock import patch

from _headed_cdp import NativeCdp, decode_png, failure_site
from _headed_evidence import EvidencePaths, EvidencePublisher
from _startup_test_support import headed_command_extension


_BYTES = b"NamiSync execution review fixture\r\n"
_COMMANDS = frozenset({
    "start_execution", "release_terminal_session", "get_plan_window",
    "get_execution_detail",
})
_GEOMETRY = frozenset({
    "rootFits", "tableUsable", "rowHeight", "detailVisible",
    "rowActivationFocused", "rowHit", "disclosureFocused",
    "disclosureVisible", "disclosureHit",
})
_WAIT_REVIEW_DIAGNOSTIC = frozenset({
    "stageExecuteReady", "stageCaptureReady", "nativeConfirmed",
    "mouseDownSeen", "mouseUpSeen", "clickSeen", "executeConnected",
    "executeDisabled", "executeFocused", "executePointerTarget",
    "reviewPending", "executionObserved", "releaseObserved",
    "windowObserved", "reviewReady", "phaseFailureObserved",
})


class _ExecutionReviewPhase:
    """One bounded owner for the real plan -> execution -> review transition."""

    def __init__(self, source: Path, target: Path) -> None:
        self.source = source
        self.target = target
        self.lock = threading.Lock()
        self.registry: object | None = None
        self.plan: dict[str, object] | None = None
        self.execution: dict[str, object] | None = None
        self.release: dict[str, object] | None = None
        self.window: dict[str, object] | None = None
        self.detail: dict[str, object] | None = None
        self.detail_calls = 0
        self.ordinal = 0
        self.failure: str | None = None
        self.capture = "waiting"
        self.pre_identity: dict[str, object] | None = None
        self.post_identity: dict[str, object] | None = None

    def bind(self, registry: object) -> None:
        self.registry = registry
        self.source.mkdir(parents=True, exist_ok=True)
        self.target.mkdir(parents=True, exist_ok=True)
        if any(self.source.iterdir()) or any(self.target.iterdir()):
            raise RuntimeError("execution review roots must start empty")
        (self.source / "one.txt").write_bytes(_BYTES)
        started = registry.start_plan(
            str(self.source), str(self.target), deletion_policy=None,
            command_id="a" * 32, wire_intent=None,
        )
        self.plan = {
            "task_id": started.task_id,
            "request_id": started.request_id,
            "session_id": started.session_id,
            "task_label": None,
        }

    def bind_visible_label(self, label: object) -> None:
        with self.lock:
            tasks = self.registry.list_tasks().tasks
            if (self.plan is None or len(tasks) != 1
                    or tasks[0].task_id != self.plan["task_id"]
                    or type(label) is not str or not label or len(label) > 128):
                raise RuntimeError("visible task does not match seeded registry task")
            self.plan["task_label"] = label

    def failure_identity(self) -> dict[str, object]:
        with self.lock:
            result = {}
            for name, record in (("plan", self.plan), ("execution", self.execution),
                                 ("window", self.window), ("detail", self.detail)):
                if record is None:
                    continue
                fields = {}
                for key in ("task_id", "request_id", "session_id", "operation_id"):
                    value = record.get(key)
                    if type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value):
                        fields[key] = value
                for key in ("view_revision", "execution_revision"):
                    value = record.get(key)
                    if type(value) is int and 0 <= value <= 9007199254740991:
                        fields[key] = value
                if fields:
                    result[name] = fields
            return result

    def wrap(self, commands: object) -> object:
        from namisync.interfaces.web.commands import CommandSpec

        wrapped = dict(commands)
        for name in _COMMANDS:
            spec = wrapped[name]
            if type(spec) is not CommandSpec:
                raise TypeError("observed command is not an exact CommandSpec")
            wrapped[name] = replace(spec, handler=self._observe(name, spec.handler))
        return wrapped

    def _observe(
        self, name: str, original: Callable[[object], object],
    ) -> Callable[[object], object]:
        def invoke(payload: object) -> object:
            with self.lock:
                self.ordinal += 1
                admitted = self.ordinal
            result = original(payload)
            with self.lock:
                self.ordinal += 1
                if self.failure is not None:
                    return result
                try:
                    self._record_locked(name, admitted, self.ordinal, payload, result)
                except BaseException as error:
                    self.failure = type(error).__name__
            return result
        return invoke

    def record(
        self, name: str, admitted: int, completed: int,
        payload: object, result: object,
    ) -> None:
        with self.lock:
            self._record_locked(name, admitted, completed, payload, result)

    def _record_locked(
        self, name: str, admitted: int, completed: int,
        payload: object, result: object,
    ) -> None:
        if self.plan is None or payload.task_id != self.plan["task_id"]:
            return
        if name == "start_execution":
            if payload.request_id != self.plan["request_id"]:
                raise ValueError("execution did not use the seeded plan")
            if result.task_id != self.plan["task_id"]:
                raise ValueError("execution response changed task identity")
            self.execution = {
                "admitted": admitted, "completed": completed,
                "request_id": result.request_id, "session_id": result.session_id,
            }
            return
        if name == "get_execution_detail":
            self.detail_calls += 1
            if self.detail_calls != 1:
                raise ValueError("execution detail was requested more than once")
            if self.window is None or (
                payload.operation_id != self.window["operation_id"]
                or payload.expected_execution_revision != self.window["execution_revision"]
                or result.get("disposition") != "current"
                or result.get("operation_id") != payload.operation_id
                or result.get("execution_revision") != payload.expected_execution_revision
            ):
                raise ValueError("execution detail does not match retained window")
            self.detail = {
                "admitted": admitted, "completed": completed,
                "operation_id": result["operation_id"],
                "execution_revision": result["execution_revision"],
                "operation_path": result["operation"].path,
            }
            return
        if self.execution is None:
            return
        if name == "release_terminal_session":
            if payload.session_id != self.execution["session_id"]:
                raise ValueError("released session does not match execution")
            if result.task_id != self.plan["task_id"] or result.session_id != payload.session_id:
                raise ValueError("release response does not match execution")
            if self.release is None:
                self.release = {
                    "admitted": admitted, "completed": completed,
                    "session_id": result.session_id,
                }
            return
        if name == "get_plan_window" and self.release is not None:
            execution = result.get("execution") if type(result) is dict else None
            rows = result.get("rows") if type(result) is dict else None
            visible_row = next((
                row for row in rows
                if type(row) is dict and type(row.get("operation_id")) is str
            ), None) if type(rows) is list else None
            operation = visible_row.get("operation_id") if visible_row is not None else None
            candidate = {
                "admitted": admitted, "completed": completed,
                "view_revision": result.get("view_revision"),
                "execution_revision": execution.get("execution_revision") if type(execution) is dict else None,
                "operation_id": operation,
                "row_display": visible_row.get("display") if visible_row is not None else None,
            }
            if (
                self.execution["completed"] < self.release["admitted"]
                and
                admitted > self.release["completed"]
                and result.get("disposition") == "current"
                and result.get("view_revision") == payload.expected_revision
                and type(execution) is dict
                and execution.get("session_id") == self.execution["session_id"]
                and type(execution.get("execution_revision")) is int
                and operation is not None
                and type(candidate["row_display"]) is str
            ):
                identity = ("view_revision", "execution_revision", "operation_id")
                if self.window is not None and any(
                    candidate[key] != self.window[key] for key in identity
                ):
                    raise ValueError("conflicting retained execution window")
                if self.window is None:
                    self.window = candidate
            return

    def _session_released_locked(self) -> bool:
        if self.registry is None or self.execution is None:
            return False
        try:
            self.registry._lifecycle.get_session(self.execution["session_id"])
        except self._session_not_found_type():
            return True
        return False

    @staticmethod
    def _session_not_found_type() -> type[Exception]:
        from namisync.dispatcher import SessionNotFound
        return SessionNotFound

    def review_ready(self) -> bool:
        with self.lock:
            return self._review_ready_locked()

    def _review_ready_locked(self) -> bool:
        if self.registry is None or self.plan is None or self.execution is None:
            return False
        task = next((
            task for task in self.registry.list_tasks().tasks
            if task.task_id == self.plan["task_id"]
        ), None)
        return bool(
            self.failure is None and self.release and self.window
            and task is not None and task.session_id == self.execution["session_id"]
            and task.session_released and self._session_released_locked()
            and self.execution["completed"] < self.release["admitted"]
            and self.release["completed"] < self.window["admitted"]
        )

    def capture_ready(self) -> bool:
        with self.lock:
            return bool(
                self._review_ready_locked() and self.detail is not None
                and self.detail_calls == 1
                and self.window["completed"] < self.detail["admitted"]
            )

    def set_capture(self, expected: str, next_phase: str) -> None:
        with self.lock:
            if self.capture != expected:
                raise RuntimeError("execution review capture phase is invalid")
            self.capture = next_phase

    def set_identity(self, phase: str, value: object) -> None:
        if phase not in {"pre", "post"} or type(value) is not dict:
            raise RuntimeError("execution review identity is invalid")
        with self.lock:
            expected = self._expected_identity_locked()
            if value != expected:
                raise RuntimeError("execution review identity does not match receipts")
            if phase == "pre":
                if self.capture != "waiting" or self.pre_identity is not None:
                    raise RuntimeError("execution review PRE identity is out of order")
                self.pre_identity = dict(value)
            else:
                if self.capture != "decoded" or self.pre_identity != value:
                    raise RuntimeError("execution review POST identity changed")
                self.post_identity = dict(value)

    def _expected_identity_locked(self) -> dict[str, object]:
        if self.plan is None or self.execution is None or self.window is None or self.detail is None:
            raise RuntimeError("execution review receipts are incomplete")
        return {
            "selectedTask": self.plan["task_label"],
            "runId": self.execution["request_id"],
            "sessionId": self.execution["session_id"],
            "executionRevision": self.detail["execution_revision"],
            "rowName": self.window["row_display"],
            "operationPath": self.detail["operation_path"],
            "rowHighlighted": True, "detailVisible": True,
            "disclosureVisible": True, "disclosureExpanded": True,
            "operationFactPresent": True, "recordingFactPresent": True,
            "evidenceFactPresent": True, "operationIdVisible": False,
        }

    def verify_files(self) -> None:
        if {path.name for path in self.source.iterdir()} != {"one.txt"}:
            raise RuntimeError("source fixture membership changed")
        if {path.name for path in self.target.iterdir()} != {"one.txt"}:
            raise RuntimeError("target fixture membership is invalid")
        if (self.source / "one.txt").read_bytes() != _BYTES:
            raise RuntimeError("source fixture bytes changed")
        if (self.target / "one.txt").read_bytes() != _BYTES:
            raise RuntimeError("target fixture bytes do not match")

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            return deepcopy({
                "plan": self.plan, "execution": self.execution, "release": self.release,
                "window": self.window, "detail": self.detail,
                "detail_calls": self.detail_calls, "failure": self.failure,
                "capture": self.capture, "pre_identity": self.pre_identity,
                "post_identity": self.post_identity,
                "review_ready": self._review_ready_locked(),
            })


def _test_spec(handler: Callable[[object], object]) -> object:
    from namisync.interfaces.web.commands import (
        CommandAccess, CommandRetry, CommandSpec, CommandTimeout, FieldRequirement,
    )
    return CommandSpec(
        validate_payload=_validate_empty, handler=handler,
        access=CommandAccess.READ_ONLY, command_id=FieldRequirement.FORBIDDEN,
        revision=FieldRequirement.FORBIDDEN, timeout=CommandTimeout.INTERACTIVE,
        retry=CommandRetry.NONE,
    )


def _validate_empty(value: object) -> None:
    if type(value) is not dict or value:
        raise ValueError("execution review control requires an empty payload")
    return None


class _Recorder:
    def __init__(self, paths: EvidencePaths, driver: Path) -> None:
        self.publisher = EvidencePublisher(paths)
        self.driver = driver
        self.lock = threading.Lock()
        self.settled = False
        self.phase: _ExecutionReviewPhase | None = None

    def complete(self, report: dict[str, object]) -> None:
        with self.lock:
            if self.settled:
                return
            self.publisher.publish_ready({"report": report, "runtime": _runtime_identity()})
            self.settled = True

    def fail(
        self, stage: str, reason: str,
        diagnostic: dict[str, bool] | None = None,
    ) -> None:
        with self.lock:
            if self.settled:
                return
            payload = {"stage": stage, "reason": reason,
                       "identity": self.phase.failure_identity() if self.phase else {}}
            if diagnostic is not None:
                if set(diagnostic) != _WAIT_REVIEW_DIAGNOSTIC or any(
                    type(value) is not bool for value in diagnostic.values()
                ):
                    raise RuntimeError("execution review diagnostic is invalid")
                payload["diagnostic"] = dict(diagnostic)
            self.publisher.publish_failure(payload)
            self.driver.write_text(
                json.dumps(payload, sort_keys=True),
                encoding="utf-8",
            )
            self.settled = True

    def finish(self, code: int, returned: bool) -> None:
        self.publisher.publish_final({"exit_code": code, "host_returned": returned})


_PAGE = r"""
(async () => {
  const until = async (fn, label) => {
    for (let i = 0; i < 1200; i += 1) {
      const value = await fn();
      if (value) return value;
      await new Promise((resolve) => setTimeout(resolve, 25));
    }
    throw new Error(label);
  };
  let sequence = 0;
  const control = async () => {
    sequence += 1;
    const requestId = sequence.toString(16).padStart(32, '0');
    const api = window.pywebview?.api;
    if (typeof api?.dispatch !== 'function') throw new Error('native bridge unavailable');
    const native = await api.dispatch(JSON.stringify({
      schema_version: 1, request_id: requestId,
      command: 'execution_review_test_control', payload: {},
    }));
    if (native === null || typeof native !== 'object') throw new Error('invalid native response');
    const response = JSON.parse(JSON.stringify(native.response));
    if (native.response_token !== null) await api.dispatch(`ack:${native.response_token}`);
    if (response?.request_id !== requestId || response?.ok !== true) throw new Error('test control refused');
    return response.result;
  };
  const card = await until(() => document.querySelector('.nami-task-rail__row .nami-task-card'), 'task');
  card.click();
  const review = await until(() => document.querySelector('.nami-plan-review'), 'review');
  const execute = await until(() => {
    const button = review.querySelector('[data-action="execute"]');
    return button instanceof HTMLButtonElement && !button.disabled ? button : null;
  }, 'execute');
  await until(() => document.hasFocus(), 'document-focus');
  execute.focus();
  await new Promise((resolve) => requestAnimationFrame(resolve));
  await new Promise((resolve) => requestAnimationFrame(resolve));
  const rect = execute.getBoundingClientRect();
  const point = {x:(rect.left+rect.right)/2,y:(rect.top+rect.bottom)/2};
  if (document.activeElement !== execute || document.elementFromPoint(point.x, point.y) !== execute) {
    throw new Error('Execute is not the native pointer target');
  }
  const nativeInput = {mouseDownSeen:false, mouseUpSeen:false, clickSeen:false};
  execute.addEventListener('mousedown', (event) => { nativeInput.mouseDownSeen ||= event.isTrusted; });
  execute.addEventListener('mouseup', (event) => { nativeInput.mouseUpSeen ||= event.isTrusted; });
  execute.addEventListener('click', (event) => { nativeInput.clickSeen ||= event.isTrusted; });
  window.__executionReviewNativeInput = nativeInput;
  window.__executionReviewExecutePoint = {point, taskLabel: card.dataset.taskLabel};
  window.__executionReviewStage = 'execute-ready';
  await until(() => window.__executionReviewNativeConfirmed === true, 'native-confirmation');
  await until(() => nativeInput.clickSeen === true, 'trusted-native-click');
  await until(async () => (await control()).review_ready === true, 'released execution review');
  const disclosure = review.querySelector('[data-action="toggle-execution-details"]');
  if (!(disclosure instanceof HTMLButtonElement)) throw new Error('card disclosure unavailable');
  if (disclosure.getAttribute('aria-expanded') !== 'true') disclosure.click();
  const row = await until(() => review.querySelector('.nami-plan-review__rows [data-node-id]'), 'operation-row');
  const focusedNodeId = row.dataset.nodeId;
  row.click();
  const detail = await until(() => {
    const value = review.querySelector('.nami-plan-review__detail');
    return value instanceof HTMLElement && !value.hidden && !value.textContent.includes('Loading')
      && [...value.querySelectorAll('dt')].some(term => term.textContent === 'Path') ? value : null;
  }, 'detail');
  const rows = review.querySelector('.nami-plan-review__rows');
  const adoptedRow = await until(() => [...rows.querySelectorAll('[data-node-id]')]
    .find(candidate => candidate.dataset.nodeId === focusedNodeId
      && candidate.dataset.highlighted === 'true' && candidate.isConnected), 'adopted-row');
  const rowActivationFocused = document.activeElement === adoptedRow;
  const rowRect = adoptedRow.getBoundingClientRect();
  const rowTarget = document.elementFromPoint(rowRect.left + 48, (rowRect.top + rowRect.bottom) / 2);
  disclosure.focus();
  const content = review.querySelector('.nami-plan-review__content');
  const table = review.querySelector('.nami-plan-review__table-card');
  const rb=review.getBoundingClientRect(), cb=content.getBoundingClientRect();
  const tb=table.getBoundingClientRect(), db=detail.getBoundingClientRect(), xb=disclosure.getBoundingClientRect();
  const hit=document.elementFromPoint((xb.left+xb.right)/2,(xb.top+xb.bottom)/2);
  window.__executionReviewGeometry = {
    rootFits: review.scrollHeight <= review.clientHeight + 1 && cb.bottom <= rb.bottom + 1,
    tableUsable: tb.height > 0 && rows.clientHeight >= 24,
    rowHeight: getComputedStyle(rows.querySelector('[data-node-id]')).height,
    rowActivationFocused,
    rowHit: rowTarget !== null && adoptedRow.contains(rowTarget),
    detailVisible: detail.closest('[hidden]') === null && db.width > 0 && db.height > 0
      && db.bottom > 0 && db.top < innerHeight,
    disclosureFocused: document.activeElement === disclosure,
    disclosureVisible: xb.width > 0 && xb.height > 0 && xb.top >= rb.top - 1
      && xb.bottom <= rb.bottom + 1,
    disclosureHit: hit === disclosure || disclosure.contains(hit),
  };
  window.__executionReviewStage = 'capture-ready';
  await until(() => window.__executionReviewCaptureAck === true, 'capture-ack');
  return {geometry: window.__executionReviewGeometry};
})()
"""


def _drive(window: object, phase: _ExecutionReviewPhase, recorder: _Recorder, retained: list[object], screenshot: Path) -> None:
    native = window.native
    core = native.browser.webview.CoreWebView2
    failed = False

    def fail(error: BaseException, _task: object | None, step: str, _method: str) -> None:
        nonlocal failed
        if failed:
            return
        failed = True
        recorder.fail(step, type(error).__name__)
        recorder.driver.with_name("runtime-failure-site.json").write_text(
            json.dumps(failure_site(_task), sort_keys=True), encoding="utf-8",
        )

    cdp = NativeCdp(native, core, retained, fail)
    decoded_dimensions: tuple[int, int] | None = None

    wait_execute = r"""(async()=>{for(let i=0;i<1200;i++){if(window.__executionReviewStage==='execute-ready')return window.__executionReviewExecutePoint;await new Promise(r=>setTimeout(r,25));}throw new Error('execute');})()"""
    wait_capture = r"""
    (async () => {
      for (let i = 0; i < 1200; i += 1) {
        if (window.__executionReviewStage === 'capture-ready') return true;
        await new Promise((resolve) => setTimeout(resolve, 25));
      }
      const review = document.querySelector('.nami-plan-review');
      const execute = review?.querySelector('[data-action="execute"]');
      const point = window.__executionReviewExecutePoint?.point;
      const input = window.__executionReviewNativeInput ?? {};
      const state = await (async () => {
        try {
          const api = window.pywebview?.api;
          if (typeof api?.dispatch !== 'function') return null;
          const requestId = 'f'.repeat(32);
          const native = await api.dispatch(JSON.stringify({
            schema_version: 1,
            request_id: requestId,
            command: 'execution_review_test_control',
            payload: {},
          }));
          if (native?.response_token !== null) {
            await api.dispatch('ack:' + native.response_token);
          }
          return native?.response?.ok === true ? native.response.result : null;
        } catch {
          return null;
        }
      })();
      return {
        stageExecuteReady: window.__executionReviewStage === 'execute-ready',
        stageCaptureReady: window.__executionReviewStage === 'capture-ready',
        nativeConfirmed: window.__executionReviewNativeConfirmed === true,
        mouseDownSeen: input.mouseDownSeen === true,
        mouseUpSeen: input.mouseUpSeen === true,
        clickSeen: input.clickSeen === true,
        executeConnected: execute?.isConnected === true,
        executeDisabled: execute?.disabled === true,
        executeFocused: document.activeElement === execute,
        executePointerTarget: point !== undefined
          && document.elementFromPoint(point.x, point.y) === execute,
        reviewPending: typeof review?.dataset.pending === 'string'
          && review.dataset.pending !== '',
        executionObserved: state?.execution !== null && state?.execution !== undefined,
        releaseObserved: state?.release !== null && state?.release !== undefined,
        windowObserved: state?.window !== null && state?.window !== undefined,
        reviewReady: state?.review_ready === true,
        phaseFailureObserved: state?.failure !== null && state?.failure !== undefined,
      };
    })()
    """

    def identity_expression() -> str:
        snapshot = phase.snapshot()
        execution, detail = snapshot["execution"], snapshot["detail"]
        if type(execution) is not dict or type(detail) is not dict:
            raise RuntimeError("execution review identity receipts are incomplete")
        constants = json.dumps({
            "runId": execution["request_id"],
            "sessionId": execution["session_id"],
            "executionRevision": detail["execution_revision"],
        })
        return rf"""(()=>{{
          const d=document.querySelector('.nami-plan-review__detail');
          const toggle=document.querySelector('[data-action="toggle-execution-details"]');
          const row=document.querySelector('.nami-plan-review__rows [aria-selected="true"]');
          const terms=[...d.querySelectorAll('dt')];
          const fact=(label)=>terms.find(term=>term.textContent===label)?.nextElementSibling?.textContent??null;
          const selected=document.querySelector('.nami-task-card[aria-current="page"]');
          const bounds=toggle.getBoundingClientRect();
          return {{selectedTask:selected?.dataset.taskLabel??null,...{constants},
            rowName:row?.querySelector('.nami-file-row__name-text')?.textContent??null,
            operationPath:fact('Path'),rowHighlighted:row?.dataset.highlighted==='true',
            detailVisible:d.hidden===false,disclosureVisible:bounds.width>0&&bounds.height>0,
            disclosureExpanded:toggle.getAttribute('aria-expanded')==='true',
            operationFactPresent:!!fact('Operation'),recordingFactPresent:!!fact('Operation recording'),
            evidenceFactPresent:!!fact('Stored evidence'),
            operationIdVisible:terms.some(term=>term.textContent==='Operation id')
          }};
        }})()"""

    def capture_ready(value: object) -> None:
        if type(value) is dict:
            recorder.fail("wait-review", "TimeoutError", value)
            return
        if not phase.capture_ready():
            raise RuntimeError("production execution receipts are incomplete")
        phase.verify_files()
        cdp.evaluate(identity_expression(), before_capture, "pre-identity")

    def before_capture(value: object) -> None:
        phase.set_identity("pre", value)
        phase.set_capture("waiting", "persisting")
        cdp.capture(screenshot, decoded, "capture")

    def decoded() -> None:
        nonlocal decoded_dimensions
        dimensions = decode_png(screenshot)
        decoded_dimensions = dimensions
        phase.set_capture("persisting", "decoded")
        cdp.evaluate(identity_expression(), lambda value: rechecked(value, dimensions), "post-identity")

    def rechecked(value: object, dimensions: tuple[int, int]) -> None:
        phase.set_identity("post", value)
        phase.set_capture("decoded", "rechecked")
        cdp.evaluate("window.__executionReviewCaptureAck=true;true", lambda ack: acknowledged(ack, dimensions), "ack")

    def acknowledged(value: object, dimensions: tuple[int, int]) -> None:
        if value is not True:
            raise RuntimeError("capture acknowledgement failed")
        phase.set_capture("rechecked", "acknowledged")

    def finished(value: object) -> None:
        dimensions = decoded_dimensions
        if dimensions is None:
            raise RuntimeError("page completed before native capture decode")
        if type(value) is not dict or set(value.get("geometry", {})) != _GEOMETRY:
            raise RuntimeError("execution geometry evidence is invalid")
        recorder.complete({"geometry": value["geometry"], "dimensions": list(dimensions), "phase": phase.snapshot()})

    def confirmed(_value: object) -> None:
        cdp.evaluate("window.__executionReviewNativeConfirmed=true;true", lambda _v: cdp.evaluate(wait_capture, capture_ready, "wait-review"), "confirm-observed")

    def execute(point: object) -> None:
        if type(point) is not dict:
            raise RuntimeError("execute point missing")
        phase.bind_visible_label(point["taskLabel"])
        point = point["point"]
        cdp.call("Input.dispatchMouseEvent", {"type":"mousePressed","button":"left","buttons":1,"clickCount":1,**point}, lambda _v: cdp.call("Input.dispatchMouseEvent", {"type":"mouseReleased","button":"left","buttons":0,"clickCount":1,**point}, confirmed, "execute-up"), "execute-down")

    cdp.evaluate(_PAGE, finished, "page")
    cdp.evaluate(wait_execute, execute, "wait-execute")


def _runtime_identity() -> dict[str, object]:
    import namisync
    return {"executable": str(Path(sys.executable).resolve()), "namisync_file": str(Path(namisync.__file__).resolve()), "versions": {name: importlib.metadata.version(name) for name in ("namisync", "pywebview", "pythonnet")}}


def _run(arguments: argparse.Namespace, recorder: _Recorder) -> int:
    from namisync.interfaces.web import host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    phase = _ExecutionReviewPhase(arguments.source, arguments.target)
    recorder.phase = phase
    retained: list[object] = []
    original = host._configure_window_appearance
    original_commands = host._production_commands

    def commands(**kwargs: object) -> object:
        return phase.wrap(original_commands(**kwargs))

    def extension(_document: object, registry: object) -> dict[str, object]:
        phase.bind(registry)
        return {"execution_review_test_control": _test_spec(lambda _payload: phase.snapshot())}

    def configure(window: object, *args: object, **kwargs: object) -> object:
        controller = original(window, *args, **kwargs)
        def loaded() -> None:
            from System import Action
            def begin() -> None:
                if arguments.large_window:
                    scale = window.native.DeviceDpi / 96
                    window.native.Width += int(160 * scale)
                    window.native.Height += int(100 * scale)
                window.native.Activate()
                window.native.browser.webview.Focus()
                _drive(window, phase, recorder, retained, arguments.screenshot)
            action = Action(begin)
            retained.append(action)
            window.native.BeginInvoke(action)
        retained.append(loaded)
        window.events.loaded += loaded
        return controller

    with ExitStack() as stack:
        stack.enter_context(patch.object(host, "_production_commands", commands))
        stack.enter_context(headed_command_extension(host, extension))
        stack.enter_context(patch.object(host, "_configure_window_appearance", configure))
        code = host.run_desktop(AppPaths.from_root(arguments.data_dir), DesktopInstanceIdentity(arguments.mutex, arguments.title), startup_error=lambda _message: recorder.fail("startup", "DesktopStartupError"))
    if not recorder.settled:
        recorder.fail("child", "HostReturned")
    recorder.finish(code, True)
    return code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--screenshot", required=True, type=Path)
    parser.add_argument("--driver", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--large-window", action="store_true")
    arguments = parser.parse_args()
    recorder = _Recorder(
        EvidencePaths(arguments.evidence_dir.resolve()), arguments.driver.resolve(),
    )
    try:
        return _run(arguments, recorder)
    except BaseException as error:
        recorder.fail("child", type(error).__name__)
        recorder.finish(1, False)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
