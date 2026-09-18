"""Installed-wheel child for the M1-4 process-live task shell witness."""

from __future__ import annotations

import argparse
import base64
import importlib.metadata
import json
import sys
import threading
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from types import MethodType
from typing import Any, Callable
from unittest.mock import patch

from _headed_evidence import EvidencePaths, EvidencePublisher
from _plan_again_trace import (
    PlanAgainHostTrace,
    trace_registry_plan_again,
    traced_plan_again_commands,
    validate_trace_snapshot,
)
from _startup_test_support import headed_command_extension


_FAILURE_STAGES = frozenset(
    {
        "page_probe",
        "page_initial",
        "page_initial_ready",
        "page_initial_capacity",
        "page_initial_basic_close",
        "page_initial_retry",
        "page_initial_navigation",
        "page_initial_navigation_cleanup",
        "page_initial_navigation_recorded",
        "page_initial_reinjection_armed",
        "page_initial_reinjection_wait",
        "page_reinjected",
        "page_busy",
        "page_terminal_first",
        "page_terminal_second",
        "page_plan_review",
        "page_plan_review_plan_surface",
        "page_plan_review_plan_offset",
        "page_plan_review_plan_notice",
        "page_plan_review_plan_refused",
        "page_plan_review_plan_release",
        "page_plan_review_plan_again",
        "page_plan_review_plan_force",
        "page_plan_review_plan_ack",
        "page_plan_review_plan_execute",
        "page_plan_review_plan_live",
        "page_plan_review_plan_paused",
        "page_plan_review_plan_resumed",
        "page_plan_review_plan_empty_prepare",
        "page_plan_review_plan_empty_wait",
        "child",
    }
)
_FAILURE_TYPES = frozenset(
    {"AssertionError", "AttributeError", "RuntimeError", "TypeError", "ValueError", "Error"}
)
_COMPLETE_TEXT = "Task shell gate complete"
_DRIVER_DIAGNOSTIC_KEYS = frozenset(
    {
        "actual_control_checkpoint", "active_element", "cdp_canceled", "cdp_faulted",
        "authoritative_selection_state", "task_delivery_session_changed", "task_delivery_session_released",
        "service_session_state", "task_delivery_active_drain_present",
        "task_delivery_session_state", "task_delivery_start_identity_count",
        "task_delivery_terminal_delivered", "task_delivery_terminal_record_present", "dialog_open",
        "document_has_focus", "execute_disabled", "execute_focused", "execute_hidden",
        "last_driver_step", "last_method", "page_confirmation_stage",
        "preflight_hook_count",
        "runtime_has_exception_details", "runtime_result_type", "trusted_click_count",
        "trusted_keydown_count", "trusted_keyup_count",
    }
)


_COMMON_JS = r"""
const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
async function until(predicate, label) {
  for (let attempt = 0; attempt < 300; attempt += 1) {
    const value = predicate();
    if (value) return value;
    await sleep(25);
  }
  throw new Error(`timed out waiting for ${label}`);
}
async function untilAsync(predicate, label) {
  for (let attempt = 0; attempt < 300; attempt += 1) {
    const value = await predicate();
    if (value) return value;
    await sleep(25);
  }
  throw new Error(`timed out waiting for ${label}`);
}
function rows() { return Array.from(document.querySelectorAll(".nami-task-rail__row")); }
function rowByTitle(title) {
  return rows().find((row) => row.querySelector(".nami-task-card")?.dataset.taskLabel === title);
}
function selectedTitle() {
  return document.querySelector('.nami-task-card[aria-current="page"]')?.dataset.taskLabel ?? null;
}
function workTitle() {
  const label = document.querySelector(".nami-work-panel")?.getAttribute("aria-label") ?? "";
  return label.startsWith("Work area — ") ? label.slice("Work area — ".length) : null;
}
function planGeometryFor(review) {
  const viewport = review?.querySelector(".nami-plan-review__rows");
  const workBody = document.querySelector(".nami-work-panel__body");
  const planActions = review?.querySelector(".nami-plan-review__actions");
  const settingRows = [...review.querySelectorAll(".nami-plan-review__settings > span")];
  return {
    documentFitsViewport: document.documentElement.scrollHeight <= innerHeight + 1,
    workBodyFitsViewport: workBody instanceof HTMLElement
      && workBody.scrollHeight <= workBody.clientHeight + 1,
    tableAbsorbsHeight: viewport instanceof HTMLElement
      && viewport.clientHeight > 0 && viewport.scrollHeight >= viewport.clientHeight,
    footerVisible: planActions instanceof HTMLElement && planActions.checkVisibility()
      && planActions.getBoundingClientRect().bottom <= innerHeight + 1,
    semanticSettingsVisible: settingRows.length === 2 && settingRows.every((row) =>
      row.textContent.length > 0 && row.getBoundingClientRect().width > 0
      && row.getBoundingClientRect().right <= review.getBoundingClientRect().right),
  };
}
function statusFor(title) { return rowByTitle(title)?.querySelector(".nami-task-card__title")?.textContent ?? null; }
function detailFor(title) { return rowByTitle(title)?.querySelector(".nami-task-card__status")?.textContent ?? null; }
function clickNew() { document.querySelector(".nami-task-rail__create")?.click(); }
function clickSelect(title) { rowByTitle(title)?.querySelector(".nami-task-card")?.click(); }
function clickClose(title) { rowByTitle(title)?.querySelector(".nami-task-rail__close")?.click(); }
function resolvedBackground(variable) {
  const witness = document.createElement("span");
  witness.style.background = `var(${variable})`;
  document.body.append(witness);
  const value = getComputedStyle(witness).backgroundColor;
  witness.remove();
  return value;
}
function hasFocusRing(element) {
  const style = getComputedStyle(element);
  return style.boxShadow !== "none" ||
    (style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0);
}
function selectionAppearance(title) {
  const row = rowByTitle(title);
  const card = row?.querySelector(".nami-task-card");
  const close = row?.querySelector(".nami-task-rail__close");
  if (card === undefined || card === null) return null;
  const style = getComputedStyle(card);
  const marker = getComputedStyle(card, "::before");
  return {
    current: card.ariaCurrent,
    persistentFill: style.backgroundColor === resolvedBackground("--color-selection-highlight"),
    markerWidth: marker.width,
    markerHeight: marker.height,
    markerAccent: marker.backgroundColor === resolvedBackground("--color-accent-fill"),
    closeLabel: close?.getAttribute("aria-label") ?? null,
    closeEnabled: close?.disabled === false,
  };
}
function selectedAppearanceSettled(title) {
  const appearance = selectionAppearance(title);
  return appearance?.current === "page" &&
    appearance.persistentFill === true &&
    appearance.markerWidth === "3px" &&
    appearance.markerAccent === true;
}
function selectionCleared(title) {
  const card = rowByTitle(title)?.querySelector(".nami-task-card");
  if (card === undefined || card === null) return false;
  const marker = getComputedStyle(card, "::before");
  return card.ariaCurrent === "false" &&
    getComputedStyle(card).backgroundColor === resolvedBackground("--color-neutral-subtle-background") &&
    marker.content === "none";
}
function railGeometry(title) {
  const row = rowByTitle(title);
  const card = row?.querySelector(".nami-task-card");
  const close = row?.querySelector(".nami-task-rail__close");
  if (!(row instanceof HTMLElement) || !(card instanceof HTMLButtonElement) || !(close instanceof HTMLButtonElement)) return null;
  const rowRect = row.getBoundingClientRect();
  const cardRect = card.getBoundingClientRect();
  const closeRect = close.getBoundingClientRect();
  const create = document.querySelector(".nami-task-rail__create");
  const createRect = create.getBoundingClientRect();
  const headingRect = document.querySelector(".nami-task-rail__header h2").getBoundingClientRect();
  return {
    fullWidth: Math.abs(cardRect.left - rowRect.left) <= 1 && Math.abs(cardRect.right - rowRect.right) <= 1,
    closeInset: closeRect.left > cardRect.left && closeRect.right < cardRect.right,
    siblingDismiss: close.parentElement === row && close.parentElement === card.parentElement,
    dismissTransparent: getComputedStyle(close).backgroundColor === "rgba(0, 0, 0, 0)",
    createAligned: Math.abs((createRect.top + createRect.bottom) / 2 - (headingRect.top + headingRect.bottom) / 2) <= 1,
    createLargeIcon: getComputedStyle(create.querySelector(".nami-icon")).width === "24px",
  };
}
let rawSequence = 0;
async function control(action, value = null) {
  rawSequence += 1;
  const requestId = rawSequence.toString(16).padStart(32, "0");
  const api = window.pywebview?.api;
  if (typeof api?.dispatch !== "function") throw new Error("native bridge is unavailable");
  const native = await api.dispatch(JSON.stringify({
    schema_version: 1,
    request_id: requestId,
    command: "task_shell_test_control",
    payload: { action, value },
  }));
  if (native === null || typeof native !== "object") throw new Error("invalid native response");
  const response = JSON.parse(JSON.stringify(native.response));
  if (native.response_token !== null) await api.dispatch(`ack:${native.response_token}`);
  if (response?.request_id !== requestId || response?.ok !== true) {
    throw new Error(`test control refused ${action}`);
  }
  return response.result;
}
async function ready() {
  await until(() => document.querySelector("#host-status")?.textContent === "Ready", "Ready");
}
"""


