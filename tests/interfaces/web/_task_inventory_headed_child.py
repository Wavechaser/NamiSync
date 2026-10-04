"""Installed-wheel child for the native M1-9 inventory action witness."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
import threading
from time import monotonic
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from typing import Callable
from unittest.mock import patch

from _headed_cdp import NativeCdp, decode_png, failure_site
from _headed_evidence import EvidencePaths, EvidencePublisher
from _headed_native import foreground_window_handle
from _startup_test_support import headed_command_extension


_COMMANDS = frozenset({"refresh_inventory", "acknowledge_inventory", "restore_inventory"})
_FILE_BYTES = b"NamiSync native inventory fixture\r\n"
_OWN_FAILURES = frozenset({
    "inventory command evidence is incomplete",
    "inventory action identities or actual effects differ",
    "inventory publication was not replaced",
    "native inventory page result is invalid",
    "native inventory window is not foreground",
    "native inventory point is invalid",
    "native inventory click target is unavailable",
    "inventory fixture identity is unavailable",
}) | frozenset(f"inventory {name} did not have one original command" for name in _COMMANDS)


def _owned_failure(error: BaseException) -> str | None:
    message = str(error)
    return message if message in _OWN_FAILURES else None


class _InventoryPhase:
    def __init__(self, source: Path) -> None:
        self.source = source
        self.lock = threading.Lock()
        self.registry: object | None = None
        self.initial: dict[str, object] | None = None
        self.fixture: dict[str, object] | None = None
        self.commands: list[dict[str, object]] = []
        self.failure: dict[str, object] | None = None

    def bind(self, registry: object) -> None:
        from namisync.workflows import LocationCandidate

        self.source.mkdir(parents=True, exist_ok=True)
        if any(self.source.iterdir()):
            raise RuntimeError("inventory fixture root must start empty")
        folder = self.source / "folder"
        folder.mkdir()
        (folder / "one.txt").write_bytes(_FILE_BYTES)
        (folder / "two.txt").write_bytes(_FILE_BYTES)
        shell = registry.create_task_shell("a" * 32)
        started = registry.start_setup_inventory(
            shell.task_id, LocationCandidate.literal(str(self.source)),
            command_id="b" * 32, wire_intent=("headed-inventory", str(self.source)),
        )
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
        fixture = {"folder_node_id": folder.node_id, "missing_node_id": missing.node_id,
                   "folder_display": folder.display, "missing_display": missing.display,
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
        for name in _COMMANDS:
            spec = wrapped[name]
            if type(spec) is not CommandSpec:
                raise TypeError("inventory command is not an exact CommandSpec")
            wrapped[name] = replace(spec, handler=self._observe(name, spec.handler))
        return wrapped

    def _observe(self, name: str, original: Callable[[object], object]) -> Callable[[object], object]:
        from namisync.interfaces.web.bridge import to_primitive_view

        def invoke(payload: object) -> object:
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
                    record.update({"task_id": payload.task_id, "request_id": payload.request_id,
                                   "command_id": payload.command_id, "node_id": payload.node_id})
                    if name == "refresh_inventory":
                        record.update({"request_id": result.request_id, "session_id": result.session_id,
                                       "prior_request_id": payload.request_id})
                except BaseException as error:
                    if self.failure is None:
                        self.failure = {"command": name, "stage": "observation", "reason": type(error).__name__,
                                        "assertion": _owned_failure(error)}
            return result
        return invoke

    def diagnostic(self) -> dict[str, object]:
        with self.lock:
            commands = list(self.commands)
            failure = self.failure
        return {
            "commands": [
                {"command": item["command"],
                 "result": item["result"] if type(item["result"]) is dict else None,
                 "original_result_type": item["original_result_type"]}
                for item in commands[:64]
            ],
            "wrapper_failure": failure,
        }

    def report(self) -> dict[str, object]:
        with self.lock:
            registry, initial = self.registry, self.initial
            commands, failure, fixture = list(self.commands), self.failure, self.fixture
        if registry is None or initial is None or failure is not None or fixture is None:
            raise RuntimeError("inventory command evidence is incomplete")
        def one(name: str) -> dict[str, object]:
            matches = [item for item in commands if item["command"] == name]
            if len(matches) != 1:
                raise RuntimeError(f"inventory {name} did not have one original command")
            return matches[0]
        refresh = one("refresh_inventory")
        acknowledge = one("acknowledge_inventory")
        restore = one("restore_inventory")
        if (refresh["prior_request_id"] != initial["request_id"]
                or refresh["request_id"] == initial["request_id"]
                or acknowledge["request_id"] != refresh["request_id"]
                or restore["request_id"] != refresh["request_id"]
                or acknowledge["node_id"] != fixture["folder_node_id"]
                or restore["node_id"] != fixture["folder_node_id"]
                or any(item["task_id"] != initial["task_id"] for item in commands)
                or acknowledge["result"]["applied"] != 1
                or restore["result"]["applied"] != 1):
            raise RuntimeError("inventory action identities or actual effects differ")
        view = registry.open_inventory_view(initial["task_id"])
        if view["request_id"] != refresh["request_id"]:
            raise RuntimeError("inventory publication was not replaced")
        return {"initial": initial, "fixture": fixture,
                "results": {"refresh": {"request_id": refresh["request_id"],
                                        "session_id": refresh["session_id"]},
                            "acknowledge": acknowledge["result"], "restore": restore["result"]},
                "publication": {"request_id": view["request_id"],
                                "view_revision": view["view_revision"],
                                "missing": view["rollup"]["missing"],
                                "acknowledged": view["rollup"]["acknowledged"]}}

    def verify_closed(self) -> None:
        with self.lock:
            registry, initial = self.registry, self.initial
        if registry is None or initial is None:
            raise RuntimeError("inventory close has no task identity")
        if any(task.task_id == initial["task_id"] for task in registry.list_tasks().tasks):
            raise RuntimeError("inventory task remained after explicit Close")
        if initial["task_id"] in registry._inventory_views:
            raise RuntimeError("inventory publication remained after Close")
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
    for (let i = 0; i < attempts; i += 1) {
      const value = await fn();
      if (value) return value;
      await new Promise(resolve => setTimeout(resolve, 25));
    }
    throw new Error(label);
  };
  const card = await until(() => document.querySelector('.nami-task-rail__row .nami-task-card'), 'task-card');
  card.click();
  const review = await until(() => {
    const pane = document.querySelector('.nami-inventory-review');
    return pane?.isConnected && !pane.querySelector('[data-action="inventory-refresh"]')?.disabled
      && pane.querySelector('.nami-inventory-review__rows [data-node-id]') ? pane : null;
  }, 'initial-inventory-view');
  const nativeClicks = Object.fromEntries(['refresh', 'filter-open', 'filter-present', 'filter-escape', 'filter-reopen', 'filter-all', 'details', 'acknowledge', 'restore-details', 'restore'].map(name => [name, false]));
  async function stage(name) {
    await until(() => document.hasFocus(), 'document-focus');
    let listenedControl = null;
    window.__inventoryNativeCheck = async () => {
      const selector = name === 'filter-open' || name === 'filter-reopen' ? '[data-action="filter-menu"]'
        : name === 'filter-present' || name === 'filter-escape' ? '.nami-filter-menu__popup [data-filter="present"]'
        : name === 'filter-all' ? '.nami-filter-menu__popup [data-filter="all"]'
        : name === 'restore-details' ? '[data-action="inventory-details"]'
        : `[data-action="inventory-${name}"]`;
      const control = review.querySelector(selector);
      if (control === null) return {point:null, facts:{connected:false}};
      control.focus();
      await new Promise(resolve => requestAnimationFrame(resolve));
      const rect = control.getBoundingClientRect();
      const point = {x:(rect.left+rect.right)/2, y:(rect.top+rect.bottom)/2};
      const hit = document.elementFromPoint(point.x, point.y);
      const facts = {document_focused:document.hasFocus(), connected:control.isConnected,
        enabled:!control.disabled, visible:!control.hidden, active:document.activeElement === control,
        hit_owned:control.contains(hit) || hit === control, sized:rect.width > 0 && rect.height > 0};
      if (listenedControl !== control) {
        control.addEventListener(name === 'filter-escape' ? 'keydown' : 'click', event => { nativeClicks[name] ||= event.isTrusted; }, {once:true});
        listenedControl = control;
      }
      return {point, facts};
    };
    window.__inventoryNativeStage = `${name}-ready`;
    await until(() => window.__inventoryNativeAck === name, `native-${name}`, name === 'refresh' ? 2800 : 1200);
    await until(() => nativeClicks[name], `trusted-${name}`);
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
  const neutral = filterTrigger.children[2].textContent === '0' && filterTrigger.dataset.active === 'false'
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
  await until(() => filterTrigger.children[2].textContent === '1'
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
  await until(() => filterTrigger.children[2].textContent === '0'
    && filterPopup.querySelector('[data-filter="all"]').ariaChecked === 'true', 'filter-reset');
  const allKeepsOpen = !filterPopup.hidden;
  const allNoCount = filterPopup.querySelector('[data-filter="all"] .nami-filter-count').hidden;
  filterTrigger.focus();
  review.querySelector('[data-action="inventory-search"]').focus();
  const focusAwayClosed = filterPopup.hidden;
  const filterMenu = {neutral, staysOpen, accented, escapeFocus:true, allKeepsOpen, allNoCount, focusAwayClosed,
    firstReachable:menuGeometry.first.hit, lastReachable:menuGeometry.last.hit, popupInside};
  if (Object.values(filterMenu).some(value => value !== true)) throw new Error('filter menu contract failed');
  const fixture = window.__inventoryFixture;
  const row = id => [...review.querySelectorAll('.nami-inventory-review__rows [data-node-id]')]
    .find(value => value.dataset.nodeId === id);
  const missing = () => row(fixture.missing_node_id);
  await until(() => missing()?.querySelector('[data-integrity="missing"]')
    && review.textContent.includes('Displayed scan: Entire location')
    && review.textContent.includes('notices from this scan'), 'refreshed-missing');
  const folder = () => row(fixture.folder_node_id);
  const folderRow = await until(folder, 'folder-row');
  folderRow.click();
  await stage('details');
  await until(() => {
    const control = review.querySelector('[data-action="inventory-acknowledge"]');
    return control && !control.hidden && !control.disabled ? control : null;
  }, 'acknowledge-control');
  await stage('acknowledge');
  await until(() => !missing() && folder()
    && !review.querySelector('[data-action="inventory-refresh"]').disabled, 'acknowledged-hidden');
  const nextFolder = await until(folder, 'folder-after-acknowledge');
  nextFolder.click();
  await stage('restore-details');
  await until(() => {
    const control = review.querySelector('[data-action="inventory-restore"]');
    return control && !control.hidden && !control.disabled ? control : null;
  }, 'restore-control');
  await stage('restore');
  await until(() => missing()?.querySelector('[data-integrity="missing"]')
    && !review.querySelector('[data-action="inventory-refresh"]').disabled, 'restored-visible');
  return {filter_geometry:menuGeometry, filter_colors:filterColors, filter_menu:filterMenu, native_clicks:nativeClicks, pane_visible:review.isConnected && !review.hidden,
    refreshed_missing:true, acknowledged_hidden:true, restored_missing:true};
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
    foreground_owned = {name: False for name in ("refresh", "filter-open", "filter-present", "filter-escape", "filter-reopen", "filter-all", "details", "acknowledge", "restore-details", "restore")}

    def fail(error: BaseException, task: object | None, step: str, _method: str) -> None:
        nonlocal failed
        if failed:
            return
        failed = True
        recorder.fail(step, type(error).__name__)
        diagnostic = failure_site(task)
        diagnostic.update({"checkpoint": checkpoint, "page_result": page_result,
                           "foreground_owned": foreground_owned, "phase": phase.diagnostic(),
                           "assertion": _owned_failure(error),
                           "click_target": click_target,
                           "owned_handle": owned_handle, "observed_handle": observed_handle})
        screenshot.with_name("inventory-failure-site.json").write_text(
            json.dumps(diagnostic, sort_keys=True), encoding="utf-8",
        )

    cdp = NativeCdp(native, core, retained, fail)
    stage_names = ("refresh", "filter-open", "filter-present", "filter-escape", "filter-reopen", "filter-all", "details", "acknowledge", "restore-details", "restore")

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
                    cdp.evaluate(f"window.__inventoryNativeAck='{name}';true", lambda _ack: next_stage(index + 1), f"ack-{name}")
                if name == "filter-escape":
                    shared = {"key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27, "nativeVirtualKeyCode": 27}
                    cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", **shared},
                        lambda _value: cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **shared},
                            released, "filter-escape-up"), "filter-escape-down")
                    return
                cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "button": "left",
                    "buttons": 1, "clickCount": 1, **point},
                    lambda _value: cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased",
                        "button": "left", "buttons": 0, "clickCount": 1, **point},
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

            require_foreground()

        cdp.evaluate(expression, click, f"wait-{name}")

    def finished(value: object) -> None:
        nonlocal checkpoint, page_result
        checkpoint = "page-result"
        if type(value) is dict:
            page_result = {key: value.get(key) for key in
                           ("filter_geometry", "filter_colors", "filter_menu", "native_clicks", "pane_visible", "refreshed_missing", "acknowledged_hidden", "restored_missing")}
        if type(value) is not dict or value.get("native_clicks") != {name: True for name in stage_names} or any(value.get(key) is not True for key in
                 ("pane_visible", "refreshed_missing", "acknowledged_hidden", "restored_missing")):
            raise RuntimeError("native inventory page result is invalid")
        checkpoint = "phase-report"
        report = phase.report()
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

    cdp.evaluate(_PAGE, finished, "page")
    next_stage(0)


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
        code = host.run_desktop(
            AppPaths.from_root(arguments.data_dir),
            DesktopInstanceIdentity(arguments.mutex, arguments.title),
            startup_error=lambda _message: recorder.fail("startup", "DesktopStartupError"),
        )
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
