"""Bounded, optional installed table-loading observations; no latency gate."""

from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from dataclasses import replace
import hashlib
import importlib.metadata
import math
import json
import os
from pathlib import Path
import platform
import re
import statistics
import sys
from threading import Lock, local
from time import perf_counter_ns
from types import MethodType
from unittest.mock import patch
from uuid import uuid4

from . import inventory, plan
from ._child import run_child
from .execution_receipt import _rootless_settlement


CASES = ("plan-base", "inventory-base")
GESTURES = ("sequential", "jump", "covered-return", "burst", "keyboard")
PROBE = Path(__file__).with_name("table_loading_probe.mjs")
PROFILE_NAME = "c5-host-profile.json"
OWNERSHIP_NAME = ".namisync-table-loading-owned.json"
MODULE = "tools.performance.table_loading"
LIMIT = 1024
BROWSER_PHASES = ("intent_wait_ns", "readiness_wait_ns", "round_trip_ns", "decode_ns", "validation_ns")
HOST_PHASES = ("pre_handler_ns", "registry_ns", "window_build_ns", "capture_ns", "projection_ns", "native_json_encode_ns", "canonical_budget_bytes", "native_json_bytes", "native_callback_script_bytes")
def _replace_once(text: str, old: str, new: str) -> str:
    pattern = re.escape(old).replace(re.escape("\n"), r"\r?\n")
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise ValueError("table-loading instrumentation anchor drifted")
    match = matches[0]
    newline = "\r\n" if "\r\n" in match.group() else "\n"
    return text[:match.start()] + new.replace("\n", newline) + text[match.end():]


def transform_asset(name: str, source: str) -> str:
    hooks = {
        "app.js": (
            ("  const request = ++task.reviewRevision;", "  globalThis.__tableLoading.initialRead('plan', task);\n  const request = ++task.reviewRevision;"),
            ("  const request = ++task.inventoryRevision;", "  globalThis.__tableLoading.initialRead('inventory', task);\n  const request = ++task.inventoryRevision;"),
            ("async function loadPlanWindow(review, offset) {", "async function loadPlanWindow(review, offset) {\n  globalThis.__tableLoading.intent('plan', offset);"),
            ("async function loadInventoryWindow(review, offset) {", "async function loadInventoryWindow(review, offset) {\n  globalThis.__tableLoading.intent('inventory', offset);"),
            ("void finishStartup().catch(() => {", "globalThis.__tableLoadingApp = Object.freeze({currentTask, selectTask, snapshot(taskId, component) {\n  const task = tasks.get(taskId);\n  const review = component === 'plan' ? task?.review : task?.inventoryReview;\n  return {task_id: task?.taskId ?? null, session_id: task?.sessionId ?? null,\n    publication_request_id: review?.summary.request_id ?? task?.requestId ?? null,\n    navigation_revision: navigationRevision, view_revision: review?.summary.view_revision ?? null,\n    action_revision: review?.actionRevision ?? null, window_request_revision: review?.windowRequestRevision ?? null,\n    initial_load_revision: component === 'plan' ? task?.reviewRevision : task?.inventoryRevision,\n    follow_generation: review?.follow?.generation ?? null};\n}});\nvoid finishStartup().catch(() => {"),
        ),
        "bridge.js": (
            ("const BRIDGE_SCHEMA_VERSION = 1;", PROBE.read_text(encoding="utf-8").split("// DRIVER\n")[0] + "\nconst BRIDGE_SCHEMA_VERSION = 1;"),
            ("    attempt.dispatched = true;", "    globalThis.__tableLoading.submit(attempt, request);\n    attempt.dispatched = true;"),
            ("export async function getPlanWindow(taskId, expectedRevision, offset, limit) {", "export async function getPlanWindow(taskId, expectedRevision, offset, limit) {\n  globalThis.__tableLoading.read('plan', offset);"),
            ("export function getInventoryWindow(taskId, expectedRevision, offset, limit) {", "export function getInventoryWindow(taskId, expectedRevision, offset, limit) {\n  globalThis.__tableLoading.read('inventory', offset);"),
            ("async function acceptNativeResponse(attempt, api, native) {", "async function acceptNativeResponse(attempt, api, native) {\n  globalThis.__tableLoading.native(attempt.requestId);"),
            ("    settleAttemptResponse(attempt, response);", "    settleAttemptResponse(attempt, response);\n    globalThis.__tableLoading.validated(attempt, response);"),
        ),
        "tree.js": (
            ("    const offset = window.offset;", "    const loadingStarted = performance.now();\n    const offset = window.offset;"),
            ("    return true;\n  }\n\n  function setActive", "    globalThis.__tableLoading.dom(window, loadingStarted, {generation, current_generation: currentGeneration});\n    return true;\n  }\n\n  function setActive"),
        ),
        "plan_review.js": (
            ("    const checkboxes = [];", "    const loadingStarted = performance.now();\n    const checkboxes = [];"),
            ("      activeOperationId: task.progressPresentation?.activeItem?.item_id ?? null,\n    };\n  }", "      activeOperationId: task.progressPresentation?.activeItem?.item_id ?? null,\n    };\n    globalThis.__tableLoading.dom(review.window, loadingStarted);\n  }"),
        ),
    }
    for old, new in hooks[name]:
        source = _replace_once(source, old, new)
    return source


