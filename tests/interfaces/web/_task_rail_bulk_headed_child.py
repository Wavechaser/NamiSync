"""Installed-wheel child for the rail's Pause all and Resume all journey."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
import threading
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from _headed_cdp import NativeCdp, decode_png, on_background_page_loaded
from _headed_evidence import EvidencePaths, EvidencePublisher
from _startup_test_support import headed_command_extension


_FOLDERS = ("first", "second", "third")
_BYTES = b"NamiSync rail bulk control fixture\r\n"
_HELD_NOTICE = "Held 2; 1 cannot pause and keeps running."
_RESUMED_NOTICE = "Resumed 2."
_COMPLETED_TITLE = "Inventory scan completed"
_HELD_TITLE = "Paused, not started"
# A bounded page wait: 40 seconds at 25 ms per poll.
_POLLS = 1600


class _Queue:
    """Three same-volume scans: the first runs behind a gate, two queue behind it."""

    def __init__(self, source: Path) -> None:
        self.source = source
        self.lock = threading.Lock()
        self.entered = threading.Event()
        self.release = threading.Event()
        self.scanner_calls = 0
        self.sessions: list[dict[str, str]] = []
        self.controls: list[dict[str, object]] = []

    def bind(self, registry: object) -> None:
        from namisync.workflows import LocationCandidate

        self.source.mkdir(parents=True, exist_ok=True)
        if any(self.source.iterdir()):
            raise RuntimeError("rail bulk fixture root must start empty")
        runtime = registry._lifecycle._runtime
        original = runtime._inventory_deps

        def gated_scan(*args: object, **kwargs: object) -> object:
            with self.lock:
                self.scanner_calls += 1
                first = self.scanner_calls == 1
            if first:
                self.entered.set()
                if not self.release.wait(90):
                    raise RuntimeError("rail bulk scan gate timed out")
            return original.scanner(*args, **kwargs)

        runtime._inventory_deps = replace(original, scanner=gated_scan)
        control_all = registry.control_all_tasks

        def observed_control_all(action: str) -> object:
            try:
                result = control_all(action)
            except BaseException as error:
                with self.lock:
                    self.controls.append({"action": action, "error": type(error).__name__})
                raise
            with self.lock:
                self.controls.append({"action": action, "result": {
                    name: getattr(result, name) for name in type(result).__slots__}})
            return result

        registry.control_all_tasks = observed_control_all
        for index, name in enumerate(_FOLDERS):
            folder = self.source / name
            folder.mkdir()
            (folder / "item.txt").write_bytes(_BYTES)
            shell = registry.create_task_shell(f"{index + 1:x}" * 32)
            started = registry.start_setup_inventory(
                shell.task_id, LocationCandidate.literal(str(folder)),
                command_id=f"{index + 4:x}" * 32, wire_intent=("headed-rail-bulk", str(folder)),
            )
            with self.lock:
                self.sessions.append({"task_id": started.task_id, "session_id": started.session_id})
            if index == 0 and not self.entered.wait(10):
                self.release.set()
                raise RuntimeError("first rail bulk scan did not enter")

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            return {"scanner_calls": self.scanner_calls, "sessions": list(self.sessions),
                    "controls": list(self.controls), "released": self.release.is_set()}


class _Recorder:
    def __init__(self, paths: EvidencePaths) -> None:
        self.publisher = EvidencePublisher(paths)
        self.lock = threading.Lock()
        self.settled = False

    def complete(self, report: dict[str, object]) -> None:
        with self.lock:
            if self.settled:
                return
            self.publisher.publish_ready({"report": report, "runtime": _runtime_identity()})
            self.settled = True

    def fail(self, stage: str, reason: str) -> None:
        with self.lock:
            if self.settled:
                return
            self.publisher.publish_failure({"failure": {"stage": stage, "type": reason}})
            self.settled = True

    def finish(self, code: int, returned: bool) -> None:
        self.publisher.publish_final({"exit_code": code, "host_returned": returned})


# The rail facts every wait reads: card titles in rail order, the two bulk
# buttons' effective availability and names, and the header notice.
_RAIL_FACTS = r"""
const railFacts = () => {
  const cards = [...document.querySelectorAll('.nami-task-rail__items .nami-task-card[data-task-label]')];
  const button = (index) => document.querySelectorAll('.nami-task-rail__bulk')[index] ?? null;
  const usable = (value) => value instanceof HTMLButtonElement && !value.disabled
    && value.getAttribute('aria-disabled') !== 'true';
  const point = (value) => {
    if (!usable(value)) return null;
    const rect = value.getBoundingClientRect();
    const center = {x: (rect.left + rect.right) / 2, y: (rect.top + rect.bottom) / 2};
    return document.elementFromPoint(center.x, center.y)?.closest('button') === value ? center : null;
  };
  const pause = button(0), resume = button(1);
  return {
    titles: cards.map((card) => card.querySelector('.nami-task-card__title')?.textContent ?? null),
    statuses: cards.map((card) => card.querySelector('.nami-task-card__status')?.textContent ?? null),
    pauseEnabled: usable(pause), resumeEnabled: usable(resume),
    pauseName: pause?.getAttribute('aria-label') ?? null, resumeName: resume?.getAttribute('aria-label') ?? null,
    pauseTooltip: pause?.title ?? null, resumeTooltip: resume?.title ?? null,
    notice: document.querySelector('.nami-task-rail__notice')?.textContent ?? null,
    noticeRole: document.querySelector('.nami-task-rail__notice')?.getAttribute('role') ?? null,
    pausePoint: point(pause), resumePoint: point(resume),
  };
};
"""


def _wait(condition: str) -> str:
    return ("(async () => {" + _RAIL_FACTS + f"""
  for (let i = 0; i < {_POLLS}; i += 1) {{
    const facts = railFacts();
    if ({condition}) return facts;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }}
  return {{timeout: true, facts: railFacts()}};
}})()""")


def _drive(window: object, queue: _Queue, recorder: _Recorder, retained: list[object],
           screenshot: Path) -> None:
    native = window.native
    failed = False

    def fail(error: BaseException, _task: object | None, step: str, _method: str) -> None:
        nonlocal failed
        if not failed:
            failed = True
            recorder.fail(step, type(error).__name__)

    cdp = NativeCdp(native, native.browser.webview.CoreWebView2, retained, fail)
    report: dict[str, object] = {}

    def checked(step: str, then: object) -> object:
        def receive(value: object) -> None:
            if type(value) is not dict or value.get("timeout") is True:
                _write_timeout(screenshot, step, value, queue.snapshot())
                raise TimeoutError(f"rail bulk {step} wait timed out")
            then(value)
        return receive

    def click(point: object, then: object, step: str) -> None:
        if type(point) is not dict or set(point) != {"x", "y"}:
            raise RuntimeError(f"rail bulk {step} target is unavailable")
        down = {"type": "mousePressed", "button": "left", "buttons": 1, "clickCount": 1, **point}
        up = {"type": "mouseReleased", "button": "left", "buttons": 0, "clickCount": 1, **point}
        cdp.call("Input.dispatchMouseEvent", down,
                 lambda _v: cdp.call("Input.dispatchMouseEvent", up, lambda _u: then(), step + "-up"),
                 step + "-down")

    def queued(facts: dict[str, object]) -> None:
        report["queued"] = facts
        click(facts["pausePoint"], lambda: cdp.evaluate(_wait(
            f"facts.notice === {json.dumps(_HELD_NOTICE)}"
            f" && facts.titles.filter((title) => title === {json.dumps(_HELD_TITLE)}).length === 2"
            " && facts.resumeEnabled"), checked("held", held), "held"), "pause-all")

    def held(facts: dict[str, object]) -> None:
        report["held"] = facts
        cdp.capture(screenshot, lambda: captured(facts), "capture")

    def captured(facts: dict[str, object]) -> None:
        report["capture_dimensions"] = list(decode_png(screenshot))
        click(facts["resumePoint"], lambda: cdp.evaluate(_wait(
            f"facts.notice === {json.dumps(_RESUMED_NOTICE)} && !facts.resumeEnabled"
            " && facts.titles.every((title) => !/paused/i.test(title ?? ''))"),
            checked("resumed", resumed), "resumed"), "resume-all")

    def resumed(facts: dict[str, object]) -> None:
        report["resumed"] = facts
        report["queue_before_release"] = queue.snapshot()
        queue.release.set()
        cdp.evaluate(_wait(
            f"facts.titles.length === 3 && facts.titles.every((title) => title === {json.dumps(_COMPLETED_TITLE)})"
            " && !facts.pauseEnabled && !facts.resumeEnabled"),
            checked("completed", completed), "completed")

    def completed(facts: dict[str, object]) -> None:
        report["completed"] = facts
        report["queue"] = queue.snapshot()
        recorder.complete(report)

    cdp.evaluate(_wait("facts.titles.length === 3 && facts.pauseEnabled && !facts.resumeEnabled"),
                 checked("queued", queued), "queued")


def _write_timeout(screenshot: Path, step: str, value: object, queue: dict[str, object]) -> None:
    facts = value.get("facts") if type(value) is dict else None
    screenshot.with_name("rail-bulk-timeout.json").write_text(
        json.dumps({"step": step, "facts": facts, "controls": queue["controls"],
                    "scanner_calls": queue["scanner_calls"]}, sort_keys=True), encoding="utf-8",
    )


def _runtime_identity() -> dict[str, object]:
    import namisync
    return {"executable": str(Path(sys.executable).resolve()),
            "namisync_file": str(Path(namisync.__file__).resolve()),
            "versions": {name: importlib.metadata.version(name)
                         for name in ("namisync", "pywebview", "pythonnet")}}


def _run(arguments: argparse.Namespace, recorder: _Recorder) -> int:
    from namisync.interfaces.web import host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    queue = _Queue(arguments.source)
    retained: list[object] = []
    original = host._configure_window_appearance

    def extension(_document: object, registry: object) -> dict[str, object]:
        queue.bind(registry)
        return {}

    def configure(window: object, *args: object, **kwargs: object) -> object:
        controller = original(window, *args, **kwargs)
        on_background_page_loaded(
            window, retained,
            lambda: _drive(window, queue, recorder, retained, arguments.screenshot),
            lambda error: recorder.fail("startup", type(error).__name__))
        return controller

    try:
        with ExitStack() as stack:
            stack.enter_context(headed_command_extension(host, extension))
            stack.enter_context(patch.object(host, "_configure_window_appearance", configure))
            code = host.run_desktop(
                AppPaths.from_root(arguments.data_dir),
                DesktopInstanceIdentity(arguments.mutex, arguments.title),
                startup_error=lambda _message: recorder.fail("startup", "DesktopStartupError"),
            )
    finally:
        queue.release.set()
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