_INITIAL_SCRIPT = _COMMON_JS + r"""
(async () => {
  await ready();
  await until(() => rows().length === 46, "46 seeded tasks");
  await control("checkpoint", "ready");
  clickNew();
  await until(() => rows().length === 47, "first new task");
  clickNew();
  await until(() => rows().length === 48, "second new task");
  const newest = rows().slice(0, 3).map((row) => row.querySelector(".nami-task-card")?.dataset.taskLabel);
  const setup = await until(() => {
    const value = document.querySelector(".nami-work-panel__body .nami-setup");
    return value instanceof HTMLElement && value.checkVisibility() ? value : null;
  }, "live Setup form");
  const setupVisible = setup.querySelector("#setup-source-path") instanceof HTMLInputElement &&
    setup.querySelector("#setup-target-path") instanceof HTMLInputElement;
  const idleGeometry = railGeometry("Task 47");
  const focusCard = rowByTitle("Task 47")?.querySelector(".nami-task-card");
  focusCard.focus({focusVisible: false});
  await sleep(100);
  const pointerFocusHidden = !hasFocusRing(focusCard);
  focusCard.blur();
  focusCard.focus({focusVisible: true});
  await until(() => hasFocusRing(focusCard), "task card keyboard focus ring");
  const keyboardFocusVisible = hasFocusRing(focusCard);
  clickNew();
  await until(() => document.querySelector("#host-status")?.textContent?.includes("could not be created"), "capacity refusal");
  const refusedCount = rows().length;
  const taskList = document.querySelector(".nami-task-rail__items");
  const settingsButton = document.querySelector(".nami-task-rail__settings");
  const settingsBefore = settingsButton.getBoundingClientRect();
  taskList.scrollTop = taskList.scrollHeight;
  const independentRail = taskList.scrollTop > 0 &&
    Math.abs(settingsButton.getBoundingClientRect().top - settingsBefore.top) <= 1 &&
    settingsBefore.bottom <= innerHeight &&
    taskList.getBoundingClientRect().bottom <= settingsBefore.top &&
    document.documentElement.scrollHeight <= innerHeight + 1;
  taskList.scrollTop = 0;
  const retainedSource = document.querySelector("#setup-source-path");
  retainedSource.value = "C:\\retained-settings-draft";
  retainedSource.dispatchEvent(new Event("input", {bubbles: true}));
  settingsButton.click();
  await until(() => document.querySelector("#theme-mode-trigger")?.disabled === false, "Settings theme readiness");
  const settingsSurface = document.querySelector(".nami-work-panel").getAttribute("aria-label") === "Settings" &&
    document.querySelectorAll("#settings-view > .nami-card").length === 2 &&
    document.querySelector("#settings-view").textContent.includes('0.1.0 "Gertrud"') &&
    rows().length === 48 && settingsButton.getAttribute("aria-current") === "page";
  clickSelect("Task 48");
  await until(() => workTitle() === "Task 48", "return from Settings");
  const settingsDraftRetained = document.querySelector("#setup-source-path") === retainedSource &&
    retainedSource.value === "C:\\retained-settings-draft";
  await control("checkpoint", "capacity");
  clickSelect("Task 47");
  await until(() => selectedTitle() === "Task 47" && workTitle() === "Task 47", "older task selection");
  await until(() => selectedAppearanceSettled("Task 47"), "older task selected appearance");
  const olderAppearance = selectionAppearance("Task 47");
  clickSelect("Task 48");
  await until(() => selectedTitle() === "Task 48" && workTitle() === "Task 48", "newer task return");
  await until(() => selectedAppearanceSettled("Task 48") && selectionCleared("Task 47"), "transferred task selection appearance");
  const newerAppearance = selectionAppearance("Task 48");
  const olderSelectionCleared = selectionCleared("Task 47");
  clickClose("Task 48");
  await until(() => rows().length === 47 && rowByTitle("Task 48") === undefined, "successful close");
  await control("checkpoint", "basic_close");

  await control("arm_close_failure");
  clickClose("Task 47");
  await until(() => rowByTitle("Task 47")?.querySelector(".nami-task-rail__close")?.getAttribute("aria-label") === "Retry close for Task 47", "failed close recovery");
  const retainedAfterFailure = rows().length === 47 && detailFor("Task 47") === "Close did not finish. Retry.";
  clickClose("Task 47");
  await until(() => rows().length === 46 && rowByTitle("Task 47") === undefined, "close retry");
  await control("checkpoint", "retry");

  await control("arm_create_delay");
  clickNew();
  await untilAsync(async () => (await control("status")).create_waiting === true, "delayed create");
  clickSelect("Task 46");
  await control("release_create");
  await until(() => rows().length === 47, "delayed create return");
  const navigationStayed = selectedTitle() === "Task 46" && workTitle() === "Task 46";
  await control("checkpoint", "navigation");
  clickClose("Task 49");
  await until(() => rows().length === 46, "delayed create cleanup");
  await control("checkpoint", "navigation_cleanup");

  await control("record", { initial: { newest, setupVisible, refusedCount, retainedAfterFailure, navigationStayed, olderAppearance, newerAppearance, olderSelectionCleared, idleGeometry, pointerFocusHidden, keyboardFocusVisible, independentRail, settingsSurface, settingsDraftRetained } });
  await control("checkpoint", "navigation_recorded");
  await control("arm_create_delay");
  await control("checkpoint", "reinjection_armed");
  clickNew();
  await untilAsync(async () => (await control("status")).create_waiting === true, "reinjection create");
  await control("checkpoint", "reinjection_wait");
  await control("set_stage", "reinjected");
  location.reload();
})()
"""


_REINJECTED_SCRIPT = _COMMON_JS + r"""
(async () => {
  await ready();
  await until(() => rows().length === 47, "reinjected task list");
  const evidence = {
    count: rows().length,
    newest: rows()[0]?.querySelector(".nami-task-card")?.dataset.taskLabel ?? null,
    selected: selectedTitle(),
    work: workTitle(),
  };
  clickClose("Task 47");
  await until(() => rows().length === 46, "reinjected task cleanup");
  await control("record", { reinjected: evidence });
  await control("start_busy");
  await control("set_stage", "busy");
  location.reload();
})()
"""


_BUSY_SCRIPT = _COMMON_JS + r"""
(async () => {
  await ready();
  await until(() => rows().length === 47 && statusFor("Task 47") === "Planning", "busy task");
  clickClose("Task 47");
  await until(() => detailFor("Task 47") === "Canceling and closing…", "pending cancellation");
  const pending = await control("status");
  const retainedPending = rows().length === 47 && rowByTitle("Task 47") !== undefined;
  await control("settle_busy");
  await until(() => rows().length === 46, "settled busy close");
  const settled = await control("status");
  await control("record", { busy: { pending, retainedPending, settled } });
  await control("arm_release_delay");
  await control("start_terminal");
  await control("set_stage", "terminal_first");
  location.reload();
})()
"""


_TERMINAL_FIRST_SCRIPT = _COMMON_JS + r"""
(async () => {
  await ready();
  await until(() => rows().length === 47 && statusFor("Task 47") === "Completed", "terminal presentation");
  await untilAsync(async () => (await control("status")).release_waiting === true, "blocked terminal release");
  const before = await control("status");
  await control("record", { terminal_first: { count: rows().length, status: statusFor("Task 47"), before } });
  await control("set_stage", "terminal_second");
  location.reload();
})()
"""


_TERMINAL_SECOND_SCRIPT = _COMMON_JS + r"""
(async () => {
  await ready();
  await until(() => rows().length === 47 && statusFor("Task 47") === "Completed", "terminal reinjection");
  await untilAsync(async () => (await control("status")).release_calls >= 2, "reconstructed terminal release");
  const retained = await control("status");
  await control("release_cleanup");
  await untilAsync(async () => (await control("status")).session_released === true, "terminal release");
  const released = await control("status");
  clickClose("Task 47");
  await until(() => rows().length === 46, "terminal explicit close");
  const closed = await control("status");
  const report = {
    terminal_second: {
      count_before_close: 47,
      status_before_close: "Completed",
      retained,
      released,
      closed,
    },
  };
  await control("record", report);
  await control("start_plan_review");
  await control("set_stage", "plan_review");
  location.reload();
})()
"""