@contextmanager
def instrumented_assets(installed_root: Path, evidence_root: Path):
    """Parent-owned restoration also runs after a killed measurement child."""
    marker = json.loads((installed_root / OWNERSHIP_NAME).read_bytes())
    if marker.get("purpose") != "GUI-C5 disposable installed measurement":
        raise ValueError("a new task-owned C5 installation is required")
    assets = installed_root / "namisync/interfaces/web/assets"
    evidence_root.mkdir()
    originals, transformed, hashes = {}, {}, {}
    for name in ("app.js", "bridge.js", "tree.js", "plan_review.js"):
        path = assets / name
        original = path.read_bytes()
        replacement = transform_asset(name, original.decode("utf-8")).encode("utf-8")
        originals[path], transformed[path] = original, replacement
        hashes[name] = {"original": hashlib.sha256(original).hexdigest(), "instrumented": hashlib.sha256(replacement).hexdigest()}
        (evidence_root / f"{name}.original").write_bytes(original)
        (evidence_root / f"{name}.instrumented").write_bytes(replacement)
    manifest = {"hashes": hashes, "restored": False, "installed_root": str(installed_root)}
    manifest_path = evidence_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    try:
        for path, replacement in transformed.items():
            path.write_bytes(replacement)
        yield hashes
    finally:
        failures = []
        for path, original in originals.items():
            try:
                path.write_bytes(original)
                restored = path.read_bytes()
                (evidence_root / f"{path.name}.restored").write_bytes(restored)
                if restored != original:
                    raise OSError("restored installed asset differs")
            except OSError as error:
                failures.append(f"{path.name}: {error}")
        manifest.update(restored=not failures, restoration_failures=failures)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        if failures:
            raise RuntimeError("C5 asset restoration failed: " + "; ".join(failures))


