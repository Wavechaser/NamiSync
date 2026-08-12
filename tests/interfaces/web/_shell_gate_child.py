"""Installed-wheel child process for the Slice 4 SH-G-7 shell gate."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.metadata
import importlib.resources
import json
import os
import sys
import threading
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch


_HOSTILE = "wave \U0001f30a e\u0301 <img onerror=alert(1)> & \u6d77"
_LONG = ("\u6ce2" * 600) + " end"
_COMPLETE_TEXT = "Shell gate complete"
_ASSETS = (
    "app.css",
    "app.js",
    "components.css",
    "index.html",
    "panels.js",
    "rail.js",
    "render.js",
    "tokens.css",
    "tree.js",
)

_INITIAL_PROBE = r"""
(async () => {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (document.querySelector("#host-status")?.textContent === "Ready") {
      break;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 50));
  }
  const app = document.querySelector("#app");
  const status = document.querySelector("#host-status");
  const rail = document.querySelector(".nami-task-rail");
  const work = document.querySelector(".nami-work-panel");
  if (!(app instanceof HTMLElement) || !(status instanceof HTMLElement) ||
      !(rail instanceof HTMLElement) || !(work instanceof HTMLElement)) {
    throw new Error("production shell is unavailable");
  }
  if (status.textContent !== "Ready") {
    throw new Error("production bridge readiness is unavailable");
  }
  const railRect = rail.getBoundingClientRect();
  const workRect = work.getBoundingClientRect();
  if (document.activeElement instanceof HTMLElement) {
    document.activeElement.blur();
  }
  return {
    status: status.textContent,
    app_live: app.getAttribute("aria-live"),
    status_role: status.getAttribute("role"),
    status_live: status.getAttribute("aria-live"),
    rail_label: rail.getAttribute("aria-label"),
    rail_heading: rail.querySelector("h2")?.textContent,
    rail_empty: rail.querySelector(".nami-shell__empty")?.textContent,
    work_label: work.getAttribute("aria-label"),
    work_heading: work.querySelector("h2")?.textContent,
    work_empty: work.querySelector(".nami-shell__empty")?.textContent,
    work_guidance: work.querySelector(".nami-shell__guidance")?.textContent,
    initial_tree_rows: document.querySelectorAll(".nami-tree-row").length,
    initial_task_ids: document.querySelectorAll("[data-task-id]").length,
    initial_session_ids: document.querySelectorAll("[data-session-id]").length,
    active_tag: document.activeElement?.tagName ?? null,
    layout: {
      rail_left: railRect.left,
      rail_right: railRect.right,
      rail_top: railRect.top,
      rail_bottom: railRect.bottom,
      work_left: workRect.left,
      work_right: workRect.right,
      work_top: workRect.top,
      work_bottom: workRect.bottom,
    },
  };
})()
"""

_ACTIVE_PROBE = r"""
(() => ({
  label: document.activeElement?.getAttribute("aria-label") ?? null,
  tag: document.activeElement?.tagName ?? null,
}))()
"""

_FINAL_PROBE = r"""
(async () => {
  await new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const status = document.querySelector("#host-status");
  const rail = document.querySelector(".nami-task-rail");
  const work = document.querySelector(".nami-work-panel");
  if (!(status instanceof HTMLElement) || !(rail instanceof HTMLElement) ||
      !(work instanceof HTMLElement)) {
    throw new Error("production shell disappeared");
  }
  const focusedBeforeTree = document.activeElement?.getAttribute("aria-label");
  const railRect = rail.getBoundingClientRect();
  const workRect = work.getBoundingClientRect();
  const focusStyle = getComputedStyle(work);
  const treeModule = await import("/tree.js");
  const renderModule = await import("/render.js");
  const treeRoot = document.createElement("div");
  treeRoot.ariaLabel = "Presentation tree evidence";
  work.append(treeRoot);
  const controller = treeModule.createTree(treeRoot);
  const hostile = __HOSTILE__;
  const longValue = __LONG__;
  const staleOne = controller.beginWindowRequest();
  const currentOne = controller.beginWindowRequest();
  let staleReads = 0;
  const unreadable = new Proxy({}, {
    get() {
      staleReads += 1;
      throw new Error("stale window was read");
    },
  });
  const firstStaleResult = controller.commitWindow(staleOne, unreadable);
  controller.commitWindow(currentOne, {
    offset: 5,
    total: 10,
    rows: [
      {
        node_id: "node-hostile",
        display: hostile,
        depth: 0,
        is_container: true,
        expanded: false,
      },
      {
        node_id: "node-long",
        display: longValue,
        depth: 1,
        is_container: false,
        expanded: false,
      },
    ],
  });
  const labels = [...treeRoot.querySelectorAll(".nami-tree-row__label")];
  const textEvidence = {
    hostile_exact: labels[0]?.textContent === hostile,
    hostile_bytes: new TextEncoder().encode(labels[0]?.textContent ?? "").length,
    hostile_sha256: await sha256(labels[0]?.textContent ?? ""),
    long_exact: labels[1]?.textContent === longValue,
    long_bytes: new TextEncoder().encode(labels[1]?.textContent ?? "").length,
    long_sha256: await sha256(labels[1]?.textContent ?? ""),
  };
  const currentTwo = controller.beginWindowRequest();
  const rows = Array.from({length: 256}, (_, index) => ({
    node_id: `node-${index}`,
    display: index === 255 ? longValue : `Row ${index}`,
    depth: index === 0 ? 0 : 1,
    is_container: index === 0,
    expanded: index === 0,
  }));
  controller.commitWindow(currentTwo, {offset: 0, total: 256, rows});
  const fingerprint = JSON.stringify(treeFingerprint(treeRoot));
  const secondStaleResult = controller.commitWindow(currentOne, unreadable);
  const stale_unchanged =
    fingerprint === JSON.stringify(treeFingerprint(treeRoot));
  const renderedRows = [...treeRoot.querySelectorAll(".nami-tree-row")];
  const spacers = [...treeRoot.querySelectorAll(".nami-tree__spacer")];
  renderModule.renderText(status, __COMPLETE_TEXT__);
  return {
    focused_before_tree: focusedBeforeTree,
    zoom: {
      stacked: railRect.bottom <= workRect.top,
      cards_positive: railRect.width > 0 && railRect.height > 0 &&
        workRect.width > 0 && workRect.height > 0,
      cards_in_viewport: railRect.left >= 0 && workRect.left >= 0 &&
        railRect.right <= innerWidth + 1 && workRect.right <= innerWidth + 1,
      no_horizontal_overflow:
        document.documentElement.scrollWidth <=
          document.documentElement.clientWidth + 1,
      focused_visible: workRect.top < innerHeight && workRect.bottom > 0,
    },
    forced: {
      active: matchMedia("(forced-colors: active)").matches,
      focus_token: getComputedStyle(document.documentElement)
        .getPropertyValue("--color-focus-ring").trim(),
      outline_style: focusStyle.outlineStyle,
      outline_width: focusStyle.outlineWidth,
    },
    tree: {
      row_h: treeModule.ROW_H,
      role: treeRoot.getAttribute("role"),
      row_count: renderedRows.length,
      spacer_count: spacers.length,
      child_count: treeRoot.children.length,
      every_row_28: renderedRows.every(
        (row) => Math.abs(row.getBoundingClientRect().height - 28) < 0.01),
      first_level: renderedRows[0]?.getAttribute("aria-level"),
      first_expanded: renderedRows[0]?.getAttribute("aria-expanded"),
      leaf_expanded: renderedRows[1]?.hasAttribute("aria-expanded"),
      stale_reads: staleReads,
      stale_results: [firstStaleResult, secondStaleResult],
      stale_unchanged,
      text: textEvidence,
    },
    complete_text: status.textContent,
  };

  async function sha256(value) {
    const digest = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(value),
    );
    return [...new Uint8Array(digest)]
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
  }

  function treeFingerprint(root) {
    return [...root.children].map((child) => ({
      class_name: child.className,
      node_id: child.dataset.nodeId ?? null,
      text: child.textContent,
      block_size: child.style.blockSize,
    }));
  }
})()
"""


class _Recorder:
    def __init__(self, output: Path) -> None:
        self._output = output
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {
            "schema_version": 1,
            "phase": "starting",
            "startup_errors": [],
        }

    def set(self, name: str, value: Any) -> None:
        with self._lock:
            self._data[name] = value

    def startup_error(self, message: str) -> None:
        del message
        self.set("startup_errors", [{"type": "DesktopStartupError"}])

    def failure(self, stage: str, error: BaseException) -> None:
        if stage not in {"page_probe", "child"}:
            stage = "child"
        with self._lock:
            if self._data.get("phase") == "complete":
                return
            self._data["phase"] = "failure"
            self._data["failure"] = {
                "stage": stage,
                "type": _error_type(error),
            }
            self._write_locked()

    def complete(self, page: dict[str, object]) -> None:
        with self._lock:
            self._data["page"] = page
            self._data["phase"] = "complete"
            self._write_locked()

    def write(self) -> None:
        with self._lock:
            self._write_locked()

    def _write_locked(self) -> None:
        self._output.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._output.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._data, ensure_ascii=True, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, self._output)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


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


def _installed_assets() -> dict[str, dict[str, object]]:
    root = importlib.resources.files("namisync.interfaces.web") / "assets"
    result: dict[str, dict[str, object]] = {}
    for name in _ASSETS:
        path = Path(str(root / name)).resolve()
        content = path.read_bytes()
        result[name] = {
            "path": str(path),
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    return result


def _window_style(native_window: object) -> dict[str, object]:
    handle = native_window.Handle
    hwnd = int(handle.ToInt64() if hasattr(handle, "ToInt64") else handle)
    getter = ctypes.windll.user32.GetWindowLongPtrW
    getter.argtypes = (ctypes.c_void_p, ctypes.c_int)
    getter.restype = ctypes.c_ssize_t
    style = int(getter(hwnd, -16)) & 0xFFFFFFFF
    return {
        "caption": style & 0x00C00000 == 0x00C00000,
        "thickframe": bool(style & 0x00040000),
        "sysmenu": bool(style & 0x00080000),
    }


def _runtime_value(task: object) -> dict[str, object]:
    if task.IsFaulted or task.IsCanceled:
        raise RuntimeError("native CDP task failed")
    envelope = json.loads(str(task.Result))
    if type(envelope) is not dict or "exceptionDetails" in envelope:
        raise RuntimeError("native CDP expression failed")
    remote = envelope.get("result")
    value = remote.get("value") if type(remote) is dict else None
    if type(value) is not dict:
        raise TypeError("native CDP result is invalid")
    return value


def _begin_probe(
    window: object,
    recorder: _Recorder,
    retained: list[object],
) -> None:
    from System import Action

    native = window.native
    if native.InvokeRequired:
        raise RuntimeError("shell probe left the UI thread")
    core = native.browser.webview.CoreWebView2
    page: dict[str, object] = {}

    def on_ui(callback: Callable[[], None]) -> None:
        action = Action(callback)
        retained.append(action)
        native.BeginInvoke(action)

    def protocol(
        method: str,
        parameters: dict[str, object],
        callback: Callable[[object], None],
        *,
        runtime: bool = False,
    ) -> None:
        task = core.CallDevToolsProtocolMethodAsync(
            method,
            json.dumps(parameters, separators=(",", ":")),
        )

        def completed() -> None:
            def finish() -> None:
                try:
                    if runtime:
                        value: object = _runtime_value(task)
                    else:
                        if task.IsFaulted or task.IsCanceled:
                            raise RuntimeError("native CDP task failed")
                        value = json.loads(str(task.Result))
                    callback(value)
                except BaseException as error:
                    recorder.failure("page_probe", error)

            on_ui(finish)

        completion = Action(completed)
        retained.append(completion)
        task.GetAwaiter().OnCompleted(completion)

    def evaluate(expression: str, callback: Callable[[object], None]) -> None:
        protocol(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
            callback,
            runtime=True,
        )

    def key(event_type: str, callback: Callable[[object], None]) -> None:
        protocol(
            "Input.dispatchKeyEvent",
            {
                "type": event_type,
                "key": "Tab",
                "code": "Tab",
                "windowsVirtualKeyCode": 9,
                "nativeVirtualKeyCode": 9,
            },
            callback,
        )

    def after_initial(value: object) -> None:
        page["initial"] = value
        key("rawKeyDown", lambda _value: key("keyUp", after_first_tab))

    def after_first_tab(_value: object) -> None:
        evaluate(_ACTIVE_PROBE, after_first_focus)

    def after_first_focus(value: object) -> None:
        page["first_focus"] = value
        key("rawKeyDown", lambda _value: key("keyUp", after_second_tab))

    def after_second_tab(_value: object) -> None:
        evaluate(_ACTIVE_PROBE, after_second_focus)

    def after_second_focus(value: object) -> None:
        page["second_focus"] = value
        native.browser.webview.ZoomFactor = 2.0
        page["controller_zoom"] = float(native.browser.webview.ZoomFactor)
        protocol(
            "Emulation.setEmulatedMedia",
            {
                "media": "screen",
                "features": [
                    {"name": "forced-colors", "value": "active"},
                    {"name": "prefers-color-scheme", "value": "light"},
                ],
            },
            after_media,
        )

    def after_media(_value: object) -> None:
        expression = (
            _FINAL_PROBE.replace("__HOSTILE__", json.dumps(_HOSTILE))
            .replace("__LONG__", json.dumps(_LONG))
            .replace("__COMPLETE_TEXT__", json.dumps(_COMPLETE_TEXT))
        )
        evaluate(expression, after_final)

    def after_final(value: object) -> None:
        page["final"] = value
        page["native"] = {
            "ui_thread": not bool(native.InvokeRequired),
            "window_style": _window_style(native),
        }
        recorder.complete(page)

    evaluate(_INITIAL_PROBE, after_initial)


def _configure_probe(
    window: object,
    recorder: _Recorder,
    retained: list[object],
    original: Callable[..., object],
) -> object:
    controller = original(window)

    def loaded() -> None:
        from System import Action

        native = window.native

        def begin() -> None:
            try:
                _begin_probe(window, recorder, retained)
            except BaseException as error:
                recorder.failure("page_probe", error)

        action = Action(begin)
        retained.append(action)
        native.BeginInvoke(action)

    retained.append(loaded)
    window.events.loaded += loaded
    return controller


def _run(arguments: argparse.Namespace, recorder: _Recorder) -> int:
    from namisync.interfaces.web import host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    recorder.set("runtime", _runtime_identity())
    recorder.set("installed_assets", _installed_assets())
    retained: list[object] = []
    original = host._configure_window_appearance
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                host,
                "_configure_window_appearance",
                lambda window: _configure_probe(
                    window,
                    recorder,
                    retained,
                    original,
                ),
            )
        )
        exit_code = host.run_desktop(
            AppPaths.from_root(arguments.data_dir),
            DesktopInstanceIdentity(arguments.mutex, arguments.title),
            startup_error=recorder.startup_error,
        )
    del retained
    recorder.set("exit_code", exit_code)
    recorder.write()
    return exit_code


def _error_type(error: BaseException) -> str:
    name = type(error).__name__
    if name in {
        "AttributeError",
        "RuntimeError",
        "TypeError",
        "ValueError",
    }:
        return name
    return "Error"


def main() -> int:
    arguments = _parse_arguments()
    recorder = _Recorder(arguments.output)
    try:
        return _run(arguments, recorder)
    except BaseException as error:
        recorder.failure("child", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