_PLAN_REVIEW_SCRIPT = _COMMON_JS + r"""
(async () => {
  window.__namiConfirmationStage = "starting";
  window.__namiConfirmationInputEvidence = null;
  window.__namiConfirmationTrustedInput = {keydown: 0, keyup: 0, click: 0};
  for (const type of ["keydown", "keyup", "click"]) {
    document.addEventListener(type, (event) => {
      if (event.isTrusted) window.__namiConfirmationTrustedInput[type] += 1;
    }, true);
  }
  await ready();
  await until(() => rows().length === 47 && statusFor("Task 47") === "Plan ready", "reviewed plan task");
  await until(() => document.querySelector(".nami-plan-review"), "Plan review surface");
  await until(() => document.querySelector(".nami-plan-review__rows [data-node-id]"), "Plan review rows");
  await control("checkpoint", "plan_surface");
  const review = document.querySelector(".nami-plan-review");
  const facts = review.querySelector(".nami-plan-review__summary").textContent;
  const viewport = review.querySelector(".nami-plan-review__rows");
  const planGeometry = planGeometryFor(review);
  viewport.scrollTop = 280 * 24;
  viewport.dispatchEvent(new Event("scroll"));
  await until(() => Number(viewport.querySelector("[data-node-id]")?.ariaRowIndex) > 2, "offset Plan window");
  await control("checkpoint", "plan_offset");
  const firstOffsetRow = viewport.querySelector("[data-node-id]");
  const topSpacer = viewport.querySelector(".nami-plan-review__spacer");
  const expectedOffset = Number(firstOffsetRow.ariaRowIndex) - 2;
  const spacerAligned = parseFloat(topSpacer.style.blockSize) === expectedOffset * 24;
  const table = review.querySelector(".nami-plan-review__list");
  const tableCard = review.querySelector(".nami-plan-review__table-card");
  tableCard.style.inlineSize = "80rem";
  const tableHeader = review.querySelector(".nami-file-list__header");
  const tableCells = [...tableHeader.children];
  const rowCells = [...firstOffsetRow.children];
  const columnsAligned = tableCells.length === 7 && rowCells.length === 7
    && tableCells.every((cell, index) => Math.abs(
      cell.getBoundingClientRect().left - rowCells[index].getBoundingClientRect().left,
    ) <= 0.5);
  const headerScrollClear = getComputedStyle(tableHeader).overflowY === "hidden"
    && getComputedStyle(viewport).overflowY === "auto"
    && getComputedStyle(tableHeader).scrollbarGutter === "stable"
    && getComputedStyle(viewport).scrollbarGutter === "stable";
  const resizeHandle = review.querySelector('.nami-file-list__column-resizer[data-column="size"]');
  const sizeBefore = tableCells[2].getBoundingClientRect().width;
  resizeHandle.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, clientX: 100 }));
  window.dispatchEvent(new PointerEvent("pointermove", { clientX: 108 }));
  window.dispatchEvent(new PointerEvent("pointerup", { clientX: 108 }));
  const pointerResizeWorked = tableCells[2].getBoundingClientRect().width > sizeBefore + 7;
  const sizeAfterPointer = tableCells[2].getBoundingClientRect().width;
  resizeHandle.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, key: "ArrowRight" }));
  const keyboardResizeWorked = tableCells[2].getBoundingClientRect().width > sizeAfterPointer + 7;
  tableCard.style.removeProperty("inline-size");
  const nameSort = review.querySelector('[data-sort-column="filename"]');
  const sizeSort = review.querySelector('[data-sort-column="size"]');
  nameSort.click();
  await until(() => tableCells[1].ariaSort === "ascending" && review.dataset.pending === "", "ascending Plan header sort");
  nameSort.click();
  await until(() => tableCells[1].ariaSort === "descending" && review.dataset.pending === "", "descending Plan header sort");
  const chevronsVisible = !nameSort.querySelector(".nami-icon--chevron-down").hidden;
  sizeSort.click();
  await until(() => tableCells[2].ariaSort === "ascending" && review.dataset.pending === "", "changed Plan header sort");
  const changedSortStartsAscending = tableCells[1].ariaSort === "none";
  sizeSort.click();
  await until(() => tableCells[2].ariaSort === "descending" && review.dataset.pending === "", "second Size sort");
  sizeSort.click();
  await until(() => tableCells[2].ariaSort === "none" && review.dataset.pending === "", "canonical Plan header reset");
  const noticeFilter = review.querySelector('.nami-plan-review__filter-list [data-operation="notice"]');
  noticeFilter.click();
  await until(() => viewport.textContent.includes("insufficient_space"), "review refusal notice");
  await control("checkpoint", "plan_notice");
  const initialRows = viewport.textContent;
  const execute = review.querySelector('[data-action="execute"]');
  const initial = {
    negativePreflight: facts.includes("1 review preflight refusal(s)"),
    refusalNotice: initialRows.includes("insufficient_space"),
    destructiveCountVisible: facts.includes("destructive"),
    requiredBytesVisible: facts.includes("B required"),
    rowRiskVisible: initialRows.includes("Risk:"),
    persistentAcknowledgmentAbsent: review.querySelector('[data-action="destructive-confirmation"]') === null,
    executeReady: execute instanceof HTMLButtonElement && !execute.disabled,
    rowHeight: getComputedStyle(review.querySelector("[data-node-id]")).height,
    spacerAligned,
    columnsAligned,
    headerScrollClear,
    pointerResizeWorked,
    keyboardResizeWorked,
    chevronsVisible,
    changedSortStartsAscending,
    planGeometry,
  };
  await control("prepare_plan_again");
  const planAgainTraceEnabled = globalThis.__namiPlanAgainTrace !== undefined;
  if (planAgainTraceEnabled) {
    await control("begin_plan_again_trace", "task-47-48");
    globalThis.__namiPlanAgainTrace.begin("task-47-48");
  }
  let firstPlanAgainError = null;
  try {
    review.querySelector('[data-action="plan-again"]').click();
    await until(() => rows().length === 48, "fresh Plan-again task");
  } catch (error) {
    firstPlanAgainError = error;
  }
  if (planAgainTraceEnabled) {
    try {
      const trace = globalThis.__namiPlanAgainTrace.snapshot();
      if (!globalThis.__namiPlanAgainTrace.end("task-47-48")) {
        throw new Error("first Plan-again trace phase did not end");
      }
      await control("record_plan_again_trace", trace);
    } catch (error) {
      if (firstPlanAgainError === null) firstPlanAgainError = error;
    }
  }
  if (firstPlanAgainError !== null) throw firstPlanAgainError;
  clickSelect("Task 48");
  await until(() => selectedTitle() === "Task 48", "fresh Plan-again selection");
  await until(() => document.querySelector(".nami-plan-review__rows")?.textContent.includes("source-added.txt"), "changed source plan row");
  await until(() => document.querySelector(".nami-plan-review__rows")?.textContent.includes("target-added.txt"), "changed target plan row");
  await control("checkpoint", "plan_again");
  await control("track_review_task");
  const fresh = document.querySelector(".nami-plan-review");
  const changedRows = fresh.querySelector(".nami-plan-review__rows").textContent;
  const freshExecute = fresh.querySelector('[data-action="execute"]');
  await control("refuse_execution");
  await control("checkpoint", "plan_force");
  await until(() => freshExecute.disabled === false, "fresh Execute readiness");
  await control("checkpoint", "plan_ack");
  window.__namiConfirmationStage = "execute-ready";
  await until(() => document.querySelector("#execution-confirmation")?.open, "destructive confirmation");
  window.__namiConfirmationStage = "cancel-open";
  await until(() => !document.querySelector("#execution-confirmation")?.open, "native Escape cancellation");
  window.__namiConfirmationInputEvidence.escapeReturnedFocus =
    document.activeElement === freshExecute;
  window.__namiConfirmationStage = "reopen-ready";
  await until(() => document.querySelector("#execution-confirmation")?.open, "reopened destructive confirmation");
  window.__namiConfirmationStage = "confirm-open";
  await until(
    () => document.querySelector("#execution-confirmation")?.dataset.closing === "true",
    "native confirmation",
  );
  window.__namiConfirmationStage = "confirm-closing";
  await until(() => !document.querySelector("#execution-confirmation")?.open, "confirmation exit");
  await control("checkpoint", "plan_execute");
  await until(() => statusFor("Task 48") === "Error", "post-admission preflight refusal");
  await control("checkpoint", "plan_refused");
  await untilAsync(async () => (await control("status")).review_session_released === true, "refused execution release");
  await control("checkpoint", "plan_release");
  await until(() => fresh.querySelector('[data-action="execute"]').hidden, "committed selection review");
  const refused = {
    committed: fresh.querySelector('[data-action="execute"]').hidden,
    unrun: statusFor("Task 48") === "Error",
    message: fresh.querySelector(".nami-plan-review__status").textContent,
  };

  const freedTaskTitle = "Task 1";
  const freedTask = rowByTitle(freedTaskTitle);
  const freedTaskClose = freedTask?.querySelector(".nami-task-rail__close");
  const freedTaskStatus = statusFor(freedTaskTitle);
  const freedTaskWasSelected = selectedTitle() === freedTaskTitle;
  if (!(freedTaskClose instanceof HTMLButtonElement) || freedTaskClose.disabled
      || freedTaskStatus !== "New task" || freedTaskWasSelected) {
    throw new Error("unused capacity task is unavailable for close");
  }
  clickClose(freedTaskTitle);
  await until(
    () => rows().length === 47 && rowByTitle(freedTaskTitle) === undefined
      && selectedTitle() === "Task 48" && workTitle() === "Task 48",
    "unused capacity task close",
  );
  const capacitySlot = {
    closedTitle: freedTaskTitle,
    closedStatus: freedTaskStatus,
    closedWasSelected: freedTaskWasSelected,
    closedIdentityRemoved: rowByTitle(freedTaskTitle) === undefined,
    retainedSelectedTask: selectedTitle() === "Task 48" && workTitle() === "Task 48",
    countBeforePlanAgain: rows().length,
  };

  await control("prepare_live_execution");
  if (planAgainTraceEnabled) {
    await control("begin_plan_again_trace", "task-48-49");
    globalThis.__namiPlanAgainTrace.begin("task-48-49");
  }
  let secondPlanAgainError = null;
  try {
    fresh.querySelector('[data-action="plan-again"]').click();
    await until(
      () => rows().length === 48 && rowByTitle("Task 49") !== undefined,
      "live Plan-again task",
    );
  } catch (error) {
    secondPlanAgainError = error;
  }
  if (planAgainTraceEnabled) {
    try {
      const trace = globalThis.__namiPlanAgainTrace.snapshot();
      if (!globalThis.__namiPlanAgainTrace.end("task-48-49")) {
        throw new Error("second Plan-again trace phase did not end");
      }
      await control("record_plan_again_trace", trace);
    } catch (error) {
      if (secondPlanAgainError === null) secondPlanAgainError = error;
    }
  }
  if (secondPlanAgainError !== null) throw secondPlanAgainError;
  clickSelect("Task 49");
  await until(() => selectedTitle() === "Task 49", "live Plan-again selection");
  await until(() => document.querySelector(".nami-plan-review__rows [data-node-id]"), "live Plan rows");
  const live = document.querySelector(".nami-plan-review");
  const liveExecute = live.querySelector('[data-action="execute"]');
  await until(() => liveExecute.disabled === false, "live Execute readiness");
  window.__namiConfirmationStage = "live-execute-ready";
  await until(() => document.querySelector("#execution-confirmation")?.open, "live destructive confirmation");
  window.__namiConfirmationStage = "live-confirm-open";
  await until(
    () => window.__namiConfirmationInputEvidence?.liveEnterConfirmed === true,
    "native live confirmation",
  );
  await untilAsync(async () => (await control("status")).execution_entered === true, "live execution");
  await until(() => !live.querySelector('[data-action="pause"]').closest(".nami-plan-review__control-group").hidden, "live controls");
  await control("checkpoint", "plan_live");
  live.querySelector('[data-action="pause"]').click();
  await until(() => !live.querySelector('[data-action="resume"]').hidden, "paused execution");
  await control("checkpoint", "plan_paused");
  const paused = live.querySelector(".nami-plan-review__status").textContent;
  live.querySelector('[data-action="resume"]').click();
  await until(() => live.querySelector('[data-action="resume"]').hidden, "resumed execution");
  await control("checkpoint", "plan_resumed");
  live.querySelector('[data-action="cancel"]').click();
  await until(() => statusFor("Task 49") === "Canceled", "canceled execution");
  await control("checkpoint", "plan_empty_prepare");
  await until(() => !live.querySelector('[data-action="plan-again"]').disabled, "settled Plan-again eligibility");
  const countBeforeEmptyPlanAgain = rows().length;
  clickClose("Task 2");
  await until(() => rows().length === 47 && rowByTitle("Task 2") === undefined, "empty Plan capacity slot");
  await control("prepare_empty_plan");
  live.querySelector('[data-action="plan-again"]').click();
  await control("checkpoint", "plan_empty_wait");
  await until(() => rows().length === 48 && rowByTitle("Task 50") !== undefined, "empty Plan-again task");
  clickSelect("Task 50");
  await until(() => selectedTitle() === "Task 50", "empty Plan selection");
  const emptyReview = await until(
    () => statusFor("Task 50") === "Plan ready" && document.querySelector(".nami-plan-review"),
    "empty Plan review",
  );
  await until(
    () => !emptyReview.querySelector(".nami-plan-review__rows [data-node-id]"),
    "empty Plan rows",
  );
  const emptyPlanGeometry = planGeometryFor(emptyReview);
  const emptyPlanMessage = emptyReview.textContent.toLowerCase().includes("empty");
  await control("record", {
    plan_review: {
      initial,
      refused,
      planAgainChangedSource: changedRows.includes("source-added.txt"),
      planAgainChangedTarget: changedRows.includes("target-added.txt"),
      capacitySlot: {
        ...capacitySlot,
        countAfterPlanAgain: countBeforeEmptyPlanAgain,
        newTaskTitle: rowByTitle("Task 49")?.querySelector(".nami-task-card")?.dataset.taskLabel ?? null,
      },
      confirmationInput: window.__namiConfirmationInputEvidence,
      paused: paused.length > 0,
      resumed: live.querySelector('[data-action="resume"]').hidden,
      canceled: statusFor("Task 49") === "Canceled",
      emptyPlanGeometry,
      emptyPlanMessage,
    },
  });
  const marker = document.createElement("p");
  marker.textContent = "Task shell gate complete";
  document.body.append(marker);
  await control("complete");
  return { complete: true };
})()
"""