class HostTimings:
    def __init__(self):
        self.current = local()
        self.records = []
        self.lock = Lock()

    def span(self, name, original):
        def invoke(*args, **kwargs):
            record = getattr(self.current, "record", None)
            if record is None or name in getattr(self.current, "active", set()):
                return original(*args, **kwargs)
            self.current.active.add(name)
            started = perf_counter_ns()
            try:
                return original(*args, **kwargs)
            finally:
                elapsed = perf_counter_ns() - started
                record[name] = record.get(name, 0) + elapsed
                self.current.active.remove(name)
        return invoke

    @contextmanager
    def installed(self):
        from namisync.interfaces.web import bridge
        from namisync.interfaces.web.drain import TaskRegistry
        from namisync.interfaces.web.inventory_review import InventoryReviewState
        from namisync.interfaces.web.plan_review import PlanReviewState
        import webview.util
        from webview.window import Window

        original_dispatch = bridge.BridgeDispatcher._dispatch_native
        original_execute = bridge.BridgeDispatcher._execute_prepared_command
        original_budget = bridge._JsonByteBudget.consume
        original_evaluate = Window.evaluate_js
        original_json = webview.util.json

        def dispatch(dispatcher, command_json):
            payload = json.loads(command_json) if command_json.startswith("{") else {}
            record = None
            if payload.get("command") in ("get_plan_window", "get_inventory_window"):
                record = {"request_id": payload["request_id"], "payload": payload["payload"], "command": payload["command"], "entered_ns": perf_counter_ns()}
                with self.lock:
                    if len(self.records) >= LIMIT:
                        raise RuntimeError("table-loading host recorder overflow")
                    self.records.append(record)
            self.current.record, self.current.active = record, set()
            return original_dispatch(dispatcher, command_json)

        def execute(dispatcher, request_id, name, spec, prepared, **kwargs):
            record = getattr(self.current, "record", None)
            if record is not None:
                record["pre_handler_ns"] = perf_counter_ns() - record["entered_ns"]
            return original_execute(dispatcher, request_id, name, spec, prepared, **kwargs)

        def budget(owner, count):
            result = original_budget(owner, count)
            record = getattr(self.current, "record", None)
            if record is not None and "capture_ns" in self.current.active:
                record["canonical_budget_bytes"] = record.get("canonical_budget_bytes", 0) + count
            return result

        class JsonProxy:
            def __getattr__(self, name):
                return getattr(original_json, name)

            def dumps(self, value, *args, **kwargs):
                record = getattr(self_outer.current, "record", None)
                if record is None:
                    return original_json.dumps(value, *args, **kwargs)
                started = perf_counter_ns()
                encoded = original_json.dumps(value, *args, **kwargs)
                record["native_json_encode_ns"] = perf_counter_ns() - started
                record["native_json_bytes"] = len(encoded.encode("utf-8"))
                return encoded

        def evaluate(window, script, *args, **kwargs):
            record = getattr(self.current, "record", None)
            if record is not None and "_returnValuesCallbacks" in script:
                record["native_callback_script_bytes"] = len(script.encode("utf-8"))
                self.current.record = None
            return original_evaluate(window, script, *args, **kwargs)

        self_outer = self
        with ExitStack() as stack:
            for owner, name, replacement in (
                (bridge.BridgeDispatcher, "_dispatch_native", dispatch),
                (bridge.BridgeDispatcher, "_execute_prepared_command", execute),
                (bridge._JsonByteBudget, "consume", budget),
                (webview.util, "json", JsonProxy()), (Window, "evaluate_js", evaluate),
                (TaskRegistry, "get_plan_window", self.span("registry_ns", TaskRegistry.get_plan_window)),
                (TaskRegistry, "get_inventory_window", self.span("registry_ns", TaskRegistry.get_inventory_window)),
                (PlanReviewState, "window", self.span("window_build_ns", PlanReviewState.window)),
                (InventoryReviewState, "window", self.span("window_build_ns", InventoryReviewState.window)),
                (bridge, "_capture_bridge_response_result", self.span("capture_ns", bridge._capture_bridge_response_result)),
                (bridge, "_project_response_value", self.span("projection_ns", bridge._project_response_value)),
            ):
                stack.enter_context(patch.object(owner, name, replacement))
            yield


def check_fixtures():
    artifact = plan.build_plan_fixture(information_heavy=False)
    view = plan.make_plan_review_state(artifact)
    # Match TaskRegistry.open_plan_view's initial prior-group collapse.
    view = replace(view, collapsed_node_ids=frozenset(node.node_id for node in view.projection.nodes if node.row_kind == "prior-group"))
    window = view.window(expected_revision=0, offset=0, limit=256)
    if len(view.projection.nodes) != 120_000 or window["total"] != 119_968 or len(window["rows"]) != 256:
        raise ValueError("Plan base fixture changed")
    from namisync.workflows.inventory_projection import build_inventory_projection
    rows, warnings = inventory.fixture("base")
    projection = build_inventory_projection(1, rows, warnings)
    inventory.correctness(projection, rows, warnings, "base")
    return {"plan-base": {"projection_nodes": 120_000, "visible_rows": 119_968}, "inventory-base": {"projection_nodes": 120_001, "visible_rows": 120_000}}


