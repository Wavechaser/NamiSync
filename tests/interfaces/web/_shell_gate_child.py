"""Installed-wheel child process for the Slice 4 SH-G-7 shell gate."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.metadata
import importlib.resources
import json
import sys
import threading
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

from _headed_evidence import EvidencePaths, EvidencePublisher


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
_FAILURE_STAGES = frozenset({"page_probe", "child"})
_FAILURE_TYPES = frozenset(
    {"AttributeError", "RuntimeError", "TypeError", "ValueError", "Error"}
)
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
_COMPLETE_TEXT = "Shell gate complete"
_TREE_FIXTURE_SCHEMA = "namisync-tree-window-fixture-v1"
_TREE_FIXTURE_VIEWS = {
    "head",
    "next",
    "tail",
    "empty",
    "maximum",
    "pointer_expanded",
    "pointer_collapsed",
    "projected_empty",
    "layout_control",
}
_ASSETS = (
    "app.css",
    "app.js",
    "appearance.js",
    "components.css",
    "index.html",
    "panels.js",
    "rail.js",
    "readiness.js",
    "render.js",
    "tokens.css",
    "theme.js",
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
    work_heading: work.querySelector("h2")?.textContent ?? null,
    work_empty: work.querySelector(".nami-shell__empty")?.textContent,
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

_THEME_FOCUS_PROBE = r"""
(() => {
  const selector = document.querySelector("#theme-mode");
  const trigger = selector?.querySelector(".nami-combobox__trigger");
  const popupId = trigger?.getAttribute("aria-controls");
  const popup = popupId === null || popupId === undefined
    ? null
    : document.getElementById(popupId);
  const selected = popup?.querySelector('[role="option"][aria-selected="true"]');
  const labelId = trigger?.getAttribute("aria-labelledby")
    ?.split(/\s+/u)[0];
  const active = document.activeElement;
  const rect = trigger?.getBoundingClientRect();
  return {
    active: active === trigger,
    associated_label: labelId === undefined
      ? null
      : document.getElementById(labelId)?.textContent ?? null,
    disabled: trigger?.disabled ?? null,
    id: active?.id ?? null,
    tag: active?.tagName ?? null,
    role: trigger?.getAttribute("role") ?? null,
    expanded: trigger?.getAttribute("aria-expanded") ?? null,
    controls: popupId ?? null,
    popup_role: popup?.getAttribute("role") ?? null,
    selected_value: selected?.dataset.value ?? null,
    value: selector?.dataset.value ?? null,
    visible: rect !== undefined && rect.width > 0 && rect.height > 0 &&
      rect.top < innerHeight && rect.bottom > 0,
  };
})()
"""

_CREATE_FOCUS_PROBE = r"""
(() => {
  const create = document.querySelector(".nami-task-rail__header .nami-button");
  const active = document.activeElement;
  const rect = create?.getBoundingClientRect();
  return {
    active: active === create,
    disabled: create?.disabled ?? null,
    tag: active?.tagName ?? null,
    text: create?.getAttribute("aria-label") ?? null,
    visible: rect !== undefined && rect.width > 0 && rect.height > 0 &&
      rect.top < innerHeight && rect.bottom > 0,
  };
})()
"""

_KEYBOARD_TREE_PROBE = r"""
(async () => {
  const work = document.querySelector(".nami-work-panel");
  if (!(work instanceof HTMLElement)) {
    throw new Error("production work panel is unavailable");
  }
  const fixtureText = __TREE_FIXTURE_TEXT__;
  const fixture = JSON.parse(fixtureText);
  if (fixture.schema !== "namisync-tree-window-fixture-v1") {
    throw new Error("tree fixture schema is unavailable");
  }
  globalThis.__namiTreeFixtureEvidence = {fixture, fixtureText};
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
  controller.commitWindow(generation, fixture.views.pointer_collapsed);
  const activeDescendant = root.getAttribute("aria-activedescendant");
  return {
    row_count: root.querySelectorAll(".nami-tree-row").length,
    tab_index: root.tabIndex,
    client_height: root.clientHeight,
    row_h: ROW_H,
    fixture_schema: fixture.schema,
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
  const descendant = state?.root?.getAttribute("aria-activedescendant");
  const row = descendant === null || descendant === undefined
    ? null
    : document.getElementById(descendant);
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
  root.style.blockSize = `${2 * ROW_H}px`;
  work.append(root);
  const fixture = globalThis.__namiTreeFixtureEvidence?.fixture;
  if (fixture?.schema !== "namisync-tree-window-fixture-v1") {
    throw new Error("scroll tree fixture is unavailable");
  }
  const maximum = fixture.views.maximum;
  const total = maximum.total;
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
  state.controller = controller;
  const generation = controller.beginWindowRequest();
  const accepted = controller.commitWindow(generation, {
    offset: 0,
    total,
    rows: maximum.rows.slice(0, 2),
  });
  root.focus();
  state.initial = {
    accepted,
    client_height: root.clientHeight,
    generation,
    fixture_schema: fixture.schema,
    row_count: root.querySelectorAll(".nami-tree-row").length,
    row_h: ROW_H,
    total,
  };
  globalThis.__namiScrollTreeEvidence = state;
  await new Promise((resolve) => requestAnimationFrame(resolve));
  const scrollBeforeResize = root.scrollTop;
  root.style.blockSize = `${4 * ROW_H}px`;
  await new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const resizeRootRect = root.getBoundingClientRect();
  const resizeViewportTop = resizeRootRect.top + root.clientTop;
  const resizeViewportBottom = resizeViewportTop + root.clientHeight;
  const resizeRendered = [...root.querySelectorAll(".nami-tree-row")];
  const resizeRects = resizeRendered.map((row) => row.getBoundingClientRect());
  state.resize = {
    client_height: root.clientHeight,
    nonblank_viewport: resizeRects.length > 0 &&
      Math.min(...resizeRects.map((rect) => rect.top)) <=
        resizeViewportTop + 0.01 &&
      Math.max(...resizeRects.map((rect) => rect.bottom)) >=
        resizeViewportBottom - 0.01,
    rendered_indices: resizeRendered.map((row) =>
      Number(row.id.slice(row.id.lastIndexOf("-") + 1))),
    request: state.requests[0] ?? null,
    row_count: resizeRendered.length,
    scroll_top: root.scrollTop,
    scroll_unchanged: root.scrollTop === scrollBeforeResize,
  };
  const rect = root.getBoundingClientRect();
  return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};

  function rows(offset) {
    const result = maximum.rows.slice(offset, offset + 5);
    if (result.length !== 5) {
      throw new Error("scroll fixture window is unavailable");
    }
    return result;
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
    resize: state.resize,
    requests: state.requests,
    row_count: rendered.length,
    scroll_top: root.scrollTop,
  };
  const requestsBeforeDispose = state.requests.length;
  const commitsBeforeDispose = state.commits.length;
  root.style.blockSize = `${8 * state.initial.row_h}px`;
  root.dispatchEvent(new Event("scroll"));
  state.controller.dispose();
  state.controller.dispose();
  await new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve)));
  root.style.blockSize = `${9 * state.initial.row_h}px`;
  root.dispatchEvent(new Event("scroll"));
  await new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve)));
  result.disposal = {
    commits_unchanged: state.commits.length === commitsBeforeDispose,
    requests_unchanged: state.requests.length === requestsBeforeDispose,
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
  const fixtureState = globalThis.__namiTreeFixtureEvidence;
  if (fixtureState?.fixture?.schema !==
      "namisync-tree-window-fixture-v1" ||
      typeof fixtureState.fixtureText !== "string") {
    throw new Error("tree fixture evidence disappeared");
  }
  const {fixture, fixtureText} = fixtureState;
  const views = fixture.views;
  const nodeIds = fixture.node_ids;
  const treeRoot = document.createElement("div");
  treeRoot.ariaLabel = "Presentation tree evidence";
  work.append(treeRoot);
  const interactions = {toggles: [], activations: []};
  const controller = treeModule.createTree(treeRoot, {
    toggle: (...value) => interactions.toggles.push(value),
    activate: (nodeId) => interactions.activations.push(nodeId),
  });
  const supplementalLayoutSource = __LAYOUT_SOURCE__;
  const supplementalLayoutRendered = __LAYOUT_RENDERED__;
  const supplementalHostile = __HOSTILE__;
  const supplementalLong = __LONG__;
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
  controller.commitWindow(currentOne, views.layout_control);
  const layoutRow = rowForNode(treeRoot, nodeIds.layout_control);
  const layoutSource = views.layout_control.rows.find(
    (row) => row.node_id === nodeIds.layout_control)?.display ?? "";
  const layoutRendered = visibleFilesystemText(layoutSource);
  const layoutLabel = layoutRow?.querySelector(".nami-tree-row__label")
    ?.textContent ?? "";

  const pointerGeneration = controller.beginWindowRequest();
  controller.commitWindow(pointerGeneration, views.pointer_collapsed);
  const projectionRow = rowForNode(treeRoot, nodeIds.projection);
  projectionRow?.querySelector(".nami-tree-row__disclosure")?.click();
  projectionRow?.querySelector(".nami-tree-row__label")?.click();

  const triState = [];
  for (const name of [
    "pointer_expanded",
    "pointer_collapsed",
    "projected_empty",
  ]) {
    const generation = controller.beginWindowRequest();
    controller.commitWindow(generation, views[name]);
    triState.push(
      rowForNode(treeRoot, nodeIds.projection)
        ?.getAttribute("aria-expanded") ?? null,
    );
  }

  const textGeneration = controller.beginWindowRequest();
  controller.commitWindow(textGeneration, views.next);
  const ordinarySource = views.next.rows.find(
    (row) => row.node_id === nodeIds.ordinary_unicode)?.display ?? "";
  const longSource = views.next.rows.find(
    (row) => row.node_id === nodeIds.long_unicode)?.display ?? "";
  const ordinaryLabel = rowForNode(treeRoot, nodeIds.ordinary_unicode)
    ?.querySelector(".nami-tree-row__label")?.textContent ?? "";
  const longLabel = rowForNode(treeRoot, nodeIds.long_unicode)
    ?.querySelector(".nami-tree-row__label")?.textContent ?? "";

  // The exhaustive sink vector is renderer-local because Windows filenames
  // cannot carry every defended character, including NUL.
  const sinkRoot = document.createElement("div");
  sinkRoot.ariaLabel = "Renderer sink coverage evidence";
  work.append(sinkRoot);
  const sinkController = treeModule.createTree(sinkRoot);
  const sinkGeneration = sinkController.beginWindowRequest();
  sinkController.commitWindow(sinkGeneration, {
    offset: 0,
    total: 3,
    rows: [
      sinkRow(0, "sink-layout", supplementalLayoutSource),
      sinkRow(1, "sink-hostile", supplementalHostile),
      sinkRow(2, "sink-long", supplementalLong),
    ],
  });
  const sinkLabels = [...sinkRoot.querySelectorAll(".nami-tree-row__label")];
  focused.focus();
  const textEvidence = {
    layout_exact: layoutLabel === layoutRendered,
    layout_controls_absent:
      !activeLayoutControlPattern.test(layoutLabel),
    layout_bytes: new TextEncoder().encode(layoutLabel).length,
    layout_sha256: await sha256(layoutLabel),
    ordinary_exact: ordinaryLabel === ordinarySource,
    ordinary_bytes: new TextEncoder().encode(ordinaryLabel).length,
    ordinary_sha256: await sha256(ordinaryLabel),
    long_exact: longLabel === longSource,
    long_bytes: new TextEncoder().encode(longLabel).length,
    long_sha256: await sha256(longLabel),
    tri_state: triState,
    callback_ids: {
      toggles: interactions.toggles,
      activations: interactions.activations,
      dataset_node_id: projectionRow?.dataset.nodeId ?? null,
    },
    supplemental: {
      layout_exact:
        sinkLabels[0]?.textContent === supplementalLayoutRendered,
      layout_controls_absent: sinkLabels.every((label) =>
        !activeLayoutControlPattern.test(label.textContent ?? "")),
      hostile_exact: sinkLabels[1]?.textContent === supplementalHostile,
      long_exact: sinkLabels[2]?.textContent === supplementalLong,
    },
  };
  const viewCoverage = {};
  for (const name of ["head", "tail", "empty"]) {
    const generation = controller.beginWindowRequest();
    const accepted = controller.commitWindow(generation, views[name]);
    const mountedRows = [
      ...treeRoot.querySelectorAll(".nami-tree-row"),
    ];
    viewCoverage[name] = {
      accepted,
      offset: views[name].offset,
      total: views[name].total,
      row_count: mountedRows.length,
      first_node_id: mountedRows[0]?.dataset.nodeId ?? null,
      last_node_id: mountedRows.at(-1)?.dataset.nodeId ?? null,
    };
  }
  const currentTwo = controller.beginWindowRequest();
  controller.commitWindow(currentTwo, views.maximum);
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
      known_leaf_expanded: rowForNode(treeRoot, nodeIds.layout_control)
        ?.hasAttribute("aria-expanded") ?? null,
      stale_reads: staleReads,
      stale_results: [firstStaleResult, secondStaleResult],
      stale_unchanged,
      text: textEvidence,
      view_coverage: viewCoverage,
    },
    fixture: {
      schema: fixture.schema,
      size: new TextEncoder().encode(fixtureText).length,
      sha256: await sha256(fixtureText),
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

  function rowForNode(root, nodeId) {
    return [...root.querySelectorAll(".nami-tree-row")].find(
      (row) => row.dataset.nodeId === nodeId,
    );
  }

  function visibleFilesystemText(value) {
    return value.replace(
      /[\u0000-\u001f\u007f-\u009f\u00ad\u061c\u200b\u200e-\u200f\u2028-\u202e\u2060-\u206f\ufeff\u27e6-\u27e7]/gu,
      (character) =>
        `⟦U+${character.codePointAt(0).toString(16).toUpperCase().padStart(4, "0")}⟧`,
    );
  }

  function sinkRow(index, nodeId, display) {
    return {
      node_id: nodeId,
      display,
      depth: 0,
      is_container: false,
      visible_index: index,
      parent_visible_index: null,
      first_child_visible_index: null,
      position_in_set: index + 1,
      set_size: 3,
      expanded: null,
    };
  }
})()
"""


class _Recorder:
    def __init__(self, evidence_paths: EvidencePaths) -> None:
        self._publisher = EvidencePublisher(evidence_paths)
        self._lock = threading.Lock()
        self._initial: str | None = None
        self._post_ready_failure: dict[str, str] | None = None
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
        if stage not in _FAILURE_STAGES:
            stage = "child"
        with self._lock:
            failure = {
                "stage": stage,
                "type": _error_type(error),
            }
            if self._initial == "failure":
                return
            if self._initial == "ready":
                if self._post_ready_failure is None:
                    self._post_ready_failure = failure
                return
            self._data["phase"] = "failure"
            self._data["failure"] = failure
            self._publisher.publish_failure({"failure": failure})
            self._initial = "failure"

    def complete(self, page: dict[str, object]) -> None:
        with self._lock:
            if self._initial is not None:
                return
            self._data["page"] = page
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
                payload["post_ready_failure"] = dict(
                    self._post_ready_failure
                )
            self._publisher.publish_final(payload)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--tree-fixture", required=True, type=Path)
    return parser.parse_args()


def _load_tree_fixture(
    path: Path,
) -> tuple[str, dict[str, object], dict[str, object]]:
    if not path.is_absolute():
        raise ValueError("tree fixture path must be absolute")
    resolved = path.resolve(strict=True)
    content = resolved.read_bytes()
    text = content.decode("utf-8", errors="strict")
    manifest = json.loads(text)
    if type(manifest) is not dict or set(manifest) != {
        "schema",
        "node_ids",
        "views",
    }:
        raise TypeError("tree fixture envelope is invalid")
    if manifest["schema"] != _TREE_FIXTURE_SCHEMA:
        raise ValueError("tree fixture schema is unsupported")
    if type(manifest["node_ids"]) is not dict or set(
        manifest["node_ids"]
    ) != {
        "projection",
        "layout_control",
        "ordinary_unicode",
        "long_unicode",
    }:
        raise TypeError("tree fixture node IDs are invalid")
    if type(manifest["views"]) is not dict or set(manifest["views"]) != (
        _TREE_FIXTURE_VIEWS
    ):
        raise TypeError("tree fixture views are invalid")
    return (
        text,
        manifest,
        {
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        },
    )


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


def _fixture_display(
    manifest: dict[str, object] | None,
    view_name: str,
    node_name: str,
) -> str | None:
    if manifest is None:
        return None
    views = manifest["views"]
    node_ids = manifest["node_ids"]
    rows = views[view_name]["rows"]
    return next(
        row["display"]
        for row in rows
        if row["node_id"] == node_ids[node_name]
    )


def _visible_filesystem_text(value: str) -> str:
    return "".join(
        f"⟦U+{ord(character):04X}⟧"
        if ord(character) in _LAYOUT_CODE_POINTS
        else character
        for character in value
    )


def _accessibility_evidence(
    value: object,
    manifest: dict[str, object] | None = None,
) -> dict[str, object]:
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
    layout_source = _fixture_display(
        manifest,
        "layout_control",
        "layout_control",
    )
    layout_rendered = (
        _visible_filesystem_text(layout_source)
        if layout_source is not None
        else None
    )
    ordinary = _fixture_display(
        manifest,
        "next",
        "ordinary_unicode",
    )
    long_value = _fixture_display(manifest, "next", "long_unicode")
    evidence = {
        "tree_count": len(trees),
        "treeitem_count": len(items),
        "keyboard_tree_named": "Keyboard tree evidence" in tree_names,
        "presentation_tree_named": "Presentation tree evidence" in tree_names,
        "layout_label_exact": (
            layout_rendered is not None and layout_rendered in item_names
        ),
        "layout_controls_absent": bool(items) and all(
            type(name) is str
            and all(
                ord(character) not in _ACTIVE_LAYOUT_CODE_POINTS
                for character in name
            )
            for name in item_name_values
        ),
        "ordinary_label_exact": (
            ordinary is not None and ordinary in item_names
        ),
        "long_label_exact": (
            long_value is not None and long_value in item_names
        ),
        "supplemental_layout_label_exact": _LAYOUT_RENDERED in item_names,
        "supplemental_hostile_label_exact": _HOSTILE in item_names,
        "supplemental_long_label_exact": _LONG in item_names,
        "active_descendant_exposed": type(related) is list and bool(related),
    }
    return evidence


def _begin_probe(
    window: object,
    recorder: _Recorder,
    retained: list[object],
    fixture_text: str,
    fixture_manifest: dict[str, object],
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
        expression = _KEYBOARD_TREE_PROBE.replace(
            "__TREE_FIXTURE_TEXT__",
            json.dumps(fixture_text),
        )
        evaluate(expression, after_keyboard_tree)

    def after_keyboard_tree(value: object) -> None:
        page["keyboard_tree"] = value
        evaluate('document.querySelector(".nami-task-rail__settings").click(); document.querySelector(".nami-task-rail__settings").focus(); ({ready: true});',
                 lambda _value: press("Tab", "Tab", 9, after_theme_tab))

    def after_theme_tab(_value: object) -> None:
        evaluate(_THEME_FOCUS_PROBE, after_theme_focus)

    def after_theme_focus(value: object) -> None:
        page["theme_focus"] = value
        evaluate('document.querySelector(".nami-task-rail__create").focus(); ({ready: true});', after_create_tab)

    def after_create_tab(_value: object) -> None:
        evaluate(_CREATE_FOCUS_PROBE, after_create_focus)

    def after_create_focus(value: object) -> None:
        page["create_focus"] = value
        evaluate('document.querySelector("#theme-mode-trigger").focus(); ({ready: true});',
                 lambda _value: press("Tab", "Tab", 9, after_tree_tab))

    def after_tree_tab(_value: object) -> None:
        evaluate(_ACTIVE_PROBE, after_first_focus)

    def after_first_focus(value: object) -> None:
        page["first_focus"] = value
        # Work pages are exclusive. Keep the native Tab witness above, then
        # replace Settings with the same tree before testing its reflow.
        evaluate(
            'const root = globalThis.__namiShellTreeEvidence.root; '
            'document.querySelector(".nami-work-panel__body").replaceChildren(root); '
            'root.focus(); ({ready: true});',
            lambda _value: press("ArrowDown", "ArrowDown", 40, after_second_key),
        )

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
        page["accessibility"] = _accessibility_evidence(
            value,
            fixture_manifest,
        )
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
    fixture_text: str,
    fixture_manifest: dict[str, object],
    *appearance_args: object,
    **appearance_kwargs: object,
) -> object:
    controller = original(window, *appearance_args, **appearance_kwargs)

    def loaded() -> None:
        from System import Action

        native = window.native

        def begin() -> None:
            try:
                _begin_probe(
                    window,
                    recorder,
                    retained,
                    fixture_text,
                    fixture_manifest,
                )
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

    fixture_text, fixture_manifest, fixture_evidence = _load_tree_fixture(
        arguments.tree_fixture
    )
    recorder.set("tree_fixture", fixture_evidence)
    recorder.set("runtime", _runtime_identity())
    recorder.set("installed_assets", _installed_assets())
    retained: list[object] = []
    original = host._configure_window_appearance
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                host,
                "_configure_window_appearance",
                lambda window, *args, **kwargs: _configure_probe(
                    window,
                    recorder,
                    retained,
                    original,
                    fixture_text,
                    fixture_manifest,
                    *args,
                    **kwargs,
                ),
            )
        )
        exit_code = host.run_desktop(
            AppPaths.from_root(arguments.data_dir),
            DesktopInstanceIdentity(arguments.mutex, arguments.title),
            startup_error=recorder.startup_error,
        )
    del retained
    if not recorder.settled:
        recorder.failure(
            "child",
            RuntimeError("host returned before shell evidence completed"),
        )
    recorder.finish(exit_code, host_returned=True)
    return exit_code


def _error_type(error: BaseException) -> str:
    name = type(error).__name__
    if name in _FAILURE_TYPES:
        return name
    return "Error"


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