class _Recorder:
    def __init__(self, paths: EvidencePaths) -> None:
        self._publisher = EvidencePublisher(paths)
        self._lock = threading.Lock()
        self._initial: str | None = None
        self._post_ready_failure: dict[str, str] | None = None
        self._data: dict[str, Any] = {
            "schema_version": 1,
            "phase": "starting",
            "startup_errors": [],
            "report": {},
        }

    def set(self, name: str, value: object) -> None:
        with self._lock:
            self._data[name] = value

    def merge_report(self, value: dict[str, object]) -> None:
        with self._lock:
            self._data["report"].update(value)

    def startup_error(self, _message: str) -> None:
        self.set("startup_errors", [{"type": "DesktopStartupError"}])

    def failure(self, stage: str, error: BaseException) -> None:
        if stage not in _FAILURE_STAGES:
            stage = "child"
        failure = {"stage": stage, "type": _error_type(error)}
        with self._lock:
            if self._initial == "failure":
                return
            if self._initial == "ready":
                if self._post_ready_failure is None:
                    self._post_ready_failure = failure
                return
            diagnostics = {
                name: value for name, value in self._data.items()
                if name in {"plan_again_browser_trace", "plan_again_host_trace"}
            }
            self._publisher.publish_failure({"failure": failure, **diagnostics})
            self._initial = "failure"

    def complete(self) -> None:
        with self._lock:
            if self._initial is not None:
                return
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
                payload["post_ready_failure"] = dict(self._post_ready_failure)
            self._publisher.publish_final(payload)