def _run_installed(case, output, token):
    from namisync.interfaces.ui_state import AppearanceValue
    from namisync.interfaces.web import host
    from namisync.workflows import LocationCandidate
    from namisync.workflows.inventory_projection import build_inventory_projection
    original_controller = plan._HeadedFixtureController
    original_ui_state = host._ui_state_owner

    with ExitStack() as stack:
        class Fixture(original_controller):
            _settle_initial_view = staticmethod(_rootless_settlement)

            def bind(self, registry):
                if case == "plan-base":
                    super().bind(registry)
                    row = self.metadata["rows"][0]
                    self.facts = {"case": case, "task_id": row["task_id"], "request_id": row["request_id"], "session_id": row["plan_session_id"], "visible_rows": 119_968}
                    return
                source = self.fixture_root / "inventory"
                source.mkdir(parents=True)
                shell = registry.create_task_shell(uuid4().hex)
                started = registry.start_setup_inventory(shell.task_id, LocationCandidate.literal(str(source)), command_id=uuid4().hex, wire_intent=("table-loading", str(source)))
                self._drain_and_release(registry, started)
                lifecycle = registry._lifecycle
                _, details = lifecycle.get_task_inventory_projection(started.task_id, started.request_id)
                rows, warnings = inventory.fixture("base")
                projection = build_inventory_projection(details.location_id, rows, warnings)
                inventory.correctness(projection, rows, warnings, "base")
                captured = replace(details, observed_count=100_000)
                original = lifecycle.get_task_inventory_projection

                def published(_service, task_id, request_id):
                    if (task_id, request_id) == (started.task_id, started.request_id):
                        return projection, captured
                    return original(task_id, request_id)

                stack.enter_context(patch.object(lifecycle, "get_task_inventory_projection", MethodType(published, lifecycle)))
                summary = registry.open_inventory_view(started.task_id)
                if summary["visible_row_count"] != 120_000 or not summary["scan_complete"]:
                    raise ValueError("Inventory published base fixture changed")
                self.facts = {"case": case, "task_id": started.task_id, "request_id": started.request_id, "session_id": started.session_id, "visible_rows": 120_000}
                self.published_fixture = dict(self.facts)

            def command(self, payload):
                if payload != {}:
                    raise ValueError("table-loading fixture accepts empty metadata only")
                return dict(self.facts)

        probe = PROBE.read_text(encoding="utf-8").split("// DRIVER\n")[1]
        def light_ui_state(path):
            owner = original_ui_state(path)
            try:
                owner.replace_section("appearance", 1, owner.read_section("appearance", 1).revision, AppearanceValue("light"))
            except BaseException:
                owner.close()
                raise
            return owner

        stack.enter_context(patch.object(host, "_ui_state_owner", light_ui_state))
        stack.enter_context(patch.object(plan, "_HeadedFixtureController", Fixture))
        stack.enter_context(patch.object(plan, "_headed_probe_script", lambda _metric: probe))
        timing = HostTimings()
        stack.enter_context(timing.installed())
        try:
            browser, headed_runtime, fixture = plan._run_headed_page({"id": case}, output.parent, 1)
        except BaseException as error:
            output.write_text(json.dumps({"complete": False, "error": str(error)[:512], "case": case, "launch_token": token, "host": timing.records}) + "\n", encoding="utf-8")
            raise
    return {"case": case, "launch_token": token, "process_id": os.getpid(), "parent_process_id": os.getppid(), "browser": browser, "host": timing.records, "fixture": fixture, "headed_runtime": headed_runtime, "runtime": {"python": sys.version, "platform": platform.platform(), "namisync_file": __import__("namisync").__file__, "versions": {name: importlib.metadata.version(name) for name in ("namisync", "pywebview", "pythonnet")}}}


