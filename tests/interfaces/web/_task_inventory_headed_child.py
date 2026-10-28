"""Installed-wheel child for the native inventory and integrity action witness."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from math import isfinite
import sys
import threading
from time import monotonic
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from typing import Callable
from unittest.mock import patch

from _headed_cdp import NativeCdp, decode_png, failure_site, runtime_value
from _headed_evidence import EvidencePaths, EvidencePublisher
from _headed_native import foreground_window_handle
from _startup_test_support import headed_command_extension


_COMMANDS = frozenset({"refresh_inventory", "acknowledge_inventory", "restore_inventory",
                       "set_inventory_selection", "set_inventory_highlighted_selection",
                       "mutate_inventory_highlight", "start_inventory_integrity", "control_integrity"})
_READ_COMMANDS = frozenset({"get_inventory_anchor"})
_FILE_BYTES = b"NamiSync native inventory fixture\r\n"
_RANGE_STAGES = ("range-folder", "range-file-toggle", "range-file-checkbox", "range-file-recheck", "range-reset", "range-anchor", "range-toggle", "range-end", "range-checkbox", "range-clear")
_INTEGRITY_STAGES = ("select-folder", "select-location-clear", "select-location", "baseline",
                     "verify", "follow-go", "pause", "resume", "verify-cancel", "cancel",
                     "baseline-menu-open", "baseline-menu-close", "baseline-menu-reopen",
                     "rebaseline-cancel-open", "rebaseline-cancel", "rebaseline-menu-open", "rebaseline-open", "rebaseline-confirm")
_CONFIRMATION_EXIT_FACT_KEYS = frozenset({
    "closed", "app_active", "theme_active", "scroll_restored", "focus_restored",
    "trigger_connected", "trigger_disabled", "trigger_hidden", "active_category",
})
_CONFIRMATION_ACTIVE_CATEGORIES = frozenset({
    "trigger", "dialog", "inventory", "body", "other",
})
_OWN_FAILURES = frozenset({
    "inventory command evidence is incomplete",
    "inventory action identities or actual effects differ",
    "inventory publication was not replaced",
    "native inventory page result is invalid",
    "native inventory window is not foreground",
    "native inventory point is invalid",
    "native inventory click target is unavailable",
    "inventory fixture identity is unavailable",
    "initial inventory loading witness timed out",
    "initial inventory loading witness is invalid",
    "initial inventory scanner did not enter",
    "native integrity runner did not enter before control",
    "native integrity Follow identity differs",
    "native integrity control witness timed out",
    "native integrity control did not leave held invocation",
    "integrity capture has no task identity",
    "integrity capture preceded terminal release",
    "native integrity detail identity differs",
    "native integrity command identity or control differs",
    "native integrity terminal reconciliation differs",
    "native integrity durable ledger differs",
    "native integrity durable hash differs",
    "inventory integrity state remained after Close",
}) | frozenset(f"inventory {name} did not have one original command" for name in _COMMANDS)


def _owned_failure(error: BaseException) -> str | None:
    message = str(error)
    return message if message in _OWN_FAILURES else None


def _bounded_confirmation_exit_diagnostic(value: object) -> dict[str, object] | None:
    if type(value) is not dict or set(value) != {"last_close", "timeout"}:
        return None
    bounded: dict[str, object] = {}
    for name in ("last_close", "timeout"):
        facts = value[name]
        if facts is None:
            bounded[name] = None
            continue
        if type(facts) is not dict or set(facts) != _CONFIRMATION_EXIT_FACT_KEYS:
            return None
        if any(type(facts[key]) is not bool for key in _CONFIRMATION_EXIT_FACT_KEYS
               if key != "active_category"):
            return None
        if facts["active_category"] not in _CONFIRMATION_ACTIVE_CATEGORIES:
            return None
        bounded[name] = {key: facts[key] for key in sorted(_CONFIRMATION_EXIT_FACT_KEYS)}
    return bounded


def _bounded_integrity_custody_diagnostic(value: object) -> dict[str, object] | None:
    booleans = {"checkbox_custody", "range_custody", "cancel_preserved_result", "scan_selected",
                "range_checkbox_focused", "range_checkbox_connected", "range_checkbox_disabled"}
    scrolls = {"range_scroll_before", "range_scroll_after"}
    if type(value) is not dict or set(value) != booleans | scrolls | {"range_active_category"}:
        return None
    if any(type(value[key]) is not bool for key in booleans):
        return None
    if any(type(value[key]) not in {int, float} or not isfinite(value[key])
           or value[key] < 0 for key in scrolls):
        return None
    if value["range_active_category"] not in {"checkbox", "tree", "inventory", "body", "other"}:
        return None
    return {key: value[key] for key in sorted(value)}


def _bounded_follow_custody_diagnostic(value: object) -> dict[str, bool] | None:
    keys = {"active_retained", "old_active_represented", "active_cleared", "active_allowed",
            "selection_preserved", "query_preserved", "focus_preserved", "enable_hidden"}
    if type(value) is not dict or set(value) != keys or any(type(value[key]) is not bool for key in keys):
        return None
    return {key: value[key] for key in sorted(keys)}


def _bounded_refresh_viewport(value: object) -> dict[str, object] | None:
    keys = {"setup", "first_arrow", "second_arrow", "before_focus", "after_focus",
            "before", "after", "minimum", "scroll_height", "client_height"}
    if type(value) is not dict or set(value) != keys:
        return None
    if any(item is not None and (type(item) not in {int, float} or not isfinite(item)
           or not 0 <= item <= 2**31) for item in value.values()):
        return None
    return {key: value[key] for key in sorted(keys)}


def _bounded_stage_diagnostic(value: object) -> dict[str, object] | None:
    keys = {"stage", "pending_wait", "listened_control_connected", "popup_open_count", "popup_close_count"}
    if type(value) is not dict or set(value) != keys:
        return None
    for key in ("stage", "pending_wait"):
        label = value[key]
        if label is not None and (type(label) is not str or not 1 <= len(label) <= 96
                or not label.isascii() or any(not (char.isalnum() or char == "-") for char in label)):
            return None
    if value["listened_control_connected"] is not None and type(value["listened_control_connected"]) is not bool:
        return None
    if any(type(value[key]) is not int or not 0 <= value[key] <= 65535
           for key in ("popup_open_count", "popup_close_count")):
        return None
    return {key: value[key] for key in sorted(keys)}


class _InventoryPhase:
    def __init__(self, source: Path) -> None:
        self.source = source
        self.lock = threading.Lock()
        self.registry: object | None = None
        self.initial: dict[str, object] | None = None
        self.fixture: dict[str, object] | None = None
        self.commands: list[dict[str, object]] = []
        self.failure: dict[str, object] | None = None
        self.initial_scan_entered = threading.Event()
        self.initial_scan_release = threading.Event()
        self.verify_runner_entered = threading.Event()
        self.verify_release = threading.Event()
        self.verify_gate_pending = False
        self.verify_runner_calls = 0
        self.verify_items: list[dict[str, str]] = []
        self.verify_control_entries: list[str] = []
        self.integrity_results: list[dict[str, object]] = []

    def bind(self, registry: object) -> None:
        from namisync.workflows import LocationCandidate

        self.source.mkdir(parents=True, exist_ok=True)
        if any(self.source.iterdir()):
            raise RuntimeError("inventory fixture root must start empty")
        folder = self.source / "folder"
        folder.mkdir()
        (folder / "one.txt").write_bytes(_FILE_BYTES)
        (folder / "two.txt").write_bytes(_FILE_BYTES)
        (folder / "zz.txt").write_bytes(_FILE_BYTES)
        for index in range(300):
            (folder / f"z-scroll-{index:03}").mkdir()
        shell = registry.create_task_shell("a" * 32)
        runtime = registry._lifecycle._runtime
        original = runtime._inventory_deps
        from namisync.core.integrity import IntegrityMode
        original_verify = runtime._integrity_deps.runners[IntegrityMode.VERIFY]

        def gated_verify(selection: object, context: object, recorder: object) -> object:
            from namisync.core.events import Progress
            with self.lock:
                self.verify_runner_calls += 1
                held = self.verify_gate_pending
                self.verify_gate_pending = False
                before_runner = held and self.verify_runner_calls > 1
                if before_runner:
                    self.verify_runner_entered.set()
            # Only the first Verify needs a real item for Follow. The later
            # cancel witness retains its original zero-outcome pre-run edge.
            if before_runner:
                if not self.verify_release.wait(60):
                    raise RuntimeError("native integrity control witness timed out")
                context.run.checkpoint()
                raise RuntimeError("native integrity control did not leave held invocation")
            def observe(body: object) -> None:
                nonlocal held
                context.run.emit(body)
                if held and type(body) is Progress and body.item_type == "integrity" and body.item_id is not None:
                    held = False
                    with self.lock:
                        self.verify_items.append({"item_id": body.item_id, "item_type": body.item_type})
                        self.verify_runner_entered.set()
                    if not self.verify_release.wait(60):
                        raise RuntimeError("native integrity control witness timed out")
                    context.run.checkpoint()
                    raise RuntimeError("native integrity control did not leave held invocation")
            observed = replace(context, run=replace(context.run, emit=observe), progress_interval_seconds=0)
            return original_verify(selection, observed, recorder)

        runtime._integrity_deps.runners[IntegrityMode.VERIFY] = gated_verify

        def delayed_scan(*args: object, **kwargs: object) -> object:
            self.initial_scan_entered.set()
            if not self.initial_scan_release.wait(60):
                raise RuntimeError("initial inventory loading witness timed out")
            return original.scanner(*args, **kwargs)

        runtime._inventory_deps = replace(original, scanner=delayed_scan)
        try:
            started = registry.start_setup_inventory(
                shell.task_id, LocationCandidate.literal(str(self.source)),
                command_id="b" * 32, wire_intent=("headed-inventory", str(self.source)),
            )
            if not self.initial_scan_entered.wait(10):
                self.initial_scan_release.set()
                raise RuntimeError("initial inventory scanner did not enter")
        finally:
            runtime._inventory_deps = original
        with self.lock:
            self.registry = registry
            self.initial = {"task_id": started.task_id, "request_id": started.request_id,
                            "session_id": started.session_id}

    def remove_fixture_file(self) -> dict[str, object]:
        from namisync.core.pathing import normalize_relative_path

        with self.lock:
            registry, initial = self.registry, self.initial
        if registry is None or initial is None:
            raise RuntimeError("inventory registry is not bound")
        task = next((item for item in registry.list_tasks().tasks
                     if item.task_id == initial["task_id"]), None)
        view = registry.open_inventory_view(initial["task_id"])
        if (task is None or not task.session_released or view["request_id"] != initial["request_id"]
                or not view["scan_complete"]):
            raise RuntimeError("initial inventory is not a released complete publication")
        projection = registry._inventory_views[initial["task_id"]].projection
        folder = projection.nodes[projection.position_by_path_key[normalize_relative_path("folder")]]
        missing = projection.nodes[projection.position_by_path_key[normalize_relative_path(r"folder\two.txt")]]
        first = projection.nodes[projection.position_by_path_key[normalize_relative_path(r"folder\one.txt")]]
        last = projection.nodes[projection.position_by_path_key[normalize_relative_path(r"folder\zz.txt")]]
        fixture = {"folder_node_id": folder.node_id, "missing_node_id": missing.node_id,
                   "first_node_id": first.node_id, "last_node_id": last.node_id,
                   "first_item_id": f"{first.row.location_id}:{first.row.row_id}",
                   "folder_display": folder.display, "missing_display": Path(missing.rel_path).name,
                   "folder_path": str(self.source / "folder"), "missing_path": missing.rel_path,
                   "domain_count": projection.nodes[0].rollup.domain_count}
        if not folder.is_container or missing.row is None:
            raise RuntimeError("inventory fixture identity is unavailable")
        with self.lock:
            self.fixture = fixture
        target = self.source / "folder" / "two.txt"
        if target.read_bytes() != _FILE_BYTES:
            raise RuntimeError("inventory source bytes changed before refresh")
        target.unlink()
        return fixture

    def wrap(self, commands: object) -> object:
        from namisync.interfaces.web.commands import CommandSpec

        wrapped = dict(commands)
        for name in _COMMANDS | _READ_COMMANDS:
            spec = wrapped[name]
            if type(spec) is not CommandSpec:
                raise TypeError("inventory command is not an exact CommandSpec")
            wrapped[name] = replace(spec, handler=self._observe(name, spec.handler))
        return wrapped

    def _observe(self, name: str, original: Callable[[object], object]) -> Callable[[object], object]:
        from namisync.interfaces.web.bridge import to_primitive_view

        def invoke(payload: object) -> object:
            if name == "start_inventory_integrity":
                if any(item["command"] == name for item in self.commands):
                    self.capture_integrity()
                if payload.mode == "verify":
                    with self.lock:
                        self.verify_runner_entered.clear()
                        self.verify_release.clear()
                        self.verify_gate_pending = True
            try:
                result = original(payload)
            except BaseException as error:
                with self.lock:
                    if self.failure is None:
                        self.failure = {"command": name, "stage": "original", "reason": type(error).__name__,
                                        "assertion": _owned_failure(error)}
                raise
            record = {"command": name, "result": result, "original_result_type": type(result).__name__}
            with self.lock:
                self.commands.append(record)
                try:
                    record["result"] = to_primitive_view(result)
                    record.update({"task_id": payload.task_id,
                                   "request_id": getattr(payload, "request_id", None),
                                   "command_id": getattr(payload, "command_id", None),
                                   "node_id": getattr(payload, "node_id", None)})
                    if name in {"set_inventory_selection", "set_inventory_highlighted_selection"}:
                        record.update({"selected": payload.selected, "expected_revision": payload.expected_revision})
                    elif name == "start_inventory_integrity":
                        record.update({"mode": payload.mode, "accept_current_evidence": payload.accept_current_evidence,
                                       "session_id": result.session_id, "next_request_id": result.request_id})
                    elif name == "control_integrity":
                        record.update({"session_id": payload.session_id, "action": payload.action})
                    elif name == "get_inventory_anchor":
                        record.update({"session_id": payload.session_id, "item_id": payload.item_id,
                                       "expected_revision": payload.expected_revision})
                    if name == "refresh_inventory":
                        record.update({"request_id": result.request_id, "session_id": result.session_id,
                                       "prior_request_id": payload.request_id})
                except BaseException as error:
                    if self.failure is None:
                        self.failure = {"command": name, "stage": "observation", "reason": type(error).__name__,
                                        "assertion": _owned_failure(error)}
            if name == "control_integrity" and payload.action in {"pause", "cancel"} and result.accepted:
                self.verify_release.set()
            return result
        return invoke

    def capture_integrity(self) -> None:
        registry, initial = self.registry, self.initial
        if registry is None or initial is None:
            raise RuntimeError("integrity capture has no task identity")
        task = next(item for item in registry.list_tasks().tasks if item.task_id == initial["task_id"])
        if not task.session_released:
            raise RuntimeError("integrity capture preceded terminal release")
        view = registry.open_inventory_view(initial["task_id"])
        window = registry.get_inventory_window(initial["task_id"], expected_revision=view["view_revision"], offset=0, limit=256)
        ledger = registry._lifecycle._runtime.list_inventory(int(view["location_id"]))
        projection = registry._inventory_views[initial["task_id"]].projection
        details = [registry.get_inventory_detail(initial["task_id"], expected_revision=view["view_revision"], node_id=node.node_id)
                   for node in projection.nodes if node.row is not None and node.row.entry_kind is not None
                   and node.row.entry_kind.value == "file"]
        integrity = dict(window["integrity"])
        integrity["items"] = []
        for detail in details:
            overlay = detail["integrity"]
            if (detail["disposition"] != "current"
                    or {key: value for key, value in overlay.items() if key != "items"}
                    != {key: value for key, value in integrity.items() if key != "items"}):
                raise RuntimeError("native integrity detail identity differs")
            integrity["items"].extend(overlay["items"])
        rows = [{"path": row.rel_path, "presence": row.presence.value,
                 "digest": row.attestation.content.digest.hex() if row.attestation else None,
                 "algorithm": row.attestation.content.algorithm if row.attestation else None,
                 "evidence_at": row.attestation.content.observed_at.isoformat() if row.attestation else None,
                 "last_verified_at": row.last_verified_at.isoformat() if row.last_verified_at else None,
                 "verification_state": row.verification_state.value} for row in ledger]
        self.integrity_results.append({"request_id": view["request_id"],
                                       "scan_request_id": view["scan_request_id"],
                                       "scan_scope": view["scan_scope"],
                                       "visible_integrity": window["integrity"],
                                       "integrity": integrity, "ledger": rows})

    def observe_verify_runner_entry(self, action: str) -> bool:
        if action not in {"pause", "cancel"}:
            raise ValueError("native integrity runner entry action is invalid")
        if not self.verify_runner_entered.is_set():
            return False
        with self.lock:
            if not self.verify_runner_entered.is_set():
                return False
            self.verify_control_entries.append(action)
        return True

    def diagnostic(self) -> dict[str, object]:
        with self.lock:
            commands = list(self.commands)
            failure = self.failure
            verify_control_entries = list(self.verify_control_entries)
        return {
            "commands": [
                {"command": item["command"],
                 "result": item["result"] if type(item["result"]) is dict else None,
                 "original_result_type": item["original_result_type"]}
                for item in commands[:64]
            ],
            "wrapper_failure": failure,
            "initial_scan_entered": self.initial_scan_entered.is_set(),
            "initial_scan_released": self.initial_scan_release.is_set(),
            "verify_runner_entered": self.verify_runner_entered.is_set(),
            "verify_runner_calls": self.verify_runner_calls,
            "verify_items": list(self.verify_items),
            "verify_control_entries": verify_control_entries,
        }

    def report(self) -> dict[str, object]:
        with self.lock:
            registry, initial = self.registry, self.initial
            commands, failure, fixture = list(self.commands), self.failure, self.fixture
            verify_control_entries = list(self.verify_control_entries)
        if registry is None or initial is None or failure is not None or fixture is None:
            raise RuntimeError("inventory command evidence is incomplete")
        def matching(name: str, expected: int) -> list[dict[str, object]]:
            matches = [item for item in commands if item["command"] == name]
            if len(matches) != expected:
                raise RuntimeError(f"inventory {name} original command count differs")
            return matches
        refresh, selected_refresh = matching("refresh_inventory", 2)
        acknowledge, context_acknowledge = matching("acknowledge_inventory", 2)
        restore, context_restore = matching("restore_inventory", 2)
        if (refresh["prior_request_id"] != initial["request_id"]
                or refresh["request_id"] == initial["request_id"]
                or refresh["node_id"] is not None
                or selected_refresh["node_id"] != fixture["missing_node_id"]
                or selected_refresh["prior_request_id"] != refresh["request_id"]
                or selected_refresh["request_id"] == refresh["request_id"]
                or selected_refresh["command_id"] == refresh["command_id"]
                or acknowledge["request_id"] != refresh["request_id"]
                or restore["request_id"] != refresh["request_id"]
                or acknowledge["node_id"] != fixture["folder_node_id"]
                or restore["node_id"] != fixture["folder_node_id"]
                or any(item["task_id"] != initial["task_id"] for item in commands)
                or acknowledge["result"]["applied"] != 1
                or restore["result"]["applied"] != 1
                or context_acknowledge["node_id"] != fixture["missing_node_id"]
                or context_restore["node_id"] != fixture["folder_node_id"]
                or context_acknowledge["request_id"] != refresh["request_id"]
                or context_restore["request_id"] != refresh["request_id"]
                or context_acknowledge["command_id"] == acknowledge["command_id"]
                or context_restore["command_id"] == restore["command_id"]
                or context_acknowledge["result"]["applied"] != 1
                or context_restore["result"]["applied"] != 1):
            raise RuntimeError("inventory action identities or actual effects differ")
        self.capture_integrity()
        view = registry.open_inventory_view(initial["task_id"])
        selections = matching("set_inventory_selection", 4)
        highlighted = matching("set_inventory_highlighted_selection", 4)
        if ([item["selected"] for item in highlighted] != [False, True, True, False]
                or [item["result"]["selected_file_count"] for item in highlighted] != [2, 3, 3, 0]):
            raise RuntimeError("native integrity command identity or control differs")
        starts = matching("start_inventory_integrity", 4)
        controls = matching("control_integrity", 3)
        anchors = matching("get_inventory_anchor", 1)
        anchor = anchors[0]
        if (anchor["session_id"] != starts[1]["session_id"]
                or anchor["item_id"] != fixture["first_item_id"]
                or anchor["result"]["disposition"] != "current"
                or anchor["result"]["node_id"] != fixture["first_node_id"]
                or not self.verify_items or self.verify_items[0] != {
                    "item_id": fixture["first_item_id"], "item_type": "integrity"}):
            raise RuntimeError("native integrity Follow identity differs")
        if (view["scan_scope"] != {"kind": "selection", "path": None}
                or view["scan_request_id"] != starts[-1]["next_request_id"]):
            raise RuntimeError("inventory publication was not replaced")
        if ([item["node_id"] for item in selections] != [None, fixture["folder_node_id"], None, None]
                or [item["selected"] for item in selections] != [False, True, False, True]
                or [item["mode"] for item in starts] != ["baseline", "verify", "verify", "rebaseline"]
                or [item["accept_current_evidence"] for item in starts] != [False, False, False, True]
                or [item["action"] for item in controls] != ["pause", "resume", "cancel"]
                or [item["session_id"] for item in controls] != [starts[1]["session_id"], starts[1]["session_id"], starts[2]["session_id"]]
                or any(not item["result"]["accepted"] for item in controls)
                or len({item["command_id"] for item in starts}) != 4
                or verify_control_entries != ["pause", "cancel"]
                or self.verify_runner_calls != 3):
            raise RuntimeError("native integrity command identity or control differs")
        for index, (start, captured) in enumerate(zip(starts, self.integrity_results, strict=True)):
            overlay = captured["integrity"]
            expected_results = (["baselined", "baselined", "missing"] if index in {0, 3}
                                else ["missing", "verified", "verified"] if index == 1 else [])
            if (captured["scan_scope"] != {"kind": "selection", "path": None}
                    or captured["scan_request_id"] != start["next_request_id"]
                    or overlay["session_id"] != start["session_id"] or overlay["request_id"] != start["next_request_id"]
                    or not overlay["complete"] or overlay["gap"]
                    or sorted(item["result"] for item in overlay["items"]) != expected_results):
                raise RuntimeError("native integrity terminal reconciliation differs")
            present = [row for row in captured["ledger"] if row["presence"] == "present" and row["digest"] is not None]
            if ({row["path"] for row in present} != {r"folder\one.txt", r"folder\zz.txt"}
                    or any(row["verification_state"] != ("verified" if index in {1, 2} else "unverified") for row in present)):
                raise RuntimeError("native integrity durable ledger differs")
            from xxhash import xxh3_128
            expected_hash = xxh3_128()
            expected_hash.update(_FILE_BYTES)
            if any(row["digest"] != expected_hash.digest().hex() for row in present):
                raise RuntimeError("native integrity durable hash differs")
        return {"initial": initial, "fixture": fixture,
                "results": {"refresh": {"request_id": refresh["request_id"],
                                        "session_id": refresh["session_id"]},
                            "selected_refresh": {"request_id": selected_refresh["request_id"],
                                                 "session_id": selected_refresh["session_id"],
                                                 "node_id": selected_refresh["node_id"],
                                                 "prior_request_id": selected_refresh["prior_request_id"]},
                            "acknowledge": acknowledge["result"], "restore": restore["result"],
                            "context_acknowledge": {"node_id": context_acknowledge["node_id"],
                                                    "applied": context_acknowledge["result"]["applied"]},
                            "context_restore": {"node_id": context_restore["node_id"],
                                                "applied": context_restore["result"]["applied"]}},
                "publication": {"request_id": view["request_id"],
                                "view_revision": view["view_revision"],
                                "scan_request_id": view["scan_request_id"],
                                "scan_scope": view["scan_scope"],
                                "missing": view["rollup"]["missing"],
                                "acknowledged": view["rollup"]["acknowledged"]},
                "integrity_results": self.integrity_results,
                "integrity_commands": {"selections": selections, "starts": starts, "controls": controls,
                                       "anchors": anchors, "actual_items": list(self.verify_items),
                                       "highlighted_selections": highlighted,
                                       "runner_entry_controls": verify_control_entries}}

    def verify_closed(self) -> None:
        with self.lock:
            registry, initial = self.registry, self.initial
        if registry is None or initial is None:
            raise RuntimeError("inventory close has no task identity")
        if any(task.task_id == initial["task_id"] for task in registry.list_tasks().tasks):
            raise RuntimeError("inventory task remained after explicit Close")
        if initial["task_id"] in registry._inventory_views:
            raise RuntimeError("inventory publication remained after Close")
        if initial["task_id"] in registry._lifecycle._runtime._retained_inventory_integrity:
            raise RuntimeError("inventory integrity state remained after Close")
        if registry._start_responses or registry._lifecycle._visibility_receipts:
            raise RuntimeError("inventory command receipts remained after Close")


class _Recorder:
    def __init__(self, paths: EvidencePaths) -> None:
        self.publisher = EvidencePublisher(paths)
        self.lock = threading.Lock()
        self.settled = False

    def ready(self, report: dict[str, object]) -> None:
        with self.lock:
            if self.settled:
                return
            import namisync
            self.publisher.publish_ready({"report": report, "runtime": {
                "executable": str(Path(sys.executable).resolve()),
                "namisync_file": str(Path(namisync.__file__).resolve()),
                "versions": {name: importlib.metadata.version(name)
                             for name in ("namisync", "pywebview", "pythonnet")},
            }})
            self.settled = True

    def fail(self, stage: str, reason: str) -> None:
        with self.lock:
            if self.settled:
                return
            self.publisher.publish_failure({"stage": stage, "reason": reason})
            self.settled = True

    def finish(self, code: int, returned: bool) -> None:
        self.publisher.publish_final({"exit_code": code, "host_returned": returned})


_PAGE = r"""
(async () => {
  const until = async (fn, label, attempts = 1200) => {
    window.__inventoryWaiting = label;
    for (let i = 0; i < attempts; i += 1) {
      const value = await fn();
      if (value) {
        window.__inventoryWaiting = null;
        return value;
      }
      await new Promise(resolve => setTimeout(resolve, 25));
    }
    throw new Error(label);
  };
  const confirmationExitFacts = (trigger = window.__inventoryConfirmationInvoker) => {
    const confirmation = document.querySelector('#rebaseline-confirmation');
    const appRoot = document.querySelector('#app');
    const themeOptions = document.querySelector('#theme-options');
    const review = document.querySelector('.nami-inventory-review');
    const active = document.activeElement;
    return {
      closed:confirmation instanceof HTMLDialogElement && !confirmation.open,
      app_active:appRoot instanceof HTMLElement && !appRoot.inert,
      theme_active:themeOptions instanceof HTMLElement && !themeOptions.inert,
      scroll_restored:document.documentElement.style.getPropertyValue('overflow') === ''
        && document.documentElement.style.getPropertyPriority('overflow') === '',
      focus_restored:active === trigger,
      trigger_connected:trigger instanceof HTMLButtonElement && trigger.isConnected,
      trigger_disabled:!(trigger instanceof HTMLButtonElement) || trigger.disabled,
      trigger_hidden:!(trigger instanceof HTMLButtonElement) || trigger.hidden,
      active_category:active === trigger ? 'trigger'
        : confirmation instanceof HTMLElement && confirmation.contains(active) ? 'dialog'
        : review instanceof HTMLElement && review.contains(active) ? 'inventory'
        : active === document.body ? 'body' : 'other',
    };
  };
  const confirmationExitReceipt = (closeFacts, trigger) => {
    const currentFacts = confirmationExitFacts(trigger);
    const focusRequired = closeFacts.trigger_connected && !closeFacts.trigger_disabled;
    return {
      closed:currentFacts.closed, app_active:currentFacts.app_active,
      theme_active:currentFacts.theme_active, scroll_restored:currentFacts.scroll_restored,
      focus_required:focusRequired, focus_restored:currentFacts.focus_restored,
      trigger_connected_at_close:closeFacts.trigger_connected,
      trigger_disabled_at_close:closeFacts.trigger_disabled,
      trigger_hidden_at_close:closeFacts.trigger_hidden,
    };
  };
  const confirmationExitReady = (closeFacts, trigger) => {
    const receipt = confirmationExitReceipt(closeFacts, trigger);
    return receipt.closed && receipt.app_active && receipt.theme_active && receipt.scroll_restored
      && (!receipt.focus_required || receipt.focus_restored);
  };
  const card = await until(() => document.querySelector('.nami-task-rail__row .nami-task-card'), 'task-card');
  card.click();
  const review = await until(() => {
    const pane = document.querySelector('.nami-inventory-review');
    return pane?.isConnected && !pane.querySelector('[data-action="inventory-refresh"]')?.disabled
      && pane.querySelector('.nami-inventory-review__rows > .nami-tree-row[role="treeitem"][data-node-id]') ? pane : null;
  }, 'initial-inventory-view');
  const tableRows = [...review.querySelectorAll('.nami-inventory-review__rows > .nami-tree-row[role="treeitem"][data-node-id]')];
  const tableHeaders = [...review.querySelector('.nami-inventory-review__columns').children];
  const checkboxAppearance = value => ({disabled:value.disabled, checked:value.checked,
    mixed:value.indeterminate, width:value.getBoundingClientRect().width,
    height:value.getBoundingClientRect().height});
  const headerControls = [...tableHeaders[0].querySelectorAll(':scope > input[data-action="inventory-select-location"]')];
  const rowCheckboxes = tableRows.map(row => {
    const controls = [...row.querySelectorAll(':scope > .nami-file-row__selection > input[data-action="inventory-select-row"]')];
    return {node_id:row.dataset.nodeId, control_count:controls.length,
      appearance:controls.length === 1 ? checkboxAppearance(controls[0]) : null};
  });
  const tableAppearance = {
    headers:tableHeaders.map(value => value.textContent),
    row_height:tableRows[0].getBoundingClientRect().height,
    row_count:tableRows.length,
    header_control_count:headerControls.length,
    header_checkbox:headerControls.length === 1 ? checkboxAppearance(headerControls[0]) : null,
    row_checkboxes:rowCheckboxes,
    column_edges:tableHeaders.map((value,index) => [value.getBoundingClientRect().left,
      value.getBoundingClientRect().right, tableRows[0].children[index].getBoundingClientRect().left,
      tableRows[0].children[index].getBoundingClientRect().right]),
  };
  const rangeStages = ['range-folder', 'range-file-toggle', 'range-file-checkbox', 'range-file-recheck', 'range-reset', 'range-anchor', 'range-toggle', 'range-end', 'range-checkbox', 'range-clear'];
  const integrityStages = ['select-folder', 'select-location-clear', 'select-location', 'baseline',
    'verify', 'follow-go', 'pause', 'resume', 'verify-cancel', 'cancel',
    'baseline-menu-open', 'baseline-menu-close', 'baseline-menu-reopen',
    'rebaseline-cancel-open', 'rebaseline-cancel', 'rebaseline-menu-open', 'rebaseline-open', 'rebaseline-confirm'];
  const nativeClicks = Object.fromEntries(['refresh', 'filter-open', 'filter-present', 'filter-escape', 'filter-reopen', 'filter-all', 'details', 'acknowledge', 'restore', 'context-open', 'context-escape', 'context-keyboard', 'context-keyboard-escape', 'context-menu', 'context-acknowledge', 'context-restore', 'selected-hide-details', 'selected-activate', 'selected-arrow-first', 'selected-arrow-second', 'selected-context-menu', 'selected-refresh', ...rangeStages, ...integrityStages].map(name => [name, false]));
  const keyboardInput = [];
  async function stage(name) {
    await until(() => document.hasFocus(), 'document-focus');
    const keyboardMenu = name === 'context-keyboard' || name === 'context-menu';
    const popup = review.querySelector('.nami-row-menu');
    window.__inventoryPopupObserver?.disconnect();
    let popupOpenCount = 0, popupCloseCount = 0;
    const popupObserver = new MutationObserver(records => {
      for (let index = 0; index < records.length; index += 1) {
        const wasHidden = records[index].oldValue !== null;
        const nowHidden = index + 1 < records.length ? records[index + 1].oldValue !== null : popup.hidden;
        if (wasHidden && !nowHidden) popupOpenCount = Math.min(65535, popupOpenCount + 1);
        if (!wasHidden && nowHidden) popupCloseCount = Math.min(65535, popupCloseCount + 1);
      }
    });
    popupObserver.observe(popup, {attributes:true, attributeFilter:['hidden'], attributeOldValue:true});
    window.__inventoryPopupObserver = popupObserver;
    const events = [];
    let opened = null;
    const observe = event => {
      const fact = {type:event.type, key:event.key ?? null, trusted:event.isTrusted,
        target:popup.contains(event.target) ? 'menu' : 'tree',
        get default_prevented() { return event.defaultPrevented; }};
      events.push(fact);
    };
    if (keyboardMenu) {
      for (const type of ['keydown', 'keyup', 'contextmenu']) document.addEventListener(type, observe, true);
      window.__inventoryContextDown = () => {
        opened = {item:popup.firstElementChild,
          rectangle:[popup.getBoundingClientRect().left, popup.getBoundingClientRect().top]};
      };
    }
    let listenedControl = null;
    window.__inventoryStageFacts = () => ({stage:name, pending_wait:window.__inventoryWaiting ?? null,
      listened_control_connected:listenedControl?.isConnected ?? null,
      popup_open_count:popupOpenCount, popup_close_count:popupCloseCount});
    const selector = name === 'select-folder' ? `.nami-inventory-review__rows > .nami-tree-row[role="treeitem"][data-node-id="${window.__inventoryFixture.folder_node_id}"] input[data-action="inventory-select-row"]`
        : name === 'range-folder' ? `.nami-inventory-review__rows [data-node-id="${window.__inventoryFixture.folder_node_id}"]`
        : name === 'range-file-checkbox' || name === 'range-file-recheck' ? `.nami-inventory-review__rows [data-node-id="${window.__inventoryFixture.first_node_id}"] input[data-action="inventory-select-row"]`
        : name === 'range-anchor' || name === 'range-file-toggle' ? `.nami-inventory-review__rows [data-node-id="${window.__inventoryFixture.first_node_id}"]`
        : name === 'range-toggle' ? `.nami-inventory-review__rows [data-node-id="${window.__inventoryFixture.missing_node_id}"]`
        : name === 'range-end' ? `.nami-inventory-review__rows [data-node-id="${window.__inventoryFixture.last_node_id}"]`
        : name === 'range-checkbox' || name === 'range-clear' ? `.nami-inventory-review__rows [data-node-id="${window.__inventoryFixture.last_node_id}"] input[data-action="inventory-select-row"]`
        : name === 'range-reset' || name === 'select-location' || name === 'select-location-clear' ? '[data-action="inventory-select-location"]'
        : name === 'rebaseline-confirm' ? '#rebaseline-confirmation [data-confirm-execution]'
        : name === 'rebaseline-cancel' ? '#rebaseline-confirmation [data-cancel-execution]'
        : name === 'rebaseline-open' || name === 'rebaseline-cancel-open' ? '[data-action="inventory-rebaseline"]'
        : ['baseline-menu-open', 'baseline-menu-close', 'baseline-menu-reopen', 'rebaseline-menu-open'].includes(name) ? '[data-action="inventory-baseline-menu"]'
        : name === 'verify-cancel' ? '[data-action="inventory-verify"]'
        : name === 'follow-go' ? '[data-action="go-current-item"]'
        : name === 'filter-open' || name === 'filter-reopen' ? '[data-action="filter-menu"]'
        : name === 'filter-present' || name === 'filter-escape' ? '.nami-filter-menu__popup [data-filter="present"]'
        : name === 'filter-all' ? '.nami-filter-menu__popup [data-filter="all"]'
        : name === 'selected-hide-details' ? '[data-action="inventory-details"]'
        : name === 'context-open' ? `.nami-inventory-review__rows [data-node-id="${window.__inventoryFixture.missing_node_id}"]`
        : name === 'context-escape' || name === 'context-keyboard-escape' ? '.nami-row-menu [data-action="row-details"]'
        : keyboardMenu || name === 'selected-context-menu' ? '.nami-inventory-review__rows'
        : name === 'selected-activate' ? `.nami-inventory-review__rows [data-node-id="${window.__inventoryFixture.folder_node_id}"]`
        : name === 'selected-arrow-first' || name === 'selected-arrow-second' ? '.nami-inventory-review__rows'
        : name === 'selected-refresh' ? '.nami-row-menu [data-action="row-refresh"]'
        : name === 'context-acknowledge' ? '.nami-row-menu [data-action="row-acknowledge"]'
        : name === 'context-restore' ? '[data-action="inventory-restore"]'
        : `[data-action="inventory-${name}"]`;
    const gesture = name === 'context-open' ? 'contextmenu'
      : ['filter-escape', 'context-escape', 'context-keyboard', 'context-keyboard-escape', 'context-menu', 'selected-context-menu', 'selected-arrow-first', 'selected-arrow-second'].includes(name) ? 'keydown' : 'click';
    let activatedControl = null;
    // Window publications replace row elements; input custody follows their identity.
    const trustedInput = event => {
      const control = event.target instanceof Element ? event.target.closest(selector) : null;
      if (event.isTrusted && control !== null
          && (!name.startsWith('selected-arrow-') || event.key === 'ArrowDown')) {
        nativeClicks[name] = true;
        activatedControl ??= control;
      }
    };
    document.addEventListener(gesture, trustedInput, true);
    window.__inventoryNativeCheck = async () => {
      const control = document.querySelector(selector);
      if (control === null) return {point:null, facts:{connected:false}};
      if (name === 'rebaseline-open' || name === 'rebaseline-cancel-open') {
        window.__inventoryConfirmationInvoker = review.querySelector('[data-action="inventory-baseline-menu"]');
      }
      const focusTarget = name === 'context-open' || name === 'selected-activate'
        || ['range-folder', 'range-file-toggle', 'range-anchor', 'range-toggle', 'range-end'].includes(name)
        ? review.querySelector('.nami-inventory-review__rows') : control;
      if (name === 'selected-refresh') window.__inventoryRefreshViewport.before_focus = review.querySelector('.nami-inventory-review__list').scrollTop;
      // Keep menu focus until the native trigger click moves it, exercising
      // pointerdown/focusout/click ordering rather than pre-closing the popup.
      const togglingBaseline = name === 'baseline-menu-close';
      if (!togglingBaseline) focusTarget.focus({preventScroll:true});
      await new Promise(resolve => requestAnimationFrame(resolve));
      if (name === 'selected-refresh') window.__inventoryRefreshViewport.after_focus = review.querySelector('.nami-inventory-review__list').scrollTop;
      const hitTarget = control === review.querySelector('.nami-inventory-review__rows')
        ? document.getElementById(control.getAttribute('aria-activedescendant')) : control;
      if (hitTarget === null || !control.contains(hitTarget)) return {point:null, facts:{connected:false}};
      const rect = hitTarget.getBoundingClientRect();
      const point = {x:(rect.left+rect.right)/2, y:(rect.top+rect.bottom)/2};
      const hit = document.elementFromPoint(point.x, point.y);
      const facts = {document_focused:document.hasFocus(), connected:control.isConnected,
        enabled:!control.disabled, visible:!control.hidden,
        active:togglingBaseline
          ? control.ariaExpanded === 'true' && document.activeElement === review.querySelector('.nami-row-menu[aria-label="Baseline actions"]').firstElementChild
          : document.activeElement === focusTarget,
        hit_owned:control.contains(hit) || hit === control, sized:rect.width > 0 && rect.height > 0};
      listenedControl = control;
      return {point, facts};
    };
    window.__inventoryNativeStage = `${name}-ready`;
    await until(() => window.__inventoryNativeAck === name, `native-${name}`, name === 'refresh' ? 2800 : 1200);
    await until(() => nativeClicks[name], `trusted-${name}`);
    document.removeEventListener(gesture, trustedInput, true);
    if (keyboardMenu) {
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      for (const type of ['keydown', 'keyup', 'contextmenu']) document.removeEventListener(type, observe, true);
      const rect = popup.getBoundingClientRect();
      keyboardInput.push({name, events, popup_visible:!popup.hidden,
        stable_focus:opened?.item === document.activeElement,
        stable_position:opened?.rectangle[0] === rect.left && opened?.rectangle[1] === rect.top});
    }
    return activatedControl;
  }
  await stage('refresh');
  const filterTrigger = review.querySelector('[data-action="filter-menu"]');
  const filterPopup = review.querySelector('.nami-filter-menu__popup');
  await until(() => !review.querySelector('[data-action="inventory-refresh"]').disabled, 'filter-ready');
  const colorReference = document.createElement('span');
  colorReference.style.cssText = 'position:fixed;visibility:hidden;forced-color-adjust:none';
  colorReference.style.backgroundColor = 'var(--color-button-fill)';
  colorReference.style.color = 'var(--color-neutral-foreground)';
  review.append(colorReference);
  await new Promise(resolve => setTimeout(resolve, 150));
  const neutralStyle = getComputedStyle(filterTrigger);
  const neutral = filterTrigger.children[2].textContent === '304/304' && filterTrigger.dataset.active === 'false'
    && neutralStyle.backgroundColor === getComputedStyle(colorReference).backgroundColor
    && neutralStyle.color === getComputedStyle(colorReference).color;
  const neutralColors = [neutralStyle.backgroundColor, neutralStyle.color];
  await stage('filter-open');
  await until(() => !filterPopup.hidden, 'filter-open');
  const menuGeometry = {};
  const rectangle = element => {
    const rect = element.getBoundingClientRect();
    return [rect.left, rect.top, rect.right, rect.bottom].map(value => Number(value.toFixed(3)));
  };
  for (const [name, key] of [['first', 'all'], ['last', 'notice']]) {
    const item = filterPopup.querySelector(`[data-filter="${key}"]`);
    item.focus();
    await new Promise(resolve => requestAnimationFrame(resolve));
    const rect = item.getBoundingClientRect();
    const hit = document.elementFromPoint((rect.left + rect.right) / 2, (rect.top + rect.bottom) / 2);
    menuGeometry[name] = {rectangle: rectangle(item), hit: item.contains(hit)};
  }
  menuGeometry.trigger = rectangle(filterTrigger);
  menuGeometry.popup = rectangle(filterPopup);
  menuGeometry.work = rectangle(review.closest('.nami-work-panel'));
  const popupInside = menuGeometry.popup[1] >= menuGeometry.work[1]
    && menuGeometry.popup[3] <= menuGeometry.work[3]
    && menuGeometry.popup[0] >= menuGeometry.work[0] && menuGeometry.popup[2] <= menuGeometry.work[2];
  await stage('filter-present');
  await until(() => filterTrigger.children[2].textContent === '303/304'
    && filterPopup.querySelector('[data-filter="present"]').ariaChecked === 'true', 'filter-settled');
  const staysOpen = !filterPopup.hidden;
  colorReference.style.backgroundColor = 'var(--color-accent-fill)';
  colorReference.style.color = 'var(--color-accent-fill-foreground)';
  await new Promise(resolve => setTimeout(resolve, 150));
  const activeStyle = getComputedStyle(filterTrigger);
  const accented = filterTrigger.dataset.active === 'true'
    && activeStyle.backgroundColor === getComputedStyle(colorReference).backgroundColor
    && activeStyle.color === getComputedStyle(colorReference).color;
  const filterColors = {neutral: neutralColors, active: [activeStyle.backgroundColor, activeStyle.color]};
  colorReference.remove();
  await stage('filter-escape');
  await until(() => filterPopup.hidden && document.activeElement === filterTrigger, 'filter-Escape');
  await stage('filter-reopen');
  await stage('filter-all');
  await until(() => filterTrigger.children[2].textContent === '304/304'
    && filterPopup.querySelector('[data-filter="all"]').ariaChecked === 'true', 'filter-reset');
  const allKeepsOpen = !filterPopup.hidden;
  const allCount = filterPopup.querySelector('[data-filter="all"] .nami-filter-count');
  const allCountMatches = !allCount.hidden && allCount.textContent === '304';
  filterTrigger.focus();
  review.querySelector('[data-action="inventory-search"]').focus();
  const focusAwayClosed = filterPopup.hidden;
  const filterMenu = {neutral, staysOpen, accented, escapeFocus:true, allKeepsOpen, allCountMatches, focusAwayClosed,
    firstReachable:menuGeometry.first.hit, lastReachable:menuGeometry.last.hit, popupInside};
  if (Object.values(filterMenu).some(value => value !== true)) throw new Error('filter menu contract failed');
  const fixture = window.__inventoryFixture;
  const row = id => [...review.querySelectorAll('.nami-inventory-review__rows > .nami-tree-row[role="treeitem"][data-node-id]')]
    .find(value => value.dataset.nodeId === id);
  const missing = () => row(fixture.missing_node_id);
  await until(() => missing()?.querySelector('[data-integrity="missing"]')
    && review.textContent.includes('Displayed scan: Entire location')
    && review.textContent.includes('notices from this scan'), 'refreshed-missing');
  const folder = () => row(fixture.folder_node_id);
  const activateFolder = async label => {
    const previous = await until(folder, 'folder-row');
    previous.click();
    // A repeated click may already look highlighted before its window re-read lands.
    await until(() => !previous.isConnected && folder()?.dataset.highlighted === 'true', label);
  };
  await activateFolder('details-folder-settled');
  await stage('details');
  await until(() => {
    const control = review.querySelector('[data-action="inventory-acknowledge"]');
    return control && !control.hidden && !control.disabled ? control : null;
  }, 'acknowledge-control');
  await stage('acknowledge');
  await until(() => !missing() && folder()
    && !review.querySelector('[data-action="inventory-refresh"]').disabled, 'acknowledged-hidden');
  await activateFolder('restore-folder-settled');
  if (review.querySelector('[data-action="inventory-details"]').ariaExpanded !== 'true') {
    throw new Error('acknowledge replacement collapsed Inventory Details');
  }
  await until(() => {
    const control = review.querySelector('[data-action="inventory-restore"]');
    return control && !control.hidden && !control.disabled ? control : null;
  }, 'restore-control');
  await stage('restore');
  await until(() => missing()?.querySelector('[data-integrity="missing"]')
    && !review.querySelector('[data-action="inventory-refresh"]').disabled, 'restored-visible');
  await activateFolder('context-folder-settled');
  const itemHeading = () => review.querySelector('.nami-plan-review__detail h2');
  await until(() => itemHeading()?.textContent === fixture.folder_display, 'context-other-details');
  await stage('context-open');
  const contextPopup = review.querySelector('.nami-row-menu');
  await until(() => !contextPopup.hidden, 'context-open');
  const otherDetailPreserved = itemHeading().textContent === fixture.folder_display;
  const activeMissing = review.querySelector('.nami-inventory-review__rows').getAttribute('aria-activedescendant') === missing().id;
  const menuRect = contextPopup.getBoundingClientRect();
  const workRect = review.closest('.nami-work-panel').getBoundingClientRect();
  const contextRawRectangles = [menuRect, workRect].map(bounds =>
    [bounds.left, bounds.top, bounds.right, bounds.bottom]);
  const contextRectangles = contextRawRectangles.map(bounds => bounds.map(value => Number(value.toFixed(3))));
  const [contextEdges, contextWorkEdges] = contextRectangles;
  const contextPopupInside = contextEdges[0] >= contextWorkEdges[0] && contextEdges[2] <= contextWorkEdges[2]
    && contextEdges[1] >= contextWorkEdges[1] && contextEdges[3] <= contextWorkEdges[3];
  await stage('context-escape');
  const escapeFocus = contextPopup.hidden && document.activeElement === review.querySelector('.nami-inventory-review__rows');
  await stage('context-keyboard');
  await until(() => !contextPopup.hidden, 'context-keyboard');
  await stage('context-keyboard-escape');
  await stage('context-menu');
  await until(() => !contextPopup.hidden, 'context-menu');
  const ownMissingActions = [...contextPopup.children].map(item => item.textContent).join('|') === 'Show details|Refresh selected|Acknowledge missing';
  await stage('context-acknowledge');
  await until(() => !missing() && !review.querySelector('[data-action="inventory-refresh"]').disabled, 'context-acknowledged-hidden');
  await activateFolder('context-restore-folder-settled');
  if (review.querySelector('[data-action="inventory-details"]').ariaExpanded !== 'true') {
    throw new Error('context acknowledge replacement collapsed Inventory Details');
  }
  await until(() => !review.querySelector('[data-action="inventory-restore"]').disabled, 'context-restore-ready');
  await stage('context-restore');
  await until(() => missing()?.querySelector('[data-integrity="missing"]')
    && !review.querySelector('[data-action="inventory-refresh"]').disabled, 'context-restored-visible');
  const rowMenu = {other_detail_preserved:otherDetailPreserved, active_missing:activeMissing,
    popup_inside:contextPopupInside, escape_focus:escapeFocus, own_missing_actions:ownMissingActions,
    acknowledged_hidden:true, restored_missing:true};
  if (Object.values(rowMenu).some(value => value !== true)) throw new Error('row context menu contract failed');
  rowMenu.rectangles = contextRectangles;
  rowMenu.raw_rectangles = contextRawRectangles;
  const summary = review.querySelector('.nami-plan-review__summary');
  const track = summary.querySelector('.nami-plan-review__progress');
  const status = {feedback_lines:summary.querySelectorAll('.nami-plan-review__status').length,
    has_scope:review.querySelector('[data-inventory-scan-facts]').textContent.includes('Displayed scan: Entire location'),
    track_height:track.getBoundingClientRect().height,
    animation:getComputedStyle(track.firstElementChild).animationName,
    value:track.firstElementChild.style.getPropertyValue('--nami-progress-value')};
  await stage('selected-hide-details');
  const selectedFolderRow = await stage('selected-activate');
  const itemCard = review.querySelector('.nami-inventory-review__detail');
  await until(() => itemHeading()?.textContent === fixture.folder_display
    && itemCard.textContent.includes(fixture.folder_path), 'selected-folder-detail');
  const diagnostics = review.querySelector('.nami-inventory-review__diagnostics');
  if (!diagnostics.hidden) throw new Error('selected Details must remain hidden');
  await until(() => !selectedFolderRow.isConnected && folder()?.dataset.highlighted === 'true', 'selected-folder-highlight');
  const viewport = review.querySelector('.nami-inventory-review__list');
  viewport.scrollTop = 7;
  const refreshViewport = window.__inventoryRefreshViewport = {setup:viewport.scrollTop,
    first_arrow:null, second_arrow:null, before_focus:null, after_focus:null,
    before:null, after:null, minimum:null, scroll_height:viewport.scrollHeight, client_height:viewport.clientHeight};
  await new Promise(resolve => requestAnimationFrame(resolve));
  await stage('selected-arrow-first');
  await until(() => review.querySelector(`.nami-inventory-review__rows [data-node-id="${fixture.first_node_id}"]`)?.dataset.highlighted === 'true', 'selected-first-highlight');
  refreshViewport.first_arrow = viewport.scrollTop;
  await stage('selected-arrow-second');
  await until(() => missing()?.dataset.highlighted === 'true', 'selected-missing-highlight');
  await until(() => itemHeading()?.textContent === fixture.missing_display
    && itemCard.textContent.includes(fixture.missing_path), 'selected-keyboard-detail');
  refreshViewport.second_arrow = viewport.scrollTop;
  const selectedRefresh = {details_hidden:diagnostics.hidden,
    detail_followed:itemHeading()?.textContent === fixture.missing_display,
    active_node_id:review.querySelector('.nami-inventory-review__rows').getAttribute('aria-activedescendant') === missing().id
      ? fixture.missing_node_id : null};
  if (!selectedRefresh.details_hidden || !selectedRefresh.detail_followed
      || selectedRefresh.active_node_id !== fixture.missing_node_id) throw new Error('selected active row differs');
  selectedRefresh.scroll_before = viewport.scrollTop;
  selectedRefresh.minimum_scroll = viewport.scrollTop;
  refreshViewport.before = viewport.scrollTop;
  let samplingRefresh = true;
  function sampleRefreshScroll() {
    if (!samplingRefresh) return;
    selectedRefresh.minimum_scroll = Math.min(selectedRefresh.minimum_scroll, viewport.scrollTop);
    refreshViewport.minimum = selectedRefresh.minimum_scroll;
    requestAnimationFrame(sampleRefreshScroll);
  }
  requestAnimationFrame(sampleRefreshScroll);
  await stage('selected-context-menu');
  await until(() => !contextPopup.hidden && contextPopup.querySelector('[data-action="row-refresh"]'), 'selected-context-menu-open');
  await stage('selected-refresh');
  await until(() => !review.querySelector('[data-action="inventory-refresh"]').disabled
    && review.querySelector('[data-inventory-scan-facts]').textContent.includes(fixture.missing_path)
    && review.querySelector('.nami-plan-review__status').textContent.includes('Only the selected scope was rescanned.'),
    'selected-item-publication');
  await until(() => missing()?.dataset.highlighted === 'true'
    && itemHeading()?.textContent === fixture.missing_display
    && itemCard.textContent.includes(fixture.missing_path), 'selected-refreshed-detail');
  selectedRefresh.refresh_focus_retained = true;
  samplingRefresh = false;
  selectedRefresh.scroll_after = viewport.scrollTop;
  refreshViewport.after = viewport.scrollTop;
  if (!(selectedRefresh.scroll_before > 0 && selectedRefresh.scroll_before < 24)
      || selectedRefresh.scroll_after !== selectedRefresh.scroll_before
      || selectedRefresh.minimum_scroll !== selectedRefresh.scroll_before) throw new Error('selected refresh lost its partial-row viewport');
  const tree = review.querySelector('.nami-inventory-review__rows');
  const rangeRow = id => tree.querySelector(`[data-node-id="${id}"]`);
  const selectionText = () => review.querySelector('[data-inventory-task-facts]').textContent;
  if (!selectionText().includes('3 of 3 files selected')) throw new Error('fresh scan must select all files');
  await stage('range-folder');
  await until(() => rangeRow(fixture.folder_node_id)?.dataset.highlighted === 'true', 'folder-range-anchor');
  await stage('range-file-toggle');
  await until(() => rangeRow(fixture.folder_node_id)?.dataset.highlighted === 'true'
    && rangeRow(fixture.first_node_id)?.dataset.highlighted === 'true', 'folder-range-file');
  await stage('range-file-checkbox');
  await until(() => selectionText().includes('2 of 3 files selected')
    && rangeRow(fixture.first_node_id)?.querySelector('input').checked === false
    && rangeRow(fixture.folder_node_id)?.querySelector('input').indeterminate === true,
    'folder-range-does-not-expand');
  await stage('range-file-recheck');
  await until(() => selectionText().includes('3 of 3 files selected')
    && rangeRow(fixture.folder_node_id)?.querySelector('input').indeterminate === false, 'folder-range-restored');
  await stage('range-reset');
  await until(() => selectionText().includes('0 of 3 files selected'), 'scan-selection-cleared');
  await stage('range-anchor');
  await until(() => rangeRow(fixture.first_node_id)?.dataset.highlighted === 'true', 'range-anchor-settled');
  await stage('range-toggle');
  await until(() => rangeRow(fixture.first_node_id)?.dataset.highlighted === 'true'
    && rangeRow(fixture.missing_node_id)?.dataset.highlighted === 'true', 'range-toggle-settled');
  viewport.scrollTop = 304*24-(viewport.clientHeight-24);
  viewport.dispatchEvent(new Event('scroll'));
  await until(() => rangeRow(fixture.last_node_id), 'range-off-window-end');
  await stage('range-end');
  await until(() => rangeRow(fixture.last_node_id)?.dataset.highlighted === 'true', 'range-end-settled');
  const rangeScroll = viewport.scrollTop;
  await stage('range-checkbox');
  await until(() => selectionText().includes('3 of 3 files selected')
    && !rangeRow(fixture.last_node_id)?.querySelector('input').disabled, 'range-selection-settled');
  const rangeScrollAfter = viewport.scrollTop;
  const rangeCheckbox = rangeRow(fixture.last_node_id).querySelector('input');
  const rangeCheckboxFocused = document.activeElement === rangeCheckbox;
  const rangeCheckboxConnected = rangeCheckbox.isConnected;
  const rangeCheckboxDisabled = rangeCheckbox.disabled;
  const rangeActiveCategory = rangeCheckboxFocused ? 'checkbox'
    : document.activeElement === tree ? 'tree'
    : review.contains(document.activeElement) ? 'inventory'
    : document.activeElement === document.body ? 'body' : 'other';
  const rangeCustody = rangeScroll > 256*24 && rangeScrollAfter === rangeScroll
    && rangeCheckboxFocused;
  await stage('range-clear');
  await until(() => selectionText().includes('0 of 3 files selected'), 'range-clear-settled');
  const search = review.querySelector('[data-action="inventory-search"]');
  search.value = '.txt'; search.dispatchEvent(new Event('input', {bubbles:true}));
  await until(() => [fixture.folder_node_id, fixture.first_node_id,
    fixture.missing_node_id, fixture.last_node_id].every(nodeId => rangeRow(nodeId)),
    'range-file-view-restored');
  folder().querySelector('.nami-tree-row__disclosure').click();
  await until(() => !missing(), 'collapsed-selection-scope');
  const activeBefore = tree.getAttribute('aria-activedescendant');
  const scrollBefore = viewport.scrollTop;
  await stage('select-folder');
  await until(() => selectionText().includes('3 of 3 files selected')
    && !review.querySelector('[data-action="inventory-baseline"]').disabled, 'folder-selection');
  const checkboxCustody = !missing() && tree.getAttribute('aria-activedescendant') === activeBefore
    && viewport.scrollTop === scrollBefore;
  search.value = 'one.txt'; search.dispatchEvent(new Event('input', {bubbles:true}));
  await until(() => selectionText().includes('2 hidden by filters or search'), 'hidden-selection');
  const hiddenSelection = selectionText();
  await stage('select-location-clear');
  await until(() => selectionText().includes('2 of 3 files selected')
    && selectionText().includes('2 hidden by filters or search'), 'location-clear');
  await stage('select-location');
  await until(() => selectionText().includes('3 of 3 files selected')
    && selectionText().includes('2 hidden by filters or search'), 'location-selection');
  folder().querySelector('.nami-tree-row__disclosure').click();
  await until(() => {
    const visibleFiles = [...review.querySelectorAll(
      '.nami-inventory-review__rows > .nami-tree-row[role="treeitem"][data-node-id][data-folder="false"]')];
    return folder()?.getAttribute('aria-expanded') === 'true'
      && visibleFiles.length === 1
      && visibleFiles[0].querySelector('.nami-tree-row__label')?.textContent === 'one.txt';
  }, 'integrity-visible-file');
  const released = async (label, expectedText, expectedState) => until(() => {
    const result = review.querySelector('.nami-plan-review__status-title');
    const states = [...review.querySelectorAll('.nami-inventory-review__rows .nami-integrity-row__presence[data-integrity-state]')]
      .map(value => value.dataset.integrityState);
    const expectedStates = expectedState === null ? [] : [expectedState];
    const currentScan = review.querySelector('[data-inventory-scan-facts]').textContent
      .includes('Displayed scan: Selected items');
    return !review.querySelector('[data-action="inventory-verify"]').disabled
      && result.textContent === expectedText
      && !review.querySelector('[data-inventory-integrity-facts]')
      && states.length === expectedStates.length
      && states.every((value, index) => value === expectedStates[index])
      && currentScan ? {text:result.textContent, states, current_scan:currentScan} : null;
  }, label);
  await stage('baseline');
  const baselinePresentation = await released('baseline-terminal',
    'Baseline incomplete', 'baselined');
  const baselineResult = baselinePresentation.text;
  await stage('verify');
  await until(() => !review.querySelector('[data-action="inventory-pause"]').disabled, 'verify-active');
  const go = await until(() => {
    const value = review.querySelector('[data-action="go-current-item"]');
    return value && !value.hidden && !value.disabled ? value : null;
  }, 'ordinary-active-item');
  const followBefore = {selection:selectionText(),
    activeNode:document.getElementById(tree.getAttribute('aria-activedescendant'))?.dataset.nodeId ?? null,
    query:search.value};
  await stage('follow-go');
  // This filtered target is already visible: the installed witness proves
  // trusted Go input and the real worker item/anchor identity. The app/tree
  // probes own preservation after asynchronous window publication.
  const activeAfter = tree.getAttribute('aria-activedescendant');
  const activeRetained = followBefore.activeNode !== null
    && document.getElementById(activeAfter)?.dataset.nodeId === followBefore.activeNode;
  const oldActiveRepresented = followBefore.activeNode !== null
    && [...tree.querySelectorAll('[data-node-id]')].some(row => row.dataset.nodeId === followBefore.activeNode);
  const followCustody = {active_retained:activeRetained, old_active_represented:oldActiveRepresented,
    active_cleared:activeAfter === null,
    active_allowed:followBefore.activeNode !== null && (oldActiveRepresented ? activeRetained : activeAfter === null),
    selection_preserved:selectionText() === followBefore.selection,
    query_preserved:search.value === followBefore.query, focus_preserved:document.activeElement === go,
    enable_hidden:review.querySelector('[data-action="enable-item-follow"]').hidden};
  window.__inventoryFollowCustodyFailure = followCustody;
  const followClickCustody = followCustody.active_allowed && followCustody.selection_preserved
    && followCustody.query_preserved && followCustody.focus_preserved && followCustody.enable_hidden;
  if (!followClickCustody) throw new Error('native integrity Follow identity differs');
  await stage('pause');
  await until(() => !review.querySelector('[data-action="inventory-resume"]').disabled, 'verify-paused');
  await stage('resume');
  const verifyPresentation = await released('verify-terminal',
    'Verification incomplete', 'verified');
  const verifyResult = verifyPresentation.text;
  await stage('verify-cancel');
  await until(() => !review.querySelector('[data-action="inventory-cancel"]').disabled, 'cancel-active');
  await stage('cancel');
  const canceledPresentation = await released('cancel-terminal',
    'Verification canceled', null);
  const canceledResult = canceledPresentation.text;
  const baselineTrigger = review.querySelector('[data-action="inventory-baseline-menu"]');
  const baselinePopup = review.querySelector('.nami-row-menu[aria-label="Baseline actions"]');
  await stage('baseline-menu-open');
  await until(() => !baselinePopup.hidden && baselineTrigger.ariaExpanded === 'true'
    && document.activeElement === baselinePopup.firstElementChild, 'baseline-menu-open');
  await stage('baseline-menu-close');
  await until(() => baselinePopup.hidden && baselineTrigger.ariaExpanded === 'false'
    && document.activeElement === baselineTrigger, 'baseline-menu-toggle-closed');
  await stage('baseline-menu-reopen');
  await until(() => !baselinePopup.hidden && baselineTrigger.ariaExpanded === 'true'
    && document.activeElement === baselinePopup.firstElementChild, 'baseline-menu-reopened');
  await stage('rebaseline-cancel-open');
  const confirmation = document.querySelector('#rebaseline-confirmation');
  await until(() => !confirmation.hidden && confirmation.open, 'rebaseline-confirmation');
  const cancelInvoker = window.__inventoryConfirmationInvoker;
  const originalConfirmationClose = confirmation.close;
  window.__inventoryConfirmationLastClose = null;
  window.__inventoryConfirmationTimeout = null;
  confirmation.close = function(...args) {
    window.__inventoryConfirmationLastClose = confirmationExitFacts();
    return Reflect.apply(originalConfirmationClose, this, args);
  };
  const confirmationText = document.querySelector('#rebaseline-confirmation-count').textContent;
  await stage('rebaseline-cancel');
  const cancelCloseFacts = await until(() => window.__inventoryConfirmationLastClose,
    'rebaseline-cancel-close');
  await until(() => cancelCloseFacts.trigger_connected && !cancelCloseFacts.trigger_disabled
    && !cancelCloseFacts.trigger_hidden && confirmationExitReady(cancelCloseFacts, cancelInvoker)
    && !cancelInvoker.disabled && document.activeElement === cancelInvoker,
    'rebaseline-cancel-no-effect');
  const cancelConfirmationRestored = confirmationExitReceipt(cancelCloseFacts, cancelInvoker);
  const cancelPreservedResult = review.querySelector('.nami-plan-review__status-title').textContent === canceledResult;
  await stage('rebaseline-menu-open');
  await until(() => !baselinePopup.hidden && baselineTrigger.ariaExpanded === 'true'
    && document.activeElement === baselinePopup.firstElementChild, 'rebaseline-menu-open');
  await stage('rebaseline-open');
  await until(() => confirmation.open, 'rebaseline-confirm-again');
  const confirmInvoker = window.__inventoryConfirmationInvoker;
  window.__inventoryConfirmationLastClose = null;
  await stage('rebaseline-confirm');
  const confirmCloseFacts = await until(() => window.__inventoryConfirmationLastClose,
    'rebaseline-confirm-close');
  try {
    await until(() => confirmationExitReady(confirmCloseFacts, confirmInvoker),
      'rebaseline-confirmation-exit');
  } catch (error) {
    window.__inventoryConfirmationTimeout = confirmationExitFacts(confirmInvoker);
    throw error;
  }
  const confirmationRestored = confirmationExitReceipt(confirmCloseFacts, confirmInvoker);
  const rebaselinePresentation = await released('rebaseline-terminal',
    'Rebaseline incomplete', 'baselined');
  const rebaselineResult = rebaselinePresentation.text;
  const scanText = review.querySelector('[data-inventory-scan-facts]').textContent;
  const scanSelected = scanText.includes('Displayed scan: Selected items');
  const integrityJourney = {checkbox_custody:checkboxCustody, range_custody:rangeCustody,
    follow_click_custody:followClickCustody,
    range_scroll:rangeScroll, hidden_selection:hiddenSelection,
    confirmation_text:confirmationText, cancel_preserved_result:cancelPreservedResult,
    baseline_result:baselineResult, verify_result:verifyResult, canceled_result:canceledResult,
    rebaseline_result:rebaselineResult, scan_selected:scanSelected,
    terminal_presentations:[baselinePresentation, verifyPresentation,
      canceledPresentation, rebaselinePresentation],
    cancel_confirmation_restored:cancelConfirmationRestored,
    confirmation_restored:confirmationRestored};
  if (!checkboxCustody || !rangeCustody || !cancelPreservedResult || !scanSelected) {
    window.__inventoryCustodyFailure = {
      checkbox_custody:checkboxCustody, range_custody:rangeCustody,
      cancel_preserved_result:cancelPreservedResult, scan_selected:scanSelected,
      range_scroll_before:rangeScroll, range_scroll_after:rangeScrollAfter,
      range_checkbox_focused:rangeCheckboxFocused, range_checkbox_connected:rangeCheckboxConnected,
      range_checkbox_disabled:rangeCheckboxDisabled, range_active_category:rangeActiveCategory,
    };
    throw new Error('integrity UI custody differs');
  }
  return {table_appearance:tableAppearance, filter_geometry:menuGeometry, filter_colors:filterColors, filter_menu:filterMenu, row_menu:rowMenu, keyboard_input:keyboardInput, native_clicks:nativeClicks, pane_visible:review.isConnected && !review.hidden,
    refreshed_missing:true, acknowledged_hidden:true, restored_missing:true, status, selected_refresh:selectedRefresh,
    integrity_journey:integrityJourney};
})()
"""


def _drive(window: object, phase: _InventoryPhase, recorder: _Recorder,
           retained: list[object], screenshot: Path) -> None:
    native = window.native
    core = native.browser.webview.CoreWebView2
    owned_handle = int(native.Handle.ToInt64())
    failed = False
    checkpoint = "page-pending"
    page_result: dict[str, object] | None = None
    observed_handle: int | None = None
    click_target: dict[str, object] | None = None
    foreground_owned = {name: False for name in ("refresh", "filter-open", "filter-present", "filter-escape", "filter-reopen", "filter-all", "details", "acknowledge", "restore", "context-open", "context-escape", "context-keyboard", "context-keyboard-escape", "context-menu", "context-acknowledge", "context-restore", "selected-hide-details", "selected-activate", "selected-arrow-first", "selected-arrow-second", "selected-context-menu", "selected-refresh", *_RANGE_STAGES, *_INTEGRITY_STAGES)}

    def fail(error: BaseException, task: object | None, step: str, _method: str) -> None:
        nonlocal failed
        if failed:
            return
        failed = True
        phase.initial_scan_release.set()
        phase.verify_release.set()
        diagnostic = failure_site(task)
        diagnostic.update({"checkpoint": checkpoint, "page_result": page_result,
                           "foreground_owned": foreground_owned, "phase": phase.diagnostic(),
                           "assertion": _owned_failure(error),
                           "click_target": click_target,
                           "owned_handle": owned_handle, "observed_handle": observed_handle,
                           "confirmation_exit": None, "integrity_custody": None, "follow_custody": None,
                           "stage_facts": None, "refresh_viewport": None})

        def publish(value: object = None) -> None:
            if type(value) is dict:
                diagnostic["confirmation_exit"] = _bounded_confirmation_exit_diagnostic(
                    value.get("confirmation_exit"))
                diagnostic["integrity_custody"] = _bounded_integrity_custody_diagnostic(
                    value.get("integrity_custody"))
                diagnostic["follow_custody"] = _bounded_follow_custody_diagnostic(
                    value.get("follow_custody"))
                diagnostic["stage_facts"] = _bounded_stage_diagnostic(value.get("stage_facts"))
                diagnostic["refresh_viewport"] = _bounded_refresh_viewport(value.get("refresh_viewport"))
            screenshot.with_name("inventory-failure-site.json").write_text(
                json.dumps(diagnostic, sort_keys=True), encoding="utf-8",
            )
            recorder.fail(step, type(error).__name__)

        expression = r"""({
          confirmation_exit:{last_close:window.__inventoryConfirmationLastClose ?? null,
            timeout:window.__inventoryConfirmationTimeout ?? null},
          integrity_custody:window.__inventoryCustodyFailure ?? null,
          follow_custody:window.__inventoryFollowCustodyFailure ?? null,
          refresh_viewport:window.__inventoryRefreshViewport ?? null,
          stage_facts:window.__inventoryStageFacts?.() ?? {stage:null,
            pending_wait:window.__inventoryWaiting ?? null, listened_control_connected:null,
            popup_open_count:0, popup_close_count:0},
        })"""
        try:
            diagnostic_task = core.CallDevToolsProtocolMethodAsync(
                "Runtime.evaluate",
                json.dumps({"expression": expression, "returnByValue": True}),
            )

            def diagnostic_completed() -> None:
                from System import Action

                def finish() -> None:
                    try:
                        publish(runtime_value(diagnostic_task))
                    except BaseException:
                        publish()

                action = Action(finish)
                retained.append(action)
                native.BeginInvoke(action)

            from System import Action
            completion = Action(diagnostic_completed)
            retained.append(completion)
            diagnostic_task.GetAwaiter().OnCompleted(completion)
        except BaseException:
            publish()

    cdp = NativeCdp(native, core, retained, fail)
    stage_names = ("refresh", "filter-open", "filter-present", "filter-escape", "filter-reopen", "filter-all", "details", "acknowledge", "restore", "context-open", "context-escape", "context-keyboard", "context-keyboard-escape", "context-menu", "context-acknowledge", "context-restore", "selected-hide-details", "selected-activate", "selected-arrow-first", "selected-arrow-second", "selected-context-menu", "selected-refresh", *_RANGE_STAGES, *_INTEGRITY_STAGES)

    def next_stage(index: int) -> None:
        if index == len(stage_names):
            return
        name = stage_names[index]
        expression = ("(async()=>{for(let i=0;i<1200;i++){"
                      f"if(window.__inventoryNativeStage==='{name}-ready')return true;"
                      "await new Promise(r=>setTimeout(r,25));}throw new Error('stage');})()")

        def click(_ready: object) -> None:
            nonlocal observed_handle
            focus_deadline = monotonic() + 60.0 if name == "refresh" else None
            runner_deadline = monotonic() + 60.0 if name in {"pause", "cancel"} else None

            def dispatch_owned(checked: object) -> None:
                nonlocal observed_handle, click_target
                if type(checked) is not dict or type(checked.get("facts")) is not dict:
                    raise RuntimeError("native inventory point is invalid")
                facts = checked["facts"]
                click_target = {"stage": name, "facts": dict(facts)}
                if not facts or any(value is not True for value in facts.values()):
                    raise RuntimeError("native inventory click target is unavailable")
                point = checked.get("point")
                if type(point) is not dict or set(point) != {"x", "y"}:
                    raise RuntimeError("native inventory point is invalid")
                observed_handle = foreground_window_handle()
                if observed_handle != owned_handle:
                    raise RuntimeError("native inventory window is not foreground")
                foreground_owned[name] = True
                def released(_value: object) -> None:
                    def acknowledge() -> None:
                        cdp.evaluate(f"window.__inventoryNativeAck='{name}';true", lambda _ack: next_stage(index + 1), f"ack-{name}")
                    if name != "follow-go":
                        acknowledge()
                        return
                    anchor_deadline = monotonic() + 10
                    def wait_anchor() -> None:
                        with phase.lock:
                            observed = any(item["command"] == "get_inventory_anchor" for item in phase.commands)
                        if observed:
                            acknowledge()
                        elif monotonic() < anchor_deadline:
                            cdp.evaluate("new Promise(resolve => setTimeout(() => resolve(true), 100))",
                                         lambda _ready: wait_anchor(), "wait-follow-anchor")
                        else:
                            raise RuntimeError("native integrity Follow identity differs")
                    wait_anchor()
                if name in {"filter-escape", "context-escape", "context-keyboard", "context-keyboard-escape", "context-menu", "selected-context-menu", "selected-arrow-first", "selected-arrow-second"}:
                    keyboard_menu = name == "context-keyboard"
                    key, virtual_key = (("ArrowDown", 40) if name.startswith("selected-arrow-")
                                        else ("F10", 121) if keyboard_menu
                                        else ("ContextMenu", 93) if name in {"context-menu", "selected-context-menu"} else ("Escape", 27))
                    shared = {"key": key, "code": key, "windowsVirtualKeyCode": virtual_key,
                              "nativeVirtualKeyCode": virtual_key, "modifiers": 8 if keyboard_menu else 0}
                    def key_up(_value: object) -> None:
                        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **shared}, released, f"{name}-up")

                    def key_down(_value: object) -> None:
                        if name in {"context-keyboard", "context-menu"}:
                            cdp.evaluate("window.__inventoryContextDown();true", key_up, f"{name}-opened")
                        else:
                            key_up(_value)

                    cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", **shared}, key_down, f"{name}-down")
                    return
                mouse_button = "right" if name == "context-open" else "left"
                modifiers = 8 if name == "range-end" else 2 if name in {"range-toggle", "range-file-toggle"} else 0
                cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "button": mouse_button,
                    "buttons": 2 if mouse_button == "right" else 1, "clickCount": 1, "modifiers": modifiers, **point},
                    lambda _value: cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased",
                        "button": mouse_button, "buttons": 0, "clickCount": 1, "modifiers": modifiers, **point},
                        released, f"{name}-up"), f"{name}-down")

            def require_foreground() -> None:
                nonlocal observed_handle
                observed_handle = foreground_window_handle()
                if observed_handle == owned_handle:
                    if name == "refresh":
                        fixture = phase.remove_fixture_file()
                        cdp.evaluate(f"window.__inventoryFixture={json.dumps(fixture)};true",
                                     lambda _value: check_target(), "fixture-identity")
                    else:
                        check_target()
                elif focus_deadline is not None and monotonic() < focus_deadline:
                    cdp.evaluate("new Promise(resolve => setTimeout(() => resolve(true), 100))",
                                 lambda _value: require_foreground(), "wait-foreground")
                else:
                    raise RuntimeError("native inventory window is not foreground")

            def check_target() -> None:
                cdp.evaluate("window.__inventoryNativeCheck()", dispatch_owned, f"preclick-{name}")

            def require_runner_entry() -> None:
                if runner_deadline is None or phase.observe_verify_runner_entry(name):
                    require_foreground()
                elif monotonic() < runner_deadline:
                    cdp.evaluate("new Promise(resolve => setTimeout(() => resolve(true), 100))",
                                 lambda _value: require_runner_entry(), f"wait-{name}-runner-entry")
                else:
                    raise RuntimeError("native integrity runner did not enter before control")

            require_runner_entry()

        cdp.evaluate(expression, click, f"wait-{name}")

    def finished(value: object) -> None:
        nonlocal checkpoint, page_result
        checkpoint = "page-result"
        if type(value) is dict:
            page_result = {key: value.get(key) for key in
                           ("table_appearance", "filter_geometry", "filter_colors", "filter_menu", "row_menu", "keyboard_input", "native_clicks", "pane_visible", "refreshed_missing", "acknowledged_hidden", "restored_missing", "status", "selected_refresh", "integrity_journey")}
        if type(value) is not dict or value.get("native_clicks") != {name: True for name in stage_names} or any(value.get(key) is not True for key in
                 ("pane_visible", "refreshed_missing", "acknowledged_hidden", "restored_missing")):
            raise RuntimeError("native inventory page result is invalid")
        checkpoint = "phase-report"
        report = phase.report()
        report["blank_scanning_shell"] = phase.initial_scan_entered.is_set() and phase.initial_scan_release.is_set()
        report.update(value)
        report["foreground_owned"] = dict(foreground_owned)
        cdp.capture(screenshot, lambda: captured(report), "capture")

    def captured(report: dict[str, object]) -> None:
        dimensions = decode_png(screenshot)
        report["dimensions"] = list(dimensions)
        close = r"""(async()=>{const button=document.querySelector('.nami-task-rail__row .nami-task-rail__close');
          if(!(button instanceof HTMLButtonElement)||button.disabled)throw new Error('task-close-unavailable');
          button.click();for(let i=0;i<1200;i++){if(!document.querySelector('.nami-task-rail__row .nami-task-card'))return true;
          await new Promise(r=>setTimeout(r,25));}throw new Error('task-close-timeout');})()"""
        cdp.evaluate(close, lambda closed: close_verified(report, closed), "task-close")

    def close_verified(report: dict[str, object], closed: object) -> None:
        if closed is not True:
            raise RuntimeError("explicit inventory Close was not observed")
        phase.verify_closed()
        report["task_closed"] = True
        recorder.ready(report)

    def initial_loading(value: object) -> None:
        if value is not True or not phase.initial_scan_entered.is_set():
            raise RuntimeError("initial inventory loading witness is invalid")
        phase.initial_scan_release.set()
        cdp.evaluate(_PAGE, finished, "page")
        next_stage(0)

    loading = r"""(async()=>{for(let i=0;i<1200;i++){
      const pane=document.querySelector('.nami-inventory-review');
      if(pane?.querySelector('.nami-plan-review__status-title')?.textContent==='Scanning'
          && pane.querySelector('.nami-progress--indeterminate')
          && !pane.querySelector('.nami-inventory-review__content').hidden
          && pane.querySelectorAll('.nami-inventory-review__rows > .nami-tree-row[role="treeitem"][data-node-id]').length===0
          && pane.querySelector('[data-action="inventory-refresh"]').disabled) return true;
      await new Promise(r=>setTimeout(r,25));}throw new Error('initial-inventory-loading');})()"""
    cdp.evaluate(loading, initial_loading, "initial-loading")


def _run(arguments: argparse.Namespace, recorder: _Recorder) -> int:
    from namisync.interfaces.web import host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    phase = _InventoryPhase(arguments.source)
    retained: list[object] = []
    original_appearance = host._configure_window_appearance
    original_commands = host._production_commands

    def commands(**kwargs: object) -> object:
        return phase.wrap(original_commands(**kwargs))

    def extension(_document: object, registry: object) -> dict[str, object]:
        phase.bind(registry)
        return {}

    def configure(window: object, *args: object, **kwargs: object) -> object:
        controller = original_appearance(window, *args, **kwargs)
        def loaded() -> None:
            from System import Action
            def begin() -> None:
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
        try:
            code = host.run_desktop(
                AppPaths.from_root(arguments.data_dir),
                DesktopInstanceIdentity(arguments.mutex, arguments.title),
                startup_error=lambda _message: recorder.fail("startup", "DesktopStartupError"),
            )
        finally:
            phase.initial_scan_release.set()
            phase.verify_release.set()
    if not recorder.settled:
        recorder.fail("child", "HostReturned")
    recorder.finish(code, True)
    return code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--screenshot", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    arguments = parser.parse_args()
    recorder = _Recorder(EvidencePaths(arguments.evidence_dir.resolve()))
    try:
        return _run(arguments, recorder)
    except BaseException as error:
        recorder.fail("child", type(error).__name__)
        recorder.finish(1, False)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