class _Control:
    def __init__(
        self, recorder: _Recorder, source: Path, target: Path,
        plan_again_trace: PlanAgainHostTrace | None = None,
    ) -> None:
        self.recorder = recorder
        self.source = source
        self.target = target
        self.registry: object | None = None
        self.service: object | None = None
        self.stage = "initial"
        self.checkpoint = "ready"
        self.create_gate = threading.Event()
        self.create_waiting = threading.Event()
        self.delay_create = False
        self.fail_close_remaining = 0
        self.close_failures = 0
        self.busy_gate = threading.Event()
        self.busy_entered = threading.Event()
        self.busy_task_id: str | None = None
        self.busy_session_id: str | None = None
        self.terminal_task_id: str | None = None
        self.terminal_session_id: str | None = None
        self.release_gate = threading.Event()
        self.release_waiting = threading.Event()
        self.delay_release = False
        self.release_calls = 0
        self.observer_release_calls = 0
        self.original_deps: object | None = None
        self.review_deps: object | None = None
        self.force_preflight_refusal = False
        self.block_execution = False
        self.execution_entered = threading.Event()
        self.execution_release = threading.Event()
        self.review_task_id: str | None = None
        self.review_plan_session_id: str | None = None
        self.preflight_hook_count = 0
        self.diagnostic_lock = threading.Lock()
        self.plan_again_trace = plan_again_trace

    def bind(self, registry: object) -> None:
        if self.registry is not None:
            return
        self.registry = registry
        if self.plan_again_trace is not None:
            trace_registry_plan_again(registry, self.plan_again_trace)
        self.service = registry._lifecycle
        service = self.service
        original_create = service.create_task_shell
        original_close_shell = service.close_task_shell
        original_release = service.release_task_session
        original_observer_release = service._observer.release

        def create_task_shell(_service: object, command_id: str, delivery_factory: object) -> object:
            result = original_create(command_id, delivery_factory)
            if self.delay_create:
                self.delay_create = False
                self.create_waiting.set()
                if not self.create_gate.wait(10):
                    raise RuntimeError("delayed create was not released")
                self.create_gate.clear()
                self.create_waiting.clear()
            return result

        def close_task_shell(_service: object, task_id: str) -> object:
            if self.fail_close_remaining > 0:
                self.fail_close_remaining -= 1
                self.close_failures += 1
                raise RuntimeError("injected cleanup failure")
            return original_close_shell(task_id)

        def release_task_session(_service: object, *args: object, **kwargs: object) -> object:
            self.release_calls += 1
            if self.delay_release:
                self.release_waiting.set()
                if not self.release_gate.wait(10):
                    raise RuntimeError("terminal cleanup was not released")
            return original_release(*args, **kwargs)

        def observer_release(session_id: str) -> object:
            self.observer_release_calls += 1
            return original_observer_release(session_id)

        service.create_task_shell = MethodType(create_task_shell, service)
        service.close_task_shell = MethodType(close_task_shell, service)
        service.release_task_session = MethodType(release_task_session, service)
        service._observer.release = observer_release

        for index in range(46):
            registry.create_task_shell(f"{1000 + index:032x}")

    def status(self) -> dict[str, object]:
        registry = self._registry()
        tasks = registry.list_tasks().tasks
        terminal = None
        session_released = None
        if self.terminal_task_id is not None:
            match = next((task for task in tasks if task.task_id == self.terminal_task_id), None)
            terminal = match is not None and match.session_state == "completed"
            session_released = None if match is None else match.session_released
        review_session_released = None
        if self.review_task_id is not None:
            review_match = next(
                (task for task in tasks if task.task_id == self.review_task_id),
                None,
            )
            review_session_released = (
                None if review_match is None else review_match.session_released
            )
        busy_state = None
        if self.busy_session_id is not None:
            try:
                busy_state = self._service().get_session(self.busy_session_id).state
            except self._session_not_found_type():
                busy_state = "retired"
        return {
            "task_count": len(tasks),
            "create_waiting": self.create_waiting.is_set(),
            "close_failures": self.close_failures,
            "busy_entered": self.busy_entered.is_set(),
            "busy_state": busy_state,
            "busy_present": any(task.task_id == self.busy_task_id for task in tasks),
            "terminal": terminal,
            "terminal_present": any(task.task_id == self.terminal_task_id for task in tasks),
            "release_waiting": self.release_waiting.is_set(),
            "session_released": session_released,
            "release_calls": self.release_calls,
            "observer_release_calls": self.observer_release_calls,
            "execution_entered": self.execution_entered.is_set(),
            "review_session_released": review_session_released,
        }

    def diagnostic_status(self) -> dict[str, object]:
        result: dict[str, object] = {
            "authoritative_selection_state": None,
            "task_delivery_session_changed": None,
            "task_delivery_session_released": None,
            "task_delivery_session_state": None,
            "task_delivery_start_identity_count": None,
            "service_session_state": None,
            "task_delivery_active_drain_present": None,
            "task_delivery_terminal_delivered": None,
            "task_delivery_terminal_record_present": None,
            "preflight_hook_count": None,
        }
        with self.diagnostic_lock:
            result["preflight_hook_count"] = self.preflight_hook_count
        if self.review_task_id is None:
            return result
        registry = self._registry()
        current_session_id = None
        with registry._condition:
            task = registry._tasks.get(self.review_task_id)
            view = registry._plan_views.get(self.review_task_id)
            if task is not None:
                with task.condition:
                    session_id = (
                        task.prior_session_id
                        if task.transition and task.prior_session_id is not None
                        else task.session_id
                    )
                    prior_record = (
                        task.prior_delivery[5]
                        if task.transition and task.prior_delivery is not None
                        else None
                    )
                    if session_id is None:
                        session_state = None
                    elif prior_record is not None:
                        session_state = prior_record.state
                    elif task.delivered_terminal_record is not None:
                        session_state = task.delivered_terminal_record.state
                    else:
                        session_state = "active"
                    result.update({
                        "task_delivery_session_changed": (
                            self.review_plan_session_id is not None
                            and session_id != self.review_plan_session_id
                        ),
                        "task_delivery_session_released": (
                            bool(task.prior_delivery[6])
                            if task.transition and task.prior_delivery is not None
                            else task.session_released
                        ),
                        "task_delivery_session_state": session_state,
                        "task_delivery_start_identity_count": len(task.start_response_ids),
                        "task_delivery_active_drain_present": task.active_drain is not None,
                        "task_delivery_terminal_delivered": task.delivered_terminal_record is not None,
                        "task_delivery_terminal_record_present": task.terminal_record is not None,
                    })
                    current_session_id = session_id
        if view is not None:
            result["authoritative_selection_state"] = view.summary()["selection_state"]
        if current_session_id is not None:
            try:
                result["service_session_state"] = self._service().get_session(
                    current_session_id
                ).state
            except self._session_not_found_type():
                result["service_session_state"] = "retired"
        return result

    def command(self, payload: object) -> object:
        if type(payload) is not dict or set(payload) != {"action", "value"}:
            raise ValueError("test control payload is invalid")
        action = payload["action"]
        value = payload["value"]
        if action == "status":
            return self.status()
        if action == "record" and type(value) is dict:
            self.recorder.merge_report(value)
            return {"accepted": True}
        if action == "checkpoint" and value in {
            "ready", "capacity", "basic_close", "retry", "navigation",
            "navigation_cleanup", "navigation_recorded", "reinjection_armed",
            "reinjection_wait"
            , "plan_surface", "plan_offset", "plan_notice", "plan_refused",
            "plan_release", "plan_again", "plan_live", "plan_paused",
            "plan_resumed", "plan_force", "plan_ack", "plan_execute",
            "plan_empty_prepare", "plan_empty_wait"
        }:
            self.checkpoint = value
            return {"accepted": True}
        if action == "set_stage" and value in {
            "reinjected", "busy", "terminal_first", "terminal_second",
            "plan_review"
        }:
            self.stage = value
            return {"accepted": True}
        if action == "arm_close_failure":
            self.fail_close_remaining = 4
            return {"accepted": True}
        if action == "arm_create_delay":
            self.create_gate.clear()
            self.create_waiting.clear()
            self.delay_create = True
            return {"accepted": True}
        if action == "release_create":
            self.create_gate.set()
            return {"accepted": True}
        if action == "start_busy":
            self._start_busy()
            return {"accepted": True}
        if action == "settle_busy":
            self.busy_gate.set()
            self._service()._runtime._deps = self.original_deps
            return {"accepted": True}
        if action == "start_terminal":
            self._start_terminal()
            return {"accepted": True}
        if action == "begin_plan_again_trace" and value in {
            "task-47-48", "task-48-49",
        } and self.plan_again_trace is not None:
            self.plan_again_trace.begin(value)
            return {"accepted": True}
        if action == "record_plan_again_trace" and self.plan_again_trace is not None:
            if type(value) is not dict or type(value.get("cases")) is not dict:
                raise ValueError("browser Plan-again trace payload is invalid")
            phases = set(value["cases"])
            if phases not in ({"task-47-48"}, {"task-47-48", "task-48-49"}):
                raise ValueError("browser Plan-again trace phases are invalid")
            validate_trace_snapshot(value, phases, allow_overflow=True)
            self.recorder.set("plan_again_browser_trace", value)
            host = self.plan_again_trace.snapshot()
            self.plan_again_trace.end(
                "task-48-49" if "task-48-49" in phases else "task-47-48"
            )
            validate_trace_snapshot(host, phases, allow_empty=True, allow_overflow=True)
            self.recorder.set("plan_again_host_trace", host)
            validate_trace_snapshot(value, phases)
            validate_trace_snapshot(host, phases, allow_empty=True)
            return {"accepted": True}
        if action == "start_plan_review":
            self._start_plan_review()
            return {"accepted": True}
        if action == "prepare_plan_again":
            self._prepare_plan_again()
            return {"accepted": True}
        if action == "prepare_empty_plan":
            self._prepare_empty_plan()
            return {"accepted": True}
        if action == "refuse_execution":
            self.force_preflight_refusal = True
            return {"accepted": True}
        if action == "track_review_task":
            review_task = self._registry().list_tasks().tasks[-1]
            self.review_task_id = review_task.task_id
            self.review_plan_session_id = review_task.session_id
            return {"accepted": True}
        if action == "prepare_live_execution":
            self.force_preflight_refusal = False
            self.block_execution = True
            self.execution_entered.clear()
            self.execution_release.clear()
            return {"accepted": True}
        if action == "arm_release_delay":
            self.release_gate.clear()
            self.release_waiting.clear()
            self.delay_release = True
            return {"accepted": True}
        if action == "release_cleanup":
            self.delay_release = False
            self.release_gate.set()
            return {"accepted": True}
        if action == "complete":
            self.execution_release.set()
            if self.review_deps is not None:
                self._service()._runtime._deps = self.review_deps
            self.recorder.complete()
            return {"accepted": True}
        raise ValueError("unknown test control action")

    def _start_busy(self) -> None:
        service = self._service()
        self.original_deps = service._runtime._deps

        def blocked_scanner(root: object, ignores: object, ctx: object, **kwargs: object) -> object:
            self.busy_entered.set()
            while not self.busy_gate.wait(0.01):
                pass
            ctx.checkpoint()
            return self.original_deps.scanner(root, ignores, ctx, **kwargs)

        service._runtime._deps = replace(self.original_deps, scanner=blocked_scanner)
        started = self._registry().start_plan(
            str(self.source), str(self.target), deletion_policy=None,
            command_id=f"{2001:032x}", wire_intent=None,
        )
        self.busy_task_id = started.task_id
        self.busy_session_id = started.session_id
        if not self.busy_entered.wait(5):
            raise RuntimeError("busy scanner did not enter")

    def _start_terminal(self) -> None:
        started = self._registry().start_plan(
            str(self.source), str(self.target), deletion_policy=None,
            command_id=f"{2002:032x}", wire_intent=None,
        )
        self.terminal_task_id = started.task_id
        self.terminal_session_id = started.session_id

    def _start_plan_review(self) -> None:
        from namisync.core.preflight import Refusal, RefusalCode, Verdict
        from namisync.workflows import LocationCandidate
        from namisync.workflows.views import PreservationSettingsView, SetupOptionsView

        self.source.mkdir(parents=True, exist_ok=True)
        self.target.mkdir(parents=True, exist_ok=True)
        (self.source / "shared.txt").write_text("source-v1", encoding="utf-8")
        (self.target / "shared.txt").write_text("target-before-v1", encoding="utf-8")
        for index in range(300):
            (self.source / f"z-{index:03d}.txt").write_text("fixture", encoding="utf-8")
        self.review_deps = self._service()._runtime._deps
        original_preflight = self.review_deps.preflight
        original_executor = self.review_deps.executor

        def preflight(review: object, world: object, **kwargs: object) -> object:
            if self.force_preflight_refusal:
                with self.diagnostic_lock:
                    self.preflight_hook_count += 1
                return Verdict(
                    False,
                    (Refusal(RefusalCode.INSUFFICIENT_SPACE, detail="headed review refusal"),),
                    world,
                )
            return original_preflight(review, world, **kwargs)

        def executor(*args: object, **kwargs: object) -> object:
            if self.block_execution:
                context = args[1]
                self.execution_entered.set()
                while not self.execution_release.wait(0.01):
                    context.checkpoint()
            return original_executor(*args, **kwargs)

        self._service()._runtime._deps = replace(
            self.review_deps,
            preflight=preflight,
            executor=executor,
        )
        self.force_preflight_refusal = True
        shell = self._registry().create_task_shell(f"{3001:032x}")
        self.review_task_id = shell.task_id
        options = SetupOptionsView(
            (),
            "trash",
            False,
            PreservationSettingsView(False, False, False),
            False,
            False,
        )
        self._registry().start_setup_plan(
            shell.task_id,
            LocationCandidate.literal(str(self.source)),
            LocationCandidate.literal(str(self.target)),
            options,
            command_id=f"{3002:032x}",
            wire_intent=("headed-plan-review",),
        )

    def _prepare_plan_again(self) -> None:
        (self.source / "shared.txt").write_text("source-v2", encoding="utf-8")
        (self.source / "source-added.txt").write_text("source-added", encoding="utf-8")
        (self.target / "shared.txt").write_text("target-before-v2", encoding="utf-8")
        (self.target / "target-added.txt").write_text("target-added", encoding="utf-8")
        self.force_preflight_refusal = False
        self.block_execution = False
        self.execution_entered.clear()
        self.execution_release.clear()

    def _prepare_empty_plan(self) -> None:
        for root in (self.source, self.target):
            for child in root.iterdir():
                if child.is_dir():
                    for nested in sorted(child.rglob("*"), reverse=True):
                        if nested.is_file() or nested.is_symlink():
                            nested.unlink()
                        elif nested.is_dir():
                            nested.rmdir()
                    child.rmdir()
                else:
                    child.unlink()
        self.force_preflight_refusal = False
        self.block_execution = False

    def _registry(self) -> object:
        if self.registry is None:
            raise RuntimeError("task registry is unavailable")
        return self.registry

    def _service(self) -> object:
        if self.service is None:
            raise RuntimeError("service is unavailable")
        return self.service

    @staticmethod
    def _session_not_found_type() -> type[Exception]:
        from namisync.dispatcher import SessionNotFound

        return SessionNotFound