def validate_child(receipt, case, token, installed_root=None):
    if receipt.get("case") != case or receipt.get("launch_token") != token:
        raise ValueError("table-loading child identity differs")
    browser = receipt.get("browser")
    if receipt.get("complete") is False or not isinstance(browser, dict) or browser.get("complete") is not True:
        reason = browser.get("error", "missing browser completion") if isinstance(browser, dict) else receipt.get("error", "missing browser receipt")
        raise ValueError("table-loading child incomplete: " + str(reason)[:512])
    if installed_root is not None and Path(receipt["runtime"]["namisync_file"]).resolve() != (installed_root / "namisync/__init__.py").resolve():
        raise ValueError("table-loading did not import the installed product")
    fixture = browser["fixture"]
    total = 119_968 if case == "plan-base" else 120_000
    if fixture["case"] != case or fixture["visible_rows"] != total or any(not fixture.get(name) for name in ("task_id", "session_id", "request_id")):
        raise ValueError("table-loading fixture identity differs")
    profile = browser["profile"]
    if (profile["theme"] != "light" or profile["reduced_motion"] or profile["forced_colors"]
        or profile["details_expanded"] != "false" or abs(profile["row_height"] - 24) > 0.1
        or profile["visibility_state"] != "visible" or not profile["document_has_focus"]
        or any(profile[name] <= 0 for name in ("inner_width", "inner_height", "device_pixel_ratio", "viewport_width", "viewport_height"))):
        raise ValueError("table-loading profile differs")
    samples = browser["gestures"]
    expected = [("initial", 1)] + [(name, index) for name in GESTURES for index in range(1, 4)]
    if [(row["kind"], row["iteration"]) for row in samples] != expected or not browser["complete"]:
        raise ValueError("table-loading gesture series incomplete")
    host = {row["request_id"]: row for row in receipt["host"]}
    if len(host) != len(receipt["host"]):
        raise ValueError("duplicate host request identity")
    if not host or set(host) != {row["request_id"] for row in browser["requests"]} or len(host) != len(browser["requests"]):
        raise ValueError("table-loading native request corpus incomplete")
    def check_owner(owner):
        if (owner["task_id"] != fixture["task_id"] or owner["session_id"] != fixture["session_id"]
            or owner["publication_request_id"] != fixture["request_id"]
            or type(owner["navigation_revision"]) is not int):
            raise ValueError("table-loading owner differs")
    for request in browser["requests"]:
        check_owner(request["ownership"])
        record = host.get(request["request_id"])
        if record is None or any(type(record.get(name)) is not int or record[name] < 0 for name in HOST_PHASES):
            raise ValueError("table-loading host phase missing")
        if record["payload"] != request["payload"] or record["command"] != request["command"] or record["payload"]["limit"] != 256:
            raise ValueError("table-loading request correlation differs")
        if (record["payload"]["task_id"] != fixture["task_id"] or request["row_count"] != 256
            or request["returned_offset"] != record["payload"]["offset"] or not request["returned_first_node_id"]):
            raise ValueError("table-loading returned window differs")
        if request.get("settlement_error") is not None or any(type(request.get(name)) is not int or request[name] < 0 for name in BROWSER_PHASES):
            raise ValueError("table-loading browser phase missing")
        if request["adopted"] and (type(request.get("dom_ns")) is not int or request["dom_ns"] < 0):
            raise ValueError("accepted table-loading DOM phase missing")
        if request["adopted"]:
            check_owner(request["adoption_ownership"])
    for sample in samples:
        check_owner(sample["ownership"])
        requests = [row for row in browser["requests"] if row["gesture"] == f'{sample["kind"]}-{sample["iteration"]}']
        target = {"initial": 0, "sequential": 256, "jump": 60_000, "covered-return": 0, "burst": 40_000}.get(sample["kind"])
        if target is None:
            setup_last = math.ceil((20_032 * 24 + profile["viewport_height"]) / 24) - 1
            setup_offset = (20_032 if case == "plan-base" else setup_last) - 32
            target = setup_offset - 1
        if (not sample["landed"] or not sample["covered"] or sample["row_count"] != 256 or sample["total"] != total
            or sample["target"] != target or sample["visibility_state"] != "visible" or not sample["document_has_focus"]
            or sample["settlement_pending"] != 0 or sample["settlement_ns"] < sample["paint_opportunity_ns"]
            or sample["offset"] > sample["first"] or sample["last"] >= sample["offset"] + sample["row_count"]
            or not sample["first_node_id"] or sample["frame_count"] < 2
            or (sample["kind"] == "keyboard" and (sample["setup_first"] != 20_032 or sample["setup_last"] != setup_last
                or sample["setup_offset"] != setup_offset or sample["active_index"] != target or not sample["active_node_id"]
                or not sample["first"] <= target <= sample["last"]))
            or (sample["kind"] != "keyboard" and sample["first"] != target)
            or sample["request_count"] != len(requests) or (sample["kind"] != "covered-return" and not requests)
            or sample["uncovered_ns"] < 0 or sample["paint_opportunity_ns"] < sample["covered_ns"]):
            raise ValueError("table-loading gesture did not land truthfully")
    return receipt


