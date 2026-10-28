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
from _headed_native import foreground_window_handle, wait_for_foreground
from _startup_test_support import headed_command_extension


_BYTES = b"NamiSync execution review fixture\r\n"
_COMMANDS = frozenset({
    "start_execution", "release_terminal_session", "get_plan_window",
    "mutate_plan_highlight", "get_execution_detail",
    "open_inventory_view", "get_inventory_window",
    "control_execution", "refresh_inventory", "start_inventory_integrity",
    "set_inventory_selection", "control_integrity", "close_task",
})
_GEOMETRY = frozenset({
    "rootFits", "tableUsable", "rowHeight", "detailVisible",
    "rowActivationFocused", "rowHit", "disclosureFocused",
    "disclosureVisible", "disclosureHit",
})
_RETENTION = frozenset({
    "sameRenderer", "sameList", "planReturned", "taskRetained",
    "rowRetained", "scrollRetained",
    "detailRetained", "selectionRetained", "keyboardRetained", "followRetained",
})
_ACTIONS = frozenset({
    "copiedActionVisible", "copiedResultVisible", "copiedRowVisible",
    "fallbackVisible", "ordinaryResultVisible", "ordinaryRowVisible",
    "closedBoth", "refreshSubmittedOnce",
})
_WAIT_REVIEW_DIAGNOSTIC = frozenset({
    "stageExecuteReady", "stageCaptureReady", "nativeConfirmed",
    "mouseDownSeen", "mouseUpSeen", "clickSeen", "executeConnected",
    "executeDisabled", "executeFocused", "executePointerTarget",
    "reviewPending", "executionObserved", "releaseObserved",
    "windowObserved", "reviewReady", "phaseFailureObserved",
    "scrollObserved", "visibleFixtureFileRowObserved",
    "rowClickDispatched", "detailObserved",
    "clickedRowConnectedBeforeClick", "clickedRowConnectedAfterClick",
    "rowClickEventObserved", "highlightMutationAdmitted",
    "highlightMutationCompleted", "postHighlightWindowAdmitted",
    "postHighlightWindowCompleted", "currentMatchingRowHighlightedAtTimeout",
    "originalClickedRowConnectedAtTimeout", "executionDetailAdmitted",
    "executionDetailCompleted",
})
_CAPTURE_READINESS_DIAGNOSTIC = frozenset({
    "recordingHealthy", "planObserved", "executionObserved",
    "originalReleaseObserved", "windowObserved", "originalLifecycleReleased",
    "executionBeforeOriginalRelease", "originalReleaseBeforeWindow",
    "detailObserved", "detailOperationMatches", "detailRevisionMatches",
    "ordinaryObserved", "ordinaryReleaseObserved", "ordinaryBeforeRelease",
    "ordinaryLifecycleReleased", "taskPresent", "currentSessionIsOrdinary",
    "currentSessionReleased", "captureReady",
})
_SELECTION_TIMEOUT_BOOLS = frozenset({
    "refreshObserved", "refreshReleaseObserved", "currentInventoryObserved",
    "phaseFailureObserved", "verifyVisible", "fallbackLabelCurrent",
    "fallbackVisible", "fallbackDisabled", "fixtureRowPresent", "checkboxConnected",
    "checkboxDisabled", "checkboxChecked", "checkboxHittable",
})
_SELECTION_TIMEOUT_DOM_BOOLS = frozenset({
    "verifyVisible", "fallbackLabelCurrent", "fallbackVisible", "fallbackDisabled",
    "fixtureRowPresent", "checkboxConnected", "checkboxDisabled", "checkboxChecked",
    "checkboxHittable",
})
_BLOCKED_STAGES = frozenset({
    "exact-close", "blocked-execution", "blocked-execution-release", "blocked-verify-pane",
    "blocked-initial-readiness", "blocked-refresh", "blocked-handoff",
    "blocked-fallback-control", "blocked-row", "blocked-checkbox", "selection-ready",
})
_SCROLL_DIAGNOSTIC_POINTS = frozenset({
    "original", "beforeVerify", "hiddenAfterVerify", "immediateReturn", "afterFrames",
})
_SCROLL_INTERACTION_POINTS = frozenset({
    "preClick", "immediateAfterClick", "firstDisconnection", "afterDetail",
})
_SCROLL_INTERACTION_FACT = frozenset({
    "scrollTop", "clientHeight", "scrollHeight", "listTop", "listBottom",
    "rowTop", "rowBottom", "originalRowConnected", "currentRowConnected",
    "rowFullyVisible", "rowHitOwned", "activeMatchesClickedNode",
    "sameReview", "sameList",
})
_PRECLICK_DIAGNOSTIC = frozenset({
    "executeFocused", "pointInsideViewport", "hitPresent",
    "hitExecute", "hitDescendant", "executeConnected", "reviewLoaded",
})