def _test_spec(handler: Callable[[object], object]) -> object:
    from namisync.interfaces.web.commands import (
        CommandAccess, CommandRetry, CommandSpec, CommandTimeout, FieldRequirement,
    )

    return CommandSpec(
        validate_payload=lambda payload: payload,
        handler=handler,
        access=CommandAccess.READ_ONLY,
        command_id=FieldRequirement.FORBIDDEN,
        revision=FieldRequirement.FORBIDDEN,
        timeout=CommandTimeout.INTERACTIVE,
        retry=CommandRetry.NONE,
    )


def _runtime_value(task: object) -> object:
    if task.IsFaulted or task.IsCanceled:
        raise RuntimeError("native CDP evaluation failed")
    envelope = json.loads(str(task.Result))
    if type(envelope) is not dict or "exceptionDetails" in envelope:
        raise RuntimeError("page task-shell probe failed")
    return envelope.get("result", {}).get("value")


def _write_driver_diagnostic(path: Path, record: dict[str, object]) -> None:
    if set(record) != _DRIVER_DIAGNOSTIC_KEYS:
        raise TypeError("driver diagnostic shape is invalid")
    path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")


def _drive_plan_confirmation(
    native: object,
    core: object,
    recorder: _Recorder,
    control: _Control,
    retained: list[object],
    screenshot: Path,
) -> Callable[[BaseException, object | None], None]:
    from System import Action

    failed = False
    last_driver_step = "start"
    last_method: str | None = None

    def fail(error: BaseException, task: object | None = None) -> None:
        nonlocal failed
        if failed:
            return
        failed = True
        diagnostic_path = screenshot.with_name("execution-confirmation-driver.json")
        faulted = bool(task is not None and task.IsFaulted)
        canceled = bool(task is not None and task.IsCanceled)
        result_type = None
        has_exception_details = None
        if task is not None and not faulted and not canceled and last_method == "Runtime.evaluate":
            try:
                envelope = json.loads(str(task.Result))
                if type(envelope) is dict:
                    has_exception_details = "exceptionDetails" in envelope
                    result = envelope.get("result")
                    if type(result) is dict and type(result.get("type")) is str:
                        result_type = result["type"]
            except (TypeError, ValueError):
                pass
        base = {
            "actual_control_checkpoint": control.checkpoint,
            "active_element": None,
            "authoritative_selection_state": None,
            "task_delivery_session_changed": None,
            "task_delivery_session_released": None,
            "task_delivery_session_state": None,
            "task_delivery_start_identity_count": None,
            "service_session_state": None,
            "task_delivery_active_drain_present": None,
            "task_delivery_terminal_delivered": None,
            "task_delivery_terminal_record_present": None,
            "cdp_canceled": canceled,
            "cdp_faulted": faulted,
            "dialog_open": None,
            "document_has_focus": None,
            "execute_disabled": None,
            "execute_focused": None,
            "execute_hidden": None,
            "last_driver_step": last_driver_step,
            "last_method": last_method,
            "page_confirmation_stage": None,
            "preflight_hook_count": None,
            "runtime_has_exception_details": has_exception_details,
            "runtime_result_type": result_type,
            "trusted_click_count": None,
            "trusted_keydown_count": None,
            "trusted_keyup_count": None,
        }
        diagnostic_expression = r"""
(() => {
  const execute = document.querySelector('.nami-plan-review [data-action="execute"]');
  const dialog = document.querySelector("#execution-confirmation");
  const active = document.activeElement;
  const counters = window.__namiConfirmationTrustedInput ?? {};
  const activeElement = active === execute ? "execute"
    : active === dialog ? "dialog"
      : active?.matches?.("[data-cancel-execution]") ? "cancel"
        : active?.matches?.("[data-confirm-execution]") ? "confirm"
          : active === null ? "none" : "other";
  return {
    active_element: activeElement,
    dialog_open: dialog?.open === true,
    document_has_focus: document.hasFocus(),
    execute_disabled: execute instanceof HTMLButtonElement ? execute.disabled : null,
    execute_focused: active === execute,
    execute_hidden: execute instanceof HTMLButtonElement ? execute.hidden : null,
    page_confirmation_stage:
      typeof window.__namiConfirmationStage === "string"
        ? window.__namiConfirmationStage : null,
    trusted_click_count: Number.isSafeInteger(counters.click) ? counters.click : null,
    trusted_keydown_count: Number.isSafeInteger(counters.keydown) ? counters.keydown : null,
    trusted_keyup_count: Number.isSafeInteger(counters.keyup) ? counters.keyup : null,
  };
})()
"""

        def publish(page: object = None) -> None:
            try:
                base.update(control.diagnostic_status())
            except BaseException:
                pass
            if type(page) is dict:
                for key in (
                    "active_element", "dialog_open", "document_has_focus", "execute_disabled",
                    "execute_focused", "execute_hidden", "page_confirmation_stage", "trusted_click_count",
                    "trusted_keydown_count", "trusted_keyup_count",
                ):
                    if key in page:
                        base[key] = page[key]
            _write_driver_diagnostic(diagnostic_path, base)
            recorder.failure("page_plan_review_plan_ack", error)

        try:
            diagnostic_task = core.CallDevToolsProtocolMethodAsync(
                "Runtime.evaluate",
                json.dumps({
                    "expression": diagnostic_expression,
                    "returnByValue": True,
                }),
            )

            def diagnostic_completed() -> None:
                def finish() -> None:
                    try:
                        publish(_runtime_value(diagnostic_task))
                    except BaseException:
                        publish()

                finish_action = Action(finish)
                retained.append(finish_action)
                native.BeginInvoke(finish_action)

            completion = Action(diagnostic_completed)
            retained.append(completion)
            diagnostic_task.GetAwaiter().OnCompleted(completion)
        except BaseException:
            publish()

    def call(
        method: str,
        parameters: dict[str, object],
        then: Callable[[object], None],
        step: str,
    ) -> None:
        nonlocal last_driver_step, last_method
        if failed:
            return
        last_driver_step = step
        last_method = method
        try:
            task = core.CallDevToolsProtocolMethodAsync(method, json.dumps(parameters))
        except BaseException as error:
            fail(error)
            return

        def completed() -> None:
            def finish() -> None:
                try:
                    then(_runtime_value(task))
                except BaseException as error:
                    fail(error, task)

            finish_action = Action(finish)
            retained.append(finish_action)
            native.BeginInvoke(finish_action)

        completion = Action(completed)
        retained.append(completion)
        task.GetAwaiter().OnCompleted(completion)

    def evaluate(expression: str, then: Callable[[object], None], step: str) -> None:
        call(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
            then,
            step,
        )

    def capture(then: Callable[[], None], step: str) -> None:
        nonlocal last_driver_step, last_method
        last_driver_step = step
        last_method = "Page.captureScreenshot"
        try:
            task = core.CallDevToolsProtocolMethodAsync(
                "Page.captureScreenshot", json.dumps({"format": "png"}),
            )
        except BaseException as error:
            fail(error)
            return

        def completed() -> None:
            def finish() -> None:
                try:
                    if task.IsFaulted or task.IsCanceled:
                        raise RuntimeError("native confirmation screenshot failed")
                    envelope = json.loads(str(task.Result))
                    data = envelope.get("data") if type(envelope) is dict else None
                    if type(data) is not str:
                        raise RuntimeError("native confirmation screenshot payload is invalid")
                    content = base64.b64decode(data, validate=True)
                    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
                        raise ValueError("native confirmation screenshot is not PNG")
                    screenshot.write_bytes(content)
                    then()
                except BaseException as error:
                    fail(error, task)

            finish_action = Action(finish)
            retained.append(finish_action)
            native.BeginInvoke(finish_action)

        completion = Action(completed)
        retained.append(completion)
        task.GetAwaiter().OnCompleted(completion)

    def dispatch(
        events: list[tuple[str, dict[str, object]]],
        done: Callable[[], None],
        step: str,
    ) -> None:
        remaining = iter(events)
        index = 0

        def advance(_value: object = None) -> None:
            nonlocal index
            try:
                method, parameters = next(remaining)
            except StopIteration:
                done()
                return
            index += 1
            call(method, parameters, advance, f"{step}.{index}")

        advance()

    def key_events(key: str, code: str, virtual_key: int) -> list[tuple[str, dict[str, object]]]:
        shared: dict[str, object] = {
            "key": key,
            "code": code,
            "windowsVirtualKeyCode": virtual_key,
            "nativeVirtualKeyCode": virtual_key,
        }
        if key == "Enter":
            return [
                ("Input.dispatchKeyEvent", {
                    "type": "keyDown", "text": "\r", "unmodifiedText": "\r", **shared,
                }),
                ("Input.dispatchKeyEvent", {"type": "keyUp", **shared}),
            ]
        return [
            ("Input.dispatchKeyEvent", {"type": "rawKeyDown", **shared}),
            ("Input.dispatchKeyEvent", {"type": "keyUp", **shared}),
        ]

    def mouse_click(point: dict[str, object]) -> list[tuple[str, dict[str, object]]]:
        shared = {
            "x": point["x"], "y": point["y"], "button": "left", "clickCount": 1,
        }
        return [
            ("Input.dispatchMouseEvent", {"type": "mousePressed", "buttons": 1, **shared}),
            ("Input.dispatchMouseEvent", {"type": "mouseReleased", "buttons": 0, **shared}),
        ]

    wait_execute = r"""
(async () => {
  for (let attempt = 0; attempt < 1200; attempt += 1) {
    if (window.__namiConfirmationStage === "execute-ready") {
      const execute = document.querySelector('.nami-plan-review [data-action="execute"]');
      if (!(execute instanceof HTMLButtonElement)) throw new Error("Execute control missing");
      execute.focus();
      await new Promise((resolve) => requestAnimationFrame(resolve));
      if (document.activeElement !== execute) throw new Error("Execute did not receive focus");
      const rect = execute.getBoundingClientRect();
      const point = {x: (rect.left + rect.right) / 2, y: (rect.top + rect.bottom) / 2};
      const inViewport = rect.width > 0 && rect.height > 0 &&
        point.x >= 0 && point.x < innerWidth && point.y >= 0 && point.y < innerHeight;
      if (!inViewport || document.elementFromPoint(point.x, point.y) !== execute) {
        throw new Error("Execute pointer target is not exact");
      }
      window.__namiExecuteFocused = true;
      window.__namiExecutePointInViewport = true;
      window.__namiExecuteHitTested = true;
      return point;
    }
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error("timed out waiting for Execute readiness");
})()
"""
    wait_cancel = r"""
(async () => {
  for (let attempt = 0; attempt < 1200; attempt += 1) {
    if (window.__namiConfirmationStage === "cancel-open") {
      const dialog = document.querySelector("#execution-confirmation");
      const cancel = dialog?.querySelector("[data-cancel-execution]");
      window.__namiConfirmationInputEvidence = {
        nativeExecuteFocused: window.__namiExecuteFocused === true,
        nativeExecutePointInViewport: window.__namiExecutePointInViewport === true,
        nativeExecuteHitTested: window.__namiExecuteHitTested === true,
        nativeModal: dialog?.matches(":modal") === true,
        cancelInitiallyFocused: document.activeElement === cancel,
        appInert: document.querySelector("#app")?.inert === true,
        popupInert: document.querySelector("#theme-options")?.inert === true,
      };
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error("timed out waiting for cancel-open confirmation");
})()
"""
    wait_confirm = r"""
(async () => {
  for (let attempt = 0; attempt < 1200; attempt += 1) {
    if (window.__namiConfirmationStage === "confirm-open") {
      const dialog = document.querySelector("#execution-confirmation");
      const confirm = dialog?.querySelector("[data-confirm-execution]");
      const background = Array.from(document.querySelectorAll(".nami-task-rail__row"))
        .find((row) => row.querySelector(".nami-task-card")?.dataset.taskLabel === "Task 47")
        ?.querySelector(".nami-task-card");
      const rail = document.querySelector(".nami-task-rail__items");
      if (!(dialog instanceof HTMLDialogElement) || !(confirm instanceof HTMLButtonElement)
          || !(background instanceof HTMLButtonElement) || !(rail instanceof HTMLElement)) {
        throw new Error("confirmation geometry is unavailable");
      }
      window.__namiConfirmationExitBarrier = dialog.animate(
        [], {duration: 60000},
      );
      window.__namiConfirmationExitBarrier.pause();
      rail.scrollTop = Math.min(120, rail.scrollHeight - rail.clientHeight);
      await new Promise((resolve) => requestAnimationFrame(resolve));
      const center = (element) => {
        const rect = element.getBoundingClientRect();
        return {x: (rect.left + rect.right) / 2, y: (rect.top + rect.bottom) / 2};
      };
      Object.assign(window.__namiConfirmationInputEvidence, {
        escapeCanceled: true,
        reopenCancelInitiallyFocused:
          document.activeElement === dialog.querySelector("[data-cancel-execution]"),
        selectedBeforeBackgroundInput:
          document.querySelector('.nami-task-card[aria-current="page"]')?.dataset.taskLabel ?? null,
        railScrollBeforeBackgroundInput: rail.scrollTop,
      });
      return {confirm: center(confirm), background: center(background)};
    }
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error("timed out waiting for confirm-open confirmation");
})()
"""

    def after_execute(value: object) -> None:
        if type(value) is not dict:
            raise RuntimeError("Execute pointer target was not verified")
        dispatch(
            mouse_click(value),
            lambda: evaluate(wait_cancel, after_cancel, "wait_cancel"),
            "open_execute_pointer",
        )

    def after_cancel(_value: object) -> None:
        dispatch(
            key_events("Escape", "Escape", 27),
            lambda: evaluate(wait_reopen, after_reopen, "wait_reopen"),
            "cancel_escape",
        )

    wait_reopen = r"""
(async () => {
  for (let attempt = 0; attempt < 1200; attempt += 1) {
    if (window.__namiConfirmationStage === "reopen-ready") {
      const execute = document.querySelector('.nami-plan-review [data-action="execute"]');
      if (!(execute instanceof HTMLButtonElement)) throw new Error("reopened Execute missing");
      execute.focus();
      await new Promise((resolve) => requestAnimationFrame(resolve));
      if (document.activeElement !== execute) throw new Error("reopened Execute did not receive focus");
      const rect = execute.getBoundingClientRect();
      const point = {x: (rect.left + rect.right) / 2, y: (rect.top + rect.bottom) / 2};
      const inViewport = rect.width > 0 && rect.height > 0 &&
        point.x >= 0 && point.x < innerWidth && point.y >= 0 && point.y < innerHeight;
      if (!inViewport || document.elementFromPoint(point.x, point.y) !== execute) {
        throw new Error("reopened Execute pointer target is not exact");
      }
      window.__namiConfirmationInputEvidence.reopenExecuteFocused = true;
      window.__namiConfirmationInputEvidence.reopenExecutePointInViewport = true;
      window.__namiConfirmationInputEvidence.reopenExecuteHitTested = true;
      return point;
    }
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error("timed out waiting to reopen confirmation");
})()
"""

    def after_reopen(value: object) -> None:
        if type(value) is not dict:
            raise RuntimeError("reopened Execute pointer target was not verified")
        dispatch(
            mouse_click(value),
            lambda: evaluate(wait_confirm, after_confirm, "wait_confirm"),
            "reopen_execute_pointer",
        )

    def after_confirm(value: object) -> None:
        if type(value) is not dict:
            raise RuntimeError("confirmation geometry was not returned")
        points = value
        capture(lambda: exercise_focus(points), "capture_dialog")

    def exercise_focus(points: dict[str, object]) -> None:
        dispatch(key_events("Tab", "Tab", 9), lambda: evaluate(
            "window.__namiConfirmationInputEvidence.firstTabFocusedConfirm = "
            "document.activeElement?.matches('[data-confirm-execution]') === true; true",
            lambda _first: dispatch(key_events("Tab", "Tab", 9), lambda: evaluate(
                "window.__namiConfirmationInputEvidence.secondTabFocusedCancel = "
                "document.activeElement?.matches('[data-cancel-execution]') === true; true",
                lambda _second: exercise_background(points),
                "verify_second_tab",
            ), "dialog_tab_second"),
            "verify_first_tab",
        ), "dialog_tab_first")

    def exercise_background(points: dict[str, object]) -> None:
        background = points["background"]
        events = mouse_click(background) + [("Input.dispatchMouseEvent", {
            "type": "mouseWheel", "x": background["x"], "y": background["y"],
            "deltaX": 0, "deltaY": 180,
        })]
        dispatch(events, lambda: evaluate(r"""
(async () => {
  await new Promise((resolve) => setTimeout(resolve, 75));
  const evidence = window.__namiConfirmationInputEvidence;
  const dialog = document.querySelector("#execution-confirmation");
  const rail = document.querySelector(".nami-task-rail__items");
  evidence.backgroundPointerBlocked =
    document.querySelector('.nami-task-card[aria-current="page"]')?.dataset.taskLabel
      === evidence.selectedBeforeBackgroundInput;
  evidence.backgroundWheelBlocked = rail?.scrollTop === evidence.railScrollBeforeBackgroundInput;
  evidence.focusContained = document.activeElement === dialog || dialog?.contains(document.activeElement);
  evidence.modalStayedOpen = dialog?.open === true && dialog.matches(":modal");
  return true;
})()
""", lambda _verified: dispatch(
            mouse_click(points["confirm"]),
            lambda: evaluate(
                wait_closing, lambda closing: exercise_closing(closing), "wait_closing",
            ),
            "confirm_pointer",
        ), "verify_background"), "background_input")

    wait_closing = r"""
(async () => {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    if (window.__namiConfirmationStage === "confirm-closing") {
      const background = Array.from(document.querySelectorAll(".nami-task-rail__row"))
        .find((row) => row.querySelector(".nami-task-card")?.dataset.taskLabel === "Task 47")
        ?.querySelector(".nami-task-card");
      if (!(background instanceof HTMLButtonElement)) throw new Error("closing background missing");
      const rect = background.getBoundingClientRect();
      return {x: (rect.left + rect.right) / 2, y: (rect.top + rect.bottom) / 2};
    }
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  throw new Error("timed out waiting for closing confirmation");
})()
"""

    def exercise_closing(value: object) -> None:
        if type(value) is not dict:
            raise RuntimeError("closing geometry was not returned")
        dispatch(mouse_click(value), lambda: evaluate(r"""
(() => {
  const evidence = window.__namiConfirmationInputEvidence;
  const dialog = document.querySelector("#execution-confirmation");
  evidence.closingPointerBlocked =
    dialog?.open === true && dialog.dataset.closing === "true" &&
    document.querySelector('.nami-task-card[aria-current="page"]')?.dataset.taskLabel
      === evidence.selectedBeforeBackgroundInput;
  window.__namiConfirmationExitBarrier?.finish();
  delete window.__namiConfirmationExitBarrier;
  return true;
})()
""", lambda _verified: evaluate(
            wait_live_execute, after_live_execute, "wait_live_execute",
        ), "verify_closing"), "closing_background_pointer")

    wait_live_execute = r"""
(async () => {
  for (let attempt = 0; attempt < 1200; attempt += 1) {
    if (window.__namiConfirmationStage === "live-execute-ready") {
      const execute = document.querySelector('.nami-plan-review [data-action="execute"]');
      if (!(execute instanceof HTMLButtonElement)) throw new Error("live Execute missing");
      execute.focus();
      await new Promise((resolve) => requestAnimationFrame(resolve));
      if (document.activeElement !== execute) throw new Error("live Execute did not receive focus");
      const rect = execute.getBoundingClientRect();
      const point = {x: (rect.left + rect.right) / 2, y: (rect.top + rect.bottom) / 2};
      const inViewport = rect.width > 0 && rect.height > 0 &&
        point.x >= 0 && point.x < innerWidth && point.y >= 0 && point.y < innerHeight;
      if (!inViewport || document.elementFromPoint(point.x, point.y) !== execute) {
        throw new Error("live Execute pointer target is not exact");
      }
      window.__namiConfirmationInputEvidence.liveExecuteFocused = true;
      window.__namiConfirmationInputEvidence.liveExecutePointInViewport = true;
      window.__namiConfirmationInputEvidence.liveExecuteHitTested = true;
      return point;
    }
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error("timed out waiting for live Execute readiness");
})()
"""

    wait_live_confirm = r"""
(async () => {
  for (let attempt = 0; attempt < 1200; attempt += 1) {
    if (window.__namiConfirmationStage === "live-confirm-open") {
      const dialog = document.querySelector("#execution-confirmation");
      const confirm = dialog?.querySelector("[data-confirm-execution]");
      if (!(dialog instanceof HTMLDialogElement) || !(confirm instanceof HTMLButtonElement)) {
        throw new Error("live confirmation missing");
      }
      window.__namiConfirmationExitBarrier = dialog.animate(
        [], {duration: 60000},
      );
      window.__namiConfirmationExitBarrier.pause();
      const rect = confirm.getBoundingClientRect();
      return {x: (rect.left + rect.right) / 2, y: (rect.top + rect.bottom) / 2};
    }
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error("timed out waiting for live confirmation");
})()
"""

    def after_live_execute(value: object) -> None:
        if type(value) is not dict:
            raise RuntimeError("live Execute pointer target was not verified")
        dispatch(
            mouse_click(value),
            lambda: evaluate(wait_live_confirm, after_live, "wait_live_confirm"),
            "live_execute_pointer",
        )

    def after_live(value: object) -> None:
        if type(value) is not dict:
            raise RuntimeError("live confirmation geometry was not returned")
        dispatch(key_events("Tab", "Tab", 9), lambda: evaluate(
            "window.__namiConfirmationInputEvidence.liveEnterFocusedConfirm = "
            "document.activeElement?.matches('[data-confirm-execution]') === true; true",
            lambda _focused: dispatch(key_events("Enter", "Enter", 13), lambda: evaluate(
                r"""
(async () => {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    const dialog = document.querySelector("#execution-confirmation");
    if (dialog?.dataset.closing === "true") {
      window.__namiConfirmationInputEvidence.liveEnterConfirmed = true;
      window.__namiConfirmationExitBarrier?.finish();
      delete window.__namiConfirmationExitBarrier;
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  throw new Error("timed out waiting for Enter confirmation");
})()
""",
                lambda _confirmed: None,
                "verify_live_enter",
            ), "live_confirm_enter"),
            "verify_live_confirm_focus",
        ), "live_confirm_tab")

    evaluate(wait_execute, after_execute, "wait_execute")
    return fail