def summarize_children(receipts):
    def summary(values):
        return {"count": len(values), "median": statistics.median(values) if values else None,
                "minimum": min(values) if values else None, "maximum": max(values) if values else None}

    result = {}
    for name in ("initial", *GESTURES):
        samples, requests, host = [], [], []
        for receipt in receipts:
            samples.extend(row for row in receipt["browser"]["gestures"] if row["kind"] == name)
            selected = [row for row in receipt["browser"]["requests"] if row["gesture"] is not None and row["gesture"].rsplit("-", 1)[0] == name]
            requests.extend(selected)
            identities = {row["request_id"] for row in selected}
            host.extend(row for row in receipt["host"] if row["request_id"] in identities)
        adopted = [row for row in requests if row["adopted"]]
        result[name] = {
            "counts": {"gestures": len(samples), "requests": len(requests), "adopted": len(adopted), "discarded": len(requests) - len(adopted)},
            "gesture": {field: summary([row[field] for row in samples]) for field in ("covered_ns", "paint_opportunity_ns", "settlement_ns", "uncovered_ns", "maximum_outstanding")},
            "browser": {field: summary([row[field] for row in requests]) for field in BROWSER_PHASES},
            "host": {field: summary([row[field] for row in host]) for field in HOST_PHASES},
            "adopted_dom_ns": summary([row["dom_ns"] for row in adopted]),
        }
    return result


def _one_child(case, output, installed_root):
    token = uuid4().hex
    evidence = output.with_name(f"{output.stem}-{token}-assets")
    with instrumented_assets(installed_root, evidence) as hashes:
        receipt = run_child(MODULE, ["--child", case, "--launch-token", token], output=output, installed_root=installed_root)
    receipt["instrumentation"] = {"hashes": hashes, "restored": True}
    try:
        return validate_child(receipt, case, token, installed_root)
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(f"{error}; raw log: {receipt.get('raw_log')}; assets: {evidence}") from error


def run_case(case, *, output, installed_root=None, children=3):
    if case not in CASES or installed_root is None:
        raise ValueError("table-loading requires a named case and fresh --installed-root")
    profile_path = output.parent / PROFILE_NAME
    profile_bytes = profile_path.read_bytes()
    profile = json.loads(profile_bytes)
    receipts = [_one_child(case, output, installed_root.resolve()) for _ in range(children)]
    if profile_path.read_bytes() != profile_bytes:
        raise ValueError("table-loading host profile changed during collection")
    for receipt in receipts:
        receipt["statistics"] = summarize_children([receipt])
    statistics_by_gesture = summarize_children(receipts)
    return {"authority": "diagnostic; no latency gate", "host_profile": profile, "host_profile_sha256": hashlib.sha256(profile_bytes).hexdigest(), "children": receipts, "statistics": statistics_by_gesture, "unobserved": ["host thread/lock queue wait", "actual compositor presentation"], "intervals": "server phases and decode nest within browser round trip; window build nests within registry; never add nested spans"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--child", choices=CASES)
    choice.add_argument("--probe", choices=CASES)
    choice.add_argument("--check", action="store_true")
    parser.add_argument("--launch-token")
    parser.add_argument("--installed-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check_fixtures()))
        return 0
    if args.output is None or args.output.exists():
        parser.error("a new --output path is required")
    if args.child:
        receipt = _run_installed(args.child, args.output, args.launch_token)
    else:
        receipt = run_case(args.probe, output=args.output, installed_root=args.installed_root, children=1)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