class _ExecutionReviewPhase:
    """One bounded owner for the real plan -> execution -> review transition."""

    def __init__(
        self, source: Path, target: Path, *, file_count: int = 1,
        branch: str = "exact",
    ) -> None:
        if file_count < 1 or branch not in {"exact", "blocked"}:
            raise ValueError("execution review branch is invalid")
        self.source = source
        self.target = target
        self.branch = branch
        self.fixture = {
            ("one.txt" if file_count == 1 else f"file-{index:02d}.txt"):
            (_BYTES if file_count == 1 else _BYTES + f"{index:02d}\r\n".encode("ascii"))
            for index in range(file_count)
        }
        self.lock = threading.Lock()
        self.registry: object | None = None
        self.plan: dict[str, object] | None = None
        self.execution: dict[str, object] | None = None
        self.release: dict[str, object] | None = None
        self.window: dict[str, object] | None = None
        self.detail: dict[str, object] | None = None
        self.highlight_mutation: dict[str, object] | None = None
        self.post_highlight_window: dict[str, object] | None = None
        self.execution_detail_attempt: dict[str, object] | None = None
        self.inventory_open: dict[str, object] | None = None
        self.inventory_window: dict[str, object] | None = None
        self.refresh: dict[str, object] | None = None
        self.refresh_admissions = 0
        self.selection: dict[str, object] | None = None
        self.ordinary: dict[str, object] | None = None
        self.controls: list[dict[str, object]] = []
        self.auxiliary_releases: list[dict[str, object]] = []
        self.close: dict[str, object] | None = None
        self.worker_entered = threading.Event()
        self.worker_release = threading.Event()
        self.ordinal = 0
        self.failure: str | None = None
        self.failure_command: str | None = None
        self.pre_identity: dict[str, object] | None = None
        self.post_identity: dict[str, object] | None = None
        self.capture_receipt: tuple[object, ...] | None = None
        self.capture_complete = False

    def bind(self, registry: object) -> None:
        self.registry = registry
        self.source.mkdir(parents=True, exist_ok=True)
        self.target.mkdir(parents=True, exist_ok=True)
        if any(self.source.iterdir()) or any(self.target.iterdir()):
            raise RuntimeError("execution review roots must start empty")
        for name, contents in self.fixture.items():
            (self.source / name).write_bytes(contents)
        started = registry.start_plan(
            str(self.source), str(self.target), deletion_policy=None,
            command_id=("a" if self.branch == "exact" else "b") * 32,
            wire_intent=None,
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
            task = next((item for item in tasks if self.plan is not None
                         and item.task_id == self.plan["task_id"]), None)
            if (self.plan is None or task is None
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
                self._record_admission_locked(name, admitted, payload)
            result = original(payload)
            with self.lock:
                self.ordinal += 1
                if self.failure is not None:
                    return result
                try:
                    self._record_locked(name, admitted, self.ordinal, payload, result)
                except BaseException as error:
                    self.failure = type(error).__name__
                    self.failure_command = name
            return result
        return invoke

    def _record_admission_locked(self, name: str, admitted: int, payload: object) -> None:
        if self.plan is None or getattr(payload, "task_id", None) != self.plan["task_id"]:
            return
        if name == "refresh_inventory":
            self.refresh_admissions += 1
        if name == "mutate_plan_highlight" and self.highlight_mutation is None:
            self.highlight_mutation = {
                "admitted": admitted, "completed": None,
                "node_id": payload.node_id,
                "expected_view_revision": payload.expected_view_revision,
                "expected_highlight_revision": payload.expected_highlight_revision,
                "result_view_revision": None, "result_highlight_revision": None,
                "disposition": None,
            }
        elif name == "get_plan_window" and self.post_highlight_window is None:
            mutation = self.highlight_mutation
            if (mutation is not None and type(mutation.get("completed")) is int
                    and payload.expected_revision == mutation.get("result_view_revision")):
                self.post_highlight_window = {
                    "admitted": admitted, "completed": None,
                    "expected_view_revision": payload.expected_revision,
                    "result_view_revision": None, "result_highlight_revision": None,
                    "matches_mutation": False,
                }
        elif name == "get_execution_detail" and self.execution_detail_attempt is None:
            self.execution_detail_attempt = {
                "admitted": admitted, "completed": None,
                "operation_id": payload.operation_id,
                "expected_execution_revision": payload.expected_execution_revision,
                "result_execution_revision": None, "disposition": None,
            }

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
        if name == "mutate_plan_highlight":
            attempt = self.highlight_mutation
            if attempt is not None and attempt["admitted"] == admitted:
                attempt.update({
                    "completed": completed,
                    "result_view_revision": result.get("view_revision"),
                    "result_highlight_revision": result.get("highlight_revision"),
                    "disposition": result.get("disposition"),
                })
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
            attempt = self.execution_detail_attempt
            if attempt is not None and attempt["admitted"] == admitted:
                attempt.update({
                    "completed": completed,
                    "result_execution_revision": result.get("execution_revision"),
                    "disposition": result.get("disposition"),
                })
            if result.get("disposition") != "current":
                return
            operations = self.window.get("operations") if self.window is not None else None
            operation_matches = (
                payload.operation_id in operations if type(operations) is dict
                else self.window is not None and payload.operation_id == self.window["operation_id"]
            )
            if self.window is None or (
                not operation_matches
                or payload.expected_execution_revision != self.window["execution_revision"]
                or result.get("operation_id") != payload.operation_id
                or result.get("execution_revision") != payload.expected_execution_revision
            ):
                raise ValueError("execution detail does not match retained window")
            if type(operations) is dict:
                self.window["operation_id"] = payload.operation_id
                self.window["row_display"] = operations[payload.operation_id]
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
            if result.task_id != self.plan["task_id"] or result.session_id != payload.session_id:
                raise ValueError("release response does not match task")
            if payload.session_id == self.execution["session_id"] and self.release is None:
                self.release = {
                    "admitted": admitted, "completed": completed,
                    "session_id": result.session_id,
                }
            elif payload.session_id in {
                value["session_id"] for value in (self.refresh, self.ordinary)
                if value is not None
            }:
                if not any(item["session_id"] == payload.session_id
                           for item in self.auxiliary_releases):
                    self.auxiliary_releases.append({
                        "admitted": admitted, "completed": completed,
                        "session_id": result.session_id,
                    })
            else:
                raise ValueError("released session does not match execution or an observed activity")
            return
        if name == "get_plan_window" and self.release is not None:
            trace = self.post_highlight_window
            mutation = self.highlight_mutation
            if (trace is not None and mutation is not None
                    and trace["admitted"] == admitted):
                matches = bool(
                    result.get("disposition") == "current"
                    and trace["expected_view_revision"] == mutation["result_view_revision"]
                    and result.get("view_revision") == mutation["result_view_revision"]
                    and result.get("highlight_revision") == mutation["result_highlight_revision"]
                )
                trace.update({
                    "completed": completed,
                    "result_view_revision": result.get("view_revision"),
                    "result_highlight_revision": result.get("highlight_revision"),
                    "matches_mutation": matches,
                })
            execution = result.get("execution") if type(result) is dict else None
            rows = result.get("rows") if type(result) is dict else None
            visible_row = next((
                row for row in rows
                if type(row) is dict and type(row.get("operation_id")) is str
            ), None) if type(rows) is list else None
            operation = visible_row.get("operation_id") if visible_row is not None else None
            operations = {
                row["operation_id"]: row.get("display")
                for row in rows
                if type(row) is dict and type(row.get("operation_id")) is str
                and type(row.get("display")) is str
            } if type(rows) is list else {}
            candidate = {
                "admitted": admitted, "completed": completed,
                "view_revision": result.get("view_revision"),
                "execution_revision": execution.get("execution_revision") if type(execution) is dict else None,
                "operation_id": operation,
                "row_display": visible_row.get("display") if visible_row is not None else None,
                "operations": operations,
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
                if self.window is None or (
                    candidate["view_revision"], candidate["execution_revision"]
                ) >= (
                    self.window["view_revision"], self.window["execution_revision"]
                ):
                    if self.detail is not None and self.detail["operation_id"] in operations:
                        candidate["operation_id"] = self.detail["operation_id"]
                        candidate["row_display"] = operations[self.detail["operation_id"]]
                    self.window = candidate
            return
        if name == "open_inventory_view" and self.release is not None:
            if type(result) is not dict or result.get("task_id") != self.plan["task_id"]:
                raise ValueError("inventory view changed task identity")
            if self.branch == "exact" and result.get("selected_file_count") != 0:
                raise ValueError("initial linked inventory selection is not empty")
            self.inventory_open = {
                "admitted": admitted, "completed": completed,
                "request_id": result.get("request_id"),
                "view_revision": result.get("view_revision"),
                "scan_request_id": result.get("scan_request_id"),
                "selected_file_count": result.get("selected_file_count"),
                "disposition": result.get("disposition"),
            }
            return
        if name == "get_inventory_window" and self.inventory_open is not None:
            if type(result) is not dict or result.get("disposition") != "current":
                return
            if result.get("view_revision") != payload.expected_revision:
                raise ValueError("inventory window revision changed")
            integrity = result.get("integrity")
            self.inventory_window = {
                "admitted": admitted, "completed": completed,
                "view_revision": result.get("view_revision"),
                "row_count": len(result.get("rows", [])),
                "integrity_session_id": integrity.get("session_id") if type(integrity) is dict else None,
                "integrity_complete": integrity.get("complete") if type(integrity) is dict else None,
                "integrity_item_count": len(integrity.get("items", [])) if type(integrity) is dict else None,
            }
            return
        if name == "refresh_inventory":
            if self.branch != "blocked" or self.inventory_open is None or result.task_id != self.plan["task_id"]:
                raise ValueError("blocked refresh changed task identity")
            self.refresh = {
                "admitted": admitted, "completed": completed,
                "request_id": result.request_id, "session_id": result.session_id,
                "command_id": payload.command_id,
            }
            return
        if name == "set_inventory_selection":
            refresh_released = self._owner_released_locked(self.refresh)
            if (self.branch != "blocked" or self.selection is not None
                    or self.inventory_open is None or not refresh_released
                    or payload.request_id != self.refresh["request_id"]
                    or payload.request_id != self.inventory_open["request_id"]
                    or payload.expected_revision != self.inventory_open["view_revision"]
                    or payload.node_id is None or payload.selected is not True
                    or type(result) is not dict
                    or result.get("task_id") != self.plan["task_id"]
                    or result.get("request_id") != payload.request_id
                    or result.get("view_revision") != payload.expected_revision + 1
                    or result.get("selected_file_count") != len(self.fixture)):
                raise ValueError("blocked selection did not adopt current inventory evidence")
            self.selection = {
                "admitted": admitted, "completed": completed,
                "request_id": payload.request_id, "node_id": payload.node_id,
                "expected_revision": payload.expected_revision,
                "view_revision": result.get("view_revision"),
                "selected_file_count": result.get("selected_file_count"),
            }
            return
        if name == "start_inventory_integrity":
            scope_owner = self.inventory_open if self.branch == "exact" else self.selection
            if (self.ordinary is not None or self.inventory_open is None
                    or scope_owner is None
                    or payload.mode != "verify" or result.task_id != self.plan["task_id"]
                    or payload.request_id != scope_owner["request_id"]
                    or payload.expected_revision != scope_owner["view_revision"]
                    or payload.scope != ("copied" if self.branch == "exact" else "selected")):
                raise ValueError("ordinary verification did not consume the current scope")
            if self.branch == "blocked" and (not self._owner_released_locked(self.refresh)
                    or self.selection is None or self.selection["completed"] >= admitted
                    or self.selection["selected_file_count"] != len(self.fixture)):
                raise ValueError("ordinary selected verification preceded selection")
            self.ordinary = {
                "admitted": admitted, "completed": completed,
                "request_id": result.request_id, "session_id": result.session_id,
                "command_id": payload.command_id, "scope": payload.scope,
            }
            return
        if name in {"control_execution", "control_integrity"}:
            owner = self.ordinary
            if owner is None or payload.session_id != owner["session_id"] or not result.accepted:
                raise ValueError("auxiliary control changed current session identity")
            self.controls.append({
                "admitted": admitted, "completed": completed, "command": name,
                "session_id": payload.session_id, "action": payload.action,
                "before": result.before, "after": result.after,
            })
            if payload.action == "pause":
                self.worker_release.set()
            return
        if name == "close_task":
            owner = self.ordinary
            if (owner is None or payload.session_id != owner["session_id"]
                    or result.task_id != self.plan["task_id"]
                    or result.session_id != payload.session_id):
                raise ValueError("Close did not consume the current released task identity")
            self.close = {
                "admitted": admitted, "completed": completed,
                "session_id": payload.session_id, "disposition": result.disposition,
            }
            return

    def _session_released_locked(self, session_id: object) -> bool:
        if self.registry is None or type(session_id) is not str:
            return False
        try:
            self.registry._lifecycle.get_session(session_id)
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
        if not self._original_review_receipts_locked():
            return False
        task = next((
            task for task in self.registry.list_tasks().tasks
            if task.task_id == self.plan["task_id"]
        ), None)
        return bool(
            task is not None and task.session_id == self.execution["session_id"]
            and task.session_released
        )

    def _original_review_receipts_locked(self) -> bool:
        return bool(
            self.registry is not None and self.plan is not None and self.execution is not None
            and self.failure is None and self.release and self.window
            and self._session_released_locked(self.execution["session_id"])
            and self.execution["completed"] < self.release["admitted"]
            and self.release["completed"] < self.window["admitted"]
        )

    def _detail_ready_locked(self) -> bool:
        return bool(
            self._original_review_receipts_locked() and self.detail is not None
            and self.detail["operation_id"] == self.window["operation_id"]
            and self.detail["execution_revision"] == self.window["execution_revision"]
        )

    def _owner_released_locked(self, owner: dict[str, object] | None) -> bool:
        if owner is None:
            return False
        release = next((
            item for item in self.auxiliary_releases
            if item["session_id"] == owner["session_id"]
        ), None)
        return bool(
            release is not None and owner["completed"] < release["admitted"]
            and self._session_released_locked(owner["session_id"])
        )

    def capture_ready(self) -> bool:
        with self.lock:
            return self._capture_ready_locked()

    def _capture_ready_locked(self) -> bool:
        owner = self.ordinary
        if not self._detail_ready_locked() or not self._owner_released_locked(owner):
            return False
        task = next((
            task for task in self.registry.list_tasks().tasks
            if task.task_id == self.plan["task_id"]
        ), None)
        return bool(
            task is not None and task.session_id == owner["session_id"]
            and task.session_released
        )

    def capture_readiness_diagnostic(self) -> dict[str, bool]:
        with self.lock:
            execution = self.execution
            release = self.release
            window = self.window
            detail = self.detail
            ordinary = self.ordinary
            ordinary_release = None if ordinary is None else next((
                item for item in self.auxiliary_releases
                if item["session_id"] == ordinary["session_id"]
            ), None)
            task = None if self.registry is None or self.plan is None else next((
                item for item in self.registry.list_tasks().tasks
                if item.task_id == self.plan["task_id"]
            ), None)
            original_lifecycle_released = bool(
                execution is not None
                and self._session_released_locked(execution["session_id"])
            )
            ordinary_lifecycle_released = bool(
                ordinary is not None
                and self._session_released_locked(ordinary["session_id"])
            )
            return {
                "recordingHealthy": self.failure is None,
                "planObserved": self.plan is not None,
                "executionObserved": execution is not None,
                "originalReleaseObserved": release is not None,
                "windowObserved": window is not None,
                "originalLifecycleReleased": original_lifecycle_released,
                "executionBeforeOriginalRelease": bool(
                    execution is not None and release is not None
                    and execution["completed"] < release["admitted"]
                ),
                "originalReleaseBeforeWindow": bool(
                    release is not None and window is not None
                    and release["completed"] < window["admitted"]
                ),
                "detailObserved": detail is not None,
                "detailOperationMatches": bool(
                    detail is not None and window is not None
                    and detail["operation_id"] == window["operation_id"]
                ),
                "detailRevisionMatches": bool(
                    detail is not None and window is not None
                    and detail["execution_revision"] == window["execution_revision"]
                ),
                "ordinaryObserved": ordinary is not None,
                "ordinaryReleaseObserved": ordinary_release is not None,
                "ordinaryBeforeRelease": bool(
                    ordinary is not None and ordinary_release is not None
                    and ordinary["completed"] < ordinary_release["admitted"]
                ),
                "ordinaryLifecycleReleased": ordinary_lifecycle_released,
                "taskPresent": task is not None,
                "currentSessionIsOrdinary": bool(
                    task is not None and ordinary is not None
                    and task.session_id == ordinary["session_id"]
                ),
                "currentSessionReleased": bool(
                    task is not None and task.session_released
                ),
                "captureReady": self._capture_ready_locked(),
            }

    def phase_failure_trace(self) -> dict[str, str | None]:
        with self.lock:
            return {"type": self.failure, "command": self.failure_command}

    def finished_ready(self) -> bool:
        with self.lock:
            owner = self.ordinary
            owner_released = self._owner_released_locked(owner)
            actions = [(item["command"], item["action"]) for item in self.controls]
            if self.branch == "exact":
                overlay_ready = bool(
                    self.inventory_window is not None and self.ordinary is not None
                    and self.inventory_window["integrity_session_id"] == self.ordinary["session_id"]
                    and self.inventory_window["integrity_complete"] is True
                    and self.inventory_window["integrity_item_count"] == len(self.fixture)
                )
                required = [("control_integrity", "pause"), ("control_integrity", "resume")]
                return bool(
                    self._detail_ready_locked() and owner_released
                    and actions == required and overlay_ready and self.close is not None
                )
            refresh_released = self._owner_released_locked(self.refresh)
            overlay_ready = bool(
                self.inventory_window is not None and self.ordinary is not None
                and self.inventory_window["integrity_session_id"] == self.ordinary["session_id"]
                and self.inventory_window["integrity_complete"] is True
                and self.inventory_window["integrity_item_count"] == len(self.fixture)
            )
            required = [("control_integrity", "pause"), ("control_integrity", "resume")]
            return bool(
                self._original_review_receipts_locked() and refresh_released
                and self.selection is not None
                and self.selection["selected_file_count"] == len(self.fixture)
                and self.selection["request_id"] == self.refresh["request_id"]
                and self.ordinary is not None
                and self.selection["completed"] < self.ordinary["admitted"]
                and owner_released and actions == required and overlay_ready
                and self.close is not None
            )

    def set_identity(self, phase: str, value: object) -> None:
        if phase not in {"pre", "post"} or type(value) is not dict:
            raise RuntimeError("execution review identity is invalid")
        with self.lock:
            if not self._capture_ready_locked():
                raise RuntimeError("execution review capture identity changed")
            expected = self._expected_identity_locked()
            if value != expected:
                raise RuntimeError("execution review identity does not match receipts")
            if phase == "pre":
                if self.pre_identity is not None:
                    raise RuntimeError("execution review capture already started")
                self.pre_identity = dict(value)
                self.capture_receipt = self._receipt_identity_locked()
            else:
                if (self.pre_identity != value or self.capture_receipt is None
                        or self.capture_receipt != self._receipt_identity_locked()):
                    raise RuntimeError("execution review POST identity changed")
                self.post_identity = dict(value)

    def acknowledge_capture(self) -> None:
        with self.lock:
            if self.post_identity is None:
                raise RuntimeError("execution review capture identity is incomplete")
            self.capture_complete = True

    def _receipt_identity_locked(self) -> tuple[object, ...]:
        if self.plan is None or self.execution is None or self.window is None or self.detail is None:
            raise RuntimeError("execution review receipts are incomplete")
        return (
            self.plan["task_id"], self.execution["request_id"],
            self.execution["session_id"], self.window["view_revision"],
            self.window["execution_revision"], self.window["operation_id"],
            self.window["row_display"], self.detail["operation_id"],
            self.detail["execution_revision"], self.detail["operation_path"],
        )

    def _expected_identity_locked(self) -> dict[str, object]:
        if self.plan is None or self.execution is None or self.window is None or self.detail is None:
            raise RuntimeError("execution review receipts are incomplete")
        return {
            "selectedTask": self.plan["task_label"],
            "runId": self.execution["request_id"],
            "sessionId": self.execution["session_id"],
            "executionRevision": self.detail["execution_revision"],
            "rowName": self.window["row_display"],
            "operationPath": str(self.target / self.detail["operation_path"]),
            "rowHighlighted": True, "detailVisible": True,
            "disclosureVisible": True, "disclosureExpanded": True,
            "operationFactPresent": True, "recordingFactPresent": True,
            "evidenceFactPresent": True, "operationIdVisible": False,
        }

    def verify_files(self) -> None:
        if {path.name for path in self.source.iterdir()} != set(self.fixture):
            raise RuntimeError("source fixture membership changed")
        if {path.name for path in self.target.iterdir()} != set(self.fixture):
            raise RuntimeError("target fixture membership is invalid")
        for name, contents in self.fixture.items():
            if (self.source / name).read_bytes() != contents:
                raise RuntimeError("source fixture bytes changed")
            if (self.target / name).read_bytes() != contents:
                raise RuntimeError("target fixture bytes do not match")

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            task = next((item for item in self.registry.list_tasks().tasks
                         if self.plan is not None and item.task_id == self.plan["task_id"]), None) \
                if self.registry is not None else None
            return deepcopy({
                "plan": self.plan, "execution": self.execution, "release": self.release,
                "window": self.window, "detail": self.detail,
                "highlight_mutation": self.highlight_mutation,
                "post_highlight_window": self.post_highlight_window,
                "execution_detail_attempt": self.execution_detail_attempt,
                "inventory_open": self.inventory_open,
                "inventory_window": self.inventory_window,
                "refresh": self.refresh, "selection": self.selection,
                "refresh_admissions": self.refresh_admissions,
                "current_association": None if task is None else {
                    "task_id": task.task_id, "request_id": task.request_id,
                    "session_id": task.session_id,
                },
                "ordinary": self.ordinary, "controls": self.controls,
                "auxiliary_releases": self.auxiliary_releases,
                "close": self.close, "branch": self.branch,
                "worker_entered": self.worker_entered.is_set(),
                "failure": self.failure, "capture_complete": self.capture_complete,
                "pre_identity": self.pre_identity,
                "post_identity": self.post_identity,
                "review_ready": self._review_ready_locked(),
            })

    def diagnostic_trace(self) -> dict[str, object]:
        with self.lock:
            return deepcopy({
                "highlight_mutation": self.highlight_mutation,
                "post_highlight_window": self.post_highlight_window,
                "execution_detail_attempt": self.execution_detail_attempt,
            })


class _ExecutionReviewJourney:
    def __init__(
        self, source: Path, target: Path,
        blocked_source: Path, blocked_target: Path,
    ) -> None:
        self.exact = _ExecutionReviewPhase(source, target, file_count=24, branch="exact")
        self.blocked = _ExecutionReviewPhase(
            blocked_source, blocked_target, file_count=1, branch="blocked",
        )

    def bind(self, registry: object) -> None:
        self.blocked.bind(registry)
        self.exact.bind(registry)

    def bind_visible_label(self, label: object) -> None:
        self.exact.bind_visible_label(label)

    def wrap(self, commands: object) -> object:
        return self.blocked.wrap(self.exact.wrap(commands))

    def failure_identity(self) -> dict[str, object]:
        return {
            "exact": self.exact.failure_identity(),
            "blocked": self.blocked.failure_identity(),
        }

    def capture_ready(self) -> bool:
        return self.exact.capture_ready()

    def set_identity(self, phase: str, value: object) -> None:
        self.exact.set_identity(phase, value)

    def acknowledge_capture(self) -> None:
        self.exact.acknowledge_capture()

    def verify_exact_files(self) -> None:
        self.exact.verify_files()

    def verify_files(self) -> None:
        self.exact.verify_files()
        self.blocked.verify_files()

    def finished_ready(self) -> bool:
        return self.exact.finished_ready() and self.blocked.finished_ready()

    def snapshot(self) -> dict[str, object]:
        return {"exact": self.exact.snapshot(), "blocked": self.blocked.snapshot()}

    def diagnostic_trace(self) -> dict[str, object]:
        return {"exact": self.exact.diagnostic_trace()}

    def capture_readiness_diagnostic(self) -> dict[str, bool]:
        return self.exact.capture_readiness_diagnostic()

    def phase_failure_trace(self) -> dict[str, dict[str, str | None]]:
        return {
            "exact": self.exact.phase_failure_trace(),
            "blocked": self.blocked.phase_failure_trace(),
        }


def _test_spec(handler: Callable[[object], object]) -> object:
    from namisync.interfaces.web.commands import (
        CommandAccess, CommandRetry, CommandSpec, CommandResponsePolicy, FieldRequirement,
    )
    return CommandSpec(
        validate_payload=_validate_empty, handler=handler,
        access=CommandAccess.READ_ONLY, command_id=FieldRequirement.FORBIDDEN,
        revision=FieldRequirement.FORBIDDEN, response_policy=CommandResponsePolicy.INTERACTIVE,
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
        self.phase: _ExecutionReviewPhase | _ExecutionReviewJourney | None = None

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
                diagnostic_kind = set(diagnostic)
                if diagnostic_kind not in {
                    _WAIT_REVIEW_DIAGNOSTIC, _CAPTURE_READINESS_DIAGNOSTIC,
                    _PRECLICK_DIAGNOSTIC, _RETENTION,
                } or any(
                    type(value) is not bool for value in diagnostic.values()
                ):
                    raise RuntimeError("execution review diagnostic is invalid")
                payload["diagnostic"] = dict(diagnostic)
                if diagnostic_kind == _WAIT_REVIEW_DIAGNOSTIC and self.phase is not None:
                    payload["trace"] = self.phase.diagnostic_trace()
                if diagnostic_kind == _CAPTURE_READINESS_DIAGNOSTIC and self.phase is not None:
                    payload["phase_failure"] = self.phase.phase_failure_trace()
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
      if (window.__namiFirstAsyncError) throw new Error('browser asynchronous error');
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
  const action = (root, name) => root?.querySelector(`[data-action="${name}"]`) ?? null;
  const usable = (root, name) => {
    const value = action(root, name);
    return value instanceof HTMLButtonElement && value.isConnected && !value.hidden
      && !value.disabled && value.closest('[hidden]') === null ? value : null;
  };
  const visibleFact = (root, selector) => [...root.querySelectorAll(selector)].find((value) => {
    const rect = value.getBoundingClientRect();
    const viewport = value.closest('.nami-plan-review__list, .nami-inventory-review__list')
      ?.getBoundingClientRect();
    return value.closest('[hidden]') === null && rect.width > 0 && rect.height > 0
      && (viewport === undefined || (rect.bottom > viewport.top && rect.top < viewport.bottom));
  }) ?? null;
  const inactivePane = (value) => value instanceof HTMLElement && value.hidden
    && getComputedStyle(value).display === 'none' && value.getClientRects().length === 0;
  const cards = await until(() => {
    const values = [...document.querySelectorAll('.nami-task-rail__row .nami-task-card')];
    return values.length === 2 ? values : null;
  }, 'tasks');
  let card = null;
  let blockedCard = null;
  for (const candidate of cards) {
    candidate.click();
    const leaf = await until(() => {
      if (candidate.getAttribute('aria-current') !== 'page') return null;
      const value = document.querySelector('.nami-plan-review__path--source');
      const text = value instanceof HTMLElement ? value.title.trim().replace(/[\\/]+$/, '') : '';
      const name = text.split(/[\\/]/).pop()?.toLowerCase();
      return name === 'source' || name === 'blocked-source' ? name : null;
    }, 'task source identity');
    if (leaf === 'source') card = candidate;
    if (leaf === 'blocked-source') blockedCard = candidate;
  }
  if (!(card instanceof HTMLElement) || !(blockedCard instanceof HTMLElement)) {
    throw new Error('execution review task identities are unavailable');
  }
  card.click();
  const ready = await until(() => {
    const review = document.querySelector('.nami-plan-review');
    if (!(review instanceof HTMLElement) || !review.isConnected) return null;
    const button = review.querySelector('[data-action="execute"]');
    const table = review.querySelector('.nami-plan-review__table-card');
    return button instanceof HTMLButtonElement && button.isConnected
      && !button.hidden && !button.disabled && table instanceof HTMLElement
      && !table.hidden && review.querySelector('.nami-plan-review__rows [data-node-id]')
      ? {review, execute:button} : null;
  }, 'execute');
  const {review, execute} = ready;
  await until(() => document.hasFocus(), 'document-focus');
  execute.focus();
  await new Promise((resolve) => requestAnimationFrame(resolve));
  await new Promise((resolve) => requestAnimationFrame(resolve));
  const rect = execute.getBoundingClientRect();
  const point = {x:(rect.left+rect.right)/2,y:(rect.top+rect.bottom)/2};
  const executeHit = document.elementFromPoint(point.x, point.y);
  const reviewLoaded = review.isConnected
    && !review.querySelector('.nami-plan-review__table-card').hidden;
  if (!execute.isConnected || !reviewLoaded
      || document.activeElement !== execute || executeHit !== execute) {
    return {preclick: {
      executeConnected: execute.isConnected,
      reviewLoaded,
      executeFocused: document.activeElement === execute,
      pointInsideViewport: point.x >= 0 && point.y >= 0
        && point.x < innerWidth && point.y < innerHeight,
      hitPresent: executeHit !== null,
      hitExecute: executeHit === execute,
      hitDescendant: executeHit !== null && executeHit !== execute && execute.contains(executeHit),
    }};
  }
  const nativeInput = {mouseDownSeen:false, mouseUpSeen:false, clickSeen:false};
  window.__executionReviewProgress = {
    scrollObserved:false, visibleFixtureFileRowObserved:false,
    rowClickDispatched:false, detailObserved:false,
    clickedRowConnectedBeforeClick:false, clickedRowConnectedAfterClick:false,
    rowClickEventObserved:false,
  };
  execute.addEventListener('mousedown', (event) => { nativeInput.mouseDownSeen ||= event.isTrusted; });
  execute.addEventListener('mouseup', (event) => { nativeInput.mouseUpSeen ||= event.isTrusted; });
  execute.addEventListener('click', (event) => { nativeInput.clickSeen ||= event.isTrusted; });
  window.__executionReviewNativeInput = nativeInput;
  window.__executionReviewExecutePoint = {point, taskLabel: card.dataset.taskLabel};
  window.__executionReviewStage = 'execute-ready';
  await until(() => window.__executionReviewNativeConfirmed === true, 'native-confirmation');
  await until(() => nativeInput.clickSeen === true, 'trusted-native-click');
  await until(async () => (await control()).exact?.review_ready === true, 'released execution review');
  const disclosure = review.querySelector('[data-action="toggle-execution-details"]');
  if (!(disclosure instanceof HTMLButtonElement)) throw new Error('card disclosure unavailable');
  if (disclosure.getAttribute('aria-expanded') !== 'true') disclosure.click();
  const rows = review.querySelector('.nami-plan-review__list');
  if (!(rows instanceof HTMLElement) || rows.scrollHeight <= rows.clientHeight) {
    throw new Error('execution review viewport is not scrollable');
  }
  rows.scrollTop = Math.min(rows.scrollHeight - rows.clientHeight, 8 * 24);
  rows.dispatchEvent(new Event('scroll'));
  await until(() => rows.scrollTop > 0, 'nonzero execution viewport');
  window.__executionReviewProgress.scrollObserved = true;
  const row = await until(() => {
    const listRect = rows.getBoundingClientRect();
    return [...rows.querySelectorAll('[data-node-id]')].find((value) => {
      const rect = value.getBoundingClientRect();
      const point = {x:rect.left + 48, y:(rect.top + rect.bottom) / 2};
      const hit = document.elementFromPoint(point.x, point.y);
      return rect.top >= listRect.top + 24 - 1 && rect.bottom <= listRect.bottom + 1
        && hit !== null && value.contains(hit);
    }) ?? null;
  }, 'operation-row');
  window.__executionReviewProgress.visibleFixtureFileRowObserved =
    /^file-\d{2}\.txt$/.test(row.querySelector('.nami-file-row__name-text')?.textContent ?? '');
  const focusedNodeId = row.dataset.nodeId;
  const interactionFact = (currentRow) => {
    const listBounds = rows.getBoundingClientRect();
    const rowBounds = currentRow.getBoundingClientRect();
    const point = {x:rowBounds.left + 48, y:(rowBounds.top + rowBounds.bottom) / 2};
    const hit = document.elementFromPoint(point.x, point.y);
    return {
      scrollTop:Math.round(rows.scrollTop),
      clientHeight:rows.clientHeight,
      scrollHeight:rows.scrollHeight,
      listTop:Math.round(listBounds.top),
      listBottom:Math.round(listBounds.bottom),
      rowTop:Math.round(rowBounds.top),
      rowBottom:Math.round(rowBounds.bottom),
      originalRowConnected:row.isConnected,
      currentRowConnected:currentRow.isConnected,
      rowFullyVisible:currentRow.isConnected
        && rowBounds.top >= listBounds.top + 24 - 1 && rowBounds.bottom <= listBounds.bottom + 1,
      rowHitOwned:currentRow.isConnected && hit !== null && currentRow.contains(hit),
      activeMatchesClickedNode:document.activeElement?.dataset?.nodeId === focusedNodeId,
      sameReview:document.querySelector('.nami-plan-review') === review,
      sameList:review.querySelector('.nami-plan-review__list') === rows,
    };
  };
  const scrollInteractionDiagnostic = {
    preClick:interactionFact(row), immediateAfterClick:null,
    firstDisconnection:null, afterDetail:null,
  };
  const observeDisconnection = () => {
    if (!row.isConnected && scrollInteractionDiagnostic.firstDisconnection === null) {
      scrollInteractionDiagnostic.firstDisconnection = interactionFact(row);
    }
  };
  row.addEventListener('click', () => {
    window.__executionReviewProgress.rowClickEventObserved = true;
  }, {once:true});
  window.__executionReviewProgress.clickedRowConnectedBeforeClick = row.isConnected;
  window.__executionReviewClickedRow = row;
  window.__executionReviewClickedNodeId = focusedNodeId;
  row.click();
  scrollInteractionDiagnostic.immediateAfterClick = interactionFact(row);
  window.__executionReviewProgress.clickedRowConnectedAfterClick = row.isConnected;
  window.__executionReviewProgress.rowClickDispatched = true;
  const detail = await until(() => {
    observeDisconnection();
    const value = review.querySelector('.nami-plan-review__detail');
    return value instanceof HTMLElement && !value.hidden && !value.textContent.includes('Loading')
      && [...value.querySelectorAll('dt')].some(term => term.textContent === 'Target path') ? value : null;
  }, 'detail');
  window.__executionReviewProgress.detailObserved = true;
  const adoptedRow = await until(() => {
    observeDisconnection();
    return [...rows.querySelectorAll('[data-node-id]')]
      .find(candidate => candidate.dataset.nodeId === focusedNodeId
        && candidate.dataset.highlighted === 'true' && candidate.isConnected) ?? null;
  }, 'adopted-row');
  observeDisconnection();
  scrollInteractionDiagnostic.afterDetail = interactionFact(adoptedRow);
  const rowActivationFocused = document.activeElement === adoptedRow;
  const executionFacts = element => [...element.querySelectorAll('dt')]
    .filter(term => term.textContent !== 'Stored evidence' && !term.textContent.startsWith('Evidence '))
    .map(term => [term.textContent, term.nextElementSibling?.textContent ?? '']);
  const retained = {
    review, rows, detail, disclosure,
    nodeId: focusedNodeId, scrollTop: rows.scrollTop, tabIndex: adoptedRow.tabIndex,
    detailFacts: executionFacts(detail),
    rowText: adoptedRow.querySelector('.nami-file-row__name-text')?.textContent ?? '',
    follow: [...review.querySelectorAll('[data-action="go-current-operation"], [data-action="enable-operation-follow"]')]
      .map((value) => [value.dataset.action, value.hidden, value.disabled, value.textContent]),
  };
  const scrollFact = (value) => ({
    scrollTop:value instanceof HTMLElement ? value.scrollTop : null,
    clientHeight:value instanceof HTMLElement ? value.clientHeight : null,
    scrollHeight:value instanceof HTMLElement ? value.scrollHeight : null,
  });
  const scrollDiagnostic = {original:scrollFact(rows)};
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
    tableUsable: tb.height > 0 && rows.clientHeight >= 48,
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

  const verifyPane = usable(review, 'pane-verify');
  if (verifyPane === null || verifyPane.getAttribute('aria-checked') !== 'false') {
    throw new Error('Verify pane control unavailable');
  }
  scrollDiagnostic.beforeVerify = scrollFact(rows);
  verifyPane.click();
  const inventory = await until(() => {
    const value = document.querySelector('.nami-inventory-review');
    return value instanceof HTMLElement && value.isConnected && value.closest('[hidden]') === null
      ? value : null;
  }, 'Verify pane');
  if (!inactivePane(review)) throw new Error('inactive Plan pane remains visible');
  scrollDiagnostic.hiddenAfterVerify = scrollFact(rows);
  const exactStart = await until(() => usable(inventory, 'verify-copied-files'), 'copied action');
  const copiedActionVisible = exactStart.isConnected;
  if (!["inventory-baseline", "inventory-baseline-menu"].every(name => {
    const control = action(inventory, name);
    return control instanceof HTMLButtonElement && control.isConnected
      && control.closest('[hidden]') === null && control.disabled;
  })) {
    throw new Error('sync Verify action presentation is invalid');
  }
  exactStart.click();
  const copiedPause = await until(() => usable(inventory, 'inventory-pause'), 'ordinary pause');
  copiedPause.click();
  const copiedResume = await until(() => usable(inventory, 'inventory-resume'), 'ordinary resume');
  copiedResume.click();
  await until(async () => {
    const value = (await control()).exact;
    return value?.ordinary !== null
      && value?.auxiliary_releases?.some((item) => item.session_id === value.ordinary.session_id)
      && value?.inventory_window?.integrity_session_id === value.ordinary.session_id
      && value?.inventory_window?.integrity_complete === true ? value : null;
  }, 'ordinary terminal overlay');
  const copiedDetails = usable(inventory, 'inventory-details');
  if (copiedDetails.ariaExpanded !== 'true') copiedDetails.click();
  const copiedResult = await until(() => {
    const value = inventory.querySelector('.nami-plan-review__status-title');
    return value instanceof HTMLElement && value.closest('[hidden]') === null
      && value.textContent === 'Verification completed'
      && visibleFact(inventory, '.nami-inventory-review__rows [data-integrity-state="verified"]') !== null
      && usable(inventory, 'inventory-pause') === null
      && usable(inventory, 'inventory-resume') === null
      && inventory.querySelector('[data-inventory-integrity-facts]') === null ? value : null;
  }, 'ordinary result');
  const copiedResultVisible = copiedResult.isConnected;
  const copiedRow = visibleFact(inventory, '.nami-inventory-review__rows [data-integrity-state="verified"]');
  const copiedRowVisible = copiedRow !== null;

  const planPane = usable(inventory, 'pane-plan');
  if (planPane === null || planPane.getAttribute('aria-checked') !== 'false') {
    throw new Error('Plan pane control unavailable');
  }
  planPane.click();
  scrollDiagnostic.immediateReturn = scrollFact(rows);
  const returnedReview = await until(() => {
    const value = document.querySelector('.nami-plan-review');
    return value instanceof HTMLElement && value.isConnected && value.closest('[hidden]') === null
      ? value : null;
  }, 'retained Plan pane');
  await until(() => {
    const detail = returnedReview.querySelector('.nami-plan-review__detail');
    const evidence = [...detail.querySelectorAll('dt')].find(term => term.textContent === 'Stored evidence');
    return evidence?.nextElementSibling?.textContent === 'Superseded'
      && ![...detail.querySelectorAll('dt')].some(term => term.textContent === 'Evidence digest');
  }, 'superseded execution evidence');
  if (!inactivePane(inventory)) throw new Error('inactive Verify pane remains visible');
  const returnedRows = returnedReview.querySelector('.nami-plan-review__list');
  const returnedRow = returnedReview.querySelector(`[data-node-id="${retained.nodeId}"]`);
  const returnedDetail = returnedReview.querySelector('.nami-plan-review__detail');
  const follow = [...returnedReview.querySelectorAll('[data-action="go-current-operation"], [data-action="enable-operation-follow"]')]
    .map((value) => [value.dataset.action, value.hidden, value.disabled, value.textContent]);
  const retention = {
    sameRenderer: returnedReview === retained.review,
    sameList: returnedRows === retained.rows,
    planReturned: action(returnedReview, 'pane-plan')?.getAttribute('aria-checked') === 'true',
    taskRetained: card.getAttribute('aria-current') === 'page',
    rowRetained: returnedRow instanceof HTMLElement
      && returnedRow.querySelector('.nami-file-row__name-text')?.textContent === retained.rowText,
    scrollRetained: returnedRows instanceof HTMLElement
      && Math.abs(returnedRows.scrollTop - retained.scrollTop) <= 1 && retained.scrollTop > 0,
    detailRetained: returnedDetail === retained.detail && !returnedDetail.hidden
      && JSON.stringify(executionFacts(returnedDetail)) === JSON.stringify(retained.detailFacts),
    selectionRetained: returnedRow?.dataset.highlighted === 'true'
      && returnedRow?.getAttribute('aria-selected') === 'true',
    keyboardRetained: returnedRow?.tabIndex === retained.tabIndex && retained.tabIndex === 0,
    followRetained: JSON.stringify(follow) === JSON.stringify(retained.follow),
  };
  if (Object.values(retention).some((value) => value !== true)) {
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    scrollDiagnostic.afterFrames = scrollFact(returnedRows);
    return {retentionFailure: retention, scrollDiagnostic, scrollInteractionDiagnostic};
  }
  window.__executionReviewStage = 'capture-ready';
  await until(() => window.__executionReviewCaptureAck === true, 'capture-ack');

  window.__executionReviewBlockedStage = 'exact-close';
  const exactClose = card.parentElement?.querySelector('.nami-task-rail__close');
  if (!(exactClose instanceof HTMLButtonElement) || exactClose.disabled) throw new Error('exact Close unavailable');
  exactClose.click();
  await until(async () => !card.isConnected && (await control()).exact?.close !== null, 'exact Close');

  window.__executionReviewBlockedStage = 'blocked-execution';
  blockedCard.click();
  const blockedPlan = await until(() => {
    const value = document.querySelector('.nami-plan-review');
    const execute = usable(value, 'execute');
    return value instanceof HTMLElement && execute !== null ? {value, execute} : null;
  }, 'blocked execution');
  blockedPlan.execute.click();
  window.__executionReviewBlockedStage = 'blocked-execution-release';
  await until(async () => (await control()).blocked?.review_ready === true, 'blocked execution release');
  window.__executionReviewBlockedStage = 'blocked-verify-pane';
  const blockedVerifyPane = await until(() => usable(blockedPlan.value, 'pane-verify'), 'blocked Verify pane');
  blockedVerifyPane.click();
  window.__executionReviewBlockedStage = 'blocked-initial-readiness';
  const blockedInventory = await until(() => {
    const value = document.querySelector('.nami-inventory-review');
    return value instanceof HTMLElement && value.closest('[hidden]') === null
      && usable(value, 'verify-copied-files') !== null ? value : null;
  }, 'blocked initial exact readiness');
  window.__executionReviewBlockedStage = 'blocked-refresh';
  const refresh = await until(() => usable(blockedInventory, 'inventory-refresh'), 'blocked refresh');
  refresh.click();
  await until(async () => (await control()).blocked.refresh_admissions === 1, 'Refresh admission');
  const refreshSubmittedOnce = (await control()).blocked.refresh_admissions === 1;
  window.__executionReviewBlockedStage = 'blocked-handoff';
  await until(async () => {
    const value = (await control()).blocked;
    return value?.refresh !== null
      && value?.auxiliary_releases?.some((item) => item.session_id === value.refresh.session_id)
      ? value : null;
  }, 'superseded exact handoff');
  await until(async () => {
    const value = (await control()).blocked;
    return value?.inventory_open?.request_id === value?.refresh?.request_id
      && value?.inventory_open?.scan_request_id === value?.refresh?.request_id;
  }, 'current refreshed inventory');
  window.__executionReviewBlockedStage = 'blocked-row';
  const {row:fallbackRow, checkbox:fallbackCheckbox} = await until(() => {
    const row = [...blockedInventory.querySelectorAll(
      '.nami-inventory-review__rows > .nami-tree-row[role="treeitem"][data-node-id]'
    )].find((value) => value.querySelector('.nami-file-row__name-text')?.textContent === 'one.txt');
    const checkbox = row?.querySelector(
      ':scope > .nami-file-row__selection > input[data-action="inventory-select-row"]');
    return row?.isConnected && checkbox instanceof HTMLInputElement
      && !checkbox.disabled && !checkbox.checked && checkbox.closest('[hidden]') === null
      ? {row, checkbox} : null;
  }, 'blocked inventory selection');
  window.__executionReviewBlockedStage = 'blocked-checkbox';
  fallbackCheckbox.focus();
  await new Promise((resolve) => requestAnimationFrame(resolve));
  const checkboxRect = fallbackCheckbox.getBoundingClientRect();
  const checkboxPoint = {x:(checkboxRect.left+checkboxRect.right)/2,
    y:(checkboxRect.top+checkboxRect.bottom)/2};
  if (checkboxRect.width <= 0 || checkboxRect.height <= 0
      || document.elementFromPoint(checkboxPoint.x, checkboxPoint.y) !== fallbackCheckbox) {
    throw new Error('blocked inventory selection is not hittable');
  }
  let trustedSelection = false;
  fallbackCheckbox.addEventListener('click', (event) => { trustedSelection ||= event.isTrusted; }, {once:true});
  window.__executionReviewSelectionTarget = () => {
    const bounds = fallbackCheckbox.getBoundingClientRect();
    const point = {x:(bounds.left+bounds.right)/2, y:(bounds.top+bounds.bottom)/2};
    if (!fallbackCheckbox.isConnected || fallbackCheckbox.disabled || fallbackCheckbox.checked
        || fallbackCheckbox.closest('[hidden]') !== null || document.activeElement !== fallbackCheckbox
        || bounds.width <= 0 || bounds.height <= 0
        || document.elementFromPoint(point.x, point.y) !== fallbackCheckbox) {
      throw new Error('blocked inventory selection target changed');
    }
    return point;
  };
  window.__executionReviewSelectionPoint = checkboxPoint;
  window.__executionReviewBlockedStage = 'selection-ready';
  window.__executionReviewStage = 'selection-ready';
  await until(() => window.__executionReviewSelectionConfirmed === true, 'native-selection-confirmation');
  await until(() => trustedSelection, 'trusted-selection-click');
  await until(async () => {
    const blocked = (await control()).blocked;
    const value = blocked?.selection;
    return value?.request_id === blocked?.refresh?.request_id
      && value?.selected_file_count === 1 ? value : null;
  }, 'authoritative blocked selection');
  await until(() => {
    const row = [...blockedInventory.querySelectorAll(
      '.nami-inventory-review__rows > .nami-tree-row[role="treeitem"][data-node-id]'
    )].find((value) => value.dataset.nodeId === fallbackRow.dataset.nodeId);
    const checkbox = row?.querySelector(
      ':scope > .nami-file-row__selection > input[data-action="inventory-select-row"]');
    return checkbox?.isConnected === true && checkbox.checked;
  }, 'blocked selection state');
  window.__executionReviewBlockedStage = 'blocked-fallback-control';
  const fallbackControl = await until(() => {
    const value = action(blockedInventory, 'inventory-verify');
    return value instanceof HTMLButtonElement && value.isConnected && !value.hidden
      && value.closest('[hidden]') === null && !value.disabled
      && value.textContent.trim() === 'Verify selected' ? value : null;
  }, 'ordinary fallback control');
  const fallbackVisible = usable(blockedInventory, 'verify-copied-files') !== null
    && usable(blockedInventory, 'inventory-baseline') !== null
    && usable(blockedInventory, 'inventory-baseline-menu') !== null;
  if (!fallbackVisible) throw new Error('copied action was forfeited by Refresh');
  const fallback = await until(() => usable(blockedInventory, 'inventory-verify'), 'ordinary fallback');
  if (fallback !== fallbackControl) throw new Error('ordinary fallback control changed after selection');
  fallback.click();
  const ordinaryPause = await until(() => usable(blockedInventory, 'inventory-pause'), 'ordinary pause');
  ordinaryPause.click();
  const ordinaryResume = await until(() => usable(blockedInventory, 'inventory-resume'), 'ordinary resume');
  ordinaryResume.click();
  await until(async () => {
    const value = (await control()).blocked;
    return value?.ordinary !== null
      && value?.auxiliary_releases?.some((item) => item.session_id === value.ordinary.session_id)
      && value?.inventory_window?.integrity_session_id === value.ordinary.session_id
      && value?.inventory_window?.integrity_complete === true ? value : null;
  }, 'ordinary terminal overlay');
  const ordinaryDetails = usable(blockedInventory, 'inventory-details');
  if (ordinaryDetails.ariaExpanded !== 'true') ordinaryDetails.click();
  const ordinaryResult = await until(() => {
    const value = blockedInventory.querySelector('.nami-plan-review__status-title');
    return value instanceof HTMLElement && value.closest('[hidden]') === null
      && value.textContent === 'Verification completed'
      && visibleFact(blockedInventory, '.nami-inventory-review__rows [data-integrity-state="verified"]') !== null
      && usable(blockedInventory, 'inventory-pause') === null
      && usable(blockedInventory, 'inventory-resume') === null
      && blockedInventory.querySelector('[data-inventory-integrity-facts]') === null ? value : null;
  }, 'ordinary result');
  const ordinaryResultVisible = ordinaryResult.isConnected;
  const ordinaryRow = visibleFact(blockedInventory, '.nami-inventory-review__rows [data-integrity-state="verified"]');
  const ordinaryRowVisible = ordinaryRow !== null;
  const blockedClose = blockedCard.parentElement?.querySelector('.nami-task-rail__close');
  if (!(blockedClose instanceof HTMLButtonElement) || blockedClose.disabled) throw new Error('blocked Close unavailable');
  blockedClose.click();
  await until(async () => !blockedCard.isConnected && (await control()).blocked?.close !== null, 'blocked Close');
  const closedBoth = document.querySelectorAll('.nami-task-rail__row .nami-task-card').length === 0;
  return {
    geometry: window.__executionReviewGeometry,
    retention,
    actions: {
      copiedActionVisible, copiedResultVisible, copiedRowVisible, fallbackVisible,
      ordinaryResultVisible, ordinaryRowVisible, closedBoth, refreshSubmittedOnce,
    },
  };
})()
"""


def _drive(window: object, phase: _ExecutionReviewJourney, recorder: _Recorder, retained: list[object], screenshot: Path) -> None:
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
    page_result: object = None

    wait_execute = r"""(async()=>{for(let i=0;i<1200;i++){if(window.__executionReviewStage==='execute-ready')return window.__executionReviewExecutePoint;await new Promise(r=>setTimeout(r,25));}throw new Error('execute');})()"""
    wait_selection = r"""
    (async () => {
      for (let i = 0; i < 1200; i += 1) {
        if (window.__executionReviewStage === 'selection-ready') {
          return window.__executionReviewSelectionPoint;
        }
        await new Promise((resolve) => setTimeout(resolve, 25));
      }
      const inventory = document.querySelector('.nami-inventory-review');
      const fallback = inventory?.querySelector('[data-action="inventory-verify"]');
      const row = [...(inventory?.querySelectorAll(
        '.nami-inventory-review__rows > .nami-tree-row[role="treeitem"][data-node-id]'
      ) ?? [])].find((value) => value.querySelector(
        '.nami-file-row__name-text')?.textContent === 'one.txt') ?? null;
      const checkbox = row?.querySelector(
        ':scope > .nami-file-row__selection > input[data-action="inventory-select-row"]');
      const bounds = checkbox?.getBoundingClientRect();
      const point = bounds === undefined ? null
        : {x:(bounds.left+bounds.right)/2, y:(bounds.top+bounds.bottom)/2};
      const booleans = {
        verifyVisible: inventory instanceof HTMLElement && inventory.isConnected
          && inventory.closest('[hidden]') === null,
        fallbackLabelCurrent: fallback?.textContent.trim() === 'Verify selected',
        fallbackVisible: fallback instanceof HTMLButtonElement && fallback.isConnected
          && !fallback.hidden && fallback.closest('[hidden]') === null,
        fallbackDisabled: fallback instanceof HTMLButtonElement && fallback.disabled,
        fixtureRowPresent: row instanceof HTMLElement && row.isConnected,
        checkboxConnected: checkbox instanceof HTMLInputElement && checkbox.isConnected,
        checkboxDisabled: checkbox instanceof HTMLInputElement && checkbox.disabled,
        checkboxChecked: checkbox instanceof HTMLInputElement && checkbox.checked,
        checkboxHittable: checkbox instanceof HTMLInputElement && point !== null
          && bounds.width > 0 && bounds.height > 0
          && document.elementFromPoint(point.x, point.y) === checkbox,
      };
      return {timeout:true, blockedStage:window.__executionReviewBlockedStage ?? null,
        booleans};
    })()
    """
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
      const progress = window.__executionReviewProgress ?? {};
      const clickedRow = window.__executionReviewClickedRow;
      const clickedNodeId = window.__executionReviewClickedNodeId;
      const currentMatchingRow = [...document.querySelectorAll(
        '.nami-plan-review__rows [data-node-id]'
      )].find((value) => value.dataset.nodeId === clickedNodeId) ?? null;
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
        executionObserved: state?.exact?.execution !== null && state?.exact?.execution !== undefined,
        releaseObserved: state?.exact?.release !== null && state?.exact?.release !== undefined,
        windowObserved: state?.exact?.window !== null && state?.exact?.window !== undefined,
        reviewReady: state?.exact?.review_ready === true,
        phaseFailureObserved: (state?.exact?.failure !== null && state?.exact?.failure !== undefined)
          || (state?.blocked?.failure !== null && state?.blocked?.failure !== undefined),
        scrollObserved: progress.scrollObserved === true,
        visibleFixtureFileRowObserved: progress.visibleFixtureFileRowObserved === true,
        rowClickDispatched: progress.rowClickDispatched === true,
        detailObserved: progress.detailObserved === true,
        clickedRowConnectedBeforeClick: progress.clickedRowConnectedBeforeClick === true,
        clickedRowConnectedAfterClick: progress.clickedRowConnectedAfterClick === true,
        rowClickEventObserved: progress.rowClickEventObserved === true,
        highlightMutationAdmitted: state?.exact?.highlight_mutation?.node_id === clickedNodeId
          && Number.isSafeInteger(state.exact.highlight_mutation.admitted),
        highlightMutationCompleted: state?.exact?.highlight_mutation?.node_id === clickedNodeId
          && Number.isSafeInteger(state.exact.highlight_mutation.completed),
        postHighlightWindowAdmitted: state?.exact?.highlight_mutation?.node_id === clickedNodeId
          && Number.isSafeInteger(state?.exact?.post_highlight_window?.admitted),
        postHighlightWindowCompleted: state?.exact?.highlight_mutation?.node_id === clickedNodeId
          && state?.exact?.post_highlight_window?.matches_mutation === true
          && Number.isSafeInteger(state.exact.post_highlight_window.completed),
        currentMatchingRowHighlightedAtTimeout: currentMatchingRow?.dataset.highlighted === 'true'
          && currentMatchingRow.getAttribute('aria-selected') === 'true',
        originalClickedRowConnectedAtTimeout: clickedRow?.isConnected === true,
        executionDetailAdmitted: Number.isSafeInteger(
          state?.exact?.execution_detail_attempt?.admitted),
        executionDetailCompleted: Number.isSafeInteger(
          state?.exact?.execution_detail_attempt?.completed),
      };
    })()
    """

    def identity_expression() -> str:
        snapshot = phase.snapshot()
        execution, detail = snapshot["exact"]["execution"], snapshot["exact"]["detail"]
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
            operationPath:fact('Target path'),rowHighlighted:row?.dataset.highlighted==='true',
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
            recorder.fail(
                "wait-review", "RuntimeError", phase.capture_readiness_diagnostic(),
            )
            return
        phase.verify_exact_files()
        cdp.evaluate(identity_expression(), before_capture, "pre-identity")

    def before_capture(value: object) -> None:
        phase.set_identity("pre", value)
        cdp.capture(screenshot, decoded, "capture")

    def decoded() -> None:
        nonlocal decoded_dimensions
        dimensions = decode_png(screenshot)
        decoded_dimensions = dimensions
        cdp.evaluate(identity_expression(), rechecked, "post-identity")

    def rechecked(value: object) -> None:
        phase.set_identity("post", value)
        cdp.evaluate("window.__executionReviewCaptureAck=true;true", acknowledged, "ack")

    def acknowledged(value: object) -> None:
        if value is not True:
            raise RuntimeError("capture acknowledgement failed")
        phase.acknowledge_capture()
        cdp.evaluate(wait_selection, select_fallback, "wait-selection")
        complete_if_ready()

    def selection_confirmed(_value: object) -> None:
        cdp.evaluate("window.__executionReviewSelectionConfirmed=true;true", lambda _v: None,
                     "confirm-selection")

    def write_selection_timeout(value: object) -> None:
        expected = {"timeout", "blockedStage", "booleans"}
        if (type(value) is not dict or set(value) != expected or value["timeout"] is not True
                or value["blockedStage"] not in _BLOCKED_STAGES
                or type(value["booleans"]) is not dict
                or set(value["booleans"]) != _SELECTION_TIMEOUT_DOM_BOOLS
                or any(type(item) is not bool for item in value["booleans"].values())):
            raise RuntimeError("selection timeout diagnostic is invalid")
        blocked = phase.snapshot()["blocked"]
        refresh = blocked["refresh"]
        refresh_observed = type(refresh) is dict
        failure = phase.blocked.phase_failure_trace()
        phase_failure = failure["type"]
        phase_failure_command = failure["command"]
        backend = {
            "refreshObserved": refresh_observed,
            "refreshReleaseObserved": refresh_observed and any(
                type(item) is dict and item.get("session_id") == refresh.get("session_id")
                for item in blocked["auxiliary_releases"]
            ),
            "currentInventoryObserved": bool(blocked["inventory_open"] is not None),
            "phaseFailureObserved": phase_failure is not None,
        }
        diagnostic = {
            "timeout": True,
            "blockedStage": value["blockedStage"],
            "phaseFailureType": phase_failure,
            "phaseFailureCommand": phase_failure_command,
            "booleans": {**backend, **value["booleans"]},
        }
        if ((phase_failure is not None and type(phase_failure) is not str)
                or (phase_failure_command is not None
                    and phase_failure_command not in _COMMANDS)
                or set(diagnostic["booleans"]) != _SELECTION_TIMEOUT_BOOLS):
            raise RuntimeError("selection timeout diagnostic is invalid")
        recorder.driver.with_name("selection-timeout-diagnostic.json").write_text(
            json.dumps(diagnostic, sort_keys=True), encoding="utf-8",
        )

    def write_scroll_diagnostic(value: object) -> None:
        if type(value) is not dict or set(value) != _SCROLL_DIAGNOSTIC_POINTS:
            raise RuntimeError("scroll retention diagnostic is invalid")
        for fact in value.values():
            if type(fact) is not dict or set(fact) != {"scrollTop", "clientHeight", "scrollHeight"}:
                raise RuntimeError("scroll retention diagnostic is invalid")
            if any(item is not None and (type(item) is not int or item < 0)
                   for item in fact.values()):
                raise RuntimeError("scroll retention diagnostic is invalid")
        recorder.driver.with_name("scroll-retention-diagnostic.json").write_text(
            json.dumps(value, sort_keys=True), encoding="utf-8",
        )

    def write_scroll_interaction_diagnostic(value: object) -> None:
        if type(value) is not dict or set(value) != _SCROLL_INTERACTION_POINTS:
            raise RuntimeError("scroll interaction diagnostic is invalid")
        for point, fact in value.items():
            if fact is None:
                if point != "firstDisconnection":
                    raise RuntimeError("scroll interaction diagnostic is invalid")
                continue
            if type(fact) is not dict or set(fact) != _SCROLL_INTERACTION_FACT:
                raise RuntimeError("scroll interaction diagnostic is invalid")
            numbers = {
                name: item for name, item in fact.items()
                if name in {"scrollTop", "clientHeight", "scrollHeight", "listTop",
                            "listBottom", "rowTop", "rowBottom"}
            }
            booleans = {name: item for name, item in fact.items() if name not in numbers}
            if (any(type(item) is not int or abs(item) > 1_000_000
                    for item in numbers.values())
                    or any(type(item) is not bool for item in booleans.values())):
                raise RuntimeError("scroll interaction diagnostic is invalid")
        recorder.driver.with_name("scroll-interaction-diagnostic.json").write_text(
            json.dumps(value, sort_keys=True), encoding="utf-8",
        )

    def write_selection_foreground_diagnostic(
        stage: str, observed_handle: int | None, owned_handle: int,
        reason: str = "foreground-changed",
    ) -> None:
        if (stage not in {"wait-selection-callback", "selection-target-callback"}
                or (observed_handle is not None and type(observed_handle) is not int)
                or type(owned_handle) is not int or owned_handle <= 0):
            raise RuntimeError("selection foreground diagnostic is invalid")
        recorder.driver.with_name("selection-foreground-diagnostic.json").write_text(
            json.dumps({
                "stage": stage,
                "observedHandle": observed_handle,
                "ownedHandle": owned_handle,
                "reason": reason,
            }, sort_keys=True),
            encoding="utf-8",
        )

    def select_fallback(point: object) -> None:
        nonlocal failed
        if type(point) is dict and point.get("timeout") is True:
            write_selection_timeout(point)
            failed = True
            recorder.fail("wait-selection", "RuntimeError")
            return
        owned_handle = int(native.Handle.ToInt64())
        def refused(facts: dict[str, object]) -> None:
            write_selection_foreground_diagnostic(
                "wait-selection-callback", facts["observedHandle"], owned_handle,
                facts["reason"],
            )
            fail(RuntimeError("native execution foreground deadline expired"),
                 None, "wait-selection-foreground", "foreground")
        wait_for_foreground(
            owned_handle, activate=native.Activate,
            ready=lambda: cdp.evaluate("window.__executionReviewSelectionTarget()",
                                       dispatch_fallback, "selection-target"),
            refused=refused, retained=retained,
        )

    def dispatch_fallback(point: object) -> None:
        if type(point) is not dict or set(point) != {"x", "y"}:
            raise RuntimeError("selection point missing")
        observed_handle = foreground_window_handle()
        owned_handle = int(native.Handle.ToInt64())
        if observed_handle != owned_handle:
            write_selection_foreground_diagnostic(
                "selection-target-callback", observed_handle, owned_handle,
            )
            raise RuntimeError("native execution window is not foreground")
        cdp.call(
            "Input.dispatchMouseEvent",
            {"type": "mousePressed", "button": "left", "buttons": 1, "clickCount": 1, **point},
            lambda _v: cdp.call(
                "Input.dispatchMouseEvent",
                {"type": "mouseReleased", "button": "left", "buttons": 0,
                 "clickCount": 1, **point},
                selection_confirmed, "selection-up",
            ),
            "selection-down",
        )

    def complete_if_ready() -> None:
        dimensions = decoded_dimensions
        value = page_result
        if value is None or not phase.exact.capture_complete:
            return
        if dimensions is None:
            raise RuntimeError("page completed before native capture decode")
        if (type(value) is not dict or set(value.get("geometry", {})) != _GEOMETRY
                or set(value.get("retention", {})) != _RETENTION
                or set(value.get("actions", {})) != _ACTIONS
                or any(item is not True for item in value["retention"].values())
                or any(item is not True for item in value["actions"].values())
                or not phase.finished_ready()):
            raise RuntimeError("execution geometry evidence is invalid")
        phase.verify_files()
        recorder.complete({
            "geometry": value["geometry"], "retention": value["retention"],
            "actions": value["actions"], "dimensions": list(dimensions),
            "phase": phase.snapshot(),
        })

    def finished(value: object) -> None:
        nonlocal page_result
        if type(value) is dict and "preclick" in value:
            recorder.fail("page-preclick", "PointerTargetError", value["preclick"])
            return
        if type(value) is dict and "retentionFailure" in value:
            write_scroll_diagnostic(value.get("scrollDiagnostic"))
            write_scroll_interaction_diagnostic(value.get("scrollInteractionDiagnostic"))
            recorder.fail("plan-retention", "RetentionError", value["retentionFailure"])
            return
        if (type(value) is not dict or set(value.get("geometry", {})) != _GEOMETRY
                or set(value.get("retention", {})) != _RETENTION
                or set(value.get("actions", {})) != _ACTIONS):
            raise RuntimeError("execution geometry evidence is invalid")
        page_result = value
        complete_if_ready()

    def confirmed(_value: object) -> None:
        cdp.evaluate("window.__executionReviewNativeConfirmed=true;true", lambda _v: cdp.evaluate(wait_capture, capture_ready, "wait-review"), "confirm-observed")

    def execute(point: object) -> None:
        if type(point) is not dict:
            raise RuntimeError("execute point missing")
        phase.bind_visible_label(point["taskLabel"])
        def dispatch_execute(current: object) -> None:
            if (type(current) is not dict
                    or foreground_window_handle() != int(native.Handle.ToInt64())):
                raise RuntimeError("native Execute target is unavailable")
            cdp.call("Input.dispatchMouseEvent", {"type":"mousePressed","button":"left","buttons":1,"clickCount":1,**current}, lambda _v: cdp.call("Input.dispatchMouseEvent", {"type":"mouseReleased","button":"left","buttons":0,"clickCount":1,**current}, confirmed, "execute-up"), "execute-down")

        def refused(facts: dict[str, object]) -> None:
            recorder.driver.with_name("execute-foreground-diagnostic.json").write_text(
                json.dumps(facts, sort_keys=True), encoding="utf-8",
            )
            fail(RuntimeError("native Execute foreground deadline expired"),
                 None, "execute-foreground", "foreground")

        wait_for_foreground(
            int(native.Handle.ToInt64()), activate=native.Activate,
            ready=lambda: cdp.evaluate(r"""(() => {
              const button = document.querySelector('.nami-plan-review [data-action="execute"]');
              if (!button?.isConnected || button.disabled || !document.hasFocus()
                  || document.activeElement !== button) throw new Error('Execute focus changed');
              const rect = button.getBoundingClientRect();
              const point = {x:(rect.left+rect.right)/2,y:(rect.top+rect.bottom)/2};
              if (rect.width <= 0 || rect.height <= 0 || point.x < 0 || point.y < 0
                  || point.x >= innerWidth || point.y >= innerHeight
                  || document.elementFromPoint(point.x, point.y) !== button) {
                throw new Error('Execute hit target changed');
              }
              return point;
            })()""", dispatch_execute, "execute-current-target"),
            refused=refused, retained=retained,
        )

    cdp.evaluate(_PAGE, finished, "page")
    cdp.evaluate(wait_execute, execute, "wait-execute")


def _runtime_identity() -> dict[str, object]:
    import namisync
    return {"executable": str(Path(sys.executable).resolve()), "namisync_file": str(Path(namisync.__file__).resolve()), "versions": {name: importlib.metadata.version(name) for name in ("namisync", "pywebview", "pythonnet")}}


def _run(arguments: argparse.Namespace, recorder: _Recorder) -> int:
    from namisync.interfaces.web import host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    phase = _ExecutionReviewJourney(
        arguments.source, arguments.target,
        arguments.blocked_source, arguments.blocked_target,
    )
    recorder.phase = phase
    retained: list[object] = []
    original = host._configure_window_appearance
    original_commands = host._production_commands
    from namisync.workflows.runtime import LocalWorkflowRuntime
    original_verify = LocalWorkflowRuntime.open_verify

    def open_verify(runtime: object, checkpoint: object) -> object:
        invocation = original_verify(runtime, checkpoint)
        run = invocation.run
        root = Path(checkpoint.binding.selected_mount) / checkpoint.binding.volume_relative_path
        owner = phase.exact if root == phase.exact.target else phase.blocked
        def gated(context: object) -> object:
            owner.worker_entered.set()
            if not owner.worker_release.wait(30):
                raise TimeoutError("ordinary verification worker gate timed out")
            context.checkpoint()
            return run(context)
        invocation.run = gated
        return invocation

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
        stack.enter_context(patch.object(LocalWorkflowRuntime, "open_verify", open_verify))
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
    parser.add_argument("--blocked-source", required=True, type=Path)
    parser.add_argument("--blocked-target", required=True, type=Path)
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