def _begin_probe(
    window: object,
    recorder: _Recorder,
    control: _Control,
    retained: list[object],
    screenshot: Path,
) -> None:
    from System import Action

    native = window.native
    if native.InvokeRequired:
        raise RuntimeError("task-shell probe left the UI thread")
    core = native.browser.webview.CoreWebView2
    starting_stage = control.stage
    script = {
        "initial": _INITIAL_SCRIPT,
        "reinjected": _REINJECTED_SCRIPT,
        "busy": _BUSY_SCRIPT,
        "terminal_first": _TERMINAL_FIRST_SCRIPT,
        "terminal_second": _TERMINAL_SECOND_SCRIPT,
        "plan_review": _PLAN_REVIEW_SCRIPT,
    }[starting_stage]
    settings = json.dumps({"expression": script, "awaitPromise": True, "returnByValue": True})

    task = core.CallDevToolsProtocolMethodAsync("Runtime.evaluate", settings)
    driver_failure = None
    if starting_stage == "plan_review":
        driver_failure = _drive_plan_confirmation(
            native, core, recorder, control, retained, screenshot,
        )

    def completed() -> None:
        def finish() -> None:
            try:
                value = _runtime_value(task)
                if starting_stage == "plan_review" and value != {"complete": True}:
                    raise RuntimeError("final page probe returned invalid evidence")
            except BaseException as error:
                if driver_failure is not None:
                    driver_failure(error, task)
                    return
                if control.stage == starting_stage or starting_stage == "terminal_second":
                    failure_stage = f"page_{starting_stage}"
                    if starting_stage in {"initial", "plan_review"}:
                        failure_stage += f"_{control.checkpoint}"
                    recorder.failure(failure_stage, error)

        finish_action = Action(finish)
        retained.append(finish_action)
        native.BeginInvoke(finish_action)

    completion = Action(completed)
    retained.append(completion)
    task.GetAwaiter().OnCompleted(completion)


