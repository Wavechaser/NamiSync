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


_LAYOUT_CODE_POINTS = (
    *range(0x0000, 0x0020),
    *range(0x007F, 0x00A0),
    0x00AD,
    0x061C,
    0x200B,
    0x200E,
    0x200F,
    *range(0x2028, 0x202F),
    *range(0x2060, 0x2070),
    0xFEFF,
    0x27E6,
    0x27E7,
)
_ACTIVE_LAYOUT_CODE_POINTS = frozenset(_LAYOUT_CODE_POINTS) - {
    0x27E6,
    0x27E7,
}
_LAYOUT_SOURCE = (
    "layout-" + "".join(chr(value) for value in _LAYOUT_CODE_POINTS) + "-end"
)
_LAYOUT_RENDERED = (
    "layout-"
    + "".join(f"⟦U+{value:04X}⟧" for value in _LAYOUT_CODE_POINTS)
    + "-end"
)
_HOSTILE = (
    "wave \U0001f30a\ufe0f e\u0301 <img onerror=alert(1)> "
    "العربية עברית A\u200cB\u200dC \U000e0020 & \u6d77"
)
_LONG = ("\u6ce2" * 600) + " end"
_RAW_NODE_ID = "node-\u202e-⟦U+202E⟧"
_COMPLETE_TEXT = "Shell gate complete"
_ASSETS = (
    "app.css",
    "app.js",
    "appearance.js",
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

_KEYBOARD_TREE_PROBE = r"""
(async () => {
  const work = document.querySelector(".nami-work-panel");
  if (!(work instanceof HTMLElement)) {
    throw new Error("production work panel is unavailable");
  }
  const {ROW_H, createTree} = await import("/tree.js");
  const root = document.createElement("div");
  root.ariaLabel = "Keyboard tree evidence";
  root.style.boxSizing = "content-box";
  root.style.blockSize = `${ROW_H}px`;
  work.append(root);
  const interactions = {toggles: [], activations: []};
  globalThis.__namiShellTreeEvidence = {root, interactions};
  const controller = createTree(root, {
    toggle: (...value) => interactions.toggles.push(value),
    activate: (nodeId) => interactions.activations.push(nodeId),
  });
  const generation = controller.beginWindowRequest();
  controller.commitWindow(generation, {
    offset: 0,
    total: 3,
    rows: [
      {
        node_id: "keyboard-root",
        display: "Keyboard root",
        depth: 0,
        is_container: true,
        visible_index: 0,
        parent_visible_index: null,
        first_child_visible_index: 1,
        position_in_set: 1,
        set_size: 1,
        expanded: true,
      },
      {
        node_id: "keyboard-child",
        display: "Keyboard child",
        depth: 1,
        is_container: true,
        visible_index: 1,
        parent_visible_index: 0,
        first_child_visible_index: null,
        position_in_set: 1,
        set_size: 2,
        expanded: false,
      },
      {
        node_id: "keyboard-sibling",
        display: "Keyboard sibling",
        depth: 1,
        is_container: false,
        visible_index: 2,
        parent_visible_index: 0,
        first_child_visible_index: null,
        position_in_set: 2,
        set_size: 2,
        expanded: null,
      },
    ],
  });
  const activeDescendant = root.getAttribute("aria-activedescendant");
  return {
    row_count: root.querySelectorAll(".nami-tree-row").length,
    tab_index: root.tabIndex,
    client_height: root.clientHeight,
    row_h: ROW_H,
    active_node: document.getElementById(activeDescendant)
      ?.dataset.nodeId ?? null,
  };
})()
"""

_ACTIVE_PROBE = r"""
(() => {
  const active = document.activeElement;
  const descendant = active?.getAttribute("aria-activedescendant");
  const activeRow = descendant === null || descendant === undefined
    ? null
    : document.getElementById(descendant);
  const rootRect = active?.getBoundingClientRect();
  const rowRect = activeRow?.getBoundingClientRect();
  return {
    label: active?.getAttribute("aria-label") ?? null,
    tag: active?.tagName ?? null,
    active_node: activeRow?.dataset.nodeId ?? null,
    scroll_top: active?.scrollTop ?? null,
    client_height: active?.clientHeight ?? null,
    fully_visible: rootRect !== undefined && rowRect !== undefined &&
      rowRect.top >= rootRect.top - 0.01 &&
      rowRect.bottom <= rootRect.bottom + 0.01,
  };
})()
"""

_POINTER_TARGET_PROBE = r"""
(() => {
  const state = globalThis.__namiShellTreeEvidence;
  const row = state?.root?.querySelector(
    '[data-node-id="keyboard-child"]',
  );
  const disclosure = row?.querySelector(".nami-tree-row__disclosure");
  const label = row?.querySelector(".nami-tree-row__label");
  if (!(disclosure instanceof HTMLElement) || !(label instanceof HTMLElement)) {
    throw new Error("keyboard tree pointer targets are unavailable");
  }
  return {disclosure: center(disclosure), label: center(label)};

  function center(element) {
    const rect = element.getBoundingClientRect();
    return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
  }
})()
"""

_INTERACTION_PROBE = r"""
(() => {
  const state = globalThis.__namiShellTreeEvidence;
  const descendant = state?.root?.getAttribute("aria-activedescendant");
  if (state === undefined) {
    throw new Error("keyboard tree interaction evidence is unavailable");
  }
  return {
    toggles: state.interactions.toggles,
    activations: state.interactions.activations,
    focus_is_tree: document.activeElement === state.root,
    active_node: document.getElementById(descendant)?.dataset.nodeId ?? null,
  };
})()
"""

_SCROLL_TREE_SETUP = r"""
(async () => {
  const work = document.querySelector(".nami-work-panel");
  if (!(work instanceof HTMLElement)) {
    throw new Error("production work panel is unavailable");
  }
  const {ROW_H, createTree} = await import("/tree.js");
  const root = document.createElement("div");
  root.ariaLabel = "Scroll paging evidence";
  root.style.boxSizing = "content-box";
  root.style.blockSize = `${4 * ROW_H}px`;
  work.append(root);
  const total = 300;
  const state = {
    activations: [],
    commits: [],
    currentOffset: 0,
    previousFocus: document.activeElement,
    requests: [],
    root,
  };
  let controller;
  controller = createTree(root, {
    activate: (nodeId) => state.activations.push(nodeId),
    requestIndex: (index, generation) => {
      state.requests.push({index, generation});
      const offset = Math.min(Math.floor(index / 4) * 4, total - 5);
      const accepted = controller.commitWindow(generation, {
        offset,
        total,
        rows: rows(offset),
      });
      if (accepted) {
        state.currentOffset = offset;
      }
      state.commits.push({accepted, generation, offset});
    },
  });
  const generation = controller.beginWindowRequest();
  const accepted = controller.commitWindow(generation, {
    offset: 0,
    total,
    rows: rows(0),
  });
  root.focus();
  state.initial = {
    accepted,
    client_height: root.clientHeight,
    generation,
    row_count: root.querySelectorAll(".nami-tree-row").length,
    row_h: ROW_H,
    total,
  };
  globalThis.__namiScrollTreeEvidence = state;
  await new Promise((resolve) => requestAnimationFrame(resolve));
  const rect = root.getBoundingClientRect();
  return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};

  function rows(offset) {
    return Array.from({length: 5}, (_, relativeIndex) => {
      const visibleIndex = offset + relativeIndex;
      return {
        node_id: `scroll-${visibleIndex}`,
        display: `Scroll ${visibleIndex}`,
        depth: 0,
        is_container: false,
        visible_index: visibleIndex,
        parent_visible_index: null,
        first_child_visible_index: null,
        position_in_set: visibleIndex + 1,
        set_size: total,
        expanded: null,
      };
    });
  }
})()
"""

_SCROLL_TREE_EVIDENCE = r"""
(async () => {
  await new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const state = globalThis.__namiScrollTreeEvidence;
  if (state === undefined) {
    throw new Error("scroll paging evidence is unavailable");
  }
  const root = state.root;
  const rootRect = root.getBoundingClientRect();
  const viewportTop = rootRect.top + root.clientTop;
  const viewportBottom = viewportTop + root.clientHeight;
  const rendered = [...root.querySelectorAll(".nami-tree-row")];
  const rects = rendered.map((row) => row.getBoundingClientRect());
  const descendant = root.getAttribute("aria-activedescendant");
  const active = descendant === null ? null : document.getElementById(descendant);
  const activeRect = active?.getBoundingClientRect();
  const result = {
    active_node: active?.dataset.nodeId ?? null,
    activations: state.activations,
    commits: state.commits,
    fully_visible_active: activeRect !== undefined &&
      activeRect.top >= viewportTop - 0.01 &&
      activeRect.bottom <= viewportBottom + 0.01,
    focus_is_tree: document.activeElement === root,
    initial: state.initial,
    nonblank_viewport: rects.length > 0 &&
      Math.min(...rects.map((rect) => rect.top)) <= viewportTop + 0.01 &&
      Math.max(...rects.map((rect) => rect.bottom)) >= viewportBottom - 0.01,
    rendered_indices: rendered.map((row) =>
      Number(row.id.slice(row.id.lastIndexOf("-") + 1))),
    requests: state.requests,
    row_count: rendered.length,
    scroll_top: root.scrollTop,
  };
  state.previousFocus?.focus();
  root.remove();
  delete globalThis.__namiScrollTreeEvidence;
  return result;
})()
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
  const focused = document.activeElement;
  if (!(focused instanceof HTMLElement)) {
    throw new Error("keyboard tree focus disappeared");
  }
  const railRect = rail.getBoundingClientRect();
  const workRect = work.getBoundingClientRect();
  const focusedRect = focused.getBoundingClientRect();
  const focusStyle = getComputedStyle(focused);
  const treeModule = await import("/tree.js");
  const renderModule = await import("/render.js");
  const treeRoot = document.createElement("div");
  treeRoot.ariaLabel = "Presentation tree evidence";
  work.append(treeRoot);
  const interactions = {toggles: [], activations: []};
  const controller = treeModule.createTree(treeRoot, {
    toggle: (...value) => interactions.toggles.push(value),
    activate: (nodeId) => interactions.activations.push(nodeId),
  });
  const layoutSource = __LAYOUT_SOURCE__;
  const layoutRendered = __LAYOUT_RENDERED__;
  const hostile = __HOSTILE__;
  const longValue = __LONG__;
  const rawNodeId = __RAW_NODE_ID__;
  const activeLayoutControlPattern =
    /[\u0000-\u001f\u007f-\u009f\u00ad\u061c\u200b\u200e-\u200f\u2028-\u202e\u2060-\u206f\ufeff]/u;
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
        node_id: rawNodeId,
        display: layoutSource,
        depth: 1,
        is_container: true,
        visible_index: 5,
        parent_visible_index: 0,
        first_child_visible_index: 6,
        position_in_set: 1,
        set_size: 1,
        expanded: true,
      },
      {
        node_id: "node-hostile",
        display: hostile,
        depth: 2,
        is_container: false,
        visible_index: 6,
        parent_visible_index: 5,
        first_child_visible_index: null,
        position_in_set: 1,
        set_size: 2,
        expanded: null,
      },
      {
        node_id: "node-long",
        display: longValue,
        depth: 2,
        is_container: false,
        visible_index: 7,
        parent_visible_index: 5,
        first_child_visible_index: null,
        position_in_set: 2,
        set_size: 2,
        expanded: null,
      },
    ],
  });
  const labels = [...treeRoot.querySelectorAll(".nami-tree-row__label")];
  const firstRow = treeRoot.querySelector(".nami-tree-row");
  firstRow?.querySelector(".nami-tree-row__disclosure")?.click();
  firstRow?.querySelector(".nami-tree-row__label")?.click();
  focused.focus();
  const textEvidence = {
    layout_exact: labels[0]?.textContent === layoutRendered,
    layout_controls_absent: labels.every((label) =>
      !activeLayoutControlPattern.test(label.textContent ?? "")),
    layout_bytes: new TextEncoder().encode(labels[0]?.textContent ?? "").length,
    layout_sha256: await sha256(labels[0]?.textContent ?? ""),
    hostile_exact: labels[1]?.textContent === hostile,
    hostile_bytes: new TextEncoder().encode(labels[1]?.textContent ?? "").length,
    hostile_sha256: await sha256(labels[1]?.textContent ?? ""),
    long_exact: labels[2]?.textContent === longValue,
    long_bytes: new TextEncoder().encode(labels[2]?.textContent ?? "").length,
    long_sha256: await sha256(labels[2]?.textContent ?? ""),
    callback_ids: {
      toggles: interactions.toggles,
      activations: interactions.activations,
      dataset_node_id: firstRow?.dataset.nodeId ?? null,
    },
  };
  const currentTwo = controller.beginWindowRequest();
  const rows = Array.from({length: 256}, (_, index) => ({
    node_id: index === 1 ? rawNodeId : `node-${index}`,
    display: index === 1
      ? layoutSource
      : index === 2
        ? hostile
        : index === 255
          ? longValue
          : `Row ${index}`,
    depth: index === 0 ? 0 : 1,
    is_container: index === 0,
    visible_index: index,
    parent_visible_index: index === 0 ? null : 0,
    first_child_visible_index: index === 0 ? 1 : null,
    position_in_set: index === 0 ? 1 : index,
    set_size: index === 0 ? 1 : 255,
    expanded: index === 0 ? true : null,
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
      focused_visible:
        focusedRect.top < innerHeight && focusedRect.bottom > 0,
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


def _accessibility_evidence(value: object) -> dict[str, object]:
    if type(value) is not dict or type(value.get("nodes")) is not list:
        raise TypeError("accessibility tree result is invalid")
    nodes = value["nodes"]

    def field(node: object, name: str) -> object:
        if type(node) is not dict:
            return None
        candidate = node.get(name)
        return candidate.get("value") if type(candidate) is dict else None

    trees = [node for node in nodes if field(node, "role") == "tree"]
    items = [node for node in nodes if field(node, "role") == "treeitem"]
    tree_names = {field(node, "name") for node in trees}
    item_name_values = tuple(field(node, "name") for node in items)
    item_names = set(item_name_values)
    keyboard = next(
        (
            node
            for node in trees
            if field(node, "name") == "Keyboard tree evidence"
        ),
        None,
    )
    properties = keyboard.get("properties") if type(keyboard) is dict else None
    active = next(
        (
            prop
            for prop in properties or []
            if type(prop) is dict and prop.get("name") == "activedescendant"
        ),
        None,
    )
    active_value = active.get("value") if type(active) is dict else None
    related = (
        active_value.get("relatedNodes")
        if type(active_value) is dict
        else None
    )
    evidence = {
        "tree_count": len(trees),
        "treeitem_count": len(items),
        "keyboard_tree_named": "Keyboard tree evidence" in tree_names,
        "presentation_tree_named": "Presentation tree evidence" in tree_names,
        "layout_label_exact": _LAYOUT_RENDERED in item_names,
        "layout_controls_absent": bool(items) and all(
            type(name) is str
            and all(
                ord(character) not in _ACTIVE_LAYOUT_CODE_POINTS
                for character in name
            )
            for name in item_name_values
        ),
        "hostile_label_exact": _HOSTILE in item_names,
        "long_label_exact": _LONG in item_names,
        "active_descendant_exposed": type(related) is list and bool(related),
    }
    return evidence


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

    def key(
        event_type: str,
        name: str,
        code: str,
        virtual_key: int,
        callback: Callable[[object], None],
    ) -> None:
        protocol(
            "Input.dispatchKeyEvent",
            {
                "type": event_type,
                "key": name,
                "code": code,
                "windowsVirtualKeyCode": virtual_key,
                "nativeVirtualKeyCode": virtual_key,
            },
            callback,
        )

    def press(
        name: str,
        code: str,
        virtual_key: int,
        callback: Callable[[object], None],
    ) -> None:
        key(
            "rawKeyDown",
            name,
            code,
            virtual_key,
            lambda _value: key(
                "keyUp",
                name,
                code,
                virtual_key,
                callback,
            ),
        )

    def click(
        point: object,
        callback: Callable[[object], None],
    ) -> None:
        if type(point) is not dict:
            raise TypeError("pointer target is invalid")
        x = point.get("x")
        y = point.get("y")
        if type(x) not in {int, float} or type(y) not in {int, float}:
            raise TypeError("pointer coordinates are invalid")

        def mouse(
            event_type: str,
            buttons: int,
            complete: Callable[[object], None],
        ) -> None:
            protocol(
                "Input.dispatchMouseEvent",
                {
                    "type": event_type,
                    "x": x,
                    "y": y,
                    "button": "left",
                    "buttons": buttons,
                    "clickCount": 1,
                },
                complete,
            )

        mouse(
            "mousePressed",
            1,
            lambda _value: mouse("mouseReleased", 0, callback),
        )

    def wheel(
        point: object,
        delta_y: float,
        callback: Callable[[object], None],
    ) -> None:
        if type(point) is not dict:
            raise TypeError("wheel target is invalid")
        x = point.get("x")
        y = point.get("y")
        if type(x) not in {int, float} or type(y) not in {int, float}:
            raise TypeError("wheel coordinates are invalid")
        protocol(
            "Input.dispatchMouseEvent",
            {
                "type": "mouseWheel",
                "x": x,
                "y": y,
                "deltaX": 0,
                "deltaY": delta_y,
            },
            callback,
        )

    def after_initial(value: object) -> None:
        page["initial"] = value
        evaluate(_KEYBOARD_TREE_PROBE, after_keyboard_tree)

    def after_keyboard_tree(value: object) -> None:
        page["keyboard_tree"] = value
        press("Tab", "Tab", 9, after_first_tab)

    def after_first_tab(_value: object) -> None:
        evaluate(_ACTIVE_PROBE, after_first_focus)

    def after_first_focus(value: object) -> None:
        page["first_focus"] = value
        press("ArrowDown", "ArrowDown", 40, after_second_key)

    def after_second_key(_value: object) -> None:
        evaluate(_ACTIVE_PROBE, after_second_focus)

    def after_second_focus(value: object) -> None:
        page["second_focus"] = value
        evaluate(_POINTER_TARGET_PROBE, after_pointer_targets)

    def after_pointer_targets(value: object) -> None:
        if type(value) is not dict:
            raise TypeError("pointer targets are invalid")
        click(value.get("disclosure"), after_disclosure_pointer)

    def after_disclosure_pointer(_value: object) -> None:
        evaluate(_INTERACTION_PROBE, after_disclosure_evidence)

    def after_disclosure_evidence(value: object) -> None:
        page["disclosure_click"] = value
        evaluate(_POINTER_TARGET_PROBE, after_disclosure_targets)

    def after_disclosure_targets(value: object) -> None:
        if type(value) is not dict:
            raise TypeError("pointer targets are invalid")
        click(value.get("label"), after_label_pointer)

    def after_label_pointer(_value: object) -> None:
        evaluate(_INTERACTION_PROBE, after_label_evidence)

    def after_label_evidence(value: object) -> None:
        page["label_click"] = value
        evaluate(_SCROLL_TREE_SETUP, after_scroll_setup)

    def after_scroll_setup(value: object) -> None:
        wheel(value, 112, after_scroll_wheel)

    def after_scroll_wheel(_value: object) -> None:
        evaluate(_SCROLL_TREE_EVIDENCE, after_scroll_evidence)

    def after_scroll_evidence(value: object) -> None:
        page["scroll_tree"] = value
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
            _FINAL_PROBE.replace(
                "__LAYOUT_SOURCE__", json.dumps(_LAYOUT_SOURCE)
            )
            .replace("__LAYOUT_RENDERED__", json.dumps(_LAYOUT_RENDERED))
            .replace("__RAW_NODE_ID__", json.dumps(_RAW_NODE_ID))
            .replace("__HOSTILE__", json.dumps(_HOSTILE))
            .replace("__LONG__", json.dumps(_LONG))
            .replace("__COMPLETE_TEXT__", json.dumps(_COMPLETE_TEXT))
        )
        evaluate(expression, after_final)

    def after_final(value: object) -> None:
        page["final"] = value
        protocol(
            "Accessibility.enable",
            {},
            lambda _value: protocol(
                "Accessibility.getFullAXTree",
                {},
                after_accessibility,
            ),
        )

    def after_accessibility(value: object) -> None:
        page["accessibility"] = _accessibility_evidence(value)
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
