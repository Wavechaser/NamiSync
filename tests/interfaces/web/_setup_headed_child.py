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
  const hasFocusRing = (element) => {
    const style = getComputedStyle(element);
    return style.boxShadow !== "none" ||
      (style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0);
  };
  const hasOnlyInsetShadow = (element) => {
    const shadow = getComputedStyle(element).boxShadow;
    const colors = shadow.match(/rgba?\([^)]*\)/g) ?? [];
    const insets = shadow.match(/\binset\b/g) ?? [];
    return colors.length > 0 && colors.length === insets.length;
  };
  await until(() => document.querySelector("#host-status")?.textContent === "Ready", "host readiness");
  document.querySelector(".nami-task-rail__header .nami-button")?.click();
  const source = await until(() => document.querySelector("#setup-source-path"), "editable source input");
  const setup = source.closest(".nami-setup");
  const target = document.querySelector("#setup-target-path");
  const options = document.querySelector(".nami-setup__options");
  if (!(source instanceof HTMLInputElement) || !(target instanceof HTMLInputElement) ||
      !(setup instanceof HTMLDivElement) || !(options instanceof HTMLDivElement) || source.disabled || target.disabled) {
    throw new Error("editable Setup controls are unavailable");
  }
  const cards = document.querySelectorAll(".nami-setup > .nami-setup__card.nami-card");
  const mode = document.querySelector('.nami-setup__mode[role="radiogroup"]');
  const syncMode = mode?.querySelector('[role="radio"][data-value="sync-plan"]');
  const inventoryMode = mode?.querySelector('[role="radio"][data-value="inventory"]');
  const more = document.querySelector(".nami-setup__more-summary");
  const advanced = document.querySelector("#setup-advanced-options.nami-setup__advanced-options");
  const verifyToggle = document.querySelector('[data-option="verify_after_execute"]');
  const additiveToggle = document.querySelector('[data-option="deletion_policy"]');
  const adsToggle = document.querySelector('[data-option="preserve_ads"]');
  const sourceLine = document.querySelector('[data-purpose="source"] .nami-setup__location-line');
  const sourceLabel = document.querySelector('[for="setup-source-path"]');
  const pathControl = document.querySelector('[data-purpose="source"] .nami-setup__path-control');
  const recentTrigger = document.querySelector("#setup-source-recent-trigger");
  const clearSource = document.querySelector('[data-purpose="source"] .nami-setup__clear');
  const picker = document.querySelector('[data-purpose="source"] .nami-setup__picker');
  const targetStatus = document.querySelector('[data-purpose="target"] .nami-setup__location-status');
  const inventoryAction = Array.from(document.querySelectorAll(".nami-setup__actions button"))
    .find((item) => item.textContent === "Create inventory");
  const planAgainAction = Array.from(document.querySelectorAll(".nami-setup__actions button"))
    .find((item) => item.textContent === "Plan again");
  const missingControls = [];
  if (cards.length !== 2) missingControls.push("cards");
  if (!(syncMode instanceof HTMLButtonElement)) missingControls.push("sync-mode");
  if (!(inventoryMode instanceof HTMLButtonElement)) missingControls.push("inventory-mode");
  if (!(more instanceof HTMLButtonElement)) missingControls.push("more-button");
  else if (more.getAttribute("aria-controls") !== "setup-advanced-options") missingControls.push("more-controls");
  if (!(advanced instanceof HTMLDivElement)) missingControls.push("advanced-panel");
  if (!(sourceLine instanceof HTMLDivElement)) missingControls.push("source-line");
  if (!(sourceLabel instanceof HTMLLabelElement)) missingControls.push("source-label");
  if (!(pathControl instanceof HTMLDivElement)) missingControls.push("path-control");
  if (!(recentTrigger instanceof HTMLButtonElement)) missingControls.push("recent-trigger");
  if (!(picker instanceof HTMLButtonElement)) missingControls.push("picker");
  if (!(verifyToggle instanceof HTMLInputElement)) missingControls.push("verify-toggle");
  if (!(additiveToggle instanceof HTMLInputElement)) missingControls.push("additive-toggle");
  if (!(clearSource instanceof HTMLButtonElement)) missingControls.push("source-clear");
  if (!(adsToggle instanceof HTMLInputElement) || !adsToggle.disabled) missingControls.push("ads-toggle");
  if (!(inventoryAction instanceof HTMLButtonElement)) missingControls.push("inventory-action");
  if (!(planAgainAction instanceof HTMLButtonElement)) missingControls.push("plan-again-action");
  if (!(targetStatus instanceof HTMLParagraphElement)) missingControls.push("target-status");
  if (missingControls.length > 0) throw new Error(`Setup layout controls are unavailable: ${missingControls.join(", ")}`);
  const emptyPathHintHidden = targetStatus.textContent === "" && targetStatus.hidden && !targetStatus.checkVisibility();
  const moreIdleTransparent = getComputedStyle(more).backgroundColor === "rgba(0, 0, 0, 0)";
  const refreshControl = document.querySelector(".nami-setup__refresh-recents");
  const refreshIdleTransparent = getComputedStyle(refreshControl).backgroundColor === "rgba(0, 0, 0, 0)" &&
    refreshControl.textContent === "" && refreshControl.querySelector(".nami-icon--arrow-clockwise") !== null;
  const refreshSquare = Math.abs(refreshControl.getBoundingClientRect().width - refreshControl.getBoundingClientRect().height) <= 1;
  const idlePathStyle = getComputedStyle(source);
  const idlePathAppearance = [idlePathStyle.backgroundColor, idlePathStyle.borderColor, idlePathStyle.borderRadius, idlePathStyle.boxShadow];
  syncMode.focus();
  syncMode.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowRight", bubbles: true}));
  await until(() => inventoryMode.getAttribute("aria-checked") === "true" && document.activeElement === inventoryMode, "keyboard inventory segment");
  inventoryMode.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowLeft", bubbles: true}));
  await until(() => syncMode.getAttribute("aria-checked") === "true" && document.activeElement === syncMode, "keyboard sync segment");
  const closedPrimaryBounds = [verifyToggle.closest("label"), additiveToggle.closest("label"), more]
    .map((item) => item.getBoundingClientRect());
  const advancedClosed = more.getAttribute("aria-expanded") === "false" && advanced.hidden && !advanced.checkVisibility();
  more.click();
  await until(() => more.getAttribute("aria-expanded") === "true" && advanced.checkVisibility(), "More options disclosure");
  const setupBounds = document.querySelector(".nami-setup").getBoundingClientRect();
  const workBounds = document.querySelector(".nami-work-panel__body").getBoundingClientRect();
  const primaryBounds = [verifyToggle.closest("label"), additiveToggle.closest("label"), more]
    .map((item) => item.getBoundingClientRect());
  const optionsBounds = options.getBoundingClientRect();
  const advancedBounds = advanced.getBoundingClientRect();
  const expandedOptionsGap = advancedBounds.top - Math.max(...primaryBounds.map((rect) => rect.bottom));
  const standardFilter = document.querySelector("#setup-filter");
  if (!(standardFilter instanceof HTMLInputElement)) throw new Error("Setup standard filter input is unavailable");
  const filterIdleStyle = getComputedStyle(standardFilter);
  const filterIdleAppearance = [filterIdleStyle.backgroundColor, filterIdleStyle.borderColor, filterIdleStyle.borderRadius, filterIdleStyle.boxShadow];
  const pathBounds = source.getBoundingClientRect();
  const pathControlBounds = pathControl.getBoundingClientRect();
  const caretBounds = recentTrigger.getBoundingClientRect();
  const pathFillsRoundedControl = Math.abs(pathBounds.left - pathControlBounds.left) <= 1 &&
    Math.abs(pathBounds.right - pathControlBounds.right) <= 1 &&
    parseFloat(getComputedStyle(source).borderRadius) > 0;
  const caretInsidePath = caretBounds.left > pathBounds.left && caretBounds.right < pathBounds.right &&
    caretBounds.top > pathBounds.top && caretBounds.bottom < pathBounds.bottom &&
    parseFloat(getComputedStyle(source).paddingRight) >= caretBounds.width;
  const browseSquare = Math.abs(picker.getBoundingClientRect().width - picker.getBoundingClientRect().height) <= 1;
  const actionBounds = document.querySelector(".nami-setup__actions").getBoundingClientRect();
  const primaryAction = document.querySelector(".nami-setup__primary-action:not([hidden])");
  const pairActions = Array.from(document.querySelectorAll(".nami-setup__pair-action:not([hidden])"));
  const pairActionsRightAligned = primaryAction instanceof HTMLButtonElement && pairActions.length === 2 &&
    primaryAction.getBoundingClientRect().left <= actionBounds.left + 1 &&
    pairActions[0].getBoundingClientRect().left > primaryAction.getBoundingClientRect().right &&
    Math.abs(pairActions[1].getBoundingClientRect().right - actionBounds.right) <= 1;
  const advancedLabelsFollowToggles = Array.from(advanced.querySelectorAll(".nami-setup__option")).every((label) => {
    const control = label.children[0];
    const caption = label.children[1];
    if (label.children.length !== 2 || !(control instanceof HTMLInputElement) ||
        control.getAttribute("role") !== "switch" || !(caption instanceof HTMLSpanElement)) return false;
    const controlBounds = control.getBoundingClientRect();
    const captionBounds = caption.getBoundingClientRect();
    const sharedGap = parseFloat(getComputedStyle(label).columnGap);
    return captionBounds.left >= controlBounds.right &&
      Math.abs((captionBounds.left - controlBounds.right) - sharedGap) <= 1 &&
      captionBounds.top < controlBounds.bottom && captionBounds.bottom > controlBounds.top;
  });
  const filterControls = document.querySelector(".nami-setup__filter-controls");
  const addFilter = filterControls?.querySelector("button");
  const filterBounds = standardFilter.getBoundingClientRect();
  const addFilterBounds = addFilter?.getBoundingClientRect();
  const addFilterInline = addFilter instanceof HTMLButtonElement && addFilterBounds.left > filterBounds.right &&
    addFilterBounds.top < filterBounds.bottom && addFilterBounds.bottom > filterBounds.top;
  const inlineRects = [sourceLabel, source, recentTrigger, picker].map((item) => item.getBoundingClientRect());
  const inlineControls = inlineRects.every((rect) => rect.top < inlineRects[0].bottom && rect.bottom > inlineRects[0].top);
  const browseOutsidePathControl = picker.getBoundingClientRect().left > pathControl.getBoundingClientRect().right;
  const availabilityRows = await until(() => {
    const values = Array.from(document.querySelectorAll(".nami-setup__recent-pair"));
    return values.length === 2 && values.some((row) =>
      row.dataset.sourceAvailability === "online" && row.dataset.targetAvailability === "online") &&
      values.some((row) => row.dataset.sourceAvailability !== row.dataset.targetAvailability) ? values : null;
  }, "online and mixed recent-pair probes");
  const onlinePair = availabilityRows.find((row) => row.dataset.sourceAvailability === "online" && row.dataset.targetAvailability === "online");
  const offlinePair = availabilityRows.find((row) => row.dataset.sourceAvailability !== row.dataset.targetAvailability);
  const offlinePaths = offlinePair.querySelectorAll(".nami-setup__pair-path");
  const recentHeaders = Array.from(document.querySelectorAll(".nami-setup__recent-pair-table th"));
  const pathStyle = getComputedStyle(offlinePaths[0]);
  const mixedStatuses = Array.from(offlinePair.querySelectorAll(".nami-setup__availability"));
  const onlineStatuses = Array.from(onlinePair.querySelectorAll(".nami-setup__availability"));
  const neutralColor = getComputedStyle(document.querySelector(".nami-setup__recent-pair-table th")).color;
  const onlineDot = mixedStatuses.find((item) => item.dataset.availability === "online")?.querySelector(".nami-setup__availability-dot");
  const offlineDot = mixedStatuses.find((item) => item.dataset.availability === "offline")?.querySelector(".nami-setup__availability-dot");
  const onlineSelect = onlinePair.querySelector(".nami-setup__pair-select");
  const offlineSelect = offlinePair.querySelector(".nami-setup__pair-select");
  const mixedStatusBounds = mixedStatuses.map((item) => item.getBoundingClientRect());
  const mixedPathBounds = Array.from(offlinePaths).map((item) => item.getBoundingClientRect());
  const recentTable = document.querySelector(".nami-setup__recent-pair-table");
  const recentHead = recentTable.querySelector("thead");
  const tableStyle = getComputedStyle(recentTable);
  const tokenWitness = document.createElement("span");
  tokenWitness.style.cssText = `border-radius: var(--radius-medium); font-size: var(--font-size-caption);
    line-height: var(--line-height-caption); background: var(--color-neutral-surface-selected);`;
  document.body.append(tokenWitness);
  const tokenStyle = getComputedStyle(tokenWitness);
  const expectedRadius = tokenStyle.borderRadius;
  const expectedFontSize = tokenStyle.fontSize;
  const expectedLineHeight = tokenStyle.lineHeight;
  const expectedHeaderFill = tokenStyle.backgroundColor;
  tokenWitness.style.background = "var(--color-neutral-surface)";
  const expectedDefaultFill = getComputedStyle(tokenWitness).backgroundColor;
  tokenWitness.style.background = "var(--color-neutral-surface-subtle)";
  const expectedSubtleFill = getComputedStyle(tokenWitness).backgroundColor;
  tokenWitness.remove();
  const tableGalleryStyle = tableStyle.borderRadius === expectedRadius && parseFloat(tableStyle.borderWidth) === 0 &&
    tableStyle.overflow === "hidden" && tableStyle.fontSize === expectedFontSize &&
    tableStyle.lineHeight === expectedLineHeight && getComputedStyle(recentHead).backgroundColor === expectedHeaderFill &&
    recentHeaders.every((header) => getComputedStyle(header).fontSize === expectedFontSize &&
      getComputedStyle(header).lineHeight === expectedLineHeight) &&
    availabilityRows.every((row, index) => getComputedStyle(row).backgroundColor ===
      (index % 2 === 0 ? expectedDefaultFill : expectedSubtleFill));
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
  const refusalHint = document.querySelector('[data-purpose="source"] .nami-setup__location-status');
  const refusalHintVisible = refusalHint.checkVisibility() && refusalHint.textContent.length > 0;
  source.focus();
  source.value = __SOURCE__;
  source.dispatchEvent(new Event("input", {bubbles: true}));
  source.dispatchEvent(new Event("blur", {bubbles: true}));
  await until(() => source.dataset.state === "resolved", "corrected typed location admission");
  const populatedPathBounds = source.getBoundingClientRect();
  const populatedCaretBounds = recentTrigger.getBoundingClientRect();
  const clearBounds = clearSource.getBoundingClientRect();
  const clearImmediatelyBeforeCaret = clearBounds.right <= populatedCaretBounds.left &&
    populatedCaretBounds.left - clearBounds.right <= 4.1 && clearBounds.top > populatedPathBounds.top &&
    clearBounds.bottom < populatedPathBounds.bottom;
  clearSource.click();
  await until(() => source.value === "" && source.dataset.state === "unresolved", "clear invalidates admitted source");
  const clearInvalidatesImmediately = source.value === "" && clearSource.hidden && document.activeElement === source;
  source.value = __SOURCE__;
  source.dispatchEvent(new Event("input", {bubbles: true}));
  source.dispatchEvent(new Event("blur", {bubbles: true}));
  await until(() => source.dataset.state === "resolved", "readmitted source after clear");
  const routineReadyHintHidden = Array.from(document.querySelectorAll(".nami-setup__location-status"))
    .every((item) => item.textContent !== "Folder is ready." || !item.checkVisibility());
  picker.focus({focusVisible: false});
  source.focus({focusVisible: true});
  await until(() => hasOnlyInsetShadow(source), "path inset focus underline");
  await Promise.all(source.getAnimations().map((animation) => animation.finished));
  const pathFocusShadow = getComputedStyle(source).boxShadow;
  const pathUsesStandardIdleStyle = idlePathAppearance.every((value, index) => value === filterIdleAppearance[index]);
  const pathHasNoOuterRing = hasOnlyInsetShadow(source) && !hasFocusRing(pathControl);
  standardFilter.focus({focusVisible: true});
  await until(() => hasOnlyInsetShadow(standardFilter), "filter inset focus underline");
  await Promise.all(standardFilter.getAnimations().map((animation) => animation.finished));
  const pathMatchesStandardFocus = getComputedStyle(standardFilter).boxShadow === pathFocusShadow;
  recentTrigger.focus();
  recentTrigger.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowDown", bubbles: true}));
  const recentOption = await until(() => document.querySelector("#setup-source-recent-popup [role=option]:focus"), "keyboard recent option");
  const recentPopup = document.querySelector("#setup-source-recent-popup");
  await until(() => hasFocusRing(recentOption), "recent option keyboard focus ring");
  const popupOptions = Array.from(recentPopup.querySelectorAll("[role=option]"));
  const popupOptionsBorderless = popupOptions.every((item) => parseFloat(getComputedStyle(item).borderWidth) === 0);
  const popupFocusIsExclusive = hasFocusRing(recentOption) && popupOptions
    .filter((item) => item !== recentOption).every((item) => !hasFocusRing(item));
  const dropdownAnchored = recentPopup.parentElement === pathControl &&
    recentPopup.getBoundingClientRect().left >= pathControl.getBoundingClientRect().left &&
    recentPopup.getBoundingClientRect().right <= pathControl.getBoundingClientRect().right;
  document.querySelector(".nami-setup__refresh-recents").click();
  await until(() => onlinePair.dataset.sourceAvailability === "online" && onlinePair.dataset.targetAvailability === "online", "availability refresh completion");
  if (recentTrigger.getAttribute("aria-expanded") !== "true" || document.activeElement !== recentOption) {
    throw new Error("unrelated availability refresh replaced recent-folder focus");
  }
  recentOption.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
  await until(() => recentTrigger.getAttribute("aria-expanded") === "false" && document.activeElement === recentTrigger, "recent Escape return");
  const recentKeyboard = document.activeElement === recentTrigger;
  const filter = standardFilter;
  if (!(filter instanceof HTMLInputElement)) throw new Error("Setup filter is unavailable");
  const hostile = "<img src=x onerror=alert(1)>";
  filter.value = hostile;
  filter.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
  await until(() => Array.from(document.querySelectorAll(".nami-setup__filter-list span"))
    .some((item) => item.textContent === hostile), "inert hostile filter");
  await until(() => onlinePair.dataset.sourceAvailability === "online" && onlinePair.dataset.targetAvailability === "online" && !onlineSelect.disabled, "refreshed online pair");
  onlineSelect.focus({focusVisible: false});
  await sleep(100);
  const pointerFocusStyle = getComputedStyle(onlineSelect);
  const pointerFocusHidden = pointerFocusStyle.boxShadow === "none" &&
    (pointerFocusStyle.outlineStyle === "none" || parseFloat(pointerFocusStyle.outlineWidth) === 0) &&
    getComputedStyle(onlinePair).boxShadow === "none";
  onlineSelect.blur();
  onlineSelect.focus({focusVisible: true});
  await until(() => getComputedStyle(onlinePair).boxShadow !== "none",
  "recent pair keyboard focus ring");
  const keyboardFocusStyle = getComputedStyle(onlineSelect);
  const focusedRowStyle = getComputedStyle(onlinePair);
  const keyboardFocusVisible = focusedRowStyle.boxShadow !== "none" && keyboardFocusStyle.boxShadow === "none";
  const pairRowFocusWhole = focusedRowStyle.boxShadow !== "none" &&
    Array.from(onlinePair.children).every((cell) => getComputedStyle(cell).backgroundColor === "rgba(0, 0, 0, 0)") &&
    getComputedStyle(onlineSelect).backgroundColor === "rgba(0, 0, 0, 0)";
  return {
    editable: true,
    typed_refusal: refusedState,
    typed_retry_resolved: source.dataset.state === "resolved",
    routine_ready_hint_hidden: routineReadyHintHidden,
    empty_path_hint_hidden: emptyPathHintHidden,
    refusal_hint_visible: refusalHintVisible,
    hostile_filter_inert: document.querySelector("img") === null,
    options_visible: options.checkVisibility(),
    two_setup_cards: cards.length === 2,
    card_heading_hierarchy: setup.querySelector(':scope > .nami-setup__card > h2')?.textContent === "Setup" &&
      setup.querySelector('.nami-setup__recent-header > h2')?.textContent === "Recent pairs" &&
      document.querySelector(".nami-work-panel > h2") === null,
    segmented_keyboard: syncMode.getAttribute("aria-checked") === "true",
    recent_dropdown_keyboard: recentKeyboard,
    disclosure_open: more.getAttribute("aria-expanded") === "true" && !advanced.hidden,
    disclosure_closed_initially: advancedClosed,
    setup_aligned_top: Math.abs(setupBounds.top - workBounds.top) <= 2,
    primary_options_one_line: primaryBounds.every((rect) => rect.top < primaryBounds[0].bottom && rect.bottom > primaryBounds[0].top) &&
      primaryBounds[0].left < primaryBounds[1].left && primaryBounds[1].right < primaryBounds[2].left,
    primary_options_stable_open: primaryBounds.every((rect, index) =>
      Math.abs(rect.left - closedPrimaryBounds[index].left) <= 1 &&
      Math.abs(rect.top - closedPrimaryBounds[index].top) <= 1 &&
      Math.abs(rect.width - closedPrimaryBounds[index].width) <= 1),
    primary_options_bounds: {closed: closedPrimaryBounds.map((rect) => rect.toJSON()),
      expanded: primaryBounds.map((rect) => rect.toJSON())},
    advanced_below_full_width: advancedBounds.top >= Math.max(...primaryBounds.map((rect) => rect.bottom)) &&
      Math.abs(advancedBounds.left - optionsBounds.left) <= 1 && Math.abs(advancedBounds.right - optionsBounds.right) <= 1,
    expanded_options_padding: expandedOptionsGap >= 8,
    more_idle_transparent: moreIdleTransparent,
    refresh_icon_transparent: refreshIdleTransparent,
    refresh_square: refreshSquare,
    recent_row_height: onlinePair.getBoundingClientRect().height,
    advanced_filters_visible: document.querySelector(".nami-setup__filters").checkVisibility(),
    advanced_labels_follow_toggles: advancedLabelsFollowToggles,
    add_filter_inline: addFilterInline,
    path_uses_standard_idle_style: pathUsesStandardIdleStyle,
    path_matches_standard_focus: pathMatchesStandardFocus,
    path_has_no_outer_ring: pathHasNoOuterRing,
    path_fills_rounded_control: pathFillsRoundedControl,
    caret_inside_path_with_text_space: caretInsidePath,
    clear_immediately_before_caret: clearImmediatelyBeforeCaret,
    clear_invalidates_immediately: clearInvalidatesImmediately,
    browse_square: browseSquare,
    pair_actions_right_aligned: pairActionsRightAligned,
    inline_location_controls: inlineControls,
    browse_outside_path_control: browseOutsidePathControl,
    dropdown_anchored: dropdownAnchored,
    dropdown_rerender_focus_restored: recentKeyboard,
    popup_options_borderless: popupOptionsBorderless,
    popup_focus_is_exclusive: popupFocusIsExclusive,
    picker_icon_only: picker.textContent === "" && picker.getAttribute("aria-label") === "Browse for source folder",
    advanced_switches: advanced.querySelectorAll('input[role="switch"]').length === 5,
    primary_options_visible: verifyToggle.checkVisibility() && additiveToggle.checkVisibility() &&
      verifyToggle.closest("label").nextElementSibling === additiveToggle.closest("label") &&
      verifyToggle.closest("label").textContent === "Verify execution" && additiveToggle.closest("label").textContent === "Additive sync",
    sync_inapplicable_actions_hidden: !inventoryAction.checkVisibility() && !planAgainAction.checkVisibility(),
    recent_pair_online_offline: onlineStatuses.every((item) => item.dataset.availability === "online"),
    mixed_pair_endpoint_truths: mixedStatuses.map((item) => [item.dataset.endpoint, item.dataset.availability, item.textContent]),
    recent_pair_two_columns: recentHeaders.map((item) => item.textContent).join("|") === "Folders|Availability",
    table_gallery_style: tableGalleryStyle,
    endpoint_statuses_align_with_paths: mixedStatusBounds.length === 2 && mixedPathBounds.length === 2 &&
      mixedStatusBounds.every((rect, index) => Math.abs(rect.top - mixedPathBounds[index].top) <= 2),
    offline_pair_disabled: offlinePair.getAttribute("aria-disabled") === "true",
    pair_two_line_paths: offlinePaths.length === 2 && offlinePaths[0].getBoundingClientRect().top < offlinePaths[1].getBoundingClientRect().top,
    pair_paths_truncated: pathStyle.textOverflow === "ellipsis" && pathStyle.overflow === "hidden" &&
      Array.from(offlinePaths).every((item) => item.scrollWidth > item.clientWidth && item.title === item.textContent),
    availability_dots_distinct: getComputedStyle(onlineDot).backgroundColor !== getComputedStyle(offlineDot).backgroundColor,
    availability_text_neutral: [...mixedStatuses, ...onlineStatuses].every((item) => getComputedStyle(item).color === neutralColor),
    pointer_focus_hidden: pointerFocusHidden,
    keyboard_focus_visible: keyboardFocusVisible,
    pair_row_focus_whole: pairRowFocusWhole,
    pair_button_focused: document.activeElement === onlineSelect,
    source_node_id: source.id,
  };
})()
"""


_POINTER_PREPARE_SCRIPT = r"""
(() => {
  const source = document.querySelector("#setup-source-path");
  const clear = document.querySelector(".nami-setup__clear");
  const online = document.querySelector('.nami-setup__recent-pair[aria-disabled="false"]');
  const disabled = document.querySelector('.nami-setup__recent-pair[aria-disabled="true"]');
  const onlineStatus = online?.querySelector(".nami-setup__availability")?.closest("td");
  const disabledStatus = disabled?.querySelector(".nami-setup__availability")?.closest("td");
  if (!(source instanceof HTMLInputElement) || !(clear instanceof HTMLButtonElement) ||
      !(online instanceof HTMLTableRowElement) || !(disabled instanceof HTMLTableRowElement) ||
      !(onlineStatus instanceof HTMLTableCellElement) || !(disabledStatus instanceof HTMLTableCellElement)) {
    throw new Error("native pointer targets are unavailable");
  }
  const api = window.pywebview?.api;
  if (api === undefined || typeof api.dispatch !== "function") throw new Error("native dispatch is unavailable");
  const dispatch = api.dispatch;
  const center = (element) => {
    const rect = element.getBoundingClientRect();
    return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
  };
  const resolveColor = (token) => {
    const witness = document.createElement("span");
    witness.style.backgroundColor = `var(${token})`;
    document.body.append(witness);
    const color = getComputedStyle(witness).backgroundColor;
    witness.remove();
    return color;
  };
  source.scrollIntoView({block: "center"});
  source.focus();
  window.__setupPointerProbe = {
    api, dispatch, admits: 0,
    online, disabled,
    onlineBase: getComputedStyle(online).backgroundColor,
    disabledBase: getComputedStyle(disabled).backgroundColor,
    hoverExpected: resolveColor("--color-neutral-surface-hover"),
    pressedExpected: resolveColor("--color-neutral-surface-pressed"),
  };
  api.dispatch = function(request) {
    try {
      if (typeof request === "string" && JSON.parse(request).command === "admit_location") {
        window.__setupPointerProbe.admits += 1;
      }
    } catch (_error) {}
    return dispatch.apply(api, arguments);
  };
  return {clear: center(clear)};
})()
"""


_POINTER_ONLINE_POINT_SCRIPT = r"""
(() => {
  const cell = window.__setupPointerProbe.online.querySelector(".nami-setup__availability").closest("td");
  cell.scrollIntoView({block: "center"});
  const rect = cell.getBoundingClientRect();
  return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
})()
"""


_POINTER_DISABLED_POINT_SCRIPT = r"""
(() => {
  const cell = window.__setupPointerProbe.disabled.querySelector(".nami-setup__availability").closest("td");
  cell.scrollIntoView({block: "center"});
  const rect = cell.getBoundingClientRect();
  return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
})()
"""


_POINTER_CLEAR_RESULT_SCRIPT = r"""
(async () => {
  const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
  const probe = window.__setupPointerProbe;
  const source = document.querySelector("#setup-source-path");
  const local = source instanceof HTMLInputElement && source.value === "" &&
    source.dataset.state === "unresolved" && document.activeElement === source && probe.admits === 0;
  probe.api.dispatch = probe.dispatch;
  source.value = __SOURCE__;
  source.dispatchEvent(new Event("input", {bubbles: true}));
  source.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
  for (let attempt = 0; attempt < 400 && source.dataset.state !== "resolved"; attempt += 1) await sleep(25);
  if (source.dataset.state !== "resolved") throw new Error("source admission was not restored after clear pointer probe");
  return {ok: local};
})()
"""


_POINTER_HOVER_RESULT_SCRIPT = r"""
(async () => {
  await new Promise((resolve) => setTimeout(resolve, 150));
  const probe = window.__setupPointerProbe;
  const row = probe.online;
  const style = getComputedStyle(row);
  const transparent = "rgba(0, 0, 0, 0)";
  probe.hover = style.backgroundColor;
  probe.hoverOk = probe.hover === probe.hoverExpected && probe.hover !== probe.onlineBase &&
    Array.from(row.children).every((cell) => getComputedStyle(cell).backgroundColor === transparent) &&
    getComputedStyle(row.querySelector(".nami-setup__pair-select")).backgroundColor === transparent;
  return {ok: probe.hoverOk};
})()
"""


_POINTER_PRESSED_RESULT_SCRIPT = r"""
(async () => {
  await new Promise((resolve) => setTimeout(resolve, 150));
  const probe = window.__setupPointerProbe;
  probe.pressedOk = getComputedStyle(probe.online).backgroundColor === probe.pressedExpected &&
    probe.pressedExpected !== probe.hover;
  return {ok: probe.pressedOk};
})()
"""


_POINTER_DISABLED_RESULT_SCRIPT = r"""
(async () => {
  await new Promise((resolve) => setTimeout(resolve, 150));
  const probe = window.__setupPointerProbe;
  const style = getComputedStyle(probe.disabled);
  const disabledOk = style.backgroundColor === probe.disabledBase && style.boxShadow === "none";
  const result = Boolean(probe.hoverOk && probe.pressedOk && disabledOk);
  delete window.__setupPointerProbe;
  return {ok: result};
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
  const frozenRecent = document.querySelector("#setup-source-recent-trigger");
  const disabledIconControlsTransparent = [frozenRecent, picker].every((control) => {
    const style = getComputedStyle(control);
    return control instanceof HTMLButtonElement && control.disabled &&
      style.backgroundColor === "rgba(0, 0, 0, 0)" && style.borderColor === "rgba(0, 0, 0, 0)";
  });
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
    frozen_switches_disabled: frozenSwitches.length === 7 && frozenSwitches.every((input) => input.disabled),
    frozen_pairs_disabled: frozenPairs.length === 2 && frozenPairs.every((button) => button.disabled),
    frozen_mode_hidden: frozenModeHidden,
    disabled_icon_controls_transparent: disabledIconControlsTransparent,
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
    const value = document.querySelector('.nami-setup__recent-pair[data-source-availability="online"][data-target-availability="online"]');
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
  const inventoryPlan = Array.from(document.querySelectorAll(".nami-setup__actions button"))
    .find((button) => button.textContent === "Create plan");
  const inventoryActionVisibility = inventory.checkVisibility() && !inventoryPlan.checkVisibility();
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
    inventory_action_visibility: inventoryActionVisibility,
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
  const cards = Array.from(document.querySelectorAll(".nami-task-rail__items .nami-task-card"));
  let reconstructed = false;
  const observations = [];
  for (const card of cards) {
    const title = card.querySelector(".nami-task-card__title")?.textContent;
    if (!title) throw new Error("reloaded task lacks its title");
    card.click();
    let source = null;
    for (let attempt = 0; attempt < 80 && source === null; attempt += 1) {
      const value = document.querySelector("#setup-source-path");
      if (document.querySelector(".nami-work-panel")?.getAttribute("aria-label") === `Work area — ${title}` &&
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


def _devtools(
    core: object,
    method: str,
    parameters: dict[str, object],
    retained: list[object],
    continuation: object,
    on_failure: object,
) -> None:
    from System import Action

    task = core.CallDevToolsProtocolMethodAsync(method, json.dumps(parameters))

    def completed() -> None:
        try:
            if task.IsFaulted or task.IsCanceled:
                raise RuntimeError(f"native {method} call failed")
            continuation(task)
        except BaseException as error:
            on_failure(error)

    action = Action(completed)
    retained.append(action)
    task.GetAwaiter().OnCompleted(action)


def _pointer_checks(
    core: object,
    source: Path,
    retained: list[object],
    continuation: object,
    on_failure: object,
) -> None:
    evaluate = lambda expression, callback: _devtools(
        core,
        "Runtime.evaluate",
        {"expression": expression, "awaitPromise": True, "returnByValue": True},
        retained,
        callback,
        on_failure,
    )

    def mouse(event_type: str, point: dict[str, object], callback: object, *, pressed: bool = False) -> None:
        parameters: dict[str, object] = {
            "type": event_type,
            "x": point["x"],
            "y": point["y"],
            "button": "left" if event_type != "mouseMoved" else "none",
            "buttons": 1 if pressed else 0,
        }
        if event_type != "mouseMoved":
            parameters["clickCount"] = 1
        _devtools(core, "Input.dispatchMouseEvent", parameters, retained, callback, on_failure)

    prepare = _POINTER_PREPARE_SCRIPT

    def result_ok(task: object) -> bool:
        result = _runtime_value(task)
        return type(result) is dict and result.get("ok") is True

    def prepared(task: object) -> None:
        points = _runtime_value(task)
        if type(points) is not dict or type(points.get("clear")) is not dict:
            raise RuntimeError("native pointer coordinates are invalid")

        def clear_released(_task: object) -> None:
            clear_script = _POINTER_CLEAR_RESULT_SCRIPT.replace("__SOURCE__", json.dumps(str(source)))

            def clear_checked(clear_task: object) -> None:
                clear_local = result_ok(clear_task)

                def online_located(online_task: object) -> None:
                    online = _runtime_value(online_task)
                    if type(online) is not dict:
                        raise RuntimeError("native online-row coordinate is invalid")

                    def online_moved(_task: object) -> None:
                        def hover_checked(hover_task: object) -> None:
                            hover_ok = result_ok(hover_task)

                            def online_pressed(_task: object) -> None:
                                def pressed_checked(pressed_task: object) -> None:
                                    pressed_ok = result_ok(pressed_task)

                                    def online_released(_task: object) -> None:
                                        def disabled_located(disabled_task: object) -> None:
                                            disabled = _runtime_value(disabled_task)
                                            if type(disabled) is not dict:
                                                raise RuntimeError("native disabled-row coordinate is invalid")

                                            def disabled_moved(_task: object) -> None:
                                                def disabled_checked(result_task: object) -> None:
                                                    pair_states = result_ok(result_task)
                                                    continuation({
                                                        "clear_pointer_local": clear_local,
                                                        "pair_pointer_states": bool(hover_ok and pressed_ok and pair_states),
                                                    })

                                                evaluate(_POINTER_DISABLED_RESULT_SCRIPT, disabled_checked)

                                            mouse("mouseMoved", disabled, disabled_moved)

                                        evaluate(_POINTER_DISABLED_POINT_SCRIPT, disabled_located)

                                    mouse("mouseReleased", online, online_released)

                                evaluate(_POINTER_PRESSED_RESULT_SCRIPT, pressed_checked)

                            mouse("mousePressed", online, online_pressed, pressed=True)

                        evaluate(_POINTER_HOVER_RESULT_SCRIPT, hover_checked)

                    mouse("mouseMoved", online, online_moved)

                evaluate(_POINTER_ONLINE_POINT_SCRIPT, online_located)

            evaluate(clear_script, clear_checked)

        def clear_pressed(_task: object) -> None:
            mouse("mouseReleased", points["clear"], clear_released)

        def clear_moved(_task: object) -> None:
            mouse("mousePressed", points["clear"], clear_pressed, pressed=True)

        mouse("mouseMoved", points["clear"], clear_moved)

    evaluate(prepare, prepared)


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

            def pointer_done(pointer: dict[str, bool]) -> None:
                editable.update(pointer)
                _capture(
                    core, screenshot_dir / "editable-expanded.png", retained,
                    lambda: _collapse_and_capture_editable(
                        core, screenshot_dir, retained, begin_frozen,
                        lambda error: recorder.failure("editable-screenshot", error),
                    ),
                    lambda error: recorder.failure("editable-expanded-screenshot", error),
                )

            _pointer_checks(
                core,
                source,
                retained,
                pointer_done,
                lambda error: recorder.failure("editable-pointer", error),
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
        "expression": 'if (document.querySelector(".nami-setup__more-summary").getAttribute("aria-expanded") === "true") document.querySelector(".nami-setup__more-summary").click();',
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