def _configure_probe(
    window: object,
    recorder: _Recorder,
    control: _Control,
    retained: list[object],
    screenshot: Path,
    original: Callable[..., object],
    large_window: bool,
    *args: object,
    **kwargs: object,
) -> object:
    controller = original(window, *args, **kwargs)

    def loaded() -> None:
        from System import Action

        if control.stage == "reinjected":
            control.create_gate.set()

        def begin() -> None:
            try:
                if large_window and control.stage == "initial":
                    scale = window.native.DeviceDpi / 96
                    window.native.Width += int(160 * scale)
                    window.native.Height += int(100 * scale)
                _begin_probe(window, recorder, control, retained, screenshot)
            except BaseException as error:
                recorder.failure("page_probe", error)

        action = Action(begin)
        retained.append(action)
        window.native.BeginInvoke(action)

    retained.append(loaded)
    window.events.loaded += loaded
    return controller


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


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--mutex", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--screenshot", required=True, type=Path)
    parser.add_argument("--plan-again-trace", action="store_true")
    parser.add_argument("--large-window", action="store_true")
    return parser.parse_args()


def _run(arguments: argparse.Namespace, recorder: _Recorder) -> int:
    from namisync.interfaces.web import host
    from namisync.interfaces.web.host import DesktopInstanceIdentity
    from namisync.interfaces.web.paths import AppPaths

    plan_again_trace = PlanAgainHostTrace() if arguments.plan_again_trace else None
    control = _Control(recorder, arguments.source, arguments.target, plan_again_trace)
    retained: list[object] = []
    original = host._configure_window_appearance
    original_commands = host._production_commands

    def commands(**kwargs: object) -> object:
        result = original_commands(**kwargs)
        return result if plan_again_trace is None else traced_plan_again_commands(
            result, plan_again_trace,
        )

    def extension(_document: object, registry: object) -> dict[str, object]:
        control.bind(registry)
        return {"task_shell_test_control": _test_spec(control.command)}

    recorder.set("runtime", _runtime_identity())
    with ExitStack() as stack:
        if plan_again_trace is not None:
            stack.enter_context(patch.object(host, "_production_commands", commands))
        stack.enter_context(headed_command_extension(host, extension))
        stack.enter_context(
            patch.object(
                host,
                "_configure_window_appearance",
                lambda window, *args, **kwargs: _configure_probe(
                    window, recorder, control, retained,
                    arguments.screenshot.resolve(), original, arguments.large_window, *args, **kwargs
                ),
            )
        )
        exit_code = host.run_desktop(
            AppPaths.from_root(arguments.data_dir),
            DesktopInstanceIdentity(arguments.mutex, arguments.title),
            startup_error=recorder.startup_error,
        )
    if not recorder.settled:
        recorder.failure("child", RuntimeError("host returned before task-shell evidence completed"))
    recorder.finish(exit_code, host_returned=True)
    return exit_code


def _error_type(error: BaseException) -> str:
    name = type(error).__name__
    return name if name in _FAILURE_TYPES else "Error"


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
