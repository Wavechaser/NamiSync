"""Installed-wheel child that captures the production Setup surface."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from threading import Lock
from typing import Any

from _headed_evidence import EvidencePaths, EvidencePublisher


_COMPLETE_TEXT = "Setup headed gate complete"


class _Recorder:
    def __init__(self, paths: EvidencePaths) -> None:
        self._publisher = EvidencePublisher(paths)
        self._lock = Lock()
        self._finished = False
        self._diagnostics: dict[str, str] = {}

    def observe(self, name: str, value: object) -> None:
        with self._lock:
            self._diagnostics[name] = repr(value)[:2048]

    def ready(self, payload: dict[str, object]) -> None:
        self._publisher.publish_ready(payload)

    def failure(self, stage: str, error: BaseException) -> None:
        with self._lock:
            if self._finished:
                return
            self._publisher.publish_failure({
                "stage": stage,
                "type": type(error).__name__,
                "detail": str(error)[:1024],
                "diagnostics": dict(self._diagnostics),
            })

    def finish(self, exit_code: int) -> None:
        with self._lock:
            if self._finished:
                return
            self._finished = True
            self._publisher.publish_final({"host_returned": True, "exit_code": exit_code})


_EDITABLE_SCRIPT = r"""
(async () => {
  const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
  async function until(predicate, label) {
    for (let attempt = 0; attempt < 200; attempt += 1) {
      const value = predicate();
      if (value) return value;
      await sleep(25);
    }
    throw new Error(`timed out waiting for ${label}`);
  }
  await until(() => document.querySelector("#host-status")?.textContent === "Ready", "host readiness");
  document.querySelector(".nami-task-rail__header .nami-button")?.click();
  const source = await until(() => document.querySelector("#setup-source-path"), "editable source input");
  const target = document.querySelector("#setup-target-path");
  const options = document.querySelector(".nami-setup__options");
  if (!(source instanceof HTMLInputElement) || !(target instanceof HTMLInputElement) ||
      !(options instanceof HTMLDivElement) || source.disabled || target.disabled) {
    throw new Error("editable Setup controls are unavailable");
  }
  const cards = document.querySelectorAll(".nami-setup > .nami-setup__card.nami-card");
  const mode = document.querySelector('.nami-setup__mode[role="radiogroup"]');
  const syncMode = mode?.querySelector('[role="radio"][data-value="sync-plan"]');
  const inventoryMode = mode?.querySelector('[role="radio"][data-value="inventory"]');
  const more = document.querySelector(".nami-setup__more-options");
  const deletionPolicy = document.querySelector("#setup-deletion-policy");
  const verifyToggle = document.querySelector('[data-option="verify_after_execute"]');
  const adsToggle = document.querySelector('[data-option="preserve_ads"]');
  const sourceLine = document.querySelector('[data-purpose="source"] .nami-setup__location-line');
  const sourceLabel = document.querySelector('[for="setup-source-path"]');
  const pathControl = document.querySelector('[data-purpose="source"] .nami-setup__path-control');
  const recentTrigger = document.querySelector("#setup-source-recent-trigger");
  const picker = document.querySelector('[data-purpose="source"] .nami-setup__picker');
  const inventoryAction = Array.from(document.querySelectorAll(".nami-setup__actions button"))
    .find((item) => item.textContent === "Create inventory");
  const planAgainAction = Array.from(document.querySelectorAll(".nami-setup__actions button"))
    .find((item) => item.textContent === "Plan again");
  if (cards.length !== 2 || !(syncMode instanceof HTMLButtonElement) || !(inventoryMode instanceof HTMLButtonElement) ||
      !(more instanceof HTMLDetailsElement) || !(sourceLine instanceof HTMLDivElement) ||
      !(sourceLabel instanceof HTMLLabelElement) || !(pathControl instanceof HTMLDivElement) ||
      !(recentTrigger instanceof HTMLButtonElement) || !(picker instanceof HTMLButtonElement) ||
      !(deletionPolicy instanceof HTMLSelectElement) || !(verifyToggle instanceof HTMLInputElement) ||
      !(adsToggle instanceof HTMLInputElement) || !adsToggle.disabled ||
      !(inventoryAction instanceof HTMLButtonElement) || !(planAgainAction instanceof HTMLButtonElement)) {
    throw new Error("Setup layout controls are unavailable");
  }
  syncMode.focus();
  syncMode.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowRight", bubbles: true}));
  await until(() => inventoryMode.getAttribute("aria-checked") === "true" && document.activeElement === inventoryMode, "keyboard inventory segment");
  inventoryMode.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowLeft", bubbles: true}));
  await until(() => syncMode.getAttribute("aria-checked") === "true" && document.activeElement === syncMode, "keyboard sync segment");
  more.querySelector("summary")?.click();
  if (!more.open) throw new Error("More options disclosure did not open");
  const inlineRects = [sourceLabel, source, recentTrigger, picker].map((item) => item.getBoundingClientRect());
  const inlineControls = inlineRects.every((rect) => rect.top < inlineRects[0].bottom && rect.bottom > inlineRects[0].top);
  const browseOutsidePathControl = picker.getBoundingClientRect().left > pathControl.getBoundingClientRect().right;
  const availabilityRows = await until(() => {
    const values = Array.from(document.querySelectorAll(".nami-setup__recent-pair"));
    const states = values.map((row) => row.dataset.availability);
    return values.length === 2 && states.includes("online") && states.includes("offline") ? values : null;
  }, "online and offline recent-pair probes");
  const onlinePair = availabilityRows.find((row) => row.dataset.availability === "online");
  const offlinePair = availabilityRows.find((row) => row.dataset.availability === "offline");
  const offlinePaths = offlinePair.querySelectorAll(".nami-setup__pair-path");
  const pathStyle = getComputedStyle(offlinePaths[0]);
  const offlineStatus = offlinePair.querySelector(".nami-setup__availability");
  const neutralColor = getComputedStyle(document.querySelector(".nami-setup__recent-pair-table th")).color;
  const onlineDot = onlinePair.querySelector(".nami-setup__availability-dot");
  const offlineDot = offlinePair.querySelector(".nami-setup__availability-dot");
  const onlineSelect = onlinePair.querySelector(".nami-setup__pair-select");
  const offlineSelect = offlinePair.querySelector(".nami-setup__pair-select");
  if (!(onlineSelect instanceof HTMLButtonElement) || !(offlineSelect instanceof HTMLButtonElement) ||
      offlinePair.getAttribute("aria-disabled") !== "true" || !offlineSelect.disabled ||
      onlinePair.getAttribute("aria-disabled") !== "false" || onlineSelect.disabled) {
    throw new Error("recent-pair availability interaction state is incorrect");
  }
  source.focus();
  source.value = "not a native folder";
  source.dispatchEvent(new Event("input", {bubbles: true}));
  source.dispatchEvent(new Event("blur", {bubbles: true}));
  await until(() => source.dataset.state !== "unresolved", "typed location refusal");
  const refusedState = source.dataset.state;
  source.focus();
  source.value = __SOURCE__;
  source.dispatchEvent(new Event("input", {bubbles: true}));
  source.dispatchEvent(new Event("blur", {bubbles: true}));
  await until(() => source.dataset.state === "resolved", "corrected typed location admission");
  recentTrigger.focus();
  recentTrigger.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowDown", bubbles: true}));
  const recentOption = await until(() => document.querySelector("#setup-source-recent-popup [role=option]:focus"), "keyboard recent option");
  const recentPopup = document.querySelector("#setup-source-recent-popup");
  const dropdownAnchored = recentPopup.parentElement === pathControl &&
    recentPopup.getBoundingClientRect().left >= pathControl.getBoundingClientRect().left &&
    recentPopup.getBoundingClientRect().right <= pathControl.getBoundingClientRect().right;
  document.querySelector(".nami-setup__refresh-recents").click();
  await until(() => onlinePair.dataset.availability === "online", "availability refresh completion");
  if (recentTrigger.getAttribute("aria-expanded") !== "true" || document.activeElement !== recentOption) {
    throw new Error("unrelated availability refresh replaced recent-folder focus");
  }
  recentOption.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
  await until(() => recentTrigger.getAttribute("aria-expanded") === "false" && document.activeElement === recentTrigger, "recent Escape return");
  const recentKeyboard = document.activeElement === recentTrigger;
  const filter = document.querySelector("#setup-filter");
  if (!(filter instanceof HTMLInputElement)) throw new Error("Setup filter is unavailable");
  const hostile = "<img src=x onerror=alert(1)>";
  filter.value = hostile;
  filter.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
  await until(() => Array.from(document.querySelectorAll(".nami-setup__filter-list span"))
    .some((item) => item.textContent === hostile), "inert hostile filter");
  await until(() => onlinePair.dataset.availability === "online" && !onlineSelect.disabled, "refreshed online pair");
  onlineSelect.focus({focusVisible: true});
  return {
    editable: true,
    typed_refusal: refusedState,
    typed_retry_resolved: source.dataset.state === "resolved",
    hostile_filter_inert: document.querySelector("img") === null,
    options_visible: options.checkVisibility(),
    two_setup_cards: cards.length === 2,
    segmented_keyboard: syncMode.getAttribute("aria-checked") === "true",
    recent_dropdown_keyboard: recentKeyboard,
    disclosure_open: more.open,
    inline_location_controls: inlineControls,
    browse_outside_path_control: browseOutsidePathControl,
    dropdown_anchored: dropdownAnchored,
    dropdown_rerender_focus_restored: recentKeyboard,
    picker_icon_only: picker.textContent === "" && picker.getAttribute("aria-label") === "Browse for source folder",
    advanced_switches: more.querySelectorAll('input[role="switch"]').length === 5,
    primary_options_visible: deletionPolicy.checkVisibility() && verifyToggle.checkVisibility(),
    sync_inapplicable_actions_hidden: !inventoryAction.checkVisibility() && !planAgainAction.checkVisibility(),
    recent_pair_online_offline: true,
    offline_pair_disabled: offlinePair.getAttribute("aria-disabled") === "true",
    pair_two_line_paths: offlinePaths.length === 2 && offlinePaths[0].getBoundingClientRect().top < offlinePaths[1].getBoundingClientRect().top,
    pair_paths_truncated: pathStyle.textOverflow === "ellipsis" && pathStyle.overflow === "hidden" &&
      Array.from(offlinePaths).every((item) => item.scrollWidth > item.clientWidth && item.title === item.textContent),
    availability_dots_distinct: getComputedStyle(onlineDot).backgroundColor !== getComputedStyle(offlineDot).backgroundColor,
    availability_text_neutral: getComputedStyle(offlineStatus).color === neutralColor &&
      getComputedStyle(onlinePair.querySelector(".nami-setup__availability")).color === neutralColor,
    pair_button_focused: document.activeElement === onlineSelect,
    source_node_id: source.id,
  };
})()
"""


_FROZEN_SCRIPT = r"""
(async () => {
  const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
  async function until(predicate, label) {
    for (let attempt = 0; attempt < 400; attempt += 1) {
      const value = predicate();
      if (value) return value;
      await sleep(25);
    }
    throw new Error(`timed out waiting for ${label}`);
  }
  const source = document.querySelector("#setup-source-path");
  const target = document.querySelector("#setup-target-path");
  const button = document.querySelector(".nami-setup__actions .nami-button--primary");
  if (!(source instanceof HTMLInputElement) || !(target instanceof HTMLInputElement) ||
      !(button instanceof HTMLButtonElement)) throw new Error("plan action is unavailable");
  const picker = document.querySelector('[data-purpose="source"] .nami-setup__picker');
  if (!(picker instanceof HTMLButtonElement)) throw new Error("source picker is unavailable");
  picker.focus();
  picker.click();
  await until(() => source.dataset.state === "resolved" && source.value === __PICKED_SOURCE__, "resolved picker choice");
  target.value = __TARGET__;
  target.dispatchEvent(new Event("input", {bubbles: true}));
  target.dispatchEvent(new Event("blur", {bubbles: true}));
  await until(() => target.dataset.state === "resolved" && !button.disabled, "resolved typed target");
  button.click();
  const mode = document.querySelector(".nami-setup__mode-group");
  await until(() => source.disabled && target.disabled && mode instanceof HTMLDivElement && mode.hidden,
    "persisted frozen Setup snapshot");
  const frozenModeHidden = !mode.checkVisibility();
  const frozenSwitches = Array.from(document.querySelectorAll('.nami-setup__options input[role="switch"]'));
  const frozenPairs = Array.from(document.querySelectorAll(".nami-setup__pair-select"));
  let planAgain;
  try {
    planAgain = await until(() => {
      const candidate = document.querySelector(".nami-setup__actions .nami-button:last-child");
      return candidate instanceof HTMLButtonElement && !candidate.hidden ? candidate : null;
    }, "fresh Plan-again readiness");
  } catch (error) {
    const detail = {
      host: document.querySelector("#host-status")?.textContent ?? null,
      guidance: document.querySelector(".nami-setup > p")?.textContent ?? null,
      action: document.querySelector(".nami-setup__action-status")?.textContent ?? null,
      task_status: document.querySelector('[aria-current="page"] .nami-task-card__status')?.textContent ?? null,
      mode_hidden: mode instanceof HTMLDivElement ? mode.hidden : null,
    };
    throw new Error(`${error.message}; dom=${JSON.stringify(detail)}`);
  }
  const before = document.querySelectorAll(".nami-task-rail__row").length;
  planAgain.click();
  await until(() => document.querySelectorAll(".nami-task-rail__row").length === before + 1, "Plan-again task identity");
  return {
    frozen: true,
    source_disabled: source.disabled,
    target_disabled: target.disabled,
    plan_again_visible: !planAgain.hidden,
    plan_again_new_task: true,
    picker_resolved: source.dataset.state === "resolved",
    frozen_switches_disabled: frozenSwitches.length === 6 && frozenSwitches.every((input) => input.disabled),
    frozen_pairs_disabled: frozenPairs.length === 2 && frozenPairs.every((button) => button.disabled),
    frozen_mode_hidden: frozenModeHidden,
  };
})()
"""


_INDEPENDENT_SCRIPT = r"""
(async () => {
  const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
  async function until(predicate, label) {
    for (let attempt = 0; attempt < 400; attempt += 1) {
      const value = predicate();
      if (value) return value;
      await sleep(25);
    }
    throw new Error(`timed out waiting for ${label}`);
  }
  function newTask() {
    document.querySelector(".nami-task-rail__header .nami-button")?.click();
  }
  async function editable() {
    return await until(() => {
      const source = document.querySelector("#setup-source-path");
      const target = document.querySelector("#setup-target-path");
      return source instanceof HTMLInputElement && target instanceof HTMLInputElement && !source.disabled ? {source, target} : null;
    }, "new editable Setup task");
  }

  newTask();
  let {source, target} = await editable();
  const recentPair = await until(() => {
    const value = document.querySelector('.nami-setup__recent-pair[data-availability="online"]');
    const button = value?.querySelector(".nami-setup__pair-select");
    return button instanceof HTMLButtonElement && !button.disabled ? button : null;
  }, "online recent pair");
  recentPair.focus();
  recentPair.click();
  await until(() => source.dataset.state === "resolved" && target.dataset.state === "resolved", "recent pair admission");
  const pairActivated = source.value.length > 0 && target.value.length > 0;
  const mode = document.querySelector('.nami-setup__mode [role="radio"][data-value="inventory"]');
  if (!(mode instanceof HTMLButtonElement)) throw new Error("task type selector is unavailable");
  mode.click();
  await until(() => document.querySelector('[for="setup-source-path"]')?.textContent === "Root", "inventory mode");
  const recentTrigger = await until(() => document.querySelector("#setup-source-recent-trigger"), "recent source trigger");
  recentTrigger.click();
  const recent = await until(() => Array.from(document.querySelectorAll('#setup-source-recent-popup [role="option"]'))
    .find((item) => item.textContent === __SOURCE__), "known online recent source");
  recent.click();
  await until(() => source.dataset.state === "resolved", "recent admission");
  const inventory = Array.from(document.querySelectorAll(".nami-setup__actions button"))
    .find((button) => button.textContent === "Create inventory");
  if (!(inventory instanceof HTMLButtonElement)) throw new Error("inventory action is unavailable");
  inventory.click();
  await until(() => source.disabled && document.querySelector(".nami-setup__mode-group")?.hidden && target.value === "" &&
    document.querySelector('[data-purpose="target"]')?.hidden === true &&
    document.querySelector('[for="setup-source-path"]')?.textContent === "Root", "frozen inventory");
  const inventoryWithoutPair = target.value === "" &&
    document.querySelector('[data-purpose="target"]')?.hidden === true;
  const inventoryInapplicableHidden = !document.querySelector('[data-purpose="target"]').checkVisibility() &&
    !document.querySelector(".nami-setup__recent-pairs").checkVisibility() &&
    !document.querySelector(".nami-setup__options").checkVisibility();

  newTask();
  ({source, target} = await editable());
  source.value = __SOURCE__;
  source.dispatchEvent(new Event("input", {bubbles: true}));
  const add = Array.from(document.querySelectorAll(".nami-setup__actions button"))
    .find((button) => button.textContent === "Add pair");
  if (!(add instanceof HTMLButtonElement)) throw new Error("pair action is unavailable");
  add.click();
  target.value = __TARGET__;
  target.dispatchEvent(new Event("input", {bubbles: true}));
  add.click();
  const batch = Array.from(document.querySelectorAll(".nami-setup__actions button"))
    .find((button) => button.textContent === "Create pair batch");
  if (!(batch instanceof HTMLButtonElement)) throw new Error("batch action is unavailable");
  batch.click();
  await until(() => {
    const states = Array.from(document.querySelectorAll(".nami-setup__batch-row")).map((item) => item.dataset.state);
    return states.includes("refused") && states.includes("created") ? states : null;
  }, "mixed serial batch");
  const original = Array.from(document.querySelectorAll(".nami-task-card"))
    .find((button) => button.querySelector(".nami-task-card__title")?.textContent === "Task 1");
  if (!(original instanceof HTMLButtonElement)) throw new Error("original frozen task is unavailable");
  original.click();
  await until(() => document.querySelector("#setup-source-path")?.disabled, "original frozen task navigation");
  return {
    recent_activated: true,
    recent_pair_activated: pairActivated,
    recent_pair_native_button: recentPair.tagName === "BUTTON",
    inventory_without_pair: inventoryWithoutPair,
    inventory_inapplicable_hidden: inventoryInapplicableHidden,
    mixed_batch: true,
    navigation_retains_frozen: true,
  };
})()
"""


_AMBIGUITY_SCRIPT = r"""
(async () => {
  const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
  async function until(predicate, label) {
    for (let attempt = 0; attempt < 400; attempt += 1) {
      const value = predicate();
      if (value) return value;
      await sleep(25);
    }
    throw new Error(`timed out waiting for ${label}`);
  }
  document.querySelector(".nami-task-rail__header .nami-button")?.click();
  const source = await until(() => {
    const value = document.querySelector("#setup-source-path");
    return value instanceof HTMLInputElement && !value.disabled ? value : null;
  }, "ambiguity Setup source");
  const target = document.querySelector("#setup-target-path");
  const start = Array.from(document.querySelectorAll(".nami-setup__actions button"))
    .find((button) => button.textContent === "Create plan");
  if (!(target instanceof HTMLInputElement) || !(start instanceof HTMLButtonElement)) {
    throw new Error("ambiguity Setup actions are unavailable");
  }
  target.value = __TARGET__;
  target.dispatchEvent(new Event("input", {bubbles: true}));
  target.dispatchEvent(new Event("blur", {bubbles: true}));
  await until(() => target.dataset.state === "resolved", "ambiguity target admission");
  const picker = document.querySelector('[data-purpose="source"] .nami-setup__picker');
  if (!(picker instanceof HTMLButtonElement)) throw new Error("ambiguity picker is unavailable");
  picker.focus();
  picker.click();
  const mounts = await until(() => {
    const values = Array.from(document.querySelectorAll('[data-purpose="source"] .nami-setup__mount'));
    return source.dataset.state === "ambiguous" && values.length === 2 ? values : null;
  }, "picker ambiguity continuation");
  const refusedBeforeChoice = start.disabled;
  const chosenIndex = Number(mounts[1].dataset.mountIndex);
  mounts[1].click();
  await until(() => source.dataset.state === "resolved" && !start.disabled, "continued picker choice");
  const frozenTask = Array.from(document.querySelectorAll(".nami-task-card"))
    .find((button) => button.querySelector(".nami-task-card__title")?.textContent === "Task 1");
  if (!(frozenTask instanceof HTMLButtonElement)) throw new Error("frozen task is unavailable before reload");
  frozenTask.click();
  await until(() => {
    const frozenSource = document.querySelector("#setup-source-path");
    const mode = document.querySelector(".nami-setup__mode-group");
    const planAgain = Array.from(document.querySelectorAll(".nami-setup__actions button"))
      .find((button) => button.textContent === "Plan again");
    return frozenSource instanceof HTMLInputElement && frozenSource.disabled &&
      mode instanceof HTMLDivElement && mode.hidden &&
      planAgain instanceof HTMLButtonElement && !planAgain.hidden;
  }, "frozen task before screenshot and reload");
  return {
    picker_ambiguous: true,
    picker_mount_index: chosenIndex,
    picker_continued: source.dataset.state === "resolved",
    start_refused_before_choice: refusedBeforeChoice,
    frozen_before_capture: true,
    task_count_before_reload: document.querySelectorAll(".nami-task-rail__row").length,
  };
})()
"""


_RELOADED_SCRIPT = r"""
(async () => {
  const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
  async function until(predicate, label) {
    for (let attempt = 0; attempt < 400; attempt += 1) {
      const value = predicate();
      if (value) return value;
      await sleep(25);
    }
    throw new Error(`timed out waiting for ${label}`);
  }
  await until(() => document.querySelector("#host-status")?.textContent === "Ready", "reloaded host readiness");
  await until(() => document.querySelectorAll(".nami-task-rail__row").length === __TASK_COUNT__, "reloaded task identities");
  const cards = Array.from(document.querySelectorAll(".nami-task-card"));
  let reconstructed = false;
  const observations = [];
  for (const card of cards) {
    const title = card.querySelector(".nami-task-card__title")?.textContent;
    if (!title) throw new Error("reloaded task lacks its title");
    card.click();
    let source = null;
    for (let attempt = 0; attempt < 80 && source === null; attempt += 1) {
      const value = document.querySelector("#setup-source-path");
      if (document.querySelector(".nami-work-panel h2")?.textContent === title &&
          value instanceof HTMLInputElement) source = value;
      else await sleep(25);
    }
    const target = document.querySelector("#setup-target-path");
    const planAgain = Array.from(document.querySelectorAll(".nami-setup__actions button"))
      .find((button) => button.textContent === "Plan again");
    observations.push({
      title,
      setup: source instanceof HTMLInputElement,
      source_disabled: source instanceof HTMLInputElement ? source.disabled : null,
      target_disabled: target instanceof HTMLInputElement ? target.disabled : null,
      plan_again_visible: planAgain instanceof HTMLButtonElement ? !planAgain.hidden : null,
    });
    if (source instanceof HTMLInputElement && source.disabled && target instanceof HTMLInputElement && target.disabled &&
        planAgain instanceof HTMLButtonElement && !planAgain.hidden) {
      reconstructed = true;
      break;
    }
  }
  const marker = document.createElement("p");
  marker.textContent = "Setup headed gate complete";
  document.body.append(marker);
  return {
    reload_task_count: cards.length,
    reload_frozen_reconstructed: reconstructed,
    reload_observations: observations,
  };
})()
"""


def _runtime_value(task: object) -> dict[str, object]:
    if task.IsFaulted or task.IsCanceled:
        raise RuntimeError("native CDP evaluation failed")
    envelope = json.loads(str(task.Result))
    exception = envelope.get("exceptionDetails") if type(envelope) is dict else None
    if type(exception) is dict:
        thrown = exception.get("exception")
        detail = thrown.get("description") if type(thrown) is dict else exception.get("text")
        raise RuntimeError(str(detail)[:1024])
    value = envelope.get("result", {}).get("value") if type(envelope) is dict else None
    if type(value) is not dict:
        raise RuntimeError("page Setup probe did not return an object")
    return value


def _capture(
    core: object,
    path: Path,
    retained: list[object],
    continuation: object,
    on_failure: object,
) -> None:
    from System import Action

    task = core.CallDevToolsProtocolMethodAsync("Page.captureScreenshot", "{\"format\":\"png\"}")

    def completed() -> None:
        try:
            if task.IsFaulted or task.IsCanceled:
                raise RuntimeError("native screenshot capture failed")
            envelope = json.loads(str(task.Result))
            data = envelope.get("data") if type(envelope) is dict else None
            if type(data) is not str:
                raise RuntimeError("native screenshot payload is invalid")
            path.write_bytes(base64.b64decode(data, validate=True))
            continuation()
        except BaseException as error:
            on_failure(error)

    action = Action(completed)
    retained.append(action)
    task.GetAwaiter().OnCompleted(action)


def _begin(
    window: object,
    recorder: _Recorder,
    screenshot_dir: Path,
    source: Path,
    target: Path,
    retained: list[object],
    state: dict[str, object],
) -> None:
    from System import Action

    core = window.native.browser.webview.CoreWebView2
    picked_source = source.parent / "picked-source"
    editable_script = _EDITABLE_SCRIPT.replace("__SOURCE__", json.dumps(str(source)))
    editable_settings = json.dumps({"expression": editable_script, "awaitPromise": True, "returnByValue": True})
    editable_task = core.CallDevToolsProtocolMethodAsync("Runtime.evaluate", editable_settings)

    def editable_done() -> None:
        try:
            editable = _runtime_value(editable_task)
            def begin_frozen() -> None:
                picked_source = source.parent / "picked-source"
                script = _FROZEN_SCRIPT.replace("__PICKED_SOURCE__", json.dumps(str(picked_source))).replace("__TARGET__", json.dumps(str(target)))
                frozen_settings = json.dumps({"expression": script, "awaitPromise": True, "returnByValue": True})
                frozen_task = core.CallDevToolsProtocolMethodAsync("Runtime.evaluate", frozen_settings)

                def frozen_done() -> None:
                    try:
                        frozen = _runtime_value(frozen_task)
                        independent_script = _INDEPENDENT_SCRIPT.replace("__SOURCE__", json.dumps(str(source))).replace("__TARGET__", json.dumps(str(target)))
                        independent_settings = json.dumps({"expression": independent_script, "awaitPromise": True, "returnByValue": True})
                        independent_task = core.CallDevToolsProtocolMethodAsync("Runtime.evaluate", independent_settings)

                        def independent_done() -> None:
                            try:
                                independent = _runtime_value(independent_task)
                                ambiguity_script = _AMBIGUITY_SCRIPT.replace("__TARGET__", json.dumps(str(target)))
                                ambiguity_settings = json.dumps({"expression": ambiguity_script, "awaitPromise": True, "returnByValue": True})
                                ambiguity_task = core.CallDevToolsProtocolMethodAsync("Runtime.evaluate", ambiguity_settings)

                                def ambiguity_done() -> None:
                                    try:
                                        ambiguity = _runtime_value(ambiguity_task)
                                        report = {**editable, **frozen, **independent, **ambiguity}

                                        def reload_page() -> None:
                                            state["report"] = report
                                            state["stage"] = "reload"
                                            reload_settings = json.dumps({
                                                "expression": "location.reload();",
                                                "awaitPromise": False,
                                                "returnByValue": True,
                                            })
                                            core.CallDevToolsProtocolMethodAsync("Runtime.evaluate", reload_settings)

                                        _capture(
                                            core, screenshot_dir / "frozen.png", retained,
                                            reload_page,
                                            lambda error: recorder.failure("frozen-screenshot", error),
                                        )
                                    except BaseException as error:
                                        recorder.failure("ambiguity", error)

                                ambiguity_action = Action(ambiguity_done)
                                retained.append(ambiguity_action)
                                ambiguity_task.GetAwaiter().OnCompleted(ambiguity_action)
                            except BaseException as error:
                                recorder.failure("independent", error)

                        independent_action = Action(independent_done)
                        retained.append(independent_action)
                        independent_task.GetAwaiter().OnCompleted(independent_action)
                    except BaseException as error:
                        recorder.failure("frozen", error)

                action = Action(frozen_done)
                retained.append(action)
                frozen_task.GetAwaiter().OnCompleted(action)

            _capture(
                core, screenshot_dir / "editable-expanded.png", retained,
                lambda: _collapse_and_capture_editable(
                    core, screenshot_dir, retained, begin_frozen,
                    lambda error: recorder.failure("editable-screenshot", error),
                ),
                lambda error: recorder.failure("editable-expanded-screenshot", error),
            )
        except BaseException as error:
            recorder.failure("editable", error)

    action = Action(editable_done)
    retained.append(action)
    editable_task.GetAwaiter().OnCompleted(action)


def _begin_reloaded(window: object, recorder: _Recorder, retained: list[object], state: dict[str, object]) -> None:
    from System import Action

    report = state.get("report")
    if type(report) is not dict or type(report.get("task_count_before_reload")) is not int:
        recorder.failure("reload", RuntimeError("reload report is unavailable"))
        return
    script = _RELOADED_SCRIPT.replace("__TASK_COUNT__", str(report["task_count_before_reload"]))
    settings = json.dumps({"expression": script, "awaitPromise": True, "returnByValue": True})
    core = window.native.browser.webview.CoreWebView2
    task = core.CallDevToolsProtocolMethodAsync("Runtime.evaluate", settings)

    def reloaded_done() -> None:
        try:
            reloaded = _runtime_value(task)
            state["stage"] = "complete"
            recorder.ready({**report, **reloaded, "screenshots": ["editable", "editable-expanded", "frozen"]})
        except BaseException as error:
            recorder.failure("reload", error)

    action = Action(reloaded_done)
    retained.append(action)
    task.GetAwaiter().OnCompleted(action)


def _collapse_and_capture_editable(
    core: object,
    screenshot_dir: Path,
    retained: list[object],
    continuation: object,
    on_failure: object,
) -> None:
    from System import Action

    settings = json.dumps({
        "expression": 'document.querySelector(".nami-setup__more-options").open = false;',
        "awaitPromise": False,
        "returnByValue": True,
    })
    task = core.CallDevToolsProtocolMethodAsync("Runtime.evaluate", settings)

    def collapsed() -> None:
        try:
            if task.IsFaulted or task.IsCanceled:
                raise RuntimeError("collapsing editable Setup failed")
            _capture(core, screenshot_dir / "editable.png", retained, continuation, on_failure)
        except BaseException as error:
            on_failure(error)

    action = Action(collapsed)
    retained.append(action)
    task.GetAwaiter().OnCompleted(action)


def _configure_probe(window: object, recorder: _Recorder, screenshot_dir: Path, source: Path, target: Path, retained: list[object], original: object, *args: object, **kwargs: object) -> object:
    controller = original(window, *args, **kwargs)
    state: dict[str, object] = {"stage": "initial", "report": None}

    def loaded() -> None:
        from System import Action

        stage = state["stage"]
        if stage == "initial":
            state["stage"] = "running"
            callback = lambda: _begin(window, recorder, screenshot_dir, source, target, retained, state)
        elif stage == "reload":
            state["stage"] = "reloading"
            callback = lambda: _begin_reloaded(window, recorder, retained, state)
        else:
            return
        action = Action(callback)
        retained.append(action)
        window.native.BeginInvoke(action)

    retained.append(loaded)
    window.events.loaded += loaded
    return controller


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--screenshot-dir", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    return parser.parse_args()


class _AmbiguousRegistry:
    def __init__(self, inner: object, candidate_path: Path, mounts: tuple[Path, Path], recorder: _Recorder) -> None:
        self._inner = inner
        self._candidate_path = str(candidate_path)
        self._mounts = tuple(str(mount) for mount in mounts)
        self._recorder = recorder

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)

    def bind_response_codec(self, response_codec: object) -> None:
        self._inner.bind_response_codec(response_codec)

    def list_tasks(self) -> object:
        result = self._inner.list_tasks()
        self._recorder.observe("list_tasks", result)
        return result

    def read_task_setup(self, task_id: str) -> object:
        try:
            result = self._inner.read_task_setup(task_id)
        except BaseException as error:
            self._recorder.observe("read_task_setup_error", error)
            raise
        self._recorder.observe("read_task_setup", result)
        return result

    def start_setup_plan(self, *args: object, **kwargs: object) -> object:
        try:
            result = self._inner.start_setup_plan(*args, **kwargs)
        except BaseException as error:
            self._recorder.observe("start_setup_plan_error", error)
            raise
        self._recorder.observe("start_setup_plan", result)
        return result

    def admit_location_candidate(self, candidate: object) -> object:
        from namisync.core.models import VolumeId
        from namisync.workflows import (
            LocationBinding,
            LocationCandidate,
            LocationCandidateResult,
            LocationCandidateState,
            VolumeResolution,
            VolumeResolutionState,
        )

        if type(candidate) is not LocationCandidate or candidate.path != self._candidate_path:
            return self._inner.admit_location_candidate(candidate)
        volume_id = VolumeId("setup-headed-clone", "NTFS")
        if candidate.selected_mount is None:
            binding = LocationBinding(
                volume_id, "", self._mounts[0], self._mounts, False
            )
            resolution = VolumeResolution(
                VolumeResolutionState.AMBIGUOUS,
                binding,
                candidates=self._mounts,
                detail="choose one mounted clone before submission",
            )
            return LocationCandidateResult(
                candidate,
                LocationCandidateState.AMBIGUOUS,
                binding=binding,
                candidates=self._mounts,
                detail=resolution.detail,
                resolution=resolution,
            )
        binding = LocationBinding(
            volume_id,
            "",
            candidate.selected_mount,
            self._mounts,
            True,
        )
        return LocationCandidateResult(
            candidate,
            LocationCandidateState.RESOLVED,
            binding=binding,
            root_path=candidate.selected_mount,
            candidates=self._mounts,
        )


def _seed_recent_pair(paths: object, source: Path, target: Path, *, token: str) -> None:
    from namisync.core.evidence import RecordingStatus
    from namisync.core.models import VolumeEvidence
    from namisync.core.planning import selection_digest
    from namisync.core.recording import (
        FinishRunCommand,
        HostCommand,
        LocationCommand,
        MappingCommand,
        SyncRunCommand,
        VolumeCommand,
    )
    from namisync.core.session import RunContext, SessionState
    from namisync.db.recorder import LedgerRecorder
    from namisync.workflows import LocationCandidate, LocationCandidateState
    from namisync.workflows.runtime import LocalWorkflowRuntime

    paths.ensure_directories()
    runtime = LocalWorkflowRuntime(paths.ledger, paths.history)
    try:
        clock = runtime.clock
        runtime.initialize_database_contracts()
        admitted = tuple(
            runtime.admit_location_candidate(LocationCandidate.literal(str(path.resolve())))
            for path in (source, target)
        )
        if any(value.state is not LocationCandidateState.RESOLVED for value in admitted):
            raise RuntimeError("headed recent roots were not natively admitted")
        source_value, target_value = admitted
        assert source_value.binding is not None and source_value.root_path is not None
        assert target_value.binding is not None and target_value.root_path is not None
        request = runtime.create_plan_request(
            token * 32,
            source_value.root_path,
            target_value.root_path,
            source_binding=source_value.binding,
            target_binding=target_value.binding,
        )
        result = runtime.open_plan(runtime.prepare_plan(request).checkpoint).run(
            RunContext(lambda _event: None, lambda: None)
        )
        if result.status is not SessionState.COMPLETED:
            raise RuntimeError("headed recent seed plan did not complete")
        plan = runtime.get_plan(request.request_id).plan
        if plan.operations:
            raise RuntimeError("headed recent seed requires empty roots and a no-op plan")
        source_binding = source_value.binding
        target_binding = target_value.binding
    finally:
        runtime.close()

    if (
        not isinstance(plan.source_volume_evidence, VolumeEvidence) or
        not isinstance(plan.target_volume_evidence, VolumeEvidence)
    ):
        raise RuntimeError("headed recent seed lacks native volume evidence")
    now = clock.now()
    run_token = token * 32
    with LedgerRecorder(paths.ledger, clock=clock) as recorder:
        host_id = recorder.ensure_host(HostCommand("setup-headed", "Setup headed", now))
        source_volume = recorder.observe_volume(VolumeCommand(
            plan.source_volume_id, plan.source_volume_evidence, now,
        ))
        target_volume = recorder.observe_volume(VolumeCommand(
            plan.target_volume_id, plan.target_volume_evidence, now,
        ))
        source_id = recorder.ensure_location(LocationCommand(
            source_volume, source_binding.volume_relative_path, now,
        ))
        target_id = recorder.ensure_location(LocationCommand(
            target_volume, target_binding.volume_relative_path, now,
        ))
        mapping_id = recorder.ensure_mapping(MappingCommand(source_id, target_id, now))
        selection = frozenset()
        run = recorder.begin_sync_run(SyncRunCommand(
            run_token,
            host_id,
            mapping_id,
            source_id,
            target_id,
            plan,
            selection,
            selection_digest(selection),
            now,
        ))
        run.finish(FinishRunCommand(
            run_token, SessionState.COMPLETED, RecordingStatus.OK, now,
        ))


def _run(arguments: argparse.Namespace, recorder: _Recorder) -> int:
    from contextlib import ExitStack
    from unittest.mock import patch

    from namisync.interfaces.web import host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    retained: list[object] = []
    original = host._configure_window_appearance
    original_commands = host._production_commands
    ambiguous = arguments.source.parent / "ambiguous-picker"
    picked_source = arguments.source.parent / "picked-source"
    offline_source = arguments.source.parent / ("offline-source-" + "s" * 72)
    offline_target = arguments.source.parent / ("offline-target-" + "t" * 72)
    ambiguous.mkdir(parents=True, exist_ok=True)
    picked_source.mkdir(parents=True, exist_ok=True)
    offline_source.mkdir(parents=True, exist_ok=True)
    offline_target.mkdir(parents=True, exist_ok=True)
    paths = AppPaths.from_root(arguments.data_dir)
    _seed_recent_pair(paths, arguments.source, arguments.target, token="e")
    _seed_recent_pair(paths, offline_source, offline_target, token="d")
    offline_source.rmdir()
    picker_calls = 0

    def picker() -> list[str]:
        nonlocal picker_calls
        picker_calls += 1
        selected = picked_source if picker_calls == 1 else ambiguous
        return [str(selected.resolve())]

    def commands(**kwargs: object) -> object:
        registry = _AmbiguousRegistry(
            kwargs["registry"],
            ambiguous.resolve(),
            (arguments.source.resolve(), arguments.target.resolve()),
            recorder,
        )
        from namisync.interfaces.web.commands import _TaskResponseCodecBinder
        if not isinstance(registry, _TaskResponseCodecBinder):
            raise RuntimeError("headed registry wrapper does not preserve response-codec binding")
        return original_commands(**{**kwargs, "picker": picker, "registry": registry})

    with ExitStack() as stack:
        stack.enter_context(patch.object(host, "_production_commands", commands))
        stack.enter_context(patch.object(
            host,
            "_configure_window_appearance",
            lambda window, *args, **kwargs: _configure_probe(window, recorder, arguments.screenshot_dir.resolve(), arguments.source.resolve(), arguments.target.resolve(), retained, original, *args, **kwargs),
        ))
        exit_code = host.run_desktop(
            paths,
            DesktopInstanceIdentity(arguments.mutex, arguments.title),
            startup_error=lambda _error: None,
        )
    recorder.finish(exit_code)
    return exit_code


def main() -> int:
    arguments = _arguments()
    recorder = _Recorder(EvidencePaths(arguments.evidence_dir.resolve()))
    try:
        return _run(arguments, recorder)
    except BaseException as error:
        recorder.failure("child", error)
        recorder.finish(1)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
